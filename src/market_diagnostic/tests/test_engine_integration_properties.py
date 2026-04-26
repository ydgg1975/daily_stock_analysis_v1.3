"""
Integration Property-Based Tests for Diagnostic Engine

Task 11.2: Write integration tests for diagnostic engine

- Property 49: Error Logging and Continuation
  Validates: Requirements 22.1, 22.2
- Property 50: Graceful Degradation with Missing Data
  Validates: Requirements 22.3, 22.4
- Property 51: Confidence Adjustment for Data Completeness
  Validates: Requirements 22.5, 22.6, 22.7
"""

from __future__ import annotations

import logging
import math
import sys
import os
from typing import Dict, List, Optional
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, strategies as st, assume

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.market_diagnostic.engine import MarketDiagnosticEngine
from src.market_diagnostic.data.models import (
    IndexDailyData,
    MarketBreadthData,
    SectorDailyData,
    CapitalFlowData,
)
from src.market_diagnostic.reports.schema import DiagnosticReport


# ---------------------------------------------------------------------------
# Shared helpers / factories
# ---------------------------------------------------------------------------

def _make_index_data(code: str = "sh000300", n: int = 60) -> IndexDailyData:
    """Create a realistic IndexDailyData with an n-day close series."""
    import math as _math
    base = 3500.0
    close_series = [base + i * 2.0 + _math.sin(i * 0.3) * 10 for i in range(n)]
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


def _make_sector_data(n: int = 5) -> List[SectorDailyData]:
    sectors = []
    for i in range(n):
        sectors.append(SectorDailyData(
            date="2024-01-15",
            industry_code=f"BK044{i}",
            industry_name=f"行业{i}",
            ret_1d=0.5 + i * 0.1,
            ret_5d=1.0 + i * 0.2,
            ret_20d=3.0 + i * 0.5,
            excess_ret_1d=0.2 + i * 0.05,
            breadth_20=0.5 + i * 0.02,
            new_high_ratio=0.05 + i * 0.01,
            amount=200.0 + i * 50,
            amount_share=0.03 + i * 0.005,
            amount_share_delta=0.001,
            limit_up_count=i + 1,
            turnover=2.0 + i * 0.3,
        ))
    return sectors


def _make_capital_data() -> CapitalFlowData:
    return CapitalFlowData(
        date="2024-01-15",
        north_net_flow=15.0,
        north_5d_avg=8.0,
        margin_balance=15000.0,
        margin_delta=50.0,
        main_net_flow=20.0,
        etf_net_flow=5.0,
        data_freshness={"north_net_flow": "T+1", "margin_balance": "T+1"},
    )


def _build_engine(fetcher) -> MarketDiagnosticEngine:
    """Build an engine with a pre-configured mock fetcher."""
    mock_dm = MagicMock()
    engine = MarketDiagnosticEngine(data_manager=mock_dm, enable_llm_narrative=False)
    engine.fetcher = fetcher
    return engine


def _make_fetcher(
    index_data=None,
    breadth_data=None,
    sector_data=None,
    capital_data=None,
):
    """Create a mock DiagnosticDataFetcher returning the given data."""
    fetcher = MagicMock()
    fetcher.fetch_index_series.return_value = index_data if index_data is not None else {}
    fetcher.fetch_breadth_data.return_value = breadth_data
    fetcher.fetch_sector_data.return_value = sector_data if sector_data is not None else []
    fetcher.fetch_capital_flow.return_value = capital_data
    return fetcher


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Data source names that the engine tracks
_DATA_SOURCES = ["index_data", "breadth_data", "sector_data", "capital_data"]

# Subset of data sources that can fail (any non-empty subset)
_failing_sources_strategy = st.frozensets(
    st.sampled_from(_DATA_SOURCES),
    min_size=1,
    max_size=len(_DATA_SOURCES),
)


@st.composite
def _partial_data_scenario(draw):
    """
    Generate a scenario where some data sources are available and some are not.

    Returns a dict mapping source name → bool (True = available).
    """
    available = {
        "index_data": draw(st.booleans()),
        "breadth_data": draw(st.booleans()),
        "sector_data": draw(st.booleans()),
        "capital_data": draw(st.booleans()),
    }
    return available


