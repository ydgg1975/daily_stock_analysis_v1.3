# -*- coding: utf-8 -*-
"""Portfolio repository.

Provides DB access helpers for portfolio account/events/snapshot tables.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_, delete, desc, func, select
from sqlalchemy.exc import IntegrityError, OperationalError

from src.storage import (
    DatabaseManager,
    PortfolioAccount,
    PortfolioBrokerConnection,
    PortfolioBrokerSyncCashBalance,
    PortfolioBrokerSyncPosition,
    PortfolioBrokerSyncState,
    PortfolioCashLedger,
    PortfolioCorporateAction,
    PortfolioDailySnapshot,
    PortfolioFxRate,
    PortfolioPosition,
    PortfolioPositionLot,
    PortfolioTrade,
    StockDaily,
)

logger = logging.getLogger(__name__)


class DuplicateTradeUidError(Exception):
    """Raised when trade_uid conflicts with existing record in one account."""


class DuplicateTradeDedupHashError(Exception):
    """Raised when dedup hash conflicts with existing record in one account."""


class PortfolioBusyError(Exception):
    """Raised when SQLite write serialization cannot acquire the ledger lock."""


class DuplicateBrokerConnectionRefError(Exception):
    """Raised when broker account reference conflicts within one owner/broker scope."""


class PortfolioRepository:
    """DB access layer for portfolio P0 domain."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    @staticmethod
    def _mark_phase_f_account_sync_in_session(*, session: Any, account_id: Optional[int]) -> None:
        if account_id is None:
            return
        session.info.setdefault("phase_f_sync_account_ids", set()).add(int(account_id))

    def _account_conditions(
        self,
        *,
        account_id: Optional[int] = None,
        include_inactive: bool = False,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[Any]:
        conditions = []
        if account_id is not None:
            conditions.append(PortfolioAccount.id == account_id)
        if not include_inactive:
            conditions.append(PortfolioAccount.is_active.is_(True))
        if not include_all_owners:
            conditions.append(PortfolioAccount.owner_id == self.db.require_user_id(owner_id))
        return conditions

    def _broker_connection_conditions(
        self,
        *,
        connection_id: Optional[int] = None,
        portfolio_account_id: Optional[int] = None,
        broker_type: Optional[str] = None,
        status: Optional[str] = None,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[Any]:
        conditions = []
        if connection_id is not None:
            conditions.append(PortfolioBrokerConnection.id == connection_id)
        if portfolio_account_id is not None:
            conditions.append(PortfolioBrokerConnection.portfolio_account_id == portfolio_account_id)
        if broker_type is not None:
            conditions.append(PortfolioBrokerConnection.broker_type == broker_type)
        if status is not None:
            conditions.append(PortfolioBrokerConnection.status == status)
        if not include_all_owners:
            conditions.append(PortfolioBrokerConnection.owner_id == self.db.require_user_id(owner_id))
        return conditions

    # ------------------------------------------------------------------
    # Account CRUD
    # ------------------------------------------------------------------
    def create_account(
        self,
        *,
        name: str,
        broker: Optional[str],
        market: str,
        base_currency: str,
        owner_id: Optional[str] = None,
    ) -> PortfolioAccount:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            row = PortfolioAccount(
                owner_id=resolved_owner_id,
                name=name,
                broker=broker,
                market=market,
                base_currency=base_currency,
                is_active=True,
            )
            session.add(row)
            session.flush()
            self.db.sync_phase_f_portfolio_account_shadow_from_session(
                session=session,
                account_id=int(row.id),
            )
            session.commit()
            session.refresh(row)
            return row

    def get_account(
        self,
        account_id: int,
        include_inactive: bool = False,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[PortfolioAccount]:
        with self.db.get_session() as session:
            return self.get_account_in_session(
                session=session,
                account_id=account_id,
                include_inactive=include_inactive,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            )

    def list_accounts(
        self,
        include_inactive: bool = False,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[PortfolioAccount]:
        with self.db.get_session() as session:
            conditions = self._account_conditions(
                include_inactive=include_inactive,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            )
            query = select(PortfolioAccount)
            if conditions:
                query = query.where(and_(*conditions))
            rows = session.execute(query.order_by(PortfolioAccount.id.asc())).scalars().all()
            return list(rows)

    def get_account_in_session(
        self,
        *,
        session: Any,
        account_id: int,
        include_inactive: bool = False,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[PortfolioAccount]:
        conditions = self._account_conditions(
            account_id=account_id,
            include_inactive=include_inactive,
            owner_id=owner_id,
            include_all_owners=include_all_owners,
        )
        return session.execute(
            select(PortfolioAccount).where(and_(*conditions)).limit(1)
        ).scalar_one_or_none()

    def update_account(
        self,
        account_id: int,
        fields: Dict[str, Any],
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[PortfolioAccount]:
        with self.db.get_session() as session:
            row = self.get_account_in_session(
                session=session,
                account_id=account_id,
                include_inactive=True,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            )
            if row is None:
                return None
            if "owner_id" in fields:
                fields["owner_id"] = self.db.require_user_id(fields.get("owner_id"))
            for key, value in fields.items():
                setattr(row, key, value)
            row.updated_at = datetime.now()
            self.db.sync_phase_f_portfolio_account_shadow_from_session(
                session=session,
                account_id=int(row.id),
            )
            session.commit()
            session.refresh(row)
            return row

    def deactivate_account(
        self,
        account_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> bool:
        with self.db.get_session() as session:
            row = self.get_account_in_session(
                session=session,
                account_id=account_id,
                include_inactive=True,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            )
            if row is None:
                return False
            row.is_active = False
            row.updated_at = datetime.now()
            self.db.sync_phase_f_portfolio_account_shadow_from_session(
                session=session,
                account_id=int(row.id),
            )
            session.commit()
            return True

    # ------------------------------------------------------------------
    # Broker connection CRUD
    # ------------------------------------------------------------------
    def create_broker_connection(
        self,
        *,
        portfolio_account_id: int,
        broker_type: str,
        broker_name: Optional[str],
        connection_name: str,
        broker_account_ref: Optional[str],
        import_mode: str,
        status: str,
        sync_metadata_json: Optional[str],
        owner_id: Optional[str] = None,
    ) -> PortfolioBrokerConnection:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            row = PortfolioBrokerConnection(
                owner_id=resolved_owner_id,
                portfolio_account_id=portfolio_account_id,
                broker_type=broker_type,
                broker_name=broker_name,
                connection_name=connection_name,
                broker_account_ref=broker_account_ref,
                import_mode=import_mode,
                status=status,
                sync_metadata_json=sync_metadata_json,
            )
            session.add(row)
            try:
                session.flush()
                self.db.sync_phase_f_portfolio_account_shadow_from_session(
                    session=session,
                    account_id=int(portfolio_account_id),
                )
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise DuplicateBrokerConnectionRefError(
                    "Duplicate broker_account_ref for this broker connection owner scope"
                ) from exc
            session.refresh(row)
            return row

    def get_broker_connection(
        self,
        connection_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[PortfolioBrokerConnection]:
        with self.db.get_session() as session:
            return self.get_broker_connection_in_session(
                session=session,
                connection_id=connection_id,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            )

    def get_broker_connection_by_ref(
        self,
        *,
        broker_type: str,
        broker_account_ref: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[PortfolioBrokerConnection]:
        with self.db.get_session() as session:
            conditions = self._broker_connection_conditions(
                broker_type=broker_type,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            )
            conditions.append(PortfolioBrokerConnection.broker_account_ref == broker_account_ref)
            return session.execute(
                select(PortfolioBrokerConnection).where(and_(*conditions)).limit(1)
            ).scalar_one_or_none()

    def list_broker_connections(
        self,
        *,
        portfolio_account_id: Optional[int] = None,
        broker_type: Optional[str] = None,
        status: Optional[str] = None,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[PortfolioBrokerConnection]:
        with self.db.get_session() as session:
            conditions = self._broker_connection_conditions(
                portfolio_account_id=portfolio_account_id,
                broker_type=broker_type,
                status=status,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            )
            query = select(PortfolioBrokerConnection)
            if conditions:
                query = query.where(and_(*conditions))
            rows = session.execute(
                query.order_by(PortfolioBrokerConnection.id.asc())
            ).scalars().all()
            return list(rows)

    def replace_broker_sync_state(
        self,
        *,
        broker_connection_id: int,
        portfolio_account_id: int,
        broker_type: str,
        broker_account_ref: Optional[str],
        sync_source: str,
        sync_status: str,
        snapshot_date: date,
        synced_at: datetime,
        base_currency: str,
        total_cash: float,
        total_market_value: float,
        total_equity: float,
        realized_pnl: float,
        unrealized_pnl: float,
        fx_stale: bool,
        payload_json: Optional[str],
        positions: Iterable[Dict[str, Any]],
        cash_balances: Iterable[Dict[str, Any]],
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> PortfolioBrokerSyncState:
        resolved_owner_id = self.db.require_user_id(owner_id)
        with self.db.get_session() as session:
            connection = self.get_broker_connection_in_session(
                session=session,
                connection_id=broker_connection_id,
                owner_id=resolved_owner_id,
                include_all_owners=include_all_owners,
            )
            if connection is None:
                raise ValueError(f"Broker connection not found: {broker_connection_id}")
            account = self.get_account_in_session(
                session=session,
                account_id=portfolio_account_id,
                include_inactive=False,
                owner_id=resolved_owner_id,
                include_all_owners=include_all_owners,
            )
            if account is None:
                raise ValueError(f"Active account not found: {portfolio_account_id}")

            row = session.execute(
                select(PortfolioBrokerSyncState)
                .where(PortfolioBrokerSyncState.broker_connection_id == broker_connection_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = PortfolioBrokerSyncState(
                    owner_id=resolved_owner_id,
                    broker_connection_id=broker_connection_id,
                    portfolio_account_id=portfolio_account_id,
                )
                session.add(row)

            row.owner_id = resolved_owner_id
            row.broker_connection_id = broker_connection_id
            row.portfolio_account_id = portfolio_account_id
            row.broker_type = broker_type
            row.broker_account_ref = broker_account_ref
            row.sync_source = sync_source
            row.sync_status = sync_status
            row.snapshot_date = snapshot_date
            row.synced_at = synced_at
            row.base_currency = base_currency
            row.total_cash = total_cash
            row.total_market_value = total_market_value
            row.total_equity = total_equity
            row.realized_pnl = realized_pnl
            row.unrealized_pnl = unrealized_pnl
            row.fx_stale = bool(fx_stale)
            row.payload_json = payload_json
            row.updated_at = datetime.now()

            session.execute(
                delete(PortfolioBrokerSyncPosition).where(
                    PortfolioBrokerSyncPosition.broker_connection_id == broker_connection_id
                )
            )
            session.execute(
                delete(PortfolioBrokerSyncCashBalance).where(
                    PortfolioBrokerSyncCashBalance.broker_connection_id == broker_connection_id
                )
            )

            for item in positions:
                session.add(
                    PortfolioBrokerSyncPosition(
                        owner_id=resolved_owner_id,
                        broker_connection_id=broker_connection_id,
                        portfolio_account_id=portfolio_account_id,
                        broker_position_ref=item.get("broker_position_ref"),
                        symbol=item["symbol"],
                        market=item["market"],
                        currency=item["currency"],
                        quantity=float(item["quantity"]),
                        avg_cost=float(item["avg_cost"]),
                        last_price=float(item["last_price"]),
                        market_value_base=float(item["market_value_base"]),
                        unrealized_pnl_base=float(item["unrealized_pnl_base"]),
                        valuation_currency=item["valuation_currency"],
                        payload_json=item.get("payload_json"),
                    )
                )

            for item in cash_balances:
                session.add(
                    PortfolioBrokerSyncCashBalance(
                        owner_id=resolved_owner_id,
                        broker_connection_id=broker_connection_id,
                        portfolio_account_id=portfolio_account_id,
                        currency=item["currency"],
                        amount=float(item["amount"]),
                        amount_base=float(item["amount_base"]),
                    )
                )

            self.db.sync_phase_f_portfolio_account_shadow_from_session(
                session=session,
                account_id=int(portfolio_account_id),
            )
            session.commit()
            session.refresh(row)
            return row

    def get_latest_broker_sync_state_for_account(
        self,
        *,
        portfolio_account_id: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[PortfolioBrokerSyncState]:
        with self.db.get_session() as session:
            query = select(PortfolioBrokerSyncState).where(
                PortfolioBrokerSyncState.portfolio_account_id == portfolio_account_id
            )
            if not include_all_owners:
                query = query.where(
                    PortfolioBrokerSyncState.owner_id == self.db.require_user_id(owner_id)
                )
            return session.execute(
                query.order_by(
                    PortfolioBrokerSyncState.synced_at.desc(),
                    PortfolioBrokerSyncState.id.desc(),
                ).limit(1)
            ).scalar_one_or_none()

    def list_broker_sync_positions(
        self,
        *,
        broker_connection_id: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[PortfolioBrokerSyncPosition]:
        with self.db.get_session() as session:
            query = select(PortfolioBrokerSyncPosition).where(
                PortfolioBrokerSyncPosition.broker_connection_id == broker_connection_id
            )
            if not include_all_owners:
                query = query.where(
                    PortfolioBrokerSyncPosition.owner_id == self.db.require_user_id(owner_id)
                )
            rows = session.execute(
                query.order_by(
                    PortfolioBrokerSyncPosition.symbol.asc(),
                    PortfolioBrokerSyncPosition.market.asc(),
                    PortfolioBrokerSyncPosition.currency.asc(),
                )
            ).scalars().all()
            return list(rows)

    def list_broker_sync_cash_balances(
        self,
        *,
        broker_connection_id: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[PortfolioBrokerSyncCashBalance]:
        with self.db.get_session() as session:
            query = select(PortfolioBrokerSyncCashBalance).where(
                PortfolioBrokerSyncCashBalance.broker_connection_id == broker_connection_id
            )
            if not include_all_owners:
                query = query.where(
                    PortfolioBrokerSyncCashBalance.owner_id == self.db.require_user_id(owner_id)
                )
            rows = session.execute(
                query.order_by(PortfolioBrokerSyncCashBalance.currency.asc())
            ).scalars().all()
            return list(rows)

    def get_broker_connection_in_session(
        self,
        *,
        session: Any,
        connection_id: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[PortfolioBrokerConnection]:
        conditions = self._broker_connection_conditions(
            connection_id=connection_id,
            owner_id=owner_id,
            include_all_owners=include_all_owners,
        )
        return session.execute(
            select(PortfolioBrokerConnection).where(and_(*conditions)).limit(1)
        ).scalar_one_or_none()

    def update_broker_connection(
        self,
        connection_id: int,
        fields: Dict[str, Any],
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[PortfolioBrokerConnection]:
        with self.db.get_session() as session:
            row = self.get_broker_connection_in_session(
                session=session,
                connection_id=connection_id,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            )
            if row is None:
                return None
            original_account_id = int(row.portfolio_account_id)
            if "owner_id" in fields:
                fields["owner_id"] = self.db.require_user_id(fields.get("owner_id"))
            for key, value in fields.items():
                setattr(row, key, value)
            row.updated_at = datetime.now()
            try:
                session.flush()
                for account_id in sorted({original_account_id, int(row.portfolio_account_id)}):
                    self.db.sync_phase_f_portfolio_account_shadow_from_session(
                        session=session,
                        account_id=account_id,
                    )
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise DuplicateBrokerConnectionRefError(
                    "Duplicate broker_account_ref for this broker connection owner scope"
                ) from exc
            session.refresh(row)
            return row

    # ------------------------------------------------------------------
    # Event writes
    # ------------------------------------------------------------------
    @contextmanager
    def portfolio_write_session(self):
        session = self.db.get_session()
        try:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        except OperationalError as exc:
            session.close()
            if self._is_sqlite_locked_error(exc):
                raise PortfolioBusyError("Portfolio ledger is busy; please retry shortly.") from exc
            raise

        try:
            yield session
            for account_id in sorted(session.info.get("phase_f_sync_account_ids", set())):
                self.db.sync_phase_f_portfolio_account_shadow_from_session(
                    session=session,
                    account_id=account_id,
                )
            session.commit()
        except OperationalError as exc:
            session.rollback()
            if self._is_sqlite_locked_error(exc):
                raise PortfolioBusyError("Portfolio ledger is busy; please retry shortly.") from exc
            raise
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def add_trade(
        self,
        *,
        account_id: int,
        trade_uid: Optional[str],
        symbol: str,
        market: str,
        currency: str,
        trade_date: date,
        side: str,
        quantity: float,
        price: float,
        fee: float,
        tax: float,
        note: Optional[str] = None,
        dedup_hash: Optional[str] = None,
    ) -> PortfolioTrade:
        with self.portfolio_write_session() as session:
            row = self.add_trade_in_session(
                session=session,
                account_id=account_id,
                trade_uid=trade_uid,
                symbol=symbol,
                market=market,
                currency=currency,
                trade_date=trade_date,
                side=side,
                quantity=quantity,
                price=price,
                fee=fee,
                tax=tax,
                note=note,
                dedup_hash=dedup_hash,
            )
            session.expunge(row)
            return row

    def add_cash_ledger(
        self,
        *,
        account_id: int,
        event_date: date,
        direction: str,
        amount: float,
        currency: str,
        note: Optional[str] = None,
    ) -> PortfolioCashLedger:
        with self.portfolio_write_session() as session:
            row = self.add_cash_ledger_in_session(
                session=session,
                account_id=account_id,
                event_date=event_date,
                direction=direction,
                amount=amount,
                currency=currency,
                note=note,
            )
            session.expunge(row)
            return row

    def add_corporate_action(
        self,
        *,
        account_id: int,
        symbol: str,
        market: str,
        currency: str,
        effective_date: date,
        action_type: str,
        cash_dividend_per_share: Optional[float] = None,
        split_ratio: Optional[float] = None,
        note: Optional[str] = None,
    ) -> PortfolioCorporateAction:
        with self.portfolio_write_session() as session:
            row = self.add_corporate_action_in_session(
                session=session,
                account_id=account_id,
                symbol=symbol,
                market=market,
                currency=currency,
                effective_date=effective_date,
                action_type=action_type,
                cash_dividend_per_share=cash_dividend_per_share,
                split_ratio=split_ratio,
                note=note,
            )
            session.expunge(row)
            return row

    def delete_trade(
        self,
        trade_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> bool:
        with self.portfolio_write_session() as session:
            return self.delete_trade_in_session(
                session=session,
                trade_id=trade_id,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            )

    def delete_cash_ledger(
        self,
        entry_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> bool:
        with self.portfolio_write_session() as session:
            return self.delete_cash_ledger_in_session(
                session=session,
                entry_id=entry_id,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            )

    def delete_corporate_action(
        self,
        action_id: int,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> bool:
        with self.portfolio_write_session() as session:
            return self.delete_corporate_action_in_session(
                session=session,
                action_id=action_id,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            )

    def has_trade_uid(self, account_id: int, trade_uid: Optional[str]) -> bool:
        """Return True when trade_uid already exists in the account."""
        uid = (trade_uid or "").strip()
        if not uid:
            return False
        with self.db.get_session() as session:
            return self.has_trade_uid_in_session(session=session, account_id=account_id, trade_uid=uid)

    def has_trade_dedup_hash(self, account_id: int, dedup_hash: Optional[str]) -> bool:
        """Return True when dedup hash already exists in the account."""
        hash_value = (dedup_hash or "").strip()
        if not hash_value:
            return False
        with self.db.get_session() as session:
            return self.has_trade_dedup_hash_in_session(
                session=session,
                account_id=account_id,
                dedup_hash=hash_value,
            )

    def has_trade_uid_in_session(self, *, session: Any, account_id: int, trade_uid: str) -> bool:
        row = session.execute(
            select(PortfolioTrade.id).where(
                and_(
                    PortfolioTrade.account_id == account_id,
                    PortfolioTrade.trade_uid == trade_uid,
                )
            ).limit(1)
        ).scalar_one_or_none()
        return row is not None

    def has_trade_dedup_hash_in_session(self, *, session: Any, account_id: int, dedup_hash: str) -> bool:
        row = session.execute(
            select(PortfolioTrade.id).where(
                and_(
                    PortfolioTrade.account_id == account_id,
                    PortfolioTrade.dedup_hash == dedup_hash,
                )
            ).limit(1)
        ).scalar_one_or_none()
        return row is not None

    def add_trade_in_session(
        self,
        *,
        session: Any,
        account_id: int,
        trade_uid: Optional[str],
        symbol: str,
        market: str,
        currency: str,
        trade_date: date,
        side: str,
        quantity: float,
        price: float,
        fee: float,
        tax: float,
        note: Optional[str] = None,
        dedup_hash: Optional[str] = None,
    ) -> PortfolioTrade:
        row = PortfolioTrade(
            account_id=account_id,
            trade_uid=trade_uid,
            symbol=symbol,
            market=market,
            currency=currency,
            trade_date=trade_date,
            side=side,
            quantity=quantity,
            price=price,
            fee=fee,
            tax=tax,
            note=note,
            dedup_hash=dedup_hash,
        )
        session.add(row)
        self._mark_phase_f_account_sync_in_session(session=session, account_id=account_id)
        self._invalidate_account_cache_in_session(
            session=session,
            account_id=account_id,
            from_date=trade_date,
        )
        try:
            session.flush()
        except IntegrityError as exc:
            raise self._translate_trade_integrity_error(
                exc=exc,
                account_id=account_id,
                trade_uid=trade_uid,
                dedup_hash=dedup_hash,
            ) from exc
        session.refresh(row)
        return row

    def add_cash_ledger_in_session(
        self,
        *,
        session: Any,
        account_id: int,
        event_date: date,
        direction: str,
        amount: float,
        currency: str,
        note: Optional[str] = None,
    ) -> PortfolioCashLedger:
        row = PortfolioCashLedger(
            account_id=account_id,
            event_date=event_date,
            direction=direction,
            amount=amount,
            currency=currency,
            note=note,
        )
        session.add(row)
        self._mark_phase_f_account_sync_in_session(session=session, account_id=account_id)
        self._invalidate_account_cache_in_session(
            session=session,
            account_id=account_id,
            from_date=event_date,
        )
        session.flush()
        session.refresh(row)
        return row

    def add_corporate_action_in_session(
        self,
        *,
        session: Any,
        account_id: int,
        symbol: str,
        market: str,
        currency: str,
        effective_date: date,
        action_type: str,
        cash_dividend_per_share: Optional[float] = None,
        split_ratio: Optional[float] = None,
        note: Optional[str] = None,
    ) -> PortfolioCorporateAction:
        row = PortfolioCorporateAction(
            account_id=account_id,
            symbol=symbol,
            market=market,
            currency=currency,
            effective_date=effective_date,
            action_type=action_type,
            cash_dividend_per_share=cash_dividend_per_share,
            split_ratio=split_ratio,
            note=note,
        )
        session.add(row)
        self._mark_phase_f_account_sync_in_session(session=session, account_id=account_id)
        self._invalidate_account_cache_in_session(
            session=session,
            account_id=account_id,
            from_date=effective_date,
        )
        session.flush()
        session.refresh(row)
        return row

    def delete_trade_in_session(
        self,
        *,
        session: Any,
        trade_id: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> bool:
        query = (
            select(PortfolioTrade)
            .join(PortfolioAccount, PortfolioAccount.id == PortfolioTrade.account_id)
            .where(PortfolioTrade.id == trade_id)
        )
        if not include_all_owners:
            query = query.where(PortfolioAccount.owner_id == self.db.require_user_id(owner_id))
        row = session.execute(query.limit(1)).scalar_one_or_none()
        if row is None:
            return False
        self._invalidate_account_cache_in_session(
            session=session,
            account_id=int(row.account_id),
            from_date=row.trade_date,
        )
        self._mark_phase_f_account_sync_in_session(session=session, account_id=int(row.account_id))
        session.delete(row)
        session.flush()
        return True

    def delete_cash_ledger_in_session(
        self,
        *,
        session: Any,
        entry_id: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> bool:
        query = (
            select(PortfolioCashLedger)
            .join(PortfolioAccount, PortfolioAccount.id == PortfolioCashLedger.account_id)
            .where(PortfolioCashLedger.id == entry_id)
        )
        if not include_all_owners:
            query = query.where(PortfolioAccount.owner_id == self.db.require_user_id(owner_id))
        row = session.execute(query.limit(1)).scalar_one_or_none()
        if row is None:
            return False
        self._invalidate_account_cache_in_session(
            session=session,
            account_id=int(row.account_id),
            from_date=row.event_date,
        )
        self._mark_phase_f_account_sync_in_session(session=session, account_id=int(row.account_id))
        session.delete(row)
        session.flush()
        return True

    def delete_corporate_action_in_session(
        self,
        *,
        session: Any,
        action_id: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> bool:
        query = (
            select(PortfolioCorporateAction)
            .join(PortfolioAccount, PortfolioAccount.id == PortfolioCorporateAction.account_id)
            .where(PortfolioCorporateAction.id == action_id)
        )
        if not include_all_owners:
            query = query.where(PortfolioAccount.owner_id == self.db.require_user_id(owner_id))
        row = session.execute(query.limit(1)).scalar_one_or_none()
        if row is None:
            return False
        self._invalidate_account_cache_in_session(
            session=session,
            account_id=int(row.account_id),
            from_date=row.effective_date,
        )
        self._mark_phase_f_account_sync_in_session(session=session, account_id=int(row.account_id))
        session.delete(row)
        session.flush()
        return True

    # ------------------------------------------------------------------
    # Event reads
    # ------------------------------------------------------------------
    def list_trades(self, account_id: int, as_of: date) -> List[PortfolioTrade]:
        with self.db.get_session() as session:
            return self.list_trades_in_session(session=session, account_id=account_id, as_of=as_of)

    def list_trades_in_session(
        self,
        *,
        session: Any,
        account_id: int,
        as_of: date,
    ) -> List[PortfolioTrade]:
        rows = session.execute(
            select(PortfolioTrade)
            .where(
                and_(
                    PortfolioTrade.account_id == account_id,
                    PortfolioTrade.trade_date <= as_of,
                )
            )
            .order_by(PortfolioTrade.trade_date.asc(), PortfolioTrade.id.asc())
        ).scalars().all()
        return list(rows)

    def list_cash_ledger(self, account_id: int, as_of: date) -> List[PortfolioCashLedger]:
        with self.db.get_session() as session:
            return self.list_cash_ledger_in_session(session=session, account_id=account_id, as_of=as_of)

    def list_cash_ledger_in_session(
        self,
        *,
        session: Any,
        account_id: int,
        as_of: date,
    ) -> List[PortfolioCashLedger]:
        rows = session.execute(
            select(PortfolioCashLedger)
            .where(
                and_(
                    PortfolioCashLedger.account_id == account_id,
                    PortfolioCashLedger.event_date <= as_of,
                )
            )
            .order_by(PortfolioCashLedger.event_date.asc(), PortfolioCashLedger.id.asc())
        ).scalars().all()
        return list(rows)

    def list_corporate_actions(self, account_id: int, as_of: date) -> List[PortfolioCorporateAction]:
        with self.db.get_session() as session:
            return self.list_corporate_actions_in_session(session=session, account_id=account_id, as_of=as_of)

    def list_corporate_actions_in_session(
        self,
        *,
        session: Any,
        account_id: int,
        as_of: date,
    ) -> List[PortfolioCorporateAction]:
        rows = session.execute(
            select(PortfolioCorporateAction)
            .where(
                and_(
                    PortfolioCorporateAction.account_id == account_id,
                    PortfolioCorporateAction.effective_date <= as_of,
                )
            )
            .order_by(PortfolioCorporateAction.effective_date.asc(), PortfolioCorporateAction.id.asc())
        ).scalars().all()
        return list(rows)

    def get_first_activity_date(self, *, account_id: int, as_of: date) -> Optional[date]:
        """Return earliest event date (trade/cash/corporate action) for one account."""
        with self.db.get_session() as session:
            first_trade = session.execute(
                select(func.min(PortfolioTrade.trade_date)).where(
                    and_(
                        PortfolioTrade.account_id == account_id,
                        PortfolioTrade.trade_date <= as_of,
                    )
                )
            ).scalar_one()
            first_cash = session.execute(
                select(func.min(PortfolioCashLedger.event_date)).where(
                    and_(
                        PortfolioCashLedger.account_id == account_id,
                        PortfolioCashLedger.event_date <= as_of,
                    )
                )
            ).scalar_one()
            first_action = session.execute(
                select(func.min(PortfolioCorporateAction.effective_date)).where(
                    and_(
                        PortfolioCorporateAction.account_id == account_id,
                        PortfolioCorporateAction.effective_date <= as_of,
                    )
                )
            ).scalar_one()

            candidates = [item for item in (first_trade, first_cash, first_action) if item is not None]
            if not candidates:
                return None
            return min(candidates)

    def query_trades(
        self,
        *,
        account_id: Optional[int],
        date_from: Optional[date],
        date_to: Optional[date],
        symbol: Optional[str],
        side: Optional[str],
        page: int,
        page_size: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Tuple[List[PortfolioTrade], int]:
        with self.db.get_session() as session:
            conditions = []
            if account_id is not None:
                conditions.append(PortfolioTrade.account_id == account_id)
            if date_from is not None:
                conditions.append(PortfolioTrade.trade_date >= date_from)
            if date_to is not None:
                conditions.append(PortfolioTrade.trade_date <= date_to)
            if symbol:
                conditions.append(PortfolioTrade.symbol == symbol)
            if side:
                conditions.append(PortfolioTrade.side == side)

            data_query = select(PortfolioTrade)
            count_query = select(func.count()).select_from(PortfolioTrade)
            if not include_all_owners:
                owner_filter = PortfolioAccount.owner_id == self.db.require_user_id(owner_id)
                data_query = data_query.join(PortfolioAccount, PortfolioAccount.id == PortfolioTrade.account_id)
                count_query = count_query.join(PortfolioAccount, PortfolioAccount.id == PortfolioTrade.account_id)
                conditions.append(owner_filter)
            if conditions:
                where_clause = and_(*conditions)
                data_query = data_query.where(where_clause)
                count_query = count_query.where(where_clause)

            total = int(session.execute(count_query).scalar_one() or 0)
            rows = session.execute(
                data_query
                .order_by(PortfolioTrade.trade_date.desc(), PortfolioTrade.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
            return list(rows), total

    def query_cash_ledger(
        self,
        *,
        account_id: Optional[int],
        date_from: Optional[date],
        date_to: Optional[date],
        direction: Optional[str],
        page: int,
        page_size: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Tuple[List[PortfolioCashLedger], int]:
        with self.db.get_session() as session:
            conditions = []
            if account_id is not None:
                conditions.append(PortfolioCashLedger.account_id == account_id)
            if date_from is not None:
                conditions.append(PortfolioCashLedger.event_date >= date_from)
            if date_to is not None:
                conditions.append(PortfolioCashLedger.event_date <= date_to)
            if direction:
                conditions.append(PortfolioCashLedger.direction == direction)

            data_query = select(PortfolioCashLedger)
            count_query = select(func.count()).select_from(PortfolioCashLedger)
            if not include_all_owners:
                owner_filter = PortfolioAccount.owner_id == self.db.require_user_id(owner_id)
                data_query = data_query.join(PortfolioAccount, PortfolioAccount.id == PortfolioCashLedger.account_id)
                count_query = count_query.join(PortfolioAccount, PortfolioAccount.id == PortfolioCashLedger.account_id)
                conditions.append(owner_filter)
            if conditions:
                where_clause = and_(*conditions)
                data_query = data_query.where(where_clause)
                count_query = count_query.where(where_clause)

            total = int(session.execute(count_query).scalar_one() or 0)
            rows = session.execute(
                data_query
                .order_by(PortfolioCashLedger.event_date.desc(), PortfolioCashLedger.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
            return list(rows), total

    def query_corporate_actions(
        self,
        *,
        account_id: Optional[int],
        date_from: Optional[date],
        date_to: Optional[date],
        symbol: Optional[str],
        action_type: Optional[str],
        page: int,
        page_size: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Tuple[List[PortfolioCorporateAction], int]:
        with self.db.get_session() as session:
            conditions = []
            if account_id is not None:
                conditions.append(PortfolioCorporateAction.account_id == account_id)
            if date_from is not None:
                conditions.append(PortfolioCorporateAction.effective_date >= date_from)
            if date_to is not None:
                conditions.append(PortfolioCorporateAction.effective_date <= date_to)
            if symbol:
                conditions.append(PortfolioCorporateAction.symbol == symbol)
            if action_type:
                conditions.append(PortfolioCorporateAction.action_type == action_type)

            data_query = select(PortfolioCorporateAction)
            count_query = select(func.count()).select_from(PortfolioCorporateAction)
            if not include_all_owners:
                owner_filter = PortfolioAccount.owner_id == self.db.require_user_id(owner_id)
                data_query = data_query.join(PortfolioAccount, PortfolioAccount.id == PortfolioCorporateAction.account_id)
                count_query = count_query.join(PortfolioAccount, PortfolioAccount.id == PortfolioCorporateAction.account_id)
                conditions.append(owner_filter)
            if conditions:
                where_clause = and_(*conditions)
                data_query = data_query.where(where_clause)
                count_query = count_query.where(where_clause)

            total = int(session.execute(count_query).scalar_one() or 0)
            rows = session.execute(
                data_query
                .order_by(PortfolioCorporateAction.effective_date.desc(), PortfolioCorporateAction.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
            return list(rows), total

    # ------------------------------------------------------------------
    # Price / FX
    # ------------------------------------------------------------------
    def get_latest_close(self, symbol: str, as_of: date) -> Optional[float]:
        with self.db.get_session() as session:
            row = session.execute(
                select(StockDaily)
                .where(
                    and_(
                        StockDaily.code == symbol,
                        StockDaily.date <= as_of,
                    )
                )
                .order_by(desc(StockDaily.date))
                .limit(1)
            ).scalar_one_or_none()
            if row is None or row.close is None:
                return None
            return float(row.close)

    def save_fx_rate(
        self,
        *,
        from_currency: str,
        to_currency: str,
        rate_date: date,
        rate: float,
        source: str = "manual",
        is_stale: bool = False,
    ) -> None:
        with self.db.get_session() as session:
            existing = session.execute(
                select(PortfolioFxRate).where(
                    and_(
                        PortfolioFxRate.from_currency == from_currency,
                        PortfolioFxRate.to_currency == to_currency,
                        PortfolioFxRate.rate_date == rate_date,
                    )
                ).limit(1)
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    PortfolioFxRate(
                        from_currency=from_currency,
                        to_currency=to_currency,
                        rate_date=rate_date,
                        rate=rate,
                        source=source,
                        is_stale=is_stale,
                    )
                )
            else:
                existing.rate = rate
                existing.source = source
                existing.is_stale = is_stale
                existing.updated_at = datetime.now()
            session.commit()

    def get_latest_fx_rate(
        self,
        *,
        from_currency: str,
        to_currency: str,
        as_of: date,
    ) -> Optional[PortfolioFxRate]:
        with self.db.get_session() as session:
            row = session.execute(
                select(PortfolioFxRate)
                .where(
                    and_(
                        PortfolioFxRate.from_currency == from_currency,
                        PortfolioFxRate.to_currency == to_currency,
                        PortfolioFxRate.rate_date <= as_of,
                    )
                )
                .order_by(desc(PortfolioFxRate.rate_date))
                .limit(1)
            ).scalar_one_or_none()
            return row

    def list_daily_snapshots_for_risk(
        self,
        *,
        as_of: date,
        cost_method: str,
        account_id: Optional[int] = None,
        lookback_days: int = 180,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[PortfolioDailySnapshot]:
        """Load snapshot rows in ascending date order for risk monitoring."""
        with self.db.get_session() as session:
            query = select(PortfolioDailySnapshot).where(
                and_(
                    PortfolioDailySnapshot.snapshot_date <= as_of,
                    PortfolioDailySnapshot.cost_method == cost_method,
                )
            )
            if account_id is not None:
                query = query.where(PortfolioDailySnapshot.account_id == account_id)
            if not include_all_owners:
                query = query.join(PortfolioAccount, PortfolioAccount.id == PortfolioDailySnapshot.account_id).where(
                    PortfolioAccount.owner_id == self.db.require_user_id(owner_id)
                )
            rows = session.execute(
                query.order_by(
                    PortfolioDailySnapshot.snapshot_date.asc(),
                    PortfolioDailySnapshot.account_id.asc(),
                )
            ).scalars().all()
            if lookback_days <= 0:
                return list(rows)
            # Keep only the latest N calendar days window for risk calculations.
            cutoff_ordinal = as_of.toordinal() - lookback_days
            return [row for row in rows if row.snapshot_date.toordinal() >= cutoff_ordinal]

    # ------------------------------------------------------------------
    # Snapshot / position cache
    # ------------------------------------------------------------------
    def replace_positions_and_lots(
        self,
        *,
        account_id: int,
        cost_method: str,
        positions: Iterable[Dict[str, Any]],
        lots: Iterable[Dict[str, Any]],
        valuation_currency: str,
    ) -> None:
        with self.db.get_session() as session:
            session.execute(
                delete(PortfolioPosition).where(
                    and_(
                        PortfolioPosition.account_id == account_id,
                        PortfolioPosition.cost_method == cost_method,
                    )
                )
            )
            session.execute(
                delete(PortfolioPositionLot).where(
                    and_(
                        PortfolioPositionLot.account_id == account_id,
                        PortfolioPositionLot.cost_method == cost_method,
                    )
                )
            )

            for item in positions:
                session.add(
                    PortfolioPosition(
                        account_id=account_id,
                        cost_method=cost_method,
                        symbol=item["symbol"],
                        market=item["market"],
                        currency=item["currency"],
                        quantity=float(item["quantity"]),
                        avg_cost=float(item["avg_cost"]),
                        total_cost=float(item["total_cost"]),
                        last_price=float(item["last_price"]),
                        market_value_base=float(item["market_value_base"]),
                        unrealized_pnl_base=float(item["unrealized_pnl_base"]),
                        valuation_currency=valuation_currency,
                    )
                )

            for lot in lots:
                session.add(
                    PortfolioPositionLot(
                        account_id=account_id,
                        cost_method=cost_method,
                        symbol=lot["symbol"],
                        market=lot["market"],
                        currency=lot["currency"],
                        open_date=lot["open_date"],
                        remaining_quantity=float(lot["remaining_quantity"]),
                        unit_cost=float(lot["unit_cost"]),
                        source_trade_id=lot.get("source_trade_id"),
                    )
                )

            self.db.sync_phase_f_portfolio_account_shadow_from_session(
                session=session,
                account_id=int(account_id),
            )
            session.commit()

    def _invalidate_account_cache_in_session(self, *, session: Any, account_id: int, from_date: date) -> None:
        session.execute(
            delete(PortfolioPositionLot).where(PortfolioPositionLot.account_id == account_id)
        )
        session.execute(
            delete(PortfolioPosition).where(PortfolioPosition.account_id == account_id)
        )
        session.execute(
            delete(PortfolioDailySnapshot).where(
                and_(
                    PortfolioDailySnapshot.account_id == account_id,
                    PortfolioDailySnapshot.snapshot_date >= from_date,
                )
            )
        )

    @staticmethod
    def _is_sqlite_locked_error(exc: OperationalError) -> bool:
        err_text = str(getattr(exc, "orig", exc)).lower()
        return any(
            token in err_text
            for token in (
                "database is locked",
                "database schema is locked",
                "database table is locked",
            )
        )

    @staticmethod
    def _translate_trade_integrity_error(
        *,
        exc: IntegrityError,
        account_id: int,
        trade_uid: Optional[str],
        dedup_hash: Optional[str],
    ) -> Exception:
        err_text = str(getattr(exc, "orig", exc)).lower()
        if trade_uid and ("uix_portfolio_trade_uid" in err_text or "unique" in err_text):
            return DuplicateTradeUidError(
                f"Duplicate trade_uid for account_id={account_id}: {trade_uid}"
            )
        if dedup_hash and (
            "uix_portfolio_trade_dedup_hash" in err_text
            or "portfolio_trades.account_id, portfolio_trades.dedup_hash" in err_text
            or ("unique" in err_text and "dedup_hash" in err_text)
        ):
            return DuplicateTradeDedupHashError(
                f"Duplicate dedup_hash for account_id={account_id}: {dedup_hash}"
            )
        return exc

    def upsert_daily_snapshot(
        self,
        *,
        account_id: int,
        snapshot_date: date,
        cost_method: str,
        base_currency: str,
        total_cash: float,
        total_market_value: float,
        total_equity: float,
        unrealized_pnl: float,
        realized_pnl: float,
        fee_total: float,
        tax_total: float,
        fx_stale: bool,
        payload: str,
    ) -> None:
        with self.db.get_session() as session:
            existing = session.execute(
                select(PortfolioDailySnapshot).where(
                    and_(
                        PortfolioDailySnapshot.account_id == account_id,
                        PortfolioDailySnapshot.snapshot_date == snapshot_date,
                        PortfolioDailySnapshot.cost_method == cost_method,
                    )
                ).limit(1)
            ).scalar_one_or_none()

            if existing is None:
                session.add(
                    PortfolioDailySnapshot(
                        account_id=account_id,
                        snapshot_date=snapshot_date,
                        cost_method=cost_method,
                        base_currency=base_currency,
                        total_cash=total_cash,
                        total_market_value=total_market_value,
                        total_equity=total_equity,
                        unrealized_pnl=unrealized_pnl,
                        realized_pnl=realized_pnl,
                        fee_total=fee_total,
                        tax_total=tax_total,
                        fx_stale=fx_stale,
                        payload=payload,
                    )
                )
            else:
                existing.base_currency = base_currency
                existing.total_cash = total_cash
                existing.total_market_value = total_market_value
                existing.total_equity = total_equity
                existing.unrealized_pnl = unrealized_pnl
                existing.realized_pnl = realized_pnl
                existing.fee_total = fee_total
                existing.tax_total = tax_total
                existing.fx_stale = fx_stale
                existing.payload = payload
                existing.updated_at = datetime.now()
            self.db.sync_phase_f_portfolio_account_shadow_from_session(
                session=session,
                account_id=int(account_id),
            )
            session.commit()

    def replace_positions_lots_and_snapshot(
        self,
        *,
        account_id: int,
        snapshot_date: date,
        cost_method: str,
        base_currency: str,
        total_cash: float,
        total_market_value: float,
        total_equity: float,
        unrealized_pnl: float,
        realized_pnl: float,
        fee_total: float,
        tax_total: float,
        fx_stale: bool,
        payload: str,
        positions: Iterable[Dict[str, Any]],
        lots: Iterable[Dict[str, Any]],
        valuation_currency: str,
    ) -> None:
        """Atomically refresh position cache and daily snapshot in one transaction."""
        with self.db.get_session() as session:
            session.execute(
                delete(PortfolioPosition).where(
                    and_(
                        PortfolioPosition.account_id == account_id,
                        PortfolioPosition.cost_method == cost_method,
                    )
                )
            )
            session.execute(
                delete(PortfolioPositionLot).where(
                    and_(
                        PortfolioPositionLot.account_id == account_id,
                        PortfolioPositionLot.cost_method == cost_method,
                    )
                )
            )

            for item in positions:
                session.add(
                    PortfolioPosition(
                        account_id=account_id,
                        cost_method=cost_method,
                        symbol=item["symbol"],
                        market=item["market"],
                        currency=item["currency"],
                        quantity=float(item["quantity"]),
                        avg_cost=float(item["avg_cost"]),
                        total_cost=float(item["total_cost"]),
                        last_price=float(item["last_price"]),
                        market_value_base=float(item["market_value_base"]),
                        unrealized_pnl_base=float(item["unrealized_pnl_base"]),
                        valuation_currency=valuation_currency,
                    )
                )

            for lot in lots:
                session.add(
                    PortfolioPositionLot(
                        account_id=account_id,
                        cost_method=cost_method,
                        symbol=lot["symbol"],
                        market=lot["market"],
                        currency=lot["currency"],
                        open_date=lot["open_date"],
                        remaining_quantity=float(lot["remaining_quantity"]),
                        unit_cost=float(lot["unit_cost"]),
                        source_trade_id=lot.get("source_trade_id"),
                    )
                )

            existing = session.execute(
                select(PortfolioDailySnapshot).where(
                    and_(
                        PortfolioDailySnapshot.account_id == account_id,
                        PortfolioDailySnapshot.snapshot_date == snapshot_date,
                        PortfolioDailySnapshot.cost_method == cost_method,
                    )
                ).limit(1)
            ).scalar_one_or_none()

            if existing is None:
                session.add(
                    PortfolioDailySnapshot(
                        account_id=account_id,
                        snapshot_date=snapshot_date,
                        cost_method=cost_method,
                        base_currency=base_currency,
                        total_cash=total_cash,
                        total_market_value=total_market_value,
                        total_equity=total_equity,
                        unrealized_pnl=unrealized_pnl,
                        realized_pnl=realized_pnl,
                        fee_total=fee_total,
                        tax_total=tax_total,
                        fx_stale=fx_stale,
                        payload=payload,
                    )
                )
            else:
                existing.base_currency = base_currency
                existing.total_cash = total_cash
                existing.total_market_value = total_market_value
                existing.total_equity = total_equity
                existing.unrealized_pnl = unrealized_pnl
                existing.realized_pnl = realized_pnl
                existing.fee_total = fee_total
                existing.tax_total = tax_total
                existing.fx_stale = fx_stale
                existing.payload = payload
                existing.updated_at = datetime.now()

            self.db.sync_phase_f_portfolio_account_shadow_from_session(
                session=session,
                account_id=int(account_id),
            )
            session.commit()
