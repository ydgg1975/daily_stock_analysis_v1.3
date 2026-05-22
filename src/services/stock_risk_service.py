# -*- coding: utf-8 -*-
"""Single-stock risk metrics for analysis reports."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import pandas as pd

from src.analyzer import AnalysisResult


def build_stock_risk_report(
    result: AnalysisResult,
    *,
    trend_result: Optional[Any] = None,
    history_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Build deterministic single-stock risk metrics and position cautions."""
    volatility = _annualized_volatility_pct(history_df)
    max_drawdown = _max_drawdown_pct(history_df)
    risk_flags = _build_risk_flags(result, trend_result, volatility, max_drawdown)
    risk_level = _risk_level(risk_flags)

    return {
        "version": 1,
        "risk_level": risk_level,
        "risk_score": _risk_score(risk_flags),
        "volatility_pct": volatility,
        "max_drawdown_pct": max_drawdown,
        "flags": risk_flags,
        "position_caution": _position_caution(risk_level, risk_flags),
    }


def attach_stock_risk_report(
    result: AnalysisResult,
    *,
    trend_result: Optional[Any] = None,
    history_df: Optional[pd.DataFrame] = None,
) -> None:
    """Attach single-stock risk report metadata to an analysis result."""
    result.stock_risk_report = build_stock_risk_report(
        result,
        trend_result=trend_result,
        history_df=history_df,
    )


def _close_series(df: Optional[pd.DataFrame]) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype="float64")
    for column in ("close", "Close", "收盘"):
        if column in df.columns:
            return pd.to_numeric(df[column], errors="coerce").dropna()
    return pd.Series(dtype="float64")


def _annualized_volatility_pct(df: Optional[pd.DataFrame]) -> Optional[float]:
    close = _close_series(df)
    if len(close) < 3:
        return None
    returns = close.pct_change().dropna()
    if returns.empty:
        return None
    value = float(returns.std(ddof=0) * math.sqrt(252) * 100.0)
    return round(value, 4)


def _max_drawdown_pct(df: Optional[pd.DataFrame]) -> Optional[float]:
    close = _close_series(df)
    if len(close) < 2:
        return None
    running_max = close.cummax()
    drawdown = (close / running_max - 1.0) * 100.0
    return round(abs(float(drawdown.min())), 4)


def _build_risk_flags(
    result: AnalysisResult,
    trend_result: Optional[Any],
    volatility: Optional[float],
    max_drawdown: Optional[float],
) -> List[Dict[str, Any]]:
    flags: List[Dict[str, Any]] = []
    if volatility is not None and volatility >= 45.0:
        flags.append({
            "id": "high_volatility",
            "severity": "high" if volatility >= 65.0 else "medium",
            "reason": f"Annualized volatility is {volatility:.1f}%.",
        })
    if max_drawdown is not None and max_drawdown >= 20.0:
        flags.append({
            "id": "large_drawdown",
            "severity": "high" if max_drawdown >= 35.0 else "medium",
            "reason": f"Recent maximum drawdown is {max_drawdown:.1f}%.",
        })

    bias_ma5 = getattr(trend_result, "bias_ma5", None)
    if isinstance(bias_ma5, (int, float)) and bias_ma5 >= 8.0:
        flags.append({
            "id": "extended_from_ma5",
            "severity": "medium",
            "reason": f"Price is {bias_ma5:.1f}% above MA5.",
        })

    rsi_6 = getattr(trend_result, "rsi_6", None)
    if isinstance(rsi_6, (int, float)) and rsi_6 >= 75.0:
        flags.append({
            "id": "short_term_overbought",
            "severity": "medium",
            "reason": f"RSI(6) is elevated at {rsi_6:.1f}.",
        })

    for item in getattr(trend_result, "risk_factors", []) or []:
        text = str(item).strip()
        if text:
            flags.append({"id": "technical_risk", "severity": "medium", "reason": text})

    risk_warning = str(getattr(result, "risk_warning", "") or "").strip()
    if risk_warning:
        flags.append({"id": "reported_risk", "severity": "medium", "reason": risk_warning})

    return flags


def _risk_score(flags: List[Dict[str, Any]]) -> int:
    score = 20
    for flag in flags:
        score += 30 if flag.get("severity") == "high" else 15
    return max(0, min(100, score))


def _risk_level(flags: List[Dict[str, Any]]) -> str:
    score = _risk_score(flags)
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    if score > 20:
        return "low"
    return "none"


def _position_caution(risk_level: str, flags: List[Dict[str, Any]]) -> str:
    if risk_level == "high":
        return "Avoid adding exposure until high-severity risk flags ease."
    if risk_level == "medium":
        return "Keep position size controlled and wait for risk confirmation to improve."
    if risk_level == "low":
        return "Use normal position discipline; monitor listed risk flags."
    return "No elevated risk flags detected from available data."
