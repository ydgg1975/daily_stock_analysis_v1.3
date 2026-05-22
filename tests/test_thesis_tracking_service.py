# -*- coding: utf-8 -*-
"""Tests for stock thesis tracking metadata."""

import json
import sys
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.analyzer import AnalysisResult
from src.services.thesis_tracking_service import attach_thesis_tracking, build_thesis_tracking


class ThesisTrackingServiceTest(unittest.TestCase):
    def test_builds_new_status_without_previous_record(self) -> None:
        result = AnalysisResult(
            code="AAPL",
            name="Apple",
            sentiment_score=65,
            trend_prediction="Sideways",
            operation_advice="Hold",
            decision_type="hold",
            analysis_summary="Wait for confirmation.",
        )

        tracking = build_thesis_tracking(result, None)

        self.assertEqual(tracking["status"], "new")
        self.assertEqual(tracking["current_thesis"], "Wait for confirmation.")
        self.assertIn("No previous analysis", tracking["key_changes"][0])

    def test_builds_broken_status_from_previous_record(self) -> None:
        result = AnalysisResult(
            code="AAPL",
            name="Apple",
            sentiment_score=52,
            trend_prediction="Sideways",
            operation_advice="Hold",
            decision_type="hold",
            analysis_summary="Momentum is weaker.",
            risk_warning="Breakout failed.",
        )
        previous = SimpleNamespace(
            query_id="q-previous",
            created_at=datetime(2026, 5, 1, 9, 0, 0),
            sentiment_score=72,
            operation_advice="Buy",
            trend_prediction="Bullish",
            analysis_summary="Buy the pullback.",
        )
        previous_raw = {
            "decision_type": "buy",
            "operation_advice": "Buy",
            "trend_prediction": "Bullish",
            "analysis_summary": "Buy the pullback.",
            "risk_warning": "Watch valuation.",
        }

        tracking = build_thesis_tracking(result, previous, previous_raw)

        self.assertEqual(tracking["status"], "broken")
        self.assertEqual(tracking["score_delta"], -20)
        self.assertTrue(tracking["decision_changed"])
        self.assertIn("Advice changed", " ".join(tracking["key_changes"]))
        self.assertEqual(tracking["previous_query_id"], "q-previous")

    def test_attach_thesis_tracking_reads_latest_history(self) -> None:
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            sentiment_score=80,
            trend_prediction="看多",
            operation_advice="买入",
            decision_type="buy",
            analysis_summary="趋势增强。",
            query_id="q-current",
        )
        previous = SimpleNamespace(
            query_id="q-old",
            created_at=datetime(2026, 5, 1, 9, 0, 0),
            sentiment_score=60,
            operation_advice="持有",
            trend_prediction="震荡",
            analysis_summary="等待确认。",
            raw_result=json.dumps({
                "decision_type": "hold",
                "analysis_summary": "等待确认。",
            }, ensure_ascii=False),
        )
        db = SimpleNamespace(
            get_analysis_history=lambda **kwargs: [previous],
        )

        attach_thesis_tracking(result, db)

        self.assertIsNotNone(result.thesis_tracking)
        self.assertEqual(result.thesis_tracking["status"], "strengthened")
        self.assertEqual(result.thesis_tracking["previous_query_id"], "q-old")


if __name__ == "__main__":
    unittest.main()
