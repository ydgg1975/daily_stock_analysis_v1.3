# -*- coding: utf-8 -*-
"""Common API response schemas."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class RootResponse(BaseModel):
    """API root route response."""

    message: str = Field(..., description="API 실행 상태 메시지", example="Daily Stock Analysis API is running")
    version: Optional[str] = Field(None, description="API 버전", example="1.0.0")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "message": "Daily Stock Analysis API is running",
            "version": "1.0.0",
        }
    })


class HealthResponse(BaseModel):
    """Health-check response."""

    status: str = Field(..., description="서비스 상태", example="ok")
    timestamp: Optional[str] = Field(None, description="타임스탬프")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "ok",
            "timestamp": "2024-01-01T12:00:00",
        }
    })


class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(..., description="오류 유형", example="validation_error")
    message: str = Field(..., description="오류 상세 메시지", example="요청 파라미터가 올바르지 않습니다.")
    detail: Optional[Any] = Field(None, description="추가 오류 정보")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": "not_found",
            "message": "리소스를 찾을 수 없습니다.",
            "detail": None,
        }
    })


class SuccessResponse(BaseModel):
    """Generic success response."""

    success: bool = Field(True, description="성공 여부")
    message: Optional[str] = Field(None, description="성공 메시지")
    data: Optional[Any] = Field(None, description="응답 데이터")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "message": "작업이 성공했습니다.",
            "data": None,
        }
    })
