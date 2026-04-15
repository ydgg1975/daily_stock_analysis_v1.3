# -*- coding: utf-8 -*-
"""Tests for Alpaca market-data fetcher."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from data_provider.alpaca_fetcher import AlpacaFetcher
from data_provider.realtime_types import RealtimeSource


class _MockResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class AlpacaFetcherTestCase(unittest.TestCase):
    def test_get_realtime_quote_builds_quote_from_snapshot(self) -> None:
        session = Mock()
        session.get.return_value = _MockResponse(
            {
                "latestTrade": {"p": 214.55, "t": "2026-04-14T13:30:00Z"},
                "latestQuote": {"ap": 214.6, "bp": 214.5, "t": "2026-04-14T13:30:00Z"},
                "dailyBar": {"o": 210.0, "h": 215.2, "l": 209.8, "c": 214.0, "v": 123456, "vw": 213.2},
                "prevDailyBar": {"c": 208.1},
            }
        )
        fetcher = AlpacaFetcher(
            api_key_id="alpaca-id",
            secret_key="alpaca-secret",
            data_feed="sip",
            session=session,
        )

        quote = fetcher.get_realtime_quote("AAPL")

        self.assertIsNotNone(quote)
        assert quote is not None
        self.assertEqual(quote.source, RealtimeSource.ALPACA)
        self.assertEqual(quote.code, "AAPL")
        self.assertAlmostEqual(float(quote.price or 0.0), 214.55, places=2)
        self.assertAlmostEqual(float(quote.pre_close or 0.0), 208.1, places=2)
        self.assertEqual(quote.volume, 123456)
        session.get.assert_called_once_with(
            "https://data.alpaca.markets/v2/stocks/AAPL/snapshot",
            params={"feed": "sip"},
            headers={
                "APCA-API-KEY-ID": "alpaca-id",
                "APCA-API-SECRET-KEY": "alpaca-secret",
                "Accept": "application/json",
            },
            timeout=15,
        )

    def test_get_daily_data_requests_adjusted_bars(self) -> None:
        session = Mock()
        session.get.return_value = _MockResponse(
            {
                "bars": [
                    {"t": "2026-04-11T00:00:00Z", "o": 100.0, "h": 101.0, "l": 99.5, "c": 100.4, "v": 1000, "vw": 100.2},
                    {"t": "2026-04-14T00:00:00Z", "o": 100.5, "h": 102.0, "l": 100.0, "c": 101.6, "v": 1200, "vw": 101.1},
                ]
            }
        )
        fetcher = AlpacaFetcher(
            api_key_id="alpaca-id",
            secret_key="alpaca-secret",
            session=session,
        )

        frame, source = fetcher.get_daily_data("AAPL", start_date="2026-04-10", end_date="2026-04-15", days=10)

        self.assertEqual(source, "AlpacaFetcher")
        self.assertEqual(list(frame["code"].unique()), ["AAPL"])
        self.assertIn("pct_chg", frame.columns)
        session.get.assert_called_once()
        args, kwargs = session.get.call_args
        self.assertEqual(args[0], "https://data.alpaca.markets/v2/stocks/AAPL/bars")
        self.assertEqual(kwargs["params"]["timeframe"], "1Day")
        self.assertEqual(kwargs["params"]["adjustment"], "all")
        self.assertEqual(kwargs["params"]["feed"], "iex")


if __name__ == "__main__":
    unittest.main()
