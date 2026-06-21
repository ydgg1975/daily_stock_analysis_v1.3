# -*- coding: utf-8 -*-
"""Deterministic trading-observation summaries from analysis results.

This is a decision-support formatter only. It never connects to brokers,
never places orders, and never provides automated trading.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text.endswith("%"):
        text = text[:-1].strip()
    if not text or text.upper() == "N/A":
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any, default: str = "待确认") -> str:
    text = str(value or "").strip()
    return text if text else default


def _dashboard(result: Any) -> Dict[str, Any]:
    dashboard = getattr(result, "dashboard", None)
    return dashboard if isinstance(dashboard, dict) else {}


def _nested(mapping: Dict[str, Any], *keys: str) -> Dict[str, Any]:
    cur: Any = mapping
    for key in keys:
        if not isinstance(cur, dict):
            return {}
        cur = cur.get(key)
    return cur if isinstance(cur, dict) else {}


def _display_name(result: Any) -> str:
    name = str(getattr(result, "name", "") or "").strip()
    code = str(getattr(result, "code", "") or "").strip()
    return f"{name}({code})" if name else code


def _score(result: Any) -> float:
    return _safe_float(getattr(result, "sentiment_score", None)) or 0.0


def _operation(result: Any) -> str:
    return str(getattr(result, "operation_advice", "") or "").strip() or "观察"


def _is_not_recommended(result: Any) -> bool:
    decision = str(getattr(result, "decision_type", "") or "").strip().lower()
    operation = _operation(result)
    if decision == "sell" or _score(result) < 45:
        return True
    return any(token in operation for token in ("卖", "减仓", "止损", "规避", "不建议", "回避"))


def _volume_ratio(result: Any) -> Optional[float]:
    volume = _nested(_dashboard(result), "data_perspective", "volume_analysis")
    return _safe_float(volume.get("volume_ratio") or volume.get("量比"))


def _price_position(result: Any) -> Dict[str, Any]:
    return _nested(_dashboard(result), "data_perspective", "price_position")


def _current_price(result: Any) -> Optional[float]:
    return _safe_float(getattr(result, "current_price", None)) or _safe_float(
        _price_position(result).get("current_price")
    )


def _break_state(result: Any) -> str:
    price = _current_price(result)
    position = _price_position(result)
    resistance = _safe_float(position.get("resistance_level"))
    support = _safe_float(position.get("support_level"))
    if price is not None and resistance is not None and resistance > 0 and price >= resistance:
        return "breakout"
    if price is not None and support is not None and support > 0 and price <= support:
        return "breakdown"
    trend = str(getattr(result, "trend_prediction", "") or "")
    if "突破" in trend:
        return "breakout"
    if "跌破" in trend or "破位" in trend:
        return "breakdown"
    return ""


def _battle_line(result: Any) -> str:
    dashboard = _dashboard(result)
    sniper = _nested(dashboard, "battle_plan", "sniper_points")
    pos = _nested(dashboard, "core_conclusion", "position_advice")
    buy = sniper.get("ideal_buy") or sniper.get("ideal_entry") or sniper.get("buy_point")
    sell = sniper.get("sell_point") or sniper.get("take_profit") or sniper.get("target")
    stop = sniper.get("stop_loss")
    take = sniper.get("take_profit") or sniper.get("target")
    parts = [
        f"买点:{_clean_text(buy)}",
        f"卖点:{_clean_text(sell)}",
        f"止损:{_clean_text(stop)}",
        f"止盈:{_clean_text(take)}",
    ]
    if pos.get("no_position"):
        parts.append(f"空仓:{_clean_text(pos.get('no_position'))}")
    if pos.get("has_position"):
        parts.append(f"持仓:{_clean_text(pos.get('has_position'))}")
    return "；".join(parts)


def _reason(result: Any) -> str:
    core = _nested(_dashboard(result), "core_conclusion")
    return _clean_text(core.get("one_sentence") or getattr(result, "analysis_summary", ""))


def _compact(items: List[Any]) -> List[Dict[str, Any]]:
    return [
        {
            "name": _display_name(item),
            "score": _score(item),
            "operation": _operation(item),
            "reason": _reason(item),
            "battle_line": _battle_line(item),
        }
        for item in items
    ]


def build_trading_observation_summary(results: List[Any], *, top_n: int = 3) -> Dict[str, Any]:
    sorted_results = sorted(results or [], key=_score, reverse=True)
    top_focus = [item for item in sorted_results if not _is_not_recommended(item)][:top_n]
    not_recommended = [item for item in sorted_results if _is_not_recommended(item)]
    tomorrow_watch = [
        item for item in sorted_results if item not in top_focus and item not in not_recommended
    ][:top_n]

    volume_up: List[Any] = []
    volume_down: List[Any] = []
    breakout: List[Any] = []
    breakdown: List[Any] = []
    for item in sorted_results:
        ratio = _volume_ratio(item)
        change_pct = _safe_float(getattr(item, "change_pct", None))
        if ratio is not None and ratio >= 1.5:
            if change_pct is None or change_pct >= 0:
                volume_up.append(item)
            else:
                volume_down.append(item)
        state = _break_state(item)
        if state == "breakout":
            breakout.append(item)
        elif state == "breakdown":
            breakdown.append(item)

    return {
        "top_focus": _compact(top_focus),
        "not_recommended": _compact(not_recommended),
        "tomorrow_watch": _compact(tomorrow_watch),
        "volume_up": _compact(volume_up),
        "volume_down": _compact(volume_down),
        "breakout": _compact(breakout),
        "breakdown": _compact(breakdown),
        "trade_pool": _compact(sorted_results),
        "disclaimer": "交易辅助观察，不是投资建议；不接券商接口，不自动交易，不下单。",
    }
