# -*- coding: utf-8 -*-
"""Internal AnalysisContextPack schema for Issue #1389 P1."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from src.utils.sanitize import redact_sensitive_mapping


PACK_VERSION = "1.0"


def _validate_iso8601_timestamp(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    if "T" not in value:
        raise ValueError("timestamp must be an ISO 8601 datetime string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("timestamp must be an ISO 8601 datetime string") from exc
    return value


class ContextFieldStatus(str, Enum):
    """Field or block quality state for the first AnalysisContextPack contract."""

    AVAILABLE = "available"
    MISSING = "missing"
    NOT_SUPPORTED = "not_supported"
    FALLBACK = "fallback"
    STALE = "stale"
    ESTIMATED = "estimated"
    PARTIAL = "partial"


class AnalysisSubject(BaseModel):
    """Minimal stock identity slot for P1."""

    code: str
    stock_name: Optional[str] = None
    market: Optional[str] = None


class AnalysisContextItem(BaseModel):
    """Field-level input context item."""

    status: ContextFieldStatus
    value: Optional[Any] = None
    source: Optional[str] = None
    timestamp: Optional[str] = None
    fallback_from: Optional[str] = None
    missing_reason: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_iso8601(cls, value: Optional[str]) -> Optional[str]:
        return _validate_iso8601_timestamp(value)


class AnalysisContextBlock(BaseModel):
    """Block-level grouping for related context items."""

    status: ContextFieldStatus
    items: Dict[str, AnalysisContextItem] = Field(default_factory=dict)
    source: Optional[str] = None
    timestamp: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_iso8601(cls, value: Optional[str]) -> Optional[str]:
        return _validate_iso8601_timestamp(value)


class DataQuality(BaseModel):
    """Container for future quality summaries without P5 scoring semantics."""

    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnalysisContextPack(BaseModel):
    """Versioned internal analysis input envelope."""

    subject: AnalysisSubject
    pack_version: Literal["1.0"] = PACK_VERSION
    phase: Optional[Dict[str, Any]] = None
    blocks: Dict[str, AnalysisContextBlock] = Field(default_factory=dict)
    data_quality: DataQuality = Field(default_factory=DataQuality)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_safe_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe dict with sensitive mapping values redacted."""
        return redact_sensitive_mapping(self.model_dump(mode="json"))
