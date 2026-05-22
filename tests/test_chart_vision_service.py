# -*- coding: utf-8 -*-
"""Tests for Vision model chart analysis."""

from types import SimpleNamespace
from unittest.mock import patch

from src.services import image_stock_extractor as vision_core
from src.services.chart_vision_service import ChartVisionAnalysisService


def _vision_response(content: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ]
    )


def test_chart_vision_degrades_without_model():
    with patch("src.services.image_stock_extractor._resolve_vision_model", return_value=""):
        result = ChartVisionAnalysisService().analyze_chart_image(
            stock_code="AAPL",
            image_content="<svg></svg>",
            image_format="svg",
        )

    assert result["status"] == "not_configured"


def test_chart_vision_sends_svg_data_url_to_litellm():
    completion = patch.object(
        vision_core.litellm,
        "completion",
        return_value=_vision_response(
            '{"trend":"bullish","pattern":"breakout","support_resistance":"support visible","risk_notes":["overextended"],"confidence":"medium","uncertainty":"volume is mixed"}'
        ),
    )
    with patch("src.services.image_stock_extractor._resolve_vision_model", return_value="openai/test-vision"), \
            patch("src.services.image_stock_extractor._get_api_keys_for_model", return_value=["sk-test"]), \
            completion as mock_completion:
        result = ChartVisionAnalysisService().analyze_chart_image(
            stock_code="AAPL",
            image_content="<svg><text>AAPL</text></svg>",
            image_format="svg",
            numeric_metadata={"support": 100},
        )

    assert result["status"] == "ok"
    assert result["analysis"]["trend"] == "bullish"
    assert result["comparison"]["agreement"] == "numeric_unclear"
    assert result["comparison"]["vision_signal"] == "bullish"
    assert result["comparison"]["numeric_signal"] == "unknown"
    assert result["evidence"]["confidence"] == "medium"
    assert result["evidence"]["uncertainty"] == "volume is mixed"
    assert any(item["type"] == "support_resistance" for item in result["evidence"]["evidence_items"])
    content = mock_completion.call_args.kwargs["messages"][0]["content"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/svg+xml;base64,")


def test_chart_vision_comparison_detects_signal_conflict():
    comparison = ChartVisionAnalysisService.compare_with_numeric_analysis(
        {"trend": "bearish", "pattern": "breakdown"},
        {
            "visual_signal": "bullish",
            "indicator_signal": "bullish",
            "pattern": {"name": "five_bar_breakout"},
        },
    )

    assert comparison["agreement"] == "conflict"
    assert comparison["vision_signal"] == "bearish"
    assert comparison["numeric_signal"] == "bullish"
    assert comparison["conflicts"][0]["type"] == "signal_mismatch"


def test_chart_vision_comparison_marks_strong_match():
    comparison = ChartVisionAnalysisService.compare_with_numeric_analysis(
        {"trend": "bullish", "pattern": "five bar breakout"},
        {
            "visual_signal": "bullish",
            "indicator_signal": "bullish",
            "pattern": {"name": "five_bar_breakout"},
        },
    )

    assert comparison["agreement"] == "strong"
    assert comparison["conflicts"] == []


def test_chart_vision_evidence_summary_marks_uncertainty_from_conflicts():
    comparison = {
        "conflicts": [
            {"type": "signal_mismatch"},
        ]
    }
    evidence = ChartVisionAnalysisService.build_evidence_summary(
        {
            "pattern": "breakout",
            "support_resistance": "price holds above support",
            "risk_notes": ["RSI looks extended"],
            "confidence": "low",
            "uncertainty": "volume confirmation is weak",
        },
        comparison,
    )

    assert evidence["confidence"] == "low"
    assert evidence["conflict_count"] == 1
    assert "Vision model reported low confidence." in evidence["uncertainty_flags"]
    assert "Vision and numeric chart analysis disagree." in evidence["uncertainty_flags"]
    assert len(evidence["evidence_items"]) == 3
