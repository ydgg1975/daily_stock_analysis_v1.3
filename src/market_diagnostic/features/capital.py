"""
Capital Flow Feature Calculation

Computes capital flow indicators from CapitalFlowData and MarketBreadthData.
Includes turnover amount analysis, North Bound Capital flows, margin balance changes,
main force flows, and ETF flows with T+1 data lag indicators.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

try:
    from src.market_diagnostic.data.models import CapitalFlowData, MarketBreadthData
except ImportError:
    from market_diagnostic.data.models import CapitalFlowData, MarketBreadthData  # type: ignore[no-redef]


@dataclass
class CapitalFeatures:
    """Capital flow features."""
    
    total_amount: float                    # Total market turnover (100M yuan)
    amount_deviation_5d: float             # (amount - ma5) / ma5
    amount_deviation_20d: float            # (amount - ma20) / ma20
    amount_deviation_60d: float            # (amount - ma60) / ma60
    north_net_flow: float                  # North Bound Capital net flow (100M yuan)
    north_5d_avg: float                    # 5-day average North Bound flow
    north_flow_trend: str                  # "inflow" / "outflow" / "neutral"
    margin_balance: float                  # Margin balance (100M yuan)
    margin_delta: float                    # Change in margin balance
    main_net_flow: float                   # Main force net flow (100M yuan)
    etf_net_flow: float                    # ETF net flow proxy (100M yuan)
    data_freshness: Dict[str, str]         # Data timeliness indicators
    has_delayed_data: bool                 # True if any T+1 data present


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default when denominator is zero or near-zero."""
    import math
    if denominator == 0 or not math.isfinite(denominator) or abs(denominator) < 1e-300:
        return default
    result = numerator / denominator
    if not math.isfinite(result):
        return default
    return result


def compute_capital_features(
    capital_data: CapitalFlowData,
    breadth_data: MarketBreadthData,
    amount_ma60: float = 0.0
) -> CapitalFeatures:
    """
    Compute capital flow features from capital flow and breadth data.
    
    Parameters
    ----------
    capital_data : CapitalFlowData
        Capital flow metrics including North Bound, margin, main force, ETF flows
    breadth_data : MarketBreadthData
        Market breadth data containing turnover amounts and moving averages
    amount_ma60 : float, optional
        60-day moving average of turnover amount (default: 0.0)
        
    Returns
    -------
    CapitalFeatures
        Computed capital flow indicators
        
    Requirements
    ------------
    7.1: Calculate total market turnover amount
    7.2: Calculate turnover deviations from 5-day, 20-day, and 60-day MAs
    7.3: Retrieve North Bound Capital net flow and calculate 5-day MA
    7.4: Retrieve margin balance changes
    7.5: Calculate main force net flow and ETF net flow proxies
    7.6: Mark T+1 delayed data with time lag indicators
    """
    # Requirement 7.1: Total market turnover amount
    total_amount = breadth_data.total_amount
    
    # Requirement 7.2: Turnover amount deviations from moving averages
    amount_deviation_5d = _safe_divide(
        total_amount - breadth_data.amount_ma5,
        breadth_data.amount_ma5,
        default=0.0
    )
    
    amount_deviation_20d = _safe_divide(
        total_amount - breadth_data.amount_ma20,
        breadth_data.amount_ma20,
        default=0.0
    )
    
    amount_deviation_60d = _safe_divide(
        total_amount - amount_ma60,
        amount_ma60,
        default=0.0
    )
    
    # Requirement 7.3: North Bound Capital net flow and 5-day average
    north_net_flow = capital_data.north_net_flow
    north_5d_avg = capital_data.north_5d_avg
    
    # Determine North Bound flow trend
    if north_5d_avg > 10.0:  # Threshold: 10亿 net inflow
        north_flow_trend = "inflow"
    elif north_5d_avg < -10.0:  # Threshold: 10亿 net outflow
        north_flow_trend = "outflow"
    else:
        north_flow_trend = "neutral"
    
    # Requirement 7.4: Margin balance changes
    margin_balance = capital_data.margin_balance
    margin_delta = capital_data.margin_delta
    
    # Requirement 7.5: Main force net flow and ETF net flow proxies
    main_net_flow = capital_data.main_net_flow
    etf_net_flow = capital_data.etf_net_flow
    
    # Requirement 7.6: Mark T+1 delayed data with time lag indicators
    data_freshness = capital_data.data_freshness.copy()
    
    # Check if any data is T+1 delayed
    has_delayed_data = any(
        'T+1' in freshness or 'unavailable' in freshness
        for freshness in data_freshness.values()
    )
    
    return CapitalFeatures(
        total_amount=total_amount,
        amount_deviation_5d=amount_deviation_5d,
        amount_deviation_20d=amount_deviation_20d,
        amount_deviation_60d=amount_deviation_60d,
        north_net_flow=north_net_flow,
        north_5d_avg=north_5d_avg,
        north_flow_trend=north_flow_trend,
        margin_balance=margin_balance,
        margin_delta=margin_delta,
        main_net_flow=main_net_flow,
        etf_net_flow=etf_net_flow,
        data_freshness=data_freshness,
        has_delayed_data=has_delayed_data,
    )
