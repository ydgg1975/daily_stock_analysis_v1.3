# -*- coding: utf-8 -*-
"""Repository helpers for portfolio runtime objects."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from sqlalchemy import and_, desc, select

from src.storage import DailyPnlSnapshot, DatabaseManager, TradeExecutionEvent


class PortfolioRepository:
    """Persistence layer for portfolio executions and daily pnl snapshots."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def add_execution_event(self, payload: Dict) -> Dict:
        quantity = float(payload.get("quantity") or 0.0)
        price = float(payload.get("price") or 0.0)
        amount = float(payload.get("amount") or 0.0)
        if amount <= 0 and payload.get("side") in {"buy", "sell"} and quantity > 0 and price > 0:
            amount = quantity * price

        with self.db.get_session() as session:
            record = TradeExecutionEvent(
                portfolio_id=payload.get("portfolio_id") or "default",
                executed_at=payload["executed_at"],
                trade_date=payload.get("trade_date") or payload["executed_at"].date(),
                side=payload["side"],
                code=payload.get("code"),
                quantity=quantity,
                price=price,
                amount=amount,
                fees=float(payload.get("fees") or 0.0),
                note=payload.get("note"),
                plan_id=payload.get("plan_id"),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.to_dict()

    def list_execution_events(
        self,
        *,
        portfolio_id: str = "default",
        limit: Optional[int] = None,
        as_of_date: Optional[date] = None,
    ) -> List[Dict]:
        with self.db.get_session() as session:
            stmt = (
                select(TradeExecutionEvent)
                .where(TradeExecutionEvent.portfolio_id == portfolio_id)
                .order_by(TradeExecutionEvent.executed_at, TradeExecutionEvent.id)
            )
            if as_of_date is not None:
                stmt = stmt.where(TradeExecutionEvent.trade_date <= as_of_date)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [row.to_dict() for row in rows]

    def upsert_daily_pnl_snapshot(self, payload: Dict) -> Dict:
        with self.db.get_session() as session:
            record = session.execute(
                select(DailyPnlSnapshot).where(
                    and_(
                        DailyPnlSnapshot.portfolio_id == (payload.get("portfolio_id") or "default"),
                        DailyPnlSnapshot.trade_date == payload["trade_date"],
                    )
                )
            ).scalar_one_or_none()

            if record is None:
                record = DailyPnlSnapshot(
                    portfolio_id=payload.get("portfolio_id") or "default",
                    trade_date=payload["trade_date"],
                )
                session.add(record)

            record.cash = float(payload.get("cash") or 0.0)
            record.market_value = float(payload.get("market_value") or 0.0)
            record.total_equity = float(payload.get("total_equity") or 0.0)
            record.realized_pnl = float(payload.get("realized_pnl") or 0.0)
            record.unrealized_pnl = float(payload.get("unrealized_pnl") or 0.0)
            record.total_pnl = float(payload.get("total_pnl") or 0.0)
            record.position_ratio = float(payload.get("position_ratio") or 0.0)
            record.win_trade_count = int(payload.get("win_trade_count") or 0)
            record.loss_trade_count = int(payload.get("loss_trade_count") or 0)
            record.note = payload.get("note")

            session.commit()
            session.refresh(record)
            return record.to_dict()

    def list_daily_pnl_snapshots(
        self,
        *,
        portfolio_id: str = "default",
        limit: Optional[int] = None,
        as_of_date: Optional[date] = None,
    ) -> List[Dict]:
        with self.db.get_session() as session:
            stmt = (
                select(DailyPnlSnapshot)
                .where(DailyPnlSnapshot.portfolio_id == portfolio_id)
                .order_by(desc(DailyPnlSnapshot.trade_date))
            )
            if as_of_date is not None:
                stmt = stmt.where(DailyPnlSnapshot.trade_date <= as_of_date)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [row.to_dict() for row in rows]
