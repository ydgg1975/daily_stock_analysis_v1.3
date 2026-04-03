# -*- coding: utf-8 -*-
"""Admin-only execution log center APIs (D2)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from api.v1.schemas.admin_logs import (
    ExecutionLogSessionDetailModel,
    ExecutionLogSessionListResponse,
)
from src.auth import verify_admin_unlock_token
from src.services.execution_log_service import ExecutionLogService

router = APIRouter()


def require_admin_unlock(
    admin_unlock_token: str | None = Header(default=None, alias="X-Admin-Unlock-Token"),
) -> None:
    """Require a valid admin unlock token for observability details."""
    if admin_unlock_token and verify_admin_unlock_token(admin_unlock_token):
        return
    raise HTTPException(
        status_code=403,
        detail={
            "error": "admin_unlock_required",
            "message": "Admin settings are locked. Verify admin password to access logs center.",
        },
    )


def _parse_optional_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": f"Invalid datetime format: {value}",
            },
        ) from None


@router.get(
    "/sessions",
    response_model=ExecutionLogSessionListResponse,
    summary="List admin execution log sessions",
)
def list_execution_log_sessions(
    stock: Optional[str] = Query(default=None, description="Filter by stock code"),
    status: Optional[str] = Query(default=None, description="Filter by overall status"),
    category: Optional[str] = Query(default=None, description="Filter by phase category"),
    provider: Optional[str] = Query(default=None, description="Filter by provider target"),
    model: Optional[str] = Query(default=None, description="Filter by AI model"),
    channel: Optional[str] = Query(default=None, description="Filter by notification channel"),
    date_from: Optional[str] = Query(default=None, description="ISO datetime start"),
    date_to: Optional[str] = Query(default=None, description="ISO datetime end"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: None = Depends(require_admin_unlock),
):
    service = ExecutionLogService()
    items, total = service.list_sessions(
        stock_code=(stock or "").strip() or None,
        status=(status or "").strip() or None,
        category=(category or "").strip() or None,
        provider=(provider or "").strip() or None,
        model=(model or "").strip() or None,
        channel=(channel or "").strip() or None,
        date_from=_parse_optional_datetime(date_from),
        date_to=_parse_optional_datetime(date_to),
        limit=limit,
        offset=offset,
    )
    return ExecutionLogSessionListResponse(total=total, items=items)


@router.get(
    "/sessions/{session_id}",
    response_model=ExecutionLogSessionDetailModel,
    summary="Get one admin execution log session detail",
)
def get_execution_log_session_detail(
    session_id: str,
    _: None = Depends(require_admin_unlock),
):
    service = ExecutionLogService()
    detail = service.get_session_detail(session_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"Execution log session not found: {session_id}",
            },
        )
    return ExecutionLogSessionDetailModel(**detail)
