# -*- coding: utf-8 -*-
"""Backtest endpoints."""

from __future__ import annotations

import logging
from typing import Callable, Optional, Type, TypeVar

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from api.deps import get_database_manager
from api.v1.schemas.backtest import (
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestRunHistoryResponse,
    BacktestSampleStatusResponse,
    BacktestClearResponse,
    BacktestCodeRequest,
    BacktestResultItem,
    BacktestResultsResponse,
    PerformanceMetrics,
    PrepareBacktestSamplesRequest,
    PrepareBacktestSamplesResponse,
    RuleBacktestDetailResponse,
    RuleBacktestHistoryItem,
    RuleBacktestHistoryResponse,
    RuleBacktestStatusResponse,
    RuleBacktestCancelResponse,
    RuleBacktestParseRequest,
    RuleBacktestParseResponse,
    RuleBacktestRunRequest,
    RuleBacktestRunResponse,
)
from api.v1.schemas.common import ErrorResponse
from src.services.backtest_service import BacktestService
from src.services.rule_backtest_service import RuleBacktestService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)
router = APIRouter()
ResponseT = TypeVar("ResponseT")


def _build_model(model_cls: Type[ResponseT], data: dict) -> ResponseT:
    return model_cls(**data)


def _build_models(model_cls: Type[ResponseT], items: list[dict]) -> list[ResponseT]:
    return [_build_model(model_cls, item) for item in items]


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


def _run_endpoint(
    action_label: str,
    operation: Callable[[], ResponseT],
    *,
    allow_validation_error: bool = False,
) -> ResponseT:
    try:
        return operation()
    except HTTPException:
        raise
    except ValueError as exc:
        if allow_validation_error:
            raise _validation_error(exc) from exc
        raise _internal_error(action_label, exc) from exc
    except Exception as exc:
        raise _internal_error(action_label, exc) from exc


# ------------------ 普通回测接口，使用 BacktestService ------------------

