# -*- coding: utf-8 -*-
"""Build shared runtime objects from existing storage and services."""

from __future__ import annotations

from datetime import date
from typing import Dict, Optional

from src.repositories.portfolio_repo import PortfolioRepository
from src.services.capital_allocation_service import CapitalAllocationService
from src.services.candidate_pool_service import CandidatePoolService
from src.services.daily_pnl_service import DailyPnlService
from src.services.holding_review_service import HoldingReviewService
from src.services.noon_monitor_service import NoonMonitorService
from src.services.portfolio_state_service import PortfolioStateService
from src.services.stock_research_service import StockResearchService
from src.storage import DatabaseManager

RUNTIME_SCHEMA_VERSIONS = {
    "portfolio_state": "1.0",
    "trade_execution_log": "1.0",
    "daily_pnl_log": "1.0",
    "holding_review_packet": "1.0",
    "capital_allocation_gate": "1.0",
    "candidate_pool": "1.0",
    "stock_research_packet": "1.0",
    "noon_monitor_packet": "1.0",
}


class RuntimeObjectBuilder:
    """Assemble shared runtime objects with stable names and lightweight schemas."""

    def __init__(
        self,
        *,
        repo: Optional[PortfolioRepository] = None,
        db_manager: Optional[DatabaseManager] = None,
        portfolio_state_service: Optional[PortfolioStateService] = None,
        daily_pnl_service: Optional[DailyPnlService] = None,
    ):
        self.repo = repo or PortfolioRepository()
        self.db = db_manager or DatabaseManager.get_instance()
        self.portfolio_state_service = portfolio_state_service or PortfolioStateService(self.repo, self.db)
        self.daily_pnl_service = daily_pnl_service or DailyPnlService(self.repo, self.portfolio_state_service)
        self.holding_review_service = HoldingReviewService(
            repo=self.repo,
            db_manager=self.db,
            portfolio_state_service=self.portfolio_state_service,
        )
        self.capital_allocation_service = CapitalAllocationService(
            portfolio_state_service=self.portfolio_state_service,
        )
        self.candidate_pool_service = CandidatePoolService(self.db)
        self.stock_research_service = StockResearchService(
            db_manager=self.db,
            candidate_pool_service=self.candidate_pool_service,
            holding_review_service=self.holding_review_service,
        )
        self.noon_monitor_service = NoonMonitorService(
            holding_review_service=self.holding_review_service,
            candidate_pool_service=self.candidate_pool_service,
        )

    def build_object(
        self,
        object_name: str,
        *,
        portfolio_id: str = "default",
        as_of_date: Optional[date] = None,
    ) -> Dict:
        normalized_name = (object_name or "").strip()
        if normalized_name == "portfolio_state":
            return self.portfolio_state_service.build_state(portfolio_id=portfolio_id, as_of_date=as_of_date)
        if normalized_name == "trade_execution_log":
            return self.build_trade_execution_log(portfolio_id=portfolio_id, as_of_date=as_of_date)
        if normalized_name == "daily_pnl_log":
            return self.build_daily_pnl_log(portfolio_id=portfolio_id, as_of_date=as_of_date)
        if normalized_name == "holding_review_packet":
            return self.holding_review_service.build_packet(portfolio_id=portfolio_id, as_of_date=as_of_date)
        if normalized_name == "capital_allocation_gate":
            return self.capital_allocation_service.build_gate(portfolio_id=portfolio_id, as_of_date=as_of_date)
        if normalized_name == "candidate_pool":
            return self.candidate_pool_service.build_pool(as_of_date=as_of_date)
        if normalized_name == "stock_research_packet":
            return self.stock_research_service.build_packet(as_of_date=as_of_date)
        if normalized_name == "noon_monitor_packet":
            return self.noon_monitor_service.build_packet(portfolio_id=portfolio_id, as_of_date=as_of_date)
        raise ValueError(f"Unsupported runtime object: {object_name}")

    def build_trade_execution_log(self, *, portfolio_id: str, as_of_date: Optional[date]) -> Dict:
        return {
            "portfolio_id": portfolio_id,
            "as_of_date": as_of_date.isoformat() if as_of_date else None,
            "items": self.repo.list_execution_events(portfolio_id=portfolio_id, as_of_date=as_of_date),
        }

    def build_daily_pnl_log(self, *, portfolio_id: str, as_of_date: Optional[date]) -> Dict:
        items = list(
            reversed(
                self.repo.list_daily_pnl_snapshots(
                    portfolio_id=portfolio_id,
                    as_of_date=as_of_date,
                )
            )
        )
        return {
            "portfolio_id": portfolio_id,
            "as_of_date": as_of_date.isoformat() if as_of_date else None,
            "items": items,
        }
