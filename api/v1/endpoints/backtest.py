# -*- coding: utf-8 -*-
"""Backtest endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

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
    RuleBacktestParseRequest,
    RuleBacktestParseResponse,
    RuleBacktestRunRequest,
    RuleBacktestRunResponse,
    RuleBacktestTradeItem,
)
from api.v1.schemas.common import ErrorResponse
from src.services.backtest_service import BacktestService
from src.services.rule_backtest_service import RuleBacktestService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/run",
    response_model=BacktestRunResponse,
    responses={
        200: {"description": "回测执行完成"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="触发回测",
    description="对历史分析记录进行回测评估，并写入 backtest_results/backtest_summaries",
)
def run_backtest(
    request: BacktestRunRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestRunResponse:
    try:
        service = BacktestService(db_manager)
        stats = service.run_backtest(
            code=request.code,
            force=request.force,
            eval_window_days=request.eval_window_days,
            min_age_days=request.min_age_days,
            limit=request.limit,
        )
        return BacktestRunResponse(**stats)
    except Exception as exc:
        logger.error(f"回测执行失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"回测执行失败: {str(exc)}"},
        )


@router.post(
    "/prepare-samples",
    response_model=PrepareBacktestSamplesResponse,
    responses={
        200: {"description": "回测样本准备完成"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="准备回测样本",
    description="按股票代码准备可用于回测的历史分析样本，并持久化到 analysis_history。",
)
def prepare_backtest_samples(
    request: PrepareBacktestSamplesRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PrepareBacktestSamplesResponse:
    try:
        service = BacktestService(db_manager)
        stats = service.prepare_backtest_samples(
            code=request.code,
            sample_count=request.sample_count,
            eval_window_days=request.eval_window_days,
            min_age_days=request.min_age_days,
            force_refresh=request.force_refresh,
        )
        return PrepareBacktestSamplesResponse(**stats)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.error(f"准备回测样本失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"准备回测样本失败: {str(exc)}"},
        )


@router.get(
    "/sample-status",
    response_model=BacktestSampleStatusResponse,
    responses={
        200: {"description": "样本状态"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取回测样本状态",
)
def get_sample_status(
    code: str = Query(..., description="股票代码"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestSampleStatusResponse:
    try:
        service = BacktestService(db_manager)
        data = service.get_sample_status(code=code)
        return BacktestSampleStatusResponse(**data)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.error(f"查询回测样本状态失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询回测样本状态失败: {str(exc)}"},
        )


@router.get(
    "/runs",
    response_model=BacktestRunHistoryResponse,
    responses={
        200: {"description": "回测历史"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取回测历史",
)
def get_backtest_runs(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestRunHistoryResponse:
    try:
        service = BacktestService(db_manager)
        data = service.list_backtest_runs(code=code, page=page, limit=limit)
        return BacktestRunHistoryResponse(**data)
    except Exception as exc:
        logger.error(f"查询回测历史失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询回测历史失败: {str(exc)}"},
        )


@router.get(
    "/results",
    response_model=BacktestResultsResponse,
    responses={
        200: {"description": "回测结果列表"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取回测结果",
    description="分页获取回测结果，支持按股票代码过滤",
)
def get_backtest_results(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="评估窗口过滤"),
    run_id: Optional[int] = Query(None, ge=1, description="回测运行ID"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=200, description="每页数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestResultsResponse:
    try:
        service = BacktestService(db_manager)
        if run_id is not None:
            data = service.get_run_results(run_id=run_id, limit=limit, page=page)
        else:
            data = service.get_recent_evaluations(code=code, eval_window_days=eval_window_days, limit=limit, page=page)
        items = [BacktestResultItem(**item) for item in data.get("items", [])]
        return BacktestResultsResponse(
            total=int(data.get("total", 0)),
            page=page,
            limit=limit,
            items=items,
        )
    except Exception as exc:
        logger.error(f"查询回测结果失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询回测结果失败: {str(exc)}"},
        )


@router.post(
    "/samples/clear",
    response_model=BacktestClearResponse,
    responses={
        200: {"description": "回测样本已清理"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="清理回测样本",
)
def clear_backtest_samples(
    request: BacktestCodeRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestClearResponse:
    try:
        service = BacktestService(db_manager)
        data = service.clear_backtest_samples(code=request.code or "")
        data["message"] = "回测样本已清理"
        return BacktestClearResponse(**data)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.error(f"清理回测样本失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"清理回测样本失败: {str(exc)}"},
        )


@router.post(
    "/results/clear",
    response_model=BacktestClearResponse,
    responses={
        200: {"description": "回测结果已清理"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="清理回测结果",
)
def clear_backtest_results(
    request: BacktestCodeRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestClearResponse:
    try:
        service = BacktestService(db_manager)
        data = service.clear_backtest_results(code=request.code or "")
        data["message"] = "回测结果已清理"
        return BacktestClearResponse(**data)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.error(f"清理回测结果失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"清理回测结果失败: {str(exc)}"},
        )


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
def parse_rule_strategy(
    request: RuleBacktestParseRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> RuleBacktestParseResponse:
    try:
        service = RuleBacktestService(db_manager)
        parsed = service.parse_strategy(request.strategy_text)
        return RuleBacktestParseResponse(
            code=request.code,
            strategy_text=request.strategy_text,
            parsed_strategy=dict(parsed),
            confidence=float(parsed.get("confidence") or 0.0),
            needs_confirmation=bool(parsed.get("needs_confirmation", False)),
            ambiguities=list(parsed.get("ambiguities") or []),
            summary=dict(parsed.get("summary") or {}),
            max_lookback=int(parsed.get("max_lookback") or 1),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(exc)}) from exc
    except Exception as exc:
        logger.error(f"解析规则策略失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"解析规则策略失败: {str(exc)}"},
        )


@router.post(
    "/rule/run",
    response_model=RuleBacktestRunResponse,
    responses={
        200: {"description": "规则回测完成"},
        400: {"description": "请求参数错误", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="运行规则回测",
)
def run_rule_backtest(
    request: RuleBacktestRunRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> RuleBacktestRunResponse:
    try:
        service = RuleBacktestService(db_manager)
        data = service.run_backtest(
            code=request.code,
            strategy_text=request.strategy_text,
            parsed_strategy=request.parsed_strategy,
            lookback_bars=request.lookback_bars,
            initial_capital=request.initial_capital,
            fee_bps=request.fee_bps,
            confirmed=request.confirmed,
        )
        trades = [RuleBacktestTradeItem(**item) for item in data.get("trades", [])]
        return RuleBacktestRunResponse(
            id=int(data["id"]),
            code=data["code"],
            strategy_text=data["strategy_text"],
            parsed_strategy=dict(data.get("parsed_strategy") or {}),
            strategy_hash=str(data["strategy_hash"]),
            timeframe=str(data["timeframe"]),
            lookback_bars=int(data["lookback_bars"]),
            initial_capital=float(data["initial_capital"]),
            fee_bps=float(data["fee_bps"]),
            parsed_confidence=data.get("parsed_confidence"),
            needs_confirmation=bool(data.get("needs_confirmation", False)),
            warnings=list(data.get("warnings") or []),
            run_at=data.get("run_at"),
            completed_at=data.get("completed_at"),
            status=str(data.get("status") or "completed"),
            no_result_reason=data.get("no_result_reason"),
            no_result_message=data.get("no_result_message"),
            trade_count=int(data.get("trade_count") or 0),
            win_count=int(data.get("win_count") or 0),
            loss_count=int(data.get("loss_count") or 0),
            total_return_pct=data.get("total_return_pct"),
            win_rate_pct=data.get("win_rate_pct"),
            avg_trade_return_pct=data.get("avg_trade_return_pct"),
            max_drawdown_pct=data.get("max_drawdown_pct"),
            avg_holding_days=data.get("avg_holding_days"),
            final_equity=data.get("final_equity"),
            summary=dict(data.get("summary") or {}),
            ai_summary=data.get("ai_summary"),
            equity_curve=list(data.get("equity_curve") or []),
            trades=trades,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.error(f"规则回测失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"规则回测失败: {str(exc)}"},
        )


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
    try:
        service = RuleBacktestService(db_manager)
        data = service.list_runs(code=code, page=page, limit=limit)
        items = [
            RuleBacktestHistoryItem(
                id=int(item["id"]),
                code=str(item["code"]),
                strategy_text=str(item["strategy_text"]),
                parsed_strategy=dict(item.get("parsed_strategy") or {}),
                strategy_hash=str(item["strategy_hash"]),
                timeframe=str(item["timeframe"]),
                lookback_bars=int(item["lookback_bars"]),
                initial_capital=float(item["initial_capital"]),
                fee_bps=float(item["fee_bps"]),
                parsed_confidence=item.get("parsed_confidence"),
                needs_confirmation=bool(item.get("needs_confirmation", False)),
                warnings=list(item.get("warnings") or []),
                run_at=item.get("run_at"),
                completed_at=item.get("completed_at"),
                status=str(item.get("status") or "completed"),
                no_result_reason=item.get("no_result_reason"),
                no_result_message=item.get("no_result_message"),
                trade_count=int(item.get("trade_count") or 0),
                win_count=int(item.get("win_count") or 0),
                loss_count=int(item.get("loss_count") or 0),
                total_return_pct=item.get("total_return_pct"),
                win_rate_pct=item.get("win_rate_pct"),
                avg_trade_return_pct=item.get("avg_trade_return_pct"),
                max_drawdown_pct=item.get("max_drawdown_pct"),
                avg_holding_days=item.get("avg_holding_days"),
                final_equity=item.get("final_equity"),
                summary=dict(item.get("summary") or {}),
            )
            for item in data.get("items", [])
        ]
        return RuleBacktestHistoryResponse(
            total=int(data.get("total", 0)),
            page=page,
            limit=limit,
            items=items,
        )
    except Exception as exc:
        logger.error(f"查询规则回测历史失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询规则回测历史失败: {str(exc)}"},
        )


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
def get_rule_backtest_run(
    run_id: int,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> RuleBacktestDetailResponse:
    try:
        service = RuleBacktestService(db_manager)
        data = service.get_run(run_id)
        if data is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "规则回测记录不存在"},
            )
        trades = [RuleBacktestTradeItem(**item) for item in data.get("trades", [])]
        return RuleBacktestDetailResponse(
            id=int(data["id"]),
            code=data["code"],
            strategy_text=data["strategy_text"],
            parsed_strategy=dict(data.get("parsed_strategy") or {}),
            strategy_hash=str(data["strategy_hash"]),
            timeframe=str(data["timeframe"]),
            lookback_bars=int(data["lookback_bars"]),
            initial_capital=float(data["initial_capital"]),
            fee_bps=float(data["fee_bps"]),
            parsed_confidence=data.get("parsed_confidence"),
            needs_confirmation=bool(data.get("needs_confirmation", False)),
            warnings=list(data.get("warnings") or []),
            run_at=data.get("run_at"),
            completed_at=data.get("completed_at"),
            status=str(data.get("status") or "completed"),
            no_result_reason=data.get("no_result_reason"),
            no_result_message=data.get("no_result_message"),
            trade_count=int(data.get("trade_count") or 0),
            win_count=int(data.get("win_count") or 0),
            loss_count=int(data.get("loss_count") or 0),
            total_return_pct=data.get("total_return_pct"),
            win_rate_pct=data.get("win_rate_pct"),
            avg_trade_return_pct=data.get("avg_trade_return_pct"),
            max_drawdown_pct=data.get("max_drawdown_pct"),
            avg_holding_days=data.get("avg_holding_days"),
            final_equity=data.get("final_equity"),
            summary=dict(data.get("summary") or {}),
            ai_summary=data.get("ai_summary"),
            equity_curve=list(data.get("equity_curve") or []),
            trades=trades,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"查询规则回测详情失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询规则回测详情失败: {str(exc)}"},
        )


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
    try:
        service = BacktestService(db_manager)
        summary = service.get_summary(scope="overall", code=None, eval_window_days=eval_window_days)
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "未找到整体回测汇总"},
            )
        return PerformanceMetrics(**summary)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"查询整体表现失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询整体表现失败: {str(exc)}"},
        )


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
    try:
        service = BacktestService(db_manager)
        summary = service.get_summary(scope="stock", code=code, eval_window_days=eval_window_days)
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"未找到 {code} 的回测汇总"},
            )
        return PerformanceMetrics(**summary)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"查询单股表现失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询单股表现失败: {str(exc)}"},
        )
