import time
from threading import Lock
from typing import Any, Dict, List

import pandas as pd

_FUNDAMENTALS_TTL_SECONDS = 60 * 30
_EARNINGS_TTL_SECONDS = 60 * 30
_fundamentals_cache: Dict[str, Dict[str, Any]] = {}
_earnings_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = Lock()


def _num(value: Any) -> Any:
    if value in (None, "", "N/A"):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return int(num) if num.is_integer() else num


def _safe_series_lookup(frame: pd.DataFrame, row_key: str, col_key: Any) -> Any:
    if frame is None or frame.empty:
        return None
    try:
        if row_key not in frame.index or col_key not in frame.columns:
            return None
        return _num(frame.loc[row_key, col_key])
    except Exception:
        return None


def get_yfinance_fundamentals(symbol: str) -> Dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {}

    now = time.time()
    with _cache_lock:
        cached = _fundamentals_cache.get(symbol)
        if cached and now - cached["ts"] < _FUNDAMENTALS_TTL_SECONDS:
            return cached["data"]

    import yfinance as yf

    ticker = yf.Ticker(symbol)
    info = ticker.info or {}

    payload = {
        "marketCap": _num(info.get("marketCap") or info.get("enterpriseValue")),
        "trailingPE": _num(info.get("trailingPE")),
        "forwardPE": _num(info.get("forwardPE")),
        "totalRevenue": _num(info.get("totalRevenue")),
        "revenueGrowth": _num(info.get("revenueGrowth")),
        "grossMargins": _num(info.get("grossMargins")),
        "operatingMargins": _num(info.get("operatingMargins")),
        "freeCashflow": _num(info.get("freeCashflow")),
        "operatingCashflow": _num(info.get("operatingCashflow")),
        "debtToEquity": _num(info.get("debtToEquity")),
        "currentRatio": _num(info.get("currentRatio")),
        "returnOnEquity": _num(info.get("returnOnEquity")),
        "returnOnAssets": _num(info.get("returnOnAssets")),
    }

    with _cache_lock:
        _fundamentals_cache[symbol] = {"ts": now, "data": payload}
    return payload


def get_yfinance_quarterly_financials(symbol: str, max_quarters: int = 6) -> List[Dict[str, Any]]:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return []

    now = time.time()
    with _cache_lock:
        cached = _earnings_cache.get(symbol)
        if cached and now - cached["ts"] < _EARNINGS_TTL_SECONDS:
            return cached["data"]

    import yfinance as yf

    ticker = yf.Ticker(symbol)
    income_df = ticker.quarterly_income_stmt
    cashflow_df = ticker.quarterly_cashflow

    if income_df is None or income_df.empty:
        with _cache_lock:
            _earnings_cache[symbol] = {"ts": now, "data": []}
        return []

    columns = list(income_df.columns)[:max_quarters]
    rows: List[Dict[str, Any]] = []
    for col in columns:
        fiscal_date = getattr(col, "date", lambda: None)()
        rows.append(
            {
                "fiscal_date": fiscal_date.isoformat() if fiscal_date else str(col)[:10],
                "revenue": _safe_series_lookup(income_df, "Total Revenue", col),
                "gross_profit": _safe_series_lookup(income_df, "Gross Profit", col),
                "operating_income": _safe_series_lookup(income_df, "Operating Income", col),
                "net_income": _safe_series_lookup(income_df, "Net Income", col),
                "eps": _safe_series_lookup(income_df, "Diluted EPS", col)
                or _safe_series_lookup(income_df, "Basic EPS", col),
                "operating_cashflow": _safe_series_lookup(cashflow_df, "Operating Cash Flow", col),
            }
        )

    with _cache_lock:
        _earnings_cache[symbol] = {"ts": now, "data": rows}
    return rows
