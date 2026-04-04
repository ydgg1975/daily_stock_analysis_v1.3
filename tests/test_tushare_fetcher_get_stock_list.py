# -*- coding: utf-8 -*-
"""Unit tests for TushareFetcher.get_stock_list().

This test file is intentionally isolated from other test modules.
It loads repo-root `.env` and stubs optional runtime deps so it can run
in minimal CI environments without network calls.

Run (repo root):

- With pytest: ``python3 -m pytest tests/test_tushare_fetcher_get_stock_list.py``
  (install once: ``pip install -r requirements-dev.txt`` or ``pip install pytest``)
- Without pytest: ``python3 tests/test_tushare_fetcher_get_stock_list.py``
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

try:
    json_repair_available = importlib.util.find_spec("json_repair") is not None
except ValueError:
    json_repair_available = "json_repair" in sys.modules

if not json_repair_available and "json_repair" not in sys.modules:
    sys.modules["json_repair"] = MagicMock()

if "fake_useragent" not in sys.modules:
    sys.modules["fake_useragent"] = MagicMock()

from data_provider.tushare_fetcher import TushareFetcher

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
except ImportError:
    pass


class TestTushareFetcherGetStockList(unittest.TestCase):
    @staticmethod
    def _make_fetcher() -> TushareFetcher:
        # Avoid real API initialization; we inject a mocked _api below.
        with patch.object(TushareFetcher, "_init_api", return_value=None):
            fetcher = TushareFetcher()
        fetcher._api = MagicMock()
        fetcher.priority = 2
        return fetcher

    def test_get_stock_list_merges_a_share_and_hk(self) -> None:
        fetcher = self._make_fetcher()

        fetcher._api.stock_basic.return_value = pd.DataFrame(
            {
                "ts_code": ["600519.SH", "000001.SZ"],
                "name": ["贵州茅台", "平安银行"],
                "industry": ["白酒", "银行"],
                "area": ["贵州", "深圳"],
                "market": ["主板", "主板"],
            }
        )
        fetcher._api.hk_basic.return_value = pd.DataFrame(
            {
                "ts_code": ["00700.HK"],
                "name": ["腾讯控股"],
                "market": ["主板"],
            }
        )

        with patch.object(fetcher, "_check_rate_limit"):
            df = fetcher.get_stock_list()

        self.assertIsNotNone(df)
        assert df is not None
        self.assertEqual(
            set(df.columns.tolist()),
            {"code", "name", "industry", "area", "market"},
        )
        self.assertEqual(len(df), 3)
        self.assertEqual(set(df["code"].tolist()), {"600519", "000001", "HK00700"})

        hk_row = df.loc[df["code"] == "HK00700"].iloc[0]
        self.assertEqual(hk_row["industry"], "")
        self.assertEqual(hk_row["area"], "")
        self.assertEqual(fetcher._stock_name_cache.get("HK00700"), "腾讯控股")

        fetcher._api.stock_basic.assert_called_once()
        fetcher._api.hk_basic.assert_called_once()

    def test_get_stock_list_cn_only_when_hk_fails(self) -> None:
        fetcher = self._make_fetcher()

        fetcher._api.stock_basic.return_value = pd.DataFrame(
            {
                "ts_code": ["600519.SH"],
                "name": ["贵州茅台"],
                "industry": ["白酒"],
                "area": ["贵州"],
                "market": ["主板"],
            }
        )
        fetcher._api.hk_basic.side_effect = Exception("permission")

        with patch.object(fetcher, "_check_rate_limit"):
            df = fetcher.get_stock_list()

        self.assertIsNotNone(df)
        assert df is not None
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["code"], "600519")

    def test_get_stock_list_returns_none_when_both_empty(self) -> None:
        fetcher = self._make_fetcher()
        fetcher._api.stock_basic.return_value = pd.DataFrame()
        fetcher._api.hk_basic.return_value = pd.DataFrame()

        with patch.object(fetcher, "_check_rate_limit"):
            df = fetcher.get_stock_list()

        self.assertIsNone(df)


if __name__ == "__main__":
    unittest.main()