@router.post(
    "/run",
    response_model=BacktestRunResponse,
    responses={
        200: {"description": "历史分析评估执行完成"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="运行历史分析评估",
    description="对历史分析记录做事后信号评估，并写入 backtest_results/backtest_summaries",
)
def run_backtest(request: BacktestRunRequest, db_manager: DatabaseManager = Depends(get_database_manager)) -> BacktestRunResponse:
    def _operation() -> BacktestRunResponse:
        service = BacktestService(db_manager)
        stats = service.run_backtest(
            code=request.code,
            force=request.force,
            eval_window_days=request.eval_window_days,
            min_age_days=request.min_age_days,
            limit=request.limit,
        )
        return BacktestRunResponse(**stats)
    return _run_endpoint("回测执行失败", _operation)


@router.post(
    "/prepare-samples",
    response_model=PrepareBacktestSamplesResponse,
    responses={
        200: {"description": "历史分析评估样本准备完成"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="准备历史分析评估样本",
    description="按股票代码准备可用于历史分析评估的分析样本，并持久化到 analysis_history。",
)
def prepare_backtest_samples(request: PrepareBacktestSamplesRequest, db_manager: DatabaseManager = Depends(get_database_manager)) -> PrepareBacktestSamplesResponse:
    def _operation() -> PrepareBacktestSamplesResponse:
        service = BacktestService(db_manager)
        stats = service.prepare_backtest_samples(
            code=request.code,
            sample_count=request.sample_count,
            eval_window_days=request.eval_window_days,
            min_age_days=request.min_age_days,
            force_refresh=request.force_refresh,
        )
        return PrepareBacktestSamplesResponse(**stats)
    return _run_endpoint("准备回测样本失败", _operation, allow_validation_error=True)


@router.get(
    "/sample-status",
    response_model=BacktestSampleStatusResponse,
    responses={
        200: {"description": "样本状态"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取历史分析评估样本状态",
)
def get_sample_status(code: str = Query(..., description="股票代码"), db_manager: DatabaseManager = Depends(get_database_manager)) -> BacktestSampleStatusResponse:
    def _operation() -> BacktestSampleStatusResponse:
        service = BacktestService(db_manager)
        data = service.get_sample_status(code=code)
        return BacktestSampleStatusResponse(**data)
    return _run_endpoint("查询回测样本状态失败", _operation, allow_validation_error=True)


@router.get(
    "/runs",
    response_model=BacktestRunHistoryResponse,
    responses={
        200: {"description": "回测历史"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取历史分析评估历史",
)
def get_backtest_runs(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestRunHistoryResponse:
    def _operation() -> BacktestRunHistoryResponse:
        service = BacktestService(db_manager)
        data = service.list_backtest_runs(code=code, page=page, limit=limit)
        return BacktestRunHistoryResponse(**data)
    return _run_endpoint("查询回测历史失败", _operation)


@router.get(
    "/results",
    response_model=BacktestResultsResponse,
    responses={
        200: {"description": "回测结果列表"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取历史分析评估结果",
    description="分页获取历史分析评估结果，支持按股票代码过滤",
)
def get_backtest_results(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="评估窗口过滤"),
    run_id: Optional[int] = Query(None, ge=1, description="回测运行ID"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=200, description="每页数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestResultsResponse:
    def _operation() -> BacktestResultsResponse:
        service = BacktestService(db_manager)
        if run_id is not None:
            data = service.get_run_results(run_id=run_id, limit=limit, page=page)
        else:
            data = service.get_recent_evaluations(code=code, eval_window_days=eval_window_days, limit=limit, page=page)
        items = [BacktestResultItem(**item) for item in data.get("items", [])]
        return BacktestResultsResponse(total=int(data.get("total", 0)), page=page, limit=limit, items=items)
    return _run_endpoint("查询回测结果失败", _operation)


@router.post(
    "/samples/clear",
    response_model=BacktestClearResponse,
    responses={
        200: {"description": "回测样本已清理"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="清理历史分析评估样本",
)
def clear_backtest_samples(request: BacktestCodeRequest, db_manager: DatabaseManager = Depends(get_database_manager)) -> BacktestClearResponse:
    def _operation() -> BacktestClearResponse:
        service = BacktestService(db_manager)
        data = service.clear_backtest_samples(code=request.code or "")
        data["message"] = "回测样本已清理"
        return BacktestClearResponse(**data)
    return _run_endpoint("清理回测样本失败", _operation, allow_validation_error=True)


@router.post(
    "/results/clear",
    response_model=BacktestClearResponse,
    responses={
        200: {"description": "回测结果已清理"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="清理历史分析评估结果",
)
def clear_backtest_results(request: BacktestCodeRequest, db_manager: DatabaseManager = Depends(get_database_manager)) -> BacktestClearResponse:
    def _operation() -> BacktestClearResponse:
        service = BacktestService(db_manager)
        data = service.clear_backtest_results(code=request.code or "")
        data["message"] = "回测结果已清理"
        return BacktestClearResponse(**data)
    return _run_endpoint("清理回测结果失败", _operation, allow_validation_error=True)


# ------------------ /rule/* 路由，使用 RuleBacktestService ------------------

@router.post(
    "/rule/parse",
    response_model=RuleBacktestParseResponse,
    responses={
        200: {"description": "策略解析完成"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="解析规则策略",
)
def parse_rule_strategy(request: RuleBacktestParseRequest, db_manager: DatabaseManager = Depends(get_database_manager)) -> RuleBacktestParseResponse:
    def _operation() -> RuleBacktestParseResponse:
        service = RuleBacktestService(db_manager)
        parsed = service.parse_strategy(
            request.strategy_text,
            code=request.code,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
        )
        strategy_spec = parsed.get("strategy_spec") if isinstance(parsed.get("strategy_spec"), dict) else {}
        return RuleBacktestParseResponse(
            code=(strategy_spec.get("symbol") or request.code),
            strategy_text=request.strategy_text,
            parsed_strategy=dict(parsed),
            normalized_strategy_family=str(strategy_spec.get("strategy_type") or parsed.get("strategy_kind") or ""),
            detected_strategy_family=(str(parsed.get("detected_strategy_family")) if parsed.get("detected_strategy_family") else None),
            executable=bool(parsed.get("executable", False)),
            normalization_state=str(parsed.get("normalization_state") or "pending"),
            assumptions=list(parsed.get("assumptions") or []),
            assumption_groups=list(parsed.get("assumption_groups") or []),
            unsupported_reason=(str(parsed.get("unsupported_reason")) if parsed.get("unsupported_reason") else None),
            unsupported_details=list(parsed.get("unsupported_details") or []),
            unsupported_extensions=list(parsed.get("unsupported_extensions") or []),
            core_intent_summary=(str(parsed.get("core_intent_summary")) if parsed.get("core_intent_summary") else None),
            interpretation_confidence=float(parsed.get("interpretation_confidence") or 0.0),
            supported_portion_summary=(str(parsed.get("supported_portion_summary")) if parsed.get("supported_portion_summary") else None),
            rewrite_suggestions=list(parsed.get("rewrite_suggestions") or []),
            parse_warnings=list(parsed.get("parse_warnings") or []),
            confidence=float(parsed.get("confidence") or 0.0),
            needs_confirmation=bool(parsed.get("needs_confirmation") or False),
            ambiguities=list(parsed.get("ambiguities") or []),
            summary=dict(parsed.get("summary") or {}),
            max_lookback=int(parsed.get("max_lookback") or 1),
        )
    return _run_endpoint("解析规则策略失败", _operation, allow_validation_error=True)


@router.post(
    "/rule/run",
    response_model=RuleBacktestRunResponse,
    responses={
        200: {"description": "规则回测已提交或已完成"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="运行确定性规则策略回测",
    description="默认异步提交规则回测任务并快速返回运行 ID；传入 wait_for_completion=true 时阻塞至完成。",
)
def run_rule_backtest(request: RuleBacktestRunRequest, background_tasks: BackgroundTasks, db_manager: DatabaseManager = Depends(get_database_manager)) -> RuleBacktestRunResponse:
    def _operation() -> RuleBacktestRunResponse:
        service = RuleBacktestService(db_manager)
        if request.wait_for_completion:
            data = service.run_backtest(
                code=request.code,
                strategy_text=request.strategy_text,
                parsed_strategy=request.parsed_strategy,
                start_date=request.start_date,
                end_date=request.end_date,
                lookback_bars=request.lookback_bars,
                initial_capital=request.initial_capital,
                fee_bps=request.fee_bps,
                slippage_bps=request.slippage_bps,
                benchmark_mode=request.benchmark_mode,
                benchmark_code=request.benchmark_code,
                confirmed=request.confirmed,
            )
            return _build_model(RuleBacktestRunResponse, data)

        data = service.submit_backtest(
            code=request.code,
            strategy_text=request.strategy_text,
            parsed_strategy=request.parsed_strategy,
            start_date=request.start_date,
            end_date=request.end_date,
            lookback_bars=request.lookback_bars,
            initial_capital=request.initial_capital,
            fee_bps=request.fee_bps,
            slippage_bps=request.slippage_bps,
            benchmark_mode=request.benchmark_mode,
            benchmark_code=request.benchmark_code,
            confirmed=request.confirmed,
        )
        background_tasks.add_task(service.process_submitted_run, int(data["id"]))
        return _build_model(RuleBacktestRunResponse, data)
    return _run_endpoint("规则回测失败", _operation, allow_validation_error=True)


@router.get(
    "/rule/runs",
    response_model=RuleBacktestHistoryResponse,
    responses={
        200: {"description": "规则回测历史"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测历史",
)
def get_rule_backtest_runs(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> RuleBacktestHistoryResponse:
    def _operation() -> RuleBacktestHistoryResponse:
        service = RuleBacktestService(db_manager)
        data = service.list_runs(code=code, page=page, limit=limit)
        items = _build_models(RuleBacktestHistoryItem, data.get("items", []))
        return RuleBacktestHistoryResponse(total=int(data.get("total", 0)), page=page, limit=limit, items=items)
    return _run_endpoint("查询规则回测历史失败", _operation)


@router.get(
    "/rule/runs/{run_id}",
    response_model=RuleBacktestDetailResponse,
    responses={
        200: {"description": "规则回测详情"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测详情",
)
def get_rule_backtest_run(run_id: int, db_manager: DatabaseManager = Depends(get_database_manager)) -> RuleBacktestDetailResponse:
    def _operation() -> RuleBacktestDetailResponse:
        service = RuleBacktestService(db_manager)
        data = service.get_run(run_id)
        if data is None:
            raise _not_found_error("规则回测记录不存在")
        return _build_model(RuleBacktestDetailResponse, data)
    return _run_endpoint("查询规则回测详情失败", _operation)


@router.get(
    "/rule/runs/{run_id}/status",
    response_model=RuleBacktestStatusResponse,
    responses={
        200: {"description": "规则回测状态"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取规则回测状态",
)
def get_rule_backtest_run_status(run_id: int, db_manager: DatabaseManager = Depends(get_database_manager)) -> RuleBacktestStatusResponse:
    def _operation() -> RuleBacktestStatusResponse:
        service = RuleBacktestService(db_manager)
        data = service.get_run_status(run_id)
        if data is None:
            raise _not_found_error("规则回测记录不存在")
        return _build_model(RuleBacktestStatusResponse, data)
    return _run_endpoint("查询规则回测状态失败", _operation)


@router.post(
    "/rule/runs/{run_id}/cancel",
    response_model=RuleBacktestCancelResponse,
    responses={
        200: {"description": "规则回测取消结果"},
        404: {"description": "记录不存在", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="取消规则回测",
    description="对尚未完成的异步规则回测执行 best-effort cancel；若任务已结束，则返回当前最终状态。",
)
def cancel_rule_backtest_run(run_id: int, db_manager: DatabaseManager = Depends(get_database_manager)) -> RuleBacktestCancelResponse:
    def _operation() -> RuleBacktestCancelResponse:
        service = RuleBacktestService(db_manager)
        data = service.cancel_run(run_id)
        if data is None:
            raise _not_found_error("规则回测记录不存在")
        return _build_model(RuleBacktestCancelResponse, data)
    return _run_endpoint("取消规则回测失败", _operation)


@router.get(
    "/performance",
    response_model=PerformanceMetrics,
    responses={
        200: {"description": "整体回测表现"},
        404: {"description": "无回测汇总", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取整体回测表现",
)
def get_overall_performance(
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="评估窗口过滤"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PerformanceMetrics:
    def _operation() -> PerformanceMetrics:
        service = BacktestService(db_manager)
        summary = service.get_summary(scope="overall", code=None, eval_window_days=eval_window_days)
        if summary is None:
            raise _not_found_error("未找到整体回测汇总")
        return PerformanceMetrics(**summary)
    return _run_endpoint("查询整体表现失败", _operation)


@router.get(
    "/performance/{code}",
    response_model=PerformanceMetrics,
    responses={
        200: {"description": "单股回测表现"},
        404: {"description": "无回测汇总", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取单股回测表现",
)
def get_stock_performance(
    code: str,
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="评估窗口过滤"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PerformanceMetrics:
    def _operation() -> PerformanceMetrics:
        service = BacktestService(db_manager)
        summary = service.get_summary(scope="stock", code=code, eval_window_days=eval_window_days)
        if summary is None:
            raise _not_found_error(f"未找到 {code} 的回测汇总")
        return _build_model(PerformanceMetrics, summary)
    return _run_endpoint("查询单股表现失败", _operation)
