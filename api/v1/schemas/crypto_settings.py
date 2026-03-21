# -*- coding: utf-8 -*-
"""Pydantic schemas for crypto settings endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CryptoSettingItem(BaseModel):
    """A single crypto setting key-value pair."""

    key: str
    value: str
    raw_value_exists: bool = True
    schema_info: Optional[Dict[str, Any]] = None


class CryptoSettingsResponse(BaseModel):
    """Response for GET /api/v1/crypto/settings."""

    config_version: str = ""
    items: List[CryptoSettingItem] = Field(default_factory=list)
    updated_at: Optional[str] = None


class CryptoSettingUpdateItem(BaseModel):
    """A single setting to update."""

    key: str
    value: str


class UpdateCryptoSettingsRequest(BaseModel):
    """Request for PUT /api/v1/crypto/settings."""

    config_version: str = Field(..., description="Current config version for optimistic concurrency")
    items: List[CryptoSettingUpdateItem] = Field(..., min_length=1)
    reload_now: bool = Field(True, description="Reload runtime config immediately after save")


class UpdateCryptoSettingsResponse(BaseModel):
    """Response for PUT /api/v1/crypto/settings."""

    success: bool = True
    config_version: str = ""
    updated_keys: List[str] = Field(default_factory=list)
    issues: List[Dict[str, Any]] = Field(default_factory=list)
