"""Shared helpers for loading locally normalized US stock history."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Tuple, Union

import pandas as pd

from data_provider.base import DataFetcherManager
from data_provider.us_index_mapping import is_us_stock_code


DEFAULT_US_STOCK_PARQUET_DIR = "/root/us_test/data/normalized/us"
LOCAL_US_PARQUET_SOURCE = "local_us_parquet"
DateLike = Union[str, date, datetime]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocalUsHistoryLoadResult:
    """Normalized result for local US parquet reads."""

    stock_code: str
    path: Path
    status: str
    dataframe: Optional[pd.DataFrame] = None
    error: Optional[str] = None

    @property
    def source_name(self) -> str:
        return LOCAL_US_PARQUET_SOURCE


def get_us_stock_parquet_dir() -> Path:
    """Return the configured US parquet root.

    `LOCAL_US_PARQUET_DIR` is the primary knob for local-first backtests.
    `US_STOCK_PARQUET_DIR` remains as a compatibility fallback.
    """

    for env_key in ("LOCAL_US_PARQUET_DIR", "US_STOCK_PARQUET_DIR"):
        configured = os.getenv(env_key, "").strip()
        if configured:
            return Path(configured)
    return Path(DEFAULT_US_STOCK_PARQUET_DIR)


def get_local_us_history_path(stock_code: str) -> Path:
    """Return the parquet path for a US ticker."""

    return get_us_stock_parquet_dir() / f"{str(stock_code or '').upper()}.parquet"


def load_local_us_daily_history(
    stock_code: str,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: Optional[int] = None,
) -> LocalUsHistoryLoadResult:
    """Load normalized local US daily history for a ticker when available."""

    normalized_code = str(stock_code or "").strip().upper()
    path = get_local_us_history_path(normalized_code)
    if not normalized_code or not is_us_stock_code(normalized_code):
        return LocalUsHistoryLoadResult(
            stock_code=normalized_code,
            path=path,
            status="not_applicable",
        )

    if not path.exists():
        return LocalUsHistoryLoadResult(
            stock_code=normalized_code,
            path=path,
            status="missing",
        )

    try:
        raw_df = pd.read_parquet(path)
    except Exception as exc:
        return LocalUsHistoryLoadResult(
            stock_code=normalized_code,
            path=path,
            status="failed",
            error=str(exc),
        )

    normalized = _normalize_local_us_history_frame(raw_df)
    if normalized is None or normalized.empty:
        return LocalUsHistoryLoadResult(
            stock_code=normalized_code,
            path=path,
            status="invalid",
            error="missing required columns or no rows after normalization",
        )

    filtered = normalized.copy()
    if start_date:
        filtered = filtered[filtered["date"] >= pd.to_datetime(start_date)]
    if end_date:
        filtered = filtered[filtered["date"] <= pd.to_datetime(end_date)]
    if days:
        filtered = filtered.tail(max(1, int(days)))

    if filtered.empty:
        return LocalUsHistoryLoadResult(
            stock_code=normalized_code,
            path=path,
            status="invalid",
            error="no rows matched the requested date window",
        )

    return LocalUsHistoryLoadResult(
        stock_code=normalized_code,
        path=path,
        status="hit",
        dataframe=filtered.reset_index(drop=True),
    )


def fetch_daily_history_with_local_us_fallback(
    stock_code: str,
    *,
    start_date: Optional[DateLike] = None,
    end_date: Optional[DateLike] = None,
    days: Optional[int] = None,
    manager: Optional[DataFetcherManager] = None,
    log_context: str = "[daily history]",
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetch daily history with a local-US-parquet fast path when applicable."""

    normalized_code = str(stock_code or "").strip().upper()
    start_date_str = _normalize_date_arg(start_date)
    end_date_str = _normalize_date_arg(end_date)

    local_history = load_local_us_daily_history(
        normalized_code,
        start_date=start_date_str,
        end_date=end_date_str,
        days=days,
    )
    if local_history.status == "hit" and local_history.dataframe is not None:
        logger.info("%s local parquet hit for %s: %s", log_context, normalized_code, local_history.path)
        return local_history.dataframe, local_history.source_name

    if local_history.status == "missing":
        logger.info("%s local parquet missing for %s: %s", log_context, normalized_code, local_history.path)
    elif local_history.status in {"invalid", "failed"}:
        logger.warning(
            "%s local parquet load failed for %s: %s (%s)",
            log_context,
            normalized_code,
            local_history.path,
            local_history.error or local_history.status,
        )

    if normalized_code and is_us_stock_code(normalized_code):
        logger.info("%s API fallback for %s", log_context, normalized_code)

    fetcher = manager or DataFetcherManager()
    return fetcher.get_daily_data(
        stock_code=normalized_code,
        start_date=start_date_str,
        end_date=end_date_str,
        days=days,
    )


def _normalize_local_us_history_frame(raw_df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if raw_df is None or raw_df.empty:
        return None

    df = raw_df.copy()
    date_column = None
    for candidate in ("trade_date", "date"):
        if candidate in df.columns:
            date_column = candidate
            break
    if date_column is None:
        return None

    required_columns = {"open", "high", "low", "close"}
    if not required_columns.issubset(set(df.columns)):
        return None

    df = df.rename(columns={date_column: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "open", "high", "low", "close"]).copy()
    if df.empty:
        return None

    df = df.sort_values("date").reset_index(drop=True)
    if "amount" not in df.columns:
        df["amount"] = None
    if "pct_chg" not in df.columns:
        df["pct_chg"] = None
    if "volume" not in df.columns:
        df["volume"] = None

    for column in ("open", "high", "low", "close", "volume", "amount", "pct_chg"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    return df


def _normalize_date_arg(value: Optional[DateLike]) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()
