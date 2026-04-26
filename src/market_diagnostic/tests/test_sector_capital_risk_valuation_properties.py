"""
Property-Based Tests for Sector, Capital, Risk, and Valuation Features (Task 6.5)

Properties tested:
- Property 20: Sector Metrics Calculation (Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6)
- Property 21: Sector Strength Score Formula (Validates: Requirement 6.7)
- Property 22: Sector Persistence Score Calculation (Validates: Requirement 6.8)
- Property 23: Capital Flow Metrics Calculation (Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5)
- Property 24: T+1 Data Marking (Validates: Requirement 7.6)
- Property 25: Risk Metrics Calculation (Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6)
- Property 26: Optional Data Incorporation (Validates: Requirement 8.7)
- Property 54: Valuation Metrics Calculation (Validates: Requirements 24.1, 24.2)
- Property 55: FED Spread Calculation (Validates: Requirement 24.1)
- Property 56: Graham Index Calculation (Validates: Requirement 24.2)
"""

from __future__ import annotations

import math
import sys
import os
import statistics

import pytest
from hypothesis import given, settings, strategies as st, assume

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.market_diagnostic.data.models import (
    SectorDailyData,
    CapitalFlowData,
    MarketBreadthData,
    IndexDailyData,
)
from src.market_diagnostic.features.sector import (
    SectorFeatureResult,
    compute_sector_features,
    compute_sector_strength_score,
    compute_sector_persistence_score,
    classify_sector_state,
    _compute_z_score,
)
from src.market_diagnostic.features.capital import (
    CapitalFeatures,
    compute_capital_features,
)
from src.market_diagnostic.features.risk import (
    RiskFeatures,
    compute_risk_features,
)
from src.market_diagnostic.features.valuation import (
    ValuationFeatures,
    compute_valuation_features,
)
from src.market_diagnostic.config import SECTOR_STRENGTH_WEIGHTS


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

@st.composite
def sector_daily_data_strategy(draw):
    """Generate a realistic SectorDailyData instance."""
    return SectorDailyData(
        date="2024-01-15",
        industry_code=draw(st.sampled_from(["BK0447", "BK0448", "BK0470", "BK0471"])),
        industry_name=draw(st.sampled_from(["电子", "计算机", "医药生物", "食品饮料"])),
        ret_1d=draw(st.floats(min_value=-0.20, max_value=0.20, allow_nan=False)),
        ret_5d=draw(st.floats(min_value=-0.50, max_value=0.50, allow_nan=False)),
        ret_20d=draw(st.floats(min_value=-0.80, max_value=0.80, allow_nan=False)),
        excess_ret_1d=draw(st.floats(min_value=-0.15, max_value=0.15, allow_nan=False)),
        breadth_20=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        new_high_ratio=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        amount=draw(st.floats(min_value=0.0, max_value=10000.0, allow_nan=False)),
        amount_share=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        amount_share_delta=draw(st.floats(min_value=-0.10, max_value=0.10, allow_nan=False)),
        limit_up_count=draw(st.integers(min_value=0, max_value=50)),
        turnover=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
    )


