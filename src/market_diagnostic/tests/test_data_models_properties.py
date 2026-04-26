"""
Property-Based Tests for Data Models

Task 1.1: Write property tests for data models
Property 2: Data Structure Completeness
Validates: Requirement 1.3

This test validates that all data model instances contain complete,
non-null required fields as specified in the design.
"""

import pytest
from hypothesis import given, strategies as st
from dataclasses import fields
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.market_diagnostic.data.models import (
    IndexDailyData,
    MarketBreadthData,
    SectorDailyData,
    CapitalFlowData
)


# Strategy generators for data models
@st.composite
def market_breadth_data_strategy(draw):
    """
    Generate valid MarketBreadthData instances.
    
    **Validates: Requirement 1.3**
    
    All required fields must be present with non-null values.
    """
    return MarketBreadthData(
        date=draw(st.dates().map(lambda d: d.strftime("%Y-%m-%d"))),
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
        total_amount=draw(st.floats(min_value=0.0, max_value=100000.0, allow_nan=False)),
        amount_ma5=draw(st.floats(min_value=0.0, max_value=100000.0, allow_nan=False)),
        amount_ma20=draw(st.floats(min_value=0.0, max_value=100000.0, allow_nan=False))
    )


@st.composite
def index_daily_data_strategy(draw):
    """Generate valid IndexDailyData instances."""
    close = draw(st.floats(min_value=1.0, max_value=10000.0, allow_nan=False))
    open_price = draw(st.floats(min_value=1.0, max_value=10000.0, allow_nan=False))
    high = max(close, open_price) + draw(st.floats(min_value=0.0, max_value=100.0))
    low = min(close, open_price) - draw(st.floats(min_value=0.0, max_value=100.0))
    prev_close = draw(st.floats(min_value=1.0, max_value=10000.0, allow_nan=False))
    
    return IndexDailyData(
        code=draw(st.sampled_from(["sh000001", "sz399001", "sz399006", "sh000300"])),
        name=draw(st.sampled_from(["上证指数", "深证成指", "创业板指", "沪深300"])),
        date=draw(st.dates().map(lambda d: d.strftime("%Y-%m-%d"))),
        close=close,
        open=open_price,
        high=high,
        low=low,
        prev_close=prev_close,
        volume=draw(st.floats(min_value=0.0, max_value=1e12, allow_nan=False)),
        amount=draw(st.floats(min_value=0.0, max_value=1e15, allow_nan=False)),
        change_pct=((close - prev_close) / prev_close) * 100,
        close_series=draw(st.lists(
            st.floats(min_value=1.0, max_value=10000.0, allow_nan=False),
            min_size=0,
            max_size=120
        )),
        volume_series=draw(st.lists(
            st.floats(min_value=0.0, max_value=1e12, allow_nan=False),
            min_size=0,
            max_size=120
        ))
    )


@st.composite
def sector_daily_data_strategy(draw):
    """Generate valid SectorDailyData instances."""
    return SectorDailyData(
        date=draw(st.dates().map(lambda d: d.strftime("%Y-%m-%d"))),
        industry_code=draw(st.text(min_size=6, max_size=6, alphabet="BK0123456789")),
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
        limit_up_count=draw(st.integers(min_value=0, max_value=100)),
        turnover=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    )


@st.composite
def capital_flow_data_strategy(draw):
    """Generate valid CapitalFlowData instances."""
    return CapitalFlowData(
        date=draw(st.dates().map(lambda d: d.strftime("%Y-%m-%d"))),
        north_net_flow=draw(st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False)),
        north_5d_avg=draw(st.floats(min_value=-500.0, max_value=500.0, allow_nan=False)),
        margin_balance=draw(st.floats(min_value=10000.0, max_value=30000.0, allow_nan=False)),
        margin_delta=draw(st.floats(min_value=-500.0, max_value=500.0, allow_nan=False)),
        main_net_flow=draw(st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False)),
        etf_net_flow=draw(st.floats(min_value=-500.0, max_value=500.0, allow_nan=False)),
        data_freshness=draw(st.dictionaries(
            keys=st.sampled_from(["north_net_flow", "margin_balance", "main_net_flow"]),
            values=st.sampled_from(["T+0", "T+1", "T+2"])
        ))
    )


# Property 2: Data Structure Completeness
@given(data=market_breadth_data_strategy())
def test_property_market_breadth_data_completeness(data):
    """
    **Property 2: Data Structure Completeness**
    **Validates: Requirement 1.3**
    
    For any market breadth data instance, all required fields SHALL be present
    with non-null values.
    
    Required fields per Requirement 1.3:
    - up_count, down_count, flat_count
    - limit_up_count, limit_down_count, explode_count
    - seal_rate, continuous_limit_up
    - above_ma20_ratio, above_ma60_ratio
    - new_high_count, new_low_count
    - total_amount, amount_ma5, amount_ma20
    """
    # Verify all required fields are present
    required_fields = {
        "date", "up_count", "down_count", "flat_count",
        "limit_up_count", "limit_down_count", "explode_count",
        "seal_rate", "continuous_limit_up",
        "above_ma20_ratio", "above_ma60_ratio",
        "new_high_count", "new_low_count",
        "total_amount", "amount_ma5", "amount_ma20"
    }
    
    model_fields = {f.name for f in fields(MarketBreadthData)}
    assert required_fields.issubset(model_fields), \
        f"Missing required fields: {required_fields - model_fields}"
    
    # Verify all fields have non-null values
    for field_name in required_fields:
        field_value = getattr(data, field_name)
        assert field_value is not None, f"Field {field_name} should not be None"
    
    # Verify numeric fields are valid (not NaN)
    numeric_fields = [
        "up_count", "down_count", "flat_count",
        "limit_up_count", "limit_down_count", "explode_count",
        "seal_rate", "continuous_limit_up",
        "above_ma20_ratio", "above_ma60_ratio",
        "new_high_count", "new_low_count",
        "total_amount", "amount_ma5", "amount_ma20"
    ]
    
    for field_name in numeric_fields:
        field_value = getattr(data, field_name)
        if isinstance(field_value, float):
            import math
            assert not math.isnan(field_value), \
                f"Field {field_name} should not be NaN"


