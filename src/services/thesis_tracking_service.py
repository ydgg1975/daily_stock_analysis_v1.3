# -*- coding: utf-8 -*-
"""Track how a stock thesis changes across analysis runs."""

import json
import logging
from typing import Any, Dict, List, Optional

from src.analyzer import AnalysisResult

logger = logging.getLogger(__name__)

_DECISION_RANK = {"sell": 0, "hold": 1, "buy": 2}


def attach_thesis_tracking(
    result: AnalysisResult,
    db: Any,
    *,
    days: int = 180,
) -> None:
    """Attach thesis comparison metadata to ``result`` using the latest prior row."""
    try:
        previous_records = db.get_analysis_history(
            code=result.code,
            days=days,
            limit=1,
            exclude_query_id=result.query_id,
        )
    except Exception as exc:
        logger.debug("Thesis tracking skipped for %s: %s", result.code, exc)
        return

    previous = previous_records[0] if previous_records else None
    previous_raw = _parse_raw_result(getattr(previous, "raw_result", None)) if previous else {}
    result.thesis_tracking = build_thesis_tracking(result, previous, previous_raw)


def build_thesis_tracking(
    result: AnalysisResult,
    previous_record: Optional[Any],
    previous_raw: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build deterministic thesis tracking metadata from current and previous analyses."""
    previous_raw = previous_raw or {}
    current_thesis = _extract_current_thesis(result)
    current_score = _safe_int(result.sentiment_score)
    current_decision = _normalize_decision(result.decision_type, result.operation_advice)

    if previous_record is None:
        return {
            "version": 1,
            "status": "new",
            "current_thesis": current_thesis,
            "previous_thesis": "",
            "key_changes": ["No previous analysis was found for this stock."],
            "previous_query_id": None,
            "previous_created_at": None,
            "score_delta": None,
            "decision_changed": False,
        }

    previous_score = _safe_int(
        previous_raw.get("sentiment_score", getattr(previous_record, "sentiment_score", None))
    )
    previous_decision = _normalize_decision(
        previous_raw.get("decision_type"),
        previous_raw.get("operation_advice", getattr(previous_record, "operation_advice", "")),
    )
    score_delta = (
        current_score - previous_score
        if current_score is not None and previous_score is not None
        else None
    )
    status = _classify_status(current_decision, previous_decision, score_delta)
    key_changes = _build_key_changes(result, previous_record, previous_raw, score_delta)

    return {
        "version": 1,
        "status": status,
        "current_thesis": current_thesis,
        "previous_thesis": _extract_previous_thesis(previous_record, previous_raw),
        "key_changes": key_changes,
        "previous_query_id": getattr(previous_record, "query_id", None),
        "previous_created_at": (
            previous_record.created_at.isoformat()
            if getattr(previous_record, "created_at", None)
            else None
        ),
        "score_delta": score_delta,
        "decision_changed": current_decision != previous_decision,
    }


def _parse_raw_result(raw_result: Any) -> Dict[str, Any]:
    if isinstance(raw_result, dict):
        return raw_result
    if isinstance(raw_result, str) and raw_result.strip():
        try:
            parsed = json.loads(raw_result)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _extract_current_thesis(result: AnalysisResult) -> str:
    dashboard = result.dashboard or {}
    core = dashboard.get("core_conclusion") if isinstance(dashboard, dict) else {}
    return _first_text(
        getattr(result, "buy_reason", ""),
        core.get("one_sentence") if isinstance(core, dict) else "",
        getattr(result, "analysis_summary", ""),
    )


def _extract_previous_thesis(previous_record: Any, raw_result: Dict[str, Any]) -> str:
    dashboard = raw_result.get("dashboard") if isinstance(raw_result, dict) else {}
    core = dashboard.get("core_conclusion") if isinstance(dashboard, dict) else {}
    return _first_text(
        raw_result.get("buy_reason"),
        core.get("one_sentence") if isinstance(core, dict) else "",
        raw_result.get("analysis_summary"),
        getattr(previous_record, "analysis_summary", ""),
    )


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_decision(decision_type: Any, operation_advice: Any) -> str:
    text = str(decision_type or operation_advice or "").lower()
    if "buy" in text or "买" in text or "加仓" in text:
        return "buy"
    if "sell" in text or "卖" in text or "减仓" in text:
        return "sell"
    return "hold"


def _classify_status(current: str, previous: str, score_delta: Optional[int]) -> str:
    rank_delta = _DECISION_RANK.get(current, 1) - _DECISION_RANK.get(previous, 1)
    if rank_delta <= -2 or (score_delta is not None and score_delta <= -20):
        return "broken"
    if rank_delta < 0 or (score_delta is not None and score_delta <= -10):
        return "weakened"
    if rank_delta > 0 or (score_delta is not None and score_delta >= 10):
        return "strengthened"
    return "maintained"


def _build_key_changes(
    result: AnalysisResult,
    previous_record: Any,
    previous_raw: Dict[str, Any],
    score_delta: Optional[int],
) -> List[str]:
    changes: List[str] = []
    previous_advice = previous_raw.get("operation_advice", getattr(previous_record, "operation_advice", ""))
    if previous_advice and previous_advice != result.operation_advice:
        changes.append(f"Advice changed from {previous_advice} to {result.operation_advice}.")

    previous_trend = previous_raw.get("trend_prediction", getattr(previous_record, "trend_prediction", ""))
    if previous_trend and previous_trend != result.trend_prediction:
        changes.append(f"Trend changed from {previous_trend} to {result.trend_prediction}.")

    if score_delta is not None and score_delta != 0:
        sign = "+" if score_delta > 0 else ""
        changes.append(f"Sentiment score changed by {sign}{score_delta} points.")

    previous_risk = str(previous_raw.get("risk_warning", "") or "").strip()
    current_risk = str(getattr(result, "risk_warning", "") or "").strip()
    if current_risk and current_risk != previous_risk:
        changes.append("Risk warning changed.")

    if not changes:
        changes.append("No material signal change versus the previous analysis.")
    return changes
