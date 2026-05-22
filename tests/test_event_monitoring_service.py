# -*- coding: utf-8 -*-
"""Tests for event monitoring priority metadata."""

from src.agent.events import PriceChangeAlert, VolumeAlert
from src.analyzer import AnalysisResult
from src.services.event_monitoring_service import EventMonitoringService


def test_classifies_downside_price_change_as_critical_thesis_break():
    service = EventMonitoringService()
    rule = PriceChangeAlert(stock_code="AAPL", direction="down", change_pct=5.0)

    event = service.classify_alert_result(
        rule,
        {
            "triggered": True,
            "observed_value": -8.2,
            "threshold": 5.0,
            "reason": "AAPL change down 5.00%: current = -8.20%",
            "data_source": "realtime_quote",
        },
    )

    assert event["category"] == "price"
    assert event["priority"] == "critical"
    assert event["thesis_break_risk"] is True
    assert event["coverage"]["earnings_calendar"] == "not_linked"


def test_cycle_summary_orders_triggered_events_by_priority():
    service = EventMonitoringService()
    volume = service.classify_alert_result(
        VolumeAlert(stock_code="600519", multiplier=2.0),
        {
            "triggered": True,
            "observed_value": 5000.0,
            "threshold": 2000.0,
            "reason": "volume spike",
        },
    )
    idle = service.classify_alert_result(
        PriceChangeAlert(stock_code="MSFT", direction="up", change_pct=3.0),
        {
            "triggered": False,
            "observed_value": 1.0,
            "threshold": 3.0,
            "reason": "not crossed",
        },
    )

    summary = service.build_cycle_summary([idle, volume])

    assert summary["evaluated"] == 2
    assert summary["triggered"] == 1
    assert summary["top_events"][0]["stock_code"] == "600519"
    assert summary["monitoring_gaps"]


def test_report_summary_marks_broken_thesis_as_critical():
    result = AnalysisResult(
        code="AAPL",
        name="Apple",
        sentiment_score=50,
        trend_prediction="weak",
        operation_advice="hold",
        thesis_tracking={
            "status": "broken",
            "key_changes": ["Advice changed from Buy to Hold."],
        },
        stock_risk_report={"risk_level": "medium", "risk_score": 50},
        chart_analysis_report={"support": 100.0, "resistance": 120.0, "conflicts": []},
    )

    summary = EventMonitoringService().build_report_summary(result)

    assert summary["monitoring_priority"] == "critical"
    assert summary["thesis_break_risk"] is True
    assert summary["top_events"][0]["event_type"] == "thesis_change"
    assert summary["watch_items"]
