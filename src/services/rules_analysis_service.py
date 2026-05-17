# -*- coding: utf-8 -*-
"""Rules analysis service: orchestrates indicators, rules, and display."""

import logging
from typing import Dict, List, Optional

import pandas as pd

from src.rules.engine import RuleEngine, dimension_summary, compute_total_score
from src.rules.indicators import compute_indicators
from src.rules.display import format_rules_tags, format_rules_tags_html
from src.schemas.rules import RulesAnalysisResult, RuleResult

logger = logging.getLogger(__name__)


class RulesAnalysisService:
    """Orchestrate rules analysis for any symbol (stock/ETF, all markets)."""

    def __init__(self):
        self._engine = RuleEngine()

    def compute_rules_for_df(
        self,
        df: Optional[pd.DataFrame],
        symbol: str = "",
        asset_type: str = "stock",
        valuation: Optional[Dict] = None,
    ) -> RulesAnalysisResult:
        """
        Compute rules from an existing OHLCV DataFrame.
        No data fetching — pure computation.

        Args:
            df: DataFrame with 'close' and 'volume' columns.
            symbol: Stock/ETF code for labeling.
            asset_type: 'stock' or 'etf'.
            valuation: Optional dict with valuation data (e.g. pe_percentile).
        """
        indicators = compute_indicators(df)

        # Inject latest close for rules that need it
        if df is not None and not df.empty and "close" in df.columns:
            indicators["close"] = float(df["close"].iloc[-1])

        # Merge valuation data (pe_percentile, etc.)
        if valuation:
            indicators.update(valuation)

        results: List[RuleResult] = self._engine.evaluate(indicators)
        summary = dimension_summary(results)
        score = compute_total_score(results)

        tags = format_rules_tags(results, summary, score)
        tags_html = format_rules_tags_html(results, summary, score)

        return RulesAnalysisResult(
            symbol=symbol,
            asset_type=asset_type,
            name="",
            matched_rules=results,
            dimension_summary=summary,
            total_score=score,
            rules_tags=tags,
            rules_tags_html=tags_html,
        )
