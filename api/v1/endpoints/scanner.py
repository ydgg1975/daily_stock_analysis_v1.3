# -*- coding: utf-8 -*-
"""Market scanner endpoints."""

from __future__ import annotations

import logging
from typing import Callable, Optional, Type, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import (
    CurrentUser,
    get_current_user,
    get_current_user_id,
    get_database_manager,
    is_admin_user,
    require_admin_user,
)
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.scanner import (
    ScannerOperationalStatusResponse,
    ScannerRunDetailResponse,
    ScannerRunHistoryResponse,
    ScannerRunRequest,
)
from src.services.market_scanner_ops_service import MarketScannerOperationsService
from src.services.market_scanner_service import MarketScannerService
from src.multi_user import OWNERSHIP_SCOPE_SYSTEM, OWNERSHIP_SCOPE_USER
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)
router = APIRouter()
ResponseT = TypeVar("ResponseT")


def _build_scanner_service(
    db_manager: DatabaseManager,
    current_user: CurrentUser | object | None,
) -> MarketScannerService:
    return MarketScannerService(db_manager, owner_id=get_current_user_id(current_user))


def _build_scanner_ops_service(
    db_manager: DatabaseManager,
    current_user: CurrentUser | object | None,
) -> MarketScannerOperationsService:
    return MarketScannerOperationsService(
        db_manager=db_manager,
        scanner_service=_build_scanner_service(db_manager, current_user),
    )


def _validation_error(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "validation_error", "message": str(exc)},
    )


def _not_found_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "not_found", "message": message},
    )


def _internal_error(action_label: str, exc: Exception) -> HTTPException:
    logger.error("%s: %s", action_label, exc, exc_info=True)
    return HTTPException(
        status_code=500,
        detail={"error": "internal_error", "message": f"{action_label}: {str(exc)}"},
    )


def _run_endpoint(action_label: str, operation: Callable[[], ResponseT]) -> ResponseT:
    try:
        return operation()
    except HTTPException:
        raise
    except ValueError as exc:
        raise _validation_error(exc) from exc
    except Exception as exc:
        raise _internal_error(action_label, exc) from exc


def _get_run_detail_payload(
    *,
    service: MarketScannerService,
    run_id: int,
    current_user: CurrentUser | object | None,
) -> dict | None:
    payload = service.get_run_detail(run_id, scope=OWNERSHIP_SCOPE_USER)
    if payload is not None:
        return payload
    if is_admin_user(current_user):
        return service.get_run_detail(run_id, scope=OWNERSHIP_SCOPE_SYSTEM)
    return None


@router.post(
    "/run",
    response_model=ScannerRunDetailResponse,
    responses={
        200: {"description": "扫描完成"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="运行市场扫描器",
    description="按当前市场配置执行一次规则型 Market Scanner，并返回已持久化的观察名单结果。",
)
def run_market_scan(
    request: ScannerRunRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> ScannerRunDetailResponse:
    def _operation() -> ScannerRunDetailResponse:
        service = _build_scanner_ops_service(db_manager, current_user)
        payload = service.run_manual_scan(
            market=request.market,
            profile=request.profile,
            shortlist_size=request.shortlist_size,
            universe_limit=request.universe_limit,
            detail_limit=request.detail_limit,
            request_source="api",
            notify=False,
        )
        return ScannerRunDetailResponse(**payload)

    return _run_endpoint("运行市场扫描失败", _operation)


@router.get(
    "/runs",
    response_model=ScannerRunHistoryResponse,
    responses={
        200: {"description": "扫描历史"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取扫描历史",
)
def get_market_scan_runs(
    market: Optional[str] = Query("cn", description="市场过滤"),
    profile: Optional[str] = Query(None, description="扫描配置过滤"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(10, ge=1, le=50, description="每页数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> ScannerRunHistoryResponse:
    def _operation() -> ScannerRunHistoryResponse:
        service = _build_scanner_service(db_manager, current_user)
        payload = service.list_runs(
            market=market,
            profile=profile,
            page=page,
            limit=limit,
            scope=OWNERSHIP_SCOPE_USER,
        )
        return ScannerRunHistoryResponse(**payload)

    return _run_endpoint("查询扫描历史失败", _operation)


@router.get(
    "/watchlists/today",
    response_model=ScannerRunDetailResponse,
    responses={
        200: {"description": "今日观察名单"},
        404: {"description": "今日尚无观察名单", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取今日观察名单",
)
def get_today_watchlist(
    market: Optional[str] = Query("cn", description="市场过滤"),
    profile: Optional[str] = Query(None, description="扫描配置过滤"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    _: CurrentUser = Depends(require_admin_user),
) -> ScannerRunDetailResponse:
    def _operation() -> ScannerRunDetailResponse:
        service = _build_scanner_service(db_manager, None)
        payload = service.get_today_watchlist(
            market=market or "cn",
            profile=profile,
        )
        if payload is None:
            raise _not_found_error("今日尚无可用 watchlist")
        return ScannerRunDetailResponse(**payload)

    return _run_endpoint("查询今日观察名单失败", _operation)


@router.get(
    "/watchlists/recent",
    response_model=ScannerRunHistoryResponse,
    responses={
        200: {"description": "近期每日观察名单"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取近期每日观察名单",
)
def get_recent_watchlists(
    market: Optional[str] = Query("cn", description="市场过滤"),
    profile: Optional[str] = Query(None, description="扫描配置过滤"),
    limit_days: int = Query(7, ge=1, le=30, description="最近天数"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    _: CurrentUser = Depends(require_admin_user),
) -> ScannerRunHistoryResponse:
    def _operation() -> ScannerRunHistoryResponse:
        service = _build_scanner_service(db_manager, None)
        payload = service.list_recent_watchlists(
            market=market or "cn",
            profile=profile,
            limit_days=limit_days,
        )
        return ScannerRunHistoryResponse(**payload)

    return _run_endpoint("查询近期观察名单失败", _operation)


@router.get(
    "/status",
    response_model=ScannerOperationalStatusResponse,
    responses={
        200: {"description": "Scanner 运行状态"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取 Scanner 运营状态",
)
def get_scanner_operational_status(
    market: Optional[str] = Query("cn", description="市场过滤"),
    profile: Optional[str] = Query(None, description="扫描配置过滤"),
    db_manager: DatabaseManager = Depends(get_database_manager),
    _: CurrentUser = Depends(require_admin_user),
) -> ScannerOperationalStatusResponse:
    def _operation() -> ScannerOperationalStatusResponse:
        service = _build_scanner_ops_service(db_manager, None)
        payload = service.get_operational_status(
            market=market or "cn",
            profile=profile,
        )
        return ScannerOperationalStatusResponse(**payload)

    return _run_endpoint("查询 Scanner 运营状态失败", _operation)


@router.get(
    "/runs/{run_id}",
    response_model=ScannerRunDetailResponse,
    responses={
        200: {"description": "扫描详情"},
        404: {"description": "未找到记录", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取单次扫描详情",
)
def get_market_scan_run(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
    current_user: CurrentUser = Depends(get_current_user),
) -> ScannerRunDetailResponse:
    def _operation() -> ScannerRunDetailResponse:
        service = _build_scanner_service(db_manager, current_user)
        payload = _get_run_detail_payload(
            service=service,
            run_id=run_id,
            current_user=current_user,
        )
        if payload is None:
            raise _not_found_error(f"未找到扫描记录 {run_id}")
        return ScannerRunDetailResponse(**payload)

    return _run_endpoint("查询扫描详情失败", _operation)
