# -*- coding: utf-8 -*-
"""Foundation tests for the Phase 1 crypto scanner backend lane."""

import os
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import inspect

from src.config import Config
from src.scheduler import Scheduler
from src.storage import DatabaseManager


class CryptoConfigTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        Config.reset_instance()

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_load_from_env_normalizes_default_and_custom_crypto_chains(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "CRYPTO_ENABLED": "true",
            "CRYPTO_CHAINS": " solana,base,SOLANA, arbitrum ,bsc ",
            "CRYPTO_REFRESH_INTERVAL_SEC": "60",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertTrue(config.crypto_enabled)
        self.assertEqual(config.crypto_refresh_interval_sec, 60)
        self.assertEqual(config.crypto_chains, ["solana", "base", "arbitrum", "bsc"])


class CryptoSchedulerTestCase(unittest.TestCase):
    def test_set_interval_task_registers_seconds_job_without_immediate_run(self) -> None:
        calls = []

        scheduler = Scheduler()
        scheduler.set_interval_task(lambda: calls.append("ran"), interval_seconds=60, run_immediately=False)

        self.assertEqual(calls, [])
        jobs = scheduler.schedule.get_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].interval, 60)
        self.assertEqual(jobs[0].unit, "seconds")


class CryptoStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "crypto_scanner.db")
        DatabaseManager.reset_instance()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def test_database_initialization_creates_crypto_launch_tables(self) -> None:
        manager = DatabaseManager(db_url=f"sqlite:///{self._db_path}")
        table_names = set(inspect(manager._engine).get_table_names())

        self.assertIn("crypto_launches", table_names)
        self.assertIn("crypto_launch_snapshots", table_names)


class CryptoFetcherValidationTestCase(unittest.TestCase):
    def test_validate_enabled_chains_rejects_unsupported_chain(self) -> None:
        from data_provider.crypto_launch_fetcher import CryptoLaunchFetcher

        fetcher = CryptoLaunchFetcher()

        with self.assertRaises(ValueError):
            fetcher.validate_enabled_chains(["bsc", "unsupported-chain"])


class CryptoUpsertTestCase(unittest.TestCase):
    """Tests for upsert_launch returning (id, is_new) tuple."""

    def setUp(self) -> None:
        from src.repositories.crypto_launch_repo import CryptoLaunchRepository
        from src.storage import DatabaseManager

        DatabaseManager.reset_instance()
        self.db = DatabaseManager("sqlite:///:memory:")
        self.repo = CryptoLaunchRepository(self.db)

    def tearDown(self) -> None:
        from src.storage import DatabaseManager

        DatabaseManager.reset_instance()

    def test_upsert_returns_tuple_with_is_new_true_on_insert(self) -> None:
        data = {
            "chain_id": "bsc",
            "pair_address": "0xtest123",
            "base_token_symbol": "TEST",
            "base_token_name": "Test Token",
            "base_token_address": "0xtoken123",
        }

        result = self.repo.upsert_launch(data)

        self.assertIsNotNone(result)
        launch_id, is_new = result
        self.assertIsInstance(launch_id, int)
        self.assertTrue(is_new)

    def test_upsert_returns_tuple_with_is_new_false_on_update(self) -> None:
        data = {
            "chain_id": "bsc",
            "pair_address": "0xtest123",
            "base_token_symbol": "TEST",
            "base_token_name": "Test Token",
            "base_token_address": "0xtoken123",
        }

        result1 = self.repo.upsert_launch(data)
        result2 = self.repo.upsert_launch(data)

        self.assertIsNotNone(result1)
        self.assertIsNotNone(result2)
        launch_id, is_new = result2
        self.assertIsInstance(launch_id, int)
        self.assertFalse(is_new)


class CryptoLaunchServiceScanTestCase(unittest.TestCase):
    """Tests for scan_once new/updated counters and retention cleanup."""

    def tearDown(self) -> None:
        Config.reset_instance()

    def test_scan_once_tracks_new_and_updated_counts(self) -> None:
        from data_provider.crypto_launch_fetcher import NormalizedLaunch
        from src.services.crypto_launch_service import CryptoLaunchService

        config = SimpleNamespace(
            crypto_chains=["bsc"],
            crypto_discovery_timeout_sec=5,
            crypto_enrichment_timeout_sec=5,
            crypto_refresh_interval_sec=60,
            crypto_enabled=True,
            crypto_snapshot_retention_days=7,
        )

        first_launch = NormalizedLaunch(
            chain_id="bsc",
            pair_address="0xnew",
            base_token_symbol="NEW",
            base_token_name="New Token",
            base_token_address="0xbase1",
            pair_created_at=datetime.now(),
        )
        second_launch = NormalizedLaunch(
            chain_id="bsc",
            pair_address="0xexisting",
            base_token_symbol="OLD",
            base_token_name="Old Token",
            base_token_address="0xbase2",
            pair_created_at=datetime.now(),
        )

        class FakeFetcher:
            def validate_enabled_chains(self, chains):
                return chains

            def discover_and_enrich(self, *args, **kwargs):
                return {"bsc": [first_launch, second_launch]}, []

        class FakeRepo:
            def __init__(self):
                self.appended = []
                self.cleanup_arg = None

            def upsert_launch(self, data):
                if data["pair_address"] == "0xnew":
                    return (101, True)
                return (102, False)

            def append_snapshot(self, launch_id, data):
                self.appended.append((launch_id, data))
                return True

            def cleanup_old_snapshots(self, retention_days=7):
                self.cleanup_arg = retention_days
                return 0

        repo = FakeRepo()
        service = CryptoLaunchService(config=config, fetcher=FakeFetcher(), repo=repo)

        result = service.scan_once()

        self.assertEqual(result["new"], 1)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["failed_chains"], [])
        self.assertEqual(len(repo.appended), 2)
        self.assertEqual(repo.cleanup_arg, 7)


if __name__ == "__main__":
    unittest.main()
