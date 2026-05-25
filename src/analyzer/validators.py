# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 结果校验层
===================================

职责：
1. 校验 LLM 返回报告的结构完整性
2. 缺失必要字段时进行占位符填充
"""

import json
from typing import Any, List, Tuple
from src.report_language import get_placeholder_text


def _normalize_risk_warning_values(value: Any) -> List[str]:
    """Normalize arbitrary risk_warning values into a flat list of text alerts."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        normalized: List[str] = []
        for item in value:
            normalized.extend(_normalize_risk_warning_values(item))
        return normalized
    if isinstance(value, dict):
        if not value:
            return []
        try:
            dumped = json.dumps(value, ensure_ascii=False)
            text = dumped.strip()
        except (TypeError, ValueError):
            text = str(value).strip()
        return [text] if text else []
    text = str(value).strip()
    return [text] if text else []


def check_content_integrity(result: Any) -> Tuple[bool, List[str]]:
    """
    Check mandatory fields for report content integrity.
    Returns (pass, missing_fields).
    """
    missing: List[str] = []

    def _is_blank_text(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        return True

    def _is_invalid_risk_alerts(value: Any) -> bool:
        return not isinstance(value, list)

    def _is_invalid_stop_loss(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, (list, tuple, dict)):
            return True
        if isinstance(value, str):
            return not value.strip()
        return False

    if getattr(result, "sentiment_score", None) is None:
        missing.append("sentiment_score")
    advice = getattr(result, "operation_advice", None)
    if not advice or not isinstance(advice, str) or _is_blank_text(advice):
        missing.append("operation_advice")
    summary = getattr(result, "analysis_summary", None)
    if not summary or not isinstance(summary, str) or _is_blank_text(summary):
        missing.append("analysis_summary")
    
    dash = getattr(result, "dashboard", {})
    dash = dash if isinstance(dash, dict) else {}
    core = dash.get("core_conclusion")
    core = core if isinstance(core, dict) else {}
    if _is_blank_text(core.get("one_sentence")):
        missing.append("dashboard.core_conclusion.one_sentence")
    intel = dash.get("intelligence")
    intel = intel if isinstance(intel, dict) else None
    if intel is None or _is_invalid_risk_alerts(intel.get("risk_alerts")):
        missing.append("dashboard.intelligence.risk_alerts")
        
    decision_type = getattr(result, "decision_type", "hold")
    if decision_type in ("buy", "hold"):
        battle = dash.get("battle_plan")
        battle = battle if isinstance(battle, dict) else {}
        sp = battle.get("sniper_points")
        sp = sp if isinstance(sp, dict) else {}
        stop_loss = sp.get("stop_loss")
        if _is_invalid_stop_loss(stop_loss):
            missing.append("dashboard.battle_plan.sniper_points.stop_loss")
            
    return len(missing) == 0, missing


def apply_placeholder_fill(result: Any, missing_fields: List[str]) -> None:
    """Fill missing mandatory fields with placeholders (in-place)."""

    def _is_blank_text(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        return True

    def _is_invalid_risk_alerts(value: Any) -> bool:
        return not isinstance(value, list)

    def _is_invalid_stop_loss(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, (list, tuple, dict)):
            return True
        if isinstance(value, str):
            return not value.strip()
        return False

    placeholder = get_placeholder_text(getattr(result, "report_language", "zh"))
    for field in missing_fields:
        if field == "sentiment_score":
            result.sentiment_score = 50
        elif field == "operation_advice":
            if _is_blank_text(getattr(result, "operation_advice", None)):
                result.operation_advice = placeholder
        elif field == "analysis_summary":
            if _is_blank_text(getattr(result, "analysis_summary", None)):
                result.analysis_summary = placeholder
        elif field == "dashboard.core_conclusion.one_sentence":
            if not getattr(result, "dashboard", None):
                result.dashboard = {}
            core = result.dashboard.get("core_conclusion")
            if not isinstance(core, dict):
                core = {}
                result.dashboard["core_conclusion"] = core
            fallback_sentence = (
                getattr(result, "analysis_summary", None)
                or getattr(result, "operation_advice", None)
                or placeholder
            )
            if _is_blank_text(core.get("one_sentence")):
                result.dashboard["core_conclusion"]["one_sentence"] = fallback_sentence
        elif field == "dashboard.intelligence.risk_alerts":
            if not getattr(result, "dashboard", None):
                result.dashboard = {}
            intelligence = result.dashboard.get("intelligence")
            if not isinstance(intelligence, dict):
                intelligence = {}
                result.dashboard["intelligence"] = intelligence
            if _is_invalid_risk_alerts(intelligence.get("risk_alerts")):
                risk_warning_values = _normalize_risk_warning_values(getattr(result, "risk_warning", ""))
                intelligence["risk_alerts"] = risk_warning_values
        elif field == "dashboard.battle_plan.sniper_points.stop_loss":
            if not getattr(result, "dashboard", None):
                result.dashboard = {}
            battle_plan = result.dashboard.get("battle_plan")
            if not isinstance(battle_plan, dict):
                battle_plan = {}
                result.dashboard["battle_plan"] = battle_plan
            sniper_points = battle_plan.get("sniper_points")
            if not isinstance(sniper_points, dict):
                sniper_points = {}
                battle_plan["sniper_points"] = sniper_points
            if _is_invalid_stop_loss(sniper_points.get("stop_loss")):
                sniper_points["stop_loss"] = placeholder
