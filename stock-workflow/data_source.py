#!/usr/bin/env python
"""
A股全栈数据层 — 三层架构 + 内置限流防封
============================================================================
优先级: mootdx (TCP 7709, 不封IP) > 腾讯财经 (HTTP GBK, 不封IP) > 东财 (HTTP, 已内置限流)

架构分层:
  Layer 1 (首选):  mootdx          → K线(日/周/月/60分) + 五档盘口 + 逐笔成交
  Layer 2 (首选):  腾讯财经         → PE/PB/市值/换手率/涨跌停/指数/ETF (88字段)
  Layer 3 (限流):  东财 eastmoney   → 资金流向/龙虎榜/解禁/融资融券/大宗交易/股东户数/分红/概念板块
  辅助层:          同花顺 THS       → 当日强势股+题材归因 / 北向资金
  辅助层:          东财行业板块     → 行业涨跌排名

东财防封策略:
  - 串行限流 (EM_MIN_INTERVAL=1.2s + 随机抖动)
  - 复用 HTTP Session (Keep-Alive)
  - 默认 UA + Referer
  - 所有 eastmoney.com 接口统一走 em_get()

市场前缀规则:  6/9开头→sh, 8开头→bj, 其余→sz
Ticker归一化:  去除 SH/SZ/BJ 前缀和 .SH/.SZ/.BJ 后缀

依赖: mootdx, requests, pandas, pyyaml
"""

from __future__ import annotations

import json
import re
import time
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# 全局常量
# ══════════════════════════════════════════════════════════════════════════════

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

# ── 通达信 (mootdx) ──────────────────────────────────────────────────────────
MOOTDX_HOSTS = [
    ("110.41.147.114", 7709),
    ("110.41.2.72", 7709),
]

# ── 腾讯财经 ─────────────────────────────────────────────────────────────────
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="

# ── 东财 (eastmoney) ─────────────────────────────────────────────────────────
EM_DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
EM_PUSH2_URL = "https://push2.eastmoney.com/api/qt"
EM_PUSH2_HIS_URL = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
EM_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"

# 东财限流参数
EM_MIN_INTERVAL = 1.2          # 最小请求间隔(秒), 批量建议 1.5~2.0
EM_SESSION: Optional[requests.Session] = None
_em_last_call: float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════════════════

def get_market_prefix(code: str) -> str:
    """6位代码 → 市场前缀 (sh/sz/bj)"""
    code = normalize_ticker(code)
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith("8"):
        return "bj"
    else:
        return "sz"


def get_market_code(code: str) -> int:
    """6位代码 → 东财市场代码 (1=上海, 0=深圳/北京)"""
    code = normalize_ticker(code)
    return 1 if code.startswith("6") else 0


def normalize_ticker(code: str) -> str:
    """
    Ticker格式归一化 → 纯6位数字。
    支持: 688017 / SH688017 / sh688017 / 688017.SH / 688017.sh / SZ000001 / BJ832000
    """
    code = str(code).strip().upper()
    # 去除 .SH / .SZ / .BJ 后缀
    if "." in code:
        code = code.split(".")[0]
    # 去除 SH / SZ / BJ 前缀
    for prefix in ("SH", "SZ", "BJ"):
        if code.startswith(prefix) and len(code) == 8:
            code = code[2:]
    return code


def build_tencent_codes(codes: list[str]) -> list[str]:
    """给纯数字代码加上腾讯所需的前缀 sh/sz/bj"""
    result = []
    for c in codes:
        c = normalize_ticker(c)
        prefix = get_market_prefix(c)
        result.append(f"{prefix}{c}")
    return result


def build_em_secid(code: str) -> str:
    """构建东财 secid: 1.600519 / 0.000001"""
    code = normalize_ticker(code)
    market = get_market_code(code)
    return f"{market}.{code}"


# ══════════════════════════════════════════════════════════════════════════════
# 东财统一限流入口
# ══════════════════════════════════════════════════════════════════════════════

