# -*- coding: utf-8 -*-
"""Tests for standard report rendering pipeline."""

import sys
import unittest
from unittest.mock import MagicMock

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.analyzer import AnalysisResult
from src.services.report_renderer import render


def _make_result(
    *,
    code: str = "AAPL",
    name: str = "Apple",
    report_language: str = "zh",
    market_snapshot: dict | None = None,
    dashboard: dict | None = None,
    trend_prediction: str = "看多",
) -> AnalysisResult:
    dashboard = dashboard or {
        "core_conclusion": {
            "one_sentence": "等待确认",
            "time_sensitivity": "3日内",
            "position_advice": {
                "no_position": "等待回踩确认",
                "has_position": "继续持有",
            },
        },
        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "120-121",
                "secondary_buy": "118",
                "stop_loss": "115",
                "take_profit": "132",
            },
            "action_checklist": ["⚠️ 等待回踩 MA5"],
        },
        "intelligence": {
            "risk_alerts": ["监管调查进展"],
            "positive_catalysts": ["公司获重大订单"],
            "latest_news": "公司发布季度财报并上调指引",
            "sentiment_summary": "市场情绪回暖",
            "earnings_outlook": "业绩预期改善",
        },
        "data_perspective": {
            "trend_status": {"is_bullish": True, "trend_score": 72},
            "price_position": {
                "ma5": 123.4567,
                "ma10": 122.1234,
                "ma20": 120.9876,
                "support_level": 119.1111,
                "resistance_level": 128.9999,
                "bias_ma5": 1.23456,
                "vwap": 124.9876,
            },
            "volume_analysis": {
                "volume_ratio": 1.35,
                "turnover_rate": 0.88,
                "volume_status": "放量",
                "volume_meaning": "资金关注提升",
            },
            "alpha_vantage": {
                "rsi14": 56.777,
                "sma20": 121.335,
                "sma60": 118.882,
            },
        },
        "structured_analysis": {
            "fundamentals": {
                "normalized": {
                    "marketCap": 123400000000,
                    "trailingPE": 21.3333,
                    "forwardPE": 19.8888,
                    "beta": 1.2345,
                    "fiftyTwoWeekHigh": 199.876,
                    "fiftyTwoWeekLow": 99.123,
                    "sharesOutstanding": 5000000000,
                    "revenueGrowth": 0.12,
                    "freeCashflow": 4567000000,
                }
            },
            "earnings_analysis": {
                "derived_metrics": {
                    "qoq_revenue_growth": 0.05,
                    "yoy_revenue_growth": 0.12,
                    "qoq_net_income_change": 0.04,
                    "yoy_net_income_change": 0.09,
                }
            },
            "sentiment_analysis": {
                "company_sentiment": "positive",
                "industry_sentiment": "neutral",
                "regulatory_sentiment": "neutral",
                "overall_confidence": "medium",
            },
        },
    }

    market_snapshot = market_snapshot or {
        "price": 125.3,
        "close": 124.0,
        "prev_close": 123.0,
        "open": 123.5,
        "high": 126.2,
        "low": 122.9,
        "change_amount": 2.3,
        "pct_chg": 1.87,
        "volume": 4500000,
        "amount": 880000000,
        "session_type": "intraday_snapshot",
        "source": "unit-test",
    }

    return AnalysisResult(
        code=code,
        name=name,
        sentiment_score=68,
        trend_prediction=trend_prediction,
        operation_advice="持有",
        analysis_summary="观望",
        decision_type="hold",
        report_language=report_language,
        dashboard=dashboard,
        market_snapshot=market_snapshot,
    )


