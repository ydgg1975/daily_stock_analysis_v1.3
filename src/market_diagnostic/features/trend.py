"""
Trend Feature Calculation

Computes technical trend indicators for market indices using numpy only (no ta-lib).
Includes MA alignment, MACD, RSRS, ATR, bias ratios, and relative strength.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    from src.market_diagnostic.data.models import IndexDailyData
except ImportError:
    from market_diagnostic.data.models import IndexDailyData  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class TrendFeatures:
    """Trend-related technical features for a single index."""

    code: str
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    ma120: float
    ma_alignment: str          # "多头排列" / "空头排列" / "缠绕"
    bias_ma5: float            # (close - ma5) / ma5
    bias_ma20: float
    bias_ma60: float
    macd_dif: float
    macd_dea: float
    macd_bar: float
    macd_signal: str           # "金叉" / "死叉" / "中性"
    atr_20: float
    rsrs_score: float          # Normalised RSRS score in [0, 1]
    near_high_20d: bool
    break_support: bool
    rs_vs_300: float           # Relative strength vs CSI300 (close ratio)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ema(series: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average using the standard multiplier 2/(period+1)."""
    if len(series) == 0:
        return np.array([])
    alpha = 2.0 / (period + 1)
    result = np.empty(len(series))
    result[0] = series[0]
    for i in range(1, len(series)):
        result[i] = alpha * series[i] + (1 - alpha) * result[i - 1]
    return result


def _sma(series: np.ndarray, period: int) -> float:
    """Simple moving average of the last *period* values. Returns NaN if insufficient data."""
    if len(series) < period:
        return float("nan")
    return float(np.mean(series[-period:]))


def _compute_macd(
    closes: np.ndarray,
) -> Tuple[float, float, float, str]:
    """
    Compute MACD (DIF, DEA, BAR) and detect golden/death cross.

    DIF  = EMA12 - EMA26
    DEA  = EMA9 of DIF
    BAR  = 2 * (DIF - DEA)

    Cross detection uses the last two values of DIF and DEA.
    """
    if len(closes) < 26:
        return float("nan"), float("nan"), float("nan"), "中性"

    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    dif_series = ema12 - ema26
    dea_series = _ema(dif_series, 9)

    dif = float(dif_series[-1])
    dea = float(dea_series[-1])
    bar = 2.0 * (dif - dea)

    # Cross detection requires at least 2 data points
    if len(dif_series) >= 2:
        prev_dif = float(dif_series[-2])
        prev_dea = float(dea_series[-2])
        if prev_dif < prev_dea and dif > dea:
            signal = "金叉"
        elif prev_dif > prev_dea and dif < dea:
            signal = "死叉"
        else:
            signal = "中性"
    else:
        signal = "中性"

    return dif, dea, bar, signal


def _compute_rsrs(
    highs: np.ndarray,
    lows: np.ndarray,
    window: int = 18,
) -> float:
    """
    Compute normalised RSRS score in [0, 1].

    RSRS slope = OLS slope of high ~ low over the last *window* days.
    Normalisation: since we only have ~60 days, we compute the slope for
    every rolling window of size *window* within the available data, then
    normalise the latest slope to [0, 1] using min-max scaling over the
    computed slope series.
    """
    n = len(highs)
    if n < window or len(lows) < window:
        return 0.5  # neutral default when insufficient data

    slopes: List[float] = []
    for start in range(n - window + 1):
        x = lows[start : start + window]
        y = highs[start : start + window]
        # OLS slope via numpy
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        denom = np.sum((x - x_mean) ** 2)
        if denom == 0:
            slopes.append(0.0)
        else:
            slope = float(np.sum((x - x_mean) * (y - y_mean)) / denom)
            slopes.append(slope)

    if len(slopes) == 0:
        return 0.5

    latest = slopes[-1]
    s_min = min(slopes)
    s_max = max(slopes)
    if s_max == s_min:
        return 0.5
    return float(np.clip((latest - s_min) / (s_max - s_min), 0.0, 1.0))


def _compute_atr20(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> float:
    """
    ATR-20: 20-day average of True Range.

    TR = max(high - low, |high - prev_close|, |low - prev_close|)
    """
    n = len(closes)
    if n < 2:
        return float("nan")

    # We need at least 2 closes to compute prev_close
    # Align arrays: TR[i] uses closes[i-1] as prev_close
    h = highs[1:]
    l = lows[1:]
    pc = closes[:-1]

    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))

    period = min(20, len(tr))
    return float(np.mean(tr[-period:]))


