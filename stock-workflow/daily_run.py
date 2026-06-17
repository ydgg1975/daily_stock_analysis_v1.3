#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os, json, logging, time
from pathlib import Path
from datetime import datetime, timedelta

PROJ = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJ))
Path(PROJ/"data"/"logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(PROJ/"data"/"logs"/f"daily_{datetime.now():%Y%m%d}.log",encoding="utf-8"),
              logging.StreamHandler()])
logger = logging.getLogger("daily")

def run():
    from steps.trading_calendar import is_trading_day
    from steps.step0_market_check import check_market_environment
    from data_source import DataSource
    from steps.screener import StockScreener
    from rules.chan_theory_signals import run_chan_analysis
    from rules.multi_timeframe import multi_timeframe_analysis
    from steps.step5_indicators import compute_all_indicators
    import json

    t0 = datetime.now()
    logger.info("="*60)
    logger.info(f"九步闭环: {t0:%Y-%m-%d %H:%M}")

    if not is_trading_day():
        logger.info("non-trading"); return
    mr = check_market_environment()
    logger.info(f"[0] 市场: {mr['score']:.0f}分 {mr['advice']}")

    ds = DataSource(); screener = StockScreener(ds)
    try:
        df = screener.run()
        if df is None or df.empty:
            logger.info("no candidates"); return
        cands = df.head(15).to_dict("records")
        logger.info(f"[1] {len(cands)} candidates")
    except Exception as e:
        logger.error(f"[1] {e}"); return

    results = []
    for c in cands[:10]:
        code = c["code"]
        try:
            kdf = ds.get_daily(code, 120)
            if kdf is None or len(kdf) < 30: continue
            r = {"code":code,"name":c.get("name",""),"price":c.get("price",0),
                 "chan":50,"mtf":50,"ind":50}
            try: cr=run_chan_analysis(kdf); r["chan"]=cr.get("score",50); r["chan_sig"]=cr.get("signal",False)
            except: pass
            try: mtf=multi_timeframe_analysis(code,day_df=kdf); r["mtf"]=mtf.resonance_score; r["mtf_lv"]=mtf.resonance_level
            except: pass
            try:
                cl=kdf["close"].values; hi=kdf["high"].values; lo=kdf["low"].values
                vc="vol" if "vol" in kdf.columns else "volume"; vo=kdf[vc].values
                ind=compute_all_indicators(cl,hi,lo,vo,cl[-1]); isc=50
                if ind.ma_status in ("完全多头","短期多头"): isc+=15
                if ind.macd_signal=="多头": isc+=10
                if 30<=ind.rsi14<50: isc+=10
                if ind.vol_ratio_520>1.5: isc+=8
                r["ind"]=max(0,min(100,isc)); r["macd"]=ind.macd_signal
                r["rsi"]=ind.rsi14; r["ma"]=ind.ma_status; r["atr"]=ind.atr14
            except: pass
            s=0
            raw=c.get("signal_strength","弱"); w={"强":90,"中":65,"弱":30}.get(raw,50); s+=w*0.30
            cc=c.get("cc_score",0) or 0; ccw=min(100,cc*25) if cc>0 else 30; s+=ccw*0.15
            vr=c.get("vol_ratio",1.0) or 1.0; vw=min(100,vr*40); s+=vw*0.15
            ts=(r["ind"]+r["mtf"])/2; s+=ts*0.15
            to=c.get("turnover",c.get("turnover_pct",1.0)) or 1.0; lw=min(100,to*12); s+=lw*0.10
            hw=80 if r.get("chan_sig") else 50; s+=hw*0.10
            mw=min(100,mr.get("score",50)); s+=mw*0.05; ms=r["mtf"]; s+=ms*0.10
            r["composite"]=round(s,1); results.append(r)
        except Exception as e: logger.warning(f"[{code}] {e}")

    results.sort(key=lambda x:x["composite"],reverse=True)
    logger.info(f"[2-4] {len(results)} analyzed")
    for r in results[:5]:
        logger.info(f"  {r['code']} {r['name']}: cmp={r['composite']} chan={r['chan']} mtf={r['mtf']} ind={r['ind']}")

    (PROJ/"data"/"candidates.json").write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str))
    elapsed = (datetime.now()-t0).total_seconds()
    logger.info(f"DONE: {elapsed:.0f}s")

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--now",action="store_true")
    args=ap.parse_args(); run()
