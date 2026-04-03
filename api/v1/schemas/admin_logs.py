# -*- coding: utf-8 -*-
"""Schemas for admin execution logs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExecutionLogEventModel(BaseModel):
    id: int
    event_at: Optional[str] = None
    phase: str
    category: Optional[str] = None
    step: Optional[str] = None
    action: Optional[str] = None
    outcome: Optional[str] = None
    reason: Optional[str] = None
    target: Optional[str] = None
    status: str
    truth_level: str
    message: Optional[str] = None
    error_code: Optional[str] = None
    detail: Dict[str, Any] = Field(default_factory=dict)


class ExecutionLogSessionSummaryModel(BaseModel):
    session_id: str
    task_id: Optional[str] = None
    query_id: Optional[str] = None
    analysis_history_id: Optional[int] = None
    code: Optional[str] = None
    name: Optional[str] = None
    overall_status: str
    truth_level: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    readable_summary: Dict[str, Any] = Field(default_factory=dict)


class ExecutionLogSessionDetailModel(ExecutionLogSessionSummaryModel):
    events: List[ExecutionLogEventModel] = Field(default_factory=list)


class ExecutionLogSessionListResponse(BaseModel):
    total: int
    items: List[ExecutionLogSessionSummaryModel] = Field(default_factory=list)
