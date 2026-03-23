# -*- coding: utf-8 -*-
"""Tests for Task 9: Ops alerts and scheduler circuit breaker."""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.storage import DatabaseManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides):
    defaults = {
        "crypto_enabled": True,
        "crypto_chains": ["bsc"],
        "crypto_refresh_interval_sec": 60,
        "crypto_discovery_timeout_sec": 5,
        "crypto_enrichment_timeout_sec": 5,
        "crypto_max_retries": 0,
        "crypto_initial_backoff_sec": 1,
        "crypto_backoff_multiplier": 2.0,
        "crypto_discovery_cache_sec": 0,  # disable cache so each scan fetches
        "crypto_enrichment_cache_sec": 30,
        "crypto_snapshot_retention_days": 7,
        "crypto_risk_enabled": False,
        "crypto_risk_min_liquidity_usd": 1000.0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_launch(chain_id="bsc", pair_address="0xpair"):
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


def _build_service(**config_overrides):
    """Build a CryptoLaunchService with mocked fetcher/repo."""
    from src.services.crypto_launch_service import CryptoLaunchService

    DatabaseManager.reset_instance()
    db = DatabaseManager("sqlite:///:memory:")
    config = _make_config(**config_overrides)
    fetcher = MagicMock()
    repo = MagicMock()
    repo.db = db

    fetcher.validate_enabled_chains = MagicMock(side_effect=lambda c: c)
    fetcher.last_chain_timings = {"bsc": {"duration_ms": 100, "status": "ok"}}

    service = CryptoLaunchService(config=config, fetcher=fetcher, repo=repo)
    return service, fetcher, repo, db


# ---------------------------------------------------------------------------
# Consecutive failure escalation
# ---------------------------------------------------------------------------

@pytest.mark.not_network
class ConsecutiveFailureAlertTestCase(unittest.TestCase):
    """3 consecutive scan_once() failures → ticket_alert warning."""

    def setUp(self):
        self.service, self.fetcher, self.repo, self.db = _build_service()
        # Make fetcher always raise
        self.fetcher.discover_and_enrich.side_effect = RuntimeError("network down")

    def tearDown(self):
        DatabaseManager.reset_instance()

    def test_ticket_alert_after_3_consecutive_failures(self):
        """After 3 consecutive failures, a ticket_alert warning should be logged."""
        with self.assertLogs("src.services.crypto_launch_service", level="WARNING") as cm:
            for _ in range(3):
                self.service.scan_once()

        ticket_alerts = [l for l in cm.output if "ticket_alert" in l]
        self.assertTrue(len(ticket_alerts) >= 1, "Expected ticket_alert warning after 3 failures")

    def test_no_ticket_alert_before_3_failures(self):
        """Before 3 consecutive failures, no ticket_alert should be logged."""
        logger = logging.getLogger("src.services.crypto_launch_service")
        with self.assertLogs(logger, level="DEBUG") as cm:
            for _ in range(2):
                self.service.scan_once()

        ticket_alerts = [l for l in cm.output if "ticket_alert" in l]
        self.assertEqual(len(ticket_alerts), 0, "No ticket_alert expected before 3 failures")

    def test_success_resets_consecutive_failures(self):
        """A successful scan should reset the failure counter."""
        # 2 failures
        for _ in range(2):
            self.service.scan_once()

        # 1 success
        self.fetcher.discover_and_enrich.side_effect = None
        bsc_launch = _make_launch()
        self.fetcher.discover_and_enrich.return_value = ({"bsc": [bsc_launch]}, [])
        self.repo.upsert_launch.return_value = (1, True)
        self.repo.append_snapshot.return_value = None
        self.repo.cleanup_old_snapshots.return_value = 0
        self.service.scan_once()

        self.assertEqual(self.service._consecutive_failures, 0)

        # 2 more failures — should not trigger ticket_alert (counter was reset)
        self.fetcher.discover_and_enrich.side_effect = RuntimeError("network down")
        with self.assertLogs("src.services.crypto_launch_service", level="DEBUG") as cm:
            for _ in range(2):
                self.service.scan_once()

        ticket_alerts = [l for l in cm.output if "ticket_alert" in l]
        self.assertEqual(len(ticket_alerts), 0)


# ---------------------------------------------------------------------------
# Page alert: no success in 3 × refresh_interval_sec
# ---------------------------------------------------------------------------

@pytest.mark.not_network
class PageAlertStalenessTestCase(unittest.TestCase):
    """No successful scan in 3 × refresh_interval_sec → page_alert critical."""

    def setUp(self):
        self.service, self.fetcher, self.repo, self.db = _build_service(
            crypto_refresh_interval_sec=60,
        )
        self.fetcher.discover_and_enrich.side_effect = RuntimeError("network down")

    def tearDown(self):
        DatabaseManager.reset_instance()

    def test_page_alert_when_no_success_beyond_threshold(self):
        """page_alert critical should fire when last success is older than 3x interval."""
        # Simulate that last success was long ago
        self.service._last_success_at = datetime.now() - timedelta(seconds=200)

        with self.assertLogs("src.services.crypto_launch_service", level="CRITICAL") as cm:
            self.service.scan_once()

        page_alerts = [l for l in cm.output if "page_alert" in l]
        self.assertTrue(len(page_alerts) >= 1, "Expected page_alert critical after staleness threshold")

    def test_no_page_alert_when_recent_success(self):
        """No page_alert when last success is within 3x interval."""
        self.service._last_success_at = datetime.now() - timedelta(seconds=30)

        with self.assertLogs("src.services.crypto_launch_service", level="DEBUG") as cm:
            self.service.scan_once()

        page_alerts = [l for l in cm.output if "page_alert" in l]
        self.assertEqual(len(page_alerts), 0)


# ---------------------------------------------------------------------------
# Circuit breaker: 5 consecutive failures
# ---------------------------------------------------------------------------

@pytest.mark.not_network
class CircuitBreakerTestCase(unittest.TestCase):
    """5 consecutive scan_once() failures → circuit opens, scheduler pauses."""

    def setUp(self):
        self.service, self.fetcher, self.repo, self.db = _build_service()
        self.fetcher.discover_and_enrich.side_effect = RuntimeError("network down")

    def tearDown(self):
        DatabaseManager.reset_instance()

    def test_circuit_opens_after_5_failures(self):
        """Circuit should open after 5 consecutive scan_once() failures."""
        for _ in range(5):
            self.service.scan_once()

        self.assertTrue(self.service._circuit_open)
        self.assertIsNotNone(self.service._circuit_open_since)

    def test_circuit_open_emits_critical_log(self):
        """Circuit opening should emit a critical log."""
        with self.assertLogs("src.services.crypto_launch_service", level="CRITICAL") as cm:
            for _ in range(5):
                self.service.scan_once()

        circuit_logs = [l for l in cm.output if "circuit" in l.lower() or "paused" in l.lower()]
        self.assertTrue(len(circuit_logs) >= 1, "Expected critical log when circuit opens")

    def test_scan_skipped_when_circuit_open(self):
        """scan_once() should skip and return early when circuit is open."""
        # Open the circuit
        for _ in range(5):
            self.service.scan_once()

        self.assertTrue(self.service._circuit_open)

        # Reset call counts to check no new fetcher calls
        self.fetcher.discover_and_enrich.reset_mock()

        result = self.service.scan_once()

        self.fetcher.discover_and_enrich.assert_not_called()
        self.assertEqual(result["new"], 0)
        self.assertEqual(result["updated"], 0)
        self.assertTrue(result.get("circuit_open", False))

    def test_circuit_not_open_before_5_failures(self):
        """Circuit should not open before 5 consecutive failures."""
        for _ in range(4):
            self.service.scan_once()

        self.assertFalse(self.service._circuit_open)


# ---------------------------------------------------------------------------
# Resume scanner
# ---------------------------------------------------------------------------

@pytest.mark.not_network
class ResumeScannerTestCase(unittest.TestCase):
    """resume_scanner() should clear circuit state."""

    def setUp(self):
        self.service, self.fetcher, self.repo, self.db = _build_service()
        self.fetcher.discover_and_enrich.side_effect = RuntimeError("network down")

    def tearDown(self):
        DatabaseManager.reset_instance()

    def test_resume_clears_circuit_state(self):
        """resume_scanner() should reset circuit_open, counter, and timestamp."""
        # Trip the circuit
        for _ in range(5):
            self.service.scan_once()

        self.assertTrue(self.service._circuit_open)

        self.service.resume_scanner()

        self.assertFalse(self.service._circuit_open)
        self.assertIsNone(self.service._circuit_open_since)
        self.assertEqual(self.service._consecutive_failures, 0)

    def test_scan_works_after_resume(self):
        """After resume, scan_once() should attempt fetching again."""
        # Trip the circuit
        for _ in range(5):
            self.service.scan_once()

        self.service.resume_scanner()

        # Make next scan succeed
        self.fetcher.discover_and_enrich.side_effect = None
        bsc_launch = _make_launch()
        self.fetcher.discover_and_enrich.return_value = ({"bsc": [bsc_launch]}, [])
        self.repo.upsert_launch.return_value = (1, True)
        self.repo.append_snapshot.return_value = None
        self.repo.cleanup_old_snapshots.return_value = 0

        result = self.service.scan_once()
        self.assertEqual(result["new"], 1)
        self.assertFalse(self.service._circuit_open)


# ---------------------------------------------------------------------------
# Status exposure
# ---------------------------------------------------------------------------

@pytest.mark.not_network
class CircuitStatusTestCase(unittest.TestCase):
    """get_status() should expose circuit breaker state."""

    def setUp(self):
        self.service, self.fetcher, self.repo, self.db = _build_service()

    def tearDown(self):
        DatabaseManager.reset_instance()

    def test_status_includes_circuit_fields(self):
        """get_status() should include circuit_open and consecutive_failures."""
        status = self.service.get_status()

        self.assertIn("circuit_open", status)
        self.assertIn("consecutive_failures", status)
        self.assertIn("circuit_open_since", status)
        self.assertFalse(status["circuit_open"])
        self.assertEqual(status["consecutive_failures"], 0)
        self.assertIsNone(status["circuit_open_since"])

    def test_status_reflects_open_circuit(self):
        """get_status() should reflect open circuit after failures."""
        self.fetcher.discover_and_enrich.side_effect = RuntimeError("boom")

        for _ in range(5):
            self.service.scan_once()

        status = self.service.get_status()
        self.assertTrue(status["circuit_open"])
        self.assertEqual(status["consecutive_failures"], 5)
        self.assertIsNotNone(status["circuit_open_since"])


if __name__ == "__main__":
    unittest.main()
