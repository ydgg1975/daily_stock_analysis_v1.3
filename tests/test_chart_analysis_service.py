# -*- coding: utf-8 -*-
"""Tests for SVG chart analysis generation."""

import pandas as pd

from src.services.chart_analysis_service import ChartAnalysisService


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
    assert "support" in result["metadata"]
    assert "resistance" in result["metadata"]


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
