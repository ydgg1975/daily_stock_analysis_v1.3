# -*- coding: utf-8 -*-
"""Foundation tests for the Phase 1 crypto scanner backend lane."""

import os
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
