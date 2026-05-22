# -*- coding: utf-8 -*-
"""Paper trading preparation and guarded execution service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

from src.services.portfolio_service import PortfolioService


@dataclass
class PaperTradingLimits:
    max_order_value_pct: float = 20.0
    max_position_weight_pct: float = 35.0
    daily_trade_limit: int = 10
    max_loss_pct: float = 10.0


class PaperTradingService:
    """Prepare and record paper trades without touching real broker APIs."""

    def __init__(
        self,
        *,
        portfolio_service: Optional[PortfolioService] = None,
        limits: Optional[PaperTradingLimits] = None,
    ):
        self.portfolio_service = portfolio_service or PortfolioService()
        self.limits = limits or PaperTradingLimits()

    def prepare_order(
        self,
        *,
        account_id: int,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        trade_date: Optional[date] = None,
        market: Optional[str] = None,
        currency: Optional[str] = None,
        reason: Optional[str] = None,
        cost_method: str = "fifo",
    ) -> Dict[str, Any]:
        trade_date = trade_date or date.today()
        side_norm = self._normalize_side(side)
        self._validate_positive(quantity=quantity, price=price)
        snapshot = self.portfolio_service.get_portfolio_snapshot(
            account_id=account_id,
            as_of=trade_date,
            cost_method=cost_method,
        )
        order_value = float(quantity) * float(price)
        risk_checks = self._build_risk_checks(
            snapshot=snapshot,
            symbol=symbol,
            side=side_norm,
            order_value=order_value,
            trade_date=trade_date,
        )
        order = {
            "account_id": account_id,
            "symbol": str(symbol).strip().upper(),
            "side": side_norm,
            "quantity": float(quantity),
            "price": float(price),
            "trade_date": trade_date.isoformat(),
            "market": market,
            "currency": currency,
            "reason": (reason or "").strip() or None,
            "order_value": round(order_value, 6),
        }
        approval_token = self._approval_token(order, risk_checks)
        return {
            "status": "approval_required",
            "mode": "paper",
            "broker_execution": "disabled",
            "approval_token": approval_token,
            "order": order,
            "risk_checks": risk_checks,
            "can_execute_after_approval": not any(item["level"] == "block" for item in risk_checks),
        }

    def execute_approved_order(
        self,
        *,
        prepared_order: Dict[str, Any],
        approval_token: str,
        approved: bool,
    ) -> Dict[str, Any]:
        if not approved:
            return {"status": "rejected", "mode": "paper", "reason": "approval was not granted"}
        expected = str(prepared_order.get("approval_token") or "")
        if not expected or approval_token != expected:
            raise ValueError("approval_token does not match prepared order")
        if not prepared_order.get("can_execute_after_approval", False):
            return {
                "status": "blocked",
                "mode": "paper",
                "risk_checks": prepared_order.get("risk_checks", []),
            }

        order = dict(prepared_order.get("order") or {})
        if not order:
            raise ValueError("prepared_order is missing order payload")
        trade_date = date.fromisoformat(str(order["trade_date"]))
        note = self._execution_note(order, prepared_order)
        trade = self.portfolio_service.record_trade(
            account_id=int(order["account_id"]),
            symbol=str(order["symbol"]),
            trade_date=trade_date,
            side=str(order["side"]),
            quantity=float(order["quantity"]),
            price=float(order["price"]),
            market=order.get("market"),
            currency=order.get("currency"),
            trade_uid=f"paper:{approval_token[:24]}",
            note=note,
        )
        return {
            "status": "executed",
            "mode": "paper",
            "trade_id": trade["id"],
            "broker_execution": "disabled",
            "order": order,
        }

    @staticmethod
    def _normalize_side(side: str) -> str:
        side_norm = str(side or "").strip().lower()
        if side_norm not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        return side_norm

    @staticmethod
    def _validate_positive(*, quantity: float, price: float) -> None:
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity and price must be > 0")

    def _build_risk_checks(
        self,
        *,
        snapshot: Dict[str, Any],
        symbol: str,
        side: str,
        order_value: float,
        trade_date: date,
    ) -> List[Dict[str, Any]]:
        total_equity = float(snapshot.get("total_equity") or snapshot.get("total_market_value") or 0.0)
        checks = [
            self._order_value_check(order_value=order_value, total_equity=total_equity),
            self._position_weight_check(
                snapshot=snapshot,
                symbol=symbol,
                side=side,
                order_value=order_value,
                total_equity=total_equity,
            ),
            self._daily_trade_limit_check(
                account_id=self._single_account_id(snapshot),
                trade_date=trade_date,
            ),
            self._loss_limit_check(snapshot=snapshot),
        ]
        return checks

    def _order_value_check(self, *, order_value: float, total_equity: float) -> Dict[str, Any]:
        weight = (order_value / total_equity * 100.0) if total_equity > 0 else 0.0
        return {
            "name": "max_order_value_pct",
            "level": "block" if weight > self.limits.max_order_value_pct else "pass",
            "observed_pct": round(weight, 4),
            "limit_pct": self.limits.max_order_value_pct,
        }

    def _position_weight_check(
        self,
        *,
        snapshot: Dict[str, Any],
        symbol: str,
        side: str,
        order_value: float,
        total_equity: float,
    ) -> Dict[str, Any]:
        current_value = 0.0
        target_symbol = str(symbol or "").strip().upper()
        for account in snapshot.get("accounts", []) or []:
            for pos in account.get("positions", []) or []:
                if str(pos.get("symbol") or "").strip().upper() == target_symbol:
                    current_value += float(pos.get("market_value_base") or 0.0)
        projected = current_value + order_value if side == "buy" else max(0.0, current_value - order_value)
        weight = (projected / total_equity * 100.0) if total_equity > 0 else 0.0
        return {
            "name": "max_position_weight_pct",
            "level": "block" if weight > self.limits.max_position_weight_pct else "pass",
            "observed_pct": round(weight, 4),
            "limit_pct": self.limits.max_position_weight_pct,
        }

    def _daily_trade_limit_check(self, *, account_id: Optional[int], trade_date: date) -> Dict[str, Any]:
        trade_count = 0
        if account_id is not None:
            trades = self.portfolio_service.list_trade_events(
                account_id=account_id,
                date_from=trade_date,
                date_to=trade_date,
                page=1,
                page_size=100,
            )
            trade_count = int(trades.get("total") or 0)
        projected = trade_count + 1
        return {
            "name": "daily_trade_limit",
            "level": "block" if projected > self.limits.daily_trade_limit else "pass",
            "observed_count": projected,
            "limit_count": self.limits.daily_trade_limit,
        }

    def _loss_limit_check(self, *, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        total_cost = 0.0
        total_unrealized = 0.0
        for account in snapshot.get("accounts", []) or []:
            total_unrealized += float(account.get("unrealized_pnl") or 0.0)
            for pos in account.get("positions", []) or []:
                total_cost += float(pos.get("total_cost") or 0.0)
        loss_pct = abs(total_unrealized) / total_cost * 100.0 if total_cost > 0 and total_unrealized < 0 else 0.0
        return {
            "name": "max_loss_pct",
            "level": "block" if loss_pct > self.limits.max_loss_pct else "pass",
            "observed_pct": round(loss_pct, 4),
            "limit_pct": self.limits.max_loss_pct,
        }

    @staticmethod
    def _single_account_id(snapshot: Dict[str, Any]) -> Optional[int]:
        accounts = list(snapshot.get("accounts", []) or [])
        if len(accounts) != 1:
            return None
        try:
            return int(accounts[0].get("account_id"))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _approval_token(order: Dict[str, Any], risk_checks: List[Dict[str, Any]]) -> str:
        payload = json.dumps({"order": order, "risk_checks": risk_checks}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _execution_note(order: Dict[str, Any], prepared_order: Dict[str, Any]) -> str:
        reason = order.get("reason") or "No reason provided"
        blocked = [item["name"] for item in prepared_order.get("risk_checks", []) if item.get("level") == "block"]
        suffix = f"; blocked_checks={','.join(blocked)}" if blocked else ""
        return f"paper_trade; reason={reason}{suffix}"
