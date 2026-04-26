"""
End-to-End Integration Tests for Market Diagnostic Engine

Task 11.3: Write end-to-end integration tests

Tests the complete workflow from data fetch to report generation.
Validates Requirements: 1.6, 22.5, 22.6, 22.7
"""

from __future__ import annotations

import json
import math
import sys
import os
from typing import Dict, List, Optional
from unittest.mock import MagicMock

import pytest

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


def _make_full_index_data() -> Dict[str, IndexDailyData]:
    """Create a full set of 9 core indices."""
    codes = [
        "sh000001", "sz399001", "sz399006", "sh000688",
        "sh000016", "sh000300", "sh000905", "sh000852", "bj899050",
    ]
    return {code: _make_index_data(code) for code in codes}


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
# 1. Full Workflow Tests
# Test complete pipeline from data fetch to report generation
# Requirements: 1.6, 22.5, 22.6, 22.7
# ---------------------------------------------------------------------------

class TestFullWorkflow:
    """
    Test the complete pipeline from data fetch to report generation.

    Validates Requirements: 1.6, 22.5, 22.6, 22.7
    """

    def _build_full_engine(self):
        """Build engine with all data sources available."""
        fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(n=10),
            capital_data=_make_capital_data(),
        )
        return _build_engine(fetcher)

    def test_full_workflow_returns_report_and_markdown(self):
        """Complete workflow should return (DiagnosticReport, str) tuple."""
        engine = self._build_full_engine()
        result = engine.run(date="2024-01-15")

        assert isinstance(result, tuple)
        assert len(result) == 2
        report, markdown = result
        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_full_workflow_report_has_all_required_fields(self):
        """Report must have all required state and score fields populated."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        # Date
        assert report.date == "2024-01-15"

        # All 7 state fields must be non-empty strings
        assert report.composite_regime and isinstance(report.composite_regime, str)
        assert report.trend_state and isinstance(report.trend_state, str)
        assert report.breadth_state and isinstance(report.breadth_state, str)
        assert report.sentiment_state and isinstance(report.sentiment_state, str)
        assert report.style_state and isinstance(report.style_state, str)
        assert report.sector_state and isinstance(report.sector_state, str)
        assert report.risk_state and isinstance(report.risk_state, str)

        # All 5 score fields must be floats
        assert isinstance(report.trend_score, float)
        assert isinstance(report.breadth_score, float)
        assert isinstance(report.sentiment_score, float)
        assert isinstance(report.risk_score, float)
        assert isinstance(report.regime_score, float)

    def test_full_workflow_markdown_has_required_sections(self):
        """Markdown output must contain all required section headers."""
        engine = self._build_full_engine()
        _, markdown = engine.run(date="2024-01-15")

        required_sections = [
            "一句话结论",
            "状态仪表盘",
            "指数与价格结构",
            "市场广度",
            "情绪与赚钱效应",
            "风格轮动",
            "板块主线诊断",
            "资金流向",
            "风险警报",
            "策略映射建议",
            "证据与置信度",
        ]
        for section in required_sections:
            assert section in markdown, (
                f"Required section '{section}' not found in Markdown output"
            )

    def test_full_workflow_json_output_is_valid(self):
        """Report.to_json() must produce valid JSON with all required keys."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        json_str = report.to_json()
        assert isinstance(json_str, str)

        # Must be valid JSON
        data = json.loads(json_str)
        assert isinstance(data, dict)

        # Required top-level keys (Req 18.1-18.10)
        required_keys = [
            "date",
            "composite_regime",
            "trend_state",
            "breadth_state",
            "sentiment_state",
            "style_state",
            "sector_state",
            "risk_state",
            "trend_score",
            "breadth_score",
            "sentiment_score",
            "risk_score",
            "regime_score",
            "indices",
            "breadth_metrics",
            "sentiment_metrics",
            "style_metrics",
            "sector_table",
            "capital_metrics",
            "risk_flags",
            "key_evidence",
            "counter_evidence",
            "confidence",
            "missing_data",
        ]
        for key in required_keys:
            assert key in data, f"Required JSON key '{key}' not found in output"

    def test_full_workflow_confidence_in_valid_range(self):
        """Confidence must be in [0.1, 1.0] for full data scenario."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.confidence, float)
        assert math.isfinite(report.confidence), (
            f"Confidence must be finite, got {report.confidence}"
        )
        assert 0.1 <= report.confidence <= 1.0, (
            f"Confidence {report.confidence} is outside [0.1, 1.0]"
        )

    def test_full_workflow_indices_populated(self):
        """With full index data, the indices list must be non-empty."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.indices, list)
        assert len(report.indices) > 0, "indices list should be non-empty with full data"

    def test_full_workflow_breadth_metrics_populated(self):
        """With breadth data available, breadth_metrics must be non-empty."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.breadth_metrics, dict)
        assert len(report.breadth_metrics) > 0, (
            "breadth_metrics should be non-empty when breadth data is available"
        )

    def test_full_workflow_sentiment_metrics_populated(self):
        """With breadth data available, sentiment_metrics must be non-empty."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.sentiment_metrics, dict)
        assert len(report.sentiment_metrics) > 0, (
            "sentiment_metrics should be non-empty when breadth data is available"
        )

    def test_full_workflow_style_metrics_populated(self):
        """With index data available, style_metrics must be non-empty."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.style_metrics, dict)
        assert len(report.style_metrics) > 0, (
            "style_metrics should be non-empty when index data is available"
        )

    def test_full_workflow_sector_table_populated(self):
        """With sector data available, sector_table must be non-empty."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.sector_table, list)
        assert len(report.sector_table) > 0, (
            "sector_table should be non-empty when sector data is available"
        )

    def test_full_workflow_capital_metrics_populated(self):
        """With capital data available, capital_metrics must be non-empty."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.capital_metrics, dict)
        assert len(report.capital_metrics) > 0, (
            "capital_metrics should be non-empty when capital data is available"
        )

    def test_full_workflow_list_fields_are_lists(self):
        """risk_flags, key_evidence, counter_evidence, missing_data must be lists."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.risk_flags, list)
        assert isinstance(report.key_evidence, list)
        assert isinstance(report.counter_evidence, list)
        assert isinstance(report.missing_data, list)

    def test_full_workflow_no_missing_data_with_all_sources(self):
        """With all data sources available, missing_data should be empty or minimal."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        # With all data available, missing_data should be empty
        assert isinstance(report.missing_data, list)
        # No critical data sources should be missing
        critical_missing = [
            item for item in report.missing_data
            if item in ("index_data", "breadth_data")
        ]
        assert len(critical_missing) == 0, (
            f"Critical data sources should not be missing: {critical_missing}"
        )


# ---------------------------------------------------------------------------
# 2. Partial Data Workflow Tests
# Test with only some data sources available
# Requirements: 1.6, 22.5, 22.6, 22.7
# ---------------------------------------------------------------------------

class TestPartialDataWorkflow:
    """
    Test graceful degradation when only some data sources are available.

    Validates Requirements: 1.6, 22.5, 22.6, 22.7
    """

    def test_only_index_data_available(self):
        """Engine should work with only index data (no breadth/sector/capital)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data("sh000300")},
            breadth_data=None,
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        # Must return valid types
        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert len(markdown) > 0

        # Date must be correct
        assert report.date == "2024-01-15"

        # Confidence must be in valid range
        assert 0.1 <= report.confidence <= 1.0

        # Missing data should reflect unavailable sources
        assert "breadth_data" in report.missing_data or "breadth_features" in report.missing_data

    def test_only_index_data_has_reduced_confidence(self):
        """Confidence should be lower with only index data vs full data."""
        # Full data
        full_fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        full_engine = _build_engine(full_fetcher)
        full_report, _ = full_engine.run(date="2024-01-15")

        # Only index data
        partial_fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
        )
        partial_engine = _build_engine(partial_fetcher)
        partial_report, _ = partial_engine.run(date="2024-01-15")

        assert partial_report.confidence <= full_report.confidence, (
            f"Partial data confidence ({partial_report.confidence}) should be <= "
            f"full data confidence ({full_report.confidence})"
        )

    def test_index_plus_breadth_data_available(self):
        """Engine should work with index + breadth data (no sector/capital)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data("sh000300")},
            breadth_data=_make_breadth_data(),
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert report.date == "2024-01-15"
        assert 0.1 <= report.confidence <= 1.0

        # Breadth metrics should be populated
        assert len(report.breadth_metrics) > 0

        # Sector and capital should be missing
        assert len(report.sector_table) == 0 or "sector_data" in report.missing_data

    def test_index_plus_sector_data_available(self):
        """Engine should work with index + sector data (no breadth/capital)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data("sh000300")},
            breadth_data=None,
            sector_data=_make_sector_data(),
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert report.date == "2024-01-15"
        assert 0.1 <= report.confidence <= 1.0

        # Sector table should be populated
        assert len(report.sector_table) > 0

    def test_partial_data_missing_sources_listed_in_report(self):
        """Missing data sources must appear in report.missing_data."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=None,   # missing
            sector_data=None,    # missing
            capital_data=None,   # missing
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # breadth_data absence should be reflected
        breadth_missing = any("breadth" in item for item in report.missing_data)
        assert breadth_missing, (
            f"breadth-related item should be in missing_data. Got: {report.missing_data}"
        )

    def test_partial_data_confidence_below_one(self):
        """Confidence must be below 1.0 when data is missing (Req 22.7)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=None,
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert report.confidence < 1.0, (
            f"Confidence should be < 1.0 when data is missing, got {report.confidence}"
        )

    def test_no_data_available_still_returns_valid_report(self):
        """Engine must return a valid report even when all data sources return empty."""
        fetcher = _make_fetcher()  # all return None/empty
        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert len(markdown) > 0
        assert report.date == "2024-01-15"
        assert 0.1 <= report.confidence <= 1.0
        assert len(report.missing_data) > 0

    def test_no_data_confidence_lower_than_full_data(self):
        """No-data confidence must be lower than full-data confidence (Req 22.5)."""
        # Full data
        full_fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        full_engine = _build_engine(full_fetcher)
        full_report, _ = full_engine.run(date="2024-01-15")

        # No data
        empty_fetcher = _make_fetcher()
        empty_engine = _build_engine(empty_fetcher)
        empty_report, _ = empty_engine.run(date="2024-01-15")

        assert empty_report.confidence < full_report.confidence, (
            f"No-data confidence ({empty_report.confidence}) should be < "
            f"full-data confidence ({full_report.confidence})"
        )

    def test_partial_data_markdown_always_non_empty(self):
        """Markdown must be non-empty regardless of data availability."""
        scenarios = [
            # (index_data, breadth_data, sector_data, capital_data)
            ({"sh000300": _make_index_data()}, None, None, None),
            ({"sh000300": _make_index_data()}, _make_breadth_data(), None, None),
            ({"sh000300": _make_index_data()}, None, _make_sector_data(), None),
            (None, None, None, None),
        ]
        for idx_data, brd_data, sec_data, cap_data in scenarios:
            fetcher = _make_fetcher(
                index_data=idx_data,
                breadth_data=brd_data,
                sector_data=sec_data,
                capital_data=cap_data,
            )
            engine = _build_engine(fetcher)
            _, markdown = engine.run(date="2024-01-15")
            assert isinstance(markdown, str)
            assert len(markdown) > 0, (
                f"Markdown should be non-empty for scenario: "
                f"index={idx_data is not None}, breadth={brd_data is not None}, "
                f"sector={sec_data is not None}, capital={cap_data is not None}"
            )

    def test_partial_data_no_exception_raised(self):
        """Engine must not raise exceptions for any partial data combination."""
        scenarios = [
            ({"sh000300": _make_index_data()}, None, None, None),
            (None, _make_breadth_data(), None, None),
            (None, None, _make_sector_data(), None),
            (None, None, None, _make_capital_data()),
            ({"sh000300": _make_index_data()}, _make_breadth_data(), None, None),
            ({"sh000300": _make_index_data()}, None, _make_sector_data(), None),
            ({"sh000300": _make_index_data()}, None, None, _make_capital_data()),
        ]
        for idx_data, brd_data, sec_data, cap_data in scenarios:
            fetcher = _make_fetcher(
                index_data=idx_data,
                breadth_data=brd_data,
                sector_data=sec_data,
                capital_data=cap_data,
            )
            engine = _build_engine(fetcher)
            try:
                report, markdown = engine.run(date="2024-01-15")
            except Exception as exc:
                pytest.fail(
                    f"Engine raised exception for partial data scenario "
                    f"(index={idx_data is not None}, breadth={brd_data is not None}, "
                    f"sector={sec_data is not None}, capital={cap_data is not None}): {exc}"
                )


