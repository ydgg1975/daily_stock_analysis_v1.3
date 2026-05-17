# -*- coding: utf-8 -*-
"""Rules engine: matches technical indicators against declarative rules."""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.schemas.rules import RuleResult


def _load_rules() -> List[dict]:
    rules_path = Path(__file__).parent / "rules.json"
    with open(rules_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_conditions() -> Dict[str, Callable[[Dict[str, Any]], bool]]:
    """Build condition lambdas keyed by condition_key from rules.json."""
    return {
        # Technical
        "ma_golden_cross": lambda d: (
            d.get("ma5") is not None and d.get("ma10") is not None
            and d.get("ma5_prev") is not None and d.get("ma10_prev") is not None
            and d["ma5_prev"] <= d["ma10_prev"] and d["ma5"] > d["ma10"]
        ),
        "ma_death_cross": lambda d: (
            d.get("ma5") is not None and d.get("ma10") is not None
            and d.get("ma5_prev") is not None and d.get("ma10_prev") is not None
            and d["ma5_prev"] >= d["ma10_prev"] and d["ma5"] < d["ma10"]
        ),
        "ma_bullish_alignment": lambda d: d.get("ma_alignment") == "bullish",
        "ma_bearish_alignment": lambda d: d.get("ma_alignment") == "bearish",
        "macd_golden_cross": lambda d: d.get("macd_cross") == "golden",
        "macd_death_cross": lambda d: d.get("macd_cross") == "death",
        "rsi_overbought": lambda d: d.get("rsi") is not None and d["rsi"] > 70,
        "rsi_oversold": lambda d: d.get("rsi") is not None and d["rsi"] < 30,
        # Trend
        "uptrend": lambda d: (
            d.get("close") is not None and d.get("ma20") is not None
            and d.get("ma20_prev") is not None
            and d["close"] > d["ma20"] and d["ma20"] > d["ma20_prev"]
        ),
        "downtrend": lambda d: (
            d.get("close") is not None and d.get("ma20") is not None
            and d.get("ma20_prev") is not None
            and d["close"] < d["ma20"] and d["ma20"] < d["ma20_prev"]
        ),
        "new_high_20d": lambda d: d.get("new_high_20d") is True,
        "new_low_20d": lambda d: d.get("new_low_20d") is True,
        "new_high_60d": lambda d: d.get("new_high_60d") is True,
        "new_low_60d": lambda d: d.get("new_low_60d") is True,
        "short_term_strong": lambda d: d.get("return_5d") is not None and d["return_5d"] > 5,
        # Capital
        "volume_surge_up": lambda d: (
            d.get("volume_ratio") is not None and d.get("close") is not None
            and d.get("ma5") is not None
            and d["volume_ratio"] > 2 and d["close"] > d["ma5"]
        ),
        "volume_shrink_down": lambda d: (
            d.get("volume_ratio") is not None and d.get("close") is not None
            and d.get("ma5") is not None
            and d["volume_ratio"] < 0.5 and d["close"] < d["ma5"]
        ),
        "break_boll_upper": lambda d: (
            d.get("close") is not None and d.get("boll_upper") is not None
            and d["close"] > d["boll_upper"]
        ),
        "break_boll_lower": lambda d: (
            d.get("close") is not None and d.get("boll_lower") is not None
            and d["close"] < d["boll_lower"]
        ),
        # Valuation (require external PE percentile data, deferred)
        "pe_percentile_low": lambda d: False,
        "pe_percentile_high": lambda d: False,
        "pe_percentile_moderate": lambda d: False,
    }


class RuleEngine:
    """Match technical indicators against declarative rules."""

    def __init__(self):
        self._rules_meta = _load_rules()
        self._conditions = _build_conditions()

    def evaluate(self, data: Dict[str, Any], valuation: Optional[Dict] = None) -> List[RuleResult]:
        """Match all rules against indicator data. Returns 22 RuleResult objects."""
        results = []
        for rule in self._rules_meta:
            cond_fn = self._conditions.get(rule["condition_key"])
            matched = False
            if cond_fn is not None:
                try:
                    matched = bool(cond_fn(data))
                except Exception:
                    matched = False
            results.append(RuleResult(
                rule_id=rule["id"],
                dimension=rule["dimension"],
                name=rule["name"],
                description=rule["description"],
                signal=rule["signal"],
                matched=matched,
                weight=rule["weight"],
            ))
        return results


def dimension_summary(results: List[RuleResult]) -> Dict[str, Dict[str, int]]:
    """Aggregate matched results by dimension, counting signals."""
    summary: Dict[str, Dict[str, int]] = {}
    for r in results:
        if not r.matched:
            continue
        dim = summary.setdefault(r.dimension, {"bullish": 0, "bearish": 0, "warning": 0, "neutral": 0})
        if r.signal in dim:
            dim[r.signal] += 1
    return {k: v for k, v in summary.items() if sum(v.values()) > 0}


def compute_total_score(results: List[RuleResult]) -> float:
    """Weighted score: bullish positive, bearish/warning negative."""
    score = 0.0
    for r in results:
        if not r.matched:
            continue
        if r.signal == "bullish":
            score += r.weight
        elif r.signal in ("bearish", "warning"):
            score -= r.weight
    return round(score, 2)
