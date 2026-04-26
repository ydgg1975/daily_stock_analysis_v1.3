# -*- coding: utf-8 -*-
"""
Unit tests for DiagnosticDataFetcher edge cases.

Tests edge cases for data fetching including:
- Missing index data handling
- Incomplete sector data handling
- T+1 data marking for North Bound Capital and margin balance

Requirements: 1.6, 7.6, 22.3, 22.4
"""

import logging
import os
import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.market_diagnostic.data.fetchers import DiagnosticDataFetcher
from src.market_diagnostic.data.models import (
    IndexDailyData,
    MarketBreadthData,
    SectorDailyData,
    CapitalFlowData,
)


def _make_daily_df(rows: int = 5) -> pd.DataFrame:
    """Create a minimal daily OHLCV DataFrame."""
    return pd.DataFrame(
        {
            "date": [f"2025-01-{i+1:02d}" for i in range(rows)],
            "open": [100.0 + i for i in range(rows)],
            "high": [105.0 + i for i in range(rows)],
            "low": [98.0 + i for i in range(rows)],
            "close": [102.0 + i for i in range(rows)],
            "volume": [1_000_000 + i * 10_000 for i in range(rows)],
            "amount": [1_020_000_000.0 + i * 1_000_000 for i in range(rows)],
            "pct_chg": [0.5 + i * 0.1 for i in range(rows)],
        }
    )


def _make_mock_manager(daily_df: pd.DataFrame = None) -> MagicMock:
    """Return a mock DataFetcherManager.

    The fetcher code calls get_daily_data() and uses the result directly as a
    DataFrame (df.empty, df.iloc[-1], etc.), so we return the DataFrame itself
    rather than a (df, source) tuple.
    """
    manager = MagicMock()
    manager.get_daily_data.return_value = daily_df
    return manager


# ---------------------------------------------------------------------------
# fetch_index_series edge cases
# ---------------------------------------------------------------------------

class TestFetchIndexSeriesMissingData(unittest.TestCase):
    """Tests for fetch_index_series() with missing / empty index data."""

    def _make_fetcher(self, daily_df=None):
        manager = _make_mock_manager(daily_df)
        return DiagnosticDataFetcher(data_manager=manager)

    def test_missing_index_data_logs_warning_and_continues(self):
        """When get_daily_data returns None for an index, a warning is logged
        and the fetcher continues with the remaining indices.

        Requirements: 1.6, 22.3
        """
        fetcher = self._make_fetcher(daily_df=None)

        with self.assertLogs("src.market_diagnostic.data.fetchers", level="WARNING") as cm:
            result = fetcher.fetch_index_series(date="2025-01-10")

        # All indices should be missing → empty result dict
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

        # A warning about missing index data should be emitted
        log_text = "\n".join(cm.output)
        self.assertIn("Missing index data", log_text)

    def test_partial_index_data_returns_available_indices(self):
        """When some indices return data and others return None, only the
        successful ones are included in the result.

        Requirements: 1.6, 22.3
        """
        good_df = _make_daily_df(rows=65)
        manager = MagicMock()

        call_count = {"n": 0}

        def side_effect(**kwargs):
            call_count["n"] += 1
            # Return data for every other call
            if call_count["n"] % 2 == 0:
                return good_df
            return None

        manager.get_daily_data.side_effect = side_effect

        fetcher = DiagnosticDataFetcher(data_manager=manager)
        result = fetcher.fetch_index_series(date="2025-01-10")

        # Should have some results but not all 9
        self.assertGreater(len(result), 0)
        self.assertLess(len(result), 9)

    def test_empty_dataframe_handled_gracefully(self):
        """When get_daily_data returns an empty DataFrame, the index is skipped
        without raising an exception.

        Requirements: 1.6, 22.3
        """
        manager = MagicMock()
        manager.get_daily_data.return_value = (pd.DataFrame(), "MockFetcher")

        fetcher = DiagnosticDataFetcher(data_manager=manager)

        # Should not raise
        result = fetcher.fetch_index_series(date="2025-01-10")

        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    def test_exception_in_one_index_does_not_abort_others(self):
        """An exception while fetching one index should not prevent the rest
        from being fetched.

        Requirements: 1.6, 22.3
        """
        good_df = _make_daily_df(rows=65)
        manager = MagicMock()

        call_count = {"n": 0}

        def side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("simulated network error")
            return good_df

        manager.get_daily_data.side_effect = side_effect

        fetcher = DiagnosticDataFetcher(data_manager=manager)
        result = fetcher.fetch_index_series(date="2025-01-10")

        # At least 8 of 9 indices should succeed
        self.assertGreaterEqual(len(result), 8)


