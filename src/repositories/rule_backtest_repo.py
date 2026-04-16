# -*- coding: utf-8 -*-
"""Repository helpers for AI-assisted rule backtests."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

from sqlalchemy import and_, delete, desc, func, select

from src.storage import DatabaseManager, RuleBacktestRun, RuleBacktestTrade


class RuleBacktestRepository:
    """Database access for rule backtest runs and trades."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def save_run(self, run: RuleBacktestRun) -> RuleBacktestRun:
        run.owner_id = self.db.require_user_id(getattr(run, "owner_id", None))
        with self.db.get_session() as session:
            session.add(run)
            session.commit()
            session.refresh(run)
        if getattr(run, "id", None) is not None:
            self.db.sync_phase_e_rule_backtest_shadow(int(run.id))
        return run

    def update_run(
        self,
        run_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
        **fields: Any,
    ) -> Optional[RuleBacktestRun]:
        with self.db.get_session() as session:
            conditions = [RuleBacktestRun.id == run_id]
            if not include_all_owners:
                conditions.append(RuleBacktestRun.owner_id == self.db.require_user_id(owner_id))
            row = session.execute(
                select(RuleBacktestRun).where(and_(*conditions)).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            for key, value in fields.items():
                setattr(row, key, value)
            session.commit()
            session.refresh(row)
        self.db.sync_phase_e_rule_backtest_shadow(int(run_id))
        return row

    def save_trades(self, trades: List[RuleBacktestTrade]) -> int:
        if not trades:
            return 0
        run_ids = sorted({int(trade.run_id) for trade in trades if getattr(trade, "run_id", None) is not None})
        with self.db.get_session() as session:
            session.add_all(trades)
            session.commit()
        for run_id in run_ids:
            self.db.sync_phase_e_rule_backtest_shadow(int(run_id))
        return len(trades)

    def get_run(
        self,
        run_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[RuleBacktestRun]:
        with self.db.get_session() as session:
            conditions = [RuleBacktestRun.id == run_id]
            if not include_all_owners:
                conditions.append(RuleBacktestRun.owner_id == self.db.require_user_id(owner_id))
            return session.execute(
                select(RuleBacktestRun).where(and_(*conditions)).limit(1)
            ).scalar_one_or_none()

    def get_runs_paginated(
        self,
        *,
        code: Optional[str] = None,
        offset: int,
        limit: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Tuple[List[RuleBacktestRun], int]:
        with self.db.get_session() as session:
            conditions = []
            if not include_all_owners:
                conditions.append(RuleBacktestRun.owner_id == self.db.require_user_id(owner_id))
            if code:
                conditions.append(RuleBacktestRun.code == code)
            where_clause = and_(*conditions) if conditions else True

            total = session.execute(
                select(func.count(RuleBacktestRun.id)).where(where_clause)
            ).scalar() or 0
            rows = session.execute(
                select(RuleBacktestRun)
                .where(where_clause)
                .order_by(desc(RuleBacktestRun.run_at))
                .offset(offset)
                .limit(limit)
            ).scalars().all()
            return list(rows), int(total)

    def get_trades_by_run(self, run_id: int) -> List[RuleBacktestTrade]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(RuleBacktestTrade)
                .where(RuleBacktestTrade.run_id == run_id)
                .order_by(RuleBacktestTrade.trade_index.asc())
            ).scalars().all()
            return list(rows)

    def delete_runs_by_code(
        self,
        *,
        code: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        resolved_owner_id = None if include_all_owners else self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            conditions = [RuleBacktestRun.code == code]
            if not include_all_owners:
                conditions.append(RuleBacktestRun.owner_id == resolved_owner_id)
            deleted = session.execute(
                delete(RuleBacktestRun).where(and_(*conditions))
            ).rowcount or 0
            session.commit()
        self.db.delete_phase_e_rule_backtest_shadow_by_code(
            code=code,
            owner_id=resolved_owner_id,
            include_all_owners=include_all_owners,
        )
        return int(deleted)

    def delete_trades_by_run_ids(self, run_ids: List[int]) -> int:
        if not run_ids:
            return 0
        with self.db.get_session() as session:
            deleted = session.execute(
                delete(RuleBacktestTrade).where(RuleBacktestTrade.run_id.in_(run_ids))
            ).rowcount or 0
            session.commit()
        for run_id in sorted({int(value) for value in run_ids}):
            self.db.sync_phase_e_rule_backtest_shadow(int(run_id))
        return int(deleted)
