"""Tests for CryptoSecurityService scoring and persistence."""
import json
import os
import sys
import unittest
from datetime import datetime, timedelta
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if "pandas" not in sys.modules:
    sys.modules["pandas"] = ModuleType("pandas")

from src.storage import CryptoLaunchSecurityScan, DatabaseManager


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "crypto")


def load_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


class CryptoSecurityServiceTestCase(unittest.TestCase):
    def setUp(self):
        from src.services.crypto_security_service import CryptoSecurityService

        DatabaseManager.reset_instance()
        self.db = DatabaseManager("sqlite:///:memory:")
        self.config = SimpleNamespace(
            crypto_risk_cache_ttl_sec=300,
            crypto_security_provider="auto",
            crypto_discovery_timeout_sec=5,
        )
        self.service = CryptoSecurityService(config=self.config, db_manager=self.db)

    def tearDown(self):
        DatabaseManager.reset_instance()

    def test_compute_risk_score_goplus_safe_token(self):
        raw_data = {
            "is_honeypot": False,
            "is_mintable": False,
            "buy_tax": 0.03,
            "sell_tax": 0.05,
            "is_open_source": True,
            "top10_holder_rate": 60.0,
            "lp_locked_pct": 80.0,
        }

        result = self.service.compute_risk_score("goplus", raw_data)

        self.assertLess(result["risk_score"], 25)
        self.assertEqual(result["risk_level"], "low")
        self.assertFalse(result["is_honeypot"])
        self.assertFalse(result["is_mintable"])
        self.assertEqual(result["auto_fail_reasons"], [])

    def test_compute_risk_score_goplus_honeypot_auto_fail(self):
        raw_data = {
            "is_honeypot": True,
            "is_mintable": False,
            "buy_tax": 0.01,
            "sell_tax": 0.01,
            "is_open_source": True,
            "top10_holder_rate": 10.0,
            "lp_locked_pct": 90.0,
        }

        result = self.service.compute_risk_score("goplus", raw_data)

        self.assertEqual(result["risk_score"], 100.0)
        self.assertEqual(result["risk_level"], "critical")
        self.assertIn("honeypot", result["auto_fail_reasons"][0].lower())

    def test_compute_risk_score_goplus_high_tax_auto_fail(self):
        raw_data = {
            "is_honeypot": False,
            "is_mintable": False,
            "buy_tax": 0.10,
            "sell_tax": 0.60,
            "is_open_source": True,
            "top10_holder_rate": 10.0,
            "lp_locked_pct": 90.0,
        }

        result = self.service.compute_risk_score("goplus", raw_data)

        self.assertEqual(result["risk_score"], 100.0)
        self.assertEqual(result["risk_level"], "critical")
        self.assertTrue(any("tax" in reason.lower() for reason in result["auto_fail_reasons"]))

    def test_compute_risk_score_goplus_moderate_risk(self):
        raw_data = {
            "is_honeypot": False,
            "is_mintable": True,
            "buy_tax": 0.20,
            "sell_tax": 0.20,
            "is_open_source": True,
            "top10_holder_rate": 55.0,
            "lp_locked_pct": 45.0,
        }

        result = self.service.compute_risk_score("goplus", raw_data)

        self.assertGreater(result["risk_score"], 26)
        self.assertLessEqual(result["risk_score"], 50)
        self.assertEqual(result["risk_level"], "medium")
        self.assertTrue(result["is_mintable"])

    def test_compute_risk_score_rugcheck(self):
        raw_data = load_fixture("rugcheck_summary_response.json")

        result = self.service.compute_risk_score("rugcheck", raw_data)

        self.assertEqual(result["risk_score"], 65.0)
        self.assertEqual(result["risk_level"], "high")
        self.assertEqual(result["top10_holder_rate_pct"], 25.7)

    def test_scan_token_goplus_chain_detection(self):
        fake_payload = {
            "is_honeypot": False,
            "is_mintable": False,
            "buy_tax": 0.02,
            "sell_tax": 0.02,
            "is_open_source": True,
            "top10_holder_rate": 30.0,
            "lp_locked_pct": 70.0,
        }

        with patch.object(self.service, "fetch_goplus", return_value=fake_payload) as mock_goplus, patch.object(
            self.service, "fetch_rugcheck", return_value=None
        ) as mock_rugcheck:
            result = self.service.scan_token(launch_id=1, token_address="0xabc", chain_id="bsc")

        self.assertIsNotNone(result)
        self.assertEqual(result["provider"], "goplus")
        mock_goplus.assert_called_once_with("0xabc", "bsc")
        mock_rugcheck.assert_not_called()

    def test_scan_token_rugcheck_chain_detection(self):
        fake_payload = load_fixture("rugcheck_summary_response.json")

        with patch.object(self.service, "fetch_goplus", return_value=None) as mock_goplus, patch.object(
            self.service, "fetch_rugcheck", return_value=fake_payload
        ) as mock_rugcheck:
            result = self.service.scan_token(launch_id=2, token_address="SoMint111", chain_id="solana")

        self.assertIsNotNone(result)
        self.assertEqual(result["provider"], "rugcheck")
        mock_rugcheck.assert_called_once_with("SoMint111")
        mock_goplus.assert_not_called()

    def test_scan_token_cache_hit_skips_fetch(self):
        with self.db.get_session() as session:
            session.add(
                CryptoLaunchSecurityScan(
                    launch_id=3,
                    provider="goplus",
                    risk_score=12.0,
                    risk_level="low",
                    is_honeypot=False,
                    is_mintable=False,
                    buy_tax_pct=3.0,
                    sell_tax_pct=5.0,
                    lp_locked_pct=80.0,
                    top10_holder_rate_pct=60.0,
                    raw_payload_json=json.dumps({"cached": True}),
                    scanned_at=datetime.now() - timedelta(seconds=30),
                )
            )
            session.commit()

        with patch.object(self.service, "fetch_goplus") as mock_goplus:
            result = self.service.scan_token(launch_id=3, token_address="0xcache", chain_id="bsc")

        self.assertEqual(result["risk_score"], 12.0)
        self.assertEqual(result["risk_level"], "low")
        self.assertEqual(result["provider"], "goplus")
        mock_goplus.assert_not_called()

    def test_scan_token_persists_to_database(self):
        fake_payload = {
            "is_honeypot": False,
            "is_mintable": True,
            "buy_tax": 0.20,
            "sell_tax": 0.20,
            "is_open_source": True,
            "top10_holder_rate": 55.0,
            "lp_locked_pct": 45.0,
        }

        with patch.object(self.service, "fetch_goplus", return_value=fake_payload):
            result = self.service.scan_token(launch_id=4, token_address="0xpersist", chain_id="bsc")

        self.assertIsNotNone(result)
        with self.db.get_session() as session:
            rows = session.query(CryptoLaunchSecurityScan).filter_by(launch_id=4).all()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].provider, "goplus")
        self.assertEqual(rows[0].risk_level, "medium")
        self.assertIsInstance(json.loads(rows[0].raw_payload_json), dict)


