"""
Breadth Feature Calculation

Computes market breadth indicators from MarketBreadthData.
Includes up/down ratio, limit-up rate, seal rate, MA penetration ratios,
new high ratio, turnover deviations, and composite breadth score.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    from src.market_diagnostic.data.models import MarketBreadthData
except ImportError:
    from market_diagnostic.data.models import MarketBreadthData  # type: ignore[no-redef]


@dataclass
class BreadthFeatures:
    """Market breadth features."""
    
    up_down_ratio: float          # up_count / down_count (0 if down_count==0)
    limit_up_rate: float          # limit_up_count / total_count
    seal_rate: float              # limit_up_count / (limit_up_count + explode_count)
    above_ma20_ratio: float       # ratio of stocks above MA20
    above_ma60_ratio: float       # ratio of stocks above MA60
    new_high_ratio: float         # new_high_count / total_count
    amount_deviation_5d: float    # (amount - amount_ma5) / amount_ma5
    amount_deviation_20d: float   # (amount - amount_ma20) / amount_ma20
    breadth_score: float          # composite 0-100


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def _normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize value to [0, 1] range, clamping to bounds."""
    if max_val == min_val:
        return 0.5
    normalized = (value - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))


def compute_breadth_features(data: MarketBreadthData) -> BreadthFeatures:
    """
    Compute breadth features from market breadth data.
    
    Parameters
    ----------
    data : MarketBreadthData
        Market-wide breadth metrics
        
    Returns
    -------
    BreadthFeatures
        Computed breadth indicators
        
    Requirements
    ------------
    3.1: Calculate up/down stock count ratio
    3.2: Calculate limit-up rate
    3.3: Calculate seal rate with division-by-zero handling
    3.4: Calculate MA penetration ratios
    3.5: Calculate new high ratio
    3.6: Calculate turnover amount deviations
    3.7: Compute composite breadth score (0-100)
    """
    # Total stock count
    total_count = data.up_count + data.down_count + data.flat_count
    
    # Requirement 3.1: Up/down ratio
    up_down_ratio = _safe_divide(data.up_count, data.down_count, default=0.0)
    
    # Requirement 3.2: Limit-up rate
    limit_up_rate = _safe_divide(data.limit_up_count, total_count, default=0.0)
    
    # Requirement 3.3: Seal rate (division-by-zero handling)
    seal_rate = _safe_divide(
        data.limit_up_count,
        data.limit_up_count + data.explode_count,
        default=0.0
    )
    
    # Requirement 3.4: MA penetration ratios (already in data)
    above_ma20_ratio = data.above_ma20_ratio
    above_ma60_ratio = data.above_ma60_ratio
    
    # Requirement 3.5: New high ratio
    new_high_ratio = _safe_divide(data.new_high_count, total_count, default=0.0)
    
    # Requirement 3.6: Turnover amount deviations
    amount_deviation_5d = _safe_divide(
        data.total_amount - data.amount_ma5,
        data.amount_ma5,
        default=0.0
    )
    amount_deviation_20d = _safe_divide(
        data.total_amount - data.amount_ma20,
        data.amount_ma20,
        default=0.0
    )
    
    # Requirement 3.7: Composite breadth score (0-100)
    # Weighted average of normalized sub-metrics
    score_components = [
        20 * _normalize(above_ma20_ratio, 0, 1),
        20 * _normalize(new_high_ratio, 0, 0.05),
        20 * _normalize(limit_up_rate, 0, 0.03),
        20 * _normalize(seal_rate, 0, 1),
        20 * _normalize(up_down_ratio, 0, 3),
    ]
    breadth_score = sum(score_components)
    breadth_score = max(0.0, min(100.0, breadth_score))
    
    return BreadthFeatures(
        up_down_ratio=up_down_ratio,
        limit_up_rate=limit_up_rate,
        seal_rate=seal_rate,
        above_ma20_ratio=above_ma20_ratio,
        above_ma60_ratio=above_ma60_ratio,
        new_high_ratio=new_high_ratio,
        amount_deviation_5d=amount_deviation_5d,
        amount_deviation_20d=amount_deviation_20d,
        breadth_score=breadth_score,
    )
