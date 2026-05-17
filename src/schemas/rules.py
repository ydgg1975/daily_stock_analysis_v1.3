# -*- coding: utf-8 -*-
"""Data structures for rules engine analysis."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RuleResult:
    """Single rule evaluation result."""
    rule_id: str
    dimension: str          # technical / trend / capital / valuation
    name: str
    description: str
    signal: str             # bullish / bearish / warning / neutral
    matched: bool
    weight: float
    detail: str = ""


@dataclass
class RulesAnalysisResult:
    """Complete rules analysis result for a single symbol."""
    symbol: str
    asset_type: str         # etf / stock
    name: str
    price: Optional[float] = None
    change_pct: Optional[float] = None
    indicators: Dict[str, Any] = field(default_factory=dict)
    matched_rules: List[RuleResult] = field(default_factory=list)
    dimension_summary: Dict[str, Dict[str, int]] = field(default_factory=dict)
    total_score: float = 0.0
    rules_tags: str = ""
    rules_tags_html: str = ""
    llm_summary: Optional[str] = None
    error: Optional[str] = None
