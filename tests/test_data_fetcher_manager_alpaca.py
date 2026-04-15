# -*- coding: utf-8 -*-
"""Tests for Alpaca routing inside DataFetcherManager realtime quotes."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from data_provider.base import DataFetcherManager
from data_provider.provider_credentials import ProviderCredentialBundle
from data_provider.realtime_types import RealtimeSource, UnifiedRealtimeQuote


class _YfinanceStub:
    name = "YfinanceFetcher"
    priority = 4

    def __init__(self, quote: UnifiedRealtimeQuote | None, daily_result=None) -> None:
        self.quote = quote
        self.daily_result = daily_result
        self.calls: list[str] = []
        self.daily_calls: list[str] = []

    def get_realtime_quote(self, stock_code: str):
        self.calls.append(stock_code)
        return self.quote

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30):
        _ = (start_date, end_date, days)
        self.daily_calls.append(stock_code)
        return self.daily_result


class _AlpacaStub:
    def __init__(self, quote: UnifiedRealtimeQuote | None, daily_result=None, daily_error: Exception | None = None) -> None:
        self.quote = quote
        self.daily_result = daily_result
        self.daily_error = daily_error
        self.calls: list[str] = []
        self.daily_calls: list[str] = []

    def get_realtime_quote(self, stock_code: str):
        self.calls.append(stock_code)
        return self.quote

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30):
        _ = (start_date, end_date, days)
        self.daily_calls.append(stock_code)
        if self.daily_error is not None:
            raise self.daily_error
        return self.daily_result


class DataFetcherManagerAlpacaTestCase(unittest.TestCase):
    def test_us_quote_prefers_alpaca_when_configured(self) -> None:
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=210.0)
        )
        manager = DataFetcherManager(fetchers=[yfinance])
        alpaca = _AlpacaStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.ALPACA, price=214.0)
        )

        with patch("data_provider.base.get_provider_credentials") as mock_credentials:
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="alpaca-id",
                secret_key="alpaca-secret",
                extras={"data_feed": "iex"},
            )
            with patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca):
                quote = manager.get_realtime_quote("AAPL")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.source, RealtimeSource.ALPACA)
        self.assertEqual(alpaca.calls, ["AAPL"])
        self.assertEqual(yfinance.calls, [])
        trace = manager.get_last_realtime_quote_trace()
        self.assertTrue(any(item["provider"] == "alpaca" and item["action"] == "succeeded" for item in trace))

    def test_us_quote_falls_back_to_yfinance_when_alpaca_returns_none(self) -> None:
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=210.0)
        )
        manager = DataFetcherManager(fetchers=[yfinance])
        alpaca = _AlpacaStub(None)

        with patch("data_provider.base.get_provider_credentials") as mock_credentials:
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="alpaca-id",
                secret_key="alpaca-secret",
                extras={"data_feed": "iex"},
            )
            with patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca):
                quote = manager.get_realtime_quote("AAPL")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.source, RealtimeSource.YFINANCE)
        self.assertEqual(alpaca.calls, ["AAPL"])
        self.assertEqual(yfinance.calls, ["AAPL"])
        trace = manager.get_last_realtime_quote_trace()
        self.assertTrue(any(item["provider"] == "alpaca" and item["action"] == "failed" for item in trace))
        self.assertTrue(any(item["provider"] == "yfinance" and item["action"] == "succeeded" for item in trace))

    def test_us_quote_marks_alpaca_as_skipped_when_not_configured(self) -> None:
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=210.0)
        )
        manager = DataFetcherManager(fetchers=[yfinance])

        with patch("data_provider.base.get_provider_credentials") as mock_credentials:
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                extras={"data_feed": "iex"},
            )
            quote = manager.get_realtime_quote("AAPL")

        self.assertIsNotNone(quote)
        trace = manager.get_last_realtime_quote_trace()
        self.assertTrue(any(item["provider"] == "alpaca" and item["action"] == "skipped" for item in trace))

    def test_us_daily_history_prefers_alpaca_when_configured(self) -> None:
        daily_frame = pd.DataFrame(
            [
                {"date": "2026-04-11", "close": 100.0},
                {"date": "2026-04-14", "close": 101.2},
            ]
        )
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=210.0),
            daily_result=(daily_frame, "YfinanceFetcher"),
        )
        manager = DataFetcherManager(fetchers=[yfinance])
        alpaca = _AlpacaStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.ALPACA, price=214.0),
            daily_result=(daily_frame, "AlpacaFetcher"),
        )

        with patch("data_provider.base.get_provider_credentials") as mock_credentials:
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="alpaca-id",
                secret_key="alpaca-secret",
                extras={"data_feed": "iex"},
            )
            with patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca):
                frame, source = manager.get_daily_data("AAPL", days=20)

        self.assertIs(frame, daily_frame)
        self.assertEqual(source, "AlpacaFetcher")
        self.assertEqual(alpaca.daily_calls, ["AAPL"])
        self.assertEqual(yfinance.daily_calls, [])

    def test_us_daily_history_falls_back_to_yfinance_when_alpaca_fails(self) -> None:
        daily_frame = pd.DataFrame(
            [
                {"date": "2026-04-10", "close": 98.5},
                {"date": "2026-04-11", "close": 100.0},
                {"date": "2026-04-14", "close": 101.2},
            ]
        )
        yfinance = _YfinanceStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.YFINANCE, price=210.0),
            daily_result=(daily_frame, "YfinanceFetcher"),
        )
        manager = DataFetcherManager(fetchers=[yfinance])
        alpaca = _AlpacaStub(
            UnifiedRealtimeQuote(code="AAPL", source=RealtimeSource.ALPACA, price=214.0),
            daily_error=RuntimeError("alpaca timeout"),
        )

        with patch("data_provider.base.get_provider_credentials") as mock_credentials:
            mock_credentials.return_value = ProviderCredentialBundle(
                provider="alpaca",
                auth_mode="key_secret",
                key_id="alpaca-id",
                secret_key="alpaca-secret",
                extras={"data_feed": "iex"},
            )
            with patch.object(manager, "_get_alpaca_fetcher", return_value=alpaca):
                frame, source = manager.get_daily_data("AAPL", days=20)

        self.assertIs(frame, daily_frame)
        self.assertEqual(source, "YfinanceFetcher")
        self.assertEqual(alpaca.daily_calls, ["AAPL"])
        self.assertEqual(yfinance.daily_calls, ["AAPL"])


if __name__ == "__main__":
    unittest.main()
