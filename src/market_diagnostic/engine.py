"""
Market Diagnostic Engine

Main orchestrator for the complete diagnostic workflow.
Coordinates data fetching → feature calculation → state classification → report generation.

Requirements: 21.6, 22.1, 22.2, 22.5, 22.6, 22.7
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports to avoid circular dependencies and optional dependencies
# ---------------------------------------------------------------------------

try:
    from src.market_diagnostic.data.fetchers import DiagnosticDataFetcher
    from src.market_diagnostic.data.models import (
        IndexDailyData,
        MarketBreadthData,
        SectorDailyData,
        CapitalFlowData,
    )
    from src.market_diagnostic.features.trend import (
        TrendFeatures,
        compute_all_trend_features,
    )
    from src.market_diagnostic.features.breadth import (
        BreadthFeatures,
        compute_breadth_features,
    )
    from src.market_diagnostic.features.sentiment import (
        SentimentFeatures,
        compute_sentiment_features,
    )
    from src.market_diagnostic.features.style import (
        StyleFeatures,
        compute_style_features,
    )
    from src.market_diagnostic.features.sector import (
        SectorFeatureResult,
        compute_sector_features,
        compute_all_sector_features,
    )
    from src.market_diagnostic.features.capital import (
        CapitalFeatures,
        compute_capital_features,
    )
    from src.market_diagnostic.features.risk import (
        RiskFeatures,
        compute_risk_features,
    )
    from src.market_diagnostic.states.classifier import (
        MarketStateClassifier,
        MarketStateResult,
    )
    from src.market_diagnostic.reports.schema import DiagnosticReport
    from src.market_diagnostic.reports.markdown_renderer import DiagnosticMarkdownRenderer
    from src.market_diagnostic.config import PRIMARY_INDEX
except ImportError:
    from market_diagnostic.data.fetchers import DiagnosticDataFetcher  # type: ignore[no-redef]
    from market_diagnostic.data.models import (  # type: ignore[no-redef]
        IndexDailyData,
        MarketBreadthData,
        SectorDailyData,
        CapitalFlowData,
    )
    from market_diagnostic.features.trend import (  # type: ignore[no-redef]
        TrendFeatures,
        compute_all_trend_features,
    )
    from market_diagnostic.features.breadth import (  # type: ignore[no-redef]
        BreadthFeatures,
        compute_breadth_features,
    )
    from market_diagnostic.features.sentiment import (  # type: ignore[no-redef]
        SentimentFeatures,
        compute_sentiment_features,
    )
    from market_diagnostic.features.style import (  # type: ignore[no-redef]
        StyleFeatures,
        compute_style_features,
    )
    from market_diagnostic.features.sector import (  # type: ignore[no-redef]
        SectorFeatureResult,
        compute_sector_features,
        compute_all_sector_features,
    )
    from market_diagnostic.features.capital import (  # type: ignore[no-redef]
        CapitalFeatures,
        compute_capital_features,
    )
    from market_diagnostic.features.risk import (  # type: ignore[no-redef]
        RiskFeatures,
        compute_risk_features,
    )
    from market_diagnostic.states.classifier import (  # type: ignore[no-redef]
        MarketStateClassifier,
        MarketStateResult,
    )
    from market_diagnostic.reports.schema import DiagnosticReport  # type: ignore[no-redef]
    from market_diagnostic.reports.markdown_renderer import DiagnosticMarkdownRenderer  # type: ignore[no-redef]
    from market_diagnostic.config import PRIMARY_INDEX  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Helper: one-sentence summary
# ---------------------------------------------------------------------------

def generate_one_sentence_summary(state_result: MarketStateResult) -> str:
    """
    Generate a concise one-sentence market summary from a MarketStateResult.

    The summary combines the composite regime, trend state, breadth state,
    and confidence level into a human-readable Chinese sentence.

    Parameters
    ----------
    state_result : MarketStateResult
        The classified market state.

    Returns
    -------
    str
        A single-sentence summary in Chinese.
    """
    # Regime display names
    _regime_display: Dict[str, str] = {
        "trend_risk_on_growth": "趋势进攻-成长主导",
        "trend_risk_on_smallcap": "趋势进攻-小盘主导",
        "balanced_rotation": "均衡轮动",
        "defensive_dividend": "防守-红利",
        "high_volatility_warning": "高波动预警",
        "panic_bottoming": "恐慌探底",
        "broad_weakness_hold": "全面弱势-持币观望",
    }

    regime_str = (
        state_result.composite_regime.value
        if hasattr(state_result.composite_regime, "value")
        else str(state_result.composite_regime)
    )
    regime_display = _regime_display.get(regime_str, regime_str)

    trend_str = (
        state_result.trend_state.value
        if hasattr(state_result.trend_state, "value")
        else str(state_result.trend_state)
    )
    breadth_str = (
        state_result.breadth_state.value
        if hasattr(state_result.breadth_state, "value")
        else str(state_result.breadth_state)
    )
    sentiment_str = (
        state_result.sentiment_state.value
        if hasattr(state_result.sentiment_state, "value")
        else str(state_result.sentiment_state)
    )
    risk_str = (
        state_result.risk_state.value
        if hasattr(state_result.risk_state, "value")
        else str(state_result.risk_state)
    )

    confidence_pct = int(state_result.confidence * 100)

    # Build the summary sentence
    summary = (
        f"当前市场处于【{regime_display}】状态，"
        f"趋势{trend_str}，广度{breadth_str}，情绪{sentiment_str}，"
        f"风险{risk_str}，综合得分{state_result.regime_score:.1f}，"
        f"置信度{confidence_pct}%。"
    )

    # Append key evidence if available
    if state_result.key_evidence:
        summary += state_result.key_evidence[0]

    return summary


# ---------------------------------------------------------------------------
# Fallback feature constructors for graceful degradation
# ---------------------------------------------------------------------------

def _make_fallback_breadth_features() -> BreadthFeatures:
    """Return a neutral BreadthFeatures when breadth data is unavailable."""
    return BreadthFeatures(
        up_down_ratio=1.0,
        limit_up_rate=0.01,
        seal_rate=0.5,
        above_ma20_ratio=0.45,
        above_ma60_ratio=0.45,
        new_high_ratio=0.01,
        amount_deviation_5d=0.0,
        amount_deviation_20d=0.0,
        breadth_score=50.0,
    )


def _make_fallback_sentiment_features() -> SentimentFeatures:
    """Return a neutral SentimentFeatures when sentiment data is unavailable."""
    return SentimentFeatures(
        limit_up_down_ratio=1.0,
        continuous_limit_up=0,
        seal_rate=0.5,
        next_day_premium=0.0,
        turnover_zscore=0.0,
        sentiment_score=50.0,
    )


def _make_fallback_capital_features() -> CapitalFeatures:
    """Return a neutral CapitalFeatures when capital data is unavailable."""
    return CapitalFeatures(
        total_amount=0.0,
        amount_deviation_5d=0.0,
        amount_deviation_20d=0.0,
        amount_deviation_60d=0.0,
        north_net_flow=0.0,
        north_5d_avg=0.0,
        north_flow_trend="neutral",
        margin_balance=0.0,
        margin_delta=0.0,
        main_net_flow=0.0,
        etf_net_flow=0.0,
        data_freshness={},
        has_delayed_data=False,
    )


def _make_fallback_risk_features(index_data: Dict[str, IndexDailyData]) -> RiskFeatures:
    """Return a minimal RiskFeatures computed from available index data."""
    try:
        return compute_risk_features(index_data, sector_data=[])
    except Exception:
        return RiskFeatures(
            realized_volatility={},
            atr_volatility={},
            vol_ratio_short_long={},
            index_drawdown={},
            cross_index_correlation=0.0,
            sector_correlation_elevation=0.0,
            cvix_value=None,
            cvix_percentile=None,
            has_cvix_data=False,
        )


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class MarketDiagnosticEngine:
    """
    Orchestrates the complete market diagnostic workflow.

    Workflow:
        Step 1: Fetch data (index_series / breadth / sector / capital)
        Step 2: Calculate features (trend / breadth / sentiment / style / sector / capital / risk)
        Step 3: State classification (MarketStateClassifier.classify())
        Step 4: Build structured report (DiagnosticReport)
        Step 5: Render Markdown (optionally with LLM narrative)

    Requirements: 21.6, 22.1, 22.2, 22.5, 22.6, 22.7
    """

    def __init__(
        self,
        data_manager,
        analyzer=None,
        enable_llm_narrative: bool = True,
    ):
        """
        Initialize the diagnostic engine.

        Parameters
        ----------
        data_manager : DataFetcherManager
            Existing DataFetcherManager instance for data fetching.
        analyzer : optional
            LLM analyzer (e.g., GeminiAnalyzer) for narrative generation.
            If None, LLM narrative is skipped even if enable_llm_narrative=True.
        enable_llm_narrative : bool
            Whether to attempt LLM narrative generation (default True).
        """
        self.fetcher = DiagnosticDataFetcher(data_manager)
        self.classifier = MarketStateClassifier()
        self.renderer = DiagnosticMarkdownRenderer()
        self.analyzer = analyzer
        self.enable_llm_narrative = enable_llm_narrative

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, date: str = None) -> Tuple[DiagnosticReport, str]:
        """
        Execute the complete diagnostic workflow.

        Parameters
        ----------
        date : str, optional
            Target trading date in 'YYYY-MM-DD' format.
            Defaults to today's date.

        Returns
        -------
        Tuple[DiagnosticReport, str]
            (structured_report, markdown_string)

        Requirements: 22.1, 22.2, 22.5, 22.6, 22.7
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        ts = datetime.now().isoformat()
        logger.info(f"[{ts}] MarketDiagnosticEngine.run() started for date={date}")

        missing_data: List[str] = []

        # ----------------------------------------------------------------
        # Step 1: Fetch data
        # ----------------------------------------------------------------
        index_data, breadth_data, sector_data, capital_data = self._fetch_data(
            date, missing_data
        )

        # ----------------------------------------------------------------
        # Step 2: Calculate features
        # ----------------------------------------------------------------
        (
            trend_features,
            breadth_features,
            sentiment_features,
            style_features,
            sector_features,
            capital_features,
            risk_features,
        ) = self._compute_features(
            date,
            index_data,
            breadth_data,
            sector_data,
            capital_data,
            missing_data,
        )

        # ----------------------------------------------------------------
        # Step 3: State classification
        # ----------------------------------------------------------------
        state_result = self._classify_states(
            date,
            trend_features,
            breadth_features,
            sentiment_features,
            style_features,
            sector_features,
            capital_features,
            risk_features,
            missing_data,
        )

        # ----------------------------------------------------------------
        # Step 4: Build structured report
        # ----------------------------------------------------------------
        one_sentence = generate_one_sentence_summary(state_result)

        report = DiagnosticReport.from_state_result(
            state_result=state_result,
            trend_features=trend_features,
            breadth_features=breadth_features,
            sentiment_features=sentiment_features,
            style_features=style_features,
            sector_features=sector_features,
            capital_features=capital_features,
            risk_features=risk_features,
            index_data=index_data,
            one_sentence_summary=one_sentence,
        )

        # Req 22.6: Ensure missing_data is included in the report
        if missing_data:
            # Merge with any missing_data already in state_result
            all_missing = list(dict.fromkeys(missing_data + list(report.missing_data)))
            report.missing_data = all_missing

        # Req 22.5 / 22.7: Confidence already set by classifier; ensure it reflects
        # data completeness (already handled in _compute_confidence)

        # ----------------------------------------------------------------
        # Step 5: Render Markdown (optionally with LLM narrative)
        # ----------------------------------------------------------------
        llm_narrative = ""
        if self.enable_llm_narrative and self.analyzer is not None:
            llm_narrative = self._generate_llm_narrative(report)

        markdown_str = self.renderer.render(report, llm_narrative=llm_narrative)

        ts_end = datetime.now().isoformat()
        logger.info(
            f"[{ts_end}] MarketDiagnosticEngine.run() completed. "
            f"regime={report.composite_regime}, confidence={report.confidence:.2f}, "
            f"missing_data={len(report.missing_data)} items"
        )

        return report, markdown_str

    # ------------------------------------------------------------------
    # Step 1: Data fetching with error handling
    # ------------------------------------------------------------------

    def _fetch_data(
        self,
        date: str,
        missing_data: List[str],
    ) -> Tuple[
        Dict[str, IndexDailyData],
        Optional[MarketBreadthData],
        List[SectorDailyData],
        Optional[CapitalFlowData],
    ]:
        """
        Fetch all required data, logging errors and continuing on failure.

        Req 22.1: Log errors with timestamp and data source info.
        Req 22.2: Continue processing with available data when non-critical data is missing.
        """
        ts = datetime.now().isoformat()

        # --- Index series (critical) ---
        index_data: Dict[str, IndexDailyData] = {}
        try:
            index_data = self.fetcher.fetch_index_series(date=date)
            if not index_data:
                logger.warning(
                    f"[{ts}] [DataSource: index_series] No index data returned for {date}"
                )
                missing_data.append("index_data")
        except Exception as exc:
            logger.error(
                f"[{ts}] [DataSource: index_series] Failed to fetch index data for {date}: {exc}"
            )
            missing_data.append("index_data")

        # --- Breadth data (non-critical: can degrade gracefully) ---
        breadth_data: Optional[MarketBreadthData] = None
        try:
            breadth_data = self.fetcher.fetch_breadth_data(date=date)
            if breadth_data is None:
                logger.warning(
                    f"[{ts}] [DataSource: breadth_data] No breadth data returned for {date}"
                )
                missing_data.append("breadth_data")
        except Exception as exc:
            logger.error(
                f"[{ts}] [DataSource: breadth_data] Failed to fetch breadth data for {date}: {exc}"
            )
            missing_data.append("breadth_data")

        # --- Sector data (non-critical) ---
        sector_data: List[SectorDailyData] = []
        try:
            sector_data = self.fetcher.fetch_sector_data(date=date)
            if not sector_data:
                logger.warning(
                    f"[{ts}] [DataSource: sector_data] No sector data returned for {date}"
                )
                missing_data.append("sector_data")
        except Exception as exc:
            logger.error(
                f"[{ts}] [DataSource: sector_data] Failed to fetch sector data for {date}: {exc}"
            )
            missing_data.append("sector_data")

        # --- Capital flow data (non-critical, often T+1) ---
        capital_data: Optional[CapitalFlowData] = None
        try:
            capital_data = self.fetcher.fetch_capital_flow(date=date)
            if capital_data is None:
                logger.warning(
                    f"[{ts}] [DataSource: capital_data] No capital flow data returned for {date}"
                )
                missing_data.append("capital_data")
        except Exception as exc:
            logger.error(
                f"[{ts}] [DataSource: capital_data] Failed to fetch capital flow data for {date}: {exc}"
            )
            missing_data.append("capital_data")

        return index_data, breadth_data, sector_data, capital_data

    # ------------------------------------------------------------------
    # Step 2: Feature calculation with graceful degradation
    # ------------------------------------------------------------------

    def _compute_features(
        self,
        date: str,
        index_data: Dict[str, IndexDailyData],
        breadth_data: Optional[MarketBreadthData],
        sector_data: List[SectorDailyData],
        capital_data: Optional[CapitalFlowData],
        missing_data: List[str],
    ) -> Tuple[
        Dict[str, TrendFeatures],
        BreadthFeatures,
        SentimentFeatures,
        StyleFeatures,
        List[SectorFeatureResult],
        CapitalFeatures,
        RiskFeatures,
    ]:
        """
        Compute all feature layers, falling back to neutral defaults on failure.

        Req 22.2: Continue processing with available data.
        Req 22.4: Skip indicators with insufficient data and add to missing_data.
        """
        ts = datetime.now().isoformat()

        # --- Trend features ---
        trend_features: Dict[str, TrendFeatures] = {}
        if index_data:
            try:
                csi300_data = index_data.get(PRIMARY_INDEX) or next(iter(index_data.values()))
                trend_features = compute_all_trend_features(index_data, csi300_data)
            except Exception as exc:
                logger.error(
                    f"[{ts}] [Feature: trend] Failed to compute trend features: {exc}"
                )
                missing_data.append("trend_features")
        else:
            missing_data.append("trend_features")

        # --- Breadth features ---
        breadth_features: BreadthFeatures
        if breadth_data is not None:
            try:
                breadth_features = compute_breadth_features(breadth_data)
            except Exception as exc:
                logger.error(
                    f"[{ts}] [Feature: breadth] Failed to compute breadth features: {exc}"
                )
                breadth_features = _make_fallback_breadth_features()
                missing_data.append("breadth_features")
        else:
            logger.warning(
                f"[{ts}] [Feature: breadth] No breadth data available, using fallback"
            )
            breadth_features = _make_fallback_breadth_features()

        # --- Sentiment features ---
        sentiment_features: SentimentFeatures
        if breadth_data is not None:
            try:
                sentiment_features = compute_sentiment_features(breadth_data)
            except Exception as exc:
                logger.error(
                    f"[{ts}] [Feature: sentiment] Failed to compute sentiment features: {exc}"
                )
                sentiment_features = _make_fallback_sentiment_features()
                missing_data.append("sentiment_features")
        else:
            logger.warning(
                f"[{ts}] [Feature: sentiment] No breadth data available, using fallback"
            )
            sentiment_features = _make_fallback_sentiment_features()

        # --- Style features ---
        style_features: Optional[StyleFeatures] = None
        if index_data:
            try:
                style_features = compute_style_features(index_data)
            except Exception as exc:
                logger.error(
                    f"[{ts}] [Feature: style] Failed to compute style features: {exc}"
                )
                missing_data.append("style_features")
        else:
            missing_data.append("style_features")

        if style_features is None:
            # Fallback: neutral style
            style_features = StyleFeatures(
                rs_large_vs_small=1.0,
                rs_300_vs_1000=1.0,
                rs_500_vs_1000=1.0,
                ret_1d={},
                ret_5d={},
                ret_20d={},
                amount_share={},
                dominant_style="风格冲突",
            )

        # --- Sector features ---
        sector_features: List[SectorFeatureResult] = []
        if sector_data:
            try:
                sector_features = compute_all_sector_features(sector_data, max_workers=4)
            except Exception as exc:
                logger.error(
                    f"[{ts}] [Feature: sector] Failed to compute sector features: {exc}"
                )
                missing_data.append("sector_features")

        # --- Capital features ---
        capital_features: CapitalFeatures
        if capital_data is not None and breadth_data is not None:
            try:
                capital_features = compute_capital_features(capital_data, breadth_data)
            except Exception as exc:
                logger.error(
                    f"[{ts}] [Feature: capital] Failed to compute capital features: {exc}"
                )
                capital_features = _make_fallback_capital_features()
                missing_data.append("capital_features")
        elif capital_data is not None:
            # breadth_data is None; create a minimal placeholder
            try:
                placeholder_breadth = MarketBreadthData(
                    date=date,
                    up_count=0, down_count=0, flat_count=0,
                    limit_up_count=0, limit_down_count=0, explode_count=0,
                    seal_rate=0.0, continuous_limit_up=0,
                    above_ma20_ratio=0.45, above_ma60_ratio=0.45,
                    new_high_count=0, new_low_count=0,
                    total_amount=capital_data.north_net_flow,  # rough proxy
                    amount_ma5=0.0, amount_ma20=0.0,
                )
                capital_features = compute_capital_features(capital_data, placeholder_breadth)
            except Exception as exc:
                logger.error(
                    f"[{ts}] [Feature: capital] Failed to compute capital features (no breadth): {exc}"
                )
                capital_features = _make_fallback_capital_features()
                missing_data.append("capital_features")
        else:
            logger.warning(
                f"[{ts}] [Feature: capital] No capital data available, using fallback"
            )
            capital_features = _make_fallback_capital_features()

        # --- Risk features ---
        risk_features: RiskFeatures
        if index_data:
            try:
                risk_features = compute_risk_features(index_data, sector_data)
            except Exception as exc:
                logger.error(
                    f"[{ts}] [Feature: risk] Failed to compute risk features: {exc}"
                )
                risk_features = _make_fallback_risk_features(index_data)
                missing_data.append("risk_features")
        else:
            logger.warning(
                f"[{ts}] [Feature: risk] No index data available, using fallback"
            )
            risk_features = _make_fallback_risk_features({})

        return (
            trend_features,
            breadth_features,
            sentiment_features,
            style_features,
            sector_features,
            capital_features,
            risk_features,
        )

    # ------------------------------------------------------------------
    # Step 3: State classification
    # ------------------------------------------------------------------

    def _classify_states(
        self,
        date: str,
        trend_features: Dict[str, TrendFeatures],
        breadth_features: BreadthFeatures,
        sentiment_features: SentimentFeatures,
        style_features: StyleFeatures,
        sector_features: List[SectorFeatureResult],
        capital_features: CapitalFeatures,
        risk_features: RiskFeatures,
        missing_data: List[str],
    ) -> MarketStateResult:
        """
        Run the MarketStateClassifier with all computed features.

        Req 22.5: Confidence score reflects data completeness.
        """
        ts = datetime.now().isoformat()
        try:
            return self.classifier.classify(
                trend_features=trend_features,
                breadth_features=breadth_features,
                sentiment_features=sentiment_features,
                style_features=style_features,
                sector_features=sector_features,
                capital_features=capital_features,
                risk_features=risk_features,
                date=date,
                missing_data=missing_data,
            )
        except Exception as exc:
            logger.error(
                f"[{ts}] [Classifier] State classification failed: {exc}. "
                "Returning default BALANCED_ROTATION state."
            )
            # Return a minimal default state so the engine can still produce output
            return self._make_default_state_result(date, missing_data)

    def _make_default_state_result(
        self, date: str, missing_data: List[str]
    ) -> MarketStateResult:
        """Return a safe default MarketStateResult when classification fails."""
        try:
            from src.market_diagnostic.states.enums import (
                TrendState, BreadthState, SentimentState, StyleState,
                SectorState, RiskState, CompositeRegime,
            )
        except ImportError:
            from market_diagnostic.states.enums import (  # type: ignore[no-redef]
                TrendState, BreadthState, SentimentState, StyleState,
                SectorState, RiskState, CompositeRegime,
            )

        return MarketStateResult(
            date=date,
            trend_state=TrendState.RANGING,
            breadth_state=BreadthState.NEUTRAL,
            sentiment_state=SentimentState.NEUTRAL,
            style_state=StyleState.STYLE_CONFLICT,
            sector_state=SectorState.NO_THEME,
            risk_state=RiskState.NEUTRAL,
            composite_regime=CompositeRegime.BALANCED_ROTATION,
            trend_score=50.0,
            breadth_score=50.0,
            sentiment_score=50.0,
            style_score=50.0,
            sector_score=50.0,
            risk_score=50.0,
            regime_score=50.0,
            key_evidence=["分类失败，使用默认状态"],
            counter_evidence=[],
            confidence=max(0.1, 0.5 - 0.15 * len(missing_data)),
            risk_flags=[],
            missing_data=list(missing_data),
        )

    # ------------------------------------------------------------------
    # Step 5 (optional): LLM narrative generation
    # ------------------------------------------------------------------

    def _generate_llm_narrative(self, report: DiagnosticReport) -> str:
        """
        Generate an LLM narrative using the analyzer (Req 21.6).

        Returns empty string on failure so the report is still usable.
        """
        ts = datetime.now().isoformat()
        try:
            prompt = self._build_llm_prompt(report)
            narrative = self.analyzer.generate_text(prompt)
            return narrative or ""
        except Exception as exc:
            logger.warning(
                f"[{ts}] [LLM] Narrative generation failed (non-critical): {exc}"
            )
            return ""

    def _build_llm_prompt(self, report: DiagnosticReport) -> str:
        """Build a concise prompt for LLM narrative generation."""
        return (
            f"请根据以下市场诊断数据，用200字以内写一段专业的市场复盘分析：\n\n"
            f"日期：{report.date}\n"
            f"综合状态：{report.composite_regime}\n"
            f"趋势：{report.trend_state}（得分{report.trend_score:.0f}）\n"
            f"广度：{report.breadth_state}（得分{report.breadth_score:.0f}）\n"
            f"情绪：{report.sentiment_state}（得分{report.sentiment_score:.0f}）\n"
            f"风险：{report.risk_state}（得分{report.risk_score:.0f}）\n"
            f"置信度：{report.confidence:.0%}\n"
            f"关键证据：{'; '.join(report.key_evidence[:2])}\n"
            f"风险标志：{', '.join(report.risk_flags) if report.risk_flags else '无'}\n\n"
            "请给出简洁、专业的市场分析，包括当前市场特征和操作建议。"
        )
