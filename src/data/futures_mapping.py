# -*- coding: utf-8 -*-
"""Domestic futures symbol normalization helpers."""

import re
from typing import List


FUTURES_ALIASES = {
    "螺纹钢": "RB",
    "螺纹": "RB",
    "铁矿石": "I",
    "铁矿": "I",
    "沪金": "AU",
    "黄金": "AU",
    "沪银": "AG",
    "白银": "AG",
    "沪铜": "CU",
    "铜": "CU",
    "焦煤": "JM",
    "焦炭": "J",
    "动力煤": "ZC",
    "玻璃": "FG",
    "纯碱": "SA",
    "甲醇": "MA",
    "豆粕": "M",
    "菜粕": "RM",
    "豆油": "Y",
    "棕榈油": "P",
    "玉米": "C",
    "淀粉": "CS",
    "白糖": "SR",
    "棉花": "CF",
    "PTA": "TA",
    "pta": "TA",
    "PVC": "V",
    "pvc": "V",
    "塑料": "L",
    "乙二醇": "EG",
    "原油": "SC",
    "燃油": "FU",
    "低硫燃油": "LU",
    "橡胶": "RU",
    "沪铝": "AL",
    "铝": "AL",
    "沪锌": "ZN",
    "锌": "ZN",
    "沪镍": "NI",
    "镍": "NI",
    "沪锡": "SN",
    "锡": "SN",
    "不锈钢": "SS",
}

FUTURES_NAMES = {
    "RB": "螺纹钢",
    "I": "铁矿石",
    "AU": "沪金",
    "AG": "沪银",
    "CU": "沪铜",
    "JM": "焦煤",
    "J": "焦炭",
    "ZC": "动力煤",
    "FG": "玻璃",
    "SA": "纯碱",
    "MA": "甲醇",
    "M": "豆粕",
    "RM": "菜粕",
    "Y": "豆油",
    "P": "棕榈油",
    "C": "玉米",
    "CS": "淀粉",
    "SR": "白糖",
    "CF": "棉花",
    "TA": "PTA",
    "V": "PVC",
    "L": "塑料",
    "EG": "乙二醇",
    "SC": "原油",
    "FU": "燃油",
    "LU": "低硫燃油",
    "RU": "橡胶",
    "AL": "沪铝",
    "ZN": "沪锌",
    "NI": "沪镍",
    "SN": "沪锡",
    "SS": "不锈钢",
}

_SPECIFIC_CONTRACT_RE = re.compile(r"^([A-Z]+)(\d{3,4})$")
_CHINESE_CONTRACT_RE = re.compile(r"^(.+?)(\d{3,4})$")


def normalize_futures_symbol(symbol: str) -> str:
    """Normalize user input to a domestic futures variety or contract symbol."""
    raw = (symbol or "").strip()
    if not raw:
        return ""

    compact = re.sub(r"\s+", "", raw)
    chinese_contract = _CHINESE_CONTRACT_RE.match(compact)
    if chinese_contract:
        alias = FUTURES_ALIASES.get(chinese_contract.group(1))
        if alias:
            return f"{alias}{chinese_contract.group(2)}"

    alias = FUTURES_ALIASES.get(raw)
    if alias:
        return alias

    upper = compact.upper()
    if _SPECIFIC_CONTRACT_RE.match(upper):
        return upper
    if upper.endswith("0") and len(upper) > 1:
        upper = upper[:-1]
    return upper


def is_specific_futures_contract(symbol: str) -> bool:
    """Return whether symbol is a concrete futures contract such as JM2609."""
    return bool(_SPECIFIC_CONTRACT_RE.match(normalize_futures_symbol(symbol)))


def get_futures_variety_symbol(symbol: str) -> str:
    """Return the variety symbol for a main-continuous or concrete contract."""
    normalized = normalize_futures_symbol(symbol)
    match = _SPECIFIC_CONTRACT_RE.match(normalized)
    if match:
        return match.group(1)
    return normalized


def to_main_contract_symbol(symbol: str) -> str:
    """Convert a futures symbol to AkShare/Sina symbol.

    Variety symbols use the main-continuous suffix ``0``. Concrete contracts
    such as ``JM2609`` are preserved.
    """
    normalized = normalize_futures_symbol(symbol)
    if not normalized:
        return ""
    if is_specific_futures_contract(normalized):
        return normalized
    return f"{normalized}0"


def parse_futures_list(value: str) -> List[str]:
    """Parse comma-separated futures list into normalized unique variety symbols."""
    seen = set()
    result: List[str] = []
    for item in (value or "").split(","):
        normalized = normalize_futures_symbol(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def get_futures_name(symbol: str) -> str:
    """Return display name for a futures variety or concrete contract."""
    normalized = normalize_futures_symbol(symbol)
    match = _SPECIFIC_CONTRACT_RE.match(normalized)
    if match:
        variety = match.group(1)
        month = match.group(2)
        return f"{FUTURES_NAMES.get(variety, variety)}{month}"
    return FUTURES_NAMES.get(normalized, normalized)
