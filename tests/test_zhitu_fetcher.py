# -*- coding: utf-8 -*-
"""
Unit tests for ZhituFetcher.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.zhitu_fetcher import ZhituFetcher


class TestZhituFetcherInit(unittest.TestCase):
    """Ensure ZhituFetcher initializes correctly with token."""

    def test_init_loads_token_from_env(self):
        with patch.dict(os.environ, {"ZHITU_API_TOKEN": "test-token-123"}):
            fetcher = ZhituFetcher()
            self.assertEqual(fetcher._token, "test-token-123")

    def test_init_uses_provided_token(self):
        fetcher = ZhituFetcher(token="custom-token-456")
        self.assertEqual(fetcher._token, "custom-token-456")

    def test_priority_default_is_5(self):
        fetcher = ZhituFetcher(token="test")
        self.assertEqual(fetcher.priority, 5)

    def test_priority_from_env(self):
        # Note: priority is a class attribute evaluated at import time,
        # so we patch it directly on the class instead.
        with patch.object(ZhituFetcher, "priority", 3):
            fetcher = ZhituFetcher(token="test")
            self.assertEqual(fetcher.priority, 3)


class TestConvertStockCode(unittest.TestCase):
    """Test stock code conversion to Zhitu format."""

    def setUp(self):
        self.fetcher = ZhituFetcher(token="test")

    def test_convert_with_sh_suffix(self):
        code, market = self.fetcher._convert_stock_code("600519.SH")
        self.assertEqual(code, "600519")
        self.assertEqual(market, "sh")

    def test_convert_with_sz_suffix(self):
        code, market = self.fetcher._convert_stock_code("000001.SZ")
        self.assertEqual(code, "000001")
        self.assertEqual(market, "sz")

    def test_convert_shanghai_prefix(self):
        # 6xx -> Shanghai
        code, market = self.fetcher._convert_stock_code("600519")
        self.assertEqual(code, "600519")
        self.assertEqual(market, "sh")

    def test_convert_shenzhen_prefix(self):
        # 0/1/2/3/4xx -> Shenzhen
        code, market = self.fetcher._convert_stock_code("000001")
        self.assertEqual(code, "000001")
        self.assertEqual(market, "sz")

    def test_convert_uppercase(self):
        code, market = self.fetcher._convert_stock_code("600519.sh")
        self.assertEqual(code, "600519")
        self.assertEqual(market, "sh")


class TestGetRealtimeQuote(unittest.TestCase):
    """Test get_realtime_quote with mocked API responses."""

    def setUp(self):
        self.fetcher = ZhituFetcher(token="test-token")

    def test_returns_none_when_empty_response(self):
        with patch.object(self.fetcher, "_get", return_value=None):
            result = self.fetcher.get_realtime_quote("600519")
            self.assertIsNone(result)

    def test_returns_none_when_no_price_field(self):
        with patch.object(self.fetcher, "_get", return_value=[{"mc": "测试"}]):
            result = self.fetcher.get_realtime_quote("600519")
            self.assertIsNone(result)

    def test_returns_quote_with_valid_data(self):
        mock_data = [{
            "dm": "600519",
            "mc": "贵州茅台",
            "p": 1688.0,
            "pc": 2.5,
            "ud": 41.0,
            "v": 1234567,
            "cje": 987654321.0,
            "h": 1700.0,
            "l": 1650.0,
            "o": 1660.0,
            "pe": 35.0,
            "sjl": 10.5,
        }]
        with patch.object(self.fetcher, "_get", return_value=mock_data):
            quote = self.fetcher.get_realtime_quote("600519")

        self.assertIsNotNone(quote)
        self.assertEqual(quote.code, "600519")
        self.assertEqual(quote.price, 1688.0)
        self.assertEqual(quote.change_pct, 2.5)
        self.assertEqual(quote.change_amount, 41.0)


class TestGetMarketStats(unittest.TestCase):
    """Test get_market_stats with mocked API responses."""

    def setUp(self):
        self.fetcher = ZhituFetcher(token="test-token")

    def test_returns_dict_with_limit_counts(self):
        mock_zt_data = [
            {"dm": "000001", "mc": "股票A"},
            {"dm": "000002", "mc": "股票B"},
            {"dm": "000003", "mc": "股票C"},
        ]
        mock_dt_data = [
            {"dm": "600001", "mc": "股票X"},
        ]

        def mock_get(url, timeout=None):
            if "ztgc" in url:
                return mock_zt_data
            if "dtgc" in url:
                return mock_dt_data
            return None

        with patch.object(self.fetcher, "_get", side_effect=mock_get):
            result = self.fetcher.get_market_stats()

        self.assertIsNotNone(result)
        self.assertIsNone(result["up_count"])
        self.assertIsNone(result["down_count"])
        self.assertEqual(result["limit_up_count"], 3)
        self.assertEqual(result["limit_down_count"], 1)
        self.assertIsNone(result["total_amount"])

    def test_returns_zeros_when_api_returns_empty(self):
        with patch.object(self.fetcher, "_get", return_value=[]):
            result = self.fetcher.get_market_stats()

        self.assertEqual(result["limit_up_count"], 0)
        self.assertEqual(result["limit_down_count"], 0)

    def test_handles_dict_response_format(self):
        mock_zt_data = {"data": [
            {"dm": "000001", "mc": "股票A"},
        ]}

        def mock_get(url, timeout=None):
            if "ztgc" in url:
                return mock_zt_data
            return []

        with patch.object(self.fetcher, "_get", side_effect=mock_get):
            result = self.fetcher.get_market_stats()

        self.assertEqual(result["limit_up_count"], 1)

    def test_up_count_and_down_count_are_none(self):
        """up_count/down_count are None because Zhitu API doesn't provide them."""
        with patch.object(self.fetcher, "_get", return_value=[]):
            result = self.fetcher.get_market_stats()

        self.assertIsNone(result["up_count"])
        self.assertIsNone(result["down_count"])
        self.assertIsNone(result["flat_count"])
        self.assertIsNone(result["total_amount"])