def _get_em_session() -> requests.Session:
    """获取或创建东财共享 Session (Keep-Alive)"""
    global EM_SESSION
    if EM_SESSION is None:
        EM_SESSION = requests.Session()
        EM_SESSION.headers.update({
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
    return EM_SESSION


def em_get(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = 15,
    **kwargs,
) -> requests.Response:
    """
    东财统一请求入口 — 自动节流 + 复用 Session + 默认 UA。

    所有 eastmoney.com 接口都应通过它请求，避免高频被封 IP。

    限流策略:
      - 每次请求前检查距上次请求的间隔
      - 不足 EM_MIN_INTERVAL 则 sleep(剩余时间 + 随机抖动 0.1~0.5s)
      - 请求完成后更新时间戳
    """
    global _em_last_call

    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call)
    if wait > 0:
        jitter = random.uniform(0.1, 0.5)
        time.sleep(wait + jitter)

    session = _get_em_session()
    merged_headers = {
        "Referer": "https://quote.eastmoney.com/",
    }
    if headers:
        merged_headers.update(headers)

    try:
        resp = session.get(url, params=params, headers=merged_headers, timeout=timeout, **kwargs)
        return resp
    finally:
        _em_last_call = time.time()


def set_em_interval(seconds: float):
    """动态调整东财请求间隔 (批量任务时调大)"""
    global EM_MIN_INTERVAL
    EM_MIN_INTERVAL = max(0.5, seconds)


# ══════════════════════════════════════════════════════════════════════════════
# 东财数据中心统一查询 helper
# ══════════════════════════════════════════════════════════════════════════════

def eastmoney_datacenter(
    report_name: str,
    columns: str = "ALL",
    filter_str: str = "",
    page_size: int = 50,
    sort_columns: str = "",
    sort_types: str = "-1",
) -> list[dict]:
    """
    东财数据中心统一查询 — 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用。

    参数:
        report_name: 报表名称, 如 "RPT_DAILYBILLBOARD_DETAILSNEW"
        columns:     返回字段, "ALL"=全部
        filter_str:  过滤条件, 如 '(SECURITY_CODE="600519")'
        page_size:   每页条数
        sort_columns:排序字段
        sort_types:  排序方式 "-1"=降序 "1"=升序

    返回: list[dict]
    """
    params = {
        "reportName": report_name,
        "columns": columns,
        "filter": filter_str,
        "pageNumber": "1",
        "pageSize": str(page_size),
        "sortColumns": sort_columns,
        "sortTypes": sort_types,
        "source": "WEB",
        "client": "WEB",
    }
    try:
        r = em_get(EM_DATACENTER_URL, params=params, timeout=15)
        d = r.json()
        if d.get("result") and d["result"].get("data"):
            return d["result"]["data"]
    except Exception as e:
        logger.warning(f"东财数据中心查询失败 [{report_name}]: {e}")
    return []


# ══════════════════════════════════════════════════════════════════════════════
# Layer 1: mootdx — K线 + 实时报价 + 逐笔成交 (TCP 7709, 不封IP)
# ══════════════════════════════════════════════════════════════════════════════

class MootdxClient:
    """
    通达信行情客户端 (mootdx TCP 协议)。

    特性:
      - 直连通达信行情服务器 (port 7709), 无需注册, 不封IP
      - 支持多周期K线: 日线/周线/月线/1分/5分/15分/30分/60分
      - 支持实时报价 (46字段, 含五档盘口)
      - 支持逐笔成交
    """

    # category 映射
    CATEGORY_MAP = {
        "1min":  7,  "5min":  8,  "15min": 9,  "30min": 10,
        "60min": 11, "day":   4,  "week":  5,  "month": 6,
    }

    def __init__(self, hosts: list[tuple[str, int]] | None = None):
        self._hosts = hosts or MOOTDX_HOSTS
        self._client = None
        self._connected = False
        self.available = False
        self._init()

    def _init(self):
        """初始化 mootdx 客户端"""
        try:
            from mootdx.quotes import Quotes
            self._client = Quotes.factory(market="std")
            # 尝试连接以验证可用性
            try:
                test = self._client.quotes(symbol=["000001"])
                if test:
                    self.available = True
                    self._connected = True
                    logger.info("[DATA] mootdx(TCP 7709) 已连接 — 不封IP, K线/盘口/逐笔")
            except Exception:
                # 连接失败但库可用, 后续按需连接
                self.available = True
                logger.warning("[DATA] mootdx 库可用但连接失败, 将按需重连")
        except ImportError:
            logger.warning("[DATA] mootdx 未安装, pip install mootdx")
            self.available = False
        except Exception as e:
            logger.error(f"[DATA] mootdx 初始化失败: {e}")
            self.available = False

    def _ensure_client(self):
        """确保客户端可用"""
        if not self.available:
            raise RuntimeError("mootdx 不可用, 请安装: pip install mootdx")
        if self._client is None:
            from mootdx.quotes import Quotes
            self._client = Quotes.factory(market="std")

    def get_kline(
        self,
        symbol: str,
        period: str = "day",
        count: int = 250,
    ) -> pd.DataFrame:
        """
        获取K线数据。

        参数:
            symbol: 股票代码 (6位数字)
            period: 周期 "1min"/"5min"/"15min"/"30min"/"60min"/"day"/"week"/"month"
            count:  获取根数

        返回: DataFrame [date, open, high, low, close, vol, amount]
        """
        self._ensure_client()
        code = normalize_ticker(symbol)
        category = self.CATEGORY_MAP.get(period, 4)

        try:
            data = self._client.bars(symbol=code, category=category, offset=count)
            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)
            # 标准列名映射
            col_map = {
                "datetime": "date", "open": "open", "high": "high",
                "low": "low", "close": "close", "volume": "vol", "amount": "amount",
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
            return df
        except Exception as e:
            logger.error(f"mootdx K线获取失败 [{code}]: {e}")
            return pd.DataFrame()

    def get_daily(self, symbol: str, count: int = 250) -> pd.DataFrame:
        """日线K线 (便捷方法)"""
        return self.get_kline(symbol, "day", count)

    def get_weekly(self, symbol: str, count: int = 100) -> pd.DataFrame:
        """周线K线"""
        return self.get_kline(symbol, "week", count)

    def get_monthly(self, symbol: str, count: int = 60) -> pd.DataFrame:
        """月线K线"""
        return self.get_kline(symbol, "month", count)

    def get_60min(self, symbol: str, count: int = 200) -> pd.DataFrame:
        """60分钟K线"""
        return self.get_kline(symbol, "60min", count)

    def get_quote(self, symbols: list[str]) -> list[dict]:
        """
        实时报价 (46字段, 含五档盘口)。

        参数:
            symbols: 股票代码列表

        返回: [{price, open, high, low, last_close, bid1~bid5, ask1~ask5, ...}]
        """
        self._ensure_client()
        codes = [normalize_ticker(s) for s in symbols]
        try:
            return self._client.quotes(symbol=codes)
        except Exception as e:
            logger.error(f"mootdx 实时报价失败: {e}")
            return []

    def get_transactions(self, symbol: str, date: str | None = None) -> list[dict]:
        """
        逐笔成交 (非交易时间返回空)。

        参数:
            symbol: 股票代码
            date:   日期 'YYYYMMDD', None=今天

        返回: [{time, price, vol, num, buyorsell(0买/1卖/2中性)}]
        """
        self._ensure_client()
        code = normalize_ticker(symbol)
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        try:
            return self._client.transaction(symbol=code, date=date)
        except Exception as e:
            logger.error(f"mootdx 逐笔成交失败 [{code}]: {e}")
            return []


# ══════════════════════════════════════════════════════════════════════════════
# Layer 2: 腾讯财经 — PE/PB/市值/换手率/涨跌停/指数/ETF (HTTP GBK, 不封IP)
# ══════════════════════════════════════════════════════════════════════════════

def tencent_quote(codes: list[str]) -> dict[str, dict]:
    """
    批量拉取腾讯财经实时行情 (88字段, GBK编码, ~分隔)。

    支持:
      - 个股: ["688017", "300476", "002463"]
      - 指数: ["000001", "000300", "399006"]
      - ETF:  ["510050", "510300"]

    返回字段索引 (实测校准 2026-05):
        1=名称, 3=当前价, 4=昨收, 5=今开,
        31=涨跌额, 32=涨跌幅%, 33=最高, 34=最低,
        37=成交额(万), 38=换手率%, 39=PE(TTM),
        43=振幅%(非PB!), 44=总市值(亿), 45=流通市值(亿),
        46=PB(市净率), 47=涨停价, 48=跌停价,
        49=量比, 52=PE(静)

    返回: {code: {name, price, pe_ttm, pb, mcap_yi, ...}}
    """
    import urllib.request

    prefixed = build_tencent_codes(codes)
    if not prefixed:
        return {}

    url = TENCENT_QUOTE_URL + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode("gbk")
    except Exception as e:
        logger.error(f"腾讯行情请求失败: {e}")
        return {}

    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]  # 去除 sh/sz/bj 前缀
        try:
            result[code] = {
                "name":          vals[1],
                "price":         float(vals[3]) if vals[3] else 0.0,
                "last_close":    float(vals[4]) if vals[4] else 0.0,
                "open":          float(vals[5]) if vals[5] else 0.0,
                "change_amt":    float(vals[31]) if vals[31] else 0.0,
                "change_pct":    float(vals[32]) if vals[32] else 0.0,
                "high":          float(vals[33]) if vals[33] else 0.0,
                "low":           float(vals[34]) if vals[34] else 0.0,
                "amount_wan":    float(vals[37]) if vals[37] else 0.0,
                "turnover_pct":  float(vals[38]) if vals[38] else 0.0,
                "pe_ttm":        float(vals[39]) if vals[39] else 0.0,
                "amplitude_pct": float(vals[43]) if vals[43] else 0.0,
                "mcap_yi":       float(vals[44]) if vals[44] else 0.0,
                "float_mcap_yi": float(vals[45]) if vals[45] else 0.0,
                "pb":            float(vals[46]) if vals[46] else 0.0,
                "limit_up":      float(vals[47]) if vals[47] else 0.0,
                "limit_down":    float(vals[48]) if vals[48] else 0.0,
                "vol_ratio":     float(vals[49]) if vals[49] else 0.0,
                "pe_static":     float(vals[52]) if vals[52] else 0.0,
            }
        except (ValueError, IndexError) as e:
            logger.debug(f"腾讯行情解析失败 [{code}]: {e}")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Layer 3: 东财 eastmoney — 独有数据 (资金流/龙虎榜/解禁/融资融券/大宗交易/股东/分红)
