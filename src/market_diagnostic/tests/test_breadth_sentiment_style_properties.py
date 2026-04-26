"""
Tests for Breadth, Sentiment, and Style Feature Calculation (Task 5.4)

Property-based tests for:
- BreadthFeatures and compute_breadth_features()
- SentimentFeatures and compute_sentiment_features()
- StyleFeatures and compute_style_features()

Properties tested:
- Property 12: Breadth Metrics Calculation (Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6)
- Property 13: Breadth Score Range Constraint (Validates: Requirement 3.7)
- Property 14: Division by Zero Handling (Validates: Requirements 3.3, 4.1)
- Property 15: Sentiment Metrics Calculation (Validates: Requirements 4.1, 4.2, 4.3, 4.6)
- Property 16: Historical Context Calculation (Validates: Requirements 4.4, 4.5)
- Property 17: Style Relative Strength Calculation (Validates: Requirements 5.1, 5.2, 5.3)
- Property 18: Multi-Period Return Calculation (Validates: Requirements 5.4, 6.1)
- Property 19: Style Classification Validity (Validates: Requirement 5.6)
"""

from __future__ import annotations

import math
import sys
import os

import pytest
from hypothesis import given, settings, strategies as st, assume

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.market_diagnostic.data.models import MarketBreadthData, IndexDailyData
from src.market_diagnostic.features.breadth import (
    BreadthFeatures,
    compute_breadth_features,
    _safe_divide,
    _normalize,
)
from src.market_diagnostic.features.sentiment import (
    SentimentFeatures,
    compute_sentiment_features,
)
from src.market_diagnostic.features.style import (
    StyleFeatures,
    compute_style_features,
    _compute_return,
    _classify_dominant_style,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

@st.composite
def market_breadth_data_strategy(draw):
    """Generate a realistic MarketBreadthData instance."""
    up_count = draw(st.integers(min_value=0, max_value=5000))
    down_count = draw(st.integers(min_value=0, max_value=5000))
    flat_count = draw(st.integers(min_value=0, max_value=500))
    limit_up_count = draw(st.integers(min_value=0, max_value=500))
    limit_down_count = draw(st.integers(min_value=0, max_value=500))
    explode_count = draw(st.integers(min_value=0, max_value=200))
    continuous_limit_up = draw(st.integers(min_value=0, max_value=100))
    
    # Ratios between 0 and 1
    above_ma20_ratio = draw(st.floats(min_value=0.0, max_value=1.0))
    above_ma60_ratio = draw(st.floats(min_value=0.0, max_value=1.0))
    seal_rate = draw(st.floats(min_value=0.0, max_value=1.0))
    
    # Counts
    new_high_count = draw(st.integers(min_value=0, max_value=500))
    new_low_count = draw(st.integers(min_value=0, max_value=500))
    
    # Amounts in billions
    total_amount = draw(st.floats(min_value=1000.0, max_value=20000.0))
    amount_ma5 = draw(st.floats(min_value=1000.0, max_value=20000.0))
    amount_ma20 = draw(st.floats(min_value=1000.0, max_value=20000.0))
    
    return MarketBreadthData(
        date="2024-01-15",
        up_count=up_count,
        down_count=down_count,
        flat_count=flat_count,
        limit_up_count=limit_up_count,
        limit_down_count=limit_down_count,
        explode_count=explode_count,
        seal_rate=seal_rate,
        continuous_limit_up=continuous_limit_up,
        above_ma20_ratio=above_ma20_ratio,
        above_ma60_ratio=above_ma60_ratio,
        new_high_count=new_high_count,
        new_low_count=new_low_count,
        total_amount=total_amount,
        amount_ma5=amount_ma5,
        amount_ma20=amount_ma20,
    )


@st.composite
def price_series_strategy(draw, min_len=5, max_len=120):
    """Generate a realistic positive price series."""
    n = draw(st.integers(min_value=min_len, max_value=max_len))
    start = draw(st.floats(min_value=100.0, max_value=10000.0))
    changes = draw(
        st.lists(
            st.floats(min_value=-0.05, max_value=0.05),
            min_size=n - 1,
            max_size=n - 1,
        )
    )
    prices = [start]
    for c in changes:
        prices.append(max(prices[-1] * (1 + c), 0.01))
    return prices


@st.composite
def index_data_strategy(draw, code="sh000300", min_len=60, max_len=60):
    """Generate an IndexDailyData with a random price series."""
    prices = draw(price_series_strategy(min_len=min_len, max_len=max_len))
    close = prices[-1]
    amount = draw(st.floats(min_value=1e10, max_value=1e12))
    
    return IndexDailyData(
        code=code,
        name="Test Index",
        date="2024-01-15",
        close=close,
        open=close * 0.99,
        high=close * 1.01,
        low=close * 0.98,
        prev_close=close * 0.995,
        volume=1e9,
        amount=amount,
        change_pct=0.5,
        close_series=prices,
        volume_series=[1e9] * len(prices),
    )


# ---------------------------------------------------------------------------
# Property 12: Breadth Metrics Calculation
# **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
# ---------------------------------------------------------------------------

@given(data=market_breadth_data_strategy())
@settings(max_examples=100, deadline=5000)
def test_property_12_breadth_metrics_calculation(data):
    """
    **Property 12: Breadth Metrics Calculation**
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
    
    For any MarketBreadthData:
    - up_down_ratio = up_count / down_count (0 if down_count == 0)
    - limit_up_rate = limit_up_count / total_count
    - seal_rate = limit_up_count / (limit_up_count + explode_count) (0 if denominator == 0)
    - above_ma20_ratio and above_ma60_ratio are preserved from input
    - new_high_ratio = new_high_count / total_count
    - amount_deviation_5d = (total_amount - amount_ma5) / amount_ma5
    - amount_deviation_20d = (total_amount - amount_ma20) / amount_ma20
    - All metrics are finite (no NaN or inf)
    """
    features = compute_breadth_features(data)
    
    total_count = data.up_count + data.down_count + data.flat_count
    
    # Requirement 3.1: Up/down ratio
    if data.down_count == 0:
        assert features.up_down_ratio == 0.0
    else:
        expected_ratio = data.up_count / data.down_count
        assert features.up_down_ratio == pytest.approx(expected_ratio, rel=1e-6)
    
    # Requirement 3.2: Limit-up rate
    if total_count == 0:
        assert features.limit_up_rate == 0.0
    else:
        expected_rate = data.limit_up_count / total_count
        assert features.limit_up_rate == pytest.approx(expected_rate, rel=1e-6)
    
    # Requirement 3.3: Seal rate
    denominator = data.limit_up_count + data.explode_count
    if denominator == 0:
        assert features.seal_rate == 0.0
    else:
        expected_seal = data.limit_up_count / denominator
        assert features.seal_rate == pytest.approx(expected_seal, rel=1e-6)
    
    # Requirement 3.4: MA penetration ratios
    assert features.above_ma20_ratio == pytest.approx(data.above_ma20_ratio, rel=1e-6)
    assert features.above_ma60_ratio == pytest.approx(data.above_ma60_ratio, rel=1e-6)
    
    # Requirement 3.5: New high ratio
    if total_count == 0:
        assert features.new_high_ratio == 0.0
    else:
        expected_new_high = data.new_high_count / total_count
        assert features.new_high_ratio == pytest.approx(expected_new_high, rel=1e-6)
    
    # Requirement 3.6: Turnover amount deviations
    if data.amount_ma5 == 0:
        assert features.amount_deviation_5d == 0.0
    else:
        expected_dev_5d = (data.total_amount - data.amount_ma5) / data.amount_ma5
        assert features.amount_deviation_5d == pytest.approx(expected_dev_5d, rel=1e-6)
    
    if data.amount_ma20 == 0:
        assert features.amount_deviation_20d == 0.0
    else:
        expected_dev_20d = (data.total_amount - data.amount_ma20) / data.amount_ma20
        assert features.amount_deviation_20d == pytest.approx(expected_dev_20d, rel=1e-6)
    
    # All metrics are finite
    assert math.isfinite(features.up_down_ratio)
    assert math.isfinite(features.limit_up_rate)
    assert math.isfinite(features.seal_rate)
    assert math.isfinite(features.above_ma20_ratio)
    assert math.isfinite(features.above_ma60_ratio)
    assert math.isfinite(features.new_high_ratio)
    assert math.isfinite(features.amount_deviation_5d)
    assert math.isfinite(features.amount_deviation_20d)


# ---------------------------------------------------------------------------
# Property 13: Breadth Score Range Constraint
# **Validates: Requirement 3.7**
# ---------------------------------------------------------------------------

@given(data=market_breadth_data_strategy())
@settings(max_examples=100, deadline=5000)
def test_property_13_breadth_score_range_constraint(data):
    """
    **Property 13: Breadth Score Range Constraint**
    **Validates: Requirement 3.7**
    
    For any MarketBreadthData:
    - breadth_score is in [0, 100]
    - breadth_score is finite
    """
    features = compute_breadth_features(data)
    
    assert 0.0 <= features.breadth_score <= 100.0
    assert math.isfinite(features.breadth_score)


# ---------------------------------------------------------------------------
# Property 14: Division by Zero Handling
# **Validates: Requirements 3.3, 4.1**
# ---------------------------------------------------------------------------

@given(
    limit_up=st.integers(min_value=0, max_value=100),
    explode=st.integers(min_value=0, max_value=100),
    limit_down=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=100, deadline=5000)
def test_property_14_division_by_zero_handling(limit_up, explode, limit_down):
    """
    **Property 14: Division by Zero Handling**
    **Validates: Requirements 3.3, 4.1**
    
    For any combination of counts:
    - When denominator is zero, result is 0.0 (not NaN or inf)
    - seal_rate handles limit_up + explode == 0
    - limit_up_down_ratio handles limit_down == 0
    """
    # Test breadth seal_rate
    data = MarketBreadthData(
        date="2024-01-15",
        up_count=100,
        down_count=100,
        flat_count=10,
        limit_up_count=limit_up,
        limit_down_count=limit_down,
        explode_count=explode,
        seal_rate=0.5,
        continuous_limit_up=10,
        above_ma20_ratio=0.5,
        above_ma60_ratio=0.4,
        new_high_count=50,
        new_low_count=30,
        total_amount=10000.0,
        amount_ma5=9500.0,
        amount_ma20=9000.0,
    )
    
    breadth_features = compute_breadth_features(data)
    
    # Seal rate should be 0.0 when limit_up + explode == 0
    if limit_up + explode == 0:
        assert breadth_features.seal_rate == 0.0
    else:
        expected_seal = limit_up / (limit_up + explode)
        assert breadth_features.seal_rate == pytest.approx(expected_seal, rel=1e-6)
    
    # Test sentiment limit_up_down_ratio
    sentiment_features = compute_sentiment_features(data)
    
    # Limit up/down ratio should be 0.0 when limit_down == 0
    if limit_down == 0:
        assert sentiment_features.limit_up_down_ratio == 0.0
    else:
        expected_ratio = limit_up / limit_down
        assert sentiment_features.limit_up_down_ratio == pytest.approx(expected_ratio, rel=1e-6)
    
    # All results should be finite
    assert math.isfinite(breadth_features.seal_rate)
    assert math.isfinite(sentiment_features.limit_up_down_ratio)


# ---------------------------------------------------------------------------
# Property 15: Sentiment Metrics Calculation
# **Validates: Requirements 4.1, 4.2, 4.3, 4.6**
# ---------------------------------------------------------------------------

@given(data=market_breadth_data_strategy())
@settings(max_examples=100, deadline=5000)
def test_property_15_sentiment_metrics_calculation(data):
    """
    **Property 15: Sentiment Metrics Calculation**
    **Validates: Requirements 4.1, 4.2, 4.3, 4.6**
    
    For any MarketBreadthData:
    - limit_up_down_ratio = limit_up_count / limit_down_count (0 if limit_down == 0)
    - continuous_limit_up is preserved from input
    - seal_rate is preserved from input
    - sentiment_score is in [0, 100]
    - All metrics are finite
    """
    features = compute_sentiment_features(data)
    
    # Requirement 4.1: Limit-up to limit-down ratio
    if data.limit_down_count == 0:
        assert features.limit_up_down_ratio == 0.0
    else:
        expected_ratio = data.limit_up_count / data.limit_down_count
        assert features.limit_up_down_ratio == pytest.approx(expected_ratio, rel=1e-6)
    
    # Requirement 4.2: Continuous limit-up count
    assert features.continuous_limit_up == data.continuous_limit_up
    
    # Requirement 4.3: Seal rate
    assert features.seal_rate == pytest.approx(data.seal_rate, rel=1e-6)
    
    # Requirement 4.6: Composite sentiment score
    assert 0.0 <= features.sentiment_score <= 100.0
    assert math.isfinite(features.sentiment_score)
    
    # All metrics are finite
    assert math.isfinite(features.limit_up_down_ratio)
    assert math.isfinite(features.seal_rate)
    assert math.isfinite(features.turnover_zscore)


# ---------------------------------------------------------------------------
# Property 16: Historical Context Calculation
# **Validates: Requirements 4.4, 4.5**
# ---------------------------------------------------------------------------

@given(
    data=market_breadth_data_strategy(),
    next_day_premium=st.floats(min_value=-0.1, max_value=0.2),
    historical_amounts=st.lists(
        st.floats(min_value=1000.0, max_value=20000.0),
        min_size=20,
        max_size=60
    ),
)
@settings(max_examples=100, deadline=5000)
def test_property_16_historical_context_calculation(data, next_day_premium, historical_amounts):
    """
    **Property 16: Historical Context Calculation**
    **Validates: Requirements 4.4, 4.5**
    
    For any MarketBreadthData with historical context:
    - next_day_premium is preserved from input
    - turnover_zscore is finite when historical data is provided
    - turnover_zscore is 0.0 when historical data is empty
    - Z-score formula: (value - mean) / std
    """
    # Test with historical data
    features_with_hist = compute_sentiment_features(
        data,
        historical_amounts=historical_amounts,
        next_day_premium=next_day_premium
    )
    
    # Requirement 4.4: Next-day premium
    assert features_with_hist.next_day_premium == pytest.approx(next_day_premium, rel=1e-6)
    
    # Requirement 4.5: Turnover Z-score with historical data
    assert math.isfinite(features_with_hist.turnover_zscore)
    
    # Test without historical data
    features_no_hist = compute_sentiment_features(data)
    assert features_no_hist.turnover_zscore == 0.0
    
    # Test with empty historical data
    features_empty_hist = compute_sentiment_features(data, historical_amounts=[])
    assert features_empty_hist.turnover_zscore == 0.0


# ---------------------------------------------------------------------------
# Property 17: Style Relative Strength Calculation
# **Validates: Requirements 5.1, 5.2, 5.3**
# ---------------------------------------------------------------------------

@given(
    sh000016=index_data_strategy(code="sh000016"),
    sz399006=index_data_strategy(code="sz399006"),
    sh000300=index_data_strategy(code="sh000300"),
    sh000852=index_data_strategy(code="sh000852"),
    sh000905=index_data_strategy(code="sh000905"),
)
@settings(max_examples=50, deadline=5000)
def test_property_17_style_relative_strength_calculation(
    sh000016, sz399006, sh000300, sh000852, sh000905
):
    """
    **Property 17: Style Relative Strength Calculation**
    **Validates: Requirements 5.1, 5.2, 5.3**
    
    For any set of style indices:
    - rs_large_vs_small = sh000016.close / sz399006.close
    - rs_300_vs_1000 = sh000300.close / sh000852.close
    - rs_500_vs_1000 = sh000905.close / sh000852.close
    - All RS ratios are positive
    - All RS ratios are finite
    """
    index_data = {
        "sh000016": sh000016,
        "sz399006": sz399006,
        "sh000300": sh000300,
        "sh000852": sh000852,
        "sh000905": sh000905,
    }
    
    features = compute_style_features(index_data)
    
    # Requirement 5.1: Large-cap vs small-cap RS
    expected_rs_large_small = sh000016.close / sz399006.close
    assert features.rs_large_vs_small == pytest.approx(expected_rs_large_small, rel=1e-6)
    
    # Requirement 5.2: CSI300 vs CSI1000 RS
    expected_rs_300_1000 = sh000300.close / sh000852.close
    assert features.rs_300_vs_1000 == pytest.approx(expected_rs_300_1000, rel=1e-6)
    
    # Requirement 5.3: CSI500 vs CSI1000 RS
    expected_rs_500_1000 = sh000905.close / sh000852.close
    assert features.rs_500_vs_1000 == pytest.approx(expected_rs_500_1000, rel=1e-6)
    
    # All RS ratios are positive and finite
    assert features.rs_large_vs_small > 0
    assert features.rs_300_vs_1000 > 0
    assert features.rs_500_vs_1000 > 0
    assert math.isfinite(features.rs_large_vs_small)
    assert math.isfinite(features.rs_300_vs_1000)
    assert math.isfinite(features.rs_500_vs_1000)


# ---------------------------------------------------------------------------
# Property 18: Multi-Period Return Calculation
# **Validates: Requirements 5.4, 6.1**
# ---------------------------------------------------------------------------

@given(
    sh000016=index_data_strategy(code="sh000016"),
    sz399006=index_data_strategy(code="sz399006"),
    sh000300=index_data_strategy(code="sh000300"),
)
@settings(max_examples=50, deadline=5000)
def test_property_18_multi_period_return_calculation(sh000016, sz399006, sh000300):
    """
    **Property 18: Multi-Period Return Calculation**
    **Validates: Requirements 5.4, 6.1**
    
    For any set of indices with 60-day history:
    - ret_1d, ret_5d, ret_20d are calculated for each index
    - Returns are finite
    - Return formula: (current - past) / past
    - All indices have return entries
    """
    index_data = {
        "sh000016": sh000016,
        "sz399006": sz399006,
        "sh000300": sh000300,
    }
    
    features = compute_style_features(index_data)
    
    # All indices should have return entries
    for code in index_data.keys():
        assert code in features.ret_1d
        assert code in features.ret_5d
        assert code in features.ret_20d
        
        # Returns should be finite
        assert math.isfinite(features.ret_1d[code])
        assert math.isfinite(features.ret_5d[code])
        assert math.isfinite(features.ret_20d[code])
        
        # Verify return calculation for 1-day
        data = index_data[code]
        if len(data.close_series) >= 2:
            expected_ret_1d = (data.close_series[-1] - data.close_series[-2]) / data.close_series[-2]
            assert features.ret_1d[code] == pytest.approx(expected_ret_1d, rel=1e-6)


# ---------------------------------------------------------------------------
# Property 19: Style Classification Validity
# **Validates: Requirement 5.6**
# ---------------------------------------------------------------------------

@given(
    rs_large_vs_small=st.floats(min_value=0.9, max_value=1.1),
    rs_300_vs_1000=st.floats(min_value=0.9, max_value=1.1),
    rs_500_vs_1000=st.floats(min_value=0.9, max_value=1.1),
)
@settings(max_examples=100, deadline=5000)
def test_property_19_style_classification_validity(
    rs_large_vs_small, rs_300_vs_1000, rs_500_vs_1000
):
    """
    **Property 19: Style Classification Validity**
    **Validates: Requirement 5.6**
    
    For any combination of RS ratios:
    - dominant_style is one of the five valid values
    - Classification rules are applied correctly:
      * "红利防守": rs_large_vs_small > 1.02 AND rs_300_vs_1000 > 1.02
      * "大盘防守": rs_large_vs_small > 1.02 AND rs_300_vs_1000 > 1.01
      * "小盘进攻": rs_large_vs_small < 0.98 AND rs_300_vs_1000 < 0.99
      * "成长主导": rs_300_vs_1000 < 0.98
      * "风格冲突": default
    """
    result = _classify_dominant_style(rs_large_vs_small, rs_300_vs_1000, rs_500_vs_1000)
    
    valid_styles = {"大盘防守", "小盘进攻", "成长主导", "红利防守", "风格冲突"}
    assert result in valid_styles
    
    # Verify classification rules
    if rs_large_vs_small > 1.02 and rs_300_vs_1000 > 1.02:
        assert result == "红利防守"
    elif rs_large_vs_small > 1.02 and rs_300_vs_1000 > 1.01:
        assert result == "大盘防守"
    elif rs_large_vs_small < 0.98 and rs_300_vs_1000 < 0.99:
        assert result == "小盘进攻"
    elif rs_300_vs_1000 < 0.98:
        assert result == "成长主导"
    else:
        assert result == "风格冲突"


# ---------------------------------------------------------------------------
# Unit tests for edge cases
# ---------------------------------------------------------------------------

class TestBreadthEdgeCases:
    def test_all_zeros(self):
        """Test with all zero counts."""
        data = MarketBreadthData(
            date="2024-01-15",
            up_count=0,
            down_count=0,
            flat_count=0,
            limit_up_count=0,
            limit_down_count=0,
            explode_count=0,
            seal_rate=0.0,
            continuous_limit_up=0,
            above_ma20_ratio=0.0,
            above_ma60_ratio=0.0,
            new_high_count=0,
            new_low_count=0,
            total_amount=0.0,
            amount_ma5=0.0,
            amount_ma20=0.0,
        )
        
        features = compute_breadth_features(data)
        
        assert features.up_down_ratio == 0.0
        assert features.limit_up_rate == 0.0
        assert features.seal_rate == 0.0
        assert features.new_high_ratio == 0.0
        assert features.amount_deviation_5d == 0.0
        assert features.amount_deviation_20d == 0.0
        assert 0.0 <= features.breadth_score <= 100.0


class TestSentimentEdgeCases:
    def test_no_historical_data(self):
        """Test sentiment calculation without historical data."""
        data = MarketBreadthData(
            date="2024-01-15",
            up_count=100,
            down_count=100,
            flat_count=10,
            limit_up_count=10,
            limit_down_count=5,
            explode_count=2,
            seal_rate=0.8,
            continuous_limit_up=3,
            above_ma20_ratio=0.5,
            above_ma60_ratio=0.4,
            new_high_count=50,
            new_low_count=30,
            total_amount=10000.0,
            amount_ma5=9500.0,
            amount_ma20=9000.0,
        )
        
        features = compute_sentiment_features(data)
        
        assert features.turnover_zscore == 0.0
        assert features.next_day_premium == 0.0
        assert 0.0 <= features.sentiment_score <= 100.0


class TestStyleEdgeCases:
    def test_missing_indices(self):
        """Test style calculation with missing indices."""
        sh000300 = IndexDailyData(
            code="sh000300",
            name="CSI300",
            date="2024-01-15",
            close=3000.0,
            open=2990.0,
            high=3010.0,
            low=2980.0,
            prev_close=2985.0,
            volume=1e9,
            amount=1e11,
            change_pct=0.5,
            close_series=[3000.0] * 60,
            volume_series=[1e9] * 60,
        )
        
        # Only one index provided
        features = compute_style_features({"sh000300": sh000300})
        
        # Should use default values (1.0) for missing indices
        assert features.rs_large_vs_small == 1.0
        assert features.rs_300_vs_1000 == 1.0
        assert features.rs_500_vs_1000 == 1.0
        assert features.dominant_style == "风格冲突"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