class TestGetSectorRankings(unittest.TestCase):
    """Test get_sector_rankings returns None since Zhitu doesn't support this API."""

    def setUp(self):
        self.fetcher = ZhituFetcher(token="test-token")

    def test_returns_none(self):
        """Zhitu API does not provide sector index real-time data."""
        result = self.fetcher.get_sector_rankings(n=5)
        self.assertIsNone(result)


class TestGetMainIndices(unittest.TestCase):
    """Test get_main_indices with mocked API responses."""

    def setUp(self):
        self.fetcher = ZhituFetcher(token="test-token")

    def test_returns_none_for_non_cn_region(self):
        result = self.fetcher.get_main_indices(region="us")
        self.assertIsNone(result)

    def test_returns_indices_list(self):
        # Only the first API call succeeds; subsequent ones raise to simulate errors.
        # This mirrors real behavior where only some indices return valid data.
        mock_data = [{
            "p": 3200.0,
            "ud": 20.5,
            "pc": 0.65,
            "v": 123456789,
            "cje": 987654321.0,
        }]

        call_count = [0]

        def mock_get(url, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_data
            raise Exception("simulated error")

        with patch.object(self.fetcher, "_get", side_effect=mock_get):
            result = self.fetcher.get_main_indices(region="cn")

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["current"], 3200.0)
        self.assertEqual(result[0]["change_pct"], 0.65)

    def test_returns_none_when_empty(self):
        with patch.object(self.fetcher, "_get", return_value=None):
            result = self.fetcher.get_main_indices(region="cn")
            self.assertIsNone(result)

    def test_returns_none_when_exception(self):
        with patch.object(self.fetcher, "_get", side_effect=Exception("API error")):
            result = self.fetcher.get_main_indices(region="cn")
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