# ══════════════════════════════════════════════════════════════════════════════

# ── 3.1 概念板块归属 ─────────────────────────────────────────────────────────

def eastmoney_concept_blocks(code: str) -> dict:
    """
    个股所属板块/概念归属 (东财 slist, spt=3, 一次请求拿全)。

    返回: {total, boards: [{name, code(BK码), change_pct, lead_stock}], concept_tags: [...]}

    注意: 东财把行业/概念/地域混在一个列表返回, 板块名自解释。
    例如: '食品饮料'=行业, '贵州板块'=地域, '酿酒概念'=概念。
    """
    code = normalize_ticker(code)
    market_code = get_market_code(code)

    params = {
        "fltt": "2", "invt": "2",
        "secid": f"{market_code}.{code}",
        "spt": "3", "pi": "0", "pz": "200", "po": "1",
        "fields": "f12,f14,f3,f128",
    }
    headers = {"Referer": "https://quote.eastmoney.com/"}

    try:
        r = em_get(
            f"{EM_PUSH2_URL}/slist/get",
            params=params, headers=headers, timeout=15,
        )
        d = r.json()
    except Exception as e:
        logger.warning(f"东财板块归属请求失败 [{code}]: {e}")
        return {"total": 0, "boards": [], "concept_tags": []}

    diff = (d.get("data") or {}).get("diff") or {}
    items = diff.values() if isinstance(diff, dict) else diff
    boards = []
    for it in items:
        boards.append({
            "name":        it.get("f14", ""),
            "code":        it.get("f12", ""),
            "change_pct":  it.get("f3", ""),
            "lead_stock":  it.get("f128", ""),
        })
    return {
        "total": len(boards),
        "boards": boards,
        "concept_tags": [b["name"] for b in boards],
    }


# ── 3.2 个股资金流向 (分钟级) ────────────────────────────────────────────────

