# -*- coding: utf-8 -*-
"""
===================================
候选股票筛选服务
===================================

职责：
1. 按市场拉取全量行情快照（efinance 优先 → akshare fallback）
2. 价格区间过滤 + 排除 ST 股
3. 按成交额降序取 Top N，返回候选列表
"""

import logging
import random
import time
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# 每个市场默认取 Top N
_DEFAULT_TOP_N_PER_MARKET = 30
# 所有市场合计上限
_MAX_TOTAL_CANDIDATES = 80

# A 股最低成交额（元）
_A_SHARE_MIN_AMOUNT = 50_000_000
# 港股/美股最低成交额（对应币种）
_HK_US_MIN_AMOUNT = 1_000_000

# ---------- 全市场快照缓存（与 data_provider 同模式） ----------
_snapshot_cache: Dict[str, Dict] = {}
_SNAPSHOT_TTL = 60  # 缓存 60 秒

# ---------- 反封禁：随机 UA ----------
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


def _set_random_user_agent():
    """为 requests 设置随机 User-Agent（与 data_provider 同策略）"""
    import requests.utils
    ua = random.choice(_USER_AGENTS)
    requests.utils.default_headers = lambda: {"User-Agent": ua}


def _get_cached_snapshot(market_key: str) -> Optional[pd.DataFrame]:
    """读取快照缓存"""
    entry = _snapshot_cache.get(market_key)
    if entry and time.time() - entry["ts"] < _SNAPSHOT_TTL:
        logger.info("[选股筛选] %s 快照缓存命中 (age=%.0fs)", market_key, time.time() - entry["ts"])
        return entry["df"]
    return None


def _set_cached_snapshot(market_key: str, df: pd.DataFrame):
    """写入快照缓存"""
    _snapshot_cache[market_key] = {"df": df, "ts": time.time()}


# ================================================================
#  A 股快照获取：efinance 优先 → akshare EM fallback（含重试）
# ================================================================

def _fetch_a_share_snapshot() -> Optional[pd.DataFrame]:
    """efinance 优先 + akshare fallback 获取 A 股全市场快照"""
    cached = _get_cached_snapshot("a_share")
    if cached is not None:
        return cached

    df = _fetch_a_share_via_efinance()
    if df is not None and not df.empty:
        _set_cached_snapshot("a_share", df)
        return df

    df = _fetch_a_share_via_akshare()
    if df is not None and not df.empty:
        _set_cached_snapshot("a_share", df)
        return df

    return None


def _fetch_a_share_via_efinance() -> Optional[pd.DataFrame]:
    """通过 efinance 获取 A 股实时行情"""
    try:
        import efinance as ef
    except ImportError:
        logger.debug("[选股筛选] efinance 未安装，跳过")
        return None

    for attempt in range(1, 3):
        try:
            _set_random_user_agent()
            logger.info("[选股筛选] efinance 获取 A 股行情... (attempt %d/2)", attempt)
            t0 = time.time()
            df = ef.stock.get_realtime_quotes()
            elapsed = time.time() - t0
            if df is not None and not df.empty:
                logger.info("[选股筛选] efinance A 股行情获取成功，共 %d 只，耗时 %.2fs", len(df), elapsed)
                # 统一列名到 akshare 风格
                return _normalize_efinance_columns(df)
            logger.warning("[选股筛选] efinance 返回空数据 (attempt %d/2)", attempt)
        except Exception as e:
            logger.warning("[选股筛选] efinance A 股行情失败 (attempt %d/2): %s", attempt, e)
            time.sleep(min(2 ** attempt, 5))

    return None


def _normalize_efinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    """将 efinance 列名映射为与 akshare stock_zh_a_spot_em 一致的中文列名"""
    col_map = {
        "股票代码": "代码",
        "股票名称": "名称",
        "最新价": "最新价",
        "涨跌幅": "涨跌幅",
        "成交量": "成交量",
        "成交额": "成交额",
        "总市值": "总市值",
        "市盈率": "市盈率-动态",
    }
    rename = {}
    for src, dst in col_map.items():
        if src in df.columns and src != dst:
            rename[src] = dst
    if rename:
        df = df.rename(columns=rename)
    return df


