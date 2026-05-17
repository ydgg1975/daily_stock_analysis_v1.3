# -*- coding: utf-8 -*-
"""
Technical indicator computation for rules engine.
Pure pandas/numpy functions. No I/O, no external calls.
"""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def compute_indicators(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """
    Compute technical indicators from OHLCV DataFrame.

    Args:
        df: DataFrame with 'close' and 'volume' columns, sorted by date ascending.
            Must have >= 5 rows.

    Returns:
        Dict of indicator values. Empty dict if input is invalid or too short.
        None values for indicators that require more data than available.
    """
    if df is None or not isinstance(df, pd.DataFrame):
        return {}
    if df.empty or len(df) < 5:
        return {}
    if "close" not in df.columns or "volume" not in df.columns:
        return {}

    close = df["close"].astype(float)
    volume = df["volume"].astype(float)
    n = len(df)

    def _safe(val: Any) -> Optional[float]:
        if val is None:
            return None
        try:
            f = float(val)
            if np.isnan(f) or np.isinf(f):
                return None
            return f
        except (ValueError, TypeError):
            return None

    def _sma(series: pd.Series, window: int) -> Optional[float]:
        if len(series) < window:
            return None
        return _safe(series.iloc[-window:].mean())

    def _sma_prev(series: pd.Series, window: int) -> Optional[float]:
        if len(series) < window + 1:
            return None
        return _safe(series.iloc[-window - 1:-1].mean())

    result: Dict[str, Any] = {}

    # Moving Averages
    for w in (5, 10, 20, 60):
        result[f"ma{w}"] = _sma(close, w)
        result[f"ma{w}_prev"] = _sma_prev(close, w)

    # MA Alignment
    ma5 = result.get("ma5")
    ma10 = result.get("ma10")
    ma20 = result.get("ma20")
    if ma5 and ma10 and ma20:
        if ma5 > ma10 > ma20:
            result["ma_alignment"] = "bullish"
        elif ma5 < ma10 < ma20:
            result["ma_alignment"] = "bearish"
        else:
            result["ma_alignment"] = "neutral"
    else:
        result["ma_alignment"] = "neutral"

    # MACD (12, 26, 9)
    if n >= 26:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        bar = 2 * (dif - dea)

        result["macd_dif"] = _safe(dif.iloc[-1])
        result["macd_dea"] = _safe(dea.iloc[-1])
        result["macd_bar"] = _safe(bar.iloc[-1])
        result["macd_dif_prev"] = _safe(dif.iloc[-2]) if n >= 27 else None
        result["macd_dea_prev"] = _safe(dea.iloc[-2]) if n >= 27 else None

        cur_dif = result["macd_dif"]
        cur_dea = result["macd_dea"]
        prev_dif = result["macd_dif_prev"]
        prev_dea = result["macd_dea_prev"]
        if cur_dif is not None and cur_dea is not None and prev_dif is not None and prev_dea is not None:
            if prev_dif <= prev_dea and cur_dif > cur_dea:
                result["macd_cross"] = "golden"
            elif prev_dif >= prev_dea and cur_dif < cur_dea:
                result["macd_cross"] = "death"
            else:
                result["macd_cross"] = "none"
        else:
            result["macd_cross"] = "none"
    else:
        for k in ("macd_dif", "macd_dea", "macd_bar", "macd_dif_prev", "macd_dea_prev"):
            result[k] = None
        result["macd_cross"] = "none"

    # RSI (14)
    if n >= 15:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        result["rsi"] = _safe(rsi.iloc[-1])
    else:
        result["rsi"] = None

    # Bollinger Bands (20)
    if n >= 20:
        mid = close.rolling(20).mean()
        std = close.rolling(20).std()
        upper = mid + 2 * std
        lower = mid - 2 * std
        result["boll_upper"] = _safe(upper.iloc[-1])
        result["boll_lower"] = _safe(lower.iloc[-1])
        result["boll_mid"] = _safe(mid.iloc[-1])
        cur_close = close.iloc[-1]
        boll_range = upper.iloc[-1] - lower.iloc[-1]
        if boll_range > 0:
            result["boll_position"] = _safe((cur_close - lower.iloc[-1]) / boll_range)
        else:
            result["boll_position"] = _safe(0.5)
    else:
        result["boll_upper"] = None
        result["boll_lower"] = None
        result["boll_mid"] = None
        result["boll_position"] = None

    # Returns
    for days in (5, 10, 20, 60):
        if n > days:
            prev = close.iloc[-days - 1]
            if prev > 0:
                result[f"return_{days}d"] = _safe((close.iloc[-1] / prev - 1) * 100)
            else:
                result[f"return_{days}d"] = None
        else:
            result[f"return_{days}d"] = None

    # Volume Ratio
    if n >= 6:
        avg_vol_5 = volume.iloc[-6:-1].mean()
        if avg_vol_5 > 0:
            result["volume_ratio"] = _safe(volume.iloc[-1] / avg_vol_5)
        else:
            result["volume_ratio"] = None
    else:
        result["volume_ratio"] = None

    # Position (0-1 within N-day range)
    for window in (20, 60):
        if n >= window:
            high = close.iloc[-window:].max()
            low = close.iloc[-window:].min()
            rng = high - low
            if rng > 0:
                result[f"position_{window}d"] = _safe((close.iloc[-1] - low) / rng)
            else:
                result[f"position_{window}d"] = _safe(0.5)
        else:
            result[f"position_{window}d"] = None

    # New High / New Low
    for window in (20, 60):
        if n >= window:
            subset = close.iloc[-window:]
            result[f"new_high_{window}d"] = bool(close.iloc[-1] >= subset.max())
            result[f"new_low_{window}d"] = bool(close.iloc[-1] <= subset.min())
        else:
            result[f"new_high_{window}d"] = False
            result[f"new_low_{window}d"] = False

    return result
