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

    def get_performance(
        self,
        *,
        account_id: Optional[int] = None,
        as_of: Optional[date] = None,
        cost_method: str = "fifo",
        eval_window_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        as_of_date = as_of or date.today()
        trades = self._list_all_paper_trades(account_id=account_id)
        snapshot = self.portfolio_service.get_portfolio_snapshot(
            account_id=account_id,
            as_of=as_of_date,
            cost_method=cost_method,
        )
        latest_prices = self._latest_prices_by_symbol(snapshot)
        rows = self._build_trade_performance_rows(trades=trades, latest_prices=latest_prices, as_of=as_of_date)
        closed = [item for item in rows if item["status"] == "closed"]
        wins = [item for item in rows if item["outcome"] == "win"]
        losses = [item for item in rows if item["outcome"] == "loss"]
        avg_return = sum(float(item["return_pct"]) for item in rows) / len(rows) if rows else 0.0
        backtest = self._backtest_comparison(eval_window_days=eval_window_days)
        return {
            "as_of": as_of_date.isoformat(),
            "mode": "paper",
            "account_id": account_id,
            "cost_method": cost_method,
            "total_trades": len(rows),
            "open_trades": len(rows) - len(closed),
            "closed_trades": len(closed),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate_pct": round(len(wins) / len(closed) * 100.0, 6) if closed else None,
            "avg_return_pct": round(avg_return, 6),
            "items": rows,
            "backtest_comparison": backtest,
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

    def _list_all_paper_trades(self, *, account_id: Optional[int]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        page = 1
        page_size = 100
        while True:
            data = self.portfolio_service.list_trade_events(
                account_id=account_id,
                page=page,
                page_size=page_size,
            )
            batch = list(data.get("items") or [])
            items.extend(item for item in batch if self._is_paper_trade(item))
            total = int(data.get("total") or len(batch))
            if page * page_size >= total or not batch:
                break
            page += 1
        return items

    @staticmethod
    def _is_paper_trade(item: Dict[str, Any]) -> bool:
        trade_uid = str(item.get("trade_uid") or "")
        note = str(item.get("note") or "")
        return trade_uid.startswith("paper:") or "paper_trade" in note

    @staticmethod
    def _latest_prices_by_symbol(snapshot: Dict[str, Any]) -> Dict[str, float]:
        prices: Dict[str, float] = {}
        for account in snapshot.get("accounts", []) or []:
            for position in account.get("positions", []) or []:
                symbol = str(position.get("symbol") or "").upper()
                if not symbol:
                    continue
                if position.get("price_available") is False:
                    continue
                try:
                    price = float(position.get("last_price") or 0.0)
                except (TypeError, ValueError):
                    price = 0.0
                if price > 0:
                    prices[symbol] = price
        return prices

    @staticmethod
    def _build_trade_performance_rows(
        *,
        trades: List[Dict[str, Any]],
        latest_prices: Dict[str, float],
        as_of: date,
    ) -> List[Dict[str, Any]]:
        sorted_trades = sorted(trades, key=lambda item: (str(item.get("trade_date") or ""), int(item.get("id") or 0)))
        buy_rows: List[Dict[str, Any]] = []
        open_lots: Dict[str, List[Dict[str, Any]]] = {}
        for trade in sorted_trades:
            symbol = str(trade.get("symbol") or "").upper()
            side = str(trade.get("side") or "").lower()
            quantity = float(trade.get("quantity") or 0.0)
            price = float(trade.get("price") or 0.0)
            trade_date = date.fromisoformat(str(trade.get("trade_date")))
            if side == "buy":
                row = {
                    "trade_id": int(trade.get("id") or 0),
                    "trade_uid": trade.get("trade_uid"),
                    "symbol": symbol,
                    "entry_date": trade_date,
                    "entry_price": price,
                    "quantity": quantity,
                    "remaining_quantity": quantity,
                    "realized_pnl": 0.0,
                    "exit_date": None,
                    "exit_price": None,
                    "note": trade.get("note"),
                }
                buy_rows.append(row)
                open_lots.setdefault(symbol, []).append(row)
                continue
            if side != "sell" or quantity <= 0:
                continue
            remaining_sell = quantity
            for lot in open_lots.get(symbol, []):
                if remaining_sell <= 0:
                    break
                lot_remaining = float(lot["remaining_quantity"])
                if lot_remaining <= 0:
                    continue
                consumed = min(lot_remaining, remaining_sell)
                lot["realized_pnl"] += consumed * (price - float(lot["entry_price"]))
                lot["remaining_quantity"] = round(lot_remaining - consumed, 10)
                lot["exit_date"] = trade_date
                lot["exit_price"] = price
                remaining_sell -= consumed
        result: List[Dict[str, Any]] = []
        for row in buy_rows:
            entry_date = row["entry_date"]
            remaining_quantity = float(row["remaining_quantity"])
            latest_price = latest_prices.get(row["symbol"])
            exit_date = row["exit_date"]
            exit_price = row["exit_price"]
            status = "closed" if remaining_quantity <= 0 else "open"
            mark_price = float(exit_price if status == "closed" else latest_price or row["entry_price"])
            unrealized_pnl = remaining_quantity * (mark_price - float(row["entry_price"])) if status == "open" else 0.0
            total_pnl = float(row["realized_pnl"]) + unrealized_pnl
            basis = float(row["quantity"]) * float(row["entry_price"])
            return_pct = total_pnl / basis * 100.0 if basis > 0 else 0.0
            holding_until = exit_date if status == "closed" and exit_date else as_of
            holding_days = max(0, (holding_until - entry_date).days)
            outcome = "win" if return_pct > 0 else "loss" if return_pct < 0 else "flat"
            result.append(
                {
                    "trade_id": row["trade_id"],
                    "trade_uid": row["trade_uid"],
                    "symbol": row["symbol"],
                    "entry_date": entry_date.isoformat(),
                    "exit_date": exit_date.isoformat() if exit_date else None,
                    "status": status,
                    "outcome": outcome,
                    "quantity": round(float(row["quantity"]), 8),
                    "remaining_quantity": round(remaining_quantity, 8),
                    "entry_price": round(float(row["entry_price"]), 8),
                    "mark_price": round(mark_price, 8),
                    "exit_price": round(float(exit_price), 8) if exit_price is not None else None,
                    "pnl": round(total_pnl, 8),
                    "return_pct": round(return_pct, 8),
                    "holding_days": holding_days,
                    "note": row["note"],
                }
            )
        return result

    @staticmethod
    def _backtest_comparison(*, eval_window_days: Optional[int]) -> Optional[Dict[str, Any]]:
        try:
            from src.services.backtest_service import BacktestService

            summary = BacktestService().get_global_summary(eval_window_days=eval_window_days)
        except Exception:
            return None
        if not summary:
            return None
        return {
            "scope": summary.get("scope"),
            "eval_window_days": summary.get("eval_window_days"),
            "win_rate_pct": summary.get("win_rate_pct"),
            "avg_return_pct": summary.get("avg_simulated_return_pct"),
            "total_evaluations": summary.get("total_evaluations"),
        }
