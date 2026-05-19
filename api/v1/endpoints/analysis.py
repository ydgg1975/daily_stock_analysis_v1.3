# -*- coding: utf-8 -*-

"""

===================================

stockanalysisjiekou

===================================



zhize竊?
1. tigong POST /api/v1/analysis/analyze chufaanalysisjiekou

2. tigong GET /api/v1/analysis/status/{task_id} chaxunrenwuzhuangtaijiekou

3. tigong GET /api/v1/analysis/tasks huoqurenwuliebiaojiekou

4. tigong GET /api/v1/analysis/tasks/stream SSE shishituisongjiekou



texing竊?
- yiburenwuduilie竊쉌enxirenwuyibuzhixing竊똟uzuseqingqiu

- fangchongfutijiao竊쉣iangtongstockdaimain_progressanalysisshifanhui 409

- SSE shishituisong竊쉜enwuzhuangtaibianhuashishinotificationqianduan

"""



import asyncio

import json

import logging

import re

import uuid

from datetime import datetime

from pathlib import Path

from typing import Optional, Union, Dict, Any



from fastapi import APIRouter, HTTPException, Depends, Query, Body

from fastapi.responses import JSONResponse, StreamingResponse



from api.deps import get_config_dep

from api.v1.schemas.analysis import (

    AnalyzeRequest,

    AnalysisResultResponse,

    TaskAccepted,

    BatchTaskAcceptedResponse,

    BatchTaskAcceptedItem,

    BatchDuplicateTaskItem,

    TaskStatus,

    TaskInfo,

    TaskListResponse,

    DuplicateTaskErrorResponse,

    MarketReviewRequest,

    MarketReviewAccepted,

)

from api.v1.schemas.common import ErrorResponse

from api.v1.schemas.history import (

    AnalysisReport,

    ReportMeta,

    ReportSummary,

    ReportStrategy,

    ReportDetails,

)

from data_provider.base import canonical_stock_code, normalize_stock_code

from src.config import Config

from src.core.market_review_lock import (

    MarketReviewExecutionLock as _MarketReviewExecutionLock,

    market_review_lock_path,

    release_market_review_lock as _release_market_review_lock,

    try_acquire_market_review_lock as _try_acquire_market_review_lock,

)

from src.core.market_review_runtime import (

    build_market_review_runtime as _runtime_build_market_review_runtime,

)

from src.report_language import get_localized_stock_name, normalize_report_language

from src.services.name_to_code_resolver import resolve_name_to_code

from src.services.stock_code_utils import is_code_like

from src.services.task_queue import (

    get_task_queue,

    DuplicateTaskError,

    TaskStatus as TaskStatusEnum,

)

from src.utils.data_processing import (

    normalize_model_used,

    parse_json_field,

    extract_fundamental_detail_fields,

    extract_board_detail_fields,

)



logger = logging.getLogger(__name__)



router = APIRouter()



_SUPPORTED_FREE_TEXT_RE = re.compile(r"^[A-Za-z0-9.*\-+\u3400-\u9fff\s]+$")





def _market_review_lock_path(config: Config) -> Path:

    return market_review_lock_path(config)





def _compute_market_review_override_region(config: Config) -> Optional[str]:

    if not getattr(config, "trading_day_check_enabled", True):

        return None



    try:

        from src.core.trading_calendar import (

            get_open_markets_today,

            compute_effective_region,

        )



        open_markets = get_open_markets_today()

        return compute_effective_region(

            getattr(config, "market_review_region", "cn") or "cn",

            open_markets,

        )

    except Exception as exc:

        logger.warning("dapanfupanjiaoyiriguolvshibai竊똞nconfigjixuzhixing: %s", exc)

        return None





def _build_market_review_runtime(config: Config, source_message: Optional[Any] = None) -> tuple[Any, Any, Any]:

    return _runtime_build_market_review_runtime(config, source_message)





