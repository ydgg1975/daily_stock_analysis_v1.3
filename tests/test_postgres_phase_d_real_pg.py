# -*- coding: utf-8 -*-
"""Real PostgreSQL validation for the Phase D scanner/watchlist baseline."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from sqlalchemy import create_engine, text

import src.auth as auth
from src.config import Config
from src.multi_user import OWNERSHIP_SCOPE_SYSTEM, OWNERSHIP_SCOPE_USER
from src.postgres_phase_d import (
    PhaseDScannerCandidate,
    PhaseDScannerRun,
    PhaseDWatchlist,
    PhaseDWatchlistItem,
)
from src.services.market_scanner_service import MarketScannerService
from src.storage import DatabaseManager

REAL_PG_DSN = str(os.getenv("POSTGRES_PHASE_A_REAL_DSN") or "").strip()


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _candidate_payload(symbol: str, *, name: str, rank: int, score: float) -> dict:
    return {
        "symbol": symbol,
        "name": name,
        "rank": rank,
        "score": score,
        "quality_hint": "高优先级",
        "reason_summary": f"{name} 趋势共振较强。",
        "reasons": [f"{name} 趋势共振较强。"],
        "key_metrics": [{"label": "最新价", "value": "10.20"}],
        "feature_signals": [{"label": "趋势结构", "value": "18.0 / 20"}],
        "risk_notes": ["注意回撤。"],
        "watch_context": [{"label": "观察触发", "value": "突破前高。"}],
        "boards": ["AI算力"],
        "_diagnostics": {"history": {"latest_trade_date": "2026-04-15"}},
    }


@unittest.skipUnless(REAL_PG_DSN, "POSTGRES_PHASE_A_REAL_DSN is required for real PostgreSQL validation")
class PostgresPhaseDRealPgTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.pg_engine = create_engine(REAL_PG_DSN, echo=False, pool_pre_ping=True)
        self._drop_phase_d_tables()
        self._configure_environment()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self._drop_phase_d_tables()
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

    def _drop_phase_d_tables(self) -> None:
        with self.pg_engine.begin() as conn:
            conn.execute(text("drop table if exists watchlist_items cascade"))
            conn.execute(text("drop table if exists watchlists cascade"))
            conn.execute(text("drop table if exists scanner_candidates cascade"))
            conn.execute(text("drop table if exists scanner_runs cascade"))

    def _pg_scalar(self, sql: str, **params):
        with self.pg_engine.begin() as conn:
            return conn.execute(text(sql), params).scalar()

    def test_real_postgres_phase_d_scanner_and_watchlist_round_trip(self) -> None:
        db = self._db()
        db.create_or_update_app_user(user_id="real-pg-user", username="real-pg-user")
        service = MarketScannerService(db, owner_id="real-pg-user")

        manual_run = service.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="A股盘前扫描 v1",
            universe_name="cn_a_liquid_watchlist_v1",
            status="completed",
            headline="real pg manual run",
            trigger_mode="manual",
            request_source="api",
            watchlist_date="2026-04-16",
            source_summary="scanner=daily",
            shortlist=[
                _candidate_payload("600001", name="算力龙头", rank=1, score=88.0),
                _candidate_payload("600002", name="机器人核心", rank=2, score=82.0),
            ],
            scope=OWNERSHIP_SCOPE_USER,
            owner_id="real-pg-user",
        )
        service.update_run_operation_metadata(
            manual_run["id"],
            trigger_mode="manual",
            watchlist_date="2026-04-16",
            request_source="api",
            notification_result={
                "attempted": True,
                "status": "success",
                "success": True,
                "channels": ["feishu"],
            },
            scope=OWNERSHIP_SCOPE_USER,
            owner_id="real-pg-user",
        )
        self.assertEqual(
            self._pg_scalar(
                "select status from scanner_runs where id = :run_id",
                run_id=manual_run["id"],
            ),
            "completed",
        )
        self.assertEqual(
            self._pg_scalar(
                "select notification_status from watchlists where source_scanner_run_id = :run_id",
                run_id=manual_run["id"],
            ),
            "success",
        )
        first_candidate_id = int(
            self._pg_scalar(
                "select min(id) from scanner_candidates where scanner_run_id = :run_id",
                run_id=manual_run["id"],
            )
        )
        service.update_run_operation_metadata(
            manual_run["id"],
            trigger_mode="scheduler",
            watchlist_date="2026-04-17",
            request_source="scheduler",
            notification_result={
                "attempted": True,
                "status": "failed",
                "success": False,
                "channels": ["feishu"],
                "message": "retry later",
            },
            scope=OWNERSHIP_SCOPE_USER,
            owner_id="real-pg-user",
        )
        system_run = service.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="A股盘前扫描 v1",
            universe_name="cn_a_liquid_watchlist_v1",
            status="completed",
            headline="real pg system run",
            trigger_mode="scheduled",
            request_source="scheduler",
            watchlist_date="2026-04-16",
            source_summary="scanner=daily",
            shortlist=[],
            scope=OWNERSHIP_SCOPE_SYSTEM,
            owner_id=None,
        )

        self.assertEqual(self._pg_scalar("select count(*) from scanner_runs"), 2)
        self.assertEqual(self._pg_scalar("select count(*) from scanner_candidates"), 2)
        self.assertEqual(self._pg_scalar("select count(*) from watchlists"), 2)
        self.assertEqual(self._pg_scalar("select count(*) from watchlist_items"), 2)
        self.assertEqual(
            self._pg_scalar(
                "select status from scanner_runs where id = :run_id",
                run_id=manual_run["id"],
            ),
            "completed",
        )
        self.assertEqual(
            self._pg_scalar(
                "select notification_status from watchlists where source_scanner_run_id = :run_id",
                run_id=manual_run["id"],
            ),
            "failed",
        )
        self.assertEqual(
            self._pg_scalar(
                "select watchlist_date::text from watchlists where source_scanner_run_id = :run_id",
                run_id=manual_run["id"],
            ),
            "2026-04-17",
        )
        self.assertEqual(
            self._pg_scalar(
                "select count(*) from watchlist_items where source_scanner_candidate_id = :candidate_id",
                candidate_id=first_candidate_id,
            ),
            1,
        )

        with db._phase_d_store.session_scope() as session:
            self.assertEqual(session.query(PhaseDScannerRun).count(), 2)
            self.assertEqual(session.query(PhaseDScannerCandidate).count(), 2)
            self.assertEqual(session.query(PhaseDWatchlist).count(), 2)
            self.assertEqual(session.query(PhaseDWatchlistItem).count(), 2)

        reset_result = db.factory_reset_non_bootstrap_state()

        self.assertIn("scanner_runs", reset_result["cleared"])
        self.assertEqual(self._pg_scalar("select count(*) from scanner_runs"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from watchlists"), 1)
        self.assertEqual(
            self._pg_scalar(
                "select scope from scanner_runs where id = :run_id",
                run_id=system_run["id"],
            ),
            OWNERSHIP_SCOPE_SYSTEM,
        )


if __name__ == "__main__":
    unittest.main()
