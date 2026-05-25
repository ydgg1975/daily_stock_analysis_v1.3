# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 决策稳定性校准
===================================

职责：
1. 结合技术指标（压力支撑）及资金流数据校准/平抑 AI 的极端预测
2. 填充与规范筹码分布、价格区间的数据形态
"""

import math
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.report_language import (
    get_chip_unavailable_text,
    is_chip_placeholder_value,
    localize_chip_health,
    infer_decision_type_from_advice,
)

logger = logging.getLogger(__name__)

# ---------- chip_structure constants & helpers ----------

_CHIP_KEYS: tuple = ("profit_ratio", "avg_cost", "concentration", "chip_health")


def _is_value_placeholder(v: Any) -> bool:
    """True if value is empty or placeholder (N/A, 数据缺失, etc.)."""
    return is_chip_placeholder_value(v)


_RISK_WARNING_PLACEHOLDER_TEXTS = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "tbd",
    "暂无",
    "待补充",
    "数据缺失",
    "未知",
    "无",
}

_STRUCTURAL_RISK_PHRASE_HINTS = (
    "重大利空",
    "重大风险",
    "关键风险",
    "减持",
    "高位减持",
    "退市",
    "退市风险",
    "停牌",
    "重大问询",
    "处罚",
    "限售",
    "违规",
    "违规风险",
    "诉讼",
    "问询",
    "监管",
    "财务",
    "审计",
    "爆雷",
    "暴雷",
    "违约",
    "违约风险",
    "流动性危机",
    "债务",
    "清算",
    "破产",
    "重大变脸",
    "major risk",
    "material adverse",
    "suspension",
    "delisting",
    "regulatory",
    "downgrade",
    "liquidity",
    "default",
)

_CAPITAL_FLOW_UNAVAILABLE_STATUS = {
    "not_supported",
    "not supported",
    "unsupported",
    "unavailable",
    "not_available",
    "not available",
    "none",
    "na",
    "n/a",
    "null",
    "missing",
}


def _is_meaningful_text(value: Any) -> bool:
    text = str(value).strip() if value is not None else ""
    if not text:
        return False
    lowered = text.strip().lower()
    return lowered not in _RISK_WARNING_PLACEHOLDER_TEXTS


def _safe_float(v: Any, default: float = 0.0) -> float:
    """Safely convert to float; return default on failure."""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        try:
            return default if math.isnan(float(v)) else float(v)
        except (ValueError, TypeError):
            return default
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return default


def _coerce_chip_metric(v: Any) -> Optional[float]:
    """Convert chip metrics while preserving the distinction between missing and zero."""
    if v is None:
        return None
    try:
        numeric = float(v)
    except (TypeError, ValueError):
        try:
            numeric = float(str(v).strip())
        except (TypeError, ValueError):
            return None
    return None if math.isnan(numeric) else numeric


_BULLISH_TREND_HINTS: Tuple[str, ...] = (
    "多头排列",
    "持续上涨",
    "趋势向上",
    "上升趋势",
    "向上发散",
    "bullish",
    "uptrend",
)
_WEAK_BULLISH_TREND_HINTS: Tuple[str, ...] = ("弱势多头",)
_BEARISH_TREND_HINTS: Tuple[str, ...] = (
    "空头排列",
    "持续下跌",
    "趋势向下",
    "下降趋势",
    "向下发散",
    "bearish",
    "downtrend",
)
_WEAK_BEARISH_TREND_HINTS: Tuple[str, ...] = ("弱势空头",)
_NEGATION_TOKENS: Tuple[str, ...] = (
    "不是",
    "并非",
    "并未",
    "没有",
    "尚不",
    "尚未",
    "未",
    "无",
    "不属",
    "非",
    "not ",
    "no ",
)
_NEGATION_BREAK_CHARS: Tuple[str, ...] = (",", ".", ";", ":", "!", "?", "，", "。", "；", "：", "！", "？", "\n")
_NEGATION_LOOKBACK_CHARS = 16
_NEGATION_MAX_GAP_CHARS = 8
_NEGATION_SCOPE_BREAK_TOKENS: Tuple[str, ...] = (
    "而是",
    "但是",
    "但",
    "反而",
    "反倒",
    "转为",
    "转成",
    "改为",
    "改成",
    " but ",
    " instead ",
    " rather ",
)
_SINGLE_CHAR_NEGATION_GAP_PREFIXES: Tuple[str, ...] = (
    "形成",
    "出现",
    "进入",
    "转为",
    "转成",
    "构成",
    "呈现",
    "显示",
    "属于",
    "是",
    "有",
    "能",
    "见",
    "站",
    "守",
    "破",
)


def _normalize_prompt_reason_items(items: Any) -> List[str]:
    """Normalize prompt reason/risk items into a clean string list."""
    if not isinstance(items, list):
        return []
    normalized: List[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _contains_trend_hint(text: str, hints: Tuple[str, ...]) -> bool:
    """Return True when text contains a non-negated strong trend hint."""
    lowered = text.strip().lower()

    def _has_negation_scope_break(gap: str) -> bool:
        normalized_gap = gap.lower()
        for token in _NEGATION_SCOPE_BREAK_TOKENS:
            token_index = normalized_gap.find(token)
            if token_index > 0:
                return True
        return False

    def _is_valid_negation_gap(token: str, gap: str) -> bool:
        if not gap:
            return True
        if token not in {"未", "无", "非"}:
            return True
        return any(gap.startswith(prefix) for prefix in _SINGLE_CHAR_NEGATION_GAP_PREFIXES)

    def _is_negated_match(index: int) -> bool:
        prefix = lowered[max(0, index - _NEGATION_LOOKBACK_CHARS):index]
        for token in _NEGATION_TOKENS:
            token_index = prefix.rfind(token)
            if token_index < 0:
                continue
            gap = prefix[token_index + len(token):]
            if any(char in gap for char in _NEGATION_BREAK_CHARS):
                continue
            stripped_gap = gap.strip()
            if len(stripped_gap) > _NEGATION_MAX_GAP_CHARS:
                continue
            if _has_negation_scope_break(stripped_gap):
                continue
            if not _is_valid_negation_gap(token, stripped_gap):
                continue
            return True
        return False

    for hint in hints:
        keyword = hint.lower()
        start = 0
        while True:
            index = lowered.find(keyword, start)
            if index < 0:
                break
            if not _is_negated_match(index):
                return True
            start = index + len(keyword)
    return False


def _infer_trend_direction(trend: Dict[str, Any]) -> str:
    """Infer the final trend direction from trend_status and ma_alignment."""
    combined = " ".join(
        str(trend.get(key, "")).strip()
        for key in ("trend_status", "ma_alignment")
        if str(trend.get(key, "")).strip()
    )
    if not combined:
        return "neutral"
    lowered = combined.lower()
    normalized = lowered.replace(" ", "")
    has_bullish = (
        _contains_trend_hint(combined, _BULLISH_TREND_HINTS + _WEAK_BULLISH_TREND_HINTS)
        or "ma5>ma10>ma20" in normalized
        or (
            "ma5>ma10" in normalized
            and any(pattern in normalized for pattern in ("ma10≤ma20", "ma10<=ma20"))
        )
    )
    has_bearish = (
        _contains_trend_hint(combined, _BEARISH_TREND_HINTS + _WEAK_BEARISH_TREND_HINTS)
        or "ma5<ma10<ma20" in normalized
        or (
            "ma5<ma10" in normalized
            and any(pattern in normalized for pattern in ("ma10≥ma20", "ma10>=ma20"))
        )
    )
    if has_bullish and not has_bearish:
        return "bullish"
    if has_bearish and not has_bullish:
        return "bearish"
    return "neutral"


def _filter_conflicting_trend_items(items: List[str], conflict_hints: Tuple[str, ...]) -> List[str]:
    """Drop reasons that directly conflict with the final trend direction."""
    return [item for item in items if not _contains_trend_hint(item, conflict_hints)]


def _sanitize_trend_analysis_for_prompt(
    trend: Any,
    *,
    volume_change_ratio: Any = None,
) -> Dict[str, Any]:
    """Clean prompt-only trend hints on a derived copy without touching runtime/provider config."""
    trend_dict = dict(trend) if isinstance(trend, dict) else {}
    signal_reasons = _normalize_prompt_reason_items(trend_dict.get("signal_reasons"))
    risk_factors = _normalize_prompt_reason_items(trend_dict.get("risk_factors"))
    prompt_notes: List[str] = []
    trend_direction = _infer_trend_direction(trend_dict)

    if trend_direction == "bearish":
        filtered_signal_reasons = _filter_conflicting_trend_items(
            signal_reasons,
            _BULLISH_TREND_HINTS + _WEAK_BULLISH_TREND_HINTS,
        )
        if len(filtered_signal_reasons) != len(signal_reasons):
            prompt_notes.append("当前技术结构偏空，已剔除与空头主判断直接冲突的看多结构理由。")
        signal_reasons = filtered_signal_reasons
        prompt_notes.append(
            "若新闻、业绩或政策催化偏多，只能表述为“事件先行、技术待确认”或“基本面偏多，但技术面尚未确认”，严禁写成确定性买点。"
        )
    elif trend_direction == "bullish":
        filtered_signal_reasons = _filter_conflicting_trend_items(
            signal_reasons,
            _BEARISH_TREND_HINTS + _WEAK_BEARISH_TREND_HINTS,
        )
        if len(filtered_signal_reasons) != len(signal_reasons):
            prompt_notes.append("当前技术结构偏多，已剔除与多头主判断直接冲突的空头结构理由。")
        signal_reasons = filtered_signal_reasons
        filtered_risk_factors = _filter_conflicting_trend_items(
            risk_factors,
            _BEARISH_TREND_HINTS + _WEAK_BEARISH_TREND_HINTS,
        )
        if len(filtered_risk_factors) != len(risk_factors):
            prompt_notes.append("当前技术结构偏多，已剔除与多头主判断直接冲突的空头结构风险表述。")
        risk_factors = filtered_risk_factors

    parsed_volume_change = _safe_float(volume_change_ratio, default=math.nan)
    if math.isfinite(parsed_volume_change) and parsed_volume_change > 10:
        prompt_notes.append(
            f"成交量较昨日变化约 {parsed_volume_change:.2f} 倍，可能存在异常数据或一次性冲量；量能信号必须降权解读，不能机械视为强确认。"
        )

    trend_dict["signal_reasons"] = signal_reasons
    trend_dict["risk_factors"] = risk_factors
    trend_dict["prompt_consistency_notes"] = prompt_notes
    trend_dict["prompt_trend_direction"] = trend_direction
    return trend_dict


def _derive_chip_health(profit_ratio: float, concentration_90: float, language: str = "zh") -> str:
    """Derive chip_health from profit_ratio and concentration_90."""
    if profit_ratio >= 0.9:
        return localize_chip_health("警惕", language)  # 获利盘极高
    if concentration_90 >= 0.25:
        return localize_chip_health("警惕", language)  # 筹码分散
    if concentration_90 < 0.15 and 0.3 <= profit_ratio < 0.9:
        return localize_chip_health("健康", language)  # 集中且获利比例适中
    return localize_chip_health("一般", language)


def _build_chip_structure_from_data(chip_data: Any, language: str = "zh") -> Dict[str, Any]:
    """Build chip_structure dict from ChipDistribution or dict."""
    if hasattr(chip_data, "profit_ratio"):
        pr = _safe_float(chip_data.profit_ratio)
        ac = chip_data.avg_cost
        c90 = _safe_float(chip_data.concentration_90)
    else:
        d = chip_data if isinstance(chip_data, dict) else {}
        pr = _safe_float(d.get("profit_ratio"))
        ac = d.get("avg_cost")
        c90 = _safe_float(d.get("concentration_90"))
    chip_health = _derive_chip_health(pr, c90, language=language)
    return {
        "profit_ratio": f"{pr:.1%}",
        "avg_cost": ac if (ac is not None and _safe_float(ac) != 0.0) else "N/A",
        "concentration": f"{c90:.2%}",
        "chip_health": chip_health,
    }


def _has_meaningful_chip_data(chip_data: Any) -> bool:
    """Return True when chip data has the core metrics required for reporting."""
    if not chip_data:
        return False
    if hasattr(chip_data, "avg_cost"):
        avg_cost = _coerce_chip_metric(getattr(chip_data, "avg_cost", None))
        concentration_90 = _coerce_chip_metric(getattr(chip_data, "concentration_90", None))
        concentration_70 = _coerce_chip_metric(getattr(chip_data, "concentration_70", None))
    else:
        d = chip_data if isinstance(chip_data, dict) else {}
        avg_cost = _coerce_chip_metric(d.get("avg_cost"))
        concentration_90_value = d.get("concentration_90")
        if concentration_90_value is None:
            concentration_90_value = d.get("concentration")
        concentration_90 = _coerce_chip_metric(concentration_90_value)
        concentration_70 = _coerce_chip_metric(d.get("concentration_70"))
    return (
        avg_cost is not None
        and avg_cost > 0
        and (
            (concentration_90 is not None and concentration_90 >= 0)
            or (concentration_70 is not None and concentration_70 >= 0)
        )
    )


def _mark_chip_structure_unavailable(result: Any, language: str) -> None:
    if not result or not isinstance(getattr(result, "dashboard", None), dict):
        return
    data_perspective = result.dashboard.get("data_perspective")
    if not isinstance(data_perspective, dict):
        return
    data_perspective["chip_structure"] = {}
    data_perspective["chip_unavailable_reason"] = get_chip_unavailable_text(language)


def normalize_chip_structure_availability(result: Any, chip_data: Any) -> None:
    """Fill valid chip metrics or collapse placeholder-only chip fields to one fallback line."""
    if not result:
        return
    language = getattr(result, "report_language", "zh")
    if _has_meaningful_chip_data(chip_data):
        fill_chip_structure_if_needed(result, chip_data)
        return
    _mark_chip_structure_unavailable(result, language)


def fill_chip_structure_if_needed(result: Any, chip_data: Any) -> None:
    """When chip_data exists, fill chip_structure placeholder fields from chip_data (in-place)."""
    if not result or not _has_meaningful_chip_data(chip_data):
        return
    try:
        if not getattr(result, "dashboard", None):
            result.dashboard = {}
        dash = result.dashboard
        dp = dash.get("data_perspective") or {}
        dash["data_perspective"] = dp
        cs = dp.get("chip_structure") or {}
        filled = _build_chip_structure_from_data(
            chip_data,
            language=getattr(result, "report_language", "zh"),
        )
        merged = dict(cs)
        for k in _CHIP_KEYS:
            if _is_value_placeholder(merged.get(k)):
                merged[k] = filled[k]
        if merged != cs:
            dp["chip_structure"] = merged
            logger.info("[chip_structure] Filled placeholder chip fields from data source (Issue #589)")
    except Exception as e:
        logger.warning("[chip_structure] Fill failed, skipping: %s", e)


_PRICE_POS_KEYS = ("ma5", "ma10", "ma20", "bias_ma5", "bias_status", "current_price", "support_level", "resistance_level")


def fill_price_position_if_needed(
    result: Any,
    trend_result: Any = None,
    realtime_quote: Any = None,
) -> None:
    """Fill missing price_position fields from trend_result / realtime data (in-place)."""
    if not result:
        return
    try:
        if not getattr(result, "dashboard", None):
            result.dashboard = {}
        dash = result.dashboard
        dp = dash.get("data_perspective") or {}
        dash["data_perspective"] = dp
        pp = dp.get("price_position") or {}

        computed: Dict[str, Any] = {}
        if trend_result:
            tr = trend_result if isinstance(trend_result, dict) else (
                trend_result.__dict__ if hasattr(trend_result, "__dict__") else {}
            )
            computed["ma5"] = tr.get("ma5")
            computed["ma10"] = tr.get("ma10")
            computed["ma20"] = tr.get("ma20")
            computed["bias_ma5"] = tr.get("bias_ma5")
            computed["current_price"] = tr.get("current_price")
            support_levels = tr.get("support_levels") or []
            resistance_levels = tr.get("resistance_levels") or []
            if support_levels:
                computed["support_level"] = support_levels[0]
            if resistance_levels:
                computed["resistance_level"] = resistance_levels[0]
        if realtime_quote:
            rq = realtime_quote if isinstance(realtime_quote, dict) else (
                realtime_quote.to_dict() if hasattr(realtime_quote, "to_dict") else {}
            )
            if _is_value_placeholder(computed.get("current_price")):
                computed["current_price"] = rq.get("price")

        filled = False
        for k in _PRICE_POS_KEYS:
            if _is_value_placeholder(pp.get(k)) and not _is_value_placeholder(computed.get(k)):
                pp[k] = computed[k]
                filled = True
        if filled:
            dp["price_position"] = pp
            logger.info("[price_position] Filled placeholder fields from computed data")
    except Exception as e:
        logger.warning("[price_position] Fill failed, skipping: %s", e)


def stabilize_decision_with_structure(
    result: Any,
    trend_result: Any = None,
    fundamental_context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Calibrate aggressive buy/sell advice with price levels and capital flow.
    """
    if not result:
        return

    try:
        from src.report_language import normalize_report_language
        language = normalize_report_language(getattr(result, "report_language", "zh"))
        dashboard = getattr(result, "dashboard", None)
        dashboard = dashboard if isinstance(dashboard, dict) else {}
        data_perspective = dashboard.get("data_perspective") if isinstance(dashboard, dict) else {}
        if not isinstance(data_perspective, dict):
            data_perspective = {}
        price_position = data_perspective.get("price_position")
        if not isinstance(price_position, dict):
            price_position = {}

        trend_dict = _as_dict_for_decision_guard(trend_result)
        current_price = _first_numeric_value(
            getattr(result, "current_price", None),
            price_position.get("current_price"),
            trend_dict.get("current_price"),
        )
        support = _first_numeric_value(
            price_position.get("support_level"),
            _first_list_value(trend_dict.get("support_levels")),
        )
        resistance = _first_numeric_value(
            price_position.get("resistance_level"),
            _first_list_value(trend_dict.get("resistance_levels")),
        )
        decision_type = infer_decision_type_from_advice(
            getattr(result, "decision_type", ""),
            default=getattr(result, "decision_type", "hold") or "hold",
        )
        decision_type = decision_type if decision_type in {"buy", "hold", "sell"} else "hold"
        advice_decision_type = infer_decision_type_from_advice(
            getattr(result, "operation_advice", ""),
            default="",
        )

        flow_bias, flow_reason = _capital_flow_bias_with_status(fundamental_context)
        if flow_bias == "unavailable":
            if isinstance(fundamental_context, dict) and "capital_flow" in fundamental_context:
                if decision_type == "buy" or advice_decision_type == "buy":
                    _downgrade_buy_without_capital_flow(
                        result,
                        language,
                        current_price=current_price,
                        support=support,
                        resistance=resistance,
                        flow_status=flow_reason,
                    )
                else:
                    _set_decision_stability_unavailable(
                        result,
                        language,
                        current_price=current_price,
                        support=support,
                        resistance=resistance,
                        flow_status=flow_reason,
                    )
            return

        if current_price is None:
            return

        broke_support = support is not None and current_price < support * 0.985
        near_support = support is not None and not broke_support and current_price <= support * 1.03
        breakout = resistance is not None and current_price > resistance * 1.01
        near_resistance = (
            resistance is not None
            and not breakout
            and current_price >= resistance * 0.97
        )
        mid_range = (
            support is not None
            and resistance is not None
            and support * 1.03 < current_price < resistance * 0.97
        )

        has_significant_risk = _has_structural_risk_alert(result)

        if decision_type == "buy":
            if near_resistance and flow_bias != "inflow":
                _downgrade_to_structural_hold(
                    result,
                    language,
                    advice_key="range",
                    reason_key="buy_near_resistance",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
            elif flow_bias == "outflow" and not breakout:
                _downgrade_to_structural_hold(
                    result,
                    language,
                    advice_key="range",
                    reason_key="buy_with_outflow",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
            elif mid_range and flow_bias == "neutral":
                _downgrade_to_structural_hold(
                    result,
                    language,
                    advice_key="range",
                    reason_key="hold_mid_range",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
        elif decision_type == "sell":
            if near_support and (flow_bias != "outflow") and not has_significant_risk:
                _downgrade_to_structural_hold(
                    result,
                    language,
                    advice_key="shakeout",
                    reason_key="sell_near_support",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
            elif flow_bias == "inflow" and not broke_support and not has_significant_risk:
                _downgrade_to_structural_hold(
                    result,
                    language,
                    advice_key="hold",
                    reason_key="sell_with_inflow",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
        elif decision_type == "hold":
            change_pct = _first_numeric_value(getattr(result, "change_pct", None))
            if change_pct is not None and change_pct < 0 and near_support and flow_bias != "outflow":
                _set_structural_hold_wording(
                    result,
                    language,
                    advice_key="shakeout",
                    reason_key="hold_shakeout",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
            elif mid_range and flow_bias == "neutral":
                _set_structural_hold_wording(
                    result,
                    language,
                    advice_key="range",
                    reason_key="hold_mid_range",
                    current_price=current_price,
                    support=support,
                    resistance=resistance,
                    flow_bias=flow_bias,
                )
        _sync_stability_dashboard_fields(result)
    except Exception as exc:
        logger.warning("[decision_stability] skipped: %s", exc)


def _has_structural_risk_alert(result: Any) -> bool:
    dashboard = getattr(result, "dashboard", {})
    dashboard = dashboard if isinstance(dashboard, dict) else {}

    risk_text = getattr(result, "risk_warning", "")
    if _is_significant_structural_risk(risk_text):
        return True

    intelligence = dashboard.get("intelligence") if isinstance(dashboard, dict) else None
    if isinstance(intelligence, dict):
        risk_alerts = intelligence.get("risk_alerts")
        if isinstance(risk_alerts, str):
            if _is_significant_structural_risk(risk_alerts):
                return True
        elif isinstance(risk_alerts, (list, tuple, set)):
            if any(_is_significant_structural_risk(item) for item in risk_alerts):
                return True

    core_conclusion = dashboard.get("core_conclusion") if isinstance(dashboard, dict) else None
    if isinstance(core_conclusion, dict):
        signal_type = str(core_conclusion.get("signal_type", "")).strip()
        if _is_significant_structural_risk(signal_type):
            return True
    return False


def _is_significant_structural_risk(value: Any) -> bool:
    text = str(value or "").strip()
    if not _is_meaningful_text(text):
        return False

    normalized = text.lower()
    if any(keyword in normalized for keyword in _STRUCTURAL_RISK_PHRASE_HINTS):
        return True

    return "重大" in text and "风险" in normalized


def _sync_stability_dashboard_fields(result: Any) -> None:
    dashboard = getattr(result, "dashboard", None)
    dashboard = dashboard if isinstance(dashboard, dict) else {}
    result.dashboard = dashboard
    dashboard["sentiment_score"] = getattr(result, "sentiment_score", None)
    dashboard["operation_advice"] = getattr(result, "operation_advice", None)
    dashboard["decision_type"] = getattr(result, "decision_type", None)


def _as_dict_for_decision_guard(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        try:
            converted = value.to_dict()
            return converted if isinstance(converted, dict) else {}
        except Exception:
            return {}
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _first_list_value(value: Any) -> Any:
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return value


def _coerce_numeric_value(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            return float(value)
        return None
    text = str(value).replace(",", "").replace("，", "").strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "NULL"}:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _first_numeric_value(*values: Any) -> Optional[float]:
    for value in values:
        if isinstance(value, (list, tuple)):
            nested = _first_numeric_value(*value)
            if nested is not None:
                return nested
            continue
        numeric = _coerce_numeric_value(value)
        if numeric is not None:
            return numeric
    return None


def _capital_flow_bias(fundamental_context: Optional[Dict[str, Any]]) -> str:
    return _capital_flow_bias_with_status(fundamental_context)[0]


def _capital_flow_bias_with_status(
    fundamental_context: Optional[Dict[str, Any]],
) -> tuple[str, str]:
    if not isinstance(fundamental_context, dict):
        return "unavailable", "invalid_context"
    block = fundamental_context.get("capital_flow")
    if not isinstance(block, dict):
        return "unavailable", "capital_flow_block_missing"
    status = str(block.get("status") or "").strip().lower()
    normalized_status = status.replace("-", " ").replace("_", " ").strip()
    if normalized_status in _CAPITAL_FLOW_UNAVAILABLE_STATUS or "not supported" in normalized_status:
        return "unavailable", status or "not_supported"
    data = block.get("data") if isinstance(block.get("data"), dict) else block
    stock_flow = data.get("stock_flow") if isinstance(data, dict) else None
    if not isinstance(stock_flow, dict) or not stock_flow:
        return "unavailable", "empty_stock_flow"

    def _flow_direction(value: Optional[float]) -> Optional[str]:
        if value is None or value == 0:
            return None
        return "inflow" if value > 0 else "outflow"

    numeric_values = [
        _coerce_numeric_value(stock_flow.get("main_net_inflow")),
        _coerce_numeric_value(stock_flow.get("inflow_5d")),
        _coerce_numeric_value(stock_flow.get("inflow_10d")),
    ]
    if all(value is None for value in numeric_values):
        return "unavailable", "missing_or_na_flow_fields"

    ordered_signals = [
        _flow_direction(value) for value in numeric_values
    ]
    directions = {signal for signal in ordered_signals if signal is not None}
    if not directions or len(directions) > 1:
        return "neutral", "conflict_or_missing"
    for signal in ordered_signals:
        if signal is not None:
            return signal, "ok"
    return "neutral", "neutral"


def _capital_flow_status_for_stability(reason: str, language: str) -> str:
    normalized = str(reason or "").strip().lower()
    if "not_supported" in normalized or "unsupported" in normalized or "not available" in normalized:
        return "市场资金流服务暂不支持" if language == "zh" else "Capital flow source unsupported"
    if "empty_stock_flow" in normalized or "missing" in normalized:
        return "资金流数据缺失" if language == "zh" else "capital flow data unavailable"
    return "资金流数据不可用" if language == "zh" else "capital flow unavailable"


def _set_decision_stability_unavailable(
    result: Any,
    language: str,
    *,
    current_price: Optional[float],
    support: Optional[float],
    resistance: Optional[float],
    flow_status: str,
) -> None:
    dashboard = getattr(result, "dashboard", None)
    dashboard = dashboard if isinstance(dashboard, dict) else {}
    result.dashboard = dashboard
    dashboard["decision_stability"] = {
        "applied": False,
        "reason": "资金流不可用，未使用资金流校准" if language == "zh" else "Capital flow unavailable; stability calibration not applied",
        "capital_flow_status": _capital_flow_status_for_stability(flow_status, language),
        "current_price": current_price,
        "support": support,
        "resistance": resistance,
        "capital_flow_bias": "unavailable",
    }
    _sync_stability_dashboard_fields(result)


def _bound_hold_watch_sentiment_score(result: Any) -> None:
    try:
        score = int(getattr(result, "sentiment_score", 50))
    except (TypeError, ValueError):
        score = 50
    result.sentiment_score = min(59, max(45, score))


def _apply_hold_watch_dashboard(
    result: Any,
    language: str,
    *,
    advice: str,
    reason: str,
    current_price: Optional[float],
    support: Optional[float],
    resistance: Optional[float],
    flow_bias: str,
    no_position: str,
    has_position: str,
    capital_flow_status: Optional[str] = None,
) -> None:
    result.operation_advice = advice

    dashboard = getattr(result, "dashboard", None)
    dashboard = dashboard if isinstance(dashboard, dict) else {}
    result.dashboard = dashboard
    core = dashboard.get("core_conclusion")
    if not isinstance(core, dict):
        core = {}
        dashboard["core_conclusion"] = core
    core["signal_type"] = "🟡持有观望" if language == "zh" else "🟡 Hold / Watch"
    core["one_sentence"] = f"{advice}：{reason}" if language == "zh" else f"{advice}: {reason}"

    position_advice = core.get("position_advice")
    if not isinstance(position_advice, dict):
        position_advice = {}
        core["position_advice"] = position_advice
    position_advice["no_position"] = no_position
    position_advice["has_position"] = has_position

    stability = {
        "applied": True,
        "reason": reason,
        "current_price": current_price,
        "support": support,
        "resistance": resistance,
        "capital_flow_bias": flow_bias,
    }
    if capital_flow_status is not None:
        stability["capital_flow_status"] = capital_flow_status
    dashboard["decision_stability"] = stability

    if reason and reason not in str(getattr(result, "risk_warning", "")):
        sep = "；" if language == "zh" else "; "
        orig_risk = getattr(result, "risk_warning", "")
        result.risk_warning = f"{orig_risk}{sep}{reason}" if orig_risk else reason
    result.buy_reason = reason or getattr(result, "buy_reason", "")


def _downgrade_buy_without_capital_flow(
    result: Any,
    language: str,
    *,
    current_price: Optional[float],
    support: Optional[float],
    resistance: Optional[float],
    flow_status: str,
) -> None:
    status_text = _capital_flow_status_for_stability(flow_status, language)
    if language == "zh":
        advice = "持有观察"
        reason = f"{status_text}，买入结论缺少资金面确认，先按观察处理。"
        no_position = "空仓先不追买，等待资金流恢复、支撑确认或有效突破后再行动。"
        has_position = "持仓以关键支撑为风控线，资金流恢复前控制仓位。"
        confidence = "低"
    else:
        advice = "Hold and watch"
        reason = f"{status_text}; the buy call lacks capital-flow confirmation, so treat it as watch-only."
        no_position = "Do not chase; wait for capital-flow recovery, support confirmation, or a valid breakout."
        has_position = "Use key support as the risk line and keep position size controlled until capital flow recovers."
        confidence = "Low"

    result.decision_type = "hold"
    result.confidence_level = confidence
    _bound_hold_watch_sentiment_score(result)
    _apply_hold_watch_dashboard(
        result,
        language,
        advice=advice,
        reason=reason,
        current_price=current_price,
        support=support,
        resistance=resistance,
        flow_bias="unavailable",
        no_position=no_position,
        has_position=has_position,
        capital_flow_status=status_text,
    )
    _sync_stability_dashboard_fields(result)
    logger.info("[decision_stability] Downgraded buy because capital flow is unavailable: %s", flow_status)


def _downgrade_to_structural_hold(
    result: Any,
    language: str,
    *,
    advice_key: str,
    reason_key: str,
    current_price: float,
    support: Optional[float],
    resistance: Optional[float],
    flow_bias: str,
) -> None:
    result.decision_type = "hold"
    _bound_hold_watch_sentiment_score(result)
    _set_structural_hold_wording(
        result,
        language,
        advice_key=advice_key,
        reason_key=reason_key,
        current_price=current_price,
        support=support,
        resistance=resistance,
        flow_bias=flow_bias,
    )


def _set_structural_hold_wording(
    result: Any,
    language: str,
    *,
    advice_key: str,
    reason_key: str,
    current_price: float,
    support: Optional[float],
    resistance: Optional[float],
    flow_bias: str,
) -> None:
    advice = {
        "zh": {
            "range": "震荡观望",
            "shakeout": "洗盘观察",
            "hold": "持有观察",
        },
        "en": {
            "range": "Range-bound watch",
            "shakeout": "Shakeout watch",
            "hold": "Hold and watch",
        },
    }[language].get(advice_key, "持有观察" if language == "zh" else "Hold and watch")
    reason_templates = {
        "zh": {
            "buy_near_resistance": "价格接近压力位且主力资金未确认流入，不宜仅因短线反弹追买。",
            "buy_with_outflow": "主力资金流出与买入结论冲突，买点需等待支撑确认或资金回流。",
            "sell_near_support": "价格贴近支撑且未见资金持续流出，不宜仅因单日下跌直接卖出。",
            "sell_with_inflow": "主力资金流入与卖出结论冲突，先按持有观察处理并跟踪支撑失效。",
            "hold_shakeout": "价格回落至支撑附近但资金未确认流出，更适合按洗盘观察处理。",
            "hold_mid_range": "价格处于支撑与压力之间且资金流不明确，维持震荡观望更可操作。",
        },
        "en": {
            "buy_near_resistance": "Price is near resistance without confirmed main-force inflow, so chasing the rebound is not actionable.",
            "buy_with_outflow": "Main-force outflow conflicts with a buy call; wait for support confirmation or capital inflow.",
            "sell_near_support": "Price is near support without sustained outflow, so a one-day drop is not enough to sell.",
            "sell_with_inflow": "Main-force inflow conflicts with a sell call; hold and watch for support failure.",
            "hold_shakeout": "Price pulled back near support without confirmed outflow, which is better treated as a shakeout watch.",
            "hold_mid_range": "Price is between support and resistance with neutral fund flow, so range-bound watch is more actionable.",
        },
    }
    reason = reason_templates[language].get(reason_key, "")
    result.operation_advice = advice
    if language == "zh" and "震荡" not in str(getattr(result, "trend_prediction", "")):
        result.trend_prediction = "震荡"
    elif language == "en" and advice_key == "range":
        result.trend_prediction = "Sideways"

    if language == "zh":
        no_position = "空仓先不追涨杀跌，等待支撑确认、放量突破 or 资金回流后再行动。"
        has_position = "持仓以关键支撑为风控线，未跌破前以观察 and 分批控仓为主。"
    else:
        no_position = "Do not chase or panic; wait for support confirmation, breakout, or renewed inflow."
        has_position = "Use key support as the risk line and manage position size unless support fails."
    _apply_hold_watch_dashboard(
        result,
        language,
        advice=advice,
        reason=reason,
        current_price=current_price,
        support=support,
        resistance=resistance,
        flow_bias=flow_bias,
        no_position=no_position,
        has_position=has_position,
    )
    logger.info("[decision_stability] Applied structural hold calibration: %s", reason_key)
