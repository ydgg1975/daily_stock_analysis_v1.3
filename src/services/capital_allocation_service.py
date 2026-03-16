# -*- coding: utf-8 -*-
"""Capital allocation gate service."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from src.services.portfolio_state_service import PortfolioStateService


class CapitalAllocationService:
    """Produce a simple rule-based capital allocation gate."""

    def __init__(
        self,
        *,
        portfolio_state_service: Optional[PortfolioStateService] = None,
        max_position_ratio: float = 0.8,
    ):
        self.portfolio_state_service = portfolio_state_service or PortfolioStateService()
        self.max_position_ratio = max_position_ratio

    def build_gate(self, *, portfolio_id: str = "default", as_of_date: Optional[date] = None) -> Dict:
        state = self.portfolio_state_service.build_state(portfolio_id=portfolio_id, as_of_date=as_of_date)
        available_position_ratio = max(self.max_position_ratio - state["position_ratio"], 0.0)
        reasons: List[str] = []
        allow_new_positions = True

        if available_position_ratio < 0.1:
            allow_new_positions = False
            reasons.append("position_limit_reached")
        if state["cash"] <= 0:
            allow_new_positions = False
            reasons.append("cash_unavailable")

        return {
            "portfolio_id": portfolio_id,
            "as_of_date": state["as_of_date"],
            "market_regime": "neutral",
            "current_position_ratio": state["position_ratio"],
            "max_position_ratio": self.max_position_ratio,
            "available_position_ratio": available_position_ratio,
            "allow_new_positions": allow_new_positions,
            "opportunity_budget": int(available_position_ratio / 0.2) if allow_new_positions else 0,
            "reasons": reasons,
        }
