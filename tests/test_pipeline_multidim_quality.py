# -*- coding: utf-8 -*-
import os
import sys
import unittest
from datetime import date, timedelta, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.core.pipeline import StockAnalysisPipeline
from src.analyzer import AnalysisResult
from data_provider.realtime_types import UnifiedRealtimeQuote, RealtimeSource


def _bars(days: int, start_close: float = 100.0):
    items = []
    for i in range(days):
        items.append(
            SimpleNamespace(
                date=date.today() - timedelta(days=days - i),
                close=start_close + i,
                volume=100000 + i * 100,
            )
        )
    return items


class TestPipelineMultiDimQuality(unittest.TestCase):
    def setUp(self) -> None:
        self._db_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "test_multidim_quality.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with patch.dict(os.environ, {"DATABASE_PATH": self._db_path}):
            from src.config import Config
            Config._instance = None
            cfg = Config._load_from_env()
        self.pipeline = StockAnalysisPipeline(config=cfg)

    def test_tem_local_ma20_available_from_ohlcv(self) -> None:
        self.pipeline.db.get_latest_data = MagicMock(return_value=_bars(120, 20.0))
        technicals = self.pipeline._build_technicals_block("TEM", {"rsi14": None, "sma20": None, "sma60": None})
        self.assertEqual(technicals["ma20"]["status"], "ok")
        self.assertEqual(technicals["ma20"]["source"], "local_from_ohlcv")
        self.assertIsNotNone(technicals["ma20"]["value"])

    def test_local_history_computes_ma5_ma10_ma20_ma60_when_bars_sufficient(self) -> None:
        self.pipeline.db.get_latest_data = MagicMock(return_value=_bars(120, 100.0))

        technicals = self.pipeline._build_technicals_block(
            "NVDA",
            {"rsi14": None, "sma20": None, "sma60": None},
        )

        self.assertEqual(technicals["ma5"]["status"], "ok")
        self.assertEqual(technicals["ma10"]["status"], "ok")
        self.assertEqual(technicals["ma20"]["status"], "ok")
        self.assertEqual(technicals["ma60"]["status"], "ok")
        self.assertEqual(technicals["ma60"]["source"], "local_from_ohlcv")

    def test_api_indicators_override_local_values_when_available(self) -> None:
        self.pipeline.db.get_latest_data = MagicMock(return_value=_bars(120, 100.0))

        technicals = self.pipeline._build_technicals_block(
            "NVDA",
            {"rsi14": 44.4, "sma20": 140.2, "sma60": 132.8},
            api_indicators={
                "ma5": {"value": 151.1, "source": "fmp_technical_indicator", "status": "ok"},
                "ma10": {"value": 149.4, "source": "fmp_technical_indicator", "status": "ok"},
                "ma20": {"value": 147.2, "source": "fmp_technical_indicator", "status": "ok"},
                "ma60": {"value": 138.9, "source": "fmp_technical_indicator", "status": "ok"},
                "rsi14": {"value": 62.5, "source": "fmp_technical_indicator", "status": "ok"},
                "vwap": {"value": 150.6, "source": "fmp_historical_price", "status": "ok"},
            },
        )

        self.assertEqual(technicals["ma5"]["value"], 151.1)
        self.assertEqual(technicals["ma10"]["value"], 149.4)
        self.assertEqual(technicals["ma20"]["value"], 147.2)
        self.assertEqual(technicals["ma60"]["value"], 138.9)
        self.assertEqual(technicals["rsi14"]["value"], 62.5)
        self.assertEqual(technicals["vwap"]["value"], 150.6)
        self.assertEqual(technicals["ma20"]["source"], "fmp_technical_indicator")
        self.assertEqual(technicals["vwap"]["source"], "fmp_historical_price")

    def test_alpha_indicator_fallback_is_preferred_over_local_when_fmp_missing(self) -> None:
        self.pipeline.db.get_latest_data = MagicMock(return_value=_bars(120, 100.0))

        technicals = self.pipeline._build_technicals_block(
            "ORCL",
            {"rsi14": 48.8, "sma20": 142.3, "sma60": 136.4},
            api_indicators={},
        )

        self.assertEqual(technicals["ma20"]["value"], 142.3)
        self.assertEqual(technicals["ma60"]["value"], 136.4)
        self.assertEqual(technicals["rsi14"]["value"], 48.8)
        self.assertEqual(technicals["ma20"]["source"], "alpha_vantage")
        self.assertEqual(technicals["ma60"]["source"], "alpha_vantage")
        self.assertEqual(technicals["rsi14"]["source"], "alpha_vantage")

    def test_tem_can_use_fmp_history_for_ma_and_vwap_when_local_history_short(self) -> None:
        self.pipeline.db.get_latest_data = MagicMock(return_value=_bars(12, 20.0))
        external_history = []
        start = date(2025, 1, 1)
        for idx in range(80):
            external_history.append(
                {
                    "date": (start + timedelta(days=idx)).isoformat(),
                    "close": 30.0 + idx * 0.2,
                    "volume": 1000000 + idx * 1000,
                    "vwap": 30.0 + idx * 0.19,
                }
            )

        technicals = self.pipeline._build_technicals_block(
            "TEM",
            {"rsi14": None, "sma20": None, "sma60": None},
            external_price_history=external_history,
        )
        self.assertEqual(technicals["ma5"]["status"], "ok")
        self.assertEqual(technicals["ma60"]["status"], "ok")
        self.assertEqual(technicals["ma60"]["source"], "fmp_historical_price")
        self.assertEqual(technicals["vwap"]["status"], "ok")
        self.assertEqual(technicals["vwap"]["source"], "fmp_historical_price")

    def test_mstr_graceful_degradation_and_quality_warnings(self) -> None:
        self.pipeline.db.get_latest_data = MagicMock(return_value=_bars(12, 50.0))
        technicals = self.pipeline._build_technicals_block("MSTR", {"rsi14": 47.7, "sma20": 138.4, "sma60": 145.0})
        fundamentals = self.pipeline._build_fundamentals_block(None)
        earnings = self.pipeline._build_earnings_analysis_block(None)
        sentiment = self.pipeline._build_sentiment_analysis_block("")
        quality = self.pipeline._build_data_quality_block(
            technicals=technicals,
            fundamentals=fundamentals,
            earnings_analysis=earnings,
            sentiment_analysis=sentiment,
            alpha_errors=["429"],
            context={"realtime": {"volume_ratio": "数据缺失", "turnover_rate": "数据缺失", "source": "stooq"}},
            diagnostics={"failure_reasons": ["history_fetch_failed", "alpha_vantage_error: 429"]},
        )
        self.assertIn("alpha_vantage: 429", quality["warnings"])
        self.assertIn("volume_ratio_unavailable", quality["warnings"])
        self.assertIn("provider_failure: history_fetch_failed", quality["warnings"])
        self.assertEqual(quality["provider_notes"]["diagnostics"]["failure_reasons"][0], "history_fetch_failed")
        self.assertEqual(sentiment["sentiment_summary"], "no_reliable_news")
        self.assertEqual(fundamentals["status"], "partial")

    def test_time_contract_fields_are_present_and_aware(self) -> None:
        ctx = {"code": "AAPL", "date": "2026-03-25", "today": {}, "yesterday": {}}
        enhanced = self.pipeline._enhance_context(
            context=ctx,
            realtime_quote=None,
            chip_data=None,
            trend_result=None,
            stock_name="Apple",
            fundamental_context=None,
        )
        self.assertIn("market_timestamp", enhanced)
        self.assertIn("market_session_date", enhanced)
        self.assertIn("report_generated_at", enhanced)
        self.assertEqual(enhanced["market_session_date"], "2026-03-25")
        self.assertIn("T", enhanced["market_timestamp"])
        self.assertTrue(
            enhanced["market_timestamp"].endswith("-04:00")
            or enhanced["market_timestamp"].endswith("-05:00")
        )
        report_dt = datetime.fromisoformat(enhanced["report_generated_at"])
        self.assertIsNotNone(report_dt.tzinfo)

    def test_time_context_prefers_realtime_market_timestamp_for_session_date(self) -> None:
        ctx = {"code": "TSLA", "date": "2026-03-28", "today": {}, "yesterday": {}}
        quote = SimpleNamespace(
            price=362.19,
            market_timestamp="2026-03-27T13:32:41-04:00",
        )

        time_ctx = self.pipeline._build_time_context(ctx, quote)

        self.assertEqual(time_ctx["market_session_date"], "2026-03-27")
        self.assertEqual(time_ctx["market_timestamp"], "2026-03-27T13:32:41-04:00")
        self.assertEqual(time_ctx["session_type"], "intraday_snapshot")

    def test_time_context_marks_last_completed_session_after_regular_close(self) -> None:
        ctx = {"code": "NVDA", "date": "2026-03-28", "today": {}, "yesterday": {}}
        quote = SimpleNamespace(
            price=167.52,
            market_timestamp="2026-03-27T16:00:00-04:00",
        )

        time_ctx = self.pipeline._build_time_context(ctx, quote)

        self.assertEqual(time_ctx["market_session_date"], "2026-03-27")
        self.assertEqual(time_ctx["market_timestamp"], "2026-03-27T16:00:00-04:00")
        self.assertEqual(time_ctx["session_type"], "last_completed_session")

    def test_compute_volume_ratio_can_mix_local_and_fallback_history(self) -> None:
        today = date.today()
        self.pipeline.db.get_latest_data = MagicMock(
            return_value=[
                SimpleNamespace(date=today - timedelta(days=1), close=100.0, volume=100.0),
            ]
        )
        ratio = self.pipeline._compute_volume_ratio(
            context={"code": "TSLA", "date": today.isoformat(), "today": {}},
            realtime_quote=SimpleNamespace(volume=600.0),
            fallback_history=[
                {"date": (today - timedelta(days=5)).isoformat(), "volume": 200.0},
                {"date": (today - timedelta(days=4)).isoformat(), "volume": 300.0},
                {"date": (today - timedelta(days=3)).isoformat(), "volume": 400.0},
                {"date": (today - timedelta(days=2)).isoformat(), "volume": 500.0},
            ],
        )

        self.assertEqual(ratio, 2.0)

    def test_sentiment_filters_industry_noise(self) -> None:
        sentiment = self.pipeline._build_sentiment_analysis_block(
            news_context="Semiconductor industry growth and macro demand remained strong.",
            news_items=[
                {
                    "title": "Semiconductor industry growth accelerates",
                    "snippet": "Sector-wide demand remains strong",
                    "url": "https://example.com/industry",
                    "news_published_at": "2026-03-25T10:00:00+00:00",
                }
            ],
            stock_code="MSTR",
            stock_name="MicroStrategy",
            business_keywords=["software", "bitcoin treasury"],
        )
        self.assertEqual(sentiment["sentiment_summary"], "no_reliable_news")
        self.assertEqual(sentiment["confidence"], "low")
        self.assertEqual(sentiment["relevance_type"], "low_relevance")

    def test_sentiment_accepts_company_specific_regulatory(self) -> None:
        sentiment = self.pipeline._build_sentiment_analysis_block(
            news_context="MSTR faces SEC regulation update and guidance beat.",
            news_items=[
                {
                    "title": "SEC opens review into MSTR filing",
                    "snippet": "MicroStrategy says cooperation continues",
                    "url": "https://example.com/mstr-sec",
                    "news_published_at": "2026-03-25T11:00:00+00:00",
                }
            ],
            stock_code="MSTR",
            stock_name="MicroStrategy",
            business_keywords=["software", "bitcoin"],
        )
        self.assertNotEqual(sentiment["sentiment_summary"], "no_reliable_news")
        self.assertIn(sentiment["relevance_type"], {"regulatory", "company_specific"})
        self.assertGreaterEqual(sentiment["relevance_score"], 0.65)

    def test_fundamentals_block_contains_extended_metrics(self) -> None:
        block = self.pipeline._build_fundamentals_block(
            {
                "valuation": {
                    "data": {
                        "market_cap": 100,
                        "pe_ttm": 22.5,
                        "forward_pe": 20.1,
                        "pb_ratio": 3.2,
                        "shares_outstanding": 5000000,
                        "52week_high": 150.5,
                        "52week_low": 80.2,
                        "net_income": 42,
                        "revenue_growth": 0.2,
                        "operating_margin": 0.18,
                        "debt_to_equity": 60,
                    }
                }
            }
        )
        self.assertIn("forwardPE", block["normalized"])
        self.assertIn("revenueGrowth", block["normalized"])
        self.assertIn("operatingMargins", block["normalized"])
        self.assertEqual(block["normalized"]["priceToBook"], 3.2)
        self.assertEqual(block["normalized"]["sharesOutstanding"], 5000000)
        self.assertEqual(block["normalized"]["fiftyTwoWeekHigh"], 150.5)
        self.assertEqual(block["normalized"]["netIncome"], 42)
        self.assertEqual(block["derived_profiles"]["growth_profile"], "high_growth")

    def test_fundamentals_block_can_use_alpha_overview_source(self) -> None:
        block = self.pipeline._build_fundamentals_block(
            fundamental_context=None,
            alpha_overview={
                "MarketCapitalization": "123456789",
                "PERatio": "25.2",
                "ForwardPE": "21.0",
                "PriceToBookRatio": "6.2",
                "SharesOutstanding": "9000000",
                "52WeekHigh": "188.5",
                "52WeekLow": "122.1",
                "RevenueTTM": "50000000",
                "QuarterlyRevenueGrowthYOY": "0.11",
                "QuarterlyEarningsGrowthYOY": "0.07",
                "OperatingMarginTTM": "0.19",
                "ReturnOnEquityTTM": "0.3",
            },
        )
        self.assertEqual(block["normalized"]["marketCap"], "123456789")
        self.assertEqual(block["normalized"]["forwardPE"], "21.0")
        self.assertEqual(block["normalized"]["priceToBook"], "6.2")
        self.assertEqual(block["normalized"]["sharesOutstanding"], "9000000")
        self.assertEqual(block["field_sources"]["marketCap"], "alpha_vantage_overview")
        self.assertNotEqual(block["derived_profiles"]["valuation_profile"], "valuation_unavailable")

    def test_fundamentals_block_does_not_treat_gross_profit_ttm_as_gross_margin(self) -> None:
        block = self.pipeline._build_fundamentals_block(
            fundamental_context=None,
            alpha_overview={
                "GrossProfitTTM": "123456789",
                "OperatingMarginTTM": "0.19",
            },
        )
        self.assertIsNone(block["normalized"]["grossMargins"])
        self.assertEqual(block["normalized"]["operatingMargins"], "0.19")

    def test_fundamentals_block_prefers_yfinance_and_emits_field_sources(self) -> None:
        block = self.pipeline._build_fundamentals_block(
            fundamental_context=None,
            alpha_overview={"MarketCapitalization": "99"},
            yfinance_fundamentals={
                "marketCap": 123,
                "trailingPE": 22.1,
                "forwardPE": 18.7,
                "priceToBook": 5.4,
                "sharesOutstanding": 7000000,
                "fiftyTwoWeekHigh": 199.8,
                "netIncome": 888,
                "totalRevenue": 4000,
                "revenueGrowth": 0.2,
                "operatingMargins": 0.25,
            },
        )
        self.assertEqual(block["normalized"]["marketCap"], 123)
        self.assertEqual(block["normalized"]["priceToBook"], 5.4)
        self.assertEqual(block["normalized"]["sharesOutstanding"], 7000000)
        self.assertEqual(block["field_sources"]["marketCap"], "yfinance")
        self.assertEqual(block["status"], "partial")
        self.assertGreaterEqual(len(block["field_sources"]), 5)

    def test_fundamentals_block_can_fallback_to_fmp_and_finnhub(self) -> None:
        block = self.pipeline._build_fundamentals_block(
            fundamental_context=None,
            alpha_overview=None,
            yfinance_fundamentals={},
            fmp_fundamentals={
                "marketCap": 555,
                "sharesOutstanding": 1000000,
                "floatShares": 800000,
                "totalRevenue": 900,
                "netIncome": 120,
                "freeCashflow": 88,
                "operatingCashflow": 101,
            },
            finnhub_fundamentals={
                "beta": 1.2,
                "priceToBook": 6.4,
                "fiftyTwoWeekHigh": 180,
                "fiftyTwoWeekLow": 80,
                "currentRatio": 1.5,
            },
        )
        self.assertEqual(block["normalized"]["marketCap"], 555)
        self.assertEqual(block["normalized"]["priceToBook"], 6.4)
        self.assertEqual(block["normalized"]["currentRatio"], 1.5)
        self.assertEqual(block["field_sources"]["marketCap"], "fmp")
        self.assertEqual(block["field_sources"]["priceToBook"], "finnhub")

    def test_fundamentals_block_prefers_statement_ttm_and_ratio_sources_for_fcf_and_roe(self) -> None:
        block = self.pipeline._build_fundamentals_block(
            fundamental_context=None,
            yfinance_fundamentals={
                "freeCashflow": 111,
                "operatingCashflow": 222,
                "returnOnEquity": 0.55,
                "returnOnAssets": 0.21,
            },
            yfinance_quarterly_income=[
                {"fiscal_date": "2025-12-31", "free_cash_flow": 30, "operating_cashflow": 45},
                {"fiscal_date": "2025-09-30", "free_cash_flow": 25, "operating_cashflow": 41},
                {"fiscal_date": "2025-06-30", "free_cash_flow": 24, "operating_cashflow": 39},
                {"fiscal_date": "2025-03-31", "free_cash_flow": 21, "operating_cashflow": 35},
            ],
            fmp_fundamentals={
                "returnOnEquity": 1.0148,
                "returnOnAssets": 0.5821,
            },
            fmp_quarterly_income=[
                {"fiscal_date": "2025-12-31", "free_cash_flow": 260, "operating_cashflow": 320},
                {"fiscal_date": "2025-09-30", "free_cash_flow": 245, "operating_cashflow": 312},
                {"fiscal_date": "2025-06-30", "free_cash_flow": 238, "operating_cashflow": 305},
                {"fiscal_date": "2025-03-31", "free_cash_flow": 223, "operating_cashflow": 298},
            ],
            finnhub_fundamentals={
                "returnOnEquity": 0.88,
                "returnOnAssets": 0.41,
            },
        )

        self.assertEqual(block["normalized"]["freeCashflow"], 966.0)
        self.assertEqual(block["normalized"]["operatingCashflow"], 1235.0)
        self.assertEqual(block["normalized"]["returnOnEquity"], 1.0148)
        self.assertEqual(block["normalized"]["returnOnAssets"], 0.5821)
        self.assertEqual(block["field_sources"]["freeCashflow"], "fmp_quarterly")
        self.assertEqual(block["field_sources"]["operatingCashflow"], "fmp_quarterly")
        self.assertEqual(block["field_sources"]["returnOnEquity"], "fmp")
        self.assertEqual(block["field_periods"]["freeCashflow"], "ttm")
        self.assertEqual(block["field_periods"]["returnOnEquity"], "ttm")

    def test_fundamentals_block_keeps_valid_existing_values_when_fallback_is_empty(self) -> None:
        block = self.pipeline._build_fundamentals_block(
            fundamental_context={
                "valuation": {
                    "data": {
                        "market_cap": 1359694000000,
                        "pe_ttm": 335.51,
                        "forward_pe": 128.93,
                        "pb_ratio": 16.55,
                        "shares_outstanding": 3752000000,
                        "float_shares": 2813000000,
                        "52week_high": 498.83,
                        "52week_low": 214.25,
                        "revenue": 94827000000,
                        "net_income": 3794000000,
                        "free_cashflow": 3733000000,
                        "operating_cashflow": 14747000000,
                        "roe": 0.0493,
                        "roa": 0.021,
                        "gross_margin": 0.1803,
                        "operating_margin": 0.047,
                        "debt_to_equity": 17.76,
                        "current_ratio": 2.16,
                    }
                }
            },
            yfinance_fundamentals={},
            fmp_fundamentals={
                "marketCap": 0,
                "sharesOutstanding": 0,
                "floatShares": 0,
                "totalRevenue": 0,
                "freeCashflow": None,
                "operatingCashflow": "",
            },
            finnhub_fundamentals={
                "priceToBook": 0,
                "beta": "",
                "fiftyTwoWeekHigh": 0,
                "fiftyTwoWeekLow": 0,
                "currentRatio": None,
            },
        )

        normalized = block["normalized"]
        self.assertEqual(normalized["marketCap"], 1359694000000)
        self.assertEqual(normalized["trailingPE"], 335.51)
        self.assertEqual(normalized["forwardPE"], 128.93)
        self.assertEqual(normalized["priceToBook"], 16.55)
        self.assertEqual(normalized["sharesOutstanding"], 3752000000)
        self.assertEqual(normalized["floatShares"], 2813000000)
        self.assertEqual(normalized["fiftyTwoWeekHigh"], 498.83)
        self.assertEqual(normalized["fiftyTwoWeekLow"], 214.25)
        self.assertEqual(normalized["totalRevenue"], 94827000000)
        self.assertEqual(normalized["freeCashflow"], 3733000000)
        self.assertEqual(normalized["operatingCashflow"], 14747000000)
        self.assertEqual(normalized["currentRatio"], 2.16)
        self.assertEqual(block["field_sources"]["marketCap"], "fundamental_context")
        self.assertEqual(block["field_sources"]["priceToBook"], "fundamental_context")

    def test_earnings_block_uses_alpha_quarterly_income(self) -> None:
        block = self.pipeline._build_earnings_analysis_block(
            fundamental_context=None,
            alpha_quarterly_income=[
                {"fiscal_date": "2025-12-31", "revenue": 120.0, "net_income": 30.0, "gross_profit": 70.0, "operating_income": 35.0, "eps": 1.0},
                {"fiscal_date": "2025-09-30", "revenue": 110.0, "net_income": 26.0, "gross_profit": 62.0, "operating_income": 31.0, "eps": 0.9},
                {"fiscal_date": "2025-06-30", "revenue": 108.0, "net_income": 24.0, "gross_profit": 60.0, "operating_income": 29.0, "eps": 0.85},
                {"fiscal_date": "2025-03-31", "revenue": 102.0, "net_income": 22.0, "gross_profit": 58.0, "operating_income": 28.0, "eps": 0.8},
                {"fiscal_date": "2024-12-31", "revenue": 95.0, "net_income": 20.0, "gross_profit": 55.0, "operating_income": 27.0, "eps": 0.7},
            ],
        )
        self.assertEqual(block["status"], "ok")
        self.assertIn("qoq_revenue_growth", block["derived_metrics"])
        self.assertIn("yoy_net_income_change", block["derived_metrics"])
        self.assertAlmostEqual(block["derived_metrics"]["yoy_revenue_growth"], 0.2632, places=4)
        self.assertAlmostEqual(block["derived_metrics"]["yoy_net_income_change"], 0.5, places=4)
        self.assertIn("quarterly_series_available", block["summary_flags"])
        self.assertEqual(block["field_sources"]["quarterly_series"], "alpha_vantage_income_statement")

    def test_earnings_block_partial_to_usable_with_yfinance_series(self) -> None:
        block = self.pipeline._build_earnings_analysis_block(
            fundamental_context=None,
            yfinance_quarterly_income=[
                {"fiscal_date": "2025-12-31", "revenue": 140.0, "gross_profit": 75.0, "operating_income": 36.0, "net_income": 28.0, "eps": 1.2},
                {"fiscal_date": "2025-09-30", "revenue": 130.0, "gross_profit": None, "operating_income": None, "net_income": 24.0, "eps": 1.0},
            ],
        )
        self.assertEqual(block["status"], "ok")
        self.assertEqual(block["field_sources"]["quarterly_series"], "yfinance")
        self.assertIn("qoq_revenue_growth", block["derived_metrics"])
        self.assertIn("loss_status", block["derived_metrics"])

    def test_realtime_source_enum_is_json_serializable_in_quality_blocks(self) -> None:
        ctx = {"code": "AAPL", "date": "2026-03-25", "today": {}, "yesterday": {}}
        quote = UnifiedRealtimeQuote(
            code="AAPL",
            name="Apple",
            source=RealtimeSource.YFINANCE,
            price=180.0,
        )
        enhanced = self.pipeline._enhance_context(
            context=ctx,
            realtime_quote=quote,
            chip_data=None,
            trend_result=None,
            stock_name="Apple",
            fundamental_context=None,
        )
        technicals = self.pipeline._build_technicals_block("AAPL", {"rsi14": None, "sma20": None, "sma60": None})
        quality = self.pipeline._build_data_quality_block(
            technicals=technicals,
            fundamentals=self.pipeline._build_fundamentals_block(None),
            earnings_analysis=self.pipeline._build_earnings_analysis_block(None),
            sentiment_analysis=self.pipeline._build_sentiment_analysis_block(""),
            alpha_errors=[],
            context=enhanced,
            diagnostics={"realtime_source": RealtimeSource.YFINANCE, "failure_reasons": []},
        )
        self.assertEqual(enhanced["realtime"]["source"], "yfinance")
        self.assertEqual(quality["provider_notes"]["market_data"], "yfinance")
        # should not raise TypeError: Object of type RealtimeSource is not JSON serializable
        json.dumps(quality, ensure_ascii=False)

    def test_sentiment_without_items_still_generates_structured_output_from_text(self) -> None:
        block = self.pipeline._build_sentiment_analysis_block(
            news_context="ORCL earnings beat and guidance raised.",
            news_items=[],
            stock_code="ORCL",
            stock_name="Oracle",
            business_keywords=["cloud", "database"],
        )
        self.assertIn("company_sentiment", block)
        self.assertIn("overall_confidence", block)
        self.assertEqual(block["sentiment_summary"], "no_reliable_news")
        self.assertEqual(block["failure_reason"], "source_empty")

    def test_sentiment_reports_relevance_failure_reason(self) -> None:
        block = self.pipeline._build_sentiment_analysis_block(
            news_context="Industry demand update with macro commentary.",
            news_items=[
                {
                    "title": "Semiconductor industry outlook",
                    "snippet": "General sector update only.",
                    "url": "https://example.com/sector",
                }
            ],
            stock_code="ORCL",
            stock_name="Oracle",
            business_keywords=["cloud"],
        )
        self.assertEqual(block["sentiment_summary"], "no_reliable_news")
        self.assertEqual(block["failure_reason"], "relevance_too_low")

    def test_orcl_multidim_blocks_have_usable_data_with_field_sources(self) -> None:
        self.pipeline.db.get_latest_data = MagicMock(return_value=_bars(120, 100.0))
        blocks = self.pipeline._build_multidim_blocks(
            code="ORCL",
            context={"stock_name": "Oracle", "realtime": {"source": "yfinance"}},
            fundamental_context=None,
            news_context="Oracle earnings beat and SEC disclosure update after cloud partnership launch.",
            news_items=[
                {
                    "title": "Oracle raises guidance after earnings beat",
                    "snippet": "ORCL reported growth and announced strategic partnership.",
                    "url": "https://example.com/orcl-earnings",
                    "news_published_at": "2026-03-25T11:00:00+00:00",
                }
            ],
            diagnostics={"failure_reasons": []},
            alpha_indicators={"rsi14": 50.0, "sma20": 100.2, "sma60": 98.8},
            alpha_overview={"PERatio": "25.2", "MarketCapitalization": "100000"},
            yfinance_fundamentals={
                "marketCap": 200000,
                "trailingPE": 22.3,
                "forwardPE": 19.8,
                "totalRevenue": 540000,
                "revenueGrowth": 0.15,
                "operatingMargins": 0.3,
            },
            yfinance_quarterly_income=[
                {"fiscal_date": "2025-12-31", "revenue": 140.0, "gross_profit": 80.0, "operating_income": 37.0, "net_income": 28.0, "eps": 1.2},
                {"fiscal_date": "2025-09-30", "revenue": 120.0, "gross_profit": 70.0, "operating_income": 30.0, "net_income": 20.0, "eps": 1.0},
            ],
            alpha_quarterly_income=[],
            alpha_errors=[],
        )
        self.assertEqual(blocks["fundamentals"]["field_sources"]["marketCap"], "yfinance")
        self.assertNotEqual(blocks["earnings_analysis"]["summary_flags"], ["earnings_data_unavailable"])
        self.assertNotEqual(blocks["sentiment_analysis"]["sentiment_summary"], "no_reliable_news")

    def test_stabilizer_keeps_strong_fundamental_names_from_overreacting_to_bearish_technicals(self) -> None:
        result = AnalysisResult(
            code="NVDA",
            name="NVIDIA",
            sentiment_score=35,
            trend_prediction="看空",
            operation_advice="观望",
            report_language="zh",
            dashboard={
                "core_conclusion": {"one_sentence": "等待确认"},
                "structured_analysis": {
                    "time_context": {
                        "market_session_date": "2026-03-27",
                        "session_type": "last_completed_session",
                    },
                    "trend_analysis": {
                        "trend_status": "强势空头",
                        "ma_alignment": "空头排列 MA5<MA10<MA20",
                        "trend_strength": 22,
                        "volume_status": "放量下跌",
                    },
                    "fundamentals": {
                        "normalized": {
                            "returnOnEquity": 0.46,
                            "returnOnAssets": 0.24,
                            "totalRevenue": 120000000000,
                            "netIncome": 58000000000,
                        },
                        "derived_profiles": {
                            "growth_profile": "high_growth",
                            "profitability_profile": "profitable",
                            "cashflow_profile": "cashflow_healthy",
                            "leverage_profile": "leverage_controllable",
                        },
                    },
                    "sentiment_analysis": {
                        "company_sentiment": "positive",
                    },
                    "data_quality": {
                        "missing_fields": [],
                    },
                    "market_context": {
                        "today": {
                            "close": 125.0,
                            "ma20": 130.0,
                        }
                    },
                    "realtime_context": {
                        "price": 125.0,
                    },
                    "technicals": {
                        "ma20": {"value": 130.0, "status": "ok", "source": "fmp_technical_indicator"},
                        "ma60": {"value": 138.0, "status": "ok", "source": "fmp_technical_indicator"},
                        "rsi14": {"value": 33.2, "status": "ok", "source": "fmp_technical_indicator"},
                    },
                },
            },
        )
        previous_raw_result = {
            "dashboard": {
                "structured_analysis": {
                    "time_context": {
                        "market_session_date": "2026-03-27",
                        "session_type": "last_completed_session",
                    },
                    "data_quality": {
                        "missing_fields": ["technicals.ma5", "technicals.ma10", "technicals.ma60"],
                    }
                }
            }
        }
        self.pipeline.db.get_analysis_history = MagicMock(
            return_value=[
                SimpleNamespace(
                    query_id="prev-nvda",
                    sentiment_score=45,
                    operation_advice="观望",
                    trend_prediction="震荡",
                    raw_result=json.dumps(previous_raw_result),
                )
            ]
        )

        stabilized = self.pipeline._stabilize_analysis_result(
            code="NVDA",
            query_id="current-nvda",
            result=result,
        )

        self.assertGreaterEqual(stabilized.sentiment_score, 42)
        self.assertEqual(stabilized.operation_advice, "观望")
        self.assertEqual(stabilized.trend_prediction, "看空")
        self.assertIn("短线技术偏弱", stabilized.dashboard["core_conclusion"]["one_sentence"])
        self.assertIn("基本面缓冲", stabilized.dashboard["decision_context"]["adjustment_reason"])
        self.assertIn("MA5/MA10/MA60", stabilized.dashboard["decision_context"]["adjustment_reason"])
        self.assertEqual(stabilized.dashboard["decision_context"]["change_reason"], "技术指标补齐导致")
        self.assertLessEqual(abs(stabilized.sentiment_score - 45), 5)

    def test_stabilizer_clamps_same_session_score_drift_when_signature_unchanged(self) -> None:
        result = AnalysisResult(
            code="NVDA",
            name="NVIDIA",
            sentiment_score=28,
            trend_prediction="看空",
            operation_advice="减仓",
            report_language="zh",
            dashboard={
                "core_conclusion": {"one_sentence": "等待确认"},
                "intelligence": {
                    "latest_news": "未发现高价值新增动态",
                },
                "structured_analysis": {
                    "time_context": {
                        "market_session_date": "2026-03-27",
                        "session_type": "last_completed_session",
                    },
                    "trend_analysis": {
                        "trend_status": "空头",
                        "ma_alignment": "空头排列 MA5<MA10<MA20",
                        "trend_strength": 28,
                        "volume_status": "放量下跌",
                    },
                    "fundamentals": {
                        "normalized": {
                            "returnOnEquity": 0.42,
                            "returnOnAssets": 0.21,
                            "totalRevenue": 120000000000,
                            "netIncome": 58000000000,
                        },
                        "derived_profiles": {
                            "growth_profile": "high_growth",
                            "profitability_profile": "profitable",
                            "cashflow_profile": "cashflow_healthy",
                            "leverage_profile": "leverage_controllable",
                        },
                    },
                    "sentiment_analysis": {
                        "company_sentiment": "positive",
                        "sentiment_summary": "no_reliable_news",
                    },
                    "data_quality": {
                        "missing_fields": [],
                    },
                    "market_context": {
                        "today": {
                            "close": 167.52,
                            "open": 170.0,
                            "high": 171.2,
                            "low": 166.8,
                            "pct_chg": -2.76,
                            "ma20": 170.4,
                        },
                        "yesterday": {
                            "close": 172.28,
                        },
                    },
                    "realtime_context": {
                        "price": 167.52,
                    },
                    "technicals": {
                        "ma20": {"value": 170.4, "status": "ok", "source": "fmp_technical_indicator"},
                        "ma60": {"value": 164.2, "status": "ok", "source": "fmp_technical_indicator"},
                        "rsi14": {"value": 36.4, "status": "ok", "source": "fmp_technical_indicator"},
                    },
                },
            },
        )
        previous_raw_result = {
            "dashboard": {
                "intelligence": {
                    "latest_news": "未发现高价值新增动态",
                },
                "decision_context": {
                    "score_breakdown": [
                        {"label": "技术分", "score": 39, "note": "均线结构偏空", "tone": "danger"},
                        {"label": "基本面分", "score": 72, "note": "盈利能力良好", "tone": "success"},
                    ]
                },
                "structured_analysis": {
                    "time_context": {
                        "market_session_date": "2026-03-27",
                        "session_type": "last_completed_session",
                    },
                    "trend_analysis": {
                        "trend_status": "空头",
                        "ma_alignment": "空头排列 MA5<MA10<MA20",
                        "trend_strength": 28,
                        "volume_status": "放量下跌",
                    },
                    "fundamentals": {
                        "normalized": {
                            "returnOnEquity": 0.42,
                            "returnOnAssets": 0.21,
                            "totalRevenue": 120000000000,
                            "netIncome": 58000000000,
                        },
                        "derived_profiles": {
                            "growth_profile": "high_growth",
                            "profitability_profile": "profitable",
                            "cashflow_profile": "cashflow_healthy",
                            "leverage_profile": "leverage_controllable",
                        },
                    },
                    "sentiment_analysis": {
                        "company_sentiment": "positive",
                        "sentiment_summary": "no_reliable_news",
                    },
                    "data_quality": {
                        "missing_fields": [],
                    },
                    "market_context": {
                        "today": {
                            "close": 167.52,
                            "open": 170.0,
                            "high": 171.2,
                            "low": 166.8,
                            "pct_chg": -2.76,
                            "ma20": 170.4,
                        },
                        "yesterday": {
                            "close": 172.28,
                        },
                    },
                    "realtime_context": {
                        "price": 167.52,
                    },
                    "technicals": {
                        "ma20": {"value": 170.4, "status": "ok", "source": "fmp_technical_indicator"},
                        "ma60": {"value": 164.2, "status": "ok", "source": "fmp_technical_indicator"},
                        "rsi14": {"value": 36.4, "status": "ok", "source": "fmp_technical_indicator"},
                    },
                },
            }
        }
        self.pipeline.db.get_analysis_history = MagicMock(
            return_value=[
                SimpleNamespace(
                    query_id="prev-nvda",
                    sentiment_score=42,
                    operation_advice="观望",
                    trend_prediction="看空",
                    raw_result=json.dumps(previous_raw_result),
                )
            ]
        )

        stabilized = self.pipeline._stabilize_analysis_result(
            code="NVDA",
            query_id="current-nvda",
            result=result,
        )

        self.assertLessEqual(abs(stabilized.sentiment_score - 42), 3)
        self.assertEqual(stabilized.dashboard["decision_context"]["change_reason"], "评分结构重算导致")
        self.assertEqual(stabilized.operation_advice, "观望")


if __name__ == "__main__":
    unittest.main()
