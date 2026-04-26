"""
Unit tests for risk feature calculation.

Tests the compute_risk_features function with various scenarios including
edge cases and data availability conditions.
"""

import pytest
import numpy as np
from typing import Dict, List

from src.market_diagnostic.data.models import IndexDailyData, SectorDailyData
from src.market_diagnostic.features.risk import compute_risk_features, RiskFeatures


def create_test_index_data(
    code: str,
    name: str,
    close: float,
    close_series: List[float],
    high_series: List[float] = None,
    low_series: List[float] = None,
) -> IndexDailyData:
    """Helper to create test IndexDailyData."""
    data = IndexDailyData(
        code=code,
        name=name,
        date="2024-01-15",
        close=close,
        open=close * 0.99,
        high=close * 1.01,
        low=close * 0.98,
        prev_close=close * 0.99,
        volume=1000000.0,
        amount=close * 1000000.0,
        change_pct=1.0,
        close_series=close_series,
        volume_series=[1000000.0] * len(close_series),
    )
    
    if high_series is not None:
        data.high_series = high_series
    if low_series is not None:
        data.low_series = low_series
    
    return data


def create_test_sector_data(
    industry_code: str,
    industry_name: str,
    ret_1d: float,
    ret_5d: float,
    ret_20d: float,
) -> SectorDailyData:
    """Helper to create test SectorDailyData."""
    return SectorDailyData(
        date="2024-01-15",
        industry_code=industry_code,
        industry_name=industry_name,
        ret_1d=ret_1d,
        ret_5d=ret_5d,
        ret_20d=ret_20d,
        excess_ret_1d=ret_1d - 0.5,
        breadth_20=0.6,
        new_high_ratio=0.1,
        amount=100.0,
        amount_share=0.05,
        amount_share_delta=0.01,
        limit_up_count=5,
        turnover=2.5,
    )


