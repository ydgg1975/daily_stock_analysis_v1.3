# -*- coding: utf-8 -*-
"""Focused coverage for the PostgreSQL Phase C market metadata baseline."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from src.config import Config
from src.data.stock_mapping import STOCK_NAME_MAP
from src.postgres_phase_c import (
    PhaseCMarketDataManifest,
    PhaseCMarketDataUsageRef,
    PhaseCMarketDatasetVersion,
    PhaseCSymbolMaster,
)
from src.services.us_history_helper import (
    LOCAL_US_PARQUET_SOURCE,
    LocalUsHistoryLoadResult,
    fetch_daily_history_with_local_us_fallback,
)
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class PostgresPhaseCStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.phase_db_path = self.data_dir / "phase-baseline.sqlite"
        self._configure_environment(enable_phase_c=True)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        os.environ.pop("LOCAL_US_PARQUET_DIR", None)
        self.temp_dir.cleanup()

    def _configure_environment(self, *, enable_phase_c: bool) -> None:
        lines = [
            "STOCK_LIST=600519",
            "GEMINI_API_KEY=test",
            "ADMIN_AUTH_ENABLED=true",
            f"DATABASE_PATH={self.sqlite_db_path}",
        ]
        if enable_phase_c:
            lines.extend(
                [
                    f"POSTGRES_PHASE_A_URL=sqlite:///{self.phase_db_path}",
                    "POSTGRES_PHASE_A_APPLY_SCHEMA=true",
                ]
            )

        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        if enable_phase_c:
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

    def test_phase_c_persists_symbol_manifest_version_and_usage_refs(self) -> None:
        db = self._db()

        symbol = db.upsert_symbol_master_entry(
            canonical_symbol="AAPL",
            display_symbol="AAPL",
            market="us",
            asset_type="equity",
            display_name="苹果",
            currency="USD",
            search_aliases=["Apple", "苹果", " apple "],
            source="stock_mapping",
            source_payload={"seed": "fixture"},
        )
        manifest = db.upsert_market_data_manifest(
            manifest_key="us.local_parquet.daily",
            dataset_family="daily_ohlcv",
            market="us",
            asset_scope="equity",
            storage_backend="parquet_local",
            root_uri="/tmp/us-parquet",
            file_format="parquet",
            partition_strategy="symbol_file",
            symbol_namespace="us_equity",
            description="fixture manifest",
            config={"writer": "fixture"},
        )
        version = db.register_market_dataset_version(
            manifest_key="us.local_parquet.daily",
            version_label="inventory:fixture123",
            version_hash="fixture123",
            source_kind="fixture_inventory",
            generated_at=datetime(2024, 1, 31, 12, 0, 0),
            as_of_date=date(2024, 1, 31),
            coverage_start=date(2024, 1, 1),
            coverage_end=date(2024, 1, 31),
            symbol_count=1,
            row_count=252,
            partition_count=1,
            file_inventory={
                "files": [
                    {
                        "symbol": "AAPL",
                        "relative_path": "AAPL.parquet",
                        "size_bytes": 1024,
                    }
                ]
            },
            content_stats={"fingerprint_kind": "fixture"},
            set_active=True,
        )
        usage = db.record_market_data_usage_ref(
            entity_type="analysis_record",
            entity_id=42,
            usage_role="primary_bars",
            manifest_key="us.local_parquet.daily",
            dataset_version_id=int(version.id),
            detail={"symbol": "AAPL", "resolved_source": LOCAL_US_PARQUET_SOURCE},
        )
        usage_duplicate = db.record_market_data_usage_ref(
            entity_type="analysis_record",
            entity_id=42,
            usage_role="primary_bars",
            manifest_key="us.local_parquet.daily",
            dataset_version_id=int(version.id),
            detail={"symbol": "AAPL", "resolved_source": LOCAL_US_PARQUET_SOURCE},
        )

        self.assertIsNotNone(symbol)
        self.assertIsNotNone(manifest)
        self.assertIsNotNone(version)
        self.assertEqual(int(usage.id), int(usage_duplicate.id))
        self.assertEqual(symbol.market, "us")
        self.assertEqual(symbol.asset_type, "equity")
        self.assertEqual(symbol.currency, "USD")
        self.assertEqual(symbol.search_aliases, ["Apple", "苹果"])

        manifest_row = db.get_market_data_manifest("us.local_parquet.daily")
        version_row = db.get_market_dataset_version(int(version.id))
        usage_rows = db.get_market_data_usage_refs(entity_type="analysis_record", entity_id=42)

        self.assertIsNotNone(manifest_row)
        self.assertEqual(int(manifest_row.active_version_id), int(version.id))
        self.assertIsNotNone(version_row)
        self.assertEqual(version_row.coverage_start.isoformat(), "2024-01-01")
        self.assertEqual(version_row.coverage_end.isoformat(), "2024-01-31")
        self.assertEqual(len(usage_rows), 1)
        self.assertEqual(usage_rows[0].detail_json["resolved_source"], LOCAL_US_PARQUET_SOURCE)

        with db._phase_c_store.session_scope() as session:
            self.assertEqual(session.query(PhaseCSymbolMaster).count(), 1)
            self.assertEqual(session.query(PhaseCMarketDataManifest).count(), 1)
            self.assertEqual(session.query(PhaseCMarketDatasetVersion).count(), 1)
            self.assertEqual(session.query(PhaseCMarketDataUsageRef).count(), 1)

    def test_phase_c_can_seed_symbol_master_from_static_stock_mapping(self) -> None:
        db = self._db()

        seeded = db.seed_symbol_master_from_stock_mapping(symbols=["600519", "AAPL", "00700"])

        self.assertEqual(seeded, 3)
        cn_row = db.get_symbol_master_entry("600519")
        us_row = db.get_symbol_master_entry("AAPL")
        hk_row = db.get_symbol_master_entry("00700")

        self.assertEqual(cn_row.display_name, STOCK_NAME_MAP["600519"])
        self.assertEqual(cn_row.market, "cn")
        self.assertEqual(cn_row.currency, "CNY")
        self.assertIn(STOCK_NAME_MAP["600519"], cn_row.search_aliases)

        self.assertEqual(us_row.display_name, STOCK_NAME_MAP["AAPL"])
        self.assertEqual(us_row.market, "us")
        self.assertEqual(us_row.currency, "USD")

        self.assertEqual(hk_row.display_name, STOCK_NAME_MAP["00700"])
        self.assertEqual(hk_row.market, "hk")
        self.assertEqual(hk_row.currency, "HKD")
        self.assertEqual(hk_row.source, "stock_mapping")

    def test_phase_c_registers_local_us_parquet_metadata_without_changing_history_helper_behavior(self) -> None:
        db = self._db()
        parquet_root = self.data_dir / "local-us"
        parquet_root.mkdir(parents=True, exist_ok=True)
        parquet_path = parquet_root / "AAPL.parquet"
        parquet_bytes = b"phase-c-fake-parquet-body"
        parquet_path.write_bytes(parquet_bytes)
        local_df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
                "close": [100.0, 101.5],
            }
        )
        local_result = LocalUsHistoryLoadResult(
            stock_code="AAPL",
            path=parquet_path,
            status="hit",
            dataframe=local_df,
        )

        with patch.dict(os.environ, {"LOCAL_US_PARQUET_DIR": str(parquet_root)}, clear=False):
            with patch(
                "src.services.us_history_helper.load_local_us_daily_history",
                return_value=local_result,
            ):
                df, source = fetch_daily_history_with_local_us_fallback(
                    "AAPL",
                    days=20,
                    manager=MagicMock(),
                    log_context="[phase-c]",
                )

            version = db.register_local_us_parquet_dataset_version(root_path=parquet_root)
            detail = db.build_local_us_parquet_usage_detail(
                stock_code="AAPL",
                file_path=parquet_path,
                dataframe=local_df,
                source_name=source,
            )
            usage = db.record_market_data_usage_ref(
                entity_type="analysis_record",
                entity_id=99,
                usage_role="primary_bars",
                manifest_key="us.local_parquet.daily",
                dataset_version_id=int(version.id),
                detail=detail,
            )

        self.assertIs(df, local_df)
        self.assertEqual(source, LOCAL_US_PARQUET_SOURCE)
        self.assertEqual(version.symbol_count, 1)
        self.assertEqual(version.partition_count, 1)
        self.assertEqual(version.file_inventory_json["files"][0]["relative_path"], "AAPL.parquet")
        self.assertEqual(detail["resolved_source"], LOCAL_US_PARQUET_SOURCE)
        self.assertEqual(detail["coverage_start"], "2024-01-02")
        self.assertEqual(detail["coverage_end"], "2024-01-03")
        self.assertEqual(detail["row_count"], 2)
        self.assertEqual(detail["content_hash"], hashlib.sha256(parquet_bytes).hexdigest())
        self.assertEqual(usage.detail_json["resolved_path"], str(parquet_path.resolve()))


if __name__ == "__main__":
    unittest.main()
