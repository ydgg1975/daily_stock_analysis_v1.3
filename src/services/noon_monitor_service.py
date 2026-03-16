# -*- coding: utf-8 -*-
"""Noon monitor packet service."""

from __future__ import annotations

from datetime import date
from typing import Dict, Optional

from src.services.candidate_pool_service import CandidatePoolService
from src.services.holding_review_service import HoldingReviewService


class NoonMonitorService:
    """Combine holdings and candidate watchlist into a noon monitor packet."""

    def __init__(
        self,
        *,
        holding_review_service: Optional[HoldingReviewService] = None,
        candidate_pool_service: Optional[CandidatePoolService] = None,
    ):
        self.holding_review_service = holding_review_service or HoldingReviewService()
        self.candidate_pool_service = candidate_pool_service or CandidatePoolService()

    def build_packet(self, *, portfolio_id: str = "default", as_of_date: Optional[date] = None) -> Dict:
        holding_review = self.holding_review_service.build_packet(
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
        )
        candidate_pool = self.candidate_pool_service.build_pool(as_of_date=as_of_date)
        watchlist = []
        for item in candidate_pool["items"][:5]:
            watchlist.append(
                {
                    "code": item["code"],
                    "name": item.get("name"),
                    "final_rank": item.get("final_rank"),
                    "recommendation_source": item.get("recommendation_source"),
                    "ai_operation_advice": item.get("ai_operation_advice"),
                }
            )
        return {
            "portfolio_id": portfolio_id,
            "as_of_date": holding_review["as_of_date"],
            "holdings": holding_review["items"],
            "watchlist": watchlist,
        }
