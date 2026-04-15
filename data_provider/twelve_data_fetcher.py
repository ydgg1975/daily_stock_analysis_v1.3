# -*- coding: utf-8 -*-
"""Twelve Data market-data fetcher for HK scanner support."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd
import requests

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS, normalize_stock_code
from .realtime_types import RealtimeSource, UnifiedRealtimeQuote, safe_float, safe_int
from .us_index_mapping import is_us_stock_code

logger = logging.getLogger(__name__)


def _is_hk_symbol(stock_code: str) -> bool:
    normalized = normalize_stock_code(stock_code).upper()
    return normalized.startswith("HK") and normalized[2:].isdigit()


def _canonical_hk_code(stock_code: str) -> str:
    normalized = normalize_stock_code(stock_code).upper()
    if not _is_hk_symbol(normalized):
        raise DataFetchError(f"TwelveDataFetcher 暂不支持该代码: {stock_code}")
    return normalized


def _provider_symbol_params(stock_code: str) -> Dict[str, Optional[str]]:
    normalized = normalize_stock_code(stock_code).upper()
    if is_us_stock_code(normalized):
        return {
            "normalized_code": normalized,
            "symbol": normalized,
            "exchange": None,
        }
    if _is_hk_symbol(normalized):
        digits = normalized[2:]
        symbol = str(int(digits)).zfill(4)
        return {
            "normalized_code": normalized,
            "symbol": symbol,
            "exchange": "HKEX",
        }
    raise DataFetchError(f"TwelveDataFetcher 暂不支持该代码: {stock_code}")


def _provider_symbol_to_hk_code(symbol: Any) -> str:
    digits = "".join(ch for ch in str(symbol or "").strip() if ch.isdigit())
    if not digits:
        return ""
    return f"HK{str(int(digits)).zfill(5)}"


class TwelveDataFetcher(BaseFetcher):
    """Minimal Twelve Data adapter for HK/US scanner history and quotes."""

    name = "TwelveDataFetcher"
    priority = 3

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.twelvedata.com",
        timeout: int = 15,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = str(api_key or "").strip()
        self.base_url = str(base_url or "https://api.twelvedata.com").rstrip("/")
        self.timeout = max(5, int(timeout))
        self.session = session or requests.Session()
        if not self.api_key:
            raise ValueError("Twelve Data requires a non-empty API key")

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def _request_json(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> Any:
        request_params = dict(params or {})
        request_params["apikey"] = self.api_key
        response = self.session.get(
            f"{self.base_url}{path}",
            params=request_params,
            timeout=self.timeout,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and str(payload.get("status") or "").strip().lower() == "error":
            raise DataFetchError(str(payload.get("message") or "Twelve Data request failed"))
        return payload

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        symbol_params = _provider_symbol_params(stock_code)
        outputsize = max(60, min(5000, 240))
        params: Dict[str, Any] = {
            "symbol": symbol_params["symbol"],
            "interval": "1day",
            "start_date": start_date,
            "end_date": end_date,
            "outputsize": outputsize,
            "format": "JSON",
        }
        if symbol_params["exchange"]:
            params["exchange"] = symbol_params["exchange"]
        payload = self._request_json("/time_series", params=params)
        values = payload.get("values") if isinstance(payload, dict) else None
        if not isinstance(values, list) or not values:
            raise DataFetchError(f"Twelve Data 未返回 {stock_code} 的日线数据")
        return pd.DataFrame(values)

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=["code", *STANDARD_COLUMNS])

        normalized = df.copy()
        if "datetime" in normalized.columns:
            normalized = normalized.rename(columns={"datetime": "date"})
        normalized["date"] = pd.to_datetime(normalized.get("date"), errors="coerce")
        normalized["open"] = pd.to_numeric(normalized.get("open"), errors="coerce")
        normalized["high"] = pd.to_numeric(normalized.get("high"), errors="coerce")
        normalized["low"] = pd.to_numeric(normalized.get("low"), errors="coerce")
        normalized["close"] = pd.to_numeric(normalized.get("close"), errors="coerce")
        normalized["volume"] = pd.to_numeric(normalized.get("volume"), errors="coerce")
        normalized["amount"] = normalized["close"] * normalized["volume"]
        normalized["pct_chg"] = normalized["close"].pct_change().fillna(0.0) * 100.0
        normalized["code"] = str(_provider_symbol_params(stock_code)["normalized_code"])
        normalized = normalized[["code", *STANDARD_COLUMNS]]
        normalized = normalized.dropna(subset=["date", "open", "high", "low", "close"])
        return normalized.sort_values("date").reset_index(drop=True)

    def get_daily_data(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30,
    ):
        end_dt = datetime.fromisoformat(end_date) if end_date else datetime.utcnow()
        start_dt = (
            datetime.fromisoformat(start_date)
            if start_date
            else end_dt - timedelta(days=max(days * 3, 60))
        )
        raw = self._fetch_raw_data(
            stock_code,
            start_dt.date().isoformat(),
            end_dt.date().isoformat(),
        )
        normalized = self._normalize_data(raw, stock_code)
        if normalized.empty:
            raise DataFetchError(f"Twelve Data 未返回 {stock_code} 的可用日线数据")
        if days:
            normalized = normalized.tail(max(1, int(days))).reset_index(drop=True)
        return normalized, self.name

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        symbol_params = _provider_symbol_params(stock_code)
        params: Dict[str, Any] = {"symbol": symbol_params["symbol"]}
        if symbol_params["exchange"]:
            params["exchange"] = symbol_params["exchange"]
        payload = self._request_json("/quote", params=params)
        if not isinstance(payload, dict):
            return None

        normalized_code = str(symbol_params["normalized_code"])
        if _is_hk_symbol(normalized_code):
            quote_code = _provider_symbol_to_hk_code(payload.get("symbol") or symbol_params["symbol"]) or normalized_code
        else:
            quote_code = normalized_code

        price = safe_float(payload.get("close") or payload.get("price"))
        prev_close = safe_float(payload.get("previous_close"))
        if price is None:
            return None
        change_amount = safe_float(payload.get("change"))
        change_pct = safe_float(payload.get("percent_change"))
        if change_amount is None and prev_close not in (None, 0):
            change_amount = float(price) - float(prev_close)
        if change_pct is None and prev_close not in (None, 0):
            change_pct = ((float(price) / float(prev_close)) - 1.0) * 100.0

        volume = safe_int(payload.get("volume"))
        amount = float(price) * float(volume) if volume is not None else None
        return UnifiedRealtimeQuote(
            code=quote_code,
            name=str(payload.get("name") or quote_code),
            source=RealtimeSource.TWELVE_DATA,
            price=price,
            change_pct=change_pct,
            change_amount=change_amount,
            volume=volume,
            amount=amount,
            open_price=safe_float(payload.get("open")),
            high=safe_float(payload.get("high")),
            low=safe_float(payload.get("low")),
            pre_close=prev_close,
            high_52w=safe_float(payload.get("fifty_two_week", {}).get("high") if isinstance(payload.get("fifty_two_week"), dict) else None),
            low_52w=safe_float(payload.get("fifty_two_week", {}).get("low") if isinstance(payload.get("fifty_two_week"), dict) else None),
            market_timestamp=str(payload.get("datetime") or "") or None,
        )
