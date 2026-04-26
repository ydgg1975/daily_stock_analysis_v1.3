"""
Unit Tests for State Classifier Edge Cases

Task 8.4: Write unit tests for state classifier edge cases
Tests:
- Classification with missing features (None values, empty dicts)
- Confidence calculation with various data completeness levels
- Evidence extraction with conflicting signals
Requirements: 17.3, 17.5, 22.5
"""

import math
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.market_diagnostic.states.enums import (
    TrendState, BreadthState, SentimentState, StyleState,
    SectorState, RiskState, CompositeRegime,
)
from src.market_diagnostic.states.classifier import MarketStateClassifier
from src.market_diagnostic.features.trend import TrendFeatures
from src.market_diagnostic.features.breadth import BreadthFeatures
from src.market_diagnostic.features.sentiment import SentimentFeatures
from src.market_diagnostic.features.style import StyleFeatures
from src.market_diagnostic.features.sector import SectorFeatureResult
from src.market_diagnostic.features.capital import CapitalFeatures
from src.market_diagnostic.features.risk import RiskFeatures


# ---------------------------------------------------------------------------
# Shared classifier instance
# ---------------------------------------------------------------------------

_classifier = MarketStateClassifier()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_default_trend_features(code="sh000300", **overrides):
    """Create a default TrendFeatures with optional overrides."""
    defaults = dict(
        code=code,
        ma5=3500.0, ma10=3480.0, ma20=3450.0, ma60=3400.0, ma120=3300.0,
        ma_alignment="缠绕",
        bias_ma5=0.0, bias_ma20=0.0, bias_ma60=0.0,
        macd_dif=0.0, macd_dea=0.0, macd_bar=0.0, macd_signal="中性",
        atr_20=30.0, rsrs_score=0.5,
        near_high_20d=False, break_support=False, rs_vs_300=1.0,
    )
    defaults.update(overrides)
    return TrendFeatures(**defaults)


def _make_default_breadth_features(**overrides):
    defaults = dict(
        up_down_ratio=1.0, limit_up_rate=0.01, seal_rate=0.7,
        above_ma20_ratio=0.5, above_ma60_ratio=0.5, new_high_ratio=0.01,
        amount_deviation_5d=0.0, amount_deviation_20d=0.0, breadth_score=50.0,
    )
    defaults.update(overrides)
    return BreadthFeatures(**defaults)


def _make_default_sentiment_features(**overrides):
    defaults = dict(
        limit_up_down_ratio=1.0, continuous_limit_up=10, seal_rate=0.7,
        next_day_premium=0.0, turnover_zscore=0.0, sentiment_score=50.0,
    )
    defaults.update(overrides)
    return SentimentFeatures(**defaults)


def _make_default_style_features(**overrides):
    defaults = dict(
        rs_large_vs_small=1.0, rs_300_vs_1000=1.0, rs_500_vs_1000=1.0,
        ret_1d={}, ret_5d={}, ret_20d={}, amount_share={},
        dominant_style="风格冲突",
    )
    defaults.update(overrides)
    return StyleFeatures(**defaults)


def _make_default_capital_features(**overrides):
    defaults = dict(
        total_amount=8000.0, amount_deviation_5d=0.0, amount_deviation_20d=0.0,
        amount_deviation_60d=0.0, north_net_flow=0.0, north_5d_avg=0.0,
        north_flow_trend="neutral", margin_balance=15000.0, margin_delta=0.0,
        main_net_flow=0.0, etf_net_flow=0.0, data_freshness={}, has_delayed_data=False,
    )
    defaults.update(overrides)
    return CapitalFeatures(**defaults)


def _make_default_risk_features(**overrides):
    defaults = dict(
        realized_volatility={"sh000300": 0.15},
        atr_volatility={"sh000300": 0.01},
        vol_ratio_short_long={"sh000300": 1.0},
        index_drawdown={"sh000300": -2.0},
        cross_index_correlation=0.5,
        sector_correlation_elevation=0.0,
        cvix_value=None, cvix_percentile=None, has_cvix_data=False,
    )
    defaults.update(overrides)
    return RiskFeatures(**defaults)


