# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - AI分析
===================================

职责：
1. 封装 LLM 调用逻辑
2. 提供股票分析与结果验证接口
"""

from src.analyzer.core import (
    AnalysisResult,
    GeminiAnalyzer,
    Router,
    _AllModelsFailedError,
    call_litellm_with_param_recovery,
    get_stock_name_multi_source,
    get_analyzer,
    persist_llm_usage,
)
from src.config import get_config
from src.analyzer.validators import (
    check_content_integrity,
    apply_placeholder_fill,
)
from src.analyzer.stabilizer import (
    _BULLISH_TREND_HINTS,
    _build_chip_structure_from_data,
    _capital_flow_bias,
    _contains_trend_hint,
    _derive_chip_health,
    _infer_trend_direction,
    _is_value_placeholder,
    _sanitize_trend_analysis_for_prompt,
    stabilize_decision_with_structure,
    normalize_chip_structure_availability,
    fill_chip_structure_if_needed,
    fill_price_position_if_needed,
)

__all__ = [
    "AnalysisResult",
    "GeminiAnalyzer",
    "Router",
    "_AllModelsFailedError",
    "call_litellm_with_param_recovery",
    "get_stock_name_multi_source",
    "get_analyzer",
    "persist_llm_usage",
    "get_config",
    "check_content_integrity",
    "apply_placeholder_fill",
    "_BULLISH_TREND_HINTS",
    "_build_chip_structure_from_data",
    "_capital_flow_bias",
    "_contains_trend_hint",
    "_derive_chip_health",
    "_infer_trend_direction",
    "_is_value_placeholder",
    "_sanitize_trend_analysis_for_prompt",
    "stabilize_decision_with_structure",
    "normalize_chip_structure_availability",
    "fill_chip_structure_if_needed",
    "fill_price_position_if_needed",
]
