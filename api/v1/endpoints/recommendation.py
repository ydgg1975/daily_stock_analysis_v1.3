# -*- coding: utf-8 -*-
"""
===================================
推荐选股 API 端点
===================================

职责：
1. 提交推荐任务（支持文件上传）
2. 查询任务状态
3. 查看推荐历史
"""

import json
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.recommendation import (
    RecommendationResult,
    RecommendHistoryItem,
    RecommendHistoryResponse,
    RecommendTaskAccepted,
    RecommendTaskStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 文件上传限制
_MAX_FILES = 5
_MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
_MAX_URLS = 10
_MAX_NOTE_LEN = 2000
_ALLOWED_EXTENSIONS = (".pdf", ".docx", ".txt", ".md", ".markdown")


@router.post(
    "/recommend",
    response_model=RecommendTaskAccepted,
    responses={
        200: {"description": "推荐任务已接受"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器内部错误", "model": ErrorResponse},
    },
    summary="提交推荐选股任务",
    description="提交推荐任务，支持指定市场、价格区间、舆情 URL 和文件上传。任务异步执行，通过 task_id 查询结果。",
)
async def submit_recommendation(
    markets: str = Form(..., description="逗号分隔市场标识，如 a_share,us,hk"),
    price_min: Optional[float] = Form(None, description="最低价格"),
    price_max: Optional[float] = Form(None, description="最高价格"),
    urls: Optional[str] = Form(None, description='JSON 数组字符串，如 ["https://..."]'),
    note: Optional[str] = Form(None, description="补充说明（上限 2000 字符）"),
    files: List[UploadFile] = File(default=[], description="舆情文件（上限 5 个，每个 2MB）"),
) -> RecommendTaskAccepted:
    """提交推荐选股任务"""
    from src.repositories.recommendation_repo import RecommendationRepository
    from src.services.recommendation_service import (
        RecommendationService,
        RecommendationTaskManager,
    )

    # 1. 参数校验
    market_list = [m.strip() for m in markets.split(",") if m.strip()]
    if not market_list:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "markets 不能为空"})

    valid_markets = {"a_share", "a", "cn", "hk", "hongkong", "us", "usa"}
    for m in market_list:
        if m.lower() not in valid_markets:
            raise HTTPException(
                status_code=400,
                detail={"error": "validation_error", "message": f"不支持的市场: {m}"},
            )

    if price_min is not None and price_max is not None and price_min > price_max:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": "price_min 不能大于 price_max"},
        )

    # 解析 URLs
    url_list: List[str] = []
    if urls:
        try:
            url_list = json.loads(urls)
            if not isinstance(url_list, list):
                url_list = []
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail={"error": "validation_error", "message": "urls 必须是合法的 JSON 数组"},
            )
        if len(url_list) > _MAX_URLS:
            raise HTTPException(
                status_code=400,
                detail={"error": "validation_error", "message": f"URL 数量不能超过 {_MAX_URLS} 条"},
            )

    # 校验 note
    if note and len(note) > _MAX_NOTE_LEN:
        note = note[:_MAX_NOTE_LEN]

    # 校验文件
    if len(files) > _MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": f"文件数量不能超过 {_MAX_FILES} 个"},
        )

    file_data_list = []
    for f in files:
        if not f.filename:
            continue
        lower_name = f.filename.lower()
        if not any(lower_name.endswith(ext) for ext in _ALLOWED_EXTENSIONS):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation_error",
                    "message": f"不支持的文件格式: {f.filename}，支持 {', '.join(_ALLOWED_EXTENSIONS)}",
                },
            )
        content = await f.read()
        if len(content) > _MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail={"error": "validation_error", "message": f"文件 {f.filename} 超过 2MB 限制"},
            )
        file_data_list.append((content, f.filename))

    # 2. 创建任务
    task_id = f"rec_{uuid.uuid4().hex[:12]}"

    repo = RecommendationRepository()
    repo.create(
        task_id=task_id,
        markets=",".join(market_list),
        price_min=price_min,
        price_max=price_max,
        urls=json.dumps(url_list, ensure_ascii=False) if url_list else None,
        note=note,
    )

    # 3. 提交异步任务
    service = RecommendationService()
    task_mgr = RecommendationTaskManager.get_instance()
    task_mgr.submit(
        task_id,
        service.recommend,
        task_id,  # passed as positional *args → recommend(task_id, ...)
        markets=market_list,
        price_min=price_min,
        price_max=price_max,
        urls=url_list if url_list else None,
        files=file_data_list if file_data_list else None,
        note=note,
    )

    return RecommendTaskAccepted(
        task_id=task_id,
        status="pending",
        message="推荐任务已提交",
    )