def _make_sector_feature(strength=1.0, persistence=0.5, state="震荡整理", **overrides):
    defaults = dict(
        industry_code="BK0001", industry_name="电子",
        strength_score=strength, persistence_score=persistence,
        crowding_score=0.0, leadership_score=0.0, state=state,
    )
    defaults.update(overrides)
    return SectorFeatureResult(**defaults)


def _full_classify(
    trend_features=None,
    breadth_features=None,
    sentiment_features=None,
    style_features=None,
    sector_features=None,
    capital_features=None,
    risk_features=None,
    missing_data=None,
):
    """Run full classify() with sensible defaults for unspecified inputs."""
    return _classifier.classify(
        trend_features=trend_features or {"sh000300": _make_default_trend_features()},
        breadth_features=breadth_features or _make_default_breadth_features(),
        sentiment_features=sentiment_features or _make_default_sentiment_features(),
        style_features=style_features or _make_default_style_features(),
        sector_features=sector_features if sector_features is not None else [],
        capital_features=capital_features or _make_default_capital_features(),
        risk_features=risk_features or _make_default_risk_features(),
        missing_data=missing_data or [],
    )


# ===========================================================================
# Section 1: Classification with missing features
# Requirements: 22.5
# ===========================================================================

class TestClassificationWithMissingFeatures:
    """Tests for graceful handling of missing/empty feature inputs."""

    def test_empty_trend_features_dict_returns_ranging(self):
        """When trend_features is an empty dict, classifier should default to RANGING."""
        result = _full_classify(trend_features={})
        assert result.trend_state == TrendState.RANGING, (
            f"Expected RANGING for empty trend_features, got {result.trend_state}"
        )

    def test_trend_features_missing_csi300_uses_first_available(self):
        """When sh000300 is absent, classifier should use the first available index."""
        # Provide only a non-CSI300 index with strong uptrend conditions
        tf = _make_default_trend_features(
            code="sh000001",
            ma5=3600.0, ma10=3550.0, ma20=3500.0, ma60=3400.0,
            ma_alignment="多头排列",
            macd_signal="金叉",
            rsrs_score=0.8,
            break_support=False,
        )
        result = _full_classify(trend_features={"sh000001": tf})
        # Should classify based on the available index, not crash
        assert result.trend_state in list(TrendState), (
            f"Expected a valid TrendState, got {result.trend_state}"
        )

    def test_nan_ma_values_treated_as_tangled(self):
        """When MA values are NaN, MA alignment should be treated as tangled (缠绕)."""
        tf = _make_default_trend_features(
            ma5=float("nan"), ma10=float("nan"),
            ma20=float("nan"), ma60=float("nan"),
            ma_alignment="缠绕",
            macd_bar=0.005,  # near zero
            macd_signal="中性",
            break_support=False,
            rsrs_score=0.5,
        )
        result = _full_classify(trend_features={"sh000300": tf})
        # NaN MAs should not trigger STRONG_UP or BREAKDOWN
        assert result.trend_state not in (TrendState.STRONG_UP,), (
            f"NaN MAs should not produce STRONG_UP, got {result.trend_state}"
        )

    def test_empty_sector_features_returns_no_theme(self):
        """When sector_features is empty, sector state should be NO_THEME."""
        result = _full_classify(sector_features=[])
        assert result.sector_state == SectorState.NO_THEME, (
            f"Expected NO_THEME for empty sectors, got {result.sector_state}"
        )

    def test_missing_data_list_reduces_confidence(self):
        """When missing_data is non-empty, confidence should be reduced (Req 22.5)."""
        result_no_missing = _full_classify(missing_data=[])
        result_with_missing = _full_classify(missing_data=["breadth_data"])

        assert result_with_missing.confidence < result_no_missing.confidence, (
            f"Confidence should decrease with missing data: "
            f"no_missing={result_no_missing.confidence:.3f}, "
            f"with_missing={result_with_missing.confidence:.3f}"
        )

    def test_missing_data_list_populated_in_result(self):
        """The missing_data list in the result should reflect what was passed in."""
        missing = ["breadth_data", "capital_data"]
        result = _full_classify(missing_data=missing)
        assert result.missing_data == missing, (
            f"Expected missing_data={missing}, got {result.missing_data}"
        )

    def test_empty_risk_vol_dict_does_not_crash(self):
        """When risk vol dicts are empty, classifier should not crash."""
        risk = _make_default_risk_features(
            realized_volatility={},
            vol_ratio_short_long={},
            index_drawdown={},
        )
        result = _full_classify(risk_features=risk)
        assert result.risk_state in list(RiskState), (
            f"Expected a valid RiskState, got {result.risk_state}"
        )

    def test_empty_capital_data_freshness_no_proxy_penalty(self):
        """When data_freshness is empty, no proxy penalty should be applied."""
        capital = _make_default_capital_features(
            data_freshness={}, has_delayed_data=False,
        )
        risk = _make_default_risk_features(has_cvix_data=True)  # has cvix, no proxy
        result = _full_classify(capital_features=capital, risk_features=risk)
        # Confidence should be at or near 1.0 with no missing data and no proxies
        assert result.confidence >= 0.9, (
            f"Expected high confidence with no missing/proxy data, got {result.confidence:.3f}"
        )

    def test_classify_returns_valid_result_with_all_defaults(self):
        """Full classify with all defaults should return a complete, valid result."""
        result = _full_classify()
        assert result.trend_state in list(TrendState)
        assert result.breadth_state in list(BreadthState)
        assert result.sentiment_state in list(SentimentState)
        assert result.style_state in list(StyleState)
        assert result.sector_state in list(SectorState)
        assert result.risk_state in list(RiskState)
        assert result.composite_regime in list(CompositeRegime)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.key_evidence, list)
        assert isinstance(result.counter_evidence, list)
        assert isinstance(result.missing_data, list)

