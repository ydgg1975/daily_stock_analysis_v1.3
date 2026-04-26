"""
Tests for MarketDiagnosticEngine

Verifies engine instantiation, run() with mock data, and graceful degradation.

Requirements: 21.6, 22.1, 22.2, 22.5, 22.6, 22.7
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

try:
    from src.market_diagnostic.engine import (
        MarketDiagnosticEngine,
        generate_one_sentence_summary,
    )
    from src.market_diagnostic.data.models import (
        IndexDailyData,
        MarketBreadthData,
        SectorDailyData,
        CapitalFlowData,
    )
    from src.market_diagnostic.reports.schema import DiagnosticReport
    from src.market_diagnostic.states.classifier import MarketStateResult
    from src.market_diagnostic.states.enums import (
        TrendState, BreadthState, SentimentState, StyleState,
        SectorState, RiskState, CompositeRegime,
    )
except ImportError:
    from market_diagnostic.engine import (  # type: ignore[no-redef]
        MarketDiagnosticEngine,
        generate_one_sentence_summary,
    )
    from market_diagnostic.data.models import (  # type: ignore[no-redef]
        IndexDailyData,
        MarketBreadthData,
        SectorDailyData,
        CapitalFlowData,
    )
    from market_diagnostic.reports.schema import DiagnosticReport  # type: ignore[no-redef]
    from market_diagnostic.states.classifier import MarketStateResult  # type: ignore[no-redef]
    from market_diagnostic.states.enums import (  # type: ignore[no-redef]
        TrendState, BreadthState, SentimentState, StyleState,
        SectorState, RiskState, CompositeRegime,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_index_data(code: str = "sh000300", n: int = 60) -> IndexDailyData:
    """Create a realistic IndexDailyData with a 60-day close series."""
    import math
    # Simulate a mild uptrend
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


def _make_breadth_data() -> MarketBreadthData:
    return MarketBreadthData(
        date="2024-01-15",
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


def _make_mock_data_manager(
    index_data: Optional[Dict] = None,
    breadth_data: Optional[MarketBreadthData] = None,
    sector_data: Optional[List] = None,
    capital_data: Optional[CapitalFlowData] = None,
):
    """Create a mock DataFetcherManager that returns preset data."""
    mock_dm = MagicMock()
    return mock_dm


def _make_mock_fetcher(
    index_data: Optional[Dict] = None,
    breadth_data: Optional[MarketBreadthData] = None,
    sector_data: Optional[List] = None,
    capital_data: Optional[CapitalFlowData] = None,
):
    """Create a mock DiagnosticDataFetcher."""
    mock_fetcher = MagicMock()
    mock_fetcher.fetch_index_series.return_value = index_data or {}
    mock_fetcher.fetch_breadth_data.return_value = breadth_data
    mock_fetcher.fetch_sector_data.return_value = sector_data or []
    mock_fetcher.fetch_capital_flow.return_value = capital_data
    return mock_fetcher


# ---------------------------------------------------------------------------
# Tests: instantiation
# ---------------------------------------------------------------------------

class TestEngineInstantiation:
    def test_engine_can_be_instantiated(self):
        """Engine should initialize without errors given a mock data_manager."""
        mock_dm = MagicMock()
        engine = MarketDiagnosticEngine(data_manager=mock_dm)
        assert engine.fetcher is not None
        assert engine.classifier is not None
        assert engine.renderer is not None
        assert engine.analyzer is None
        assert engine.enable_llm_narrative is True

    def test_engine_with_analyzer(self):
        """Engine should accept an optional analyzer."""
        mock_dm = MagicMock()
        mock_analyzer = MagicMock()
        engine = MarketDiagnosticEngine(
            data_manager=mock_dm,
            analyzer=mock_analyzer,
            enable_llm_narrative=True,
        )
        assert engine.analyzer is mock_analyzer

    def test_engine_llm_disabled(self):
        """Engine should respect enable_llm_narrative=False."""
        mock_dm = MagicMock()
        engine = MarketDiagnosticEngine(
            data_manager=mock_dm,
            enable_llm_narrative=False,
        )
        assert engine.enable_llm_narrative is False


# ---------------------------------------------------------------------------
# Tests: run() with mock data
# ---------------------------------------------------------------------------

class TestEngineRun:
    def _build_engine_with_mock_fetcher(self, fetcher):
        """Helper: build engine and inject mock fetcher."""
        mock_dm = MagicMock()
        engine = MarketDiagnosticEngine(data_manager=mock_dm, enable_llm_narrative=False)
        engine.fetcher = fetcher
        return engine

    def test_run_returns_tuple(self):
        """run() should return (DiagnosticReport, str)."""
        index_data = {
            "sh000300": _make_index_data("sh000300"),
            "sh000001": _make_index_data("sh000001"),
        }
        fetcher = _make_mock_fetcher(
            index_data=index_data,
            breadth_data=_make_breadth_data(),
            sector_data=_make_sector_data(),
            capital_data=_make_capital_data(),
        )
        engine = self._build_engine_with_mock_fetcher(fetcher)
        result = engine.run(date="2024-01-15")

        assert isinstance(result, tuple)
        assert len(result) == 2
        report, markdown = result
        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)

    def test_run_report_has_date(self):
        """Report should contain the requested date."""
        index_data = {"sh000300": _make_index_data("sh000300")}
        fetcher = _make_mock_fetcher(
            index_data=index_data,
            breadth_data=_make_breadth_data(),
        )
        engine = self._build_engine_with_mock_fetcher(fetcher)
        report, _ = engine.run(date="2024-01-15")
        assert report.date == "2024-01-15"

    def test_run_markdown_contains_date(self):
        """Markdown output should contain the date."""
        index_data = {"sh000300": _make_index_data("sh000300")}
        fetcher = _make_mock_fetcher(
            index_data=index_data,
            breadth_data=_make_breadth_data(),
        )
        engine = self._build_engine_with_mock_fetcher(fetcher)
        _, markdown = engine.run(date="2024-01-15")
        assert "2024-01-15" in markdown

    def test_run_report_has_composite_regime(self):
        """Report should have a non-empty composite_regime."""
        index_data = {"sh000300": _make_index_data("sh000300")}
        fetcher = _make_mock_fetcher(
            index_data=index_data,
            breadth_data=_make_breadth_data(),
        )
        engine = self._build_engine_with_mock_fetcher(fetcher)
        report, _ = engine.run(date="2024-01-15")
        assert report.composite_regime != ""

    def test_run_confidence_in_range(self):
        """Confidence should be in [0.1, 1.0]."""
        index_data = {"sh000300": _make_index_data("sh000300")}
        fetcher = _make_mock_fetcher(
            index_data=index_data,
            breadth_data=_make_breadth_data(),
        )
        engine = self._build_engine_with_mock_fetcher(fetcher)
        report, _ = engine.run(date="2024-01-15")
        assert 0.1 <= report.confidence <= 1.0

    def test_run_with_default_date(self):
        """run() without date argument should use today's date."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        index_data = {"sh000300": _make_index_data("sh000300")}
        fetcher = _make_mock_fetcher(index_data=index_data)
        engine = self._build_engine_with_mock_fetcher(fetcher)
        report, _ = engine.run()
        assert report.date == today


