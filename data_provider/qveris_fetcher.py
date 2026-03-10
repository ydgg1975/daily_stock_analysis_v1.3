# -*- coding: utf-8 -*-
"""QVerisFetcher -- QVeris API data source for US stocks.

Aggregates Alpha Vantage, FMP, EODHD, Finnhub via QVeris routing engine.
Scope: US stocks only.  Priority: env QVERIS_PRIORITY (default 3).
"""
import logging, os
from typing import Any, Dict, List, Optional
import pandas as pd
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential
from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS
from .realtime_types import UnifiedRealtimeQuote, RealtimeSource, safe_float, safe_int
from .us_index_mapping import is_us_stock_code

logger = logging.getLogger(__name__)

# Column mapping tables --------------------------------------------------
_AV_COL_MAP = {"1. open": "open", "2. high": "high", "3. low": "low", "4. close": "close", "5. volume": "volume"}
_GENERIC_COLS = ("date", "open", "high", "low", "close", "volume", "amount")

# Real-time quote key aliases per provider (Finnhub c/o/h/l/v, FMP full names, AV mixed)
_RT_ALIASES: Dict[str, List[str]] = {
    "price": ["price", "c", "close"],
    "prev_close": ["previousClose", "pc", "prev_close"],
    "change_pct": ["dp", "change_pct", "changesPercentage"],
    "change_amount": ["d", "change", "change_amount"],
    "volume": ["volume", "v"],
    "open": ["open", "o"],
    "high": ["high", "h"],
    "low": ["low", "l"],
}


def _pick(data: Dict, keys_or_alias: Any) -> Any:
    """Return the first non-None value from *data*.

    *keys_or_alias* can be a list of key strings (used for historical parsing)
    or a string key into _RT_ALIASES (used for real-time quote mapping).
    """
    keys = _RT_ALIASES[keys_or_alias] if isinstance(keys_or_alias, str) else keys_or_alias
    return next((data[k] for k in keys if data.get(k) is not None), None)


class QVerisFetcher(BaseFetcher):
    """QVeris API data source (US stocks only, requires QVERIS_API_KEY)."""

    name = "QVerisFetcher"
    priority = int(os.getenv("QVERIS_PRIORITY", "3"))

    def __init__(self) -> None:
        from src.qveris_client import QVerisClient
        self._client = QVerisClient()
        if not self._client.enabled:
            logger.info("[QVerisFetcher] QVERIS_API_KEY not set, fetcher disabled")

    def _guard(self, code: str) -> str:
        """Validate US stock + enabled client. Returns uppercased code."""
        code = code.strip().upper()
        if not is_us_stock_code(code):
            raise DataFetchError(f"[QVerisFetcher] {code} is not a US stock, skipping")
        if not self._client.enabled:
            raise DataFetchError("[QVerisFetcher] disabled (no API key)")
        return code

    # -- Historical data ---------------------------------------------------

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5),
           retry=retry_if_not_exception_type(DataFetchError))
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        code = self._guard(stock_code)
        from src.qveris_client import QVerisError
        try:
            result = self._client.search_and_execute(
                query=f"historical daily stock price for {code}",
                parameters={"symbol": code, "from": start_date, "to": end_date},
            )
        except QVerisError as exc:
            raise DataFetchError(f"[QVerisFetcher] {exc}") from exc
        if not result:
            raise DataFetchError(f"[QVerisFetcher] No data for {code}")
        return self._to_dataframe(result, code)

    @staticmethod
    def _to_dataframe(result: Any, code: str) -> pd.DataFrame:
        if isinstance(result, dict):
            data = result.get("data") or result.get("historical") or result.get("results") or result
            if isinstance(data, dict):
                for key in data:
                    if "time series" in key.lower() or "daily" in key.lower():
                        return pd.DataFrame([{"date": dt, **v} for dt, v in data[key].items()])
                data = [data]
        else:
            data = result
        if not isinstance(data, list) or not data:
            raise DataFetchError(f"[QVerisFetcher] Unexpected format for {code}")
        return pd.DataFrame(data)

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        df = df.copy()
        col_map: Dict[str, str] = {}
        lc = {c.lower().strip(): c for c in df.columns}
        for av_key, std in _AV_COL_MAP.items():
            if av_key in lc:
                col_map[lc[av_key]] = std
        for std in _GENERIC_COLS:
            if std not in col_map.values() and std in lc:
                col_map[lc[std]] = std
        df = df.rename(columns=col_map)
        if "date" not in df.columns:
            df = df.reset_index().rename(columns={"index": "date"})
        # Sort by date ascending before computing pct_chg (QVeris may return reverse-chronological)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.sort_values("date", ascending=True).reset_index(drop=True)
        if "pct_chg" not in df.columns and "close" in df.columns:
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df["pct_chg"] = (df["close"].pct_change() * 100).fillna(0).round(2)
        if "amount" not in df.columns and {"volume", "close"} <= set(df.columns):
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
            df["amount"] = df["volume"] * pd.to_numeric(df["close"], errors="coerce")
        df["code"] = stock_code
        return df[[c for c in ["code"] + STANDARD_COLUMNS if c in df.columns]]

    # -- Real-time quote ---------------------------------------------------

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        code = stock_code.strip().upper()
        if not is_us_stock_code(code) or not self._client.enabled:
            return None
        data = self._fetch_realtime(code)
        return self._build_quote(data, code) if data else None

    def _fetch_realtime(self, code: str) -> Optional[Dict]:
        from src.qveris_client import QVerisError
        try:
            r = self._client.search_and_execute(query=f"real-time stock quote for {code}", parameters={"symbol": code})
        except QVerisError as exc:
            logger.warning("[QVerisFetcher] RT error %s: %s", code, exc)
            return None
        if not r:
            return None
        d = r if isinstance(r, dict) else {}
        return d["data"] if ("data" in d and isinstance(d["data"], dict)) else d

    @staticmethod
    def _build_quote(d: Dict, code: str) -> Optional[UnifiedRealtimeQuote]:
        price = safe_float(_pick(d, "price"))
        if price is None:
            return None
        prev = safe_float(_pick(d, "prev_close"))
        cpct = safe_float(_pick(d, "change_pct"))
        camt = safe_float(_pick(d, "change_amount"))
        if cpct is None and prev and prev > 0:
            camt = price - prev
            cpct = round(camt / prev * 100, 2)
        return UnifiedRealtimeQuote(
            code=code, name=d.get("name", code), source=RealtimeSource.QVERIS,
            price=price,
            change_pct=round(cpct, 2) if cpct is not None else None,
            change_amount=round(camt, 4) if camt is not None else None,
            volume=safe_int(_pick(d, "volume")),
            open_price=safe_float(_pick(d, "open")),
            high=safe_float(_pick(d, "high")),
            low=safe_float(_pick(d, "low")),
            pre_close=prev,
        )
