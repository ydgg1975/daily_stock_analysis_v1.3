# -*- coding: utf-8 -*-
"""Stock research packet service."""

from __future__ import annotations

from datetime import date
from typing import Dict, Optional

from src.services.candidate_pool_service import CandidatePoolService
from src.services.holding_review_service import HoldingReviewService
from src.storage import DatabaseManager


class StockResearchService:
    """Enrich candidate pool items with analysis and news context."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        candidate_pool_service: Optional[CandidatePoolService] = None,
        holding_review_service: Optional[HoldingReviewService] = None,
    ):
        self.db = db_manager or DatabaseManager.get_instance()
        self.candidate_pool_service = candidate_pool_service or CandidatePoolService(self.db)
        self.holding_review_service = holding_review_service or HoldingReviewService(db_manager=self.db)

    def build_packet(self, *, as_of_date: Optional[date] = None) -> Dict:
        candidate_pool = self.candidate_pool_service.build_pool(as_of_date=as_of_date)
        enriched = []
        for item in candidate_pool["items"]:
            latest_analysis = self.holding_review_service.get_latest_analysis_for_code(
                item["code"],
                as_of_date=as_of_date,
                preferred_query_id=item.get("ai_query_id"),
            )
            recent_news = self.holding_review_service.get_recent_news(
                query_id=item.get("ai_query_id"),
                code=item["code"],
                as_of_date=as_of_date,
            )
            backtest_summary = self.holding_review_service.get_latest_backtest_summary(
                item["code"],
                as_of_date=as_of_date,
            )
            enriched.append(
                {
                    **item,
                    "latest_analysis": latest_analysis,
                    "recent_news": recent_news,
                    "backtest_summary": backtest_summary,
                }
            )
        return {
            "run_id": candidate_pool["run_id"],
            "trade_date": candidate_pool["trade_date"],
            "items": enriched,
        }
