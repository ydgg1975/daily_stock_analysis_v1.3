# -*- coding: utf-8 -*-
"""
Unit tests for Issue #234: intraday realtime technical indicators.

Covers:
- _augment_historical_with_realtime: append/update logic, guards
- _compute_ma_status: MA alignment string
- _enhance_context: today override with realtime + trend_result
"""

import os
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from data_provider.realtime_types import UnifiedRealtimeQuote, RealtimeSource
from src.stock_analyzer import StockTrendAnalyzer, TrendAnalysisResult, TrendStatus
from src.core.pipeline import StockAnalysisPipeline


def _make_realtime_quote(
    price: float = 15.72,
    open_price: float = 15.62,
    high: float = 16.29,
    low: float = 15.55,
    volume: int = 13995600,
    change_pct: float = 0.96,
) -> UnifiedRealtimeQuote:
    return UnifiedRealtimeQuote(
        code="600519",
        name="贵州茅台",
        source=RealtimeSource.TENCENT,
        price=price,
        open_price=open_price,
        high=high,
        low=low,
        volume=volume,
        change_pct=change_pct,
    )


def _make_historical_df(days: int = 25, last_date: date = None) -> pd.DataFrame:
    """Build historical OHLCV DataFrame."""
    if last_date is None:
        last_date = date.today() - timedelta(days=1)
    dates = [last_date - timedelta(days=i) for i in range(days - 1, -1, -1)]
    base = 100.0
    data = []
    for i, d in enumerate(dates):
        close = base + i * 0.5
        data.append({
            "code": "600519",
            "date": d,
            "open": close - 0.2,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": 1000000 + i * 10000,
            "amount": close * (1000000 + i * 10000),
            "pct_chg": 0.5,
            "ma5": close,
            "ma10": close - 0.1,
            "ma20": close - 0.2,
            "volume_ratio": 1.0,
        })
    return pd.DataFrame(data)


class TestAugmentHistoricalWithRealtime(unittest.TestCase):
    """Tests for _augment_historical_with_realtime."""

    def setUp(self) -> None:
        self._db_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "test_issue234.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with patch.dict(os.environ, {"DATABASE_PATH": self._db_path}):
            from src.config import Config
            Config._instance = None
            self.config = Config._load_from_env()
        self.pipeline = StockAnalysisPipeline(config=self.config)

    def test_returns_unchanged_when_realtime_none(self) -> None:
        df = _make_historical_df()
        result = self.pipeline._augment_historical_with_realtime(df, None, "600519")
        self.assertIs(result, df)
        self.assertEqual(len(result), len(df))

    def test_returns_unchanged_when_price_invalid(self) -> None:
        df = _make_historical_df()
        quote = _make_realtime_quote(price=0)
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertEqual(len(result), len(df))
        quote2 = MagicMock()
        quote2.price = None
        result2 = self.pipeline._augment_historical_with_realtime(df, quote2, "600519")
        self.assertEqual(len(result2), len(df))

    def test_returns_unchanged_when_df_empty(self) -> None:
        df = pd.DataFrame()
        quote = _make_realtime_quote()
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertTrue(result.empty)

    def test_returns_unchanged_when_df_missing_close(self) -> None:
        df = pd.DataFrame({"date": [date.today()], "open": [100]})
        quote = _make_realtime_quote()
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertEqual(len(result), 1)
        self.assertNotIn("close", result.columns)

    @patch("src.core.pipeline.is_market_open", return_value=True)
    @patch("src.core.pipeline.get_market_for_stock", return_value="cn")
    def test_appends_row_when_last_date_before_today(
        self, _mock_market, _mock_open
    ) -> None:
        df = _make_historical_df(last_date=date.today() - timedelta(days=1))
        quote = _make_realtime_quote(price=15.72)
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertEqual(len(result), len(df) + 1)
        last = result.iloc[-1]
        self.assertEqual(last["close"], 15.72)
        self.assertEqual(last["date"], date.today())

    @patch("src.core.pipeline.is_market_open", return_value=True)
    @patch("src.core.pipeline.get_market_for_stock", return_value="cn")
    def test_updates_last_row_when_last_date_is_today(
        self, _mock_market, _mock_open
    ) -> None:
        df = _make_historical_df(last_date=date.today(), days=25)
        df.loc[df.index[-1], "date"] = date.today()
        quote = _make_realtime_quote(price=16.0)
        result = self.pipeline._augment_historical_with_realtime(df, quote, "600519")
        self.assertEqual(len(result), len(df))
        self.assertEqual(result.iloc[-1]["close"], 16.0)