def _run_market_review_background(

    send_notification: bool,

    override_region: Optional[str] = None,

    lock_token: Optional[_MarketReviewExecutionLock] = None,

    config: Optional[Config] = None,

    query_id: Optional[str] = None,

) -> None:

    """Run market review after the API response has been accepted."""

    from src.core.market_review import run_market_review



    runtime_config = config or get_config_dep()

    try:

        notifier, analyzer, search_service = _build_market_review_runtime(runtime_config)

        review_kwargs = {

            "notifier": notifier,

            "analyzer": analyzer,

            "search_service": search_service,

            "send_notification": send_notification,

            "override_region": override_region,

        }

        if query_id:

            review_kwargs["query_id"] = query_id

        report = run_market_review(**review_kwargs)

        if not report:

            raise RuntimeError("dapanfupanweifanhuikechijiuhuabaogao")

        return {"result": report}

    finally:

        _release_market_review_lock(lock_token)





def _invalid_analysis_input_error() -> HTTPException:

    return HTTPException(

        status_code=400,

        detail={

            "error": "validation_error",

            "message": "inputruyouxiaodestockdaimahuostockmingcheng",

        },

    )





def _is_obviously_invalid_analysis_input(text: str) -> bool:

    """Reject mixed alphanumeric noise and unsupported symbols early."""

    if not text or is_code_like(text):

        return False



    if not _SUPPORTED_FREE_TEXT_RE.fullmatch(text):

        return True



    has_letters = any(ch.isalpha() and ch.isascii() for ch in text)

    has_digits = any(ch.isdigit() for ch in text)

    return has_letters and has_digits





def _resolve_and_normalize_input(raw_value: str) -> str:

    """

    Resolve and normalize a stock input for analysis requests.



    Code-like values keep the existing canonical path.

    Non-code inputs must resolve to a known stock code. Obvious garbage

    input is rejected before expensive resolver and task-queue work.

    """

    text = (raw_value or "").strip()

    if not text:

        return ""



    if is_code_like(text):

        return canonical_stock_code(text)



    if _is_obviously_invalid_analysis_input(text):

        raise _invalid_analysis_input_error()



    resolved = resolve_name_to_code(text)

    if resolved:

        return canonical_stock_code(resolved)



    raise _invalid_analysis_input_error()





# ============================================================

# POST /analyze - chufastockanalysis

# ============================================================



@router.post(

    "/analyze",

    response_model=AnalysisResultResponse,

    responses={

        200: {"description": "Analysis completed in sync mode", "model": AnalysisResultResponse},

        202: {

            "description": "Analysis task accepted in async mode",

            "model": Union[TaskAccepted, BatchTaskAcceptedResponse],

        },

        400: {"description": "qingqiucanshucuowu", "model": ErrorResponse},

        409: {"description": "Duplicate analysis task rejected", "model": DuplicateTaskErrorResponse},

        500: {"description": "analysisshibai", "model": ErrorResponse},

    },

    summary="chufastockanalysis",

    description="Start an AI stock analysis task. Supports sync and async modes."

)

