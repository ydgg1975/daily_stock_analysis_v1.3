# -*- coding: utf-8 -*-
"""Real PostgreSQL validation for the Phase E backtest baseline."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from sqlalchemy import create_engine, text

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from src.config import Config
from src.postgres_phase_e import PhaseEBacktestArtifact, PhaseEBacktestRun, phase_e_shadow_run_id
from src.services.backtest_service import BacktestService
from src.services.rule_backtest_service import RuleBacktestService
from src.services.us_history_helper import LOCAL_US_PARQUET_SOURCE
from src.storage import AnalysisHistory, DatabaseManager, RuleBacktestRun, RuleBacktestTrade, StockDaily

REAL_PG_DSN = str(os.getenv("POSTGRES_PHASE_A_REAL_DSN") or "").strip()


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


@unittest.skipUnless(REAL_PG_DSN, "POSTGRES_PHASE_A_REAL_DSN is required for real PostgreSQL validation")
class PostgresPhaseERealPgTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.pg_engine = create_engine(REAL_PG_DSN, echo=False, pool_pre_ping=True)
        self._drop_phase_e_tables()
        self._configure_environment()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        os.environ.pop("LOCAL_US_PARQUET_DIR", None)
        self._drop_phase_e_tables()
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

    def _drop_phase_e_tables(self) -> None:
        with self.pg_engine.begin() as conn:
            conn.execute(text("delete from market_data_usage_refs where entity_type = 'backtest_run'"))
            conn.execute(text("drop table if exists backtest_artifacts cascade"))
            conn.execute(text("drop table if exists backtest_runs cascade"))

    def _pg_scalar(self, sql: str, **params):
        with self.pg_engine.begin() as conn:
            return conn.execute(text(sql), params).scalar()

    def _create_user(self, user_id: str = "real-pg-phase-e-user") -> None:
        self._db().create_or_update_app_user(
            user_id=user_id,
            username=user_id,
            display_name="Real PG Phase E User",
            role="user",
            password_hash="hash",
            is_active=True,
        )

    def _seed_historical_eval_fixture(self, *, owner_id: str, code: str) -> None:
        created_at = datetime(2024, 1, 1, 0, 0, 0) - timedelta(days=30)
        with self._db().get_session() as session:
            session.add(
                AnalysisHistory(
                    owner_id=owner_id,
                    query_id=f"real-pg-phase-e:{code}",
                    code=code,
                    name=code,
                    report_type="simple",
                    sentiment_score=80,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="real pg phase e fixture",
                    stop_loss=95.0,
                    take_profit=110.0,
                    created_at=created_at,
                    context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
                )
            )
            session.commit()

    def _seed_rule_prices(self, *, code: str = "600519") -> None:
        with self._db().get_session() as session:
            closes = [
                10.0, 10.2, 10.1, 10.5, 11.0, 11.6, 11.8, 11.2,
                10.8, 10.2, 9.9, 10.3, 10.9, 11.4, 11.9, 12.1,
                11.7, 11.1, 10.7, 10.4, 10.8, 11.3, 11.8, 12.2,
            ]
            for index, close in enumerate(closes):
                current_date = date(2024, 1, 1) + timedelta(days=index)
                session.add(
                    StockDaily(
                        code=code,
                        date=current_date,
                        open=close - 0.1,
                        high=close + 0.2,
                        low=close - 0.3,
                        close=float(close),
                        data_source="DatabaseCache",
                    )
                )
            session.commit()

    def test_real_postgres_phase_e_historical_eval_round_trip(self) -> None:
        db = self._db()
        self._create_user()
        self._seed_historical_eval_fixture(owner_id="real-pg-phase-e-user", code="AAPL")

        parquet_root = self.data_dir / "local-us"
        parquet_root.mkdir(parents=True, exist_ok=True)
        (parquet_root / "AAPL.parquet").write_bytes(b"real-pg-phase-e")
        os.environ["LOCAL_US_PARQUET_DIR"] = str(parquet_root)

        fixture_df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]),
                "open": [100.0, 101.0, 102.0, 103.0],
                "high": [101.0, 111.0, 108.0, 109.0],
                "low": [99.0, 100.0, 103.0, 104.0],
                "close": [100.0, 105.0, 106.0, 107.0],
                "volume": [1000, 1000, 1000, 1000],
            }
        )
        service = BacktestService(db, owner_id="real-pg-phase-e-user")
        with patch.object(
            service,
            "_load_history_with_local_us_fallback",
            return_value=(fixture_df, LOCAL_US_PARQUET_SOURCE),
        ):
            stats = service.run_backtest(code="AAPL", force=False, eval_window_days=3, min_age_days=0, limit=10)

        self.assertEqual(stats["saved"], 1)
        run_id = int(
            self._pg_scalar(
                "select id from backtest_runs where run_type = 'analysis_eval' and owner_user_id = :owner_user_id",
                owner_user_id="real-pg-phase-e-user",
            )
        )
        self.assertEqual(self._pg_scalar("select count(*) from backtest_runs"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from backtest_artifacts"), 2)
        self.assertEqual(
            self._pg_scalar(
                "select count(*) from market_data_usage_refs where entity_type = 'backtest_run' and entity_id = :entity_id",
                entity_id=run_id,
            ),
            1,
        )

        with db._phase_e_store.session_scope() as session:
            self.assertEqual(session.query(PhaseEBacktestRun).count(), 1)
            self.assertEqual(session.query(PhaseEBacktestArtifact).count(), 2)

    def test_real_postgres_phase_e_rule_backtest_round_trip_and_factory_reset(self) -> None:
        db = self._db()
        self._create_user()
        self._seed_rule_prices()
        service = RuleBacktestService(db, owner_id="real-pg-phase-e-user")

        with patch.object(service, "_get_llm_adapter", return_value=None):
            submitted = service.submit_backtest(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                start_date="2024-01-08",
                end_date="2024-01-18",
                lookback_bars=20,
                confirmed=True,
            )
            service.process_submitted_run(submitted["id"])

        self.assertEqual(
            self._pg_scalar(
                "select status from backtest_runs where id = :run_id",
                run_id=phase_e_shadow_run_id("rule_deterministic", int(submitted["id"])),
            ),
            "completed",
        )
        self.assertEqual(
            self._pg_scalar(
                "select count(*) from backtest_artifacts where backtest_run_id = :run_id and artifact_kind = 'comparison'",
                run_id=phase_e_shadow_run_id("rule_deterministic", int(submitted["id"])),
            ),
            1,
        )

        with db.get_session() as session:
            sqlite_run = session.query(RuleBacktestRun).filter(RuleBacktestRun.id == int(submitted["id"])).one()
            sqlite_trade_count = session.query(RuleBacktestTrade).filter(RuleBacktestTrade.run_id == sqlite_run.id).count()
        self.assertGreater(sqlite_trade_count, 0)

        reset_result = db.factory_reset_non_bootstrap_state()
        self.assertIn("backtest_runs", reset_result["cleared"])
        self.assertEqual(self._pg_scalar("select count(*) from backtest_runs"), 0)
        self.assertEqual(self._pg_scalar("select count(*) from backtest_artifacts"), 0)


if __name__ == "__main__":
    unittest.main()
