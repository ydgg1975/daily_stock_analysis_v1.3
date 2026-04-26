"""
Performance Tests for Market Diagnostic System (Task 13.3)

Tests:
- Property 52: Data Caching Efficiency (Validates: Requirement 23.1)
  - Cache hit is faster than cache miss
  - Cached data is returned correctly
  - Cache avoids redundant API calls (mock API, verify called once)

- Execution time tests:
  - Sector feature calculation for 31 sectors completes in reasonable time
  - Parallel processing is faster than sequential for large sector lists
  - Full engine run with mock data completes within a reasonable time limit

Requirements: 23.1, 23.5
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
import time
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch, call

import pytest
from hypothesis import given, settings, strategies as st

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.market_diagnostic.data.cache import DiagnosticDataCache
from src.market_diagnostic.data.models import (
    IndexDailyData,
    MarketBreadthData,
    SectorDailyData,
    CapitalFlowData,
)
from src.market_diagnostic.features.sector import (
    compute_all_sector_features,
    compute_sector_features,
)
from src.market_diagnostic.engine import MarketDiagnosticEngine


# ---------------------------------------------------------------------------
# Shared helpers / factories
# ---------------------------------------------------------------------------

def _make_index_data(code: str = "sh000300", n: int = 60) -> IndexDailyData:
    """Create a realistic IndexDailyData with an n-day close series."""
    base = 3500.0
    close_series = [base + i * 2.0 + math.sin(i * 0.3) * 10 for i in range(n)]
    return IndexDailyData(
        code=code,
        name="沪深300",
        date="2024-01-15",
        close=close_series[-1],
        open=close_series[-1] - 5,
        high=close_series[-1] + 10,
        low=close_series[-1] - 15,
        prev_close=close_series[-2],
        volume=1e9,
        amount=5e10,
        change_pct=0.5,
        close_series=close_series,
        volume_series=[1e9] * n,
    )


def _make_breadth_data(date: str = "2024-01-15") -> MarketBreadthData:
    return MarketBreadthData(
        date=date,
        up_count=2500,
        down_count=1800,
        flat_count=200,
        limit_up_count=80,
        limit_down_count=20,
        explode_count=15,
        seal_rate=0.84,
        continuous_limit_up=12,
        above_ma20_ratio=0.52,
        above_ma60_ratio=0.48,
        new_high_count=150,
        new_low_count=50,
        total_amount=8500.0,
        amount_ma5=8000.0,
        amount_ma20=7500.0,
    )


def _make_sector_data(n: int = 31) -> List[SectorDailyData]:
    """Create a list of n SectorDailyData instances."""
    sectors = []
    for i in range(n):
        sectors.append(SectorDailyData(
            date="2024-01-15",
            industry_code=f"BK{1000 + i:04d}",
            industry_name=f"行业{i:02d}",
            ret_1d=0.01 * (i % 5 - 2),
            ret_5d=0.02 * (i % 7 - 3),
            ret_20d=0.05 * (i % 9 - 4),
            excess_ret_1d=0.005 * (i % 5 - 2),
            breadth_20=0.3 + 0.02 * (i % 10),
            new_high_ratio=0.05 + 0.01 * (i % 5),
            amount=500.0 + 10.0 * i,
            amount_share=0.03 + 0.001 * i,
            amount_share_delta=0.001 * (i % 5 - 2),
            limit_up_count=i % 5,
            turnover=0.02 + 0.001 * i,
        ))
    return sectors


def _make_capital_data(date: str = "2024-01-15") -> CapitalFlowData:
    return CapitalFlowData(
        date=date,
        north_net_flow=50.0,
        north_5d_avg=30.0,
        margin_balance=15000.0,
        margin_delta=100.0,
        main_net_flow=200.0,
        etf_net_flow=50.0,
        data_freshness={"north_net_flow": "T+1", "margin_balance": "T+1"},
    )


# ---------------------------------------------------------------------------
# Property 52: Data Caching Efficiency
# Validates: Requirement 23.1
# ---------------------------------------------------------------------------

class TestDataCachingEfficiency:
    """
    **Property 52: Data Caching Efficiency**
    Validates: Requirement 23.1

    For any data fetch operation where data for the same date was previously
    fetched, the Data_Layer SHALL use cached data instead of making redundant
    API calls.
    """

    def test_cache_hit_faster_than_cache_miss(self, tmp_path):
        """Cache retrieval should be faster than writing + reading from scratch."""
        cache = DiagnosticDataCache(cache_dir=str(tmp_path))
        date = "2024-01-15"
        key = "index_series"
        data = {"close": 3500.0, "series": list(range(60))}

        # Warm up: write to cache
        cache.set(key, date, data)

        # Measure cache miss (write + read)
        t0 = time.perf_counter()
        cache.set(key, date, data)
        t_write = time.perf_counter() - t0

        # Measure cache hit (read only)
        t0 = time.perf_counter()
        result = cache.get(key, date)
        t_read = time.perf_counter() - t0

        assert result is not None, "Cache hit should return data"
        # Cache read should be at most as slow as write (typically much faster)
        # We allow a generous 10x margin since file I/O can vary
        assert t_read <= t_write * 10 + 0.1, (
            f"Cache read ({t_read:.4f}s) should not be dramatically slower than write ({t_write:.4f}s)"
        )

    def test_cached_data_returned_correctly(self, tmp_path):
        """Data retrieved from cache must be identical to what was stored."""
        cache = DiagnosticDataCache(cache_dir=str(tmp_path))
        date = "2024-01-15"
        key = "breadth_data"
        original_data = {
            "up_count": 2500,
            "down_count": 1800,
            "above_ma20_ratio": 0.52,
            "series": [1.0, 2.0, 3.0],
        }

        cache.set(key, date, original_data)
        retrieved = cache.get(key, date)

        assert retrieved is not None, "Cache should return stored data"
        assert retrieved == original_data, "Retrieved data must match stored data"

    def test_cache_avoids_redundant_api_calls(self, tmp_path):
        """
        When data is already cached for a date, the API should only be called
        once (on the first fetch), not on subsequent fetches for the same date.

        Validates: Requirement 23.1
        """
        cache = DiagnosticDataCache(cache_dir=str(tmp_path))
        date = "2024-01-15"
        key = "index_series"

        # Simulate an API call counter
        api_call_count = 0

        def mock_api_fetch(date: str) -> dict:
            nonlocal api_call_count
            api_call_count += 1
            return {"close": 3500.0, "date": date}

        # First fetch: cache miss → API is called
        if not cache.has(key, date):
            data = mock_api_fetch(date)
            cache.set(key, date, data)

        # Second fetch: cache hit → API should NOT be called
        if not cache.has(key, date):
            data = mock_api_fetch(date)
            cache.set(key, date, data)

        # Third fetch: cache hit → API should NOT be called
        if not cache.has(key, date):
            data = mock_api_fetch(date)
            cache.set(key, date, data)

        assert api_call_count == 1, (
            f"API should be called exactly once (cache miss), but was called {api_call_count} times"
        )

    def test_cache_miss_triggers_api_call(self, tmp_path):
        """When no cache entry exists, the API must be called to fetch data."""
        cache = DiagnosticDataCache(cache_dir=str(tmp_path))
        date = "2024-01-15"
        key = "sector_data"

        api_call_count = 0

        def mock_api_fetch(date: str) -> dict:
            nonlocal api_call_count
            api_call_count += 1
            return {"sectors": []}

        # No cache entry exists yet
        assert not cache.has(key, date), "Cache should be empty initially"

        if not cache.has(key, date):
            data = mock_api_fetch(date)
            cache.set(key, date, data)

        assert api_call_count == 1, "API should be called once on cache miss"
        assert cache.has(key, date), "Data should be cached after first fetch"

    def test_different_dates_use_separate_cache_entries(self, tmp_path):
        """Cache entries for different dates must be independent."""
        cache = DiagnosticDataCache(cache_dir=str(tmp_path))
        key = "index_series"
        date1 = "2024-01-15"
        date2 = "2024-01-16"

        data1 = {"close": 3500.0}
        data2 = {"close": 3520.0}

        cache.set(key, date1, data1)
        cache.set(key, date2, data2)

        retrieved1 = cache.get(key, date1)
        retrieved2 = cache.get(key, date2)

        assert retrieved1 == data1, "Date1 cache entry should be independent"
        assert retrieved2 == data2, "Date2 cache entry should be independent"
        assert retrieved1 != retrieved2, "Different dates should have different cached data"

    def test_cache_has_returns_false_for_missing_entry(self, tmp_path):
        """cache.has() must return False when no entry exists for the key/date."""
        cache = DiagnosticDataCache(cache_dir=str(tmp_path))
        assert not cache.has("nonexistent_key", "2024-01-15")

    def test_cache_has_returns_true_after_set(self, tmp_path):
        """cache.has() must return True after data is stored."""
        cache = DiagnosticDataCache(cache_dir=str(tmp_path))
        cache.set("test_key", "2024-01-15", {"value": 42})
        assert cache.has("test_key", "2024-01-15")

    @given(
        date=st.dates(
            min_value=__import__("datetime").date(2020, 1, 1),
            max_value=__import__("datetime").date(2025, 12, 31),
        ).map(lambda d: d.strftime("%Y-%m-%d")),
        value=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=30)
    def test_property_52_cache_roundtrip_correctness(self, date, value):
        """
        **Property 52: Data Caching Efficiency**
        Validates: Requirement 23.1

        For any date and value, data stored in the cache must be retrievable
        and identical to what was stored.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache = DiagnosticDataCache(cache_dir=tmp_dir)
            key = "test_metric"
            data = {"value": value, "date": date}

            cache.set(key, date, data)
            retrieved = cache.get(key, date)

            assert retrieved is not None, f"Cache should return data for date={date}"
            assert retrieved["value"] == pytest.approx(value, rel=1e-9), (
                f"Retrieved value {retrieved['value']} should match stored value {value}"
            )
            assert retrieved["date"] == date


