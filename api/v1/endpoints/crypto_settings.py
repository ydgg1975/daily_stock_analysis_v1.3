# -*- coding: utf-8 -*-
"""Crypto scanner settings endpoints.

Provides a crypto-focused view of the system config, filtering to CRYPTO_* keys only.
Delegates to SystemConfigService for actual persistence and validation.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_system_config_service
from api.v1.schemas.crypto_settings import (
    CryptoSettingItem,
    CryptoSettingsResponse,
    UpdateCryptoSettingsRequest,
    UpdateCryptoSettingsResponse,
)
from src.services.system_config_service import (
    ConfigConflictError,
    ConfigValidationError,
    SystemConfigService,
)

logger = logging.getLogger(__name__)

CRYPTO_KEY_PREFIX = "CRYPTO_"

router = APIRouter()


@router.get("/settings", response_model=CryptoSettingsResponse)
def get_crypto_settings(
    service: SystemConfigService = Depends(get_system_config_service),
) -> CryptoSettingsResponse:
    """Return current crypto config settings (CRYPTO_* keys only)."""
    try:
        payload = service.get_config(include_schema=True)
        all_items = payload.get("items", [])

        crypto_items = []
        for item in all_items:
            key = item.get("key", "")
            if key.startswith(CRYPTO_KEY_PREFIX):
                crypto_items.append(
                    CryptoSettingItem(
                        key=key,
                        value=item.get("value", ""),
                        raw_value_exists=item.get("raw_value_exists", True),
                        schema_info=item.get("schema"),
                    )
                )

        return CryptoSettingsResponse(
            config_version=payload.get("config_version", ""),
            items=crypto_items,
            updated_at=payload.get("updated_at"),
        )
    except Exception as exc:
        logger.error("Failed to load crypto settings: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to load crypto settings",
            },
        )


@router.put("/settings", response_model=UpdateCryptoSettingsResponse)
def update_crypto_settings(
    request: UpdateCryptoSettingsRequest,
    service: SystemConfigService = Depends(get_system_config_service),
) -> UpdateCryptoSettingsResponse:
    """Update crypto config settings. Only CRYPTO_* keys are accepted."""
    for item in request.items:
        if not item.key.startswith(CRYPTO_KEY_PREFIX):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_failed",
                    "message": f"Key '{item.key}' is not a crypto setting (must start with CRYPTO_)",
                },
            )

    try:
        payload = service.update(
            config_version=request.config_version,
            items=[item.model_dump() for item in request.items],
            reload_now=request.reload_now,
        )
        return UpdateCryptoSettingsResponse(
            success=True,
            config_version=payload.get("config_version", ""),
            updated_keys=[item.key for item in request.items],
            issues=payload.get("issues", []),
        )
    except ConfigValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_failed",
                "message": "Crypto settings validation failed",
                "issues": exc.issues,
            },
        )
    except ConfigConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "config_version_conflict",
                "message": "Configuration has changed, please reload and retry",
                "current_config_version": exc.current_version,
            },
        )
    except Exception as exc:
        logger.error("Failed to update crypto settings: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to update crypto settings",
            },
        )
