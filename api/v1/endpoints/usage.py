# -*- coding: utf-8 -*-
"""LLM usage tracking endpoint."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from api.deps import get_database_manager
from api.v1.schemas.usage import UsageDashboardResponse, UsageSummaryResponse
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))  # Beijing time (UTC+8)

router = APIRouter()

_VALID_PERIODS = {"today", "month", "all"}


def _date_range(period: str):
    """Return (from_dt, to_dt) as naive datetimes in Beijing time (UTC+8)."""
    now = datetime.now(tz=_CST).replace(tzinfo=None)  # naive, Beijing local
    if period == "today":
        from_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        from_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # all
        from_dt = datetime(2000, 1, 1)
    return from_dt, now


def _normalize_period(period: str) -> str:
    return period if period in _VALID_PERIODS else "month"


def _provider_from_model(model: str) -> Optional[str]:
    if not model or "/" not in model:
        return None
    provider, _ = model.split("/", 1)
    return provider or None


def _positive_int(value: Any) -> Optional[int]:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def _context_window_from_info(info: Any) -> Optional[int]:
    if not isinstance(info, dict):
        return None
    for key in ("max_input_tokens", "max_tokens", "context_window"):
        value = _positive_int(info.get(key))
        if value is not None:
            return value
    return None


@lru_cache(maxsize=256)
def _resolve_context_window(model: str) -> Optional[int]:
    if not model:
        return None

    try:
        import litellm  # type: ignore
    except Exception:
        return None

    model_keys = [model]
    if "/" in model:
        model_keys.append(model.split("/", 1)[1])

    get_model_info = getattr(litellm, "get_model_info", None)
    if callable(get_model_info):
        for key in model_keys:
            try:
                context_window = _context_window_from_info(get_model_info(key))
            except Exception:
                context_window = None
            if context_window is not None:
                return context_window

    model_cost = getattr(litellm, "model_cost", {})
    if isinstance(model_cost, dict):
        for key in model_keys:
            context_window = _context_window_from_info(model_cost.get(key))
            if context_window is not None:
                return context_window

    return None


def _context_usage_ratio(total_tokens: int, context_window: Optional[int]) -> Optional[float]:
    if not context_window:
        return None
    return round((total_tokens or 0) / context_window, 4)


def _enrich_model_row(row: dict[str, Any]) -> dict[str, Any]:
    model = str(row.get("model") or "unknown")
    context_window = _resolve_context_window(model)
    max_total_tokens = int(row.get("max_total_tokens") or row.get("total_tokens") or 0)
    return {
        **row,
        "provider": _provider_from_model(model),
        "max_total_tokens": max_total_tokens,
        "context_window": context_window,
        "context_usage_ratio": _context_usage_ratio(max_total_tokens, context_window),
    }


def _enrich_call_record(row: dict[str, Any]) -> dict[str, Any]:
    model = str(row.get("model") or "unknown")
    context_window = _resolve_context_window(model)
    called_at = row.get("called_at")
    if isinstance(called_at, datetime):
        called_at_value = called_at.isoformat()
    else:
        called_at_value = str(called_at or "")
    return {
        **row,
        "called_at": called_at_value,
        "provider": _provider_from_model(model),
        "context_window": context_window,
        "context_usage_ratio": _context_usage_ratio(int(row.get("total_tokens") or 0), context_window),
    }


def _build_summary_payload(period: str, from_dt: datetime, to_dt: datetime, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "period": period,
        "from_date": from_dt.date().isoformat(),
        "to_date": to_dt.date().isoformat(),
        "total_calls": data.get("total_calls", 0),
        "total_prompt_tokens": data.get("total_prompt_tokens", 0),
        "total_completion_tokens": data.get("total_completion_tokens", 0),
        "total_tokens": data.get("total_tokens", 0),
        "by_call_type": data.get("by_call_type", []),
        "by_model": [_enrich_model_row(row) for row in data.get("by_model", [])],
    }


@router.get(
    "/summary",
    response_model=UsageSummaryResponse,
    summary="LLM token usage summary",
    description="Aggregate token consumption by period, call type, and model.",
)
def get_usage_summary(
    period: str = Query("month", description="'today' | 'month' | 'all'"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> UsageSummaryResponse:
    normalized_period = _normalize_period(period)
    from_dt, to_dt = _date_range(normalized_period)
    data = db_manager.get_llm_usage_summary(from_dt, to_dt)
    return UsageSummaryResponse(**_build_summary_payload(normalized_period, from_dt, to_dt, data))


@router.get(
    "/dashboard",
    response_model=UsageDashboardResponse,
    summary="LLM token usage monitoring dashboard",
    description="Return token totals, model/context breakdowns, and recent LLM call records.",
)
def get_usage_dashboard(
    period: str = Query("month", description="'today' | 'month' | 'all'"),
    limit: int = Query(50, ge=1, le=200, description="Recent call records to include"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> UsageDashboardResponse:
    normalized_period = _normalize_period(period)
    from_dt, to_dt = _date_range(normalized_period)
    data = db_manager.get_llm_usage_summary(from_dt, to_dt)
    records = db_manager.get_llm_usage_records(from_dt, to_dt, limit=limit)
    payload = _build_summary_payload(normalized_period, from_dt, to_dt, data)
    payload["recent_calls"] = [_enrich_call_record(row) for row in records]
    return UsageDashboardResponse(**payload)