class TestRiskFeatures:
    """Test suite for risk feature calculation."""
    
    def test_basic_risk_calculation(self):
        """Test basic risk feature calculation with sufficient data."""
        # Create test data with 60 days of history
        close_series = [3000 + i * 10 + np.random.randn() * 5 for i in range(60)]
        high_series = [c * 1.01 for c in close_series]
        low_series = [c * 0.99 for c in close_series]
        
        index_data = {
            "sh000300": create_test_index_data(
                "sh000300", "沪深300", 3600.0, close_series, high_series, low_series
            ),
            "sz399006": create_test_index_data(
                "sz399006", "创业板指", 2400.0, 
                [2000 + i * 8 + np.random.randn() * 4 for i in range(60)],
                [c * 1.01 for c in [2000 + i * 8 for i in range(60)]],
                [c * 0.99 for c in [2000 + i * 8 for i in range(60)]],
            ),
        }
        
        sector_data = [
            create_test_sector_data("BK0447", "电子", 1.5, 3.0, 8.0),
            create_test_sector_data("BK0448", "医药", 0.8, 2.0, 5.0),
            create_test_sector_data("BK0449", "银行", -0.5, -1.0, -2.0),
        ]
        
        result = compute_risk_features(index_data, sector_data)
        
        # Verify all required fields are present
        assert isinstance(result, RiskFeatures)
        assert "sh000300" in result.realized_volatility
        assert "sz399006" in result.realized_volatility
        assert "sh000300" in result.atr_volatility
        assert "sh000300" in result.vol_ratio_short_long
        assert "sh000300" in result.index_drawdown
        
        # Verify volatility values are reasonable (positive)
        assert result.realized_volatility["sh000300"] >= 0
        assert result.atr_volatility["sh000300"] >= 0
        
        # Verify vol ratio is positive
        assert result.vol_ratio_short_long["sh000300"] > 0
        
        # Verify correlation is in valid range [-1, 1]
        assert -1.0 <= result.cross_index_correlation <= 1.0
        
        # Verify drawdown is non-positive (or zero if at peak)
        assert result.index_drawdown["sh000300"] <= 0
    
    def test_insufficient_data(self):
        """Test risk calculation with insufficient historical data."""
        # Only 5 days of data
        close_series = [3000.0, 3010.0, 3020.0, 3015.0, 3025.0]
        
        index_data = {
            "sh000300": create_test_index_data(
                "sh000300", "沪深300", 3025.0, close_series
            ),
        }
        
        sector_data = [
            create_test_sector_data("BK0447", "电子", 1.5, 3.0, 8.0),
        ]
        
        result = compute_risk_features(index_data, sector_data)
        
        # Should still return valid result with defaults
        assert isinstance(result, RiskFeatures)
        assert "sh000300" in result.realized_volatility
        assert result.realized_volatility["sh000300"] >= 0
    
    def test_with_cvix_data(self):
        """Test risk calculation with C-VIX data available."""
        close_series = [3000 + i * 10 for i in range(60)]
        
        index_data = {
            "sh000300": create_test_index_data(
                "sh000300", "沪深300", 3600.0, close_series
            ),
        }
        
        sector_data = [
            create_test_sector_data("BK0447", "电子", 1.5, 3.0, 8.0),
        ]
        
        # Provide C-VIX data
        cvix_value = 25.0
        cvix_historical = [20.0, 22.0, 24.0, 26.0, 28.0, 30.0]
        
        result = compute_risk_features(
            index_data, sector_data, cvix_value, cvix_historical
        )
        
        # Verify C-VIX data is incorporated
        assert result.has_cvix_data is True
        assert result.cvix_value == 25.0
        assert result.cvix_percentile is not None
        assert 0 <= result.cvix_percentile <= 100
    
    def test_without_cvix_data(self):
        """Test risk calculation without C-VIX data."""
        close_series = [3000 + i * 10 for i in range(60)]
        
        index_data = {
            "sh000300": create_test_index_data(
                "sh000300", "沪深300", 3600.0, close_series
            ),
        }
        
        sector_data = [
            create_test_sector_data("BK0447", "电子", 1.5, 3.0, 8.0),
        ]
        
        result = compute_risk_features(index_data, sector_data)
        
        # Verify C-VIX data is not present
        assert result.has_cvix_data is False
        assert result.cvix_value is None
        assert result.cvix_percentile is None
    
    def test_drawdown_calculation(self):
        """Test drawdown calculation from peak."""
        # Create series with clear peak and drawdown
        close_series = [3000, 3100, 3200, 3300, 3400, 3350, 3300, 3250, 3200, 3150]
        close_series.extend([3100 + i for i in range(50)])  # Extend to 60 days
        
        index_data = {
            "sh000300": create_test_index_data(
                "sh000300", "沪深300", 3150.0, close_series
            ),
        }
        
        sector_data = [
            create_test_sector_data("BK0447", "电子", 1.5, 3.0, 8.0),
        ]
        
        result = compute_risk_features(index_data, sector_data)
        
        # Peak is 3400, current is 3150, drawdown should be negative
        # Drawdown = (3150 - 3400) / 3400 * 100 ≈ -7.35%
        assert result.index_drawdown["sh000300"] < 0
        assert result.index_drawdown["sh000300"] > -10  # Should be around -7.35%
    
    def test_volatility_ratio(self):
        """Test short-term to long-term volatility ratio."""
        # Create series with increasing volatility in recent days
        base_series = [3000 + i for i in range(40)]
        # Add high volatility in last 5 days
        volatile_series = [3040 + i * 20 * (-1)**i for i in range(20)]
        close_series = base_series + volatile_series
        
        index_data = {
            "sh000300": create_test_index_data(
                "sh000300", "沪深300", volatile_series[-1], close_series
            ),
        }
        
        sector_data = [
            create_test_sector_data("BK0447", "电子", 1.5, 3.0, 8.0),
        ]
        
        result = compute_risk_features(index_data, sector_data)
        
        # Short-term volatility should be higher than long-term
        # So ratio should be > 1.0
        assert result.vol_ratio_short_long["sh000300"] > 1.0
    
    def test_cross_index_correlation(self):
        """Test cross-index correlation calculation."""
        # Create two highly correlated series using deterministic data
        # Use a strong trend with minimal noise to ensure high correlation
        base = [3000 + i * 10 for i in range(60)]
        close_series_1 = [b + (i % 3) * 2 for i, b in enumerate(base)]  # deterministic small variation
        close_series_2 = [b * 0.8 + (i % 3) * 1.6 for i, b in enumerate(base)]  # same pattern, scaled
        
        index_data = {
            "sh000300": create_test_index_data(
                "sh000300", "沪深300", close_series_1[-1], close_series_1
            ),
            "sz399006": create_test_index_data(
                "sz399006", "创业板指", close_series_2[-1], close_series_2
            ),
        }
        
        sector_data = [
            create_test_sector_data("BK0447", "电子", 1.5, 3.0, 8.0),
        ]
        
        result = compute_risk_features(index_data, sector_data)
        
        # Correlation should be positive and reasonably high
        assert result.cross_index_correlation > 0.5
        assert result.cross_index_correlation <= 1.0
    
    def test_sector_correlation_elevation(self):
        """Test sector correlation elevation calculation."""
        close_series = [3000 + i * 10 for i in range(60)]
        
        index_data = {
            "sh000300": create_test_index_data(
                "sh000300", "沪深300", 3600.0, close_series
            ),
        }
        
        # Create sectors with varying correlations
        sector_data = [
            create_test_sector_data("BK0447", "电子", 2.0, 5.0, 10.0),
            create_test_sector_data("BK0448", "医药", 1.8, 4.5, 9.0),
            create_test_sector_data("BK0449", "银行", 1.5, 4.0, 8.0),
            create_test_sector_data("BK0450", "地产", -1.0, -2.0, -4.0),
        ]
        
        result = compute_risk_features(index_data, sector_data)
        
        # Sector correlation elevation should be calculated
        # (difference from historical baseline of 0.3)
        assert isinstance(result.sector_correlation_elevation, float)
    
    def test_empty_sector_data(self):
        """Test risk calculation with empty sector data."""
        close_series = [3000 + i * 10 for i in range(60)]
        
        index_data = {
            "sh000300": create_test_index_data(
                "sh000300", "沪深300", 3600.0, close_series
            ),
        }
        
        sector_data = []
        
        result = compute_risk_features(index_data, sector_data)
        
        # Should still return valid result
        assert isinstance(result, RiskFeatures)
        assert result.sector_correlation_elevation == -0.3  # 0.0 - 0.3 baseline
    
    def test_single_index(self):
        """Test risk calculation with only one index."""
        close_series = [3000 + i * 10 for i in range(60)]
        
        index_data = {
            "sh000300": create_test_index_data(
                "sh000300", "沪深300", 3600.0, close_series
            ),
        }
        
        sector_data = [
            create_test_sector_data("BK0447", "电子", 1.5, 3.0, 8.0),
        ]
        
        result = compute_risk_features(index_data, sector_data)
        
        # With only one index, cross-correlation should be 0.0 (no pairs)
        assert result.cross_index_correlation == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
