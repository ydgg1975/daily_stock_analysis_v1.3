"""
Risk Feature Calculation

Computes risk indicators including realized volatility, ATR-based volatility,
volatility ratios, drawdowns, correlations, and optional C-VIX integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

try:
    from src.market_diagnostic.data.models import IndexDailyData, SectorDailyData
except ImportError:
    from market_diagnostic.data.models import IndexDailyData, SectorDailyData  # type: ignore[no-redef]


@dataclass
class RiskFeatures:
    """Risk-related features for market diagnostic."""
    
    realized_volatility: Dict[str, float]      # 20-day realized vol for each index
    atr_volatility: Dict[str, float]           # ATR-based vol for each index
    vol_ratio_short_long: Dict[str, float]     # 5-day vol / 20-day vol ratio
    index_drawdown: Dict[str, float]           # Drawdown from recent peak (%)
    cross_index_correlation: float             # Average pairwise correlation
    sector_correlation_elevation: float        # Current vs historical baseline
    cvix_value: Optional[float]                # C-VIX value if available
    cvix_percentile: Optional[float]           # C-VIX historical percentile
    has_cvix_data: bool                        # Whether C-VIX data is available


def _safe_std(series: np.ndarray, default: float = 0.0) -> float:
    """Compute standard deviation safely, returning default if insufficient data."""
    if len(series) < 2:
        return default
    return float(np.std(series, ddof=1))


def _safe_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Compute correlation coefficient safely, returning 0.0 if insufficient data."""
    if len(x) < 2 or len(y) < 2 or len(x) != len(y):
        return 0.0
    
    # Remove NaN values
    mask = ~(np.isnan(x) | np.isnan(y))
    x_clean = x[mask]
    y_clean = y[mask]
    
    if len(x_clean) < 2:
        return 0.0
    
    corr_matrix = np.corrcoef(x_clean, y_clean)
    return float(corr_matrix[0, 1]) if not np.isnan(corr_matrix[0, 1]) else 0.0


