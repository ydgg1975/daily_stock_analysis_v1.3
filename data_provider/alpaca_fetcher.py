# -*- coding: utf-8 -*-
"""Alpaca market-data fetcher for US stock scanner enrichment."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pandas as pd
import requests

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS
from .realtime_types import RealtimeSource, UnifiedRealtimeQuote, safe_float, safe_int
from .us_index_mapping import is_us_stock_code

logger = logging.getLogger(__name__)


def _isoformat_utc(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


class AlpacaFetcher(BaseFetcher):
    """Minimal Alpaca market-data adapter."""

    name = "AlpacaFetcher"
    priority = 3

    def __init__(
        self,
        *,
        api_key_id: str,
        secret_key: str,
        base_url: str = "https://data.alpaca.markets",
        data_feed: str = "iex",
        timeout: int = 15,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key_id = str(api_key_id or "").strip()
        self.secret_key = str(secret_key or "").strip()
        self.base_url = str(base_url or "https://data.alpaca.markets").rstrip("/")
        self.data_feed = str(data_feed or "iex").strip().lower() or "iex"
        self.timeout = max(5, int(timeout))
        self.session = session or requests.Session()
        if not self.api_key_id or not self.secret_key:
            raise ValueError("Alpaca requires both api_key_id and secret_key")

    def _headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key_id,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Accept": "application/json",
        }

    def _request_json(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> Any:
        response = self.session.get(
            f"{self.base_url}{path}",
            params=params or {},
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("message"):
            # Alpaca 4xx payloads commonly use {"message": "..."}.
            if response.status_code >= 400:
                raise DataFetchError(str(payload.get("message")))
        return payload

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        symbol = str(stock_code or "").strip().upper()
        if not is_us_stock_code(symbol):
            raise DataFetchError(f"AlpacaFetcher 仅支持美股代码: {stock_code}")

        payload = self._request_json(
            f"/v2/stocks/{symbol}/bars",
            params={
                "timeframe": "1Day",
                "start": start_date,
                "end": end_date,
                "adjustment": "all",
                "feed": self.data_feed,
                "limit": 1000,
            },
        )
        bars = payload.get("bars") if isinstance(payload, dict) else None
        if not isinstance(bars, list) or not bars:
            raise DataFetchError(f"Alpaca 未返回 {symbol} 的历史 bars")
        return pd.DataFrame(bars)

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=["code", *STANDARD_COLUMNS])

        normalized = df.copy()
        normalized = normalized.rename(
            columns={
                "t": "date",
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume",
                "vw": "vwap",
            }
        )
        normalized["date"] = pd.to_datetime(normalized["date"], utc=True, errors="coerce").dt.tz_localize(None)
        normalized["amount"] = pd.to_numeric(normalized.get("vwap"), errors="coerce") * pd.to_numeric(
            normalized.get("volume"),
            errors="coerce",
        )
        normalized["pct_chg"] = pd.to_numeric(normalized["close"], errors="coerce").pct_change().fillna(0.0) * 100.0
        normalized["code"] = str(stock_code or "").strip().upper()
        keep_cols = ["code", *STANDARD_COLUMNS]
        normalized = normalized[keep_cols].dropna(subset=["date", "open", "high", "low", "close"])
        return normalized.reset_index(drop=True)

    def get_daily_data(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30,
    ):
        end_dt = (
            datetime.fromisoformat(end_date)
            if end_date
            else datetime.now(timezone.utc)
        )
        start_dt = (
            datetime.fromisoformat(start_date)
            if start_date
            else end_dt - timedelta(days=max(days * 3, 30))
        )
        raw = self._fetch_raw_data(
            stock_code,
            start_dt.date().isoformat(),
            end_dt.date().isoformat(),
        )
        normalized = self._normalize_data(raw, stock_code)
        if normalized.empty:
            raise DataFetchError(f"Alpaca 未返回 {stock_code} 的可用历史数据")
        if days:
            normalized = normalized.tail(max(1, int(days))).reset_index(drop=True)
        return normalized, self.name

    def get_latest_quote(self, stock_code: str) -> Dict[str, Any]:
        symbol = str(stock_code or "").strip().upper()
        payload = self._request_json(
            f"/v2/stocks/{symbol}/quotes/latest",
            params={"feed": self.data_feed},
        )
        return payload.get("quote") if isinstance(payload, dict) else {}

    def get_snapshot(self, stock_code: str) -> Dict[str, Any]:
        symbol = str(stock_code or "").strip().upper()
        payload = self._request_json(
            f"/v2/stocks/{symbol}/snapshot",
            params={"feed": self.data_feed},
        )
        return payload if isinstance(payload, dict) else {}

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        symbol = str(stock_code or "").strip().upper()
        if not is_us_stock_code(symbol):
            return None

        snapshot = self.get_snapshot(symbol)
        latest_trade = snapshot.get("latestTrade") if isinstance(snapshot, dict) else {}
        latest_quote = snapshot.get("latestQuote") if isinstance(snapshot, dict) else {}
        minute_bar = snapshot.get("minuteBar") if isinstance(snapshot, dict) else {}
        daily_bar = snapshot.get("dailyBar") if isinstance(snapshot, dict) else {}
        prev_daily_bar = snapshot.get("prevDailyBar") if isinstance(snapshot, dict) else {}

        price = safe_float(
            latest_trade.get("p")
            or minute_bar.get("c")
            or daily_bar.get("c")
            or (
                (safe_float(latest_quote.get("ap")) or 0.0) + (safe_float(latest_quote.get("bp")) or 0.0)
            ) / 2.0
            if latest_quote
            else None
        )
        prev_close = safe_float(prev_daily_bar.get("c"))
        if price is None:
            quote = self.get_latest_quote(symbol)
            price = safe_float(quote.get("ap") or quote.get("bp"))
            if prev_close is None:
                prev_close = safe_float(daily_bar.get("o"))
        if price is None:
            return None

        high = safe_float(daily_bar.get("h") or minute_bar.get("h"))
        low = safe_float(daily_bar.get("l") or minute_bar.get("l"))
        open_price = safe_float(daily_bar.get("o") or minute_bar.get("o"))
        volume = safe_int(daily_bar.get("v") or minute_bar.get("v"))
        vwap = safe_float(daily_bar.get("vw") or minute_bar.get("vw"))
        amount = None
        if vwap is not None and volume is not None:
            amount = float(vwap) * float(volume)

        change_amount = None
        change_pct = None
        if prev_close is not None and prev_close > 0:
            change_amount = price - prev_close
            change_pct = (change_amount / prev_close) * 100.0

        return UnifiedRealtimeQuote(
            code=symbol,
            name=symbol,
            source=RealtimeSource.ALPACA,
            price=price,
            change_pct=round(change_pct, 4) if change_pct is not None else None,
            change_amount=round(change_amount, 4) if change_amount is not None else None,
            volume=volume,
            amount=amount,
            amplitude=(
                round(((high - low) / prev_close) * 100.0, 4)
                if high is not None and low is not None and prev_close not in (None, 0)
                else None
            ),
            open_price=open_price,
            high=high,
            low=low,
            pre_close=prev_close,
            market_timestamp=(
                _isoformat_utc(latest_trade.get("t"))
                or _isoformat_utc(latest_quote.get("t"))
                or _isoformat_utc(daily_bar.get("t"))
            ),
        )
