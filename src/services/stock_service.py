# -*- coding: utf-8 -*-
"""
===================================
股票数据服务层
===================================

职责：
1. 封装股票数据获取逻辑
2. 提供实时行情和历史数据接口
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

import pandas as pd

from data_provider.us_index_mapping import is_us_stock_code
from src.repositories.stock_repo import StockRepository

logger = logging.getLogger(__name__)


class StockService:
    """
    股票数据服务
    
    封装股票数据获取的业务逻辑
    """
    
    def __init__(self):
        """初始化股票数据服务"""
        self.repo = StockRepository()
    
    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票实时行情
        
        Args:
            stock_code: 股票代码
            
        Returns:
            实时行情数据字典
        """
        try:
            # 调用数据获取器获取实时行情
            from data_provider.base import DataFetcherManager
            
            manager = DataFetcherManager()
            quote = manager.get_realtime_quote(stock_code)
            
            if quote is None:
                logger.warning(f"获取 {stock_code} 实时行情失败")
                return None
            
            # UnifiedRealtimeQuote 是 dataclass，使用 getattr 安全访问字段
            # 字段映射: UnifiedRealtimeQuote -> API 响应
            # - code -> stock_code
            # - name -> stock_name
            # - price -> current_price
            # - change_amount -> change
            # - change_pct -> change_percent
            # - open_price -> open
            # - high -> high
            # - low -> low
            # - pre_close -> prev_close
            # - volume -> volume
            # - amount -> amount
            return {
                "stock_code": getattr(quote, "code", stock_code),
                "stock_name": getattr(quote, "name", None),
                "current_price": getattr(quote, "price", 0.0) or 0.0,
                "change": getattr(quote, "change_amount", None),
                "change_percent": getattr(quote, "change_pct", None),
                "open": getattr(quote, "open_price", None),
                "high": getattr(quote, "high", None),
                "low": getattr(quote, "low", None),
                "prev_close": getattr(quote, "pre_close", None),
                "volume": getattr(quote, "volume", None),
                "amount": getattr(quote, "amount", None),
                "update_time": datetime.now().isoformat(),
            }
            
        except ImportError:
            logger.warning("DataFetcherManager 未找到，使用占位数据")
            return self._get_placeholder_quote(stock_code)
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}", exc_info=True)
            return None
    
    def get_history_data(
        self,
        stock_code: str,
        period: str = "daily",
        days: int = 30
    ) -> Dict[str, Any]:
        """
        获取股票历史行情
        
        Args:
            stock_code: 股票代码
            period: K 线周期 (daily/weekly/monthly)
            days: 获取天数
            
        Returns:
            历史行情数据字典
        """
        if period not in {"daily", "weekly", "monthly", "yearly"}:
            raise ValueError(f"不支持的周期参数: {period}")
        
        try:
            # 调用数据获取器获取历史数据
            from data_provider.base import DataFetcherManager
            
            manager = DataFetcherManager()
            fetch_days = days
            if period == "weekly":
                fetch_days = max(days, 180)
            elif period == "monthly":
                fetch_days = max(days, 365)
            elif period == "yearly":
                fetch_days = max(days, 365 * 5)

            df: Optional[pd.DataFrame] = None
            if is_us_stock_code(stock_code):
                df = self._load_local_us_history(stock_code, days=fetch_days)
                if df is None:
                    logger.info("US history API fallback for %s", stock_code)

            if df is None:
                df, source = manager.get_daily_data(stock_code, days=fetch_days)
            
            if df is None or df.empty:
                logger.warning(f"获取 {stock_code} 历史数据失败")
                return {"stock_code": stock_code, "period": period, "data": []}

            if period != "daily":
                df = self._aggregate_history_frame(df, period)
                if df.empty:
                    logger.warning(f"聚合 {stock_code} {period} 历史数据后为空")
                    return {"stock_code": stock_code, "period": period, "data": []}
            
            # 获取股票名称
            stock_name = manager.get_stock_name(stock_code)
            
            # 转换为响应格式
            data = []
            for _, row in df.iterrows():
                date_val = row.get("date")
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val)
                
                data.append({
                    "date": date_str,
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)) if row.get("volume") else None,
                    "amount": float(row.get("amount", 0)) if row.get("amount") else None,
                    "change_percent": float(row.get("pct_chg", 0)) if row.get("pct_chg") else None,
                })
            
            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "period": period,
                "data": data,
            }
            
        except ImportError:
            logger.warning("DataFetcherManager 未找到，返回空数据")
            return {"stock_code": stock_code, "period": period, "data": []}
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}", exc_info=True)
            return {"stock_code": stock_code, "period": period, "data": []}

    def _get_local_us_history_path(self, stock_code: str) -> Path:
        return Path("/root/us_test/data/normalized/us") / f"{stock_code.upper()}.parquet"

    def _load_local_us_history(self, stock_code: str, days: int = 30) -> Optional[pd.DataFrame]:
        path = self._get_local_us_history_path(stock_code)
        if not path.exists():
            return None
        try:
            df = pd.read_parquet(path)
            if df is None or df.empty or "trade_date" not in df.columns:
                logger.warning("US local parquet invalid for %s: %s", stock_code, path)
                return None
            df = df.sort_values("trade_date").tail(days).copy()
            df = df.rename(columns={"trade_date": "date"})
            if "amount" not in df.columns:
                df["amount"] = None
            if "pct_chg" not in df.columns:
                df["pct_chg"] = None
            logger.info("US local parquet hit for %s: %s", stock_code, path)
            return df
        except Exception as e:
            logger.warning("US local parquet load failed for %s: %s (%s)", stock_code, path, e)
            return None

    def get_intraday_data(
        self,
        stock_code: str,
        interval: str = "5m",
        range_period: str = "1d",
    ) -> Dict[str, Any]:
        """
        获取分钟级 / 日内行情，优先用于报告图表展示。
        """
        supported_intervals = {"1m", "2m", "5m", "15m", "30m", "60m", "90m"}
        supported_ranges = {"1d", "5d", "1mo"}
        if interval not in supported_intervals:
            raise ValueError(f"不支持的 interval 参数: {interval}")
        if range_period not in supported_ranges:
            raise ValueError(f"不支持的 range 参数: {range_period}")

        try:
            import yfinance as yf
            from data_provider.base import DataFetcherManager
            from data_provider.yfinance_fetcher import YfinanceFetcher

            manager = DataFetcherManager()
            symbol = YfinanceFetcher()._convert_stock_code(stock_code)
            df = yf.download(
                tickers=symbol,
                period=range_period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                prepost=True,
                multi_level_index=True,
            )
            if isinstance(df.columns, pd.MultiIndex):
                ticker_level = df.columns.get_level_values(-1)
                if (ticker_level == symbol).any():
                    df = df.loc[:, ticker_level == symbol].copy()
                df.columns = df.columns.get_level_values(0)

            if df is None or df.empty:
                logger.warning("获取 %s intraday 数据为空", stock_code)
                return {
                    "stock_code": stock_code,
                    "stock_name": manager.get_stock_name(stock_code),
                    "interval": interval,
                    "range": range_period,
                    "data": [],
                    "source": "yfinance",
                }

            df = df.reset_index()
            timestamp_column = next((col for col in df.columns if str(col).lower() in {"datetime", "date"}), None)
            if timestamp_column is None:
                raise ValueError("intraday 数据缺少时间列")

            data: List[Dict[str, Any]] = []
            for _, row in df.iterrows():
                timestamp = row.get(timestamp_column)
                if hasattr(timestamp, "isoformat"):
                    time_value = timestamp.isoformat()
                else:
                    time_value = str(timestamp)
                data.append({
                    "time": time_value,
                    "open": float(row.get("Open", 0)),
                    "high": float(row.get("High", 0)),
                    "low": float(row.get("Low", 0)),
                    "close": float(row.get("Close", 0)),
                    "volume": float(row.get("Volume", 0)) if row.get("Volume") is not None else None,
                })

            return {
                "stock_code": stock_code,
                "stock_name": manager.get_stock_name(stock_code),
                "interval": interval,
                "range": range_period,
                "data": data,
                "source": "yfinance",
            }
        except ImportError:
            logger.warning("yfinance 不可用，无法获取 intraday 数据")
            return {
                "stock_code": stock_code,
                "interval": interval,
                "range": range_period,
                "data": [],
                "source": "unavailable",
            }
        except Exception as e:
            logger.error(f"获取 intraday 数据失败: {e}", exc_info=True)
            return {
                "stock_code": stock_code,
                "interval": interval,
                "range": range_period,
                "data": [],
                "source": "error",
            }

    def _aggregate_history_frame(self, df: pd.DataFrame, period: str) -> pd.DataFrame:
        if period == "daily":
            return df

        if "date" not in df.columns:
            return pd.DataFrame()

        frame = df.copy()
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.sort_values("date")
        frame = frame.set_index("date")

        if period == "weekly":
            rule = "W-FRI"
        elif period == "monthly":
            rule = "ME"
        elif period == "yearly":
            rule = "YE"
        else:
            return frame.reset_index()
        aggregated = frame.resample(rule).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "amount": "sum",
            }
        )
        aggregated = aggregated.dropna(subset=["open", "high", "low", "close"]).reset_index()
        aggregated["pct_chg"] = aggregated["close"].pct_change() * 100
        aggregated["pct_chg"] = aggregated["pct_chg"].fillna(0).round(2)
        aggregated["code"] = frame["code"].iloc[-1] if "code" in frame.columns and not frame.empty else None
        return aggregated
    
    def _get_placeholder_quote(self, stock_code: str) -> Dict[str, Any]:
        """
        获取占位行情数据（用于测试）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            占位行情数据
        """
        return {
            "stock_code": stock_code,
            "stock_name": f"股票{stock_code}",
            "current_price": 0.0,
            "change": None,
            "change_percent": None,
            "open": None,
            "high": None,
            "low": None,
            "prev_close": None,
            "volume": None,
            "amount": None,
            "update_time": datetime.now().isoformat(),
        }