def _ma_alignment(ma5: float, ma10: float, ma20: float, ma60: float) -> str:
    """Classify MA alignment as bullish, bearish, or tangled."""
    if any(np.isnan(v) for v in [ma5, ma10, ma20, ma60]):
        return "缠绕"
    if ma5 > ma10 > ma20 > ma60:
        return "多头排列"
    if ma5 < ma10 < ma20 < ma60:
        return "空头排列"
    return "缠绕"


def _safe_bias(close: float, ma: float) -> float:
    """Bias ratio = (close - ma) / ma. Returns 0.0 if ma is zero or NaN."""
    if np.isnan(ma) or ma == 0:
        return 0.0
    return (close - ma) / ma


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_trend_features(
    data: IndexDailyData,
    csi300_close: Optional[float] = None,
) -> TrendFeatures:
    """
    Compute trend features for a single index using numpy only (no ta-lib).

    Parameters
    ----------
    data:
        IndexDailyData with close_series (and optionally high/low series).
        The series should be ordered oldest → newest.
    csi300_close:
        Latest close of CSI300 for relative-strength calculation.
        If None, rs_vs_300 is set to 1.0 (neutral).
    """
    closes = np.array(data.close_series, dtype=float)
    close = data.close

    # ---- Moving averages ----
    ma5 = _sma(closes, 5)
    ma10 = _sma(closes, 10)
    ma20 = _sma(closes, 20)
    ma60 = _sma(closes, 60)
    ma120 = _sma(closes, 120)

    # ---- MA alignment ----
    alignment = _ma_alignment(ma5, ma10, ma20, ma60)

    # ---- Bias ratios ----
    bias_ma5 = _safe_bias(close, ma5)
    bias_ma20 = _safe_bias(close, ma20)
    bias_ma60 = _safe_bias(close, ma60)

    # ---- MACD ----
    dif, dea, bar, macd_signal = _compute_macd(closes)

    # ---- ATR-20 ----
    # IndexDailyData does not carry high/low series by default.
    # We approximate using close_series only when high/low series are absent.
    high_series = getattr(data, "high_series", None)
    low_series = getattr(data, "low_series", None)

    if high_series is not None and low_series is not None and len(high_series) > 1:
        highs = np.array(high_series, dtype=float)
        lows = np.array(low_series, dtype=float)
    else:
        # Fallback: approximate high/low from close series
        # (less accurate but avoids crashing when series are absent)
        highs = closes
        lows = closes

    atr_20 = _compute_atr20(highs, lows, closes)

    # ---- RSRS ----
    rsrs_score = _compute_rsrs(highs, lows)

    # ---- Near 20-day high ----
    if len(closes) >= 20:
        high_20d = float(np.max(closes[-20:]))
        near_high_20d = close >= high_20d * 0.98
    else:
        near_high_20d = False

    # ---- Break support (below MA60) ----
    break_support = (not np.isnan(ma60)) and (close < ma60)

    # ---- Relative strength vs CSI300 ----
    if csi300_close is not None and csi300_close != 0:
        rs_vs_300 = close / csi300_close
    else:
        rs_vs_300 = 1.0

    return TrendFeatures(
        code=data.code,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        ma60=ma60,
        ma120=ma120,
        ma_alignment=alignment,
        bias_ma5=bias_ma5,
        bias_ma20=bias_ma20,
        bias_ma60=bias_ma60,
        macd_dif=dif,
        macd_dea=dea,
        macd_bar=bar,
        macd_signal=macd_signal,
        atr_20=atr_20,
        rsrs_score=rsrs_score,
        near_high_20d=near_high_20d,
        break_support=break_support,
        rs_vs_300=rs_vs_300,
    )


def compute_all_trend_features(
    index_data: Dict[str, IndexDailyData],
    csi300_data: IndexDailyData,
) -> Dict[str, TrendFeatures]:
    """
    Compute trend features for all indices and include relative strength vs CSI300.

    Parameters
    ----------
    index_data:
        Mapping of index code → IndexDailyData for all indices to analyse.
    csi300_data:
        IndexDailyData for CSI300 (sh000300), used as the benchmark.

    Returns
    -------
    Dict mapping index code → TrendFeatures.
    """
    csi300_close = csi300_data.close

    result: Dict[str, TrendFeatures] = {}
    for code, data in index_data.items():
        result[code] = compute_trend_features(data, csi300_close=csi300_close)

    # Ensure CSI300 itself is included (rs_vs_300 == 1.0 by definition)
    if csi300_data.code not in result:
        result[csi300_data.code] = compute_trend_features(
            csi300_data, csi300_close=csi300_close
        )

    return result