def eastmoney_fund_flow_minute(code: str) -> list[dict]:
    """
    个股资金流向 (分钟级, 当日盘中)。

    返回: [{time, main_net, small_net, mid_net, large_net, super_net}, ...]
    单位: 元
    """
    code = normalize_ticker(code)
    secid = build_em_secid(code)

    params = {
        "secid": secid, "klt": 1,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    headers = {
        "Referer": "https://quote.eastmoney.com/",
        "Origin": "https://quote.eastmoney.com",
    }

    try:
        r = em_get(
            f"{EM_PUSH2_URL}/stock/fflow/kline/get",
            params=params, headers=headers, timeout=10,
        )
        d = r.json()
    except Exception as e:
        logger.warning(f"push2 资金流请求失败 [{code}]: {e}")
        return []

    rows = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append({
                "time":       parts[0],
                "main_net":   float(parts[1]),
                "small_net":  float(parts[2]),
                "mid_net":    float(parts[3]),
                "large_net":  float(parts[4]),
                "super_net":  float(parts[5]),
            })
    return rows


# ── 3.3 个股资金流 (120日, 日级) ─────────────────────────────────────────────

def stock_fund_flow_120d(code: str) -> list[dict]:
    """
    个股资金流 (日级, 最近120个交易日)。

    返回: [{date, main_net, small_net, mid_net, large_net, super_net}]
    单位: 元
    """
    code = normalize_ticker(code)
    market_code = get_market_code(code)

    params = {
        "secid": f"{market_code}.{code}",
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "lmt": "120",
    }
    headers = {
        "Referer": "https://quote.eastmoney.com/",
        "Origin": "https://quote.eastmoney.com",
    }

    try:
        r = em_get(EM_PUSH2_HIS_URL, params=params, headers=headers, timeout=15)
        d = r.json()
    except Exception as e:
        logger.warning(f"push2his 资金流请求失败 [{code}]: {e}")
        return []

    rows = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 7:
            rows.append({
                "date":       parts[0],
                "main_net":   float(parts[1]) if parts[1] != "-" else 0.0,
                "small_net":  float(parts[2]) if parts[2] != "-" else 0.0,
                "mid_net":    float(parts[3]) if parts[3] != "-" else 0.0,
                "large_net":  float(parts[4]) if parts[4] != "-" else 0.0,
                "super_net":  float(parts[5]) if parts[5] != "-" else 0.0,
            })
    return rows


# ── 3.4 行业板块排名 ─────────────────────────────────────────────────────────

def industry_comparison(top_n: int = 10) -> dict:
    """
    全行业涨跌幅排名 (东财行业板块, ~100个行业)。

    返回: {top: [{rank, name, change_pct, code, up_count, down_count, leader, leader_change}],
           bottom: [...], total: int}

    用法:
        data = industry_comparison(10)
        print("TOP5:", data["top"][:5])
        print("BOT5:", data["bottom"][:5])
    """
    url = f"{EM_PUSH2_URL}/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "fltt": "2", "invt": "2",
        "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
    }
    headers = {"Referer": "https://quote.eastmoney.com/"}

    try:
        r = em_get(url, params=params, headers=headers, timeout=15)
        d = r.json()
    except Exception as e:
        logger.warning(f"行业板块排名请求失败: {e}")
        return {"top": [], "bottom": [], "total": 0}

    items = d.get("data", {}).get("diff", [])
    if not items:
        return {"top": [], "bottom": [], "total": 0}

    rows = []
    for i, item in enumerate(items):
        rows.append({
            "rank":          i + 1,
            "name":          item.get("f14", ""),
            "change_pct":    item.get("f3", 0),
            "code":          item.get("f12", ""),
            "up_count":      item.get("f104", 0),
            "down_count":    item.get("f105", 0),
            "leader":        item.get("f140", ""),
            "leader_change": item.get("f136", 0),
        })

    return {
        "top":    rows[:top_n],
        "bottom": rows[-top_n:] if len(rows) >= top_n else rows,
        "total":  len(rows),
    }


# ── 3.5 龙虎榜席位 (个股) ────────────────────────────────────────────────────

def dragon_tiger_board(code: str, trade_date: str, look_back: int = 30) -> dict:
    """
    龙虎榜数据聚合 (个股上榜记录 + 买卖席位 TOP5 + 机构动向)。

    参数:
        code:       股票代码
        trade_date: 日期 'YYYY-MM-DD'
        look_back:  回看天数

    返回: {records: [...], seats: {buy: [...], sell: [...]}, institution: {buy_amt, sell_amt, net_amt}}
    """
    code = normalize_ticker(code)
    start = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=look_back)
    start_str = start.strftime("%Y-%m-%d")

    # 1. 上榜记录
    records = []
    data = eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f"(TRADE_DATE>='{start_str}')(TRADE_DATE<='{trade_date}')(SECURITY_CODE=\"{code}\")",
        page_size=50,
        sort_columns="TRADE_DATE", sort_types="-1",
    )
    for row in data:
        records.append({
            "date":      str(row.get("TRADE_DATE", ""))[:10],
            "reason":    row.get("EXPLANATION", ""),
            "net_buy":   round((row.get("BILLBOARD_NET_AMT") or 0) / 10000, 1),
            "turnover":  round(float(row.get("TURNOVERRATE") or 0), 2),
        })

    # 2. 最近上榜的买卖席位
    seats = {"buy": [], "sell": []}
    buy_data, sell_data = [], []
    if records:
        latest_date = records[0]["date"]
        # 买入席位
        buy_data = eastmoney_datacenter(
            "RPT_BILLBOARD_DAILYDETAILSBUY",
            filter_str=f"(TRADE_DATE='{latest_date}')(SECURITY_CODE=\"{code}\")",
            page_size=10,
            sort_columns="BUY", sort_types="-1",
        )
        for row in buy_data[:5]:
            seats["buy"].append({
                "name":      row.get("OPERATEDEPT_NAME", ""),
                "buy_amt":   round((row.get("BUY") or 0) / 10000, 1),
                "sell_amt":  round((row.get("SELL") or 0) / 10000, 1),
                "net":       round((row.get("NET") or 0) / 10000, 1),
            })
        # 卖出席位
        sell_data = eastmoney_datacenter(
            "RPT_BILLBOARD_DAILYDETAILSSELL",
            filter_str=f"(TRADE_DATE='{latest_date}')(SECURITY_CODE=\"{code}\")",
            page_size=10,
            sort_columns="SELL", sort_types="-1",
        )
        for row in sell_data[:5]:
            seats["sell"].append({
                "name":      row.get("OPERATEDEPT_NAME", ""),
                "buy_amt":   round((row.get("BUY") or 0) / 10000, 1),
                "sell_amt":  round((row.get("SELL") or 0) / 10000, 1),
                "net":       round((row.get("NET") or 0) / 10000, 1),
            })

    # 3. 机构买卖统计 (OPERATEDEPT_CODE="0"=机构专用)
    institution = {"buy_amt": 0.0, "sell_amt": 0.0, "net_amt": 0.0}
    for detail_data, side in [(buy_data, "buy"), (sell_data, "sell")]:
        for row in detail_data:
            if str(row.get("OPERATEDEPT_CODE", "")) == "0":
                amt = (row.get("BUY") or 0) if side == "buy" else (row.get("SELL") or 0)
                if side == "buy":
                    institution["buy_amt"] += amt
                else:
                    institution["sell_amt"] += amt
    institution["buy_amt"] = round(institution["buy_amt"] / 10000, 1)
    institution["sell_amt"] = round(institution["sell_amt"] / 10000, 1)
    institution["net_amt"] = round(institution["buy_amt"] - institution["sell_amt"], 1)

    return {"records": records, "seats": seats, "institution": institution}


