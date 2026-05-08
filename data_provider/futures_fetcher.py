# -*- coding: utf-8 -*-
"""AkShare-backed domestic futures main-contract data fetcher."""

import logging
from typing import Dict

import akshare as ak
import pandas as pd

from src.data.futures_mapping import (
    get_futures_name,
    is_specific_futures_contract,
    normalize_futures_symbol,
    to_main_contract_symbol,
)

from .base import BaseFetcher, DataFetchError

logger = logging.getLogger(__name__)


class FuturesFetcher(BaseFetcher):
    """Fetch domestic commodity futures main-continuous daily data."""

    name = "FuturesFetcher"
    priority = 0

    _COLUMN_MAP: Dict[str, str] = {
        "日期": "date",
        "date": "date",
        "开盘价": "open",
        "开盘": "open",
        "open": "open",
        "最高价": "high",
        "最高": "high",
        "high": "high",
        "最低价": "low",
        "最低": "low",
        "low": "low",
        "收盘价": "close",
        "收盘": "close",
        "close": "close",
        "成交量": "volume",
        "volume": "volume",
        "成交额": "amount",
        "amount": "amount",
        "涨跌幅": "pct_chg",
        "涨跌幅%": "pct_chg",
        "pct_chg": "pct_chg",
    }

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        symbol = to_main_contract_symbol(stock_code)
        if not symbol:
            raise DataFetchError("期货品种代码不能为空")
        if is_specific_futures_contract(symbol):
            logger.info("[FuturesFetcher] 获取期货具体合约日线: %s", symbol)
            df = ak.futures_zh_daily_sina(symbol=symbol)
            if df is None or df.empty or "date" not in df.columns:
                return df
            normalized = df.copy()
            normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            return normalized[(normalized["date"] >= start) & (normalized["date"] <= end)]
        logger.info("[FuturesFetcher] 获取期货主力连续日线: %s", symbol)
        return ak.futures_main_sina(symbol=symbol, start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        normalized = df.rename(columns={col: self._COLUMN_MAP.get(str(col), str(col)) for col in df.columns}).copy()
        required = ["date", "open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in normalized.columns]
        if missing:
            raise DataFetchError(f"期货日线缺少必要字段: {', '.join(missing)}")

        if "amount" not in normalized.columns:
            normalized["amount"] = 0
        if "pct_chg" not in normalized.columns:
            close = pd.to_numeric(normalized["close"], errors="coerce")
            normalized["pct_chg"] = close.pct_change().fillna(0) * 100

        return normalized[["date", "open", "high", "low", "close", "volume", "amount", "pct_chg"]]

    def get_stock_name(self, stock_code: str) -> str:
        """Return futures display name using the existing stock-name interface."""
        symbol = normalize_futures_symbol(stock_code)
        name = get_futures_name(symbol)
        if not name:
            return stock_code
        return name if is_specific_futures_contract(symbol) else f"{name}主力"
