# -*- coding: utf-8 -*-
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.us_fundamentals_provider import get_yfinance_fundamentals, get_yfinance_quarterly_financials


class _FakeTicker:
    def __init__(self):
        self.info = {
            "marketCap": 123,
            "trailingPE": 20.1,
            "forwardPE": 18.4,
            "totalRevenue": 1000,
            "revenueGrowth": 0.22,
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


class TestUsFundamentalsProvider(unittest.TestCase):
    @patch("yfinance.Ticker", return_value=_FakeTicker())
    def test_get_yfinance_fundamentals_maps_core_fields(self, _mock_ticker):
        payload = get_yfinance_fundamentals("ORCL")
        self.assertEqual(payload["marketCap"], 123)
        self.assertEqual(payload["trailingPE"], 20.1)
        self.assertEqual(payload["freeCashflow"], 88)

    @patch("yfinance.Ticker", return_value=_FakeTicker())
    def test_get_yfinance_quarterly_financials_maps_quarters(self, _mock_ticker):
        rows = get_yfinance_quarterly_financials("ORCL")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["revenue"], 120)
        self.assertEqual(rows[0]["operating_cashflow"], 35)


if __name__ == "__main__":
    unittest.main()