# ---------------------------------------------------------------------------
# Property 49: Error Logging and Continuation
# Validates: Requirements 22.1, 22.2
# ---------------------------------------------------------------------------

@given(failing_sources=_failing_sources_strategy)
@settings(max_examples=40)
def test_property_49_engine_continues_when_data_source_raises(failing_sources):
    """
    **Property 49: Error Logging and Continuation**
    **Validates: Requirements 22.1, 22.2**

    For any subset of data sources that raise an exception, the engine SHALL:
    - NOT raise an exception itself
    - Return a valid DiagnosticReport
    - Return a valid Markdown string
    """
    fetcher = MagicMock()

    # Configure each source to either raise or return valid data
    if "index_data" in failing_sources:
        fetcher.fetch_index_series.side_effect = RuntimeError("index fetch failed")
    else:
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}

    if "breadth_data" in failing_sources:
        fetcher.fetch_breadth_data.side_effect = RuntimeError("breadth fetch failed")
    else:
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()

    if "sector_data" in failing_sources:
        fetcher.fetch_sector_data.side_effect = RuntimeError("sector fetch failed")
    else:
        fetcher.fetch_sector_data.return_value = _make_sector_data()

    if "capital_data" in failing_sources:
        fetcher.fetch_capital_flow.side_effect = RuntimeError("capital fetch failed")
    else:
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

    engine = _build_engine(fetcher)

    # Must not raise
    report, markdown = engine.run(date="2024-01-15")

    # Must return valid types
    assert isinstance(report, DiagnosticReport)
    assert isinstance(markdown, str)
    assert len(markdown) > 0


@given(failing_sources=_failing_sources_strategy)
@settings(max_examples=40)
def test_property_49_failed_sources_appear_in_missing_data(failing_sources):
    """
    **Property 49: Error Logging and Continuation**
    **Validates: Requirements 22.1, 22.2**

    When a data source raises an exception, the failed source SHALL be
    included in the report's missing_data list.
    """
    fetcher = MagicMock()

    if "index_data" in failing_sources:
        fetcher.fetch_index_series.side_effect = RuntimeError("index fetch failed")
    else:
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}

    if "breadth_data" in failing_sources:
        fetcher.fetch_breadth_data.side_effect = RuntimeError("breadth fetch failed")
    else:
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()

    if "sector_data" in failing_sources:
        fetcher.fetch_sector_data.side_effect = RuntimeError("sector fetch failed")
    else:
        fetcher.fetch_sector_data.return_value = _make_sector_data()

    if "capital_data" in failing_sources:
        fetcher.fetch_capital_flow.side_effect = RuntimeError("capital fetch failed")
    else:
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

    engine = _build_engine(fetcher)
    report, _ = engine.run(date="2024-01-15")

    # Each failed source must appear in missing_data
    for source in failing_sources:
        assert source in report.missing_data, (
            f"Failed source '{source}' not found in report.missing_data: "
            f"{report.missing_data}"
        )