def _fetch_a_share_via_akshare() -> Optional[pd.DataFrame]:
    """通过 akshare（东方财富）获取 A 股实时行情，含重试"""
    try:
        import akshare as ak
    except ImportError:
        logger.error("akshare 未安装，无法筛选 A 股")
        return None

    last_error = None
    for attempt in range(1, 3):
        try:
            _set_random_user_agent()
            logger.info("[选股筛选] akshare 获取 A 股行情... (attempt %d/2)", attempt)
            t0 = time.time()
            df = ak.stock_zh_a_spot_em()
            elapsed = time.time() - t0
            logger.info("[选股筛选] akshare A 股行情获取成功，共 %d 只，耗时 %.2fs", len(df), elapsed)
            return df
        except Exception as e:
            last_error = e
            logger.warning("[选股筛选] akshare A 股行情失败 (attempt %d/2): %s", attempt, e)
            time.sleep(min(2 ** attempt, 5))

    logger.error("[选股筛选] akshare A 股行情最终失败: %s", last_error)
    return None


# ================================================================
#  港股快照获取（akshare + 重试）
# ================================================================

def _fetch_hk_snapshot() -> Optional[pd.DataFrame]:
    """获取港股全市场快照，含缓存与重试"""
    cached = _get_cached_snapshot("hk")
    if cached is not None:
        return cached

    try:
        import akshare as ak
    except ImportError:
        logger.error("akshare 未安装，无法筛选港股")
        return None

    last_error = None
    for attempt in range(1, 3):
        try:
            _set_random_user_agent()
            logger.info("[选股筛选] 获取港股实时行情... (attempt %d/2)", attempt)
            t0 = time.time()
            df = ak.stock_hk_spot_em()
            elapsed = time.time() - t0
            logger.info("[选股筛选] 港股行情获取成功，共 %d 只，耗时 %.2fs", len(df), elapsed)
            _set_cached_snapshot("hk", df)
            return df
        except Exception as e:
            last_error = e
            logger.warning("[选股筛选] 港股行情失败 (attempt %d/2): %s", attempt, e)
            time.sleep(min(2 ** attempt, 5))

    logger.error("[选股筛选] 港股行情最终失败: %s", last_error)
    return None


# ================================================================
#  美股快照获取（akshare + yfinance fallback）
# ================================================================

def _fetch_us_snapshot() -> Optional[pd.DataFrame]:
    """获取美股全市场快照，含缓存、重试与 yfinance fallback"""
    cached = _get_cached_snapshot("us")
    if cached is not None:
        return cached

    try:
        import akshare as ak
    except ImportError:
        ak = None

    if ak is not None:
        last_error = None
        for attempt in range(1, 3):
            try:
                _set_random_user_agent()
                logger.info("[选股筛选] 获取美股实时行情... (attempt %d/2)", attempt)
                t0 = time.time()
                df = ak.stock_us_spot_em()
                elapsed = time.time() - t0
                logger.info("[选股筛选] 美股行情获取成功，共 %d 只，耗时 %.2fs", len(df), elapsed)
                _set_cached_snapshot("us", df)
                return df
            except Exception as e:
                last_error = e
                logger.warning("[选股筛选] akshare 美股行情失败 (attempt %d/2): %s", attempt, e)
                time.sleep(min(2 ** attempt, 5))
        logger.warning("[选股筛选] akshare 美股最终失败: %s，yfinance 暂不支持批量快照", last_error)

    return None


# ================================================================
#  公共入口
# ================================================================

