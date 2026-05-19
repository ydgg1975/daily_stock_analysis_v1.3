# -*- coding: utf-8 -*-
"""한국 주식 코드 유틸리티."""

import re
from typing import Optional


_KR_PREFIX_RE = re.compile(r"^(KR|KS|KQ)(\d{6})$")
_KR_SUFFIX_RE = re.compile(r"^(\d{6})\.(KS|KQ)$")


def parse_kr_stock_code(stock_code: str | None) -> Optional[tuple[str, str]]:
    """한국 주식 코드를 Yahoo Finance용 시장 접미사와 함께 파싱한다."""
    code = (stock_code or "").strip().upper()
    if not code:
        return None

    suffix_match = _KR_SUFFIX_RE.match(code)
    if suffix_match:
        return suffix_match.group(1), suffix_match.group(2)

    prefix_match = _KR_PREFIX_RE.match(code)
    if prefix_match:
        prefix, digits = prefix_match.groups()
        suffix = "KQ" if prefix == "KQ" else "KS"
        return digits, suffix

    return None


def is_kr_stock_code(stock_code: str | None) -> bool:
    """명시적인 한국 주식 코드 형식인지 확인한다."""
    return parse_kr_stock_code(stock_code) is not None


def normalize_kr_stock_code(stock_code: str | None) -> Optional[str]:
    """내부 저장/표시용 한국 주식 코드를 정규화한다."""
    parsed = parse_kr_stock_code(stock_code)
    if not parsed:
        return None
    digits, suffix = parsed
    return f"{digits}.{suffix}"


def get_kr_yf_symbol(stock_code: str | None) -> Optional[str]:
    """한국 주식 코드를 Yahoo Finance 심볼로 변환한다."""
    return normalize_kr_stock_code(stock_code)