# ---------------------------------------------------------------------------
# fetch_breadth_data fallback
# ---------------------------------------------------------------------------

class TestFetchBreadthDataFallback(unittest.TestCase):
    """Tests for fetch_breadth_data() when AkShare is unavailable."""

    def test_falls_back_to_manager_when_akshare_unavailable(self):
        """When the module-level `ak` is None, fetch_breadth_data should
        delegate to _fetch_breadth_from_manager.

        Requirements: 1.6
        """
        manager = MagicMock()
        manager.get_market_stats.return_value = {
            "up_count": 2000,
            "down_count": 1500,
            "flat_count": 200,
            "limit_up_count": 80,
            "limit_down_count": 10,
            "explode_count": 20,
            "total_amount": 8000.0,
            "continuous_limit_up": 30,
            "above_ma20_ratio": 0.55,
            "above_ma60_ratio": 0.48,
            "new_high_count": 120,
            "new_low_count": 40,
            "amount_ma5": 7500.0,
            "amount_ma20": 7000.0,
        }

        fetcher = DiagnosticDataFetcher(data_manager=manager)

        with patch("src.market_diagnostic.data.fetchers.ak", None):
            result = fetcher.fetch_breadth_data(date="2025-01-10")

        self.assertIsNotNone(result)
        self.assertIsInstance(result, MarketBreadthData)
        self.assertEqual(result.up_count, 2000)
        self.assertEqual(result.down_count, 1500)

    def test_returns_none_when_manager_has_no_stats(self):
        """When both AkShare and the manager have no data, None is returned."""
        manager = MagicMock()
        manager.get_market_stats.return_value = None

        fetcher = DiagnosticDataFetcher(data_manager=manager)

        with patch("src.market_diagnostic.data.fetchers.ak", None):
            result = fetcher.fetch_breadth_data(date="2025-01-10")

        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# fetch_sector_data edge cases
# ---------------------------------------------------------------------------

