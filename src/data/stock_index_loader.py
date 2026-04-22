# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import RLock
from typing import Dict, Iterable, Set

from src.data.stock_mapping import is_meaningful_stock_name

logger = logging.getLogger(__name__)

_STOCK_INDEX_FILENAME = "stocks.index.json"
_STOCK_INDEX_CACHE: Dict[str, str] | None = None
_STOCK_CODE_INDEX_CACHE: Dict[str, str] | None = None
_STOCK_INDEX_CACHE_LOCK = RLock()


def get_stock_index_candidate_paths() -> tuple[Path, ...]:
    """Return the supported locations for the generated stock index."""
    repo_root = Path(__file__).resolve().parents[2]
    return (
        repo_root / "apps" / "dsa-web" / "public" / _STOCK_INDEX_FILENAME,
        repo_root / "static" / _STOCK_INDEX_FILENAME,
    )


def _add_lookup_key(keys: set[str], value: str) -> None:
    candidate = str(value or "").strip()
    if not candidate:
        return
    keys.add(candidate)
    keys.add(candidate.upper())


def _build_lookup_keys(canonical_code: str, display_code: str) -> Iterable[str]:
    keys: set[str] = set()
    _add_lookup_key(keys, canonical_code)
    _add_lookup_key(keys, display_code)

    canonical_upper = str(canonical_code or "").strip().upper()
    display_upper = str(display_code or "").strip().upper()

    if "." in canonical_upper:
        base, suffix = canonical_upper.rsplit(".", 1)
        if suffix in {"SH", "SZ", "SS", "BJ"} and base.isdigit():
            _add_lookup_key(keys, base)
        elif suffix == "HK" and base.isdigit() and 1 <= len(base) <= 5:
            digits = base.zfill(5)
            _add_lookup_key(keys, digits)
            _add_lookup_key(keys, f"HK{digits}")

    for candidate in (canonical_upper, display_upper):
        if candidate.startswith("HK"):
            digits = candidate[2:]
            if digits.isdigit() and 1 <= len(digits) <= 5:
                digits = digits.zfill(5)
                _add_lookup_key(keys, digits)
                _add_lookup_key(keys, f"HK{digits}")

    return keys


def _load_stock_index_file(index_path: Path) -> Dict[str, str]:
    with index_path.open("r", encoding="utf-8") as fh:
        raw_items = json.load(fh)

    if not isinstance(raw_items, list):
        raise ValueError(
            f"Unexpected {_STOCK_INDEX_FILENAME} payload type: {type(raw_items).__name__}"
        )

    stock_name_map: Dict[str, str] = {}
    for item in raw_items:
        if not isinstance(item, list) or len(item) < 3:
            continue

        canonical_code, display_code, name_zh = item[0], item[1], item[2]
        if not is_meaningful_stock_name(name_zh, str(display_code or canonical_code or "")):
            continue

        for key in _build_lookup_keys(str(canonical_code or ""), str(display_code or "")):
            stock_name_map[key] = str(name_zh).strip()

    return stock_name_map


def _add_name_code_candidate(candidates: dict[str, Set[str]], name: str, code: str) -> None:
    normalized_name = str(name or "").strip()
    normalized_code = str(code or "").strip().upper()
    if not normalized_name or not normalized_code:
        return
    candidates.setdefault(normalized_name, set()).add(normalized_code)


def _build_name_to_code_map(raw_items: list) -> Dict[str, str]:
    candidates: dict[str, Set[str]] = {}

    for item in raw_items:
        if not isinstance(item, list) or len(item) < 3:
            continue

        canonical_code, display_code, name_zh = item[0], item[1], item[2]
        display = str(display_code or canonical_code or "").strip()
        code = display.split(".", 1)[0].upper()
        if not code:
            continue

        if is_meaningful_stock_name(name_zh, code):
            _add_name_code_candidate(candidates, str(name_zh).strip(), code)

        aliases = item[5] if len(item) > 5 else []
        if isinstance(aliases, list):
            for alias in aliases:
                if is_meaningful_stock_name(alias, code):
                    _add_name_code_candidate(candidates, str(alias).strip(), code)

    return {
        name: next(iter(codes))
        for name, codes in candidates.items()
        if len(codes) == 1
    }


def _load_stock_code_index_file(index_path: Path) -> Dict[str, str]:
    with index_path.open("r", encoding="utf-8") as fh:
        raw_items = json.load(fh)

    if not isinstance(raw_items, list):
        raise ValueError(
            f"Unexpected {_STOCK_INDEX_FILENAME} payload type: {type(raw_items).__name__}"
        )

    return _build_name_to_code_map(raw_items)


def get_stock_name_index_map() -> Dict[str, str]:
    """Lazily load and cache the generated stock-name index."""
    global _STOCK_INDEX_CACHE

    if _STOCK_INDEX_CACHE is not None:
        return _STOCK_INDEX_CACHE

    with _STOCK_INDEX_CACHE_LOCK:
        if _STOCK_INDEX_CACHE is not None:
            return _STOCK_INDEX_CACHE

        for candidate_path in get_stock_index_candidate_paths():
            if not candidate_path.is_file():
                continue

            try:
                _STOCK_INDEX_CACHE = _load_stock_index_file(candidate_path)
                logger.debug(
                    "[股票名称] 已加载前端股票索引映射: %s (%d 条)",
                    candidate_path,
                    len(_STOCK_INDEX_CACHE),
                )
                return _STOCK_INDEX_CACHE
            except (OSError, TypeError, ValueError) as exc:
                logger.debug("[股票名称] 读取股票索引失败 %s: %s", candidate_path, exc)

        _STOCK_INDEX_CACHE = {}
        return _STOCK_INDEX_CACHE


def get_stock_code_index_map() -> Dict[str, str]:
    """Lazily load and cache the generated stock-name -> code index."""
    global _STOCK_CODE_INDEX_CACHE

    if _STOCK_CODE_INDEX_CACHE is not None:
        return _STOCK_CODE_INDEX_CACHE

    with _STOCK_INDEX_CACHE_LOCK:
        if _STOCK_CODE_INDEX_CACHE is not None:
            return _STOCK_CODE_INDEX_CACHE

        for candidate_path in get_stock_index_candidate_paths():
            if not candidate_path.is_file():
                continue

            try:
                _STOCK_CODE_INDEX_CACHE = _load_stock_code_index_file(candidate_path)
                logger.debug(
                    "[股票名称] 已加载股票名称反向索引: %s (%d 条)",
                    candidate_path,
                    len(_STOCK_CODE_INDEX_CACHE),
                )
                return _STOCK_CODE_INDEX_CACHE
            except (OSError, TypeError, ValueError) as exc:
                logger.debug("[股票名称] 读取股票反向索引失败 %s: %s", candidate_path, exc)

        _STOCK_CODE_INDEX_CACHE = {}
        return _STOCK_CODE_INDEX_CACHE


def get_index_stock_name(stock_code: str) -> str | None:
    """Resolve a stock name from the generated frontend stock index."""
    code = str(stock_code or "").strip()
    if not code:
        return None

    stock_name_map = get_stock_name_index_map()
    for key in _build_lookup_keys(code, code):
        name = stock_name_map.get(key)
        if is_meaningful_stock_name(name, code):
            return name

    return None


def _clear_stock_index_cache_for_tests() -> None:
    global _STOCK_INDEX_CACHE, _STOCK_CODE_INDEX_CACHE
    with _STOCK_INDEX_CACHE_LOCK:
        _STOCK_INDEX_CACHE = None
        _STOCK_CODE_INDEX_CACHE = None