# ── 3.6 全市场龙虎榜 ─────────────────────────────────────────────────────────

def daily_dragon_tiger(
    trade_date: str | None = None, min_net_buy: float | None = None
) -> dict:
    """
    全市场龙虎榜 — 当日所有上榜股票 + 净买额排名 + 上榜原因。

    参数:
        trade_date:  'YYYY-MM-DD', None=今天
        min_net_buy: 净买入下限 (万元), None=不过滤

    返回: {date, total_records, stocks: [{code, name, reason, close, change_pct,
           net_buy_wan, buy_wan, sell_wan, turnover_pct}]}
    """
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    data = eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
        page_size=500,
        sort_columns="BILLBOARD_NET_AMT", sort_types="-1",
    )
    if not data:
        return {
            "date": trade_date, "total_records": 0, "stocks": [],
            "note": "无数据 (非交易日或盘后未更新)",
        }

    actual_date = str(data[0].get("TRADE_DATE", ""))[:10] if data else trade_date
    stocks = []
    for row in data:
        net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
        if min_net_buy is not None and net_buy < min_net_buy:
            continue
        stocks.append({
            "code":          row.get("SECURITY_CODE", ""),
            "name":          row.get("SECURITY_NAME_ABBR", ""),
            "reason":        row.get("EXPLANATION", ""),
            "close":         row.get("CLOSE_PRICE") or 0,
            "change_pct":    round(float(row.get("CHANGE_RATE") or 0), 2),
            "net_buy_wan":   round(net_buy, 1),
            "buy_wan":       round((row.get("BILLBOARD_BUY_AMT") or 0) / 10000, 1),
            "sell_wan":      round((row.get("BILLBOARD_SELL_AMT") or 0) / 10000, 1),
            "turnover_pct":  round(float(row.get("TURNOVERRATE") or 0), 2),
        })
    return {"date": actual_date, "total_records": len(stocks), "stocks": stocks}


# ── 3.7 限售解禁日历 ─────────────────────────────────────────────────────────

def lockup_expiry(code: str, trade_date: str, forward_days: int = 90) -> dict:
    """
    限售解禁日历。

    返回: {history: [{date, type, shares, ratio}], upcoming: [{...}]}
    """
    code = normalize_ticker(code)

    # 历史解禁
    history_data = eastmoney_datacenter(
        "RPT_LIFT_STAGE",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=15,
        sort_columns="FREE_DATE", sort_types="-1",
    )
    history = []
    for row in history_data:
        history.append({
            "date":    str(row.get("FREE_DATE", ""))[:10],
            "type":    row.get("LIMITED_STOCK_TYPE", ""),
            "shares":  row.get("FREE_SHARES_NUM", 0),
            "ratio":   row.get("FREE_RATIO", 0),
        })

    # 未来待解禁
    end_date = datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=forward_days)
    end_str = end_date.strftime("%Y-%m-%d")
    upcoming_data = eastmoney_datacenter(
        "RPT_LIFT_STAGE",
        filter_str=f'(SECURITY_CODE="{code}")(FREE_DATE>=\'{trade_date}\')(FREE_DATE<=\'{end_str}\')',
        page_size=20,
        sort_columns="FREE_DATE", sort_types="1",
    )
    upcoming = []
    for row in upcoming_data:
        upcoming.append({
            "date":    str(row.get("FREE_DATE", ""))[:10],
            "type":    row.get("LIMITED_STOCK_TYPE", ""),
            "shares":  row.get("FREE_SHARES_NUM", 0),
            "ratio":   row.get("FREE_RATIO", 0),
        })

    return {"history": history, "upcoming": upcoming}


# ── 3.8 融资融券明细 ─────────────────────────────────────────────────────────

def margin_trading(code: str, page_size: int = 30) -> list[dict]:
    """
    融资融券明细 (日级)。

    返回: [{date, rzye(融资余额), rzmre(融资买入), rqye(融券余额), ...}]
    单位: 元
    """
    code = normalize_ticker(code)
    data = eastmoney_datacenter(
        "RPTA_WEB_RZRQ_GGMX",
        filter_str=f'(SCODE="{code}")',
        page_size=page_size,
        sort_columns="DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        rows.append({
            "date":    str(row.get("DATE", ""))[:10],
            "rzye":    row.get("RZYE", 0),
            "rzmre":   row.get("RZMRE", 0),
            "rzche":   row.get("RZCHE", 0),
            "rqye":    row.get("RQYE", 0),
            "rqmcl":   row.get("RQMCL", 0),
            "rqchl":   row.get("RQCHL", 0),
            "rzrqye":  row.get("RZRQYE", 0),
        })
    return rows


# ── 3.9 大宗交易 ─────────────────────────────────────────────────────────────