# ---------------------------------------------------------------------------
# 3. Report Completeness Tests
# Verify the complete report structure
# Requirements: 18.1-18.10, 22.5, 22.6, 22.7
# ---------------------------------------------------------------------------

class TestReportCompleteness:
    """
    Verify the complete report structure with all required fields.

    Validates Requirements: 18.1-18.10, 22.5, 22.6, 22.7
    """

    def _build_full_engine(self):
        fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(n=10),
            capital_data=_make_capital_data(),
        )
        return _build_engine(fetcher)

    def test_all_7_state_fields_populated(self):
        """All 7 state fields must be non-empty strings (Req 18.1)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        state_fields = [
            ("composite_regime", report.composite_regime),
            ("trend_state", report.trend_state),
            ("breadth_state", report.breadth_state),
            ("sentiment_state", report.sentiment_state),
            ("style_state", report.style_state),
            ("sector_state", report.sector_state),
            ("risk_state", report.risk_state),
        ]
        for field_name, value in state_fields:
            assert value is not None, f"{field_name} must not be None"
            assert isinstance(value, str), f"{field_name} must be a string, got {type(value)}"
            assert len(value) > 0, f"{field_name} must not be empty"

    def test_all_5_score_fields_populated(self):
        """All 5 score fields must be floats (Req 18.1)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        score_fields = [
            ("trend_score", report.trend_score),
            ("breadth_score", report.breadth_score),
            ("sentiment_score", report.sentiment_score),
            ("risk_score", report.risk_score),
            ("regime_score", report.regime_score),
        ]
        for field_name, value in score_fields:
            assert value is not None, f"{field_name} must not be None"
            assert isinstance(value, (int, float)), (
                f"{field_name} must be numeric, got {type(value)}"
            )
            assert math.isfinite(float(value)), (
                f"{field_name} must be finite, got {value}"
            )

    def test_indices_field_is_list(self):
        """indices must be a list (Req 18.2)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")
        assert isinstance(report.indices, list)

    def test_breadth_metrics_field_is_dict(self):
        """breadth_metrics must be a dict (Req 18.3)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")
        assert isinstance(report.breadth_metrics, dict)

    def test_sentiment_metrics_field_is_dict(self):
        """sentiment_metrics must be a dict (Req 18.4)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")
        assert isinstance(report.sentiment_metrics, dict)

    def test_style_metrics_field_is_dict(self):
        """style_metrics must be a dict (Req 18.5)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")
        assert isinstance(report.style_metrics, dict)

    def test_sector_table_field_is_list(self):
        """sector_table must be a list (Req 18.6)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")
        assert isinstance(report.sector_table, list)

    def test_capital_metrics_field_is_dict(self):
        """capital_metrics must be a dict (Req 18.7)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")
        assert isinstance(report.capital_metrics, dict)

    def test_risk_flags_is_list(self):
        """risk_flags must be a list (Req 18.8)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")
        assert isinstance(report.risk_flags, list)

    def test_key_evidence_is_list(self):
        """key_evidence must be a list (Req 18.9)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")
        assert isinstance(report.key_evidence, list)

    def test_counter_evidence_is_list(self):
        """counter_evidence must be a list (Req 18.9)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")
        assert isinstance(report.counter_evidence, list)

    def test_missing_data_is_list(self):
        """missing_data must be a list (Req 18.10)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")
        assert isinstance(report.missing_data, list)

    def test_confidence_is_float_in_range(self):
        """confidence must be a float in [0.1, 1.0] (Req 18.9, 22.7)."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.confidence, float)
        assert math.isfinite(report.confidence), (
            f"confidence must be finite, got {report.confidence}"
        )
        assert 0.1 <= report.confidence <= 1.0, (
            f"confidence {report.confidence} is outside [0.1, 1.0]"
        )

    def test_missing_data_section_in_json_when_data_missing(self):
        """JSON output must include missing_data when data is unavailable (Req 18.10)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=None,
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        json_str = report.to_json()
        data = json.loads(json_str)

        assert "missing_data" in data
        assert isinstance(data["missing_data"], list)
        assert len(data["missing_data"]) > 0, (
            "missing_data in JSON should be non-empty when data sources are unavailable"
        )

    def test_confidence_in_json_reflects_data_completeness(self):
        """JSON confidence must reflect data completeness (Req 22.5, 22.7)."""
        # Full data
        full_fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        full_engine = _build_engine(full_fetcher)
        full_report, _ = full_engine.run(date="2024-01-15")
        full_data = json.loads(full_report.to_json())

        # Partial data
        partial_fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
        )
        partial_engine = _build_engine(partial_fetcher)
        partial_report, _ = partial_engine.run(date="2024-01-15")
        partial_data = json.loads(partial_report.to_json())

        assert partial_data["confidence"] <= full_data["confidence"], (
            f"Partial data confidence ({partial_data['confidence']}) should be <= "
            f"full data confidence ({full_data['confidence']})"
        )

    def test_markdown_contains_missing_data_section_when_data_missing(self):
        """Markdown must include missing data info when data is unavailable (Req 22.6)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=None,
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        _, markdown = engine.run(date="2024-01-15")

        # The evidence section should mention missing data
        assert "缺失数据" in markdown or "missing" in markdown.lower() or "不可用" in markdown, (
            "Markdown should indicate missing data when sources are unavailable"
        )

    def test_sector_table_entries_have_required_fields(self):
        """Each sector_table entry must have required fields (Req 18.6)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(n=5),
            capital_data=_make_capital_data(),
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert len(report.sector_table) > 0
        for entry in report.sector_table:
            assert isinstance(entry, dict)
            assert "industry_code" in entry
            assert "industry_name" in entry
            assert "strength_score" in entry

    def test_indices_entries_have_required_fields(self):
        """Each indices entry must have required fields (Req 18.2)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data("sh000300")},
            breadth_data=_make_breadth_data(),
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert len(report.indices) > 0
        for entry in report.indices:
            assert isinstance(entry, dict)
            assert "code" in entry
            # Technical indicators should be present
            assert "ma_alignment" in entry
            assert "macd_signal" in entry


# ---------------------------------------------------------------------------
# 4. Error Handling in E2E Workflow
# Test that fetch errors are handled gracefully
# Requirements: 1.6, 22.1, 22.2
# ---------------------------------------------------------------------------

class TestErrorHandlingE2E:
    """
    Test that data fetch errors are handled gracefully in the full workflow.

    Validates Requirements: 1.6, 22.1, 22.2
    """

    def test_fetch_exception_does_not_propagate(self):
        """Exceptions from data fetchers must not propagate to the caller."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("Network timeout")
        fetcher.fetch_breadth_data.side_effect = ConnectionError("API unavailable")
        fetcher.fetch_sector_data.side_effect = ValueError("Invalid response")
        fetcher.fetch_capital_flow.side_effect = TimeoutError("Request timed out")

        engine = _build_engine(fetcher)

        # Must not raise
        try:
            report, markdown = engine.run(date="2024-01-15")
        except Exception as exc:
            pytest.fail(f"Engine should not raise exceptions, but got: {exc}")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)

    def test_fetch_exception_adds_to_missing_data(self):
        """Failed fetches must add the source to missing_data (Req 1.6)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("failed")
        fetcher.fetch_breadth_data.side_effect = RuntimeError("failed")
        fetcher.fetch_sector_data.return_value = []
        fetcher.fetch_capital_flow.return_value = None

        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert "index_data" in report.missing_data, (
            f"index_data should be in missing_data after fetch failure. "
            f"Got: {report.missing_data}"
        )
        assert "breadth_data" in report.missing_data, (
            f"breadth_data should be in missing_data after fetch failure. "
            f"Got: {report.missing_data}"
        )

    def test_fetch_exception_reduces_confidence(self):
        """Fetch failures must reduce confidence below 1.0 (Req 22.7)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("failed")
        fetcher.fetch_breadth_data.side_effect = RuntimeError("failed")
        fetcher.fetch_sector_data.return_value = []
        fetcher.fetch_capital_flow.return_value = None

        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert report.confidence < 1.0, (
            f"Confidence should be < 1.0 after fetch failures, got {report.confidence}"
        )

    def test_all_fetches_fail_still_produces_valid_report(self):
        """All fetch failures must still produce a valid DiagnosticReport."""
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
        assert report.date == "2024-01-15"
        assert 0.1 <= report.confidence <= 1.0
        assert len(report.missing_data) > 0

        # All 7 state fields must still be populated
        assert report.composite_regime
        assert report.trend_state
        assert report.breadth_state
        assert report.sentiment_state
        assert report.style_state
        assert report.sector_state
        assert report.risk_state


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
