# -*- coding: utf-8 -*-
"""Tests for single-stock risk report generation."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.analyzer import AnalysisResult
from src.services.stock_risk_service import build_stock_risk_report


class StockRiskServiceTest(unittest.TestCase):
    def test_builds_volatility_drawdown_and_flags(self) -> None:
        result = AnalysisResult(
            code="AAPL",
            name="Apple",
            sentiment_score=62,
            trend_prediction="Sideways",
            operation_advice="Hold",
            analysis_summary="Wait for confirmation.",
            risk_warning="Breakout failed.",
        )
        trend = SimpleNamespace(
            bias_ma5=9.5,
            rsi_6=78.0,
            risk_factors=["Support is close to failing."],
        )
        df = pd.DataFrame({"close": [100, 130, 85, 92, 80, 88]})

        report = build_stock_risk_report(result, trend_result=trend, history_df=df)

        self.assertEqual(report["version"], 1)
        self.assertIsNotNone(report["volatility_pct"])
        self.assertGreaterEqual(report["max_drawdown_pct"], 30)
        self.assertIn(report["risk_level"], {"medium", "high"})
        flag_ids = {flag["id"] for flag in report["flags"]}
        self.assertIn("large_drawdown", flag_ids)
        self.assertIn("extended_from_ma5", flag_ids)
        self.assertIn("short_term_overbought", flag_ids)
        self.assertIn("reported_risk", flag_ids)


if __name__ == "__main__":
    unittest.main()