def block_trade(code: str, page_size: int = 20) -> list[dict]:
    """
    大宗交易记录。

    返回: [{date, price, close, premium_pct, vol, amount, buyer, seller}]
    """
    code = normalize_ticker(code)
    data = eastmoney_datacenter(
        "RPT_DATA_BLOCKTRADE",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="TRADE_DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        close = row.get("CLOSE_PRICE") or 0
        deal_price = row.get("DEAL_PRICE") or 0
        premium = ((deal_price / close - 1) * 100) if close else 0
        rows.append({
            "date":         str(row.get("TRADE_DATE", ""))[:10],
            "price":        deal_price,
            "close":        close,
            "premium_pct":  round(premium, 2),
            "vol":          row.get("DEAL_VOLUME", 0),
            "amount":       row.get("DEAL_AMT", 0),
            "buyer":        row.get("BUYER_NAME", ""),
            "seller":       row.get("SELLER_NAME", ""),
        })
    return rows


# ── 3.10 股东户数变化 ────────────────────────────────────────────────────────

def holder_num_change(code: str, page_size: int = 10) -> list[dict]:
    """
    股东户数变化 (季度级, 筹码集中度)。

    返回: [{date, holder_num, change_num, change_ratio, avg_shares}]

    股东户数持续减少 = 筹码集中 = 主力吸筹信号。
    """
    code = normalize_ticker(code)
    data = eastmoney_datacenter(
        "RPT_HOLDERNUMLATEST",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="END_DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        rows.append({
            "date":          str(row.get("END_DATE", ""))[:10],
            "holder_num":    row.get("HOLDER_NUM", 0),
            "change_num":    row.get("HOLDER_NUM_CHANGE", 0),
            "change_ratio":  row.get("HOLDER_NUM_RATIO", 0),
            "avg_shares":    row.get("AVG_FREE_SHARES", 0),
        })
    return rows


# ── 3.11 分红送转历史 ────────────────────────────────────────────────────────

def dividend_history(code: str, page_size: int = 20) -> list[dict]:
    """
    分红送转历史。

    返回: [{date, bonus_rmb(每股派息), transfer_ratio(转增), bonus_ratio(送股), plan(进度)}]
    """
    code = normalize_ticker(code)
    data = eastmoney_datacenter(
        "RPT_SHAREBONUS_DET",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="EX_DIVIDEND_DATE", sort_types="-1",
    )
    rows = []
    for row in data:
        rows.append({
            "date":            str(row.get("EX_DIVIDEND_DATE", ""))[:10],
            "bonus_rmb":       row.get("PRETAX_BONUS_RMB", 0),
            "transfer_ratio":  row.get("TRANSFER_RATIO", 0),
            "bonus_ratio":     row.get("BONUS_RATIO", 0),
            "plan":            row.get("ASSIGN_PROGRESS", ""),
        })
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# 辅助层: 同花顺 THS — 强势股归因 + 北向资金 (HTTP, 零鉴权, 极低封IP风险)
# ══════════════════════════════════════════════════════════════════════════════

def ths_hot_reason(date: str | None = None) -> pd.DataFrame:
    """
    同花顺当日强势股归因 — 不只告诉你"哪些走强", 还告诉你"为什么走强"。

    参数:
        date: 'YYYY-MM-DD', None=今天

    返回: DataFrame [代码, 名称, 收盘价, 涨跌额, 涨幅%, 换手率%, 成交额, 成交量, 大单净量, 市场, 题材归因]

    reason 字段是核心 — 同花顺编辑部人工运营的题材标签。
    例如: "算力租赁+Token工厂+AI政务"
    """
    from datetime import date as _date
    if date is None:
        date = _date.today().strftime("%Y-%m-%d")

    url = (
        f"http://zx.10jqka.com.cn/event/api/getharden/"
        f"date/{date}/orderby/date/orderway/desc/charset/GBK/"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "Chrome/117.0.0.0 Safari/537.36"
        ),
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
    except Exception as e:
        logger.error(f"同花顺热点请求失败: {e}")
        return pd.DataFrame()

    if data.get("errocode", 0) != 0:
        logger.warning(f"同花顺热点错误: {data.get('errormsg', '')}")
        return pd.DataFrame()

    rows = data.get("data") or []
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    rename_map = {
        "name": "名称", "code": "代码", "reason": "题材归因",
        "close": "收盘价", "zhangdie": "涨跌额", "zhangfu": "涨幅%",
        "huanshou": "换手率%", "chengjiaoe": "成交额",
        "chengjiaoliang": "成交量", "ddejingliang": "大单净量",
        "market": "市场",
    }
    df = df.rename(columns=rename_map)
    return df


