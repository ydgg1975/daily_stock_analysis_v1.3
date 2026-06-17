#!/usr/bin/env python
# -*- coding: utf-8 -*-
import numpy as np
from typing import Dict, Any, Optional

def calc_atr_position(atr14: float, price: float, base_weight: float = 0.20) -> Dict[str, Any]:
    atr_pct = atr14 / price * 100 if price > 0 else 3
    if atr_pct < 2: risk_budget = 0.015; weight = min(base_weight, 0.25)
    elif atr_pct < 4: risk_budget = 0.010; weight = min(base_weight, 0.20)
    elif atr_pct < 6: risk_budget = 0.007; weight = min(base_weight, 0.15)
    else: risk_budget = 0.004; weight = min(base_weight, 0.10)
    shares_mult = risk_budget / atr_pct if atr_pct > 0 else 1
    return {"atr_pct": round(atr_pct,2), "risk_budget": risk_budget, "weight": weight, "shares_mult": round(shares_mult,3)}

def diversify_positions(positions, max_same_industry=2, max_same_sub=1):
    # 行业去相关化 - 基础实现
    industry_count = {}
    optimized = []
    for pos in positions:
        ind = pos.get("industry", "unknown")
        if industry_count.get(ind, 0) < max_same_industry:
            optimized.append(pos)
            industry_count[ind] = industry_count.get(ind, 0) + 1
    return optimized
