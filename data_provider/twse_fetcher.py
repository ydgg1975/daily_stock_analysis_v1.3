# -*- coding: utf-8 -*-
"""
===================================
台股数据源 (TWSE/TWTP) — MCP 桥接
===================================

职责：
1. 通过 MCP (casual-market) 工具获取台湾股票数据
2. 将 MCP 返回的数据转换为 DSA 标准格式
3. 支持日线、实时行情、板块排行、筹码分布等

设计模式：遵循 DSA 的策略模式 (Strategy Pattern)
- 继承 BaseFetcher
- 优先级设为 0（最高，因为 MCP 是我们自己的可控数据源）

台股代码规则：
- 上市：4位数字（如 2330 台积电）
- 上柜：4位数字（如 5274 信骅）
- ETF：4位数字（如 0050 台湾50）
- 不使用 SH/SZ/HK 前缀
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .base import BaseFetcher

logger = logging.getLogger(__name__)


class TWSEFetcher(BaseFetcher):
    """
    台股数据源 — 通过 MCP casual-market 工具获取数据
    
    Priority 0: 最高优先级（MCP 是我们自己的可控数据源）
    """

    name = "twse"
    priority = 0  # 最高优先级

    def __init__(self, mcp_bridge=None, **kwargs):
        """
        Args:
            mcp_bridge: MCP 数据桥接实例，负责调用 MCP 工具获取数据
                        如果为 None，将通过 subprocess 调用 hermes CLI
        """
        super().__init__(**kwargs)
        self.mcp_bridge = mcp_bridge

    # ─── 核心方法（必须实现） ───

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        通过 MCP 获取台股日K线数据
        
        MCP get_stock_history 返回格式：
        {
            "success": true,
            "data": {
                "symbol": "2330",
                "month": "202605",
                "daily_prices": [
                    {"date": "2026-05-04", "open": 2200.0, "high": 2285.0,
                     "low": 2195.0, "close": 2275.0, "volume": 44458732,
                     "trade_value": 99944198300.0, "transactions": 129173,
                     "change": "+140.00"}
                ],
                "count": 13
            }
        }
        
        Args:
            stock_code: 台股代码，如 '2330'
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        """
        try:
            # 需要拉取 start_date 所在月份的数据
            # MCP get_stock_history 一次回一个月
            # 先取起始月，如果跨月则需要多次拉取
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            all_records = []
            current = start_dt.replace(day=1)
            
            while current <= end_dt:
                date_param = current.strftime("%Y%m") + "01"  # YYYYMMDD format
                
                data = self._call_mcp("get_stock_history", {
                    "symbol": stock_code,
                    "date": date_param
                })
                
                if not data or not data.get("success"):
                    logger.debug(f"TWSEFetcher: no data for {stock_code} month {date_param}")
                    # Move to next month
                    if current.month == 12:
                        current = current.replace(year=current.year + 1, month=1)
                    else:
                        current = current.replace(month=current.month + 1)
                    continue
                
                daily_prices = data.get("data", {}).get("daily_prices", [])
                for entry in daily_prices:
                    try:
                        change_str = str(entry.get("change", "0")).replace(",", "").strip()
                        # Calculate pct_chg from change and close
                        close_val = float(entry.get("close", 0))
                        change_val = float(change_str) if change_str else 0.0
                        # Previous close = close - change
                        prev_close = close_val - change_val if close_val else None
                        pct_chg = (change_val / prev_close * 100) if prev_close and prev_close > 0 else None
                        
                        all_records.append({
                            "date": entry.get("date", ""),
                            "open": float(entry.get("open", 0)),
                            "high": float(entry.get("high", 0)),
                            "low": float(entry.get("low", 0)),
                            "close": float(entry.get("close", 0)),
                            "volume": float(entry.get("volume", 0)),
                            "amount": float(entry.get("trade_value", 0)),
                            "pct_chg": pct_chg,
                        })
                    except (ValueError, TypeError) as e:
                        logger.debug(f"TWSEFetcher: skipping entry {entry}: {e}")
                        continue
                
                # Move to next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)

            df = pd.DataFrame(all_records)
            if df.empty:
                return df

            # 过滤日期范围
            df["date"] = pd.to_datetime(df["date"])
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            df = df[(df["date"] >= start) & (df["date"] <= end)]
            df = df.sort_values("date").reset_index(drop=True)

            return df

        except Exception as e:
            logger.error(f"TWSEFetcher._fetch_raw_data error: {e}")
            return pd.DataFrame()

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化为 DSA 标准格式
        列: [date, open, high, low, close, volume, amount, pct_chg]
        """
        if df.empty:
            return df

        # 确保 date 列为字符串格式 YYYY-MM-DD
        if pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = df["date"].dt.strftime("%Y-%m-%d")

        # 确保数值列
        for col in ["open", "high", "low", "close", "volume", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "pct_chg" in df.columns:
            df["pct_chg"] = pd.to_numeric(df["pct_chg"], errors="coerce")

        # 按标准列排序
        standard_cols = [col for col in ["date", "open", "high", "low", "close", "volume", "amount", "pct_chg"] if col in df.columns]
        df = df[standard_cols]

        return df

    # ─── 市场概览方法 ───

    def get_main_indices(self, region: str = "tw") -> Optional[List[Dict[str, Any]]]:
        """获取台股主要指数（加权指数、电子、金融等）"""
        try:
            data = self._call_mcp("get_market_historical_index", {})
            if not data or not data.get("success"):
                return None

            indices = data.get("data", {}).get("indices", [])
            result = []
            for idx in indices:
                try:
                    pct = float(str(idx.get("漲跌百分比", "0")).replace("%", "").replace(",", ""))
                    change = float(str(idx.get("漲跌點數", "0")).replace(",", ""))
                    current = float(str(idx.get("收盤指數", "0")).replace(",", ""))
                    result.append({
                        "code": idx.get("指數", ""),
                        "name": idx.get("指數", ""),
                        "current": current,
                        "change": change,
                        "change_pct": pct / 100 if abs(pct) < 10 else pct,  # 可能已经是百分比
                        "volume": 0,
                        "amount": 0,
                    })
                except (ValueError, TypeError) as e:
                    logger.debug(f"TWSEFetcher: skip index row: {e}")
                    continue
            return result if result else None

        except Exception as e:
            logger.error(f"TWSEFetcher.get_main_indices error: {e}")
            return None

    def get_market_stats(self) -> Optional[Dict[str, Any]]:
        """获取台股市场涨跌统计"""
        try:
            data = self._call_mcp("get_real_time_trading_stats", {})
            if not data or not data.get("success"):
                return None

            stats = data.get("data", {})
            return {
                "up_count": stats.get("advancing_stocks", 0),
                "down_count": stats.get("declining_stocks", 0),
                "flat_count": stats.get("unchanged_stocks", 0),
                "limit_up_count": stats.get("limit_up_stocks", 0),
                "limit_down_count": stats.get("limit_down_stocks", 0),
                "total_amount": stats.get("total_value", 0),
            }
        except Exception as e:
            logger.error(f"TWSEFetcher.get_market_stats error: {e}")
            return None

    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取台股实时行情"""
        try:
            data = self._call_mcp("get_taiwan_stock_price", {"symbol": stock_code})
            if not data or not data.get("success"):
                return None

            info = data.get("data", {})
            return {
                "code": stock_code,
                "name": info.get("name", ""),
                "current": self._safe_float(info.get("closePrice", 0)),
                "change": self._safe_float(info.get("change", 0)),
                "change_pct": self._safe_float(info.get("changePercent", 0)),
                "open": self._safe_float(info.get("openPrice", 0)),
                "high": self._safe_float(info.get("highPrice", 0)),
                "low": self._safe_float(info.get("lowPrice", 0)),
                "volume": self._safe_float(info.get("volume", 0)),
                "amount": 0,
                "date": info.get("date", ""),
            }
        except Exception as e:
            logger.error(f"TWSEFetcher.get_realtime_quote error for {stock_code}: {e}")
            return None

    def get_institutional_data(self, stock_code: str, date: str = None) -> Optional[Dict[str, Any]]:
        """获取台股三大法人买卖超数据"""
        try:
            params = {}
            if stock_code:
                params["symbol"] = stock_code
            if date:
                params["date"] = date

            data = self._call_mcp("get_institutional_investors", params)
            if not data or not data.get("success"):
                return None

            return data.get("data", {})
        except Exception as e:
            logger.error(f"TWSEFetcher.get_institutional_data error: {e}")
            return None

    # ─── 辅助方法 ───

    @staticmethod
    def _safe_float(value, default=0.0) -> float:
        """安全转换数值"""
        try:
            if value is None or value == '-' or value == '--':
                return default
            return float(str(value).replace(",", "").replace("%", ""))
        except (ValueError, TypeError):
            return default

    def _call_mcp(self, tool_name: str, params: dict) -> Optional[dict]:
        """
        调用 MCP casual-market 工具
        
        两种模式：
        1. 如果有 mcp_bridge（从 Hermes agent 调用），直接调用
        2. 如果没有（作为独立 Python 运行），通过 hermes CLI 调用
        """
        if self.mcp_bridge:
            return self.mcp_bridge.call_tool(tool_name, params)

        # 通过 hermes CLI 调用 MCP
        import json
        import subprocess

        try:
            # 构建 hermes CLI 命令
            cmd = [
                "hermes", "mcp", "call", "casual-market",
                tool_name,
                "--params", json.dumps(params)
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                logger.error(f"TWSEFetcher MCP call failed: {result.stderr}")
                return None
            
            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.error(f"TWSEFetcher MCP call error: {e}")
            return None

    def is_tw_stock(self, code: str) -> bool:
        """判断是否为台股代码"""
        normalized = code.strip()
        # 台股代码：4位数字（上市/上柜） 或 6位数字含字母（如 0050B）
        if normalized.isdigit() and 4 <= len(normalized) <= 6:
            return True
        return False