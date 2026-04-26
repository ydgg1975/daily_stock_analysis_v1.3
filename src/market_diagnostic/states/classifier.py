"""
Market State Classifier

Classifies market conditions across all dimensions and synthesizes a composite regime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    from src.market_diagnostic.states.enums import (
        TrendState, BreadthState, SentimentState, StyleState,
        SectorState, RiskState, CompositeRegime,
    )
    from src.market_diagnostic.features.trend import TrendFeatures
    from src.market_diagnostic.features.breadth import BreadthFeatures
    from src.market_diagnostic.features.sentiment import SentimentFeatures
    from src.market_diagnostic.features.style import StyleFeatures
    from src.market_diagnostic.features.sector import SectorFeatureResult
    from src.market_diagnostic.features.capital import CapitalFeatures
    from src.market_diagnostic.features.risk import RiskFeatures
except ImportError:
    from market_diagnostic.states.enums import (  # type: ignore[no-redef]
        TrendState, BreadthState, SentimentState, StyleState,
        SectorState, RiskState, CompositeRegime,
    )
    from market_diagnostic.features.trend import TrendFeatures  # type: ignore[no-redef]
    from market_diagnostic.features.breadth import BreadthFeatures  # type: ignore[no-redef]
    from market_diagnostic.features.sentiment import SentimentFeatures  # type: ignore[no-redef]
    from market_diagnostic.features.style import StyleFeatures  # type: ignore[no-redef]
    from market_diagnostic.features.sector import SectorFeatureResult  # type: ignore[no-redef]
    from market_diagnostic.features.capital import CapitalFeatures  # type: ignore[no-redef]
    from market_diagnostic.features.risk import RiskFeatures  # type: ignore[no-redef]


@dataclass
class MarketStateResult:
    """Complete market state classification result."""

    date: str
    trend_state: TrendState
    breadth_state: BreadthState
    sentiment_state: SentimentState
    style_state: StyleState
    sector_state: SectorState
    risk_state: RiskState
    composite_regime: CompositeRegime

    # Dimension scores (0-100)
    trend_score: float
    breadth_score: float
    sentiment_score: float
    style_score: float
    sector_score: float
    risk_score: float

    # Composite regime score
    # 0.20*trend + 0.15*breadth + 0.15*sentiment + 0.15*style + 0.15*sector - 0.20*risk
    regime_score: float

    # Evidence
    key_evidence: List[str] = field(default_factory=list)      # 3 key supporting items
    counter_evidence: List[str] = field(default_factory=list)

    # Reliability
    confidence: float = 1.0   # [0.1, 1.0]
    risk_flags: List[str] = field(default_factory=list)
    missing_data: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CSI300_CODE = "sh000300"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class MarketStateClassifier:
    """
    Classifies market state across all dimensions and synthesizes a composite regime.

    Requirements: 9.1-9.6, 10.1-10.6, 11.1-11.6, 12.1-12.5, 13.1-13.5,
                  14.1-14.10, 15.1-15.8, 16.1-16.5, 17.1-17.7
    """

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def classify(
        self,
        trend_features: Dict[str, TrendFeatures],
        breadth_features: BreadthFeatures,
        sentiment_features: SentimentFeatures,
        style_features: StyleFeatures,
        sector_features: List[SectorFeatureResult],
        capital_features: CapitalFeatures,
        risk_features: RiskFeatures,
        date: str = "",
        missing_data: Optional[List[str]] = None,
    ) -> MarketStateResult:
        """
        Orchestrate all sub-classifiers and return a complete MarketStateResult.

        Requirements: 9.1-9.6, 10.1-10.6, 11.1-11.6, 12.1-12.5, 13.1-13.5,
                      14.1-14.10, 15.1-15.8, 17.1-17.7
        """
        if missing_data is None:
            missing_data = []

        # --- Sub-state classification ---
        trend_state = self._classify_trend(trend_features)
        breadth_state = self._classify_breadth(breadth_features)
        sentiment_state = self._classify_sentiment(sentiment_features)
        style_state = self._classify_style(style_features)
        sector_state = self._classify_sector(sector_features)
        risk_state, risk_flags = self._classify_risk(
            risk_features, breadth_features, sector_features, capital_features
        )

        # --- Dimension scores ---
        trend_score = self._score_trend(trend_state)
        breadth_score = self._score_breadth(breadth_state, breadth_features)
        sentiment_score = self._score_sentiment(sentiment_state, sentiment_features)
        style_score = self._score_style(style_state)
        sector_score = self._score_sector(sector_state, sector_features)
        risk_score = self._score_risk(risk_state)

        # --- Composite regime ---
        composite_regime = self._classify_composite(
            trend_state, breadth_state, sentiment_state,
            style_state, sector_state, risk_state,
        )

        # --- Regime score (Req 15.8) ---
        regime_score = (
            0.20 * trend_score
            + 0.15 * breadth_score
            + 0.15 * sentiment_score
            + 0.15 * style_score
            + 0.15 * sector_score
            - 0.20 * risk_score
        )
        regime_score = _clamp(regime_score, 0.0, 100.0)

        # --- Evidence ---
        key_evidence, counter_evidence = self._extract_evidence(
            trend_state, breadth_state, sentiment_state,
            style_state, sector_state, risk_state,
            trend_features, breadth_features, sentiment_features,
            style_features, sector_features, capital_features, risk_features,
        )

        # --- Confidence ---
        all_states = [trend_state, breadth_state, sentiment_state,
                      style_state, sector_state, risk_state]
        confidence = self._compute_confidence(
            missing_data, all_states,
            trend_features, breadth_features, sentiment_features,
            capital_features, risk_features,
        )

        return MarketStateResult(
            date=date,
            trend_state=trend_state,
            breadth_state=breadth_state,
            sentiment_state=sentiment_state,
            style_state=style_state,
            sector_state=sector_state,
            risk_state=risk_state,
            composite_regime=composite_regime,
            trend_score=trend_score,
            breadth_score=breadth_score,
            sentiment_score=sentiment_score,
            style_score=style_score,
            sector_score=sector_score,
            risk_score=risk_score,
            regime_score=regime_score,
            key_evidence=key_evidence,
            counter_evidence=counter_evidence,
            confidence=confidence,
            risk_flags=risk_flags,
            missing_data=missing_data,
        )

    # ------------------------------------------------------------------
    # Trend classification  (Req 9.1-9.5)
    # ------------------------------------------------------------------

    def _classify_trend(self, features: Dict[str, TrendFeatures]) -> TrendState:
        """
        Based on sh000300 (CSI300).

        9.1 强趋势上行: MA5>MA10>MA20>MA60 AND MACD golden cross AND RSRS>0.7
        9.2 趋势上行中的回调: bullish MA alignment BUT MA5<MA10 AND MA20 rising
        9.3 震荡: tangled MAs AND MACD near zero
        9.4 趋势转弱: MA5<MA10<MA20 OR MACD death cross
        9.5 破位下行: price breaking below MA60 AND RSRS<0.3
        """
        # Try to get CSI300 features; fall back to first available
        tf = features.get(_CSI300_CODE) or features.get("000300")
        if tf is None and features:
            tf = next(iter(features.values()))
        if tf is None:
            return TrendState.RANGING

        import math

        def _valid(v: float) -> bool:
            return not math.isnan(v)

        ma5, ma10, ma20, ma60 = tf.ma5, tf.ma10, tf.ma20, tf.ma60

        # Req 9.5: Breakdown — highest priority
        if tf.break_support and _valid(ma60) and tf.rsrs_score < 0.3:
            return TrendState.BREAKDOWN

        # Req 9.1: Strong uptrend
        if (
            _valid(ma5) and _valid(ma10) and _valid(ma20) and _valid(ma60)
            and ma5 > ma10 > ma20 > ma60
            and tf.macd_signal == "金叉"
            and tf.rsrs_score > 0.7
        ):
            return TrendState.STRONG_UP

        # Req 9.4: Weakening — MA5<MA10<MA20 OR death cross
        if (
            (_valid(ma5) and _valid(ma10) and _valid(ma20) and ma5 < ma10 < ma20)
            or tf.macd_signal == "死叉"
        ):
            return TrendState.WEAKENING

        # Req 9.2: Pullback in uptrend — bullish alignment but MA5<MA10
        if (
            tf.ma_alignment == "多头排列"
            and _valid(ma5) and _valid(ma10)
            and ma5 < ma10
        ):
            return TrendState.PULLBACK_IN_UPTREND

        # Req 9.3: Ranging — tangled MAs and MACD near zero
        if tf.ma_alignment == "缠绕" and abs(tf.macd_bar) < 0.01:
            return TrendState.RANGING

        # Default: ranging
        return TrendState.RANGING

    # ------------------------------------------------------------------
    # Breadth classification  (Req 10.1-10.5)
    # ------------------------------------------------------------------

    def _classify_breadth(self, f: BreadthFeatures) -> BreadthState:
        """Threshold-based classification on above_ma20_ratio."""
        r = f.above_ma20_ratio
        if r < 0.20:
            return BreadthState.EXTREME_WEAK
        if r < 0.35:
            return BreadthState.WEAK
        if r < 0.55:
            return BreadthState.NEUTRAL
        if r < 0.70:
            return BreadthState.STRONG
        return BreadthState.OVERHEATED

    # ------------------------------------------------------------------
    # Sentiment classification  (Req 11.1-11.5)
    # ------------------------------------------------------------------

    def _classify_sentiment(self, f: SentimentFeatures) -> SentimentState:
        """
        11.1 冰点: very low limit-up rate, high limit-down, low seal rate
        11.2 回暖: recovering limit-up rate, improving seal rate
        11.3 中性: moderate values
        11.4 活跃: high limit-up, high seal rate, positive next-day premium
        11.5 狂热: extreme limit-up, very high seal rate, strong continuous limit-ups
        """
        score = f.sentiment_score  # 0-100

        # Use composite score as primary signal, supplemented by individual indicators
        if score >= 80 or (f.limit_up_down_ratio >= 5.0 and f.seal_rate >= 0.85
                           and f.continuous_limit_up >= 20):
            return SentimentState.EUPHORIC

        if score >= 60 or (f.limit_up_down_ratio >= 2.5 and f.seal_rate >= 0.70
                           and f.next_day_premium > 0):
            return SentimentState.ACTIVE

        if score >= 40 or (f.limit_up_down_ratio >= 1.0 and f.seal_rate >= 0.50):
            return SentimentState.NEUTRAL

        if score >= 20 or (f.limit_up_down_ratio >= 0.5 and f.seal_rate >= 0.30):
            return SentimentState.WARMING

        return SentimentState.FROZEN

    # ------------------------------------------------------------------
    # Style classification  (Req 12.1-12.5)
    # ------------------------------------------------------------------

    def _classify_style(self, f: StyleFeatures) -> StyleState:
        """Map dominant_style string to StyleState enum."""
        mapping = {
            "大盘防守": StyleState.LARGE_CAP_DEFENSIVE,
            "小盘进攻": StyleState.SMALL_CAP_OFFENSIVE,
            "成长主导": StyleState.GROWTH_DOMINANT,
            "红利防守": StyleState.DIVIDEND_DEFENSIVE,
            "风格冲突": StyleState.STYLE_CONFLICT,
        }
        return mapping.get(f.dominant_style, StyleState.STYLE_CONFLICT)

    # ------------------------------------------------------------------
    # Sector classification  (Req 13.1-13.5)
    # ------------------------------------------------------------------

    def _classify_sector(self, sectors: List[SectorFeatureResult]) -> SectorState:
        """
        13.1 无主线: no sector with strength_score > 1.5
        13.2 单主线: exactly one sector with strength > 2.0 AND persistence > 0.7
        13.3 双主线并行: two sectors with strength > 1.8 AND persistence > 0.6
        13.4 高速轮动: top-5 rankings changing significantly (proxy: many sectors 1.5-2.0)
        13.5 退潮分化: declining strength across previously strong sectors
        """
        if not sectors:
            return SectorState.NO_THEME

        strong_single = [s for s in sectors if s.strength_score > 2.0 and s.persistence_score > 0.7]
        dual_candidates = [s for s in sectors if s.strength_score > 1.8 and s.persistence_score > 0.6]
        above_threshold = [s for s in sectors if s.strength_score > 1.5]

        # 13.2 Single theme
        if len(strong_single) == 1:
            return SectorState.SINGLE_THEME

        # 13.3 Dual theme
        if len(dual_candidates) >= 2:
            return SectorState.DUAL_THEME

        # 13.1 No theme
        if not above_threshold:
            return SectorState.NO_THEME

        # 13.5 Fading: many sectors above threshold but none dominant
        # Proxy: sectors with state "弱势退潮" outnumber strong ones
        fading_count = sum(1 for s in sectors if s.state == "弱势退潮")
        if fading_count > len(sectors) * 0.4:
            return SectorState.FADING

        # 13.4 Fast rotation: multiple sectors in moderate range without persistence
        moderate = [s for s in sectors if 1.5 < s.strength_score <= 2.0]
        if len(moderate) >= 3:
            return SectorState.FAST_ROTATION

        return SectorState.NO_THEME

    # ------------------------------------------------------------------
    # Risk classification  (Req 14.1-14.10)
    # ------------------------------------------------------------------

    def _classify_risk(
        self,
        risk_features: RiskFeatures,
        breadth_features: BreadthFeatures,
        sector_features: List[SectorFeatureResult],
        capital_features: CapitalFeatures,
    ) -> tuple[RiskState, List[str]]:
        """
        Returns (RiskState, risk_flags).

        Risk flags (Req 14.5-14.10):
        - vol_spike: realized vol > 2x historical mean (proxy: vol_ratio > 2.0)
        - breadth_collapse: above_ma20_ratio < 0.15
        - sector_overcrowding: top sector amount_share > 0.25
        - northbound_outflow: north_5d_avg < -10
        - leadership_breakdown: top sectors' leadership_score is low
        - index_break_support: sh000300 breaks below MA60
        """
        flags: List[str] = []

        # Req 14.5: vol_spike — short/long vol ratio > 2.0 for CSI300
        csi300_vol_ratio = risk_features.vol_ratio_short_long.get(
            _CSI300_CODE,
            risk_features.vol_ratio_short_long.get("000300", 1.0)
        )
        if csi300_vol_ratio > 2.0:
            flags.append("vol_spike")

        # Req 14.6: breadth_collapse
        if breadth_features.above_ma20_ratio < 0.15:
            flags.append("breadth_collapse")

        # Req 14.7: sector_overcrowding
        if sector_features:
            max_share = max((s.crowding_score for s in sector_features), default=0.0)
            # crowding_score is a Z-score; use raw amount_share if available
            # Fallback: check if any sector has high crowding Z-score (>2.0 ≈ top 2.5%)
            top_amount_shares = [
                getattr(s, "amount_share", None) for s in sector_features
            ]
            raw_shares = [v for v in top_amount_shares if v is not None]
            if raw_shares and max(raw_shares) > 0.25:
                flags.append("sector_overcrowding")
            elif not raw_shares and max_share > 2.0:
                flags.append("sector_overcrowding")

        # Req 14.8: northbound_outflow — north_5d_avg < -10 (亿元)
        if capital_features.north_5d_avg < -10.0:
            flags.append("northbound_outflow")

        # Req 14.9: leadership_breakdown — top sectors have low leadership scores
        if sector_features:
            top5 = sorted(sector_features, key=lambda s: s.strength_score, reverse=True)[:5]
            avg_leadership = sum(s.leadership_score for s in top5) / len(top5)
            if avg_leadership < -0.5:  # Below average leadership
                flags.append("leadership_breakdown")

        # Req 14.10: index_break_support — CSI300 below MA60
        csi300_drawdown = risk_features.index_drawdown.get(
            _CSI300_CODE,
            risk_features.index_drawdown.get("000300", 0.0)
        )
        # break_support is encoded in drawdown being significantly negative
        # Use drawdown < -5% as proxy for breaking MA60 support
        if csi300_drawdown < -5.0:
            flags.append("index_break_support")

        # Classify risk state based on volatility, drawdown, and flag count
        n_flags = len(flags)
        csi300_vol = risk_features.realized_volatility.get(
            _CSI300_CODE,
            risk_features.realized_volatility.get("000300", 0.0)
        )
        csi300_dd = abs(csi300_drawdown)

        # Req 14.4: Extreme risk
        if n_flags >= 3 or csi300_vol > 0.40 or csi300_dd > 20.0:
            return RiskState.EXTREME, flags

        # Req 14.3: High risk
        if n_flags >= 1 or csi300_vol > 0.25 or csi300_dd > 10.0:
            return RiskState.HIGH, flags

        # Req 14.2: Neutral risk
        if csi300_vol > 0.15 or csi300_dd > 5.0:
            return RiskState.NEUTRAL, flags

        # Req 14.1: Low risk
        return RiskState.LOW, flags

    # ------------------------------------------------------------------
    # Composite regime  (Req 15.1-15.7)
    # ------------------------------------------------------------------

    def _classify_composite(
        self,
        trend: TrendState,
        breadth: BreadthState,
        sentiment: SentimentState,
        style: StyleState,
        sector: SectorState,
        risk: RiskState,
    ) -> CompositeRegime:
        """
        Priority-ordered mapping rules:
        1. risk==EXTREME → HIGH_VOL_WARNING
        2. breadth==EXTREME_WEAK and sentiment==FROZEN → PANIC_BOTTOMING
        3. trend in (BREAKDOWN, WEAKENING) and breadth in (EXTREME_WEAK, WEAK) → BROAD_WEAKNESS_HOLD
        4. trend==STRONG_UP and style==GROWTH_DOMINANT → TREND_RISK_ON_GROWTH
        5. trend==STRONG_UP and style==SMALL_CAP_OFFENSIVE → TREND_RISK_ON_SMALLCAP
        6. style==DIVIDEND_DEFENSIVE → DEFENSIVE_DIVIDEND
        7. default → BALANCED_ROTATION
        """
        # 1
        if risk == RiskState.EXTREME:
            return CompositeRegime.HIGH_VOL_WARNING

        # 2
        if breadth == BreadthState.EXTREME_WEAK and sentiment == SentimentState.FROZEN:
            return CompositeRegime.PANIC_BOTTOMING

        # 3
        if (trend in (TrendState.BREAKDOWN, TrendState.WEAKENING)
                and breadth in (BreadthState.EXTREME_WEAK, BreadthState.WEAK)):
            return CompositeRegime.BROAD_WEAKNESS_HOLD

        # 4
        if trend == TrendState.STRONG_UP and style == StyleState.GROWTH_DOMINANT:
            return CompositeRegime.TREND_RISK_ON_GROWTH

        # 5
        if trend == TrendState.STRONG_UP and style == StyleState.SMALL_CAP_OFFENSIVE:
            return CompositeRegime.TREND_RISK_ON_SMALLCAP

        # 6
        if style == StyleState.DIVIDEND_DEFENSIVE:
            return CompositeRegime.DEFENSIVE_DIVIDEND

        # 7
        return CompositeRegime.BALANCED_ROTATION

    # ------------------------------------------------------------------
    # Dimension scores
    # ------------------------------------------------------------------

    def _score_trend(self, state: TrendState) -> float:
        """Map trend state to 0-100 score (Req 9.6)."""
        mapping = {
            TrendState.STRONG_UP: 90.0,
            TrendState.PULLBACK_IN_UPTREND: 65.0,
            TrendState.RANGING: 50.0,
            TrendState.WEAKENING: 30.0,
            TrendState.BREAKDOWN: 10.0,
        }
        return mapping.get(state, 50.0)

    def _score_breadth(self, state: BreadthState, f: BreadthFeatures) -> float:
        """Map breadth state to 0-100 score (Req 10.6)."""
        # Use the composite breadth_score from features as primary signal
        return _clamp(f.breadth_score, 0.0, 100.0)

    def _score_sentiment(self, state: SentimentState, f: SentimentFeatures) -> float:
        """Map sentiment state to 0-100 score (Req 11.6)."""
        return _clamp(f.sentiment_score, 0.0, 100.0)

    def _score_style(self, state: StyleState) -> float:
        """Map style state to 0-100 score."""
        mapping = {
            StyleState.GROWTH_DOMINANT: 80.0,
            StyleState.SMALL_CAP_OFFENSIVE: 75.0,
            StyleState.STYLE_CONFLICT: 50.0,
            StyleState.LARGE_CAP_DEFENSIVE: 40.0,
            StyleState.DIVIDEND_DEFENSIVE: 35.0,
        }
        return mapping.get(state, 50.0)

    def _score_sector(self, state: SectorState, sectors: List[SectorFeatureResult]) -> float:
        """Map sector state to 0-100 score."""
        mapping = {
            SectorState.SINGLE_THEME: 80.0,
            SectorState.DUAL_THEME: 70.0,
            SectorState.FAST_ROTATION: 55.0,
            SectorState.NO_THEME: 40.0,
            SectorState.FADING: 25.0,
        }
        return mapping.get(state, 50.0)

    def _score_risk(self, state: RiskState) -> float:
        """Map risk state to 0-100 score (higher = more risk)."""
        mapping = {
            RiskState.LOW: 10.0,
            RiskState.NEUTRAL: 35.0,
            RiskState.HIGH: 65.0,
            RiskState.EXTREME: 90.0,
        }
        return mapping.get(state, 35.0)

    # ------------------------------------------------------------------
    # Evidence extraction  (Req 17.1-17.2)
    # ------------------------------------------------------------------

    def _extract_evidence(
        self,
        trend: TrendState,
        breadth: BreadthState,
        sentiment: SentimentState,
        style: StyleState,
        sector: SectorState,
        risk: RiskState,
        trend_features: Dict[str, TrendFeatures],
        breadth_features: BreadthFeatures,
        sentiment_features: SentimentFeatures,
        style_features: StyleFeatures,
        sector_features: List[SectorFeatureResult],
        capital_features: CapitalFeatures,
        risk_features: RiskFeatures,
    ) -> tuple[List[str], List[str]]:
        """
        Extract 3 key supporting evidence items and counter-evidence.
        Req 17.1: 3 most important supporting evidence items
        Req 17.2: counter-evidence that contradicts the main conclusion
        """
        key_evidence: List[str] = []
        counter_evidence: List[str] = []

        # --- Supporting evidence ---
        # Trend evidence
        tf = trend_features.get(_CSI300_CODE) or trend_features.get("000300")
        if tf is not None:
            if trend == TrendState.STRONG_UP:
                key_evidence.append(
                    f"沪深300 MA多头排列(MA5={tf.ma5:.1f}>MA10={tf.ma10:.1f}>MA20={tf.ma20:.1f}>MA60={tf.ma60:.1f})"
                    f"，MACD{tf.macd_signal}，RSRS={tf.rsrs_score:.2f}"
                )
            elif trend == TrendState.BREAKDOWN:
                key_evidence.append(
                    f"沪深300 跌破MA60({tf.ma60:.1f})，RSRS={tf.rsrs_score:.2f}<0.3，趋势破位"
                )
            elif trend == TrendState.WEAKENING:
                key_evidence.append(
                    f"沪深300 均线走弱(MA5={tf.ma5:.1f}<MA10={tf.ma10:.1f})，MACD{tf.macd_signal}"
                )
            elif trend == TrendState.PULLBACK_IN_UPTREND:
                key_evidence.append(
                    f"沪深300 多头排列中回调(MA5={tf.ma5:.1f}<MA10={tf.ma10:.1f})，趋势未破坏"
                )
            else:
                key_evidence.append(
                    f"沪深300 均线缠绕，MACD柱={tf.macd_bar:.4f}，市场震荡"
                )

        # Breadth evidence
        r = breadth_features.above_ma20_ratio
        key_evidence.append(
            f"市场广度：站上MA20个股比例={r:.1%}({breadth.value})，"
            f"涨跌比={breadth_features.up_down_ratio:.2f}"
        )

        # Sentiment evidence
        key_evidence.append(
            f"市场情绪：涨停/跌停比={sentiment_features.limit_up_down_ratio:.2f}，"
            f"封板率={sentiment_features.seal_rate:.1%}，"
            f"情绪分={sentiment_features.sentiment_score:.0f}({sentiment.value})"
        )

        # Keep only top 3
        key_evidence = key_evidence[:3]

        # --- Counter-evidence ---
        # Bullish trend but weak breadth
        if trend in (TrendState.STRONG_UP, TrendState.PULLBACK_IN_UPTREND):
            if breadth in (BreadthState.EXTREME_WEAK, BreadthState.WEAK):
                counter_evidence.append(
                    f"指数走强但广度偏弱(MA20比例={r:.1%})，上涨缺乏普遍参与"
                )

        # Bearish trend but positive sentiment
        if trend in (TrendState.WEAKENING, TrendState.BREAKDOWN):
            if sentiment in (SentimentState.ACTIVE, SentimentState.EUPHORIC):
                counter_evidence.append(
                    f"趋势走弱但情绪仍{sentiment.value}，可能存在结构性分化"
                )

        # High risk but strong trend
        if risk in (RiskState.HIGH, RiskState.EXTREME):
            if trend == TrendState.STRONG_UP:
                counter_evidence.append(
                    f"趋势强劲但风险状态为{risk.value}，需警惕波动放大"
                )

        # Capital outflow despite positive trend
        if capital_features.north_5d_avg < -5.0 and trend in (
            TrendState.STRONG_UP, TrendState.PULLBACK_IN_UPTREND
        ):
            counter_evidence.append(
                f"北向资金5日均值={capital_features.north_5d_avg:.1f}亿，外资持续流出"
            )

        # Overheated breadth as risk
        if breadth == BreadthState.OVERHEATED:
            counter_evidence.append(
                f"广度过热(MA20比例={r:.1%})，短期回调风险上升"
            )

        return key_evidence, counter_evidence

    # ------------------------------------------------------------------
    # Confidence computation  (Req 17.3-17.7)
    # ------------------------------------------------------------------

    def _compute_confidence(
        self,
        missing_data: List[str],
        states: List,
        trend_features: Dict[str, TrendFeatures],
        breadth_features: BreadthFeatures,
        sentiment_features: SentimentFeatures,
        capital_features: CapitalFeatures,
        risk_features: RiskFeatures,
    ) -> float:
        """
        Req 17.3: -0.15 per missing core indicator (design says -0.15, req says -0.2; use design)
        Req 17.4: +0.10 when signals consistent across trend/breadth/sentiment
        Req 17.5: -0.10 for extreme anomalous values
        Req 17.6: -0.05 per estimated/proxy data item
        Req 17.7: clamp to [0.1, 1.0]
        """
        confidence = 1.0

        # Req 17.3: Penalise missing core indicators (-0.15 each)
        core_indicators = [
            "index_data", "breadth_data", "sentiment_data",
            "capital_data", "risk_data",
        ]
        for indicator in core_indicators:
            if any(indicator in m for m in missing_data):
                confidence -= 0.15

        # Also penalise each item in missing_data list
        confidence -= 0.15 * len(missing_data)

        # Req 17.4: Boost for consistent signals
        # Consistent = trend and breadth and sentiment all point same direction
        trend_states = [s for s in states if isinstance(s, TrendState)]
        breadth_states = [s for s in states if isinstance(s, BreadthState)]
        sentiment_states = [s for s in states if isinstance(s, SentimentState)]

        if trend_states and breadth_states and sentiment_states:
            t = trend_states[0]
            b = breadth_states[0]
            s = sentiment_states[0]

            bullish_trend = t in (TrendState.STRONG_UP, TrendState.PULLBACK_IN_UPTREND)
            bullish_breadth = b in (BreadthState.STRONG, BreadthState.OVERHEATED)
            bullish_sentiment = s in (SentimentState.ACTIVE, SentimentState.EUPHORIC)

            bearish_trend = t in (TrendState.WEAKENING, TrendState.BREAKDOWN)
            bearish_breadth = b in (BreadthState.EXTREME_WEAK, BreadthState.WEAK)
            bearish_sentiment = s in (SentimentState.FROZEN, SentimentState.WARMING)

            if (bullish_trend and bullish_breadth and bullish_sentiment) or \
               (bearish_trend and bearish_breadth and bearish_sentiment):
                confidence += 0.10

        # Req 17.5: Penalise extreme anomalous values (-0.10)
        # Check for extreme volatility ratios
        for code, vol_ratio in risk_features.vol_ratio_short_long.items():
            if vol_ratio > 3.0:
                confidence -= 0.10
                break

        # Check for extreme sentiment values
        if sentiment_features.limit_up_down_ratio > 10.0 or \
           sentiment_features.limit_up_down_ratio == 0.0:
            confidence -= 0.10

        # Req 17.6: Penalise estimated/proxy data (-0.05 per item)
        proxy_count = 0
        if capital_features.has_delayed_data:
            proxy_count += 1
        if not risk_features.has_cvix_data:
            proxy_count += 1  # Using ATR as C-VIX proxy
        # Check data_freshness for T+1 markers
        for freshness in capital_features.data_freshness.values():
            if "T+1" in freshness or "proxy" in freshness.lower() or "估计" in freshness:
                proxy_count += 1

        confidence -= 0.05 * proxy_count

        # Req 17.7: Clamp to [0.1, 1.0]
        return _clamp(confidence, 0.1, 1.0)
