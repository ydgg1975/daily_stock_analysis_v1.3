# -*- coding: utf-8 -*-
"""Repository helpers for the Market Scanner domain."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select

from src.storage import (
    DatabaseManager,
    MarketScannerCandidate,
    MarketScannerRun,
)


class ScannerRepository:
    """Persistence layer for scanner runs and shortlisted candidates."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def save_run_with_candidates(
        self,
        *,
        run: MarketScannerRun,
        candidates: List[MarketScannerCandidate],
    ) -> MarketScannerRun:
        with self.db.get_session() as session:
            session.add(run)
            session.flush()
            for candidate in candidates:
                candidate.run_id = run.id
            session.add_all(candidates)
            session.commit()
            session.refresh(run)
            return run

    def get_runs_paginated(
        self,
        *,
        market: Optional[str],
        profile: Optional[str],
        offset: int,
        limit: int,
    ) -> Tuple[List[MarketScannerRun], int]:
        with self.db.get_session() as session:
            conditions = []
            if market:
                conditions.append(MarketScannerRun.market == market)
            if profile:
                conditions.append(MarketScannerRun.profile == profile)

            where_clause = and_(*conditions) if conditions else True
            total = session.execute(
                select(func.count(MarketScannerRun.id)).where(where_clause)
            ).scalar() or 0
            rows = session.execute(
                select(MarketScannerRun)
                .where(where_clause)
                .order_by(desc(MarketScannerRun.run_at))
                .offset(offset)
                .limit(limit)
            ).scalars().all()
            return list(rows), int(total)

    def get_run(self, run_id: int) -> Optional[MarketScannerRun]:
        with self.db.get_session() as session:
            return session.execute(
                select(MarketScannerRun)
                .where(MarketScannerRun.id == run_id)
                .limit(1)
            ).scalar_one_or_none()

    def get_recent_runs(
        self,
        *,
        market: Optional[str],
        profile: Optional[str],
        limit: int = 20,
    ) -> List[MarketScannerRun]:
        with self.db.get_session() as session:
            conditions = []
            if market:
                conditions.append(MarketScannerRun.market == market)
            if profile:
                conditions.append(MarketScannerRun.profile == profile)

            where_clause = and_(*conditions) if conditions else True
            rows = session.execute(
                select(MarketScannerRun)
                .where(where_clause)
                .order_by(desc(MarketScannerRun.run_at), desc(MarketScannerRun.id))
                .limit(limit)
            ).scalars().all()
            return list(rows)

    def get_runs_before(
        self,
        *,
        market: Optional[str],
        profile: Optional[str],
        run_at: datetime,
        run_id: int,
        limit: int = 20,
    ) -> List[MarketScannerRun]:
        with self.db.get_session() as session:
            conditions = [
                or_(
                    MarketScannerRun.run_at < run_at,
                    and_(MarketScannerRun.run_at == run_at, MarketScannerRun.id < run_id),
                )
            ]
            if market:
                conditions.append(MarketScannerRun.market == market)
            if profile:
                conditions.append(MarketScannerRun.profile == profile)

            rows = session.execute(
                select(MarketScannerRun)
                .where(and_(*conditions))
                .order_by(desc(MarketScannerRun.run_at), desc(MarketScannerRun.id))
                .limit(limit)
            ).scalars().all()
            return list(rows)

    def get_candidates_for_run(self, run_id: int) -> List[MarketScannerCandidate]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(MarketScannerCandidate)
                .where(MarketScannerCandidate.run_id == run_id)
                .order_by(MarketScannerCandidate.rank.asc(), MarketScannerCandidate.id.asc())
            ).scalars().all()
            return list(rows)

    def count_recent_symbol_mentions(
        self,
        *,
        symbol: str,
        market: str,
        profile: str,
        exclude_run_id: Optional[int] = None,
        recent_run_limit: int = 5,
    ) -> int:
        with self.db.get_session() as session:
            recent_run_query = (
                select(MarketScannerRun.id)
                .where(
                    and_(
                        MarketScannerRun.market == market,
                        MarketScannerRun.profile == profile,
                    )
                )
                .order_by(desc(MarketScannerRun.run_at))
            )
            if exclude_run_id is not None:
                recent_run_query = recent_run_query.where(MarketScannerRun.id != exclude_run_id)
            recent_run_ids = session.execute(recent_run_query.limit(recent_run_limit)).scalars().all()
            if not recent_run_ids:
                return 0

            return int(
                session.execute(
                    select(func.count(func.distinct(MarketScannerCandidate.run_id)))
                    .where(
                        and_(
                            MarketScannerCandidate.symbol == symbol,
                            MarketScannerCandidate.run_id.in_(recent_run_ids),
                        )
                    )
                ).scalar() or 0
            )

    def update_run(
        self,
        run_id: int,
        *,
        status: Optional[str] = None,
        source_summary: Optional[str] = None,
        summary_json: Optional[str] = None,
        diagnostics_json: Optional[str] = None,
        universe_notes_json: Optional[str] = None,
        scoring_notes_json: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        shortlist_size: Optional[int] = None,
        universe_size: Optional[int] = None,
        preselected_size: Optional[int] = None,
        evaluated_size: Optional[int] = None,
    ) -> Optional[MarketScannerRun]:
        with self.db.get_session() as session:
            run = session.execute(
                select(MarketScannerRun)
                .where(MarketScannerRun.id == run_id)
                .limit(1)
            ).scalar_one_or_none()
            if run is None:
                return None

            if status is not None:
                run.status = status
            if source_summary is not None:
                run.source_summary = source_summary
            if summary_json is not None:
                run.summary_json = summary_json
            if diagnostics_json is not None:
                run.diagnostics_json = diagnostics_json
            if universe_notes_json is not None:
                run.universe_notes_json = universe_notes_json
            if scoring_notes_json is not None:
                run.scoring_notes_json = scoring_notes_json
            if completed_at is not None:
                run.completed_at = completed_at
            if shortlist_size is not None:
                run.shortlist_size = int(shortlist_size)
            if universe_size is not None:
                run.universe_size = int(universe_size)
            if preselected_size is not None:
                run.preselected_size = int(preselected_size)
            if evaluated_size is not None:
                run.evaluated_size = int(evaluated_size)

            session.add(run)
            session.commit()
            session.refresh(run)
            return run
