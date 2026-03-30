# -*- coding: utf-8 -*-
"""System configuration endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from starlette.requests import Request

from api.deps import get_system_config_service
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.system_config import (
    SystemConfigConflictResponse,
    SystemConfigResponse,
    SystemConfigSchemaResponse,
    SystemConfigValidationErrorResponse,
    TestLLMChannelRequest,
    TestLLMChannelResponse,
    UpdateSystemConfigRequest,
    UpdateSystemConfigResponse,
    ValidateSystemConfigRequest,
    ValidateSystemConfigResponse,
)
from src.auth import verify_admin_unlock_token
from src.services.system_config_service import ConfigConflictError, ConfigValidationError, SystemConfigService

logger = logging.getLogger(__name__)

router = APIRouter()


def require_admin_unlock(
    request: Request,
    admin_unlock_token: str | None = Header(default=None, alias="X-Admin-Unlock-Token"),
) -> None:
    """Require a valid admin unlock token for write-sensitive config operations."""
    if admin_unlock_token and verify_admin_unlock_token(admin_unlock_token):
        return

    raise HTTPException(
        status_code=403,
        detail={
            "error": "admin_unlock_required",
            "message": "Admin settings are locked. Verify admin password to continue.",
            "path": str(request.url.path),
        },
    )


@router.get(
    "/config",
    response_model=SystemConfigResponse,
    responses={
        200: {"description": "Configuration loaded"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Get system configuration",
    description="Read current configuration from .env and return raw values.",
)
def get_system_config(
    include_schema: bool = Query(True, description="Whether to include schema metadata"),
    service: SystemConfigService = Depends(get_system_config_service),
) -> SystemConfigResponse:
    """Load and return current system configuration."""
    try:
        payload = service.get_config(include_schema=include_schema)
        return SystemConfigResponse.model_validate(payload)
    except Exception as exc:
        logger.error("Failed to load system configuration: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to load system configuration",
            },
        )


@router.put(
    "/config",
    response_model=UpdateSystemConfigResponse,
    responses={
        200: {"description": "Configuration updated"},
        400: {"description": "Validation failed", "model": SystemConfigValidationErrorResponse},
        403: {"description": "Admin unlock required", "model": ErrorResponse},
        409: {"description": "Version conflict", "model": SystemConfigConflictResponse},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Update system configuration",
    description="Update key-value pairs in .env. Mask token preserves existing secret values.",
)
def update_system_config(
    request: UpdateSystemConfigRequest,
    service: SystemConfigService = Depends(get_system_config_service),
    _: None = Depends(require_admin_unlock),
) -> UpdateSystemConfigResponse:
    """Validate and persist system configuration updates."""
    try:
        payload = service.update(
            config_version=request.config_version,
            items=[item.model_dump() for item in request.items],
            mask_token=request.mask_token,
            reload_now=request.reload_now,
        )
        return UpdateSystemConfigResponse.model_validate(payload)
    except ConfigValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_failed",
                "message": "System configuration validation failed",
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
        logger.error("Failed to update system configuration: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to update system configuration",
            },
        )


@router.post(
    "/config/validate",
    response_model=ValidateSystemConfigResponse,
    responses={
        200: {"description": "Validation completed"},
        403: {"description": "Admin unlock required", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Validate system configuration",
    description="Validate submitted configuration values without writing to .env.",
)
def validate_system_config(
    request: ValidateSystemConfigRequest,
    service: SystemConfigService = Depends(get_system_config_service),
    _: None = Depends(require_admin_unlock),
) -> ValidateSystemConfigResponse:
    """Run pre-save validation only."""
    try:
        payload = service.validate(items=[item.model_dump() for item in request.items])
        return ValidateSystemConfigResponse.model_validate(payload)
    except Exception as exc:
        logger.error("Failed to validate system configuration: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to validate system configuration",
            },
        )


@router.post(
    "/config/llm/test-channel",
    response_model=TestLLMChannelResponse,
    responses={
        200: {"description": "Channel test completed"},
        403: {"description": "Admin unlock required", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Test one LLM channel",
    description="Run a minimal LLM request against one unsaved or saved channel definition.",
)
def test_llm_channel(
    request: TestLLMChannelRequest,
    service: SystemConfigService = Depends(get_system_config_service),
    _: None = Depends(require_admin_unlock),
) -> TestLLMChannelResponse:
    """Validate and test one channel definition without writing `.env`."""
    try:
        payload = service.test_llm_channel(
            name=request.name,
            protocol=request.protocol,
            base_url=request.base_url,
            api_key=request.api_key,
            models=request.models,
            enabled=request.enabled,
            timeout_seconds=request.timeout_seconds,
        )
        return TestLLMChannelResponse.model_validate(payload)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": str(exc),
            },
        )
    except Exception as exc:
        logger.error("Failed to test LLM channel: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to test LLM channel",
            },
        )


@router.get(
    "/config/schema",
    response_model=SystemConfigSchemaResponse,
    responses={
        200: {"description": "Schema loaded"},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Get system configuration schema",
    description="Return categorized field metadata used for dynamic settings form rendering.",
)
def get_system_config_schema(
    service: SystemConfigService = Depends(get_system_config_service),
) -> SystemConfigSchemaResponse:
    """Return schema metadata for system configuration fields."""
    try:
        payload = service.get_schema()
        return SystemConfigSchemaResponse.model_validate(payload)
    except Exception as exc:
        logger.error("Failed to load system configuration schema: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to load system configuration schema",
            },
        )
