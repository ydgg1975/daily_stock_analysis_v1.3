# -*- coding: utf-8 -*-
"""Backtest repository.

Provides database access helpers for backtest tables.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import and_, delete, desc, func, select

from src.storage import BacktestResult, BacktestRun, BacktestSummary, DatabaseManager, AnalysisHistory

logger = logging.getLogger(__name__)


class BacktestRepository:
    """DB access layer for backtesting."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def get_candidates(
        self,
        *,
        code: Optional[str],
        min_age_days: int,
        limit: int,
        eval_window_days: int,
        engine_version: str,
        force: bool,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[AnalysisHistory]:
        """Return AnalysisHistory rows eligible for backtest."""
        cutoff_dt = datetime.now() - timedelta(days=min_age_days)

        with self.db.get_session() as session:
            conditions = [AnalysisHistory.created_at <= cutoff_dt]
            if not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.db.require_user_id(owner_id))
            if code:
                conditions.append(AnalysisHistory.code == code)

            query = select(AnalysisHistory).where(and_(*conditions))

            if not force:
                existing_ids = select(BacktestResult.analysis_history_id).where(
                    and_(
                        BacktestResult.eval_window_days == eval_window_days,
                        BacktestResult.engine_version == engine_version,
                    )
                )
                query = query.where(AnalysisHistory.id.not_in(existing_ids))

            query = query.order_by(desc(AnalysisHistory.created_at)).limit(limit)
            rows = session.execute(query).scalars().all()
            return list(rows)

    def save_run(self, run: BacktestRun) -> BacktestRun:
        run.owner_id = self.db.require_user_id(getattr(run, "owner_id", None))
        with self.db.get_session() as session:
            session.add(run)
            session.commit()
            session.refresh(run)
        if getattr(run, "id", None) is not None:
            self.db.sync_phase_e_analysis_backtest_shadow(int(run.id))
        return run

    def get_runs_paginated(
        self,
        *,
        code: Optional[str] = None,
        offset: int,
        limit: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Tuple[List[BacktestRun], int]:
        with self.db.get_session() as session:
            conditions = []
            if not include_all_owners:
                conditions.append(BacktestRun.owner_id == self.db.require_user_id(owner_id))
            if code:
                conditions.append(BacktestRun.code == code)
            where_clause = and_(*conditions) if conditions else True

            total = session.execute(select(func.count(BacktestRun.id)).where(where_clause)).scalar() or 0
            rows = session.execute(
                select(BacktestRun)
                .where(where_clause)
                .order_by(desc(BacktestRun.run_at))
                .offset(offset)
                .limit(limit)
            ).scalars().all()
            return list(rows), int(total)

    def get_run(
        self,
        run_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[BacktestRun]:
        with self.db.get_session() as session:
            conditions = [BacktestRun.id == run_id]
            if not include_all_owners:
                conditions.append(BacktestRun.owner_id == self.db.require_user_id(owner_id))
            return session.execute(
                select(BacktestRun).where(and_(*conditions)).limit(1)
            ).scalar_one_or_none()

    def delete_runs_by_code(
        self,
        *,
        code: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        resolved_owner_id = None if include_all_owners else self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            conditions = [BacktestRun.code == code]
            if not include_all_owners:
                conditions.append(BacktestRun.owner_id == resolved_owner_id)
            deleted = session.execute(
                delete(BacktestRun).where(and_(*conditions))
            ).rowcount or 0
            session.commit()
        self.db.delete_phase_e_analysis_backtest_shadow_by_code(
            code=code,
            owner_id=resolved_owner_id,
            include_all_owners=include_all_owners,
        )
        return int(deleted)

    def delete_results_by_code(
        self,
        *,
        code: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        with self.db.get_session() as session:
            conditions = [BacktestResult.code == code]
            if not include_all_owners:
                conditions.append(BacktestResult.owner_id == self.db.require_user_id(owner_id))
            deleted = session.execute(
                delete(BacktestResult).where(and_(*conditions))
            ).rowcount or 0
            session.commit()
            return int(deleted)

    def delete_results_by_analysis_ids(
        self,
        analysis_ids: List[int],
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        if not analysis_ids:
            return 0
        with self.db.get_session() as session:
            conditions = [BacktestResult.analysis_history_id.in_(analysis_ids)]
            if not include_all_owners:
                conditions.append(BacktestResult.owner_id == self.db.require_user_id(owner_id))
            deleted = session.execute(
                delete(BacktestResult).where(and_(*conditions))
            ).rowcount or 0
            session.commit()
            return int(deleted)

    def delete_summaries_by_code(
        self,
        *,
        code: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        with self.db.get_session() as session:
            conditions = [
                BacktestSummary.scope == "stock",
                BacktestSummary.code == code,
            ]
            if not include_all_owners:
                conditions.append(BacktestSummary.owner_id == self.db.require_user_id(owner_id))
            deleted = session.execute(
                delete(BacktestSummary).where(and_(*conditions))
            ).rowcount or 0
            session.commit()
            return int(deleted)

    def delete_all_summaries_for_window(
        self,
        *,
        eval_window_days: int,
        engine_version: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        with self.db.get_session() as session:
            conditions = [
                BacktestSummary.eval_window_days == eval_window_days,
                BacktestSummary.engine_version == engine_version,
            ]
            if not include_all_owners:
                conditions.append(BacktestSummary.owner_id == self.db.require_user_id(owner_id))
            deleted = session.execute(
                delete(BacktestSummary).where(and_(*conditions))
            ).rowcount or 0
            session.commit()
            return int(deleted)

    def list_backtest_codes(
        self,
        *,
        eval_window_days: int,
        engine_version: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[str]:
        with self.db.get_session() as session:
            conditions = [
                BacktestResult.eval_window_days == eval_window_days,
                BacktestResult.engine_version == engine_version,
            ]
            if not include_all_owners:
                conditions.append(BacktestResult.owner_id == self.db.require_user_id(owner_id))
            rows = session.execute(
                select(BacktestResult.code)
                .where(and_(*conditions))
                .distinct()
            ).scalars().all()
            return [str(code) for code in rows if code]

    def count_analysis_history(
        self,
        *,
        code: Optional[str] = None,
        created_before: Optional[datetime] = None,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        """Count analysis history rows matching optional filters."""
        with self.db.get_session() as session:
            conditions = []
            if not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.db.require_user_id(owner_id))
            if code:
                conditions.append(AnalysisHistory.code == code)
            if created_before is not None:
                conditions.append(AnalysisHistory.created_at <= created_before)

            query = select(func.count(AnalysisHistory.id))
            if conditions:
                query = query.where(and_(*conditions))
            return int(session.execute(query).scalar() or 0)

    def save_result(self, result: BacktestResult) -> None:
        result.owner_id = self.db.require_user_id(getattr(result, "owner_id", None))
        with self.db.get_session() as session:
            session.add(result)
            session.commit()

    def save_results_batch(self, results: List[BacktestResult], *, replace_existing: bool = False) -> int:
        if not results:
            return 0

        with self.db.get_session() as session:
            try:
                for result in results:
                    result.owner_id = self.db.require_user_id(getattr(result, "owner_id", None))
                if replace_existing:
                    analysis_ids = sorted({r.analysis_history_id for r in results if r.analysis_history_id is not None})
                    key_pairs = sorted({(r.eval_window_days, r.engine_version) for r in results})

                    if analysis_ids and key_pairs:
                        for window_days, engine_version in key_pairs:
                            session.execute(
                                delete(BacktestResult).where(
                                    and_(
                                        BacktestResult.analysis_history_id.in_(analysis_ids),
                                        BacktestResult.eval_window_days == window_days,
                                        BacktestResult.engine_version == engine_version,
                                    )
                                )
                            )

                session.add_all(results)
                session.commit()
                return len(results)
            except Exception as exc:
                session.rollback()
                logger.error(f"批量保存回测结果失败: {exc}")
                raise

    def get_results_paginated(
        self,
        *,
        code: Optional[str],
        eval_window_days: Optional[int] = None,
        run_id: Optional[int] = None,
        days: Optional[int],
        offset: int,
        limit: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Tuple[List[BacktestResult], int]:
        with self.db.get_session() as session:
            conditions = []
            if not include_all_owners:
                conditions.append(BacktestResult.owner_id == self.db.require_user_id(owner_id))
            if code:
                conditions.append(BacktestResult.code == code)
            if eval_window_days is not None:
                conditions.append(BacktestResult.eval_window_days == eval_window_days)
            if run_id is not None:
                run = session.execute(
                    select(BacktestRun).where(
                        and_(
                            BacktestRun.id == run_id,
                            BacktestRun.owner_id == self.db.require_user_id(owner_id),
                        ) if not include_all_owners else BacktestRun.id == run_id
                    ).limit(1)
                ).scalar_one_or_none()
                if run is None:
                    return [], 0
                conditions.append(BacktestResult.evaluated_at == run.completed_at)
            if days:
                cutoff = datetime.now() - timedelta(days=int(days))
                conditions.append(BacktestResult.evaluated_at >= cutoff)

            where_clause = and_(*conditions) if conditions else True

            total = session.execute(select(func.count(BacktestResult.id)).where(where_clause)).scalar() or 0
            rows = session.execute(
                select(BacktestResult)
                .where(where_clause)
                .order_by(desc(BacktestResult.evaluated_at))
                .offset(offset)
                .limit(limit)
            ).scalars().all()
            return list(rows), int(total)

    def get_sample_rows(
        self,
        *,
        code: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[AnalysisHistory]:
        with self.db.get_session() as session:
            conditions = [AnalysisHistory.query_id.like(f"bt-sample:{code}:%")]
            if not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.db.require_user_id(owner_id))
            rows = session.execute(
                select(AnalysisHistory)
                .where(and_(*conditions))
                .order_by(desc(AnalysisHistory.created_at))
            ).scalars().all()
            return list(rows)

    def delete_sample_rows(
        self,
        *,
        code: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        with self.db.get_session() as session:
            conditions = [AnalysisHistory.query_id.like(f"bt-sample:{code}:%")]
            if not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.db.require_user_id(owner_id))
            analysis_rows = session.execute(
                select(AnalysisHistory.id).where(and_(*conditions))
            ).scalars().all()
            if analysis_rows:
                session.execute(delete(BacktestResult).where(BacktestResult.analysis_history_id.in_(analysis_rows)))
                deleted = session.execute(
                    delete(AnalysisHistory).where(AnalysisHistory.id.in_(analysis_rows))
                ).rowcount or 0
            else:
                deleted = 0
            session.commit()
            return int(deleted)

    def upsert_summary(self, summary: BacktestSummary) -> None:
        """Insert or replace summary row by unique key."""
        summary.owner_id = self.db.require_user_id(getattr(summary, "owner_id", None))
        with self.db.get_session() as session:
            existing = session.execute(
                select(BacktestSummary)
                .where(
                    and_(
                        BacktestSummary.owner_id == summary.owner_id,
                        BacktestSummary.scope == summary.scope,
                        BacktestSummary.code == summary.code,
                        BacktestSummary.eval_window_days == summary.eval_window_days,
                        BacktestSummary.engine_version == summary.engine_version,
                    )
                )
                .limit(1)
            ).scalar_one_or_none()

            if existing:
                for attr in (
                    "computed_at",
                    "total_evaluations",
                    "completed_count",
                    "insufficient_count",
                    "long_count",
                    "cash_count",
                    "win_count",
                    "loss_count",
                    "neutral_count",
                    "direction_accuracy_pct",
                    "win_rate_pct",
                    "neutral_rate_pct",
                    "avg_stock_return_pct",
                    "avg_simulated_return_pct",
                    "stop_loss_trigger_rate",
                    "take_profit_trigger_rate",
                    "ambiguous_rate",
                    "avg_days_to_first_hit",
                    "advice_breakdown_json",
                    "diagnostics_json",
                ):
                    setattr(existing, attr, getattr(summary, attr))
                session.commit()
                return

            session.add(summary)
            session.commit()

    def get_summary(
        self,
        *,
        scope: str,
        code: Optional[str],
        eval_window_days: Optional[int] = None,
        engine_version: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[BacktestSummary]:
        with self.db.get_session() as session:
            conditions = [
                BacktestSummary.scope == scope,
                BacktestSummary.code == code,
                BacktestSummary.engine_version == engine_version,
            ]
            if not include_all_owners:
                conditions.append(BacktestSummary.owner_id == self.db.require_user_id(owner_id))
            if eval_window_days is not None:
                conditions.append(BacktestSummary.eval_window_days == eval_window_days)

            row = session.execute(
                select(BacktestSummary)
                .where(and_(*conditions))
                .order_by(desc(BacktestSummary.computed_at))
                .limit(1)
            ).scalar_one_or_none()
            return row

    @staticmethod
    def parse_analysis_date_from_snapshot(context_snapshot: Optional[str]) -> Optional[date]:
        if not context_snapshot:
            return None

        try:
            payload = json.loads(context_snapshot)
        except Exception:
            return None

        if not isinstance(payload, dict):
            return None

        enhanced = payload.get("enhanced_context")
        if not isinstance(enhanced, dict):
            return None

        date_str = enhanced.get("date")
        if not date_str:
            return None

        try:
            return datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
        except Exception:
            return None
