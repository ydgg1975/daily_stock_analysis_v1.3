# -*- coding: utf-8 -*-
"""Derive current portfolio state from execution events."""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Optional

from sqlalchemy import desc, select

from src.repositories.portfolio_repo import PortfolioRepository
from src.storage import DatabaseManager, StockDaily


class PortfolioStateService:
    """Build portfolio state snapshots from append-only execution events."""

    def __init__(
        self,
        repo: Optional[PortfolioRepository] = None,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.repo = repo or PortfolioRepository()
        self.db = db_manager or DatabaseManager.get_instance()

    def build_state(self, *, portfolio_id: str = "default", as_of_date: Optional[date] = None) -> Dict:
        effective_date = as_of_date or date.today()
        events = self.repo.list_execution_events(portfolio_id=portfolio_id, as_of_date=effective_date)
        cash = 0.0
        total_realized_pnl = 0.0
        positions: Dict[str, Dict] = {}

        for event in events:
            side = event["side"]
            amount = float(event.get("amount") or 0.0)
            fees = float(event.get("fees") or 0.0)
            code = event.get("code")

            if side == "cash_in":
                cash += amount
                continue
            if side == "cash_out":
                cash -= amount
                continue
            if side == "fee":
                cash -= amount
                continue
            if not code:
                continue

            position = positions.setdefault(
                code,
                {
                    "code": code,
                    "quantity": 0.0,
                    "total_cost": 0.0,
                    "avg_cost": 0.0,
                    "opened_at": event["trade_date"],
                    "last_trade_at": event["trade_date"],
                },
            )
            quantity = float(event.get("quantity") or 0.0)
            price = float(event.get("price") or 0.0)

            if side == "buy":
                cash -= amount + fees
                position["total_cost"] += amount + fees
                position["quantity"] += quantity
                position["last_trade_at"] = event["trade_date"]
                if position["quantity"] > 0:
                    position["avg_cost"] = position["total_cost"] / position["quantity"]
            elif side == "sell":
                if position["quantity"] < quantity:
                    raise ValueError(f"Sell quantity exceeds current position for {code}")
                cash += amount - fees
                realized = (price - position["avg_cost"]) * quantity - fees
                total_realized_pnl += realized
                position["quantity"] -= quantity
                position["total_cost"] -= position["avg_cost"] * quantity
                position["last_trade_at"] = event["trade_date"]
                if position["quantity"] > 0:
                    position["avg_cost"] = position["total_cost"] / position["quantity"]
                else:
                    positions.pop(code, None)

        holdings = []
        total_market_value = 0.0
        total_unrealized_pnl = 0.0

        for code, position in positions.items():
            latest_price = self._get_latest_close(code=code, as_of_date=effective_date) or position["avg_cost"]
            market_value = position["quantity"] * latest_price
            unrealized_pnl = market_value - position["total_cost"]
            total_market_value += market_value
            total_unrealized_pnl += unrealized_pnl
            holding_days = self._holding_days(position["opened_at"], effective_date)
            holdings.append(
                {
                    "code": code,
                    "quantity": float(position["quantity"]),
                    "avg_cost": float(position["avg_cost"]),
                    "latest_price": float(latest_price),
                    "market_value": float(market_value),
                    "unrealized_pnl": float(unrealized_pnl),
                    "holding_days": holding_days,
                    "weight": 0.0,
                    "opened_at": position["opened_at"],
                    "last_trade_at": position["last_trade_at"],
                }
            )

        total_equity = cash + total_market_value
        position_ratio = (total_market_value / total_equity) if total_equity > 0 else 0.0
        for holding in holdings:
            holding["weight"] = (holding["market_value"] / total_equity) if total_equity > 0 else 0.0

        return {
            "portfolio_id": portfolio_id,
            "as_of_date": effective_date.isoformat(),
            "cash": float(cash),
            "market_value": float(total_market_value),
            "total_equity": float(total_equity),
            "position_ratio": float(position_ratio),
            "total_realized_pnl": float(total_realized_pnl),
            "total_unrealized_pnl": float(total_unrealized_pnl),
            "holdings": sorted(holdings, key=lambda item: item["code"]),
        }

    def _get_latest_close(self, *, code: str, as_of_date: date) -> Optional[float]:
        with self.db.get_session() as session:
            row = session.execute(
                select(StockDaily)
                .where(
                    StockDaily.code == code,
                    StockDaily.date <= as_of_date,
                )
                .order_by(desc(StockDaily.date))
                .limit(1)
            ).scalar_one_or_none()
            return float(row.close) if row and row.close is not None else None

    @staticmethod
    def _holding_days(opened_at: str, as_of_date: date) -> int:
        opened_date = datetime.fromisoformat(str(opened_at)).date() if "T" in str(opened_at) else date.fromisoformat(str(opened_at))
        return max((as_of_date - opened_date).days + 1, 1)
