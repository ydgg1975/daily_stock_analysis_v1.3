# -*- coding: utf-8 -*-
"""Offline smoke tests for representative A-share, HK, and US agent flows."""

from unittest.mock import patch

import pandas as pd
import pytest

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.agent.factory import get_tool_registry


REPRESENTATIVE_STOCKS = [
    ("600519", "cn"),
    ("HK00700", "hk"),
    ("AAPL", "us"),
]


def _sample_history(stock_code: str) -> pd.DataFrame:
    rows = []
    for idx in range(1, 31):
        close = 100 + idx
        rows.append(
            {
                "code": stock_code,
                "date": f"2026-03-{idx:02d}",
                "open": close - 0.8,
                "high": close + 1.2,
                "low": close - 1.4,
                "close": close,
                "volume": 100000 + idx * 1000,
            }
        )
    return pd.DataFrame(rows)


@pytest.mark.parametrize(("stock_code", "market"), REPRESENTATIVE_STOCKS)
def test_representative_market_history_tool_smoke(stock_code, market):
    registry = get_tool_registry()

    with patch("src.services.history_loader.load_history_df", return_value=(_sample_history(stock_code), "db_cache")):
        result = registry.execute("get_daily_history", stock_code=stock_code, days=20)

    assert result["code"] == stock_code
    assert result["source"] == "db_cache"
    assert result["actual_records"] == 20
    assert result["data"][-1]["code"] == stock_code
    assert market in {"cn", "hk", "us"}


@pytest.mark.parametrize(("stock_code", "market"), REPRESENTATIVE_STOCKS)
def test_representative_market_chart_analysis_tool_smoke(stock_code, market):
    registry = get_tool_registry()

    with patch("src.services.history_loader.load_history_df", return_value=(_sample_history(stock_code), "fixture")):
        result = registry.execute("generate_chart_analysis", stock_code=stock_code, days=20)

    assert result["stock_code"] == stock_code
    assert result["status"] == "ok"
    assert result["source"] == "fixture"
    assert result["image_format"] == "svg"
    assert result["svg_omitted"] is True
    assert "svg" not in result
    assert result["metadata"]["version"] == 1
    assert result["metadata"]["latest_close"] == 130.0
    assert market in {"cn", "hk", "us"}