class TestReportRenderer(unittest.TestCase):
    def test_render_contains_required_sections(self) -> None:
        out = render("markdown", [_make_result()], summary_only=False)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertIn("1. 标题区", out)
        self.assertIn("2. 重要信息速览", out)
        self.assertIn("3. 持仓建议", out)
        self.assertIn("4. 当日行情", out)
        self.assertIn("5. 技术面", out)
        self.assertIn("6. 基本面 / 财报 / 情绪", out)
        self.assertIn("7. 作战计划", out)
        self.assertIn("8. 检查清单", out)

    def test_regular_change_uses_price_minus_prev_close(self) -> None:
        r = _make_result(
            market_snapshot={
                "price": 110,
                "close": 109,
                "prev_close": 100,
                "open": 101,
                "high": 112,
                "low": 99,
                "session_type": "intraday_snapshot",
            }
        )
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("**涨跌额**: 10.00", out)
        self.assertIn("**涨跌幅**: 10.00%", out)

    def test_regular_and_extended_sessions_are_separated(self) -> None:
        r = _make_result(
            market_snapshot={
                "price": 105,
                "close": 100,
                "prev_close": 95,
                "open": 96,
                "high": 106,
                "low": 94,
                "session_type": "after_hours",
                "extended_timestamp": "2026-03-27T20:00:00-04:00",
            }
        )
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("**当前价**: 100.00", out)  # regular section uses close
        self.assertIn("**扩展时段价格**: 105.00", out)
        self.assertIn("**会话标签**: 盘后", out)

    def test_conflict_outputs_reasoned_na(self) -> None:
        r = _make_result(
            market_snapshot={
                "price": 110,
                "prev_close": 100,
                "regular_change": 20,
                "regular_change_pct": 20,
                "session_type": "intraday_snapshot",
            }
        )
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("NA（口径冲突，待校正）", out)

    def test_numeric_display_is_rounded(self) -> None:
        out = render("markdown", [_make_result()], summary_only=False)
        assert out is not None
        self.assertIn("**MA5**: 123.46", out)
        self.assertIn("**支撑位**: 119.11", out)
        self.assertIn("**RSI14**: 56.78", out)
        self.assertNotIn("123.4567", out)

    def test_missing_values_use_reasoned_na(self) -> None:
        r = _make_result(
            market_snapshot={
                "price": None,
                "close": None,
                "prev_close": None,
                "session_type": "intraday_snapshot",
            },
            dashboard={"core_conclusion": {}, "battle_plan": {}, "intelligence": {}},
        )
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("NA（接口未返回）", out)
        self.assertNotIn("N/A", out)
        self.assertNotIn("数据缺失", out)

    def test_trade_level_annotation_and_risk_warning(self) -> None:
        r = _make_result(
            market_snapshot={
                "price": 100,
                "close": 100,
                "prev_close": 98,
                "session_type": "intraday_snapshot",
            },
            dashboard={
                "core_conclusion": {},
                "intelligence": {},
                "battle_plan": {
                    "sniper_points": {
                        "ideal_buy": "105",
                        "secondary_buy": "95",
                        "stop_loss": "110",
                        "take_profit": "125",
                    }
                },
            },
            trend_prediction="看多",
        )
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("突破买点", out)
        self.assertIn("回踩买点", out)
        self.assertIn("做多语境下止损位不能高于当前价", out)
        self.assertIn("当前价已跌破关键防守位", out)

    def test_key_metrics_present_or_reasoned_na(self) -> None:
        r = _make_result()
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("**VWAP**:", out)
        self.assertIn("**成交额**:", out)
        self.assertIn("**均价**:", out)
        self.assertIn("**52w high**:", out)
        self.assertIn("**Beta**:", out)
        self.assertIn("**totalShares / sharesOutstanding**:", out)

    def test_news_value_grading_filters_low_value_items(self) -> None:
        r = _make_result(
            dashboard={
                "core_conclusion": {},
                "battle_plan": {},
                "intelligence": {
                    "positive_catalysts": ["公司参加品牌活动"],
                    "latest_news": "高管出席品牌活动",
                },
            },
        )
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("未发现高价值新增催化", out)
        self.assertIn("未发现高价值新增动态", out)
        self.assertIn("低价值已降权", out)

    def test_summary_only_still_renders_dashboard_summary(self) -> None:
        out = render("markdown", [_make_result()], summary_only=True)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertIn("分析结果摘要", out)
        self.assertNotIn("1. 标题区", out)

    def test_english_report_uses_english_title_labels(self) -> None:
        r = _make_result(report_language="en", name="Unnamed Stock", code="TSLA")
        out = render("markdown", [r], summary_only=True)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertIn("Decision Dashboard", out)
        self.assertIn("Stock Analysis Report", out)


if __name__ == "__main__":
    unittest.main()
