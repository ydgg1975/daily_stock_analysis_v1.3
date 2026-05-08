# -*- coding: utf-8 -*-
"""Build and cache domestic futures autocomplete index data."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Iterable, List, Optional

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 6 * 60 * 60
_CACHE: Dict[str, object] = {"items": None, "loaded_at": 0.0}


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_contract_code(value: object) -> str:
    return _clean_text(value).upper()


def _dedupe_aliases(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        text = _clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _contract_suffix(code: str) -> str:
    digits = ""
    for char in reversed(code):
        if not char.isdigit():
            break
        digits = char + digits
    return digits


def _build_item(
    *,
    code: str,
    name: str,
    aliases: List[str],
    exchange: str,
    popularity: int,
) -> Dict[str, object]:
    return {
        "canonical_code": code,
        "display_code": code,
        "name_zh": name or code,
        "aliases": aliases,
        "market": "FUTURES",
        "asset_type": "futures",
        "exchange": exchange,
        "active": True,
        "popularity": popularity,
    }


def build_futures_index(
    *,
    symbol_mark_loader: Callable[[], pd.DataFrame] = ak.futures_symbol_mark,
    realtime_loader: Callable[[str], pd.DataFrame] = ak.futures_zh_realtime,
    max_workers: int = 8,
) -> List[Dict[str, object]]:
    """Build futures autocomplete index from AkShare's current symbol tables."""
    mark_df = symbol_mark_loader()
    if mark_df is None or mark_df.empty:
        return []

    rows = mark_df.to_dict("records")
    items_by_code: Dict[str, Dict[str, object]] = {}

    def fetch_contracts(row: Dict[str, object]) -> List[Dict[str, object]]:
        variety_name = _clean_text(row.get("symbol"))
        exchange_name = _clean_text(row.get("exchange"))
        if not variety_name:
            return []
        try:
            contract_df = realtime_loader(variety_name)
        except Exception as exc:
            logger.debug("[FuturesIndex] realtime contracts skipped: symbol=%s error=%s", variety_name, exc)
            return []
        if contract_df is None or contract_df.empty:
            return []

        result: List[Dict[str, object]] = []
        for index, contract in enumerate(contract_df.to_dict("records")):
            code = _normalize_contract_code(contract.get("symbol"))
            if not code:
                continue
            name = _clean_text(contract.get("name")) or code
            exchange = _clean_text(contract.get("exchange")) or exchange_name
            suffix = _contract_suffix(code)
            aliases = _dedupe_aliases(
                [
                    variety_name,
                    name,
                    f"{variety_name}{suffix}" if suffix else "",
                ]
            )
            popularity = max(1, 1000 - index)
            result.append(
                _build_item(
                    code=code,
                    name=name,
                    aliases=aliases,
                    exchange=exchange,
                    popularity=popularity,
                )
            )
        return result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_contracts, row) for row in rows]
        for future in as_completed(futures):
            for item in future.result():
                code = str(item["canonical_code"])
                if code not in items_by_code:
                    items_by_code[code] = item

    return sorted(
        items_by_code.values(),
        key=lambda item: (-int(item.get("popularity") or 0), str(item.get("canonical_code") or "")),
    )


def get_futures_index_items(*, force_refresh: bool = False) -> List[Dict[str, object]]:
    """Return cached futures autocomplete items."""
    now = time.time()
    cached_items = _CACHE.get("items")
    loaded_at = float(_CACHE.get("loaded_at") or 0)
    if not force_refresh and isinstance(cached_items, list) and now - loaded_at < _CACHE_TTL_SECONDS:
        return cached_items

    items = build_futures_index()
    _CACHE["items"] = items
    _CACHE["loaded_at"] = now
    return items
