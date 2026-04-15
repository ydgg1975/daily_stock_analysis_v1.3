# -*- coding: utf-8 -*-
"""Tests for HK routing inside DataFetcherManager realtime quotes."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from data_provider.base import DataFetcherManager
from data_provider.realtime_types import RealtimeSource, UnifiedRealtimeQuote


class _AkshareHkStub:
    name = "AkshareFetcher"
    priority = 2

    def __init__(self, quote: UnifiedRealtimeQuote | None) -> None:
        self.quote = quote
        self.calls: list[tuple[str, str | None]] = []

    def get_realtime_quote(self, stock_code: str, source: str | None = None):
        self.calls.append((stock_code, source))
        return self.quote


class _TwelveDataStub:
    def __init__(self, quote: UnifiedRealtimeQuote | None) -> None:
        self.quote = quote
        self.calls: list[str] = []

    def get_realtime_quote(self, stock_code: str):
        self.calls.append(stock_code)
        return self.quote


class DataFetcherManagerTwelveDataTestCase(unittest.TestCase):
    def test_hk_quote_prefers_twelve_data_when_available(self) -> None:
        akshare = _AkshareHkStub(
            UnifiedRealtimeQuote(code="HK00700", source=RealtimeSource.AKSHARE_EM, price=500.0)
        )
        manager = DataFetcherManager(fetchers=[akshare])
        twelve_data = _TwelveDataStub(
            UnifiedRealtimeQuote(code="HK00700", source=RealtimeSource.TWELVE_DATA, price=503.5)
        )

        with patch.object(manager, "_get_twelve_data_fetcher", return_value=twelve_data):
            quote = manager.get_realtime_quote("HK00700")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.source, RealtimeSource.TWELVE_DATA)
        self.assertEqual(twelve_data.calls, ["HK00700"])
        self.assertEqual(akshare.calls, [])

    def test_hk_quote_falls_back_to_akshare_when_twelve_data_returns_none(self) -> None:
        akshare = _AkshareHkStub(
            UnifiedRealtimeQuote(code="HK00700", source=RealtimeSource.AKSHARE_EM, price=500.0)
        )
        manager = DataFetcherManager(fetchers=[akshare])
        twelve_data = _TwelveDataStub(None)

        with patch.object(manager, "_get_twelve_data_fetcher", return_value=twelve_data):
            quote = manager.get_realtime_quote("HK00700")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.source, RealtimeSource.AKSHARE_EM)
        self.assertEqual(twelve_data.calls, ["HK00700"])
        self.assertEqual(akshare.calls, [("HK00700", "hk")])


if __name__ == "__main__":
    unittest.main()
