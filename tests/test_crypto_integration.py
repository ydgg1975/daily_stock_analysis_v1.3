# -*- coding: utf-8 -*-
"""Integration tests for Phase 2 crypto roundtrip flows."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

for optional_module in ("litellm", "json_repair"):
    try:
        __import__(optional_module)
    except ModuleNotFoundError:
        sys.modules[optional_module] = MagicMock()

if "pandas" not in sys.modules:
    sys.modules["pandas"] = ModuleType("pandas")

import src.core.config_registry as config_registry
from src.config import Config
from src.core.config_manager import ConfigManager
from src.repositories.crypto_launch_repo import CryptoLaunchRepository
from src.repositories.crypto_watchlist_repo import CryptoWatchlistRepository
from src.services.crypto_alert_service import CryptoAlertService
from src.services.crypto_security_service import CryptoSecurityService
from src.services.system_config_service import SystemConfigService
from src.storage import CryptoLaunchSecurityScan, DatabaseManager


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "crypto"
VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def make_launch_payload(suffix: str, **overrides) -> dict:
    payload = {
        "chain_id": "bsc",
        "pair_address": f"0xpair{suffix}",
        "base_token_address": f"0xtoken{suffix}",
        "base_token_symbol": f"TK{suffix[-4:].upper()}",
        "base_token_name": f"Token {suffix}",
        "quote_token_address": "0xquote",
        "quote_token_symbol": "USDT",
        "quote_token_name": "Tether",
        "liquidity_usd": 25000.0,
        "volume_usd_24h": 120000.0,
        "buys_24h": 40,
        "sells_24h": 20,
        "price_usd": 0.125,
        "price_change_pct_24h": 15.5,
        "fdv_usd": 1500000.0,
        "market_cap_usd": 950000.0,
        "data_complete": True,
        "raw_payload": json.dumps({"source": "integration-test", "suffix": suffix}, ensure_ascii=True),
    }
    payload.update(overrides)
    return payload


@pytest.mark.not_network
class TestSecurityScanToRiskBadgeRoundtrip:
    def setup_method(self):
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "crypto_integration.sqlite3"
        self.manager = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.repo = CryptoLaunchRepository(db_manager=self.manager)
        self.config = SimpleNamespace(
            crypto_risk_cache_ttl_sec=300,
            crypto_security_provider="auto",
            crypto_discovery_timeout_sec=5,
        )
        self.security_service = CryptoSecurityService(config=self.config, db_manager=self.manager)
        created = self.repo.upsert_launch(make_launch_payload("risk-badge"))
        assert created is not None
        self.launch_id = created[0]

    def teardown_method(self):
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def test_goplus_scan_persists_and_surfaces_in_feed_and_detail(self):
        raw_scan = {
            "provider": "goplus",
            "chain_id": "bsc",
            "token_address": "0xtokenriskbadge",
            "is_honeypot": False,
            "is_mintable": True,
            "buy_tax": 0.08,
            "sell_tax": 0.12,
            "is_open_source": True,
            "top10_holder_rate": 41.0,
            "lp_locked_pct": 72.5,
            "holders": [{"address": "0xaaa", "percent": "41.0"}],
            "raw": {"provider": "fixture"},
        }

        with patch.object(self.security_service, "fetch_goplus", return_value=raw_scan) as mock_fetch:
            result = self.security_service.scan_token(
                launch_id=self.launch_id,
                token_address="0xtokenriskbadge",
                chain_id="bsc",
            )

        assert result is not None
        assert mock_fetch.called
        assert isinstance(result["risk_score"], float)
        assert 0.0 <= result["risk_score"] <= 100.0
        assert result["risk_level"] in VALID_RISK_LEVELS

        with self.manager.get_session() as session:
            rows = session.query(CryptoLaunchSecurityScan).filter_by(launch_id=self.launch_id).all()

        assert len(rows) == 1
        assert rows[0].provider == "goplus"
        assert rows[0].risk_score == pytest.approx(result["risk_score"])
        assert rows[0].risk_level == result["risk_level"]

        feed = self.repo.list_launches(limit=10)
        assert feed["total"] == 1
        assert len(feed["items"]) == 1
        assert feed["items"][0]["id"] == self.launch_id
        assert feed["items"][0]["risk_score"] == pytest.approx(result["risk_score"])
        assert feed["items"][0]["risk_level"] == result["risk_level"]

        detail = self.repo.get_launch_detail(self.launch_id)
        assert detail is not None
        assert detail["id"] == self.launch_id
        assert detail["risk_score"] == pytest.approx(result["risk_score"])
        assert detail["risk_level"] == result["risk_level"]

    def test_rugcheck_compute_and_persist_roundtrip(self):
        launch_result = self.repo.upsert_launch(
            make_launch_payload(
                "solana-risk",
                chain_id="solana",
                pair_address="SoPair111",
                base_token_address="SoMint111",
                base_token_symbol="SOLT",
                base_token_name="Solana Test",
            )
        )
        assert launch_result is not None
        launch_id = launch_result[0]
        raw_scan = load_fixture("rugcheck_summary_response.json")

        computed = self.security_service.compute_risk_score("rugcheck", raw_scan)

        assert isinstance(computed["risk_score"], float)
        assert 0.0 <= computed["risk_score"] <= 100.0
        assert computed["risk_level"] in VALID_RISK_LEVELS

        persisted = self.security_service._persist_scan(launch_id, "rugcheck", raw_scan, computed)

        assert persisted is True
        detail = self.repo.get_launch_detail(launch_id)
        assert detail is not None
        assert detail["risk_score"] == pytest.approx(computed["risk_score"])
        assert detail["risk_level"] == computed["risk_level"]


@pytest.mark.not_network
class TestSettingsSaveToConfigRoundtrip:
    PHASE_2_CRYPTO_FIELDS = {
        "CRYPTO_RISK_ENABLED": "boolean",
        "CRYPTO_RISK_MIN_LIQUIDITY_USD": "number",
        "CRYPTO_RISK_CACHE_TTL_SEC": "integer",
        "CRYPTO_WATCHLIST_ENABLED": "boolean",
        "CRYPTO_ALERTS_ENABLED": "boolean",
        "CRYPTO_ALERT_LIQUIDITY_DROP_PCT": "number",
        "CRYPTO_ALERT_VOLUME_SPIKE_MULTIPLIER": "number",
        "CRYPTO_SNAPSHOT_RETENTION_DAYS": "integer",
        "CRYPTO_SECURITY_PROVIDER": "string",
    }

    def setup_method(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temp_dir.name) / ".env"
        self.env_path.write_text("CRYPTO_RISK_ENABLED=true\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        Config.reset_instance()
        self.manager = ConfigManager(env_path=self.env_path)
        self.service = SystemConfigService(manager=self.manager)

    def teardown_method(self):
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        self.temp_dir.cleanup()

    def test_phase_2_crypto_field_definitions_are_registered_with_expected_types(self):
        field_definitions = getattr(config_registry, "FIELD_DEFINITIONS", None)
        if field_definitions is None:
            field_definitions = getattr(config_registry, "_FIELD_DEFINITIONS")

        for key, expected_type in self.PHASE_2_CRYPTO_FIELDS.items():
            assert key in field_definitions
            field = config_registry.get_field_definition(key)
            assert field["category"] == "crypto"
            assert field["data_type"] == expected_type

    def test_crypto_settings_persist_and_reload_via_system_config_service(self):
        old_version = self.manager.get_config_version()
        updates = [
            {"key": "CRYPTO_RISK_ENABLED", "value": "false"},
            {"key": "CRYPTO_RISK_CACHE_TTL_SEC", "value": "900"},
            {"key": "CRYPTO_SECURITY_PROVIDER", "value": "goplus"},
            {"key": "CRYPTO_ALERTS_ENABLED", "value": "true"},
        ]

        result = self.service.update(
            config_version=old_version,
            items=updates,
            reload_now=False,
        )

        assert result["success"] is True
        assert set(result["updated_keys"]) == {
            "CRYPTO_RISK_ENABLED",
            "CRYPTO_RISK_CACHE_TTL_SEC",
            "CRYPTO_SECURITY_PROVIDER",
            "CRYPTO_ALERTS_ENABLED",
        }

        reloaded_service = SystemConfigService(manager=ConfigManager(env_path=self.env_path))
        payload = reloaded_service.get_config(include_schema=True)
        config_map = {item["key"]: item for item in payload["items"]}

        assert config_map["CRYPTO_RISK_ENABLED"]["value"] == "false"
        assert config_map["CRYPTO_RISK_CACHE_TTL_SEC"]["value"] == "900"
        assert config_map["CRYPTO_SECURITY_PROVIDER"]["value"] == "goplus"
        assert config_map["CRYPTO_ALERTS_ENABLED"]["value"] == "true"
        assert config_map["CRYPTO_SECURITY_PROVIDER"]["schema"]["category"] == "crypto"
        assert config_map["CRYPTO_SECURITY_PROVIDER"]["schema"]["data_type"] == "string"


@pytest.mark.not_network
class TestWatchlistToAlertRoundtrip:
    def setup_method(self):
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "crypto_alerts.sqlite3"
        self.manager = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.launch_repo = CryptoLaunchRepository(db_manager=self.manager)
        self.watchlist_repo = CryptoWatchlistRepository(db_manager=self.manager)
        self.config = SimpleNamespace(
            crypto_alerts_enabled=True,
            crypto_alert_liquidity_drop_pct=30.0,
            crypto_alert_volume_spike_multiplier=5.0,
        )
        self.service = CryptoAlertService(config=self.config, watchlist_repo=self.watchlist_repo)

        watched = self.launch_repo.upsert_launch(make_launch_payload("watched"))
        unwatched = self.launch_repo.upsert_launch(make_launch_payload("unwatched"))
        assert watched is not None
        assert unwatched is not None
        self.watched_launch_id = watched[0]
        self.unwatched_launch_id = unwatched[0]
        self.watchlist_repo.add_watch(self.watched_launch_id)

    def teardown_method(self):
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def test_watchlist_gates_alert_evaluation_and_dispatch_formatting(self):
        alerts = self.service.check_watched_launches(
            current_launches=[
                {
                    "id": self.watched_launch_id,
                    "liquidity_usd": 600.0,
                    "volume_usd_24h": 100.0,
                    "risk_level": "high",
                },
                {
                    "id": self.unwatched_launch_id,
                    "liquidity_usd": 500.0,
                    "volume_usd_24h": 1000.0,
                    "risk_level": "critical",
                },
            ],
            previous_launches={
                self.watched_launch_id: {
                    "liquidity_usd": 1000.0,
                    "volume_usd_24h": 100.0,
                    "risk_level": "low",
                },
                self.unwatched_launch_id: {
                    "liquidity_usd": 1000.0,
                    "volume_usd_24h": 100.0,
                    "risk_level": "low",
                },
            },
        )

        assert alerts
        assert all(alert["launch_id"] == self.watched_launch_id for alert in alerts)
        assert {alert["alert_type"] for alert in alerts} == {"liquidity_drop", "risk_level_change"}

        with patch(
            "src.services.crypto_alert_service.NotificationBuilder.build_simple_alert",
            return_value="FORMATTED CRYPTO ALERT",
        ) as mock_build_alert:
            with patch("src.services.crypto_alert_service.logger") as mock_logger:
                dispatched = self.service.dispatch_alert(alerts[0])

        assert dispatched is True
        mock_build_alert.assert_called_once_with(
            alerts[0]["title"],
            alerts[0]["message"],
            alerts[0]["severity"],
        )
        mock_logger.warning.assert_called_once()
        assert mock_logger.warning.call_args[0][0] == "Crypto alert dispatch prepared: %s"
        assert mock_logger.warning.call_args[0][1] == "FORMATTED CRYPTO ALERT"
