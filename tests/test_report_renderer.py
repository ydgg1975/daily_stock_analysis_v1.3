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
from src.services.report_renderer import build_standard_report_payload, render


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
        self.assertIn("Part A. Executive Summary", out)
        self.assertIn("Part B. Action Plan", out)
        self.assertIn("Part C. Events / Sentiment / News", out)
        self.assertIn("Part D. Evidence", out)
        self.assertIn("Part E. Source / Coverage / Method Notes", out)

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
        self.assertIn("**Change**: 10.00", out)
        self.assertIn("**Change %**: 10.00%", out)

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
        self.assertIn("**Analysis Price**: 100.00", out)
        self.assertIn("**扩展时段价格**: 105.00", out)
        self.assertIn("**会话标签**: 盘后", out)

    def test_summary_panel_exposes_user_facing_price_basis_labels(self) -> None:
        payload = build_standard_report_payload(_make_result(), report_language="zh")
        summary = payload["summary_panel"]
        self.assertEqual(summary["price_label"], "Analysis Price")
        self.assertEqual(summary["price_basis"], "Intraday snapshot")
        self.assertIn("market snapshot", summary["price_basis_detail"])
        self.assertTrue(summary["reference_session"])

    def test_completed_session_uses_completed_close_basis_label(self) -> None:
        payload = build_standard_report_payload(
            _make_result(
                market_snapshot={
                    "close": 124,
                    "prev_close": 121,
                    "open": 122,
                    "high": 125,
                    "low": 120,
                    "session_type": "last_completed_session",
                }
            ),
            report_language="zh",
        )
        summary = payload["summary_panel"]
        self.assertEqual(summary["price_basis"], "Last close")
        self.assertIn("last completed session close", payload["market"]["time_context"]["price_context_note"])

    def test_material_conflict_prefers_recomputed_change_and_keeps_warning(self) -> None:
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
        self.assertIn("**Change**: 10.00", out)
        self.assertIn("**Change %**: 10.00%", out)
        self.assertIn("常规时段多源涨跌口径存在较大偏差", out)

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
        payload = build_standard_report_payload(r, report_language="zh")
        decision_panel = payload["decision_panel"]

        self.assertEqual(decision_panel["setup_type"], "趋势延续 / 等回踩")
        self.assertIn("技术失效位", decision_panel["stop_loss"])
        self.assertIn("95.00", decision_panel["support"])
        self.assertIn("125.00", decision_panel["resistance"])
        self.assertNotIn("110", decision_panel["stop_loss"])

    def test_social_synthesis_fills_highlights_even_when_no_hard_news(self) -> None:
        result = _make_result(
            dashboard={
                "core_conclusion": {},
                "battle_plan": {},
                "intelligence": {
                    "social_context": (
                        "📱 Social Sentiment Intelligence for NVDA (Reddit / X / Polymarket)\n"
                        "Buzz Score: 74/100\n"
                        "Sentiment Score: 0.12\n"
                        "Mentions: 180\n"
                        "Top Mentions:\n"
                        "1. \"AI demand remains strong and traders are watching the breakout level\""
                    ),
                },
                "structured_analysis": {
                    "sentiment_analysis": {
                        "company_sentiment": "neutral",
                        "industry_sentiment": "positive",
                        "regulatory_sentiment": "neutral",
                    },
                },
            },
        )
        payload = build_standard_report_payload(result, report_language="zh")
        highlights = payload["highlights"]
        self.assertIn("LLM 综合讨论摘要", highlights["social_synthesis"])
        self.assertEqual(highlights["social_tone"], "mixed")
        self.assertEqual(highlights["social_attention"], "discussion appears elevated")
        self.assertIn("AI demand remains strong", highlights["social_narrative_focus"])

    def test_key_metrics_present_or_reasoned_na(self) -> None:
        r = _make_result()
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("**VWAP**:", out)
        self.assertIn("**Turnover**:", out)
        self.assertIn("**Avg Price**:", out)
        self.assertIn("**52周最高**:", out)
        self.assertIn("**Beta系数**:", out)
        self.assertIn("**总股本**:", out)

    def test_renderer_consumes_structured_context_fallbacks(self) -> None:
        r = _make_result(
            market_snapshot={"session_type": "intraday_snapshot"},
            dashboard={
                "core_conclusion": {"one_sentence": "等待确认"},
                "battle_plan": {},
                "intelligence": {},
                "structured_analysis": {
                    "time_context": {"session_type": "intraday_snapshot"},
                    "market_context": {
                        "today": {
                            "close": 125.3,
                            "open": 123.5,
                            "high": 126.2,
                            "low": 122.9,
                            "pct_chg": 1.87,
                            "volume": 4500000,
                            "amount": 880000000,
                            "ma5": 123.4567,
                            "ma10": 122.1234,
                            "ma20": 120.9876,
                        },
                        "yesterday": {"close": 123.0},
                    },
                    "realtime_context": {
                        "price": 125.3,
                        "volume_ratio": 1.35,
                        "turnover_rate": 0.88,
                        "source": "yfinance",
                        "vwap": 124.9876,
                        "pb_ratio": 9.87,
                        "total_mv": 123400000000,
                        "circ_mv": 100000000000,
                    },
                    "technicals": {
                        "ma5": {"value": 123.4567, "status": "ok"},
                        "ma10": {"value": 122.1234, "status": "ok"},
                        "ma20": {"value": 120.9876, "status": "ok"},
                        "rsi14": {"value": 56.777, "status": "ok"},
                    },
                    "fundamental_context": {
                        "valuation": {
                            "data": {
                                "market_cap": 123400000000,
                                "pb_ratio": 9.87,
                                "shares_outstanding": 5000000000,
                                "52week_high": 199.876,
                                "52week_low": 99.123,
                                "beta": 1.2345,
                            }
                        },
                        "earnings": {
                            "data": {
                                "financial_report": {
                                    "revenue": 10000000000,
                                    "net_income": 2500000000,
                                }
                            }
                        },
                    },
                    "earnings_analysis": {
                        "quarterly_series": [{"revenue": 10000000000, "net_income": 2500000000}],
                        "derived_metrics": {"yoy_net_income_change": 0.12},
                    },
                },
            },
        )
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("**Prev Close**: 123.00", out)
        self.assertIn("**Volume**: 450.00万", out)
        self.assertIn("**MA5**: 123.46", out)
        self.assertIn("**MA10**: 122.12", out)
        self.assertIn("**VWAP**: 124.99", out)
        self.assertIn("**市净率(最新值)**: 9.87", out)
        self.assertIn("**52周最高**: 199.88", out)
        self.assertIn("**净利润(TTM)**: 25.00亿", out)

    def test_standard_report_localizes_user_visible_labels_to_chinese(self) -> None:
        payload = build_standard_report_payload(_make_result(), report_language="zh")
        fundamental_labels = [item["label"] for item in payload["fundamental_fields"]]
        earnings_labels = [item["label"] for item in payload["earnings_fields"]]
        sentiment = {item["label"]: item["value"] for item in payload["sentiment_fields"]}

        self.assertIn("市盈率(TTM)", fundamental_labels)
        self.assertTrue(any(label.startswith("预期市盈率") for label in fundamental_labels))
        self.assertTrue(any(label.startswith("市净率") for label in fundamental_labels))
        self.assertTrue(any(label.startswith("总股本") for label in fundamental_labels))
        self.assertFalse(any(label.startswith("营收增速") for label in fundamental_labels))
        self.assertTrue(any(label.startswith("营收环比增速") for label in earnings_labels))
        self.assertTrue(any(label.startswith("净利润同比变化") for label in earnings_labels))
        self.assertEqual(sentiment["公司情绪"], "积极")
        self.assertEqual(sentiment["置信度"], "中")

    def test_standard_report_separates_ttm_and_latest_quarter_basis(self) -> None:
        payload = build_standard_report_payload(
            _make_result(
                dashboard={
                    "core_conclusion": {"one_sentence": "等待确认"},
                    "battle_plan": {},
                    "intelligence": {
                        "earnings_outlook": "原始摘要不应直接覆盖口径说明",
                    },
                    "structured_analysis": {
                        "fundamentals": {
                            "normalized": {
                                "revenueGrowth": -0.031,
                                "netIncomeGrowth": -0.606,
                            },
                            "field_periods": {
                                "revenueGrowth": "ttm_yoy",
                                "netIncomeGrowth": "ttm_yoy",
                            },
                        },
                        "earnings_analysis": {
                            "derived_metrics": {
                                "yoy_revenue_growth": 0.2879,
                                "yoy_net_income_change": 1.0538,
                            }
                        },
                    },
                },
            ),
            report_language="zh",
        )
        earnings_outlook = payload["highlights"]["earnings_outlook"]
        earnings_fields = {item["label"]: item["value"] for item in payload["earnings_fields"]}

        self.assertIn("TTM口径仍承压", earnings_outlook)
        self.assertIn("最新季度同比口径为营收同比28.79%、净利润同比105.38%", earnings_outlook)
        self.assertIn("两者口径不同，需分开解读", earnings_outlook)
        self.assertEqual(
            earnings_fields["财报趋势摘要(最新季度)"],
            "最新季度同比口径：营收与利润同向改善。",
        )

    def test_fundamental_fields_expose_ttm_source_for_fcf_and_roe_roa(self) -> None:
        payload = build_standard_report_payload(
            _make_result(
                dashboard={
                    "core_conclusion": {"one_sentence": "等待确认"},
                    "battle_plan": {},
                    "intelligence": {},
                    "structured_analysis": {
                        "fundamentals": {
                            "normalized": {
                                "freeCashflow": 96676000000,
                                "operatingCashflow": 124430000000,
                                "returnOnEquity": 1.0148,
                                "returnOnAssets": 0.5821,
                            },
                            "field_sources": {
                                "freeCashflow": "fmp_quarterly",
                                "operatingCashflow": "fmp_quarterly",
                                "returnOnEquity": "fmp",
                                "returnOnAssets": "fmp",
                            },
                            "field_periods": {
                                "freeCashflow": "ttm",
                                "operatingCashflow": "ttm",
                                "returnOnEquity": "ttm",
                                "returnOnAssets": "ttm",
                            },
                        }
                    },
                },
            ),
            report_language="zh",
        )

        fields = {item["label"]: item for item in payload["fundamental_fields"]}

        self.assertEqual(fields["自由现金流(TTM)"]["value"], "966.76亿")
        self.assertEqual(fields["自由现金流(TTM)"]["source"], "FMP Statements")
        self.assertEqual(fields["自由现金流(TTM)"]["status"], "TTM")
        self.assertEqual(fields["ROE(TTM)"]["value"], "101.48%")
        self.assertEqual(fields["ROE(TTM)"]["source"], "FMP")
        self.assertEqual(fields["ROE(TTM)"]["status"], "TTM")
        self.assertEqual(fields["ROA(TTM)"]["value"], "58.21%")
        self.assertEqual(fields["ROA(TTM)"]["source"], "FMP")
        self.assertEqual(fields["ROA(TTM)"]["status"], "TTM")

    def test_ttm_pending_validation_fields_render_reasoned_na(self) -> None:
        payload = build_standard_report_payload(
            _make_result(
                dashboard={
                    "core_conclusion": {"one_sentence": "等待确认"},
                    "battle_plan": {},
                    "intelligence": {},
                    "structured_analysis": {
                        "fundamentals": {
                            "normalized": {
                                "freeCashflow": 96676000000,
                                "operatingCashflow": 124430000000,
                                "returnOnEquity": 1.0148,
                                "returnOnAssets": 0.5821,
                            },
                            "field_sources": {
                                "freeCashflow": "alpha_vantage_overview",
                                "operatingCashflow": "fundamental_context",
                                "returnOnEquity": "alpha_vantage_overview",
                                "returnOnAssets": "fundamental_context",
                            },
                            "field_periods": {
                                "freeCashflow": "ttm_pending_validation",
                                "operatingCashflow": "ttm_pending_validation",
                                "returnOnEquity": "ttm_pending_validation",
                                "returnOnAssets": "ttm_pending_validation",
                            },
                        }
                    },
                },
            ),
            report_language="zh",
        )

        fields = {item["label"]: item for item in payload["fundamental_fields"]}

        self.assertEqual(fields["自由现金流(TTM待复核)"]["value"], "NA（口径冲突，待校正）")
        self.assertEqual(fields["自由现金流(TTM待复核)"]["status"], "TTM待复核")
        self.assertEqual(fields["经营现金流(TTM待复核)"]["value"], "NA（口径冲突，待校正）")
        self.assertEqual(fields["ROE(TTM待复核)"]["value"], "NA（口径冲突，待校正）")
        self.assertEqual(fields["ROE(TTM待复核)"]["status"], "TTM待复核")
        self.assertEqual(fields["ROA(TTM待复核)"]["value"], "NA（口径冲突，待校正）")
        self.assertEqual(fields["ROA(TTM待复核)"]["status"], "TTM待复核")

    def test_stale_earnings_recap_is_demoted_from_latest_news(self) -> None:
        payload = build_standard_report_payload(
            _make_result(
                dashboard={
                    "core_conclusion": {"one_sentence": "等待确认"},
                    "battle_plan": {},
                    "intelligence": {
                        "positive_catalysts": ["公司获重大订单"],
                        "latest_news": "2026-02-25 财报解读：营收与利润大幅超预期，AI 业务继续高增。",
                    },
                    "structured_analysis": {
                        "time_context": {
                            "market_session_date": "2026-03-28",
                            "news_published_at": "2026-02-25T16:05:00-04:00",
                        },
                        "fundamentals": {
                            "normalized": {
                                "revenueGrowth": 0.22,
                                "netIncomeGrowth": 0.31,
                            },
                            "field_periods": {
                                "revenueGrowth": "ttm_yoy",
                                "netIncomeGrowth": "ttm_yoy",
                            },
                        },
                        "earnings_analysis": {
                            "derived_metrics": {
                                "yoy_revenue_growth": 0.7321,
                                "yoy_net_income_change": 0.9447,
                            }
                        },
                    },
                },
            ),
            report_language="zh",
        )

        self.assertEqual(payload["highlights"]["latest_news"], ["未发现高价值新增动态"])
        self.assertIn(
            "2026-02-25 财报解读：营收与利润大幅超预期，AI 业务继续高增。",
            payload["highlights"]["positive_catalysts"],
        )
        self.assertIn("最新季度同比口径", payload["highlights"]["earnings_outlook"])

    def test_market_commentary_is_routed_to_risk_not_latest_news(self) -> None:
        payload = build_standard_report_payload(
            _make_result(
                dashboard={
                    "core_conclusion": {"one_sentence": "等待确认"},
                    "battle_plan": {},
                    "intelligence": {
                        "latest_news": "媒体解读：AI 需求放缓引发估值担忧，短线情绪继续承压。",
                        "risk_alerts": ["估值仍然偏高"],
                    },
                    "structured_analysis": {
                        "time_context": {
                            "market_session_date": "2026-03-28",
                            "news_published_at": "2026-03-28T08:30:00-04:00",
                        }
                    },
                },
            ),
            report_language="zh",
        )

        self.assertEqual(payload["highlights"]["latest_news"], ["未发现高价值新增动态"])
        self.assertIn(
            "媒体解读：AI 需求放缓引发估值担忧，短线情绪继续承压。",
            payload["highlights"]["risk_alerts"],
        )
        self.assertNotIn(
            "媒体解读：AI 需求放缓引发估值担忧，短线情绪继续承压。",
            payload["highlights"]["positive_catalysts"],
        )

    def test_trade_plan_preserves_ma_token_text_without_fake_decimals(self) -> None:
        payload = build_standard_report_payload(
            _make_result(
                dashboard={
                    "core_conclusion": {},
                    "intelligence": {},
                    "battle_plan": {
                        "sniper_points": {
                            "ideal_buy": "回踩 MA20 附近分批",
                            "secondary_buy": "突破前高再跟",
                            "stop_loss": "跌破 115 止损",
                            "take_profit": "132",
                        },
                        "position_strategy": {
                            "suggested_position": "回踩 MA20 附近先试 30% 仓位",
                            "entry_plan": "等待 MA20 附近缩量企稳",
                            "risk_control": "若放量跌破 MA20 则收缩仓位",
                        },
                    },
                },
            ),
            report_language="zh",
        )
        battle_fields = {item["label"]: item["value"] for item in payload["battle_fields"]}

        self.assertIn("MA20", battle_fields["理想买入点"])
        self.assertIn("MA20", battle_fields["仓位建议"])
        self.assertNotIn("MA20.00", battle_fields["理想买入点"])
        self.assertNotIn("MA20.00", battle_fields["仓位建议"])

    def test_extended_timestamp_is_not_reused_when_session_has_no_extended_quote(self) -> None:
        payload = build_standard_report_payload(
            _make_result(
                market_snapshot={
                    "price": 125.3,
                    "close": 124.0,
                    "prev_close": 123.0,
                    "session_type": "intraday_snapshot",
                },
                dashboard={
                    "core_conclusion": {},
                    "battle_plan": {},
                    "intelligence": {},
                    "structured_analysis": {
                        "time_context": {
                            "market_timestamp": "2026-03-27T13:32:41-04:00",
                            "market_session_date": "2026-03-28",
                            "session_type": "intraday_snapshot",
                        }
                    },
                },
            ),
            report_language="zh",
        )
        extended_fields = {item["label"]: item["value"] for item in payload["market"]["extended_fields"]}
        time_ctx = payload["market"]["time_context"]

        self.assertEqual(extended_fields["扩展时段时间"], "NA（当前数据源未提供）")
        self.assertEqual(time_ctx["market_session_date"], "2026-03-27")

    def test_zero_placeholder_technicals_render_reasoned_na(self) -> None:
        r = _make_result(
            dashboard={
                "core_conclusion": {},
                "battle_plan": {},
                "intelligence": {},
                "data_perspective": {
                    "trend_status": {},
                    "price_position": {
                        "ma5": 0,
                        "ma10": "0.00",
                    },
                    "volume_analysis": {},
                    "alpha_vantage": {},
                },
                "structured_analysis": {
                    "technicals": {
                        "ma5": {"value": 0, "status": "insufficient_history"},
                        "ma10": {"value": 0, "status": "data_unavailable"},
                    }
                },
            },
        )
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("**MA5**: NA（样本不足）", out)
        self.assertIn("**MA10**: NA（当前数据源未提供）", out)
        self.assertIn("**乖离率(MA5)**: NA（样本不足）", out)
        self.assertNotIn("**MA5**: 0.00", out)
        self.assertNotIn("**MA10**: 0.00", out)
        self.assertNotIn("**乖离率(MA5)**: 0.00%", out)

    def test_zero_placeholder_market_and_trend_metrics_render_reasoned_na(self) -> None:
        r = _make_result(
            market_snapshot={
                "price": 362.19,
                "close": 362.19,
                "prev_close": 374.20,
                "session_type": "intraday_snapshot",
                "source": "finnhub",
            },
            dashboard={
                "core_conclusion": {},
                "battle_plan": {},
                "intelligence": {},
                "data_perspective": {
                    "trend_status": {"trend_score": 0},
                    "price_position": {},
                    "volume_analysis": {
                        "volume_ratio": 0.0,
                        "turnover_rate": "0.00",
                    },
                    "alpha_vantage": {},
                },
                "structured_analysis": {
                    "market_context": {
                        "today": {"close": 362.19},
                        "yesterday": {"close": 374.20},
                    },
                    "realtime_context": {
                        "price": 362.19,
                        "volume_ratio": 0,
                        "turnover_rate": "0.0",
                        "source": "finnhub",
                    },
                    "trend_analysis": {"trend_strength": 0},
                },
            },
        )
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("**Volume Ratio**: NA（当前数据源未提供）", out)
        self.assertIn("**Turnover Rate**: NA（字段待接入）", out)
        self.assertIn("**趋势强度**: NA（接口未返回）", out)
        self.assertNotIn("**Volume Ratio**: 0.00", out)
        self.assertNotIn("**Turnover Rate**: 0.00%", out)
        self.assertNotIn("**趋势强度**: 0.00/100", out)

    def test_source_is_hidden_when_only_provider_tag_exists_without_quote_data(self) -> None:
        r = _make_result(
            market_snapshot={
                "source": "finnhub",
                "session_type": "intraday_snapshot",
            },
            dashboard={
                "core_conclusion": {},
                "battle_plan": {},
                "intelligence": {},
                "structured_analysis": {
                    "realtime_context": {
                        "source": "finnhub",
                    }
                },
            },
        )
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("**Analysis Price**: NA（接口未返回）", out)
        self.assertIn("**Market Feed**: Upstream quote feed · intraday snapshot", out)
        self.assertNotIn("**Market Feed**: Finnhub", out)

    def test_market_close_timestamp_forces_last_completed_session_price_basis(self) -> None:
        r = _make_result(
            market_snapshot={
                "price": 167.52,
                "close": 168.99,
                "prev_close": 171.24,
                "open": 169.99,
                "high": 170.97,
                "low": 167.55,
                "session_type": "intraday_snapshot",
            },
            dashboard={
                "core_conclusion": {"one_sentence": "等待确认"},
                "battle_plan": {},
                "intelligence": {},
                "structured_analysis": {
                    "time_context": {
                        "market_timestamp": "2026-03-27T16:00:00-04:00",
                        "market_session_date": "2026-03-27",
                        "session_type": "intraday_snapshot",
                    }
                },
            },
            code="NVDA",
            name="NVIDIA",
        )
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("**Analysis Price**: 168.99", out)
        self.assertIn("**Price basis / Session**: Last close / 2026-03-27 regular session", out)
        self.assertIn("**会话标签**: 上一已收盘交易日", out)
        self.assertNotIn("**Analysis Price**: 167.52", out)

    def test_completed_session_recovers_prev_close_and_recomputes_change(self) -> None:
        r = _make_result(
            market_snapshot={
                "price": 167.52,
                "close": 167.52,
                "prev_close": 167.52,
                "change_amount": 0.0,
                "pct_chg": 0.0,
                "open": 170.2,
                "high": 171.0,
                "low": 167.1,
                "session_type": "last_completed_session",
            },
            dashboard={
                "core_conclusion": {"one_sentence": "等待确认"},
                "battle_plan": {},
                "intelligence": {},
                "structured_analysis": {
                    "time_context": {
                        "market_timestamp": "2026-03-27T16:00:00-04:00",
                        "market_session_date": "2026-03-27",
                        "session_type": "last_completed_session",
                    },
                    "market_context": {
                        "today": {
                            "close": 167.52,
                            "pct_chg": -2.17,
                            "high": 171.0,
                            "low": 167.1,
                        },
                        "yesterday": {
                            "close": 171.24,
                        },
                    },
                },
            },
            code="NVDA",
            name="NVIDIA",
        )

        payload = build_standard_report_payload(r, report_language="zh")
        regular_metrics = payload["market"]["regular_metrics"]

        self.assertAlmostEqual(regular_metrics["close"], 167.52, places=2)
        self.assertAlmostEqual(regular_metrics["prev_close"], 171.24, places=2)
        self.assertAlmostEqual(regular_metrics["change_amount"], -3.72, places=2)
        self.assertAlmostEqual(regular_metrics["change_pct"], -2.17, places=2)
        self.assertNotAlmostEqual(regular_metrics["prev_close"], regular_metrics["close"], places=2)
        self.assertEqual(payload["summary_panel"]["change_pct"], "-2.17%")

    def test_completed_session_prefers_eod_context_bundle_over_conflicting_snapshot(self) -> None:
        r = _make_result(
            market_snapshot={
                "price": 167.52,
                "close": 168.40,
                "prev_close": 168.40,
                "open": 168.30,
                "high": 169.0,
                "low": 166.8,
                "volume": 98765432,
                "change_amount": 0.0,
                "pct_chg": 0.0,
                "source": "finnhub",
                "session_type": "last_completed_session",
            },
            dashboard={
                "core_conclusion": {"one_sentence": "等待确认"},
                "battle_plan": {},
                "intelligence": {},
                "structured_analysis": {
                    "time_context": {
                        "market_timestamp": "2026-03-27T16:00:00-04:00",
                        "market_session_date": "2026-03-27",
                        "session_type": "last_completed_session",
                    },
                    "market_context": {
                        "today": {
                            "close": 167.52,
                            "open": 170.10,
                            "high": 171.10,
                            "low": 166.90,
                            "volume": 45670000,
                            "amount": 7654000000,
                            "pct_chg": -2.76,
                            "data_source": "yfinance_eod",
                        },
                        "yesterday": {
                            "close": 172.28,
                            "data_source": "yfinance_eod",
                        },
                    },
                    "realtime_context": {
                        "price": 167.52,
                        "pre_close": 168.40,
                        "change_amount": 0.0,
                        "change_pct": 0.0,
                        "source": "finnhub",
                    },
                },
            },
            code="NVDA",
            name="NVIDIA",
        )

        payload = build_standard_report_payload(r, report_language="zh")
        market_fields = {item["label"]: item["value"] for item in payload["market"]["regular_fields"]}
        regular_metrics = payload["market"]["regular_metrics"]

        self.assertEqual(market_fields["行情来源"], "yfinance_eod")
        self.assertEqual(market_fields["当前价"], "167.52")
        self.assertEqual(market_fields["昨收"], "172.28")
        self.assertEqual(market_fields["开盘"], "170.10")
        self.assertEqual(market_fields["最高"], "171.10")
        self.assertEqual(market_fields["最低"], "166.90")
        self.assertEqual(market_fields["成交量"], "4567.00万")
        self.assertAlmostEqual(regular_metrics["close"], 167.52, places=2)
        self.assertAlmostEqual(regular_metrics["prev_close"], 172.28, places=2)
        self.assertAlmostEqual(regular_metrics["open"], 170.10, places=2)
        self.assertAlmostEqual(regular_metrics["high"], 171.10, places=2)
        self.assertAlmostEqual(regular_metrics["low"], 166.90, places=2)
        self.assertAlmostEqual(regular_metrics["volume"], 45670000, places=2)
        self.assertAlmostEqual(regular_metrics["change_amount"], -4.76, places=2)
        self.assertAlmostEqual(regular_metrics["change_pct"], -2.76, places=2)
        self.assertNotAlmostEqual(regular_metrics["prev_close"], regular_metrics["close"], places=2)

    def test_standard_report_exposes_compact_summary_sections(self) -> None:
        payload = build_standard_report_payload(_make_result(), report_language="zh")
        technical_fields = payload["table_sections"]["technical"]["fields"]
        ma20_field = next(field for field in technical_fields if field["label"] == "MA20")
        support_field = next(field for field in technical_fields if field["label"] == "支撑位")

        self.assertEqual(payload["summary_panel"]["ticker"], "AAPL")
        self.assertEqual(payload["summary_panel"]["operation_advice"], "持有")
        self.assertEqual(payload["table_sections"]["market"]["title"], "行情表")
        self.assertEqual(payload["table_sections"]["market"]["fields"][0]["label"], "Analysis Price")
        self.assertEqual(payload["table_sections"]["technical"]["title"], "技术面表")
        self.assertEqual(payload["table_sections"]["fundamental"]["title"], "基本面表")
        self.assertEqual(payload["table_sections"]["earnings"]["title"], "财报表")
        self.assertEqual(payload["summary_panel"]["current_price"], "125.30")
        self.assertEqual(payload["visual_blocks"]["price_position"]["vs_ma20"], "上方")
        self.assertIn("公司获重大订单", payload["highlights"]["positive_catalysts"])
        self.assertIn("理想买入点", [item["label"] for item in payload["battle_plan_compact"]["cards"]])
        self.assertEqual(payload["checklist_items"][0]["status"], "warn")
        self.assertIn(payload["decision_panel"]["setup_type"], {"突破跟随", "回踩买点", "趋势延续 / 等回踩"})
        self.assertIn("（", payload["decision_panel"]["ideal_entry"])
        self.assertEqual(payload["decision_panel"]["no_position_advice"], "等待回踩确认")
        self.assertEqual(payload["reason_layer"]["top_risk"], "监管调查进展")
        self.assertEqual(payload["reason_layer"]["top_catalyst"], "公司获重大订单")
        self.assertEqual(payload["reason_layer"]["latest_key_update"], "公司发布季度财报并上调指引")
        self.assertTrue(payload["coverage_notes"]["data_sources"])
        self.assertTrue(payload["coverage_notes"]["method_notes"])
        self.assertEqual(ma20_field["source"], "Local OHLCV")
        self.assertEqual(ma20_field["status"], "已就绪")
        self.assertEqual(support_field["source"], "本地派生")
        self.assertEqual(support_field["status"], "派生")

    def test_market_display_fields_dedupe_close_when_same_as_reference_price(self) -> None:
        payload = build_standard_report_payload(_make_result(), report_language="zh")
        display_labels = [item["label"] for item in payload["market"]["display_fields"]]

        self.assertIn("Analysis Price", display_labels)
        self.assertIn("Session Open", display_labels)
        self.assertNotIn("Reference Close", display_labels)

    def test_standard_report_exposes_decision_context_for_stability_notes(self) -> None:
        r = _make_result(
            dashboard={
                "core_conclusion": {"one_sentence": "等待确认"},
                "battle_plan": {},
                "intelligence": {},
                "decision_context": {
                    "short_term_view": "短线技术偏弱，价格位于 MA20 下方。",
                    "composite_view": "基本面与现金流仍有支撑，综合建议以观望为主。",
                    "adjustment_reason": "MA5/10/20/60 已补齐，并保留基本面缓冲。",
                    "change_reason": "技术指标补齐导致",
                    "previous_score": 45,
                    "score_change": -3,
                    "score_breakdown": [
                        {"label": "技术分", "score": 38, "note": "均线结构偏空", "tone": "danger"},
                        {"label": "基本面分", "score": 72, "note": "现金流健康", "tone": "success"},
                    ],
                },
            },
        )

        payload = build_standard_report_payload(r, report_language="zh")

        self.assertEqual(payload["decision_context"]["short_term_view"], "短线技术偏弱，价格位于 MA20 下方。")
        self.assertEqual(payload["decision_context"]["composite_view"], "基本面与现金流仍有支撑，综合建议以观望为主。")
        self.assertEqual(payload["decision_context"]["adjustment_reason"], "MA5/10/20/60 已补齐，并保留基本面缓冲。")
        self.assertEqual(payload["decision_context"]["change_reason"], "技术指标补齐导致")
        self.assertEqual(payload["decision_context"]["previous_score"], "45")
        self.assertEqual(payload["decision_context"]["score_change"], "-3")
        self.assertEqual(payload["decision_context"]["score_breakdown"][0]["label"], "技术分")
        self.assertEqual(payload["decision_context"]["score_breakdown"][0]["score"], 38)
        self.assertEqual(payload["decision_context"]["score_breakdown"][0]["tone"], "danger")

    def test_renderer_prefers_raw_market_context_over_formatted_snapshot_strings(self) -> None:
        r = _make_result(
            market_snapshot={
                "price": "125.30",
                "close": "124.00",
                "prev_close": "123.00",
                "volume": "450.00万",
                "amount": "8.80亿",
                "session_type": "intraday_snapshot",
                "source": "snapshot-text",
            },
            dashboard={
                "core_conclusion": {"one_sentence": "等待确认"},
                "battle_plan": {},
                "intelligence": {},
                "structured_analysis": {
                    "time_context": {"session_type": "intraday_snapshot"},
                    "market_context": {
                        "today": {
                            "close": 124.0,
                            "open": 123.5,
                            "high": 126.2,
                            "low": 122.9,
                            "pct_chg": 1.87,
                            "volume": 4500000,
                            "amount": 880000000,
                        },
                        "yesterday": {"close": 123.0},
                    },
                    "realtime_context": {
                        "price": 125.3,
                        "pre_close": 123.0,
                        "change_amount": 2.3,
                        "change_pct": 1.87,
                        "amplitude": 2.68,
                        "volume": 4500000,
                        "amount": 880000000,
                        "open_price": 123.5,
                        "high": 126.2,
                        "low": 122.9,
                        "source": "yfinance",
                    },
                },
            },
        )
        out = render("markdown", [r], summary_only=False)
        assert out is not None
        self.assertIn("**Prev Close**: 123.00", out)
        self.assertIn("**Volume**: 450.00万", out)
        self.assertIn("**Turnover**: 8.80亿", out)
        self.assertIn("**Market Feed**: YFinance · intraday snapshot", out)

    def test_standard_report_keeps_time_context_when_available(self) -> None:
        r = _make_result()
        structured = r.dashboard.setdefault("structured_analysis", {})
        structured["time_context"] = {
            "market_timestamp": "2026-03-27T09:35:00-04:00",
            "market_session_date": "2026-03-27",
            "news_published_at": "2026-03-27T09:00:00-04:00",
            "report_generated_at": "2026-03-27T21:35:00+08:00",
            "session_type": "intraday_snapshot",
        }

        payload = build_standard_report_payload(r, report_language="zh")
        time_ctx = payload["market"]["time_context"]

        self.assertEqual(time_ctx["market_timestamp"], "2026-03-27T09:35:00-04:00")
        self.assertEqual(time_ctx["market_session_date"], "2026-03-27")
        self.assertEqual(time_ctx["news_published_at"], "2026-03-27T09:00:00-04:00")
        self.assertEqual(time_ctx["report_generated_at"], "2026-03-27T21:35:00+08:00")
        self.assertEqual(time_ctx["session_type"], "intraday_snapshot")

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
        self.assertIn("未发现高价值新增动态", out)
        self.assertIn("低价值已降权", out)
        self.assertNotIn("公司参加品牌活动", out)
        self.assertNotIn("高管出席品牌活动", out)

    def test_summary_only_still_renders_dashboard_summary(self) -> None:
        out = render("markdown", [_make_result()], summary_only=True)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertIn("分析结果摘要", out)
        self.assertNotIn("Part A. Executive Summary", out)

    def test_english_report_uses_english_title_labels(self) -> None:
        r = _make_result(report_language="en", name="Unnamed Stock", code="TSLA")
        out = render("markdown", [r], summary_only=True)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertIn("Decision Dashboard", out)
        self.assertIn("Stock Analysis Report", out)


if __name__ == "__main__":
    unittest.main()
