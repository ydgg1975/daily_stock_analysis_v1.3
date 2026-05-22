# -*- coding: utf-8 -*-
"""Stock utility endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.stocks import (
    ExtractFromImageResponse,
    ExtractItem,
    KLineData,
    StockChartAnalysisResponse,
    StockHistoryResponse,
    StockQuote,
)
from src.services.image_stock_extractor import (
    ALLOWED_MIME,
    MAX_SIZE_BYTES,
    extract_stock_codes_from_image,
)
from src.services.import_parser import (
    MAX_FILE_BYTES,
    parse_import_from_bytes,
    parse_import_from_text,
)
from src.services.stock_service import StockService

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_MIME_STR = ", ".join(sorted(ALLOWED_MIME))


@router.post(
    "/extract-from-image",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "추출 성공"},
        400: {"description": "이미지 요청 오류", "model": ErrorResponse},
        500: {"description": "서버 내부 오류", "model": ErrorResponse},
    },
    summary="이미지에서 종목 코드 추출",
    description="업로드한 스크린샷 또는 이미지를 Vision LLM으로 분석해 종목 코드를 추출합니다. JPEG, PNG, WebP, GIF를 지원하며 최대 크기는 5MB입니다.",
)
def extract_from_image(
    file: Optional[UploadFile] = File(None, description="분석할 이미지 파일"),
    include_raw: bool = Query(False, description="원본 LLM 응답 포함 여부"),
) -> ExtractFromImageResponse:
    """Extract stock codes from an uploaded image."""
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": "multipart/form-data의 file 필드로 이미지를 업로드하세요."},
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_type",
                "message": f"지원하지 않는 이미지 형식입니다: {content_type}. 허용 형식: {ALLOWED_MIME_STR}",
            },
        )

    try:
        data = file.file.read(MAX_SIZE_BYTES)
        if file.file.read(1):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"이미지는 {MAX_SIZE_BYTES // (1024 * 1024)}MB 이하만 업로드할 수 있습니다.",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("failed to read uploaded image: %s", e)
        raise HTTPException(
            status_code=400,
            detail={"error": "read_failed", "message": "업로드한 이미지 파일을 읽지 못했습니다."},
        )

    try:
        items, raw_text = extract_stock_codes_from_image(data, content_type)
        extract_items = [ExtractItem(code=code, name=name, confidence=conf) for code, name, conf in items]
        codes = [i.code for i in extract_items]
        return ExtractFromImageResponse(
            codes=codes,
            items=extract_items,
            raw_text=raw_text if include_raw else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "extract_failed", "message": str(e)})
    except Exception as e:
        logger.error("image extraction failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": "이미지에서 종목 코드를 추출하지 못했습니다."},
        )


@router.post(
    "/parse-import",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "가져오기 파싱 성공"},
        400: {"description": "요청 또는 파싱 오류", "model": ErrorResponse},
        500: {"description": "서버 내부 오류", "model": ErrorResponse},
    },
    summary="CSV, Excel, 텍스트에서 종목 코드 추출",
    description="CSV, Excel 파일 또는 텍스트 입력에서 종목 코드를 추출합니다. 파일은 최대 2MB, 텍스트 입력은 최대 100KB를 권장합니다.",
)
async def parse_import(request: Request) -> ExtractFromImageResponse:
    """Parse stock codes from uploaded files or JSON text."""
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as e:
            logger.warning("[parse_import] JSON parse failed: %s", e)
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_json", "message": f"JSON 파싱에 실패했습니다: {e}"},
            )
        text = body.get("text") if isinstance(body, dict) else None
        if not text or not isinstance(text, str):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": 'JSON 본문에 {"text": "..."} 형식의 문자열을 넣어주세요.'},
            )
        try:
            items = parse_import_from_text(text)
        except ValueError as e:
            logger.warning(
                "[parse_import] parse_import_from_text failed: text_bytes=%d, error=%s",
                len(text.encode("utf-8")),
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    elif "multipart" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file or not hasattr(file, "read"):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "multipart/form-data의 file 필드로 파일을 업로드하세요."},
            )
        file_size = getattr(file, "size", None)
        if isinstance(file_size, int) and file_size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"파일은 {MAX_FILE_BYTES // (1024 * 1024)}MB 이하만 업로드할 수 있습니다.",
                },
            )
        try:
            data = file.file.read(MAX_FILE_BYTES)
            if file.file.read(1):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "file_too_large",
                        "message": f"파일은 {MAX_FILE_BYTES // (1024 * 1024)}MB 이하만 업로드할 수 있습니다.",
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            filename = getattr(file, "filename", None) or ""
            logger.warning("[parse_import] file read failed: filename=%r, error=%s", filename, e)
            raise HTTPException(
                status_code=400,
                detail={"error": "read_failed", "message": "업로드한 파일을 읽지 못했습니다."},
            )
        filename = getattr(file, "filename", None) or ""
        try:
            items = parse_import_from_bytes(data, filename=filename)
        except ValueError as e:
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            logger.warning(
                "[parse_import] parse_import_from_bytes failed: filename=%r, ext=%r, bytes=%d, error=%s",
                filename,
                ext,
                len(data),
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": 'multipart/form-data file 업로드 또는 application/json {"text": "..."} 요청을 사용하세요.',
            },
        )

    extract_items = [ExtractItem(code=code, name=name, confidence=conf) for code, name, conf in items]
    codes = list(dict.fromkeys(i.code for i in extract_items if i.code))
    return ExtractFromImageResponse(codes=codes, items=extract_items, raw_text=None)


@router.get(
    "/{stock_code}/quote",
    response_model=StockQuote,
    responses={
        200: {"description": "실시간 시세"},
        404: {"description": "종목을 찾을 수 없음", "model": ErrorResponse},
        500: {"description": "서버 내부 오류", "model": ErrorResponse},
    },
    summary="종목 실시간 시세 조회",
    description="지정한 종목 코드의 최신 시세를 조회합니다.",
)
def get_stock_quote(stock_code: str) -> StockQuote:
    """Return realtime quote for a stock code."""
    try:
        service = StockService()
        result = service.get_realtime_quote(stock_code)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"종목 시세를 찾을 수 없습니다: {stock_code}"},
            )

        return StockQuote(
            stock_code=result.get("stock_code", stock_code),
            stock_name=result.get("stock_name"),
            current_price=result.get("current_price", 0.0),
            change=result.get("change"),
            change_percent=result.get("change_percent"),
            open=result.get("open"),
            high=result.get("high"),
            low=result.get("low"),
            prev_close=result.get("prev_close"),
            volume=result.get("volume"),
            amount=result.get("amount"),
            update_time=result.get("update_time"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed to fetch realtime quote: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"실시간 시세 조회에 실패했습니다: {str(e)}"},
        )


@router.get(
    "/{stock_code}/chart-analysis",
    response_model=StockChartAnalysisResponse,
    responses={
        200: {"description": "Chart analysis preview"},
        500: {"description": "Server error", "model": ErrorResponse},
    },
    summary="Get stock chart analysis preview",
    description="Return candlestick SVG and chart-analysis metadata for a stock.",
)
def get_stock_chart_analysis(
    stock_code: str,
    days: int = Query(90, ge=30, le=240, description="Recent trading days to analyze"),
    include_svg: bool = Query(True, description="Whether to include the SVG image"),
) -> StockChartAnalysisResponse:
    """Return chart SVG and metadata for Web preview."""
    try:
        from src.agent.tools.analysis_tools import _handle_generate_chart_analysis

        result = _handle_generate_chart_analysis(
            stock_code=stock_code,
            days=days,
            include_svg=include_svg,
        )
        if result.get("error"):
            return StockChartAnalysisResponse(
                stock_code=stock_code,
                source=result.get("source"),
                requested_days=days,
                status="degraded",
                image_format="svg",
                svg=None,
                svg_omitted=not include_svg,
                svg_length=0,
                metadata={},
                reason=result.get("error"),
            )
        return StockChartAnalysisResponse(
            stock_code=result.get("stock_code") or stock_code,
            source=result.get("source"),
            requested_days=int(result.get("requested_days") or days),
            status=result.get("status") or "ok",
            image_format=result.get("image_format") or "svg",
            svg=result.get("svg"),
            svg_omitted=bool(result.get("svg_omitted", not include_svg)),
            svg_length=int(result.get("svg_length") or len(result.get("svg") or "")),
            metadata=result.get("metadata") or {},
            reason=result.get("reason"),
        )
    except Exception as e:
        logger.error("failed to generate chart analysis: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Chart analysis failed: {str(e)}"},
        )


@router.get(
    "/{stock_code}/history",
    response_model=StockHistoryResponse,
    responses={
        200: {"description": "과거 시세 데이터"},
        422: {"description": "지원하지 않는 period 값", "model": ErrorResponse},
        500: {"description": "서버 내부 오류", "model": ErrorResponse},
    },
    summary="종목 과거 시세 조회",
    description="지정한 종목 코드의 과거 K라인 데이터를 조회합니다.",
)
def get_stock_history(
    stock_code: str,
    period: str = Query("daily", description="K라인 주기", pattern="^(daily|weekly|monthly)$"),
    days: int = Query(30, ge=1, le=365, description="조회 일수"),
) -> StockHistoryResponse:
    """Return historical price data for a stock code."""
    try:
        service = StockService()
        result = service.get_history_data(stock_code=stock_code, period=period, days=days)

        data = [
            KLineData(
                date=item.get("date"),
                open=item.get("open"),
                high=item.get("high"),
                low=item.get("low"),
                close=item.get("close"),
                volume=item.get("volume"),
                amount=item.get("amount"),
                change_percent=item.get("change_percent"),
            )
            for item in result.get("data", [])
        ]

        return StockHistoryResponse(
            stock_code=stock_code,
            stock_name=result.get("stock_name"),
            period=period,
            data=data,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "unsupported_period", "message": str(e)},
        )
    except Exception as e:
        logger.error("failed to fetch historical quote: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"과거 시세 조회에 실패했습니다: {str(e)}"},
        )
