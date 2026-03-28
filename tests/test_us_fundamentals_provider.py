# -*- coding: utf-8 -*-
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider import us_fundamentals_provider as provider
from data_provider.us_fundamentals_provider import (
    get_finnhub_metrics,
    get_finnhub_quote,
    get_fmp_fundamentals,
    get_fmp_historical_prices,
    get_fmp_technical_indicator,
    get_fmp_technical_indicators,
    get_fmp_quarterly_financials,
    get_fmp_quote,
    get_yfinance_fundamentals,
    get_yfinance_quarterly_financials,
)


class _FakeTicker:
    def __init__(self):
        self.info = {
            "marketCap": 123,
            "trailingPE": 20.1,
            "forwardPE": 18.4,
            "priceToBook": 6.2,
            "beta": 1.1,
            "fiftyTwoWeekHigh": 188.5,
            "fiftyTwoWeekLow": 122.1,
            "sharesOutstanding": 9000000,
            "floatShares": 8000000,
            "totalRevenue": 1000,
            "revenueGrowth": 0.22,
            "netIncomeToCommon": 222,
            "grossMargins": 0.7,
            "operatingMargins": 0.31,
            "freeCashflow": 88,
            "operatingCashflow": 99,
            "debtToEquity": 42,
            "currentRatio": 1.5,
            "returnOnEquity": 0.28,
            "returnOnAssets": 0.1,
        }
        self.quarterly_income_stmt = pd.DataFrame(
            {
                pd.Timestamp("2025-12-31"): {
                    "Total Revenue": 120,
                    "Gross Profit": 60,
                    "Operating Income": 30,
                    "Net Income": 20,
                    "Diluted EPS": 1.2,
                },
                pd.Timestamp("2025-09-30"): {
                    "Total Revenue": 100,
                    "Gross Profit": 48,
                    "Operating Income": 24,
                    "Net Income": 18,
                    "Diluted EPS": 1.0,
                },
            }
        )
        self.quarterly_cashflow = pd.DataFrame(
            {
                pd.Timestamp("2025-12-31"): {"Operating Cash Flow": 35},
                pd.Timestamp("2025-09-30"): {"Operating Cash Flow": 30},
            }
        )


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class TestUsFundamentalsProvider(unittest.TestCase):
    def setUp(self) -> None:
        with provider._cache_lock:
            provider._request_cache.clear()

    @patch("yfinance.Ticker", return_value=_FakeTicker())
    def test_get_yfinance_fundamentals_maps_core_fields(self, _mock_ticker):
        payload = get_yfinance_fundamentals("ORCL")
        self.assertEqual(payload["marketCap"], 123)
        self.assertEqual(payload["trailingPE"], 20.1)
        self.assertEqual(payload["freeCashflow"], 88)
        self.assertEqual(payload["priceToBook"], 6.2)
        self.assertEqual(payload["sharesOutstanding"], 9000000)
        self.assertEqual(payload["netIncome"], 222)

    @patch("yfinance.Ticker", return_value=_FakeTicker())
    def test_get_yfinance_quarterly_financials_maps_quarters(self, _mock_ticker):
        rows = get_yfinance_quarterly_financials("ORCL")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["revenue"], 120)
        self.assertEqual(rows[0]["operating_cashflow"], 35)
        self.assertIsNone(rows[0]["free_cash_flow"])

    @patch("data_provider.us_fundamentals_provider.get_config")
    @patch("data_provider.us_fundamentals_provider.requests.get")
    def test_get_finnhub_quote_maps_core_fields(self, mock_get, mock_config):
        mock_config.return_value = SimpleNamespace(finnhub_api_keys=["fh-key"])
        mock_get.return_value = _FakeResponse(
            {
                "c": 125.3,
                "pc": 123.0,
                "d": 2.3,
                "dp": 1.87,
                "h": 126.2,
                "l": 122.9,
                "o": 123.5,
                "t": 1711550100,
            }
        )

        payload = get_finnhub_quote("NVDA")
        self.assertEqual(payload["price"], 125.3)
        self.assertEqual(payload["pre_close"], 123)
        self.assertEqual(payload["change_amount"], 2.3)
        self.assertEqual(payload["change_pct"], 1.87)
        self.assertEqual(payload["amplitude"], 2.6829)
        self.assertEqual(payload["source"], "finnhub")
        self.assertIn("market_timestamp", payload)

    @patch("data_provider.us_fundamentals_provider.get_config")
    @patch("data_provider.us_fundamentals_provider.requests.get")
    def test_get_finnhub_metrics_maps_key_ratios(self, mock_get, mock_config):
        mock_config.return_value = SimpleNamespace(finnhub_api_keys=["fh-key"])
        mock_get.return_value = _FakeResponse(
            {
                "metric": {
                    "beta": 1.2,
                    "peTTM": 32.5,
                    "pbAnnual": 18.6,
                    "52WeekHigh": 142.0,
                    "52WeekLow": 75.0,
                    "currentRatioQuarterly": 1.4,
                    "grossMarginTTM": 0.74,
                    "operatingMarginTTM": 0.41,
                    "roeTTM": 0.55,
                    "roaTTM": 0.33,
                    "totalDebtToEquityQuarterly": 28.0,
                }
            }
        )

        payload = get_finnhub_metrics("NVDA")
        self.assertEqual(payload["beta"], 1.2)
        self.assertEqual(payload["trailingPE"], 32.5)
        self.assertEqual(payload["priceToBook"], 18.6)
        self.assertEqual(payload["fiftyTwoWeekHigh"], 142)
        self.assertEqual(payload["currentRatio"], 1.4)
        self.assertEqual(payload["grossMargins"], 0.74)

    @patch("data_provider.us_fundamentals_provider.get_config")
    @patch("data_provider.us_fundamentals_provider.requests.get")
    def test_get_fmp_quote_derives_amount_from_price_and_volume(self, mock_get, mock_config):
        mock_config.return_value = SimpleNamespace(fmp_api_keys=["fmp-key"])
        mock_get.return_value = _FakeResponse([
            {
                "price": 130.0,
                "previousClose": 128.0,
                "change": 2.0,
                "changesPercentage": 1.56,
                "dayHigh": 131.2,
                "dayLow": 127.6,
                "open": 128.5,
                "volume": 1000000,
                "yearHigh": 145.0,
                "yearLow": 95.0,
                "timestamp": 1711550100,
            }
        ])

        payload = get_fmp_quote("ORCL")
        self.assertEqual(payload["price"], 130.0)
        self.assertEqual(payload["volume"], 1000000)
        self.assertEqual(payload["amount"], 130000000.0)
        self.assertEqual(payload["high_52w"], 145.0)

    @patch("data_provider.us_fundamentals_provider.get_config")
    @patch("data_provider.us_fundamentals_provider.requests.get")
    def test_get_fmp_fundamentals_merges_profile_ratios_and_quarterlies(self, mock_get, mock_config):
        mock_config.return_value = SimpleNamespace(fmp_api_keys=["fmp-key"])

        def _side_effect(url, params=None, headers=None, timeout=15):
            if url.endswith("/quote/ORCL"):
                return _FakeResponse([
                    {
                        "price": 130.0,
                        "previousClose": 128.0,
                        "change": 2.0,
                        "changesPercentage": 1.56,
                        "dayHigh": 131.2,
                        "dayLow": 127.6,
                        "open": 128.5,
                        "volume": 1000000,
                        "yearHigh": 145.0,
                        "yearLow": 95.0,
                        "timestamp": 1711550100,
                    }
                ])
            if url.endswith("/profile/ORCL"):
                return _FakeResponse([
                    {
                        "mktCap": 1000000000,
                        "beta": 1.08,
                        "sharesOutstanding": 2700000000,
                        "floatShares": 2600000000,
                    }
                ])
            if url.endswith("/ratios-ttm/ORCL"):
                return _FakeResponse([
                    {
                        "peRatioTTM": 25.1,
                        "priceToBookRatioTTM": 18.2,
                        "currentRatioTTM": 1.3,
                        "grossProfitMarginTTM": 0.71,
                        "operatingProfitMarginTTM": 0.43,
                        "debtEquityRatioTTM": 510.0,
                        "returnOnEquityTTM": 0.78,
                        "returnOnAssetsTTM": 0.14,
                    }
                ])
            if url.endswith("/income-statement/ORCL"):
                return _FakeResponse([
                    {
                        "date": "2025-12-31",
                        "revenue": 15000,
                        "grossProfit": 10500,
                        "operatingIncome": 6400,
                        "netIncome": 3600,
                        "eps": 1.5,
                    },
                    {
                        "date": "2025-09-30",
                        "revenue": 14500,
                        "grossProfit": 10000,
                        "operatingIncome": 6100,
                        "netIncome": 3400,
                        "eps": 1.4,
                    },
                    {
                        "date": "2025-06-30",
                        "revenue": 14000,
                        "grossProfit": 9800,
                        "operatingIncome": 5900,
                        "netIncome": 3200,
                        "eps": 1.3,
                    },
                    {
                        "date": "2025-03-31",
                        "revenue": 13800,
                        "grossProfit": 9600,
                        "operatingIncome": 5700,
                        "netIncome": 3150,
                        "eps": 1.25,
                    },
                    {
                        "date": "2024-12-31",
                        "revenue": 13000,
                        "grossProfit": 9100,
                        "operatingIncome": 5400,
                        "netIncome": 2900,
                        "eps": 1.1,
                    },
                ])
            if url.endswith("/cash-flow-statement/ORCL"):
                return _FakeResponse([
                    {"date": "2025-12-31", "operatingCashFlow": 4200, "freeCashFlow": 3500},
                    {"date": "2025-09-30", "operatingCashFlow": 4100, "freeCashFlow": 3300},
                    {"date": "2025-06-30", "operatingCashFlow": 4000, "freeCashFlow": 3200},
                    {"date": "2025-03-31", "operatingCashFlow": 3950, "freeCashFlow": 3180},
                    {"date": "2024-12-31", "operatingCashFlow": 3600, "freeCashFlow": 3000},
                ])
            raise AssertionError(f"Unexpected URL: {url}")

        mock_get.side_effect = _side_effect

        payload = get_fmp_fundamentals("ORCL")
        self.assertEqual(payload["marketCap"], 1000000000)
        self.assertEqual(payload["sharesOutstanding"], 2700000000)
        self.assertEqual(payload["floatShares"], 2600000000)
        self.assertEqual(payload["trailingPE"], 25.1)
        self.assertEqual(payload["priceToBook"], 18.2)
        self.assertEqual(payload["fiftyTwoWeekHigh"], 145)
        self.assertEqual(payload["totalRevenue"], 57300)
        self.assertEqual(payload["netIncome"], 13350)
        self.assertEqual(payload["freeCashflow"], 13180)
        self.assertEqual(payload["operatingCashflow"], 16250)
        self.assertEqual(payload["returnOnEquity"], 0.78)
        self.assertEqual(payload["returnOnAssets"], 0.14)
        self.assertAlmostEqual(payload["revenueGrowth"], 0.1538, places=4)
        self.assertAlmostEqual(payload["netIncomeGrowth"], 0.2414, places=4)
        self.assertEqual(payload["_meta"]["field_periods"]["freeCashflow"], "ttm")
        self.assertEqual(payload["_meta"]["field_sources"]["freeCashflow"], "fmp_quarterly")
        self.assertEqual(payload["_meta"]["field_periods"]["returnOnEquity"], "ttm")
        self.assertEqual(payload["_meta"]["field_sources"]["returnOnEquity"], "fmp_ratios_ttm")

    @patch("data_provider.us_fundamentals_provider.get_config")
    @patch("data_provider.us_fundamentals_provider.requests.get")
    def test_get_fmp_fundamentals_preserves_zero_ttm_cashflow_without_falling_back_to_latest_quarter(self, mock_get, mock_config):
        mock_config.return_value = SimpleNamespace(fmp_api_keys=["fmp-key"])

        def _side_effect(url, params=None, headers=None, timeout=15):
            if url.endswith("/quote/ORCL"):
                return _FakeResponse([{"yearHigh": 145.0, "yearLow": 95.0}])
            if url.endswith("/profile/ORCL"):
                return _FakeResponse([{"mktCap": 1000000000, "sharesOutstanding": 2700000000}])
            if url.endswith("/ratios-ttm/ORCL"):
                return _FakeResponse([{"returnOnEquityTTM": 0.78, "returnOnAssetsTTM": 0.14}])
            if url.endswith("/income-statement/ORCL"):
                return _FakeResponse([
                    {"date": "2025-12-31", "revenue": 10, "netIncome": 4},
                    {"date": "2025-09-30", "revenue": 9, "netIncome": 3},
                    {"date": "2025-06-30", "revenue": 8, "netIncome": 2},
                    {"date": "2025-03-31", "revenue": 7, "netIncome": 1},
                ])
            if url.endswith("/cash-flow-statement/ORCL"):
                return _FakeResponse([
                    {"date": "2025-12-31", "operatingCashFlow": 3, "freeCashFlow": 2},
                    {"date": "2025-09-30", "operatingCashFlow": -1, "freeCashFlow": -1},
                    {"date": "2025-06-30", "operatingCashFlow": -1, "freeCashFlow": -1},
                    {"date": "2025-03-31", "operatingCashFlow": -1, "freeCashFlow": 0},
                ])
            raise AssertionError(f"Unexpected URL: {url}")

        mock_get.side_effect = _side_effect

        payload = get_fmp_fundamentals("ORCL")
        self.assertEqual(payload["freeCashflow"], 0.0)
        self.assertEqual(payload["operatingCashflow"], 0.0)
        self.assertEqual(payload["returnOnEquity"], 0.78)
        self.assertEqual(payload["returnOnAssets"], 0.14)
        self.assertEqual(payload["_meta"]["field_periods"]["freeCashflow"], "ttm")
        self.assertEqual(payload["_meta"]["field_sources"]["freeCashflow"], "fmp_quarterly")

    @patch("data_provider.us_fundamentals_provider.get_config")
    @patch("data_provider.us_fundamentals_provider.requests.get")
    def test_get_fmp_quarterly_financials_and_history_normalize_rows(self, mock_get, mock_config):
        mock_config.return_value = SimpleNamespace(fmp_api_keys=["fmp-key"])

        def _side_effect(url, params=None, headers=None, timeout=15):
            if url.endswith("/income-statement/TEM"):
                return _FakeResponse([
                    {"date": "2025-12-31", "revenue": 600, "grossProfit": 300, "operatingIncome": 90, "netIncome": 40, "eps": 0.2},
                    {"date": "2025-09-30", "revenue": 560, "grossProfit": 270, "operatingIncome": 70, "netIncome": 20, "eps": 0.1},
                ])
            if url.endswith("/cash-flow-statement/TEM"):
                return _FakeResponse([
                    {"date": "2025-12-31", "operatingCashFlow": 80, "freeCashFlow": 60},
                    {"date": "2025-09-30", "operatingCashFlow": 75, "freeCashFlow": 58},
                ])
            if url.endswith("/historical-price-full/TEM"):
                return _FakeResponse(
                    {
                        "historical": [
                            {"date": "2025-12-31", "open": 50, "high": 52, "low": 49, "close": 51, "volume": 1000, "vwap": 50.5},
                            {"date": "2025-12-30", "open": 49, "high": 51, "low": 48, "close": 50, "volume": 1200, "vwap": 49.8},
                        ]
                    }
                )
            raise AssertionError(f"Unexpected URL: {url}")

        mock_get.side_effect = _side_effect

        quarters = get_fmp_quarterly_financials("TEM", max_quarters=2)
        history = get_fmp_historical_prices("TEM", days=2)
        self.assertEqual(len(quarters), 2)
        self.assertEqual(quarters[0]["operating_cashflow"], 80)
        self.assertEqual(quarters[0]["free_cash_flow"], 60)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["date"], "2025-12-30")
        self.assertEqual(history[1]["vwap"], 50.5)

    @patch("data_provider.us_fundamentals_provider.get_config")
    @patch("data_provider.us_fundamentals_provider.requests.get")
    def test_get_fmp_technical_indicators_prefers_latest_non_empty_values(self, mock_get, mock_config):
        mock_config.return_value = SimpleNamespace(fmp_api_keys=["fmp-key"])

        def _side_effect(url, params=None, headers=None, timeout=15):
            if url.endswith("/stable/technical-indicators/sma"):
                period = int((params or {}).get("periodLength", 0))
                return _FakeResponse(
                    [
                        {"date": "2025-12-30", "sma": 100 + period},
                        {"date": "2025-12-31", "sma": 101 + period},
                    ]
                )
            if url.endswith("/stable/technical-indicators/rsi"):
                return _FakeResponse(
                    [
                        {"date": "2025-12-30", "rsi": 55.2},
                        {"date": "2025-12-31", "rsi": 56.8},
                    ]
                )
            raise AssertionError(f"Unexpected URL: {url}")

        mock_get.side_effect = _side_effect

        sma_rows = get_fmp_technical_indicator("NVDA", "sma", period_length=20)
        summary = get_fmp_technical_indicators("NVDA")

        self.assertEqual(sma_rows[-1]["value"], 121)
        self.assertEqual(summary["ma5"]["value"], 106)
        self.assertEqual(summary["ma10"]["value"], 111)
        self.assertEqual(summary["ma20"]["value"], 121)
        self.assertEqual(summary["ma60"]["value"], 161)
        self.assertEqual(summary["rsi14"]["value"], 56.8)
        self.assertEqual(summary["ma20"]["source"], "fmp_technical_indicator")


if __name__ == "__main__":
    unittest.main()