# ---------------------------------------------------------------------------
# Tests: graceful degradation (Req 22.1, 22.2, 22.6, 22.7)
# ---------------------------------------------------------------------------

class TestGracefulDegradation:
    def _build_engine_with_mock_fetcher(self, fetcher):
        mock_dm = MagicMock()
        engine = MarketDiagnosticEngine(data_manager=mock_dm, enable_llm_narrative=False)
        engine.fetcher = fetcher
        return engine

    def test_run_with_no_data_still_returns_report(self):
        """Engine should return a report even when all data fetches fail."""
        fetcher = _make_mock_fetcher()  # all return empty/None
        engine = self._build_engine_with_mock_fetcher(fetcher)
        report, markdown = engine.run(date="2024-01-15")
        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_run_with_no_data_has_missing_data_list(self):
        """Report should include missing_data entries when data is unavailable."""
        fetcher = _make_mock_fetcher()  # all return empty/None
        engine = self._build_engine_with_mock_fetcher(fetcher)
        report, _ = engine.run(date="2024-01-15")
        # At minimum, index_data and breadth_data should be flagged
        assert len(report.missing_data) > 0

    def test_run_with_no_data_confidence_reduced(self):
        """Confidence should be reduced when data is missing."""
        fetcher = _make_mock_fetcher()  # all return empty/None
        engine = self._build_engine_with_mock_fetcher(fetcher)
        report, _ = engine.run(date="2024-01-15")
        # With missing data, confidence should be below 1.0
        assert report.confidence < 1.0

    def test_run_with_only_index_data(self):
        """Engine should work with only index data (no breadth/sector/capital)."""
        index_data = {"sh000300": _make_index_data("sh000300")}
        fetcher = _make_mock_fetcher(index_data=index_data)
        engine = self._build_engine_with_mock_fetcher(fetcher)
        report, markdown = engine.run(date="2024-01-15")
        assert isinstance(report, DiagnosticReport)
        assert report.date == "2024-01-15"

    def test_run_with_fetcher_exception_still_returns(self):
        """Engine should handle exceptions from fetcher gracefully."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("Network error")
        fetcher.fetch_breadth_data.side_effect = RuntimeError("Network error")
        fetcher.fetch_sector_data.side_effect = RuntimeError("Network error")
        fetcher.fetch_capital_flow.side_effect = RuntimeError("Network error")

        mock_dm = MagicMock()
        engine = MarketDiagnosticEngine(data_manager=mock_dm, enable_llm_narrative=False)
        engine.fetcher = fetcher

        report, markdown = engine.run(date="2024-01-15")
        assert isinstance(report, DiagnosticReport)
        assert len(report.missing_data) > 0

    def test_run_logs_errors_on_fetch_failure(self, caplog):
        """Engine should log errors when data fetching fails (Req 22.1)."""
        fetcher = MagicMock()
        fetcher.fetch_index_series.side_effect = RuntimeError("API timeout")
        fetcher.fetch_breadth_data.return_value = None
        fetcher.fetch_sector_data.return_value = []
        fetcher.fetch_capital_flow.return_value = None

        mock_dm = MagicMock()
        engine = MarketDiagnosticEngine(data_manager=mock_dm, enable_llm_narrative=False)
        engine.fetcher = fetcher

        with caplog.at_level(logging.ERROR, logger="src.market_diagnostic.engine"):
            engine.run(date="2024-01-15")

        # Should have logged at least one error
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) >= 1


# ---------------------------------------------------------------------------
# Tests: generate_one_sentence_summary
# ---------------------------------------------------------------------------

class TestGenerateOneSentenceSummary:
    def _make_state_result(self) -> MarketStateResult:
        return MarketStateResult(
            date="2024-01-15",
            trend_state=TrendState.STRONG_UP,
            breadth_state=BreadthState.STRONG,
            sentiment_state=SentimentState.ACTIVE,
            style_state=StyleState.GROWTH_DOMINANT,
            sector_state=SectorState.SINGLE_THEME,
            risk_state=RiskState.NEUTRAL,
            composite_regime=CompositeRegime.TREND_RISK_ON_GROWTH,
            trend_score=85.0,
            breadth_score=70.0,
            sentiment_score=65.0,
            style_score=75.0,
            sector_score=80.0,
            risk_score=35.0,
            regime_score=72.0,
            key_evidence=["沪深300 MA多头排列，MACD金叉"],
            counter_evidence=[],
            confidence=0.85,
            risk_flags=[],
            missing_data=[],
        )

    def test_summary_is_string(self):
        """generate_one_sentence_summary should return a string."""
        state = self._make_state_result()
        summary = generate_one_sentence_summary(state)
        assert isinstance(summary, str)

    def test_summary_is_non_empty(self):
        """Summary should not be empty."""
        state = self._make_state_result()
        summary = generate_one_sentence_summary(state)
        assert len(summary) > 0

    def test_summary_contains_regime(self):
        """Summary should mention the composite regime."""
        state = self._make_state_result()
        summary = generate_one_sentence_summary(state)
        # Should contain either the regime key or its display name
        assert "趋势进攻" in summary or "trend_risk_on_growth" in summary

    def test_summary_contains_confidence(self):
        """Summary should mention confidence percentage."""
        state = self._make_state_result()
        summary = generate_one_sentence_summary(state)
        assert "85%" in summary or "置信度" in summary

    def test_summary_with_all_regimes(self):
        """generate_one_sentence_summary should work for all CompositeRegime values."""
        for regime in CompositeRegime:
            state = MarketStateResult(
                date="2024-01-15",
                trend_state=TrendState.RANGING,
                breadth_state=BreadthState.NEUTRAL,
                sentiment_state=SentimentState.NEUTRAL,
                style_state=StyleState.STYLE_CONFLICT,
                sector_state=SectorState.NO_THEME,
                risk_state=RiskState.NEUTRAL,
                composite_regime=regime,
                trend_score=50.0,
                breadth_score=50.0,
                sentiment_score=50.0,
                style_score=50.0,
                sector_score=50.0,
                risk_score=50.0,
                regime_score=50.0,
                key_evidence=[],
                counter_evidence=[],
                confidence=0.7,
                risk_flags=[],
                missing_data=[],
            )
            summary = generate_one_sentence_summary(state)
            assert isinstance(summary, str)
            assert len(summary) > 0


# ---------------------------------------------------------------------------
# Tests: LLM narrative integration
# ---------------------------------------------------------------------------

class TestLLMNarrative:
    def test_llm_narrative_called_when_enabled(self):
        """LLM analyzer should be called when enable_llm_narrative=True and analyzer is set."""
        mock_dm = MagicMock()
        mock_analyzer = MagicMock()
        mock_analyzer.generate_text.return_value = "市场分析：当前处于上升趋势。"

        engine = MarketDiagnosticEngine(
            data_manager=mock_dm,
            analyzer=mock_analyzer,
            enable_llm_narrative=True,
        )
        index_data = {"sh000300": _make_index_data("sh000300")}
        engine.fetcher = _make_mock_fetcher(
            index_data=index_data,
            breadth_data=_make_breadth_data(),
        )

        _, markdown = engine.run(date="2024-01-15")
        mock_analyzer.generate_text.assert_called_once()
        assert "市场分析" in markdown

    def test_llm_narrative_skipped_when_disabled(self):
        """LLM analyzer should NOT be called when enable_llm_narrative=False."""
        mock_dm = MagicMock()
        mock_analyzer = MagicMock()

        engine = MarketDiagnosticEngine(
            data_manager=mock_dm,
            analyzer=mock_analyzer,
            enable_llm_narrative=False,
        )
        index_data = {"sh000300": _make_index_data("sh000300")}
        engine.fetcher = _make_mock_fetcher(index_data=index_data)

        engine.run(date="2024-01-15")
        mock_analyzer.generate_text.assert_not_called()

    def test_llm_narrative_skipped_when_no_analyzer(self):
        """LLM narrative should be skipped when analyzer is None."""
        mock_dm = MagicMock()
        engine = MarketDiagnosticEngine(
            data_manager=mock_dm,
            analyzer=None,
            enable_llm_narrative=True,
        )
        index_data = {"sh000300": _make_index_data("sh000300")}
        engine.fetcher = _make_mock_fetcher(index_data=index_data)

        # Should not raise
        report, markdown = engine.run(date="2024-01-15")
        assert isinstance(report, DiagnosticReport)

    def test_llm_failure_does_not_break_report(self):
        """LLM failure should not prevent report generation."""
        mock_dm = MagicMock()
        mock_analyzer = MagicMock()
        mock_analyzer.generate_text.side_effect = RuntimeError("LLM API error")

        engine = MarketDiagnosticEngine(
            data_manager=mock_dm,
            analyzer=mock_analyzer,
            enable_llm_narrative=True,
        )
        index_data = {"sh000300": _make_index_data("sh000300")}
        engine.fetcher = _make_mock_fetcher(
            index_data=index_data,
            breadth_data=_make_breadth_data(),
        )

        report, markdown = engine.run(date="2024-01-15")
        assert isinstance(report, DiagnosticReport)
        assert isinstance(markdown, str)
