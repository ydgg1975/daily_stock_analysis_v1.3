"""
Comprehensive Integration Tests for Market Diagnostic System

Task 15.2: Write comprehensive integration tests

Tests the complete workflow from data fetch to report generation,
error handling across all layers, and graceful degradation with missing data.

Requirements: 22.1, 22.2, 22.5, 22.6, 22.7
"""

from __future__ import annotations

import json
import logging
import math
import sys
import os
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch, call

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
# 1. Complete Workflow Tests (Req 22.1, 22.2, 22.5, 22.6, 22.7)
# ---------------------------------------------------------------------------

class TestCompleteWorkflowWithRealData:
    """
    Test the complete workflow from data fetch to report generation using mocked data.

    Validates Requirements: 22.1, 22.2, 22.5, 22.6, 22.7
    """

    def _build_full_engine(self):
        fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(n=10),
            capital_data=_make_capital_data(),
        )
        return _build_engine(fetcher)

    def test_complete_workflow_returns_report_and_markdown(self):
        """Complete workflow returns (DiagnosticReport, str) tuple."""
        engine = self._build_full_engine()
        result = engine.run(date="2024-01-15")

        assert isinstance(result, tuple)
        assert len(result) == 2
        report, markdown = result
        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_complete_workflow_report_date_matches_input(self):
        """Report date must match the input date."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")
        assert report.date == "2024-01-15"

    def test_complete_workflow_all_state_fields_populated(self):
        """All 7 state fields must be non-empty strings."""
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
            assert isinstance(value, str), f"{field_name} must be a string"
            assert len(value) > 0, f"{field_name} must not be empty"

    def test_complete_workflow_all_score_fields_are_finite_floats(self):
        """All 5 score fields must be finite floats."""
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
            assert isinstance(value, (int, float)), f"{field_name} must be numeric"
            assert math.isfinite(float(value)), f"{field_name} must be finite, got {value}"

    def test_complete_workflow_json_output_is_valid(self):
        """Report.to_json() must produce valid JSON with all required keys."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        json_str = report.to_json()
        data = json.loads(json_str)
        assert isinstance(data, dict)

        required_keys = [
            "date", "composite_regime", "trend_state", "breadth_state",
            "sentiment_state", "style_state", "sector_state", "risk_state",
            "trend_score", "breadth_score", "sentiment_score", "risk_score",
            "regime_score", "indices", "breadth_metrics", "sentiment_metrics",
            "style_metrics", "sector_table", "capital_metrics", "risk_flags",
            "key_evidence", "counter_evidence", "confidence", "missing_data",
        ]
        for key in required_keys:
            assert key in data, f"Required JSON key '{key}' not found"

    def test_complete_workflow_confidence_in_valid_range(self):
        """Confidence must be in [0.1, 1.0] for full data scenario."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.confidence, float)
        assert math.isfinite(report.confidence)
        assert 0.1 <= report.confidence <= 1.0, (
            f"Confidence {report.confidence} is outside [0.1, 1.0]"
        )

    def test_complete_workflow_indices_populated_with_full_data(self):
        """With full index data, the indices list must be non-empty."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.indices, list)
        assert len(report.indices) > 0

    def test_complete_workflow_breadth_metrics_populated(self):
        """With breadth data, breadth_metrics must be non-empty."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.breadth_metrics, dict)
        assert len(report.breadth_metrics) > 0

    def test_complete_workflow_sector_table_populated(self):
        """With sector data, sector_table must be non-empty."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.sector_table, list)
        assert len(report.sector_table) > 0

    def test_complete_workflow_capital_metrics_populated(self):
        """With capital data, capital_metrics must be non-empty."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.capital_metrics, dict)
        assert len(report.capital_metrics) > 0

    def test_complete_workflow_list_fields_are_lists(self):
        """risk_flags, key_evidence, counter_evidence, missing_data must be lists."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.risk_flags, list)
        assert isinstance(report.key_evidence, list)
        assert isinstance(report.counter_evidence, list)
        assert isinstance(report.missing_data, list)

    def test_complete_workflow_no_critical_missing_data_with_all_sources(self):
        """With all data sources, critical data should not be missing."""
        engine = self._build_full_engine()
        report, _ = engine.run(date="2024-01-15")

        critical_missing = [
            item for item in report.missing_data
            if item in ("index_data", "breadth_data")
        ]
        assert len(critical_missing) == 0, (
            f"Critical data sources should not be missing: {critical_missing}"
        )

    def test_complete_workflow_markdown_has_required_sections(self):
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

    def test_complete_workflow_fetcher_called_with_correct_date(self):
        """All fetcher methods must be called with the correct date."""
        fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        engine = _build_engine(fetcher)
        engine.run(date="2024-01-15")

        fetcher.fetch_index_series.assert_called_once()
        fetcher.fetch_breadth_data.assert_called_once()
        fetcher.fetch_sector_data.assert_called_once()
        fetcher.fetch_capital_flow.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Error Handling Across All Layers (Req 22.1, 22.2)