@given(failing_sources=_failing_sources_strategy)
@settings(max_examples=40)
def test_property_49_errors_are_logged_at_error_level(failing_sources):
    """
    **Property 49: Error Logging and Continuation**
    **Validates: Requirement 22.1**

    When a data source raises an exception, the engine SHALL log the error
    at ERROR level (not just WARNING or INFO).
    """
    fetcher = MagicMock()

    if "index_data" in failing_sources:
        fetcher.fetch_index_series.side_effect = RuntimeError("index fetch failed")
    else:
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}

    if "breadth_data" in failing_sources:
        fetcher.fetch_breadth_data.side_effect = RuntimeError("breadth fetch failed")
    else:
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()

    if "sector_data" in failing_sources:
        fetcher.fetch_sector_data.side_effect = RuntimeError("sector fetch failed")
    else:
        fetcher.fetch_sector_data.return_value = _make_sector_data()

    if "capital_data" in failing_sources:
        fetcher.fetch_capital_flow.side_effect = RuntimeError("capital fetch failed")
    else:
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

    engine = _build_engine(fetcher)

    # Use a custom log handler to capture ERROR-level records within the test
    # (avoids function-scoped fixture issues with Hypothesis)
    error_records = []

    class _ErrorCapture(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.ERROR:
                error_records.append(record)

    handler = _ErrorCapture()
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    try:
        engine.run(date="2024-01-15")
    finally:
        root_logger.removeHandler(handler)

    assert len(error_records) >= 1, (
        f"Expected at least one ERROR log when sources {failing_sources} fail, "
        f"but no ERROR records were captured."
    )


def test_property_49_all_sources_failing_still_returns_report():
    """
    **Property 49: Error Logging and Continuation**
    **Validates: Requirements 22.1, 22.2**

    When ALL data sources raise exceptions, the engine SHALL still return
    a valid DiagnosticReport and Markdown string (not raise).
    """
    fetcher = MagicMock()
    fetcher.fetch_index_series.side_effect = RuntimeError("all failed")
    fetcher.fetch_breadth_data.side_effect = RuntimeError("all failed")
    fetcher.fetch_sector_data.side_effect = RuntimeError("all failed")
    fetcher.fetch_capital_flow.side_effect = RuntimeError("all failed")

    engine = _build_engine(fetcher)
    report, markdown = engine.run(date="2024-01-15")

    assert isinstance(report, DiagnosticReport)
    assert isinstance(markdown, str)
    assert len(markdown) > 0
    assert len(report.missing_data) > 0


# ---------------------------------------------------------------------------
# Property 50: Graceful Degradation with Missing Data
# Validates: Requirements 22.3, 22.4
# ---------------------------------------------------------------------------

@given(scenario=_partial_data_scenario())
@settings(max_examples=40)
def test_property_50_partial_data_returns_valid_report(scenario):
    """
    **Property 50: Graceful Degradation with Missing Data**
    **Validates: Requirements 22.3, 22.4**

    For any combination of available/missing data sources, the engine SHALL
    return a valid DiagnosticReport with all required fields populated.
    """
    fetcher = _make_fetcher(
        index_data={"sh000300": _make_index_data()} if scenario["index_data"] else None,
        breadth_data=_make_breadth_data() if scenario["breadth_data"] else None,
        sector_data=_make_sector_data() if scenario["sector_data"] else None,
        capital_data=_make_capital_data() if scenario["capital_data"] else None,
    )
    engine = _build_engine(fetcher)
    report, markdown = engine.run(date="2024-01-15")

    # Report must be a valid DiagnosticReport
    assert isinstance(report, DiagnosticReport)

    # All required fields must be present and non-None
    assert report.date == "2024-01-15"
    assert report.composite_regime is not None
    assert report.trend_state is not None
    assert report.breadth_state is not None
    assert report.sentiment_state is not None
    assert report.risk_state is not None
    assert isinstance(report.confidence, float)
    assert isinstance(report.missing_data, list)


@given(scenario=_partial_data_scenario())
@settings(max_examples=40)
def test_property_50_missing_sources_listed_in_report(scenario):
    """
    **Property 50: Graceful Degradation with Missing Data**
    **Validates: Requirements 22.3, 22.4**

    When data sources return None/empty, the corresponding items SHALL
    appear in the report's missing_data list.
    """
    fetcher = _make_fetcher(
        index_data={"sh000300": _make_index_data()} if scenario["index_data"] else None,
        breadth_data=_make_breadth_data() if scenario["breadth_data"] else None,
        sector_data=_make_sector_data() if scenario["sector_data"] else None,
        capital_data=_make_capital_data() if scenario["capital_data"] else None,
    )
    engine = _build_engine(fetcher)
    report, _ = engine.run(date="2024-01-15")

    # Sources that are unavailable should be reflected in missing_data
    if not scenario["index_data"]:
        assert "index_data" in report.missing_data, (
            f"'index_data' should be in missing_data when index is unavailable. "
            f"Got: {report.missing_data}"
        )
    if not scenario["breadth_data"]:
        # breadth_data absence may cascade to breadth_features or breadth_data itself
        breadth_related = any(
            "breadth" in item for item in report.missing_data
        )
        assert breadth_related or "breadth_data" in report.missing_data, (
            f"Some breadth-related item should be in missing_data when breadth is unavailable. "
            f"Got: {report.missing_data}"
        )


@given(scenario=_partial_data_scenario())
@settings(max_examples=40)
def test_property_50_partial_data_produces_valid_markdown(scenario):
    """
    **Property 50: Graceful Degradation with Missing Data**
    **Validates: Requirements 22.3, 22.4**

    For any combination of available/missing data, the engine SHALL produce
    a valid non-empty Markdown string.
    """
    fetcher = _make_fetcher(
        index_data={"sh000300": _make_index_data()} if scenario["index_data"] else None,
        breadth_data=_make_breadth_data() if scenario["breadth_data"] else None,
        sector_data=_make_sector_data() if scenario["sector_data"] else None,
        capital_data=_make_capital_data() if scenario["capital_data"] else None,
    )
    engine = _build_engine(fetcher)
    _, markdown = engine.run(date="2024-01-15")

    assert isinstance(markdown, str)
    assert len(markdown) > 0


@given(scenario=_partial_data_scenario())
@settings(max_examples=40)
def test_property_50_no_exception_raised_for_any_data_combination(scenario):
    """
    **Property 50: Graceful Degradation with Missing Data**
    **Validates: Requirements 22.3, 22.4**

    The engine SHALL NOT raise any exception regardless of which data
    sources are available or missing.
    """
    fetcher = _make_fetcher(
        index_data={"sh000300": _make_index_data()} if scenario["index_data"] else None,
        breadth_data=_make_breadth_data() if scenario["breadth_data"] else None,
        sector_data=_make_sector_data() if scenario["sector_data"] else None,
        capital_data=_make_capital_data() if scenario["capital_data"] else None,
    )
    engine = _build_engine(fetcher)

    # Must not raise
    try:
        report, markdown = engine.run(date="2024-01-15")
    except Exception as exc:
        pytest.fail(
            f"Engine raised an exception with scenario {scenario}: {exc}"
        )


# ---------------------------------------------------------------------------
# Property 51: Confidence Adjustment for Data Completeness
# Validates: Requirements 22.5, 22.6, 22.7
# ---------------------------------------------------------------------------

@given(scenario=_partial_data_scenario())
@settings(max_examples=40)
def test_property_51_confidence_always_in_valid_range(scenario):
    """
    **Property 51: Confidence Adjustment for Data Completeness**
    **Validates: Requirements 22.5, 22.6, 22.7**

    For any data availability scenario, the confidence score SHALL always
    be in the range [0.1, 1.0].
    """
    fetcher = _make_fetcher(
        index_data={"sh000300": _make_index_data()} if scenario["index_data"] else None,
        breadth_data=_make_breadth_data() if scenario["breadth_data"] else None,
        sector_data=_make_sector_data() if scenario["sector_data"] else None,
        capital_data=_make_capital_data() if scenario["capital_data"] else None,
    )
    engine = _build_engine(fetcher)
    report, _ = engine.run(date="2024-01-15")

    assert 0.1 <= report.confidence <= 1.0, (
        f"Confidence {report.confidence} is outside [0.1, 1.0] "
        f"for scenario {scenario}"
    )


def test_property_51_full_data_has_higher_confidence_than_no_data():
    """
    **Property 51: Confidence Adjustment for Data Completeness**
    **Validates: Requirements 22.5, 22.6, 22.7**

    When all data sources are available, confidence SHALL be higher than
    when no data sources are available.
    """
    # Full data scenario
    full_fetcher = _make_fetcher(
        index_data={"sh000300": _make_index_data(), "sh000001": _make_index_data("sh000001")},
        breadth_data=_make_breadth_data(),
        sector_data=_make_sector_data(),
        capital_data=_make_capital_data(),
    )
    full_engine = _build_engine(full_fetcher)
    full_report, _ = full_engine.run(date="2024-01-15")

    # No data scenario
    empty_fetcher = _make_fetcher()  # all return None/empty
    empty_engine = _build_engine(empty_fetcher)
    empty_report, _ = empty_engine.run(date="2024-01-15")

    assert full_report.confidence > empty_report.confidence, (
        f"Full data confidence ({full_report.confidence}) should be greater than "
        f"no-data confidence ({empty_report.confidence})"
    )


@given(failing_sources=_failing_sources_strategy)
@settings(max_examples=40)
def test_property_51_more_missing_data_means_lower_confidence(failing_sources):
    """
    **Property 51: Confidence Adjustment for Data Completeness**
    **Validates: Requirements 22.5, 22.6, 22.7**

    When more data sources are missing, confidence SHALL be lower than
    when all data sources are available.
    """
    # Full data scenario (baseline)
    full_fetcher = _make_fetcher(
        index_data={"sh000300": _make_index_data()},
        breadth_data=_make_breadth_data(),
        sector_data=_make_sector_data(),
        capital_data=_make_capital_data(),
    )
    full_engine = _build_engine(full_fetcher)
    full_report, _ = full_engine.run(date="2024-01-15")

    # Partial data scenario (some sources missing)
    partial_fetcher = _make_fetcher(
        index_data=None if "index_data" in failing_sources else {"sh000300": _make_index_data()},
        breadth_data=None if "breadth_data" in failing_sources else _make_breadth_data(),
        sector_data=None if "sector_data" in failing_sources else _make_sector_data(),
        capital_data=None if "capital_data" in failing_sources else _make_capital_data(),
    )
    partial_engine = _build_engine(partial_fetcher)
    partial_report, _ = partial_engine.run(date="2024-01-15")

    # Partial data confidence must be <= full data confidence
    assert partial_report.confidence <= full_report.confidence, (
        f"Partial data confidence ({partial_report.confidence}) should be <= "
        f"full data confidence ({full_report.confidence}) "
        f"when sources {failing_sources} are missing"
    )


@given(failing_sources=_failing_sources_strategy)
@settings(max_examples=40)
def test_property_51_confidence_reflects_missing_data_in_report(failing_sources):
    """
    **Property 51: Confidence Adjustment for Data Completeness**
    **Validates: Requirements 22.6, 22.7**

    When data is missing, the report SHALL include a missing_data section
    AND the confidence SHALL be below 1.0.
    """
    fetcher = MagicMock()

    if "index_data" in failing_sources:
        fetcher.fetch_index_series.side_effect = RuntimeError("failed")
    else:
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}

    if "breadth_data" in failing_sources:
        fetcher.fetch_breadth_data.side_effect = RuntimeError("failed")
    else:
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()

    if "sector_data" in failing_sources:
        fetcher.fetch_sector_data.side_effect = RuntimeError("failed")
    else:
        fetcher.fetch_sector_data.return_value = _make_sector_data()

    if "capital_data" in failing_sources:
        fetcher.fetch_capital_flow.side_effect = RuntimeError("failed")
    else:
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

    engine = _build_engine(fetcher)
    report, _ = engine.run(date="2024-01-15")

    # When data is missing, missing_data list must be non-empty
    assert len(report.missing_data) > 0, (
        f"missing_data should be non-empty when sources {failing_sources} fail"
    )

    # Confidence must be below 1.0 when data is missing
    assert report.confidence < 1.0, (
        f"Confidence should be < 1.0 when data is missing, got {report.confidence}"
    )


def test_property_51_confidence_is_float_not_nan_or_inf():
    """
    **Property 51: Confidence Adjustment for Data Completeness**
    **Validates: Requirement 22.7**

    The confidence score SHALL always be a finite float (not NaN or Inf).
    """
    # Test with no data
    empty_fetcher = _make_fetcher()
    empty_engine = _build_engine(empty_fetcher)
    empty_report, _ = empty_engine.run(date="2024-01-15")

    assert isinstance(empty_report.confidence, float)
    assert math.isfinite(empty_report.confidence), (
        f"Confidence should be finite, got {empty_report.confidence}"
    )

    # Test with full data
    full_fetcher = _make_fetcher(
        index_data={"sh000300": _make_index_data()},
        breadth_data=_make_breadth_data(),
        sector_data=_make_sector_data(),
        capital_data=_make_capital_data(),
    )
    full_engine = _build_engine(full_fetcher)
    full_report, _ = full_engine.run(date="2024-01-15")

    assert isinstance(full_report.confidence, float)
    assert math.isfinite(full_report.confidence), (
        f"Confidence should be finite, got {full_report.confidence}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
