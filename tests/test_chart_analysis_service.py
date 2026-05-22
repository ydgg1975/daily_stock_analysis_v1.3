# -*- coding: utf-8 -*-
"""Tests for SVG chart analysis generation."""

import pandas as pd

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.analyzer import AnalysisResult
from src.services.chart_analysis_service import (
    ChartAnalysisService,
    attach_chart_analysis_report,
    build_chart_analysis_report,
)


def _sample_ohlcv(closes):
    rows = []
    for idx, close in enumerate(closes, start=1):
        rows.append(
            {
                "date": f"2026-03-{idx:02d}",
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1000 + idx * 100,
            }
        )
    return pd.DataFrame(rows)


def test_chart_analysis_generates_svg_and_metadata():
    service = ChartAnalysisService()
    result = service.analyze("AAPL", _sample_ohlcv([10, 11, 12, 11, 13, 14, 15, 16]))

    assert result["status"] == "ok"
    assert result["image_format"] == "svg"
    assert result["svg"].startswith("<svg")
    assert "AAPL chart analysis" in result["svg"]
    assert result["metadata"]["version"] == 1
    assert result["metadata"]["pattern"]["name"] == "five_bar_breakout"
    assert result["metadata"]["visual_signal"] == "bullish"
    assert result["metadata"]["display_labels"]["pattern"] == "5-bar breakout"
    assert "support" in result["metadata"]
    assert "resistance" in result["metadata"]


def test_chart_analysis_svg_includes_axes_labels_and_macd_histogram():
    service = ChartAnalysisService()
    result = service.analyze("AAPL", _sample_ohlcv([10, 11, 12, 11, 13, 14, 15, 16]))

    svg = result["svg"]
    assert "Support" in svg
    assert "Resistance" in svg
    assert "RSI 70" in svg
    assert "RSI 30" in svg
    assert "03-01" in svg
    assert 'opacity="0.42"' in svg


def test_chart_analysis_reports_conflict_between_visual_and_indicator_signal():
    service = ChartAnalysisService()
    result = service.analyze(
        "TEST",
        _sample_ohlcv([10, 12, 14, 16, 18, 20, 19, 18, 17, 16]),
    )

    assert result["status"] == "ok"
    assert result["metadata"]["conflicts"]
    assert result["metadata"]["conflicts"][0]["type"] == "signal_conflict"


def test_chart_analysis_degrades_without_data():
    service = ChartAnalysisService()
    result = service.analyze("EMPTY", pd.DataFrame())

    assert result["status"] == "degraded"
    assert result["svg"] == ""


def test_build_chart_analysis_report_omits_svg_for_report_payload():
    report = build_chart_analysis_report("AAPL", _sample_ohlcv([10, 11, 12, 11, 13, 14, 15, 16]))

    assert report["status"] == "ok"
    assert report["pattern_label"] == "5-bar breakout"
    assert report["support"] == 9.0
    assert "svg" not in report


def test_attach_chart_analysis_report_to_analysis_result():
    result = AnalysisResult(
        code="AAPL",
        name="Apple",
        sentiment_score=70,
        trend_prediction="bullish",
        operation_advice="hold",
    )

    attach_chart_analysis_report(result, _sample_ohlcv([10, 11, 12, 11, 13, 14, 15, 16]))

    assert result.chart_analysis_report
    assert result.to_dict()["chart_analysis_report"]["status"] == "ok"
