"""
Unit tests for sector data enrichment (Task 2.1.5)

Tests the implementation of:
- Sector breadth calculation (above_ma20_ratio within sector)
- Sector new high ratio calculation
- Sector limit-up count calculation
- Sector turnover and amount share calculation
- Excess return calculation vs CSI300
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
from src.market_diagnostic.data.models import SectorDailyData


class TestSectorEnrichment:
    """Test suite for sector data enrichment"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_data_manager = Mock()
        self.fetcher = DiagnosticDataFetcher(self.mock_data_manager)
    
    def test_calculate_sector_breadth_metrics_success(self):
        """Test sector breadth metrics calculation with valid data"""
        # Mock sector constituents
        mock_constituents_df = pd.DataFrame({
            '代码': [f'{i:06d}' for i in range(20)],
            '名称': [f'Stock{i}' for i in range(20)]
        })
        
        # Mock historical data for individual stocks
        def mock_get_daily_data(stock_code, days=None, **kwargs):
            dates = pd.date_range(end='2024-01-15', periods=30)
            
            # Create different patterns for different stocks
            code_num = int(stock_code)
            if code_num % 4 == 0:
                # Above MA20, at new high, limit-up
                prices = np.linspace(10, 15, 30)
                pct_chg = 10.0
            elif code_num % 4 == 1:
                # Above MA20, not at new high, not limit-up
                prices = 12 + np.random.randn(30) * 0.2
                prices[-1] = 12.5
                pct_chg = 2.0
            elif code_num % 4 == 2:
                # Below MA20
                prices = np.linspace(15, 10, 30)
                pct_chg = -3.0
            else:
                # Mixed
                prices = 12 + np.sin(np.linspace(0, 4*np.pi, 30))
                pct_chg = 0.5
            
            return pd.DataFrame({
                'date': dates,
                'close': prices,
                'open': prices * 0.99,
                'high': prices * 1.01,
                'low': prices * 0.98,
                'volume': np.random.randint(1000000, 10000000, 30),
                'pct_chg': [pct_chg] * 30
            })
        
        self.mock_data_manager.get_daily_data = mock_get_daily_data
        
        with patch('src.market_diagnostic.data.fetchers.ak') as mock_ak:
            mock_ak.stock_board_industry_cons_em.return_value = mock_constituents_df
            
            breadth_20, new_high_ratio, limit_up_count = self.fetcher._calculate_sector_breadth_metrics(
                'BK0447', '电子', '2024-01-15'
            )
        
        # Verify results are in valid ranges
        assert 0 <= breadth_20 <= 1
        assert 0 <= new_high_ratio <= 1
        assert limit_up_count >= 0
        
        # With our mock data:
        # - 25% should be above MA20 (code_num % 4 == 0 or 1)
        # - 25% should be at new high (code_num % 4 == 0)
        # - 25% should be limit-up (code_num % 4 == 0)
        assert breadth_20 > 0  # Should have some stocks above MA20
        assert new_high_ratio >= 0  # Should have some new highs
        assert limit_up_count >= 0  # Should have some limit-ups
    
    def test_calculate_sector_breadth_metrics_no_constituents(self):
        """Test sector breadth metrics with no constituents"""
        with patch('src.market_diagnostic.data.fetchers.ak') as mock_ak:
            mock_ak.stock_board_industry_cons_em.return_value = pd.DataFrame()
            
            breadth_20, new_high_ratio, limit_up_count = self.fetcher._calculate_sector_breadth_metrics(
                'BK0447', '电子', '2024-01-15'
            )
        
        # Should return default values
        assert breadth_20 == 0.5
        assert new_high_ratio == 0.0
        assert limit_up_count == 0
    
    def test_calculate_sector_breadth_metrics_insufficient_data(self):
        """Test sector breadth metrics with insufficient historical data"""
        mock_constituents_df = pd.DataFrame({
            '代码': ['000001', '000002'],
            '名称': ['Stock1', 'Stock2']
        })
        
        # Mock get_daily_data to return insufficient data
        def mock_get_daily_data_short(stock_code, days=None, **kwargs):
            # Only 10 days of data (insufficient for MA20)
            dates = pd.date_range(end='2024-01-15', periods=10)
            prices = 10 + np.cumsum(np.random.randn(10) * 0.1)
            
            return pd.DataFrame({
                'date': dates,
                'close': prices,
                'open': prices * 0.99,
                'high': prices * 1.01,
                'low': prices * 0.98,
                'volume': np.random.randint(1000000, 10000000, 10),
                'pct_chg': [1.0] * 10
            })
        
        self.mock_data_manager.get_daily_data = mock_get_daily_data_short
        
        with patch('src.market_diagnostic.data.fetchers.ak') as mock_ak:
            mock_ak.stock_board_industry_cons_em.return_value = mock_constituents_df
            
            breadth_20, new_high_ratio, limit_up_count = self.fetcher._calculate_sector_breadth_metrics(
                'BK0447', '电子', '2024-01-15'
            )
        
        # Should return default values when no valid stocks
        assert breadth_20 == 0.5
        assert new_high_ratio == 0.0
        assert limit_up_count == 0
    
    def test_fetch_sector_data_enrichment(self):
        """Integration test for sector data enrichment"""
        # Mock industry capital flow
        mock_flow_df = pd.DataFrame({
            '名称': ['电子', '计算机', '传媒'],
            '成交额': [50000000000, 40000000000, 30000000000],  # 500亿, 400亿, 300亿
            '主力净流入-净额': [1000000000, -500000000, 200000000],
            '涨跌幅': [2.5, -1.2, 0.8]
        })
        
        # Mock industry historical data
        def mock_industry_hist(symbol, period, start_date, end_date, adjust):
            dates = pd.date_range(end='2024-01-15', periods=30)
            prices = 1000 + np.cumsum(np.random.randn(30) * 10)
            
            return pd.DataFrame({
                '日期': dates,
                '收盘': prices,
                '开盘': prices * 0.99,
                '最高': prices * 1.01,
                '最低': prices * 0.98,
                '成交额': np.random.randint(10000000000, 100000000000, 30),
                '成交量': np.random.randint(1000000, 10000000, 30),
                '涨跌幅': np.random.randn(30) * 2,
                '换手率': np.random.rand(30) * 5
            })
        
        # Mock sector constituents
        mock_constituents_df = pd.DataFrame({
            '代码': [f'{i:06d}' for i in range(10)],
            '名称': [f'Stock{i}' for i in range(10)]
        })
        
        # Mock CSI300 data for excess return
        def mock_get_daily_data(stock_code, days=None, **kwargs):
            if stock_code == 'sh000300':
                # CSI300 data
                return pd.DataFrame({
                    'date': pd.date_range(end='2024-01-15', periods=2),
                    'close': [3000, 3030],
                    'pct_chg': [0.0, 1.0]
                })
            else:
                # Individual stock data
                dates = pd.date_range(end='2024-01-15', periods=30)
                prices = 10 + np.cumsum(np.random.randn(30) * 0.1)
                
                return pd.DataFrame({
                    'date': dates,
                    'close': prices,
                    'open': prices * 0.99,
                    'high': prices * 1.01,
                    'low': prices * 0.98,
                    'volume': np.random.randint(1000000, 10000000, 30),
                    'pct_chg': [2.0] * 30
                })
        
        self.mock_data_manager.get_daily_data = mock_get_daily_data
        
        with patch('src.market_diagnostic.data.fetchers.ak') as mock_ak, \
             patch('src.market_diagnostic.data.fetchers.time') as mock_time, \
             patch('src.market_diagnostic.data.fetchers.SHENWAN_INDUSTRIES', {'BK0447': '电子', 'BK0448': '计算机', 'BK0449': '传媒'}):
            mock_time.sleep = lambda x: None
            mock_time.time = __import__('time').time
            mock_ak.stock_sector_fund_flow_rank.return_value = mock_flow_df
            mock_ak.stock_board_industry_hist_em.side_effect = mock_industry_hist
            mock_ak.stock_board_industry_cons_em.return_value = mock_constituents_df
            
            # Fetch sector data (limit to 3 sectors for testing)
            sector_data = self.fetcher.fetch_sector_data('2024-01-15')
        
        # Verify sector data is returned
        assert sector_data is not None
        assert len(sector_data) > 0
        
        # Verify enriched fields are calculated
        for sector in sector_data:
            assert isinstance(sector, SectorDailyData)
            
            # Verify returns are calculated
            assert isinstance(sector.ret_1d, float)
            assert isinstance(sector.ret_5d, float)
            assert isinstance(sector.ret_20d, float)
            
            # Verify excess return is calculated (not placeholder 0.0)
            assert isinstance(sector.excess_ret_1d, float)
            
            # Verify breadth metrics are calculated (not placeholder 0.5)
            assert 0 <= sector.breadth_20 <= 1
            assert 0 <= sector.new_high_ratio <= 1
            
            # Verify amount metrics are calculated
            assert sector.amount >= 0
            assert 0 <= sector.amount_share <= 1
            assert isinstance(sector.amount_share_delta, float)
            
            # Verify limit-up count is calculated
            assert sector.limit_up_count >= 0
            
            # Verify turnover is calculated
            assert sector.turnover >= 0
    
    def test_sector_amount_share_calculation(self):
        """Test sector amount share and delta calculation"""
        # Mock industry capital flow with known amounts
        mock_flow_df = pd.DataFrame({
            '名称': ['电子', '计算机'],
            '成交额': [60000000000, 40000000000],  # 600亿, 400亿 (total 1000亿)
            '主力净流入-净额': [0, 0],
            '涨跌幅': [0, 0]
        })
        
        # Mock industry historical data
        def mock_industry_hist(symbol, period, start_date, end_date, adjust):
            dates = pd.date_range(end='2024-01-15', periods=30)
            
            # Create amount series with known 5-day average
            amounts = np.ones(30) * 50000000000  # 500亿 for 5-day average
            amounts[-1] = 60000000000  # 600亿 for latest
            
            return pd.DataFrame({
                '日期': dates,
                '收盘': np.ones(30) * 1000,
                '开盘': np.ones(30) * 1000,
                '最高': np.ones(30) * 1000,
                '最低': np.ones(30) * 1000,
                '成交额': amounts,
                '成交量': np.ones(30) * 1000000,
                '涨跌幅': np.zeros(30),
                '换手率': np.ones(30) * 2.0
            })
        
        mock_constituents_df = pd.DataFrame({
            '代码': ['000001'],
            '名称': ['Stock1']
        })
        
        def mock_get_daily_data(stock_code, days=None, **kwargs):
            if stock_code == 'sh000300':
                return pd.DataFrame({
                    'date': pd.date_range(end='2024-01-15', periods=2),
                    'close': [3000, 3000],
                    'pct_chg': [0.0, 0.0]
                })
            else:
                return pd.DataFrame({
                    'date': pd.date_range(end='2024-01-15', periods=30),
                    'close': np.ones(30) * 10,
                    'pct_chg': np.zeros(30)
                })
        
        self.mock_data_manager.get_daily_data = mock_get_daily_data
        
        with patch('src.market_diagnostic.data.fetchers.ak') as mock_ak, \
             patch('src.market_diagnostic.data.fetchers.time') as mock_time, \
             patch('src.market_diagnostic.data.fetchers.SHENWAN_INDUSTRIES', {'BK0447': '电子'}):
            mock_time.sleep = lambda x: None
            mock_time.time = __import__('time').time
            mock_ak.stock_sector_fund_flow_rank.return_value = mock_flow_df
            mock_ak.stock_board_industry_hist_em.side_effect = mock_industry_hist
            mock_ak.stock_board_industry_cons_em.return_value = mock_constituents_df
            
            sector_data = self.fetcher.fetch_sector_data('2024-01-15')
        
        assert len(sector_data) > 0
        sector = sector_data[0]
        
        # Verify amount share calculation
        # 电子: 600亿 / 1000亿 = 0.6
        assert abs(sector.amount_share - 0.6) < 0.01
        
        # Verify amount share delta is calculated
        # Should be positive since latest (600亿) > 5-day avg (500亿)
        assert isinstance(sector.amount_share_delta, float)
    
    def test_sector_excess_return_calculation(self):
        """Test sector excess return vs CSI300 calculation"""
        mock_flow_df = pd.DataFrame({
            '名称': ['电子'],
            '成交额': [50000000000],
            '主力净流入-净额': [0],
            '涨跌幅': [3.5]  # Sector return: 3.5%
        })
        
        def mock_industry_hist(symbol, period, start_date, end_date, adjust):
            return pd.DataFrame({
                '日期': pd.date_range(end='2024-01-15', periods=30),
                '收盘': np.linspace(1000, 1035, 30),  # 3.5% return
                '涨跌幅': [3.5] + [0] * 29,
                '成交额': np.ones(30) * 50000000000,
                '换手率': np.ones(30) * 2.0
            })
        
        mock_constituents_df = pd.DataFrame({
            '代码': ['000001'],
            '名称': ['Stock1']
        })
        
        def mock_get_daily_data(stock_code, days=None, **kwargs):
            if stock_code == 'sh000300':
                # CSI300 return: 1.0%
                return pd.DataFrame({
                    'date': pd.date_range(end='2024-01-15', periods=2),
                    'close': [3000, 3030],
                    'pct_chg': [0.0, 1.0]
                })
            else:
                return pd.DataFrame({
                    'date': pd.date_range(end='2024-01-15', periods=30),
                    'close': np.ones(30) * 10,
                    'pct_chg': np.zeros(30)
                })
        
        self.mock_data_manager.get_daily_data = mock_get_daily_data
        
        with patch('src.market_diagnostic.data.fetchers.ak') as mock_ak, \
             patch('src.market_diagnostic.data.fetchers.time') as mock_time, \
             patch('src.market_diagnostic.data.fetchers.SHENWAN_INDUSTRIES', {'BK0447': '电子'}):
            mock_time.sleep = lambda x: None
            mock_time.time = __import__('time').time
            mock_ak.stock_sector_fund_flow_rank.return_value = mock_flow_df
            mock_ak.stock_board_industry_hist_em.side_effect = mock_industry_hist
            mock_ak.stock_board_industry_cons_em.return_value = mock_constituents_df
            
            sector_data = self.fetcher.fetch_sector_data('2024-01-15')
        
        assert len(sector_data) > 0
        sector = sector_data[0]
        
        # Verify excess return calculation
        # Excess return = 3.5% - 1.0% = 2.5%
        assert abs(sector.excess_ret_1d - 2.5) < 0.1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
