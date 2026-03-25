# -*- coding: utf-8 -*-
import os
import sys
import unittest
from datetime import date, timedelta, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.pipeline import StockAnalysisPipeline


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


if __name__ == "__main__":
    unittest.main()