@router.get(
    "/status/{task_id}",
    response_model=RecommendTaskStatus,
    responses={
        200: {"description": "任务状态"},
        404: {"description": "任务不存在", "model": ErrorResponse},
    },
    summary="查询推荐任务状态",
)
def get_recommendation_status(task_id: str) -> RecommendTaskStatus:
    """查询推荐任务的执行状态与结果"""
    from src.services.recommendation_service import RecommendationTaskManager

    task_mgr = RecommendationTaskManager.get_instance()
    status = task_mgr.get_status(task_id)

    if status is None:
        # 尝试从 DB 加载已完成的任务
        from src.repositories.recommendation_repo import RecommendationRepository
        repo = RecommendationRepository()
        record = repo.get_by_task_id(task_id)
        if record:
            result_data = None
            if record.get("status") == "completed" and record.get("result"):
                try:
                    result_data = RecommendationResult(**json.loads(record["result"]))
                except Exception:
                    result_data = None
            return RecommendTaskStatus(
                task_id=task_id,
                status=record.get("status", "failed"),
                progress=100 if record.get("status") == "completed" else 0,
                result=result_data,
                error=record.get("error"),
            )
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "任务不存在"})

    result_data = None
    if status["status"] == "completed" and status.get("result"):
        try:
            result_data = RecommendationResult(**status["result"])
        except Exception:
            result_data = None

    return RecommendTaskStatus(
        task_id=task_id,
        status=status["status"],
        progress=status.get("progress", 0),
        result=result_data,
        error=status.get("error"),
    )


@router.get(
    "/history",
    response_model=RecommendHistoryResponse,
    summary="查询推荐历史记录",
)
def get_recommendation_history(
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
) -> RecommendHistoryResponse:
    """分页查询推荐历史"""
    from src.repositories.recommendation_repo import RecommendationRepository

    repo = RecommendationRepository()
    items, total = repo.list_history(limit=limit, offset=offset)

    history_items = []
    for item in items:
        stock_count = 0
        if item.get("result"):
            try:
                result_dict = json.loads(item["result"])
                stock_count = len(result_dict.get("stocks", []))
            except Exception:
                pass

        history_items.append(
            RecommendHistoryItem(
                id=item["id"],
                task_id=item["task_id"],
                markets=item["markets"],
                price_min=item.get("price_min"),
                price_max=item.get("price_max"),
                stock_count=stock_count,
                status=item.get("status", "unknown"),
                model_used=item.get("model_used"),
                created_at=item.get("created_at"),
            )
        )

    return RecommendHistoryResponse(
        total=total,
        items=history_items,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{record_id}",
    response_model=RecommendationResult,
    responses={
        200: {"description": "推荐详情"},
        404: {"description": "记录不存在", "model": ErrorResponse},
    },
    summary="获取单条推荐详情",
)
def get_recommendation_detail(record_id: int) -> RecommendationResult:
    """根据记录 ID 获取完整推荐结果"""
    from src.repositories.recommendation_repo import RecommendationRepository

    repo = RecommendationRepository()
    record = repo.get_by_id(record_id)

    if not record:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "记录不存在"})

    if record.get("status") != "completed" or not record.get("result"):
        raise HTTPException(
            status_code=404,
            detail={"error": "not_ready", "message": "推荐结果尚未完成"},
        )

    try:
        result_dict = json.loads(record["result"])
        return RecommendationResult(**result_dict)
    except Exception as e:
        logger.error("解析推荐结果失败: %s", e)
        raise HTTPException(
            status_code=500,
            detail={"error": "parse_error", "message": "推荐结果解析失败"},
        )
