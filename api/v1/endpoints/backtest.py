# -*- coding: utf-8 -*-

"""Backtest endpoints."""



from __future__ import annotations



import logging

from datetime import date

from typing import Optional



from fastapi import APIRouter, Depends, HTTPException, Query



from api.deps import get_database_manager

from api.v1.schemas.backtest import (

    BacktestRunRequest,

    BacktestRunResponse,

    BacktestResultItem,

    BacktestResultsResponse,

    PerformanceMetrics,

)

from api.v1.schemas.common import ErrorResponse

from src.services.backtest_service import BacktestService

from src.storage import DatabaseManager



logger = logging.getLogger(__name__)



router = APIRouter()





def _validate_analysis_date_range(

    analysis_date_from: Optional[date],

    analysis_date_to: Optional[date],

) -> None:

    if analysis_date_from and analysis_date_to and analysis_date_from > analysis_date_to:

        raise HTTPException(

            status_code=400,

            detail={

                "error": "invalid_params",

                "message": "analysis_date_from cannot be after analysis_date_to",

            },

        )





@router.post(

    "/run",

    response_model=BacktestRunResponse,

    responses={

        200: {"description": "huicezhixingwancheng"},

        500: {"description": "fuwuqicuowu", "model": ErrorResponse},

    },

    summary="chufahuice",

    description="duilishianalysisrecordjinxinghuicepinggu竊똟ingxieru backtest_results/backtest_summaries",

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

        logger.error(f"huicezhixingshibai: {exc}", exc_info=True)

        raise HTTPException(

            status_code=500,

            detail={"error": "internal_error", "message": f"huicezhixingshibai: {str(exc)}"},

        )





@router.get(

    "/results",

    response_model=BacktestResultsResponse,

    responses={

        200: {"description": "huicejieguoliebiao"},

        500: {"description": "fuwuqicuowu", "model": ErrorResponse},

    },

    summary="huoquhuicejieguo",

    description="fenyehuoquhuicejieguo竊똺hichianstockdaimaguolv",

)

def get_backtest_results(

    code: Optional[str] = Query(None, description="stockdaimashaixuan"),

    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="pingguchuangkouguolv"),

    analysis_date_from: Optional[date] = Query(None, description="Analysis date start, inclusive"),

    analysis_date_to: Optional[date] = Query(None, description="Analysis date end, inclusive"),

    page: int = Query(1, ge=1, description="yema"),

    limit: int = Query(20, ge=1, le=200, description="meiyeshuliang"),

    db_manager: DatabaseManager = Depends(get_database_manager),

) -> BacktestResultsResponse:

    try:

        _validate_analysis_date_range(analysis_date_from, analysis_date_to)

        service = BacktestService(db_manager)

        data = service.get_recent_evaluations(

            code=code,

            eval_window_days=eval_window_days,

            limit=limit,

            page=page,

            analysis_date_from=analysis_date_from,

            analysis_date_to=analysis_date_to,

        )

        items = [BacktestResultItem(**item) for item in data.get("items", [])]

        return BacktestResultsResponse(

            total=int(data.get("total", 0)),

            page=page,

            limit=limit,

            items=items,

        )

    except HTTPException:

        raise

    except Exception as exc:

        logger.error(f"chaxunhuicejieguoshibai: {exc}", exc_info=True)

        raise HTTPException(

            status_code=500,

            detail={"error": "internal_error", "message": f"chaxunhuicejieguoshibai: {str(exc)}"},

        )





@router.get(

    "/performance",

    response_model=PerformanceMetrics,

    responses={

        200: {"description": "zhengtihuicebiaoxian"},

        404: {"description": "wuhuicehuizong", "model": ErrorResponse},

        500: {"description": "fuwuqicuowu", "model": ErrorResponse},

    },

    summary="huoquzhengtihuicebiaoxian",

)

def get_overall_performance(

    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="pingguchuangkouguolv"),

    analysis_date_from: Optional[date] = Query(None, description="Analysis date start, inclusive"),

    analysis_date_to: Optional[date] = Query(None, description="Analysis date end, inclusive"),

    db_manager: DatabaseManager = Depends(get_database_manager),

) -> PerformanceMetrics:

    try:

        _validate_analysis_date_range(analysis_date_from, analysis_date_to)

        service = BacktestService(db_manager)

        summary = service.get_summary(

            scope="overall",

            code=None,

            eval_window_days=eval_window_days,

            analysis_date_from=analysis_date_from,

            analysis_date_to=analysis_date_to,

        )

        if summary is None:

            raise HTTPException(

                status_code=404,

                detail={"error": "not_found", "message": "weizhaodaozhengtihuicehuizong"},

            )

        return PerformanceMetrics(**summary)

    except ValueError as exc:

        raise HTTPException(

            status_code=400,

            detail={"error": "invalid_params", "message": str(exc)},

        )

    except HTTPException:

        raise

    except Exception as exc:

        logger.error(f"chaxunzhengtibiaoxianshibai: {exc}", exc_info=True)

        raise HTTPException(

            status_code=500,

            detail={"error": "internal_error", "message": f"chaxunzhengtibiaoxianshibai: {str(exc)}"},

        )





@router.get(

    "/performance/{code}",

    response_model=PerformanceMetrics,

    responses={

        200: {"description": "danguhuicebiaoxian"},

        404: {"description": "wuhuicehuizong", "model": ErrorResponse},

        500: {"description": "fuwuqicuowu", "model": ErrorResponse},

    },

    summary="huoqudanguhuicebiaoxian",

)

def get_stock_performance(

    code: str,

    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="pingguchuangkouguolv"),

    analysis_date_from: Optional[date] = Query(None, description="Analysis date start, inclusive"),

    analysis_date_to: Optional[date] = Query(None, description="Analysis date end, inclusive"),

    db_manager: DatabaseManager = Depends(get_database_manager),

) -> PerformanceMetrics:

    try:

        _validate_analysis_date_range(analysis_date_from, analysis_date_to)

        service = BacktestService(db_manager)

        summary = service.get_summary(

            scope="stock",

            code=code,

            eval_window_days=eval_window_days,

            analysis_date_from=analysis_date_from,

            analysis_date_to=analysis_date_to,

        )

        if summary is None:

            raise HTTPException(

                status_code=404,

                detail={"error": "not_found", "message": f"weizhaodao {code} dehuicehuizong"},

            )

        return PerformanceMetrics(**summary)

    except ValueError as exc:

        raise HTTPException(

            status_code=400,

            detail={"error": "invalid_params", "message": str(exc)},

        )

    except HTTPException:

        raise

    except Exception as exc:

        logger.error(f"chaxundangubiaoxianshibai: {exc}", exc_info=True)

        raise HTTPException(

            status_code=500,

            detail={"error": "internal_error", "message": f"chaxundangubiaoxianshibai: {str(exc)}"},

        )


