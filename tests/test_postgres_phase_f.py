# -*- coding: utf-8 -*-
"""Focused coverage for the PostgreSQL Phase F portfolio baseline."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

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


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class PostgresPhaseFStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.phase_db_path = self.data_dir / "phase-baseline.sqlite"
        self._configure_environment(enable_phase_f=True)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self.temp_dir.cleanup()

    def _configure_environment(self, *, enable_phase_f: bool) -> None:
        lines = [
            "STOCK_LIST=600519",
            "GEMINI_API_KEY=test",
            "ADMIN_AUTH_ENABLED=true",
            f"DATABASE_PATH={self.sqlite_db_path}",
        ]
        if enable_phase_f:
            lines.extend(
                [
                    f"POSTGRES_PHASE_A_URL=sqlite:///{self.phase_db_path}",
                    "POSTGRES_PHASE_A_APPLY_SCHEMA=true",
                ]
            )

        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        if enable_phase_f:
            os.environ["POSTGRES_PHASE_A_URL"] = f"sqlite:///{self.phase_db_path}"
            os.environ["POSTGRES_PHASE_A_APPLY_SCHEMA"] = "true"
        else:
            os.environ.pop("POSTGRES_PHASE_A_URL", None)
            os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)

        Config.reset_instance()
        DatabaseManager.reset_instance()
        auth.refresh_auth_state()

    def _db(self) -> DatabaseManager:
        return DatabaseManager.get_instance()

    def test_phase_f_dual_writes_accounts_connections_and_sync_overlay_without_changing_current_reads(self) -> None:
        db = self._db()
        db.create_or_update_app_user(user_id="phase-f-user", username="phase-f-user")
        service = PortfolioService(owner_id="phase-f-user")

        account = service.create_account(
            name="Global",
            broker="IBKR",
            market="us",
            base_currency="USD",
        )
        connection = service.create_broker_connection(
            portfolio_account_id=account["id"],
            broker_type="ibkr",
            broker_name="Interactive Brokers",
            connection_name="Primary IBKR",
            broker_account_ref="U1234567",
            import_mode="file",
            sync_metadata={"source": "flex"},
        )

        service.replace_broker_sync_state(
            broker_connection_id=connection["id"],
            portfolio_account_id=account["id"],
            broker_type="ibkr",
            broker_account_ref="U1234567",
            sync_source="api",
            sync_status="success",
            snapshot_date=date(2026, 4, 16),
            synced_at=datetime(2026, 4, 16, 8, 30, 0),
            base_currency="USD",
            total_cash=1000.0,
            total_market_value=2500.0,
            total_equity=3500.0,
            realized_pnl=25.0,
            unrealized_pnl=75.0,
            fx_stale=False,
            payload={"snapshot": "initial"},
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
                    "payload_json": '{"source":"ibkr"}',
                },
                {
                    "broker_position_ref": "MSFT-1",
                    "symbol": "MSFT",
                    "market": "us",
                    "currency": "USD",
                    "quantity": 5.0,
                    "avg_cost": 180.0,
                    "last_price": 190.0,
                    "market_value_base": 950.0,
                    "unrealized_pnl_base": 50.0,
                    "valuation_currency": "USD",
                    "payload_json": '{"source":"ibkr"}',
                },
            ],
            cash_balances=[
                {"currency": "USD", "amount": 800.0, "amount_base": 800.0},
                {"currency": "HKD", "amount": 1560.0, "amount_base": 200.0},
            ],
        )

        current_accounts = service.list_accounts()
        current_connections = service.list_broker_connections(portfolio_account_id=account["id"])
        current_sync_state = service.get_latest_broker_sync_state(portfolio_account_id=account["id"])

        self.assertEqual([item["name"] for item in current_accounts], ["Global"])
        self.assertEqual([item["broker_account_ref"] for item in current_connections], ["U1234567"])
        self.assertEqual([item["symbol"] for item in current_sync_state["positions"]], ["AAPL", "MSFT"])
        self.assertEqual([item["currency"] for item in current_sync_state["cash_balances"]], ["HKD", "USD"])

        with db._phase_f_store.session_scope() as session:
            pg_account = session.query(PhaseFPortfolioAccount).filter(PhaseFPortfolioAccount.id == account["id"]).one()
            pg_connection = session.query(PhaseFBrokerConnection).filter(PhaseFBrokerConnection.id == connection["id"]).one()
            pg_sync_state = (
                session.query(PhaseFPortfolioSyncState)
                .filter(PhaseFPortfolioSyncState.broker_connection_id == connection["id"])
                .one()
            )
            pg_sync_positions = (
                session.query(PhaseFPortfolioSyncPosition)
                .filter(PhaseFPortfolioSyncPosition.portfolio_sync_state_id == pg_sync_state.id)
                .order_by(PhaseFPortfolioSyncPosition.canonical_symbol.asc())
                .all()
            )
            pg_cash_balances = (
                session.query(PhaseFPortfolioSyncCashBalance)
                .filter(PhaseFPortfolioSyncCashBalance.portfolio_sync_state_id == pg_sync_state.id)
                .order_by(PhaseFPortfolioSyncCashBalance.currency.asc())
                .all()
            )

        self.assertEqual(pg_account.owner_user_id, "phase-f-user")
        self.assertEqual(pg_account.broker_label, "IBKR")
        self.assertEqual(pg_connection.owner_user_id, "phase-f-user")
        self.assertEqual(pg_connection.portfolio_account_id, account["id"])
        self.assertEqual(pg_connection.sync_metadata["source"], "flex")
        self.assertEqual(pg_sync_state.owner_user_id, "phase-f-user")
        self.assertEqual(pg_sync_state.payload_json["snapshot"], "initial")
        self.assertEqual([row.canonical_symbol for row in pg_sync_positions], ["AAPL", "MSFT"])
        self.assertEqual([row.currency for row in pg_cash_balances], ["HKD", "USD"])
        self.assertEqual(float(pg_cash_balances[0].amount_base), 200.0)

    def test_phase_f_dual_writes_ledger_and_replayed_positions_while_preserving_owner_isolation(self) -> None:
        db = self._db()
        db.create_or_update_app_user(user_id="portfolio-user-a", username="portfolio-user-a")
        db.create_or_update_app_user(user_id="portfolio-user-b", username="portfolio-user-b")
        service_a = PortfolioService(owner_id="portfolio-user-a")
        service_b = PortfolioService(owner_id="portfolio-user-b")

        account_a = service_a.create_account(name="Alice", broker="Demo", market="us", base_currency="USD")
        account_b = service_b.create_account(name="Bob", broker="Demo", market="us", base_currency="USD")

        service_a.record_cash_ledger(
            account_id=account_a["id"],
            event_date=date(2026, 4, 10),
            direction="in",
            amount=5000.0,
            currency="USD",
        )
        service_a.record_trade(
            account_id=account_a["id"],
            symbol="AAPL",
            trade_date=date(2026, 4, 11),
            side="buy",
            quantity=10.0,
            price=150.0,
            fee=1.0,
            tax=0.0,
            market="us",
            currency="USD",
            trade_uid="alice-buy-1",
            dedup_hash="alice-dedup-1",
        )
        service_a.record_corporate_action(
            account_id=account_a["id"],
            symbol="AAPL",
            effective_date=date(2026, 4, 12),
            action_type="cash_dividend",
            market="us",
            currency="USD",
            cash_dividend_per_share=0.2,
        )

        service_b.record_cash_ledger(
            account_id=account_b["id"],
            event_date=date(2026, 4, 10),
            direction="in",
            amount=3000.0,
            currency="USD",
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
        snapshot = service_a.get_portfolio_snapshot(
            account_id=account_a["id"],
            as_of=date(2026, 4, 12),
            cost_method="fifo",
        )

        self.assertEqual(snapshot["accounts"][0]["positions"][0]["symbol"], "AAPL")

        with db._phase_f_store.session_scope() as session:
            pg_ledger_rows = (
                session.query(PhaseFPortfolioLedger)
                .filter(PhaseFPortfolioLedger.portfolio_account_id == account_a["id"])
                .order_by(PhaseFPortfolioLedger.event_time.asc(), PhaseFPortfolioLedger.id.asc())
                .all()
            )
            pg_positions = (
                session.query(PhaseFPortfolioPosition)
                .filter(PhaseFPortfolioPosition.portfolio_account_id == account_a["id"])
                .order_by(PhaseFPortfolioPosition.canonical_symbol.asc())
                .all()
            )
            pg_other_owner_ledger = (
                session.query(PhaseFPortfolioLedger)
                .filter(PhaseFPortfolioLedger.portfolio_account_id == account_b["id"])
                .all()
            )

        self.assertEqual([row.entry_type for row in pg_ledger_rows], ["cash", "trade", "corporate_action"])
        self.assertEqual(pg_ledger_rows[1].owner_user_id, "portfolio-user-a")
        self.assertEqual(pg_ledger_rows[1].external_ref, "alice-buy-1")
        self.assertEqual(pg_ledger_rows[1].dedup_hash, "alice-dedup-1")
        self.assertEqual(pg_ledger_rows[1].payload_json["side"], "buy")
        self.assertEqual(len(pg_positions), 1)
        self.assertEqual(pg_positions[0].owner_user_id, "portfolio-user-a")
        self.assertEqual(pg_positions[0].source_kind, "replayed_ledger")
        self.assertEqual(pg_positions[0].canonical_symbol, "AAPL")
        self.assertAlmostEqual(float(pg_positions[0].quantity), 10.0, places=6)
        self.assertEqual(len(pg_other_owner_ledger), 1)
        self.assertEqual(pg_other_owner_ledger[0].owner_user_id, "portfolio-user-b")

    def test_phase_f_shadow_resync_tracks_delete_paths_and_overlay_replacement(self) -> None:
        db = self._db()
        db.create_or_update_app_user(user_id="cleanup-user", username="cleanup-user")
        service = PortfolioService(owner_id="cleanup-user")

        account = service.create_account(name="Cleanup", broker="IBKR", market="us", base_currency="USD")
        connection = service.create_broker_connection(
            portfolio_account_id=account["id"],
            broker_type="ibkr",
            broker_name="Interactive Brokers",
            connection_name="Cleanup IBKR",
            broker_account_ref="U7654321",
            import_mode="file",
        )
        trade = service.record_trade(
            account_id=account["id"],
            symbol="AAPL",
            trade_date=date(2026, 4, 10),
            side="buy",
            quantity=10.0,
            price=150.0,
            market="us",
            currency="USD",
            trade_uid="cleanup-trade-1",
            dedup_hash="cleanup-trade-1",
        )

        service.replace_broker_sync_state(
            broker_connection_id=connection["id"],
            portfolio_account_id=account["id"],
            broker_type="ibkr",
            broker_account_ref="U7654321",
            sync_source="api",
            sync_status="success",
            snapshot_date=date(2026, 4, 16),
            synced_at=datetime(2026, 4, 16, 9, 0, 0),
            base_currency="USD",
            total_cash=500.0,
            total_market_value=1600.0,
            total_equity=2100.0,
            realized_pnl=0.0,
            unrealized_pnl=100.0,
            fx_stale=False,
            payload={"revision": 1},
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
            cash_balances=[{"currency": "USD", "amount": 500.0, "amount_base": 500.0}],
        )

        service.replace_broker_sync_state(
            broker_connection_id=connection["id"],
            portfolio_account_id=account["id"],
            broker_type="ibkr",
            broker_account_ref="U7654321",
            sync_source="api",
            sync_status="success",
            snapshot_date=date(2026, 4, 17),
            synced_at=datetime(2026, 4, 17, 9, 0, 0),
            base_currency="USD",
            total_cash=650.0,
            total_market_value=0.0,
            total_equity=650.0,
            realized_pnl=50.0,
            unrealized_pnl=0.0,
            fx_stale=False,
            payload={"revision": 2},
            positions=[],
            cash_balances=[{"currency": "USD", "amount": 650.0, "amount_base": 650.0}],
        )
        deleted = service.delete_trade_event(trade["id"])

        self.assertTrue(deleted)
        self.assertEqual(service.list_trade_events(account_id=account["id"], page=1, page_size=20)["items"], [])

        with db._phase_f_store.session_scope() as session:
            pg_ledger_rows = (
                session.query(PhaseFPortfolioLedger)
                .filter(PhaseFPortfolioLedger.portfolio_account_id == account["id"])
                .all()
            )
            pg_sync_state = (
                session.query(PhaseFPortfolioSyncState)
                .filter(PhaseFPortfolioSyncState.broker_connection_id == connection["id"])
                .one()
            )
            pg_sync_positions = (
                session.query(PhaseFPortfolioSyncPosition)
                .filter(PhaseFPortfolioSyncPosition.portfolio_sync_state_id == pg_sync_state.id)
                .all()
            )
            pg_cash_balances = (
                session.query(PhaseFPortfolioSyncCashBalance)
                .filter(PhaseFPortfolioSyncCashBalance.portfolio_sync_state_id == pg_sync_state.id)
                .all()
            )

        self.assertEqual(len(pg_ledger_rows), 0)
        self.assertEqual(pg_sync_state.snapshot_date.isoformat(), "2026-04-17")
        self.assertEqual(pg_sync_state.payload_json["revision"], 2)
        self.assertEqual(pg_sync_positions, [])
        self.assertEqual(len(pg_cash_balances), 1)
        self.assertAlmostEqual(float(pg_cash_balances[0].amount), 650.0, places=6)


if __name__ == "__main__":
    unittest.main()