@given(data=index_daily_data_strategy())
def test_property_index_daily_data_completeness(data):
    """
    Verify IndexDailyData structure completeness.
    
    All required fields must be present with non-null values.
    """
    required_fields = {
        "code", "name", "date", "close", "open", "high", "low",
        "prev_close", "volume", "amount", "change_pct",
        "close_series", "volume_series"
    }
    
    model_fields = {f.name for f in fields(IndexDailyData)}
    assert required_fields.issubset(model_fields)
    
    # Verify all fields have non-null values
    for field_name in required_fields:
        field_value = getattr(data, field_name)
        assert field_value is not None, f"Field {field_name} should not be None"
    
    # Verify price relationships
    assert data.high >= data.close, "High should be >= close"
    assert data.high >= data.open, "High should be >= open"
    assert data.low <= data.close, "Low should be <= close"
    assert data.low <= data.open, "Low should be <= open"


@given(data=sector_daily_data_strategy())
def test_property_sector_daily_data_completeness(data):
    """
    Verify SectorDailyData structure completeness.
    
    All required fields must be present with non-null values.
    """
    required_fields = {
        "date", "industry_code", "industry_name",
        "ret_1d", "ret_5d", "ret_20d", "excess_ret_1d",
        "breadth_20", "new_high_ratio", "amount", "amount_share",
        "amount_share_delta", "limit_up_count", "turnover"
    }
    
    model_fields = {f.name for f in fields(SectorDailyData)}
    assert required_fields.issubset(model_fields)
    
    # Verify all fields have non-null values
    for field_name in required_fields:
        field_value = getattr(data, field_name)
        assert field_value is not None, f"Field {field_name} should not be None"
    
    # Verify ratio fields are in valid range [0, 1]
    assert 0.0 <= data.breadth_20 <= 1.0, "breadth_20 should be in [0, 1]"
    assert 0.0 <= data.new_high_ratio <= 1.0, "new_high_ratio should be in [0, 1]"
    assert 0.0 <= data.amount_share <= 1.0, "amount_share should be in [0, 1]"
    assert 0.0 <= data.turnover <= 1.0, "turnover should be in [0, 1]"


@given(data=capital_flow_data_strategy())
def test_property_capital_flow_data_completeness(data):
    """
    **Property 4: Capital Flow Data Structure**
    **Validates: Requirement 1.5**
    
    For any capital flow data instance, all required fields SHALL be present
    with appropriate values or null markers.
    """
    required_fields = {
        "date", "north_net_flow", "north_5d_avg",
        "margin_balance", "margin_delta", "main_net_flow",
        "etf_net_flow", "data_freshness"
    }
    
    model_fields = {f.name for f in fields(CapitalFlowData)}
    assert required_fields.issubset(model_fields)
    
    # Verify all fields are present (can be None for optional fields)
    for field_name in required_fields:
        assert hasattr(data, field_name), f"Field {field_name} should exist"
    
    # Verify data_freshness is a dictionary
    assert isinstance(data.data_freshness, dict), \
        "data_freshness should be a dictionary"


@given(data=market_breadth_data_strategy())
def test_property_breadth_ratios_bounded(data):
    """
    Verify that ratio fields in MarketBreadthData are bounded [0, 1].
    
    This ensures data integrity for percentage-based metrics.
    """
    # Verify seal_rate is in [0, 1]
    assert 0.0 <= data.seal_rate <= 1.0, \
        f"seal_rate {data.seal_rate} should be in [0, 1]"
    
    # Verify above_ma20_ratio is in [0, 1]
    assert 0.0 <= data.above_ma20_ratio <= 1.0, \
        f"above_ma20_ratio {data.above_ma20_ratio} should be in [0, 1]"
    
    # Verify above_ma60_ratio is in [0, 1]
    assert 0.0 <= data.above_ma60_ratio <= 1.0, \
        f"above_ma60_ratio {data.above_ma60_ratio} should be in [0, 1]"


@given(data=market_breadth_data_strategy())
def test_property_breadth_counts_non_negative(data):
    """
    Verify that count fields in MarketBreadthData are non-negative.
    
    Stock counts cannot be negative.
    """
    count_fields = [
        "up_count", "down_count", "flat_count",
        "limit_up_count", "limit_down_count", "explode_count",
        "continuous_limit_up", "new_high_count", "new_low_count"
    ]
    
    for field_name in count_fields:
        field_value = getattr(data, field_name)
        assert field_value >= 0, \
            f"{field_name} {field_value} should be non-negative"


@given(data=market_breadth_data_strategy())
def test_property_breadth_amounts_non_negative(data):
    """
    Verify that amount fields in MarketBreadthData are non-negative.
    
    Trading amounts cannot be negative.
    """
    amount_fields = ["total_amount", "amount_ma5", "amount_ma20"]
    
    for field_name in amount_fields:
        field_value = getattr(data, field_name)
        assert field_value >= 0, \
            f"{field_name} {field_value} should be non-negative"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
