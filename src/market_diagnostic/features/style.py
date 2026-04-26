"""
Style Feature Calculation

Computes market style indicators from index data.
Includes relative strength ratios, multi-period returns, amount shares,
and dominant style classification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

try:
    from src.market_diagnostic.data.models import IndexDailyData
except ImportError:
    from market_diagnostic.data.models import IndexDailyData  # type: ignore[no-redef]


@dataclass
class StyleFeatures:
    """Market style features."""
    
    # Relative strength (close ratio)
    rs_large_vs_small: float      # sh000016 / sz399006 (上证50 vs 创业板指)
    rs_300_vs_1000: float         # sh000300 / sh000852 (沪深300 vs 中证1000)
    rs_500_vs_1000: float         # sh000905 / sh000852 (中证500 vs 中证1000)
    
    # Returns per style index
    ret_1d: Dict[str, float]      # {code: 1d return}
    ret_5d: Dict[str, float]      # {code: 5d return}
    ret_20d: Dict[str, float]     # {code: 20d return}
    
    # Amount share
    amount_share: Dict[str, float]  # {code: amount share of total}
    
    # Dominant style
    dominant_style: str           # "大盘防守" / "小盘进攻" / "成长主导" / "红利防守" / "风格冲突"


def _safe_divide(numerator: float, denominator: float, default: float = 1.0) -> float:
    """Safe division that returns default when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def _compute_return(close_series: list[float], periods: int) -> float:
    """
    Compute N-period return from close series.
    
    Parameters
    ----------
    close_series : list[float]
        Historical closing prices (oldest to newest)
    periods : int
        Number of periods (1 for 1d, 5 for 5d, 20 for 20d)
        
    Returns
    -------
    float
        Return as decimal (e.g., 0.05 for 5% gain)
    """
    if len(close_series) < periods + 1:
        return 0.0
    
    current = close_series[-1]
    past = close_series[-(periods + 1)]
    
    if past == 0:
        return 0.0
    
    return (current - past) / past


def _classify_dominant_style(
    rs_large_vs_small: float,
    rs_300_vs_1000: float,
    rs_500_vs_1000: float,
) -> str:
    """
    Classify dominant market style based on relative strength ratios.
    
    Rules:
    - "大盘防守": rs_large_vs_small > 1.02 AND rs_300_vs_1000 > 1.01
    - "小盘进攻": rs_large_vs_small < 0.98 AND rs_300_vs_1000 < 0.99
    - "成长主导": rs_300_vs_1000 < 0.98 (small/growth outperforming)
    - "红利防守": rs_large_vs_small > 1.02 AND rs_300_vs_1000 > 1.02
    - "风格冲突": conflicting signals (default)
    
    Requirements: 5.6
    """
    # Check for 红利防守 first (most specific)
    if rs_large_vs_small > 1.02 and rs_300_vs_1000 > 1.02:
        return "红利防守"
    
    # Check for 大盘防守
    if rs_large_vs_small > 1.02 and rs_300_vs_1000 > 1.01:
        return "大盘防守"
    
    # Check for 小盘进攻
    if rs_large_vs_small < 0.98 and rs_300_vs_1000 < 0.99:
        return "小盘进攻"
    
    # Check for 成长主导
    if rs_300_vs_1000 < 0.98:
        return "成长主导"
    
    # Default: conflicting signals
    return "风格冲突"


def compute_style_features(index_data: Dict[str, IndexDailyData]) -> StyleFeatures:
    """
    Compute style features from index data.
    
    Parameters
    ----------
    index_data : Dict[str, IndexDailyData]
        Dictionary mapping index code to IndexDailyData
        Expected codes: sh000016, sz399006, sh000300, sh000852, sh000905
        
    Returns
    -------
    StyleFeatures
        Computed style indicators
        
    Requirements
    ------------
    5.1: Calculate relative strength between large-cap and small-cap
    5.2: Calculate relative strength between 沪深300 and 中证1000
    5.3: Calculate relative strength between 中证500 and 中证1000
    5.4: Calculate 1-day, 5-day, and 20-day returns for each style index
    5.6: Identify dominant style
    """
    # Extract index closes
    sh000016_close = index_data.get("sh000016", index_data.get("000016"))
    sz399006_close = index_data.get("sz399006", index_data.get("399006"))
    sh000300_close = index_data.get("sh000300", index_data.get("000300"))
    sh000852_close = index_data.get("sh000852", index_data.get("000852"))
    sh000905_close = index_data.get("sh000905", index_data.get("000905"))
    
    # Requirement 5.1: Large-cap vs small-cap relative strength
    if sh000016_close and sz399006_close:
        rs_large_vs_small = _safe_divide(sh000016_close.close, sz399006_close.close, 1.0)
    else:
        rs_large_vs_small = 1.0
    
    # Requirement 5.2: CSI300 vs CSI1000 relative strength
    if sh000300_close and sh000852_close:
        rs_300_vs_1000 = _safe_divide(sh000300_close.close, sh000852_close.close, 1.0)
    else:
        rs_300_vs_1000 = 1.0
    
    # Requirement 5.3: CSI500 vs CSI1000 relative strength
    if sh000905_close and sh000852_close:
        rs_500_vs_1000 = _safe_divide(sh000905_close.close, sh000852_close.close, 1.0)
    else:
        rs_500_vs_1000 = 1.0
    
    # Requirement 5.4: Multi-period returns
    ret_1d: Dict[str, float] = {}
    ret_5d: Dict[str, float] = {}
    ret_20d: Dict[str, float] = {}
    
    for code, data in index_data.items():
        ret_1d[code] = _compute_return(data.close_series, 1)
        ret_5d[code] = _compute_return(data.close_series, 5)
        ret_20d[code] = _compute_return(data.close_series, 20)
    
    # Amount share calculation
    total_amount = sum(data.amount for data in index_data.values())
    amount_share: Dict[str, float] = {}
    
    for code, data in index_data.items():
        amount_share[code] = _safe_divide(data.amount, total_amount, 0.0)
    
    # Requirement 5.6: Classify dominant style
    dominant_style = _classify_dominant_style(
        rs_large_vs_small,
        rs_300_vs_1000,
        rs_500_vs_1000,
    )
    
    return StyleFeatures(
        rs_large_vs_small=rs_large_vs_small,
        rs_300_vs_1000=rs_300_vs_1000,
        rs_500_vs_1000=rs_500_vs_1000,
        ret_1d=ret_1d,
        ret_5d=ret_5d,
        ret_20d=ret_20d,
        amount_share=amount_share,
        dominant_style=dominant_style,
    )
