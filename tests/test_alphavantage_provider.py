# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from data_provider import alphavantage_provider as av


class TestAlphaVantageProvider(unittest.TestCase):
    def setUp(self) -> None:
        av._overview_cache.clear()
        av._income_cache.clear()

    @patch("data_provider.alphavantage_provider._request")
    def test_get_shares_outstanding_parses_int(self, mock_request) -> None:
        mock_request.return_value = {"SharesOutstanding": "15200000000"}
        self.assertEqual(av.get_shares_outstanding("AAPL"), 15200000000)

    @patch("data_provider.alphavantage_provider._request")
    def test_get_company_overview_uses_cache(self, mock_request) -> None:
        mock_request.return_value = {"Symbol": "AAPL", "SharesOutstanding": "100"}
        first = av.get_company_overview("AAPL")
        second = av.get_company_overview("AAPL")
        self.assertEqual(first, second)
        mock_request.assert_called_once()

    @patch("data_provider.alphavantage_provider._request")
    def test_get_income_statement_quarterly_parses_and_caches(self, mock_request) -> None:
        mock_request.return_value = {
            "quarterlyReports": [
                {
                    "fiscalDateEnding": "2025-12-31",
                    "totalRevenue": "120000000",
                    "grossProfit": "70000000",
                    "operatingIncome": "25000000",
                    "netIncome": "20000000",
                    "reportedEPS": "1.2",
                }
            ]
        }
        first = av.get_income_statement_quarterly("ORCL")
        second = av.get_income_statement_quarterly("ORCL")
        self.assertEqual(first[0]["revenue"], 120000000.0)
        self.assertEqual(first, second)
        mock_request.assert_called_once()
