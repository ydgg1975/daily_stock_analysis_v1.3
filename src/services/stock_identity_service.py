# -*- coding: utf-8 -*-
"""
===================================
Stock Identity Service
===================================

单一真源：给任意输入的股票代码，返回规范化的 (canonical_code, canonical_name)。
所有写入 AnalysisHistory / UserWatchlist 的路径都必须通过本服务，确保 (code, name) 一致。
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from src.data.stock_mapping import STOCK_NAME_MAP
from src.services.stock_code_utils import normalize_code

logger = logging.getLogger(__name__)


class StockIdentityNotFound(Exception):
    """Raised when a stock code cannot be resolved to a canonical (code, name) pair."""

    def __init__(self, raw: str):
        super().__init__(f"无法识别的股票代码: {raw}")
        self.raw = raw


def _lookup_name_from_akshare(code: str) -> Optional[str]:
    """Opt-in fallback for codes not in STOCK_NAME_MAP. Returns None on failure."""
    try:
        import akshare as ak  # type: ignore
    except ImportError:
        return None
    try:
        # A-shares: fetch realtime quote board (cached inside akshare adapters)
        # Only attempt fallback for 6-digit A-share codes to keep cost bounded.
        if len(code) == 6 and code.isdigit():
            df = ak.stock_zh_a_spot_em()
            matched = df[df["代码"] == code]
            if len(matched) > 0:
                name = str(matched.iloc[0]["名称"]).strip()
                if name:
                    return name
    except Exception as exc:  # pragma: no cover - network / provider errors
        logger.warning("akshare lookup failed for %s: %s", code, exc)
    return None


def normalize_stock_identity(raw_code: str) -> Tuple[str, str]:
    """
    Normalize a stock code to a canonical (code, name) pair.

    Resolution order:
      1. Clean whitespace + run shared `normalize_code`.
      2. Look up in `STOCK_NAME_MAP` (authoritative local table).
      3. Fallback to akshare (A-share only, opt-in).

    Raises:
        StockIdentityNotFound: when no canonical name can be resolved.
    """
    if not raw_code or not raw_code.strip():
        raise StockIdentityNotFound(raw_code or "")

    cleaned = raw_code.strip()
    canonical = normalize_code(cleaned) or cleaned

    name = STOCK_NAME_MAP.get(canonical)
    if name:
        return canonical, name

    fallback = _lookup_name_from_akshare(canonical)
    if fallback:
        return canonical, fallback

    raise StockIdentityNotFound(raw_code)