def screen(
    markets: List[str],
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    top_n: int = _MAX_TOTAL_CANDIDATES,
) -> List[Dict]:
    """
    按市场和价格区间筛选候选股票。

    Args:
        markets: 市场列表，如 ["a_share", "hk", "us"]
        price_min: 最低价格（可选）
        price_max: 最高价格（可选）
        top_n: 返回的候选总数上限

    Returns:
        候选股票字典列表
    """
    per_market_n = min(_DEFAULT_TOP_N_PER_MARKET, max(top_n // max(len(markets), 1), 10))
    all_candidates: List[Dict] = []

    for market in markets:
        market = market.strip().lower()
        try:
            if market in ("a_share", "a", "cn"):
                candidates = _screen_a_share(price_min, price_max, per_market_n)
            elif market in ("hk", "hongkong"):
                candidates = _screen_hk(price_min, price_max, per_market_n)
            elif market in ("us", "usa"):
                candidates = _screen_us(price_min, price_max, per_market_n)
            else:
                logger.warning("不支持的市场: %s", market)
                continue
            all_candidates.extend(candidates)
        except Exception as e:
            logger.error("筛选 %s 市场失败: %s", market, e)
            continue

    # 按成交额降序排序，取 Top N
    all_candidates.sort(key=lambda x: x.get("amount", 0) or 0, reverse=True)
    return all_candidates[:top_n]


def _screen_a_share(
    price_min: Optional[float],
    price_max: Optional[float],
    top_n: int,
) -> List[Dict]:
    """筛选 A 股候选"""
    df = _fetch_a_share_snapshot()
    if df is None or df.empty:
        return []

    return _filter_and_rank(
        df,
        market="a_share",
        price_col="最新价",
        name_col="名称",
        code_col="代码",
        change_pct_col="涨跌幅",
        amount_col="成交额",
        pe_col="市盈率-动态",
        cap_col="总市值",
        price_min=price_min,
        price_max=price_max,
        min_amount=_A_SHARE_MIN_AMOUNT,
        top_n=top_n,
        exclude_st=True,
    )


def _screen_hk(
    price_min: Optional[float],
    price_max: Optional[float],
    top_n: int,
) -> List[Dict]:
    """筛选港股候选"""
    df = _fetch_hk_snapshot()
    if df is None or df.empty:
        return []

    return _filter_and_rank(
        df,
        market="hk",
        price_col="最新价",
        name_col="名称",
        code_col="代码",
        change_pct_col="涨跌幅",
        amount_col="成交额",
        pe_col=None,
        cap_col="总市值",
        price_min=price_min,
        price_max=price_max,
        min_amount=_HK_US_MIN_AMOUNT,
        top_n=top_n,
        exclude_st=False,
    )


def _screen_us(
    price_min: Optional[float],
    price_max: Optional[float],
    top_n: int,
) -> List[Dict]:
    """筛选美股候选"""
    df = _fetch_us_snapshot()
    if df is None or df.empty:
        return []

    return _filter_and_rank(
        df,
        market="us",
        price_col="最新价",
        name_col="名称",
        code_col="代码",
        change_pct_col="涨跌幅",
        amount_col="成交额",
        pe_col=None,
        cap_col="总市值",
        price_min=price_min,
        price_max=price_max,
        min_amount=_HK_US_MIN_AMOUNT,
        top_n=top_n,
        exclude_st=False,
    )


def _filter_and_rank(
    df: pd.DataFrame,
    *,
    market: str,
    price_col: str,
    name_col: str,
    code_col: str,
    change_pct_col: str,
    amount_col: str,
    pe_col: Optional[str],
    cap_col: Optional[str],
    price_min: Optional[float],
    price_max: Optional[float],
    min_amount: float,
    top_n: int,
    exclude_st: bool,
) -> List[Dict]:
    """通用筛选排序逻辑"""
    if df is None or df.empty:
        return []

    df = df.copy()

    # 数值列转换
    for col in [price_col, amount_col, change_pct_col]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if pe_col and pe_col in df.columns:
        df[pe_col] = pd.to_numeric(df[pe_col], errors="coerce")
    if cap_col and cap_col in df.columns:
        df[cap_col] = pd.to_numeric(df[cap_col], errors="coerce")

    # 排除无效数据
    df = df.dropna(subset=[price_col])
    df = df[df[price_col] > 0]

    # 排除 ST 股
    if exclude_st and name_col in df.columns:
        df = df[~df[name_col].str.contains(r"ST|退市", case=False, na=False)]

    # 价格区间过滤
    if price_min is not None:
        df = df[df[price_col] >= price_min]
    if price_max is not None:
        df = df[df[price_col] <= price_max]

    # 成交额过滤
    if amount_col in df.columns:
        df = df[df[amount_col] >= min_amount]

    # 按成交额降序排序
    if amount_col in df.columns:
        df = df.sort_values(amount_col, ascending=False)

    # 取 Top N
    df = df.head(top_n)

    # 构造结果
    results = []
    for _, row in df.iterrows():
        item = {
            "code": str(row.get(code_col, "")),
            "name": str(row.get(name_col, "")),
            "market": market,
            "price": _safe_float(row.get(price_col)),
            "change_pct": _safe_float(row.get(change_pct_col)),
            "amount": _safe_float(row.get(amount_col)),
            "pe": _safe_float(row.get(pe_col)) if pe_col and pe_col in df.columns else None,
            "market_cap": _safe_float(row.get(cap_col)) if cap_col and cap_col in df.columns else None,
        }
        results.append(item)

    return results


def _safe_float(value) -> Optional[float]:
    """安全转换为浮点数"""
    if value is None:
        return None
    try:
        import math
        v = float(value)
        return None if math.isnan(v) else v
    except (ValueError, TypeError):
        return None
