# -*- coding: utf-8 -*-
"""Read-only IBKR API sync service for user-owned portfolio accounts."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Protocol
from urllib.parse import urlparse, urlunparse

import requests

from data_provider.base import canonical_stock_code
from src.services.portfolio_import_service import IBKR_BROKER
from src.services.portfolio_service import PortfolioConflictError, PortfolioService

logger = logging.getLogger(__name__)

IBKR_DEFAULT_API_BASE_URL = "https://localhost:5000/v1/api"
IBKR_SUPPORTED_POSITION_ASSET_CLASSES = {"", "STK", "ETF", "FUND"}


@dataclass(frozen=True)
class IbkrHttpResult:
    status_code: int
    payload: Any


class PortfolioIbkrSyncError(ValueError):
    """Structured, user-safe sync error for IBKR read-only account state sync."""

    def __init__(self, *, code: str, message: str, status_code: int = 400) -> None:
        self.code = str(code or "ibkr_sync_error").strip() or "ibkr_sync_error"
        self.status_code = int(status_code or 400)
        super().__init__(str(message or "IBKR sync failed").strip() or "IBKR sync failed")


class IbkrHttpTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]],
        verify: bool,
        timeout: int,
    ) -> IbkrHttpResult:
        ...


class RequestsIbkrHttpTransport:
    """HTTP transport backed by requests for production use."""

    def get(
        self,
        url: str,
        *,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]],
        verify: bool,
        timeout: int,
    ) -> IbkrHttpResult:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            verify=verify,
            timeout=timeout,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        return IbkrHttpResult(status_code=int(response.status_code), payload=payload)


class IbkrApiClient:
    """Minimal Client Portal Web API client for read-only portfolio endpoints."""

    def __init__(
        self,
        *,
        session_token: str,
        base_url: str,
        verify_ssl: bool,
        transport: Optional[IbkrHttpTransport] = None,
        timeout_seconds: int = 20,
    ) -> None:
        self.base_url = PortfolioIbkrSyncService.normalize_api_base_url(base_url)
        self.verify_ssl = bool(verify_ssl)
        self.timeout_seconds = max(5, int(timeout_seconds))
        self.transport = transport or RequestsIbkrHttpTransport()
        self.headers = {
            "Accept": "application/json",
            "Cookie": f"api={session_token}",
        }

    def list_accounts(self) -> List[Dict[str, Any]]:
        payload = self._get_json("/portfolio/accounts")
        if not isinstance(payload, list):
            raise PortfolioIbkrSyncError(
                code="ibkr_payload_unsupported",
                message="IBKR /portfolio/accounts 返回了当前版本不支持的数据结构，请改用 Flex 导入或更新适配器后再试。",
            )
        return [item for item in payload if isinstance(item, dict)]

    def get_account_summary(self, account_id: str) -> Dict[str, Any]:
        payload = self._get_json(f"/portfolio/{account_id}/summary")
        if not isinstance(payload, dict):
            raise PortfolioIbkrSyncError(
                code="ibkr_payload_unsupported",
                message="IBKR 账户摘要返回了当前版本不支持的数据结构，请改用 Flex 导入或更新适配器后再试。",
            )
        return payload

    def get_account_ledger(self, account_id: str) -> Dict[str, Any]:
        payload = self._get_json(f"/portfolio/{account_id}/ledger")
        if not isinstance(payload, dict):
            raise PortfolioIbkrSyncError(
                code="ibkr_payload_unsupported",
                message="IBKR 现金账本返回了当前版本不支持的数据结构，请改用 Flex 导入或更新适配器后再试。",
            )
        return payload

    def list_positions(self, account_id: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for page_id in range(20):
            payload = self._get_json(f"/portfolio/{account_id}/positions/{page_id}")
            rows = self._extract_position_rows(payload)
            if not rows:
                break
            items.extend(rows)
            if len(rows) < 100:
                break
        return items

    def _get_json(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        result = self.transport.get(
            url,
            headers=self.headers,
            params=params,
            verify=self.verify_ssl,
            timeout=self.timeout_seconds,
        )
        if result.status_code >= 400:
            self._raise_http_error(path=path, result=result)
        return result.payload

    @staticmethod
    def _extract_position_rows(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            rows = [item for item in payload if isinstance(item, dict)]
            if payload and not rows:
                raise PortfolioIbkrSyncError(
                    code="ibkr_payload_unsupported",
                    message="IBKR 持仓接口返回了无法识别的列表结构，当前版本无法安全同步。",
                )
            return rows
        if isinstance(payload, dict):
            for key in ("positions", "items", "data", "result"):
                rows = payload.get(key)
                if isinstance(rows, list):
                    valid_rows = [item for item in rows if isinstance(item, dict)]
                    if rows and not valid_rows:
                        raise PortfolioIbkrSyncError(
                            code="ibkr_payload_unsupported",
                            message="IBKR 持仓接口返回了无法识别的条目结构，当前版本无法安全同步。",
                        )
                    return valid_rows
        raise PortfolioIbkrSyncError(
            code="ibkr_payload_unsupported",
            message="IBKR 持仓接口返回了当前版本不支持的数据结构，请改用 Flex 导入或更新适配器后再试。",
        )

    @staticmethod
    def _payload_text(payload: Any) -> str:
        if isinstance(payload, dict):
            for key in ("message", "error", "detail"):
                value = payload.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()
            return json.dumps(payload, ensure_ascii=False, sort_keys=True)[:255]
        if payload is None:
            return ""
        return str(payload).strip()[:255]

    def _raise_http_error(self, *, path: str, result: IbkrHttpResult) -> None:
        detail = self._payload_text(result.payload).lower()
        if result.status_code in {401, 403}:
            raise PortfolioIbkrSyncError(
                code="ibkr_session_expired",
                message="当前 IBKR session 已失效、未授权或未连上可访问账户，请在 Client Portal / Gateway 中重新建立只读会话后再试。",
                status_code=400,
            )
        if result.status_code == 404:
            raise PortfolioIbkrSyncError(
                code="ibkr_payload_unsupported",
                message="当前 IBKR session 下找不到所需账户数据，请确认 broker account ref、API base URL 与当前只读会话是否匹配。",
                status_code=400,
            )
        if result.status_code == 400 and "account" in detail:
            raise PortfolioIbkrSyncError(
                code="ibkr_account_not_found",
                message="IBKR 未返回所选账户的有效只读数据，请确认 broker account ref 与当前会话匹配。",
                status_code=400,
            )
        raise PortfolioIbkrSyncError(
            code="ibkr_upstream_error",
            message="IBKR 只读接口暂时返回异常，请稍后重试或检查本地 Client Portal 会话。",
            status_code=400,
        )


class PortfolioIbkrSyncService:
    """Manual, read-only IBKR sync that stores current-state overlays per user."""

    def __init__(
        self,
        *,
        portfolio_service: Optional[PortfolioService] = None,
        transport: Optional[IbkrHttpTransport] = None,
        timeout_seconds: int = 20,
    ) -> None:
        self.portfolio_service = portfolio_service or PortfolioService()
        self.transport = transport
        self.timeout_seconds = max(5, int(timeout_seconds))

    def sync_read_only_account_state(
        self,
        *,
        account_id: int,
        session_token: str,
        broker_connection_id: Optional[int] = None,
        broker_account_ref: Optional[str] = None,
        api_base_url: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
    ) -> Dict[str, Any]:
        account = self.portfolio_service.get_account(account_id, include_inactive=False)
        if account is None:
            raise ValueError(f"Active account not found: {account_id}")

        session_token_norm = self._normalize_session_token(session_token)
        existing_connection = self._resolve_existing_connection(
            account_id=account_id,
            broker_connection_id=broker_connection_id,
        )
        remote_account_hint = (
            self._normalize_account_ref(broker_account_ref)
            or self._normalize_account_ref((existing_connection or {}).get("broker_account_ref"))
        )
        sync_defaults = self._resolve_connection_sync_defaults(
            connection=existing_connection,
            api_base_url=api_base_url,
            verify_ssl=verify_ssl,
        )
        client = IbkrApiClient(
            session_token=session_token_norm,
            base_url=sync_defaults["api_base_url"],
            verify_ssl=sync_defaults["verify_ssl"],
            transport=self.transport,
            timeout_seconds=self.timeout_seconds,
        )

        remote_accounts = client.list_accounts()
        remote_account = self._select_remote_account(remote_accounts, broker_account_ref=remote_account_hint)
        remote_account_ref = self._extract_remote_account_ref(remote_account)
        connection, used_existing_connection = self._resolve_or_create_connection(
            account_id=account_id,
            existing_connection=existing_connection,
            remote_account_ref=remote_account_ref,
            sync_defaults=sync_defaults,
        )

        try:
            summary = client.get_account_summary(remote_account_ref)
            ledger = client.get_account_ledger(remote_account_ref)
            positions = client.list_positions(remote_account_ref)
            normalized = self._normalize_ibkr_sync_payload(
                account=account,
                remote_account=remote_account,
                summary=summary,
                ledger=ledger,
                positions=positions,
            )
            self._apply_account_alignment(
                account_id=account_id,
                account=account,
                base_currency=normalized["base_currency"],
                position_markets=normalized["position_markets"],
            )

            self.portfolio_service.replace_broker_sync_state(
                broker_connection_id=int(connection["id"]),
                portfolio_account_id=account_id,
                broker_type=IBKR_BROKER,
                broker_account_ref=remote_account_ref,
                sync_source="api",
                sync_status="success",
                snapshot_date=normalized["snapshot_date"],
                synced_at=normalized["synced_at"],
                base_currency=normalized["base_currency"],
                total_cash=normalized["total_cash"],
                total_market_value=normalized["total_market_value"],
                total_equity=normalized["total_equity"],
                realized_pnl=normalized["realized_pnl"],
                unrealized_pnl=normalized["unrealized_pnl"],
                fx_stale=normalized["fx_stale"],
                payload=normalized["payload"],
                positions=normalized["positions"],
                cash_balances=normalized["cash_balances"],
            )
            updated_connection = self.portfolio_service.mark_broker_connection_synced(
                int(connection["id"]),
                sync_source="api",
                sync_status="success",
                sync_metadata={
                    "ibkr_api": self._build_ibkr_sync_metadata(
                        existing=connection.get("sync_metadata"),
                        api_base_url=sync_defaults["api_base_url"],
                        verify_ssl=sync_defaults["verify_ssl"],
                        broker_account_ref=remote_account_ref,
                        base_currency=normalized["base_currency"],
                        position_count=len(normalized["positions"]),
                        cash_balance_count=len(normalized["cash_balances"]),
                    )
                },
            ) or connection
        except PortfolioConflictError as exc:
            self._mark_connection_sync_error(
                connection=connection,
                sync_defaults=sync_defaults,
                remote_account_ref=remote_account_ref,
                exc=exc,
            )
            raise PortfolioIbkrSyncError(
                code="ibkr_account_mapping_conflict",
                message="当前 IBKR 账户映射与已有持仓账户绑定冲突，请确认 broker account ref 是否已经绑定到另一账户。",
                status_code=409,
            ) from exc
        except Exception as exc:
            self._mark_connection_sync_error(
                connection=connection,
                sync_defaults=sync_defaults,
                remote_account_ref=remote_account_ref,
                exc=exc,
            )
            raise
        return {
            "account_id": int(account_id),
            "broker_connection_id": int(updated_connection["id"]),
            "broker_account_ref": remote_account_ref,
            "connection_name": str(updated_connection["connection_name"]),
            "snapshot_date": normalized["snapshot_date"].isoformat(),
            "synced_at": normalized["synced_at"].isoformat(),
            "base_currency": normalized["base_currency"],
            "total_cash": round(normalized["total_cash"], 6),
            "total_market_value": round(normalized["total_market_value"], 6),
            "total_equity": round(normalized["total_equity"], 6),
            "realized_pnl": round(normalized["realized_pnl"], 6),
            "unrealized_pnl": round(normalized["unrealized_pnl"], 6),
            "position_count": len(normalized["positions"]),
            "cash_balance_count": len(normalized["cash_balances"]),
            "fx_stale": bool(normalized["fx_stale"]),
            "snapshot_overlay_active": True,
            "used_existing_connection": bool(used_existing_connection),
            "api_base_url": sync_defaults["api_base_url"],
            "verify_ssl": bool(sync_defaults["verify_ssl"]),
            "warnings": list(normalized["warnings"]),
        }

    def _resolve_existing_connection(
        self,
        *,
        account_id: int,
        broker_connection_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        if broker_connection_id is None:
            return None
        connection = self.portfolio_service.get_broker_connection(int(broker_connection_id))
        if connection is None:
            raise PortfolioIbkrSyncError(
                code="ibkr_connection_not_found",
                message=f"未找到可用的 IBKR connection：{broker_connection_id}",
            )
        if int(connection["portfolio_account_id"]) != int(account_id):
            raise PortfolioIbkrSyncError(
                code="ibkr_account_mapping_conflict",
                message="所选 IBKR connection 不属于当前持仓账户，请切换到正确账户后再试。",
                status_code=409,
            )
        if str(connection.get("broker_type") or "").strip().lower() != IBKR_BROKER:
            raise PortfolioIbkrSyncError(
                code="ibkr_connection_type_invalid",
                message="所选 broker connection 不是 IBKR 类型，无法用于 IBKR 只读同步。",
            )
        return connection

    def _resolve_connection_sync_defaults(
        self,
        *,
        connection: Optional[Dict[str, Any]],
        api_base_url: Optional[str],
        verify_ssl: Optional[bool],
    ) -> Dict[str, Any]:
        existing = self._extract_ibkr_api_config((connection or {}).get("sync_metadata"))
        resolved_base_url = self.normalize_api_base_url(
            api_base_url or existing.get("api_base_url") or IBKR_DEFAULT_API_BASE_URL
        )
        if verify_ssl is None:
            if isinstance(existing.get("verify_ssl"), bool):
                resolved_verify_ssl = bool(existing["verify_ssl"])
            else:
                resolved_verify_ssl = not self._is_localhost_url(resolved_base_url)
        else:
            resolved_verify_ssl = bool(verify_ssl)
        return {
            "api_base_url": resolved_base_url,
            "verify_ssl": resolved_verify_ssl,
        }

    def _select_remote_account(
        self,
        accounts: List[Dict[str, Any]],
        *,
        broker_account_ref: Optional[str],
    ) -> Dict[str, Any]:
        valid_accounts: List[tuple[str, Dict[str, Any]]] = []
        for item in accounts:
            try:
                valid_accounts.append((self._extract_remote_account_ref(item), item))
            except PortfolioIbkrSyncError:
                continue
        if not valid_accounts:
            if accounts:
                raise PortfolioIbkrSyncError(
                    code="ibkr_account_identifier_invalid",
                    message="IBKR /portfolio/accounts 未返回可识别的 account identifier，当前版本无法继续同步。",
                )
            raise PortfolioIbkrSyncError(
                code="ibkr_empty_accounts",
                message="当前 IBKR session 下没有可访问账户，请确认 Client Portal / Gateway 会话已登录并暴露账户元数据。",
            )
        if broker_account_ref:
            for account_ref, item in valid_accounts:
                if account_ref == broker_account_ref:
                    return item
            raise PortfolioIbkrSyncError(
                code="ibkr_account_not_found",
                message=f"当前 IBKR session 下找不到 broker account ref={broker_account_ref} 对应的账户，请确认映射是否正确。",
            )
        if len(valid_accounts) == 1:
            return valid_accounts[0][1]
        raise PortfolioIbkrSyncError(
            code="ibkr_account_ambiguous",
            message="当前 IBKR session 暴露了多个账户；请显式填写 broker account ref，或复用已绑定的 connection 后再试。",
        )

    def _resolve_or_create_connection(
        self,
        *,
        account_id: int,
        existing_connection: Optional[Dict[str, Any]],
        remote_account_ref: str,
        sync_defaults: Dict[str, Any],
    ) -> tuple[Dict[str, Any], bool]:
        if existing_connection is not None:
            next_metadata = self._build_ibkr_sync_metadata(
                existing=existing_connection.get("sync_metadata"),
                api_base_url=sync_defaults["api_base_url"],
                verify_ssl=sync_defaults["verify_ssl"],
                broker_account_ref=remote_account_ref,
            )
            updated = self.portfolio_service.update_broker_connection(
                int(existing_connection["id"]),
                broker_name="Interactive Brokers",
                broker_account_ref=remote_account_ref,
                sync_metadata=self._merge_connection_sync_metadata(existing_connection, next_metadata),
            )
            return updated or existing_connection, True

        linked = self.portfolio_service.get_broker_connection_by_ref(
            broker_type=IBKR_BROKER,
            broker_account_ref=remote_account_ref,
        )
        if linked is not None:
            if int(linked["portfolio_account_id"]) != int(account_id):
                raise PortfolioIbkrSyncError(
                    code="ibkr_account_mapping_conflict",
                    message="该 broker account ref 已经绑定到当前用户的另一持仓账户，请先确认账户映射再同步。",
                    status_code=409,
                )
            next_metadata = self._build_ibkr_sync_metadata(
                existing=linked.get("sync_metadata"),
                api_base_url=sync_defaults["api_base_url"],
                verify_ssl=sync_defaults["verify_ssl"],
                broker_account_ref=remote_account_ref,
            )
            updated = self.portfolio_service.update_broker_connection(
                int(linked["id"]),
                broker_name="Interactive Brokers",
                sync_metadata=self._merge_connection_sync_metadata(linked, next_metadata),
            )
            return updated or linked, True

        account_connections = self.portfolio_service.list_broker_connections(
            portfolio_account_id=account_id,
            broker_type=IBKR_BROKER,
        )
        if len(account_connections) == 1 and not account_connections[0].get("broker_account_ref"):
            next_metadata = self._build_ibkr_sync_metadata(
                existing=account_connections[0].get("sync_metadata"),
                api_base_url=sync_defaults["api_base_url"],
                verify_ssl=sync_defaults["verify_ssl"],
                broker_account_ref=remote_account_ref,
            )
            updated = self.portfolio_service.update_broker_connection(
                int(account_connections[0]["id"]),
                broker_name="Interactive Brokers",
                broker_account_ref=remote_account_ref,
                sync_metadata=self._merge_connection_sync_metadata(account_connections[0], next_metadata),
            )
            return updated or account_connections[0], True

        created = self.portfolio_service.create_broker_connection(
            portfolio_account_id=account_id,
            broker_type=IBKR_BROKER,
            broker_name="Interactive Brokers",
            connection_name=f"IBKR {remote_account_ref}"[:64],
            broker_account_ref=remote_account_ref,
            import_mode="api",
            sync_metadata={
                "ibkr_api": self._build_ibkr_sync_metadata(
                    existing=None,
                    api_base_url=sync_defaults["api_base_url"],
                    verify_ssl=sync_defaults["verify_ssl"],
                    broker_account_ref=remote_account_ref,
                )
            },
        )
        return created, False

    def _normalize_ibkr_sync_payload(
        self,
        *,
        account: Dict[str, Any],
        remote_account: Dict[str, Any],
        summary: Dict[str, Any],
        ledger: Dict[str, Any],
        positions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        synced_at = datetime.now()
        snapshot_date = synced_at.date()
        base_currency = self._normalize_currency(
            remote_account.get("currency")
            or self._summary_text(summary, "currency")
            or account.get("base_currency")
            or "USD"
        )

        cash_rows, cash_total_base, cash_fx_stale = self._normalize_ledger_balances(
            ledger=ledger,
            base_currency=base_currency,
            as_of_date=snapshot_date,
        )
        position_rows, position_total_base, unrealized_total_base, position_fx_stale, warnings, markets = (
            self._normalize_positions(
                positions=positions,
                base_currency=base_currency,
                as_of_date=snapshot_date,
            )
        )
        if not positions:
            warnings.append("IBKR 当前未返回持仓，系统已按空持仓完成同步。")
        if not cash_rows:
            warnings.append("IBKR 当前未返回现金余额明细，系统已按空余额或摘要回退口径处理。")

        total_cash = self._summary_amount(summary, "totalcashvalue", "settledcash")
        if total_cash is None:
            total_cash = cash_total_base
            warnings.append("IBKR 摘要中缺少总现金字段，已根据 ledger 明细回退计算。")
        total_market_value = self._summary_amount(summary, "stockmarketvalue", "netstockmarketvalue")
        if total_market_value is None:
            total_market_value = position_total_base
            warnings.append("IBKR 摘要中缺少持仓市值字段，已根据持仓明细回退计算。")
        total_equity = self._summary_amount(summary, "netliquidation")
        if total_equity is None:
            total_equity = total_cash + total_market_value
            warnings.append("IBKR 摘要中缺少总权益字段，已按现金加市值回退计算。")
        realized_pnl = self._summary_amount(summary, "realizedpnl")
        if realized_pnl is None:
            realized_pnl = 0.0
        unrealized_pnl = self._summary_amount(summary, "unrealizedpnl")
        if unrealized_pnl is None:
            unrealized_pnl = unrealized_total_base
            if position_rows:
                warnings.append("IBKR 摘要中缺少未实现盈亏字段，已根据持仓明细回退计算。")

        return {
            "snapshot_date": snapshot_date,
            "synced_at": synced_at,
            "base_currency": base_currency,
            "total_cash": float(total_cash),
            "total_market_value": float(total_market_value),
            "total_equity": float(total_equity),
            "realized_pnl": float(realized_pnl),
            "unrealized_pnl": float(unrealized_pnl),
            "positions": position_rows,
            "cash_balances": cash_rows,
            "fx_stale": bool(cash_fx_stale or position_fx_stale),
            "warnings": warnings,
            "position_markets": markets,
            "payload": {
                "remote_account": {
                    "account_id": self._extract_remote_account_ref(remote_account),
                    "display_name": remote_account.get("displayName") or remote_account.get("desc"),
                    "currency": base_currency,
                },
                "summary": summary,
                "ledger": ledger,
                "position_count": len(position_rows),
                "cash_balance_count": len(cash_rows),
            },
        }

    def _normalize_ledger_balances(
        self,
        *,
        ledger: Dict[str, Any],
        base_currency: str,
        as_of_date: date,
    ) -> tuple[List[Dict[str, Any]], float, bool]:
        rows: List[Dict[str, Any]] = []
        total_base = 0.0
        fx_stale = False
        explicit_base_present = False
        base_fallback_amount: Optional[float] = None

        for currency_key, block in ledger.items():
            if not isinstance(block, dict):
                continue
            raw_amount = self._pick_first_numeric(
                block,
                "cashbalance",
                "settledcash",
                "endingcash",
                "cash",
            )
            if raw_amount is None:
                continue
            if str(currency_key or "").strip().upper() == "BASE":
                base_fallback_amount = float(raw_amount)
                continue
            currency = self._normalize_currency(currency_key)
            if currency == base_currency:
                explicit_base_present = True
            amount_base, stale, _ = self.portfolio_service.convert_amount(
                amount=float(raw_amount),
                from_currency=currency,
                to_currency=base_currency,
                as_of_date=as_of_date,
            )
            rows.append(
                {
                    "currency": currency,
                    "amount": float(raw_amount),
                    "amount_base": float(amount_base),
                }
            )
            total_base += float(amount_base)
            fx_stale = fx_stale or stale

        if not explicit_base_present and base_fallback_amount is not None:
            rows.append(
                {
                    "currency": base_currency,
                    "amount": float(base_fallback_amount),
                    "amount_base": float(base_fallback_amount),
                }
            )
            total_base += float(base_fallback_amount)

        rows.sort(key=lambda item: item["currency"])
        return rows, float(total_base), bool(fx_stale)

    def _normalize_positions(
        self,
        *,
        positions: Iterable[Dict[str, Any]],
        base_currency: str,
        as_of_date: date,
    ) -> tuple[List[Dict[str, Any]], float, float, bool, List[str], List[str]]:
        rows: List[Dict[str, Any]] = []
        warnings: List[str] = []
        total_market_value_base = 0.0
        total_unrealized_base = 0.0
        fx_stale = False
        markets: set[str] = set()

        for item in positions:
            asset_class = str(
                item.get("assetClass")
                or item.get("asset_class")
                or item.get("secType")
                or ""
            ).strip().upper()
            if asset_class not in IBKR_SUPPORTED_POSITION_ASSET_CLASSES:
                warnings.append(f"Skipped unsupported IBKR asset class: {asset_class or 'unknown'}")
                continue

            quantity = self._to_float(item.get("position"))
            if quantity is None or abs(quantity) <= 1e-8:
                continue
            if quantity < 0:
                symbol_hint = item.get("contractDesc") or item.get("symbol") or item.get("ticker") or "unknown"
                warnings.append(f"Skipped short position for {symbol_hint} in read-only sync")
                continue

            market = self._infer_position_market(item)
            raw_symbol = (
                item.get("ticker")
                or item.get("symbol")
                or item.get("contractDesc")
                or item.get("description")
                or item.get("localSymbol")
            )
            symbol = self._normalize_position_symbol(raw_symbol, market=market)
            if not symbol:
                warnings.append("Skipped IBKR position with missing symbol")
                continue

            currency = self._normalize_currency(item.get("currency") or self._default_currency_for_market(market))
            avg_cost = self._to_float(item.get("avgCost")) or self._to_float(item.get("avgPrice")) or 0.0
            last_price = self._to_float(item.get("mktPrice")) or self._to_float(item.get("marketPrice")) or 0.0
            market_value_local = self._to_float(item.get("mktValue")) or self._to_float(item.get("marketValue"))
            if market_value_local is None:
                market_value_local = float(quantity) * float(last_price or avg_cost)
            if last_price <= 0 and abs(quantity) > 1e-8:
                last_price = float(market_value_local) / float(quantity)
            unrealized_local = self._to_float(item.get("unrealizedPnl")) or self._to_float(item.get("upl")) or 0.0

            market_value_base, stale_mv, _ = self.portfolio_service.convert_amount(
                amount=float(market_value_local),
                from_currency=currency,
                to_currency=base_currency,
                as_of_date=as_of_date,
            )
            unrealized_base, stale_upnl, _ = self.portfolio_service.convert_amount(
                amount=float(unrealized_local),
                from_currency=currency,
                to_currency=base_currency,
                as_of_date=as_of_date,
            )
            rows.append(
                {
                    "broker_position_ref": str(item.get("conid") or "").strip() or None,
                    "symbol": symbol,
                    "market": market,
                    "currency": currency,
                    "quantity": float(quantity),
                    "avg_cost": float(avg_cost),
                    "last_price": float(last_price),
                    "market_value_base": float(market_value_base),
                    "unrealized_pnl_base": float(unrealized_base),
                    "valuation_currency": base_currency,
                    "payload_json": json.dumps(
                        {
                            "conid": item.get("conid"),
                            "contract_desc": item.get("contractDesc"),
                            "currency": currency,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                }
            )
            total_market_value_base += float(market_value_base)
            total_unrealized_base += float(unrealized_base)
            fx_stale = fx_stale or stale_mv or stale_upnl
            markets.add(market)

        rows.sort(key=lambda item: (item["market"], item["symbol"], item["currency"]))
        return rows, float(total_market_value_base), float(total_unrealized_base), bool(fx_stale), warnings[:20], sorted(markets)

    def _apply_account_alignment(
        self,
        *,
        account_id: int,
        account: Dict[str, Any],
        base_currency: str,
        position_markets: List[str],
    ) -> None:
        updates: Dict[str, Any] = {}
        current_broker = str(account.get("broker") or "").strip()
        if not current_broker:
            updates["broker"] = "IBKR"
        current_base_currency = self._normalize_currency(account.get("base_currency") or "CNY")
        if current_base_currency != base_currency:
            updates["base_currency"] = base_currency

        if len(position_markets) > 1:
            next_market = "global"
        elif len(position_markets) == 1:
            next_market = position_markets[0]
        else:
            next_market = str(account.get("market") or "global").strip().lower() or "global"
        current_market = str(account.get("market") or "").strip().lower() or "cn"
        if current_market != next_market:
            updates["market"] = next_market

        if updates:
            self.portfolio_service.update_account(account_id, **updates)

    @staticmethod
    def normalize_api_base_url(value: str) -> str:
        text = str(value or "").strip() or IBKR_DEFAULT_API_BASE_URL
        if "://" not in text:
            text = f"https://{text}"
        parsed = urlparse(text)
        path = parsed.path.rstrip("/")
        if path.endswith("/v1/api"):
            normalized_path = path
        elif path.endswith("/v1"):
            normalized_path = f"{path}/api"
        elif path.endswith("/api"):
            normalized_path = path
        elif path:
            normalized_path = f"{path}/v1/api"
        else:
            normalized_path = "/v1/api"
        return urlunparse((parsed.scheme or "https", parsed.netloc, normalized_path, "", "", ""))

    @staticmethod
    def _is_localhost_url(value: str) -> bool:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").strip().lower()
        return hostname in {"localhost", "127.0.0.1", "::1"}

    @staticmethod
    def _normalize_session_token(value: str) -> str:
        token = str(value or "").strip()
        if not token:
            raise PortfolioIbkrSyncError(
                code="ibkr_session_required",
                message="请提供当前有效的 IBKR session token，再执行只读同步。",
            )
        if len(token) > 512:
            raise PortfolioIbkrSyncError(
                code="ibkr_session_invalid",
                message="当前 IBKR session token 长度异常，请重新复制有效 token 后再试。",
            )
        return token

    @staticmethod
    def _normalize_account_ref(value: Any) -> Optional[str]:
        text = str(value or "").strip().upper()
        return text[:128] or None

    @staticmethod
    def _extract_remote_account_ref(item: Dict[str, Any]) -> str:
        for key in ("accountId", "id", "accountVan", "account"):
            value = str(item.get(key) or "").strip()
            if value:
                return value.upper()[:128]
        raise PortfolioIbkrSyncError(
            code="ibkr_account_identifier_invalid",
            message="IBKR /portfolio/accounts 未返回受支持的 account identifier 字段。",
        )

    @staticmethod
    def _extract_ibkr_api_config(sync_metadata: Any) -> Dict[str, Any]:
        if not isinstance(sync_metadata, dict):
            return {}
        nested = sync_metadata.get("ibkr_api")
        if isinstance(nested, dict):
            return dict(nested)
        return {}

    def _build_ibkr_sync_metadata(
        self,
        *,
        existing: Any,
        api_base_url: str,
        verify_ssl: bool,
        broker_account_ref: str,
        base_currency: Optional[str] = None,
        position_count: Optional[int] = None,
        cash_balance_count: Optional[int] = None,
        last_sync_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        metadata = self._extract_ibkr_api_config(existing)
        metadata.update(
            {
                "auth_mode": "session_token",
                "api_base_url": self.normalize_api_base_url(api_base_url),
                "verify_ssl": bool(verify_ssl),
                "broker_account_ref": broker_account_ref,
                "sync_scope": "account_state",
            }
        )
        if base_currency:
            metadata["base_currency"] = self._normalize_currency(base_currency)
        if position_count is not None:
            metadata["position_count"] = int(position_count)
        if cash_balance_count is not None:
            metadata["cash_balance_count"] = int(cash_balance_count)
        if last_sync_error:
            metadata["last_sync_error"] = str(last_sync_error)[:255]
        else:
            metadata.pop("last_sync_error", None)
        return metadata

    def _merge_connection_sync_metadata(
        self,
        connection: Optional[Dict[str, Any]],
        ibkr_api_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = dict((connection or {}).get("sync_metadata") or {})
        merged["ibkr_api"] = ibkr_api_metadata
        return merged

    def _infer_position_market(self, item: Dict[str, Any]) -> str:
        explicit = str(item.get("countryCode") or item.get("country_code") or "").strip().upper()
        if explicit in {"HK", "HKG"}:
            return "hk"
        if explicit in {"CN", "CHN"}:
            return "cn"
        if explicit in {"US", "USA"}:
            return "us"

        exchange = " ".join(
            [
                str(item.get("listingExchange") or ""),
                str(item.get("exchange") or ""),
                str(item.get("listing_exchange") or ""),
            ]
        ).upper()
        if any(token in exchange for token in ("SEHK", "HKEX", ".HK")):
            return "hk"
        if any(token in exchange for token in ("SSE", "SZSE", "SHSE", "XSHE")):
            return "cn"

        raw_symbol = str(
            item.get("ticker")
            or item.get("symbol")
            or item.get("contractDesc")
            or item.get("localSymbol")
            or ""
        ).strip().upper()
        if raw_symbol.startswith("HK") or re.fullmatch(r"\d{1,5}(\.HK)?", raw_symbol):
            return "hk"
        if raw_symbol.isdigit() and len(raw_symbol) == 6:
            return "cn"
        currency = self._normalize_currency(item.get("currency") or "USD")
        if currency == "HKD":
            return "hk"
        if currency == "CNY":
            return "cn"
        return "us"

    def _normalize_position_symbol(self, value: Any, *, market: str) -> str:
        text = str(value or "").strip().upper()
        if not text:
            return ""
        text = text.replace(" ", "")
        if market == "hk":
            if re.fullmatch(r"\d{1,5}", text):
                return canonical_stock_code(f"HK{text.zfill(5)}")
            if re.fullmatch(r"\d{1,5}\.HK", text):
                return canonical_stock_code(text)
            if text.startswith("HK"):
                return canonical_stock_code(text)
        return canonical_stock_code(text)

    @staticmethod
    def _summary_text(summary: Dict[str, Any], key: str) -> Optional[str]:
        block = summary.get(key)
        if isinstance(block, dict):
            for candidate in ("currency", "text", "value"):
                value = block.get(candidate)
                if value is not None and str(value).strip():
                    return str(value).strip()
        if block is not None and str(block).strip():
            return str(block).strip()
        return None

    def _summary_amount(self, summary: Dict[str, Any], *keys: str) -> Optional[float]:
        for key in keys:
            block = summary.get(key)
            amount = self._pick_amount_from_block(block)
            if amount is not None:
                return amount
        return None

    def _pick_amount_from_block(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return self._to_float(value)
        if isinstance(value, dict):
            return self._pick_first_numeric(
                value,
                "amount",
                "value",
                "current",
                "rawValue",
            )
        return None

    @staticmethod
    def _pick_first_numeric(block: Dict[str, Any], *keys: str) -> Optional[float]:
        for key in keys:
            value = block.get(key)
            numeric = PortfolioIbkrSyncService._to_float(value)
            if numeric is not None:
                return numeric
        return None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if not text or text.lower() == "nan":
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _normalize_currency(value: Any) -> str:
        currency = str(value or "").strip().upper()
        if not currency:
            raise PortfolioIbkrSyncError(
                code="ibkr_payload_unsupported",
                message="IBKR 返回了缺少 currency 的关键字段，当前版本无法安全同步该 payload。",
            )
        return currency[:8]

    def _mark_connection_sync_error(
        self,
        *,
        connection: Dict[str, Any],
        sync_defaults: Dict[str, Any],
        remote_account_ref: str,
        exc: Exception,
    ) -> None:
        try:
            safe_error = str(exc) if isinstance(exc, PortfolioIbkrSyncError) else "Unexpected IBKR sync error"
            self.portfolio_service.mark_broker_connection_synced(
                int(connection["id"]),
                sync_source="api",
                sync_status="error",
                sync_metadata={
                    "ibkr_api": self._build_ibkr_sync_metadata(
                        existing=connection.get("sync_metadata"),
                        api_base_url=sync_defaults["api_base_url"],
                        verify_ssl=sync_defaults["verify_ssl"],
                        broker_account_ref=remote_account_ref,
                        last_sync_error=safe_error,
                    )
                },
            )
        except Exception as mark_exc:  # pragma: no cover - defensive path
            logger.warning("Failed to persist IBKR sync error metadata: %s", mark_exc, exc_info=True)

    @staticmethod
    def _default_currency_for_market(market: str) -> str:
        if market == "hk":
            return "HKD"
        if market == "us":
            return "USD"
        return "CNY"