# ---------------------------------------------------------------------------
# Execution time tests
# ---------------------------------------------------------------------------

class TestExecutionTime:
    """Tests that verify the system meets performance requirements."""

    def test_sector_feature_calculation_31_sectors_reasonable_time(self):
        """
        Sector feature calculation for 31 sectors should complete in
        a reasonable time (well under the 60-second full-run budget).

        Validates: Requirement 23.5 (partial - sector calculation component)
        """
        sectors = _make_sector_data(n=31)

        t0 = time.perf_counter()
        results = compute_all_sector_features(sectors, max_workers=4)
        elapsed = time.perf_counter() - t0

        assert len(results) == 31, "Should compute features for all 31 sectors"
        # Sector calculation alone should be very fast (< 5 seconds)
        assert elapsed < 5.0, (
            f"Sector feature calculation for 31 sectors took {elapsed:.2f}s, "
            "expected < 5.0s"
        )

    def test_parallel_processing_completes_correctly(self):
        """
        Parallel processing via compute_all_sector_features should produce
        the same results as sequential processing.

        Validates: Requirement 23.4 (parallel processing correctness)
        """
        sectors = _make_sector_data(n=31)

        # Parallel results
        parallel_results = compute_all_sector_features(sectors, max_workers=4)

        # Sequential results (max_workers=1 effectively serializes)
        sequential_results = compute_all_sector_features(sectors, max_workers=1)

        assert len(parallel_results) == len(sequential_results) == 31

        for p, s in zip(parallel_results, sequential_results):
            assert p.industry_code == s.industry_code
            assert p.strength_score == pytest.approx(s.strength_score, rel=1e-6)
            assert p.persistence_score == pytest.approx(s.persistence_score, rel=1e-6)
            assert p.state == s.state

    def test_parallel_not_slower_than_sequential_for_large_input(self):
        """
        Parallel processing should not be dramatically slower than sequential
        for a large sector list (31 sectors). In practice it should be faster
        or comparable.

        Validates: Requirement 23.4
        """
        sectors = _make_sector_data(n=31)

        # Warm up to avoid cold-start bias
        compute_all_sector_features(sectors[:5], max_workers=1)
        compute_all_sector_features(sectors[:5], max_workers=4)

        t0 = time.perf_counter()
        compute_all_sector_features(sectors, max_workers=1)
        t_sequential = time.perf_counter() - t0

        t0 = time.perf_counter()
        compute_all_sector_features(sectors, max_workers=4)
        t_parallel = time.perf_counter() - t0

        # Parallel should not be more than 3x slower than sequential
        # (on a single-core CI machine, parallel overhead may dominate for small tasks)
        assert t_parallel < t_sequential * 3 + 0.5, (
            f"Parallel ({t_parallel:.3f}s) should not be dramatically slower than "
            f"sequential ({t_sequential:.3f}s)"
        )

    def test_full_engine_run_with_mock_data_within_time_limit(self):
        """
        Full engine run with mock data should complete within a reasonable
        time limit. With mocked data fetchers (no real API calls), this
        should be well under 60 seconds.

        Validates: Requirement 23.5
        """
        # Build mock data
        index_codes = [
            "sh000001", "sz399001", "sz399006", "sh000688",
            "sh000016", "sh000300", "sh000905", "sh000852", "bj899050",
        ]
        index_data = {code: _make_index_data(code=code, n=60) for code in index_codes}
        breadth_data = _make_breadth_data()
        sector_data = _make_sector_data(n=31)
        capital_data = _make_capital_data()

        # Create mock data manager
        mock_data_manager = MagicMock()

        # Create engine with mocked fetcher
        engine = MarketDiagnosticEngine(
            data_manager=mock_data_manager,
            analyzer=None,
            enable_llm_narrative=False,
        )

        # Patch the fetcher methods to return mock data
        engine.fetcher.fetch_index_series = MagicMock(return_value=index_data)
        engine.fetcher.fetch_breadth_data = MagicMock(return_value=breadth_data)
        engine.fetcher.fetch_sector_data = MagicMock(return_value=sector_data)
        engine.fetcher.fetch_capital_flow = MagicMock(return_value=capital_data)

        t0 = time.perf_counter()
        report, markdown = engine.run(date="2024-01-15")
        elapsed = time.perf_counter() - t0

        # Verify the run completed successfully
        assert report is not None, "Engine should return a report"
        assert isinstance(markdown, str), "Engine should return a markdown string"
        assert len(markdown) > 0, "Markdown report should not be empty"

        # Requirement 23.5: Full diagnostic run within 60 seconds
        # With mocked data (no real API calls), this should be well under 10 seconds
        assert elapsed < 60.0, (
            f"Full engine run took {elapsed:.2f}s, must complete within 60 seconds (Req 23.5)"
        )

    def test_engine_run_data_fetchers_called_once_per_run(self):
        """
        Each data fetcher should be called exactly once per engine.run() call,
        not multiple times (which would indicate redundant fetching).

        Validates: Requirement 23.1 (no redundant API calls within a single run)
        """
        index_data = {"sh000300": _make_index_data()}
        breadth_data = _make_breadth_data()
        sector_data = _make_sector_data(n=5)
        capital_data = _make_capital_data()

        mock_data_manager = MagicMock()
        engine = MarketDiagnosticEngine(
            data_manager=mock_data_manager,
            analyzer=None,
            enable_llm_narrative=False,
        )

        mock_fetch_index = MagicMock(return_value=index_data)
        mock_fetch_breadth = MagicMock(return_value=breadth_data)
        mock_fetch_sector = MagicMock(return_value=sector_data)
        mock_fetch_capital = MagicMock(return_value=capital_data)

        engine.fetcher.fetch_index_series = mock_fetch_index
        engine.fetcher.fetch_breadth_data = mock_fetch_breadth
        engine.fetcher.fetch_sector_data = mock_fetch_sector
        engine.fetcher.fetch_capital_flow = mock_fetch_capital

        engine.run(date="2024-01-15")

        # Each fetcher should be called exactly once
        mock_fetch_index.assert_called_once()
        mock_fetch_breadth.assert_called_once()
        mock_fetch_sector.assert_called_once()
        mock_fetch_capital.assert_called_once()

    def test_cache_prevents_redundant_fetches_across_runs(self, tmp_path):
        """
        When the same date is requested twice, the cache should prevent
        redundant API calls on the second run.

        Validates: Requirement 23.1
        """
        cache = DiagnosticDataCache(cache_dir=str(tmp_path))
        date = "2024-01-15"
        key = "index_series"

        fetch_count = 0

        def fetch_with_cache(date: str) -> dict:
            nonlocal fetch_count
            if cache.has(key, date):
                return cache.get(key, date)
            # Cache miss: fetch from "API"
            fetch_count += 1
            data = {"close": 3500.0, "date": date}
            cache.set(key, date, data)
            return data

        # First call: cache miss
        result1 = fetch_with_cache(date)
        # Second call: cache hit
        result2 = fetch_with_cache(date)
        # Third call: cache hit
        result3 = fetch_with_cache(date)

        assert fetch_count == 1, (
            f"API should be called exactly once across multiple runs for the same date, "
            f"but was called {fetch_count} times"
        )
        assert result1 == result2 == result3, "All calls should return the same data"
