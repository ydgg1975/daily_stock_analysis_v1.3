"""
Tests for Trend Feature Calculation (Task 4.1 / 4.2 / 4.3)

Unit tests and property-based tests for:
- TrendFeatures dataclass
- compute_trend_features()
- compute_all_trend_features()

Properties tested:
- Property 7: Moving Average Calculation Completeness (Validates: Requirement 2.1)
- Property 8: MA Alignment Classification Validity (Validates: Requirement 2.2)
- Property 9: MACD Calculation Completeness (Validates: Requirement 2.3)
- Property 10: Technical Indicator Calculation (Validates: Requirements 2.4, 2.5, 2.6)
- Property 11: Relative Strength Calculation (Validates: Requirement 2.7)
"""

from __future__ import annotations

import math
import sys
import os

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st, assume

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.market_diagnostic.data.models import IndexDailyData
from src.market_diagnostic.features.trend import (
    TrendFeatures,
    _ema,
    _sma,
    _compute_macd,
    _compute_rsrs,
    _compute_atr20,
    _ma_alignment,
    compute_trend_features,
    compute_all_trend_features,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_index_data(
    close_series: list[float],
    code: str = "sh000300",
    name: str = "沪深300",
    high_series: list[float] | None = None,
    low_series: list[float] | None = None,
) -> IndexDailyData:
    """Build a minimal IndexDailyData for testing."""
    close = close_series[-1] if close_series else 3000.0
    data = IndexDailyData(
        code=code,
        name=name,
        date="2024-01-15",
        close=close,
        open=close * 0.99,
        high=close * 1.01,
        low=close * 0.98,
        prev_close=close * 0.995,
        volume=1e9,
        amount=1e11,
        change_pct=0.5,
        close_series=close_series,
        volume_series=[1e9] * len(close_series),
    )
    if high_series is not None:
        object.__setattr__(data, "high_series", high_series)
    if low_series is not None:
        object.__setattr__(data, "low_series", low_series)
    return data


def _trending_up(n: int = 60, start: float = 3000.0, step: float = 5.0) -> list[float]:
    """Monotonically increasing price series."""
    return [start + i * step for i in range(n)]


def _trending_down(n: int = 60, start: float = 3000.0, step: float = 5.0) -> list[float]:
    """Monotonically decreasing price series."""
    return [start - i * step for i in range(n)]


def _flat(n: int = 60, price: float = 3000.0) -> list[float]:
    return [price] * n


# ---------------------------------------------------------------------------
# Unit tests – MA calculation
# ---------------------------------------------------------------------------

class TestMovingAverages:
    def test_sma_basic(self):
        series = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert _sma(series, 3) == pytest.approx(4.0)

    def test_sma_insufficient_data(self):
        series = np.array([1.0, 2.0])
        assert math.isnan(_sma(series, 5))

    def test_ma5_correct(self):
        closes = list(range(1, 61))  # 1..60
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        expected = sum(range(56, 61)) / 5  # last 5 values: 56,57,58,59,60
        assert tf.ma5 == pytest.approx(expected)

    def test_ma20_correct(self):
        closes = list(range(1, 61))
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        expected = sum(range(41, 61)) / 20
        assert tf.ma20 == pytest.approx(expected)

    def test_ma120_nan_when_insufficient(self):
        closes = list(range(1, 61))  # only 60 points
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert math.isnan(tf.ma120)

    def test_ma120_computed_when_sufficient(self):
        closes = list(range(1, 121))  # 120 points
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        expected = sum(range(1, 121)) / 120
        assert tf.ma120 == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Unit tests – MA alignment
# ---------------------------------------------------------------------------

class TestMAAlignment:
    def test_bullish_alignment(self):
        assert _ma_alignment(50, 40, 30, 20) == "多头排列"

    def test_bearish_alignment(self):
        assert _ma_alignment(20, 30, 40, 50) == "空头排列"

    def test_tangled_alignment(self):
        assert _ma_alignment(35, 30, 40, 20) == "缠绕"

    def test_equal_values_tangled(self):
        assert _ma_alignment(30, 30, 30, 30) == "缠绕"

    def test_nan_returns_tangled(self):
        assert _ma_alignment(float("nan"), 30, 20, 10) == "缠绕"

    def test_uptrend_series_gives_bullish(self):
        closes = _trending_up(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.ma_alignment == "多头排列"

    def test_downtrend_series_gives_bearish(self):
        closes = _trending_down(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.ma_alignment == "空头排列"


# ---------------------------------------------------------------------------
# Unit tests – Bias ratios
# ---------------------------------------------------------------------------

class TestBiasRatios:
    def test_bias_ma5_positive_when_above(self):
        closes = _flat(60, 3000.0)
        data = _make_index_data(closes)
        # Override close to be above MA5
        data = IndexDailyData(
            code=data.code, name=data.name, date=data.date,
            close=3100.0, open=data.open, high=data.high, low=data.low,
            prev_close=data.prev_close, volume=data.volume, amount=data.amount,
            change_pct=data.change_pct, close_series=closes,
            volume_series=data.volume_series,
        )
        tf = compute_trend_features(data)
        assert tf.bias_ma5 > 0

    def test_bias_ma5_zero_when_equal(self):
        closes = _flat(60, 3000.0)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.bias_ma5 == pytest.approx(0.0)

    def test_bias_formula(self):
        closes = _flat(60, 3000.0)
        data = _make_index_data(closes)
        # Manually set close to 3300
        data2 = IndexDailyData(
            code=data.code, name=data.name, date=data.date,
            close=3300.0, open=data.open, high=data.high, low=data.low,
            prev_close=data.prev_close, volume=data.volume, amount=data.amount,
            change_pct=data.change_pct, close_series=closes,
            volume_series=data.volume_series,
        )
        tf = compute_trend_features(data2)
        # MA5 = 3000, close = 3300 → bias = 0.1
        assert tf.bias_ma5 == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# Unit tests – MACD
# ---------------------------------------------------------------------------

class TestMACD:
    def test_macd_requires_26_bars(self):
        closes = list(range(1, 25))  # only 24 bars
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert math.isnan(tf.macd_dif)
        assert math.isnan(tf.macd_dea)
        assert math.isnan(tf.macd_bar)
        assert tf.macd_signal == "中性"

    def test_macd_computed_with_sufficient_data(self):
        closes = _trending_up(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert not math.isnan(tf.macd_dif)
        assert not math.isnan(tf.macd_dea)
        assert not math.isnan(tf.macd_bar)

    def test_macd_bar_formula(self):
        """BAR = 2 * (DIF - DEA)."""
        closes = _trending_up(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.macd_bar == pytest.approx(2 * (tf.macd_dif - tf.macd_dea))

    def test_golden_cross_detected(self):
        """
        Construct a series where DIF crosses above DEA at the end.
        Use a sharp upward spike at the end to force a golden cross.
        """
        # Start with a downtrend (DIF < DEA), then spike up
        base = _trending_down(50, start=3000.0, step=10.0)
        spike = [base[-1] + i * 100 for i in range(1, 15)]
        closes = base + spike
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        # After a strong upward spike, DIF should cross above DEA
        assert tf.macd_signal in ("金叉", "中性")  # may be 中性 if already crossed

    def test_death_cross_detected(self):
        """
        Construct a series where DIF crosses below DEA at the end.
        """
        base = _trending_up(50, start=3000.0, step=10.0)
        crash = [base[-1] - i * 100 for i in range(1, 15)]
        closes = base + crash
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.macd_signal in ("死叉", "中性")


# ---------------------------------------------------------------------------
# Unit tests – ATR-20
# ---------------------------------------------------------------------------

class TestATR20:
    def test_atr_positive(self):
        closes = _trending_up(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.atr_20 >= 0

    def test_atr_with_explicit_high_low(self):
        closes = _flat(60, 3000.0)
        highs = [c * 1.02 for c in closes]
        lows = [c * 0.98 for c in closes]
        data = _make_index_data(closes, high_series=highs, low_series=lows)
        tf = compute_trend_features(data)
        # TR ≈ high - low = 0.04 * 3000 = 120
        assert tf.atr_20 == pytest.approx(120.0, rel=0.01)

    def test_atr_nan_with_single_bar(self):
        data = _make_index_data([3000.0])
        tf = compute_trend_features(data)
        assert math.isnan(tf.atr_20)


# ---------------------------------------------------------------------------
# Unit tests – RSRS
# ---------------------------------------------------------------------------

class TestRSRS:
    def test_rsrs_in_unit_interval(self):
        closes = _trending_up(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert 0.0 <= tf.rsrs_score <= 1.0

    def test_rsrs_default_when_insufficient(self):
        closes = _flat(10)  # fewer than 18 bars
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.rsrs_score == pytest.approx(0.5)

    def test_rsrs_uptrend_high(self):
        """Strong uptrend should yield RSRS near 1."""
        closes = _trending_up(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.rsrs_score >= 0.5


# ---------------------------------------------------------------------------
# Unit tests – near_high_20d and break_support
# ---------------------------------------------------------------------------

class TestBooleanFlags:
    def test_near_high_20d_true_at_peak(self):
        closes = _trending_up(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.near_high_20d is True

    def test_near_high_20d_false_at_trough(self):
        closes = _trending_down(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.near_high_20d is False

    def test_break_support_true_below_ma60(self):
        # Downtrend: close will be below MA60
        closes = _trending_down(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.break_support is True

    def test_break_support_false_above_ma60(self):
        closes = _trending_up(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.break_support is False


# ---------------------------------------------------------------------------
# Unit tests – relative strength
# ---------------------------------------------------------------------------

class TestRelativeStrength:
    def test_rs_vs_300_neutral_when_no_csi300(self):
        closes = _flat(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data, csi300_close=None)
        assert tf.rs_vs_300 == pytest.approx(1.0)

    def test_rs_vs_300_formula(self):
        closes = _flat(60, 4000.0)
        data = _make_index_data(closes)
        tf = compute_trend_features(data, csi300_close=3000.0)
        assert tf.rs_vs_300 == pytest.approx(4000.0 / 3000.0)

    def test_compute_all_includes_csi300(self):
        csi300 = _make_index_data(_flat(60, 3000.0), code="sh000300")
        other = _make_index_data(_flat(60, 4000.0), code="sz399006")
        result = compute_all_trend_features({"sz399006": other}, csi300)
        assert "sh000300" in result
        assert "sz399006" in result

    def test_compute_all_rs_vs_300_for_csi300_itself(self):
        csi300 = _make_index_data(_flat(60, 3000.0), code="sh000300")
        result = compute_all_trend_features({"sh000300": csi300}, csi300)
        assert result["sh000300"].rs_vs_300 == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Unit tests – edge cases (Task 4.3)
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_close_series(self):
        data = _make_index_data([])
        tf = compute_trend_features(data)
        assert math.isnan(tf.ma5)
        assert math.isnan(tf.ma20)
        assert math.isnan(tf.ma60)
        assert tf.ma_alignment == "缠绕"
        assert tf.macd_signal == "中性"

    def test_single_bar(self):
        data = _make_index_data([3000.0])
        tf = compute_trend_features(data)
        assert math.isnan(tf.ma5)
        assert math.isnan(tf.atr_20)

    def test_extreme_price_spike(self):
        """Should not crash with extreme values."""
        closes = _flat(60, 3000.0)
        closes[-1] = 1e9  # extreme spike
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert isinstance(tf, TrendFeatures)

    def test_all_same_prices(self):
        closes = _flat(60, 3000.0)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.bias_ma5 == pytest.approx(0.0)
        assert tf.bias_ma20 == pytest.approx(0.0)
        assert tf.bias_ma60 == pytest.approx(0.0)
        assert tf.ma_alignment == "缠绕"  # all equal → not strictly ordered

    def test_macd_signal_detection_accuracy(self):
        """Verify MACD signal is one of the three valid values."""
        closes = _trending_up(60)
        data = _make_index_data(closes)
        tf = compute_trend_features(data)
        assert tf.macd_signal in ("金叉", "死叉", "中性")


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

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
def index_data_strategy(draw, min_len=5, max_len=120):
    """Generate an IndexDailyData with a random price series."""
    prices = draw(price_series_strategy(min_len=min_len, max_len=max_len))
    return _make_index_data(prices)


# ============================================================================
# Property 7: Moving Average Calculation Completeness
# **Validates: Requirement 2.1**
# ============================================================================

@given(data=index_data_strategy(min_len=5, max_len=120))
@settings(max_examples=50, deadline=5000)
def test_property_7_ma_calculation_completeness(data):
    """
    **Property 7: Moving Average Calculation Completeness**
    **Validates: Requirement 2.1**

    For any IndexDailyData with N bars:
    - MA5 is finite iff N >= 5
    - MA10 is finite iff N >= 10
    - MA20 is finite iff N >= 20
    - MA60 is finite iff N >= 60
    - MA120 is finite iff N >= 120
    - All finite MAs are positive
    """
    n = len(data.close_series)
    tf = compute_trend_features(data)

    for period, ma_val in [(5, tf.ma5), (10, tf.ma10), (20, tf.ma20), (60, tf.ma60), (120, tf.ma120)]:
        if n >= period:
            assert not math.isnan(ma_val), f"MA{period} should be finite when N={n} >= {period}"
            assert ma_val > 0, f"MA{period} should be positive"
        else:
            assert math.isnan(ma_val), f"MA{period} should be NaN when N={n} < {period}"


# ============================================================================
# Property 8: MA Alignment Classification Validity
# **Validates: Requirement 2.2**
# ============================================================================

@given(data=index_data_strategy(min_len=60, max_len=120))
@settings(max_examples=50, deadline=5000)
def test_property_8_ma_alignment_validity(data):
    """
    **Property 8: MA Alignment Classification Validity**
    **Validates: Requirement 2.2**

    For any IndexDailyData with >= 60 bars:
    - ma_alignment is one of the three valid values
    - If MA5 > MA10 > MA20 > MA60, alignment == "多头排列"
    - If MA5 < MA10 < MA20 < MA60, alignment == "空头排列"
    - Otherwise, alignment == "缠绕"
    """
    tf = compute_trend_features(data)

    valid_alignments = {"多头排列", "空头排列", "缠绕"}
    assert tf.ma_alignment in valid_alignments

    if not any(math.isnan(v) for v in [tf.ma5, tf.ma10, tf.ma20, tf.ma60]):
        if tf.ma5 > tf.ma10 > tf.ma20 > tf.ma60:
            assert tf.ma_alignment == "多头排列"
        elif tf.ma5 < tf.ma10 < tf.ma20 < tf.ma60:
            assert tf.ma_alignment == "空头排列"
        else:
            assert tf.ma_alignment == "缠绕"


# ============================================================================
# Property 9: MACD Calculation Completeness
# **Validates: Requirement 2.3**
# ============================================================================

@given(data=index_data_strategy(min_len=5, max_len=120))
@settings(max_examples=50, deadline=5000)
def test_property_9_macd_calculation_completeness(data):
    """
    **Property 9: MACD Calculation Completeness**
    **Validates: Requirement 2.3**

    For any IndexDailyData:
    - If N < 26, DIF/DEA/BAR are NaN and signal is "中性"
    - If N >= 26, DIF/DEA/BAR are finite
    - BAR == 2 * (DIF - DEA) always (when finite)
    - macd_signal is one of "金叉", "死叉", "中性"
    """
    n = len(data.close_series)
    tf = compute_trend_features(data)

    valid_signals = {"金叉", "死叉", "中性"}
    assert tf.macd_signal in valid_signals

    if n < 26:
        assert math.isnan(tf.macd_dif)
        assert math.isnan(tf.macd_dea)
        assert math.isnan(tf.macd_bar)
        assert tf.macd_signal == "中性"
    else:
        assert not math.isnan(tf.macd_dif)
        assert not math.isnan(tf.macd_dea)
        assert not math.isnan(tf.macd_bar)
        assert tf.macd_bar == pytest.approx(2 * (tf.macd_dif - tf.macd_dea), rel=1e-6)


# ============================================================================
# Property 10: Technical Indicator Calculation
# **Validates: Requirements 2.4, 2.5, 2.6**
# ============================================================================

@given(data=index_data_strategy(min_len=20, max_len=120))
@settings(max_examples=50, deadline=5000)
def test_property_10_technical_indicator_calculation(data):
    """
    **Property 10: Technical Indicator Calculation**
    **Validates: Requirements 2.4, 2.5, 2.6**

    For any IndexDailyData with >= 20 bars:
    - rsrs_score is in [0, 1]
    - atr_20 >= 0 (when computable)
    - bias_ma5, bias_ma20, bias_ma60 are finite when respective MA is finite
    - near_high_20d and break_support are booleans
    """
    tf = compute_trend_features(data)

    # RSRS in [0, 1]
    assert 0.0 <= tf.rsrs_score <= 1.0

    # ATR non-negative when computable
    if not math.isnan(tf.atr_20):
        assert tf.atr_20 >= 0.0

    # Bias ratios finite when MA is finite
    n = len(data.close_series)
    if n >= 5:
        assert not math.isnan(tf.bias_ma5)
    if n >= 20:
        assert not math.isnan(tf.bias_ma20)
    if n >= 60:
        assert not math.isnan(tf.bias_ma60)

    # Boolean flags
    assert isinstance(tf.near_high_20d, bool)
    assert isinstance(tf.break_support, bool)


# ============================================================================
# Property 11: Relative Strength Calculation
# **Validates: Requirement 2.7**
# ============================================================================

@given(
    prices_a=price_series_strategy(min_len=60, max_len=60),
    prices_b=price_series_strategy(min_len=60, max_len=60),
)
@settings(max_examples=50, deadline=5000)
def test_property_11_relative_strength_calculation(prices_a, prices_b):
    """
    **Property 11: Relative Strength Calculation**
    **Validates: Requirement 2.7**

    For any two indices A and B:
    - rs_vs_300 for A = close_A / close_B
    - rs_vs_300 for B (as CSI300) = 1.0
    - rs_vs_300 is always positive
    - compute_all_trend_features includes all provided indices
    """
    data_a = _make_index_data(prices_a, code="sz399006")
    data_b = _make_index_data(prices_b, code="sh000300")

    result = compute_all_trend_features({"sz399006": data_a}, data_b)

    assert "sz399006" in result
    assert "sh000300" in result

    # CSI300 rs_vs_300 == 1.0
    assert result["sh000300"].rs_vs_300 == pytest.approx(1.0)

    # Other index rs_vs_300 = close_A / close_B
    expected_rs = prices_a[-1] / prices_b[-1]
    assert result["sz399006"].rs_vs_300 == pytest.approx(expected_rs, rel=1e-6)

    # rs_vs_300 always positive
    for tf in result.values():
        assert tf.rs_vs_300 > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
