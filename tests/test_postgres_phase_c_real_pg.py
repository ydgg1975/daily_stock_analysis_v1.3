# -*- coding: utf-8 -*-
"""Real PostgreSQL validation for the Phase C market metadata baseline."""

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
from src.postgres_phase_c import (
    PhaseCMarketDataManifest,
    PhaseCMarketDataUsageRef,
    PhaseCMarketDatasetVersion,
    PhaseCSymbolMaster,
)
from src.storage import DatabaseManager

REAL_PG_DSN = str(os.getenv("POSTGRES_PHASE_A_REAL_DSN") or "").strip()


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


@unittest.skipUnless(REAL_PG_DSN, "POSTGRES_PHASE_A_REAL_DSN is required for real PostgreSQL validation")
class PostgresPhaseCRealPgTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.pg_engine = create_engine(REAL_PG_DSN, echo=False, pool_pre_ping=True)
        self._drop_phase_c_tables()
        self._configure_environment()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self._drop_phase_c_tables()
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

    def _drop_phase_c_tables(self) -> None:
        with self.pg_engine.begin() as conn:
            conn.execute(text("drop table if exists market_data_usage_refs cascade"))
            conn.execute(text("drop table if exists market_dataset_versions cascade"))
            conn.execute(text("drop table if exists market_data_manifests cascade"))
            conn.execute(text("drop table if exists symbol_master cascade"))

    def _pg_scalar(self, sql: str, **params):
        with self.pg_engine.begin() as conn:
            return conn.execute(text(sql), params).scalar()

    def test_real_postgres_phase_c_metadata_round_trip(self) -> None:
        db = self._db()
        parquet_root = self.data_dir / "local-us"
        parquet_root.mkdir(parents=True, exist_ok=True)
        parquet_path = parquet_root / "AAPL.parquet"
        parquet_path.write_bytes(b"real-pg-phase-c")

        symbol = db.upsert_symbol_master_entry(
            canonical_symbol="AAPL",
            display_symbol="AAPL",
            market="us",
            asset_type="equity",
            display_name="苹果",
            currency="USD",
            search_aliases=["Apple", "苹果"],
            source="stock_mapping",
            source_payload={"seed": "real-pg"},
        )
        version = db.register_local_us_parquet_dataset_version(root_path=parquet_root)
        usage = db.record_market_data_usage_ref(
            entity_type="analysis_record",
            entity_id=501,
            usage_role="primary_bars",
            manifest_key="us.local_parquet.daily",
            dataset_version_id=int(version.id),
            detail={"symbol": "AAPL", "resolved_path": str(parquet_path.resolve())},
        )

        self.assertEqual(symbol.canonical_symbol, "AAPL")
        self.assertEqual(self._pg_scalar("select count(*) from symbol_master"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from market_data_manifests"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from market_dataset_versions"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from market_data_usage_refs"), 1)
        self.assertEqual(
            self._pg_scalar(
                "select active_version_id from market_data_manifests where manifest_key = :manifest_key",
                manifest_key="us.local_parquet.daily",
            ),
            int(version.id),
        )
        self.assertEqual(
            self._pg_scalar(
                "select count(*) from market_data_usage_refs where entity_type = 'analysis_record' and entity_id = :entity_id",
                entity_id=501,
            ),
            1,
        )
        self.assertEqual(int(usage.dataset_version_id), int(version.id))

        with db._phase_c_store.session_scope() as session:
            self.assertEqual(session.query(PhaseCSymbolMaster).count(), 1)
            self.assertEqual(session.query(PhaseCMarketDataManifest).count(), 1)
            self.assertEqual(session.query(PhaseCMarketDatasetVersion).count(), 1)
            self.assertEqual(session.query(PhaseCMarketDataUsageRef).count(), 1)


if __name__ == "__main__":
    unittest.main()
