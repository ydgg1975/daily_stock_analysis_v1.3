#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os, json, urllib.request, logging
from pathlib import Path
from datetime import datetime

PROJ = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJ))
Path(PROJ/"data"/"logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler(PROJ/"data"/"logs"/"monitor.log",encoding="utf-8"),logging.StreamHandler()])
logger = logging.getLogger("monitor")
SCT = "SCT363204TpHVA8URZu9qAL3syyy12DjE3"

def is_open():
    from steps.trading_calendar import is_trading_day, is_market_open
    return is_trading_day() and is_market_open()

def load_pos():
    f=PROJ/"data"/"sim_state.json"
    return json.loads(f.read_text()).get("positions",{}) if f.exists() else {}

def get_quote(codes):
    pref=[]
    for c in codes:
        pfx="sh" if c.startswith(("6","9")) else "sz"
        pref.append(pfx+c)
    url="https://qt.gtimg.cn/q="+",".join(pref)
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    resp=urllib.request.urlopen(req,timeout=10)
    data=resp.read().decode("gbk",errors="replace")
    prices={}
    for line in data.strip().split(";"):
        if "=" not in line or chr(34) not in line: continue
        vals=line.split(chr(34))[1].split("~")
        if len(vals)<53: continue
        code=line.split("=")[0].split("_")[-1][2:]
        prices[code]={"price":float(vals[3]) if vals[3] else 0,
            "change":float(vals[32]) if vals[32] else 0,
            "vol":float(vals[49]) if vals[49] else 0}
    return prices

def push(title,content):
    try:
        import urllib.parse
        data=urllib.parse.urlencode({"title":title,"desp":content}).encode()
        urllib.request.urlopen(urllib.request.Request(f"https://sctapi.ftqq.com/{SCT}.send",data=data),timeout=10)
        logger.info(f"Pushed: {title}")
    except Exception as e: logger.warning(f"Push err: {e}")

def run():
    if not is_open(): logger.info("Closed"); return
    pos=load_pos()
    if not pos: logger.info("No positions"); return
    prices=get_quote(list(pos.keys()))
    alerts=[]; total_pnl=0
    for code,p in pos.items():
        q=prices.get(code,{})
        cur=q.get("price",p.get("entry_price",0))
        entry=p.get("entry_price",cur)
        sl=p.get("stop_loss",entry*0.95)
        tp=p.get("take_profit",entry*1.10)
        sh=p.get("shares",0)
        pnl=(cur-entry)/entry*100 if entry>0 else 0
        total_pnl+=(cur-entry)*sh
        p["current_price"]=cur; p["market_value"]=cur*sh
        if cur<=sl:
            a=f"{code} {p["name"]}: STOP {cur:.2f}<={sl:.2f} {pnl:+.1f}%"
            alerts.append(a); logger.warning(a)
        elif cur>=tp:
            a=f"{code} {p["name"]}: TARGET {cur:.2f}>={tp:.2f} {pnl:+.1f}%"
            alerts.append(a); logger.warning(a)
        elif pnl>=5:
            p["stop_loss"]=entry
            a=f"{code} {p["name"]}: +{pnl:.1f}% trailing->cost"
            alerts.append(a); logger.info(a)
    state={"cash":506070,"positions":pos,
        "total_value":506070+sum(p.get("market_value",0) for p in pos.values()),
        "last_monitor":datetime.now().isoformat()}
    (PROJ/"data"/"sim_state.json").write_text(json.dumps(state,indent=2,ensure_ascii=False))
    logger.info(f"Done. PnL={total_pnl:+,.0f}")
    if alerts:
        push(f"Monitor: {len(alerts)} alerts", chr(10).join(alerts[:5]))

if __name__=="__main__": run()