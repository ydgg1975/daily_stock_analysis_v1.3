# -*- coding: utf-8 -*-
"""Request/response schemas for rules engine API."""

from typing import Dict, List, Optional

from pydantic import BaseModel


class RulesAnalyzeRequest(BaseModel):
    symbol: str


class RulesBatchRequest(BaseModel):
    symbols: List[str]


class RuleResultSchema(BaseModel):
    rule_id: str
    dimension: str
    name: str
    signal: str
    matched: bool
    weight: float
    detail: str = ""


class RulesAnalysisResponse(BaseModel):
    symbol: str
    asset_type: str
    total_score: float
    matched_rules: List[RuleResultSchema]
    dimension_summary: Dict[str, Dict[str, int]]
    tags: str = ""
    error: Optional[str] = None


class RulesBatchResponse(BaseModel):
    results: List[RulesAnalysisResponse]
