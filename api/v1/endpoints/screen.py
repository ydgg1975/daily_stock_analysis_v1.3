# -*- coding: utf-8 -*-
"""
===================================
AI 选股 API 端点（基于东方财富妙想智能选股）
===================================

职责：
1. 接收自然语言选股条件
2. 复用 miaoxiang_tools 中的 smart_stock_screen 实现
3. 返回结构化选股结果
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agent.tools.miaoxiang_tools import _handle_smart_stock_screen

logger = logging.getLogger(__name__)

router = APIRouter()


class ScreenQueryRequest(BaseModel):
    """AI 选股请求"""
    query: str = Field(..., min_length=1, max_length=500, description="自然语言选股条件，如 '今天涨幅超过5%的A股'")


class ScreenQueryResponse(BaseModel):
    """AI 选股响应"""
    success: bool
    query: str
    results_count: int = 0
    returned_count: int = 0
    data_source: Optional[str] = None
    results: List[Dict[str, Any]] = Field(default_factory=list)
    message: Optional[str] = None
    error: Optional[str] = None


@router.post(
    "/query",
    response_model=ScreenQueryResponse,
    summary="AI 智能选股",
    description="通过自然语言条件调用东方财富妙想 API 筛选股票。需配置 MX_APIKEY。",
)
def screen_query(payload: ScreenQueryRequest) -> ScreenQueryResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="选股条件不能为空")

    logger.info("AI screen query: %s", query)
    result = _handle_smart_stock_screen(query)

    # Error case: MX_APIKEY not configured or all keys failed
    if "error" in result:
        err_msg = result["error"]
        if "not configured" in err_msg or "MX_APIKEY" in err_msg:
            raise HTTPException(
                status_code=503,
                detail="AI 选股功能未启用：请在设置页配置 MX_APIKEY（东方财富妙想 API Key）。",
            )
        return ScreenQueryResponse(
            success=False,
            query=query,
            error=err_msg,
        )

    return ScreenQueryResponse(
        success=bool(result.get("success", False)),
        query=result.get("query", query),
        results_count=int(result.get("results_count", 0) or 0),
        returned_count=int(result.get("returned_count", 0) or 0),
        data_source=result.get("data_source"),
        results=result.get("results", []) or [],
        message=result.get("message"),
    )
