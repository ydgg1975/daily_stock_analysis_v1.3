#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pandas as pd, numpy as np
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

@dataclass
class MTFResult:
    resonance_score: float = 0
    resonance_level: str = "none"  # triple/double/single/none
    weekly_signal: str = "neutral"
    daily_signal: str = "neutral"
    h60_signal: str = "neutral"
    quality_signal: bool = False
    buy_signals: list = None
    sell_signals: list = None

def _calc_ma_score(closes):
    if len(closes) < 30: return 50, "neutral"
    ma5 = sum(closes[-5:])/5; ma20 = sum(closes[-20:])/20
    ma60 = sum(closes[-60:])/60 if len(closes)>=60 else sum(closes[-len(closes):])/len(closes)
    price = closes[-1]
    if ma5 > ma20 > ma60 and price > ma5: return 80, "bullish"
    if price > ma60: return 60, "neutral_bullish"
    if price < ma60: return 40, "bearish"
    return 50, "neutral"

def multi_timeframe_analysis(code: str, wk_df=None, day_df=None, h60_df=None) -> MTFResult:
    r = MTFResult()
    scores = []; signals = []; r.buy_signals = []; r.sell_signals = []
    # 周线
    if wk_df is not None and len(wk_df) >= 20:
        w_closes = wk_df["close"].values if "close" in wk_df.columns else wk_df.iloc[:,-1].values
        ws, r.weekly_signal = _calc_ma_score(w_closes)
        scores.append(ws); signals.append(r.weekly_signal)
    # 日线
    if day_df is not None and len(day_df) >= 30:
        d_closes = day_df["close"].values if "close" in day_df.columns else day_df.iloc[:,-1].values
        ds, r.daily_signal = _calc_ma_score(d_closes)
        scores.append(ds); signals.append(r.daily_signal)
    # 60分钟
    if h60_df is not None and len(h60_df) >= 30:
        h_closes = h60_df["close"].values if "close" in h60_df.columns else h60_df.iloc[:,-1].values
        hs, r.h60_signal = _calc_ma_score(h_closes)
        scores.append(hs); signals.append(r.h60_signal)
    # 共振判断
    if not scores: return r
    bull_count = sum(1 for s in signals if s in ("bullish", "neutral_bullish"))
    if len(scores) >= 3 and bull_count == 3: r.resonance_level = "triple"
    elif len(scores) >= 2 and bull_count >= 2: r.resonance_level = "double"
    elif bull_count >= 1: r.resonance_level = "single"
    else: r.resonance_level = "none"
    r.resonance_score = sum(scores)/len(scores) if scores else 50
    if r.resonance_score >= 65: r.quality_signal = True; r.buy_signals.append("多周期共振")
    return r