class CryptoSecurityFetchTestCase(unittest.TestCase):
    def setUp(self):
        from src.services.crypto_security_service import CryptoSecurityService

        self.config = SimpleNamespace(
            crypto_risk_cache_ttl_sec=300,
            crypto_security_provider="auto",
            crypto_discovery_timeout_sec=5,
        )
        self.db = MagicMock()
        self.service = CryptoSecurityService(config=self.config, db_manager=self.db)

    @patch("requests.get")
    def test_fetch_goplus_normalizes_payload(self, mock_get):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = load_fixture("goplus_evm_response.json")
        mock_get.return_value = response

        result = self.service.fetch_goplus("0xabcdef1234567890abcdef1234567890abcdef12", "bsc")

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["buy_tax"], 0.03)
        self.assertAlmostEqual(result["sell_tax"], 0.05)
        self.assertEqual(result["top10_holder_rate"], 60.0)
        self.assertEqual(result["lp_locked_pct"], 50.0)

    @patch("requests.get")
    def test_fetch_rugcheck_normalizes_payload(self, mock_get):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = load_fixture("rugcheck_summary_response.json")
        mock_get.return_value = response

        result = self.service.fetch_rugcheck("TestMint123abc")

        self.assertIsNotNone(result)
        self.assertIn("risks", result)
        self.assertEqual(result["tokenMeta"]["symbol"], "TEST")


if __name__ == "__main__":
    unittest.main()
