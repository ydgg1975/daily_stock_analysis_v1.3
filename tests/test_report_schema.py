# -*- coding: utf-8 -*-
"""
===================================
Report Engine - Schema parsing and fallback tests
===================================

Tests for AnalysisReportSchema validation and analyzer fallback behavior.
"""

import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Mock litellm before importing analyzer (optional runtime dep)
try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.schemas.report_schema import AnalysisReportSchema
from src.analyzer import GeminiAnalyzer, AnalysisResult


class TestAnalysisReportSchema(unittest.TestCase):
    """Schema parsing tests."""

    def test_valid_dashboard_parses(self) -> None:
        """Valid LLM-like JSON parses successfully."""
        data = {
            "stock_name": "guizhoumaotai",
            "sentiment_score": 75,
            "trend_prediction": "kanduo",
            "operation_advice": "chiyou",
            "decision_type": "hold",
            "confidence_level": "zhong",
            "dashboard": {
                "core_conclusion": {"one_sentence": "chiyouguanwang"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "110yuan"}},
            },
            "analysis_summary": "jibenmianwenjian",
        }
        schema = AnalysisReportSchema.model_validate(data)
        self.assertEqual(schema.stock_name, "guizhoumaotai")
        self.assertEqual(schema.sentiment_score, 75)
        self.assertIsNotNone(schema.dashboard)

    def test_schema_allows_optional_fields_missing(self) -> None:
        """Schema accepts minimal valid structure."""
        data = {
            "stock_name": "ceshi",
            "sentiment_score": 50,
            "trend_prediction": "zhendang",
            "operation_advice": "guanwang",
        }
        schema = AnalysisReportSchema.model_validate(data)
        self.assertIsNone(schema.dashboard)
        self.assertIsNone(schema.analysis_summary)

    def test_schema_allows_numeric_strings(self) -> None:
        """Schema accepts string values for numeric fields (LLM may return N/A)."""
        data = {
            "stock_name": "ceshi",
            "sentiment_score": 60,
            "trend_prediction": "kanduo",
            "operation_advice": "mairu",
            "dashboard": {
                "data_perspective": {
                    "price_position": {
                        "current_price": "N/A",
                        "bias_ma5": "2.5",
                    }
                }
            },
        }
        schema = AnalysisReportSchema.model_validate(data)
        self.assertIsNotNone(schema.dashboard)
        pp = schema.dashboard and schema.dashboard.data_perspective and schema.dashboard.data_perspective.price_position
        self.assertIsNotNone(pp)
        if pp:
            self.assertEqual(pp.current_price, "N/A")
            self.assertEqual(pp.bias_ma5, "2.5")

    def test_schema_fails_on_invalid_sentiment_score(self) -> None:
        """Schema validation fails when sentiment_score out of range."""
        data = {
            "stock_name": "ceshi",
            "sentiment_score": 150,  # out of 0-100
            "trend_prediction": "kanduo",
            "operation_advice": "mairu",
        }
        with self.assertRaises(Exception):
            AnalysisReportSchema.model_validate(data)


class TestAnalyzerSchemaFallback(unittest.TestCase):
    """Analyzer fallback when schema validation fails."""

    def test_parse_response_continues_when_schema_fails(self) -> None:
        """When schema validation fails, analyzer continues with raw dict."""
        analyzer = GeminiAnalyzer()
        response = json.dumps({
            "stock_name": "guizhoumaotai",
            "sentiment_score": 150,  # invalid for schema
            "trend_prediction": "kanduo",
            "operation_advice": "chiyou",
            "analysis_summary": "ceshizhaiyao",
        })
        result = analyzer._parse_response(response, "600519", "guizhoumaotai")
        self.assertIsInstance(result, AnalysisResult)
        self.assertEqual(result.code, "600519")
        self.assertEqual(result.sentiment_score, 150)  # from raw dict
        self.assertTrue(result.success)

    def test_parse_response_valid_json_succeeds(self) -> None:
        """Valid JSON produces correct AnalysisResult."""
        analyzer = GeminiAnalyzer()
        response = json.dumps({
            "stock_name": "guizhoumaotai",
            "sentiment_score": 72,
            "trend_prediction": "kanduo",
            "operation_advice": "chiyou",
            "decision_type": "hold",
            "confidence_level": "gao",
            "analysis_summary": "jishumianxianghao",
        })
        result = analyzer._parse_response(response, "600519", "gupiao600519")
        self.assertIsInstance(result, AnalysisResult)
        self.assertEqual(result.name, "guizhoumaotai")
        self.assertEqual(result.sentiment_score, 72)
        self.assertEqual(result.analysis_summary, "jishumianxianghao")

    def test_parse_response_keeps_unknown_dashboard_fields(self) -> None:
        analyzer = GeminiAnalyzer()
        response = json.dumps({
            "stock_name": "guizhoumaotai",
            "sentiment_score": 72,
            "trend_prediction": "kanduo",
            "operation_advice": "chiyou",
            "decision_type": "hold",
            "analysis_summary": "jishumianxianghao",
            "dashboard": {
                "core_conclusion": {
                    "one_sentence": "xianguancha",
                    "signal_type": "🟡chiyouguanwang",
                },
                "decision_stability": {
                    "applied": True,
                    "reason": "huiceyanzheng",
                },
            },
        })
        result = analyzer._parse_response(response, "600519", "gupiao600519")
        self.assertEqual(result.dashboard["decision_stability"]["applied"], True)
        self.assertEqual(result.dashboard["decision_stability"]["reason"], "huiceyanzheng")

    def test_parse_text_response_honors_injected_runtime_report_language(self) -> None:
        """Fallback text parsing should use the analyzer's injected config, not the global singleton."""
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(config=SimpleNamespace(report_language="en"))

        result = analyzer._parse_text_response("bullish buy setup", "AAPL", "Apple")

        self.assertEqual(result.report_language, "en")
        self.assertEqual(result.trend_prediction, "Bullish")
        self.assertEqual(result.operation_advice, "Buy")
        self.assertEqual(result.confidence_level, "Low")
