# -*- coding: utf-8 -*-
"""Daily PnL snapshot generation service."""

from __future__ import annotations

import math
from datetime import date
from typing import Optional, Tuple

from src.repositories.portfolio_repo import PortfolioRepository
from src.services.portfolio_state_service import PortfolioStateService


class DailyPnlService:
    """Create and persist daily pnl snapshots."""

    def __init__(
        self,
        repo: Optional[PortfolioRepository] = None,
        portfolio_state_service: Optional[PortfolioStateService] = None,
    ):
        self.repo = repo or PortfolioRepository()
        self.portfolio_state_service = portfolio_state_service or PortfolioStateService(repo=self.repo)

    def generate_snapshot(self, *, portfolio_id: str = "default", trade_date: Optional[date] = None) -> dict:
        effective_date = trade_date or date.today()
        state = self.portfolio_state_service.build_state(portfolio_id=portfolio_id, as_of_date=effective_date)
        realized_pnl, win_trade_count, loss_trade_count = self._calculate_daily_realized_pnl(
            portfolio_id=portfolio_id,
            trade_date=effective_date,
        )
        snapshot = self.repo.upsert_daily_pnl_snapshot(
            {
                "portfolio_id": portfolio_id,
                "trade_date": effective_date,
                "cash": state["cash"],
                "market_value": state["market_value"],
                "total_equity": state["total_equity"],
                "realized_pnl": realized_pnl,
                "unrealized_pnl": state["total_unrealized_pnl"],
                "total_pnl": realized_pnl + state["total_unrealized_pnl"],
                "position_ratio": state["position_ratio"],
                "win_trade_count": win_trade_count,
                "loss_trade_count": loss_trade_count,
            }
        )
        return snapshot

    def _calculate_daily_realized_pnl(self, *, portfolio_id: str, trade_date: date) -> Tuple[float, int, int]:
        events = self.repo.list_execution_events(portfolio_id=portfolio_id, as_of_date=trade_date)
        positions = {}
        realized_today = 0.0
        win_trade_count = 0
        loss_trade_count = 0

        for event in events:
            side = event["side"]
            code = event.get("code")
            if not code:
                continue
            position = positions.setdefault(
                code,
                {
                    "quantity": 0.0,
                    "total_cost": 0.0,
                    "avg_cost": 0.0,
                },
            )
            quantity = float(event.get("quantity") or 0.0)
            price = float(event.get("price") or 0.0)
            amount = float(event.get("amount") or 0.0)
            fees = float(event.get("fees") or 0.0)
            self._validate_trade_event(
                side=side,
                code=code,
                quantity=quantity,
                price=price,
                amount=amount,
                fees=fees,
            )

            if side == "buy":
                position["total_cost"] += amount + fees
                position["quantity"] += quantity
                if position["quantity"] > 0:
                    position["avg_cost"] = position["total_cost"] / position["quantity"]
                continue

            if side != "sell":
                continue

            if position["quantity"] < quantity:
                raise ValueError(f"Sell quantity exceeds current position for {code}")
            realized_trade = (price - position["avg_cost"]) * quantity - fees
            if event["trade_date"] == trade_date.isoformat():
                realized_today += realized_trade
                if realized_trade > 0:
                    win_trade_count += 1
                elif realized_trade < 0:
                    loss_trade_count += 1

            position["quantity"] -= quantity
            position["total_cost"] -= position["avg_cost"] * quantity
            if position["quantity"] > 0:
                position["avg_cost"] = position["total_cost"] / position["quantity"]

        return float(realized_today), win_trade_count, loss_trade_count

    @staticmethod
    def _validate_trade_event(
        *,
        side: str,
        code: str,
        quantity: float,
        price: float,
        amount: float,
        fees: float,
    ) -> None:
        numeric_values = {
            "quantity": quantity,
            "price": price,
            "amount": amount,
            "fees": fees,
        }
        for field_name, value in numeric_values.items():
            if not math.isfinite(value):
                raise ValueError(f"Invalid non-finite {field_name} for {code}")

        if fees < 0:
            raise ValueError(f"Invalid negative fees for {code}")

        if side in {"buy", "sell"}:
            if quantity <= 0:
                raise ValueError(f"Invalid non-positive quantity for {code}")
            if price <= 0:
                raise ValueError(f"Invalid non-positive price for {code}")
            if amount <= 0:
                raise ValueError(f"Invalid non-positive amount for {code}")
            expected_amount = quantity * price
            if not math.isclose(amount, expected_amount, rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError(f"Inconsistent trade amount for {code}")