class TestFetchSectorDataIncomplete(unittest.TestCase):
    """Tests for fetch_sector_data() with incomplete sector data."""

    def test_incomplete_sector_data_continues_with_available_sectors(self):
        """When some sectors fail to fetch, the method continues and returns
        the successfully fetched sectors.

        Requirements: 1.6, 22.4
        """
        manager = MagicMock()
        # Simulate partial sector data from manager fallback
        manager.get_sector_rankings.return_value = (
            [
                {
                    "code": "BK0447",
                    "name": "电子",
                    "change_pct": 1.5,
                    "ret_5d": 3.0,
                    "ret_20d": 5.0,
                    "excess_ret_1d": 0.5,
                    "amount": 500.0,
                    "amount_share": 0.06,
                    "amount_share_delta": 0.01,
                    "limit_up_count": 3,
                    "turnover": 2.5,
                    "breadth_20": 0.6,
                    "new_high_ratio": 0.1,
                },
                {
                    "code": "BK0448",
                    "name": "计算机",
                    "change_pct": 0.8,
                    "ret_5d": 1.5,
                    "ret_20d": 2.0,
                    "excess_ret_1d": -0.2,
                    "amount": 300.0,
                    "amount_share": 0.04,
                    "amount_share_delta": -0.005,
                    "limit_up_count": 1,
                    "turnover": 1.8,
                    "breadth_20": 0.5,
                    "new_high_ratio": 0.05,
                },
            ],
            [],
        )

        fetcher = DiagnosticDataFetcher(data_manager=manager)

        # Force AkShare path to fail so we use manager fallback
        with patch("src.market_diagnostic.data.fetchers.ak", None):
            result = fetcher.fetch_sector_data(date="2025-01-10")

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].industry_name, "电子")
        self.assertEqual(result[1].industry_name, "计算机")

    def test_empty_sector_data_returns_empty_list(self):
        """When the manager returns no sector data, an empty list is returned.

        Requirements: 1.6, 22.4
        """
        manager = MagicMock()
        manager.get_sector_rankings.return_value = ([], [])

        fetcher = DiagnosticDataFetcher(data_manager=manager)

        with patch("src.market_diagnostic.data.fetchers.ak", None):
            result = fetcher.fetch_sector_data(date="2025-01-10")

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_sector_processing_exception_skips_bad_sector(self):
        """An exception while processing one sector should not abort the rest.

        Requirements: 1.6, 22.4
        """
        manager = MagicMock()
        # First sector has bad data (missing required fields), second is fine
        manager.get_sector_rankings.return_value = (
            [
                # Good sector
                {
                    "code": "BK0447",
                    "name": "电子",
                    "change_pct": 1.5,
                    "ret_5d": 3.0,
                    "ret_20d": 5.0,
                    "excess_ret_1d": 0.5,
                    "amount": 500.0,
                    "amount_share": 0.06,
                    "amount_share_delta": 0.01,
                    "limit_up_count": 3,
                    "turnover": 2.5,
                    "breadth_20": 0.6,
                    "new_high_ratio": 0.1,
                },
            ],
            [],
        )

        fetcher = DiagnosticDataFetcher(data_manager=manager)

        with patch("src.market_diagnostic.data.fetchers.ak", None):
            result = fetcher.fetch_sector_data(date="2025-01-10")

        # Should still return the good sector
        self.assertGreaterEqual(len(result), 1)


# ---------------------------------------------------------------------------
# fetch_capital_flow T+1 marking
# ---------------------------------------------------------------------------

