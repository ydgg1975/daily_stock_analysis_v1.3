# -*- coding: utf-8 -*-

"""

===================================

stockshujujiekou

===================================



zhize竊?
1. POST /api/v1/stocks/extract-from-image congtupiantiqustockdaima

2. POST /api/v1/stocks/parse-import jiexi CSV/Excel/jiantieban

3. GET /api/v1/stocks/{code}/quote shishixingqingjiekou

4. GET /api/v1/stocks/{code}/history lishiquotejiekou

"""



import logging

from typing import Optional



from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile



from api.v1.schemas.stocks import (

    ExtractFromImageResponse,

    ExtractItem,

    KLineData,

    StockHistoryResponse,

    StockQuote,

)

from api.v1.schemas.common import ErrorResponse

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



# xuzai /{stock_code} luyouzhiqiandingyi

ALLOWED_MIME_STR = ", ".join(ALLOWED_MIME)





@router.post(

    "/extract-from-image",

    response_model=ExtractFromImageResponse,

    responses={

        200: {"description": "추출된 종목 코드"},

        400: {"description": "유효하지 않은 이미지", "model": ErrorResponse},

        500: {"description": "서버 오류", "model": ErrorResponse},

    },

    summary="이미지에서 종목 코드 추출",

    description="Upload an image and extract stock codes with a Vision LLM. Supports JPEG, PNG, WebP, and GIF up to 5 MB.",

)

def extract_from_image(

    file: Optional[UploadFile] = File(None, description="Image file. Form field name: file"),

    include_raw: bool = Query(False, description="결과에 원본 LLM 응답을 포함할지 여부"),

) -> ExtractFromImageResponse:

    """

    congshangchuandetupianzhongtiqustockdaima竊늮hiyong Vision LLM竊됥?


    biaodanziduanqingshiyong file shangchuantupian?굖ouxianji竊숮emini / Anthropic / OpenAI竊늮hougekeyong竊됥?
    """

    if not file or not file.filename:

        raise HTTPException(

            status_code=400,

            detail={"error": "bad_request", "message": "파일이 제공되지 않았습니다. form-data의 file 필드로 이미지를 업로드하세요."},

        )



    content_type = (file.content_type or "").split(";")[0].strip().lower()

    if content_type not in ALLOWED_MIME:

        raise HTTPException(

            status_code=400,

            detail={

                "error": "unsupported_type",

                "message": f"지원하지 않는 파일 형식입니다: {content_type}. 허용 형식: {ALLOWED_MIME_STR}",

            },

        )



    try:

        # xianduquxiandingdaxiao竊똺aijianchashifouhaiyoushengyu竊늶uyiqingxi竊쉉haochuzejujue竊?
        data = file.file.read(MAX_SIZE_BYTES)

        if file.file.read(1):

            raise HTTPException(

                status_code=400,

                detail={

                    "error": "file_too_large",

                    "message": f"이미지는 {MAX_SIZE_BYTES // (1024 * 1024)}MB를 초과할 수 없습니다.",

                },

            )

    except HTTPException:

        raise

    except Exception as e:

        logger.warning(f"duqushangchuanwenjianshibai: {e}")

        raise HTTPException(

            status_code=400,

            detail={"error": "read_failed", "message": "업로드된 파일을 읽지 못했습니다."},

        )



    try:

        items, raw_text = extract_stock_codes_from_image(data, content_type)

        extract_items = [

            ExtractItem(code=code, name=name, confidence=conf) for code, name, conf in items

        ]

        codes = [i.code for i in extract_items]

        return ExtractFromImageResponse(

            codes=codes,

            items=extract_items,

            raw_text=raw_text if include_raw else None,

        )

    except ValueError as e:

        raise HTTPException(status_code=400, detail={"error": "extract_failed", "message": str(e)})

    except Exception as e:

        logger.error(f"tupiantiqushibai: {e}", exc_info=True)

        raise HTTPException(

            status_code=500,

            detail={"error": "internal_error", "message": "이미지에서 종목 정보를 추출하지 못했습니다."},

        )





@router.post(

    "/parse-import",

    response_model=ExtractFromImageResponse,

    responses={

        200: {"description": "파싱 결과"},

        400: {"description": "데이터가 없거나 파싱에 실패했습니다", "model": ErrorResponse},

        500: {"description": "서버 오류", "model": ErrorResponse},

    },

    summary="CSV/Excel/클립보드 텍스트 파싱",

    description="CSV/Excel 파일 또는 붙여넣은 텍스트에서 종목 코드를 파싱합니다. 파일은 2MB, 텍스트는 100KB까지 지원합니다.",

)