def trigger_analysis(

        request: AnalyzeRequest,

        config: Config = Depends(get_config_dep)

) -> Union[AnalysisResultResponse, JSONResponse]:

    """

    chufastockanalysis

    

    qidong AI zhinenganalysisrenwu竊똺hichidanzhihuoduozhistockpilianganalysis

    

    liucheng竊?
    1. jiaoyanqingqiucanshu

    2. yibumoshi竊쉒ianchachongfu -> tijiaorenwuduilie -> fanhui 202

    3. tongbumoshi竊쉦hijiezhixinganalysis -> fanhui 200

    

    Args:

        request: analysisqingqiucanshu

        config: configyilai

        

    Returns:

        AnalysisResultResponse: analysisjieguo竊늯ongbumoshi竊?
        TaskAccepted | BatchTaskAcceptedResponse: renwuyijieshou竊늶ibumoshi竊똣anhui 202竊?
        

    Raises:

        HTTPException: 400 - qingqiucanshucuowu

        HTTPException: 409 - stockin_progressanalysiszhong

        HTTPException: 500 - analysisshibai

    """

    # jiaoyanqingqiucanshu

    stock_codes = []

    if request.stock_code:

        stock_codes.append(request.stock_code)

    if request.stock_codes:

        stock_codes.extend(request.stock_codes)



    if not stock_codes:

        raise HTTPException(

            status_code=400,

            detail={

                "error": "validation_error",

                "message": "bixutigong stock_code huo stock_codes canshu"

            }

        )



    # Normalize and de-duplicate inputs while preserving compatibility.

    resolved = [_resolve_and_normalize_input(c) for c in stock_codes]

    

    seen = set()

    unique_codes = []

    for code in resolved:

        if not code:

            continue

        # Use normalize_stock_code to ensure '600519' and '600519.SH' are merged

        norm = normalize_stock_code(code)

        if norm not in seen:

            seen.add(norm)

            unique_codes.append(code)

    

    stock_codes = unique_codes



    # Limit the number of stocks in a single request to prevent DoS

    MAX_BATCH_SIZE = 50

    if len(stock_codes) > MAX_BATCH_SIZE:

        raise HTTPException(

            status_code=400,

            detail={

                "error": "validation_error",

                "message": f"dancianalysisqingqiuzuiduozhichi {MAX_BATCH_SIZE} zhistock"

            }

        )



    if not stock_codes:

        raise HTTPException(

            status_code=400,

            detail={

                "error": "validation_error",

                "message": "stockdaimabunengweikonghuojinbaohankongbaizifu"

            }

        )



    # Sync mode only supports single-stock analysis.

    if not request.async_mode:

        if len(stock_codes) > 1:

            raise HTTPException(

                status_code=400,

                detail={

                    "error": "validation_error",

                    "message": "tongbumoshijinzhichidanzhistockanalysis竊똰ingshiyong async_mode=true jinxingpilianganalysis"

                }

            )

        return _handle_sync_analysis(stock_codes[0], request)



    # Async mode submits one task per stock.

    return _handle_async_analysis_batch(stock_codes, request)





def _handle_async_analysis_batch(

    stock_codes: list,

    request: AnalyzeRequest

) -> JSONResponse:

    """

    Handle asynchronous analysis requests, including batch submission.

    """

    task_queue = get_task_queue()

    

    # Preserve metadata for single-stock requests. For batch requests,

    # only carry through metadata that semantically applies to the whole

    # batch, such as import/image source tracking.

    is_single = len(stock_codes) == 1

    preserve_batch_metadata = request.selection_source in {"import", "image"}



    stock_name = request.stock_name if is_single else None

    original_query = request.original_query if (is_single or preserve_batch_metadata) else None

    selection_source = request.selection_source if (is_single or preserve_batch_metadata) else None

    notify = getattr(request, "notify", True)

    skills = getattr(request, "skills", None)



    submit_kwargs = dict(

        stock_codes=stock_codes,

        stock_name=stock_name,

        original_query=original_query,

        selection_source=selection_source,

        report_type=request.report_type,

        force_refresh=request.force_refresh,

        notify=notify,

    )

    if skills is not None:

        submit_kwargs["skills"] = skills



    accepted_tasks, duplicate_errors = task_queue.submit_tasks_batch(**submit_kwargs)



    accepted = [

        BatchTaskAcceptedItem(

            task_id=task.task_id,

            stock_code=task.stock_code,

            status="pending",

            message=f"analysisrenwuyijiaruduilie: {task.stock_code}",

        )

        for task in accepted_tasks

    ]

    duplicates = [

        BatchDuplicateTaskItem(

            stock_code=dup.stock_code,

            existing_task_id=dup.existing_task_id,

            message=str(dup),

        )

        for dup in duplicate_errors

    ]

    

    # danzhistockqiebeijujue竊쉇aochi 409 jianrongxing

    if len(stock_codes) == 1 and duplicates:

        dup = duplicates[0]

        error_response = DuplicateTaskErrorResponse(

            error="duplicate_task",

            message=dup.message,

            stock_code=dup.stock_code,

            existing_task_id=dup.existing_task_id,

        )

        return JSONResponse(

            status_code=409,

            content=error_response.model_dump()

        )

    

    # danzhistockchenggong竊쉇aochiyuanyouxiangyinggeshijianrongxing

    if len(stock_codes) == 1 and accepted:

        task_accepted = TaskAccepted(

            task_id=accepted[0].task_id,

            status="pending",

            message=accepted[0].message,

        )

        return JSONResponse(

            status_code=202,

            content=task_accepted.model_dump()

        )

    

    # piliang竊쉌anhuihuizongjieguo

    batch_response = BatchTaskAcceptedResponse(

        accepted=accepted,

        duplicates=duplicates,

        message=f"Submitted {len(accepted)} task(s), skipped {len(duplicates)} duplicate task(s)",

    )

    return JSONResponse(

        status_code=202,

        content=batch_response.model_dump()

    )





