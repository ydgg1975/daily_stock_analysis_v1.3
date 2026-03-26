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
    market_snapshot: dict = None,
    current_price: float = None,
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
        market_snapshot=market_snapshot,
        current_price=current_price,
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
        r.trend_prediction = "看多"
        out = render("markdown", [r], summary_only=False)
        self.assertIn("筹码", out)
        self.assertIn("NA（当前市场暂不支持）", out)
        self.assertIn("换手率 NA（字段待接入）", out)

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
        self.assertIn("NA（接口未返回）（Alpha Vantage SMA20: 138.41）", out)
        self.assertIn("乖离率(MA5) | 0.00%", out)
        self.assertIn("量比 NA（接口未返回）", out)
        self.assertIn("换手率 NA（字段待接入）", out)

    def test_render_uses_asia_shanghai_timestamp(self) -> None:
        r = _make_result()
        fixed = datetime(2026, 3, 25, 9, 30, 15, tzinfo=ZoneInfo("Asia/Shanghai"))
        with unittest.mock.patch("src.services.report_renderer._now_shanghai", return_value=fixed):
            out = render("markdown", [r], summary_only=False)
        self.assertIn("2026-03-25 09:30:15", out)
        self.assertIn("报告生成时间（北京时间）", out)

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
                "session_type": "last_completed_session",
                "news_published_at": "2026-03-24T20:00:00-04:00",
            },
        )
        self.assertIn("2026-03-25 09:00:00", out)
        self.assertIn("2026-03-24T21:00:00-04:00", out)
        self.assertIn("2026-03-24", out)
        self.assertIn("last_completed_session", out)

    def test_render_uses_time_context_when_extra_context_missing(self) -> None:
        r = _make_result(
            code="TSLA",
            name="Tesla",
            dashboard={
                "core_conclusion": {"one_sentence": "观望"},
                "intelligence": {},
                "battle_plan": {"sniper_points": {"stop_loss": "200"}},
                "structured_analysis": {
                    "time_context": {
                        "market_timestamp": "2026-03-25T16:00:00-04:00",
                        "market_session_date": "2026-03-25",
                        "report_generated_at": "2026-03-26T08:30:00+08:00",
                        "session_type": "last_completed_session",
                    }
                },
            },
        )
        out = render("markdown", [r], summary_only=True)
        self.assertIn("2026-03-25T16:00:00-04:00", out)
        self.assertIn("2026-03-25", out)
        self.assertIn("last_completed_session", out)

    def test_render_structured_blocks_fundamentals_earnings_sentiment(self) -> None:
        r = _make_result(
            code="ORCL",
            name="Oracle",
            dashboard={
                "core_conclusion": {"one_sentence": "观望"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {"sniper_points": {"stop_loss": "100"}},
                "structured_analysis": {
                    "time_context": {
                        "market_timestamp": "2026-03-24T21:00:00-04:00",
                        "market_session_date": "2026-03-24",
                        "report_generated_at": "2026-03-25T01:00:00+00:00",
                        "news_published_at": "2026-03-24T20:00:00-04:00",
                        "session_type": "intraday_snapshot",
                    },
                    "fundamentals": {
                        "normalized": {"marketCap": 1000000, "trailingPE": 22.1, "revenueGrowth": 0.12},
                        "derived_insights": ["valuation_high", "high_growth"],
                    },
                    "earnings_analysis": {
                        "derived_metrics": {"qoq_revenue_growth": 0.05, "yoy_net_income_change": 0.08},
                        "summary_flags": ["quarterly_series_available"],
                        "narrative_insights": ["margins improving"],
                    },
                    "sentiment_analysis": {
                        "company_sentiment": "positive",
                        "industry_sentiment": "background_only",
                        "regulatory_sentiment": "neutral",
                        "overall_confidence": "medium",
                        "relevance_type": "company_specific",
                        "relevance_score": 0.82,
                    },
                    "data_quality": {"fundamentals_status": "ok", "warnings": []},
                },
            },
        )
        out = render("markdown", [r], summary_only=False)
        self.assertIn("基本面摘要（Fundamentals）", out)
        self.assertIn("财报趋势（Earnings）", out)
        self.assertIn("结构化情绪（Sentiment）", out)
        self.assertIn("session_type: intraday_snapshot", out)

    def test_render_industry_news_not_presented_as_company_latest_news(self) -> None:
        r = _make_result(
            code="TEM",
            name="Tempus AI",
            dashboard={
                "core_conclusion": {"one_sentence": "观望"},
                "intelligence": {
                    "latest_news": "Anthropic faces new regulation inquiry.",
                    "risk_alerts": ["监管动态"],
                    "positive_catalysts": ["行业合作扩张"],
                },
                "battle_plan": {"sniper_points": {"stop_loss": "30"}},
                "structured_analysis": {
                    "sentiment_analysis": {
                        "relevance_type": "industry_general",
                        "company_sentiment": "no_reliable_news",
                        "industry_sentiment": "neutral",
                        "regulatory_sentiment": "neutral",
                        "overall_confidence": "low",
                    }
                },
            },
        )
        out = render("markdown", [r], summary_only=False)
        self.assertIn("行业背景", out)
        self.assertNotIn("📢 最新动态", out)

    def test_render_unknown_platform_returns_none(self) -> None:
        """Unknown platform returns None (caller fallback)."""
        r = _make_result()
        out = render("unknown_platform", [r])
        self.assertIsNone(out)

    def test_render_structured_sections_are_explicit_even_when_missing(self) -> None:
        r = _make_result(
            dashboard={
                "core_conclusion": {"one_sentence": "观望"},
                "intelligence": {},
                "battle_plan": {"sniper_points": {"stop_loss": "100"}},
                "structured_analysis": {},
            }
        )
        out = render("markdown", [r], summary_only=False)
        self.assertIn("基本面摘要（Fundamentals）", out)
        self.assertIn("财报趋势（Earnings）", out)
        self.assertIn("结构化情绪（Sentiment）", out)
        self.assertIn("数据质量说明", out)

    def test_render_empty_results_returns_content(self) -> None:
        """Empty results still produces header."""
        out = render("markdown", [], summary_only=True)
        self.assertIsNotNone(out)
        self.assertIn("0", out)


    def test_render_market_snapshot_recomputes_inconsistent_change_fields(self) -> None:
        r = _make_result(code="AAPL", name="Apple", market_snapshot={
            "price": 100.0,
            "close": 100.0,
            "prev_close": 90.0,
            "change_amount": 1.0,
            "pct_chg": 1.0,
        })
        out = render("markdown", [r], summary_only=False)
        self.assertIn("10.00", out)
        self.assertIn("11.11%", out)
        self.assertIn("口径校验", out)

    def test_render_trade_level_annotations_and_risk_warning(self) -> None:
        r = _make_result(
            code="AAPL",
            name="Apple",
            current_price=100.0,
            market_snapshot={"price": 100.0},
            dashboard={
                "core_conclusion": {"one_sentence": "观望"},
                "intelligence": {"risk_alerts": []},
                "battle_plan": {
                    "sniper_points": {
                        "ideal_buy": "105",
                        "secondary_buy": "95",
                        "stop_loss": "102",
                        "take_profit": "120",
                    }
                },
            },
        )
        out = render("markdown", [r], summary_only=False)
        self.assertIn("突破买点", out)
        self.assertIn("回踩买点", out)
        self.assertIn("止损位高于当前价", out)


    def test_render_filters_low_value_news_and_catalyst(self) -> None:
        r = _make_result(
            code="AAPL",
            name="Apple",
            dashboard={
                "core_conclusion": {"one_sentence": "观望"},
                "intelligence": {
                    "sentiment_summary": "中性",
                    "positive_catalysts": ["公司参加品牌活动"],
                    "latest_news": "CEO 出席公开活动并接受采访",
                },
                "battle_plan": {"sniper_points": {"stop_loss": "90"}},
            },
        )
        out = render("markdown", [r], summary_only=False)
        self.assertIn("未发现高价值新增催化", out)
        self.assertIn("未发现高价值新增动态", out)