async def parse_import(request: Request) -> ExtractFromImageResponse:

    """

    jiexi CSV/Excel wenjianhuojiantiebanwenben??


    - multipart/form-data + file: shangchuanwenjian

    - application/json + {"text": "..."}: zhantiewenben

    - youxianshiyong file竊똱uotongshitigongzehulve text

    """

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

                detail={"error": "bad_request", "message": "text 값이 없습니다. {\"text\": \"...\"} 형식으로 요청하세요."},

            )

        try:

            items = parse_import_from_text(text)

        except ValueError as e:

            text_bytes = len(text.encode("utf-8"))

            logger.warning(

                "[parse_import] parse_import_from_text failed: text_bytes=%d, error=%s",

                text_bytes,

                e,

            )

            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})

    elif "multipart" in content_type:

        form = await request.form()

        file = form.get("file")

        if not file or not hasattr(file, "read"):

            raise HTTPException(

                status_code=400,

                detail={"error": "bad_request", "message": "파일이 제공되지 않았습니다. form-data의 file 필드를 사용하세요."},

            )

        file_size = getattr(file, "size", None)

        if isinstance(file_size, int) and file_size > MAX_FILE_BYTES:

            raise HTTPException(

                status_code=400,

                detail={

                    "error": "file_too_large",

                    "message": f"wenjianchaoguo {MAX_FILE_BYTES // (1024 * 1024)}MB xianzhi",

                },

            )

        try:

            data = file.file.read(MAX_FILE_BYTES)

            if file.file.read(1):

                raise HTTPException(

                    status_code=400,

                    detail={

                        "error": "file_too_large",

                        "message": f"wenjianchaoguo {MAX_FILE_BYTES // (1024 * 1024)}MB xianzhi",

                    },

                )

        except HTTPException:

            raise

        except Exception as e:

            filename = getattr(file, "filename", None) or ""

            size = getattr(file, "size", None)

            logger.warning(

                "[parse_import] file read failed: filename=%r, size=%s, error=%s",

                filename,

                size,

                e,

            )

            raise HTTPException(

                status_code=400,

                detail={"error": "read_failed", "message": "파일을 읽지 못했습니다."},

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

                "message": "파일 업로드는 multipart/form-data를 사용하고, 텍스트 입력은 application/json으로 {\"text\": \"...\"}를 제출하세요.",

            },

        )



    extract_items = [

        ExtractItem(code=code, name=name, confidence=conf)

        for code, name, conf in items

    ]

    codes = list(dict.fromkeys(i.code for i in extract_items if i.code))

    return ExtractFromImageResponse(codes=codes, items=extract_items, raw_text=None)





@router.get(

    "/{stock_code}/quote",

    response_model=StockQuote,

    responses={

        200: {"description": "quoteshuju"},

        404: {"description": "stockbucunzai", "model": ErrorResponse},

        500: {"description": "fuwuqicuowu", "model": ErrorResponse},

    },

    summary="huoqustockshishixingqing",

    description="huoquzhidingstockdezuixinquoteshuju"

)

def get_stock_quote(stock_code: str) -> StockQuote:

    """

    huoqustockshishixingqing

    

    huoquzhidingstockdezuixinquoteshuju

    

    Args:

        stock_code: stockdaima竊늭u 600519??0700?갂APL竊?
        

    Returns:

        StockQuote: shishixinginputju

        

    Raises:

        HTTPException: 404 - stockbucunzai

    """

    try:

        service = StockService()

        

        # shiyong def erfei async def竊똅astAPI zidongzaixianchengchizhongzhixing

        result = service.get_realtime_quote(stock_code)

        

        if result is None:

            raise HTTPException(

                status_code=404,

                detail={

                    "error": "not_found",

                    "message": f"weizhaodaostock {stock_code} dequoteshuju"

                }

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

            update_time=result.get("update_time")

        )

        

    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"huoqushishixingqingshibai: {e}", exc_info=True)

        raise HTTPException(

            status_code=500,

            detail={

                "error": "internal_error",

                "message": f"실시간 시세 조회에 실패했습니다: {str(e)}"

            }

        )





@router.get(

    "/{stock_code}/history",

    response_model=StockHistoryResponse,

    responses={

        200: {"description": "lishiquoteshuju"},

        422: {"description": "buzhichidezhouqicanshu", "model": ErrorResponse},

        500: {"description": "fuwuqicuowu", "model": ErrorResponse},

    },

    summary="huoqustocklishiquote",

    description="huoquzhidingstockdelishi K xianshuju"

)

def get_stock_history(

    stock_code: str,

    period: str = Query("daily", description="K xianzhouqi", pattern="^(daily|weekly|monthly)$"),

    days: int = Query(30, ge=1, le=365, description="huoqutianshu")

) -> StockHistoryResponse:

    """

    huoqustocklishiquote

    

    huoquzhidingstockdelishi K xianshuju

    

    Args:

        stock_code: stockdaima

        period: K xianzhouqi (daily/weekly/monthly)

        days: huoqutianshu

        

    Returns:

        StockHistoryResponse: lishiquoteshuju

    """

    try:

        service = StockService()

        

        # shiyong def erfei async def竊똅astAPI zidongzaixianchengchizhongzhixing

        result = service.get_history_data(

            stock_code=stock_code,

            period=period,

            days=days

        )

        

        # zhuanhuanweixiangyingmodel

        data = [

            KLineData(

                date=item.get("date"),

                open=item.get("open"),

                high=item.get("high"),

                low=item.get("low"),

                close=item.get("close"),

                volume=item.get("volume"),

                amount=item.get("amount"),

                change_percent=item.get("change_percent")

            )

            for item in result.get("data", [])

        ]

        

        return StockHistoryResponse(

            stock_code=stock_code,

            stock_name=result.get("stock_name"),

            period=period,

            data=data

        )

    

    except ValueError as e:

        # period canshubuzhichidecuowu竊늭u weekly/monthly竊?
        raise HTTPException(

            status_code=422,

            detail={

                "error": "unsupported_period",

                "message": str(e)

            }

        )

    except Exception as e:

        logger.error(f"huoqulishiquoteshibai: {e}", exc_info=True)

        raise HTTPException(

            status_code=500,

            detail={

                "error": "internal_error",

                "message": f"과거 시세 조회에 실패했습니다: {str(e)}"

            }

        )