def _handle_sync_analysis(

    stock_code: str,

    request: AnalyzeRequest

) -> AnalysisResultResponse:

    """

    chulitongbuanalysisqingqiu

    

    zhijiezhixinganalysis竊똡engdaiwanchenghoufanhuijieguo

    """

    import uuid

    from src.services.analysis_service import AnalysisService

    

    query_id = uuid.uuid4().hex

    

    try:

        service = AnalysisService()

        result = service.analyze_stock(

            stock_code=stock_code,

            report_type=request.report_type,

            force_refresh=request.force_refresh,

            query_id=query_id,

            send_notification=getattr(request, "notify", True),

            skills=getattr(request, "skills", None),

        )



        if result is None:

            error_message = service.last_error or f"analysisstock {stock_code} shibai"

            raise HTTPException(

                status_code=500,

                detail={

                    "error": "analysis_failed",

                    "message": error_message,

                }

            )



        # goujianbaogaojiegou

        report_data = result.get("report", {})

        context_snapshot, fundamental_snapshot = _load_sync_fundamental_sources(

            query_id=query_id,

            stock_code=result.get("stock_code", stock_code),

        )

        report = _build_analysis_report(

            report_data,

            query_id,

            stock_code,

            result.get("stock_name"),

            context_snapshot=context_snapshot,

            fallback_fundamental_payload=fundamental_snapshot,

        )



        return AnalysisResultResponse(

            query_id=query_id,

            stock_code=result.get("stock_code", stock_code),

            stock_name=result.get("stock_name"),

            report=report.model_dump() if report else None,

            created_at=datetime.now().isoformat()

        )



    except HTTPException:

        raise

    except Exception as e:

        logger.error(f"analysisshibai: {e}", exc_info=True)

        raise HTTPException(

            status_code=500,

            detail={

                "error": "internal_error",

                "message": f"analysisguochengfashengcuowu: {str(e)}"

            }

        )





# ============================================================

# POST /market-review - chufadapanfupan

# ============================================================



@router.post(

    "/market-review",

    response_model=MarketReviewAccepted,

    status_code=202,

    responses={

        202: {"description": "dapanfupanrenwuyijieshou", "model": MarketReviewAccepted},

        409: {"description": "dapanfupanin_progresszhixing", "model": ErrorResponse},

        500: {"description": "tijiaoshibai", "model": ErrorResponse},

    },

    summary="chufadapanfupan",

    description="tijiaoyigehoutaidapanfupanrenwu竊똣uyong CLI dedapanfupanlianlubingsavebaogao?굁iekouneibujintigongjinchengnei/danjifangzhong竊똱uduoshili竊늕uo Worker/duorongqi竊뎏ushu竊똸ujiehewaibumidengjizhibimianchongfuchufa??",

)