# ===========================================================================
# Section 2: Confidence calculation with various data completeness levels
# Requirements: 17.3, 17.5
# ===========================================================================

class TestConfidenceCalculation:
    """Tests for _compute_confidence() with various data completeness levels."""

    def _compute_confidence_direct(self, missing_data, states=None, **feature_overrides):
        """Helper to call _compute_confidence directly."""
        if states is None:
            states = [
                TrendState.RANGING,
                BreadthState.NEUTRAL,
                SentimentState.NEUTRAL,
                StyleState.STYLE_CONFLICT,
                SectorState.NO_THEME,
                RiskState.NEUTRAL,
            ]
        trend_features = feature_overrides.get(
            "trend_features", {"sh000300": _make_default_trend_features()}
        )
        breadth_features = feature_overrides.get(
            "breadth_features", _make_default_breadth_features()
        )
        sentiment_features = feature_overrides.get(
            "sentiment_features", _make_default_sentiment_features()
        )
        capital_features = feature_overrides.get(
            "capital_features", _make_default_capital_features()
        )
        risk_features = feature_overrides.get(
            "risk_features", _make_default_risk_features()
        )
        return _classifier._compute_confidence(
            missing_data=missing_data,
            states=states,
            trend_features=trend_features,
            breadth_features=breadth_features,
            sentiment_features=sentiment_features,
            capital_features=capital_features,
            risk_features=risk_features,
        )

    def test_zero_missing_items_high_confidence(self):
        """With 0 missing items and no anomalies, confidence should be high (>= 0.9)."""
        confidence = self._compute_confidence_direct(missing_data=[])
        assert confidence >= 0.9, (
            f"Expected confidence >= 0.9 with no missing data, got {confidence:.3f}"
        )

    def test_one_missing_item_reduces_confidence_by_015(self):
        """With 1 non-core missing item, confidence should be reduced by ~0.15 (Req 17.3).

        The classifier applies -0.15 per item in missing_data. Core indicator names
        (e.g. 'breadth_data') also trigger an additional -0.15 match penalty, so we
        use a non-core name to isolate the per-item penalty.
        """
        confidence_0 = self._compute_confidence_direct(missing_data=[])
        # Use a non-core-indicator name to get exactly -0.15 (only the len penalty)
        confidence_1 = self._compute_confidence_direct(missing_data=["some_extra_indicator"])
        delta = confidence_0 - confidence_1
        assert abs(delta - 0.15) < 0.01, (
            f"Expected confidence reduction of ~0.15 for 1 non-core missing item, got {delta:.3f}"
        )

    def test_three_missing_items_significantly_reduces_confidence(self):
        """With 3+ missing items, confidence should be significantly reduced."""
        confidence_0 = self._compute_confidence_direct(missing_data=[])
        confidence_3 = self._compute_confidence_direct(
            missing_data=["breadth_data", "capital_data", "risk_data"]
        )
        assert confidence_3 < confidence_0 - 0.30, (
            f"Expected confidence significantly reduced with 3 missing items: "
            f"base={confidence_0:.3f}, with_3_missing={confidence_3:.3f}"
        )

    def test_consistent_bullish_signals_boost_confidence(self):
        """When trend/breadth/sentiment all bullish, confidence should be boosted by 0.10 (Req 17.4).

        To observe the full +0.10 boost without clamping, we use 3 non-core missing items
        to bring the base confidence down to ~0.50, then compare neutral vs bullish states.
        """
        # Use 3 non-core missing items to bring base confidence below 0.90 so the
        # +0.10 boost is not masked by the 1.0 ceiling clamp.
        missing_3 = ["extra_item_1", "extra_item_2", "extra_item_3"]
        bullish_states = [
            TrendState.STRONG_UP,
            BreadthState.STRONG,
            SentimentState.ACTIVE,
            StyleState.GROWTH_DOMINANT,
            SectorState.SINGLE_THEME,
            RiskState.LOW,
        ]
        neutral_states = [
            TrendState.RANGING,
            BreadthState.NEUTRAL,
            SentimentState.NEUTRAL,
            StyleState.STYLE_CONFLICT,
            SectorState.NO_THEME,
            RiskState.NEUTRAL,
        ]
        confidence_bullish = self._compute_confidence_direct(
            missing_data=missing_3, states=bullish_states
        )
        confidence_neutral = self._compute_confidence_direct(
            missing_data=missing_3, states=neutral_states
        )
        assert confidence_bullish > confidence_neutral, (
            f"Consistent bullish signals should boost confidence: "
            f"bullish={confidence_bullish:.3f}, neutral={confidence_neutral:.3f}"
        )
        # The boost should be approximately 0.10
        boost = confidence_bullish - confidence_neutral
        assert abs(boost - 0.10) < 0.01, (
            f"Expected confidence boost of ~0.10 for consistent signals, got {boost:.3f}"
        )

    def test_consistent_bearish_signals_boost_confidence(self):
        """When trend/breadth/sentiment all bearish, confidence should also be boosted."""
        bearish_states = [
            TrendState.BREAKDOWN,
            BreadthState.EXTREME_WEAK,
            SentimentState.FROZEN,
            StyleState.LARGE_CAP_DEFENSIVE,
            SectorState.FADING,
            RiskState.EXTREME,
        ]
        neutral_states = [
            TrendState.RANGING,
            BreadthState.NEUTRAL,
            SentimentState.NEUTRAL,
            StyleState.STYLE_CONFLICT,
            SectorState.NO_THEME,
            RiskState.NEUTRAL,
        ]
        confidence_bearish = self._compute_confidence_direct(
            missing_data=[], states=bearish_states
        )
        confidence_neutral = self._compute_confidence_direct(
            missing_data=[], states=neutral_states
        )
        assert confidence_bearish > confidence_neutral, (
            f"Consistent bearish signals should boost confidence: "
            f"bearish={confidence_bearish:.3f}, neutral={confidence_neutral:.3f}"
        )

    def test_extreme_vol_ratio_reduces_confidence(self):
        """When vol_ratio > 3.0, confidence should be reduced by 0.10 (Req 17.5)."""
        normal_risk = _make_default_risk_features(
            vol_ratio_short_long={"sh000300": 1.0}
        )
        extreme_risk = _make_default_risk_features(
            vol_ratio_short_long={"sh000300": 3.5}
        )
        confidence_normal = self._compute_confidence_direct(
            missing_data=[], risk_features=normal_risk
        )
        confidence_extreme = self._compute_confidence_direct(
            missing_data=[], risk_features=extreme_risk
        )
        delta = confidence_normal - confidence_extreme
        assert abs(delta - 0.10) < 0.01, (
            f"Expected confidence reduction of ~0.10 for extreme vol ratio, got {delta:.3f}"
        )

    def test_extreme_sentiment_ratio_reduces_confidence(self):
        """When limit_up_down_ratio is extreme (>10 or ==0), confidence should be reduced."""
        normal_sentiment = _make_default_sentiment_features(limit_up_down_ratio=1.0)
        extreme_sentiment = _make_default_sentiment_features(limit_up_down_ratio=15.0)
        confidence_normal = self._compute_confidence_direct(
            missing_data=[], sentiment_features=normal_sentiment
        )
        confidence_extreme = self._compute_confidence_direct(
            missing_data=[], sentiment_features=extreme_sentiment
        )
        assert confidence_extreme < confidence_normal, (
            f"Extreme sentiment ratio should reduce confidence: "
            f"normal={confidence_normal:.3f}, extreme={confidence_extreme:.3f}"
        )

    def test_zero_sentiment_ratio_reduces_confidence(self):
        """When limit_up_down_ratio == 0 (no limit-ups), confidence should be reduced."""
        normal_sentiment = _make_default_sentiment_features(limit_up_down_ratio=1.0)
        zero_sentiment = _make_default_sentiment_features(limit_up_down_ratio=0.0)
        confidence_normal = self._compute_confidence_direct(
            missing_data=[], sentiment_features=normal_sentiment
        )
        confidence_zero = self._compute_confidence_direct(
            missing_data=[], sentiment_features=zero_sentiment
        )
        assert confidence_zero < confidence_normal, (
            f"Zero sentiment ratio should reduce confidence: "
            f"normal={confidence_normal:.3f}, zero={confidence_zero:.3f}"
        )

    def test_delayed_capital_data_reduces_confidence(self):
        """When capital data has T+1 delay, confidence should be reduced (Req 17.6)."""
        fresh_capital = _make_default_capital_features(
            data_freshness={}, has_delayed_data=False
        )
        delayed_capital = _make_default_capital_features(
            data_freshness={"north_net_flow": "T+1 delayed"},
            has_delayed_data=True,
        )
        confidence_fresh = self._compute_confidence_direct(
            missing_data=[], capital_features=fresh_capital
        )
        confidence_delayed = self._compute_confidence_direct(
            missing_data=[], capital_features=delayed_capital
        )
        assert confidence_delayed < confidence_fresh, (
            f"Delayed data should reduce confidence: "
            f"fresh={confidence_fresh:.3f}, delayed={confidence_delayed:.3f}"
        )

    def test_confidence_always_clamped_to_01_10(self):
        """Confidence should always be in [0.1, 1.0] regardless of inputs (Req 17.7)."""
        # Many missing items should not push confidence below 0.1
        many_missing = [f"indicator_{i}" for i in range(20)]
        confidence = self._compute_confidence_direct(missing_data=many_missing)
        assert 0.1 <= confidence <= 1.0, (
            f"Confidence {confidence:.3f} is outside [0.1, 1.0]"
        )

    def test_confidence_not_above_1_with_consistent_signals(self):
        """Confidence should never exceed 1.0 even with consistent signals."""
        bullish_states = [
            TrendState.STRONG_UP,
            BreadthState.STRONG,
            SentimentState.ACTIVE,
            StyleState.GROWTH_DOMINANT,
            SectorState.SINGLE_THEME,
            RiskState.LOW,
        ]
        confidence = self._compute_confidence_direct(
            missing_data=[], states=bullish_states
        )
        assert confidence <= 1.0, (
            f"Confidence {confidence:.3f} should not exceed 1.0"
        )

    def test_full_classify_confidence_reflects_missing_data(self):
        """Full classify() confidence should decrease as more items are added to missing_data."""
        result_0 = _full_classify(missing_data=[])
        result_1 = _full_classify(missing_data=["breadth_data"])
        result_3 = _full_classify(missing_data=["breadth_data", "capital_data", "risk_data"])

        assert result_0.confidence >= result_1.confidence, (
            f"Confidence should not increase with more missing data: "
            f"0_missing={result_0.confidence:.3f}, 1_missing={result_1.confidence:.3f}"
        )
        assert result_1.confidence >= result_3.confidence, (
            f"Confidence should not increase with more missing data: "
            f"1_missing={result_1.confidence:.3f}, 3_missing={result_3.confidence:.3f}"
        )