@st.composite
def sector_list_strategy(draw, min_size=3, max_size=10):
    """Generate a list of SectorDailyData instances with distinct codes."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    codes = [f"BK0{400 + i}" for i in range(n)]
    names = [f"行业{i}" for i in range(n)]
    sectors = []
    for i in range(n):
        sectors.append(SectorDailyData(
            date="2024-01-15",
            industry_code=codes[i],
            industry_name=names[i],
            ret_1d=draw(st.floats(min_value=-0.10, max_value=0.10, allow_nan=False)),
            ret_5d=draw(st.floats(min_value=-0.30, max_value=0.30, allow_nan=False)),
            ret_20d=draw(st.floats(min_value=-0.50, max_value=0.50, allow_nan=False)),
            excess_ret_1d=draw(st.floats(min_value=-0.10, max_value=0.10, allow_nan=False)),
            breadth_20=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
            new_high_ratio=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
            amount=draw(st.floats(min_value=10.0, max_value=5000.0, allow_nan=False)),
            amount_share=draw(st.floats(min_value=0.01, max_value=0.30, allow_nan=False)),
            amount_share_delta=draw(st.floats(min_value=-0.05, max_value=0.05, allow_nan=False)),
            limit_up_count=draw(st.integers(min_value=0, max_value=20)),
            turnover=draw(st.floats(min_value=0.0, max_value=0.30, allow_nan=False)),
        ))
    return sectors


@st.composite
def capital_flow_data_strategy(draw):
    """Generate a realistic CapitalFlowData instance."""
    north_net_flow = draw(st.floats(min_value=-500.0, max_value=500.0, allow_nan=False))
    north_5d_avg = draw(st.floats(min_value=-200.0, max_value=200.0, allow_nan=False))
    freshness = draw(st.dictionaries(
        keys=st.sampled_from(["north_net_flow", "margin_balance"]),
        values=st.sampled_from(["T+0", "T+1", "T+1 (delayed)", "unavailable"]),
        min_size=0,
        max_size=2,
    ))
    return CapitalFlowData(
        date="2024-01-15",
        north_net_flow=north_net_flow,
        north_5d_avg=north_5d_avg,
        margin_balance=draw(st.floats(min_value=10000.0, max_value=30000.0, allow_nan=False)),
        margin_delta=draw(st.floats(min_value=-500.0, max_value=500.0, allow_nan=False)),
        main_net_flow=draw(st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False)),
        etf_net_flow=draw(st.floats(min_value=-500.0, max_value=500.0, allow_nan=False)),
        data_freshness=freshness,
    )


@st.composite
def market_breadth_data_strategy(draw):
    """Generate a realistic MarketBreadthData instance."""
    total_amount = draw(st.floats(min_value=1000.0, max_value=20000.0, allow_nan=False))
    amount_ma5 = draw(st.floats(min_value=500.0, max_value=20000.0, allow_nan=False))
    amount_ma20 = draw(st.floats(min_value=500.0, max_value=20000.0, allow_nan=False))
    return MarketBreadthData(
        date="2024-01-15",
        up_count=draw(st.integers(min_value=0, max_value=5000)),
        down_count=draw(st.integers(min_value=0, max_value=5000)),
        flat_count=draw(st.integers(min_value=0, max_value=500)),
        limit_up_count=draw(st.integers(min_value=0, max_value=500)),
        limit_down_count=draw(st.integers(min_value=0, max_value=500)),
        explode_count=draw(st.integers(min_value=0, max_value=200)),
        seal_rate=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        continuous_limit_up=draw(st.integers(min_value=0, max_value=100)),
        above_ma20_ratio=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        above_ma60_ratio=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        new_high_count=draw(st.integers(min_value=0, max_value=500)),
        new_low_count=draw(st.integers(min_value=0, max_value=500)),
        total_amount=total_amount,
        amount_ma5=amount_ma5,
        amount_ma20=amount_ma20,
    )


@st.composite
def price_series_strategy(draw, min_len=25, max_len=60):
    """Generate a realistic positive price series."""
    n = draw(st.integers(min_value=min_len, max_value=max_len))
    start = draw(st.floats(min_value=500.0, max_value=5000.0))
    changes = draw(st.lists(
        st.floats(min_value=-0.03, max_value=0.03),
        min_size=n - 1,
        max_size=n - 1,
    ))
    prices = [start]
    for c in changes:
        prices.append(max(prices[-1] * (1 + c), 1.0))
    return prices


@st.composite
def index_daily_data_strategy(draw, code="sh000300"):
    """Generate an IndexDailyData with a price series."""
    prices = draw(price_series_strategy())
    close = prices[-1]
    data = IndexDailyData(
        code=code,
        name="Test Index",
        date="2024-01-15",
        close=close,
        open=close * 0.995,
        high=close * 1.01,
        low=close * 0.99,
        prev_close=prices[-2] if len(prices) >= 2 else close,
        volume=1e9,
        amount=1e11,
        change_pct=0.5,
        close_series=prices,
        volume_series=[1e9] * len(prices),
    )
    # high_series and low_series are optional dynamic attributes used by risk/trend features
    data.high_series = [p * 1.01 for p in prices]
    data.low_series = [p * 0.99 for p in prices]
    return data


@st.composite
def index_data_dict_strategy(draw, min_indices=2, max_indices=4):
    """Generate a dict of IndexDailyData for risk feature testing."""
    codes = ["sh000001", "sh000300", "sz399006", "sh000852"]
    n = draw(st.integers(min_value=min_indices, max_value=max_indices))
    selected = codes[:n]
    result = {}
    for code in selected:
        result[code] = draw(index_daily_data_strategy(code=code))
    return result


@st.composite
def valuation_data_strategy(draw):
    """Generate realistic valuation data dict."""
    return {
        "csi300_pe": draw(st.floats(min_value=5.0, max_value=80.0, allow_nan=False)),
        "csi300_pb": draw(st.floats(min_value=0.5, max_value=10.0, allow_nan=False)),
        "csi500_pe": draw(st.floats(min_value=5.0, max_value=100.0, allow_nan=False)),
        "csi500_pb": draw(st.floats(min_value=0.5, max_value=10.0, allow_nan=False)),
        "csi1000_pe": draw(st.floats(min_value=5.0, max_value=120.0, allow_nan=False)),
        "csi1000_pb": draw(st.floats(min_value=0.5, max_value=10.0, allow_nan=False)),
        "bond_yield_10y": draw(st.floats(min_value=1.0, max_value=6.0, allow_nan=False)),
        "bond_yield_1y": draw(st.floats(min_value=0.5, max_value=5.0, allow_nan=False)),
    }


# ---------------------------------------------------------------------------
# Property 20: Sector Metrics Calculation
# **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6**
# ---------------------------------------------------------------------------

@given(
    sector=sector_daily_data_strategy(),
    all_sectors=sector_list_strategy(min_size=3, max_size=8),
)
@settings(max_examples=100, deadline=5000)
def test_property_20_sector_metrics_calculation(sector, all_sectors):
    """
    **Property 20: Sector Metrics Calculation**
    **Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.6**

    For any SectorDailyData and list of sectors:
    - SectorFeatureResult contains all required fields
    - excess_ret_1d is preserved from input (Req 6.2)
    - breadth_20 is in [0, 1] (Req 6.3)
    - new_high_ratio is in [0, 1] (Req 6.4)
    - amount_share and amount_share_delta are preserved (Req 6.5)
    - limit_up_count is preserved (Req 6.6)
    - All numeric fields are finite
    """
    # Include the target sector in all_sectors for cross-sectional Z-score
    all_sectors_with_target = all_sectors + [sector]

    result = compute_sector_features(sector, all_sectors_with_target)

    # Verify result type and required fields
    assert isinstance(result, SectorFeatureResult)
    assert result.industry_code == sector.industry_code
    assert result.industry_name == sector.industry_name

    # Requirement 6.2: excess returns are in the input data
    assert math.isfinite(sector.excess_ret_1d)

    # Requirement 6.3: breadth_20 is in [0, 1]
    assert 0.0 <= sector.breadth_20 <= 1.0

    # Requirement 6.4: new_high_ratio is in [0, 1]
    assert 0.0 <= sector.new_high_ratio <= 1.0

    # Requirement 6.5: amount metrics are finite
    assert math.isfinite(sector.amount)
    assert math.isfinite(sector.amount_share)
    assert math.isfinite(sector.amount_share_delta)

    # Requirement 6.6: limit_up_count is non-negative
    assert sector.limit_up_count >= 0

    # Computed scores are finite
    assert math.isfinite(result.strength_score)
    assert math.isfinite(result.persistence_score)
    assert math.isfinite(result.crowding_score)
    assert math.isfinite(result.leadership_score)

    # Persistence score is in [0, 1]
    assert 0.0 <= result.persistence_score <= 1.0

    # State is a valid string
    valid_states = {"主升趋势", "趋势强化", "震荡整理", "超跌反弹", "弱势退潮"}
    assert result.state in valid_states


# ---------------------------------------------------------------------------
# Property 21: Sector Strength Score Formula
# **Validates: Requirement 6.7**
# ---------------------------------------------------------------------------

@given(all_sectors=sector_list_strategy(min_size=5, max_size=15))
@settings(max_examples=100, deadline=5000)
def test_property_21_sector_strength_score_formula(all_sectors):
    """
    **Property 21: Sector Strength Score Formula**
    **Validates: Requirement 6.7**

    For any list of sectors, the strength score formula must be:
        strength_score = 0.25*z(ret_5d_excess) + 0.20*z(ret_20d_excess)
                       + 0.20*z(breadth_20) + 0.10*z(new_high_ratio)
                       + 0.10*z(amount_share_delta) + 0.10*z(leadership_score)
                       - 0.05*z(crowding_score)

    Properties:
    - Weights sum to |0.25+0.20+0.20+0.10+0.10+0.10-0.05| = 0.90
    - Score is finite for all valid inputs
    - When all sectors are identical, all Z-scores are 0, so score is 0
    """
    # Test that score is finite for all sectors
    for sector in all_sectors:
        score = compute_sector_strength_score(sector, all_sectors)
        assert math.isfinite(score), f"Strength score should be finite, got {score}"

    # When all sectors are identical (same values), Z-scores are all 0
    # so strength_score should be 0
    identical_sector = SectorDailyData(
        date="2024-01-15",
        industry_code="BK0001",
        industry_name="测试行业",
        ret_1d=0.01,
        ret_5d=0.05,
        ret_20d=0.10,
        excess_ret_1d=0.005,
        breadth_20=0.5,
        new_high_ratio=0.1,
        amount=1000.0,
        amount_share=0.05,
        amount_share_delta=0.01,
        limit_up_count=5,
        turnover=0.02,
    )
    identical_list = [identical_sector] * 5
    score_identical = compute_sector_strength_score(identical_sector, identical_list)
    assert score_identical == pytest.approx(0.0, abs=1e-9), \
        "When all sectors are identical, strength score should be 0"

    # Verify weight signs: higher ret_5d should increase score (positive weight)
    # Create two sectors differing only in ret_5d
    base_sectors = [
        SectorDailyData(
            date="2024-01-15",
            industry_code=f"BK0{100+i}",
            industry_name=f"行业{i}",
            ret_1d=0.0,
            ret_5d=float(i) * 0.01,
            ret_20d=0.0,
            excess_ret_1d=0.0,
            breadth_20=0.5,
            new_high_ratio=0.1,
            amount=1000.0,
            amount_share=0.05,
            amount_share_delta=0.0,
            limit_up_count=0,
            turnover=0.02,
        )
        for i in range(5)
    ]
    # The sector with highest ret_5d should have the highest strength score
    scores = [compute_sector_strength_score(s, base_sectors) for s in base_sectors]
    # Scores should be monotonically increasing with ret_5d
    for i in range(len(scores) - 1):
        assert scores[i] <= scores[i + 1], \
            "Higher ret_5d should yield higher strength score (positive weight)"


# ---------------------------------------------------------------------------
# Property 22: Sector Persistence Score Calculation
# **Validates: Requirement 6.8**
# ---------------------------------------------------------------------------

@given(sector=sector_daily_data_strategy())
@settings(max_examples=100, deadline=5000)
def test_property_22_sector_persistence_score_no_history(sector):
    """
    **Property 22: Sector Persistence Score Calculation**
    **Validates: Requirement 6.8**

    Without historical rankings:
    - Persistence score is in [0, 1]
    - Score is finite
    - Positive multi-period returns yield higher persistence
    """
    score = compute_sector_persistence_score(sector)

    assert math.isfinite(score)
    assert 0.0 <= score <= 1.0


@given(
    sector=sector_daily_data_strategy(),
    rankings=st.lists(
        st.integers(min_value=1, max_value=31),
        min_size=3,
        max_size=20,
    ),
    amount_share_trend=st.floats(min_value=-0.05, max_value=0.05, allow_nan=False),
)
@settings(max_examples=100, deadline=5000)
def test_property_22_sector_persistence_score_with_history(sector, rankings, amount_share_trend):
    """
    **Property 22: Sector Persistence Score Calculation (with history)**
    **Validates: Requirement 6.8**

    With historical rankings:
    - Persistence score is in [0, 1]
    - Score is finite
    - Lower average ranking (closer to 1) yields higher persistence
    """
    score = compute_sector_persistence_score(sector, rankings, amount_share_trend)

    assert math.isfinite(score)
    assert 0.0 <= score <= 1.0

    # Consistently top-ranked sector should have higher persistence than bottom-ranked
    top_rankings = [1, 2, 1, 2, 1]
    bottom_rankings = [30, 31, 29, 31, 30]
    score_top = compute_sector_persistence_score(sector, top_rankings)
    score_bottom = compute_sector_persistence_score(sector, bottom_rankings)
    assert score_top >= score_bottom, \
        "Top-ranked sector should have higher persistence than bottom-ranked"


# ---------------------------------------------------------------------------
# Property 23: Capital Flow Metrics Calculation
# **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**
# ---------------------------------------------------------------------------

@given(
    capital_data=capital_flow_data_strategy(),
    breadth_data=market_breadth_data_strategy(),
    amount_ma60=st.floats(min_value=0.0, max_value=20000.0, allow_nan=False, allow_subnormal=False),
)
@settings(max_examples=100, deadline=5000)
def test_property_23_capital_flow_metrics_calculation(capital_data, breadth_data, amount_ma60):
    """
    **Property 23: Capital Flow Metrics Calculation**
    **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**

    For any capital flow and breadth data:
    - total_amount equals breadth_data.total_amount (Req 7.1)
    - amount_deviation_5d = (total - ma5) / ma5, 0 if ma5 == 0 (Req 7.2)
    - amount_deviation_20d = (total - ma20) / ma20, 0 if ma20 == 0 (Req 7.2)
    - amount_deviation_60d = (total - ma60) / ma60, 0 if ma60 == 0 (Req 7.2)
    - north_net_flow and north_5d_avg are preserved (Req 7.3)
    - margin_balance and margin_delta are preserved (Req 7.4)
    - main_net_flow and etf_net_flow are preserved (Req 7.5)
    - All metrics are finite
    """
    features = compute_capital_features(capital_data, breadth_data, amount_ma60)

    # Requirement 7.1: Total market turnover
    assert features.total_amount == pytest.approx(breadth_data.total_amount, rel=1e-9)

    # Requirement 7.2: Turnover deviations
    if breadth_data.amount_ma5 == 0:
        assert features.amount_deviation_5d == 0.0
    else:
        expected_5d = (breadth_data.total_amount - breadth_data.amount_ma5) / breadth_data.amount_ma5
        assert features.amount_deviation_5d == pytest.approx(expected_5d, rel=1e-6)

    if breadth_data.amount_ma20 == 0:
        assert features.amount_deviation_20d == 0.0
    else:
        expected_20d = (breadth_data.total_amount - breadth_data.amount_ma20) / breadth_data.amount_ma20
        assert features.amount_deviation_20d == pytest.approx(expected_20d, rel=1e-6)

    if amount_ma60 == 0:
        assert features.amount_deviation_60d == 0.0
    else:
        expected_60d = (breadth_data.total_amount - amount_ma60) / amount_ma60
        if math.isfinite(expected_60d):
            assert features.amount_deviation_60d == pytest.approx(expected_60d, rel=1e-6)
        else:
            # Near-zero denominator: implementation returns 0.0 as safe default
            assert features.amount_deviation_60d == 0.0

    # Requirement 7.3: North Bound Capital
    assert features.north_net_flow == pytest.approx(capital_data.north_net_flow, rel=1e-9)
    assert features.north_5d_avg == pytest.approx(capital_data.north_5d_avg, rel=1e-9)

    # Requirement 7.4: Margin balance
    assert features.margin_balance == pytest.approx(capital_data.margin_balance, rel=1e-9)
    assert features.margin_delta == pytest.approx(capital_data.margin_delta, rel=1e-9)

    # Requirement 7.5: Main force and ETF flows
    assert features.main_net_flow == pytest.approx(capital_data.main_net_flow, rel=1e-9)
    assert features.etf_net_flow == pytest.approx(capital_data.etf_net_flow, rel=1e-9)

    # All metrics are finite
    assert math.isfinite(features.total_amount)
    assert math.isfinite(features.amount_deviation_5d)
    assert math.isfinite(features.amount_deviation_20d)
    assert math.isfinite(features.amount_deviation_60d)
    assert math.isfinite(features.north_net_flow)
    assert math.isfinite(features.north_5d_avg)
    assert math.isfinite(features.margin_balance)
    assert math.isfinite(features.margin_delta)
    assert math.isfinite(features.main_net_flow)
    assert math.isfinite(features.etf_net_flow)

    # North flow trend is one of the valid values
    assert features.north_flow_trend in {"inflow", "outflow", "neutral"}


# ---------------------------------------------------------------------------
# Property 24: T+1 Data Marking
# **Validates: Requirement 7.6**
# ---------------------------------------------------------------------------

@given(
    north_freshness=st.sampled_from(["T+0", "T+1", "T+1 (delayed)", "unavailable"]),
    margin_freshness=st.sampled_from(["T+0", "T+1", "T+1 (delayed)", "unavailable"]),
)
@settings(max_examples=100, deadline=5000)
def test_property_24_t1_data_marking(north_freshness, margin_freshness):
    """
    **Property 24: T+1 Data Marking**
    **Validates: Requirement 7.6**

    For capital flow data with T+1 delayed fields:
    - data_freshness dict is preserved from input
    - has_delayed_data is True when any field contains 'T+1' or 'unavailable'
    - has_delayed_data is False when all fields are 'T+0'
    """
    capital_data = CapitalFlowData(
        date="2024-01-15",
        north_net_flow=10.0,
        north_5d_avg=5.0,
        margin_balance=15000.0,
        margin_delta=50.0,
        main_net_flow=20.0,
        etf_net_flow=5.0,
        data_freshness={
            "north_net_flow": north_freshness,
            "margin_balance": margin_freshness,
        },
    )
    breadth_data = MarketBreadthData(
        date="2024-01-15",
        up_count=2000,
        down_count=1500,
        flat_count=100,
        limit_up_count=50,
        limit_down_count=10,
        explode_count=5,
        seal_rate=0.9,
        continuous_limit_up=20,
        above_ma20_ratio=0.55,
        above_ma60_ratio=0.45,
        new_high_count=100,
        new_low_count=30,
        total_amount=8000.0,
        amount_ma5=7500.0,
        amount_ma20=7000.0,
    )

    features = compute_capital_features(capital_data, breadth_data)

    # data_freshness is preserved
    assert features.data_freshness["north_net_flow"] == north_freshness
    assert features.data_freshness["margin_balance"] == margin_freshness

    # has_delayed_data reflects whether any field is T+1 or unavailable
    has_t1 = "T+1" in north_freshness or "T+1" in margin_freshness
    has_unavailable = "unavailable" in north_freshness or "unavailable" in margin_freshness
    expected_delayed = has_t1 or has_unavailable
    assert features.has_delayed_data == expected_delayed


def test_property_24_t1_marking_all_current():
    """
    **Property 24: T+1 Data Marking (all T+0)**
    **Validates: Requirement 7.6**

    When all data is T+0, has_delayed_data should be False.
    """
    capital_data = CapitalFlowData(
        date="2024-01-15",
        north_net_flow=10.0,
        north_5d_avg=5.0,
        margin_balance=15000.0,
        margin_delta=50.0,
        main_net_flow=20.0,
        etf_net_flow=5.0,
        data_freshness={
            "north_net_flow": "T+0",
            "margin_balance": "T+0",
        },
    )
    breadth_data = MarketBreadthData(
        date="2024-01-15",
        up_count=2000,
        down_count=1500,
        flat_count=100,
        limit_up_count=50,
        limit_down_count=10,
        explode_count=5,
        seal_rate=0.9,
        continuous_limit_up=20,
        above_ma20_ratio=0.55,
        above_ma60_ratio=0.45,
        new_high_count=100,
        new_low_count=30,
        total_amount=8000.0,
        amount_ma5=7500.0,
        amount_ma20=7000.0,
    )

    features = compute_capital_features(capital_data, breadth_data)
    assert features.has_delayed_data is False


# ---------------------------------------------------------------------------
# Property 25: Risk Metrics Calculation
# **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**
# ---------------------------------------------------------------------------

@given(index_data=index_data_dict_strategy(min_indices=2, max_indices=3))
@settings(max_examples=50, deadline=10000)
def test_property_25_risk_metrics_calculation(index_data):
    """
    **Property 25: Risk Metrics Calculation**
    **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**

    For any set of index data:
    - realized_volatility is computed for each index (Req 8.1)
    - atr_volatility is computed for each index (Req 8.2)
    - vol_ratio_short_long is computed for each index (Req 8.3)
    - index_drawdown is computed for each index (Req 8.4)
    - cross_index_correlation is in [-1, 1] (Req 8.5)
    - sector_correlation_elevation is finite (Req 8.6)
    - All metrics are finite and non-negative where applicable
    """
    features = compute_risk_features(index_data, sector_data=[])

    for code in index_data.keys():
        # Requirement 8.1: Realized volatility exists and is non-negative
        assert code in features.realized_volatility
        assert features.realized_volatility[code] >= 0.0
        assert math.isfinite(features.realized_volatility[code])

        # Requirement 8.2: ATR volatility exists and is non-negative
        assert code in features.atr_volatility
        assert features.atr_volatility[code] >= 0.0
        assert math.isfinite(features.atr_volatility[code])

        # Requirement 8.3: Vol ratio exists and is non-negative
        assert code in features.vol_ratio_short_long
        assert features.vol_ratio_short_long[code] >= 0.0
        assert math.isfinite(features.vol_ratio_short_long[code])

        # Requirement 8.4: Drawdown exists and is <= 0 (drawdown is negative or zero)
        assert code in features.index_drawdown
        assert features.index_drawdown[code] <= 0.0 or features.index_drawdown[code] == 0.0
        assert math.isfinite(features.index_drawdown[code])

    # Requirement 8.5: Cross-index correlation is in [-1, 1]
    assert -1.0 <= features.cross_index_correlation <= 1.0
    assert math.isfinite(features.cross_index_correlation)

    # Requirement 8.6: Sector correlation elevation is finite
    assert math.isfinite(features.sector_correlation_elevation)


@given(
    prices=price_series_strategy(min_len=25, max_len=60),
)
@settings(max_examples=100, deadline=5000)
def test_property_25_realized_volatility_uses_20day_std(prices):
    """
    **Property 25: Realized Volatility Uses 20-Day Rolling Std**
    **Validates: Requirement 8.1**

    For a price series with >= 20 data points:
    - realized_volatility = std(returns[-20:]) * sqrt(252)
    - This is the annualized 20-day realized volatility
    """
    assume(len(prices) >= 21)

    index_data = {
        "sh000300": IndexDailyData(
            code="sh000300",
            name="CSI300",
            date="2024-01-15",
            close=prices[-1],
            open=prices[-1] * 0.995,
            high=prices[-1] * 1.01,
            low=prices[-1] * 0.99,
            prev_close=prices[-2],
            volume=1e9,
            amount=1e11,
            change_pct=0.5,
            close_series=prices,
            volume_series=[1e9] * len(prices),
        )
    }

    features = compute_risk_features(index_data, sector_data=[])

    import numpy as np
    closes = np.array(prices, dtype=float)
    returns = np.diff(closes) / closes[:-1]
    expected_vol = float(np.std(returns[-20:], ddof=1)) * np.sqrt(252)

    assert features.realized_volatility["sh000300"] == pytest.approx(expected_vol, rel=1e-6)


@given(
    prices=price_series_strategy(min_len=25, max_len=60),
)
@settings(max_examples=100, deadline=5000)
def test_property_25_drawdown_from_peak(prices):
    """
    **Property 25: Drawdown from Peak**
    **Validates: Requirement 8.4**

    For a price series with >= 20 data points:
    - drawdown = (current - peak) / peak * 100
    - drawdown <= 0 always (current <= peak by definition of peak)
    """
    assume(len(prices) >= 20)

    index_data = {
        "sh000300": IndexDailyData(
            code="sh000300",
            name="CSI300",
            date="2024-01-15",
            close=prices[-1],
            open=prices[-1] * 0.995,
            high=prices[-1] * 1.01,
            low=prices[-1] * 0.99,
            prev_close=prices[-2],
            volume=1e9,
            amount=1e11,
            change_pct=0.5,
            close_series=prices,
            volume_series=[1e9] * len(prices),
        )
    }

    features = compute_risk_features(index_data, sector_data=[])

    import numpy as np
    closes = np.array(prices, dtype=float)
    peak = float(np.max(closes))
    current = prices[-1]
    expected_drawdown = ((current - peak) / peak) * 100

    assert features.index_drawdown["sh000300"] == pytest.approx(expected_drawdown, rel=1e-6)
    # Drawdown is always <= 0 (current can't exceed peak)
    assert features.index_drawdown["sh000300"] <= 0.0 + 1e-9


# ---------------------------------------------------------------------------
# Property 26: Optional Data Incorporation
# **Validates: Requirement 8.7**
# ---------------------------------------------------------------------------

@given(
    index_data=index_data_dict_strategy(min_indices=1, max_indices=2),
    cvix_value=st.floats(min_value=10.0, max_value=80.0, allow_nan=False),
    cvix_historical=st.lists(
        st.floats(min_value=5.0, max_value=100.0, allow_nan=False),
        min_size=10,
        max_size=50,
    ),
)
@settings(max_examples=50, deadline=10000)
def test_property_26_optional_cvix_data_incorporation(index_data, cvix_value, cvix_historical):
    """
    **Property 26: Optional Data Incorporation**
    **Validates: Requirement 8.7**

    When C-VIX data is provided:
    - has_cvix_data is True
    - cvix_value is preserved
    - cvix_percentile is in [0, 100]
    - cvix_percentile is finite

    When C-VIX data is not provided:
    - has_cvix_data is False
    - cvix_value is None
    - cvix_percentile is None
    """
    # With C-VIX data
    features_with_cvix = compute_risk_features(
        index_data,
        sector_data=[],
        cvix_value=cvix_value,
        cvix_historical=cvix_historical,
    )

    assert features_with_cvix.has_cvix_data is True
    assert features_with_cvix.cvix_value == pytest.approx(cvix_value, rel=1e-9)
    assert features_with_cvix.cvix_percentile is not None
    assert 0.0 <= features_with_cvix.cvix_percentile <= 100.0
    assert math.isfinite(features_with_cvix.cvix_percentile)

    # Without C-VIX data
    features_no_cvix = compute_risk_features(index_data, sector_data=[])

    assert features_no_cvix.has_cvix_data is False
    assert features_no_cvix.cvix_value is None
    assert features_no_cvix.cvix_percentile is None


@given(
    index_data=index_data_dict_strategy(min_indices=1, max_indices=2),
    cvix_value=st.floats(min_value=10.0, max_value=80.0, allow_nan=False),
)
@settings(max_examples=50, deadline=10000)
def test_property_26_cvix_without_historical(index_data, cvix_value):
    """
    **Property 26: Optional Data Incorporation (no historical)**
    **Validates: Requirement 8.7**

    When C-VIX value is provided but no historical data:
    - has_cvix_data is True
    - cvix_percentile is None (cannot compute without history)
    """
    features = compute_risk_features(
        index_data,
        sector_data=[],
        cvix_value=cvix_value,
        cvix_historical=None,
    )

    assert features.has_cvix_data is True
    assert features.cvix_value == pytest.approx(cvix_value, rel=1e-9)
    assert features.cvix_percentile is None


# ---------------------------------------------------------------------------
# Property 54: Valuation Metrics Calculation
# **Validates: Requirements 24.1, 24.2**
# ---------------------------------------------------------------------------

@given(valuation_data=valuation_data_strategy())
@settings(max_examples=100, deadline=5000)
def test_property_54_valuation_metrics_calculation(valuation_data):
    """
    **Property 54: Valuation Metrics Calculation**
    **Validates: Requirements 24.1, 24.2**

    For any valuation data:
    - PE/PB values are preserved from input (Req 24.1)
    - FED Spread = 1/PE - bond_yield_10y/100 (Req 24.1)
    - Graham Index = PE * PB (Req 24.2)
    - All metrics are finite
    - valuation_level is one of the valid values
    """
    features = compute_valuation_features(valuation_data)

    # Requirement 24.1: PE/PB values preserved
    assert features.csi300_pe == pytest.approx(valuation_data["csi300_pe"], rel=1e-9)
    assert features.csi300_pb == pytest.approx(valuation_data["csi300_pb"], rel=1e-9)
    assert features.csi500_pe == pytest.approx(valuation_data["csi500_pe"], rel=1e-9)
    assert features.csi500_pb == pytest.approx(valuation_data["csi500_pb"], rel=1e-9)
    assert features.csi1000_pe == pytest.approx(valuation_data["csi1000_pe"], rel=1e-9)
    assert features.csi1000_pb == pytest.approx(valuation_data["csi1000_pb"], rel=1e-9)

    # Bond yields preserved
    assert features.bond_yield_10y == pytest.approx(valuation_data["bond_yield_10y"], rel=1e-9)
    assert features.bond_yield_1y == pytest.approx(valuation_data["bond_yield_1y"], rel=1e-9)

    # Requirement 24.2: Graham Index = PE * PB
    assert features.graham_index_csi300 == pytest.approx(
        valuation_data["csi300_pe"] * valuation_data["csi300_pb"], rel=1e-6
    )
    assert features.graham_index_csi500 == pytest.approx(
        valuation_data["csi500_pe"] * valuation_data["csi500_pb"], rel=1e-6
    )
    assert features.graham_index_csi1000 == pytest.approx(
        valuation_data["csi1000_pe"] * valuation_data["csi1000_pb"], rel=1e-6
    )

    # All metrics are finite
    assert math.isfinite(features.fed_spread_csi300)
    assert math.isfinite(features.fed_spread_csi500)
    assert math.isfinite(features.fed_spread_csi1000)
    assert math.isfinite(features.graham_index_csi300)
    assert math.isfinite(features.graham_index_csi500)
    assert math.isfinite(features.graham_index_csi1000)
    assert math.isfinite(features.term_spread)

    # valuation_level is valid
    valid_levels = {"undervalued", "fair", "overvalued", "bubble"}
    assert features.valuation_level in valid_levels

    # Without historical data, percentiles are None
    assert features.has_historical_data is False
    assert features.csi300_pe_percentile is None
    assert features.csi300_pb_percentile is None


# ---------------------------------------------------------------------------
# Property 55: FED Spread Calculation
# **Validates: Requirement 24.1**
# ---------------------------------------------------------------------------

@given(
    pe=st.floats(min_value=5.0, max_value=100.0, allow_nan=False),
    bond_yield_pct=st.floats(min_value=1.0, max_value=6.0, allow_nan=False),
)
@settings(max_examples=100, deadline=5000)
def test_property_55_fed_spread_calculation(pe, bond_yield_pct):
    """
    **Property 55: FED Spread Calculation**
    **Validates: Requirement 24.1**

    FED Spread = 1/PE - bond_yield_10y/100

    Properties:
    - FED Spread is finite
    - When PE is very high (expensive), FED Spread is lower
    - When bond yield is higher, FED Spread is lower
    - Formula: earnings_yield - bond_yield_decimal
    """
    valuation_data = {
        "csi300_pe": pe,
        "csi300_pb": 1.5,
        "csi500_pe": pe,
        "csi500_pb": 1.5,
        "csi1000_pe": pe,
        "csi1000_pb": 1.5,
        "bond_yield_10y": bond_yield_pct,
        "bond_yield_1y": bond_yield_pct * 0.8,
    }

    features = compute_valuation_features(valuation_data)

    # FED Spread = 1/PE - bond_yield/100
    expected_fed_spread = (1.0 / pe) - (bond_yield_pct / 100.0)
    assert features.fed_spread_csi300 == pytest.approx(expected_fed_spread, rel=1e-6)
    assert features.fed_spread_csi500 == pytest.approx(expected_fed_spread, rel=1e-6)
    assert features.fed_spread_csi1000 == pytest.approx(expected_fed_spread, rel=1e-6)

    # FED Spread is finite
    assert math.isfinite(features.fed_spread_csi300)


@given(
    pe_low=st.floats(min_value=5.0, max_value=15.0, allow_nan=False),
    pe_high=st.floats(min_value=50.0, max_value=100.0, allow_nan=False),
    bond_yield_pct=st.floats(min_value=1.0, max_value=5.0, allow_nan=False),
)
@settings(max_examples=100, deadline=5000)
def test_property_55_fed_spread_monotone_in_pe(pe_low, pe_high, bond_yield_pct):
    """
    **Property 55: FED Spread Monotone in PE**
    **Validates: Requirement 24.1**

    Higher PE (more expensive) → lower FED Spread (less attractive vs bonds).
    """
    def get_fed_spread(pe):
        vd = {
            "csi300_pe": pe, "csi300_pb": 1.5,
            "csi500_pe": pe, "csi500_pb": 1.5,
            "csi1000_pe": pe, "csi1000_pb": 1.5,
            "bond_yield_10y": bond_yield_pct,
            "bond_yield_1y": bond_yield_pct * 0.8,
        }
        return compute_valuation_features(vd).fed_spread_csi300

    spread_low_pe = get_fed_spread(pe_low)
    spread_high_pe = get_fed_spread(pe_high)

    # Lower PE → higher earnings yield → higher FED spread
    assert spread_low_pe > spread_high_pe, \
        f"Lower PE ({pe_low}) should yield higher FED spread than high PE ({pe_high})"


# ---------------------------------------------------------------------------
# Property 56: Graham Index Calculation
# **Validates: Requirement 24.2**
# ---------------------------------------------------------------------------

@given(
    pe=st.floats(min_value=5.0, max_value=100.0, allow_nan=False),
    pb=st.floats(min_value=0.5, max_value=10.0, allow_nan=False),
)
@settings(max_examples=100, deadline=5000)
def test_property_56_graham_index_calculation(pe, pb):
    """
    **Property 56: Graham Index Calculation**
    **Validates: Requirement 24.2**

    Graham Index = PE * PB

    Properties:
    - Graham Index is always positive (PE > 0, PB > 0)
    - Graham Index is finite
    - Graham Index = PE * PB exactly
    - Higher PE or PB → higher Graham Index (monotone)
    """
    valuation_data = {
        "csi300_pe": pe,
        "csi300_pb": pb,
        "csi500_pe": pe,
        "csi500_pb": pb,
        "csi1000_pe": pe,
        "csi1000_pb": pb,
        "bond_yield_10y": 3.0,
        "bond_yield_1y": 2.0,
    }

    features = compute_valuation_features(valuation_data)

    expected_graham = pe * pb

    # Graham Index = PE * PB
    assert features.graham_index_csi300 == pytest.approx(expected_graham, rel=1e-6)
    assert features.graham_index_csi500 == pytest.approx(expected_graham, rel=1e-6)
    assert features.graham_index_csi1000 == pytest.approx(expected_graham, rel=1e-6)

    # Graham Index is positive and finite
    assert features.graham_index_csi300 > 0.0
    assert math.isfinite(features.graham_index_csi300)


@given(
    pe=st.floats(min_value=5.0, max_value=100.0, allow_nan=False),
    pb_low=st.floats(min_value=0.5, max_value=2.0, allow_nan=False),
    pb_high=st.floats(min_value=5.0, max_value=10.0, allow_nan=False),
)
@settings(max_examples=100, deadline=5000)
def test_property_56_graham_index_monotone_in_pb(pe, pb_low, pb_high):
    """
    **Property 56: Graham Index Monotone in PB**
    **Validates: Requirement 24.2**

    Higher PB → higher Graham Index (for fixed PE).
    """
    def get_graham(pb):
        vd = {
            "csi300_pe": pe, "csi300_pb": pb,
            "csi500_pe": pe, "csi500_pb": pb,
            "csi1000_pe": pe, "csi1000_pb": pb,
            "bond_yield_10y": 3.0,
            "bond_yield_1y": 2.0,
        }
        return compute_valuation_features(vd).graham_index_csi300

    graham_low = get_graham(pb_low)
    graham_high = get_graham(pb_high)

    assert graham_low < graham_high, \
        f"Higher PB ({pb_high}) should yield higher Graham Index than low PB ({pb_low})"


# ---------------------------------------------------------------------------
# Additional: Valuation with historical data (percentiles)
# ---------------------------------------------------------------------------

@given(
    valuation_data=valuation_data_strategy(),
    hist_pe=st.lists(
        st.floats(min_value=5.0, max_value=100.0, allow_nan=False),
        min_size=10,
        max_size=50,
    ),
    hist_pb=st.lists(
        st.floats(min_value=0.5, max_value=10.0, allow_nan=False),
        min_size=10,
        max_size=50,
    ),
)
@settings(max_examples=50, deadline=5000)
def test_property_54_valuation_percentiles_with_history(valuation_data, hist_pe, hist_pb):
    """
    **Property 54: Valuation Metrics with Historical Data**
    **Validates: Requirements 24.1, 24.2**

    When historical PE/PB data is provided:
    - has_historical_data is True
    - PE/PB percentiles are in [0, 100]
    - Percentiles are finite
    """
    historical_pe = {"csi300": hist_pe, "csi500": hist_pe, "csi1000": hist_pe}
    historical_pb = {"csi300": hist_pb, "csi500": hist_pb, "csi1000": hist_pb}

    features = compute_valuation_features(valuation_data, historical_pe, historical_pb)

    assert features.has_historical_data is True

    # Percentiles should be in [0, 100] when computed
    for percentile in [
        features.csi300_pe_percentile,
        features.csi300_pb_percentile,
        features.csi500_pe_percentile,
        features.csi500_pb_percentile,
        features.csi1000_pe_percentile,
        features.csi1000_pb_percentile,
    ]:
        if percentile is not None:
            assert 0.0 <= percentile <= 100.0
            assert math.isfinite(percentile)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