def trigger_market_review(

    request: Optional[MarketReviewRequest] = Body(None),

    config: Config = Depends(get_config_dep),

) -> MarketReviewAccepted:

    """Trigger market review from Web/API without blocking the request."""

    request = request or MarketReviewRequest()



    override_region = _compute_market_review_override_region(config)

    if override_region == "":

        return MarketReviewAccepted(

            status="accepted",

            message="jinridapanfupanrelatedmarketjunweifeijiaoyiri竊똹itiaoguodapanfupan",

            send_notification=request.send_notification,

        )



    lock_token = _try_acquire_market_review_lock(config)

    if lock_token is None:

        raise HTTPException(

            status_code=409,

            detail={

                "error": "duplicate_market_review",

                "message": "dapanfupanin_progresszhixingzhong竊똰inglaterzaishi",

            },

        )



    try:

        task_id = uuid.uuid4().hex

        task = get_task_queue().submit_background_task(

            lambda: _run_market_review_background(

                request.send_notification,

                override_region=override_region,

                lock_token=lock_token,

                config=config,

                query_id=task_id,

            ),

            stock_code="market_review",

            stock_name="dapanfupan",

            message="dapanfupanrenwuyitijiao",

            task_id=task_id,

        )

    except Exception:

        _release_market_review_lock(lock_token)

        raise



    return MarketReviewAccepted(

        status="accepted",

        message="dapanfupanrenwuyitijiao竊똷anchenghouhuisavebaogaobinganconfigtuisongnotification",

        send_notification=request.send_notification,

        task_id=task.task_id,

    )





# ============================================================

# GET /tasks - huoqurenwuliebiao

# ============================================================



@router.get(

    "/tasks",

    response_model=TaskListResponse,

    responses={

        200: {"description": "renwuliebiao"},

    },

    summary="huoquanalysisrenwuliebiao",

    description="huoqudangqiansuoyouanalysisrenwu竊똩eanzhuangtaishaixuan"

)

def get_task_list(

    status: Optional[str] = Query(

        None,

        description="shaixuanzhuangtai竊쉚ending, processing, completed, failed竊늷hichidouhaofengeduoge竊?"

    ),

    limit: int = Query(20, description="fanhuishuliangxianzhi", ge=1, le=100),

) -> TaskListResponse:

    """

    huoquanalysisrenwuliebiao

    

    Args:

        status: zhuangtaishaixuan竊늟exuan竊?
        limit: fanhuishuliangxianzhi

        

    Returns:

        TaskListResponse: renwuliebiaoxiangying

    """

    task_queue = get_task_queue()

    

    # huoqusuoyourenwu

    all_tasks = task_queue.list_all_tasks(limit=limit)

    

    # zhuangtaishaixuan

    if status:

        status_list = [s.strip().lower() for s in status.split(",")]

        all_tasks = [t for t in all_tasks if t.status.value in status_list]

    

    # tongjixinxi

    stats = task_queue.get_task_stats()

    

    # zhuanhuanwei Schema

    task_infos = [

        TaskInfo(

            task_id=t.task_id,

            stock_code=t.stock_code,

            stock_name=t.stock_name,

            status=t.status.value,

            progress=t.progress,

            message=t.message,

            report_type=t.report_type,

            created_at=t.created_at.isoformat(),

            started_at=t.started_at.isoformat() if t.started_at else None,

            completed_at=t.completed_at.isoformat() if t.completed_at else None,

            error=t.error,

            original_query=t.original_query,

            selection_source=t.selection_source,

        )

        for t in all_tasks

    ]

    

    return TaskListResponse(

        total=stats["total"],

        pending=stats["pending"],

        processing=stats["processing"],

        tasks=task_infos,

    )





# ============================================================

# GET /tasks/stream - SSE shishituisong

# ============================================================



@router.get(

    "/tasks/stream",

    responses={

        200: {"description": "SSE shijianliu", "content": {"text/event-stream": {}}},

    },

    summary="renwuzhuangtai SSE liu",

    description="tongguo Server-Sent Events shishituisongrenwuzhuangtaibianhua"

)

