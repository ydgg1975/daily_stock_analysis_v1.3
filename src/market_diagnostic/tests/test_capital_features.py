"""
Unit tests for capital flow feature calculation (Task 6.2)

Tests the implementation of:
- Total market turnover calculation
- Turnover deviation calculations (5d, 20d, 60d)
- North Bound Capital flow analysis
- Margin balance tracking
- Main force and ETF flow proxies
- T+1 data lag indicators
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.market_diagnostic.features.capital import (
    CapitalFeatures,
    compute_capital_features,
    _safe_divide,
)
from src.market_diagnostic.data.models import CapitalFlowData, MarketBreadthData


class TestCapitalFeatures:
    """Test suite for capital flow feature calculation"""
    
    def test_safe_divide_normal(self):
        """Test safe division with normal values"""
        result = _safe_divide(10.0, 2.0)
        assert result == 5.0
    
    def test_safe_divide_zero_denominator(self):
        """Test safe division with zero denominator"""
        result = _safe_divide(10.0, 0.0, default=0.0)
        assert result == 0.0
    
    def test_safe_divide_custom_default(self):
        """Test safe division with custom default"""
        result = _safe_divide(10.0, 0.0, default=-1.0)
        assert result == -1.0
    
    def test_compute_capital_features_basic(self):
        """Test basic capital feature computation"""
        # Create test data
        capital_data = CapitalFlowData(
            date='2024-01-15',
            north_net_flow=50.0,  # 50亿 inflow
            north_5d_avg=30.0,
            margin_balance=18000.0,  # 1.8万亿
            margin_delta=100.0,
            main_net_flow=20.0,
            etf_net_flow=10.0,
            data_freshness={
                'north_net_flow': 'T+0',
                'margin_balance': 'T+1',
                'main_net_flow': 'T+0 (proxy)',
                'etf_net_flow': 'T+0 (proxy)',
            }
        )
        
        breadth_data = MarketBreadthData(
            date='2024-01-15',
            up_count=2000,
            down_count=1500,
            flat_count=500,
            limit_up_count=50,
            limit_down_count=10,
            explode_count=5,
            seal_rate=0.9,
            continuous_limit_up=20,
            above_ma20_ratio=0.55,
            above_ma60_ratio=0.45,
            new_high_count=100,
            new_low_count=50,
            total_amount=10000.0,  # 1万亿
            amount_ma5=9000.0,
            amount_ma20=8500.0,
        )
        
        amount_ma60 = 8000.0
        
        # Compute features
        features = compute_capital_features(capital_data, breadth_data, amount_ma60)
        
        # Verify basic fields
        assert features.total_amount == 10000.0
        assert features.north_net_flow == 50.0
        assert features.north_5d_avg == 30.0
        assert features.margin_balance == 18000.0
        assert features.margin_delta == 100.0
        assert features.main_net_flow == 20.0
        assert features.etf_net_flow == 10.0
        
        # Verify calculated fields
        assert features.amount_deviation_5d == pytest.approx((10000 - 9000) / 9000, rel=1e-6)
        assert features.amount_deviation_20d == pytest.approx((10000 - 8500) / 8500, rel=1e-6)
        assert features.amount_deviation_60d == pytest.approx((10000 - 8000) / 8000, rel=1e-6)
        
        # Verify North Bound flow trend
        assert features.north_flow_trend == "inflow"  # 30亿 > 10亿 threshold
        
        # Verify data freshness
        assert features.data_freshness['north_net_flow'] == 'T+0'
        assert features.data_freshness['margin_balance'] == 'T+1'
        assert features.has_delayed_data is True  # margin_balance is T+1
    
    def test_compute_capital_features_north_outflow(self):
        """Test capital features with North Bound outflow"""
        capital_data = CapitalFlowData(
            date='2024-01-15',
            north_net_flow=-30.0,  # 30亿 outflow
            north_5d_avg=-20.0,
            margin_balance=18000.0,
            margin_delta=-50.0,
            main_net_flow=-10.0,
            etf_net_flow=-5.0,
            data_freshness={
                'north_net_flow': 'T+0',
                'margin_balance': 'T+0',
                'main_net_flow': 'T+0 (proxy)',
                'etf_net_flow': 'T+0 (proxy)',
            }
        )
        
        breadth_data = MarketBreadthData(
            date='2024-01-15',
            up_count=1000,
            down_count=2500,
            flat_count=500,
            limit_up_count=10,
            limit_down_count=50,
            explode_count=5,
            seal_rate=0.5,
            continuous_limit_up=5,
            above_ma20_ratio=0.30,
            above_ma60_ratio=0.25,
            new_high_count=20,
            new_low_count=200,
            total_amount=8000.0,
            amount_ma5=9000.0,
            amount_ma20=9500.0,
        )
        
        amount_ma60 = 10000.0
        
        features = compute_capital_features(capital_data, breadth_data, amount_ma60)
        
        # Verify North Bound flow trend is outflow
        assert features.north_flow_trend == "outflow"  # -20亿 < -10亿 threshold
        
        # Verify negative deviations
        assert features.amount_deviation_5d < 0
        assert features.amount_deviation_20d < 0
        assert features.amount_deviation_60d < 0
        
        # Verify no delayed data
        assert features.has_delayed_data is False
    
    def test_compute_capital_features_neutral_flow(self):
        """Test capital features with neutral North Bound flow"""
        capital_data = CapitalFlowData(
            date='2024-01-15',
            north_net_flow=5.0,
            north_5d_avg=3.0,  # Between -10 and 10
            margin_balance=18000.0,
            margin_delta=0.0,
            main_net_flow=0.0,
            etf_net_flow=0.0,
            data_freshness={
                'north_net_flow': 'T+0',
                'margin_balance': 'T+0',
                'main_net_flow': 'T+0 (proxy)',
                'etf_net_flow': 'T+0 (proxy)',
            }
        )
        
        breadth_data = MarketBreadthData(
            date='2024-01-15',
            up_count=1500,
            down_count=1500,
            flat_count=1000,
            limit_up_count=30,
            limit_down_count=30,
            explode_count=10,
            seal_rate=0.75,
            continuous_limit_up=10,
            above_ma20_ratio=0.50,
            above_ma60_ratio=0.45,
            new_high_count=50,
            new_low_count=50,
            total_amount=9000.0,
            amount_ma5=9000.0,
            amount_ma20=9000.0,
        )
        
        amount_ma60 = 9000.0
        
        features = compute_capital_features(capital_data, breadth_data, amount_ma60)
        
        # Verify neutral flow trend
        assert features.north_flow_trend == "neutral"
        
        # Verify zero deviations (amount equals all MAs)
        assert features.amount_deviation_5d == 0.0
        assert features.amount_deviation_20d == 0.0
        assert features.amount_deviation_60d == 0.0
    
    def test_compute_capital_features_zero_ma(self):
        """Test capital features with zero moving averages (edge case)"""
        capital_data = CapitalFlowData(
            date='2024-01-15',
            north_net_flow=10.0,
            north_5d_avg=5.0,
            margin_balance=18000.0,
            margin_delta=50.0,
            main_net_flow=5.0,
            etf_net_flow=2.0,
            data_freshness={}
        )
        
        breadth_data = MarketBreadthData(
            date='2024-01-15',
            up_count=2000,
            down_count=1000,
            flat_count=1000,
            limit_up_count=40,
            limit_down_count=20,
            explode_count=5,
            seal_rate=0.8,
            continuous_limit_up=15,
            above_ma20_ratio=0.60,
            above_ma60_ratio=0.50,
            new_high_count=80,
            new_low_count=40,
            total_amount=10000.0,
            amount_ma5=0.0,  # Zero MA (edge case)
            amount_ma20=0.0,
        )
        
        amount_ma60 = 0.0
        
        features = compute_capital_features(capital_data, breadth_data, amount_ma60)
        
        # Verify safe division returns default (0.0) for zero denominators
        assert features.amount_deviation_5d == 0.0
        assert features.amount_deviation_20d == 0.0
        assert features.amount_deviation_60d == 0.0
    
    def test_compute_capital_features_unavailable_data(self):
        """Test capital features with unavailable data"""
        capital_data = CapitalFlowData(
            date='2024-01-15',
            north_net_flow=0.0,
            north_5d_avg=0.0,
            margin_balance=0.0,
            margin_delta=0.0,
            main_net_flow=0.0,
            etf_net_flow=0.0,
            data_freshness={
                'north_net_flow': 'unavailable',
                'margin_balance': 'unavailable',
                'main_net_flow': 'unavailable',
                'etf_net_flow': 'unavailable',
            }
        )
        
        breadth_data = MarketBreadthData(
            date='2024-01-15',
            up_count=2000,
            down_count=1500,
            flat_count=500,
            limit_up_count=50,
            limit_down_count=10,
            explode_count=5,
            seal_rate=0.9,
            continuous_limit_up=20,
            above_ma20_ratio=0.55,
            above_ma60_ratio=0.45,
            new_high_count=100,
            new_low_count=50,
            total_amount=10000.0,
            amount_ma5=9000.0,
            amount_ma20=8500.0,
        )
        
        amount_ma60 = 8000.0
        
        features = compute_capital_features(capital_data, breadth_data, amount_ma60)
        
        # Verify has_delayed_data is True (unavailable counts as delayed)
        assert features.has_delayed_data is True
        
        # Verify all data freshness fields are marked unavailable
        assert all('unavailable' in v for v in features.data_freshness.values())
    
    def test_compute_capital_features_all_t0_data(self):
        """Test capital features with all T+0 data (no delays)"""
        capital_data = CapitalFlowData(
            date='2024-01-15',
            north_net_flow=40.0,
            north_5d_avg=35.0,
            margin_balance=18000.0,
            margin_delta=80.0,
            main_net_flow=15.0,
            etf_net_flow=8.0,
            data_freshness={
                'north_net_flow': 'T+0',
                'margin_balance': 'T+0',
                'main_net_flow': 'T+0',
                'etf_net_flow': 'T+0',
            }
        )
        
        breadth_data = MarketBreadthData(
            date='2024-01-15',
            up_count=2500,
            down_count=1000,
            flat_count=500,
            limit_up_count=60,
            limit_down_count=5,
            explode_count=3,
            seal_rate=0.95,
            continuous_limit_up=25,
            above_ma20_ratio=0.65,
            above_ma60_ratio=0.55,
            new_high_count=120,
            new_low_count=30,
            total_amount=11000.0,
            amount_ma5=10000.0,
            amount_ma20=9500.0,
        )
        
        amount_ma60 = 9000.0
        
        features = compute_capital_features(capital_data, breadth_data, amount_ma60)
        
        # Verify no delayed data
        assert features.has_delayed_data is False
        
        # Verify all data is T+0
        assert all('T+0' in v for v in features.data_freshness.values())
        
        # Verify strong inflow trend
        assert features.north_flow_trend == "inflow"
        
        # Verify positive deviations
        assert features.amount_deviation_5d > 0
        assert features.amount_deviation_20d > 0
        assert features.amount_deviation_60d > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
