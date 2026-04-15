# -*- coding: utf-8 -*-
"""Tests for Twelve Data market-data fetcher."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from data_provider.realtime_types import RealtimeSource
from data_provider.twelve_data_fetcher import TwelveDataFetcher


class _MockResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class TwelveDataFetcherTestCase(unittest.TestCase):
    def test_get_realtime_quote_builds_hk_quote(self) -> None:
        session = Mock()
        session.get.return_value = _MockResponse(
            {
                "symbol": "0700",
                "name": "Tencent Holdings Limited",
                "exchange": "HKEX",
                "close": "503.5",
                "previous_close": "496.0",
                "percent_change": "1.51",
                "change": "7.5",
                "volume": "12345000",
                "open": "500.0",
                "high": "505.0",
                "low": "498.0",
                "datetime": "2026-04-15",
            }
        )
        fetcher = TwelveDataFetcher(
            api_key="td-key",
            session=session,
        )

        quote = fetcher.get_realtime_quote("HK00700")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.source, RealtimeSource.TWELVE_DATA)
        self.assertEqual(quote.code, "HK00700")
        self.assertEqual(quote.name, "Tencent Holdings Limited")
        self.assertAlmostEqual(float(quote.price or 0.0), 503.5, places=2)
        self.assertAlmostEqual(float(quote.pre_close or 0.0), 496.0, places=2)
        self.assertEqual(quote.volume, 12_345_000)
        session.get.assert_called_once_with(
            "https://api.twelvedata.com/quote",
            params={
                "symbol": "0700",
                "exchange": "HKEX",
                "apikey": "td-key",
            },
            timeout=15,
            headers={"Accept": "application/json"},
        )

    def test_get_daily_data_normalizes_hk_time_series(self) -> None:
        session = Mock()
        session.get.return_value = _MockResponse(
            {
                "meta": {"symbol": "0700", "exchange": "HKEX", "interval": "1day"},
                "values": [
                    {"datetime": "2026-04-15", "open": "500.0", "high": "505.0", "low": "498.0", "close": "503.5", "volume": "12345000"},
                    {"datetime": "2026-04-14", "open": "492.0", "high": "498.0", "low": "490.5", "close": "496.0", "volume": "11345000"},
                ],
            }
        )
        fetcher = TwelveDataFetcher(
            api_key="td-key",
            session=session,
        )

        frame, source = fetcher.get_daily_data("HK00700", start_date="2026-04-10", end_date="2026-04-15", days=10)

        self.assertEqual(source, "TwelveDataFetcher")
        self.assertEqual(list(frame["code"].unique()), ["HK00700"])
        self.assertEqual(frame.iloc[-1]["close"], 503.5)
        self.assertIn("pct_chg", frame.columns)
        self.assertGreater(float(frame.iloc[-1]["amount"]), 0.0)
        session.get.assert_called_once()
        args, kwargs = session.get.call_args
        self.assertEqual(args[0], "https://api.twelvedata.com/time_series")
        self.assertEqual(kwargs["params"]["symbol"], "0700")
        self.assertEqual(kwargs["params"]["exchange"], "HKEX")
        self.assertEqual(kwargs["params"]["interval"], "1day")


if __name__ == "__main__":
    unittest.main()