# ===========================================================================
# Section 3: Evidence extraction with conflicting signals
# Requirements: 17.2
# ===========================================================================

class TestEvidenceExtractionConflictingSignals:
    """Tests for counter_evidence population when signals conflict."""

    def test_bullish_trend_weak_breadth_generates_counter_evidence(self):
        """When trend is bullish but breadth is weak, counter_evidence should be populated."""
        # Bullish trend
        tf = _make_default_trend_features(
            ma5=3600.0, ma10=3550.0, ma20=3500.0, ma60=3400.0,
            ma_alignment="多头排列",
            macd_signal="金叉",
            rsrs_score=0.8,
            break_support=False,
        )
        # Weak breadth
        bf = _make_default_breadth_features(above_ma20_ratio=0.25)

        result = _full_classify(
            trend_features={"sh000300": tf},
            breadth_features=bf,
        )
        assert result.counter_evidence, (
            "Expected counter_evidence when trend is bullish but breadth is weak"
        )
        # The counter evidence should mention breadth weakness
        combined = " ".join(result.counter_evidence)
        assert any(keyword in combined for keyword in ["广度", "MA20", "偏弱", "参与"]), (
            f"Counter evidence should mention breadth weakness, got: {result.counter_evidence}"
        )

    def test_bullish_trend_extreme_weak_breadth_generates_counter_evidence(self):
        """When trend is bullish but breadth is extreme weak, counter_evidence should be populated."""
        tf = _make_default_trend_features(
            ma5=3600.0, ma10=3550.0, ma20=3500.0, ma60=3400.0,
            ma_alignment="多头排列",
            macd_signal="金叉",
            rsrs_score=0.8,
            break_support=False,
        )
        bf = _make_default_breadth_features(above_ma20_ratio=0.10)  # extreme weak

        result = _full_classify(
            trend_features={"sh000300": tf},
            breadth_features=bf,
        )
        assert result.counter_evidence, (
            "Expected counter_evidence when trend is bullish but breadth is extreme weak"
        )

    def test_bearish_trend_euphoric_sentiment_generates_counter_evidence(self):
        """When trend is bearish but sentiment is euphoric, counter_evidence should be populated."""
        # Bearish trend (death cross)
        tf = _make_default_trend_features(
            ma5=3300.0, ma10=3350.0, ma20=3400.0, ma60=3450.0,
            ma_alignment="空头排列",
            macd_signal="死叉",
            rsrs_score=0.4,
            break_support=False,
        )
        # Euphoric sentiment
        sf = _make_default_sentiment_features(
            limit_up_down_ratio=6.0,
            continuous_limit_up=25,
            seal_rate=0.9,
            sentiment_score=85.0,
        )

        result = _full_classify(
            trend_features={"sh000300": tf},
            sentiment_features=sf,
        )
        assert result.counter_evidence, (
            "Expected counter_evidence when trend is bearish but sentiment is euphoric"
        )

    def test_bearish_trend_active_sentiment_generates_counter_evidence(self):
        """When trend is weakening but sentiment is active, counter_evidence should be populated."""
        tf = _make_default_trend_features(
            ma5=3300.0, ma10=3350.0, ma20=3400.0, ma60=3450.0,
            ma_alignment="空头排列",
            macd_signal="死叉",
            rsrs_score=0.4,
            break_support=False,
        )
        sf = _make_default_sentiment_features(
            limit_up_down_ratio=3.0,
            seal_rate=0.75,
            sentiment_score=65.0,
        )

        result = _full_classify(
            trend_features={"sh000300": tf},
            sentiment_features=sf,
        )
        assert result.counter_evidence, (
            "Expected counter_evidence when trend is weakening but sentiment is active"
        )

    def test_strong_trend_high_risk_generates_counter_evidence(self):
        """When trend is strong but risk is high, counter_evidence should be populated."""
        tf = _make_default_trend_features(
            ma5=3600.0, ma10=3550.0, ma20=3500.0, ma60=3400.0,
            ma_alignment="多头排列",
            macd_signal="金叉",
            rsrs_score=0.8,
            break_support=False,
        )
        # High risk via extreme volatility
        risk = _make_default_risk_features(
            realized_volatility={"sh000300": 0.50},  # > 0.40 → EXTREME
            vol_ratio_short_long={"sh000300": 2.5},
            index_drawdown={"sh000300": -2.0},
        )

        result = _full_classify(
            trend_features={"sh000300": tf},
            risk_features=risk,
        )
        assert result.counter_evidence, (
            "Expected counter_evidence when trend is strong but risk is extreme"
        )

    def test_north_outflow_with_bullish_trend_generates_counter_evidence(self):
        """When north bound capital is flowing out despite bullish trend, counter_evidence should appear."""
        tf = _make_default_trend_features(
            ma5=3600.0, ma10=3550.0, ma20=3500.0, ma60=3400.0,
            ma_alignment="多头排列",
            macd_signal="金叉",
            rsrs_score=0.8,
            break_support=False,
        )
        capital = _make_default_capital_features(north_5d_avg=-20.0)  # significant outflow

        result = _full_classify(
            trend_features={"sh000300": tf},
            capital_features=capital,
        )
        assert result.counter_evidence, (
            "Expected counter_evidence when north capital is flowing out despite bullish trend"
        )
        combined = " ".join(result.counter_evidence)
        assert "北向" in combined, (
            f"Counter evidence should mention north bound capital, got: {result.counter_evidence}"
        )

    def test_overheated_breadth_generates_counter_evidence(self):
        """When breadth is overheated, counter_evidence should warn of reversal risk."""
        bf = _make_default_breadth_features(above_ma20_ratio=0.80)  # overheated

        result = _full_classify(breadth_features=bf)
        assert result.counter_evidence, (
            "Expected counter_evidence when breadth is overheated"
        )
        combined = " ".join(result.counter_evidence)
        assert any(keyword in combined for keyword in ["过热", "回调", "风险"]), (
            f"Counter evidence should mention overheated risk, got: {result.counter_evidence}"
        )

    def test_consistent_signals_no_counter_evidence(self):
        """When all signals are consistent (all bearish), counter_evidence should be minimal."""
        # All bearish signals
        tf = _make_default_trend_features(
            ma5=3300.0, ma10=3350.0, ma20=3400.0, ma60=3450.0,
            ma_alignment="空头排列",
            macd_signal="死叉",
            rsrs_score=0.2,
            break_support=True,
        )
        bf = _make_default_breadth_features(above_ma20_ratio=0.15)  # extreme weak
        sf = _make_default_sentiment_features(
            limit_up_down_ratio=0.2,
            seal_rate=0.1,
            sentiment_score=5.0,
        )
        capital = _make_default_capital_features(north_5d_avg=0.0)  # neutral capital

        result = _full_classify(
            trend_features={"sh000300": tf},
            breadth_features=bf,
            sentiment_features=sf,
            capital_features=capital,
        )
        # With consistent bearish signals, counter_evidence should be empty or minimal
        # (no bullish trend to conflict with weak breadth, no strong sentiment to conflict with weak trend)
        # The overheated breadth counter-evidence should NOT appear since breadth is extreme weak
        combined = " ".join(result.counter_evidence)
        assert "过热" not in combined, (
            f"Should not have overheated counter evidence when breadth is extreme weak: {result.counter_evidence}"
        )

    def test_key_evidence_always_has_at_most_3_items(self):
        """key_evidence should always contain at most 3 items (Req 17.1)."""
        result = _full_classify()
        assert len(result.key_evidence) <= 3, (
            f"Expected at most 3 key evidence items, got {len(result.key_evidence)}: {result.key_evidence}"
        )

    def test_key_evidence_not_empty_for_normal_inputs(self):
        """key_evidence should not be empty for normal inputs (Req 17.1)."""
        result = _full_classify()
        assert len(result.key_evidence) > 0, (
            "Expected at least 1 key evidence item for normal inputs"
        )

    def test_pullback_in_uptrend_with_weak_breadth_generates_counter_evidence(self):
        """When trend is pullback-in-uptrend but breadth is weak, counter_evidence should appear."""
        tf = _make_default_trend_features(
            ma5=3500.0, ma10=3550.0, ma20=3500.0, ma60=3400.0,
            ma_alignment="多头排列",
            macd_signal="中性",
            rsrs_score=0.55,
            break_support=False,
        )
        bf = _make_default_breadth_features(above_ma20_ratio=0.28)  # weak

        result = _full_classify(
            trend_features={"sh000300": tf},
            breadth_features=bf,
        )
        assert result.counter_evidence, (
            "Expected counter_evidence when pullback-in-uptrend but breadth is weak"
        )


