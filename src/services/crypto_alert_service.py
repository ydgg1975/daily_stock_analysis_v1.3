# -*- coding: utf-8 -*-
"""Deterministic alert evaluation for watched crypto launches."""

import logging
from typing import Any, Optional

from src.config import Config
from src.notification import NotificationBuilder, NotificationService
from src.repositories.crypto_watchlist_repo import CryptoWatchlistRepository

logger = logging.getLogger(__name__)

_RISK_LEVEL_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


class CryptoAlertService:
    """Evaluates deterministic threshold-based alerts for watched crypto launches."""

    def __init__(self, config=None, watchlist_repo=None):
        self.config = config or Config.get_instance()
        self.watchlist_repo = watchlist_repo or CryptoWatchlistRepository()

    def evaluate_alerts(self, launch_id: int, old_data: dict, new_data: dict) -> list[dict]:
        """Compare old vs new data for a watched launch and return alert payloads."""
        if not getattr(self.config, "crypto_alerts_enabled", False):
            return []

        alerts = []
        old_data = old_data or {}
        new_data = new_data or {}

        liquidity_threshold_pct = float(
            getattr(self.config, "crypto_alert_liquidity_drop_pct", 30.0)
        )
        volume_spike_multiplier = float(
            getattr(self.config, "crypto_alert_volume_spike_multiplier", 5.0)
        )

        old_liquidity = self._number(new_value=old_data.get("liquidity_usd"))
        new_liquidity = self._number(new_value=new_data.get("liquidity_usd"))
        if old_liquidity is not None and new_liquidity is not None:
            threshold_liquidity = old_liquidity * (1 - (liquidity_threshold_pct / 100.0))
            if new_liquidity < threshold_liquidity:
                drop_pct = ((old_liquidity - new_liquidity) / old_liquidity) * 100.0
                severity = "critical" if drop_pct > 50 else "warning"
                alerts.append(
                    {
                        "launch_id": launch_id,
                        "alert_type": "liquidity_drop",
                        "title": f"Crypto launch {launch_id} liquidity dropped",
                        "message": (
                            f"Liquidity fell from ${old_liquidity:,.2f} to ${new_liquidity:,.2f} "
                            f"({drop_pct:.1f}% drop)."
                        ),
                        "severity": severity,
                        "details": {
                            "old_liquidity_usd": old_liquidity,
                            "new_liquidity_usd": new_liquidity,
                            "drop_pct": round(drop_pct, 2),
                            "threshold_pct": liquidity_threshold_pct,
                        },
                    }
                )

        old_volume = self._number(new_value=old_data.get("volume_usd_24h"))
        new_volume = self._number(new_value=new_data.get("volume_usd_24h"))
        if old_volume is not None and new_volume is not None:
            threshold_volume = old_volume * volume_spike_multiplier
            if new_volume > threshold_volume:
                multiplier = new_volume / old_volume
                alerts.append(
                    {
                        "launch_id": launch_id,
                        "alert_type": "volume_spike",
                        "title": f"Crypto launch {launch_id} volume spiked",
                        "message": (
                            f"24h volume increased from ${old_volume:,.2f} to ${new_volume:,.2f} "
                            f"({multiplier:.1f}x baseline)."
                        ),
                        "severity": "info",
                        "details": {
                            "old_volume_usd_24h": old_volume,
                            "new_volume_usd_24h": new_volume,
                            "multiplier": round(multiplier, 2),
                            "threshold_multiplier": volume_spike_multiplier,
                        },
                    }
                )

        old_risk_level = self._normalize_risk_level(old_data.get("risk_level"))
        new_risk_level = self._normalize_risk_level(new_data.get("risk_level"))
        if old_risk_level and new_risk_level:
            old_risk_index = _RISK_LEVEL_ORDER.get(old_risk_level)
            new_risk_index = _RISK_LEVEL_ORDER.get(new_risk_level)
            if old_risk_index is not None and new_risk_index is not None and new_risk_index > old_risk_index:
                delta = new_risk_index - old_risk_index
                severity = "critical" if delta >= 2 else "warning"
                alerts.append(
                    {
                        "launch_id": launch_id,
                        "alert_type": "risk_level_change",
                        "title": f"Crypto launch {launch_id} risk worsened",
                        "message": f"Risk level changed from {old_risk_level} to {new_risk_level}.",
                        "severity": severity,
                        "details": {
                            "old_risk_level": old_risk_level,
                            "new_risk_level": new_risk_level,
                            "risk_delta": delta,
                        },
                    }
                )

        return alerts

    def check_watched_launches(self, current_launches: list[dict], previous_launches: dict[int, dict]) -> list[dict]:
        """Collect alerts for watched launches only."""
        if not getattr(self.config, "crypto_alerts_enabled", False):
            return []

        watched_ids = set(self.watchlist_repo.get_watched_launch_ids())
        if not watched_ids:
            return []

        alerts = []
        previous_launches = previous_launches or {}
        for launch in current_launches or []:
            launch_id = launch.get("id")
            if launch_id not in watched_ids:
                continue

            old_data = previous_launches.get(launch_id)
            if not old_data:
                continue

            alerts.extend(self.evaluate_alerts(launch_id, old_data, launch))

        return alerts

    def dispatch_alert(self, alert: dict) -> bool:
        """Format and send a crypto alert through notification channels."""
        formatted_message = NotificationBuilder.build_simple_alert(
            alert.get("title", "Crypto Alert"),
            alert.get("message", ""),
            alert.get("severity", "info"),
        )
        logger.warning("Crypto alert dispatch: %s", formatted_message)
        try:
            notifier = NotificationService()
            sent = notifier.send(formatted_message)
            if sent:
                logger.info("Crypto alert sent successfully for launch %s", alert.get("launch_id"))
            else:
                logger.warning("Crypto alert notification returned False for launch %s", alert.get("launch_id"))
            return sent
        except Exception:
            logger.exception("Failed to send crypto alert for launch %s", alert.get("launch_id"))
            return False

    @staticmethod
    def _number(new_value: Any) -> Optional[float]:
        if new_value is None:
            return None
        try:
            return float(new_value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_risk_level(value: Any) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        return normalized if normalized in _RISK_LEVEL_ORDER else None