def compute_risk_features(
    index_data: Dict[str, IndexDailyData],
    sector_data: List[SectorDailyData],
    cvix_value: Optional[float] = None,
    cvix_historical: Optional[List[float]] = None,
) -> RiskFeatures:
    """
    Compute risk features from index and sector data.
    
    Parameters
    ----------
    index_data : Dict[str, IndexDailyData]
        Dictionary mapping index code to IndexDailyData
    sector_data : List[SectorDailyData]
        List of sector daily data for correlation analysis
    cvix_value : Optional[float]
        Current C-VIX value if available
    cvix_historical : Optional[List[float]]
        Historical C-VIX values for percentile calculation
        
    Returns
    -------
    RiskFeatures
        Computed risk indicators
        
    Requirements
    ------------
    8.1: Calculate realized volatility using 20-day rolling standard deviation
    8.2: Calculate ATR-based volatility for each major index
    8.3: Calculate short-term to long-term volatility ratio
    8.4: Calculate index drawdown from recent peaks
    8.5: Calculate cross-asset correlation (index-to-index)
    8.6: Calculate sector correlation elevation
    8.7: Incorporate C-VIX data when available
    """
    realized_volatility: Dict[str, float] = {}
    atr_volatility: Dict[str, float] = {}
    vol_ratio_short_long: Dict[str, float] = {}
    index_drawdown: Dict[str, float] = {}
    
    # Requirement 8.1: Calculate realized volatility (20-day rolling std of returns)
    # Requirement 8.2: Calculate ATR-based volatility
    # Requirement 8.3: Calculate short-term to long-term volatility ratio
    # Requirement 8.4: Calculate index drawdown from recent peaks
    for code, data in index_data.items():
        closes = np.array(data.close_series, dtype=float)
        
        if len(closes) >= 2:
            # Calculate returns
            returns = np.diff(closes) / closes[:-1]
            
            # Requirement 8.1: Realized volatility (20-day)
            if len(returns) >= 20:
                realized_vol = _safe_std(returns[-20:]) * np.sqrt(252)  # Annualized
            else:
                realized_vol = _safe_std(returns) * np.sqrt(252)
            realized_volatility[code] = realized_vol
            
            # Requirement 8.3: Short-term (5-day) to long-term (20-day) volatility ratio
            if len(returns) >= 20:
                vol_5d = _safe_std(returns[-5:], default=1e-6) * np.sqrt(252)
                vol_20d = _safe_std(returns[-20:], default=1e-6) * np.sqrt(252)
                vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1.0
            else:
                vol_ratio = 1.0
            vol_ratio_short_long[code] = vol_ratio
        else:
            realized_volatility[code] = 0.0
            vol_ratio_short_long[code] = 1.0
        
        # Requirement 8.2: ATR-based volatility
        # Get high/low series if available, otherwise use close as approximation
        high_series = getattr(data, "high_series", None)
        low_series = getattr(data, "low_series", None)
        
        if high_series is not None and low_series is not None and len(high_series) >= 2:
            highs = np.array(high_series, dtype=float)
            lows = np.array(low_series, dtype=float)
            
            # Calculate True Range
            h = highs[1:]
            l = lows[1:]
            pc = closes[:-1]
            
            tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
            
            # ATR-20
            period = min(20, len(tr))
            atr = float(np.mean(tr[-period:]))
            
            # Convert ATR to percentage volatility
            current_price = data.close
            atr_vol_pct = (atr / current_price) * 100 if current_price > 0 else 0.0
            atr_volatility[code] = atr_vol_pct
        else:
            # Fallback: use realized volatility
            atr_volatility[code] = realized_volatility.get(code, 0.0)
        
        # Requirement 8.4: Calculate drawdown from recent peak
        if len(closes) >= 20:
            # Find peak in last 60 days (or available data)
            peak = float(np.max(closes))
            current = data.close
            drawdown_pct = ((current - peak) / peak) * 100 if peak > 0 else 0.0
            # Drawdown is always <= 0; clamp to 0 if current is at or above peak
            index_drawdown[code] = min(drawdown_pct, 0.0)
        else:
            index_drawdown[code] = 0.0
    
    # Requirement 8.5: Calculate cross-asset correlation (index-to-index)
    # Compute pairwise correlations between all indices
    index_codes = list(index_data.keys())
    correlations: List[float] = []
    
    for i, code1 in enumerate(index_codes):
        for code2 in index_codes[i+1:]:
            data1 = index_data[code1]
            data2 = index_data[code2]
            
            # Use the shorter series length
            min_len = min(len(data1.close_series), len(data2.close_series))
            if min_len >= 20:
                series1 = np.array(data1.close_series[-min_len:], dtype=float)
                series2 = np.array(data2.close_series[-min_len:], dtype=float)
                
                # Calculate returns
                returns1 = np.diff(series1) / series1[:-1]
                returns2 = np.diff(series2) / series2[:-1]
                
                corr = _safe_correlation(returns1, returns2)
                correlations.append(corr)
    
    cross_index_correlation = float(np.mean(correlations)) if correlations else 0.0
    
    # Requirement 8.6: Calculate sector correlation elevation
    # Compute average pairwise correlation between sectors
    sector_returns: List[np.ndarray] = []
    
    for sector in sector_data:
        # Use 1-day, 5-day, 20-day returns as a proxy for sector return series
        # In a real implementation, we would need historical sector return series
        # For now, we'll use a simplified approach
        returns = np.array([sector.ret_1d, sector.ret_5d / 5, sector.ret_20d / 20], dtype=float)
        sector_returns.append(returns)
    
    sector_correlations: List[float] = []
    for i, returns1 in enumerate(sector_returns):
        for returns2 in sector_returns[i+1:]:
            corr = _safe_correlation(returns1, returns2)
            sector_correlations.append(corr)
    
    current_sector_corr = float(np.mean(sector_correlations)) if sector_correlations else 0.0
    
    # Historical baseline (simplified: assume 0.3 as typical baseline)
    # In production, this should be calculated from historical data
    historical_baseline = 0.3
    sector_correlation_elevation = current_sector_corr - historical_baseline
    
    # Requirement 8.7: Incorporate C-VIX data when available
    has_cvix_data = cvix_value is not None
    cvix_percentile = None
    
    if has_cvix_data and cvix_historical is not None and len(cvix_historical) > 0:
        # Calculate percentile of current C-VIX value
        cvix_array = np.array(cvix_historical, dtype=float)
        cvix_percentile = float(np.sum(cvix_array <= cvix_value) / len(cvix_array) * 100)
    
    return RiskFeatures(
        realized_volatility=realized_volatility,
        atr_volatility=atr_volatility,
        vol_ratio_short_long=vol_ratio_short_long,
        index_drawdown=index_drawdown,
        cross_index_correlation=cross_index_correlation,
        sector_correlation_elevation=sector_correlation_elevation,
        cvix_value=cvix_value,
        cvix_percentile=cvix_percentile,
        has_cvix_data=has_cvix_data,
    )