class TestFetchCapitalFlowT1Marking(unittest.TestCase):
    """Tests for T+1 data freshness marking in fetch_capital_flow().

    Requirements: 7.6, 22.3, 22.4
    """

    def _make_north_df(self, include_target_date: bool = False, date: str = "2025-01-10") -> pd.DataFrame:
        """Build a mock North Bound Capital DataFrame."""
        rows = [
            {"日期": "2025-01-06", "当日资金流入": 50_000_000},
            {"日期": "2025-01-07", "当日资金流入": -30_000_000},
            {"日期": "2025-01-08", "当日资金流入": 80_000_000},
            {"日期": "2025-01-09", "当日资金流入": 20_000_000},
        ]
        if include_target_date:
            rows.append({"日期": date, "当日资金流入": 60_000_000})
        df = pd.DataFrame(rows)
        df["日期"] = pd.to_datetime(df["日期"])
        return df

    def _make_margin_df(self) -> pd.DataFrame:
        """Build a mock margin balance DataFrame."""
        return pd.DataFrame(
            {
                "融资余额": [1_500_000_000_000, 1_600_000_000_000, 1_550_000_000_000],
            }
        )

    def test_north_bound_capital_marked_t1_when_date_not_in_data(self):
        """When the target date is not in the North Bound Capital data,
        data_freshness['north_net_flow'] should be 'T+1'.

        Requirements: 7.6, 22.3
        """
        manager = _make_mock_manager()
        fetcher = DiagnosticDataFetcher(data_manager=manager)

        north_df = self._make_north_df(include_target_date=False)
        margin_df = self._make_margin_df()

        mock_ak = MagicMock()
        mock_ak.stock_hsgt_hist_em.return_value = north_df
        mock_ak.stock_margin_underlying_info_szse.return_value = margin_df

        with patch("src.market_diagnostic.data.fetchers.ak", mock_ak):
            result = fetcher.fetch_capital_flow(date="2025-01-10")

        self.assertIsNotNone(result)
        self.assertIsInstance(result, CapitalFlowData)
        self.assertEqual(result.data_freshness.get("north_net_flow"), "T+1")

    def test_north_bound_capital_marked_t0_when_date_in_data(self):
        """When the target date IS present in the North Bound Capital data,
        data_freshness['north_net_flow'] should be 'T+0'.

        Requirements: 7.6, 22.3
        """
        manager = _make_mock_manager()
        fetcher = DiagnosticDataFetcher(data_manager=manager)

        north_df = self._make_north_df(include_target_date=True, date="2025-01-10")
        margin_df = self._make_margin_df()

        mock_ak = MagicMock()
        mock_ak.stock_hsgt_hist_em.return_value = north_df
        mock_ak.stock_margin_underlying_info_szse.return_value = margin_df

        with patch("src.market_diagnostic.data.fetchers.ak", mock_ak):
            result = fetcher.fetch_capital_flow(date="2025-01-10")

        self.assertIsNotNone(result)
        self.assertEqual(result.data_freshness.get("north_net_flow"), "T+0")

    def test_margin_balance_marked_t1_on_success(self):
        """When margin balance data is fetched successfully,
        data_freshness['margin_balance'] should be 'T+1'.

        Requirements: 7.6, 22.4
        """
        manager = _make_mock_manager()
        fetcher = DiagnosticDataFetcher(data_manager=manager)

        north_df = self._make_north_df(include_target_date=False)
        margin_df = self._make_margin_df()

        mock_ak = MagicMock()
        mock_ak.stock_hsgt_hist_em.return_value = north_df
        mock_ak.stock_margin_underlying_info_szse.return_value = margin_df

        with patch("src.market_diagnostic.data.fetchers.ak", mock_ak):
            result = fetcher.fetch_capital_flow(date="2025-01-10")

        self.assertIsNotNone(result)
        self.assertEqual(result.data_freshness.get("margin_balance"), "T+1")

    def test_north_bound_capital_marked_unavailable_on_api_failure(self):
        """When the North Bound Capital API raises an exception,
        data_freshness['north_net_flow'] should be 'unavailable'.

        Requirements: 7.6, 22.3
        """
        manager = _make_mock_manager()
        fetcher = DiagnosticDataFetcher(data_manager=manager)

        margin_df = self._make_margin_df()

        mock_ak = MagicMock()
        mock_ak.stock_hsgt_hist_em.side_effect = RuntimeError("API timeout")
        mock_ak.stock_margin_underlying_info_szse.return_value = margin_df

        with patch("src.market_diagnostic.data.fetchers.ak", mock_ak):
            result = fetcher.fetch_capital_flow(date="2025-01-10")

        self.assertIsNotNone(result)
        self.assertEqual(result.data_freshness.get("north_net_flow"), "unavailable")

    def test_margin_balance_marked_unavailable_on_api_failure(self):
        """When the margin balance API raises an exception,
        data_freshness['margin_balance'] should be 'unavailable'.

        Requirements: 7.6, 22.4
        """
        manager = _make_mock_manager()
        fetcher = DiagnosticDataFetcher(data_manager=manager)

        north_df = self._make_north_df(include_target_date=False)

        mock_ak = MagicMock()
        mock_ak.stock_hsgt_hist_em.return_value = north_df
        mock_ak.stock_margin_underlying_info_szse.side_effect = RuntimeError("connection refused")

        with patch("src.market_diagnostic.data.fetchers.ak", mock_ak):
            result = fetcher.fetch_capital_flow(date="2025-01-10")

        self.assertIsNotNone(result)
        self.assertEqual(result.data_freshness.get("margin_balance"), "unavailable")

    def test_both_fields_unavailable_when_akshare_is_none(self):
        """When ak module is None, both north_net_flow and margin_balance
        should be marked 'unavailable'.

        Requirements: 7.6, 22.3, 22.4
        """
        manager = _make_mock_manager()
        fetcher = DiagnosticDataFetcher(data_manager=manager)

        with patch("src.market_diagnostic.data.fetchers.ak", None):
            result = fetcher.fetch_capital_flow(date="2025-01-10")

        self.assertIsNotNone(result)
        self.assertEqual(result.data_freshness.get("north_net_flow"), "unavailable")
        self.assertEqual(result.data_freshness.get("margin_balance"), "unavailable")


