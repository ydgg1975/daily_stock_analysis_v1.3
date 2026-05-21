# -*- coding: utf-8 -*-
"""
===================================
이력 API
===================================

역할:
1. GET /api/v1/history 이력 목록 조회 API를 제공합니다.
2. GET /api/v1/history/{query_id} 이력 상세 조회 API를 제공합니다.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Body

from api.deps import get_database_manager
from api.v1.schemas.history import (
    HistoryListResponse,
    HistoryItem,
    DeleteHistoryRequest,
    DeleteHistoryResponse,
    NewsIntelItem,
    NewsIntelResponse,
    AnalysisReport,
    ReportMeta,
    ReportSummary,
    ReportStrategy,
    ReportDetails,
    MarkdownReportResponse,
)
from api.v1.schemas.common import ErrorResponse
from src.storage import DatabaseManager
from src.report_language import (
    get_sentiment_label,
    get_localized_stock_name,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from src.services.history_service import HistoryService, MarkdownReportGenerationError
from src.utils.data_processing import (
    normalize_model_used,
    extract_fundamental_detail_fields,
    extract_board_detail_fields,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=HistoryListResponse,
    responses={
        200: {"description": "이력 목록"},
        500: {"description": "서버 오류", "model": ErrorResponse},
    },
    summary="분석 이력 목록 조회",
    description="분석 이력 요약을 페이지 단위로 조회하며 종목 코드와 날짜 범위 필터를 지원합니다."
)
def get_history_list(
    stock_code: Optional[str] = Query(None, description="종목 코드 필터"),
    start_date: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="페이지 번호(1부터 시작)"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 개수"),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> HistoryListResponse:
    """
    분석 이력 목록 조회

    분석 이력 요약을 페이지 단위로 조회하며 종목 코드와 날짜 범위 필터를 지원합니다.

    Args:
        stock_code: 종목 코드 필터
        start_date: 시작일
        end_date: 종료일
        page: 페이지 번호
        limit: 페이지당 개수
        db_manager: 데이터베이스 관리자 의존성

    Returns:
        HistoryListResponse: 이력 목록
    """
    try:
        service = HistoryService(db_manager)

        # Use def instead of async def so FastAPI runs it in the thread pool.
        result = service.get_history_list(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            page=page,
            limit=limit
        )

        # Convert to response model.
        items = [
            HistoryItem(
                id=item.get("id"),
                query_id=item.get("query_id", ""),
                stock_code=item.get("stock_code", ""),
                stock_name=item.get("stock_name"),
                report_type=item.get("report_type"),
                sentiment_score=item.get("sentiment_score"),
                operation_advice=item.get("operation_advice"),
                created_at=item.get("created_at")
            )
            for item in result.get("items", [])
        ]

        return HistoryListResponse(
            total=result.get("total", 0),
            page=page,
            limit=limit,
            items=items
        )

    except Exception as e:
        logger.error(f"이력 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"이력 목록 조회 실패: {str(e)}"
            }
        )


@router.delete(
    "",
    response_model=DeleteHistoryResponse,
    responses={
        200: {"description": "삭제 성공"},
        400: {"description": "요청 파라미터 오류", "model": ErrorResponse},
        500: {"description": "서버 오류", "model": ErrorResponse},
    },
    summary="분석 이력 삭제",
    description="이력 기본 키 ID로 분석 이력을 일괄 삭제합니다."
)
def delete_history_records(
    request: DeleteHistoryRequest = Body(...),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> DeleteHistoryResponse:
    """
    기본 키 ID로 분석 이력을 일괄 삭제합니다.
    """
    record_ids = sorted({record_id for record_id in request.record_ids if record_id is not None})
    if not record_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "message": "record_ids는 비어 있을 수 없습니다."
            }
        )

    try:
        service = HistoryService(db_manager)
        deleted = service.delete_history_records(record_ids)
        return DeleteHistoryResponse(deleted=deleted)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이력 삭제 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"이력 삭제 실패: {str(e)}"
            }
        )


@router.get(
    "/{record_id}",
    response_model=AnalysisReport,
    responses={
        200: {"description": "보고서 상세"},
        404: {"description": "보고서 없음", "model": ErrorResponse},
        500: {"description": "서버 오류", "model": ErrorResponse},
    },
    summary="이력 보고서 상세 조회",
    description="분석 이력 ID 또는 query_id로 전체 분석 보고서를 조회합니다."
)
def get_history_detail(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> AnalysisReport:
    """
    이력 보고서 상세 조회

    분석 이력 기본 키 ID 또는 query_id로 전체 분석 보고서를 조회합니다.
    먼저 기본 키 ID(정수)로 조회하고, 유효한 정수가 아니면 query_id로 조회합니다.

    Args:
        record_id: 분석 이력 기본 키 ID(정수) 또는 query_id(문자열)
        db_manager: 데이터베이스 관리자 의존성

    Returns:
        AnalysisReport: 전체 분석 보고서

    Raises:
        HTTPException: 404 - 보고서 없음
    """
    try:
        service = HistoryService(db_manager)

        # Try integer ID first, fall back to query_id string lookup
        result = service.resolve_and_get_detail(record_id)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"id/query_id={record_id} 인 분석 기록을 찾을 수 없습니다."
                }
            )

        # Extract price information from context_snapshot.
        # Use `is None` instead of `or` so 0.0 is not treated as missing.
        # Do not use `change_60d` as a fallback for intraday change_pct.
        current_price = None
        change_pct = None
        context_snapshot = result.get("context_snapshot")
        if context_snapshot and isinstance(context_snapshot, dict):
            # Prefer enhanced_context.realtime.
            enhanced_context = context_snapshot.get("enhanced_context") or {}
            realtime = enhanced_context.get("realtime") or {}
            current_price = realtime.get("price")
            change_pct = realtime.get("change_pct")

            # Fallback to realtime_quote_raw when missing.
            realtime_quote_raw = context_snapshot.get("realtime_quote_raw")
            if not isinstance(realtime_quote_raw, dict):
                realtime_quote_raw = {}
            if current_price is None:
                current_price = realtime_quote_raw.get("price")
            if change_pct is None:
                change_pct = realtime_quote_raw.get("change_pct")
            if change_pct is None:
                change_pct = realtime_quote_raw.get("pct_chg")

        raw_result = result.get("raw_result")
        if not isinstance(raw_result, dict):
            raw_result = {}
        report_language = normalize_report_language(
            result.get("report_language")
            or raw_result.get("report_language")
            or (
                context_snapshot.get("report_language")
                if isinstance(context_snapshot, dict)
                else None
            )
        )
        stock_name = get_localized_stock_name(
            result.get("stock_name"),
            result.get("stock_code", ""),
            report_language,
        )

        # Build response model.
        meta = ReportMeta(
            id=result.get("id"),
            query_id=result.get("query_id", ""),
            stock_code=result.get("stock_code", ""),
            stock_name=stock_name,
            report_type=result.get("report_type"),
            report_language=report_language,
            created_at=result.get("created_at"),
            current_price=current_price,
            change_pct=change_pct,
            model_used=normalize_model_used(result.get("model_used"))
        )

        summary = ReportSummary(
            analysis_summary=result.get("analysis_summary"),
            operation_advice=localize_operation_advice(
                result.get("operation_advice"),
                report_language,
            ),
            trend_prediction=localize_trend_prediction(
                result.get("trend_prediction"),
                report_language,
            ),
            sentiment_score=result.get("sentiment_score"),
            sentiment_label=(
                get_sentiment_label(result.get("sentiment_score"), report_language)
                if result.get("sentiment_score") is not None
                else result.get("sentiment_label")
            )
        )

        strategy = ReportStrategy(
            ideal_buy=result.get("ideal_buy"),
            secondary_buy=result.get("secondary_buy"),
            stop_loss=result.get("stop_loss"),
            take_profit=result.get("take_profit")
        )

        fallback_fundamental = db_manager.get_latest_fundamental_snapshot(
            query_id=result.get("query_id", ""),
            code=result.get("stock_code", ""),
        )
        extracted_fundamental = extract_fundamental_detail_fields(
            context_snapshot=result.get("context_snapshot"),
            fallback_fundamental_payload=fallback_fundamental,
        )
        extracted_boards = extract_board_detail_fields(
            context_snapshot=result.get("context_snapshot"),
            fallback_fundamental_payload=fallback_fundamental,
        )

        details = ReportDetails(
            news_content=result.get("news_content"),
            raw_result=result.get("raw_result"),
            context_snapshot=result.get("context_snapshot"),
            financial_report=extracted_fundamental.get("financial_report"),
            dividend_metrics=extracted_fundamental.get("dividend_metrics"),
            belong_boards=extracted_boards.get("belong_boards"),
            sector_rankings=extracted_boards.get("sector_rankings"),
        )

        return AnalysisReport(
            meta=meta,
            summary=summary,
            strategy=strategy,
            details=details
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이력 상세 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"이력 상세 조회 실패: {str(e)}"
            }
        )


@router.get(
    "/{record_id}/news",
    response_model=NewsIntelResponse,
    responses={
        200: {"description": "뉴스 정보 목록"},
        500: {"description": "서버 오류", "model": ErrorResponse},
    },
    summary="이력 보고서 관련 뉴스 조회",
    description="분석 이력 ID로 관련 뉴스 정보를 조회합니다. 비어 있어도 200을 반환합니다."
)
def get_history_news(
    record_id: str,
    limit: int = Query(20, ge=1, le=100, description="반환 개수 제한"),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> NewsIntelResponse:
    """
    이력 보고서 관련 뉴스 조회

    분석 이력 ID 또는 query_id로 관련 뉴스 정보를 조회합니다.
    Internally resolves record_id to query_id.

    Args:
        record_id: 분석 이력 기본 키 ID(정수) 또는 query_id(문자열)
        limit: 반환 개수 제한
        db_manager: 데이터베이스 관리자 의존성

    Returns:
        NewsIntelResponse: 뉴스 정보 목록
    """
    try:
        service = HistoryService(db_manager)
        items = service.resolve_and_get_news(record_id=record_id, limit=limit)

        response_items = [
            NewsIntelItem(
                title=item.get("title", ""),
                snippet=item.get("snippet"),
                url=item.get("url", "")
            )
            for item in items
        ]

        return NewsIntelResponse(
            total=len(response_items),
            items=response_items
        )

    except Exception as e:
        logger.error(f"뉴스 정보 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"뉴스 정보 조회 실패: {str(e)}"
            }
        )


@router.get(
    "/{record_id}/markdown",
    response_model=MarkdownReportResponse,
    responses={
        200: {"description": "Markdown 형식 보고서"},
        404: {"description": "보고서 없음", "model": ErrorResponse},
        500: {"description": "서버 오류", "model": ErrorResponse},
    },
    summary="이력 보고서 Markdown 형식 조회",
    description="분석 이력 ID로 Markdown 형식의 전체 분석 보고서를 조회합니다."
)
def get_history_markdown(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> MarkdownReportResponse:
    """
    이력 보고서의 Markdown 형식 내용을 조회합니다.

    분석 이력 ID 또는 query_id로 알림 전송 형식과 같은 Markdown 보고서를 생성합니다.

    Args:
        record_id: 분석 이력 기본 키 ID(정수) 또는 query_id(문자열)
        db_manager: 데이터베이스 관리자 의존성

    Returns:
        MarkdownReportResponse: Markdown 형식 전체 보고서

    Raises:
        HTTPException: 404 - 보고서 없음
        HTTPException: 500 - 보고서 생성 실패(서버 내부 오류)
    """
    service = HistoryService(db_manager)

    try:
        markdown_content = service.get_markdown_report(record_id)
    except MarkdownReportGenerationError as e:
        logger.error(f"Markdown report generation failed for {record_id}: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "generation_failed",
                "message": f"Markdown 보고서 생성 실패: {e.message}"
            }
        )
    except Exception as e:
        logger.error(f"Markdown 보고서 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Markdown 보고서 조회 실패: {str(e)}"
            }
        )

    if markdown_content is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"id/query_id={record_id} 인 분석 기록을 찾을 수 없습니다."
            }
        )

    return MarkdownReportResponse(content=markdown_content)
