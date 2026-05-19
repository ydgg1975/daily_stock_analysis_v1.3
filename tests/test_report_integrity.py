# -*- coding: utf-8 -*-
"""
===================================
Report Engine - Content integrity tests
===================================

Tests for check_content_integrity, apply_placeholder_fill, and retry/placeholder behavior.
"""

import json
import sys
import unittest
from unittest.mock import MagicMock, patch

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.analyzer import AnalysisResult, GeminiAnalyzer, check_content_integrity, apply_placeholder_fill


class TestCheckContentIntegrity(unittest.TestCase):
    """Content integrity check tests."""

    def test_pass_when_all_required_present(self) -> None:
        """Integrity passes when all mandatory fields are present."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="wenjian",
            decision_type="hold",
            dashboard={
                "core_conclusion": {"one_sentence": "chiyouguanwang"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "110yuan"}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_fail_when_analysis_summary_empty(self) -> None:
        """Integrity fails when analysis_summary is empty."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="",
            decision_type="hold",
            dashboard={
                "core_conclusion": {"one_sentence": "chiyou"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "110"}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertFalse(ok)
        self.assertIn("analysis_summary", missing)

    def test_fail_when_one_sentence_missing(self) -> None:
        """Integrity fails when core_conclusion.one_sentence is missing."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="wenjian",
            decision_type="hold",
            dashboard={
                "core_conclusion": {},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "110"}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertFalse(ok)
        self.assertIn("dashboard.core_conclusion.one_sentence", missing)

    def test_fail_when_one_sentence_blank(self) -> None:
        """Integrity fails when one_sentence is blank whitespace."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="wenjian",
            decision_type="hold",
            dashboard={
                "core_conclusion": {"one_sentence": "   "},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "110"}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertFalse(ok)
        self.assertIn("dashboard.core_conclusion.one_sentence", missing)

    def test_fail_when_stop_loss_missing_for_buy(self) -> None:
        """Integrity fails when stop_loss missing and decision_type is buy."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="mairu",
            analysis_summary="wenjian",
            decision_type="buy",
            dashboard={
                "core_conclusion": {"one_sentence": "kemairu"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertFalse(ok)
        self.assertIn("dashboard.battle_plan.sniper_points.stop_loss", missing)

    def test_pass_when_stop_loss_missing_for_sell(self) -> None:
        """Integrity passes when stop_loss missing and decision_type is sell."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kankong",
            sentiment_score=35,
            operation_advice="maichu",
            analysis_summary="ruoshi",
            decision_type="sell",
            dashboard={
                "core_conclusion": {"one_sentence": "jianyimaichu"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_fail_when_risk_alerts_missing(self) -> None:
        """Integrity fails when intelligence.risk_alerts field is missing."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="wenjian",
            decision_type="hold",
            dashboard={
                "core_conclusion": {"one_sentence": "chiyou"},
                "intelligence": {},
                "battle_plan": {"sniper_points": {"stop_loss": "110"}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertFalse(ok)
        self.assertIn("dashboard.intelligence.risk_alerts", missing)

    def test_fail_when_risk_alerts_is_none(self) -> None:
        """Integrity fails when risk_alerts is None."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="wenjian",
            decision_type="hold",
            dashboard={
                "core_conclusion": {"one_sentence": "chiyou"},
                "intelligence": {"risk_alerts": None},
                "battle_plan": {"sniper_points": {"stop_loss": "110"}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertFalse(ok)
        self.assertIn("dashboard.intelligence.risk_alerts", missing)

    def test_fail_when_risk_alerts_is_invalid_type(self) -> None:
        """Integrity fails when risk_alerts is not list."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="wenjian",
            decision_type="hold",
            dashboard={
                "core_conclusion": {"one_sentence": "chiyou"},
                "intelligence": {"risk_alerts": "xuliuyi"},
                "battle_plan": {"sniper_points": {"stop_loss": "110"}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertFalse(ok)
        self.assertIn("dashboard.intelligence.risk_alerts", missing)

    def test_fail_when_stop_loss_is_blank(self) -> None:
        """Integrity fails when stop_loss is blank whitespace."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="mairu",
            analysis_summary="wenjian",
            decision_type="buy",
            dashboard={
                "core_conclusion": {"one_sentence": "kemairu"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "   "}},
            },
        )
        ok, missing = check_content_integrity(result)
        self.assertFalse(ok)
        self.assertIn("dashboard.battle_plan.sniper_points.stop_loss", missing)


class TestApplyPlaceholderFill(unittest.TestCase):
    """Placeholder fill tests."""

    def test_fills_missing_analysis_summary(self) -> None:
        """Placeholder fills analysis_summary when missing."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="",
            decision_type="hold",
            dashboard={},
        )
        apply_placeholder_fill(result, ["analysis_summary"])
        self.assertEqual(result.analysis_summary, "daibuchong")

    def test_fills_missing_analysis_summary_in_english(self) -> None:
        """English report should use English placeholder text for missing analysis_summary."""
        result = AnalysisResult(
            code="600519",
            name="MacaoTech",
            report_language="en",
            trend_prediction="Bullish",
            sentiment_score=70,
            operation_advice="Buy",
            analysis_summary="",
            decision_type="buy",
            dashboard={},
        )
        apply_placeholder_fill(result, ["analysis_summary"])
        self.assertEqual(result.analysis_summary, "TBD")

    def test_fills_missing_stop_loss(self) -> None:
        """Placeholder fills stop_loss when missing."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="mairu",
            analysis_summary="wenjian",
            decision_type="buy",
            dashboard={"battle_plan": {"sniper_points": {}}},
        )
        apply_placeholder_fill(result, ["dashboard.battle_plan.sniper_points.stop_loss"])
        self.assertEqual(
            result.dashboard["battle_plan"]["sniper_points"]["stop_loss"],
            "daibuchong",
        )

    def test_fills_risk_alerts_empty_list(self) -> None:
        """Placeholder fills risk_alerts with empty list when missing."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="wenjian",
            decision_type="hold",
            dashboard={"intelligence": {}},
        )
        apply_placeholder_fill(result, ["dashboard.intelligence.risk_alerts"])
        self.assertEqual(result.dashboard["intelligence"]["risk_alerts"], [])

    def test_fills_risk_alerts_when_none(self) -> None:
        """Placeholder fills risk_alerts when value is None."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="wenjian",
            decision_type="hold",
            risk_warning="zhuyirongzi",
            dashboard={"intelligence": {"risk_alerts": None}},
        )
        apply_placeholder_fill(result, ["dashboard.intelligence.risk_alerts"])
        self.assertEqual(result.dashboard["intelligence"]["risk_alerts"], ["zhuyirongzi"])

    def test_fills_risk_alerts_when_invalid_type(self) -> None:
        """Placeholder fills risk_alerts when value is non-list."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="wenjian",
            decision_type="hold",
            dashboard={"intelligence": {"risk_alerts": "zhuyihuiche"}},
        )
        apply_placeholder_fill(result, ["dashboard.intelligence.risk_alerts"])
        self.assertEqual(result.dashboard["intelligence"]["risk_alerts"], [])

    def test_fills_risk_alerts_when_risk_warning_is_list(self) -> None:
        """Placeholder handles list risk_warning and flattens valid text values."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="wenjian",
            decision_type="hold",
            risk_warning=["huichefengxian", "bodongjiada"],
            dashboard={"intelligence": {"risk_alerts": ""}},
        )
        apply_placeholder_fill(result, ["dashboard.intelligence.risk_alerts"])
        self.assertEqual(result.dashboard["intelligence"]["risk_alerts"], ["huichefengxian", "bodongjiada"])

    def test_fills_risk_alerts_when_risk_warning_is_dict(self) -> None:
        """Placeholder serializes dict risk_warning into a string risk alert."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="chiyou",
            analysis_summary="wenjian",
            decision_type="hold",
            risk_warning={"note": "jishumianpianruo"},
            dashboard={"intelligence": {"risk_alerts": ""}},
        )
        apply_placeholder_fill(result, ["dashboard.intelligence.risk_alerts"])
        self.assertEqual(
            json.loads(result.dashboard["intelligence"]["risk_alerts"][0]),
            {"note": "jishumianpianruo"},
        )

    def test_fills_stop_loss_when_blank(self) -> None:
        """Placeholder fills stop_loss when blank whitespace."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="mairu",
            analysis_summary="wenjian",
            decision_type="buy",
            dashboard={"battle_plan": {"sniper_points": {"stop_loss": "   "}}},
        )
        apply_placeholder_fill(result, ["dashboard.battle_plan.sniper_points.stop_loss"])
        self.assertEqual(
            result.dashboard["battle_plan"]["sniper_points"]["stop_loss"],
            "daibuchong",
        )

    def test_fills_stop_loss_when_invalid_type(self) -> None:
        """Placeholder fills stop_loss when value is invalid type."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="mairu",
            analysis_summary="wenjian",
            decision_type="buy",
            dashboard={"battle_plan": {"sniper_points": {"stop_loss": {}}}},
        )
        apply_placeholder_fill(result, ["dashboard.battle_plan.sniper_points.stop_loss"])
        self.assertEqual(
            result.dashboard["battle_plan"]["sniper_points"]["stop_loss"],
            "daibuchong",
        )

    def test_fills_none_dashboard_blocks_from_existing_context(self) -> None:
        """Placeholder fill handles null dashboard blocks and reuses existing result text."""
        result = AnalysisResult(
            code="600519",
            name="guizhoumaotai",
            trend_prediction="kanduo",
            sentiment_score=70,
            operation_advice="mairu",
            analysis_summary="yiyouqushizhaiyao",
            risk_warning="diepozhichengxujiancang",
            decision_type="buy",
            dashboard={
                "core_conclusion": None,
                "intelligence": None,
                "battle_plan": None,
            },
        )

        apply_placeholder_fill(
            result,
            [
                "dashboard.core_conclusion.one_sentence",
                "dashboard.intelligence.risk_alerts",
                "dashboard.battle_plan.sniper_points.stop_loss",
            ],
        )

        self.assertEqual(result.dashboard["core_conclusion"]["one_sentence"], "yiyouqushizhaiyao")
        self.assertEqual(result.dashboard["intelligence"]["risk_alerts"], ["diepozhichengxujiancang"])
        self.assertEqual(result.dashboard["battle_plan"]["sniper_points"]["stop_loss"], "daibuchong")


class TestIntegrityRetryPrompt(unittest.TestCase):
    """Retry prompt construction tests."""

    def test_retry_prompt_includes_previous_response(self) -> None:
        """Retry prompt should carry previous response sobuquanshizengliangde。"""
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()
        prompt = analyzer._build_integrity_retry_prompt(
            "yuanshitishi",
            '{"analysis_summary": "yiyouneirong"}',
            ["dashboard.core_conclusion.one_sentence"],
        )
        self.assertIn("yuanshitishi", prompt)
        self.assertIn('{"analysis_summary": "yiyouneirong"}', prompt)
        self.assertIn("dashboard.core_conclusion.one_sentence", prompt)