class TestComputeMaStatus(unittest.TestCase):
    """Tests for _compute_ma_status."""

    def test_bullish_alignment(self) -> None:
        status = StockAnalysisPipeline._compute_ma_status(11, 10, 9.5, 9)
        self.assertIn("多头", status)

    def test_bearish_alignment(self) -> None:
        status = StockAnalysisPipeline._compute_ma_status(8, 9, 9.5, 10)
        self.assertIn("空头", status)

    def test_consolidation(self) -> None:
        status = StockAnalysisPipeline._compute_ma_status(10, 10, 10, 10)
        self.assertIn("震荡", status)


class TestEnhanceContextRealtimeOverride(unittest.TestCase):
    """Tests for _enhance_context today override with realtime + trend."""

    def setUp(self) -> None:
        self._db_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "test_issue234.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with patch.dict(os.environ, {"DATABASE_PATH": self._db_path}):
            from src.config import Config
            Config._instance = None
            self.config = Config._load_from_env()
        self.pipeline = StockAnalysisPipeline(config=self.config)

    def test_today_overridden_when_realtime_and_trend_exist(self) -> None:
        context = {
            "code": "600519",
            "date": (date.today() - timedelta(days=1)).isoformat(),
            "today": {"close": 15.0, "ma5": 14.8, "ma10": 14.5},
            "yesterday": {"close": 14.5, "volume": 1000000},
            "session_type": "intraday_snapshot",
        }
        quote = _make_realtime_quote(price=15.72, volume=2000000)
        quote.market_timestamp = f"{context['date']}T10:30:00+08:00"
        trend = TrendAnalysisResult(
            code="600519",
            trend_status=TrendStatus.BULL,
            ma5=15.5,
            ma10=15.2,
            ma20=14.9,
        )
        enhanced = self.pipeline._enhance_context(
            context, quote, None, trend, "贵州茅台"
        )
        self.assertEqual(enhanced["today"]["close"], 15.72)
        self.assertEqual(enhanced["today"]["ma5"], 15.5)
        self.assertEqual(enhanced["today"]["ma10"], 15.2)
        self.assertEqual(enhanced["today"]["ma20"], 14.9)
        self.assertIn("多头", enhanced["ma_status"])
        self.assertEqual(enhanced["date"], date.today().isoformat())
        self.assertIn("price_change_ratio", enhanced)
        self.assertIn("volume_change_ratio", enhanced)

    def test_enhance_context_injects_runtime_news_window_days(self) -> None:
        context = {"code": "600519", "today": {"close": 15.0}}
        enhanced = self.pipeline._enhance_context(
            context, None, None, None, "贵州茅台"
        )
        self.assertEqual(
            enhanced["news_window_days"],
            self.pipeline.search_service.news_window_days,
        )

    def test_enhance_context_preserves_realtime_quote_fields_for_standard_report(self) -> None:
        context = {"code": "NVDA", "today": {"close": 125.0}}
        self.pipeline.db.get_latest_data = MagicMock(return_value=[])
        quote = UnifiedRealtimeQuote(
            code="NVDA",
            name="NVIDIA",
            source=RealtimeSource.YFINANCE,
            price=125.3,
            pre_close=123.0,
            change_amount=2.3,
            change_pct=1.87,
            amplitude=2.68,
            open_price=123.5,
            high=126.2,
            low=122.9,
            volume=4500000,
            amount=880000000,
            total_mv=123400000000,
            high_52w=199.876,
            low_52w=99.123,
        )
        enhanced = self.pipeline._enhance_context(
            context, quote, None, None, "NVIDIA"
        )

        self.assertEqual(enhanced["realtime"]["pre_close"], 123.0)
        self.assertEqual(enhanced["realtime"]["change_amount"], 2.3)
        self.assertEqual(enhanced["realtime"]["amplitude"], 2.68)
        self.assertEqual(enhanced["realtime"]["open_price"], 123.5)
        self.assertEqual(enhanced["realtime"]["volume"], 4500000)
        self.assertEqual(enhanced["realtime"]["amount"], 880000000)
        self.assertEqual(enhanced["realtime"]["high_52w"], 199.876)
        self.assertEqual(enhanced["realtime"]["low_52w"], 99.123)

    def test_merge_us_quote_fallbacks_fills_missing_fields(self) -> None:
        quote = UnifiedRealtimeQuote(
            code="NVDA",
            name="NVIDIA",
            source=RealtimeSource.YFINANCE,
            price=125.3,
        )
        merged = self.pipeline._merge_us_quote_fallbacks(
            quote,
            code="NVDA",
            stock_name="NVIDIA",
            payloads=[
                {"pre_close": 123.0, "change_amount": 2.3, "change_pct": 1.87, "source": "finnhub"},
                {"volume": 55000000, "high_52w": 152.5, "low_52w": 76.1, "source": "fmp"},
            ],
        )
        self.assertEqual(merged.pre_close, 123.0)
        self.assertEqual(merged.change_amount, 2.3)
        self.assertEqual(merged.change_pct, 1.87)
        self.assertEqual(merged.volume, 55000000)
        self.assertEqual(merged.high_52w, 152.5)
        self.assertEqual(merged.low_52w, 76.1)

    def test_merge_us_quote_fallbacks_does_not_override_valid_values_with_empty_payloads(self) -> None:
        quote = UnifiedRealtimeQuote(
            code="TSLA",
            name="Tesla",
            source=RealtimeSource.YFINANCE,
            price=362.19,
            pre_close=374.20,
            change_amount=-12.01,
            change_pct=-3.21,
            volume=37254000,
        )

        merged = self.pipeline._merge_us_quote_fallbacks(
            quote,
            code="TSLA",
            stock_name="Tesla",
            payloads=[
                {
                    "price": None,
                    "pre_close": "",
                    "change_amount": "0.0",
                    "change_pct": None,
                    "volume": 0,
                    "source": "finnhub",
                },
                {
                    "price": "0.0",
                    "pre_close": "0",
                    "volume": "0",
                    "market_timestamp": "2026-03-27T13:32:41-04:00",
                    "source": "fmp",
                },
            ],
        )

        self.assertEqual(merged.price, 362.19)
        self.assertEqual(merged.pre_close, 374.20)
        self.assertEqual(merged.change_amount, -12.01)
        self.assertEqual(merged.change_pct, -3.21)
        self.assertEqual(merged.volume, 37254000)
        self.assertEqual(merged.market_timestamp, "2026-03-27T13:32:41-04:00")
        self.assertEqual(merged.source, RealtimeSource.YFINANCE)

    def test_merge_us_quote_fallbacks_keeps_prev_close_when_payload_only_has_close_like_fields(self) -> None:
        quote = UnifiedRealtimeQuote(
            code="NVDA",
            name="NVIDIA",
            source=RealtimeSource.YFINANCE,
            price=167.52,
            pre_close=171.24,
            change_amount=-3.72,
            change_pct=-2.17,
        )

        merged = self.pipeline._merge_us_quote_fallbacks(
            quote,
            code="NVDA",
            stock_name="NVIDIA",
            payloads=[
                {
                    "price": 167.52,
                    "close": 167.52,
                    "regularMarketPrice": 167.52,
                    "change_pct": -2.17,
                    "source": "fmp",
                }
            ],
        )

        self.assertEqual(merged.pre_close, 171.24)
        self.assertEqual(merged.change_amount, -3.72)
        self.assertEqual(merged.change_pct, -2.17)

    def test_today_not_overridden_when_trend_missing(self) -> None:
        context = {"code": "600519", "today": {"close": 15.0}}
        quote = _make_realtime_quote(price=15.72)
        enhanced = self.pipeline._enhance_context(
            context, quote, None, None, "贵州茅台"
        )
        self.assertEqual(enhanced["today"]["close"], 15.0)

    def test_today_not_overridden_when_realtime_missing(self) -> None:
        context = {"code": "600519", "today": {"close": 15.0}}
        trend = TrendAnalysisResult(code="600519", ma5=15.0, ma10=14.8, ma20=14.5)
        enhanced = self.pipeline._enhance_context(
            context, None, None, trend, "贵州茅台"
        )
        self.assertEqual(enhanced["today"]["close"], 15.0)

    def test_last_completed_session_keeps_eod_today_even_with_realtime_and_trend(self) -> None:
        context = {
            "code": "NVDA",
            "today": {
                "close": 167.52,
                "open": 170.10,
                "high": 171.10,
                "low": 166.90,
                "volume": 45670000,
                "pct_chg": -2.76,
                "data_source": "yfinance_eod",
            },
            "session_type": "last_completed_session",
        }
        quote = _make_realtime_quote(
            price=168.99,
            change_pct=-1.91,
            volume=99999999,
        )
        trend = TrendAnalysisResult(code="NVDA", ma5=168.1, ma10=169.5, ma20=170.4)
        enhanced = self.pipeline._enhance_context(context, quote, None, trend, "NVIDIA")

        self.assertEqual(enhanced["today"]["close"], 167.52)
        self.assertEqual(enhanced["today"]["open"], 170.10)
        self.assertEqual(enhanced["today"]["volume"], 45670000)
        self.assertEqual(enhanced["today"]["data_source"], "yfinance_eod")

    def test_us_stock_computes_volume_ratio_and_turnover(self) -> None:
        context = {
            "code": "AAPL",
            "date": date.today().isoformat(),
            "today": {"volume": 1200, "close": 180.0},
            "yesterday": {"volume": 900},
        }
        quote = UnifiedRealtimeQuote(
            code="AAPL",
            name="Apple",
            source=RealtimeSource.YFINANCE,
            price=181.0,
            volume=1200,
        )
        bars = [MagicMock(date=date.today() - timedelta(days=i), volume=v) for i, v in enumerate([1200, 1000, 1100, 900, 1000, 1000])]
        self.pipeline.db.get_latest_data = MagicMock(return_value=bars)

        enhanced = self.pipeline._enhance_context(
            context, quote, None, None, "Apple", shares_outstanding=10000
        )

        self.assertEqual(enhanced["realtime"]["volume_ratio"], 1.2)
        self.assertAlmostEqual(enhanced["realtime"]["turnover_rate"], 12.0, places=4)

    def test_us_stock_can_use_external_history_for_volume_ratio(self) -> None:
        context = {"code": "AAPL", "today": {"volume": 1200, "close": 180.0}}
        quote = UnifiedRealtimeQuote(
            code="AAPL",
            name="Apple",
            source=RealtimeSource.FMP,
            price=181.0,
            volume=1200,
        )
        self.pipeline.db.get_latest_data = MagicMock(return_value=[])
        enhanced = self.pipeline._enhance_context(
            context,
            quote,
            None,
            None,
            "Apple",
            shares_outstanding=10000,
            fallback_history=[
                {"date": "2025-12-20", "volume": 1000},
                {"date": "2025-12-21", "volume": 1100},
                {"date": "2025-12-22", "volume": 900},
                {"date": "2025-12-23", "volume": 1000},
                {"date": "2025-12-24", "volume": 1000},
            ],
        )
        self.assertEqual(enhanced["realtime"]["volume_ratio"], 1.2)

    def test_us_stock_missing_shares_keeps_turnover_missing(self) -> None:
        context = {"code": "AAPL", "today": {"volume": 1200}}
        quote = UnifiedRealtimeQuote(
            code="AAPL",
            source=RealtimeSource.YFINANCE,
            price=181.0,
            volume=1200,
        )
        self.pipeline.db.get_latest_data = MagicMock(return_value=[])
        enhanced = self.pipeline._enhance_context(
            context, quote, None, None, "Apple", shares_outstanding=None
        )
        self.assertEqual(enhanced["realtime"]["turnover_rate"], "数据缺失")

    def test_us_stock_zero_placeholder_metrics_mark_missing_in_context(self) -> None:
        context = {"code": "TSLA", "today": {"volume": 37254000, "close": 362.19}}
        quote = UnifiedRealtimeQuote(
            code="TSLA",
            source=RealtimeSource.FINNHUB,
            price=362.19,
            volume=37254000,
            volume_ratio=0.0,
            turnover_rate=0.0,
        )
        self.pipeline.db.get_latest_data = MagicMock(return_value=[])

        enhanced = self.pipeline._enhance_context(
            context, quote, None, None, "Tesla", shares_outstanding=None
        )

        self.assertEqual(enhanced["realtime"]["volume_ratio"], "数据缺失")
        self.assertEqual(enhanced["realtime"]["turnover_rate"], "数据缺失")

    def test_today_not_overridden_when_trend_ma_zero(self) -> None:
        """When StockTrendAnalyzer returns early (data insufficient), ma5=0.0. Must not override."""
        context = {"code": "600519", "today": {"close": 15.0, "ma5": 14.8}}
        quote = _make_realtime_quote(price=15.72)
        trend = TrendAnalysisResult(code="600519")  # defaults: ma5=ma10=ma20=0.0
        enhanced = self.pipeline._enhance_context(
            context, quote, None, trend, "贵州茅台"
        )
        self.assertEqual(enhanced["today"]["close"], 15.0)
        self.assertEqual(enhanced["today"]["ma5"], 14.8)

    def test_fetch_and_save_us_stock_falls_back_to_realtime_snapshot_when_daily_fails(self) -> None:
        self.pipeline.fetcher_manager.get_stock_name = MagicMock(return_value="Apple")
        self.pipeline.fetcher_manager.get_daily_data = MagicMock(side_effect=RuntimeError("daily fetch failed"))
        self.pipeline.fetcher_manager.get_realtime_quote = MagicMock(
            return_value=UnifiedRealtimeQuote(
                code="AAPL",
                name="Apple",
                source=RealtimeSource.STOOQ,
                price=251.64,
                open_price=250.0,
                high=252.2,
                low=249.8,
                volume=123456,
                change_pct=0.8,
            )
        )
        self.pipeline.db.has_today_data = MagicMock(return_value=False)
        self.pipeline.db.save_daily_data = MagicMock(return_value=1)

        ok, err = self.pipeline.fetch_and_save_stock_data("AAPL", force_refresh=True)

        self.assertTrue(ok)
        self.assertIsNone(err)
        args, _ = self.pipeline.db.save_daily_data.call_args
        self.assertEqual(args[0].iloc[0]["close"], 251.64)
        self.assertEqual(args[1], "AAPL")
        self.assertEqual(args[2], "stooq_realtime_snapshot")
        self.pipeline.fetcher_manager.get_daily_data.assert_called_once_with("AAPL", days=180)

    def test_fetch_and_save_us_stock_backfills_history_when_today_row_exists_but_bars_insufficient(self) -> None:
        self.pipeline.fetcher_manager.get_stock_name = MagicMock(return_value="NVIDIA")
        self.pipeline.fetcher_manager.get_daily_data = MagicMock(
            return_value=(_make_historical_df(days=70, last_date=date.today()), "yfinance")
        )
        self.pipeline.fetcher_manager.get_realtime_quote = MagicMock(return_value=None)
        self.pipeline.db.has_today_data = MagicMock(return_value=True)
        self.pipeline.db.get_latest_data = MagicMock(
            return_value=[
                MagicMock(date=date.today(), close=168.99, volume=100),
                MagicMock(date=date.today() - timedelta(days=1), close=171.24, volume=100),
            ]
        )
        self.pipeline.db.save_daily_data = MagicMock(return_value=70)

        ok, err = self.pipeline.fetch_and_save_stock_data("NVDA", force_refresh=False)

        self.assertTrue(ok)
        self.assertIsNone(err)
        self.pipeline.fetcher_manager.get_daily_data.assert_called_once_with("NVDA", days=180)
        self.pipeline.db.save_daily_data.assert_called_once()

    def test_build_us_realtime_snapshot_df_uses_market_trade_date(self) -> None:
        self.pipeline.fetcher_manager.get_realtime_quote = MagicMock(
            return_value=UnifiedRealtimeQuote(
                code="NVDA",
                name="NVIDIA",
                source=RealtimeSource.YFINANCE,
                price=167.52,
                open_price=169.99,
                high=170.97,
                low=167.01,
                volume=194056113,
                change_pct=-2.76,
                market_timestamp="2026-03-27T16:00:00-04:00",
            )
        )

        df, source = self.pipeline._build_us_realtime_snapshot_df("NVDA")

        self.assertEqual(source, "yfinance_realtime_snapshot")
        self.assertIsNotNone(df)
        assert df is not None
        self.assertEqual(df.iloc[0]["date"], "2026-03-27")

    def test_us_stock_volume_ratio_marks_missing_when_history_insufficient(self) -> None:
        context = {
            "code": "AAPL",
            "date": date.today().isoformat(),
            "today": {"volume": 1000},
        }
        quote = UnifiedRealtimeQuote(
            code="AAPL",
            source=RealtimeSource.STOOQ,
            price=200.0,
            volume=1000,
        )
        self.pipeline.db.get_latest_data = MagicMock(return_value=[])
        enhanced = self.pipeline._enhance_context(
            context, quote, None, None, "Apple", shares_outstanding=10000
        )
        self.assertEqual(enhanced["realtime"]["volume_ratio"], "数据缺失")


if __name__ == "__main__":
    unittest.main()
