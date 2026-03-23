# -*- coding: utf-8 -*-
"""Tests for crypto scan observability: structured logging, per-chain timing, gap detection, caching."""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import logging
import time
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.storage import DatabaseManager, CryptoScanMetric


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides):
    """Create a minimal config namespace for CryptoLaunchService."""
    defaults = {
        "crypto_enabled": True,
        "crypto_chains": ["bsc", "solana"],
        "crypto_refresh_interval_sec": 60,
        "crypto_discovery_timeout_sec": 5,
        "crypto_enrichment_timeout_sec": 5,
        "crypto_max_retries": 0,
        "crypto_initial_backoff_sec": 1,
        "crypto_backoff_multiplier": 2.0,
        "crypto_discovery_cache_sec": 60,
        "crypto_enrichment_cache_sec": 30,
        "crypto_snapshot_retention_days": 7,
        "crypto_risk_enabled": False,
        "crypto_risk_min_liquidity_usd": 1000.0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_launch(chain_id="bsc", pair_address="0xpair"):
    """Build a minimal NormalizedLaunch-like object."""
    return SimpleNamespace(
        chain_id=chain_id,
        dex_id="pancakeswap",
        pair_address=pair_address,
        pair_url=f"https://dex.example/{pair_address}",
        pair_created_at=datetime.now() - timedelta(hours=1),
        base_token_address="0xtoken",
        base_token_symbol="TEST",
        base_token_name="Test Token",
        quote_token_address="0xquote",
        quote_token_symbol="USDT",
        quote_token_name="Tether",
        liquidity_usd=50000.0,
        volume_usd_24h=120000.0,
        buys_24h=80,
        sells_24h=20,
        price_usd=0.01,
        price_change_pct_24h=5.0,
        fdv_usd=1000000.0,
        market_cap_usd=800000.0,
        dexscreener_url="https://dexscreener.com/bsc/0xpair",
        website_url="https://test.example",
        socials_json="{}",
        labels_json="[]",
        raw_payload="{}",
        data_complete=True,
    )


# ---------------------------------------------------------------------------
# Task 4: Structured scan logging + per-chain timing
# ---------------------------------------------------------------------------

@pytest.mark.not_network
class ScanLoggingTestCase(unittest.TestCase):
    """Verify scan_once() emits structured log events and persists CryptoScanMetric."""

    def setUp(self):
        DatabaseManager.reset_instance()
        self.db = DatabaseManager("sqlite:///:memory:")
        self.config = _make_config()
        self.fetcher = MagicMock()
        self.repo = MagicMock()
        self.repo.db = self.db

        # Default: fetcher validates chains, returns one launch per chain
        self.fetcher.validate_enabled_chains = MagicMock(side_effect=lambda c: c)
        bsc_launch = _make_launch("bsc", "0xbsc-pair")
        sol_launch = _make_launch("solana", "0xsol-pair")
        self.fetcher.discover_and_enrich.return_value = (
            {"bsc": [bsc_launch], "solana": [sol_launch]},
            [],
        )
        # Set per-chain timings on fetcher
        self.fetcher.last_chain_timings = {
            "bsc": {"duration_ms": 150, "pools_discovered": 1, "status": "ok"},
            "solana": {"duration_ms": 200, "pools_discovered": 1, "status": "ok"},
        }

        self.repo.upsert_launch.return_value = (1, True)
        self.repo.append_snapshot.return_value = None
        self.repo.cleanup_old_snapshots.return_value = 0

        from src.services.crypto_launch_service import CryptoLaunchService
        self.service = CryptoLaunchService(
            config=self.config, fetcher=self.fetcher, repo=self.repo,
        )

    def tearDown(self):
        DatabaseManager.reset_instance()

    def test_scan_once_emits_crypto_scan_complete_log(self):
        """scan_once() should emit a JSON-structured crypto_scan_complete log event."""
        with self.assertLogs("src.services.crypto_launch_service", level="INFO") as cm:
            self.service.scan_once()

        # Find the structured log line
        scan_log = None
        for line in cm.output:
            if "crypto_scan_complete" in line:
                # Extract JSON from log line
                json_start = line.index("{")
                scan_log = json.loads(line[json_start:])
                break

        self.assertIsNotNone(scan_log, "No crypto_scan_complete log event found")
        self.assertEqual(scan_log["event"], "crypto_scan_complete")
        self.assertIn("scan_id", scan_log)
        self.assertIn("duration_ms", scan_log)
        self.assertIn("per_chain", scan_log)
        self.assertIn("launches_new", scan_log)
        self.assertIn("launches_updated", scan_log)
        self.assertIn("started_at", scan_log)
        self.assertIn("finished_at", scan_log)
        self.assertIsInstance(scan_log["per_chain"], dict)

    def test_scan_once_log_event_has_correct_counts(self):
        """Log event counts should reflect actual scan results."""
        # 2 new launches across 2 chains
        self.repo.upsert_launch.return_value = (1, True)

        with self.assertLogs("src.services.crypto_launch_service", level="INFO") as cm:
            result = self.service.scan_once()

        scan_log = None
        for line in cm.output:
            if "crypto_scan_complete" in line:
                json_start = line.index("{")
                scan_log = json.loads(line[json_start:])
                break

        self.assertIsNotNone(scan_log)
        self.assertEqual(scan_log["launches_new"], result["new"])
        self.assertEqual(scan_log["launches_updated"], result["updated"])
        self.assertEqual(scan_log["chains_total"], 2)

    def test_scan_once_persists_crypto_scan_metric(self):
        """scan_once() should persist a CryptoScanMetric row to the database."""
        self.service.scan_once()

        metrics = self.db.get_scan_metrics(limit=10)
        self.assertEqual(len(metrics), 1)

        m = metrics[0]
        self.assertIsNotNone(m["scan_id"])
        self.assertGreaterEqual(m["duration_ms"], 0)
        self.assertEqual(m["chains_total"], 2)
        self.assertEqual(m["chains_failed"], 0)
        self.assertTrue(m["success"])

    def test_scan_once_metric_includes_per_chain_timing(self):
        """Persisted metric should include per-chain timing JSON."""
        self.service.scan_once()

        metrics = self.db.get_scan_metrics(limit=10)
        self.assertEqual(len(metrics), 1)

        per_chain = json.loads(metrics[0]["per_chain_json"])
        self.assertIn("bsc", per_chain)
        self.assertIn("solana", per_chain)
        self.assertEqual(per_chain["bsc"]["duration_ms"], 150)

    def test_scan_once_metric_records_failure(self):
        """When scan_once() fails, metric should have success=False."""
        self.fetcher.discover_and_enrich.side_effect = RuntimeError("network down")

        self.service.scan_once()

        metrics = self.db.get_scan_metrics(limit=10)
        self.assertEqual(len(metrics), 1)
        self.assertFalse(metrics[0]["success"])


# ---------------------------------------------------------------------------
# Task 5: Gap detection + discovery cache
# ---------------------------------------------------------------------------

@pytest.mark.not_network
class GapDetectionTestCase(unittest.TestCase):
    """Verify gap detection and discovery caching on CryptoLaunchService."""

    def setUp(self):
        DatabaseManager.reset_instance()
        self.db = DatabaseManager("sqlite:///:memory:")
        self.config = _make_config(crypto_refresh_interval_sec=60)
        self.fetcher = MagicMock()
        self.repo = MagicMock()
        self.repo.db = self.db

        self.fetcher.validate_enabled_chains = MagicMock(side_effect=lambda c: c)
        bsc_launch = _make_launch("bsc", "0xbsc-pair")
        self.fetcher.discover_and_enrich.return_value = ({"bsc": [bsc_launch]}, [])
        self.fetcher.last_chain_timings = {
            "bsc": {"duration_ms": 100, "pools_discovered": 1, "status": "ok"},
        }
        self.repo.upsert_launch.return_value = (1, True)
        self.repo.append_snapshot.return_value = None
        self.repo.cleanup_old_snapshots.return_value = 0

    def tearDown(self):
        DatabaseManager.reset_instance()

    def _create_service(self, **config_overrides):
        cfg = _make_config(**config_overrides)
        from src.services.crypto_launch_service import CryptoLaunchService
        return CryptoLaunchService(config=cfg, fetcher=self.fetcher, repo=self.repo)

    def test_gap_detected_when_last_scan_is_stale(self):
        """Gap should be detected when last scan metric is older than 2x interval."""
        # Insert a stale metric (5 minutes ago, interval=60s, threshold=120s)
        stale_time = datetime.now() - timedelta(minutes=5)
        self.db.save_scan_metric(
            scan_id="old00001",
            started_at=stale_time - timedelta(seconds=2),
            finished_at=stale_time,
            duration_ms=2000,
            chains_total=1,
            chains_failed=0,
            launches_new=0,
            launches_updated=0,
            success=True,
        )

        service = self._create_service(crypto_refresh_interval_sec=60)

        self.assertTrue(service._gap_detected)
        self.assertGreater(service._gap_duration_sec, 0)

    def test_no_gap_when_last_scan_is_recent(self):
        """No gap when last scan metric is within 2x interval."""
        recent_time = datetime.now() - timedelta(seconds=30)
        self.db.save_scan_metric(
            scan_id="new00001",
            started_at=recent_time - timedelta(seconds=1),
            finished_at=recent_time,
            duration_ms=1000,
            chains_total=1,
            chains_failed=0,
            launches_new=0,
            launches_updated=0,
            success=True,
        )

        service = self._create_service(crypto_refresh_interval_sec=60)

        self.assertFalse(service._gap_detected)

    def test_no_gap_when_no_previous_scans(self):
        """First-ever scan should not flag as gap (nothing to compare against)."""
        service = self._create_service(crypto_refresh_interval_sec=60)

        self.assertFalse(service._gap_detected)

    def test_gap_detected_cleared_after_scan(self):
        """After successful scan_once(), gap should be cleared."""
        stale_time = datetime.now() - timedelta(minutes=5)
        self.db.save_scan_metric(
            scan_id="old00002",
            started_at=stale_time - timedelta(seconds=2),
            finished_at=stale_time,
            duration_ms=2000,
            chains_total=1,
            chains_failed=0,
            launches_new=0,
            launches_updated=0,
            success=True,
        )

        service = self._create_service(crypto_refresh_interval_sec=60)
        self.assertTrue(service._gap_detected)

        service.scan_once()

        self.assertFalse(service._gap_detected)

    def test_discovery_cache_skips_second_fetch_within_ttl(self):
        """Two scan_once() calls within discovery_cache_sec should reuse cached results."""
        service = self._create_service(
            crypto_discovery_cache_sec=60,
            crypto_chains=["bsc"],
        )

        service.scan_once()
        service.scan_once()

        # discover_and_enrich should only be called once
        self.assertEqual(self.fetcher.discover_and_enrich.call_count, 1)

    def test_discovery_cache_expires_after_ttl(self):
        """Cache should expire after discovery_cache_sec."""
        service = self._create_service(
            crypto_discovery_cache_sec=1,
            crypto_chains=["bsc"],
        )

        service.scan_once()
        time.sleep(1.1)
        service.scan_once()


        # Both calls should fetch
        self.assertEqual(self.fetcher.discover_and_enrich.call_count, 2)


# ---------------------------------------------------------------------------
# Task 6: Extended get_status() with observability
# ---------------------------------------------------------------------------

@pytest.mark.not_network
class StatusObservabilityTestCase(unittest.TestCase):
    """Verify get_status() exposes gap, per-chain timing, and recent scans."""

    def setUp(self):
        DatabaseManager.reset_instance()
        self.db = DatabaseManager("sqlite:///:memory:")
        self.config = _make_config()
        self.fetcher = MagicMock()
        self.repo = MagicMock()
        self.repo.db = self.db

        self.fetcher.validate_enabled_chains = MagicMock(side_effect=lambda c: c)
        bsc_launch = _make_launch("bsc", "0xbsc-pair")
        self.fetcher.discover_and_enrich.return_value = ({"bsc": [bsc_launch]}, [])
        self.fetcher.last_chain_timings = {
            "bsc": {"duration_ms": 100, "pools_discovered": 1, "status": "ok"},
        }
        self.repo.upsert_launch.return_value = (1, True)
        self.repo.append_snapshot.return_value = None
        self.repo.cleanup_old_snapshots.return_value = 0

    def tearDown(self):
        DatabaseManager.reset_instance()

    def _create_service(self, **config_overrides):
        cfg = _make_config(**config_overrides)
        from src.services.crypto_launch_service import CryptoLaunchService
        return CryptoLaunchService(config=cfg, fetcher=self.fetcher, repo=self.repo)

    def test_status_includes_gap_fields(self):
        """get_status() should include gap_detected and gap_duration_sec."""
        stale_time = datetime.now() - timedelta(minutes=5)
        self.db.save_scan_metric(
            scan_id="stale001",
            started_at=stale_time - timedelta(seconds=2),
            finished_at=stale_time,
            duration_ms=2000,
            chains_total=1,
            chains_failed=0,
            launches_new=0,
            launches_updated=0,
            success=True,
        )

        service = self._create_service(crypto_refresh_interval_sec=60)
        status = service.get_status()

        self.assertIn("gap_detected", status)
        self.assertTrue(status["gap_detected"])
        self.assertGreater(status["gap_duration_sec"], 0)

    def test_status_includes_per_chain_timing(self):
        """get_status() should include per_chain_timing from fetcher."""
        service = self._create_service(crypto_chains=["bsc"])
        service.scan_once()
        status = service.get_status()

        self.assertIn("per_chain_timing", status)
        self.assertIn("bsc", status["per_chain_timing"])
        self.assertEqual(status["per_chain_timing"]["bsc"]["duration_ms"], 100)

    def test_status_includes_recent_scans(self):
        """get_status() should return recent_scans from metric history."""
        service = self._create_service(crypto_chains=["bsc"])
        service.scan_once()
        status = service.get_status()

        self.assertIn("recent_scans", status)
        self.assertGreaterEqual(len(status["recent_scans"]), 1)
        self.assertIn("scan_id", status["recent_scans"][0])

    def test_status_gap_false_when_no_gap(self):
        """get_status() gap_detected should be False when no gap exists."""
        service = self._create_service(crypto_refresh_interval_sec=60)
        status = service.get_status()

        self.assertFalse(status["gap_detected"])
        self.assertEqual(status["gap_duration_sec"], 0)


if __name__ == "__main__":
    unittest.main()
