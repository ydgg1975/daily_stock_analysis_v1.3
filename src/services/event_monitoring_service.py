# -*- coding: utf-8 -*-
"""Event monitoring classification for stock-analysis alerts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class EventMonitoringService:
    """Classify alert evaluations into actionable event-monitoring metadata."""

    def classify_alert_result(self, rule: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        alert_type = self._alert_type(rule)
        stock_code = str(getattr(rule, "stock_code", "") or result.get("target") or "").strip()
        observed = self._optional_float(result.get("observed_value"))
        threshold = self._optional_float(result.get("threshold"))
        triggered = bool(result.get("triggered"))
        direction = str(getattr(rule, "direction", "") or "").lower()
        category = self._category(alert_type)
        priority_score = self._priority_score(
            alert_type=alert_type,
            direction=direction,
            observed=observed,
            threshold=threshold,
            triggered=triggered,
        )
        thesis_break = self._thesis_break_risk(
            alert_type=alert_type,
            direction=direction,
            observed=observed,
            triggered=triggered,
        )
        return {
            "stock_code": stock_code,
            "event_type": alert_type,
            "category": category,
            "triggered": triggered,
            "priority": self._priority_label(priority_score),
            "priority_score": priority_score,
            "thesis_break_risk": thesis_break,
            "reason": result.get("reason") or result.get("message"),
            "data_source": result.get("data_source"),
            "data_timestamp": self._serialize_timestamp(result.get("data_timestamp")),
            "coverage": self._coverage(alert_type),
        }

    def build_cycle_summary(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        ordered = sorted(events, key=lambda item: int(item.get("priority_score") or 0), reverse=True)
        triggered = [item for item in ordered if item.get("triggered")]
        return {
            "evaluated": len(events),
            "triggered": len(triggered),
            "critical": sum(1 for item in triggered if item.get("priority") == "critical"),
            "warning": sum(1 for item in triggered if item.get("priority") == "warning"),
            "info": sum(1 for item in triggered if item.get("priority") == "info"),
            "top_events": triggered[:10],
            "monitoring_gaps": self._monitoring_gaps(),
        }

    @staticmethod
    def _alert_type(rule: Any) -> str:
        raw = getattr(rule, "alert_type", "") or ""
        return str(getattr(raw, "value", raw) or "").strip().lower()

    @staticmethod
    def _category(alert_type: str) -> str:
        if alert_type in {"price_cross", "price_change_percent"}:
            return "price"
        if alert_type == "volume_spike":
            return "volume"
        if alert_type in {"ma_price_cross", "rsi_threshold", "macd_cross", "kdj_cross", "cci_threshold"}:
            return "technical"
        if alert_type in {"earnings_calendar", "disclosure_change", "news_change"}:
            return "fundamental_event"
        return "unknown"

    def _priority_score(
        self,
        *,
        alert_type: str,
        direction: str,
        observed: Optional[float],
        threshold: Optional[float],
        triggered: bool,
    ) -> int:
        if not triggered:
            return 0
        score = 50
        if alert_type == "price_change_percent" and observed is not None:
            magnitude = abs(observed)
            if magnitude >= 8.0:
                score += 35
            elif magnitude >= 5.0:
                score += 25
            elif magnitude >= 3.0:
                score += 15
            if observed < 0:
                score += 10
        elif alert_type == "volume_spike" and observed is not None and threshold and threshold > 0:
            ratio = observed / threshold
            if ratio >= 2.0:
                score += 30
            elif ratio >= 1.2:
                score += 20
            else:
                score += 10
        elif alert_type == "price_cross":
            score += 25 if direction == "below" else 15
        elif alert_type in {"macd_cross", "kdj_cross", "ma_price_cross"}:
            score += 20 if "bear" in direction or direction == "below" else 12
        else:
            score += 10
        return min(score, 100)

    @staticmethod
    def _priority_label(score: int) -> str:
        if score >= 80:
            return "critical"
        if score >= 55:
            return "warning"
        return "info"

    @staticmethod
    def _thesis_break_risk(
        *,
        alert_type: str,
        direction: str,
        observed: Optional[float],
        triggered: bool,
    ) -> bool:
        if not triggered:
            return False
        if alert_type == "price_change_percent" and observed is not None and observed <= -5.0:
            return True
        if alert_type == "price_cross" and direction == "below":
            return True
        if alert_type in {"macd_cross", "kdj_cross"} and "bear" in direction:
            return True
        if alert_type == "ma_price_cross" and direction == "below":
            return True
        return False

    @staticmethod
    def _coverage(alert_type: str) -> Dict[str, Any]:
        return {
            "price_volume": "available" if alert_type in {"price_cross", "price_change_percent", "volume_spike"} else "partial",
            "technical": "available" if alert_type in {"ma_price_cross", "rsi_threshold", "macd_cross", "kdj_cross", "cci_threshold"} else "partial",
            "earnings_calendar": "not_linked",
            "disclosure_news": "not_linked",
        }

    @staticmethod
    def _monitoring_gaps() -> List[str]:
        return [
            "Earnings calendar ingestion is not linked yet.",
            "Disclosure and news change streams are not linked yet.",
        ]

    @staticmethod
    def _optional_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _serialize_timestamp(value: Any) -> Optional[str]:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
