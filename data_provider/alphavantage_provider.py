import os
import time
from threading import Lock

import requests

API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"
_OVERVIEW_CACHE_TTL_SECONDS = 60 * 60 * 24
_overview_cache = {}
_overview_cache_lock = Lock()
_INCOME_CACHE_TTL_SECONDS = 60 * 60 * 12
_income_cache = {}
_income_cache_lock = Lock()


def _request(params: dict) -> dict:
    if not API_KEY:
        raise ValueError("ALPHA_VANTAGE_API_KEY 未配置")

    params = {**params, "apikey": API_KEY}
    resp = requests.get(BASE_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if "Error Message" in data:
        raise ValueError(data["Error Message"])
    if "Note" in data:
        raise ValueError(data["Note"])

    return data


def get_rsi(symbol: str, interval: str = "daily", time_period: int = 14):
    data = _request({
        "function": "RSI",
        "symbol": symbol,
        "interval": interval,
        "time_period": time_period,
        "series_type": "close",
    })

    values = data.get("Technical Analysis: RSI", {})
    if not values:
        return None

    latest_key = sorted(values.keys(), reverse=True)[0]
    return float(values[latest_key]["RSI"])


def get_sma(symbol: str, period: int = 20, interval: str = "daily"):
    data = _request({
        "function": "SMA",
        "symbol": symbol,
        "interval": interval,
        "time_period": period,
        "series_type": "close",
    })

    values = data.get("Technical Analysis: SMA", {})
    if not values:
        return None

    latest_key = sorted(values.keys(), reverse=True)[0]
    return float(values[latest_key]["SMA"])


def get_company_overview(symbol: str) -> dict:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {}

    now = time.time()
    with _overview_cache_lock:
        cached = _overview_cache.get(symbol)
        if cached and now - cached["ts"] < _OVERVIEW_CACHE_TTL_SECONDS:
            return cached["data"]

    data = _request({
        "function": "OVERVIEW",
        "symbol": symbol,
    })

    with _overview_cache_lock:
        _overview_cache[symbol] = {"ts": now, "data": data}
    return data


def get_shares_outstanding(symbol: str):
    try:
        overview = get_company_overview(symbol)
    except Exception:
        return None

    raw_val = overview.get("SharesOutstanding")
    if raw_val in (None, "", "None"):
        return None

    try:
        value = int(float(raw_val))
        if value <= 0:
            return None
        return value
    except (TypeError, ValueError):
        return None


def _to_float(value):
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_income_statement_quarterly(symbol: str):
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return []

    now = time.time()
    with _income_cache_lock:
        cached = _income_cache.get(symbol)
        if cached and now - cached["ts"] < _INCOME_CACHE_TTL_SECONDS:
            return cached["data"]

    data = _request({
        "function": "INCOME_STATEMENT",
        "symbol": symbol,
    })
    quarterly = data.get("quarterlyReports", []) if isinstance(data, dict) else []
    result = []
    for item in quarterly[:8]:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "fiscal_date": item.get("fiscalDateEnding"),
                "reported_currency": item.get("reportedCurrency"),
                "revenue": _to_float(item.get("totalRevenue")),
                "gross_profit": _to_float(item.get("grossProfit")),
                "operating_income": _to_float(item.get("operatingIncome")),
                "net_income": _to_float(item.get("netIncome")),
                "eps": _to_float(item.get("reportedEPS")),
            }
        )
    with _income_cache_lock:
        _income_cache[symbol] = {"ts": now, "data": result}
    return result
