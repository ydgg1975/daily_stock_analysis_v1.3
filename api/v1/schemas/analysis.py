# -*- coding: utf-8 -*-
"""Analysis API schemas."""

from enum import Enum
from typing import Any, List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from src.utils.analysis_metadata import SELECTION_SOURCE_PATTERN


class TaskStatusEnum(str, Enum):
    """Task status values."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalyzeRequest(BaseModel):
    """Analysis request parameters."""

    stock_code: Optional[str] = Field(None, description="단일 종목 코드", json_schema_extra={"example": "600519"})
    stock_codes: Optional[List[str]] = Field(None, description="여러 종목 코드. stock_code와 둘 중 하나만 사용합니다.", json_schema_extra={"example": ["600519", "000858"]})
    report_type: str = Field("detailed", description="보고서 유형: simple(간단) / detailed(상세) / full(전체) / brief(요약)", pattern="^(simple|detailed|full|brief)$")
    force_refresh: bool = Field(False, description="캐시를 무시하고 강제로 새로 분석할지 여부")
    async_mode: bool = Field(False, description="비동기 작업으로 실행할지 여부")
    stock_name: Optional[str] = Field(None, description="사용자가 선택한 종목명", json_schema_extra={"example": "贵州茅台"})
    original_query: Optional[str] = Field(None, description="사용자의 원본 입력", json_schema_extra={"example": "茅台"})
    selection_source: Optional[str] = Field(None, description="종목 선택 출처", pattern=SELECTION_SOURCE_PATTERN, json_schema_extra={"example": "autocomplete"})
    notify: bool = Field(True, description="푸시 알림을 보낼지 여부")
    skills: Optional[List[str]] = Field(
        None,
        validation_alias=AliasChoices("skills", "strategies"),
        description="이번 분석에 사용할 strategy skill ID 목록. legacy strategies 필드와 호환됩니다.",
        json_schema_extra={"example": ["bull_trend", "growth_quality"]},
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "report_type": "detailed",
            "force_refresh": False,
            "async_mode": False,
            "stock_name": "贵州茅台",
            "original_query": "茅台",
            "selection_source": "autocomplete",
            "notify": True,
            "skills": ["bull_trend"],
        }
    })


class MarketReviewRequest(BaseModel):
    """Market review trigger parameters."""

    send_notification: bool = Field(True, description="시장 리뷰 완료 후 푸시 알림을 보낼지 여부")


class MarketReviewAccepted(BaseModel):
    """Market review background task accepted response."""

    status: str = Field("accepted", description="제출 상태")
    message: str = Field(..., description="안내 메시지")
    send_notification: bool = Field(..., description="알림 발송 여부")
    task_id: Optional[str] = Field(None, description="작업이 실제로 제출된 경우 반환되는 작업 ID")


class AnalysisResultResponse(BaseModel):
    """Analysis result response."""

    query_id: str = Field(..., description="분석 기록 고유 ID")
    stock_code: str = Field(..., description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    report: Optional[Any] = Field(None, description="분석 보고서")
    created_at: str = Field(..., description="생성 시간")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query_id": "abc123def456",
            "stock_code": "AAPL",
            "stock_name": "Apple",
            "report": {"summary": {"sentiment_score": 75, "operation_advice": "hold"}},
            "created_at": "2024-01-01T12:00:00",
        }
    })


class TaskAccepted(BaseModel):
    """Async task accepted response."""

    task_id: str = Field(..., description="상태 조회에 사용할 작업 ID")
    status: str = Field(..., description="작업 상태", pattern="^(pending|processing)$")
    message: Optional[str] = Field(None, description="안내 메시지")

    model_config = ConfigDict(json_schema_extra={
        "example": {"task_id": "task_abc123", "status": "pending", "message": "Analysis task accepted"}
    })


class BatchTaskAcceptedItem(BaseModel):
    """Successfully submitted item in a batch async task request."""

    task_id: str = Field(..., description="상태 조회에 사용할 작업 ID")
    stock_code: str = Field(..., description="종목 코드")
    status: str = Field(..., description="작업 상태", pattern="^(pending|processing)$")
    message: Optional[str] = Field(None, description="안내 메시지")

    model_config = ConfigDict(json_schema_extra={
        "example": {"task_id": "task_abc123", "stock_code": "AAPL", "status": "pending", "message": "분석 작업이 큐에 추가되었습니다: AAPL"}
    })


class BatchDuplicateTaskItem(BaseModel):
    """Duplicate item in a batch async task request."""

    stock_code: str = Field(..., description="종목 코드")
    existing_task_id: str = Field(..., description="이미 존재하는 작업 ID")
    message: str = Field(..., description="오류 메시지")

    model_config = ConfigDict(json_schema_extra={
        "example": {"stock_code": "AAPL", "existing_task_id": "task_existing_123", "message": "종목 AAPL이 이미 분석 중입니다. (task_id: task_existing_123)"}
    })


class BatchTaskAcceptedResponse(BaseModel):
    """Batch async task accepted response."""

    accepted: List[BatchTaskAcceptedItem] = Field(default_factory=list, description="성공적으로 제출된 작업 목록")
    duplicates: List[BatchDuplicateTaskItem] = Field(default_factory=list, description="중복으로 건너뛴 작업 목록")
    message: str = Field(..., description="요약 메시지")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "accepted": [{"task_id": "task_abc123", "stock_code": "AAPL", "status": "pending", "message": "분석 작업이 큐에 추가되었습니다: AAPL"}],
            "duplicates": [{"stock_code": "MSFT", "existing_task_id": "task_existing_456", "message": "종목 MSFT가 이미 분석 중입니다. (task_id: task_existing_456)"}],
            "message": "1개 작업을 제출했고 1개 중복 작업은 건너뛰었습니다.",
        }
    })


class TaskStatus(BaseModel):
    """Task status model."""

    task_id: str = Field(..., description="작업 ID")
    status: str = Field(..., description="작업 상태", pattern="^(pending|processing|completed|failed)$")
    progress: Optional[int] = Field(None, description="진행률(0-100)", ge=0, le=100)
    result: Optional[AnalysisResultResponse] = Field(None, description="분석 결과. completed 상태에서만 존재합니다.")
    market_review_report: Optional[str] = Field(None, description="시장 리뷰 작업이 반환한 보고서 텍스트")
    error: Optional[str] = Field(None, description="오류 메시지. failed 상태에서만 존재합니다.")
    stock_name: Optional[str] = Field(None, description="종목명")
    original_query: Optional[str] = Field(None, description="사용자의 원본 입력")
    selection_source: Optional[str] = Field(None, description="선택 출처", pattern=SELECTION_SOURCE_PATTERN)
    skills: Optional[List[str]] = Field(None, description="이번 작업에 사용한 strategy skill ID 목록")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "status": "completed",
            "progress": 100,
            "result": None,
            "market_review_report": None,
            "error": None,
            "stock_name": "Apple",
            "original_query": "Apple",
            "selection_source": "autocomplete",
            "skills": ["bull_trend"],
        }
    })


class TaskInfo(BaseModel):
    """Task details model used for task lists and SSE events."""

    task_id: str = Field(..., description="작업 ID")
    stock_code: str = Field(..., description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    status: TaskStatusEnum = Field(..., description="작업 상태")
    progress: int = Field(0, description="진행률(0-100)", ge=0, le=100)
    message: Optional[str] = Field(None, description="상태 메시지")
    report_type: str = Field("detailed", description="보고서 유형")
    created_at: str = Field(..., description="생성 시간")
    started_at: Optional[str] = Field(None, description="시작 시간")
    completed_at: Optional[str] = Field(None, description="완료 시간")
    error: Optional[str] = Field(None, description="오류 메시지. failed 상태에서만 존재합니다.")
    original_query: Optional[str] = Field(None, description="사용자의 원본 입력")
    selection_source: Optional[str] = Field(None, description="선택 출처", pattern=SELECTION_SOURCE_PATTERN)
    skills: Optional[List[str]] = Field(None, description="이번 작업에 사용한 strategy skill ID 목록")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "abc123def456",
            "stock_code": "AAPL",
            "stock_name": "Apple",
            "status": "processing",
            "progress": 50,
            "message": "분석 중...",
            "report_type": "detailed",
            "created_at": "2026-02-05T10:30:00",
            "started_at": "2026-02-05T10:30:01",
            "completed_at": None,
            "error": None,
            "original_query": "Apple",
            "selection_source": "autocomplete",
            "skills": ["bull_trend"],
        }
    })


class TaskListResponse(BaseModel):
    """Task list response."""

    total: int = Field(..., description="전체 작업 수")
    pending: int = Field(..., description="대기 중인 작업 수")
    processing: int = Field(..., description="처리 중인 작업 수")
    tasks: List[TaskInfo] = Field(..., description="작업 목록")

    model_config = ConfigDict(json_schema_extra={
        "example": {"total": 3, "pending": 1, "processing": 2, "tasks": []}
    })


class DuplicateTaskErrorResponse(BaseModel):
    """Duplicate task error response."""

    error: str = Field("duplicate_task", description="오류 유형")
    message: str = Field(..., description="오류 메시지")
    stock_code: str = Field(..., description="종목 코드")
    existing_task_id: str = Field(..., description="이미 존재하는 작업 ID")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": "duplicate_task",
            "message": "종목 AAPL이 이미 분석 중입니다.",
            "stock_code": "AAPL",
            "existing_task_id": "abc123def456",
        }
    })
