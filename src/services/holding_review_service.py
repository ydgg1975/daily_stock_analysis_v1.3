# -*- coding: utf-8 -*-
"""Holding review packet assembly service."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Dict, List, Optional

from sqlalchemy import desc, or_, select

from src.repositories.portfolio_repo import PortfolioRepository
from src.services.portfolio_state_service import PortfolioStateService
from src.storage import AnalysisHistory, BacktestSummary, DatabaseManager, NewsIntel


class HoldingReviewService:
    """Build holding review packet from portfolio state and historical context."""

    def __init__(
        self,
        *,
        repo: Optional[PortfolioRepository] = None,
        db_manager: Optional[DatabaseManager] = None,
        portfolio_state_service: Optional[PortfolioStateService] = None,
    ):
        self.repo = repo or PortfolioRepository()
        self.db = db_manager or DatabaseManager.get_instance()
        self.portfolio_state_service = portfolio_state_service or PortfolioStateService(self.repo, self.db)

    def build_packet(self, *, portfolio_id: str = "default", as_of_date: Optional[date] = None) -> Dict:
        state = self.portfolio_state_service.build_state(portfolio_id=portfolio_id, as_of_date=as_of_date)
        items: List[Dict] = []
        for holding in state["holdings"]:
            latest_analysis = self.get_latest_analysis_for_code(holding["code"], as_of_date=as_of_date)
            recent_news = self.get_recent_news(
                query_id=latest_analysis.get("query_id") if latest_analysis else None,
                code=holding["code"],
                as_of_date=as_of_date,
            )
            items.append(
                {
                    **holding,
                    "latest_analysis": latest_analysis,
                    "recent_news": recent_news,
                    "news_count": len(recent_news),
                    "backtest_summary": self.get_latest_backtest_summary(holding["code"], as_of_date=as_of_date),
                }
            )
        return {
            "portfolio_id": portfolio_id,
            "as_of_date": state["as_of_date"],
            "items": items,
        }

    def get_latest_analysis_for_code(
        self,
        code: str,
        *,
        as_of_date: Optional[date],
        preferred_query_id: Optional[str] = None,
    ) -> Optional[Dict]:
        with self.db.get_session() as session:
            stmt = select(AnalysisHistory).where(AnalysisHistory.code == code)
            if as_of_date is not None:
                stmt = stmt.where(AnalysisHistory.created_at <= self._end_of_day(as_of_date))
            if preferred_query_id:
                stmt = stmt.order_by(
                    desc(AnalysisHistory.query_id == preferred_query_id),
                    desc(AnalysisHistory.created_at),
                )
            else:
                stmt = stmt.order_by(desc(AnalysisHistory.created_at))
            row = session.execute(stmt.limit(1)).scalar_one_or_none()
            if row is None:
                return None
            return {
                "id": row.id,
                "query_id": row.query_id,
                "report_type": row.report_type,
                "sentiment_score": row.sentiment_score,
                "operation_advice": row.operation_advice,
                "trend_prediction": row.trend_prediction,
                "analysis_summary": row.analysis_summary,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }

    def get_recent_news(self, *, query_id: Optional[str], code: str, as_of_date: Optional[date]) -> List[Dict]:
        with self.db.get_session() as session:
            stmt = select(NewsIntel)
            if query_id:
                stmt = stmt.where(NewsIntel.query_id == query_id)
            else:
                stmt = stmt.where(NewsIntel.code == code)
            if as_of_date is not None:
                cutoff = self._end_of_day(as_of_date)
                stmt = stmt.where(
                    or_(
                        NewsIntel.published_date.is_(None),
                        NewsIntel.published_date <= cutoff,
                    )
                )
                stmt = stmt.where(NewsIntel.fetched_at <= cutoff)
            rows = session.execute(
                stmt.order_by(desc(NewsIntel.published_date), desc(NewsIntel.fetched_at)).limit(3)
            ).scalars().all()
        return [
            {
                "title": row.title,
                "source": row.source,
                "published_date": row.published_date.isoformat() if row.published_date else None,
                "url": row.url,
            }
            for row in rows
        ]

    def get_latest_backtest_summary(self, code: str, *, as_of_date: Optional[date]) -> Optional[Dict]:
        with self.db.get_session() as session:
            stmt = select(BacktestSummary).where(
                BacktestSummary.scope == "stock",
                BacktestSummary.code == code,
            )
            if as_of_date is not None:
                stmt = stmt.where(BacktestSummary.computed_at <= self._end_of_day(as_of_date))
            row = session.execute(stmt.order_by(desc(BacktestSummary.computed_at)).limit(1)).scalar_one_or_none()
            if row is None:
                return None
            return {
                "total_evaluations": row.total_evaluations,
                "completed_count": row.completed_count,
                "win_count": row.win_count,
                "loss_count": row.loss_count,
                "win_rate_pct": row.win_rate_pct,
                "computed_at": row.computed_at.isoformat() if row.computed_at else None,
            }

    @staticmethod
    def _end_of_day(target_date: date) -> datetime:
        return datetime.combine(target_date, time.max)