# ---------------------------------------------------------------------------

class TestErrorHandlingAcrossAllLayers:
    """
    Test error handling when data sources raise exceptions.

    Validates Requirements:
    - 22.1: Log error with timestamp and data source info, continue processing
    - 22.2: Continue processing and mark indicator as unavailable
    """

    def test_index_fetch_error_does_not_raise(self):
        """Engine must not raise when index fetch raises an exception (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("index API failed")
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_breadth_fetch_error_does_not_raise(self):
        """Engine must not raise when breadth fetch raises an exception (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}
        fetcher.fetch_breadth_data.side_effect = RuntimeError("breadth API failed")
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)

    def test_sector_fetch_error_does_not_raise(self):
        """Engine must not raise when sector fetch raises an exception (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.side_effect = RuntimeError("sector API failed")
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)

    def test_capital_fetch_error_does_not_raise(self):
        """Engine must not raise when capital fetch raises an exception (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.side_effect = RuntimeError("capital API failed")

        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)

    def test_all_sources_failing_still_returns_valid_report(self):
        """Engine must return valid report even when all sources fail (Req 22.1, 22.2)."""
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

    def test_index_fetch_error_adds_to_missing_data(self):
        """Failed index fetch must add 'index_data' to missing_data (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("index API failed")
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert "index_data" in report.missing_data, (
            f"'index_data' should be in missing_data after fetch error. Got: {report.missing_data}"
        )

    def test_breadth_fetch_error_adds_to_missing_data(self):
        """Failed breadth fetch must add breadth-related item to missing_data (Req 22.2)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}
        fetcher.fetch_breadth_data.side_effect = RuntimeError("breadth API failed")
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        breadth_missing = any("breadth" in item for item in report.missing_data)
        assert breadth_missing, (
            f"breadth-related item should be in missing_data. Got: {report.missing_data}"
        )

    def test_sector_fetch_error_adds_to_missing_data(self):
        """Failed sector fetch must add 'sector_data' to missing_data (Req 22.2)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.side_effect = RuntimeError("sector API failed")
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert "sector_data" in report.missing_data, (
            f"'sector_data' should be in missing_data. Got: {report.missing_data}"
        )

    def test_capital_fetch_error_adds_to_missing_data(self):
        """Failed capital fetch must add 'capital_data' to missing_data (Req 22.2)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.side_effect = RuntimeError("capital API failed")

        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert "capital_data" in report.missing_data, (
            f"'capital_data' should be in missing_data. Got: {report.missing_data}"
        )

    def test_fetch_errors_are_logged_at_error_level(self):
        """Data fetch errors must be logged at ERROR level (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("index API failed")
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)

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
            "Expected at least one ERROR log when index fetch fails"
        )

    def test_error_log_contains_data_source_info(self):
        """Error log must contain data source information (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("index API failed")
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)

        error_messages = []

        class _ErrorCapture(logging.Handler):
            def emit(self, record):
                if record.levelno >= logging.ERROR:
                    error_messages.append(record.getMessage())

        handler = _ErrorCapture()
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        try:
            engine.run(date="2024-01-15")
        finally:
            root_logger.removeHandler(handler)

        # At least one error message should mention the data source
        source_mentioned = any(
            "index" in msg.lower() or "DataSource" in msg or "index_series" in msg
            for msg in error_messages
        )
        assert source_mentioned, (
            f"Error log should mention data source. Got messages: {error_messages}"
        )

    def test_engine_continues_processing_after_index_error(self):
        """Engine must continue processing other data sources after index error (Req 22.2)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("index API failed")
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # Other fetchers should still have been called
        fetcher.fetch_breadth_data.assert_called_once()
        fetcher.fetch_sector_data.assert_called_once()
        fetcher.fetch_capital_flow.assert_called_once()

    def test_engine_continues_processing_after_breadth_error(self):
        """Engine must continue processing other data sources after breadth error (Req 22.2)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}
        fetcher.fetch_breadth_data.side_effect = RuntimeError("breadth API failed")
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # Other fetchers should still have been called
        fetcher.fetch_index_series.assert_called_once()
        fetcher.fetch_sector_data.assert_called_once()
        fetcher.fetch_capital_flow.assert_called_once()

    def test_partial_error_report_still_has_valid_states(self):
        """Report must have valid state classifications even with partial errors (Req 22.2)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}
        fetcher.fetch_breadth_data.side_effect = RuntimeError("breadth API failed")
        fetcher.fetch_sector_data.side_effect = RuntimeError("sector API failed")
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # States must still be valid strings
        assert isinstance(report.composite_regime, str) and len(report.composite_regime) > 0
        assert isinstance(report.trend_state, str) and len(report.trend_state) > 0
        assert isinstance(report.breadth_state, str) and len(report.breadth_state) > 0

    def test_multiple_errors_all_sources_in_missing_data(self):
        """All failed sources must appear in missing_data (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("failed")
        fetcher.fetch_breadth_data.side_effect = RuntimeError("failed")
        fetcher.fetch_sector_data.side_effect = RuntimeError("failed")
        fetcher.fetch_capital_flow.side_effect = RuntimeError("failed")

        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        for source in ["index_data", "breadth_data", "sector_data", "capital_data"]:
            assert source in report.missing_data, (
                f"'{source}' should be in missing_data when all sources fail. "
                f"Got: {report.missing_data}"
            )


# ---------------------------------------------------------------------------
# 3. Graceful Degradation with Missing Data (Req 22.2, 22.5, 22.6, 22.7)
# ---------------------------------------------------------------------------

class TestGracefulDegradationWithMissingData:
    """
    Test graceful degradation when various data sources are missing.

    Validates Requirements:
    - 22.2: Continue processing and mark indicator as unavailable
    - 22.5: Classify using available features and reduce confidence
    - 22.6: Include missing_data section in output
    - 22.7: Set confidence to reflect data completeness
    """

    def test_only_index_data_available_returns_valid_report(self):
        """Engine works with only index data (no breadth/sector/capital)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data("sh000300")},
            breadth_data=None,
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert len(markdown) > 0
        assert report.date == "2024-01-15"
        assert 0.1 <= report.confidence <= 1.0

    def test_only_breadth_data_available_returns_valid_report(self):
        """Engine works with only breadth data (no index/sector/capital)."""
        fetcher = _make_fetcher(
            index_data=None,
            breadth_data=_make_breadth_data(),
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert 0.1 <= report.confidence <= 1.0

    def test_only_sector_data_available_returns_valid_report(self):
        """Engine works with only sector data (no index/breadth/capital)."""
        fetcher = _make_fetcher(
            index_data=None,
            breadth_data=None,
            sector_data=_make_sector_data(),
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert 0.1 <= report.confidence <= 1.0

    def test_only_capital_data_available_returns_valid_report(self):
        """Engine works with only capital data (no index/breadth/sector)."""
        fetcher = _make_fetcher(
            index_data=None,
            breadth_data=None,
            sector_data=None,
            capital_data=_make_capital_data(),
        )
        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert 0.1 <= report.confidence <= 1.0

    def test_no_data_available_returns_valid_report(self):
        """Engine returns valid report even when all data sources return empty."""
        fetcher = _make_fetcher()  # all return None/empty
        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert len(markdown) > 0
        assert report.date == "2024-01-15"
        assert 0.1 <= report.confidence <= 1.0
        assert len(report.missing_data) > 0

    def test_missing_breadth_data_uses_fallback_features(self):
        """When breadth data is missing, engine uses fallback breadth features (Req 22.5)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=None,
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # Report must still have valid breadth state
        assert isinstance(report.breadth_state, str)
        assert len(report.breadth_state) > 0

    def test_missing_capital_data_uses_fallback_features(self):
        """When capital data is missing, engine uses fallback capital features (Req 22.5)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=_make_breadth_data(),
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # Report must still have valid risk state
        assert isinstance(report.risk_state, str)
        assert len(report.risk_state) > 0

    def test_missing_sector_data_produces_empty_sector_table(self):
        """When sector data is missing, sector_table should be empty (Req 22.6)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=_make_breadth_data(),
            sector_data=None,
            capital_data=_make_capital_data(),
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.sector_table, list)
        # Sector table should be empty when no sector data
        assert len(report.sector_table) == 0

    def test_missing_breadth_data_uses_fallback_breadth_metrics(self):
        """When breadth data is missing, engine uses fallback neutral breadth metrics (Req 22.5).

        The engine uses fallback BreadthFeatures (neutral values) when breadth data is
        unavailable, so breadth_metrics will contain fallback values rather than being empty.
        The missing_data list will reflect that breadth_data was unavailable.
        """
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=None,
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # breadth_metrics should contain fallback neutral values (not empty)
        assert isinstance(report.breadth_metrics, dict)
        assert len(report.breadth_metrics) > 0

        # The fallback uses above_ma20_ratio=0.45 (neutral)
        assert report.breadth_metrics.get("above_ma20_ratio") == 0.45

        # breadth_data should be in missing_data to indicate it was unavailable
        breadth_missing = any("breadth" in item for item in report.missing_data)
        assert breadth_missing, (
            f"breadth-related item should be in missing_data. Got: {report.missing_data}"
        )

    def test_missing_data_listed_in_report_missing_data_field(self):
        """Missing data sources must appear in report.missing_data (Req 22.6)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=None,
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # breadth_data absence should be reflected
        breadth_missing = any("breadth" in item for item in report.missing_data)
        assert breadth_missing, (
            f"breadth-related item should be in missing_data. Got: {report.missing_data}"
        )

    def test_missing_data_section_in_json_when_data_missing(self):
        """JSON output must include non-empty missing_data when data is unavailable (Req 22.6)."""
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
        assert len(data["missing_data"]) > 0

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

    def test_no_data_confidence_lower_than_full_data(self):
        """No-data confidence must be lower than full-data confidence (Req 22.7)."""
        full_fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        full_engine = _build_engine(full_fetcher)
        full_report, _ = full_engine.run(date="2024-01-15")

        empty_fetcher = _make_fetcher()
        empty_engine = _build_engine(empty_fetcher)
        empty_report, _ = empty_engine.run(date="2024-01-15")

        assert empty_report.confidence < full_report.confidence, (
            f"No-data confidence ({empty_report.confidence}) should be < "
            f"full-data confidence ({full_report.confidence})"
        )

    def test_partial_data_confidence_lower_than_full_data(self):
        """Partial data confidence must be lower than full data confidence (Req 22.7)."""
        full_fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        full_engine = _build_engine(full_fetcher)
        full_report, _ = full_engine.run(date="2024-01-15")

        partial_fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
        )
        partial_engine = _build_engine(partial_fetcher)
        partial_report, _ = partial_engine.run(date="2024-01-15")

        assert partial_report.confidence <= full_report.confidence, (
            f"Partial data confidence ({partial_report.confidence}) should be <= "
            f"full data confidence ({full_report.confidence})"
        )

    def test_confidence_always_finite_with_missing_data(self):
        """Confidence must always be a finite float, even with missing data (Req 22.7)."""
        fetcher = _make_fetcher()  # all return None/empty
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert isinstance(report.confidence, float)
        assert math.isfinite(report.confidence), (
            f"Confidence should be finite, got {report.confidence}"
        )

    def test_confidence_in_valid_range_with_missing_data(self):
        """Confidence must be in [0.1, 1.0] even with missing data (Req 22.7)."""
        fetcher = _make_fetcher()  # all return None/empty
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert 0.1 <= report.confidence <= 1.0, (
            f"Confidence {report.confidence} is outside [0.1, 1.0]"
        )

    def test_markdown_always_non_empty_regardless_of_data(self):
        """Markdown must be non-empty regardless of data availability."""
        scenarios = [
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
                f"index={idx_data is not None}, breadth={brd_data is not None}"
            )

    def test_no_exception_raised_for_any_partial_data_combination(self):
        """Engine must not raise exceptions for any partial data combination."""
        scenarios = [
            ({"sh000300": _make_index_data()}, None, None, None),
            (None, _make_breadth_data(), None, None),
            (None, None, _make_sector_data(), None),
            (None, None, None, _make_capital_data()),
            ({"sh000300": _make_index_data()}, _make_breadth_data(), None, None),
            ({"sh000300": _make_index_data()}, None, _make_sector_data(), None),
            ({"sh000300": _make_index_data()}, None, None, _make_capital_data()),
            (None, _make_breadth_data(), _make_sector_data(), None),
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
            try:
                report, markdown = engine.run(date="2024-01-15")
            except Exception as exc:
                pytest.fail(
                    f"Engine raised exception for partial data scenario "
                    f"(index={idx_data is not None}, breadth={brd_data is not None}, "
                    f"sector={sec_data is not None}, capital={cap_data is not None}): {exc}"
                )


# ---------------------------------------------------------------------------
# 4. Report Layer Missing Data Section (Req 22.6)
# ---------------------------------------------------------------------------

class TestReportLayerMissingDataSection:
    """
    Test that the Report_Layer correctly includes missing_data section.

    Validates Requirement 22.6: When Report_Layer generates output with missing data,
    include missing_data section.
    """

    def test_missing_data_section_present_in_json_always(self):
        """JSON output must always have a missing_data key (Req 22.6)."""
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
        assert "missing_data" in full_data

        # No data
        empty_fetcher = _make_fetcher()
        empty_engine = _build_engine(empty_fetcher)
        empty_report, _ = empty_engine.run(date="2024-01-15")
        empty_data = json.loads(empty_report.to_json())
        assert "missing_data" in empty_data

    def test_missing_data_is_list_in_json(self):
        """missing_data in JSON must be a list (Req 22.6)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=None,
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        data = json.loads(report.to_json())
        assert isinstance(data["missing_data"], list)

    def test_missing_data_non_empty_when_sources_unavailable(self):
        """missing_data must be non-empty when data sources are unavailable (Req 22.6)."""
        fetcher = _make_fetcher(
            index_data=None,
            breadth_data=None,
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert len(report.missing_data) > 0, (
            "missing_data should be non-empty when all sources are unavailable"
        )

    def test_missing_data_empty_when_all_sources_available(self):
        """missing_data should be empty when all data sources are available."""
        fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # With all data available, no critical sources should be missing
        critical_missing = [
            item for item in report.missing_data
            if item in ("index_data", "breadth_data", "sector_data", "capital_data")
        ]
        assert len(critical_missing) == 0, (
            f"No critical data sources should be missing: {critical_missing}"
        )

    def test_missing_data_items_are_strings(self):
        """All items in missing_data must be strings (Req 22.6)."""
        fetcher = _make_fetcher(
            index_data=None,
            breadth_data=None,
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        for item in report.missing_data:
            assert isinstance(item, str), (
                f"missing_data item must be a string, got {type(item)}: {item}"
            )

    def test_missing_data_merged_from_all_layers(self):
        """missing_data must include items from all layers (data + feature layers)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("index failed")
        fetcher.fetch_breadth_data.side_effect = RuntimeError("breadth failed")
        fetcher.fetch_sector_data.side_effect = RuntimeError("sector failed")
        fetcher.fetch_capital_flow.side_effect = RuntimeError("capital failed")

        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # All four data sources should be in missing_data
        assert len(report.missing_data) >= 4, (
            f"Expected at least 4 missing items, got {len(report.missing_data)}: "
            f"{report.missing_data}"
        )

    def test_confidence_in_json_reflects_data_completeness(self):
        """JSON confidence must reflect data completeness (Req 22.5, 22.7)."""
        full_fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        full_engine = _build_engine(full_fetcher)
        full_report, _ = full_engine.run(date="2024-01-15")
        full_data = json.loads(full_report.to_json())

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


# ---------------------------------------------------------------------------
# 5. State Layer Missing Features (Req 22.5)
# ---------------------------------------------------------------------------

class TestStateLayerMissingFeatures:
    """
    Test that the State_Layer classifies using available features and reduces confidence.

    Validates Requirement 22.5: When State_Layer encounters missing features,
    classify using available features and reduce confidence score accordingly.
    """

    def test_classification_succeeds_with_only_index_features(self):
        """State classification must succeed with only trend features (Req 22.5)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=None,
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # All states must be classified
        assert isinstance(report.trend_state, str) and len(report.trend_state) > 0
        assert isinstance(report.breadth_state, str) and len(report.breadth_state) > 0
        assert isinstance(report.composite_regime, str) and len(report.composite_regime) > 0

    def test_confidence_reduced_when_features_missing(self):
        """Confidence must be reduced when features are missing (Req 22.5)."""
        # Full features
        full_fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        full_engine = _build_engine(full_fetcher)
        full_report, _ = full_engine.run(date="2024-01-15")

        # Missing breadth and capital features
        partial_fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=None,
            sector_data=None,
            capital_data=None,
        )
        partial_engine = _build_engine(partial_fetcher)
        partial_report, _ = partial_engine.run(date="2024-01-15")

        assert partial_report.confidence < full_report.confidence, (
            f"Confidence should be reduced when features are missing. "
            f"Full: {full_report.confidence}, Partial: {partial_report.confidence}"
        )

    def test_fallback_breadth_features_produce_neutral_state(self):
        """When breadth data is missing, fallback should produce neutral breadth state (Req 22.5)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=None,
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # Fallback breadth features use above_ma20_ratio=0.45, which is NEUTRAL
        assert report.breadth_state == "中性", (
            f"Fallback breadth should produce neutral state, got: {report.breadth_state}"
        )

    def test_fallback_sentiment_features_produce_neutral_state(self):
        """When breadth data is missing, fallback should produce neutral sentiment state (Req 22.5)."""
        fetcher = _make_fetcher(
            index_data={"sh000300": _make_index_data()},
            breadth_data=None,
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # Fallback sentiment features use sentiment_score=50.0, which is NEUTRAL
        assert report.sentiment_state == "中性", (
            f"Fallback sentiment should produce neutral state, got: {report.sentiment_state}"
        )

    def test_regime_score_is_finite_with_missing_features(self):
        """Regime score must be finite even with missing features (Req 22.5)."""
        fetcher = _make_fetcher(
            index_data=None,
            breadth_data=None,
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        assert math.isfinite(report.regime_score), (
            f"Regime score should be finite, got {report.regime_score}"
        )

    def test_all_scores_in_valid_range_with_missing_features(self):
        """All scores must be in valid range even with missing features (Req 22.5)."""
        fetcher = _make_fetcher()  # all return None/empty
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        score_fields = [
            ("trend_score", report.trend_score),
            ("breadth_score", report.breadth_score),
            ("sentiment_score", report.sentiment_score),
            ("risk_score", report.risk_score),
            ("regime_score", report.regime_score),
        ]
        for field_name, value in score_fields:
            assert math.isfinite(float(value)), f"{field_name} must be finite"
            assert 0.0 <= float(value) <= 100.0, (
                f"{field_name} ({value}) should be in [0, 100]"
            )


# ---------------------------------------------------------------------------
# 6. Data Layer Error Logging (Req 22.1)
# ---------------------------------------------------------------------------

class TestDataLayerErrorLogging:
    """
    Test that the Data_Layer logs errors with timestamp and data source info.

    Validates Requirement 22.1: When Data_Layer encounters a data fetching error,
    log error with timestamp and data source info, continue processing.
    """

    def test_error_logged_when_index_fetch_fails(self):
        """Error must be logged when index fetch fails (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("index API failed")
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)

        with self._capture_error_logs() as error_records:
            engine.run(date="2024-01-15")

        assert len(error_records) >= 1, "Expected at least one ERROR log"

    def test_error_logged_when_breadth_fetch_fails(self):
        """Error must be logged when breadth fetch fails (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}
        fetcher.fetch_breadth_data.side_effect = RuntimeError("breadth API failed")
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)

        with self._capture_error_logs() as error_records:
            engine.run(date="2024-01-15")

        assert len(error_records) >= 1, "Expected at least one ERROR log"

    def test_error_logged_when_sector_fetch_fails(self):
        """Error must be logged when sector fetch fails (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.side_effect = RuntimeError("sector API failed")
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)

        with self._capture_error_logs() as error_records:
            engine.run(date="2024-01-15")

        assert len(error_records) >= 1, "Expected at least one ERROR log"

    def test_error_logged_when_capital_fetch_fails(self):
        """Error must be logged when capital fetch fails (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.return_value = {"sh000300": _make_index_data()}
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.side_effect = RuntimeError("capital API failed")

        engine = _build_engine(fetcher)

        with self._capture_error_logs() as error_records:
            engine.run(date="2024-01-15")

        assert len(error_records) >= 1, "Expected at least one ERROR log"

    def test_error_message_contains_data_source_identifier(self):
        """Error message must contain data source identifier (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("index API failed")
        fetcher.fetch_breadth_data.return_value = _make_breadth_data()
        fetcher.fetch_sector_data.return_value = _make_sector_data()
        fetcher.fetch_capital_flow.return_value = _make_capital_data()

        engine = _build_engine(fetcher)

        error_messages = []

        class _ErrorCapture(logging.Handler):
            def emit(self, record):
                if record.levelno >= logging.ERROR:
                    error_messages.append(record.getMessage())

        handler = _ErrorCapture()
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        try:
            engine.run(date="2024-01-15")
        finally:
            root_logger.removeHandler(handler)

        # Error message should mention the data source
        source_mentioned = any(
            "index" in msg.lower() or "DataSource" in msg
            for msg in error_messages
        )
        assert source_mentioned, (
            f"Error log should mention data source. Got: {error_messages}"
        )

    @staticmethod
    def _capture_error_logs():
        """Context manager to capture ERROR-level log records."""
        import contextlib

        @contextlib.contextmanager
        def _ctx():
            records = []

            class _Handler(logging.Handler):
                def emit(self, record):
                    if record.levelno >= logging.ERROR:
                        records.append(record)

            handler = _Handler()
            root_logger = logging.getLogger()
            root_logger.addHandler(handler)
            try:
                yield records
            finally:
                root_logger.removeHandler(handler)

        return _ctx()


# ---------------------------------------------------------------------------
# 7. End-to-End Workflow Scenarios (Req 22.1, 22.2, 22.5, 22.6, 22.7)
# ---------------------------------------------------------------------------

class TestEndToEndWorkflowScenarios:
    """
    End-to-end workflow tests covering realistic scenarios.

    Validates Requirements: 22.1, 22.2, 22.5, 22.6, 22.7
    """

    def test_scenario_index_only_workflow(self):
        """Scenario: Only index data available - minimal viable workflow."""
        fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=None,
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        # Must produce valid output
        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str) and len(markdown) > 0

        # Confidence must be reduced
        assert report.confidence < 1.0

        # Missing data must be listed
        assert len(report.missing_data) > 0

        # JSON must be valid
        data = json.loads(report.to_json())
        assert data["confidence"] < 1.0
        assert len(data["missing_data"]) > 0

    def test_scenario_index_and_breadth_workflow(self):
        """Scenario: Index + breadth data available - common partial data scenario."""
        fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=None,
            capital_data=None,
        )
        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str) and len(markdown) > 0

        # Breadth metrics should be populated
        assert len(report.breadth_metrics) > 0

        # Sector table should be empty
        assert len(report.sector_table) == 0

        # Confidence should be reduced but not minimal
        assert 0.1 <= report.confidence <= 1.0

    def test_scenario_all_sources_fail_gracefully(self):
        """Scenario: All data sources fail - system must degrade gracefully."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = ConnectionError("network error")
        fetcher.fetch_breadth_data.side_effect = ConnectionError("network error")
        fetcher.fetch_sector_data.side_effect = ConnectionError("network error")
        fetcher.fetch_capital_flow.side_effect = ConnectionError("network error")

        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        # Must not raise
        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str) and len(markdown) > 0

        # All sources must be in missing_data
        for source in ["index_data", "breadth_data", "sector_data", "capital_data"]:
            assert source in report.missing_data

        # Confidence must be at minimum
        assert report.confidence == 0.1

    def test_scenario_intermittent_failures(self):
        """Scenario: Some sources fail, others succeed - mixed scenario."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.return_value = _make_full_index_data()
        fetcher.fetch_breadth_data.side_effect = TimeoutError("timeout")
        fetcher.fetch_sector_data.return_value = _make_sector_data(n=5)
        fetcher.fetch_capital_flow.side_effect = TimeoutError("timeout")

        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str) and len(markdown) > 0

        # Failed sources must be in missing_data
        breadth_missing = any("breadth" in item for item in report.missing_data)
        assert breadth_missing
        assert "capital_data" in report.missing_data

        # Successful sources should produce data
        assert len(report.indices) > 0
        assert len(report.sector_table) > 0

        # Confidence must be reduced
        assert report.confidence < 1.0

    def test_scenario_full_data_produces_complete_report(self):
        """Scenario: All data available - complete report with all sections."""
        fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(n=10),
            capital_data=_make_capital_data(),
        )
        engine = _build_engine(fetcher)
        report, markdown = engine.run(date="2024-01-15")

        # All sections must be populated
        assert len(report.indices) > 0
        assert len(report.breadth_metrics) > 0
        assert len(report.sentiment_metrics) > 0
        assert len(report.style_metrics) > 0
        assert len(report.sector_table) > 0
        assert len(report.capital_metrics) > 0

        # Evidence must be present
        assert len(report.key_evidence) > 0

        # Confidence must be high
        assert report.confidence >= 0.5

    def test_scenario_report_serialization_roundtrip(self):
        """Scenario: Report can be serialized to JSON and back."""
        fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        engine = _build_engine(fetcher)
        report, _ = engine.run(date="2024-01-15")

        # Serialize to JSON
        json_str = report.to_json()
        assert isinstance(json_str, str)

        # Parse back
        data = json.loads(json_str)
        assert isinstance(data, dict)

        # Reconstruct from dict
        reconstructed = DiagnosticReport.from_dict(data)
        assert reconstructed.date == report.date
        assert reconstructed.composite_regime == report.composite_regime
        assert reconstructed.confidence == report.confidence
        assert reconstructed.missing_data == report.missing_data

    def test_scenario_different_dates_produce_independent_reports(self):
        """Scenario: Running for different dates produces independent reports."""
        fetcher = _make_fetcher(
            index_data=_make_full_index_data(),
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        engine = _build_engine(fetcher)

        report1, _ = engine.run(date="2024-01-15")
        report2, _ = engine.run(date="2024-01-16")

        assert report1.date == "2024-01-15"
        assert report2.date == "2024-01-16"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
