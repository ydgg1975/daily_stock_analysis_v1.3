# -*- coding: utf-8 -*-
"""Real PostgreSQL validation for the Phase F portfolio baseline."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy import create_engine, text

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from src.config import Config
from src.postgres_phase_f import (
    PhaseFBrokerConnection,
    PhaseFPortfolioAccount,
    PhaseFPortfolioLedger,
    PhaseFPortfolioPosition,
    PhaseFPortfolioSyncCashBalance,
    PhaseFPortfolioSyncPosition,
    PhaseFPortfolioSyncState,
)
from src.services.portfolio_service import PortfolioService
from src.storage import DatabaseManager

REAL_PG_DSN = str(os.getenv("POSTGRES_PHASE_A_REAL_DSN") or "").strip()


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


@unittest.skipUnless(REAL_PG_DSN, "POSTGRES_PHASE_A_REAL_DSN is required for real PostgreSQL validation")
class PostgresPhaseFRealPgTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.pg_engine = create_engine(REAL_PG_DSN, echo=False, pool_pre_ping=True)
        self._drop_phase_f_tables()
        self._configure_environment()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self._drop_phase_f_tables()
        self.pg_engine.dispose()
        self.temp_dir.cleanup()

    def _configure_environment(self) -> None:
        lines = [
            "STOCK_LIST=600519",
            "GEMINI_API_KEY=test",
            "ADMIN_AUTH_ENABLED=true",
            f"DATABASE_PATH={self.sqlite_db_path}",
            f"POSTGRES_PHASE_A_URL={REAL_PG_DSN}",
            "POSTGRES_PHASE_A_APPLY_SCHEMA=true",
        ]
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        os.environ["POSTGRES_PHASE_A_URL"] = REAL_PG_DSN
        os.environ["POSTGRES_PHASE_A_APPLY_SCHEMA"] = "true"
        Config.reset_instance()
        DatabaseManager.reset_instance()
        auth.refresh_auth_state()

    def _db(self) -> DatabaseManager:
        return DatabaseManager.get_instance()

    def _drop_phase_f_tables(self) -> None:
        with self.pg_engine.begin() as conn:
            conn.execute(text("drop table if exists portfolio_sync_cash_balances cascade"))
            conn.execute(text("drop table if exists portfolio_sync_positions cascade"))
            conn.execute(text("drop table if exists portfolio_sync_states cascade"))
            conn.execute(text("drop table if exists portfolio_positions cascade"))
            conn.execute(text("drop table if exists portfolio_ledger cascade"))
            conn.execute(text("drop table if exists broker_connections cascade"))
            conn.execute(text("drop table if exists portfolio_accounts cascade"))

    def _pg_scalar(self, sql: str, **params):
        with self.pg_engine.begin() as conn:
            return conn.execute(text(sql), params).scalar()

    def test_real_postgres_phase_f_portfolio_round_trip(self) -> None:
        db = self._db()
        db.create_or_update_app_user(user_id="real-pg-phase-f-user", username="real-pg-phase-f-user")
        service = PortfolioService(owner_id="real-pg-phase-f-user")

        account = service.create_account(name="Real PG", broker="IBKR", market="us", base_currency="USD")
        connection = service.create_broker_connection(
            portfolio_account_id=account["id"],
            broker_type="ibkr",
            broker_name="Interactive Brokers",
            connection_name="Real PG IBKR",
            broker_account_ref="U8888888",
            import_mode="file",
            sync_metadata={"source": "flex"},
        )
        service.record_cash_ledger(
            account_id=account["id"],
            event_date=date(2026, 4, 10),
            direction="in",
            amount=5000.0,
            currency="USD",
        )
        service.record_trade(
            account_id=account["id"],
            symbol="AAPL",
            trade_date=date(2026, 4, 11),
            side="buy",
            quantity=10.0,
            price=150.0,
            fee=1.0,
            tax=0.0,
            market="us",
            currency="USD",
            trade_uid="real-pg-trade-1",
            dedup_hash="real-pg-trade-1",
        )
        db.save_daily_data(
            __import__("pandas").DataFrame(
                [
                    {
                        "date": date(2026, 4, 12),
                        "open": 160.0,
                        "high": 160.0,
                        "low": 160.0,
                        "close": 160.0,
                        "volume": 1.0,
                        "amount": 160.0,
                        "pct_chg": 0.0,
                    }
                ]
            ),
            code="AAPL",
            data_source="unit-test",
        )
        service.get_portfolio_snapshot(account_id=account["id"], as_of=date(2026, 4, 12), cost_method="fifo")
        service.replace_broker_sync_state(
            broker_connection_id=connection["id"],
            portfolio_account_id=account["id"],
            broker_type="ibkr",
            broker_account_ref="U8888888",
            sync_source="api",
            sync_status="success",
            snapshot_date=date(2026, 4, 16),
            synced_at=datetime(2026, 4, 16, 8, 45, 0),
            base_currency="USD",
            total_cash=1000.0,
            total_market_value=1600.0,
            total_equity=2600.0,
            realized_pnl=0.0,
            unrealized_pnl=100.0,
            fx_stale=False,
            payload={"snapshot": "real-pg"},
            positions=[
                {
                    "broker_position_ref": "AAPL-1",
                    "symbol": "AAPL",
                    "market": "us",
                    "currency": "USD",
                    "quantity": 10.0,
                    "avg_cost": 150.0,
                    "last_price": 160.0,
                    "market_value_base": 1600.0,
                    "unrealized_pnl_base": 100.0,
                    "valuation_currency": "USD",
                }
            ],
            cash_balances=[{"currency": "USD", "amount": 1000.0, "amount_base": 1000.0}],
        )

        self.assertEqual(self._pg_scalar("select count(*) from portfolio_accounts"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from broker_connections"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from portfolio_ledger"), 2)
        self.assertEqual(self._pg_scalar("select count(*) from portfolio_positions"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from portfolio_sync_states"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from portfolio_sync_positions"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from portfolio_sync_cash_balances"), 1)

        with db._phase_f_store.session_scope() as session:
            self.assertEqual(session.query(PhaseFPortfolioAccount).count(), 1)
            self.assertEqual(session.query(PhaseFBrokerConnection).count(), 1)
            self.assertEqual(session.query(PhaseFPortfolioLedger).count(), 2)
            self.assertEqual(session.query(PhaseFPortfolioPosition).count(), 1)
            self.assertEqual(session.query(PhaseFPortfolioSyncState).count(), 1)
            self.assertEqual(session.query(PhaseFPortfolioSyncPosition).count(), 1)
            self.assertEqual(session.query(PhaseFPortfolioSyncCashBalance).count(), 1)


if __name__ == "__main__":
    unittest.main()
