# -*- coding: utf-8 -*-
"""
===================================
TwelveDataFetcher - 美股增强数据源
===================================

数据来源：Twelve Data API (https://twelvedata.com)
特点：美股/港股/全球市场，免费 800 次/天
定位：美股场景下 YfinanceFetcher 的 fallback / 替代

关键策略：
1. 仅在配置了 TWELVEDATA_API_KEY 时启用
2. 优先级默认 5（低于 YfinanceFetcher 的 4），可通过 TWELVEDATA_PRIORITY 调整
3. 支持美股和港股代码自动转换
"""

import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

import pandas as pd
import requests

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS
from .us_index_mapping import is_us_stock_code, is_us_index_code, get_us_index_yf_symbol

logger = logging.getLogger(__name__)

# Twelve Data 美股指数代码映射
_TD_INDEX_MAP = {
    "SPX": "SPX",
    "DJI": "DJI",
    "IXIC": "IXIC",
    "NDX": "NDX",
    "RUT": "RUT",
    "VIX": "VIX",
}


class TwelveDataFetcher(BaseFetcher):
    """
    Twelve Data 数据源实现

    优先级：5（默认，低于 YfinanceFetcher；可通过 TWELVEDATA_PRIORITY 环境变量调整）
    数据来源：Twelve Data REST API
    免费额度：800 次/天，8 次/分钟
    """

    name = "TwelveDataFetcher"
    priority = int(os.getenv("TWELVEDATA_PRIORITY", "5"))

    BASE_URL = "https://api.twelvedata.com"

    def __init__(self):
        self._api_key = os.getenv("TWELVEDATA_API_KEY", "").strip()
        if not self._api_key:
            logger.warning("TWELVEDATA_API_KEY 未配置，TwelveDataFetcher 不可用")
            self.priority = 999

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        转换股票代码为 Twelve Data 格式

        - 美股：AAPL -> AAPL
        - 美股指数：SPX -> SPX
        - 港股：HK00700 -> 0700:HKEX
        - A股：600519 -> 600519:SHH
        """
        code = stock_code.strip().upper()

        if code in _TD_INDEX_MAP:
            return _TD_INDEX_MAP[code]

        if is_us_stock_code(code):
            return code

        if code.startswith("HK"):
            hk_num = code[2:].lstrip("0") or "0"
            return f"{hk_num.zfill(4)}:HKEX"

        if code.isdigit() and len(code) == 6:
            if code.startswith(("600", "601", "603", "688")):
                return f"{code}:SHH"
            else:
                return f"{code}:SHZ"

        return code

    def _request(self, endpoint: str, params: dict) -> dict:
        """发送 API 请求"""
        params["apikey"] = self._api_key
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "error":
                raise DataFetchError(
                    f"Twelve Data API 错误: {data.get('message', 'unknown')}"
                )
            return data
        except requests.RequestException as e:
            raise DataFetchError(f"Twelve Data 请求失败: {e}") from e

    def _fetch_raw_data(
        self, stock_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """从 Twelve Data 获取日线数据"""
        td_code = self._convert_stock_code(stock_code)

        # 根据日期范围估算 outputsize，避免硬编码截断
        # Twelve Data 的 outputsize 是返回数据点上限，5000 为 API 最大值
        try:
            delta_days = (
                datetime.strptime(end_date, "%Y-%m-%d")
                - datetime.strptime(start_date, "%Y-%m-%d")
            ).days
            output_size = min(max(delta_days, 60), 5000)
        except (ValueError, TypeError):
            output_size = 250

        params = {
            "symbol": td_code,
            "interval": "1day",
            "start_date": start_date,
            "end_date": end_date,
            "outputsize": output_size,
            "format": "JSON",
        }

        data = self._request("time_series", params)
        values = data.get("values", [])
        if not values:
            raise DataFetchError(
                f"Twelve Data 未返回 {stock_code} ({td_code}) 的数据"
            )

        df = pd.DataFrame(values)
        return df

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化 Twelve Data 数据

        Twelve Data 返回列：datetime, open, high, low, close, volume
        映射到标准列：date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()

        df = df.rename(columns={"datetime": "date"})

        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.sort_values("date", ascending=True).reset_index(drop=True)
        if "close" in df.columns:
            df["pct_chg"] = df["close"].pct_change() * 100
            df["pct_chg"] = df["pct_chg"].fillna(0).round(2)

        if "volume" in df.columns and "close" in df.columns:
            df["amount"] = df["volume"] * df["close"]
        else:
            df["amount"] = 0

        df["code"] = stock_code

        keep_cols = ["code"] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df