async def task_stream():

    """

    SSE renwuzhuangtailiu

    

    shijianleixing竊?
    - connected: lianjiechenggong

    - task_created: xinrenwuchuangjian

    - task_started: renwukaishizhixing

    - task_progress: renwujieduanjindugengxin

    - task_completed: renwuwancheng

    - task_failed: renwushibai

    - heartbeat: xintiao竊늤ei 30 miao竊?
    

    Returns:

        StreamingResponse: SSE shijianliu

    """

    async def event_generator():

        task_queue = get_task_queue()

        event_queue: asyncio.Queue = asyncio.Queue()

        

        # sendlianjiechenggongshijian

        yield _format_sse_event("connected", {"message": "Connected to task stream"})

        

        # senddangqianjinxingzhongderenwu

        pending_tasks = task_queue.list_pending_tasks()

        for task in pending_tasks:

            yield _format_sse_event("task_created", task.to_dict())

        

        # dingyuerenwushijian

        task_queue.subscribe(event_queue)

        

        try:

            while True:

                try:

                    # dengdaishijian竊똠haoshisendxintiao

                    event = await asyncio.wait_for(event_queue.get(), timeout=30)

                    yield _format_sse_event(event["type"], event["data"])

                except asyncio.TimeoutError:

                    # xintiao

                    yield _format_sse_event("heartbeat", {

                        "timestamp": datetime.now().isoformat()

                    })

        except asyncio.CancelledError:

            logger.debug("SSE client disconnected, cancelling event generator")

            raise

        finally:

            task_queue.unsubscribe(event_queue)

    

    return StreamingResponse(

        event_generator(),

        media_type="text/event-stream",

        headers={

            "Cache-Control": "no-cache",

            "Connection": "keep-alive",

            "X-Accel-Buffering": "no",  # jinyong Nginx huanchong

        }

    )





def _format_sse_event(event_type: str, data: Dict[str, Any]) -> str:

    """

    geshihua SSE shijian

    

    Args:

        event_type: shijianleixing

        data: shijianshuju

        

    Returns:

        SSE geshizifuchuan

    """

    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"





# ============================================================

# GET /status/{task_id} - chaxundangerenwuzhuangtai

# ============================================================



@router.get(

    "/status/{task_id}",

    response_model=TaskStatus,

    responses={

        200: {"description": "renwuzhuangtai"},

        404: {"description": "renwubucunzai", "model": ErrorResponse},

    },

    summary="chaxunanalysisrenwuzhuangtai",

    description="genju task_id chaxundangerenwudezhuangtai"

)

