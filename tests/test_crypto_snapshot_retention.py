# -*- coding: utf-8 -*-
"""Tests for crypto snapshot dedup and retention cleanup."""

import unittest
from datetime import datetime, timedelta


class CryptoSnapshotDedupTestCase(unittest.TestCase):
    """Test snapshot minute-level deduplication."""

    def setUp(self) -> None:
        from src.repositories.crypto_launch_repo import CryptoLaunchRepository
        from src.storage import DatabaseManager

        DatabaseManager.reset_instance()
        self.db = DatabaseManager("sqlite:///:memory:")
        self.repo = CryptoLaunchRepository(self.db)
        result = self.repo.upsert_launch(
            {
                "chain_id": "bsc",
                "pair_address": "0xdedup_test",
                "base_token_symbol": "DDP",
                "base_token_name": "Dedup Token",
                "base_token_address": "0xddp_addr",
            }
        )
        self.assertIsNotNone(result)
        self.launch_id = result[0]

    def tearDown(self) -> None:
        from src.storage import DatabaseManager

        DatabaseManager.reset_instance()

    def test_append_snapshot_deduplicates_within_same_minute(self) -> None:
        data = {"liquidity_usd": 1000.0, "volume_usd_24h": 500.0}

        ok1 = self.repo.append_snapshot(self.launch_id, data)
        ok2 = self.repo.append_snapshot(self.launch_id, data)

        self.assertTrue(ok1)
        self.assertTrue(ok2)

        from src.storage import CryptoLaunchSnapshot

        with self.db.get_session() as session:
            count = session.query(CryptoLaunchSnapshot).filter_by(
                launch_id=self.launch_id
            ).count()

        self.assertEqual(count, 1)


class CryptoSnapshotRetentionTestCase(unittest.TestCase):
    """Test old snapshot cleanup."""

    def setUp(self) -> None:
        from src.repositories.crypto_launch_repo import CryptoLaunchRepository
        from src.storage import DatabaseManager

        DatabaseManager.reset_instance()
        self.db = DatabaseManager("sqlite:///:memory:")
        self.repo = CryptoLaunchRepository(self.db)
        result = self.repo.upsert_launch(
            {
                "chain_id": "bsc",
                "pair_address": "0xretention_test",
                "base_token_symbol": "RET",
                "base_token_name": "Retention Token",
                "base_token_address": "0xret_addr",
            }
        )
        self.assertIsNotNone(result)
        self.launch_id = result[0]

    def tearDown(self) -> None:
        from src.storage import DatabaseManager

        DatabaseManager.reset_instance()

    def test_cleanup_deletes_old_snapshots(self) -> None:
        from src.storage import CryptoLaunchSnapshot

        old_time = datetime.now() - timedelta(days=10)
        with self.db.get_session() as session:
            old_snap = CryptoLaunchSnapshot(
                launch_id=self.launch_id,
                snapshot_at=old_time,
                liquidity_usd=100.0,
            )
            session.add(old_snap)

        self.repo.append_snapshot(self.launch_id, {"liquidity_usd": 200.0})

        deleted = self.repo.cleanup_old_snapshots(retention_days=7)
        self.assertEqual(deleted, 1)

        with self.db.get_session() as session:
            remaining = session.query(CryptoLaunchSnapshot).filter_by(
                launch_id=self.launch_id
            ).count()

        self.assertEqual(remaining, 1)


if __name__ == "__main__":
    unittest.main()
