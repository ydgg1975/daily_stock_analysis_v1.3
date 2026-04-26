"""
Data Fetchers for Market Diagnostic System

Implements data fetching logic for indices, breadth, sectors, capital flow, and valuation.
Integrates with existing DataFetcherManager from daily_stock_analysis.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

try:
    import akshare as ak
except ImportError:
    ak = None
    logging.warning("akshare not available, some features will be limited")

from data_provider.base import DataFetcherManager, is_st_stock
from .models import (
    IndexDailyData,
    MarketBreadthData,
    SectorDailyData,
    CapitalFlowData,
)
from ..config import INDEX_POOL, SHENWAN_INDUSTRIES, STOCK_FILTERS

logger = logging.getLogger(__name__)


class DiagnosticDataFetcher:
    """
    Data fetcher for market diagnostic system.
    
    Integrates with existing DataFetcherManager to fetch:
    - Index series (60-day historical data for 9 core indices)
    - Market breadth metrics
    - Sector data (31 Shenwan Level-1 industries)
    - Capital flow data
    - Valuation and macro data
    
    Implements error handling, logging, and stock filtering logic.
    """
    
    def __init__(self, data_manager: DataFetcherManager):
        """
        Initialize DiagnosticDataFetcher.
        
        Args:
            data_manager: Existing DataFetcherManager instance
        """
        self.data_manager = data_manager
        self._cache: Dict[str, any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        
    def fetch_index_series(
        self,
        date: Optional[str] = None,
        days: int = 60
    ) -> Dict[str, IndexDailyData]:
        """
        Fetch 60-day historical data for 9 core indices.
        
        Args:
            date: Target date in 'YYYY-MM-DD' format (default: today)
            days: Number of historical days to fetch (default: 60)
            
        Returns:
            Dictionary mapping index code to IndexDailyData
            
        Requirements: 1.1, 1.2, 21.1, 21.2
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
            
        logger.info(f"[DiagnosticDataFetcher] Fetching index series for {date}, days={days}")
        
        result: Dict[str, IndexDailyData] = {}
        missing_data: List[str] = []
        
        # Calculate start date
        end_date = datetime.strptime(date, '%Y-%m-%d')
        start_date = (end_date - timedelta(days=days * 2)).strftime('%Y-%m-%d')  # Fetch extra to ensure 60 trading days
        
        for code, name in INDEX_POOL.items():
            try:
                logger.debug(f"[DiagnosticDataFetcher] Fetching {code} ({name})...")
                
                # Fetch daily data using DataFetcherManager
                # get_daily_data returns Tuple[DataFrame, source_name]
                result_tuple = self.data_manager.get_daily_data(
                    stock_code=code,
                    start_date=start_date,
                    end_date=date,
                    days=days * 2  # Request extra days to ensure we get enough trading days
                )
                
                # Unpack tuple
                if isinstance(result_tuple, tuple):
                    df, source_name = result_tuple
                    logger.debug(f"[DiagnosticDataFetcher] {code} fetched from {source_name}")
                else:
                    df = result_tuple
                
                if df is None or df.empty:
                    logger.warning(f"[DiagnosticDataFetcher] No data for {code} ({name})")
                    missing_data.append(f"{code}:{name}")
                    continue
                
                # Get the latest row for current day data
                latest = df.iloc[-1]
                
                # Extract close and volume series (last 60 days)
                close_series = df['close'].tail(days).tolist()
                volume_series = df['volume'].tail(days).tolist()
                
                # Create IndexDailyData object
                index_data = IndexDailyData(
                    code=code,
                    name=name,
                    date=date,
                    close=float(latest['close']),
                    open=float(latest['open']),
                    high=float(latest['high']),
                    low=float(latest['low']),
                    prev_close=float(df.iloc[-2]['close']) if len(df) > 1 else float(latest['close']),
                    volume=float(latest['volume']),
                    amount=float(latest.get('amount', 0)),
                    change_pct=float(latest.get('pct_chg', 0)),
                    close_series=close_series,
                    volume_series=volume_series,
                )
                
                result[code] = index_data
                logger.debug(f"[DiagnosticDataFetcher] {code} fetched successfully: close={index_data.close}, change_pct={index_data.change_pct}%")
                
            except Exception as e:
                logger.error(f"[DiagnosticDataFetcher] Error fetching {code} ({name}): {e}")
                missing_data.append(f"{code}:{name}")
                continue
        
        if missing_data:
            logger.warning(f"[DiagnosticDataFetcher] Missing index data: {', '.join(missing_data)}")
        
        logger.info(f"[DiagnosticDataFetcher] Index series fetch complete: {len(result)}/{len(INDEX_POOL)} indices")
        return result
    
    def fetch_breadth_data(
        self,
        date: Optional[str] = None
    ) -> Optional[MarketBreadthData]:
        """
        Fetch market breadth metrics.
        
        Retrieves:
        - Up/down counts
        - Limit-up/down counts
        - Exploded board counts
        - MA20/MA60 penetration ratios
        - New high/low counts
        - Total market turnover
        
        Uses AkShare interfaces:
        - ak.stock_zh_a_spot_em() for market-wide realtime quotes
        - ak.stock_zt_pool_em() for limit-up pool
        - ak.stock_dt_pool_em() for limit-down pool
        
        Args:
            date: Target date in 'YYYY-MM-DD' format (default: today)
            
        Returns:
            MarketBreadthData object or None if fetch fails
            
        Requirements: 1.3, 1.7, 21.3
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
            
        logger.info(f"[DiagnosticDataFetcher] Fetching breadth data for {date}")
        
        try:
            # Check cache first (20-minute TTL)
            cache_key = f"breadth_{date}"
            if cache_key in self._cache:
                cache_age = time.time() - self._cache_timestamps.get(cache_key, 0)
                if cache_age < 1200:  # 20 minutes
                    logger.debug(f"[DiagnosticDataFetcher] Using cached breadth data (age: {cache_age:.0f}s)")
                    return self._cache[cache_key]
            
            # Fetch market-wide realtime quotes
            if ak is None:
                logger.warning("[DiagnosticDataFetcher] akshare not available, using DataFetcherManager fallback")
                return self._fetch_breadth_from_manager(date)
            
            logger.debug("[DiagnosticDataFetcher] Fetching market-wide quotes from AkShare...")
            time.sleep(2)  # Rate limiting
            df_market = ak.stock_zh_a_spot_em()
            
            if df_market is None or df_market.empty:
                logger.warning("[DiagnosticDataFetcher] No market data from AkShare")
                return self._fetch_breadth_from_manager(date)
            
            # Filter stocks (exclude ST, suspended, etc.)
            df_filtered = self._filter_stocks(df_market)
            total_stocks = len(df_filtered)
            
            # Calculate up/down counts
            up_count = len(df_filtered[df_filtered['涨跌幅'] > 0])
            down_count = len(df_filtered[df_filtered['涨跌幅'] < 0])
            flat_count = len(df_filtered[df_filtered['涨跌幅'] == 0])
            
            # Fetch limit-up pool
            logger.debug("[DiagnosticDataFetcher] Fetching limit-up pool...")
            time.sleep(2)  # Rate limiting
            date_str = date.replace('-', '')
            try:
                df_limit_up = ak.stock_zt_pool_em(date=date_str)
                limit_up_count = len(df_limit_up) if df_limit_up is not None and not df_limit_up.empty else 0
            except Exception as e:
                logger.warning(f"[DiagnosticDataFetcher] Failed to fetch limit-up pool: {e}")
                limit_up_count = len(df_filtered[df_filtered['涨跌幅'] >= 9.5])
            
            # Fetch limit-down pool
            logger.debug("[DiagnosticDataFetcher] Fetching limit-down pool...")
            time.sleep(2)  # Rate limiting
            try:
                df_limit_down = ak.stock_dt_pool_em(date=date_str)
                limit_down_count = len(df_limit_down) if df_limit_down is not None and not df_limit_down.empty else 0
            except Exception as e:
                logger.warning(f"[DiagnosticDataFetcher] Failed to fetch limit-down pool: {e}")
                limit_down_count = len(df_filtered[df_filtered['涨跌幅'] <= -9.5])
            
            # Calculate explode count (stocks that broke limit-up)
            # Estimate: stocks with 涨跌幅 between 8% and 9.9% (likely exploded boards)
            explode_count = len(df_filtered[(df_filtered['涨跌幅'] >= 8.0) & (df_filtered['涨跌幅'] < 9.5)])
            
            # Calculate seal rate
            seal_rate = limit_up_count / (limit_up_count + explode_count) if (limit_up_count + explode_count) > 0 else 0.0
            
            # Calculate continuous limit-up count (2+ consecutive limit-ups)
            continuous_limit_up = self._calculate_continuous_limit_up(date)
            
            # Calculate MA penetration ratios (requires individual stock MA calculation)
            above_ma20_ratio, above_ma60_ratio = self._calculate_ma_penetration_ratios(df_filtered)
            
            # Calculate new high/low counts (requires 20-day historical data)
            new_high_count, new_low_count = self._calculate_new_highs_lows(df_filtered, date)
            
            # Calculate total market turnover (成交额)
            total_amount = df_filtered['成交额'].sum() / 1e8  # Convert to 100 million yuan
            
            # Calculate amount moving averages (requires historical data)
            amount_ma5 = total_amount  # TODO: Implement with historical data
            amount_ma20 = total_amount  # TODO: Implement with historical data
            
            breadth_data = MarketBreadthData(
                date=date,
                up_count=int(up_count),
                down_count=int(down_count),
                flat_count=int(flat_count),
                limit_up_count=int(limit_up_count),
                limit_down_count=int(limit_down_count),
                explode_count=int(explode_count),
                seal_rate=float(seal_rate),
                continuous_limit_up=int(continuous_limit_up),
                above_ma20_ratio=float(above_ma20_ratio),
                above_ma60_ratio=float(above_ma60_ratio),
                new_high_count=int(new_high_count),
                new_low_count=int(new_low_count),
                total_amount=float(total_amount),
                amount_ma5=float(amount_ma5),
                amount_ma20=float(amount_ma20),
            )
            
            # Cache the result
            self._cache[cache_key] = breadth_data
            self._cache_timestamps[cache_key] = time.time()
            
            logger.info(f"[DiagnosticDataFetcher] Breadth data fetched: up={up_count}, down={down_count}, "
                       f"limit_up={limit_up_count}, seal_rate={seal_rate:.2%}, total_amount={total_amount:.2f}亿")
            return breadth_data
            
        except Exception as e:
            logger.error(f"[DiagnosticDataFetcher] Error fetching breadth data: {e}")
            # Fallback to DataFetcherManager
            return self._fetch_breadth_from_manager(date)
    
    def _fetch_breadth_from_manager(self, date: str) -> Optional[MarketBreadthData]:
        """
        Fallback method to fetch breadth data using DataFetcherManager.
        
        Args:
            date: Target date in 'YYYY-MM-DD' format
            
        Returns:
            MarketBreadthData object or None if fetch fails
        """
        try:
            stats = self.data_manager.get_market_stats()
            
            if stats is None:
                logger.warning(f"[DiagnosticDataFetcher] No market stats available for {date}")
                return None
            
            # Extract breadth metrics
            up_count = stats.get('up_count', 0)
            down_count = stats.get('down_count', 0)
            flat_count = stats.get('flat_count', 0)
            limit_up_count = stats.get('limit_up_count', 0)
            limit_down_count = stats.get('limit_down_count', 0)
            total_amount = stats.get('total_amount', 0)
            
            # Calculate explode count and seal rate
            explode_count = stats.get('explode_count', 0)
            seal_rate = limit_up_count / (limit_up_count + explode_count) if (limit_up_count + explode_count) > 0 else 0.0
            
            # Placeholder values for metrics requiring detailed calculation
            continuous_limit_up = stats.get('continuous_limit_up', 0)
            above_ma20_ratio = stats.get('above_ma20_ratio', 0.5)
            above_ma60_ratio = stats.get('above_ma60_ratio', 0.5)
            new_high_count = stats.get('new_high_count', 0)
            new_low_count = stats.get('new_low_count', 0)
            amount_ma5 = stats.get('amount_ma5', total_amount)
            amount_ma20 = stats.get('amount_ma20', total_amount)
            
            breadth_data = MarketBreadthData(
                date=date,
                up_count=up_count,
                down_count=down_count,
                flat_count=flat_count,
                limit_up_count=limit_up_count,
                limit_down_count=limit_down_count,
                explode_count=explode_count,
                seal_rate=seal_rate,
                continuous_limit_up=continuous_limit_up,
                above_ma20_ratio=above_ma20_ratio,
                above_ma60_ratio=above_ma60_ratio,
                new_high_count=new_high_count,
                new_low_count=new_low_count,
                total_amount=total_amount,
                amount_ma5=amount_ma5,
                amount_ma20=amount_ma20,
            )
            
            logger.info(f"[DiagnosticDataFetcher] Breadth data fetched from manager: up={up_count}, down={down_count}")
            return breadth_data
            
        except Exception as e:
            logger.error(f"[DiagnosticDataFetcher] Error in fallback breadth fetch: {e}")
            return None
    
    def fetch_sector_data(
        self,
        date: Optional[str] = None
    ) -> List[SectorDailyData]:
        """
        Fetch 31 Shenwan Level-1 industry data.
        
        Retrieves:
        - Returns (1d, 5d, 20d)
        - Excess returns vs CSI300
        - Breadth metrics
        - Turnover and amount share
        - Capital flow
        
        Uses AkShare interfaces:
        - ak.stock_board_industry_hist_em() for industry historical data
        - ak.stock_sector_fund_flow_rank() for industry capital flow
        
        Args:
            date: Target date in 'YYYY-MM-DD' format (default: today)
            
        Returns:
            List of SectorDailyData objects
            
        Requirements: 1.4, 21.4
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
            
        logger.info(f"[DiagnosticDataFetcher] Fetching sector data for {date}")
        
        result: List[SectorDailyData] = []
        missing_data: List[str] = []
        
        # Check cache first (20-minute TTL)
        cache_key = f"sector_{date}"
        if cache_key in self._cache:
            cache_age = time.time() - self._cache_timestamps.get(cache_key, 0)
            if cache_age < 1200:  # 20 minutes
                logger.debug(f"[DiagnosticDataFetcher] Using cached sector data (age: {cache_age:.0f}s)")
                return self._cache[cache_key]
        
        # Try AkShare first
        if ak is not None:
            try:
                result = self._fetch_sector_from_akshare(date, missing_data)
                if result:
                    # Cache the result
                    self._cache[cache_key] = result
                    self._cache_timestamps[cache_key] = time.time()
                    logger.info(f"[DiagnosticDataFetcher] Sector data fetch complete: {len(result)} sectors")
                    return result
            except Exception as e:
                logger.warning(f"[DiagnosticDataFetcher] AkShare sector fetch failed: {e}, falling back to manager")
        
        # Fallback to DataFetcherManager
        try:
            top_sectors, bottom_sectors = self.data_manager.get_sector_rankings(n=31)
            
            if not top_sectors and not bottom_sectors:
                logger.warning(f"[DiagnosticDataFetcher] No sector data available for {date}")
                return result
            
            # Combine all sectors
            all_sectors = top_sectors + bottom_sectors
            
            for sector in all_sectors:
                try:
                    industry_code = sector.get('code', '')
                    industry_name = sector.get('name', '')
                    
                    # Extract sector metrics
                    ret_1d = sector.get('change_pct', 0.0)
                    ret_5d = sector.get('ret_5d', 0.0)
                    ret_20d = sector.get('ret_20d', 0.0)
                    excess_ret_1d = sector.get('excess_ret_1d', 0.0)
                    amount = sector.get('amount', 0.0)
                    amount_share = sector.get('amount_share', 0.0)
                    amount_share_delta = sector.get('amount_share_delta', 0.0)
                    limit_up_count = sector.get('limit_up_count', 0)
                    turnover = sector.get('turnover', 0.0)
                    
                    # Placeholder values for metrics requiring detailed calculation
                    breadth_20 = sector.get('breadth_20', 0.5)
                    new_high_ratio = sector.get('new_high_ratio', 0.0)
                    
                    sector_data = SectorDailyData(
                        date=date,
                        industry_code=industry_code,
                        industry_name=industry_name,
                        ret_1d=ret_1d,
                        ret_5d=ret_5d,
                        ret_20d=ret_20d,
                        excess_ret_1d=excess_ret_1d,
                        breadth_20=breadth_20,
                        new_high_ratio=new_high_ratio,
                        amount=amount,
                        amount_share=amount_share,
                        amount_share_delta=amount_share_delta,
                        limit_up_count=limit_up_count,
                        turnover=turnover,
                    )
                    
                    result.append(sector_data)
                    
                except Exception as e:
                    logger.error(f"[DiagnosticDataFetcher] Error processing sector {industry_name}: {e}")
                    missing_data.append(industry_name)
                    continue
            
            if missing_data:
                logger.warning(f"[DiagnosticDataFetcher] Missing sector data: {', '.join(missing_data)}")
            
            logger.info(f"[DiagnosticDataFetcher] Sector data fetch complete: {len(result)} sectors")
            return result
            
        except Exception as e:
            logger.error(f"[DiagnosticDataFetcher] Error fetching sector data: {e}")
            return result
    
    def _fetch_sector_from_akshare(self, date: str, missing_data: List[str]) -> List[SectorDailyData]:
        """
        Fetch sector data using AkShare interfaces.
        
        Args:
            date: Target date in 'YYYY-MM-DD' format
            missing_data: List to append missing sector names
            
        Returns:
            List of SectorDailyData objects
        """
        result: List[SectorDailyData] = []
        
        # Fetch industry capital flow rankings
        logger.debug("[DiagnosticDataFetcher] Fetching industry capital flow rankings...")
        time.sleep(2)  # Rate limiting
        try:
            df_flow = ak.stock_sector_fund_flow_rank(indicator="今日")
            flow_dict = {}
            if df_flow is not None and not df_flow.empty:
                for _, row in df_flow.iterrows():
                    name = row.get('名称', '')
                    flow_dict[name] = {
                        'amount': row.get('成交额', 0) / 1e8,  # Convert to 100 million yuan
                        'main_net_flow': row.get('主力净流入-净额', 0) / 1e8,
                        'change_pct': row.get('涨跌幅', 0),
                    }
        except Exception as e:
            logger.warning(f"[DiagnosticDataFetcher] Failed to fetch industry capital flow: {e}")
            flow_dict = {}
        
        # Calculate total market amount for amount_share calculation
        total_market_amount = sum(v['amount'] for v in flow_dict.values()) if flow_dict else 0.0
        
        # Fetch CSI300 data for excess return calculation
        csi300_ret_1d = 0.0
        try:
            df_csi300 = self.data_manager.get_daily_data(
                stock_code="sh000300",
                days=2
            )
            if df_csi300 is not None and len(df_csi300) >= 2:
                csi300_ret_1d = float(df_csi300.iloc[-1].get('pct_chg', 0))
        except Exception as e:
            logger.warning(f"[DiagnosticDataFetcher] Failed to fetch CSI300 for excess return: {e}")
        
        # Fetch historical data for each industry
        for industry_code, industry_name in SHENWAN_INDUSTRIES.items():
            try:
                logger.debug(f"[DiagnosticDataFetcher] Fetching {industry_name} ({industry_code})...")
                time.sleep(3)  # Rate limiting (3 seconds between sectors)
                
                # Fetch industry historical data
                df_hist = ak.stock_board_industry_hist_em(
                    symbol=industry_code,
                    period="日k",
                    start_date=(datetime.strptime(date, '%Y-%m-%d') - timedelta(days=40)).strftime('%Y%m%d'),
                    end_date=date.replace('-', ''),
                    adjust=""
                )
                
                if df_hist is None or df_hist.empty:
                    logger.warning(f"[DiagnosticDataFetcher] No historical data for {industry_name}")
                    missing_data.append(industry_name)
                    continue
                
                # Get latest row
                latest = df_hist.iloc[-1]
                
                # Calculate returns
                # Prefer flow_dict's change_pct (today's return from capital flow ranking)
                # as it's more reliable than hist data's last row
                flow_data_for_ret = flow_dict.get(industry_name, {})
                if 'change_pct' in flow_data_for_ret:
                    ret_1d = float(flow_data_for_ret['change_pct'])
                else:
                    ret_1d = float(latest.get('涨跌幅', 0))
                
                # Calculate 5-day and 20-day returns
                if len(df_hist) >= 5:
                    close_5d_ago = df_hist.iloc[-5]['收盘']
                    ret_5d = ((latest['收盘'] - close_5d_ago) / close_5d_ago * 100) if close_5d_ago > 0 else 0
                else:
                    ret_5d = ret_1d
                
                if len(df_hist) >= 20:
                    close_20d_ago = df_hist.iloc[-20]['收盘']
                    ret_20d = ((latest['收盘'] - close_20d_ago) / close_20d_ago * 100) if close_20d_ago > 0 else 0
                else:
                    ret_20d = ret_1d
                
                # Get flow data
                flow_data = flow_dict.get(industry_name, {})
                amount = flow_data.get('amount', float(latest.get('成交额', 0)) / 1e8)
                
                # Calculate amount share
                amount_share = (amount / total_market_amount) if total_market_amount > 0 else 0.0
                
                # Calculate amount_share_delta (vs 5-day average)
                amount_share_delta = 0.0
                if len(df_hist) >= 5:
                    recent_amounts = df_hist.tail(5)['成交额'].astype(float) / 1e8
                    avg_amount_5d = recent_amounts.mean()
                    # Calculate historical amount shares (approximate)
                    if total_market_amount > 0:
                        avg_share_5d = avg_amount_5d / total_market_amount
                        amount_share_delta = amount_share - avg_share_5d
                
                # Calculate excess return vs CSI300
                excess_ret_1d = ret_1d - csi300_ret_1d
                
                # Fetch sector constituents for breadth and new high calculations
                breadth_20, new_high_ratio, limit_up_count = self._calculate_sector_breadth_metrics(
                    industry_code, industry_name, date
                )
                
                turnover = float(latest.get('换手率', 0))
                
                sector_data = SectorDailyData(
                    date=date,
                    industry_code=industry_code,
                    industry_name=industry_name,
                    ret_1d=ret_1d,
                    ret_5d=ret_5d,
                    ret_20d=ret_20d,
                    excess_ret_1d=excess_ret_1d,
                    breadth_20=breadth_20,
                    new_high_ratio=new_high_ratio,
                    amount=amount,
                    amount_share=amount_share,
                    amount_share_delta=amount_share_delta,
                    limit_up_count=limit_up_count,
                    turnover=turnover,
                )
                
                result.append(sector_data)
                logger.debug(f"[DiagnosticDataFetcher] {industry_name} fetched: ret_1d={ret_1d:.2f}%, "
                           f"excess_ret={excess_ret_1d:.2f}%, breadth_20={breadth_20:.2%}, "
                           f"amount_share={amount_share:.2%}")
                
            except Exception as e:
                logger.error(f"[DiagnosticDataFetcher] Error fetching {industry_name}: {e}")
                missing_data.append(industry_name)
                continue
        
        return result
    
    def fetch_capital_flow(
        self,
        date: Optional[str] = None
    ) -> Optional[CapitalFlowData]:
        """
        Fetch capital flow data.
        
        Retrieves:
        - North Bound Capital net flow (T+1 data)
        - Margin balance (T+1 data)
        - Main force net flow
        - ETF net flow proxy
        
        Uses AkShare interfaces:
        - ak.stock_hsgt_hist_em() for North Bound Capital
        - ak.stock_margin_underlying_info_szse() for margin balance
        
        Args:
            date: Target date in 'YYYY-MM-DD' format (default: today)
            
        Returns:
            CapitalFlowData object or None if fetch fails
            
        Requirements: 1.5, 7.6, 21.5
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
            
        logger.info(f"[DiagnosticDataFetcher] Fetching capital flow data for {date}")
        
        try:
            # Check cache first (daily TTL)
            cache_key = f"capital_{date}"
            if cache_key in self._cache:
                cache_age = time.time() - self._cache_timestamps.get(cache_key, 0)
                if cache_age < 86400:  # 24 hours
                    logger.debug(f"[DiagnosticDataFetcher] Using cached capital flow data (age: {cache_age:.0f}s)")
                    return self._cache[cache_key]
            
            data_freshness = {}
            
            # Fetch North Bound Capital data (T+1)
            north_net_flow = 0.0
            north_5d_avg = 0.0
            if ak is not None:
                try:
                    logger.debug("[DiagnosticDataFetcher] Fetching North Bound Capital data...")
                    time.sleep(2)  # Rate limiting
                    df_north = ak.stock_hsgt_hist_em(symbol="沪深港通")
                    
                    if df_north is not None and not df_north.empty:
                        # Find the row for the target date (may be T+1)
                        df_north['日期'] = pd.to_datetime(df_north['日期'])
                        target_date = pd.to_datetime(date)
                        
                        # Try to find exact date, otherwise use latest available
                        matching_rows = df_north[df_north['日期'] == target_date]
                        if not matching_rows.empty:
                            north_net_flow = float(matching_rows.iloc[0].get('当日资金流入', 0)) / 1e8
                            data_freshness['north_net_flow'] = 'T+0'
                        else:
                            # Use latest available (T+1)
                            latest = df_north.iloc[-1]
                            north_net_flow = float(latest.get('当日资金流入', 0)) / 1e8
                            data_freshness['north_net_flow'] = 'T+1'
                        
                        # Calculate 5-day average
                        if len(df_north) >= 5:
                            recent_flows = df_north.tail(5)['当日资金流入'].astype(float) / 1e8
                            north_5d_avg = float(recent_flows.mean())
                        else:
                            north_5d_avg = north_net_flow
                        
                        logger.debug(f"[DiagnosticDataFetcher] North Bound Capital: {north_net_flow:.2f}亿 (5d avg: {north_5d_avg:.2f}亿)")
                except Exception as e:
                    logger.warning(f"[DiagnosticDataFetcher] Failed to fetch North Bound Capital: {e}")
                    data_freshness['north_net_flow'] = 'unavailable'
            else:
                data_freshness['north_net_flow'] = 'unavailable'
            
            # Fetch margin balance data (T+1)
            margin_balance = 0.0
            margin_delta = 0.0
            if ak is not None:
                try:
                    logger.debug("[DiagnosticDataFetcher] Fetching margin balance data...")
                    time.sleep(2)  # Rate limiting
                    df_margin = ak.stock_margin_underlying_info_szse(date=date.replace('-', ''))
                    
                    if df_margin is not None and not df_margin.empty:
                        # Sum up total margin balance
                        margin_balance = float(df_margin['融资余额'].sum()) / 1e8
                        # Calculate delta (requires historical data)
                        # TODO: Implement historical comparison
                        margin_delta = 0.0
                        data_freshness['margin_balance'] = 'T+1'
                        logger.debug(f"[DiagnosticDataFetcher] Margin balance: {margin_balance:.2f}亿")
                except Exception as e:
                    logger.warning(f"[DiagnosticDataFetcher] Failed to fetch margin balance: {e}")
                    data_freshness['margin_balance'] = 'unavailable'
            else:
                data_freshness['margin_balance'] = 'unavailable'
            
            # Main force net flow (proxy using market stats)
            main_net_flow = 0.0
            data_freshness['main_net_flow'] = 'T+0 (proxy)'
            
            # ETF net flow (proxy)
            etf_net_flow = 0.0
            data_freshness['etf_net_flow'] = 'T+0 (proxy)'
            
            capital_data = CapitalFlowData(
                date=date,
                north_net_flow=north_net_flow,
                north_5d_avg=north_5d_avg,
                margin_balance=margin_balance,
                margin_delta=margin_delta,
                main_net_flow=main_net_flow,
                etf_net_flow=etf_net_flow,
                data_freshness=data_freshness,
            )
            
            # Cache the result
            self._cache[cache_key] = capital_data
            self._cache_timestamps[cache_key] = time.time()
            
            logger.info(f"[DiagnosticDataFetcher] Capital flow data fetched: north={north_net_flow:.2f}亿, margin={margin_balance:.2f}亿")
            return capital_data
            
        except Exception as e:
            logger.error(f"[DiagnosticDataFetcher] Error fetching capital flow data: {e}")
            return None
    
    def fetch_valuation_data(
        self,
        date: Optional[str] = None
    ) -> Optional[Dict[str, any]]:
        """
        Fetch valuation and macro data.
        
        Retrieves:
        - Index PE/PB ratios
        - Bond yields
        - Exchange rates
        
        Uses AkShare interfaces:
        - ak.stock_zh_index_value_csindex() for index valuation
        - ak.bond_zh_us_rate() for bond yields
        - ak.currency_boc_sina() for exchange rates
        
        Args:
            date: Target date in 'YYYY-MM-DD' format (default: today)
            
        Returns:
            Dictionary containing valuation metrics or None if fetch fails
            
        Requirements: 1.6, 24.1, 24.2
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
            
        logger.info(f"[DiagnosticDataFetcher] Fetching valuation data for {date}")
        
        try:
            # Check cache first (daily TTL)
            cache_key = f"valuation_{date}"
            if cache_key in self._cache:
                cache_age = time.time() - self._cache_timestamps.get(cache_key, 0)
                if cache_age < 86400:  # 24 hours
                    logger.debug(f"[DiagnosticDataFetcher] Using cached valuation data (age: {cache_age:.0f}s)")
                    return self._cache[cache_key]
            
            valuation_data = {'date': date}
            
            # Fetch index valuation (PE/PB)
            if ak is not None:
                for index_code, index_name in [('000300', 'csi300'), ('000905', 'csi500'), ('000852', 'csi1000')]:
                    try:
                        logger.debug(f"[DiagnosticDataFetcher] Fetching {index_name} valuation...")
                        time.sleep(2)  # Rate limiting
                        df_val = ak.stock_zh_index_value_csindex(symbol=index_code)
                        
                        if df_val is not None and not df_val.empty:
                            latest = df_val.iloc[-1]
                            valuation_data[f'{index_name}_pe'] = float(latest.get('市盈率2', 0))  # Use PE TTM
                            valuation_data[f'{index_name}_pb'] = float(latest.get('市净率', 0)) if '市净率' in latest else 0.0
                            logger.debug(f"[DiagnosticDataFetcher] {index_name} PE={valuation_data[f'{index_name}_pe']:.2f}")
                    except Exception as e:
                        logger.warning(f"[DiagnosticDataFetcher] Failed to fetch {index_name} valuation: {e}")
                        valuation_data[f'{index_name}_pe'] = 0.0
                        valuation_data[f'{index_name}_pb'] = 0.0
                
                # Fetch bond yields
                try:
                    logger.debug("[DiagnosticDataFetcher] Fetching bond yields...")
                    time.sleep(2)  # Rate limiting
                    df_bond = ak.bond_zh_us_rate()
                    
                    if df_bond is not None and not df_bond.empty:
                        latest = df_bond.iloc[-1]
                        valuation_data['bond_yield_10y'] = float(latest.get('中国国债收益率10年', 0))
                        valuation_data['bond_yield_1y'] = float(latest.get('中国国债收益率2年', 0))  # Use 2Y as proxy for 1Y
                        logger.debug(f"[DiagnosticDataFetcher] Bond yield 10Y={valuation_data['bond_yield_10y']:.2f}%")
                except Exception as e:
                    logger.warning(f"[DiagnosticDataFetcher] Failed to fetch bond yields: {e}")
                    valuation_data['bond_yield_10y'] = 0.0
                    valuation_data['bond_yield_1y'] = 0.0
                
                # Fetch exchange rate
                try:
                    logger.debug("[DiagnosticDataFetcher] Fetching USD/CNY exchange rate...")
                    time.sleep(2)  # Rate limiting
                    df_fx = ak.currency_boc_sina()
                    
                    if df_fx is not None and not df_fx.empty:
                        latest = df_fx.iloc[-1]
                        valuation_data['usd_cny'] = float(latest.get('央行中间价', 0))
                        logger.debug(f"[DiagnosticDataFetcher] USD/CNY={valuation_data['usd_cny']:.2f}")
                except Exception as e:
                    logger.warning(f"[DiagnosticDataFetcher] Failed to fetch exchange rate: {e}")
                    valuation_data['usd_cny'] = 0.0
            else:
                # Set default values if akshare not available
                valuation_data.update({
                    'csi300_pe': 0.0,
                    'csi300_pb': 0.0,
                    'csi500_pe': 0.0,
                    'csi500_pb': 0.0,
                    'csi1000_pe': 0.0,
                    'csi1000_pb': 0.0,
                    'bond_yield_10y': 0.0,
                    'bond_yield_1y': 0.0,
                    'usd_cny': 0.0,
                })
            
            # Cache the result
            self._cache[cache_key] = valuation_data
            self._cache_timestamps[cache_key] = time.time()
            
            logger.info(f"[DiagnosticDataFetcher] Valuation data fetched successfully")
            return valuation_data
            
        except Exception as e:
            logger.error(f"[DiagnosticDataFetcher] Error fetching valuation data: {e}")
            return None
    
    def _filter_stocks(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter stocks based on criteria.
        
        Excludes:
        - ST stocks
        - Suspended stocks
        - Newly listed stocks (within 60 days)
        - Anomalous samples
        
        Args:
            df: DataFrame containing stock data
            
        Returns:
            Filtered DataFrame
            
        Requirements: 1.7
        """
        if df is None or df.empty:
            return df
        
        original_count = len(df)
        
        # Filter ST stocks
        if STOCK_FILTERS['exclude_st'] and '名称' in df.columns:
            df = df[~df['名称'].apply(lambda x: is_st_stock(str(x)))]
        
        # Filter suspended stocks (volume = 0)
        if STOCK_FILTERS['exclude_suspended'] and '成交量' in df.columns:
            df = df[df['成交量'] > 0]
        
        # Filter newly listed stocks (requires listing_date field)
        # Note: This requires additional data that may not be available in spot data
        # Skipping for now as it requires separate API call
        
        # Filter anomalous samples (extreme price changes)
        if STOCK_FILTERS['exclude_anomalous'] and '涨跌幅' in df.columns:
            # Exclude stocks with > 20% change (unless limit-up/down)
            df = df[(df['涨跌幅'].abs() <= 20) | (df['涨跌幅'].abs() >= 9.5)]
        
        filtered_count = len(df)
        logger.debug(f"[DiagnosticDataFetcher] Stock filtering: {original_count} -> {filtered_count} ({original_count - filtered_count} filtered)")
        
        return df
    
    def _calculate_continuous_limit_up(self, date: str) -> int:
        """
        Calculate count of stocks with 2+ consecutive limit-ups.
        
        Args:
            date: Target date in 'YYYY-MM-DD' format
            
        Returns:
            Count of stocks with continuous limit-ups
            
        Requirements: 3.2, 4.2
        """
        if ak is None:
            logger.warning("[DiagnosticDataFetcher] akshare not available for continuous limit-up calculation")
            return 0
        
        try:
            date_str = date.replace('-', '')
            time.sleep(2)  # Rate limiting
            df_limit_up = ak.stock_zt_pool_em(date=date_str)
            
            if df_limit_up is None or df_limit_up.empty:
                return 0
            
            # Count stocks with 连板数 >= 2
            if '连板数' in df_limit_up.columns:
                continuous_count = len(df_limit_up[df_limit_up['连板数'] >= 2])
                logger.debug(f"[DiagnosticDataFetcher] Continuous limit-up count: {continuous_count}")
                return continuous_count
            else:
                logger.warning("[DiagnosticDataFetcher] '连板数' column not found in limit-up pool")
                return 0
                
        except Exception as e:
            logger.warning(f"[DiagnosticDataFetcher] Failed to calculate continuous limit-up: {e}")
            return 0
    
    def _calculate_ma_penetration_ratios(self, df_market: pd.DataFrame) -> Tuple[float, float]:
        """
        Calculate ratio of stocks above MA20 and MA60.
        
        This requires fetching 60-day historical data for each stock to calculate MAs.
        For performance, we use a sampling approach or cached MA values.
        
        Args:
            df_market: DataFrame containing market-wide stock data
            
        Returns:
            Tuple of (above_ma20_ratio, above_ma60_ratio)
            
        Requirements: 3.4
        """
        if df_market is None or df_market.empty:
            return 0.5, 0.5
        
        try:
            # Extract stock codes
            stock_codes = df_market['代码'].tolist() if '代码' in df_market.columns else []
            
            if not stock_codes:
                logger.warning("[DiagnosticDataFetcher] No stock codes found for MA calculation")
                return 0.5, 0.5
            
            # For performance, sample a subset of stocks (e.g., 500 stocks)
            # This provides a representative estimate without fetching all ~5000 stocks
            sample_size = min(500, len(stock_codes))
            sampled_codes = np.random.choice(stock_codes, size=sample_size, replace=False)
            
            above_ma20_count = 0
            above_ma60_count = 0
            valid_count = 0
            
            logger.debug(f"[DiagnosticDataFetcher] Calculating MA ratios for {sample_size} sampled stocks...")
            
            for i, code in enumerate(sampled_codes):
                try:
                    # Fetch 60-day historical data
                    df_hist = self.data_manager.get_daily_data(
                        stock_code=code,
                        days=80  # Fetch extra to ensure 60 trading days
                    )
                    
                    if df_hist is None or len(df_hist) < 60:
                        continue
                    
                    # Calculate MA20 and MA60
                    df_hist['ma20'] = df_hist['close'].rolling(window=20).mean()
                    df_hist['ma60'] = df_hist['close'].rolling(window=60).mean()
                    
                    # Get latest values
                    latest = df_hist.iloc[-1]
                    
                    if pd.notna(latest['ma20']) and latest['close'] > latest['ma20']:
                        above_ma20_count += 1
                    
                    if pd.notna(latest['ma60']) and latest['close'] > latest['ma60']:
                        above_ma60_count += 1
                    
                    valid_count += 1
                    
                    # Rate limiting: small delay every 50 stocks
                    if (i + 1) % 50 == 0:
                        time.sleep(0.5)
                        logger.debug(f"[DiagnosticDataFetcher] Processed {i + 1}/{sample_size} stocks...")
                    
                except Exception as e:
                    logger.debug(f"[DiagnosticDataFetcher] Failed to calculate MA for {code}: {e}")
                    continue
            
            if valid_count == 0:
                logger.warning("[DiagnosticDataFetcher] No valid stocks for MA calculation")
                return 0.5, 0.5
            
            # Calculate ratios
            above_ma20_ratio = above_ma20_count / valid_count
            above_ma60_ratio = above_ma60_count / valid_count
            
            logger.info(f"[DiagnosticDataFetcher] MA penetration ratios: MA20={above_ma20_ratio:.2%}, MA60={above_ma60_ratio:.2%} (sample: {valid_count} stocks)")
            
            return above_ma20_ratio, above_ma60_ratio
            
        except Exception as e:
            logger.error(f"[DiagnosticDataFetcher] Error calculating MA penetration ratios: {e}")
            return 0.5, 0.5
    
    def _calculate_new_highs_lows(self, df_market: pd.DataFrame, date: str) -> Tuple[int, int]:
        """
        Calculate count of stocks at 20-day new highs/lows.
        
        Args:
            df_market: DataFrame containing market-wide stock data
            date: Target date in 'YYYY-MM-DD' format
            
        Returns:
            Tuple of (new_high_count, new_low_count)
            
        Requirements: 3.5
        """
        if df_market is None or df_market.empty:
            return 0, 0
        
        try:
            # Extract stock codes
            stock_codes = df_market['代码'].tolist() if '代码' in df_market.columns else []
            
            if not stock_codes:
                logger.warning("[DiagnosticDataFetcher] No stock codes found for new high/low calculation")
                return 0, 0
            
            # For performance, sample a subset of stocks
            sample_size = min(500, len(stock_codes))
            sampled_codes = np.random.choice(stock_codes, size=sample_size, replace=False)
            
            new_high_count = 0
            new_low_count = 0
            valid_count = 0
            
            logger.debug(f"[DiagnosticDataFetcher] Calculating new highs/lows for {sample_size} sampled stocks...")
            
            for i, code in enumerate(sampled_codes):
                try:
                    # Fetch 20-day historical data
                    df_hist = self.data_manager.get_daily_data(
                        stock_code=code,
                        days=30  # Fetch extra to ensure 20 trading days
                    )
                    
                    if df_hist is None or len(df_hist) < 20:
                        continue
                    
                    # Get last 20 days
                    df_20d = df_hist.tail(20)
                    
                    # Check if latest close is 20-day high
                    latest_close = df_20d['close'].iloc[-1]
                    max_20d = df_20d['close'].max()
                    min_20d = df_20d['close'].min()
                    
                    if latest_close >= max_20d:
                        new_high_count += 1
                    
                    if latest_close <= min_20d:
                        new_low_count += 1
                    
                    valid_count += 1
                    
                    # Rate limiting: small delay every 50 stocks
                    if (i + 1) % 50 == 0:
                        time.sleep(0.5)
                        logger.debug(f"[DiagnosticDataFetcher] Processed {i + 1}/{sample_size} stocks...")
                    
                except Exception as e:
                    logger.debug(f"[DiagnosticDataFetcher] Failed to calculate new high/low for {code}: {e}")
                    continue
            
            if valid_count == 0:
                logger.warning("[DiagnosticDataFetcher] No valid stocks for new high/low calculation")
                return 0, 0
            
            # Scale up to total market
            total_stocks = len(stock_codes)
            new_high_count_scaled = int(new_high_count * total_stocks / valid_count)
            new_low_count_scaled = int(new_low_count * total_stocks / valid_count)
            
            logger.info(f"[DiagnosticDataFetcher] New highs/lows: {new_high_count_scaled}/{new_low_count_scaled} (sample: {valid_count} stocks)")
            
            return new_high_count_scaled, new_low_count_scaled
            
        except Exception as e:
            logger.error(f"[DiagnosticDataFetcher] Error calculating new highs/lows: {e}")
            return 0, 0
    
    def _calculate_sector_breadth_metrics(
        self,
        industry_code: str,
        industry_name: str,
        date: str
    ) -> Tuple[float, float, int]:
        """
        Calculate sector-specific breadth metrics.
        
        Fetches sector constituents and calculates:
        - breadth_20: Ratio of stocks above MA20 within sector
        - new_high_ratio: Ratio of stocks at 20-day new high within sector
        - limit_up_count: Count of limit-up stocks within sector
        
        Args:
            industry_code: Shenwan industry code (e.g., 'BK0447')
            industry_name: Industry name (e.g., '电子')
            date: Target date in 'YYYY-MM-DD' format
            
        Returns:
            Tuple of (breadth_20, new_high_ratio, limit_up_count)
            
        Requirements: 6.3, 6.4
        """
        try:
            # Fetch sector constituents
            logger.debug(f"[DiagnosticDataFetcher] Fetching constituents for {industry_name}...")
            time.sleep(2)  # Rate limiting
            
            df_cons = ak.stock_board_industry_cons_em(symbol=industry_name)
            
            if df_cons is None or df_cons.empty:
                logger.warning(f"[DiagnosticDataFetcher] No constituents found for {industry_name}")
                return 0.5, 0.0, 0
            
            # Extract stock codes
            stock_codes = df_cons['代码'].tolist() if '代码' in df_cons.columns else []
            
            if not stock_codes:
                logger.warning(f"[DiagnosticDataFetcher] No stock codes in constituents for {industry_name}")
                return 0.5, 0.0, 0
            
            total_stocks = len(stock_codes)
            logger.debug(f"[DiagnosticDataFetcher] {industry_name} has {total_stocks} constituents")
            
            # For performance, sample if sector is large
            sample_size = min(50, total_stocks)  # Sample up to 50 stocks per sector
            sampled_codes = np.random.choice(stock_codes, size=sample_size, replace=False) if total_stocks > sample_size else stock_codes
            
            above_ma20_count = 0
            new_high_count = 0
            limit_up_count = 0
            valid_count = 0
            
            for i, code in enumerate(sampled_codes):
                try:
                    # Fetch historical data for MA20 and new high calculation
                    df_hist = self.data_manager.get_daily_data(
                        stock_code=code,
                        days=30  # Fetch extra to ensure 20 trading days
                    )
                    
                    if df_hist is None or len(df_hist) < 20:
                        continue
                    
                    # Calculate MA20
                    df_hist['ma20'] = df_hist['close'].rolling(window=20).mean()
                    
                    # Get latest values
                    latest = df_hist.iloc[-1]
                    
                    # Check if above MA20
                    if pd.notna(latest['ma20']) and latest['close'] > latest['ma20']:
                        above_ma20_count += 1
                    
                    # Check if at 20-day new high
                    df_20d = df_hist.tail(20)
                    max_20d = df_20d['close'].max()
                    if latest['close'] >= max_20d:
                        new_high_count += 1
                    
                    # Check if limit-up (涨跌幅 >= 9.5%)
                    change_pct = latest.get('pct_chg', 0)
                    if change_pct >= 9.5:
                        limit_up_count += 1
                    
                    valid_count += 1
                    
                    # Rate limiting: small delay every 20 stocks
                    if (i + 1) % 20 == 0:
                        time.sleep(0.3)
                    
                except Exception as e:
                    logger.debug(f"[DiagnosticDataFetcher] Failed to process {code} in {industry_name}: {e}")
                    continue
            
            if valid_count == 0:
                logger.warning(f"[DiagnosticDataFetcher] No valid stocks processed for {industry_name}")
                return 0.5, 0.0, 0
            
            # Calculate ratios
            breadth_20 = above_ma20_count / valid_count
            new_high_ratio = new_high_count / valid_count
            
            # Scale limit_up_count to total sector size
            limit_up_count_scaled = int(limit_up_count * total_stocks / valid_count)
            
            logger.debug(f"[DiagnosticDataFetcher] {industry_name} breadth metrics: "
                        f"breadth_20={breadth_20:.2%}, new_high_ratio={new_high_ratio:.2%}, "
                        f"limit_up={limit_up_count_scaled} (sample: {valid_count}/{total_stocks})")
            
            return breadth_20, new_high_ratio, limit_up_count_scaled
            
        except Exception as e:
            logger.error(f"[DiagnosticDataFetcher] Error calculating sector breadth for {industry_name}: {e}")
            return 0.5, 0.0, 0
