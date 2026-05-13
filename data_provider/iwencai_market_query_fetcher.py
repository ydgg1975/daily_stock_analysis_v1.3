# -*- coding: utf-8 -*-
"""
IwencaiMarketQueryFetcher - optional realtime quote via Tonghuashun iWencai OpenAPI.

Uses the installed skill CLI (skills/hithink-market-query/scripts/cli.py) with
IWENCAI_API_KEY. Does not support daily OHLCV; daily path raises DataFetchError immediately.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .base import BaseFetcher, DataFetchError, normalize_stock_code
from .realtime_types import RealtimeSource, UnifiedRealtimeQuote, safe_float, safe_int
from .us_index_mapping import is_us_stock_code

logger = logging.getLogger(__name__)

_DATE_SUFFIX_RE = re.compile(r"\[(\d{8})\]")


def _iwencai_is_hk_code(stock_code: str) -> bool:
    """HK stock detection (aligned with akshare_fetcher._is_hk_code, no akshare import)."""
    code = stock_code.lower()
    if code.startswith("hk"):
        numeric_part = code[2:]
        return numeric_part.isdigit() and 1 <= len(numeric_part) <= 5
    return code.isdigit() and len(code) == 5


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_cli_path() -> Path:
    return _repo_root() / "skills" / "hithink-market-query" / "scripts" / "cli.py"


def _stringify_iwencai_code(ts: Any) -> str:
    """Normalize API stock code cell for comparison (handles int/float from JSON)."""
    if ts is None:
        return ""
    if isinstance(ts, bool):
        return str(ts)
    if isinstance(ts, int):
        return str(ts)
    if isinstance(ts, float):
        if ts != ts:  # NaN
            return ""
        r = round(ts)
        if abs(ts - r) < 1e-9:
            return str(int(r))
        return str(ts).strip()
    return str(ts).strip()


def _code_from_iwencai_ts(ts_code: str) -> str:
    s = (ts_code or "").strip().upper()
    if "." in s:
        base, suf = s.rsplit(".", 1)
        if suf in ("SH", "SZ", "BJ") and base.isdigit():
            return base
    return normalize_stock_code(s)


def _latest_date_suffix(row: Dict[str, Any]) -> Optional[str]:
    """Pick the latest YYYYMMDD from column names like 收盘价[20260511]."""
    dates: List[str] = []
    for k in row.keys():
        if not isinstance(k, str):
            continue
        m = _DATE_SUFFIX_RE.search(k)
        if m:
            dates.append(m.group(1))
    if not dates:
        return None
    return max(dates)


def _get_by_suffix(row: Dict[str, Any], prefix: str, date_suffix: Optional[str]) -> Any:
    if date_suffix:
        key = f"{prefix}[{date_suffix}]"
        if key in row:
            return row[key]
    for k, v in row.items():
        if isinstance(k, str) and k.startswith(prefix) and "[" in k:
            return v
    return None


def parse_iwencai_cli_payload(
    payload: Dict[str, Any],
    stock_code: str,
) -> Optional[UnifiedRealtimeQuote]:
    """
    Map hithink-market-query CLI stdout JSON to UnifiedRealtimeQuote.

    Expects the wrapped shape from cli.py main(): success, datas, ...
    """
    if not payload.get("success") or "datas" not in payload:
        return None
    datas = payload.get("datas") or []
    if not isinstance(datas, list) or not datas:
        return None

    want = normalize_stock_code(stock_code)
    row: Optional[Dict[str, Any]] = None
    for item in datas:
        if not isinstance(item, dict):
            continue
        ts = item.get("股票代码") or item.get("code")
        if ts is not None and _code_from_iwencai_ts(_stringify_iwencai_code(ts)) == want:
            row = item
            break
    if row is None and datas and isinstance(datas[0], dict):
        row = datas[0]

    if row is None:
        return None

    date_suf = _latest_date_suffix(row)

    name = str(row.get("股票简称") or row.get("name") or "").strip()
    price = safe_float(row.get("最新价"))
    if price is None or price <= 0:
        close_key = None
        if date_suf:
            close_key = f"收盘价[{date_suf}]"
        if close_key and close_key in row:
            price = safe_float(row.get(close_key))
    if price is None or price <= 0:
        return None

    change_pct = safe_float(row.get("最新涨跌幅"))
    if change_pct is None and date_suf:
        change_pct = safe_float(_get_by_suffix(row, "涨跌幅", date_suf))

    change_amount = safe_float(_get_by_suffix(row, "涨跌_前复权", date_suf))
    if change_amount is None:
        change_amount = safe_float(row.get("涨跌额"))

    open_p = safe_float(_get_by_suffix(row, "开盘价_前复权", date_suf))
    high = safe_float(_get_by_suffix(row, "最高价_前复权", date_suf))
    low = safe_float(_get_by_suffix(row, "最低价_前复权", date_suf))

    vol = safe_int(_get_by_suffix(row, "成交量", date_suf))
    amt = safe_float(_get_by_suffix(row, "成交额", date_suf))
    turnover = safe_float(_get_by_suffix(row, "换手率", date_suf))
    amplitude = safe_float(_get_by_suffix(row, "振幅", date_suf))

    pre_close: Optional[float] = None
    if price is not None and change_amount is not None:
        pre_close = price - change_amount

    return UnifiedRealtimeQuote(
        code=want,
        name=name,
        source=RealtimeSource.IWENCAI_MARKET_QUERY,
        price=price,
        change_pct=change_pct,
        change_amount=change_amount,
        volume=vol,
        amount=amt,
        volume_ratio=None,
        turnover_rate=turnover,
        amplitude=amplitude,
        open_price=open_p,
        high=high,
        low=low,
        pre_close=pre_close,
    )


class IwencaiMarketQueryFetcher(BaseFetcher):
    """
    Realtime quotes via iWencai query2data (hithink-market-query skill CLI).

    Daily data is intentionally unsupported; raises DataFetchError so DataFetcherManager
    falls through to other fetchers quickly.
    """

    name = "IwencaiMarketQueryFetcher"
    priority = int(os.getenv("IWENCAI_MARKET_QUERY_PRIORITY", "8"))

    def __init__(self) -> None:
        from src.config import get_config

        cfg = get_config()
        self._cli_path = Path(cfg.iwencai_cli_path) if cfg.iwencai_cli_path else _default_cli_path()
        self._skill_cwd = self._cli_path.parent.parent
        self._query_template = cfg.iwencai_market_query_template
        self._timeout = max(5, int(cfg.iwencai_subprocess_timeout_sec))

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        raise DataFetchError(
            "IwencaiMarketQueryFetcher does not support daily K-line; use other fetchers in the chain."
        )

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        return df

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        stock_code = normalize_stock_code(stock_code)
        if is_us_stock_code(stock_code) or _iwencai_is_hk_code(stock_code):
            logger.debug("[Iwencai] skip non-A-share code %s", stock_code)
            return None

        from src.config import get_config

        cfg = get_config()
        if not cfg.iwencai_market_query_enabled:
            return None
        if not (os.environ.get("IWENCAI_API_KEY") or "").strip():
            logger.debug("[Iwencai] IWENCAI_API_KEY not set, skip")
            return None
        if not self._cli_path.is_file():
            logger.warning("[Iwencai] CLI not found: %s", self._cli_path)
            return None

        query = self._query_template.format(code=stock_code)
        cmd = [
            sys.executable,
            str(self._cli_path),
            "--query",
            query,
            "--limit",
            "8",
            "--timeout",
            str(self._timeout),
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self._skill_cwd),
                capture_output=True,
                text=True,
                timeout=self._timeout + 5,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired:
            logger.warning("[Iwencai] subprocess timeout for %s", stock_code)
            return None
        except Exception as e:
            logger.warning("[Iwencai] subprocess failed for %s: %s", stock_code, e)
            return None

        raw_out = (proc.stdout or "").strip()
        if not raw_out:
            err_tail = (proc.stderr or "")[-500:]
            logger.warning(
                "[Iwencai] empty stdout for %s exit=%s stderr_tail=%r",
                stock_code,
                proc.returncode,
                err_tail,
            )
            return None

        try:
            payload = json.loads(raw_out)
        except json.JSONDecodeError:
            logger.warning("[Iwencai] invalid JSON stdout for %s (first 200 chars)", stock_code)
            return None

        if proc.returncode != 0:
            logger.warning(
                "[Iwencai] CLI exit %s for %s keys=%s",
                proc.returncode,
                stock_code,
                list(payload.keys()) if isinstance(payload, dict) else type(payload),
            )

        quote = parse_iwencai_cli_payload(payload, stock_code)
        if quote and quote.has_basic_data():
            logger.info("[Iwencai] realtime quote OK for %s price=%s", stock_code, quote.price)
            return quote

        return None


def iwencai_fetcher_should_register() -> bool:
    """Whether to append IwencaiMarketQueryFetcher in DataFetcherManager."""
    from src.config import get_config

    cfg = get_config()
    if not cfg.iwencai_market_query_enabled:
        return False
    if not (os.environ.get("IWENCAI_API_KEY") or "").strip():
        return False
    path = Path(cfg.iwencai_cli_path) if cfg.iwencai_cli_path else _default_cli_path()
    return path.is_file()
