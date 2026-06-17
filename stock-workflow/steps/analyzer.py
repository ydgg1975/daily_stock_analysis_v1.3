#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 2: 分析模块 — 4大战法并行检测
─────────────────────────────────────────
  1. 首板+横盘+起爆  (check_first_board)
  2. 涨停回踩         (check_pullback)
  3. 波动点           (check_wave_point)
  4. 试盘线           (check_test_line)

每个战法返回: {signal, score, reason, entry_price, stop_loss}
分析器并行执行4大战法，选择得分最高的策略作为最终结果。
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

import pandas as pd
import numpy as np
import yaml

# ── 导入数据源 (项目内部 data_source.py) ──────────────────
_PROJ_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..")
)
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

try:
    from data_source import DataSource, normalize_ticker
except ImportError:
    # fallback: 尝试外部 quant_trading
    _QT_DIR = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "quant_trading")
    )
    if _QT_DIR not in sys.path:
        sys.path.insert(0, _QT_DIR)
    try:
        from data_source import DataSource
    except ImportError:
        # 最后的占位
        class DataSource:
            """占位数据源"""
            @staticmethod
            def get_kline(symbol: str, count: int = 250,
                          end_date=None):
                return None
            @staticmethod
            def get_daily_kline(symbols, start, end, dividend='front'):
                return {}

# ── 日志 ────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── 默认配置 ────────────────────────────────────────
DEFAULT_CONFIG = {
    "strategies": {
        "first_board": {
            "enabled": True,
            "lookback_days": 60,
            "consolidation_days": 5,
            "breakout_vol_ratio": 2.0,
            "limit_up_pct": 9.5,          # 涨停阈值(%)
            "consolidation_range_pct": 5.0, # 横盘振幅范围(%)
            "consolidation_vol_shrink": 0.5, # 横盘期缩量比例
        },
        "pullback": {
            "enabled": True,
            "pullback_ratio": 0.382,
            "vol_shrink_ratio": 0.5,
            "tolerance_pct": 2.0,          # 回踩容差(%)
            "rally_min_pct": 10.0,         # 最低涨幅要求(%)
            "bounce_confirm_pct": 1.0,     # 反弹确认涨幅(%)
        },
        "wave_point": {
            "enabled": True,
            "atr_period": 14,
            "wave_pct": 3.0,
            "wave_lookback": 30,            # 波段回溯天数
            "trough_confirm_ratio": 0.3,    # 波谷确认: 从低点反弹比例
        },
        "test_line": {
            "enabled": True,
            "line_tolerance": 0.02,
            "wick_ratio": 0.60,             # 影线占比阈值
            "shadow_tolerance_pct": 2.0,    # 影线容差
            "volume_confirm": 1.2,          # 量确认倍率
        },
    },
    "risk": {
        "stop_loss": {
            "price_atr_mult": 2.0,
            "max_loss_pct": 5.0,
        },
        "take_profit": {
            "rr_ratio": 2.0,
        },
    },
}


# ══════════════════════════════════════════════════════
# 结果数据结构
# ══════════════════════════════════════════════════════

@dataclass
class StrategyResult:
    """单战法分析结果"""
    signal: bool = False
    score: float = 0.0         # 0-100
    reason: str = ""
    entry_price: float = 0.0
    stop_loss: float = 0.0
    strategy_name: str = ""


@dataclass
class AnalysisResult:
    """综合分析结果"""
    symbol: str = ""
    timestamp: str = ""
    signal: bool = False
    best_strategy: str = ""
    best_score: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    reason: str = ""
    # 所有战法详细结果
    details: Dict[str, StrategyResult] = field(default_factory=dict)


# ══════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════

def _calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """计算 ATR (Average True Range)"""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()


def _calc_fibonacci(high: float, low: float) -> Dict[str, float]:
    """计算斐波那契回撤位"""
    diff = high - low
    return {
        "0.000": low,
        "0.236": high - diff * 0.236,
        "0.382": high - diff * 0.382,
        "0.500": high - diff * 0.500,
        "0.618": high - diff * 0.618,
        "0.786": high - diff * 0.786,
        "1.000": high,
    }


def _is_limit_up(close: float, prev_close: float,
                  limit_pct: float = 9.5) -> bool:
    """判断涨停 (考虑四舍五入)"""
    if prev_close <= 0:
        return False
    change_pct = (close - prev_close) / prev_close * 100
    # A股涨停通常 9.9%~10.0%，科创板/创业板 19.9%~20.0%
    return change_pct >= limit_pct


def _find_limit_up_days(df: pd.DataFrame, limit_pct: float = 9.5) -> pd.DataFrame:
    """找出所有涨停日"""
    prev_close = df["close"].shift(1)
    change_pct = (df["close"] - prev_close) / prev_close * 100
    mask = change_pct >= limit_pct
    return df[mask].copy()