def get_analysis_status(task_id: str) -> TaskStatus:

    """

    chaxunanalysisrenwuzhuangtai

    

    youxiancongrenwuduiliechaxun竊똱uguobucunzaizecongshujukuchaxunlishirecord

    

    Args:

        task_id: renwu ID

        

    Returns:

        TaskStatus: renwuzhuangtaixinxi

        

    Raises:

        HTTPException: 404 - renwubucunzai

    """

    # 1. xiancongrenwuduiliechaxun

    task_queue = get_task_queue()

    task = task_queue.get_task(task_id)

    

    if task:

        result: Optional[AnalysisResultResponse] = None

        market_review_report = None



        if task.status == TaskStatusEnum.COMPLETED and isinstance(task.result, dict):

            if task.stock_code == "market_review":

                report_text = task.result.get("result")

                if isinstance(report_text, str) and report_text.strip():

                    market_review_report = report_text

            else:

                try:

                    result = AnalysisResultResponse.model_validate(task.result)

                except Exception:

                    logger.warning(

                        "jiexirenwujieguoshibai竊똦uituiweikongfanhui: task_id=%s",

                        task.task_id,

                    )



        return TaskStatus(

            task_id=task.task_id,

            status=task.status.value,

            progress=task.progress,

            result=result,

            market_review_report=market_review_report,

            error=task.error,

            stock_name=task.stock_name,

            original_query=task.original_query,

            selection_source=task.selection_source,

            skills=getattr(task, "skills", None),

        )

    

    # 2. congshujukuchaxunyiwanchengderecord

    try:

        from src.storage import DatabaseManager

        db = DatabaseManager.get_instance()

        records = db.get_analysis_history(query_id=task_id, limit=1)



        if records:

            record = records[0]

            raw_result = parse_json_field(record.raw_result)

            if getattr(record, "report_type", None) == "market_review":

                market_review_report = None

                if isinstance(raw_result, dict):

                    report_text = raw_result.get("raw_response") or raw_result.get("market_review_report")

                    if isinstance(report_text, str) and report_text.strip():

                        market_review_report = report_text

                if not market_review_report and record.news_content:

                    market_review_report = record.news_content



                return TaskStatus(

                    task_id=task_id,

                    status="completed",

                    progress=100,

                    result=None,

                    market_review_report=market_review_report,

                    error=None,

                    stock_name=record.name,

                )



            model_used = normalize_model_used(

                (raw_result or {}).get("model_used") if isinstance(raw_result, dict) else None

            )

            report_language = normalize_report_language(

                (raw_result or {}).get("report_language") if isinstance(raw_result, dict) else None

            )

            stock_name = get_localized_stock_name(record.name, record.code, report_language)



            # Extract current_price / change_pct from context_snapshot

            current_price = None

            change_pct = None

            skills = None

            context_snapshot = parse_json_field(getattr(record, 'context_snapshot', None))

            if context_snapshot and isinstance(context_snapshot, dict):

                raw_skills = context_snapshot.get("skills")

                if isinstance(raw_skills, list):

                    skills = [str(skill) for skill in raw_skills]

                enhanced_context = context_snapshot.get('enhanced_context') or {}

                realtime = enhanced_context.get('realtime') or {}

                current_price = realtime.get('price')

                change_pct = realtime.get('change_pct')

                realtime_quote_raw = context_snapshot.get('realtime_quote_raw') or {}

                if current_price is None:

                    current_price = realtime_quote_raw.get('price')

                if change_pct is None:

                    change_pct = realtime_quote_raw.get('change_pct')

                if change_pct is None:

                    change_pct = realtime_quote_raw.get('pct_chg')



            # Build report from DB record so completed tasks return real data

            report_dict = AnalysisReport(

                meta=ReportMeta(

                    id=record.id,

                    query_id=task_id,

                    stock_code=record.code,

                    stock_name=stock_name,

                    report_type=getattr(record, 'report_type', None),

                    report_language=report_language,

                    created_at=record.created_at.isoformat() if record.created_at else None,

                    model_used=model_used,

                    current_price=current_price,

                    change_pct=change_pct,

                ),

                summary=ReportSummary(

                    sentiment_score=record.sentiment_score,

                    operation_advice=record.operation_advice,

                    trend_prediction=record.trend_prediction,

                    analysis_summary=record.analysis_summary,

                ),

                strategy=ReportStrategy(

                    ideal_buy=_stringify_report_strategy_value(getattr(record, 'ideal_buy', None)),

                    secondary_buy=_stringify_report_strategy_value(getattr(record, 'secondary_buy', None)),

                    stop_loss=_stringify_report_strategy_value(getattr(record, 'stop_loss', None)),

                    take_profit=_stringify_report_strategy_value(getattr(record, 'take_profit', None)),

                ),

            ).model_dump()

            return TaskStatus(

                task_id=task_id,

                status="completed",

                progress=100,

                result=AnalysisResultResponse(

                    query_id=task_id,

                    stock_code=record.code,

                    stock_name=stock_name,

                    report=report_dict,

                    created_at=record.created_at.isoformat() if record.created_at else datetime.now().isoformat()

                ),

                error=None,

                skills=skills,

            )



    except Exception as e:

        logger.error(f"chaxunrenwuzhuangtaishibai: {e}", exc_info=True)

        raise HTTPException(

            status_code=500,

            detail={

                "error": "internal_error",

                "message": f"chaxunrenwuzhuangtaishibai: {str(e)}"

            }

        )



    # 3. renwubucunzai

    raise HTTPException(

        status_code=404,

        detail={

            "error": "not_found",

            "message": f"renwu {task_id} bucunzaihuoyiguoqi"

        }

    )





# ============================================================

# fuzhuhanshu

# ============================================================



