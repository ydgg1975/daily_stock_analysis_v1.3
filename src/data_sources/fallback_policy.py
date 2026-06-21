"""Fallback policy helpers shared by market and news routers."""

from __future__ import annotations

from typing import Iterable, List


def normalize_priority(raw_priority: str, defaults: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in str(raw_priority or "").split(","):
        name = item.strip()
        if not name:
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            result.append(name)
    for item in defaults:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
