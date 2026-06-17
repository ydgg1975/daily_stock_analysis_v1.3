#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Step 5: 统一技术指标引擎 — MACD/RSI/KDJ/布林带/ATR/均线/量价"""
import math
from typing import List
from dataclasses import dataclass, field

@dataclass
class IndicatorResult:
    macd_dif: float = 0; macd_dea: float = 0; macd_bar: float = 0
    macd_signal: str = '中性'
    rsi14: float = 50; rsi_signal: str = '中性'
    kdj_k: float = 50; kdj_d: float = 50; kdj_j: float = 50
    bb_upper: float = 0; bb_mid: float = 0; bb_lower: float = 0
    bb_width: float = 0; bb_pos: float = 50
    atr14: float = 0; atr_pct: float = 0
    ma5: float = 0; ma10: float = 0; ma20: float = 0; ma60: float = 0
    ma_status: str = '中性'
    vol_ratio_520: float = 1.0
    buy_signals: List[str] = field(default_factory=list)
    sell_signals: List[str] = field(default_factory=list)

def compute_all_indicators(closes, highs, lows, volumes, price):
    r = IndicatorResult(); n = len(closes)
    if n < 10: return r
    # MA
    r.ma5 = sum(closes[-5:])/5; r.ma10 = sum(closes[-10:])/10
    r.ma20 = sum(closes[-20:])/20 if n>=20 else sum(closes)/n
    r.ma60 = sum(closes[-60:])/60 if n>=60 else r.ma20
    if r.ma5>r.ma10>r.ma20>r.ma60: r.ma_status='完全多头'
    elif r.ma5>r.ma10>r.ma20: r.ma_status='短期多头'
    elif price<r.ma60: r.ma_status='空头弱势'
    else: r.ma_status='震荡'
    # MACD
    e12=[closes[0]]; e26=[closes[0]]
    for i in range(1,n):
        e12.append(closes[i]*2/13+e12[-1]*11/13)
        e26.append(closes[i]*2/27+e26[-1]*25/27)
    dif=[e12[i]-e26[i] for i in range(n)]
    dea=[dif[0]]
    for i in range(1,n): dea.append(dif[i]*2/10+dea[-1]*8/10)
    r.macd_dif=round(dif[-1],3); r.macd_dea=round(dea[-1],3)
    r.macd_bar=round((dif[-1]-dea[-1])*2,3)
    if dif[-1]>dea[-1] and dif[-1]>0: r.macd_signal='多头'
    elif dif[-1]>dea[-1]: r.macd_signal='金叉'
    else: r.macd_signal='空头'
    # RSI
    gains=[max(closes[i]-closes[i-1],0) for i in range(n-14,n)]
    losses=[max(closes[i-1]-closes[i],0) for i in range(n-14,n)]
    avg_g=sum(gains)/14; avg_l=sum(losses)/14
    r.rsi14=round(100-100/(1+avg_g/avg_l),1) if avg_l>0 else 100
    if r.rsi14>70: r.rsi_signal='超买'
    elif r.rsi14<30: r.rsi_signal='超卖'
    else: r.rsi_signal='中性'
    # KDJ
    l9=min(lows[-9:]); h9=max(highs[-9:])
    rsv=(closes[-1]-l9)/(h9-l9)*100 if h9!=l9 else 50
    r.kdj_k=round(rsv/3+50*2/3,1); r.kdj_d=round(r.kdj_k/3+50*2/3,1)
    r.kdj_j=round(3*r.kdj_k-2*r.kdj_d,1)
    # BB
    bb_mid=r.ma20
    bb_std=math.sqrt(sum((c-bb_mid)**2 for c in closes[-20:])/20) if n>=20 else 0
    r.bb_upper=round(bb_mid+2*bb_std,2); r.bb_mid=round(bb_mid,2)
    r.bb_lower=round(bb_mid-2*bb_std,2)
    if bb_mid>0: r.bb_width=round((r.bb_upper-r.bb_lower)/bb_mid*100,1)
    if r.bb_upper!=r.bb_lower: r.bb_pos=round((price-r.bb_lower)/(r.bb_upper-r.bb_lower)*100,1)
    # ATR
    tr=[]
    for i in range(n-14,n):
        tr.append(max(highs[i]-lows[i],abs(highs[i]-closes[i-1]),abs(lows[i]-closes[i-1])))
    r.atr14=round(sum(tr)/14,2)
    if price>0: r.atr_pct=round(r.atr14/price*100,2)
    # Volume
    v5=sum(volumes[-5:])/5; v20=sum(volumes[-20:])/20
    r.vol_ratio_520=round(v5/v20,2) if v20>0 else 1
    # Signals
    if r.ma_status in ('完全多头','短期多头'): r.buy_signals.append('均线多头')
    if r.macd_signal=='多头': r.buy_signals.append('MACD多头')
    if 30<=r.rsi14<45: r.buy_signals.append('RSI偏低')
    if r.vol_ratio_520>1.5: r.buy_signals.append('放量')
    if r.macd_signal=='空头': r.sell_signals.append('MACD空头')
    if r.rsi14>70: r.sell_signals.append('RSI超买')
    return r

if __name__=='__main__':
    import random; random.seed(42)
    c=[100+sum(random.gauss(0,2) for _ in range(i)) for i in range(1,101)]
    h=[x+random.uniform(0,3) for x in c]; l=[x-random.uniform(0,3) for x in c]
    v=[random.uniform(1e4,5e4) for _ in range(100)]
    r=compute_all_indicators(c,h,l,v,c[-1])
    print(f'MA5={r.ma5:.2f} MACD={r.macd_signal} RSI={r.rsi14} BB={r.bb_pos:.0f}%')
    print(f'Buy:{r.buy_signals} Sell:{r.sell_signals}')
