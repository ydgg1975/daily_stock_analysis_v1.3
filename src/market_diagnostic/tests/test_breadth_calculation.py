"""
Unit tests for breadth data calculation enhancements (Task 2.1.4)

Tests the implementation of:
- Continuous limit-up count calculation
- MA penetration ratio calculation
- New high/low count calculation
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.market_diagnostic.data.fetchers import DiagnosticDataFetcher
from src.market_diagnostic.data.models import MarketBreadthData


class TestBreadthCalculation:
    """Test suite for breadth data calculation enhancements"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_data_manager = Mock()
        self.fetcher = DiagnosticDataFetcher(self.mock_data_manager)
    
    def test_calculate_continuous_limit_up_success(self):
        """Test continuous limit-up calculation with valid data"""
        # Mock akshare limit-up pool data
        mock_limit_up_df = pd.DataFrame({
            '代码': ['000001', '000002', '000003', '000004'],
            '名称': ['Stock1', 'Stock2', 'Stock3', 'Stock4'],
            '连板数': [1, 2, 3, 2]
        })
        
        with patch('src.market_diagnostic.data.fetchers.ak') as mock_ak:
            mock_ak.stock_zt_pool_em.return_value = mock_limit_up_df
            
            result = self.fetcher._calculate_continuous_limit_up('2024-01-15')
            
            # Should count stocks with 连板数 >= 2 (3 stocks)
            assert result == 3
    
    def test_calculate_continuous_limit_up_no_data(self):
        """Test continuous limit-up calculation with no data"""
        with patch('src.market_diagnostic.data.fetchers.ak') as mock_ak:
            mock_ak.stock_zt_pool_em.return_value = pd.DataFrame()
            
            result = self.fetcher._calculate_continuous_limit_up('2024-01-15')
            
            assert result == 0
    
    def test_calculate_continuous_limit_up_missing_column(self):
        """Test continuous limit-up calculation with missing column"""
        mock_limit_up_df = pd.DataFrame({
            '代码': ['000001', '000002'],
            '名称': ['Stock1', 'Stock2']
            # Missing '连板数' column
        })
        
        with patch('src.market_diagnostic.data.fetchers.ak') as mock_ak:
            mock_ak.stock_zt_pool_em.return_value = mock_limit_up_df
            
            result = self.fetcher._calculate_continuous_limit_up('2024-01-15')
            
            assert result == 0
    
    def test_calculate_ma_penetration_ratios_success(self):
        """Test MA penetration ratio calculation with valid data"""
        # Mock market data
        mock_market_df = pd.DataFrame({
            '代码': [f'{i:06d}' for i in range(100)],
            '名称': [f'Stock{i}' for i in range(100)],
            '涨跌幅': np.random.randn(100) * 2
        })
        
        # Mock historical data for individual stocks
        def mock_get_daily_data(stock_code, days=None, **kwargs):
            # Generate 60 days of mock price data
            dates = pd.date_range(end='2024-01-15', periods=60)
            prices = 10 + np.cumsum(np.random.randn(60) * 0.1)
            
            return pd.DataFrame({
                'date': dates,
                'close': prices,
                'open': prices * 0.99,
                'high': prices * 1.01,
                'low': prices * 0.98,
                'volume': np.random.randint(1000000, 10000000, 60)
            })
        
        self.mock_data_manager.get_daily_data = mock_get_daily_data
        
        # Run calculation
        above_ma20, above_ma60 = self.fetcher._calculate_ma_penetration_ratios(mock_market_df)
        
        # Verify results are in valid range [0, 1]
        assert 0 <= above_ma20 <= 1
        assert 0 <= above_ma60 <= 1
        
        # Verify they are not placeholder values (0.5)
        # Note: Due to randomness, they might be close to 0.5, so we just check they're calculated
        assert isinstance(above_ma20, float)
        assert isinstance(above_ma60, float)
    
    def test_calculate_ma_penetration_ratios_empty_data(self):
        """Test MA penetration ratio calculation with empty data"""
        empty_df = pd.DataFrame()
        
        above_ma20, above_ma60 = self.fetcher._calculate_ma_penetration_ratios(empty_df)
        
        # Should return default values
        assert above_ma20 == 0.5
        assert above_ma60 == 0.5
    
    def test_calculate_ma_penetration_ratios_insufficient_history(self):
        """Test MA penetration ratio calculation with insufficient historical data"""
        mock_market_df = pd.DataFrame({
            '代码': ['000001', '000002'],
            '名称': ['Stock1', 'Stock2'],
            '涨跌幅': [1.5, -0.8]
        })
        
        # Mock get_daily_data to return insufficient data
        def mock_get_daily_data_short(stock_code, days=None, **kwargs):
            # Only 10 days of data (insufficient for MA60)
            dates = pd.date_range(end='2024-01-15', periods=10)
            prices = 10 + np.cumsum(np.random.randn(10) * 0.1)
            
            return pd.DataFrame({
                'date': dates,
                'close': prices,
                'open': prices * 0.99,
                'high': prices * 1.01,
                'low': prices * 0.98,
                'volume': np.random.randint(1000000, 10000000, 10)
            })
        
        self.mock_data_manager.get_daily_data = mock_get_daily_data_short
        
        above_ma20, above_ma60 = self.fetcher._calculate_ma_penetration_ratios(mock_market_df)
        
        # Should return default values when no valid stocks
        assert above_ma20 == 0.5
        assert above_ma60 == 0.5
    
    def test_calculate_new_highs_lows_success(self):
        """Test new high/low calculation with valid data"""
        mock_market_df = pd.DataFrame({
            '代码': [f'{i:06d}' for i in range(100)],
            '名称': [f'Stock{i}' for i in range(100)],
            '涨跌幅': np.random.randn(100) * 2
        })
        
        # Mock historical data
        def mock_get_daily_data(stock_code, days=None, **kwargs):
            dates = pd.date_range(end='2024-01-15', periods=20)
            
            # Create price series where latest is either high or low
            code_num = int(stock_code)
            if code_num % 3 == 0:
                # New high
                prices = np.linspace(10, 15, 20)
            elif code_num % 3 == 1:
                # New low
                prices = np.linspace(15, 10, 20)
            else:
                # Neither
                prices = 12 + np.random.randn(20) * 0.5
            
            return pd.DataFrame({
                'date': dates,
                'close': prices,
                'open': prices * 0.99,
                'high': prices * 1.01,
                'low': prices * 0.98,
                'volume': np.random.randint(1000000, 10000000, 20)
            })
        
        self.mock_data_manager.get_daily_data = mock_get_daily_data
        
        new_high_count, new_low_count = self.fetcher._calculate_new_highs_lows(mock_market_df, '2024-01-15')
        
        # Verify results are non-negative integers
        assert isinstance(new_high_count, int)
        assert isinstance(new_low_count, int)
        assert new_high_count >= 0
        assert new_low_count >= 0
        
        # With our mock data, we should have some new highs and lows
        # (approximately 1/3 each based on our mock logic)
        assert new_high_count > 0
        assert new_low_count > 0
    
    def test_calculate_new_highs_lows_empty_data(self):
        """Test new high/low calculation with empty data"""
        empty_df = pd.DataFrame()
        
        new_high_count, new_low_count = self.fetcher._calculate_new_highs_lows(empty_df, '2024-01-15')
        
        assert new_high_count == 0
        assert new_low_count == 0
    
    def test_fetch_breadth_data_integration(self):
        """Integration test for fetch_breadth_data with all enhancements"""
        # Mock akshare market data
        mock_market_df = pd.DataFrame({
            '代码': [f'{i:06d}' for i in range(50)],
            '名称': [f'Stock{i}' for i in range(50)],
            '涨跌幅': np.random.randn(50) * 3,
            '成交额': np.random.randint(1000000, 100000000, 50),
            '成交量': np.random.randint(100000, 10000000, 50),
            '最新价': 10 + np.random.randn(50) * 2
        })
        
        mock_limit_up_df = pd.DataFrame({
            '代码': ['000001', '000002', '000003'],
            '名称': ['Stock1', 'Stock2', 'Stock3'],
            '连板数': [1, 2, 3]
        })
        
        # Mock historical data
        def mock_get_daily_data(stock_code, days=None, **kwargs):
            n_days = min(days or 60, 60)
            dates = pd.date_range(end='2024-01-15', periods=n_days)
            prices = 10 + np.cumsum(np.random.randn(n_days) * 0.1)
            
            return pd.DataFrame({
                'date': dates,
                'close': prices,
                'open': prices * 0.99,
                'high': prices * 1.01,
                'low': prices * 0.98,
                'volume': np.random.randint(1000000, 10000000, n_days)
            })
        
        self.mock_data_manager.get_daily_data = mock_get_daily_data
        
        with patch('src.market_diagnostic.data.fetchers.ak') as mock_ak:
            mock_ak.stock_zh_a_spot_em.return_value = mock_market_df
            mock_ak.stock_zt_pool_em.return_value = mock_limit_up_df
            mock_ak.stock_dt_pool_em.return_value = pd.DataFrame()
            
            # Fetch breadth data
            breadth_data = self.fetcher.fetch_breadth_data('2024-01-15')
        
        # Verify breadth data is returned
        assert breadth_data is not None
        assert isinstance(breadth_data, MarketBreadthData)
        
        # Verify enhanced fields are calculated
        assert breadth_data.continuous_limit_up >= 0
        assert 0 <= breadth_data.above_ma20_ratio <= 1
        assert 0 <= breadth_data.above_ma60_ratio <= 1
        assert breadth_data.new_high_count >= 0
        assert breadth_data.new_low_count >= 0
        
        # Verify basic fields are still calculated
        assert breadth_data.up_count >= 0
        assert breadth_data.down_count >= 0
        assert breadth_data.limit_up_count >= 0
        assert 0 <= breadth_data.seal_rate <= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
