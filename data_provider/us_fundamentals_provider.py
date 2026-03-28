# -*- coding: utf-8 -*-
"""US stock fallback helpers for fundamentals, quotes, and historical prices."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from src.config import get_config

logger = logging.getLogger(__name__)

_FUNDAMENTALS_TTL_SECONDS = 60 * 30
_EARNINGS_TTL_SECONDS = 60 * 30
_QUOTE_TTL_SECONDS = 60 * 5
_HISTORY_TTL_SECONDS = 60 * 30
_request_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = Lock()

_FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"
_FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
_FMP_STABLE_BASE_URL = "https://financialmodelingprep.com/stable"


def _num(value: Any) -> Any:
    if value in (None, "", "N/A", "None"):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return int(num) if num.is_integer() else num


def _first_defined(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", "N/A", "None"):
            return value
    return None


def _safe_series_lookup(frame: pd.DataFrame, row_key: str, col_key: Any) -> Any:
    if frame is None or frame.empty:
        return None
    try:
        if row_key not in frame.index or col_key not in frame.columns:
            return None
        return _num(frame.loc[row_key, col_key])
    except Exception:
        return None


def _cache_get(key: str, ttl_seconds: int) -> Any:
    now = time.time()
    with _cache_lock:
        cached = _request_cache.get(key)
        if cached and now - cached["ts"] < ttl_seconds:
            return cached["data"]
    return None


def _cache_set(key: str, data: Any) -> Any:
    with _cache_lock:
        _request_cache[key] = {"ts": time.time(), "data": data}
    return data


def _first_key(*config_attrs: str) -> Optional[str]:
    config = get_config()
    for attr in config_attrs:
        value = getattr(config, attr, None)
        if isinstance(value, list):
            for item in value:
                token = str(item or "").strip()
                if token:
                    return token
        else:
            token = str(value or "").strip()
            if token:
                return token
    return None


def _request_json(url: str, *, params: Dict[str, Any], headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> Any:
    response = requests.get(url, params=params, headers=headers or {}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        if payload.get("error"):
            raise ValueError(str(payload.get("error")))
        if payload.get("Error Message"):
            raise ValueError(str(payload.get("Error Message")))
    return payload


def _epoch_to_iso(value: Any) -> Optional[str]:
    try:
        ts = int(float(value))
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _compute_amplitude(high: Any, low: Any, prev_close: Any) -> Optional[float]:
    high_v = _num(high)
    low_v = _num(low)
    prev_v = _num(prev_close)
    if not isinstance(high_v, (int, float)) or not isinstance(low_v, (int, float)):
        return None
    if not isinstance(prev_v, (int, float)) or prev_v <= 0:
        return None
    return round((float(high_v) - float(low_v)) / float(prev_v) * 100.0, 4)


def _normalize_growth(curr: Any, prev: Any) -> Optional[float]:
    curr_v = _num(curr)
    prev_v = _num(prev)
    if not isinstance(curr_v, (int, float)) or not isinstance(prev_v, (int, float)):
        return None
    if prev_v == 0:
        return None
    return round((float(curr_v) - float(prev_v)) / abs(float(prev_v)), 4)


def _sum_recent_quarters(rows: List[Dict[str, Any]], key: str, quarters: int = 4) -> Optional[float]:
    if not isinstance(rows, list):
        return None
    samples: List[float] = []
    for row in rows[:quarters]:
        if not isinstance(row, dict):
            return None
        value = _num(row.get(key))
        if not isinstance(value, (int, float)):
            return None
        samples.append(float(value))
    if len(samples) != quarters:
        return None
    return round(sum(samples), 4)


def _derive_ttm_growth(rows: List[Dict[str, Any]], key: str) -> Optional[float]:
    latest_ttm = _sum_recent_quarters(rows, key, quarters=4)
    previous_ttm = _sum_recent_quarters(rows[4:], key, quarters=4) if isinstance(rows, list) else None
    growth = _normalize_growth(latest_ttm, previous_ttm)
    if growth is not None:
        return growth
    if len(rows) >= 5:
        return _normalize_growth(rows[0].get(key), rows[4].get(key))
    if len(rows) >= 2:
        return _normalize_growth(rows[0].get(key), rows[1].get(key))
    return None


def _extract_indicator_value(row: Dict[str, Any], indicator: str) -> Any:
    if not isinstance(row, dict):
        return None
    lower_name = indicator.lower()
    candidates = (
        lower_name,
        indicator,
        indicator.upper(),
        f"{lower_name}_value",
        f"{indicator.upper()}",
    )
    for key in candidates:
        value = row.get(key)
        if value not in (None, "", "N/A", "None"):
            return _num(value)
    return None


def _latest_indicator_row(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    valid_rows = [row for row in rows if isinstance(row, dict) and _num(row.get("value")) is not None]
    if not valid_rows:
        return None
    return max(valid_rows, key=lambda row: str(row.get("date") or ""))


def get_yfinance_fundamentals(symbol: str) -> Dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {}

    cache_key = f"yf:fundamentals:{symbol}"
    cached = _cache_get(cache_key, _FUNDAMENTALS_TTL_SECONDS)
    if cached is not None:
        return cached

    import yfinance as yf

    ticker = yf.Ticker(symbol)
    info = ticker.info or {}

    payload = {
        "marketCap": _num(_first_defined(info.get("marketCap"), info.get("enterpriseValue"))),
        "trailingPE": _num(info.get("trailingPE")),
        "forwardPE": _num(info.get("forwardPE")),
        "priceToBook": _num(info.get("priceToBook")),
        "beta": _num(info.get("beta")),
        "fiftyTwoWeekHigh": _num(info.get("fiftyTwoWeekHigh")),
        "fiftyTwoWeekLow": _num(info.get("fiftyTwoWeekLow")),
        "sharesOutstanding": _num(info.get("sharesOutstanding")),
        "floatShares": _num(info.get("floatShares")),
        "totalRevenue": _num(info.get("totalRevenue")),
        "revenueGrowth": _num(info.get("revenueGrowth")),
        "netIncome": _num(_first_defined(info.get("netIncomeToCommon"), info.get("netIncome"))),
        "grossMargins": _num(info.get("grossMargins")),
        "operatingMargins": _num(info.get("operatingMargins")),
        "freeCashflow": _num(info.get("freeCashflow")),
        "operatingCashflow": _num(info.get("operatingCashflow")),
        "debtToEquity": _num(info.get("debtToEquity")),
        "currentRatio": _num(info.get("currentRatio")),
        "returnOnEquity": _num(info.get("returnOnEquity")),
        "returnOnAssets": _num(info.get("returnOnAssets")),
        "_meta": {
            "field_periods": {
                "marketCap": "latest",
                "trailingPE": "ttm",
                "forwardPE": "consensus",
                "priceToBook": "latest",
                "beta": "latest",
                "fiftyTwoWeekHigh": "rolling_52w",
                "fiftyTwoWeekLow": "rolling_52w",
                "sharesOutstanding": "latest",
                "floatShares": "latest",
                "totalRevenue": "provider_reported_total",
                "revenueGrowth": "provider_reported_growth",
                "netIncome": "provider_reported_total",
                "grossMargins": "ttm",
                "operatingMargins": "ttm",
                "freeCashflow": "provider_reported_total",
                "operatingCashflow": "provider_reported_total",
                "debtToEquity": "latest",
                "currentRatio": "latest",
                "returnOnEquity": "ttm",
                "returnOnAssets": "ttm",
            },
            "field_sources": {
                "marketCap": "yfinance",
                "trailingPE": "yfinance",
                "forwardPE": "yfinance",
                "priceToBook": "yfinance",
                "beta": "yfinance",
                "fiftyTwoWeekHigh": "yfinance",
                "fiftyTwoWeekLow": "yfinance",
                "sharesOutstanding": "yfinance",
                "floatShares": "yfinance",
                "totalRevenue": "yfinance",
                "revenueGrowth": "yfinance",
                "netIncome": "yfinance",
                "grossMargins": "yfinance",
                "operatingMargins": "yfinance",
                "freeCashflow": "yfinance",
                "operatingCashflow": "yfinance",
                "debtToEquity": "yfinance",
                "currentRatio": "yfinance",
                "returnOnEquity": "yfinance",
                "returnOnAssets": "yfinance",
            },
        },
    }
    return _cache_set(cache_key, payload)


def get_yfinance_quarterly_financials(symbol: str, max_quarters: int = 6) -> List[Dict[str, Any]]:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return []

    cache_key = f"yf:quarterly:{symbol}:{max_quarters}"
    cached = _cache_get(cache_key, _EARNINGS_TTL_SECONDS)
    if cached is not None:
        return cached

    import yfinance as yf

    ticker = yf.Ticker(symbol)
    income_df = ticker.quarterly_income_stmt
    cashflow_df = ticker.quarterly_cashflow

    if income_df is None or income_df.empty:
        return _cache_set(cache_key, [])

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
                "eps": _num(
                    _first_defined(
                        _safe_series_lookup(income_df, "Diluted EPS", col),
                        _safe_series_lookup(income_df, "Basic EPS", col),
                    )
                ),
                "operating_cashflow": _safe_series_lookup(cashflow_df, "Operating Cash Flow", col),
                "free_cash_flow": _safe_series_lookup(cashflow_df, "Free Cash Flow", col),
            }
        )

    return _cache_set(cache_key, rows)


def get_finnhub_quote(symbol: str) -> Dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    api_key = _first_key("finnhub_api_keys", "finnhub_api_key")
    if not symbol or not api_key:
        return {}

    cache_key = f"finnhub:quote:{symbol}"
    cached = _cache_get(cache_key, _QUOTE_TTL_SECONDS)
    if cached is not None:
        return cached

    data = _request_json(
        f"{_FINNHUB_BASE_URL}/quote",
        params={"symbol": symbol, "token": api_key},
    )
    prev_close = _num(data.get("pc"))
    payload = {
        "price": _num(data.get("c")),
        "pre_close": prev_close,
        "change_amount": _num(data.get("d")),
        "change_pct": _num(data.get("dp")),
        "high": _num(data.get("h")),
        "low": _num(data.get("l")),
        "open_price": _num(data.get("o")),
        "market_timestamp": _epoch_to_iso(data.get("t")),
        "amplitude": _compute_amplitude(data.get("h"), data.get("l"), prev_close),
        "source": "finnhub",
    }
    return _cache_set(cache_key, {k: v for k, v in payload.items() if v is not None})


def get_finnhub_metrics(symbol: str) -> Dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    api_key = _first_key("finnhub_api_keys", "finnhub_api_key")
    if not symbol or not api_key:
        return {}

    cache_key = f"finnhub:metrics:{symbol}"
    cached = _cache_get(cache_key, _FUNDAMENTALS_TTL_SECONDS)
    if cached is not None:
        return cached

    payload = _request_json(
        f"{_FINNHUB_BASE_URL}/stock/metric",
        params={"symbol": symbol, "metric": "all", "token": api_key},
    )
    metrics = payload.get("metric", {}) if isinstance(payload, dict) else {}
    if not isinstance(metrics, dict):
        metrics = {}

    normalized = {
        "beta": _num(metrics.get("beta")),
        "trailingPE": _num(_first_defined(metrics.get("peTTM"), metrics.get("peBasicExclExtraTTM"))),
        "priceToBook": _num(_first_defined(metrics.get("pbAnnual"), metrics.get("pbQuarterly"))),
        "fiftyTwoWeekHigh": _num(metrics.get("52WeekHigh")),
        "fiftyTwoWeekLow": _num(metrics.get("52WeekLow")),
        "currentRatio": _num(_first_defined(metrics.get("currentRatioAnnual"), metrics.get("currentRatioQuarterly"))),
        "grossMargins": _num(metrics.get("grossMarginTTM")),
        "operatingMargins": _num(metrics.get("operatingMarginTTM")),
        "returnOnEquity": _num(metrics.get("roeTTM")),
        "returnOnAssets": _num(metrics.get("roaTTM")),
        "debtToEquity": _num(_first_defined(metrics.get("totalDebtToEquityQuarterly"), metrics.get("totalDebtToEquityAnnual"))),
    }
    return _cache_set(cache_key, {k: v for k, v in normalized.items() if v is not None})


def _fmp_get(path: str, symbol: str, *, params: Optional[Dict[str, Any]] = None) -> Any:
    api_key = _first_key("fmp_api_keys", "fmp_api_key")
    if not api_key:
        return []
    final_params = {"apikey": api_key, **(params or {})}
    return _request_json(f"{_FMP_BASE_URL}/{path}/{symbol}", params=final_params)


def _fmp_stable_get(path: str, *, params: Optional[Dict[str, Any]] = None) -> Any:
    api_key = _first_key("fmp_api_keys", "fmp_api_key")
    if not api_key:
        return []
    final_params = {"apikey": api_key, **(params or {})}
    return _request_json(f"{_FMP_STABLE_BASE_URL}/{path}", params=final_params)


def get_fmp_quote(symbol: str) -> Dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if not symbol or not _first_key("fmp_api_keys", "fmp_api_key"):
        return {}

    cache_key = f"fmp:quote:{symbol}"
    cached = _cache_get(cache_key, _QUOTE_TTL_SECONDS)
    if cached is not None:
        return cached

    rows = _fmp_get("quote", symbol)
    row = rows[0] if isinstance(rows, list) and rows else {}
    if not isinstance(row, dict):
        row = {}

    prev_close = _num(row.get("previousClose"))
    price = _num(row.get("price"))
    volume = _num(row.get("volume"))
    amount = None
    if price is not None and volume is not None:
        amount = price * volume
    payload = {
        "price": price,
        "pre_close": prev_close,
        "change_amount": _num(row.get("change")),
        "change_pct": _num(_first_defined(row.get("changesPercentage"), row.get("changePercentage"))),
        "high": _num(row.get("dayHigh")),
        "low": _num(row.get("dayLow")),
        "open_price": _num(row.get("open")),
        "volume": volume,
        "amount": amount,
        "high_52w": _num(row.get("yearHigh")),
        "low_52w": _num(row.get("yearLow")),
        "market_timestamp": _epoch_to_iso(row.get("timestamp")),
        "amplitude": _compute_amplitude(row.get("dayHigh"), row.get("dayLow"), prev_close),
        "source": "fmp",
    }
    return _cache_set(cache_key, {k: v for k, v in payload.items() if v is not None})


def get_fmp_profile(symbol: str) -> Dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if not symbol or not _first_key("fmp_api_keys", "fmp_api_key"):
        return {}

    cache_key = f"fmp:profile:{symbol}"
    cached = _cache_get(cache_key, _FUNDAMENTALS_TTL_SECONDS)
    if cached is not None:
        return cached

    rows = _fmp_get("profile", symbol)
    row = rows[0] if isinstance(rows, list) and rows else {}
    if not isinstance(row, dict):
        row = {}

    payload = {
        "marketCap": _num(_first_defined(row.get("mktCap"), row.get("marketCap"))),
        "beta": _num(row.get("beta")),
        "sharesOutstanding": _num(row.get("sharesOutstanding")),
        "floatShares": _num(row.get("floatShares")),
        "companyName": row.get("companyName"),
        "industry": row.get("industry"),
        "sector": row.get("sector"),
    }
    return _cache_set(cache_key, {k: v for k, v in payload.items() if v not in (None, "")})


def get_fmp_ratios_ttm(symbol: str) -> Dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if not symbol or not _first_key("fmp_api_keys", "fmp_api_key"):
        return {}

    cache_key = f"fmp:ratios-ttm:{symbol}"
    cached = _cache_get(cache_key, _FUNDAMENTALS_TTL_SECONDS)
    if cached is not None:
        return cached

    rows = _fmp_get("ratios-ttm", symbol)
    row = rows[0] if isinstance(rows, list) and rows else {}
    if not isinstance(row, dict):
        row = {}

    payload = {
        "trailingPE": _num(_first_defined(row.get("peRatioTTM"), row.get("priceEarningsRatioTTM"))),
        "priceToBook": _num(_first_defined(row.get("priceToBookRatioTTM"), row.get("pbRatioTTM"))),
        "currentRatio": _num(row.get("currentRatioTTM")),
        "grossMargins": _num(_first_defined(row.get("grossProfitMarginTTM"), row.get("grossMarginTTM"))),
        "operatingMargins": _num(_first_defined(row.get("operatingProfitMarginTTM"), row.get("operatingMarginTTM"))),
        "debtToEquity": _num(_first_defined(row.get("debtEquityRatioTTM"), row.get("debtToEquityTTM"))),
        "returnOnEquity": _num(row.get("returnOnEquityTTM")),
        "returnOnAssets": _num(row.get("returnOnAssetsTTM")),
    }
    return _cache_set(cache_key, {k: v for k, v in payload.items() if v is not None})


def _merge_cashflow_by_date(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        fiscal_date = str(row.get("date") or row.get("fiscalDateEnding") or row.get("fiscal_date") or "").strip()
        if not fiscal_date:
            continue
        merged[fiscal_date] = {
            "operating_cashflow": _num(_first_defined(row.get("operatingCashFlow"), row.get("operating_cashflow"))),
            "free_cash_flow": _num(_first_defined(row.get("freeCashFlow"), row.get("free_cash_flow"))),
        }
    return merged


def get_fmp_quarterly_financials(symbol: str, max_quarters: int = 6) -> List[Dict[str, Any]]:
    symbol = (symbol or "").strip().upper()
    if not symbol or not _first_key("fmp_api_keys", "fmp_api_key"):
        return []

    cache_key = f"fmp:quarterly:{symbol}:{max_quarters}"
    cached = _cache_get(cache_key, _EARNINGS_TTL_SECONDS)
    if cached is not None:
        return cached

    income_rows = _fmp_get("income-statement", symbol, params={"period": "quarter", "limit": max_quarters})
    cashflow_rows = _fmp_get("cash-flow-statement", symbol, params={"period": "quarter", "limit": max_quarters})
    if not isinstance(income_rows, list):
        income_rows = []
    if not isinstance(cashflow_rows, list):
        cashflow_rows = []

    cashflow_by_date = _merge_cashflow_by_date(cashflow_rows)
    merged: List[Dict[str, Any]] = []
    for row in income_rows[:max_quarters]:
        if not isinstance(row, dict):
            continue
        fiscal_date = str(row.get("date") or row.get("fiscalDateEnding") or "")[:10]
        cashflow = cashflow_by_date.get(fiscal_date, {})
        merged.append(
            {
                "fiscal_date": fiscal_date,
                "revenue": _num(_first_defined(row.get("revenue"), row.get("totalRevenue"))),
                "gross_profit": _num(row.get("grossProfit")),
                "operating_income": _num(row.get("operatingIncome")),
                "net_income": _num(row.get("netIncome")),
                "eps": _num(_first_defined(row.get("eps"), row.get("reportedEPS"))),
                "operating_cashflow": cashflow.get("operating_cashflow"),
                "free_cash_flow": cashflow.get("free_cash_flow"),
            }
        )

    return _cache_set(cache_key, merged)


def get_fmp_fundamentals(symbol: str) -> Dict[str, Any]:
    symbol = (symbol or "").strip().upper()
    if not symbol or not _first_key("fmp_api_keys", "fmp_api_key"):
        return {}

    cache_key = f"fmp:fundamentals:{symbol}"
    cached = _cache_get(cache_key, _FUNDAMENTALS_TTL_SECONDS)
    if cached is not None:
        return cached

    quote = get_fmp_quote(symbol)
    profile = get_fmp_profile(symbol)
    ratios_ttm = get_fmp_ratios_ttm(symbol)
    quarterly = get_fmp_quarterly_financials(symbol, max_quarters=8)

    latest = quarterly[0] if quarterly else {}
    revenue_ttm = _sum_recent_quarters(quarterly, "revenue", quarters=4)
    net_income_ttm = _sum_recent_quarters(quarterly, "net_income", quarters=4)
    operating_cashflow_ttm = _sum_recent_quarters(quarterly, "operating_cashflow", quarters=4)
    free_cashflow_ttm = _sum_recent_quarters(quarterly, "free_cash_flow", quarters=4)
    revenue_growth = _derive_ttm_growth(quarterly, "revenue")
    net_income_growth = _derive_ttm_growth(quarterly, "net_income")
    cashflow_period = "ttm" if operating_cashflow_ttm is not None else ("latest_quarter" if latest.get("operating_cashflow") is not None else None)
    free_cashflow_period = "ttm" if free_cashflow_ttm is not None else ("latest_quarter" if latest.get("free_cash_flow") is not None else None)
    revenue_period = "ttm" if revenue_ttm is not None else ("latest_quarter" if latest.get("revenue") is not None else None)
    net_income_period = "ttm" if net_income_ttm is not None else ("latest_quarter" if latest.get("net_income") is not None else None)

    payload = {
        "marketCap": profile.get("marketCap"),
        "beta": profile.get("beta") or ratios_ttm.get("beta"),
        "sharesOutstanding": profile.get("sharesOutstanding"),
        "floatShares": profile.get("floatShares"),
        "trailingPE": ratios_ttm.get("trailingPE"),
        "priceToBook": ratios_ttm.get("priceToBook"),
        "fiftyTwoWeekHigh": quote.get("high_52w"),
        "fiftyTwoWeekLow": quote.get("low_52w"),
        "totalRevenue": revenue_ttm if revenue_ttm is not None else latest.get("revenue"),
        "netIncome": net_income_ttm if net_income_ttm is not None else latest.get("net_income"),
        "freeCashflow": free_cashflow_ttm if free_cashflow_ttm is not None else latest.get("free_cash_flow"),
        "operatingCashflow": operating_cashflow_ttm if operating_cashflow_ttm is not None else latest.get("operating_cashflow"),
        "revenueGrowth": revenue_growth,
        "netIncomeGrowth": net_income_growth,
        "grossMargins": ratios_ttm.get("grossMargins"),
        "operatingMargins": ratios_ttm.get("operatingMargins"),
        "debtToEquity": ratios_ttm.get("debtToEquity"),
        "currentRatio": ratios_ttm.get("currentRatio"),
        "returnOnEquity": ratios_ttm.get("returnOnEquity"),
        "returnOnAssets": ratios_ttm.get("returnOnAssets"),
        "_meta": {
            "field_periods": {
                "marketCap": "latest",
                "beta": "latest",
                "sharesOutstanding": "latest",
                "floatShares": "latest",
                "trailingPE": "ttm",
                "priceToBook": "ttm",
                "fiftyTwoWeekHigh": "rolling_52w",
                "fiftyTwoWeekLow": "rolling_52w",
                "totalRevenue": revenue_period,
                "netIncome": net_income_period,
                "freeCashflow": free_cashflow_period,
                "operatingCashflow": cashflow_period,
                "revenueGrowth": "ttm_yoy" if revenue_growth is not None else None,
                "netIncomeGrowth": "ttm_yoy" if net_income_growth is not None else None,
                "grossMargins": "ttm",
                "operatingMargins": "ttm",
                "debtToEquity": "latest",
                "currentRatio": "latest",
                "returnOnEquity": "ttm",
                "returnOnAssets": "ttm",
            },
            "field_sources": {
                "marketCap": "fmp_profile",
                "beta": "fmp_profile",
                "sharesOutstanding": "fmp_profile",
                "floatShares": "fmp_profile",
                "trailingPE": "fmp_ratios_ttm",
                "priceToBook": "fmp_ratios_ttm",
                "fiftyTwoWeekHigh": "fmp_quote",
                "fiftyTwoWeekLow": "fmp_quote",
                "totalRevenue": "fmp_quarterly" if revenue_ttm is not None else "fmp_latest_quarter",
                "netIncome": "fmp_quarterly" if net_income_ttm is not None else "fmp_latest_quarter",
                "freeCashflow": "fmp_quarterly" if free_cashflow_ttm is not None else "fmp_latest_quarter",
                "operatingCashflow": "fmp_quarterly" if operating_cashflow_ttm is not None else "fmp_latest_quarter",
                "revenueGrowth": "fmp_quarterly" if revenue_growth is not None else None,
                "netIncomeGrowth": "fmp_quarterly" if net_income_growth is not None else None,
                "grossMargins": "fmp_ratios_ttm",
                "operatingMargins": "fmp_ratios_ttm",
                "debtToEquity": "fmp_ratios_ttm",
                "currentRatio": "fmp_ratios_ttm",
                "returnOnEquity": "fmp_ratios_ttm",
                "returnOnAssets": "fmp_ratios_ttm",
            },
        },
    }
    return _cache_set(cache_key, {k: v for k, v in payload.items() if v is not None})


def get_fmp_historical_prices(symbol: str, days: int = 180) -> List[Dict[str, Any]]:
    symbol = (symbol or "").strip().upper()
    if not symbol or not _first_key("fmp_api_keys", "fmp_api_key"):
        return []

    cache_key = f"fmp:history:{symbol}:{days}"
    cached = _cache_get(cache_key, _HISTORY_TTL_SECONDS)
    if cached is not None:
        return cached

    payload = _fmp_get("historical-price-full", symbol, params={"timeseries": max(5, int(days))})
    rows = payload.get("historical", []) if isinstance(payload, dict) else []
    normalized: List[Dict[str, Any]] = []
    for row in reversed(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "date": row.get("date"),
                "open": _num(row.get("open")),
                "high": _num(row.get("high")),
                "low": _num(row.get("low")),
                "close": _num(row.get("close")),
                "volume": _num(row.get("volume")),
                "vwap": _num(_first_defined(row.get("vwap"), row.get("VWAP"))),
            }
        )
    return _cache_set(cache_key, normalized)


def get_fmp_technical_indicator(
    symbol: str,
    indicator: str,
    *,
    period_length: int,
    timeframe: str = "1day",
) -> List[Dict[str, Any]]:
    symbol = (symbol or "").strip().upper()
    indicator_name = (indicator or "").strip().lower()
    if not symbol or not indicator_name or not _first_key("fmp_api_keys", "fmp_api_key"):
        return []

    cache_key = f"fmp:technical:{indicator_name}:{symbol}:{period_length}:{timeframe}"
    cached = _cache_get(cache_key, _QUOTE_TTL_SECONDS)
    if cached is not None:
        return cached

    payload = _fmp_stable_get(
        f"technical-indicators/{indicator_name}",
        params={
            "symbol": symbol,
            "periodLength": int(period_length),
            "timeframe": timeframe,
        },
    )
    rows = payload if isinstance(payload, list) else payload.get("data", []) if isinstance(payload, dict) else []
    normalized: List[Dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "date": row.get("date"),
                "value": _extract_indicator_value(row, indicator_name),
                "close": _num(row.get("close")),
            }
        )
    return _cache_set(cache_key, normalized)


def get_fmp_technical_indicators(
    symbol: str,
    *,
    timeframe: str = "1day",
) -> Dict[str, Dict[str, Any]]:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {}

    cache_key = f"fmp:technical-summary:{symbol}:{timeframe}"
    cached = _cache_get(cache_key, _QUOTE_TTL_SECONDS)
    if cached is not None:
        return cached

    summary: Dict[str, Dict[str, Any]] = {}
    for period in (5, 10, 20, 60):
        rows = get_fmp_technical_indicator(
            symbol,
            "sma",
            period_length=period,
            timeframe=timeframe,
        )
        latest = _latest_indicator_row(rows)
        if latest is not None:
            summary[f"ma{period}"] = {
                "value": _num(latest.get("value")),
                "source": "fmp_technical_indicator",
                "status": "ok",
                "timeframe": timeframe,
            }

    rsi_rows = get_fmp_technical_indicator(
        symbol,
        "rsi",
        period_length=14,
        timeframe=timeframe,
    )
    latest_rsi = _latest_indicator_row(rsi_rows)
    if latest_rsi is not None:
        summary["rsi14"] = {
            "value": _num(latest_rsi.get("value")),
            "source": "fmp_technical_indicator",
            "status": "ok",
            "timeframe": timeframe,
        }

    return _cache_set(cache_key, summary)


__all__ = [
    "get_finnhub_metrics",
    "get_finnhub_quote",
    "get_fmp_fundamentals",
    "get_fmp_historical_prices",
    "get_fmp_technical_indicator",
    "get_fmp_technical_indicators",
    "get_fmp_profile",
    "get_fmp_quarterly_financials",
    "get_fmp_quote",
    "get_fmp_ratios_ttm",
    "get_yfinance_fundamentals",
    "get_yfinance_quarterly_financials",
]
