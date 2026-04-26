"""
Integration Tests for MarketAnalyzer Extension

Task 12.2: Write integration tests for MarketAnalyzer extension

Tests:
- Diagnostic mode enabled vs disabled
- Fallback to existing review generation
- Integration with existing data fetchers
- Backward compatibility

Requirements: 21.1, 21.7, 21.8
"""

from __future__ import annotations

import sys
import os
from typing import Optional, Tuple
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

# ---------------------------------------------------------------------------
# Stub out optional third-party modules that may not be installed in the
# test environment (e.g. newspaper, tenacity) before importing MarketAnalyzer.
# ---------------------------------------------------------------------------
for _mod in ("newspaper", "tenacity"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# newspaper sub-modules used by search_service.py
for _sub in ("newspaper.Article", "newspaper.Config"):
    if _sub not in sys.modules:
        sys.modules[_sub] = MagicMock()

from src.market_analyzer import MarketAnalyzer, MarketOverview, MarketIndex


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------

def _make_mock_analyzer():
    """Create a mock LLM analyzer that returns a simple string."""
    analyzer = MagicMock()
    analyzer.is_available.return_value = True
    analyzer.generate_text.return_value = "## Mock LLM Review\nSome analysis text."
    return analyzer


def _make_mock_search_service():
    """Create a mock search service that returns empty results."""
    search_service = MagicMock()
    response = MagicMock()
    response.results = []
    search_service.search_stock_news.return_value = response
    return search_service


def _make_mock_data_manager():
    """Create a mock DataFetcherManager with minimal return values."""
    dm = MagicMock()
    dm.get_main_indices.return_value = [
        {
            "code": "sh000001",
            "name": "上证指数",
            "current": 3200.0,
            "change": 10.0,
            "change_pct": 0.31,
            "open": 3190.0,
            "high": 3210.0,
            "low": 3185.0,
            "prev_close": 3190.0,
            "volume": 1e9,
            "amount": 5e10,
            "amplitude": 0.78,
        }
    ]
    dm.get_market_stats.return_value = {
        "up_count": 2500,
        "down_count": 1800,
        "flat_count": 200,
        "limit_up_count": 80,
        "limit_down_count": 20,
        "total_amount": 8500.0,
    }
    dm.get_sector_rankings.return_value = (
        [{"name": "电子", "change_pct": 2.5}],
        [{"name": "银行", "change_pct": -1.2}],
    )
    return dm


def _make_mock_diagnostic_report():
    """Create a minimal mock DiagnosticReport."""
    report = MagicMock()
    report.date = "2024-01-15"
    report.composite_regime = "balanced_rotation"
    report.trend_state = "震荡"
    report.breadth_state = "中性"
    report.sentiment_state = "中性"
    report.style_state = "风格冲突"
    report.sector_state = "无主线"
    report.risk_state = "中性风险"
    report.confidence = 0.75
    report.missing_data = []
    return report


def _build_market_analyzer(
    enable_diagnostic: bool = False,
    analyzer=None,
    search_service=None,
    mock_data_manager=True,
) -> MarketAnalyzer:
    """
    Build a MarketAnalyzer with mocked dependencies to avoid real API calls.
    """
    with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
        mock_dm_cls.return_value = _make_mock_data_manager()
        ma = MarketAnalyzer(
            search_service=search_service or _make_mock_search_service(),
            analyzer=analyzer,
            region="cn",
            enable_diagnostic=enable_diagnostic,
        )
    return ma


# ---------------------------------------------------------------------------
# 1. Diagnostic Mode Enabled Tests (Req 21.7)
# ---------------------------------------------------------------------------

class TestDiagnosticModeEnabled:
    """
    Tests for MarketAnalyzer with enable_diagnostic=True.

    Validates Requirement 21.7: When MarketAnalyzer is initialized with
    enable_diagnostic=True, the System SHALL instantiate MarketDiagnosticEngine.
    """

    def test_diagnostic_engine_is_set_when_enabled(self):
        """
        MarketAnalyzer(enable_diagnostic=True) should have diagnostic_engine set.

        Req 21.7: When MarketAnalyzer is initialized with enable_diagnostic=True,
        THE System SHALL instantiate MarketDiagnosticEngine.
        """
        with patch("src.market_analyzer.DataFetcherManager"):
            with patch("src.market_diagnostic.engine.MarketDiagnosticEngine") as mock_engine_cls:
                mock_engine_cls.return_value = MagicMock()
                ma = MarketAnalyzer(enable_diagnostic=True)

        assert ma.diagnostic_engine is not None

    def test_diagnostic_engine_is_market_diagnostic_engine_instance(self):
        """
        diagnostic_engine should be an instance of MarketDiagnosticEngine.

        Req 21.7: The System SHALL instantiate MarketDiagnosticEngine.
        """
        with patch("src.market_analyzer.DataFetcherManager"):
            with patch("src.market_diagnostic.engine.MarketDiagnosticEngine") as mock_engine_cls:
                mock_instance = MagicMock()
                mock_engine_cls.return_value = mock_instance
                ma = MarketAnalyzer(enable_diagnostic=True)

        assert ma.diagnostic_engine is mock_instance

    def test_run_full_analysis_calls_diagnostic_engine_run(self):
        """
        run_full_analysis() with diagnostic enabled should call diagnostic_engine.run().

        Req 21.8: When MarketAnalyzer.run_full_analysis() is called with diagnostic
        enabled, THE System SHALL execute the full diagnostic workflow.
        """
        mock_report = _make_mock_diagnostic_report()
        mock_markdown = "## Diagnostic Report\nFull analysis."

        with patch("src.market_analyzer.DataFetcherManager"):
            with patch("src.market_diagnostic.engine.MarketDiagnosticEngine") as mock_engine_cls:
                mock_engine = MagicMock()
                mock_engine.run.return_value = (mock_report, mock_markdown)
                mock_engine_cls.return_value = mock_engine
                ma = MarketAnalyzer(enable_diagnostic=True)

        result = ma.run_full_analysis()

        mock_engine.run.assert_called_once()
        assert result == (mock_report, mock_markdown)

    def test_run_full_analysis_returns_diagnostic_report_tuple(self):
        """
        run_full_analysis() with diagnostic enabled should return (DiagnosticReport, str).

        Req 21.8: The System SHALL execute the full diagnostic workflow and return
        the Markdown report.
        """
        mock_report = _make_mock_diagnostic_report()
        mock_markdown = "## Diagnostic Report\nFull analysis."

        with patch("src.market_analyzer.DataFetcherManager"):
            with patch("src.market_diagnostic.engine.MarketDiagnosticEngine") as mock_engine_cls:
                mock_engine = MagicMock()
                mock_engine.run.return_value = (mock_report, mock_markdown)
                mock_engine_cls.return_value = mock_engine
                ma = MarketAnalyzer(enable_diagnostic=True)

        report, markdown = ma.run_full_analysis()

        assert report is mock_report
        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_run_full_analysis_first_element_is_not_none_in_diagnostic_mode(self):
        """
        In diagnostic mode, the first element of the tuple should not be None.

        Req 21.8: The System SHALL return a DiagnosticReport (not None) in diagnostic mode.
        """
        mock_report = _make_mock_diagnostic_report()

        with patch("src.market_analyzer.DataFetcherManager"):
            with patch("src.market_diagnostic.engine.MarketDiagnosticEngine") as mock_engine_cls:
                mock_engine = MagicMock()
                mock_engine.run.return_value = (mock_report, "## Report")
                mock_engine_cls.return_value = mock_engine
                ma = MarketAnalyzer(enable_diagnostic=True)

        report, _ = ma.run_full_analysis()

        assert report is not None

    def test_diagnostic_engine_receives_data_manager(self):
        """
        MarketDiagnosticEngine should be initialized with the data_manager.

        Req 21.1: The System SHALL reuse DataFetcherManager from base.py.
        """
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_instance = MagicMock()
            mock_dm_cls.return_value = mock_dm_instance

            with patch("src.market_diagnostic.engine.MarketDiagnosticEngine") as mock_engine_cls:
                mock_engine_cls.return_value = MagicMock()
                ma = MarketAnalyzer(enable_diagnostic=True)

        # Verify engine was called with data_manager keyword argument
        call_kwargs = mock_engine_cls.call_args.kwargs
        assert "data_manager" in call_kwargs
        assert call_kwargs["data_manager"] is mock_dm_instance

    def test_diagnostic_engine_receives_analyzer(self):
        """
        MarketDiagnosticEngine should be initialized with the analyzer.

        Req 21.6: WHERE LLM narrative generation is enabled, THE System SHALL
        call GeminiAnalyzer.generate_text().
        """
        mock_llm_analyzer = _make_mock_analyzer()

        with patch("src.market_analyzer.DataFetcherManager"):
            with patch("src.market_diagnostic.engine.MarketDiagnosticEngine") as mock_engine_cls:
                mock_engine_cls.return_value = MagicMock()
                ma = MarketAnalyzer(enable_diagnostic=True, analyzer=mock_llm_analyzer)

        call_kwargs = mock_engine_cls.call_args.kwargs
        assert "analyzer" in call_kwargs
        assert call_kwargs["analyzer"] is mock_llm_analyzer


# ---------------------------------------------------------------------------
# 2. Diagnostic Mode Disabled Tests (Req 21.8)
# ---------------------------------------------------------------------------

class TestDiagnosticModeDisabled:
    """
    Tests for MarketAnalyzer with enable_diagnostic=False (default).

    Validates Requirement 21.8: When diagnostic is disabled, the system
    should fall back to existing review generation.
    """

    def test_diagnostic_engine_is_none_when_disabled(self):
        """
        MarketAnalyzer(enable_diagnostic=False) should have diagnostic_engine = None.

        Req 21.8: When diagnostic is disabled, no engine should be instantiated.
        """
        with patch("src.market_analyzer.DataFetcherManager"):
            ma = MarketAnalyzer(enable_diagnostic=False)

        assert ma.diagnostic_engine is None

    def test_run_full_analysis_returns_none_report_when_disabled(self):
        """
        run_full_analysis() with diagnostic disabled should return (None, str).

        Req 21.8: Fallback returns None as the first element.
        """
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = _make_mock_data_manager()
            ma = MarketAnalyzer(
                enable_diagnostic=False,
                analyzer=_make_mock_analyzer(),
                search_service=_make_mock_search_service(),
            )

        report, markdown = ma.run_full_analysis()

        assert report is None

    def test_run_full_analysis_returns_string_markdown_when_disabled(self):
        """
        run_full_analysis() with diagnostic disabled should return a non-empty string.

        Req 21.8: Fallback returns a Markdown string as the second element.
        """
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = _make_mock_data_manager()
            ma = MarketAnalyzer(
                enable_diagnostic=False,
                analyzer=_make_mock_analyzer(),
                search_service=_make_mock_search_service(),
            )

        _, markdown = ma.run_full_analysis()

        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_run_full_analysis_calls_get_market_overview_when_disabled(self):
        """
        run_full_analysis() with diagnostic disabled should call get_market_overview().

        Req 21.8: Fallback uses existing review generation pipeline.
        """
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = _make_mock_data_manager()
            ma = MarketAnalyzer(
                enable_diagnostic=False,
                analyzer=_make_mock_analyzer(),
                search_service=_make_mock_search_service(),
            )

        with patch.object(ma, "get_market_overview", wraps=ma.get_market_overview) as mock_overview:
            with patch.object(ma, "generate_market_review", return_value="## Review") as mock_review:
                ma.run_full_analysis()

        mock_overview.assert_called_once()

    def test_run_full_analysis_calls_generate_market_review_when_disabled(self):
        """
        run_full_analysis() with diagnostic disabled should call generate_market_review().

        Req 21.8: Fallback uses existing review generation pipeline.
        """
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = _make_mock_data_manager()
            ma = MarketAnalyzer(
                enable_diagnostic=False,
                analyzer=_make_mock_analyzer(),
                search_service=_make_mock_search_service(),
            )

        with patch.object(ma, "get_market_overview", return_value=MarketOverview(date="2024-01-15")):
            with patch.object(ma, "search_market_news", return_value=[]):
                with patch.object(ma, "generate_market_review", return_value="## Review") as mock_review:
                    report, markdown = ma.run_full_analysis()

        mock_review.assert_called_once()
        assert report is None
        assert markdown == "## Review"

    def test_diagnostic_engine_not_instantiated_when_disabled(self):
        """
        MarketDiagnosticEngine should NOT be instantiated when enable_diagnostic=False.
        """
        with patch("src.market_analyzer.DataFetcherManager"):
            with patch("src.market_diagnostic.engine.MarketDiagnosticEngine") as mock_engine_cls:
                ma = MarketAnalyzer(enable_diagnostic=False)

        mock_engine_cls.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Backward Compatibility Tests
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """
    Tests that existing MarketAnalyzer functionality is not broken.

    Validates Requirement 21.1: The System SHALL reuse DataFetcherManager.
    """

    def test_default_initialization_works_without_enable_diagnostic(self):
        """
        MarketAnalyzer() without enable_diagnostic should work as before.

        Backward compatibility: default behavior unchanged.
        """
        with patch("src.market_analyzer.DataFetcherManager"):
            ma = MarketAnalyzer()

        assert ma is not None
        assert ma.diagnostic_engine is None

    def test_default_enable_diagnostic_is_false(self):
        """
        Default value of enable_diagnostic should be False.

        Backward compatibility: existing code not affected.
        """
        with patch("src.market_analyzer.DataFetcherManager"):
            ma = MarketAnalyzer()

        assert ma.diagnostic_engine is None

    def test_generate_market_review_still_works(self):
        """
        generate_market_review() should still work after the extension.

        Backward compatibility: existing method not broken.
        """
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = _make_mock_data_manager()
            ma = MarketAnalyzer(
                enable_diagnostic=False,
                analyzer=_make_mock_analyzer(),
            )

        overview = MarketOverview(date="2024-01-15")
        result = ma.generate_market_review(overview, [])

        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_market_overview_still_works(self):
        """
        get_market_overview() should still work after the extension.

        Backward compatibility: existing method not broken.
        """
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = _make_mock_data_manager()
            ma = MarketAnalyzer(enable_diagnostic=False)

        overview = ma.get_market_overview()

        assert isinstance(overview, MarketOverview)
        assert overview.date is not None

    def test_market_analyzer_has_data_manager_attribute(self):
        """
        MarketAnalyzer should still have data_manager attribute.

        Req 21.1: The System SHALL reuse DataFetcherManager from base.py.
        """
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm = MagicMock()
            mock_dm_cls.return_value = mock_dm
            ma = MarketAnalyzer()

        assert hasattr(ma, "data_manager")
        assert ma.data_manager is mock_dm

    def test_region_parameter_still_works(self):
        """
        region parameter should still work after the extension.

        Backward compatibility: existing parameters not broken.
        """
        with patch("src.market_analyzer.DataFetcherManager"):
            ma_cn = MarketAnalyzer(region="cn")
            ma_us = MarketAnalyzer(region="us")

        assert ma_cn.region == "cn"
        assert ma_us.region == "us"

    def test_search_service_parameter_still_works(self):
        """
        search_service parameter should still work after the extension.

        Backward compatibility: existing parameters not broken.
        """
        mock_ss = _make_mock_search_service()
        with patch("src.market_analyzer.DataFetcherManager"):
            ma = MarketAnalyzer(search_service=mock_ss)

        assert ma.search_service is mock_ss

    def test_analyzer_parameter_still_works(self):
        """
        analyzer parameter should still work after the extension.

        Backward compatibility: existing parameters not broken.
        """
        mock_llm = _make_mock_analyzer()
        with patch("src.market_analyzer.DataFetcherManager"):
            ma = MarketAnalyzer(analyzer=mock_llm)

        assert ma.analyzer is mock_llm


# ---------------------------------------------------------------------------
# 4. Integration with Existing Data Fetchers (Req 21.1)
# ---------------------------------------------------------------------------

class TestDataFetcherIntegration:
    """
    Tests that MarketAnalyzer integrates correctly with existing data fetchers.

    Validates Requirement 21.1: The System SHALL reuse DataFetcherManager.
    """

    def test_data_manager_is_instantiated_on_init(self):
        """
        DataFetcherManager should be instantiated during MarketAnalyzer.__init__().

        Req 21.1: The System SHALL reuse DataFetcherManager from base.py.
        """
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = MagicMock()
            ma = MarketAnalyzer()

        mock_dm_cls.assert_called_once()

    def test_diagnostic_engine_uses_same_data_manager_as_analyzer(self):
        """
        MarketDiagnosticEngine should use the same DataFetcherManager instance
        as the MarketAnalyzer.

        Req 21.1: The System SHALL reuse DataFetcherManager from base.py.
        """
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_instance = MagicMock()
            mock_dm_cls.return_value = mock_dm_instance

            with patch("src.market_diagnostic.engine.MarketDiagnosticEngine") as mock_engine_cls:
                mock_engine_cls.return_value = MagicMock()
                ma = MarketAnalyzer(enable_diagnostic=True)

        # The engine should have been initialized with the same data_manager
        call_kwargs = mock_engine_cls.call_args.kwargs
        assert call_kwargs.get("data_manager") is mock_dm_instance

    def test_run_full_analysis_fallback_uses_data_manager_for_indices(self):
        """
        In fallback mode, run_full_analysis() should use data_manager.get_main_indices().

        Req 21.2: The System SHALL call DataFetcherManager.get_main_indices().
        """
        mock_dm = _make_mock_data_manager()
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = mock_dm
            ma = MarketAnalyzer(
                enable_diagnostic=False,
                analyzer=_make_mock_analyzer(),
                search_service=_make_mock_search_service(),
            )

        ma.run_full_analysis()

        mock_dm.get_main_indices.assert_called()

    def test_run_full_analysis_fallback_uses_data_manager_for_market_stats(self):
        """
        In fallback mode, run_full_analysis() should use data_manager.get_market_stats().

        Req 21.3: The System SHALL call DataFetcherManager.get_market_stats().
        """
        mock_dm = _make_mock_data_manager()
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = mock_dm
            ma = MarketAnalyzer(
                enable_diagnostic=False,
                analyzer=_make_mock_analyzer(),
                search_service=_make_mock_search_service(),
            )

        ma.run_full_analysis()

        mock_dm.get_market_stats.assert_called()

    def test_run_full_analysis_fallback_uses_data_manager_for_sector_rankings(self):
        """
        In fallback mode, run_full_analysis() should use data_manager.get_sector_rankings().

        Req 21.4: The System SHALL call DataFetcherManager.get_sector_rankings().
        """
        mock_dm = _make_mock_data_manager()
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = mock_dm
            ma = MarketAnalyzer(
                enable_diagnostic=False,
                analyzer=_make_mock_analyzer(),
                search_service=_make_mock_search_service(),
            )

        ma.run_full_analysis()

        mock_dm.get_sector_rankings.assert_called()


# ---------------------------------------------------------------------------
# 5. Return Type Contract Tests
# ---------------------------------------------------------------------------

class TestReturnTypeContract:
    """
    Tests that run_full_analysis() always returns a (Optional[DiagnosticReport], str) tuple.
    """

    def test_return_type_is_tuple_in_diagnostic_mode(self):
        """run_full_analysis() must return a 2-tuple in diagnostic mode."""
        mock_report = _make_mock_diagnostic_report()

        with patch("src.market_analyzer.DataFetcherManager"):
            with patch("src.market_diagnostic.engine.MarketDiagnosticEngine") as mock_engine_cls:
                mock_engine = MagicMock()
                mock_engine.run.return_value = (mock_report, "## Report")
                mock_engine_cls.return_value = mock_engine
                ma = MarketAnalyzer(enable_diagnostic=True)

        result = ma.run_full_analysis()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_return_type_is_tuple_in_fallback_mode(self):
        """run_full_analysis() must return a 2-tuple in fallback mode."""
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = _make_mock_data_manager()
            ma = MarketAnalyzer(
                enable_diagnostic=False,
                analyzer=_make_mock_analyzer(),
                search_service=_make_mock_search_service(),
            )

        result = ma.run_full_analysis()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_second_element_is_string_in_diagnostic_mode(self):
        """Second element of run_full_analysis() must be a string in diagnostic mode."""
        mock_report = _make_mock_diagnostic_report()

        with patch("src.market_analyzer.DataFetcherManager"):
            with patch("src.market_diagnostic.engine.MarketDiagnosticEngine") as mock_engine_cls:
                mock_engine = MagicMock()
                mock_engine.run.return_value = (mock_report, "## Diagnostic Report")
                mock_engine_cls.return_value = mock_engine
                ma = MarketAnalyzer(enable_diagnostic=True)

        _, markdown = ma.run_full_analysis()

        assert isinstance(markdown, str)

    def test_second_element_is_string_in_fallback_mode(self):
        """Second element of run_full_analysis() must be a string in fallback mode."""
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = _make_mock_data_manager()
            ma = MarketAnalyzer(
                enable_diagnostic=False,
                analyzer=_make_mock_analyzer(),
                search_service=_make_mock_search_service(),
            )

        _, markdown = ma.run_full_analysis()

        assert isinstance(markdown, str)

    def test_first_element_is_none_in_fallback_mode(self):
        """First element of run_full_analysis() must be None in fallback mode."""
        with patch("src.market_analyzer.DataFetcherManager") as mock_dm_cls:
            mock_dm_cls.return_value = _make_mock_data_manager()
            ma = MarketAnalyzer(
                enable_diagnostic=False,
                analyzer=_make_mock_analyzer(),
                search_service=_make_mock_search_service(),
            )

        report, _ = ma.run_full_analysis()

        assert report is None

    def test_first_element_is_not_none_in_diagnostic_mode(self):
        """First element of run_full_analysis() must not be None in diagnostic mode."""
        mock_report = _make_mock_diagnostic_report()

        with patch("src.market_analyzer.DataFetcherManager"):
            with patch("src.market_diagnostic.engine.MarketDiagnosticEngine") as mock_engine_cls:
                mock_engine = MagicMock()
                mock_engine.run.return_value = (mock_report, "## Report")
                mock_engine_cls.return_value = mock_engine
                ma = MarketAnalyzer(enable_diagnostic=True)

        report, _ = ma.run_full_analysis()

        assert report is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
