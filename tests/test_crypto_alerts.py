# -*- coding: utf-8 -*-
"""Unit tests for crypto alert evaluation and formatting."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

for optional_module in ("litellm", "json_repair"):
    try:
        __import__(optional_module)
    except ModuleNotFoundError:
        sys.modules[optional_module] = MagicMock()

from src.services.crypto_alert_service import CryptoAlertService


@pytest.mark.not_network
class TestCryptoAlertService:
    def setup_method(self):
        self.mock_config = MagicMock()
        self.mock_config.crypto_alerts_enabled = True
        self.mock_config.crypto_alert_liquidity_drop_pct = 30.0
        self.mock_config.crypto_alert_volume_spike_multiplier = 5.0
        self.mock_watchlist_repo = MagicMock()
        self.mock_watchlist_repo.get_watched_launch_ids.return_value = [101]
        self.service = CryptoAlertService(
            config=self.mock_config,
            watchlist_repo=self.mock_watchlist_repo,
        )

    def test_evaluate_alerts_detects_liquidity_drop(self):
        alerts = self.service.evaluate_alerts(
            101,
            {"liquidity_usd": 1000.0},
            {"liquidity_usd": 650.0},
        )

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["launch_id"] == 101
        assert alert["alert_type"] == "liquidity_drop"
        assert alert["severity"] == "warning"
        assert alert["details"]["drop_pct"] == pytest.approx(35.0)

    def test_evaluate_alerts_detects_volume_spike(self):
        alerts = self.service.evaluate_alerts(
            101,
            {"volume_usd_24h": 100.0},
            {"volume_usd_24h": 600.0},
        )

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["alert_type"] == "volume_spike"
        assert alert["severity"] == "info"
        assert alert["details"]["multiplier"] == pytest.approx(6.0)

    def test_evaluate_alerts_detects_risk_level_worsening(self):
        alerts = self.service.evaluate_alerts(
            101,
            {"risk_level": "low"},
            {"risk_level": "high"},
        )

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["alert_type"] == "risk_level_change"
        assert alert["severity"] == "critical"
        assert alert["details"]["old_risk_level"] == "low"
        assert alert["details"]["new_risk_level"] == "high"

    def test_check_watched_launches_skips_unwatched_launches(self):
        self.mock_watchlist_repo.get_watched_launch_ids.return_value = [202]

        alerts = self.service.check_watched_launches(
            current_launches=[
                {"id": 101, "liquidity_usd": 600.0},
                {"id": 202, "liquidity_usd": 600.0},
            ],
            previous_launches={
                101: {"liquidity_usd": 1000.0},
                202: {"liquidity_usd": 1000.0},
            },
        )

        assert len(alerts) == 1
        assert alerts[0]["launch_id"] == 202

    def test_dispatch_alert_logs_formatted_message(self):
        alert = {
            "launch_id": 101,
            "alert_type": "liquidity_drop",
            "title": "Liquidity dropped",
            "message": "Liquidity dropped sharply",
            "severity": "warning",
            "details": {"drop_pct": 35.0},
        }

        with patch(
            "src.services.crypto_alert_service.NotificationBuilder.build_simple_alert",
            return_value="FORMATTED ALERT",
        ) as mock_build_alert:
            with patch("src.services.crypto_alert_service.logger") as mock_logger:
                sent = self.service.dispatch_alert(alert)

        assert sent is True
        mock_build_alert.assert_called_once_with(
            "Liquidity dropped",
            "Liquidity dropped sharply",
            "warning",
        )
        mock_logger.warning.assert_called_once()
        assert mock_logger.warning.call_args[0][0] == "Crypto alert dispatch prepared: %s"
        assert mock_logger.warning.call_args[0][1] == "FORMATTED ALERT"

    def test_evaluate_alerts_skips_none_and_zero_baselines(self):
        alerts = self.service.evaluate_alerts(
            101,
            {"liquidity_usd": 0, "volume_usd_24h": None, "risk_level": None},
            {"liquidity_usd": 10.0, "volume_usd_24h": 1000.0, "risk_level": "medium"},
        )

        assert alerts == []

    def test_evaluate_alerts_returns_empty_when_disabled(self):
        self.mock_config.crypto_alerts_enabled = False

        alerts = self.service.evaluate_alerts(
            101,
            {"liquidity_usd": 1000.0},
            {"liquidity_usd": 100.0},
        )

        assert alerts == []
