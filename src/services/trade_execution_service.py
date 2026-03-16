# -*- coding: utf-8 -*-
"""Portfolio execution recording service."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.repositories.portfolio_repo import PortfolioRepository

SUPPORTED_EXECUTION_SIDES = {"buy", "sell", "cash_in", "cash_out", "fee"}


class TradeExecutionService:
    """Validate and persist execution events."""

    def __init__(self, repo: Optional[PortfolioRepository] = None):
        self.repo = repo or PortfolioRepository()

    def record_execution(
        self,
        *,
        portfolio_id: str,
        executed_at: datetime,
        side: str,
        code: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        amount: Optional[float] = None,
        fees: float = 0.0,
        note: Optional[str] = None,
        plan_id: Optional[str] = None,
    ) -> dict:
        normalized_side = (side or "").strip().lower()
        if normalized_side not in SUPPORTED_EXECUTION_SIDES:
            raise ValueError(f"Unsupported execution side: {side}")

        normalized_code = (code or "").strip().upper() or None
        quantity_value = float(quantity or 0.0)
        price_value = float(price or 0.0)
        amount_value = float(amount or 0.0)
        fee_value = float(fees or 0.0)

        if normalized_side in {"buy", "sell"}:
            if not normalized_code:
                raise ValueError("Trade execution requires stock code")
            if quantity_value <= 0 or price_value <= 0:
                raise ValueError("Trade execution requires positive quantity and price")
            amount_value = quantity_value * price_value
        else:
            if amount_value <= 0:
                raise ValueError(f"{normalized_side} execution requires positive amount")

        persisted = self.repo.add_execution_event(
            {
                "portfolio_id": portfolio_id,
                "executed_at": executed_at,
                "trade_date": executed_at.date(),
                "side": normalized_side,
                "code": normalized_code,
                "quantity": quantity_value,
                "price": price_value,
                "amount": amount_value,
                "fees": fee_value,
                "note": note,
                "plan_id": plan_id,
            }
        )
        persisted["gross_amount"] = amount_value
        persisted["net_cash_flow"] = self._calculate_net_cash_flow(
            side=normalized_side,
            amount=amount_value,
            fees=fee_value,
        )
        return persisted

    @staticmethod
    def _calculate_net_cash_flow(*, side: str, amount: float, fees: float) -> float:
        if side == "buy":
            return -(amount + fees)
        if side == "sell":
            return amount - fees
        if side == "cash_in":
            return amount
        if side == "cash_out":
            return -amount
        return -amount
