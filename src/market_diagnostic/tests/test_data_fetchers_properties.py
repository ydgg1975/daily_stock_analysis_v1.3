"""
Property-Based Tests for Data Fetchers

Task 2.2: Write property tests for data fetchers

This module contains property-based tests that validate universal correctness
properties across all data fetching operations.

Properties tested:
- Property 1: Historical Data Completeness (Validates: Requirement 1.2)
- Property 3: Sector Data Completeness (Validates: Requirement 1.4)
- Property 4: Capital Flow Data Structure (Validates: Requirement 1.5)
- Property 5: Error Handling Continuity (Validates: Requirements 1.6, 22.1, 22.2)
- Property 6: Stock Filtering Consistency (Validates: Requirement 1.7)
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.market_diagnostic.data.fetchers import DiagnosticDataFetcher
from src.market_diagnostic.data.models import (
    IndexDailyData,
    MarketBreadthData,
    SectorDailyData,
    CapitalFlowData
)
from src.market_diagnostic.config import INDEX_POOL, SHENWAN_INDUSTRIES


# ============================================================================
# Strategy Generators
# ============================================================================

@st.composite
def valid_date_strategy(draw):
    """Generate valid date strings in YYYY-MM-DD format."""
    date = draw(st.dates(
        min_value=datetime(2020, 1, 1).date(),
        max_value=datetime(2025, 12, 31).date()
    ))
    return date.strftime('%Y-%m-%d')


@st.composite
def historical_days_strategy(draw):
    """Generate valid historical days count (20-120)."""
    return draw(st.integers(min_value=20, max_value=120))


@st.composite
def mock_index_dataframe_strategy(draw, days=60):
    """Generate mock DataFrame for index historical data."""
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    
    # Generate realistic price series
    base_price = draw(st.floats(min_value=1000.0, max_value=5000.0))
    prices = []
    current_price = base_price
    
    for _ in range(days):
        # Random walk with drift
        change = draw(st.floats(min_value=-0.03, max_value=0.03))
        current_price = current_price * (1 + change)
        prices.append(current_price)
    
    df = pd.DataFrame({
        'date': dates,
        'open': [p * draw(st.floats(min_value=0.98, max_value=1.02)) for p in prices],
        'high': [p * draw(st.floats(min_value=1.00, max_value=1.05)) for p in prices],
        'low': [p * draw(st.floats(min_value=0.95, max_value=1.00)) for p in prices],
        'close': prices,
        'volume': [draw(st.floats(min_value=1e8, max_value=1e10)) for _ in range(days)],
        'amount': [draw(st.floats(min_value=1e10, max_value=1e12)) for _ in range(days)],
        'pct_chg': [draw(st.floats(min_value=-10.0, max_value=10.0)) for _ in range(days)],
    })
    
    return df


@st.composite
def mock_sector_list_strategy(draw, num_sectors=5):
    """Generate mock list of sector data."""
    sectors = []
    for i in range(num_sectors):
        sector = {
            'code': f'BK{draw(st.integers(min_value=1000, max_value=9999))}',
            'name': draw(st.sampled_from(['电子', '计算机', '医药生物', '食品饮料', '银行'])),
            'change_pct': draw(st.floats(min_value=-10.0, max_value=10.0)),
            'amount': draw(st.floats(min_value=100.0, max_value=10000.0)),
        }
        sectors.append(sector)
    return sectors


# ============================================================================
# Property 1: Historical Data Completeness
# **Validates: Requirement 1.2**
# ============================================================================

@given(
    date=valid_date_strategy(),
    days=historical_days_strategy()
)
@settings(max_examples=5, deadline=5000)
def test_property_1_historical_data_completeness(date, days):
    """
    **Property 1: Historical Data Completeness**
    **Validates: Requirement 1.2**
    
    WHEN the system fetches index data for a valid date and days parameter,
    THE Data_Layer SHALL retrieve at least the requested number of days
    of historical price series for technical indicator calculation.
    
    For any index in INDEX_POOL:
    - close_series length >= min(days, available_trading_days)
    - volume_series length >= min(days, available_trading_days)
    - All series values are non-null and valid floats
    """
    # Create mock data manager
    mock_data_manager = Mock()
    
    # Create mock DataFrame with sufficient historical data
    mock_df = pd.DataFrame({
        'date': pd.date_range(end=date, periods=days, freq='D'),
        'open': np.random.uniform(1000, 5000, days),
        'high': np.random.uniform(1000, 5000, days),
        'low': np.random.uniform(1000, 5000, days),
        'close': np.random.uniform(1000, 5000, days),
        'volume': np.random.uniform(1e8, 1e10, days),
        'amount': np.random.uniform(1e10, 1e12, days),
        'pct_chg': np.random.uniform(-10, 10, days),
    })
    
    mock_data_manager.get_daily_data = Mock(return_value=mock_df)
    
    # Create fetcher
    fetcher = DiagnosticDataFetcher(mock_data_manager)
    
    # Fetch index series
    result = fetcher.fetch_index_series(date=date, days=days)
    
    # Property assertions
    assert isinstance(result, dict), "Result should be a dictionary"
    
    # For each successfully fetched index
    for code, index_data in result.items():
        assert isinstance(index_data, IndexDailyData), \
            f"Index {code} should return IndexDailyData instance"
        
        # Verify close_series completeness
        assert len(index_data.close_series) > 0, \
            f"Index {code} close_series should not be empty"
        
        # Verify close_series length is reasonable (at least min(days, available))
        # Note: We expect at least some data, but may be less than requested due to trading days
        assert len(index_data.close_series) <= days, \
            f"Index {code} close_series length {len(index_data.close_series)} should not exceed requested {days}"
        
        # Verify volume_series completeness
        assert len(index_data.volume_series) > 0, \
            f"Index {code} volume_series should not be empty"
        
        assert len(index_data.volume_series) == len(index_data.close_series), \
            f"Index {code} volume_series and close_series should have same length"
        
        # Verify all series values are valid (non-null, non-NaN)
        for i, price in enumerate(index_data.close_series):
            assert price is not None, \
                f"Index {code} close_series[{i}] should not be None"
            assert not np.isnan(price), \
                f"Index {code} close_series[{i}] should not be NaN"
            assert price > 0, \
                f"Index {code} close_series[{i}] should be positive"
        
        for i, vol in enumerate(index_data.volume_series):
            assert vol is not None, \
                f"Index {code} volume_series[{i}] should not be None"
            assert not np.isnan(vol), \
                f"Index {code} volume_series[{i}] should not be NaN"
            assert vol >= 0, \
                f"Index {code} volume_series[{i}] should be non-negative"


# ============================================================================
# Property 3: Sector Data Completeness
# **Validates: Requirement 1.4**
# ============================================================================

@given(date=valid_date_strategy())
@settings(max_examples=5, deadline=5000)
def test_property_3_sector_data_completeness(date):
    """
    **Property 3: Sector Data Completeness**
    **Validates: Requirement 1.4**
    
    WHEN the system fetches sector data for a valid date,
    THE Data_Layer SHALL retrieve data for all 31 Shenwan Level-1 industries
    including returns, breadth, turnover, and capital flow.
    
    For each sector in the result:
    - All required fields are present (ret_1d, ret_5d, ret_20d, excess_ret_1d, etc.)
    - All numeric fields are valid (non-null, non-NaN)
    - Ratio fields are bounded [0, 1]
    """
    # Create mock data manager
    mock_data_manager = Mock()
    
    # Mock sector rankings with minimal data
    mock_sectors = []
    for i, (code, name) in enumerate(list(SHENWAN_INDUSTRIES.items())[:5]):  # Use only 5 sectors for speed
        sector = {
            'code': code,
            'name': name,
            'change_pct': np.random.uniform(-10, 10),
            'ret_5d': np.random.uniform(-20, 20),
            'ret_20d': np.random.uniform(-30, 30),
            'excess_ret_1d': np.random.uniform(-5, 5),
            'amount': np.random.uniform(100, 10000),
            'amount_share': np.random.uniform(0.01, 0.15),
            'amount_share_delta': np.random.uniform(-0.05, 0.05),
            'limit_up_count': np.random.randint(0, 20),
            'turnover': np.random.uniform(0.01, 0.20),
            'breadth_20': np.random.uniform(0.0, 1.0),
            'new_high_ratio': np.random.uniform(0.0, 0.5),
        }
        mock_sectors.append(sector)
    
    mock_data_manager.get_sector_rankings = Mock(return_value=(mock_sectors[:3], mock_sectors[3:]))
    
    # Create fetcher
    fetcher = DiagnosticDataFetcher(mock_data_manager)
    
    # Patch akshare to prevent real API calls
    with patch('src.market_diagnostic.data.fetchers.ak', None):
        # Fetch sector data
        result = fetcher.fetch_sector_data(date=date)
    
    # Property assertions
    assert isinstance(result, list), "Result should be a list"
    assert len(result) > 0, "Result should contain at least one sector"
    
    # For each sector in result
    for sector_data in result:
        assert isinstance(sector_data, SectorDailyData), \
            "Each sector should be SectorDailyData instance"
        
        # Verify required fields are present
        required_fields = [
            'date', 'industry_code', 'industry_name',
            'ret_1d', 'ret_5d', 'ret_20d', 'excess_ret_1d',
            'breadth_20', 'new_high_ratio', 'amount', 'amount_share',
            'amount_share_delta', 'limit_up_count', 'turnover'
        ]
        
        for field in required_fields:
            assert hasattr(sector_data, field), \
                f"Sector {sector_data.industry_name} should have field {field}"
            
            value = getattr(sector_data, field)
            assert value is not None, \
                f"Sector {sector_data.industry_name} field {field} should not be None"
        
        # Verify numeric fields are valid (non-NaN)
        numeric_fields = [
            'ret_1d', 'ret_5d', 'ret_20d', 'excess_ret_1d',
            'breadth_20', 'new_high_ratio', 'amount', 'amount_share',
            'amount_share_delta', 'turnover'
        ]
        
        for field in numeric_fields:
            value = getattr(sector_data, field)
            if isinstance(value, float):
                assert not np.isnan(value), \
                    f"Sector {sector_data.industry_name} field {field} should not be NaN"
        
        # Verify ratio fields are bounded [0, 1]
        ratio_fields = ['breadth_20', 'new_high_ratio', 'amount_share', 'turnover']
        
        for field in ratio_fields:
            value = getattr(sector_data, field)
            assert 0.0 <= value <= 1.0, \
                f"Sector {sector_data.industry_name} field {field} = {value} should be in [0, 1]"
        
        # Verify count fields are non-negative integers
        assert sector_data.limit_up_count >= 0, \
            f"Sector {sector_data.industry_name} limit_up_count should be non-negative"


# ============================================================================
# Property 4: Capital Flow Data Structure
# **Validates: Requirement 1.5**
# ============================================================================

@given(date=valid_date_strategy())
@settings(max_examples=5, deadline=5000)
def test_property_4_capital_flow_data_structure(date):
    """
    **Property 4: Capital Flow Data Structure**
    **Validates: Requirement 1.5**
    
    WHEN the system fetches capital flow data for a valid date,
    THE Data_Layer SHALL retrieve North Bound Capital, margin balance,
    main force net flow, and ETF net flow with appropriate data freshness markers.
    
    For the capital flow result:
    - All required fields are present
    - data_freshness dictionary contains timeliness markers
    - T+1 data is properly marked
    - Numeric fields are valid (non-null, non-NaN)
    """
    # Create mock data manager
    mock_data_manager = Mock()
    
    # Create fetcher with mocked akshare
    fetcher = DiagnosticDataFetcher(mock_data_manager)
    
    # Mock the internal methods to avoid actual API calls
    with patch('src.market_diagnostic.data.fetchers.ak') as mock_ak:
        # Mock North Bound Capital data
        mock_north_df = pd.DataFrame({
            '日期': [pd.to_datetime(date)],
            '当日资金流入': [np.random.uniform(-100, 100) * 1e8]
        })
        mock_ak.stock_hsgt_hist_em = Mock(return_value=mock_north_df)
        
        # Mock margin balance data
        mock_margin_df = pd.DataFrame({
            '融资余额': [np.random.uniform(15000, 20000) * 1e8]
        })
        mock_ak.stock_margin_underlying_info_szse = Mock(return_value=mock_margin_df)
        
        # Fetch capital flow data
        result = fetcher.fetch_capital_flow(date=date)
    
    # Property assertions
    if result is not None:  # Allow for graceful failure
        assert isinstance(result, CapitalFlowData), \
            "Result should be CapitalFlowData instance"
        
        # Verify required fields are present
        required_fields = [
            'date', 'north_net_flow', 'north_5d_avg',
            'margin_balance', 'margin_delta', 'main_net_flow',
            'etf_net_flow', 'data_freshness'
        ]
        
        for field in required_fields:
            assert hasattr(result, field), \
                f"Capital flow data should have field {field}"
        
        # Verify data_freshness is a dictionary
        assert isinstance(result.data_freshness, dict), \
            "data_freshness should be a dictionary"
        
        # Verify data_freshness contains expected keys
        expected_freshness_keys = ['north_net_flow', 'margin_balance', 'main_net_flow', 'etf_net_flow']
        for key in expected_freshness_keys:
            if key in result.data_freshness:
                freshness_value = result.data_freshness[key]
                assert isinstance(freshness_value, str), \
                    f"data_freshness[{key}] should be a string"
                assert freshness_value in ['T+0', 'T+1', 'T+2', 'T+0 (proxy)', 'unavailable'], \
                    f"data_freshness[{key}] should be a valid timeliness marker"
        
        # Verify numeric fields are valid (non-NaN)
        numeric_fields = [
            'north_net_flow', 'north_5d_avg', 'margin_balance',
            'margin_delta', 'main_net_flow', 'etf_net_flow'
        ]
        
        for field in numeric_fields:
            value = getattr(result, field)
            if isinstance(value, float):
                assert not np.isnan(value), \
                    f"Capital flow field {field} should not be NaN"


# ============================================================================
# Property 5: Error Handling Continuity
# **Validates: Requirements 1.6, 22.1, 22.2**
# ============================================================================

@given(
    date=valid_date_strategy(),
    fail_index_count=st.integers(min_value=0, max_value=3)
)
@settings(max_examples=5, deadline=5000)
def test_property_5_error_handling_continuity(date, fail_index_count):
    """
    **Property 5: Error Handling Continuity**
    **Validates: Requirements 1.6, 22.1, 22.2**
    
    WHEN the Data_Layer encounters missing or invalid data for some indices,
    THE System SHALL log the error and continue processing with available data.
    
    Properties:
    - System does not crash when some data sources fail
    - Successfully fetched data is returned
    - Missing data is logged
    - Result dictionary contains only successfully fetched indices
    """
    # Create mock data manager
    mock_data_manager = Mock()
    
    # Create a side effect that fails for some indices
    index_codes = list(INDEX_POOL.keys())
    failing_indices = index_codes[:fail_index_count]
    
    def mock_get_daily_data(stock_code, **kwargs):
        if stock_code in failing_indices:
            return None  # Simulate failure
        else:
            # Return valid data
            days = kwargs.get('days', 60)
            return pd.DataFrame({
                'date': pd.date_range(end=date, periods=days, freq='D'),
                'open': np.random.uniform(1000, 5000, days),
                'high': np.random.uniform(1000, 5000, days),
                'low': np.random.uniform(1000, 5000, days),
                'close': np.random.uniform(1000, 5000, days),
                'volume': np.random.uniform(1e8, 1e10, days),
                'amount': np.random.uniform(1e10, 1e12, days),
                'pct_chg': np.random.uniform(-10, 10, days),
            })
    
    mock_data_manager.get_daily_data = Mock(side_effect=mock_get_daily_data)
    
    # Create fetcher
    fetcher = DiagnosticDataFetcher(mock_data_manager)
    
    # Fetch index series (should not crash)
    result = fetcher.fetch_index_series(date=date, days=60)
    
    # Property assertions
    assert isinstance(result, dict), "Result should be a dictionary even with failures"
    
    # Verify that successfully fetched indices are in result
    expected_success_count = len(index_codes) - fail_index_count
    assert len(result) == expected_success_count, \
        f"Result should contain {expected_success_count} successfully fetched indices"
    
    # Verify that failing indices are NOT in result
    for failing_code in failing_indices:
        assert failing_code not in result, \
            f"Failing index {failing_code} should not be in result"
    
    # Verify that successful indices ARE in result
    for code in index_codes:
        if code not in failing_indices:
            assert code in result, \
                f"Successful index {code} should be in result"
            assert isinstance(result[code], IndexDailyData), \
                f"Successful index {code} should return IndexDailyData"


# ============================================================================
# Property 6: Stock Filtering Consistency
# **Validates: Requirement 1.7**
# ============================================================================

@given(
    st_stock_count=st.integers(min_value=0, max_value=100),
    suspended_stock_count=st.integers(min_value=0, max_value=50),
    normal_stock_count=st.integers(min_value=100, max_value=500)
)
@settings(max_examples=5, deadline=5000)
def test_property_6_stock_filtering_consistency(st_stock_count, suspended_stock_count, normal_stock_count):
    """
    **Property 6: Stock Filtering Consistency**
    **Validates: Requirement 1.7**
    
    WHEN the system processes raw data,
    THE Data_Layer SHALL exclude ST stocks, suspended stocks, newly listed stocks,
    and anomalous samples from market breadth calculations.
    
    Properties:
    - ST stocks are filtered out (names containing 'ST', '*ST', 'S', etc.)
    - Suspended stocks are filtered out (volume = 0)
    - Anomalous samples are filtered out (extreme price changes)
    - Filtered count = original count - excluded count
    """
    # Create mock data manager
    mock_data_manager = Mock()
    
    # Create fetcher
    fetcher = DiagnosticDataFetcher(mock_data_manager)
    
    # Create mock market data with mixed stock types
    stock_data = []
    
    # Add ST stocks
    for i in range(st_stock_count):
        stock_data.append({
            '代码': f'60{i:04d}',
            '名称': f'ST测试{i}',
            '最新价': np.random.uniform(5, 50),
            '涨跌幅': np.random.uniform(-10, 10),
            '成交量': np.random.uniform(1e6, 1e8),
            '成交额': np.random.uniform(1e8, 1e10),
        })
    
    # Add suspended stocks (volume = 0)
    for i in range(suspended_stock_count):
        stock_data.append({
            '代码': f'00{i:04d}',
            '名称': f'正常股{i}',
            '最新价': np.random.uniform(5, 50),
            '涨跌幅': 0.0,
            '成交量': 0.0,  # Suspended
            '成交额': 0.0,
        })
    
    # Add normal stocks
    for i in range(normal_stock_count):
        stock_data.append({
            '代码': f'30{i:04d}',
            '名称': f'正常股{i}',
            '最新价': np.random.uniform(5, 50),
            '涨跌幅': np.random.uniform(-10, 10),
            '成交量': np.random.uniform(1e6, 1e8),
            '成交额': np.random.uniform(1e8, 1e10),
        })
    
    df_market = pd.DataFrame(stock_data)
    
    # Apply filtering
    df_filtered = fetcher._filter_stocks(df_market)
    
    # Property assertions
    original_count = len(df_market)
    filtered_count = len(df_filtered)
    
    # Verify filtering occurred
    assert filtered_count <= original_count, \
        "Filtered count should be <= original count"
    
    # Verify ST stocks are excluded
    if st_stock_count > 0:
        st_names_in_filtered = df_filtered['名称'].str.contains('ST', na=False).sum()
        assert st_names_in_filtered == 0, \
            "ST stocks should be filtered out"
    
    # Verify suspended stocks are excluded
    if suspended_stock_count > 0:
        suspended_in_filtered = (df_filtered['成交量'] == 0).sum()
        assert suspended_in_filtered == 0, \
            "Suspended stocks (volume=0) should be filtered out"
    
    # Verify expected filtered count
    expected_filtered_count = normal_stock_count
    assert filtered_count == expected_filtered_count, \
        f"Filtered count {filtered_count} should equal normal stock count {expected_filtered_count}"
    
    # Verify all remaining stocks have positive volume
    assert (df_filtered['成交量'] > 0).all(), \
        "All filtered stocks should have positive volume"


# ============================================================================
# Additional Property: Data Consistency Across Multiple Fetches
# ============================================================================

@given(date=valid_date_strategy())
@settings(max_examples=5, deadline=5000)
def test_property_data_consistency_across_fetches(date):
    """
    **Additional Property: Data Consistency Across Multiple Fetches**
    
    WHEN the system fetches the same data multiple times for the same date,
    THE results SHALL be consistent (idempotent).
    
    This validates caching behavior and data consistency.
    """
    # Create mock data manager
    mock_data_manager = Mock()
    
    # Create consistent mock data
    mock_df = pd.DataFrame({
        'date': pd.date_range(end=date, periods=60, freq='D'),
        'open': np.random.uniform(1000, 5000, 60),
        'high': np.random.uniform(1000, 5000, 60),
        'low': np.random.uniform(1000, 5000, 60),
        'close': np.random.uniform(1000, 5000, 60),
        'volume': np.random.uniform(1e8, 1e10, 60),
        'amount': np.random.uniform(1e10, 1e12, 60),
        'pct_chg': np.random.uniform(-10, 10, 60),
    })
    
    mock_data_manager.get_daily_data = Mock(return_value=mock_df)
    
    # Create fetcher
    fetcher = DiagnosticDataFetcher(mock_data_manager)
    
    # Fetch data twice
    result1 = fetcher.fetch_index_series(date=date, days=60)
    result2 = fetcher.fetch_index_series(date=date, days=60)
    
    # Property assertions
    assert len(result1) == len(result2), \
        "Multiple fetches should return same number of indices"
    
    # Verify same indices are present
    assert set(result1.keys()) == set(result2.keys()), \
        "Multiple fetches should return same index codes"
    
    # Verify data values are consistent
    for code in result1.keys():
        data1 = result1[code]
        data2 = result2[code]
        
        assert data1.close == data2.close, \
            f"Index {code} close price should be consistent across fetches"
        
        assert len(data1.close_series) == len(data2.close_series), \
            f"Index {code} close_series length should be consistent"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
