# -*- coding: utf-8 -*-
"""Rules engine API endpoints."""

import logging
from typing import List

from fastapi import APIRouter, HTTPException

from api.v1.schemas.rules import (
    RulesAnalyzeRequest, RulesBatchRequest,
    RulesAnalysisResponse, RulesBatchResponse, RuleResultSchema,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=RulesAnalysisResponse)
async def analyze_rules(req: RulesAnalyzeRequest):
    """Analyze a single symbol using the rules engine."""
    try:
        from data_provider.base import DataFetcherManager, _is_etf_code
        from src.services.rules_analysis_service import RulesAnalysisService

        manager = DataFetcherManager()
        df, _ = manager.get_daily_data(req.symbol, days=150)
        if df is None or df.empty:
            return RulesAnalysisResponse(
                symbol=req.symbol, asset_type="unknown", total_score=0.0,
                matched_rules=[], dimension_summary={},
                error="No historical data available",
            )

        svc = RulesAnalysisService()
        asset_type = "etf" if _is_etf_code(req.symbol) else "stock"
        result = svc.compute_rules_for_df(df, symbol=req.symbol, asset_type=asset_type)

        return RulesAnalysisResponse(
            symbol=result.symbol, asset_type=result.asset_type,
            total_score=result.total_score,
            matched_rules=[
                RuleResultSchema(
                    rule_id=r.rule_id, dimension=r.dimension, name=r.name,
                    signal=r.signal, matched=r.matched, weight=r.weight, detail=r.detail,
                ) for r in result.matched_rules
            ],
            dimension_summary=result.dimension_summary,
            tags=result.rules_tags,
        )
    except Exception as exc:
        logger.error("Rules analysis failed for %s: %s", req.symbol, exc)
        raise HTTPException(status_code=500, detail="analysis_failed")


@router.post("/batch", response_model=RulesBatchResponse)
async def batch_analyze_rules(req: RulesBatchRequest):
    """Batch analyze up to 10 symbols."""
    if len(req.symbols) > 10:
        raise HTTPException(status_code=400, detail="too_many")
    results: List[RulesAnalysisResponse] = []
    for symbol in req.symbols[:10]:
        try:
            resp = await analyze_rules(RulesAnalyzeRequest(symbol=symbol))
            results.append(resp)
        except Exception:
            results.append(RulesAnalysisResponse(
                symbol=symbol, asset_type="unknown", total_score=0.0,
                matched_rules=[], dimension_summary={}, error="analysis_failed",
            ))
    return RulesBatchResponse(results=results)
