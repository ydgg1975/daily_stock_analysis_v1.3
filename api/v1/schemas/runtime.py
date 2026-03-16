from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class RuntimeObjectEnvelopeResponse(BaseModel):
    object_name: str
    schema_version: str
    generated_at: str
    data: Dict[str, Any] = Field(default_factory=dict)


class RuntimeObjectListResponse(BaseModel):
    total: int
    items: List[str] = Field(default_factory=list)
