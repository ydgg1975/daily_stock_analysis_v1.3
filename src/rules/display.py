# -*- coding: utf-8 -*-
"""Display formatter: Markdown (emoji) and HTML (inline style) tag output."""

from typing import Dict

from src.schemas.rules import RuleResult

_SIGNAL_EMOJI = {"bullish": "🟢", "bearish": "🔴", "warning": "🟡", "neutral": "⚪"}
_SIGNAL_LABEL = {"bullish": "偏多", "bearish": "偏空", "warning": "注意", "neutral": "中性"}
_SIGNAL_COLOR = {"bullish": "#52c41a", "bearish": "#cf1322", "warning": "#faad14", "neutral": "#8d969e"}
_DIMENSION_LABEL = {"technical": "技术面", "trend": "趋势面", "capital": "资金面", "valuation": "估值面"}


def compute_verdict(summary: Dict[str, Dict[str, int]]) -> str:
    """Overall verdict: warning > bearish > bullish > neutral."""
    total_warning = sum(d.get("warning", 0) for d in summary.values())
    total_bearish = sum(d.get("bearish", 0) for d in summary.values())
    total_bullish = sum(d.get("bullish", 0) for d in summary.values())
    if total_warning > 0:
        return "warning"
    if total_bearish > total_bullish:
        return "bearish"
    if total_bullish > total_bearish:
        return "bullish"
    return "neutral"


def _dim_verdict(dim_data: Dict[str, int]) -> str:
    dim_warning = dim_data.get("warning", 0)
    dim_bearish = dim_data.get("bearish", 0)
    dim_bullish = dim_data.get("bullish", 0)
    if dim_warning > 0:
        return "warning"
    if dim_bearish > dim_bullish:
        return "bearish"
    if dim_bullish > dim_bearish:
        return "bullish"
    return "neutral"


def format_rules_tags(results: list, summary: Dict[str, Dict[str, int]], score: float) -> str:
    """Markdown emoji tags. Empty string if no rules matched."""
    matched = [r for r in results if r.matched]
    if not matched:
        return ""
    verdict = compute_verdict(summary)
    lines = [f"**{_SIGNAL_EMOJI[verdict]} 综合判定: {_SIGNAL_LABEL[verdict]}** (评分: {score:+.1f})"]
    lines.append("")
    for dim_key in ("technical", "trend", "capital", "valuation"):
        if dim_key not in summary:
            continue
        dv = _dim_verdict(summary[dim_key])
        dim_rules = [r for r in matched if r.dimension == dim_key]
        rule_names = "、".join(r.name for r in dim_rules)
        lines.append(f"{_SIGNAL_EMOJI[dv]} **{_DIMENSION_LABEL[dim_key]}**: {rule_names}")
    return "\n".join(lines)


def format_rules_tags_html(results: list, summary: Dict[str, Dict[str, int]], score: float) -> str:
    """HTML inline-styled tags. Empty string if no rules matched."""
    matched = [r for r in results if r.matched]
    if not matched:
        return ""
    verdict = compute_verdict(summary)
    parts = [f'<strong><span style="color:{_SIGNAL_COLOR[verdict]}">● {_SIGNAL_LABEL[verdict]}</span> (评分: {score:+.1f})</strong>']
    for dim_key in ("technical", "trend", "capital", "valuation"):
        if dim_key not in summary:
            continue
        dv = _dim_verdict(summary[dim_key])
        dim_rules = [r for r in matched if r.dimension == dim_key]
        rule_names = "、".join(r.name for r in dim_rules)
        parts.append(f'<span style="color:{_SIGNAL_COLOR[dv]}">●</span> <strong>{_DIMENSION_LABEL[dim_key]}</strong>: {rule_names}')
    return "<br>".join(parts)