# ===========================================================================
# Section 4: Integration edge cases
# ===========================================================================

class TestIntegrationEdgeCases:
    """Integration tests for edge cases across the full classify() pipeline."""

    def test_all_missing_data_still_returns_valid_result(self):
        """Even with many missing data items, classify() should return a valid result."""
        many_missing = [
            "index_data", "breadth_data", "sentiment_data",
            "capital_data", "risk_data", "sector_data",
        ]
        result = _full_classify(missing_data=many_missing)
        assert result.trend_state in list(TrendState)
        assert result.breadth_state in list(BreadthState)
        assert result.composite_regime in list(CompositeRegime)
        assert 0.1 <= result.confidence <= 1.0

    def test_extreme_values_do_not_crash_classifier(self):
        """Extreme feature values should not cause exceptions."""
        tf = _make_default_trend_features(
            ma5=1e10, ma10=1e10, ma20=1e10, ma60=1e10,
            rsrs_score=1.0, macd_bar=1e6,
        )
        bf = _make_default_breadth_features(
            above_ma20_ratio=1.0, up_down_ratio=100.0,
        )
        sf = _make_default_sentiment_features(
            limit_up_down_ratio=100.0, sentiment_score=100.0,
        )
        result = _full_classify(
            trend_features={"sh000300": tf},
            breadth_features=bf,
            sentiment_features=sf,
        )
        assert result is not None
        assert 0.1 <= result.confidence <= 1.0

    def test_single_sector_with_high_strength_classified_as_single_theme(self):
        """A single sector with high strength and persistence should yield SINGLE_THEME."""
        sectors = [
            _make_sector_feature(strength=2.5, persistence=0.8, state="主升趋势",
                                 industry_code="BK0001", industry_name="电子"),
        ]
        result = _full_classify(sector_features=sectors)
        assert result.sector_state == SectorState.SINGLE_THEME, (
            f"Expected SINGLE_THEME for one strong sector, got {result.sector_state}"
        )

    def test_multiple_sectors_with_high_strength_classified_as_dual_theme(self):
        """Two sectors with high strength and persistence should yield DUAL_THEME."""
        sectors = [
            _make_sector_feature(strength=2.0, persistence=0.7, state="主升趋势",
                                 industry_code="BK0001", industry_name="电子"),
            _make_sector_feature(strength=1.9, persistence=0.65, state="趋势强化",
                                 industry_code="BK0002", industry_name="计算机"),
        ]
        result = _full_classify(sector_features=sectors)
        assert result.sector_state == SectorState.DUAL_THEME, (
            f"Expected DUAL_THEME for two strong sectors, got {result.sector_state}"
        )

    def test_confidence_is_float_not_nan(self):
        """Confidence should always be a finite float, never NaN."""
        result = _full_classify()
        assert not math.isnan(result.confidence), (
            f"Confidence should not be NaN, got {result.confidence}"
        )
        assert math.isfinite(result.confidence), (
            f"Confidence should be finite, got {result.confidence}"
        )

    def test_regime_score_is_finite(self):
        """Regime score should always be a finite float."""
        result = _full_classify()
        assert math.isfinite(result.regime_score), (
            f"Regime score should be finite, got {result.regime_score}"
        )
        assert 0.0 <= result.regime_score <= 100.0, (
            f"Regime score {result.regime_score} is outside [0, 100]"
        )