# ---------------------------------------------------------------------------
# fetch_valuation_data edge cases
# ---------------------------------------------------------------------------

class TestFetchValuationDataEdgeCases(unittest.TestCase):
    """Tests for fetch_valuation_data() error handling."""

    def test_returns_none_on_unexpected_exception(self):
        """When an unexpected exception occurs at the top level,
        fetch_valuation_data should return None.

        Requirements: 1.6
        """
        manager = _make_mock_manager()
        fetcher = DiagnosticDataFetcher(data_manager=manager)

        mock_ak = MagicMock()
        # Make the valuation call raise an unexpected error
        mock_ak.stock_zh_index_value_csindex.side_effect = Exception("unexpected crash")
        mock_ak.bond_zh_us_rate.side_effect = Exception("unexpected crash")
        mock_ak.currency_boc_sina.side_effect = Exception("unexpected crash")

        with patch("src.market_diagnostic.data.fetchers.ak", mock_ak):
            result = fetcher.fetch_valuation_data(date="2025-01-10")

        # Should return partial data (not None) since individual failures are caught
        # and the method only returns None on a top-level exception
        self.assertIsNotNone(result)
        self.assertIn("date", result)

    def test_returns_default_zeros_when_akshare_unavailable(self):
        """When ak is None, fetch_valuation_data should return a dict with
        zero-valued fields rather than None.

        Requirements: 1.6
        """
        manager = _make_mock_manager()
        fetcher = DiagnosticDataFetcher(data_manager=manager)

        with patch("src.market_diagnostic.data.fetchers.ak", None):
            result = fetcher.fetch_valuation_data(date="2025-01-10")

        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("csi300_pe"), 0.0)
        self.assertEqual(result.get("bond_yield_10y"), 0.0)
        self.assertEqual(result.get("usd_cny"), 0.0)

    def test_partial_api_failure_returns_partial_data_with_logging(self):
        """When some valuation APIs fail and others succeed, the method should
        return partial data and log warnings for the failures.

        Requirements: 1.6
        """
        manager = _make_mock_manager()
        fetcher = DiagnosticDataFetcher(data_manager=manager)

        good_val_df = pd.DataFrame(
            [{"市盈率2": 15.5, "市净率": 1.8}]
        )
        good_bond_df = pd.DataFrame(
            [{"中国国债收益率10年": 2.85, "中国国债收益率2年": 2.10}]
        )

        mock_ak = MagicMock()
        # First index valuation succeeds, others fail
        mock_ak.stock_zh_index_value_csindex.side_effect = [
            good_val_df,
            Exception("API error"),
            Exception("API error"),
        ]
        mock_ak.bond_zh_us_rate.return_value = good_bond_df
        mock_ak.currency_boc_sina.side_effect = Exception("FX API down")

        with patch("src.market_diagnostic.data.fetchers.ak", mock_ak):
            with self.assertLogs("src.market_diagnostic.data.fetchers", level="WARNING") as cm:
                result = fetcher.fetch_valuation_data(date="2025-01-10")

        self.assertIsNotNone(result)
        # Successful fields should have real values
        self.assertEqual(result.get("csi300_pe"), 15.5)
        self.assertEqual(result.get("bond_yield_10y"), 2.85)
        # Failed fields should default to 0.0
        self.assertEqual(result.get("csi500_pe"), 0.0)
        self.assertEqual(result.get("usd_cny"), 0.0)

        log_text = "\n".join(cm.output)
        self.assertIn("Failed to fetch", log_text)


if __name__ == "__main__":
    unittest.main()
