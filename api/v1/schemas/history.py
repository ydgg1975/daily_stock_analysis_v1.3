# -*- coding: utf-8 -*-
"""History and report API schemas."""

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HistoryItem(BaseModel):
    """Analysis history summary item."""

    id: Optional[int] = Field(None, description="분석 이력 기본 키 ID")
    query_id: str = Field(..., description="분석 기록에 연결된 query_id. 배치 분석에서는 중복될 수 있습니다.")
    stock_code: str = Field(..., description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    report_type: Optional[str] = Field(None, description="보고서 유형")
    sentiment_score: Optional[int] = Field(None, description="감성 점수. 과거 데이터는 0-100 범위를 벗어날 수 있어 읽을 때 제한하지 않습니다.")
    operation_advice: Optional[str] = Field(None, description="운영 조언")
    created_at: Optional[str] = Field(None, description="생성 시간")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1234,
                "query_id": "abc123",
                "stock_code": "AAPL",
                "stock_name": "Apple",
                "report_type": "detailed",
                "sentiment_score": 75,
                "operation_advice": "hold",
                "created_at": "2024-01-01T12:00:00",
            }
        }


class HistoryListResponse(BaseModel):
    """Analysis history list response."""

    total: int = Field(..., description="전체 기록 수")
    page: int = Field(..., description="현재 페이지")
    limit: int = Field(..., description="페이지당 항목 수")
    items: List[HistoryItem] = Field(default_factory=list, description="기록 목록")

    class Config:
        json_schema_extra = {
            "example": {
                "total": 100,
                "page": 1,
                "limit": 20,
                "items": [],
            }
        }


class DeleteHistoryRequest(BaseModel):
    """Delete history request."""

    record_ids: List[int] = Field(default_factory=list, description="삭제할 분석 이력 기본 키 ID 목록")


class DeleteHistoryResponse(BaseModel):
    """Delete history response."""

    deleted: int = Field(..., description="실제로 삭제된 분석 이력 수")


class NewsIntelItem(BaseModel):
    """News intelligence item."""

    title: str = Field(..., description="뉴스 제목")
    snippet: str = Field("", description="뉴스 요약")
    url: str = Field(..., description="뉴스 링크")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Company reports stronger quarterly revenue",
                "snippet": "Quarterly revenue increased 20% year over year...",
                "url": "https://example.com/news/123",
            }
        }


class NewsIntelResponse(BaseModel):
    """News intelligence response."""

    total: int = Field(..., description="뉴스 수")
    items: List[NewsIntelItem] = Field(default_factory=list, description="뉴스 목록")

    class Config:
        json_schema_extra = {
            "example": {
                "total": 2,
                "items": [],
            }
        }


class ReportMeta(BaseModel):
    """Report metadata."""

    model_config = ConfigDict(protected_namespaces=("model_validate", "model_dump"))

    id: Optional[int] = Field(None, description="분석 이력 기본 키 ID. 이력 보고서에만 포함됩니다.")
    query_id: str = Field(..., description="분석 기록에 연결된 query_id. 배치 분석에서는 중복될 수 있습니다.")
    stock_code: str = Field(..., description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    report_type: Optional[str] = Field(None, description="보고서 유형")
    report_language: Optional[str] = Field(None, description="보고서 출력 언어(zh/en)")
    created_at: Optional[str] = Field(None, description="생성 시간")
    current_price: Optional[float] = Field(None, description="분석 당시 가격")
    change_pct: Optional[float] = Field(None, description="분석 당시 등락률(%)")
    model_used: Optional[str] = Field(None, description="분석에 사용한 LLM 모델")


class ReportSummary(BaseModel):
    """Report summary section."""

    analysis_summary: Optional[str] = Field(None, description="핵심 결론")
    operation_advice: Optional[str] = Field(None, description="운영 조언")
    trend_prediction: Optional[str] = Field(None, description="추세 전망")
    sentiment_score: Optional[int] = Field(None, description="감성 점수. 과거 데이터는 0-100 범위를 벗어날 수 있어 읽을 때 제한하지 않습니다.")
    sentiment_label: Optional[str] = Field(None, description="감성 라벨")


class ReportStrategy(BaseModel):
    """Report strategy price section."""

    ideal_buy: Optional[str] = Field(None, description="이상적인 매수가")
    secondary_buy: Optional[str] = Field(None, description="보조 매수가")
    stop_loss: Optional[str] = Field(None, description="손절가")
    take_profit: Optional[str] = Field(None, description="익절가")


class ReportDetails(BaseModel):
    """Report details section."""

    news_content: Optional[str] = Field(None, description="뉴스 요약")
    raw_result: Optional[Any] = Field(None, description="원본 분석 결과(JSON)")
    context_snapshot: Optional[Any] = Field(None, description="분석 당시 컨텍스트 스냅샷(JSON)")
    financial_report: Optional[Any] = Field(None, description="구조화된 재무 보고서 요약(fundamental_context 기반)")
    dividend_metrics: Optional[Any] = Field(None, description="구조화된 배당 지표(TTM 기준 포함)")
    belong_boards: Optional[Any] = Field(None, description="관련 섹터 목록")
    sector_rankings: Optional[Any] = Field(None, description="섹터 등락 순위 구조({top, bottom})")


class AnalysisReport(BaseModel):
    """Full analysis report."""

    meta: ReportMeta = Field(..., description="메타데이터")
    summary: ReportSummary = Field(..., description="요약 섹션")
    strategy: Optional[ReportStrategy] = Field(None, description="전략 가격 섹션")
    details: Optional[ReportDetails] = Field(None, description="상세 섹션")

    analysis_map: Optional[Any] = Field(None, description="Agent analysis flow map and trace data")
    analysis_confidence: Optional[Any] = Field(None, description="Agent confidence score and quality factors")

    class Config:
        json_schema_extra = {
            "example": {
                "meta": {
                    "query_id": "abc123",
                    "stock_code": "AAPL",
                    "stock_name": "Apple",
                    "report_type": "detailed",
                    "report_language": "en",
                    "created_at": "2024-01-01T12:00:00",
                },
                "summary": {
                    "analysis_summary": "Technical momentum is constructive.",
                    "operation_advice": "hold",
                    "trend_prediction": "bullish",
                    "sentiment_score": 75,
                    "sentiment_label": "positive",
                },
                "strategy": {
                    "ideal_buy": "180.00",
                    "secondary_buy": "175.00",
                    "stop_loss": "170.00",
                    "take_profit": "200.00",
                },
                "details": None,
            }
        }


class MarkdownReportResponse(BaseModel):
    """Markdown report response."""

    content: str = Field(..., description="전체 Markdown 보고서 내용")

    class Config:
        json_schema_extra = {
            "example": {
                "content": "# Apple (AAPL) Analysis Report\n\n> Analysis date: **2024-01-01**\n\n..."
            }
        }