def hsgt_realtime() -> pd.DataFrame:
    """
    沪深股通当日实时分钟流向 (含集合竞价 09:10–15:00)。

    返回: DataFrame [time, hgt_yi(沪股通累计净买入, 亿), sgt_yi(深股通累计净买入, 亿)]
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "Chrome/117.0.0.0 Safari/537.36"
        ),
        "Host": "data.hexin.cn",
        "Referer": "https://data.hexin.cn/",
    }
    try:
        r = requests.get(
            "https://data.hexin.cn/market/hsgtApi/method/dayChart/",
            headers=headers, timeout=10,
        )
        d = r.json()
    except Exception as e:
        logger.error(f"北向资金请求失败: {e}")
        return pd.DataFrame()

    times = d.get("time", [])
    hgt = d.get("hgt", [])
    sgt = d.get("sgt", [])

    n = len(times)
    return pd.DataFrame({
        "time":    times,
        "hgt_yi":  hgt[:n] + [None] * (n - len(hgt)),
        "sgt_yi":  sgt[:n] + [None] * (n - len(sgt)),
    })


# ══════════════════════════════════════════════════════════════════════════════
# 统一数据源入口 — DataSource
# ══════════════════════════════════════════════════════════════════════════════

class DataSource:
    """
    A股全栈数据源 — 三层架构 + 自动降级 + 内置限流。

    优先级: mootdx (K线/盘口) > 腾讯财经 (PE/PB/市值) > 东财 (独有数据)

    用法:
        ds = DataSource()
        # K线
        df = ds.get_kline("600519", period="day", count=250)
        # 行情
        quotes = ds.get_quote(["600519", "000858"])
        # 概念板块
        blocks = ds.get_concept_blocks("600519")
        # 资金流向
        flow = ds.get_fund_flow("000858")
        # 龙虎榜
        dt = ds.get_dragon_tiger("002475", "2026-05-17")
        # 行业排名
        ind = ds.get_industry_comparison(10)
        # 同花顺热点
        hot = ds.get_hot_stocks()
        # 北向资金
        north = ds.get_northbound()
    """

    def __init__(self, config: dict | None = None):
        """
        初始化数据源。

        参数:
            config: 配置字典, 可选字段:
                - mootdx.hosts: [(ip, port), ...]
                - eastmoney.min_interval: 东财请求间隔(秒)
                - history_days: 历史K线天数
        """
        self._config = config or {}
        self._mootdx: Optional[MootdxClient] = None

        # 东财限流配置
        em_cfg = self._config.get("eastmoney", {})
        if em_cfg.get("min_interval"):
            set_em_interval(float(em_cfg["min_interval"]))

        # 历史K线天数
        self.history_days = self._config.get("history_days", 250)

    # ── 数据源可用性 ──────────────────────────────────────────────────────

    @property
    def mootdx_available(self) -> bool:
        """mootdx 是否可用"""
        return self.mootdx is not None and self.mootdx.available

    @property
    def mootdx(self) -> Optional[MootdxClient]:
        """懒加载 mootdx 客户端"""
        if self._mootdx is None:
            hosts = self._config.get("mootdx", {}).get("hosts")
            if hosts:
                hosts = [tuple(h.split(":")) if isinstance(h, str) else h for h in hosts]
                hosts = [(h[0], int(h[1])) for h in hosts]
            try:
                self._mootdx = MootdxClient(hosts=hosts)
                if not self._mootdx.available:
                    self._mootdx = None
            except Exception:
                self._mootdx = None
        return self._mootdx

    # ── K线 (mootdx) ──────────────────────────────────────────────────────

    def get_kline(
        self, symbol: str, period: str = "day", count: int | None = None
    ) -> pd.DataFrame:
        if count is None:
            count = self.history_days
        # 优先 mootdx
        if self.mootdx_available:
            try:
                df = self.mootdx.get_kline(symbol, period, count)
                if df is not None and hasattr(df, 'empty') and not df.empty:
                    return df
            except Exception as e:
                logger.debug(f'mootdx [{symbol}] error, trying Sina: {e}')
        # 降级: 新浪K线 (仅支持日线)
        if period in ("day", None):
            df = self._sina_kline(symbol, count)
            if df is not None and len(df) > 0:
                return df
        logger.warning(f"K线 [{symbol}] mootdx+新浪均失败")
        return pd.DataFrame()

    def get_daily(self, symbol: str, count: int | None = None) -> pd.DataFrame:
        """日线K线"""
        return self.get_kline(symbol, "day", count)

    def get_weekly(self, symbol: str, count: int = 100) -> pd.DataFrame:
        """周线K线"""
        return self.get_kline(symbol, "week", count)

    def get_monthly(self, symbol: str, count: int = 60) -> pd.DataFrame:
        """月线K线"""
        return self.get_kline(symbol, "month", count)

    def get_60min(self, symbol: str, count: int = 200) -> pd.DataFrame:
        """60分钟K线"""
        return self.get_kline(symbol, "60min", count)

    # ── 实时行情 (腾讯优先, mootdx 补充盘口) ──────────────────────────────

    def get_quote(self, symbols: list[str]) -> dict[str, dict]:
        """
        批量获取实时行情 (腾讯财经 + mootdx 补充盘口)。

        返回: {code: {name, price, pe_ttm, pb, mcap_yi, ...}}
        """
        # 腾讯财经拿估值 + 价格
        quotes = tencent_quote(symbols)
        # mootdx 补充五档盘口 (如果当前未包含)
        return quotes

    # ── 概念板块 (东财) ───────────────────────────────────────────────────

    def get_concept_blocks(self, code: str) -> dict:
        """个股所属板块/概念归属"""
        return eastmoney_concept_blocks(code)

    # ── 资金流向 (东财) ───────────────────────────────────────────────────

    def get_fund_flow(self, code: str, period: str = "minute") -> list[dict]:
        """
        个股资金流向。

        参数:
            code:   股票代码
            period: "minute"(分钟级, 当日) / "120d"(日级, 120日)
        """
        if period == "120d":
            return stock_fund_flow_120d(code)
        return eastmoney_fund_flow_minute(code)

    # ── 龙虎榜 ────────────────────────────────────────────────────────────

    def get_dragon_tiger(
        self, code: str, trade_date: str, look_back: int = 30
    ) -> dict:
        """个股龙虎榜"""
        return dragon_tiger_board(code, trade_date, look_back)

    def get_daily_dragon_tiger(
        self, trade_date: str | None = None, min_net_buy: float | None = None
    ) -> dict:
        """全市场龙虎榜"""
        return daily_dragon_tiger(trade_date, min_net_buy)

    # ── 限售解禁 ──────────────────────────────────────────────────────────

    def get_lockup_expiry(
        self, code: str, trade_date: str, forward_days: int = 90
    ) -> dict:
        """限售解禁日历"""
        return lockup_expiry(code, trade_date, forward_days)

    # ── 行业排名 ──────────────────────────────────────────────────────────

    def get_industry_comparison(self, top_n: int = 10) -> dict:
        """行业板块涨跌幅排名"""
        return industry_comparison(top_n)

    # ── 融资融券 ──────────────────────────────────────────────────────────

    def get_margin_trading(self, code: str, page_size: int = 30) -> list[dict]:
        """融资融券明细"""
        return margin_trading(code, page_size)

    # ── 大宗交易 ──────────────────────────────────────────────────────────

    def get_block_trade(self, code: str, page_size: int = 20) -> list[dict]:
        """大宗交易"""
        return block_trade(code, page_size)

    # ── 股东户数 ──────────────────────────────────────────────────────────

    def get_holder_change(self, code: str, page_size: int = 10) -> list[dict]:
        """股东户数变化 (筹码集中度)"""
        return holder_num_change(code, page_size)

    # ── 分红送转 ──────────────────────────────────────────────────────────

    def get_dividend_history(self, code: str, page_size: int = 20) -> list[dict]:
        """分红送转历史"""
        return dividend_history(code, page_size)

    # ── 同花顺热点 ────────────────────────────────────────────────────────

    def get_hot_stocks(self, date: str | None = None) -> pd.DataFrame:
        """当日强势股 + 题材归因"""
        return ths_hot_reason(date)

    # ── 选股器兼容适配器 ──────────────────────────────────────────────
    def get_realtime_quotes(self):
        import pandas as pd
        codes = [
            '600519','000858','300750','601318','000333','600036','601398',
            '601288','601939','600900','002594','601857','600276','603259',
            '002475','600809','000651','002415','300059','600030','688017',
            '300308','300476','002463','603501','688981','300274','002230',
            '603160','002049','300782','688536','300604','002371','600941',
            '601728','688256','300394','603986','002916','600150','002241',
            '300502','688608','603893','300433','002384','300735','600584',
            '603236','000977','300474','600536','002439','300496','688111',
            '600570','300124','002920','002938','300033','603444','600031',
            '601899','002142','600048','000002','601668','600585','000725',
            '002304','000568','600887','601012','002027','300450',
        ]
        quotes = self.get_quote(codes)
        rows = []
        for code, q in quotes.items():
            rows.append({
                'code':code,'name':q.get('name',''),'price':q.get('price',0),
                'change_pct':q.get('change_pct',0),'pe_ttm':q.get('pe_ttm',0),
                'mcap_yi':q.get('mcap_yi',0),'turnover':q.get('turnover_pct',0),
                'vol_ratio':q.get('vol_ratio',0),'amount_wan':q.get('amount_wan',0),
                'pb':q.get('pb',0),
            })
        return pd.DataFrame(rows)

    def get_history_kline(self, code, days=120):
        return self.get_kline(code, 'day', days)

    def get_auction_data(self, codes):
        return {}

    # ── 北向资金 ──────────────────────────────────────────────────────────

    def get_northbound(self) -> pd.DataFrame:
        """北向资金分钟级流向"""
        return hsgt_realtime()

    # ── 综合批量查询 ──────────────────────────────────────────────────────

    def get_batch_quotes(self, symbols: list[str]) -> pd.DataFrame:
        """
        批量查询多只股票的估值指标。

        返回: DataFrame [code, name, price, change_pct, pe_ttm, pb, mcap_yi, turnover_pct]
        """
        quotes = self.get_quote(symbols)
        rows = []
        for code in symbols:
            code = normalize_ticker(code)
            q = quotes.get(code, {})
            if q:
                rows.append({
                    "code":          code,
                    "name":          q.get("name", ""),
                    "price":         q.get("price", 0),
                    "change_pct":    q.get("change_pct", 0),
                    "pe_ttm":        q.get("pe_ttm", 0),
                    "pb":            q.get("pb", 0),
                    "mcap_yi":       q.get("mcap_yi", 0),
                    "turnover_pct":  q.get("turnover_pct", 0),
                })
        return pd.DataFrame(rows)

    # ── 信息 ──────────────────────────────────────────────────────────────

    @property
    def status(self) -> dict:
        """数据源状态"""
        return {
            "mootdx":        self.mootdx_available,
            "tencent":       True,   # 腾讯财经 HTTP, 总是可用
            "eastmoney":     True,   # 东财 HTTP (已内置限流)
            "ths":           True,   # 同花顺 HTTP
            "em_interval":   EM_MIN_INTERVAL,
            "history_days":  self.history_days,
        }

    def __repr__(self) -> str:
        s = self.status
        return (
            f"DataSource(mootdx={s['mootdx']}, tencent={s['tencent']}, "
            f"eastmoney={s['eastmoney']}(限流{s['em_interval']}s), "
            f"history_days={s['history_days']})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 便捷函数 (模块级, 无需实例化 DataSource)
# ══════════════════════════════════════════════════════════════════════════════

# 缓存单例
_ds_cache: Optional[DataSource] = None



def get_ds(config: dict | None = None) -> DataSource:
    """获取 DataSource 单例"""
    global _ds_cache
    if _ds_cache is None:
        _ds_cache = DataSource(config)
    return _ds_cache


# ══════════════════════════════════════════════════════════════════════════════
# 自测
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 60)
    print("A股数据层自测")
    print("=" * 60)

    # 1. 工具函数
    print("\n── 工具函数 ──")
    print(f"normalize('SH600519'): {normalize_ticker('SH600519')}")
    print(f"normalize('000001.SZ'): {normalize_ticker('000001.SZ')}")
    print(f"prefix('600519'): {get_market_prefix('600519')}")
    print(f"prefix('000001'): {get_market_prefix('000001')}")
    print(f"prefix('832000'): {get_market_prefix('832000')}")

    # 2. 腾讯行情 (不封IP, 速度快)
    print("\n── 腾讯行情 ──")
    quotes = tencent_quote(["600519", "000858"])
    for code, q in quotes.items():
        print(f"  {q['name']}({code}): {q['price']}元 PE={q['pe_ttm']} PB={q['pb']} 市值={q['mcap_yi']}亿")

    # 3. 东财概念板块
    print("\n── 东财概念板块 ──")
    blocks = eastmoney_concept_blocks("600519")
    print(f"  贵州茅台: {blocks['total']} 个板块")
    print(f"  前5: {blocks['concept_tags'][:5]}")

    # 4. 行业排名
    print("\n── 行业板块排名 ──")
    ind = industry_comparison(5)
    print(f"  共 {ind['total']} 个行业")
    print("  TOP5:")
    for r in ind["top"][:5]:
        print(f"    {r['rank']}. {r['name']}: {r['change_pct']}% 领涨={r['leader']}")
    print("  BOT5:")
    for r in ind["bottom"][:5]:
        print(f"    {r['rank']}. {r['name']}: {r['change_pct']}%")

    # 5. DataSource
    print("\n── DataSource 统一入口 ──")
    ds = DataSource()
    print(f"  {ds}")
    print(f"  mootdx: {ds.mootdx_available}")

    # 6. 尝试 mootdx K线
    if ds.mootdx_available:
        print("\n── mootdx K线 ──")
        df = ds.get_daily("600519", count=5)
        if not df.empty:
            print(df.tail(3).to_string())

    print("\n✅ 自测完成")
