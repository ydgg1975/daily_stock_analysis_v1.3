# -*- coding: utf-8 -*-
"""
===================================
Report Engine - Report renderer tests
===================================

Tests for Jinja2 report rendering and fallback behavior.
"""

import sys
import unittest
from unittest.mock import MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.analyzer import AnalysisResult
from src.services.report_renderer import render


def _make_result(
    code: str = "600519",
    name: str = "贵州茅台",
    sentiment_score: int = 72,
    operation_advice: str = "持有",
    analysis_summary: str = "稳健",
    decision_type: str = "hold",
    dashboard: dict = None,
    report_language: str = "zh",
) -> AnalysisResult:
    if dashboard is None:
        dashboard = {
            "core_conclusion": {"one_sentence": "持有观望"},
            "intelligence": {"risk_alerts": []},
            "battle_plan": {"sniper_points": {"stop_loss": "110"}},
        }
    return AnalysisResult(
        code=code,
        name=name,
        trend_prediction="看多",
        sentiment_score=sentiment_score,
        operation_advice=operation_advice,
        analysis_summary=analysis_summary,
        decision_type=decision_type,
        dashboard=dashboard,
        report_language=report_language,
    )


class TestReportRenderer(unittest.TestCase):
    """Report renderer tests."""

    def test_render_markdown_summary_only(self) -> None:
        """Markdown platform renders with summary_only."""
        r = _make_result()
        out = render("markdown", [r], summary_only=True)
        self.assertIsNotNone(out)
        self.assertIn("决策仪表盘", out)
        self.assertIn("贵州茅台", out)
        self.assertIn("持有", out)

    def test_render_markdown_full(self) -> None:
        """Markdown platform renders full report."""
        r = _make_result()
        out = render("markdown", [r], summary_only=False)
        self.assertIsNotNone(out)
        self.assertIn("核心结论", out)
        self.assertIn("作战计划", out)

    def test_render_wechat(self) -> None:
        """Wechat platform renders."""
        r = _make_result()
        out = render("wechat", [r])
        self.assertIsNotNone(out)
        self.assertIn("贵州茅台", out)

    def test_render_brief(self) -> None:
        """Brief platform renders 3-5 sentence summary."""
        r = _make_result()
        out = render("brief", [r])
        self.assertIsNotNone(out)
        self.assertIn("决策简报", out)
        self.assertIn("贵州茅台", out)

    def test_render_markdown_in_english(self) -> None:
        """Markdown renderer switches headings and summary labels for English reports."""
        r = _make_result(
            name="Kweichow Moutai",
            operation_advice="Buy",
            analysis_summary="Momentum remains constructive.",
            report_language="en",
        )
        out = render("markdown", [r], summary_only=True)
        self.assertIsNotNone(out)
        self.assertIn("Decision Dashboard", out)
        self.assertIn("Summary", out)
        self.assertIn("Buy", out)

    def test_render_markdown_market_snapshot_uses_template_context(self) -> None:
        """Market snapshot macro should render localized labels with template context."""
        r = _make_result(
            code="AAPL",
            name="Apple",
            operation_advice="Buy",
            report_language="en",
        )
        r.market_snapshot = {
            "close": "180.10",
            "prev_close": "178.25",
            "open": "179.00",
            "high": "181.20",
            "low": "177.80",
            "pct_chg": "+1.04%",
            "change_amount": "1.85",
            "amplitude": "1.91%",
            "volume": "1200000",
            "amount": "215000000",
            "price": "180.35",
            "volume_ratio": "1.2",
            "turnover_rate": "0.8%",
            "source": "polygon",
        }

        out = render("markdown", [r], summary_only=False)

        self.assertIsNotNone(out)
        self.assertIn("Market Snapshot", out)
        self.assertIn("Volume Ratio", out)

    def test_render_markdown_us_stock_chip_not_supported_and_turnover_missing(self) -> None:
        r = _make_result(
            code="AAPL",
            name="Apple",
            report_language="zh",
            dashboard={
                "core_conclusion": {"one_sentence": "观望"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "170"}},
                "data_perspective": {
                    "volume_analysis": {
                        "volume_ratio": 0.8,
                        "volume_status": "正常",
                        "turnover_rate": "N/A",
                        "volume_meaning": "量能平稳",
                    },
                    "chip_structure": {"profit_ratio": "N/A"},
                },
            },
        )
        out = render("markdown", [r], summary_only=False)
        self.assertIn("筹码", out)
        self.assertIn("美股暂不支持该指标", out)
        self.assertIn("换手率 数据缺失", out)

    def test_render_markdown_missing_ma_and_bias_with_alpha_vantage_supplement(self) -> None:
        r = _make_result(
            code="MSTR",
            name="MicroStrategy",
            report_language="zh",
            dashboard={
                "core_conclusion": {"one_sentence": "观望"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "120"}},
                "data_perspective": {
                    "price_position": {
                        "current_price": 130.5,
                        "ma5": 0.0,
                        "ma10": 0.0,
                        "ma20": None,
                        "bias_ma5": 0.0,
                        "support_level": None,
                        "resistance_level": None,
                    },
                    "volume_analysis": {
                        "volume_ratio": 0.0,
                        "turnover_rate": None,
                        "volume_status": "缺失",
                    },
                    "alpha_vantage": {
                        "rsi14": 47.7279,
                        "sma20": 138.406,
                        "sma60": 144.9608,
                    },
                },
            },
        )
        out = render("markdown", [r], summary_only=False)
        self.assertIn("N/A（Alpha Vantage SMA20: 138.406）", out)
        self.assertIn("乖离率(MA5) | 数据缺失", out)
        self.assertIn("量比 数据缺失", out)
        self.assertIn("换手率 数据缺失", out)

    def test_render_uses_asia_shanghai_timestamp(self) -> None:
        r = _make_result()
        fixed = datetime(2026, 3, 25, 9, 30, 15, tzinfo=ZoneInfo("Asia/Shanghai"))
        with unittest.mock.patch("src.services.report_renderer._now_shanghai", return_value=fixed):
            out = render("markdown", [r], summary_only=False)
        self.assertIn("2026-03-25 09:30:15", out)
        self.assertIn("report_generated_at", out)

    def test_render_prefers_time_contract_fields(self) -> None:
        r = _make_result(code="AAPL", name="Apple")
        out = render(
            "markdown",
            [r],
            summary_only=True,
            extra_context={
                "report_generated_at": "2026-03-25T01:00:00+00:00",
                "market_timestamp": "2026-03-24T21:00:00-04:00",
                "market_session_date": "2026-03-24",
                "news_published_at": "2026-03-24T20:00:00-04:00",
            },
        )
        self.assertIn("2026-03-25T01:00:00+00:00", out)
        self.assertIn("2026-03-24T21:00:00-04:00", out)
        self.assertIn("2026-03-24", out)

    def test_render_unknown_platform_returns_none(self) -> None:
        """Unknown platform returns None (caller fallback)."""
        r = _make_result()
        out = render("unknown_platform", [r])
        self.assertIsNone(out)

    def test_render_empty_results_returns_content(self) -> None:
        """Empty results still produces header."""
        out = render("markdown", [], summary_only=True)
        self.assertIsNotNone(out)
        self.assertIn("0", out)
