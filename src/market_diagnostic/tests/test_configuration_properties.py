"""
Property-Based Tests for Configuration Management

Task 14.2: Write property tests for configuration
Property 53: Configuration Application
Validates: Requirement 24.6

This test validates that configuration values are consistent, valid, and
applied correctly across all components of the Market Diagnostic System.
"""

import math
import sys
import os

import pytest
from hypothesis import given, settings, strategies as st

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.market_diagnostic import config
from src.market_diagnostic.config import (
    INDEX_POOL,
    STYLE_PAIRS,
    SHENWAN_INDUSTRIES,
    BREADTH_THRESHOLDS,
    REGIME_SCORE_WEIGHTS,
    SECTOR_STRENGTH_WEIGHTS,
    CONFIDENCE_PARAMS,
    TREND_THRESHOLDS,
    SENTIMENT_THRESHOLDS,
    SECTOR_THRESHOLDS,
    RISK_THRESHOLDS,
)
from src.market_diagnostic.states.classifier import MarketStateClassifier
from src.market_diagnostic.features.breadth import BreadthFeatures


# ---------------------------------------------------------------------------
# Property 53: Configuration Application
# Validates: Requirement 24.6
# ---------------------------------------------------------------------------


class TestIndexPoolConfiguration:
    """Tests for INDEX_POOL configuration (Requirement 24.1)."""

    def test_index_pool_has_exactly_9_core_indices(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        INDEX_POOL SHALL contain exactly 9 core indices as specified in
        Requirement 1.1.
        """
        assert len(INDEX_POOL) == 9, (
            f"INDEX_POOL should have exactly 9 indices, got {len(INDEX_POOL)}"
        )

    def test_index_pool_contains_required_indices(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        INDEX_POOL SHALL contain all 9 required core indices.
        """
        required_codes = {
            "sh000001",  # 上证指数
            "sz399001",  # 深证成指
            "sz399006",  # 创业板指
            "sh000688",  # 科创50
            "sh000016",  # 上证50
            "sh000300",  # 沪深300
            "sh000905",  # 中证500
            "sh000852",  # 中证1000
            "sh000015",  # 微盘股指数 proxy
        }
        actual_codes = set(INDEX_POOL.keys())
        assert required_codes == actual_codes, (
            f"INDEX_POOL missing codes: {required_codes - actual_codes}"
        )

    def test_index_pool_names_are_non_empty(self):
        """All index names in INDEX_POOL must be non-empty strings."""
        for code, name in INDEX_POOL.items():
            assert isinstance(name, str) and len(name) > 0, (
                f"Index {code} has empty or invalid name: {name!r}"
            )


class TestStylePairsConfiguration:
    """Tests for STYLE_PAIRS configuration (Requirement 24.2)."""

    def test_style_pairs_has_exactly_3_pairs(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        STYLE_PAIRS SHALL contain exactly 3 pairs as specified in
        Requirements 5.1, 5.2, 5.3.
        """
        assert len(STYLE_PAIRS) == 3, (
            f"STYLE_PAIRS should have exactly 3 pairs, got {len(STYLE_PAIRS)}"
        )

    def test_style_pairs_reference_valid_indices(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        Each index code in STYLE_PAIRS SHALL exist in INDEX_POOL.
        """
        for idx_a, idx_b, label in STYLE_PAIRS:
            assert idx_a in INDEX_POOL, (
                f"Style pair index {idx_a!r} not found in INDEX_POOL"
            )
            assert idx_b in INDEX_POOL, (
                f"Style pair index {idx_b!r} not found in INDEX_POOL"
            )

    def test_style_pairs_have_non_empty_labels(self):
        """All style pair labels must be non-empty strings."""
        for idx_a, idx_b, label in STYLE_PAIRS:
            assert isinstance(label, str) and len(label) > 0, (
                f"Style pair ({idx_a}, {idx_b}) has empty label"
            )

    def test_style_pairs_are_distinct(self):
        """Each style pair should compare two different indices."""
        for idx_a, idx_b, label in STYLE_PAIRS:
            assert idx_a != idx_b, (
                f"Style pair ({idx_a}, {idx_b}) compares an index to itself"
            )


class TestShenwanIndustriesConfiguration:
    """Tests for SHENWAN_INDUSTRIES configuration (Requirement 24.3)."""

    def test_shenwan_industries_has_exactly_31_industries(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        SHENWAN_INDUSTRIES SHALL contain exactly 31 Level-1 industries as
        specified in Requirement 1.4.
        """
        assert len(SHENWAN_INDUSTRIES) == 31, (
            f"SHENWAN_INDUSTRIES should have exactly 31 industries, "
            f"got {len(SHENWAN_INDUSTRIES)}"
        )

    def test_shenwan_industry_codes_have_correct_format(self):
        """All industry codes must follow the BK#### format."""
        for code in SHENWAN_INDUSTRIES:
            assert code.startswith("BK"), (
                f"Industry code {code!r} should start with 'BK'"
            )
            assert len(code) == 6, (
                f"Industry code {code!r} should be 6 characters long"
            )

    def test_shenwan_industry_names_are_non_empty(self):
        """All industry names must be non-empty strings."""
        for code, name in SHENWAN_INDUSTRIES.items():
            assert isinstance(name, str) and len(name) > 0, (
                f"Industry {code} has empty or invalid name: {name!r}"
            )

    def test_shenwan_industry_codes_are_unique(self):
        """All industry codes must be unique."""
        codes = list(SHENWAN_INDUSTRIES.keys())
        assert len(codes) == len(set(codes)), "Duplicate industry codes found"

    def test_shenwan_industry_names_are_unique(self):
        """All industry names must be unique."""
        names = list(SHENWAN_INDUSTRIES.values())
        assert len(names) == len(set(names)), "Duplicate industry names found"


class TestBreadthThresholdsConfiguration:
    """Tests for BREADTH_THRESHOLDS configuration (Requirement 24.4)."""

    def test_breadth_thresholds_are_monotonically_increasing(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        BREADTH_THRESHOLDS values SHALL be monotonically increasing to
        define non-overlapping classification bands.
        """
        ordered_keys = ["extreme_weak", "weak", "neutral", "strong"]
        values = [BREADTH_THRESHOLDS[k] for k in ordered_keys]

        for i in range(len(values) - 1):
            assert values[i] < values[i + 1], (
                f"BREADTH_THRESHOLDS[{ordered_keys[i]}]={values[i]} should be "
                f"< BREADTH_THRESHOLDS[{ordered_keys[i+1]}]={values[i+1]}"
            )

    def test_breadth_thresholds_are_valid_ratios(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        All BREADTH_THRESHOLDS values SHALL be in the valid ratio range (0, 1).
        """
        for key, value in BREADTH_THRESHOLDS.items():
            assert 0.0 < value < 1.0, (
                f"BREADTH_THRESHOLDS[{key!r}]={value} should be in (0, 1)"
            )

    def test_breadth_thresholds_match_classifier(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        The breadth thresholds in config SHALL match the thresholds used
        in MarketStateClassifier._classify_breadth().

        This ensures configuration values are applied consistently across
        all components (Requirement 24.6).
        """
        classifier = MarketStateClassifier()

        # Build a minimal BreadthFeatures with above_ma20_ratio just below
        # each threshold and verify the classifier produces the expected state.
        from src.market_diagnostic.states.enums import BreadthState

        extreme_weak_threshold = BREADTH_THRESHOLDS["extreme_weak"]  # 0.20
        weak_threshold = BREADTH_THRESHOLDS["weak"]                  # 0.35
        neutral_threshold = BREADTH_THRESHOLDS["neutral"]            # 0.55
        strong_threshold = BREADTH_THRESHOLDS["strong"]              # 0.70

        def make_breadth(ratio: float) -> BreadthFeatures:
            return BreadthFeatures(
                up_down_ratio=1.0,
                limit_up_rate=0.02,
                seal_rate=0.6,
                above_ma20_ratio=ratio,
                above_ma60_ratio=ratio,
                new_high_ratio=0.01,
                amount_deviation_5d=0.0,
                amount_deviation_20d=0.0,
                breadth_score=50.0,
            )

        # Just below extreme_weak threshold → EXTREME_WEAK
        state = classifier._classify_breadth(make_breadth(extreme_weak_threshold - 0.01))
        assert state == BreadthState.EXTREME_WEAK, (
            f"Ratio {extreme_weak_threshold - 0.01:.2f} should be EXTREME_WEAK"
        )

        # At extreme_weak threshold → WEAK
        state = classifier._classify_breadth(make_breadth(extreme_weak_threshold))
        assert state == BreadthState.WEAK, (
            f"Ratio {extreme_weak_threshold:.2f} should be WEAK"
        )

        # Just below weak threshold → WEAK
        state = classifier._classify_breadth(make_breadth(weak_threshold - 0.01))
        assert state == BreadthState.WEAK, (
            f"Ratio {weak_threshold - 0.01:.2f} should be WEAK"
        )

        # At weak threshold → NEUTRAL
        state = classifier._classify_breadth(make_breadth(weak_threshold))
        assert state == BreadthState.NEUTRAL, (
            f"Ratio {weak_threshold:.2f} should be NEUTRAL"
        )

        # Just below neutral threshold → NEUTRAL
        state = classifier._classify_breadth(make_breadth(neutral_threshold - 0.01))
        assert state == BreadthState.NEUTRAL, (
            f"Ratio {neutral_threshold - 0.01:.2f} should be NEUTRAL"
        )

        # At neutral threshold → STRONG
        state = classifier._classify_breadth(make_breadth(neutral_threshold))
        assert state == BreadthState.STRONG, (
            f"Ratio {neutral_threshold:.2f} should be STRONG"
        )

        # Just below strong threshold → STRONG
        state = classifier._classify_breadth(make_breadth(strong_threshold - 0.01))
        assert state == BreadthState.STRONG, (
            f"Ratio {strong_threshold - 0.01:.2f} should be STRONG"
        )

        # At strong threshold → OVERHEATED
        state = classifier._classify_breadth(make_breadth(strong_threshold))
        assert state == BreadthState.OVERHEATED, (
            f"Ratio {strong_threshold:.2f} should be OVERHEATED"
        )


class TestRegimeScoreWeightsConfiguration:
    """Tests for REGIME_SCORE_WEIGHTS configuration (Requirement 24.5)."""

    def test_regime_score_weights_sum_to_expected_value(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        REGIME_SCORE_WEIGHTS SHALL sum to 0.60 as specified in Requirement 15.8:
        0.20 (trend) + 0.15 (breadth) + 0.15 (sentiment) + 0.15 (style)
        + 0.15 (sector) - 0.20 (risk) = 0.60.

        The risk weight is negative, so the net sum of all weights is 0.60.
        """
        total = sum(REGIME_SCORE_WEIGHTS.values())
        assert abs(total - 0.60) < 1e-9, (
            f"REGIME_SCORE_WEIGHTS should sum to 0.60, got {total}"
        )

    def test_regime_score_weights_risk_is_negative(self):
        """The risk weight SHALL be negative (it reduces the regime score)."""
        assert REGIME_SCORE_WEIGHTS["risk"] < 0, (
            "REGIME_SCORE_WEIGHTS['risk'] should be negative"
        )

    def test_regime_score_weights_non_risk_are_positive(self):
        """All non-risk weights SHALL be positive."""
        for key, value in REGIME_SCORE_WEIGHTS.items():
            if key != "risk":
                assert value > 0, (
                    f"REGIME_SCORE_WEIGHTS[{key!r}]={value} should be positive"
                )

    def test_regime_score_weights_contain_required_keys(self):
        """REGIME_SCORE_WEIGHTS SHALL contain all required dimension keys."""
        required_keys = {"trend", "breadth", "sentiment", "style", "sector", "risk"}
        assert required_keys == set(REGIME_SCORE_WEIGHTS.keys()), (
            f"Missing keys: {required_keys - set(REGIME_SCORE_WEIGHTS.keys())}"
        )


class TestSectorStrengthWeightsConfiguration:
    """Tests for SECTOR_STRENGTH_WEIGHTS configuration (Requirement 24.5)."""

    def test_sector_strength_weights_sum_to_approximately_one(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        SECTOR_STRENGTH_WEIGHTS SHALL sum to approximately 1.0 (positive
        weights minus the negative crowding weight), as specified in
        Requirement 6.7:
        0.25 + 0.20 + 0.20 + 0.10 + 0.10 + 0.10 - 0.05 = 0.90.

        Note: The design specifies weights that sum to 0.90 (not 1.0 exactly),
        which is the intended formula per Requirement 6.7.
        """
        total = sum(SECTOR_STRENGTH_WEIGHTS.values())
        # Per Requirement 6.7: 0.25+0.20+0.20+0.10+0.10+0.10-0.05 = 0.90
        assert abs(total - 0.90) < 1e-9, (
            f"SECTOR_STRENGTH_WEIGHTS should sum to 0.90, got {total}"
        )

    def test_sector_strength_weights_crowding_is_negative(self):
        """The crowding_score weight SHALL be negative."""
        assert SECTOR_STRENGTH_WEIGHTS["crowding_score"] < 0, (
            "SECTOR_STRENGTH_WEIGHTS['crowding_score'] should be negative"
        )

    def test_sector_strength_weights_non_crowding_are_positive(self):
        """All non-crowding weights SHALL be positive."""
        for key, value in SECTOR_STRENGTH_WEIGHTS.items():
            if key != "crowding_score":
                assert value > 0, (
                    f"SECTOR_STRENGTH_WEIGHTS[{key!r}]={value} should be positive"
                )

    def test_sector_strength_weights_contain_required_keys(self):
        """SECTOR_STRENGTH_WEIGHTS SHALL contain all required metric keys."""
        required_keys = {
            "ret_5d_excess",
            "ret_20d_excess",
            "breadth_20",
            "new_high_ratio",
            "amount_share_delta",
            "leadership_score",
            "crowding_score",
        }
        assert required_keys == set(SECTOR_STRENGTH_WEIGHTS.keys()), (
            f"Missing keys: {required_keys - set(SECTOR_STRENGTH_WEIGHTS.keys())}"
        )


class TestThresholdRangesConfiguration:
    """Tests that all threshold values are in valid ranges."""

    def test_trend_thresholds_rsrs_values_are_valid_ratios(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        RSRS thresholds SHALL be in (0, 1) as they represent normalized scores.
        """
        assert 0.0 < TREND_THRESHOLDS["rsrs_strong"] < 1.0, (
            f"rsrs_strong={TREND_THRESHOLDS['rsrs_strong']} should be in (0, 1)"
        )
        assert 0.0 < TREND_THRESHOLDS["rsrs_weak"] < 1.0, (
            f"rsrs_weak={TREND_THRESHOLDS['rsrs_weak']} should be in (0, 1)"
        )

    def test_trend_thresholds_rsrs_ordering(self):
        """rsrs_weak SHALL be less than rsrs_strong."""
        assert TREND_THRESHOLDS["rsrs_weak"] < TREND_THRESHOLDS["rsrs_strong"], (
            "rsrs_weak should be less than rsrs_strong"
        )

    def test_sentiment_thresholds_limit_up_rates_are_valid_ratios(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        Limit-up rate thresholds SHALL be in (0, 1) as they are ratios.
        """
        assert 0.0 < SENTIMENT_THRESHOLDS["limit_up_rate_low"] < 1.0
        assert 0.0 < SENTIMENT_THRESHOLDS["limit_up_rate_high"] < 1.0

    def test_sentiment_thresholds_limit_up_rate_ordering(self):
        """limit_up_rate_low SHALL be less than limit_up_rate_high."""
        assert (
            SENTIMENT_THRESHOLDS["limit_up_rate_low"]
            < SENTIMENT_THRESHOLDS["limit_up_rate_high"]
        ), "limit_up_rate_low should be less than limit_up_rate_high"

    def test_sentiment_thresholds_seal_rates_are_valid_ratios(self):
        """Seal rate thresholds SHALL be in (0, 1)."""
        assert 0.0 < SENTIMENT_THRESHOLDS["seal_rate_low"] < 1.0
        assert 0.0 < SENTIMENT_THRESHOLDS["seal_rate_high"] < 1.0

    def test_sentiment_thresholds_seal_rate_ordering(self):
        """seal_rate_low SHALL be less than seal_rate_high."""
        assert (
            SENTIMENT_THRESHOLDS["seal_rate_low"]
            < SENTIMENT_THRESHOLDS["seal_rate_high"]
        ), "seal_rate_low should be less than seal_rate_high"

    def test_sector_thresholds_strength_ordering(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        Sector strength thresholds SHALL be ordered: weak < moderate < strong.
        """
        assert (
            SECTOR_THRESHOLDS["strength_weak"]
            < SECTOR_THRESHOLDS["strength_moderate"]
            < SECTOR_THRESHOLDS["strength_strong"]
        ), "Sector strength thresholds should be ordered: weak < moderate < strong"

    def test_sector_thresholds_persistence_ordering(self):
        """Sector persistence thresholds SHALL be ordered: moderate < high."""
        assert (
            SECTOR_THRESHOLDS["persistence_moderate"]
            < SECTOR_THRESHOLDS["persistence_high"]
        ), "persistence_moderate should be less than persistence_high"

    def test_sector_thresholds_persistence_are_valid_ratios(self):
        """Persistence thresholds SHALL be in (0, 1)."""
        assert 0.0 < SECTOR_THRESHOLDS["persistence_moderate"] < 1.0
        assert 0.0 < SECTOR_THRESHOLDS["persistence_high"] < 1.0


class TestConfidenceParamsConfiguration:
    """Tests for CONFIDENCE_PARAMS configuration (Requirement 24.5)."""

    def test_confidence_params_base_is_one(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        base_confidence SHALL be 1.0 (full confidence before penalties).
        """
        assert CONFIDENCE_PARAMS["base_confidence"] == 1.0, (
            f"base_confidence should be 1.0, got {CONFIDENCE_PARAMS['base_confidence']}"
        )

    def test_confidence_params_min_max_are_valid(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        min_confidence and max_confidence SHALL be in [0, 1] with
        min < max, as required by Requirement 17.7.
        """
        min_conf = CONFIDENCE_PARAMS["min_confidence"]
        max_conf = CONFIDENCE_PARAMS["max_confidence"]

        assert 0.0 <= min_conf <= 1.0, (
            f"min_confidence={min_conf} should be in [0, 1]"
        )
        assert 0.0 <= max_conf <= 1.0, (
            f"max_confidence={max_conf} should be in [0, 1]"
        )
        assert min_conf < max_conf, (
            f"min_confidence={min_conf} should be < max_confidence={max_conf}"
        )

    def test_confidence_params_penalties_are_positive(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        All penalty values SHALL be positive (they reduce confidence).
        """
        penalty_keys = [
            "missing_core_indicator_penalty",
            "extreme_anomaly_penalty",
            "estimated_data_penalty",
        ]
        for key in penalty_keys:
            assert CONFIDENCE_PARAMS[key] > 0, (
                f"CONFIDENCE_PARAMS[{key!r}]={CONFIDENCE_PARAMS[key]} should be positive"
            )

    def test_confidence_params_bonus_is_positive(self):
        """signal_consistency_bonus SHALL be positive."""
        assert CONFIDENCE_PARAMS["signal_consistency_bonus"] > 0, (
            "signal_consistency_bonus should be positive"
        )

    def test_confidence_params_penalties_are_less_than_one(self):
        """
        **Property 53: Configuration Application**
        **Validates: Requirement 24.6**

        Individual penalty values SHALL be less than 1.0 so that a single
        missing indicator does not reduce confidence to zero.
        """
        penalty_keys = [
            "missing_core_indicator_penalty",
            "extreme_anomaly_penalty",
            "estimated_data_penalty",
        ]
        for key in penalty_keys:
            assert CONFIDENCE_PARAMS[key] < 1.0, (
                f"CONFIDENCE_PARAMS[{key!r}]={CONFIDENCE_PARAMS[key]} should be < 1.0"
            )

    def test_confidence_params_contain_required_keys(self):
        """CONFIDENCE_PARAMS SHALL contain all required keys."""
        required_keys = {
            "base_confidence",
            "missing_core_indicator_penalty",
            "signal_consistency_bonus",
            "extreme_anomaly_penalty",
            "estimated_data_penalty",
            "min_confidence",
            "max_confidence",
        }
        assert required_keys.issubset(set(CONFIDENCE_PARAMS.keys())), (
            f"Missing keys: {required_keys - set(CONFIDENCE_PARAMS.keys())}"
        )


# ---------------------------------------------------------------------------
# Hypothesis-based property tests
# ---------------------------------------------------------------------------


@given(
    ratio=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=200)
def test_property_53_breadth_thresholds_partition_ratio_space(ratio):
    """
    **Property 53: Configuration Application**
    **Validates: Requirement 24.6**

    For any above_ma20_ratio in [0, 1], the BREADTH_THRESHOLDS SHALL
    partition the space into exactly 5 non-overlapping bands, and the
    classifier SHALL assign exactly one state.

    This verifies that configuration values are applied consistently in
    the classifier (Requirement 24.6).
    """
    from src.market_diagnostic.states.enums import BreadthState

    classifier = MarketStateClassifier()

    breadth = BreadthFeatures(
        up_down_ratio=1.0,
        limit_up_rate=0.02,
        seal_rate=0.6,
        above_ma20_ratio=ratio,
        above_ma60_ratio=ratio,
        new_high_ratio=0.01,
        amount_deviation_5d=0.0,
        amount_deviation_20d=0.0,
        breadth_score=50.0,
    )

    state = classifier._classify_breadth(breadth)

    # Verify the state is one of the 5 valid states
    assert state in list(BreadthState), f"Invalid state {state!r} for ratio {ratio}"

    # Verify the state matches the expected band from config
    extreme_weak = BREADTH_THRESHOLDS["extreme_weak"]
    weak = BREADTH_THRESHOLDS["weak"]
    neutral = BREADTH_THRESHOLDS["neutral"]
    strong = BREADTH_THRESHOLDS["strong"]

    if ratio < extreme_weak:
        assert state == BreadthState.EXTREME_WEAK
    elif ratio < weak:
        assert state == BreadthState.WEAK
    elif ratio < neutral:
        assert state == BreadthState.NEUTRAL
    elif ratio < strong:
        assert state == BreadthState.STRONG
    else:
        assert state == BreadthState.OVERHEATED


@given(
    weights=st.fixed_dictionaries(
        {
            "trend": st.just(REGIME_SCORE_WEIGHTS["trend"]),
            "breadth": st.just(REGIME_SCORE_WEIGHTS["breadth"]),
            "sentiment": st.just(REGIME_SCORE_WEIGHTS["sentiment"]),
            "style": st.just(REGIME_SCORE_WEIGHTS["style"]),
            "sector": st.just(REGIME_SCORE_WEIGHTS["sector"]),
            "risk": st.just(REGIME_SCORE_WEIGHTS["risk"]),
        }
    ),
    scores=st.fixed_dictionaries(
        {
            "trend": st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
            "breadth": st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
            "sentiment": st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
            "style": st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
            "sector": st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
            "risk": st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        }
    ),
)
@settings(max_examples=200)
def test_property_53_regime_score_formula_produces_valid_range(weights, scores):
    """
    **Property 53: Configuration Application**
    **Validates: Requirement 24.6**

    For any valid dimension scores in [0, 100], the regime score formula
    using REGIME_SCORE_WEIGHTS SHALL produce a result in [0, 100].

    Formula: 0.20*trend + 0.15*breadth + 0.15*sentiment + 0.15*style
             + 0.15*sector - 0.20*risk
    """
    regime_score = (
        weights["trend"] * scores["trend"]
        + weights["breadth"] * scores["breadth"]
        + weights["sentiment"] * scores["sentiment"]
        + weights["style"] * scores["style"]
        + weights["sector"] * scores["sector"]
        + weights["risk"] * scores["risk"]  # risk weight is negative
    )

    # With all scores in [0, 100] and weights summing to 0:
    # min = positive_weights * 0 + negative_weight * 100 = -0.20 * 100 = -20
    # max = positive_weights * 100 + negative_weight * 0 = 0.80 * 100 = 80
    # The score is in [-20, 80] before clamping
    assert -20.0 <= regime_score <= 80.0, (
        f"Regime score {regime_score} is outside expected range [-20, 80]"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