def _load_sync_fundamental_sources(

    query_id: str,

    stock_code: str,

) -> tuple[Optional[Any], Optional[Dict[str, Any]]]:

    """

    Load context_snapshot and fallback fundamental snapshot for sync analyze response.

    """

    try:

        from src.storage import DatabaseManager



        db = DatabaseManager.get_instance()

        records = db.get_analysis_history(query_id=query_id, code=stock_code, limit=1)

        context_snapshot = None

        if records:

            context_snapshot = parse_json_field(getattr(records[0], "context_snapshot", None))



        fallback_fundamental = db.get_latest_fundamental_snapshot(

            query_id=query_id,

            code=stock_code,

        )

        return context_snapshot, fallback_fundamental

    except Exception as e:

        logger.debug(

            "load sync fundamental sources failed (fail-open): query_id=%s stock_code=%s err=%s",

            query_id,

            stock_code,

            e,

        )

        return None, None





def _stringify_report_strategy_value(value: Any) -> Optional[str]:

    if value is None:

        return None

    if isinstance(value, str):

        return value

    return str(value)





def _build_analysis_report(

        report_data: Dict[str, Any],

        query_id: str,

        stock_code: str,

        stock_name: Optional[str] = None,

        context_snapshot: Optional[Any] = None,

        fallback_fundamental_payload: Optional[Dict[str, Any]] = None,

) -> AnalysisReport:

    """

    goujianfuhe API guifandeanalysisbaogao

    

    Args:

        report_data: yuanshibaogaoshuju

        query_id: chaxun ID

        stock_code: stockdaima

        stock_name: stockmingcheng

        context_snapshot: shangxiawenkuaizhao竊늟exuan竊?
        fallback_fundamental_payload: jibenmiankuaizhao payload竊늟exuan竊?
        

    Returns:

        AnalysisReport: jiegouhuadeanalysisbaogao

    """

    meta_data = report_data.get("meta", {})

    summary_data = report_data.get("summary", {})

    strategy_data = report_data.get("strategy", {})

    details_data = report_data.get("details", {})

    report_language = normalize_report_language(

        meta_data.get("report_language")

        or (context_snapshot or {}).get("report_language")

        or getattr(Config.get_instance(), "report_language", "zh")

    )

    localized_stock_name = get_localized_stock_name(

        meta_data.get("stock_name", stock_name),

        meta_data.get("stock_code", stock_code),

        report_language,

    )



    meta = ReportMeta(

        query_id=meta_data.get("query_id", query_id),

        stock_code=meta_data.get("stock_code", stock_code),

        stock_name=localized_stock_name,

        report_type=meta_data.get("report_type", "detailed"),

        report_language=report_language,

        created_at=meta_data.get("created_at", datetime.now().isoformat()),

        current_price=meta_data.get("current_price"),

        change_pct=meta_data.get("change_pct"),

        model_used=normalize_model_used(meta_data.get("model_used")),

    )



    summary = ReportSummary(

        analysis_summary=summary_data.get("analysis_summary"),

        operation_advice=summary_data.get("operation_advice"),

        trend_prediction=summary_data.get("trend_prediction"),

        sentiment_score=summary_data.get("sentiment_score"),

        sentiment_label=summary_data.get("sentiment_label")

    )



    strategy = None

    if strategy_data:

        strategy = ReportStrategy(

            ideal_buy=_stringify_report_strategy_value(strategy_data.get("ideal_buy")),

            secondary_buy=_stringify_report_strategy_value(strategy_data.get("secondary_buy")),

            stop_loss=_stringify_report_strategy_value(strategy_data.get("stop_loss")),

            take_profit=_stringify_report_strategy_value(strategy_data.get("take_profit"))

        )



    extracted_fundamental = extract_fundamental_detail_fields(

        context_snapshot=context_snapshot,

        fallback_fundamental_payload=fallback_fundamental_payload,

    )

    extracted_boards = extract_board_detail_fields(

        context_snapshot=context_snapshot,

        fallback_fundamental_payload=fallback_fundamental_payload,

    )

    details = None

    has_board_details = bool(extracted_boards.get("belong_boards")) or extracted_boards.get("sector_rankings") is not None

    if details_data or any(extracted_fundamental.values()) or has_board_details or context_snapshot is not None:

        details = ReportDetails(

            news_content=details_data.get("news_summary") or details_data.get("news_content"),

            raw_result=details_data,

            context_snapshot=context_snapshot,

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


