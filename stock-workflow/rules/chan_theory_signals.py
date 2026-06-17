#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pandas as pd, numpy as np
from typing import Dict, Any, Optional

class ChanSignals:
    def __init__(self, df):
        self.df = df
        self.closes = df["close"].values if "close" in df.columns else df.iloc[:,-1].values
        self.highs = df["high"].values if "high" in df.columns else df.iloc[:,-3].values
        self.lows = df["low"].values if "low" in df.columns else df.iloc[:,-2].values

    def find_pivots(self, window=2):
        highs, lows = [], []
        n = len(self.closes)
        for i in range(window, n-window):
            if all(self.highs[i] >= self.highs[i-j] for j in range(1,window+1)) and all(self.highs[i] >= self.highs[i+j] for j in range(1,window+1)):
                highs.append((i, self.highs[i]))
            if all(self.lows[i] <= self.lows[i-j] for j in range(1,window+1)) and all(self.lows[i] <= self.lows[i+j] for j in range(1,window+1)):
                lows.append((i, self.lows[i]))
        return highs, lows

    def analyze(self) -> Dict[str, Any]:
        highs, lows = self.find_pivots()
        n = len(self.closes); price = float(self.closes[-1])
        zs_top = max(h[1] for h in highs[-3:]) if highs else price*1.05
        zs_bot = max(l[1] for l in lows[-3:]) if lows else price*0.95
        score = 50
        if price > zs_top: score += 15  # 突破中枢
        elif price < zs_bot: score -= 15  # 跌破中枢
        if price > sum(self.closes[-20:])/20: score += 5
        return {"pivots_high": len(highs), "pivots_low": len(lows), "zs_top": zs_top, "zs_bot": zs_bot, "score": score, "signal": score >= 60}

def run_chan_analysis(df) -> Dict[str, Any]:
    return ChanSignals(df).analyze()
