"""
Core Data Models

Defines data structures for market diagnostic system.
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class IndexDailyData:
    """
    Daily data for a single index.
    
    Attributes:
        code: Index code (e.g., 'sh000001', 'sz399006')
        name: Index name (e.g., '上证指数', '创业板指')
        date: Trading date in 'YYYY-MM-DD' format
        close: Closing price
        open: Opening price
        high: Highest price
        low: Lowest price
        prev_close: Previous day's closing price
        volume: Trading volume
        amount: Trading amount in yuan
        change_pct: Daily change percentage
        close_series: Historical closing prices (up to 60 days)
        volume_series: Historical trading volumes (up to 60 days)
    """
    code: str
    name: str
    date: str
    close: float
    open: float
    high: float
    low: float
    prev_close: float
    volume: float
    amount: float
    change_pct: float
    close_series: List[float] = field(default_factory=list)
    volume_series: List[float] = field(default_factory=list)


@dataclass
class MarketBreadthData:
    """
    Market-wide breadth metrics.
    
    Attributes:
        date: Trading date in 'YYYY-MM-DD' format
        up_count: Number of stocks with positive returns
        down_count: Number of stocks with negative returns
        flat_count: Number of stocks with zero returns
        limit_up_count: Number of stocks hitting upper limit
        limit_down_count: Number of stocks hitting lower limit
        explode_count: Number of stocks that broke limit-up (炸板)
        seal_rate: Seal rate = limit_up / (limit_up + explode)
        continuous_limit_up: Number of stocks with 2+ consecutive limit-ups
        above_ma20_ratio: Ratio of stocks above MA20 (0-1)
        above_ma60_ratio: Ratio of stocks above MA60 (0-1)
        new_high_count: Number of stocks at 20-day high
        new_low_count: Number of stocks at 20-day low
        total_amount: Total market turnover in 100 million yuan
        amount_ma5: 5-day average turnover in 100 million yuan
        amount_ma20: 20-day average turnover in 100 million yuan
    """
    date: str
    up_count: int
    down_count: int
    flat_count: int
    limit_up_count: int
    limit_down_count: int
    explode_count: int
    seal_rate: float
    continuous_limit_up: int
    above_ma20_ratio: float
    above_ma60_ratio: float
    new_high_count: int
    new_low_count: int
    total_amount: float
    amount_ma5: float
    amount_ma20: float


@dataclass
class SectorDailyData:
    """
    Daily data for a single sector (Shenwan Level-1 industry).
    
    Attributes:
        date: Trading date in 'YYYY-MM-DD' format
        industry_code: Industry code (e.g., 'BK0447')
        industry_name: Industry name (e.g., '电子')
        ret_1d: 1-day return
        ret_5d: 5-day return
        ret_20d: 20-day return
        excess_ret_1d: 1-day excess return vs CSI300
        breadth_20: Ratio of stocks above MA20 within industry
        new_high_ratio: Ratio of stocks at 20-day high within industry
        amount: Industry turnover in 100 million yuan
        amount_share: Industry turnover as share of total market
        amount_share_delta: Change in amount_share vs 5-day average
        limit_up_count: Number of limit-up stocks in industry
        turnover: Industry turnover rate
    """
    date: str
    industry_code: str
    industry_name: str
    ret_1d: float
    ret_5d: float
    ret_20d: float
    excess_ret_1d: float
    breadth_20: float
    new_high_ratio: float
    amount: float
    amount_share: float
    amount_share_delta: float
    limit_up_count: int
    turnover: float


@dataclass
class CapitalFlowData:
    """
    Capital flow metrics.
    
    Attributes:
        date: Trading date in 'YYYY-MM-DD' format
        north_net_flow: North Bound Capital net inflow in 100 million yuan (T+1 data)
        north_5d_avg: 5-day average of North Bound Capital net flow
        margin_balance: Margin financing balance in 100 million yuan (T+1 data)
        margin_delta: Change in margin balance
        main_net_flow: Main force net inflow in 100 million yuan
        etf_net_flow: ETF net subscription proxy in 100 million yuan
        data_freshness: Dictionary indicating data timeliness for each field
    """
    date: str
    north_net_flow: float
    north_5d_avg: float
    margin_balance: float
    margin_delta: float
    main_net_flow: float
    etf_net_flow: float
    data_freshness: Dict[str, str] = field(default_factory=dict)