def _wick_ratio(row) -> Tuple[float, float, str]:
    """
    计算影线比例
    返回: (upper_wick_ratio, lower_wick_ratio, wick_type)
    wick_type: 'upper' | 'lower' | 'both' | 'none'
    """
    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    total_range = h - l
    if total_range <= 0:
        return 0.0, 0.0, "none"

    body_high = max(o, c)
    body_low = min(o, c)
    body = body_high - body_low

    upper_wick = h - body_high
    lower_wick = body_low - l

    upper_ratio = upper_wick / total_range
    lower_ratio = lower_wick / total_range

    if upper_ratio >= 0.6 and lower_ratio >= 0.6:
        wick_type = "both"
    elif upper_ratio >= 0.6:
        wick_type = "upper"
    elif lower_ratio >= 0.6:
        wick_type = "lower"
    else:
        wick_type = "none"

    return upper_ratio, lower_ratio, wick_type


def _calc_ma(df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
    """计算多个周期的均线"""
    for p in periods:
        df[f"ma{p}"] = df["close"].rolling(window=p, min_periods=1).mean()
    return df


def _detect_swing_points(df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """
    检测波段高低点
    使用局部极值法: window根K线内的最高/最低点
    """
    df = df.copy()
    df["swing_high"] = False
    df["swing_low"] = False

    high = df["high"].values
    low = df["low"].values

    for i in range(window, len(df) - window):
        # 波段高点: 当前high大于左右各window根K线的high
        if high[i] == max(high[i - window : i + window + 1]):
            df.iloc[i, df.columns.get_loc("swing_high")] = True
        # 波段低点: 当前low小于左右各window根K线的low
        if low[i] == min(low[i - window : i + window + 1]):
            df.iloc[i, df.columns.get_loc("swing_low")] = True

    return df


# ══════════════════════════════════════════════════════
# 4 大战法检测函数
# ══════════════════════════════════════════════════════

def check_first_board(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> StrategyResult:
    """
    战法1: 首板+横盘+起爆

    逻辑:
      1. 回溯60天找到首板（第一个涨停板）
      2. 涨停后至少5天横盘整理（振幅<5%，缩量）
      3. 最近一根K线放量突破（量>20日均量×2）
      4. 根据横盘质量评分

    返回: StrategyResult
    """
    cfg = (config or DEFAULT_CONFIG)["strategies"]["first_board"]
    if not cfg.get("enabled", True):
        return StrategyResult(strategy_name="first_board", reason="战法未启用")

    lookback = cfg["lookback_days"]
    cons_days = cfg["consolidation_days"]
    vol_ratio = cfg["breakout_vol_ratio"]
    limit_pct = cfg["limit_up_pct"]
    cons_range = cfg.get("consolidation_range_pct", 5.0)
    cons_vol_shrink = cfg.get("consolidation_vol_shrink", 0.5)

    # 数据不足
    if df is None or len(df) < lookback:
        return StrategyResult(
            strategy_name="first_board",
            reason=f"数据不足 (需要≥{lookback}天，实际{len(df) if df is not None else 0}天)",
        )

    df = df.tail(lookback).copy().reset_index(drop=True)

    # 计算参考均线
    df["ma20_vol"] = df["vol"].rolling(20, min_periods=5).mean()

    # ── 找到首板 ──
    prev_close = df["close"].shift(1)
    change_pct = (df["close"] - prev_close) / prev_close * 100
    limit_up_mask = change_pct >= limit_pct

    if not limit_up_mask.any():
        return StrategyResult(
            strategy_name="first_board",
            reason=f"回溯{lookback}天内未发现涨停板",
        )

    # 取第一个涨停日
    first_lu_idx = limit_up_mask[limit_up_mask].index[0]
    lu_row = df.iloc[first_lu_idx]
    lu_close = lu_row["close"]
    lu_vol = lu_row["vol"]

    # ── 检查涨停后有无足够交易日 ──
    remaining = len(df) - first_lu_idx - 1
    if remaining < cons_days:
        return StrategyResult(
            strategy_name="first_board",
            reason=f"涨停后仅{remaining}天，不足{cons_days}天横盘要求",
            score=10,
        )

    # ── 横盘区域分析 ──
    consolidation = df.iloc[first_lu_idx + 1 :]  # 涨停后所有K线

    # 从前往后找突破起点：第一根量>均量×vol_ratio 且 收盘突破此前横盘高点的K线
    avg_vol_series = df["ma20_vol"]
    breakout_start = len(df)  # 默认无突破（到末尾）
    cons_high_running = consolidation["high"].iloc[0]

    for i in range(len(consolidation)):
        idx = consolidation.index[i]
        row = consolidation.iloc[i]
        if avg_vol_series.iloc[idx] > 0:
            vr = row["vol"] / avg_vol_series.iloc[idx]
            if vr >= vol_ratio and row["close"] > cons_high_running * 1.02:
                breakout_start = idx
                break
        cons_high_running = max(cons_high_running, row["high"])

    # 横盘区 = 涨停后到突破前
    cons_zone = df.iloc[first_lu_idx + 1 : breakout_start]
    if len(cons_zone) < cons_days:
        return StrategyResult(
            strategy_name="first_board",
            reason=f"涨停后横盘{len(cons_zone)}天不足{cons_days}天（突破过早）",
            score=10,
        )

    cons_high = cons_zone["high"].max()
    cons_low = cons_zone["low"].min()
    cons_range_pct = (cons_high - cons_low) / lu_close * 100
    cons_avg_vol = cons_zone["vol"].mean()

    # 横盘质量检查
    if cons_range_pct > cons_range:
        return StrategyResult(
            strategy_name="first_board",
            reason=f"横盘振幅{cons_range_pct:.1f}%超过{cons_range}%阈值，非有效横盘",
            score=15,
        )

    # ── 起爆确认 ──
    last_row = df.iloc[-1]
    break_vol = last_row["vol"]
    avg_vol = df["ma20_vol"].iloc[-1]

    if avg_vol <= 0:
        return StrategyResult(
            strategy_name="first_board",
            reason="无法计算均量",
            score=5,
        )

    break_vol_ratio = break_vol / avg_vol

    if break_vol_ratio < vol_ratio:
        return StrategyResult(
            strategy_name="first_board",
            reason=f"突破量比{break_vol_ratio:.1f}<{vol_ratio}，未满足起爆条件",
            score=20,
        )

    # 还需要突破横盘区间上沿
    if last_row["close"] <= cons_high:
        return StrategyResult(
            strategy_name="first_board",
            reason=f"收盘{last_row['close']:.2f}未突破横盘上沿{cons_high:.2f}",
            score=20,
        )

    # ── 综合评分 ──
    score = 50  # 基础分

    # 横盘天数加分 (每多1天+2分，上限+20)
    extra_days = len(cons_zone) - cons_days
    score += min(extra_days * 2, 20)

    # 横盘紧凑度加分 (振幅越小越好)
    if cons_range_pct < 2.0:
        score += 20
    elif cons_range_pct < 3.0:
        score += 12
    elif cons_range_pct < 4.0:
        score += 6

    # 缩量程度加分
    if lu_vol > 0:
        shrink_ratio = cons_avg_vol / lu_vol
        if shrink_ratio < 0.3:
            score += 12
        elif shrink_ratio < 0.5:
            score += 6

    # 放量突破加分
    if break_vol_ratio >= 3.0:
        score += 8
    elif break_vol_ratio >= 2.5:
        score += 4

    score = min(score, 100)

    # ── 入场价与止损价 ──
    entry_price = last_row["close"]
    # 止损设在横盘区间支撑下方
    stop_loss = cons_low * (1 - cfg.get("stop_loss_discount", 0.02))

    # ATR止损作为备选
    atr = _calc_atr(df).iloc[-1]
    atr_stop = entry_price - atr * DEFAULT_CONFIG["risk"]["stop_loss"]["price_atr_mult"]
    stop_loss = max(stop_loss, atr_stop)  # 取较近的止损位

    return StrategyResult(
        signal=True,
        score=score,
        reason=f"首板横盘起爆: 横盘{len(cons_zone)}天/振幅{cons_range_pct:.1f}%/量比{break_vol_ratio:.1f}",
        entry_price=entry_price,
        stop_loss=round(stop_loss, 2),
        strategy_name="first_board",
    )


def check_pullback(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> StrategyResult:
    """
    战法2: 涨停回踩

    逻辑:
      1. 找到前期涨停拉升段（涨幅≥10%）
      2. 计算0.382斐波那契回撤位
      3. 当前价格回踩到0.382位附近（容差±2%）
      4. 缩量至涨停量50%以下
      5. 出现反弹确认信号

    返回: StrategyResult
    """
    cfg = (config or DEFAULT_CONFIG)["strategies"]["pullback"]
    if not cfg.get("enabled", True):
        return StrategyResult(strategy_name="pullback", reason="战法未启用")

    pullback_ratio = cfg["pullback_ratio"]
    vol_shrink = cfg["vol_shrink_ratio"]
    tolerance = cfg.get("tolerance_pct", 2.0) / 100
    rally_min = cfg.get("rally_min_pct", 10.0) / 100
    bounce_confirm = cfg.get("bounce_confirm_pct", 1.0) / 100

    if df is None or len(df) < 30:
        return StrategyResult(
            strategy_name="pullback",
            reason=f"数据不足 (需要≥30天，实际{len(df) if df is not None else 0}天)",
        )

    df = df.tail(90).copy().reset_index(drop=True)

    # ── 寻找前期涨停拉升段 ──
    limit_up_days = _find_limit_up_days(df)
    if limit_up_days.empty:
        return StrategyResult(
            strategy_name="pullback",
            reason="近90天无涨停板，无法执行回踩检测",
        )

    # 取最近一次涨停作为参考点
    last_lu_idx = limit_up_days.index[-1]
    lu_row = df.iloc[last_lu_idx]
    lu_close = lu_row["close"]
    lu_vol = lu_row["vol"]

    # 找到涨停前的起涨点 (涨停前最低价)
    pre_lu = df.iloc[: last_lu_idx + 1]
    rally_low = pre_lu["low"].min()
    rally_high = pre_lu["high"].max()  # 包含涨停日的最高价

    # 计算实际涨幅
    rally_pct = (rally_high - rally_low) / rally_low
    if rally_pct < rally_min:
        return StrategyResult(
            strategy_name="pullback",
            reason=f"拉升幅度{rally_pct*100:.1f}%不足{rally_min*100:.0f}%",
            score=10,
        )

    # ── 斐波那契回撤位 ──
    fib = _calc_fibonacci(rally_high, rally_low)
    target_price = fib[f"{pullback_ratio:.3f}"]

    # ── 回踩确认 ──
    current_close = df["close"].iloc[-1]
    current_low = df["low"].iloc[-1]
    deviation = abs(current_close - target_price) / target_price

    if deviation > tolerance:
        return StrategyResult(
            strategy_name="pullback",
            reason=f"价格{current_close:.2f}偏离{pullback_ratio}回撤位{target_price:.2f} ({deviation*100:.1f}%>{tolerance*100:.1f}%)",
            score=15,
        )

    # ── 缩量确认 ──
    # 最近5日均量 vs 涨停量
    recent_vol = df["vol"].iloc[-5:].mean()
    if lu_vol > 0 and recent_vol / lu_vol > vol_shrink:
        return StrategyResult(
            strategy_name="pullback",
            reason=f"近期均量/涨停量={recent_vol/lu_vol*100:.0f}%>{vol_shrink*100:.0f}%，未充分缩量",
            score=20,
        )

    # ── 反弹确认 ──
    # 最近一根K线需要收阳或出现下影线反弹
    last_row = df.iloc[-1]
    is_bullish = last_row["close"] > last_row["open"]
    has_lower_wick = (min(last_row["open"], last_row["close"]) - last_row["low"]) > 0

    prev_row = df.iloc[-2]
    bounce_from_low = (last_row["close"] - last_row["low"]) / last_row["low"] if last_row["low"] > 0 else 0

    if not is_bullish and bounce_from_low < bounce_confirm:
        return StrategyResult(
            strategy_name="pullback",
            reason="未出现反弹确认信号（未收阳且下影线反弹不足）",
            score=25,
        )

    # ── 综合评分 ──
    score = 50  # 基础分

    # 回踩精度加分
    if deviation < 0.01:  # 1%内
        score += 25
    elif deviation < 0.015:
        score += 15
    elif deviation < 0.02:
        score += 8

    # 缩量程度加分
    if lu_vol > 0:
        shrink = recent_vol / lu_vol
        if shrink < 0.3:
            score += 15
        elif shrink < 0.4:
            score += 8

    # K线形态加分
    if is_bullish:
        body_pct = abs(last_row["close"] - last_row["open"]) / last_row["open"]
        if body_pct > 0.02:  # 实体>2%
            score += 8

    score = min(score, 100)

    # ── 入场价与止损价 ──
    entry_price = current_close
    # 止损设在下一个斐波那契位下方
    next_fib_key = "0.500" if pullback_ratio < 0.5 else "0.618"
    stop_loss = fib[next_fib_key] * 0.98  # 下方2%保护

    return StrategyResult(
        signal=True,
        score=score,
        reason=f"涨停回踩{pullback_ratio}: 价格{current_close:.2f}→回撤位{target_price:.2f} (偏离{deviation*100:.1f}%)/缩量{recent_vol/lu_vol*100 if lu_vol>0 else 0:.0f}%",
        entry_price=entry_price,
        stop_loss=round(stop_loss, 2),
        strategy_name="pullback",
    )


def check_wave_point(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> StrategyResult:
    """
    战法3: 波动点 (ATR波谷入场)

    逻辑:
      1. 计算ATR(14)作为波动基准
      2. 检测波段高低点
      3. 波段振幅≥3%
      4. 当前处于波谷区域 + 确认信号（反弹启动）
      5. 入场价=波谷附近，止损=波谷下方ATR×2

    返回: StrategyResult
    """
    cfg = (config or DEFAULT_CONFIG)["strategies"]["wave_point"]
    if not cfg.get("enabled", True):
        return StrategyResult(strategy_name="wave_point", reason="战法未启用")

    atr_period = cfg["atr_period"]
    wave_pct = cfg["wave_pct"] / 100
    lookback = cfg.get("wave_lookback", 30)
    trough_confirm = cfg.get("trough_confirm_ratio", 0.3)

    if df is None or len(df) < atr_period + 10:
        return StrategyResult(
            strategy_name="wave_point",
            reason=f"数据不足 (需要≥{atr_period+10}天，实际{len(df) if df is not None else 0}天)",
        )

    df = df.tail(lookback + 10).copy().reset_index(drop=True)

    # ── 计算 ATR ──
    df["atr"] = _calc_atr(df, atr_period)
    current_atr = df["atr"].iloc[-1]

    if current_atr <= 0:
        return StrategyResult(strategy_name="wave_point", reason="ATR数据异常")

    # ── 检测波段高低点 ──
    df = _detect_swing_points(df, window=3)

    swing_lows = df[df["swing_low"]].copy()
    swing_highs = df[df["swing_high"]].copy()

    if len(swing_lows) < 1 or len(swing_highs) < 1:
        return StrategyResult(
            strategy_name="wave_point",
            reason=f"未检测到足够波段高低点 (低点{len(swing_lows)}/高点{len(swing_highs)})",
            score=10,
        )

    # ── 取最近一次完整波段 ──
    # 找到最近一个波谷和之前的波峰
    last_low = swing_lows.iloc[-1]
    last_low_idx = last_low.name
    last_low_price = last_low["low"]

    # 在最近波谷之前的波峰
    prev_highs = swing_highs[swing_highs.index < last_low_idx]
    if prev_highs.empty:
        return StrategyResult(
            strategy_name="wave_point",
            reason="无法找到波谷前的高点，波段不完整",
            score=10,
        )
    last_high = prev_highs.iloc[-1]
    last_high_price = last_high["high"]

    # ── 波段幅度检查 ──
    wave_amplitude = (last_high_price - last_low_price) / last_low_price
    if wave_amplitude < wave_pct:
        return StrategyResult(
            strategy_name="wave_point",
            reason=f"波段振幅{wave_amplitude*100:.1f}%不足{wave_pct*100:.1f}%",
            score=15,
        )

    # ── 当前位置判断 ──
    current_close = df["close"].iloc[-1]
    current_low = df["low"].iloc[-1]
    bars_since_low = len(df) - 1 - last_low_idx
    current_position_pct = (current_close - last_low_price) / last_low_price

    # 需要处于波谷附近 (距波谷≤3根K线 且 价格在波谷价格的 +5% 以内)
    in_trough_zone = bars_since_low <= 3 and current_position_pct < 0.05

    if not in_trough_zone:
        return StrategyResult(
            strategy_name="wave_point",
            reason=f"距波谷{bars_since_low}天/偏离{current_position_pct*100:.1f}%，不在波谷区域",
            score=20,
        )

    # ── 确认信号: 从低点反弹 ──
    bounce_from_trough = (current_close - last_low_price) / last_low_price
    if bounce_from_trough > trough_confirm:
        # 已确认反弹，信号有效
        confirm_ok = True
    else:
        # 检查是否出现反转K线（下影线长+收阳）
        last_row = df.iloc[-1]
        _, lower_wick, wick_type = _wick_ratio(last_row)
        is_bullish = last_row["close"] > last_row["open"]
        confirm_ok = lower_wick >= 0.5 or is_bullish

    if not confirm_ok:
        return StrategyResult(
            strategy_name="wave_point",
            reason="波谷区域但缺少确认信号（无反弹/无反转K线）",
            score=25,
        )

    # ── 综合评分 ──
    score = 50

    # 波段幅度越大越好 (3%~8%之间)
    if 0.05 <= wave_amplitude <= 0.08:
        score += 20
    elif 0.03 <= wave_amplitude < 0.05:
        score += 10

    # 波谷位置越精确越好
    if current_position_pct < 0.02:
        score += 15
    elif current_position_pct < 0.03:
        score += 8

    # 反弹确认质量
    if bounce_from_trough >= trough_confirm:
        score += 10

    # ATR适度 (波动率适中)
    atr_pct = current_atr / current_close
    if 0.01 <= atr_pct <= 0.04:
        score += 8

    score = min(score, 100)

    # ── 入场价与止损价 ──
    entry_price = current_close
    stop_loss = last_low_price - current_atr * DEFAULT_CONFIG["risk"]["stop_loss"]["price_atr_mult"]
    stop_loss = max(stop_loss, current_close * 0.95)  # 硬止损5%

    return StrategyResult(
        signal=True,
        score=score,
        reason=f"波动点: 振幅{wave_amplitude*100:.1f}%/ATR{current_atr:.2f}/波谷偏离{current_position_pct*100:.1f}%",
        entry_price=entry_price,
        stop_loss=round(stop_loss, 2),
        strategy_name="wave_point",
    )


def check_test_line(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> StrategyResult:
    """
    战法4: 试盘线 (影线探测支撑/压力)

    逻辑:
      1. 检测长上影线或长下影线 (影线占比>60%)
      2. 影线长度容差2%
      3. 上影线→测试压力位；下影线→测试支撑位
      4. 成交量配合确认
      5. 下影线试盘为做多信号，上影线为警示

    返回: StrategyResult
    """
    cfg = (config or DEFAULT_CONFIG)["strategies"]["test_line"]
    if not cfg.get("enabled", True):
        return StrategyResult(strategy_name="test_line", reason="战法未启用")

    wick_threshold = cfg.get("wick_ratio", 0.60)
    tolerance = cfg.get("line_tolerance", 0.02)
    volume_confirm = cfg.get("volume_confirm", 1.2)

    if df is None or len(df) < 10:
        return StrategyResult(
            strategy_name="test_line",
            reason=f"数据不足 (需要≥10天，实际{len(df) if df is not None else 0}天)",
        )

    df = df.tail(20).copy().reset_index(drop=True)

    # ── 分析最近3根K线的影线 ──
    last_row = df.iloc[-1]
    upper_ratio, lower_ratio, wick_type = _wick_ratio(last_row)

    # 如果最新K线不符合，检查前一根
    if wick_type == "none":
        prev_row = df.iloc[-2]
        upper_ratio, lower_ratio, wick_type = _wick_ratio(prev_row)
        check_row = prev_row
        bar_offset = 1
    else:
        check_row = last_row
        bar_offset = 0

    if wick_type == "none" or wick_type == "both":
        return StrategyResult(
            strategy_name="test_line",
            reason=f"近2日无有效试盘线 (上影{max(upper_ratio, lower_ratio)*100:.0f}%<{wick_threshold*100:.0f}%)",
            score=10,
        )

    # ── 确定试盘方向 ──
    o, h, l, c = check_row["open"], check_row["high"], check_row["low"], check_row["close"]
    body_high = max(o, c)
    body_low = min(o, c)
    body = body_high - body_low

    if wick_type == "lower":
        # 下影线试盘 → 测试支撑 → 做多信号
        shadow_len = body_low - l
        direction = "支撑试盘"
    else:
        # 上影线试盘 → 测试压力 → 先观望，若次日突破上影高点则做多
        shadow_len = h - body_high
        direction = "压力试盘"

    # ── 影线容差检查 ──
    # 影线长度相对K线总范围的占比
    total_range = h - l
    if total_range <= 0:
        return StrategyResult(strategy_name="test_line", reason="K线范围异常")

    shadow_pct = shadow_len / total_range
    if shadow_pct < wick_threshold - tolerance:
        return StrategyResult(
            strategy_name="test_line",
            reason=f"影线占比{shadow_pct*100:.1f}%未达{wick_threshold*100:.0f}%阈值",
            score=10,
        )

    # ── 成交量确认 ──
    avg_vol = df["vol"].iloc[:-1].mean()
    test_vol = check_row["vol"]
    vol_ratio_val = test_vol / avg_vol if avg_vol > 0 else 1.0

    if vol_ratio_val < volume_confirm and wick_type == "lower":
        return StrategyResult(
            strategy_name="test_line",
            reason=f"下影线试盘量比{vol_ratio_val:.1f}<{volume_confirm}，确认不足",
            score=25,
        )

    # ── 支撑/阻力位识别 ──
    if wick_type == "lower":
        # 下影线低点即为支撑位
        key_level = l
        # 检查是否与前期低点吻合
        prev_low = df["low"].iloc[:-1].min()
        level_confirm = abs(key_level - prev_low) / prev_low < tolerance
    else:
        # 上影线高点即为压力位
        key_level = h
        # 检查是否与前期高点吻合
        prev_high = df["high"].iloc[:-1].max()
        level_confirm = abs(key_level - prev_high) / prev_high < tolerance

    # ── 综合评分 ──
    score = 50

    # 影线质量
    if shadow_pct >= 0.75:
        score += 20
    elif shadow_pct >= 0.65:
        score += 10

    # 下影线(支撑试盘)优于上影线
    if wick_type == "lower":
        score += 15
    else:
        # 上影线 + 次日突破确认 才给分
        if bar_offset == 1:
            # 上影线次日，检查是否突破上影高点
            if last_row["close"] > check_row["high"]:
                score += 15
            else:
                score -= 10
        else:
            # 当日上影线，等待确认
            score -= 5

    # 量能配合
    if vol_ratio_val >= 2.0:
        score += 10
    elif vol_ratio_val >= 1.5:
        score += 5

    # 关键位确认
    if level_confirm:
        score += 10

    score = min(score, 100)

    # ── 信号判断 ──
    # 下影线试盘直接做多；上影线需次日突破才做多
    if wick_type == "lower":
        signal = True
        entry_price = check_row["close"]
        stop_loss = l * 0.98  # 影线低点下方2%
    else:
        if bar_offset == 1 and last_row["close"] > check_row["high"]:
            signal = True
            entry_price = last_row["close"]
            stop_loss = check_row["low"] * 0.98
        else:
            signal = False
            entry_price = 0.0
            stop_loss = 0.0

    if signal and score < 40:
        signal = False

    return StrategyResult(
        signal=signal,
        score=score,
        reason=f"试盘线({direction}): 影线{shadow_pct*100:.0f}%/量比{vol_ratio_val:.1f}/关键位{'吻合' if level_confirm else '未确认'}",
        entry_price=entry_price if signal else 0.0,
        stop_loss=round(stop_loss, 2) if signal else 0.0,
        strategy_name="test_line",
    )


# ══════════════════════════════════════════════════════
# 分析器主类
# ══════════════════════════════════════════════════════

class Analyzer:
    """
    战法分析器 — 4大战法并行检测

    使用方式:
        analyzer = Analyzer()
        result = analyzer.analyze("000001.SZ", ds=data_source_instance)
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化分析器

        Args:
            config_path: 配置文件路径，默认使用 ../config.yaml
        """
        self.config = self._load_config(config_path)
        self.strategies = [
            check_first_board,
            check_pullback,
            check_wave_point,
            check_test_line,
        ]

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """深度合并字典，override 中的值覆盖 base"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Analyzer._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """加载配置，与默认配置深度合并"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "config.yaml"
            )
            config_path = os.path.normpath(config_path)

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                # 深度合并：用户配置覆盖默认配置
                merged = self._deep_merge(DEFAULT_CONFIG, cfg)
                logger.info(f"配置已加载: {config_path}")
                return merged
            except Exception as e:
                logger.warning(f"配置加载失败 {config_path}: {e}，使用默认配置")

        logger.info("使用默认配置")
        return DEFAULT_CONFIG

    def analyze(
        self,
        symbol: str,
        ds: Optional[Any] = None,
        df: Optional[pd.DataFrame] = None,
    ) -> AnalysisResult:
        """
        对单只股票执行4大战法并行分析

        Args:
            symbol: 股票代码 (如 "000001.SZ")
            ds: DataSource 实例 (用于获取K线数据)
            df: 直接传入的K线DataFrame (优先使用)

        Returns:
            AnalysisResult 综合分析结果
        """
        # ── 获取数据 ──
        if df is None:
            if ds is not None:
                df = self._fetch_kline(symbol, ds)
            else:
                return AnalysisResult(
                    symbol=symbol,
                    timestamp=datetime.now().isoformat(),
                    reason="无数据源且未提供K线DataFrame",
                )

        if df is None or len(df) < 10:
            return AnalysisResult(
                symbol=symbol,
                timestamp=datetime.now().isoformat(),
                reason=f"K线数据不足 ({len(df) if df is not None else 0}条)",
            )

        # ── 确保列名标准化 ──
        df = self._normalize_columns(df)

        # ── 并行执行4大战法 ──
        results: Dict[str, StrategyResult] = {}
        max_workers = min(4, os.cpu_count() or 4)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(strategy, df, self.config): strategy.__name__
                for strategy in self.strategies
            }
            for future in as_completed(future_map):
                name = future_map[future]
                try:
                    result = future.result(timeout=30)
                    results[name] = result
                except Exception as e:
                    logger.error(f"战法 {name} 执行异常: {e}")
                    results[name] = StrategyResult(
                        strategy_name=name,
                        reason=f"执行异常: {str(e)}",
                    )

        # ── 选择最佳策略 ──
        best: Optional[StrategyResult] = None
        for r in results.values():
            if r.signal and (best is None or r.score > best.score):
                best = r

        if best is None:
            # 所有战法均无信号，返回得分最高的分析结果
            best = max(results.values(), key=lambda r: r.score)

        # ── 计算止盈价 ──
        rr_ratio = self.config.get("risk", {}).get("take_profit", {}).get("rr_ratio", 2.0)
        if best.signal and best.entry_price > 0 and best.stop_loss > 0:
            risk = best.entry_price - best.stop_loss
            take_profit = best.entry_price + risk * rr_ratio
        else:
            take_profit = 0.0

        return AnalysisResult(
            symbol=symbol,
            timestamp=datetime.now().isoformat(),
            signal=best.signal,
            best_strategy=best.strategy_name,
            best_score=best.score,
            entry_price=best.entry_price,
            stop_loss=best.stop_loss,
            take_profit=round(take_profit, 2),
            reason=best.reason,
            details=results,
        )

    def _fetch_kline(self, symbol: str, ds: Any) -> Optional[pd.DataFrame]:
        """从数据源获取K线"""
        try:
            # 尝试 get_kline (便捷方法)
            if hasattr(ds, "get_kline"):
                return ds.get_kline(symbol, count=250)

            # 尝试 get_daily_kline (标准方法)
            if hasattr(ds, "get_daily_kline"):
                end = datetime.now().strftime("%Y-%m-%d")
                start = (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%d")
                result = ds.get_daily_kline([symbol], start, end)
                if isinstance(result, dict) and symbol in result:
                    return result[symbol]
                return None

            logger.warning("数据源不支持已知接口")
            return None

        except Exception as e:
            logger.error(f"获取K线失败: {symbol}: {e}")
            return None

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名"""
        df = df.copy()
        col_map = {
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "vol",
            "Amount": "amount",
            # 中文列名
            "日期": "date", "开盘": "open", "最高": "high",
            "最低": "low", "收盘": "close", "成交量": "vol",
            "成交额": "amount",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        required = ["open", "high", "low", "close", "vol"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"K线数据缺少必要列: {missing}")

        return df

    def analyze_batch(
        self,
        symbols: List[str],
        ds: Optional[Any] = None,
        df_map: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> Dict[str, AnalysisResult]:
        """
        批量分析多只股票

        Args:
            symbols: 股票代码列表
            ds: DataSource 实例
            df_map: {symbol: DataFrame} 字典

        Returns:
            {symbol: AnalysisResult} 字典
        """
        results = {}
        for symbol in symbols:
            df = df_map.get(symbol) if df_map else None
            results[symbol] = self.analyze(symbol, ds=ds, df=df)
        return results

    def get_signal_summary(self, results: Dict[str, AnalysisResult]) -> pd.DataFrame:
        """将分析结果汇总为 DataFrame"""
        records = []
        for symbol, r in results.items():
            records.append({
                "symbol": symbol,
                "signal": r.signal,
                "best_strategy": r.best_strategy,
                "score": r.best_score,
                "entry_price": r.entry_price,
                "stop_loss": r.stop_loss,
                "take_profit": r.take_profit,
                "reason": r.reason,
            })
        return pd.DataFrame(records)


# ══════════════════════════════════════════════════════
# 测试入口
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # ── 生成模拟数据测试 ──
    print("=" * 60)
    print("  A股战法分析模块 - 测试")
    print("=" * 60)

    # 模拟60天K线：包含涨停→横盘→起爆
    np.random.seed(42)
    n = 60
    dates = pd.date_range(end=datetime.now(), periods=n, freq="B")
    # 基础价格走势：前47天在10元附近震荡
    np.random.seed(42)
    base = np.ones(n) * 10.0
    base[:47] = 10.0 + np.random.randn(47) * 0.15

    # day 47: 首板涨停 (~10.0 → ~10.97)
    base[47] = base[46] * 1.097
    lu_close = base[47]

    # day 48-56: 横盘（含涨停日共9根横盘K线，涨停后8根）
    # 但涨停日不算横盘，所以涨停后的 day48~day56 共9根横盘
    for i in range(48, 57):
        base[i] = lu_close + np.random.randn() * 0.03  # 极小振幅

    # day 57-59: 起爆
    base[57] = lu_close * 1.04  # 首日突破
    base[58] = lu_close * 1.07  # 继续上攻
    base[59] = lu_close * 1.10  # 再上攻

    close = base.copy()
    open_price = close.copy()
    # 随机开盘价偏移
    for i in range(n):
        open_price[i] = close[i] * (1 + np.random.randn() * 0.01)

    high = np.maximum(open_price, close) + np.abs(np.random.randn(n) * 0.03)
    low = np.minimum(open_price, close) - np.abs(np.random.randn(n) * 0.03)
    # 横盘期进一步压缩影线
    for i in range(48, 57):
        high[i] = max(open_price[i], close[i]) + abs(np.random.randn() * 0.02)
        low[i] = min(open_price[i], close[i]) - abs(np.random.randn() * 0.02)

    # 成交量
    vol = np.ones(n) * 80000
    vol[47] = 600000                  # 涨停日巨量
    vol[48:57] = 25000                # 横盘严重缩量
    vol[57] = 350000                  # 起爆日放量
    vol[58] = 420000                  # 持续放量
    vol[59] = 380000                  # 维持放量

    # day 54 加入试盘线
    test_idx = 54
    low[test_idx] = close[test_idx] - 0.35
    vol[test_idx] = 260000

    test_df = pd.DataFrame({
        "date": dates,
        "open": np.round(open_price, 2),
        "high": np.round(high, 2),
        "low": np.round(low, 2),
        "close": np.round(close, 2),
        "vol": vol.astype(int),
        "amount": vol * close,
    })

    print(f"模拟数据: {len(test_df)} 根K线")
    print(f"日期范围: {test_df['date'].iloc[0].date()} ~ {test_df['date'].iloc[-1].date()}")

    # ── 运行分析 ──
    analyzer = Analyzer()
    result = analyzer.analyze("000001.SZ", df=test_df)

    print(f"\n📊 分析结果: {result.symbol}")
    print(f"  信号: {'✅ 买入' if result.signal else '❌ 无信号'}")
    print(f"  最佳战法: {result.best_strategy}")
    print(f"  评分: {result.best_score:.0f}/100")
    print(f"  入场价: {result.entry_price:.2f}")
    print(f"  止损价: {result.stop_loss:.2f}")
    print(f"  止盈价: {result.take_profit:.2f}")
    print(f"  理由: {result.reason}")

    print(f"\n📋 各战法详情:")
    for name, r in result.details.items():
        status = "🟢" if r.signal else "⚪"
        print(f"  {status} {name}: 评分{r.score:.0f} | {r.reason[:60]}")

    print(f"\n{'=' * 60}")
    print("  测试完成")
    print(f"{'=' * 60}")
