# -*- coding: utf-8 -*-
"""Portfolio service for P0 account/events/snapshot workflow."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from data_provider.base import canonical_stock_code
from src.config import get_config
from src.repositories.portfolio_repo import (
    DuplicateBrokerConnectionRefError,
    DuplicateTradeDedupHashError,
    DuplicateTradeUidError,
    PortfolioBusyError as RepoPortfolioBusyError,
    PortfolioRepository,
)

logger = logging.getLogger(__name__)

PortfolioBusyError = RepoPortfolioBusyError

try:
    import yfinance as yf
except Exception:  # pragma: no cover - optional dependency path
    yf = None

EPS = 1e-8
VALID_ACCOUNT_MARKETS = {"cn", "hk", "us", "global"}
VALID_EVENT_MARKETS = {"cn", "hk", "us"}
VALID_COST_METHODS = {"fifo", "avg"}
VALID_SIDES = {"buy", "sell"}
VALID_CASH_DIRECTIONS = {"in", "out"}
VALID_CORPORATE_ACTIONS = {"cash_dividend", "split_adjustment"}
VALID_BROKER_CONNECTION_STATUSES = {"active", "disabled", "error"}
VALID_BROKER_IMPORT_MODES = {"file", "manual", "api"}
PORTFOLIO_FX_REFRESH_DISABLED_REASON = "portfolio_fx_update_disabled"


class PortfolioConflictError(Exception):
    """Raised when request conflicts with existing portfolio state."""


class PortfolioOversellError(ValueError):
    """Raised when a sell would exceed the available position quantity."""

    def __init__(
        self,
        *,
        symbol: str,
        trade_date: Optional[date],
        requested_quantity: float,
        available_quantity: float,
    ) -> None:
        self.symbol = symbol
        self.trade_date = trade_date
        self.requested_quantity = float(requested_quantity)
        self.available_quantity = max(0.0, float(available_quantity))
        date_hint = f" on {trade_date.isoformat()}" if trade_date is not None else ""
        super().__init__(
            "Oversell detected for "
            f"{symbol}{date_hint}: requested={round(self.requested_quantity, 8)}, "
            f"available={round(self.available_quantity, 8)}"
        )


@dataclass
class _AvgState:
    quantity: float = 0.0
    total_cost: float = 0.0


class PortfolioService:
    """Business logic for account CRUD, event writes, and snapshot replay."""

    def __init__(
        self,
        repo: Optional[PortfolioRepository] = None,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ):
        self.repo = repo or PortfolioRepository()
        self.owner_id = owner_id
        self.include_all_owners = bool(include_all_owners)

    def _owner_kwargs(self) -> Dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "include_all_owners": self.include_all_owners,
        }

    def _resolve_owner_id(self, owner_id: Optional[str] = None) -> str:
        return self.repo.db.require_user_id(self.owner_id if owner_id is None else owner_id)

    # ------------------------------------------------------------------
    # Account CRUD
    # ------------------------------------------------------------------
    def create_account(
        self,
        *,
        name: str,
        broker: Optional[str],
        market: str,
        base_currency: str,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        name_norm = (name or "").strip()
        if not name_norm:
            raise ValueError("name is required")
        market_norm = self._normalize_account_market(market)
        base_currency_norm = self._normalize_currency(base_currency)
        row = self.repo.create_account(
            name=name_norm,
            broker=(broker or "").strip() or None,
            market=market_norm,
            base_currency=base_currency_norm,
            owner_id=self._resolve_owner_id(owner_id),
        )
        return self._account_to_dict(row)

    def list_accounts(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        rows = self.repo.list_accounts(include_inactive=include_inactive, **self._owner_kwargs())
        return [self._account_to_dict(r) for r in rows]

    def get_account(self, account_id: int, *, include_inactive: bool = False) -> Optional[Dict[str, Any]]:
        row = self.repo.get_account(
            account_id,
            include_inactive=include_inactive,
            **self._owner_kwargs(),
        )
        if row is None:
            return None
        return self._account_to_dict(row)

    def update_account(
        self,
        account_id: int,
        *,
        name: Optional[str] = None,
        broker: Optional[str] = None,
        market: Optional[str] = None,
        base_currency: Optional[str] = None,
        owner_id: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {}
        if name is not None:
            name_norm = name.strip()
            if not name_norm:
                raise ValueError("name is required")
            fields["name"] = name_norm
        if broker is not None:
            fields["broker"] = broker.strip() or None
        if market is not None:
            fields["market"] = self._normalize_account_market(market)
        if base_currency is not None:
            fields["base_currency"] = self._normalize_currency(base_currency)
        if owner_id is not None:
            fields["owner_id"] = self._resolve_owner_id(owner_id)
        if is_active is not None:
            fields["is_active"] = bool(is_active)
        if not fields:
            raise ValueError("No fields provided for update")

        row = self.repo.update_account(account_id, fields, **self._owner_kwargs())
        if row is None:
            return None
        return self._account_to_dict(row)

    def deactivate_account(self, account_id: int) -> bool:
        return self.repo.deactivate_account(account_id, **self._owner_kwargs())

    # ------------------------------------------------------------------
    # Broker connection CRUD
    # ------------------------------------------------------------------
    def create_broker_connection(
        self,
        *,
        portfolio_account_id: int,
        broker_type: str,
        connection_name: str,
        broker_name: Optional[str] = None,
        broker_account_ref: Optional[str] = None,
        import_mode: str = "file",
        status: str = "active",
        sync_metadata: Optional[Dict[str, Any]] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_owner_id = self._resolve_owner_id(owner_id)
        account = self.repo.get_account(
            portfolio_account_id,
            include_inactive=False,
            owner_id=resolved_owner_id,
            include_all_owners=self.include_all_owners,
        )
        if account is None:
            raise ValueError(f"Active account not found: {portfolio_account_id}")
        try:
            row = self.repo.create_broker_connection(
                portfolio_account_id=int(account.id),
                broker_type=self._normalize_broker_type(broker_type),
                broker_name=(broker_name or "").strip() or None,
                connection_name=self._normalize_connection_name(connection_name),
                broker_account_ref=self._normalize_broker_account_ref(broker_account_ref),
                import_mode=self._normalize_import_mode(import_mode),
                status=self._normalize_broker_connection_status(status),
                sync_metadata_json=self._serialize_sync_metadata(sync_metadata),
                owner_id=resolved_owner_id,
            )
        except DuplicateBrokerConnectionRefError as exc:
            raise PortfolioConflictError(str(exc)) from exc
        return self._broker_connection_to_dict(row, portfolio_account_name=account.name)

    def list_broker_connections(
        self,
        *,
        portfolio_account_id: Optional[int] = None,
        broker_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if portfolio_account_id is not None:
            self.repo.get_account(
                portfolio_account_id,
                include_inactive=True,
                **self._owner_kwargs(),
            ) or self._raise_missing_account(portfolio_account_id)
        broker_type_norm = self._normalize_broker_type(broker_type) if broker_type is not None else None
        status_norm = (
            self._normalize_broker_connection_status(status)
            if status is not None and str(status).strip()
            else None
        )
        rows = self.repo.list_broker_connections(
            portfolio_account_id=portfolio_account_id,
            broker_type=broker_type_norm,
            status=status_norm,
            **self._owner_kwargs(),
        )
        account_lookup = self._account_name_lookup()
        return [
            self._broker_connection_to_dict(
                row,
                portfolio_account_name=account_lookup.get(int(row.portfolio_account_id)),
            )
            for row in rows
        ]

    def update_broker_connection(
        self,
        connection_id: int,
        *,
        portfolio_account_id: Optional[int] = None,
        connection_name: Optional[str] = None,
        broker_name: Optional[str] = None,
        broker_account_ref: Optional[str] = None,
        import_mode: Optional[str] = None,
        status: Optional[str] = None,
        sync_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {}
        portfolio_account_name: Optional[str] = None
        if portfolio_account_id is not None:
            account = self.repo.get_account(
                portfolio_account_id,
                include_inactive=False,
                **self._owner_kwargs(),
            )
            if account is None:
                raise ValueError(f"Active account not found: {portfolio_account_id}")
            fields["portfolio_account_id"] = int(account.id)
            portfolio_account_name = account.name
        if connection_name is not None:
            fields["connection_name"] = self._normalize_connection_name(connection_name)
        if broker_name is not None:
            fields["broker_name"] = broker_name.strip() or None
        if broker_account_ref is not None:
            fields["broker_account_ref"] = self._normalize_broker_account_ref(broker_account_ref)
        if import_mode is not None:
            fields["import_mode"] = self._normalize_import_mode(import_mode)
        if status is not None:
            fields["status"] = self._normalize_broker_connection_status(status)
        if sync_metadata is not None:
            fields["sync_metadata_json"] = self._serialize_sync_metadata(sync_metadata)
        if not fields:
            raise ValueError("No fields provided for update")

        try:
            row = self.repo.update_broker_connection(connection_id, fields, **self._owner_kwargs())
        except DuplicateBrokerConnectionRefError as exc:
            raise PortfolioConflictError(str(exc)) from exc
        if row is None:
            return None
        if portfolio_account_name is None:
            portfolio_account_name = self._account_name_lookup().get(int(row.portfolio_account_id))
        return self._broker_connection_to_dict(row, portfolio_account_name=portfolio_account_name)

    def get_broker_connection_by_ref(
        self,
        *,
        broker_type: str,
        broker_account_ref: str,
    ) -> Optional[Dict[str, Any]]:
        broker_type_norm = self._normalize_broker_type(broker_type)
        broker_account_ref_norm = self._normalize_broker_account_ref(broker_account_ref)
        if broker_account_ref_norm is None:
            raise ValueError("broker_account_ref is required")
        row = self.repo.get_broker_connection_by_ref(
            broker_type=broker_type_norm,
            broker_account_ref=broker_account_ref_norm,
            **self._owner_kwargs(),
        )
        if row is None:
            return None
        account_name = self._account_name_lookup().get(int(row.portfolio_account_id))
        return self._broker_connection_to_dict(row, portfolio_account_name=account_name)

    def get_broker_connection(self, connection_id: int) -> Optional[Dict[str, Any]]:
        row = self.repo.get_broker_connection(connection_id, **self._owner_kwargs())
        if row is None:
            return None
        account_name = self._account_name_lookup().get(int(row.portfolio_account_id))
        return self._broker_connection_to_dict(row, portfolio_account_name=account_name)

    def mark_broker_connection_imported(
        self,
        connection_id: int,
        *,
        import_source: str,
        import_fingerprint: Optional[str] = None,
        sync_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        fields: Dict[str, Any] = {
            "last_imported_at": datetime.now(),
            "last_import_source": (import_source or "").strip().lower() or "file",
            "last_import_fingerprint": (import_fingerprint or "").strip() or None,
            "status": "active",
        }
        if sync_metadata is not None:
            fields["sync_metadata_json"] = self._serialize_sync_metadata(sync_metadata)
        row = self.repo.update_broker_connection(connection_id, fields, **self._owner_kwargs())
        if row is None:
            return None
        account_name = self._account_name_lookup().get(int(row.portfolio_account_id))
        return self._broker_connection_to_dict(row, portfolio_account_name=account_name)

    def mark_broker_connection_synced(
        self,
        connection_id: int,
        *,
        sync_source: str,
        sync_status: str,
        sync_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        connection = self.get_broker_connection(connection_id)
        if connection is None:
            return None

        metadata = dict(connection.get("sync_metadata") or {})
        if sync_metadata:
            metadata.update(sync_metadata)
        metadata["last_sync_source"] = (sync_source or "").strip().lower() or "api"
        metadata["last_sync_status"] = (sync_status or "").strip().lower() or "success"
        metadata["last_sync_at"] = datetime.now().isoformat()

        row = self.repo.update_broker_connection(
            connection_id,
            {"sync_metadata_json": self._serialize_sync_metadata(metadata)},
            **self._owner_kwargs(),
        )
        if row is None:
            return None
        account_name = self._account_name_lookup().get(int(row.portfolio_account_id))
        return self._broker_connection_to_dict(row, portfolio_account_name=account_name)

    def replace_broker_sync_state(
        self,
        *,
        broker_connection_id: int,
        portfolio_account_id: int,
        broker_type: str,
        broker_account_ref: Optional[str],
        sync_source: str,
        sync_status: str,
        snapshot_date: date,
        synced_at: datetime,
        base_currency: str,
        total_cash: float,
        total_market_value: float,
        total_equity: float,
        realized_pnl: float,
        unrealized_pnl: float,
        fx_stale: bool,
        payload: Optional[Dict[str, Any]],
        positions: Iterable[Dict[str, Any]],
        cash_balances: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        connection = self.get_broker_connection(broker_connection_id)
        if connection is None:
            raise ValueError(f"Broker connection not found: {broker_connection_id}")
        if int(connection["portfolio_account_id"]) != int(portfolio_account_id):
            raise PortfolioConflictError(
                "Broker sync state cannot be written to a different portfolio account than the linked broker connection"
            )
        row = self.repo.replace_broker_sync_state(
            broker_connection_id=broker_connection_id,
            portfolio_account_id=portfolio_account_id,
            broker_type=self._normalize_broker_type(broker_type),
            broker_account_ref=self._normalize_broker_account_ref(broker_account_ref),
            sync_source=(sync_source or "").strip().lower() or "api",
            sync_status=(sync_status or "").strip().lower() or "success",
            snapshot_date=snapshot_date,
            synced_at=synced_at,
            base_currency=self._normalize_currency(base_currency),
            total_cash=float(total_cash),
            total_market_value=float(total_market_value),
            total_equity=float(total_equity),
            realized_pnl=float(realized_pnl),
            unrealized_pnl=float(unrealized_pnl),
            fx_stale=bool(fx_stale),
            payload_json=json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
            positions=list(positions),
            cash_balances=list(cash_balances),
            **self._owner_kwargs(),
        )
        return self._broker_sync_state_row_to_dict(row)

    def get_latest_broker_sync_state(self, *, portfolio_account_id: int) -> Optional[Dict[str, Any]]:
        row = self.repo.get_latest_broker_sync_state_for_account(
            portfolio_account_id=portfolio_account_id,
            **self._owner_kwargs(),
        )
        if row is None:
            return None
        positions = self.repo.list_broker_sync_positions(
            broker_connection_id=int(row.broker_connection_id),
            **self._owner_kwargs(),
        )
        cash_balances = self.repo.list_broker_sync_cash_balances(
            broker_connection_id=int(row.broker_connection_id),
            **self._owner_kwargs(),
        )
        return self._broker_sync_bundle_to_dict(row, positions=positions, cash_balances=cash_balances)

    # ------------------------------------------------------------------
    # Event writes
    # ------------------------------------------------------------------
    def record_trade(
        self,
        *,
        account_id: int,
        symbol: str,
        trade_date: date,
        side: str,
        quantity: float,
        price: float,
        fee: float = 0.0,
        tax: float = 0.0,
        market: Optional[str] = None,
        currency: Optional[str] = None,
        trade_uid: Optional[str] = None,
        dedup_hash: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        side_norm = (side or "").strip().lower()
        if side_norm not in VALID_SIDES:
            raise ValueError("side must be buy or sell")
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity and price must be > 0")
        if fee < 0 or tax < 0:
            raise ValueError("fee and tax must be >= 0")
        symbol_norm = canonical_stock_code(symbol)
        if not symbol_norm:
            raise ValueError("symbol is required")
        trade_uid_norm = (trade_uid or "").strip() or None
        dedup_hash_norm = (dedup_hash or "").strip() or None
        try:
            with self.repo.portfolio_write_session() as session:
                account = self._require_active_account_in_session(session=session, account_id=account_id)
                market_hint = market
                if market_hint is None and str(account.market or "").strip().lower() == "global":
                    market_hint = self._infer_market_from_symbol(symbol_norm)
                market_norm = self._normalize_event_market(market_hint or account.market)
                currency_norm = self._normalize_currency(currency or self._default_currency_for_market(market_norm))
                self._validate_trade_identity(
                    account_id=account_id,
                    trade_uid=trade_uid_norm,
                    dedup_hash=dedup_hash_norm,
                    session=session,
                )
                if side_norm == "sell":
                    self._validate_sell_quantity(
                        account_id=account_id,
                        symbol=symbol_norm,
                        market=market_norm,
                        currency=currency_norm,
                        trade_date=trade_date,
                        quantity=float(quantity),
                        session=session,
                    )
                row = self.repo.add_trade_in_session(
                    session=session,
                    account_id=account_id,
                    trade_uid=trade_uid_norm,
                    symbol=symbol_norm,
                    market=market_norm,
                    currency=currency_norm,
                    trade_date=trade_date,
                    side=side_norm,
                    quantity=float(quantity),
                    price=float(price),
                    fee=float(fee),
                    tax=float(tax),
                    note=(note or "").strip() or None,
                    dedup_hash=dedup_hash_norm,
                )
                return {"id": int(row.id)}
        except (DuplicateTradeUidError, DuplicateTradeDedupHashError) as exc:
            raise PortfolioConflictError(str(exc)) from exc

    def record_cash_ledger(
        self,
        *,
        account_id: int,
        event_date: date,
        direction: str,
        amount: float,
        currency: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        direction_norm = (direction or "").strip().lower()
        if direction_norm not in VALID_CASH_DIRECTIONS:
            raise ValueError("direction must be in or out")
        if amount <= 0:
            raise ValueError("amount must be > 0")
        with self.repo.portfolio_write_session() as session:
            account = self._require_active_account_in_session(session=session, account_id=account_id)
            currency_norm = self._normalize_currency(currency or account.base_currency)
            row = self.repo.add_cash_ledger_in_session(
                session=session,
                account_id=account_id,
                event_date=event_date,
                direction=direction_norm,
                amount=float(amount),
                currency=currency_norm,
                note=(note or "").strip() or None,
            )
            return {"id": int(row.id)}

    def record_corporate_action(
        self,
        *,
        account_id: int,
        symbol: str,
        effective_date: date,
        action_type: str,
        market: Optional[str] = None,
        currency: Optional[str] = None,
        cash_dividend_per_share: Optional[float] = None,
        split_ratio: Optional[float] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        action_type_norm = (action_type or "").strip().lower()
        if action_type_norm not in VALID_CORPORATE_ACTIONS:
            raise ValueError("action_type must be cash_dividend or split_adjustment")

        if action_type_norm == "cash_dividend":
            if cash_dividend_per_share is None or cash_dividend_per_share < 0:
                raise ValueError("cash_dividend_per_share must be >= 0 for cash_dividend")
        if action_type_norm == "split_adjustment":
            if split_ratio is None or split_ratio <= 0:
                raise ValueError("split_ratio must be > 0 for split_adjustment")
        with self.repo.portfolio_write_session() as session:
            account = self._require_active_account_in_session(session=session, account_id=account_id)
            market_hint = market
            if market_hint is None and str(account.market or "").strip().lower() == "global":
                symbol_norm = canonical_stock_code(symbol)
                market_hint = self._infer_market_from_symbol(symbol_norm)
            market_norm = self._normalize_event_market(market_hint or account.market)
            currency_norm = self._normalize_currency(currency or self._default_currency_for_market(market_norm))
            symbol_norm = canonical_stock_code(symbol)
            if not symbol_norm:
                raise ValueError("symbol is required")
            row = self.repo.add_corporate_action_in_session(
                session=session,
                account_id=account_id,
                symbol=symbol_norm,
                market=market_norm,
                currency=currency_norm,
                effective_date=effective_date,
                action_type=action_type_norm,
                cash_dividend_per_share=cash_dividend_per_share,
                split_ratio=split_ratio,
                note=(note or "").strip() or None,
            )
            return {"id": int(row.id)}

    def delete_trade_event(self, trade_id: int) -> bool:
        with self.repo.portfolio_write_session() as session:
            return self.repo.delete_trade_in_session(
                session=session,
                trade_id=trade_id,
                **self._owner_kwargs(),
            )

    def delete_cash_ledger_event(self, entry_id: int) -> bool:
        with self.repo.portfolio_write_session() as session:
            return self.repo.delete_cash_ledger_in_session(
                session=session,
                entry_id=entry_id,
                **self._owner_kwargs(),
            )

    def delete_corporate_action_event(self, action_id: int) -> bool:
        with self.repo.portfolio_write_session() as session:
            return self.repo.delete_corporate_action_in_session(
                session=session,
                action_id=action_id,
                **self._owner_kwargs(),
            )

    def list_trade_events(
        self,
        *,
        account_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        if account_id is not None:
            self._require_active_account(account_id)
        page, page_size = self._validate_paging(page=page, page_size=page_size)
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("date_from must be <= date_to")

        symbol_norm: Optional[str] = None
        if symbol is not None and symbol.strip():
            symbol_norm = canonical_stock_code(symbol)
            if not symbol_norm:
                raise ValueError("symbol is invalid")

        side_norm: Optional[str] = None
        if side is not None and side.strip():
            side_norm = side.strip().lower()
            if side_norm not in VALID_SIDES:
                raise ValueError("side must be buy or sell")

        rows, total = self.repo.query_trades(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            symbol=symbol_norm,
            side=side_norm,
            page=page,
            page_size=page_size,
            **self._owner_kwargs(),
        )
        return {
            "items": [self._trade_row_to_dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def list_cash_ledger_events(
        self,
        *,
        account_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        direction: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        if account_id is not None:
            self._require_active_account(account_id)
        page, page_size = self._validate_paging(page=page, page_size=page_size)
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("date_from must be <= date_to")

        direction_norm: Optional[str] = None
        if direction is not None and direction.strip():
            direction_norm = direction.strip().lower()
            if direction_norm not in VALID_CASH_DIRECTIONS:
                raise ValueError("direction must be in or out")

        rows, total = self.repo.query_cash_ledger(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            direction=direction_norm,
            page=page,
            page_size=page_size,
            **self._owner_kwargs(),
        )
        return {
            "items": [self._cash_ledger_row_to_dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def list_corporate_action_events(
        self,
        *,
        account_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        symbol: Optional[str] = None,
        action_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        if account_id is not None:
            self._require_active_account(account_id)
        page, page_size = self._validate_paging(page=page, page_size=page_size)
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("date_from must be <= date_to")

        symbol_norm: Optional[str] = None
        if symbol is not None and symbol.strip():
            symbol_norm = canonical_stock_code(symbol)
            if not symbol_norm:
                raise ValueError("symbol is invalid")

        action_norm: Optional[str] = None
        if action_type is not None and action_type.strip():
            action_norm = action_type.strip().lower()
            if action_norm not in VALID_CORPORATE_ACTIONS:
                raise ValueError("action_type must be cash_dividend or split_adjustment")

        rows, total = self.repo.query_corporate_actions(
            account_id=account_id,
            date_from=date_from,
            date_to=date_to,
            symbol=symbol_norm,
            action_type=action_norm,
            page=page,
            page_size=page_size,
            **self._owner_kwargs(),
        )
        return {
            "items": [self._corporate_action_row_to_dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ------------------------------------------------------------------
    # Snapshot replay
    # ------------------------------------------------------------------
    def get_portfolio_snapshot(
        self,
        *,
        account_id: Optional[int] = None,
        as_of: Optional[date] = None,
        cost_method: str = "fifo",
    ) -> Dict[str, Any]:
        as_of_date = as_of or date.today()
        method = self._normalize_cost_method(cost_method)

        if account_id is not None:
            account = self._require_active_account(account_id)
            account_rows = [account]
        else:
            account_rows = self.repo.list_accounts(include_inactive=False, **self._owner_kwargs())

        accounts_payload: List[Dict[str, Any]] = []
        aggregate_currency = self._resolve_snapshot_currency(
            account_rows=account_rows,
            requested_account_id=account_id,
        )
        aggregate = {
            "total_cash": 0.0,
            "total_market_value": 0.0,
            "total_equity": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "fee_total": 0.0,
            "tax_total": 0.0,
            "fx_stale": False,
        }

        for account in account_rows:
            account_snapshot = self._load_cached_account_snapshot(
                account=account,
                as_of_date=as_of_date,
                cost_method=method,
            )
            if account_snapshot is None:
                account_snapshot = self._build_account_snapshot(
                    account=account,
                    as_of_date=as_of_date,
                    cost_method=method,
                )

                self.repo.replace_positions_lots_and_snapshot(
                    account_id=account.id,
                    snapshot_date=as_of_date,
                    cost_method=method,
                    base_currency=account.base_currency,
                    total_cash=account_snapshot["total_cash"],
                    total_market_value=account_snapshot["total_market_value"],
                    total_equity=account_snapshot["total_equity"],
                    unrealized_pnl=account_snapshot["unrealized_pnl"],
                    realized_pnl=account_snapshot["realized_pnl"],
                    fee_total=account_snapshot["fee_total"],
                    tax_total=account_snapshot["tax_total"],
                    fx_stale=account_snapshot["fx_stale"],
                    payload=json.dumps(account_snapshot["payload"], ensure_ascii=False),
                    positions=account_snapshot["positions_cache"],
                    lots=account_snapshot["lots_cache"],
                    valuation_currency=account.base_currency,
                )

            accounts_payload.append(account_snapshot["public"])

            cash_cny, stale_cash, _ = self._convert_amount(
                amount=account_snapshot["total_cash"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            mv_cny, stale_mv, _ = self._convert_amount(
                amount=account_snapshot["total_market_value"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            eq_cny, stale_eq, _ = self._convert_amount(
                amount=account_snapshot["total_equity"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            realized_cny, stale_realized, _ = self._convert_amount(
                amount=account_snapshot["realized_pnl"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            unrealized_cny, stale_unrealized, _ = self._convert_amount(
                amount=account_snapshot["unrealized_pnl"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            fee_cny, stale_fee, _ = self._convert_amount(
                amount=account_snapshot["fee_total"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )
            tax_cny, stale_tax, _ = self._convert_amount(
                amount=account_snapshot["tax_total"],
                from_currency=account.base_currency,
                to_currency=aggregate_currency,
                as_of_date=as_of_date,
            )

            aggregate["total_cash"] += cash_cny
            aggregate["total_market_value"] += mv_cny
            aggregate["total_equity"] += eq_cny
            aggregate["realized_pnl"] += realized_cny
            aggregate["unrealized_pnl"] += unrealized_cny
            aggregate["fee_total"] += fee_cny
            aggregate["tax_total"] += tax_cny
            aggregate["fx_stale"] = aggregate["fx_stale"] or any(
                [
                    stale_cash,
                    stale_mv,
                    stale_eq,
                    stale_realized,
                    stale_unrealized,
                    stale_fee,
                    stale_tax,
                ]
            )

        return {
            "as_of": as_of_date.isoformat(),
            "cost_method": method,
            "currency": aggregate_currency,
            "account_count": len(account_rows),
            "total_cash": round(aggregate["total_cash"], 6),
            "total_market_value": round(aggregate["total_market_value"], 6),
            "total_equity": round(aggregate["total_equity"], 6),
            "realized_pnl": round(aggregate["realized_pnl"], 6),
            "unrealized_pnl": round(aggregate["unrealized_pnl"], 6),
            "fee_total": round(aggregate["fee_total"], 6),
            "tax_total": round(aggregate["tax_total"], 6),
            "fx_stale": aggregate["fx_stale"],
            "accounts": accounts_payload,
        }

    def refresh_fx_rates(
        self,
        *,
        account_id: Optional[int] = None,
        as_of: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Refresh account FX pairs online with stale fallback when fetch fails."""
        as_of_date = as_of or date.today()
        config = get_config()
        refresh_enabled = bool(getattr(config, "portfolio_fx_update_enabled", True))
        if account_id is not None:
            account_rows = [self._require_active_account(account_id)]
        else:
            account_rows = self.repo.list_accounts(include_inactive=False, **self._owner_kwargs())

        summary = {
            "as_of": as_of_date.isoformat(),
            "account_count": len(account_rows),
            "refresh_enabled": refresh_enabled,
            "disabled_reason": None if refresh_enabled else PORTFOLIO_FX_REFRESH_DISABLED_REASON,
            "pair_count": 0,
            "updated_count": 0,
            "stale_count": 0,
            "error_count": 0,
        }
        for account in account_rows:
            item = self._refresh_account_fx_rates(
                account=account,
                as_of_date=as_of_date,
                refresh_enabled=refresh_enabled,
            )
            summary["pair_count"] += item["pair_count"]
            summary["updated_count"] += item["updated_count"]
            summary["stale_count"] += item["stale_count"]
            summary["error_count"] += item["error_count"]
        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _validate_trade_identity(
        self,
        *,
        account_id: int,
        trade_uid: Optional[str],
        dedup_hash: Optional[str],
        session: Optional[Any] = None,
    ) -> None:
        if trade_uid and self._has_trade_uid(account_id=account_id, trade_uid=trade_uid, session=session):
            raise PortfolioConflictError(f"Duplicate trade_uid for account_id={account_id}: {trade_uid}")
        if dedup_hash and self._has_trade_dedup_hash(account_id=account_id, dedup_hash=dedup_hash, session=session):
            raise PortfolioConflictError(f"Duplicate dedup_hash for account_id={account_id}: {dedup_hash}")

    def _validate_sell_quantity(
        self,
        *,
        account_id: int,
        symbol: str,
        market: str,
        currency: str,
        trade_date: date,
        quantity: float,
        session: Optional[Any] = None,
    ) -> None:
        key = (
            canonical_stock_code(symbol),
            self._normalize_event_market(market),
            self._normalize_currency(currency),
        )
        available_quantity = self._calculate_available_quantity(
            account_id=account_id,
            key=key,
            as_of_date=trade_date,
            session=session,
        )
        if available_quantity + EPS < quantity:
            raise PortfolioOversellError(
                symbol=key[0],
                trade_date=trade_date,
                requested_quantity=quantity,
                available_quantity=available_quantity,
            )

    def _calculate_available_quantity(
        self,
        *,
        account_id: int,
        key: Tuple[str, str, str],
        as_of_date: date,
        session: Optional[Any] = None,
    ) -> float:
        if session is None:
            trades = self.repo.list_trades(account_id, as_of=as_of_date)
            corporate_actions = self.repo.list_corporate_actions(account_id, as_of=as_of_date)
        else:
            trades = self.repo.list_trades_in_session(session=session, account_id=account_id, as_of=as_of_date)
            corporate_actions = self.repo.list_corporate_actions_in_session(
                session=session,
                account_id=account_id,
                as_of=as_of_date,
            )

        events = []
        for row in corporate_actions:
            event_key = (
                canonical_stock_code(row.symbol),
                self._normalize_event_market(row.market),
                self._normalize_currency(row.currency),
            )
            if event_key == key:
                events.append(("corp", row.effective_date, row.id, row))
        for row in trades:
            event_key = (
                canonical_stock_code(row.symbol),
                self._normalize_event_market(row.market),
                self._normalize_currency(row.currency),
            )
            if event_key == key:
                events.append(("trade", row.trade_date, row.id, row))

        # Quantity validation only depends on position-changing events for one symbol.
        # Cash ledger entries do not affect shares held, so we keep the same corp->trade
        # ordering as full replay without pulling unrelated cash events into this path.
        event_priority = {"corp": 1, "trade": 2}
        events.sort(key=lambda item: (item[1], event_priority[item[0]], item[2]))

        quantity_held = 0.0
        for event_type, event_date, _, event in events:
            if event_type == "corp":
                action_type = (event.action_type or "").strip().lower()
                if action_type != "split_adjustment":
                    continue
                split_ratio = float(event.split_ratio or 0.0)
                if split_ratio <= 0:
                    raise ValueError(f"Invalid split_ratio for {key[0]}")
                if abs(split_ratio - 1.0) <= EPS:
                    continue
                quantity_held *= split_ratio
                continue

            qty = float(event.quantity or 0.0)
            if qty <= 0:
                raise ValueError(f"Invalid trade quantity for {key[0]}")
            side = (event.side or "").strip().lower()
            if side == "buy":
                quantity_held += qty
                continue
            if side != "sell":
                raise ValueError(f"Unsupported trade side: {event.side}")
            if quantity_held + EPS < qty:
                raise PortfolioOversellError(
                    symbol=key[0],
                    trade_date=event_date,
                    requested_quantity=qty,
                    available_quantity=quantity_held,
                )
            quantity_held -= qty
            if quantity_held <= EPS:
                quantity_held = 0.0

        return quantity_held

    def _replay_account(self, *, account: Any, as_of_date: date, cost_method: str) -> Dict[str, Any]:
        trades = self.repo.list_trades(account.id, as_of=as_of_date)
        cash_ledger = self.repo.list_cash_ledger(account.id, as_of=as_of_date)
        corporate_actions = self.repo.list_corporate_actions(account.id, as_of=as_of_date)

        events = []
        for row in cash_ledger:
            events.append(("cash", row.event_date, row.id, row))
        for row in trades:
            events.append(("trade", row.trade_date, row.id, row))
        for row in corporate_actions:
            events.append(("corp", row.effective_date, row.id, row))

        # Same-day deterministic ordering: cash -> corporate action -> trade.
        event_priority = {"cash": 0, "corp": 1, "trade": 2}
        events.sort(key=lambda item: (item[1], event_priority[item[0]], item[2]))

        cash_balances: Dict[str, float] = defaultdict(float)
        fees_total_base = 0.0
        taxes_total_base = 0.0
        realized_pnl_base = 0.0
        fx_stale = False
        fx_currencies_used: Set[str] = set()

        fifo_lots: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
        avg_state: Dict[Tuple[str, str, str], _AvgState] = defaultdict(_AvgState)

        for event_type, event_date, _, event in events:
            if event_type == "cash":
                currency = self._normalize_currency(event.currency)
                amount = float(event.amount or 0.0)
                if event.direction == "in":
                    cash_balances[currency] += amount
                elif event.direction == "out":
                    cash_balances[currency] -= amount
                else:
                    raise ValueError(f"Unsupported cash direction: {event.direction}")
                continue

            if event_type == "trade":
                key = (
                    canonical_stock_code(event.symbol),
                    self._normalize_event_market(event.market),
                    self._normalize_currency(event.currency),
                )
                qty = float(event.quantity or 0.0)
                price = float(event.price or 0.0)
                fee = float(event.fee or 0.0)
                tax = float(event.tax or 0.0)
                if qty <= 0 or price <= 0:
                    raise ValueError(f"Invalid trade quantity or price for {event.symbol}")

                gross = qty * price
                side = (event.side or "").lower().strip()
                if side == "buy":
                    cash_balances[key[2]] -= (gross + fee + tax)
                    if cost_method == "fifo":
                        unit_cost = (gross + fee + tax) / qty
                        fifo_lots[key].append(
                            {
                                "symbol": key[0],
                                "market": key[1],
                                "currency": key[2],
                                "open_date": event_date,
                                "remaining_quantity": qty,
                                "unit_cost": unit_cost,
                                "source_trade_id": event.id,
                            }
                        )
                    else:
                        state = avg_state[key]
                        state.quantity += qty
                        state.total_cost += (gross + fee + tax)
                elif side == "sell":
                    cash_balances[key[2]] += (gross - fee - tax)
                    proceeds_net = gross - fee - tax
                    if cost_method == "fifo":
                        cost_basis = self._consume_fifo_lots(
                            fifo_lots[key],
                            qty,
                            key[0],
                            event_date,
                        )
                    else:
                        cost_basis = self._consume_avg_position(
                            avg_state[key],
                            qty,
                            key[0],
                            event_date,
                        )
                    realized_local = proceeds_net - cost_basis
                    realized_base, stale_realized, _ = self._convert_amount(
                        amount=realized_local,
                        from_currency=key[2],
                        to_currency=account.base_currency,
                        as_of_date=event_date,
                    )
                    if self._normalize_currency(key[2]) != self._normalize_currency(account.base_currency):
                        fx_currencies_used.add(self._normalize_currency(key[2]))
                    realized_pnl_base += realized_base
                    fx_stale = fx_stale or stale_realized
                else:
                    raise ValueError(f"Unsupported trade side: {event.side}")

                fee_base, stale_fee, _ = self._convert_amount(
                    amount=fee,
                    from_currency=key[2],
                    to_currency=account.base_currency,
                    as_of_date=event_date,
                )
                tax_base, stale_tax, _ = self._convert_amount(
                    amount=tax,
                    from_currency=key[2],
                    to_currency=account.base_currency,
                    as_of_date=event_date,
                )
                if self._normalize_currency(key[2]) != self._normalize_currency(account.base_currency):
                    fx_currencies_used.add(self._normalize_currency(key[2]))
                fees_total_base += fee_base
                taxes_total_base += tax_base
                fx_stale = fx_stale or stale_fee or stale_tax
                continue

            if event_type == "corp":
                key = (
                    canonical_stock_code(event.symbol),
                    self._normalize_event_market(event.market),
                    self._normalize_currency(event.currency),
                )
                action_type = (event.action_type or "").strip().lower()
                if action_type == "cash_dividend":
                    per_share = float(event.cash_dividend_per_share or 0.0)
                    if per_share <= 0:
                        continue
                    qty_held = self._held_quantity(
                        key=key,
                        cost_method=cost_method,
                        fifo_lots=fifo_lots,
                        avg_state=avg_state,
                    )
                    if qty_held > EPS:
                        cash_balances[key[2]] += qty_held * per_share
                elif action_type == "split_adjustment":
                    split_ratio = float(event.split_ratio or 0.0)
                    if split_ratio <= 0:
                        raise ValueError(f"Invalid split_ratio for {event.symbol}")
                    if abs(split_ratio - 1.0) <= EPS:
                        continue
                    if cost_method == "fifo":
                        for lot in fifo_lots[key]:
                            lot["remaining_quantity"] *= split_ratio
                            lot["unit_cost"] /= split_ratio
                    else:
                        state = avg_state[key]
                        state.quantity *= split_ratio
                else:
                    raise ValueError(f"Unsupported corporate action type: {event.action_type}")

        position_rows, lot_rows, market_value_base, total_cost_base, stale_pos = self._build_positions(
            account=account,
            as_of_date=as_of_date,
            cost_method=cost_method,
            fifo_lots=fifo_lots,
            avg_state=avg_state,
            fx_currencies_used=fx_currencies_used,
        )
        fx_stale = fx_stale or stale_pos

        total_cash_base = 0.0
        for currency, amount in cash_balances.items():
            converted, stale, _ = self._convert_amount(
                amount=amount,
                from_currency=currency,
                to_currency=account.base_currency,
                as_of_date=as_of_date,
            )
            if self._normalize_currency(currency) != self._normalize_currency(account.base_currency):
                fx_currencies_used.add(self._normalize_currency(currency))
            total_cash_base += converted
            fx_stale = fx_stale or stale

        unrealized_pnl_base = market_value_base - total_cost_base
        total_equity_base = total_cash_base + market_value_base

        account_payload = {
            "account_id": account.id,
            "account_name": account.name,
            "owner_id": account.owner_id,
            "broker": account.broker,
            "market": account.market,
            "base_currency": account.base_currency,
            "as_of": as_of_date.isoformat(),
            "cost_method": cost_method,
            "total_cash": round(total_cash_base, 6),
            "total_market_value": round(market_value_base, 6),
            "total_equity": round(total_equity_base, 6),
            "realized_pnl": round(realized_pnl_base, 6),
            "unrealized_pnl": round(unrealized_pnl_base, 6),
            "fee_total": round(fees_total_base, 6),
            "tax_total": round(taxes_total_base, 6),
            "fx_stale": fx_stale,
            "positions": position_rows,
        }

        cache_payload = dict(account_payload)
        cache_payload["_cache_meta"] = {
            "fx_currencies": sorted(fx_currencies_used),
        }

        return {
            "public": account_payload,
            "payload": cache_payload,
            "positions_cache": position_rows,
            "lots_cache": lot_rows,
            "total_cash": float(total_cash_base),
            "total_market_value": float(market_value_base),
            "total_equity": float(total_equity_base),
            "realized_pnl": float(realized_pnl_base),
            "unrealized_pnl": float(unrealized_pnl_base),
            "fee_total": float(fees_total_base),
            "tax_total": float(taxes_total_base),
            "fx_stale": fx_stale,
        }

    def _build_account_snapshot(self, *, account: Any, as_of_date: date, cost_method: str) -> Dict[str, Any]:
        sync_state = self.get_latest_broker_sync_state(portfolio_account_id=int(account.id))
        if sync_state is not None and self._should_use_broker_sync_state(sync_state=sync_state, as_of_date=as_of_date):
            return self._build_synced_account_snapshot(
                account=account,
                sync_state=sync_state,
                cost_method=cost_method,
                as_of_date=as_of_date,
            )
        return self._replay_account(account=account, as_of_date=as_of_date, cost_method=cost_method)

    @staticmethod
    def _should_use_broker_sync_state(*, sync_state: Dict[str, Any], as_of_date: date) -> bool:
        if str(sync_state.get("sync_status") or "").strip().lower() != "success":
            return False
        snapshot_date_raw = str(sync_state.get("snapshot_date") or "").strip()
        if not snapshot_date_raw:
            return False
        try:
            snapshot_date = date.fromisoformat(snapshot_date_raw)
        except ValueError:
            return False
        return snapshot_date == as_of_date

    def _build_synced_account_snapshot(
        self,
        *,
        account: Any,
        sync_state: Dict[str, Any],
        cost_method: str,
        as_of_date: date,
    ) -> Dict[str, Any]:
        positions = [
            {
                "symbol": item["symbol"],
                "market": item["market"],
                "currency": item["currency"],
                "quantity": float(item["quantity"]),
                "avg_cost": float(item["avg_cost"]),
                "total_cost": round(float(item["quantity"]) * float(item["avg_cost"]), 8),
                "last_price": float(item["last_price"]),
                "market_value_base": float(item["market_value_base"]),
                "unrealized_pnl_base": float(item["unrealized_pnl_base"]),
                "valuation_currency": item["valuation_currency"],
            }
            for item in list(sync_state.get("positions") or [])
        ]
        payload = {
            "account_id": account.id,
            "account_name": account.name,
            "owner_id": account.owner_id,
            "broker": account.broker,
            "market": account.market,
            "base_currency": sync_state.get("base_currency") or account.base_currency,
            "as_of": as_of_date.isoformat(),
            "cost_method": cost_method,
            "total_cash": round(float(sync_state.get("total_cash", 0.0) or 0.0), 6),
            "total_market_value": round(float(sync_state.get("total_market_value", 0.0) or 0.0), 6),
            "total_equity": round(float(sync_state.get("total_equity", 0.0) or 0.0), 6),
            "realized_pnl": round(float(sync_state.get("realized_pnl", 0.0) or 0.0), 6),
            "unrealized_pnl": round(float(sync_state.get("unrealized_pnl", 0.0) or 0.0), 6),
            "fee_total": 0.0,
            "tax_total": 0.0,
            "fx_stale": bool(sync_state.get("fx_stale")),
            "positions": positions,
        }
        return {
            "public": payload,
            "payload": {
                **payload,
                "_cache_meta": {
                    "fx_currencies": [],
                },
            },
            "positions_cache": positions,
            "lots_cache": [],
            "total_cash": float(payload["total_cash"]),
            "total_market_value": float(payload["total_market_value"]),
            "total_equity": float(payload["total_equity"]),
            "realized_pnl": float(payload["realized_pnl"]),
            "unrealized_pnl": float(payload["unrealized_pnl"]),
            "fee_total": 0.0,
            "tax_total": 0.0,
            "fx_stale": bool(payload["fx_stale"]),
        }

    def _load_cached_account_snapshot(
        self,
        *,
        account: Any,
        as_of_date: date,
        cost_method: str,
    ) -> Optional[Dict[str, Any]]:
        cached = self.repo.get_cached_snapshot_bundle(
            account_id=int(account.id),
            snapshot_date=as_of_date,
            cost_method=cost_method,
        )
        if cached is None:
            return None

        snapshot_row = cached["snapshot"]
        snapshot_updated_at = getattr(snapshot_row, "updated_at", None)
        if snapshot_updated_at is None:
            return None

        payload_raw = self._parse_snapshot_payload(getattr(snapshot_row, "payload", None))
        positions_cache = [self._cached_position_row_to_dict(row) for row in cached["positions"]]
        latest_market_update = self.repo.get_latest_market_data_update(
            symbols=[item["symbol"] for item in positions_cache],
            as_of=as_of_date,
        )
        if latest_market_update is not None and latest_market_update > snapshot_updated_at:
            return None

        fx_currencies = self._extract_cached_fx_currencies(payload_raw)
        latest_fx_update = self.repo.get_latest_fx_rate_update(
            as_of=as_of_date,
            base_currency=snapshot_row.base_currency or account.base_currency,
            currencies=fx_currencies,
        )
        if latest_fx_update is None and payload_raw.get("_cache_meta") is None:
            latest_fx_update = self.repo.get_latest_fx_rate_update(as_of=as_of_date)
        if latest_fx_update is not None and latest_fx_update > snapshot_updated_at:
            return None

        lots_cache = [self._cached_lot_row_to_dict(row) for row in cached["lots"]]
        payload = self._cached_snapshot_public_payload(
            account=account,
            snapshot_row=snapshot_row,
            positions=positions_cache,
            as_of_date=as_of_date,
            cost_method=cost_method,
            payload=payload_raw,
        )
        return {
            "public": payload,
            "payload": payload,
            "positions_cache": positions_cache,
            "lots_cache": lots_cache,
            "total_cash": float(snapshot_row.total_cash or 0.0),
            "total_market_value": float(snapshot_row.total_market_value or 0.0),
            "total_equity": float(snapshot_row.total_equity or 0.0),
            "realized_pnl": float(snapshot_row.realized_pnl or 0.0),
            "unrealized_pnl": float(snapshot_row.unrealized_pnl or 0.0),
            "fee_total": float(snapshot_row.fee_total or 0.0),
            "tax_total": float(snapshot_row.tax_total or 0.0),
            "fx_stale": bool(snapshot_row.fx_stale),
        }

    def _build_positions(
        self,
        *,
        account: Any,
        as_of_date: date,
        cost_method: str,
        fifo_lots: Dict[Tuple[str, str, str], List[Dict[str, Any]]],
        avg_state: Dict[Tuple[str, str, str], _AvgState],
        fx_currencies_used: Optional[Set[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float, float, bool]:
        position_rows: List[Dict[str, Any]] = []
        lot_rows: List[Dict[str, Any]] = []
        market_value_base = 0.0
        total_cost_base = 0.0
        fx_stale = False

        keys: Iterable[Tuple[str, str, str]]
        if cost_method == "fifo":
            keys = list(fifo_lots.keys())
        else:
            keys = list(avg_state.keys())
        latest_closes = self.repo.get_latest_closes(
            symbols=[key[0] for key in keys],
            as_of=as_of_date,
        )

        for key in sorted(keys):
            symbol, market, currency = key

            if cost_method == "fifo":
                active_lots = [lot for lot in fifo_lots[key] if lot["remaining_quantity"] > EPS]
                qty = sum(float(lot["remaining_quantity"]) for lot in active_lots)
                if qty <= EPS:
                    continue
                total_cost = sum(float(lot["remaining_quantity"]) * float(lot["unit_cost"]) for lot in active_lots)
                avg_cost = total_cost / qty
                lot_rows.extend(active_lots)
            else:
                state = avg_state[key]
                qty = float(state.quantity)
                total_cost = float(state.total_cost)
                if qty <= EPS:
                    continue
                avg_cost = total_cost / qty
                lot_rows.append(
                    {
                        "symbol": symbol,
                        "market": market,
                        "currency": currency,
                        "open_date": as_of_date,
                        "remaining_quantity": qty,
                        "unit_cost": avg_cost,
                        "source_trade_id": None,
                    }
                )

            last_price = latest_closes.get(symbol)
            if last_price is None or last_price <= 0:
                last_price = avg_cost
            if (
                fx_currencies_used is not None
                and self._normalize_currency(currency) != self._normalize_currency(account.base_currency)
            ):
                fx_currencies_used.add(self._normalize_currency(currency))

            local_market_value = qty * float(last_price)
            market_base, stale_market, _ = self._convert_amount(
                amount=local_market_value,
                from_currency=currency,
                to_currency=account.base_currency,
                as_of_date=as_of_date,
            )
            cost_base, stale_cost, _ = self._convert_amount(
                amount=total_cost,
                from_currency=currency,
                to_currency=account.base_currency,
                as_of_date=as_of_date,
            )
            unrealized_base = market_base - cost_base
            fx_stale = fx_stale or stale_market or stale_cost

            position_rows.append(
                {
                    "symbol": symbol,
                    "market": market,
                    "currency": currency,
                    "quantity": round(qty, 8),
                    "avg_cost": round(avg_cost, 8),
                    "total_cost": round(total_cost, 8),
                    "last_price": round(float(last_price), 8),
                    "market_value_base": round(market_base, 8),
                    "unrealized_pnl_base": round(unrealized_base, 8),
                    "valuation_currency": account.base_currency,
                }
            )

            market_value_base += market_base
            total_cost_base += cost_base

        return position_rows, lot_rows, market_value_base, total_cost_base, fx_stale

    @staticmethod
    def _consume_fifo_lots(
        lots: List[Dict[str, Any]],
        quantity: float,
        symbol: str,
        trade_date: Optional[date] = None,
    ) -> float:
        remaining = quantity
        cost_basis = 0.0
        while remaining > EPS:
            if not lots:
                raise PortfolioOversellError(
                    symbol=symbol,
                    trade_date=trade_date,
                    requested_quantity=quantity,
                    available_quantity=quantity - remaining,
                )
            head = lots[0]
            take = min(remaining, float(head["remaining_quantity"]))
            cost_basis += take * float(head["unit_cost"])
            head["remaining_quantity"] = float(head["remaining_quantity"]) - take
            remaining -= take
            if head["remaining_quantity"] <= EPS:
                lots.pop(0)
        return cost_basis

    @staticmethod
    def _consume_avg_position(
        state: _AvgState,
        quantity: float,
        symbol: str,
        trade_date: Optional[date] = None,
    ) -> float:
        if state.quantity + EPS < quantity:
            raise PortfolioOversellError(
                symbol=symbol,
                trade_date=trade_date,
                requested_quantity=quantity,
                available_quantity=state.quantity,
            )
        if state.quantity <= EPS:
            raise PortfolioOversellError(
                symbol=symbol,
                trade_date=trade_date,
                requested_quantity=quantity,
                available_quantity=0.0,
            )
        avg_cost = state.total_cost / state.quantity
        cost_basis = avg_cost * quantity
        state.quantity -= quantity
        state.total_cost -= cost_basis
        if state.quantity <= EPS:
            state.quantity = 0.0
            state.total_cost = 0.0
        return cost_basis

    @staticmethod
    def _held_quantity(
        *,
        key: Tuple[str, str, str],
        cost_method: str,
        fifo_lots: Dict[Tuple[str, str, str], List[Dict[str, Any]]],
        avg_state: Dict[Tuple[str, str, str], _AvgState],
    ) -> float:
        if cost_method == "fifo":
            return sum(float(lot["remaining_quantity"]) for lot in fifo_lots.get(key, []))
        return float(avg_state.get(key, _AvgState()).quantity)

    def _convert_amount(
        self,
        *,
        amount: float,
        from_currency: str,
        to_currency: str,
        as_of_date: date,
    ) -> Tuple[float, bool, str]:
        from_norm = self._normalize_currency(from_currency)
        to_norm = self._normalize_currency(to_currency)
        if abs(amount) <= EPS:
            return 0.0, False, "zero"
        if from_norm == to_norm:
            return float(amount), False, "identity"

        direct = self.repo.get_latest_fx_rate(
            from_currency=from_norm,
            to_currency=to_norm,
            as_of=as_of_date,
        )
        if direct is not None and direct.rate > 0:
            return float(amount) * float(direct.rate), bool(direct.is_stale), "direct_rate"

        inverse = self.repo.get_latest_fx_rate(
            from_currency=to_norm,
            to_currency=from_norm,
            as_of=as_of_date,
        )
        if inverse is not None and inverse.rate > 0:
            return float(amount) / float(inverse.rate), bool(inverse.is_stale), "inverse_rate"

        # P0 fallback: keep pipeline available even when FX cache is missing.
        return float(amount), True, "fallback_1_to_1"

    def convert_amount(
        self,
        *,
        amount: float,
        from_currency: str,
        to_currency: str,
        as_of_date: date,
    ) -> Tuple[float, bool, str]:
        """Public conversion entry for cross-service consumers."""
        return self._convert_amount(
            amount=amount,
            from_currency=from_currency,
            to_currency=to_currency,
            as_of_date=as_of_date,
        )

    def _list_account_refresh_fx_currencies(
        self,
        *,
        account: Any,
        as_of_date: date,
        strict: bool = True,
    ) -> List[str]:
        """Return distinct non-base currencies participating in refresh for one account."""
        base_currency = self._normalize_currency(account.base_currency)
        currencies: Set[str] = set()
        rows = list(self.repo.list_trades(account.id, as_of=as_of_date))
        rows.extend(self.repo.list_cash_ledger(account.id, as_of=as_of_date))
        for row in rows:
            try:
                currency = self._normalize_currency(row.currency)
            except ValueError:
                if strict:
                    raise
                logger.warning(
                    "Skip invalid FX refresh currency for account %s on %s: %r",
                    account.id,
                    as_of_date.isoformat(),
                    getattr(row, "currency", None),
                )
                continue
            if currency != base_currency:
                currencies.add(currency)
        return sorted(currencies)

    def _refresh_account_fx_rates(
        self,
        *,
        account: Any,
        as_of_date: date,
        refresh_enabled: bool,
    ) -> Dict[str, int]:
        """Refresh FX pairs for one account and keep stale fallback on failures."""
        refresh_currencies = self._list_account_refresh_fx_currencies(
            account=account,
            as_of_date=as_of_date,
            strict=refresh_enabled,
        )
        if not refresh_enabled:
            return {
                "pair_count": len(refresh_currencies),
                "updated_count": 0,
                "stale_count": 0,
                "error_count": 0,
            }

        base_currency = self._normalize_currency(account.base_currency)
        summary = {
            "pair_count": len(refresh_currencies),
            "updated_count": 0,
            "stale_count": 0,
            "error_count": 0,
        }
        for from_currency in refresh_currencies:
            try:
                rate = self._fetch_fx_rate_from_yfinance(
                    from_currency=from_currency,
                    to_currency=base_currency,
                    as_of_date=as_of_date,
                )
                if rate is not None and rate > 0:
                    self.repo.save_fx_rate(
                        from_currency=from_currency,
                        to_currency=base_currency,
                        rate_date=as_of_date,
                        rate=rate,
                        source="yfinance",
                        is_stale=False,
                    )
                    summary["updated_count"] += 1
                    continue
            except Exception as exc:
                logger.warning(
                    "FX online fetch failed for %s/%s on %s: %s",
                    from_currency,
                    base_currency,
                    as_of_date.isoformat(),
                    exc,
                )

            fallback = self.repo.get_latest_fx_rate(
                from_currency=from_currency,
                to_currency=base_currency,
                as_of=as_of_date,
            )
            if fallback is not None and float(fallback.rate or 0.0) > 0:
                self.repo.save_fx_rate(
                    from_currency=from_currency,
                    to_currency=base_currency,
                    rate_date=as_of_date,
                    rate=float(fallback.rate),
                    source=(fallback.source or "cache_fallback"),
                    is_stale=True,
                )
                summary["stale_count"] += 1
            else:
                summary["error_count"] += 1
        return summary

    @staticmethod
    def _fetch_fx_rate_from_yfinance(
        *,
        from_currency: str,
        to_currency: str,
        as_of_date: date,
    ) -> Optional[float]:
        """Fetch latest available FX close rate around as_of date."""
        if yf is None:
            return None
        symbol = f"{from_currency}{to_currency}=X"
        ticker = yf.Ticker(symbol)
        history = ticker.history(
            start=(as_of_date - timedelta(days=7)).isoformat(),
            end=(as_of_date + timedelta(days=1)).isoformat(),
            interval="1d",
            auto_adjust=False,
        )
        if history is None or history.empty or "Close" not in history:
            return None
        close = history["Close"].dropna()
        if close.empty:
            return None
        value = float(close.iloc[-1])
        if value <= 0:
            return None
        return value

    def _require_active_account(self, account_id: int) -> Any:
        account = self.repo.get_account(account_id, include_inactive=False, **self._owner_kwargs())
        if account is None:
            raise ValueError(f"Active account not found: {account_id}")
        return account

    def _require_active_account_in_session(self, *, session: Any, account_id: int) -> Any:
        account = self.repo.get_account_in_session(
            session=session,
            account_id=account_id,
            include_inactive=False,
            **self._owner_kwargs(),
        )
        if account is None:
            raise ValueError(f"Active account not found: {account_id}")
        return account

    def _has_trade_uid(self, *, account_id: int, trade_uid: str, session: Optional[Any] = None) -> bool:
        if session is None:
            return self.repo.has_trade_uid(account_id, trade_uid)
        return self.repo.has_trade_uid_in_session(session=session, account_id=account_id, trade_uid=trade_uid)

    def _has_trade_dedup_hash(
        self,
        *,
        account_id: int,
        dedup_hash: str,
        session: Optional[Any] = None,
    ) -> bool:
        if session is None:
            return self.repo.has_trade_dedup_hash(account_id, dedup_hash)
        return self.repo.has_trade_dedup_hash_in_session(
            session=session,
            account_id=account_id,
            dedup_hash=dedup_hash,
        )

    def _account_name_lookup(self) -> Dict[int, str]:
        rows = self.repo.list_accounts(include_inactive=True, **self._owner_kwargs())
        return {int(row.id): str(row.name) for row in rows}

    @staticmethod
    def _raise_missing_account(account_id: int) -> None:
        raise ValueError(f"Account not found: {account_id}")

    @staticmethod
    def _account_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "id": row.id,
            "owner_id": row.owner_id,
            "name": row.name,
            "broker": row.broker,
            "market": row.market,
            "base_currency": row.base_currency,
            "is_active": bool(row.is_active),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def _broker_connection_to_dict(row: Any, *, portfolio_account_name: Optional[str] = None) -> Dict[str, Any]:
        sync_metadata: Dict[str, Any] = {}
        if getattr(row, "sync_metadata_json", None):
            try:
                parsed = json.loads(row.sync_metadata_json)
                if isinstance(parsed, dict):
                    sync_metadata = parsed
            except Exception:
                sync_metadata = {}
        return {
            "id": int(row.id),
            "owner_id": row.owner_id,
            "portfolio_account_id": int(row.portfolio_account_id),
            "portfolio_account_name": portfolio_account_name,
            "broker_type": row.broker_type,
            "broker_name": row.broker_name,
            "connection_name": row.connection_name,
            "broker_account_ref": row.broker_account_ref,
            "import_mode": row.import_mode,
            "status": row.status,
            "last_imported_at": row.last_imported_at.isoformat() if row.last_imported_at else None,
            "last_import_source": row.last_import_source,
            "last_import_fingerprint": row.last_import_fingerprint,
            "sync_metadata": sync_metadata,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def _broker_sync_state_row_to_dict(row: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if getattr(row, "payload_json", None):
            try:
                parsed = json.loads(row.payload_json)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = {}
        return {
            "id": int(row.id),
            "owner_id": row.owner_id,
            "broker_connection_id": int(row.broker_connection_id),
            "portfolio_account_id": int(row.portfolio_account_id),
            "broker_type": row.broker_type,
            "broker_account_ref": row.broker_account_ref,
            "sync_source": row.sync_source,
            "sync_status": row.sync_status,
            "snapshot_date": row.snapshot_date.isoformat() if row.snapshot_date else None,
            "synced_at": row.synced_at.isoformat() if row.synced_at else None,
            "base_currency": row.base_currency,
            "total_cash": float(row.total_cash or 0.0),
            "total_market_value": float(row.total_market_value or 0.0),
            "total_equity": float(row.total_equity or 0.0),
            "realized_pnl": float(row.realized_pnl or 0.0),
            "unrealized_pnl": float(row.unrealized_pnl or 0.0),
            "fx_stale": bool(row.fx_stale),
            "payload": payload,
        }

    @staticmethod
    def _broker_sync_bundle_to_dict(
        row: Any,
        *,
        positions: Iterable[Any],
        cash_balances: Iterable[Any],
    ) -> Dict[str, Any]:
        data = PortfolioService._broker_sync_state_row_to_dict(row)
        data["positions"] = [
            {
                "broker_position_ref": item.broker_position_ref,
                "symbol": item.symbol,
                "market": item.market,
                "currency": item.currency,
                "quantity": float(item.quantity or 0.0),
                "avg_cost": float(item.avg_cost or 0.0),
                "last_price": float(item.last_price or 0.0),
                "market_value_base": float(item.market_value_base or 0.0),
                "unrealized_pnl_base": float(item.unrealized_pnl_base or 0.0),
                "valuation_currency": item.valuation_currency,
            }
            for item in positions
        ]
        data["cash_balances"] = [
            {
                "currency": item.currency,
                "amount": float(item.amount or 0.0),
                "amount_base": float(item.amount_base or 0.0),
            }
            for item in cash_balances
        ]
        return data

    @staticmethod
    def _cached_position_row_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "symbol": row.symbol,
            "market": row.market,
            "currency": row.currency,
            "quantity": round(float(row.quantity or 0.0), 8),
            "avg_cost": round(float(row.avg_cost or 0.0), 8),
            "total_cost": round(float(row.total_cost or 0.0), 8),
            "last_price": round(float(row.last_price or 0.0), 8),
            "market_value_base": round(float(row.market_value_base or 0.0), 8),
            "unrealized_pnl_base": round(float(row.unrealized_pnl_base or 0.0), 8),
            "valuation_currency": row.valuation_currency,
        }

    @staticmethod
    def _cached_lot_row_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "symbol": row.symbol,
            "market": row.market,
            "currency": row.currency,
            "open_date": row.open_date,
            "remaining_quantity": float(row.remaining_quantity or 0.0),
            "unit_cost": float(row.unit_cost or 0.0),
            "source_trade_id": row.source_trade_id,
        }

    @staticmethod
    def _parse_snapshot_payload(payload_raw: Optional[str]) -> Dict[str, Any]:
        if not payload_raw:
            return {}
        try:
            payload = json.loads(payload_raw)
        except Exception:
            return {}
        if isinstance(payload, dict):
            return payload
        return {}

    def _cached_snapshot_public_payload(
        self,
        *,
        account: Any,
        snapshot_row: Any,
        positions: List[Dict[str, Any]],
        as_of_date: date,
        cost_method: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        public_payload = dict(payload or self._parse_snapshot_payload(getattr(snapshot_row, "payload", None)))
        public_payload.pop("_cache_meta", None)
        public_payload.update(
            {
                "account_id": int(account.id),
                "account_name": account.name,
                "owner_id": account.owner_id,
                "broker": account.broker,
                "market": account.market,
                "base_currency": snapshot_row.base_currency or account.base_currency,
                "as_of": as_of_date.isoformat(),
                "cost_method": cost_method,
                "total_cash": round(float(snapshot_row.total_cash or 0.0), 6),
                "total_market_value": round(float(snapshot_row.total_market_value or 0.0), 6),
                "total_equity": round(float(snapshot_row.total_equity or 0.0), 6),
                "realized_pnl": round(float(snapshot_row.realized_pnl or 0.0), 6),
                "unrealized_pnl": round(float(snapshot_row.unrealized_pnl or 0.0), 6),
                "fee_total": round(float(snapshot_row.fee_total or 0.0), 6),
                "tax_total": round(float(snapshot_row.tax_total or 0.0), 6),
                "fx_stale": bool(snapshot_row.fx_stale),
                "positions": positions,
            }
        )
        return public_payload

    @staticmethod
    def _extract_cached_fx_currencies(payload: Optional[Dict[str, Any]]) -> List[str]:
        if not isinstance(payload, dict):
            return []
        meta = payload.get("_cache_meta")
        if not isinstance(meta, dict):
            return []
        raw = meta.get("fx_currencies")
        if not isinstance(raw, list):
            return []
        return sorted({str(item or "").strip().upper() for item in raw if str(item or "").strip()})

    @staticmethod
    def _trade_row_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "id": int(row.id),
            "account_id": int(row.account_id),
            "trade_uid": row.trade_uid,
            "symbol": row.symbol,
            "market": row.market,
            "currency": row.currency,
            "trade_date": row.trade_date.isoformat() if row.trade_date else "",
            "side": row.side,
            "quantity": float(row.quantity),
            "price": float(row.price),
            "fee": float(row.fee),
            "tax": float(row.tax),
            "note": row.note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _cash_ledger_row_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "id": int(row.id),
            "account_id": int(row.account_id),
            "event_date": row.event_date.isoformat() if row.event_date else "",
            "direction": row.direction,
            "amount": float(row.amount),
            "currency": row.currency,
            "note": row.note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _corporate_action_row_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "id": int(row.id),
            "account_id": int(row.account_id),
            "symbol": row.symbol,
            "market": row.market,
            "currency": row.currency,
            "effective_date": row.effective_date.isoformat() if row.effective_date else "",
            "action_type": row.action_type,
            "cash_dividend_per_share": (
                float(row.cash_dividend_per_share) if row.cash_dividend_per_share is not None else None
            ),
            "split_ratio": float(row.split_ratio) if row.split_ratio is not None else None,
            "note": row.note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _validate_paging(*, page: int, page_size: int) -> Tuple[int, int]:
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be in [1, 100]")
        return page, page_size

    @staticmethod
    def _normalize_account_market(value: str) -> str:
        market = (value or "").strip().lower()
        if market not in VALID_ACCOUNT_MARKETS:
            raise ValueError("market must be one of: cn, hk, us, global")
        return market

    @staticmethod
    def _normalize_event_market(value: str) -> str:
        market = (value or "").strip().lower()
        if market not in VALID_EVENT_MARKETS:
            raise ValueError("market must be one of: cn, hk, us")
        return market

    @staticmethod
    def _infer_market_from_symbol(symbol: str) -> str:
        normalized = canonical_stock_code(symbol)
        if normalized.startswith("HK"):
            return "hk"
        if normalized.isdigit():
            if len(normalized) <= 5:
                return "hk"
            return "cn"
        return "us"

    def _resolve_snapshot_currency(
        self,
        *,
        account_rows: List[Any],
        requested_account_id: Optional[int],
    ) -> str:
        if not account_rows:
            return "CNY"
        if requested_account_id is not None or len(account_rows) == 1:
            return self._normalize_currency(account_rows[0].base_currency)
        currencies = {self._normalize_currency(row.base_currency) for row in account_rows}
        if len(currencies) == 1:
            return next(iter(currencies))
        return "CNY"

    @staticmethod
    def _normalize_broker_type(value: str) -> str:
        broker_type = (value or "").strip().lower()
        if not broker_type or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,31}", broker_type):
            raise ValueError("broker_type must use 2-32 lowercase letters, numbers, _ or -")
        return broker_type

    @staticmethod
    def _normalize_connection_name(value: str) -> str:
        connection_name = (value or "").strip()
        if not connection_name:
            raise ValueError("connection_name is required")
        return connection_name[:64]

    @staticmethod
    def _normalize_broker_account_ref(value: Optional[str]) -> Optional[str]:
        broker_account_ref = (value or "").strip()
        return broker_account_ref[:128] or None

    @staticmethod
    def _normalize_broker_connection_status(value: str) -> str:
        status = (value or "").strip().lower()
        if status not in VALID_BROKER_CONNECTION_STATUSES:
            raise ValueError("status must be one of: active, disabled, error")
        return status

    @staticmethod
    def _normalize_import_mode(value: str) -> str:
        import_mode = (value or "").strip().lower()
        if import_mode not in VALID_BROKER_IMPORT_MODES:
            raise ValueError("import_mode must be one of: file, manual, api")
        return import_mode

    @staticmethod
    def _serialize_sync_metadata(value: Optional[Dict[str, Any]]) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("sync_metadata must be an object")
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _normalize_currency(value: str) -> str:
        currency = (value or "").strip().upper()
        if not currency:
            raise ValueError("currency is required")
        return currency

    @staticmethod
    def _normalize_cost_method(value: str) -> str:
        method = (value or "").strip().lower()
        if method not in VALID_COST_METHODS:
            raise ValueError("cost_method must be fifo or avg")
        return method

    @staticmethod
    def _default_currency_for_market(market: str) -> str:
        if market == "hk":
            return "HKD"
        if market == "us":
            return "USD"
        return "CNY"
