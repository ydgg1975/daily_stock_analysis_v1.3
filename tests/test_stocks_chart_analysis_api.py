# -*- coding: utf-8 -*-
"""Contract tests for stock chart-analysis API."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app


def test_chart_analysis_endpoint_returns_svg_and_metadata():
    app = create_app()
    client = TestClient(app)

    with patch(
        "src.agent.tools.analysis_tools._handle_generate_chart_analysis",
        return_value={
            "stock_code": "AAPL",
            "source": "test",
            "requested_days": 60,
            "status": "ok",
            "image_format": "svg",
            "svg": "<svg></svg>",
            "metadata": {"visual_signal": "bullish"},
        },
    ):
        response = client.get("/api/v1/stocks/AAPL/chart-analysis", params={"days": 60, "include_svg": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["stock_code"] == "AAPL"
    assert payload["source"] == "test"
    assert payload["status"] == "ok"
    assert payload["svg"] == "<svg></svg>"
    assert payload["svg_length"] == len("<svg></svg>")
    assert payload["metadata"]["visual_signal"] == "bullish"


def test_chart_analysis_endpoint_returns_degraded_for_missing_data():
    app = create_app()
    client = TestClient(app)

    with patch(
        "src.agent.tools.analysis_tools._handle_generate_chart_analysis",
        return_value={"error": "No historical data available for chart analysis on EMPTY"},
    ):
        response = client.get("/api/v1/stocks/EMPTY/chart-analysis", params={"days": 60})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["reason"] == "No historical data available for chart analysis on EMPTY"
