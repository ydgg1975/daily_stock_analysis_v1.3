#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 3: 计划模块 (Planner) — 仓位计算 + 止损止盈
────────────────────────────────────────────────────
功能:
  1. 仓位计算: 根据信号强度分配资金权重 (强30%/中20%/弱10%)
  2. 止损计算: 支撑止损 / ATR止损 / 硬止损 (三者取最紧)
  3. 止盈计算: 风险收益比 RR = (entry - stop) × rr_ratio
  4. 移动止盈: +5%→成本, +10%→锁+5%, +20%→锁+10%
  5. 仓位上限: 最多5只, 单笔风险≤1%

兼容旧接口:
  - create_plan(df) → List[Position]           (兼容 sa-2 子代理的接口)
  - plan(list_of_dicts) → List[PositionPlan]   (完整版接口, 含止损止盈计算)

配置来源: config.yaml → position, risk 段
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from data_source import DataSource

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════

@dataclass
class Position:
    """单笔持仓计划 (兼容旧接口)"""
    stock: str = ""
    name: str = ""
    strategy: str = ""
    signal_strength: str = ""    # 强 / 中 / 弱
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    position_pct: float = 0.0   # 仓位占比 (0-1)
    shares: int = 0             # 股数 (100股整数倍)
    capital: float = 0.0        # 占用资金
    risk_amount: float = 0.0    # 风险金额
    score: float = 0.0


@dataclass
class PositionPlan:
    """完整交易计划 (新版输出格式)"""
    stock_code: str = ""
    stock_name: str = ""
    entry_price: float = 0.0
    position_size: int = 0           # 股数 (100的整数倍)
    position_pct: float = 0.0        # 仓位占比 (0-1)
    stop_loss: float = 0.0           # 止损价
    take_profit: float = 0.0         # 止盈价
    risk_amount: float = 0.0         # 风险金额
    strategy_name: str = ""
    signal_score: float = 0.0
    signal_strength: str = ""        # 强 / 中 / 弱

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "entry_price": self.entry_price,
            "position_size": self.position_size,
            "position_pct": round(self.position_pct, 4),
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_amount": round(self.risk_amount, 2),
            "strategy_name": self.strategy_name,
            "signal_score": self.signal_score,
        }


@dataclass
class PlanConfig:
    """仓位管理配置"""
    max_positions: int = 5
    risk_per_trade: float = 0.01    # 单笔风险 1%
    capital: float = 1_000_000      # 总资金(元)
    position_weights: dict = field(default_factory=lambda: {
        "强": 0.30, "strong": 0.30,
        "中": 0.20, "normal": 0.20,
        "弱": 0.10, "weak": 0.10,
    })
    # 止损参数
    support_below_pct: float = 0.03  # 支撑下方 3%
    atr_mult: float = 2.0            # ATR 倍数
    max_loss_pct: float = 0.05       # 硬止损 5%
    # 止盈参数
    rr_ratio: float = 2.0            # 盈亏比
    # 移动止盈规则: [(涨幅阈值%, 锁定价表达式)]
    trailing_rules: list = field(default_factory=lambda: [
        (20.0, "10pct"),
        (10.0, "5pct"),
        (5.0,  "cost"),
    ])

    @classmethod
    def from_dict(cls, cfg: dict) -> "PlanConfig":
        """从 config.yaml 解析配置"""
        pos = cfg.get("position", {})
        risk = cfg.get("risk", {})
        sl = risk.get("stop_loss", {})
        tp = risk.get("take_profit", {})

        user_weights = pos.get("position_weights", {})
        base_weights = {
            "强": 0.30, "strong": 0.30,
            "中": 0.20, "normal": 0.20,
            "弱": 0.10, "weak": 0.10,
        }
        base_weights.update(user_weights)

        return cls(
            max_positions=pos.get("max_positions", 5),
            risk_per_trade=pos.get("risk_per_trade", 0.01),
            capital=pos.get("capital", 1_000_000),
            position_weights=base_weights,
            support_below_pct=sl.get("support_below_pct", 3.0) / 100.0,
            atr_mult=sl.get("price_atr_mult", 2.0),
            max_loss_pct=sl.get("max_loss_pct", 5.0) / 100.0,
            rr_ratio=tp.get("rr_ratio", 2.0),
        )


# ═══════════════════════════════════════════════════════════════
# 主类: Planner
# ═══════════════════════════════════════════════════════════════

class Planner:
    """
    交易计划生成器。

    职责:
      - 仓位计算: 信号强度 → 权重 → 股数(100股整手)
      - 止损计算: 支撑止损 / ATR止损 / 硬止损 取最紧
      - 止盈计算: 风险收益比
      - 移动止盈: 浮盈达到阈值自动上移止损
      - 总量控制: ≤5只, 单笔风险≤1%

    用法:
        from steps.planner import Planner
        p = Planner(config_dict, data_source=ds)

        # 新版接口 (推荐)
        plans = p.plan(list_of_analysis_dicts)

        # 旧版兼容
        plans = p.create_plan(df, screening_results)
    """

    def __init__(self, config: Optional[PlanConfig] = None, data_source: Optional[DataSource] = None):
        self.config = config or PlanConfig()
        self._ds = data_source

    # ── 新版接口: plan() ────────────────────────────────

    def plan(self, analysis_results: List[Dict[str, Any]]) -> List[PositionPlan]:
        """
        根据分析结果生成完整交易计划 (含止损止盈计算)。

        参数:
            analysis_results: 分析/选股结果列表, 每项至少包含:
                stock_code / code, stock_name / name,
                entry_price, signal_strength,
                stop_loss (可选, 分析器给出的止损)

        返回:
            List[PositionPlan]  按仓位占比降序排列
        """
        if not analysis_results:
            logger.info("[计划] 无分析结果, 跳过")
            return []

        cfg = self.config
        logger.info("=" * 50)
        logger.info(f"[计划] 候选{len(analysis_results)}只 | 资金{cfg.capital/1e4:.0f}万 | 最多{cfg.max_positions}只")
        logger.info("=" * 50)

        plans: List[PositionPlan] = []
        remaining_capital = cfg.capital

        # 按信号评分降序
        sorted_items = sorted(
            analysis_results,
            key=lambda x: float(x.get("signal_score", x.get("best_score", x.get("score", 0))) or 0),
            reverse=True,
        )

        for item in sorted_items:
            if len(plans) >= cfg.max_positions:
                break

            plan = self._plan_one(item, remaining_capital)
            if plan is not None:
                plans.append(plan)
                remaining_capital -= plan.position_size * plan.entry_price

        if not plans:
            logger.warning("[计划] 无有效计划")
            return []

        # 日志汇总
        for p in plans:
            logger.info(
                f"  {p.stock_code} {p.stock_name:6s} | "
                f"入{p.entry_price:.2f} | {p.position_size}股({p.position_pct*100:.1f}%) | "
                f"止{p.stop_loss:.2f} | 盈{p.take_profit:.2f} | "
                f"险{p.risk_amount:.0f}元 | {p.strategy_name}/{p.signal_score:.0f}分"
            )

        logger.info(f"[计划] ✅ 完成: {len(plans)}只")
        return plans

    def _plan_one(self, item: Dict[str, Any], remaining_capital: float) -> Optional[PositionPlan]:
        """为单只股票生成计划"""
        cfg = self.config

        stock_code   = item.get("stock_code", item.get("code", ""))
        stock_name   = item.get("stock_name", item.get("name", ""))
        entry_price  = float(item.get("entry_price", 0) or 0)
        strength     = item.get("signal_strength", item.get("strength", "中"))
        strategy     = item.get("strategy_name", item.get("best_strategy", ""))
        score        = float(item.get("signal_score", item.get("best_score", item.get("score", 0))) or 0)

        if not stock_code or entry_price <= 0:
            logger.debug(f"[计划] 跳过无效项: {stock_code} entry={entry_price}")
            return None

        # ── 1. 仓位权重 & 股数 ──
        weight = cfg.position_weights.get(strength, 0.20)
        allocated = cfg.capital * weight
        allocated = min(allocated, remaining_capital)

        shares = int(allocated / entry_price / 100) * 100
        if shares < 100:
            logger.warning(f"[计划] {stock_code} 仓位不足1手 ({shares}股)")
            return None

        actual_capital = shares * entry_price
        position_pct = actual_capital / cfg.capital

        # ── 2. 止损计算 ──
        existing_stop = float(item.get("stop_loss", 0) or 0)
        stop_loss = self._calc_stop_loss(stock_code, entry_price, existing_stop, item)

        # ── 3. 止盈计算 ──
        take_profit = self._calc_take_profit(entry_price, stop_loss)

        # ── 4. 风险检查: 单笔风险 ≤ 总资金 × 1% ──
        risk = entry_price - stop_loss
        risk_amount = shares * risk if risk > 0 else 0
        max_risk = cfg.capital * cfg.risk_per_trade

        if risk_amount > max_risk and risk > 0:
            # 缩减仓位以满足风险要求
            shares = int(max_risk / risk / 100) * 100
            if shares < 100:
                logger.warning(f"[计划] {stock_code} 风险过大, 缩仓后仍不足1手")
                return None
            actual_capital = shares * entry_price
            position_pct = actual_capital / cfg.capital
            risk_amount = shares * risk

        plan = PositionPlan(
            stock_code=stock_code,
            stock_name=stock_name,
            entry_price=entry_price,
            position_size=shares,
            position_pct=position_pct,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_amount=risk_amount,
            strategy_name=strategy,
            signal_score=score,
            signal_strength=strength,
        )
        return plan

    # ── 止损计算 ────────────────────────────────────────

    def _calc_stop_loss(
        self,
        stock_code: str,
        entry_price: float,
        existing_stop: float,
        item: Dict[str, Any],
    ) -> float:
        """
        综合止损: 支撑止损 / ATR止损 / 硬止损 — 取最紧的(最高价)。

        止损规则:
          1. 分析器给出的止损 (已有)
          2. 支撑位下方3%: stop = support × 0.97
          3. ATR止损: stop = entry - 2×ATR
          4. 硬止损: stop = entry × 0.95
        """
        cfg = self.config
        candidates: List[float] = []

        # a. 分析器止损
        if existing_stop > 0 and existing_stop < entry_price:
            candidates.append(existing_stop)

        # b. 支撑位下方3%
        support = self._detect_support(stock_code, item)
        if support > 0 and support < entry_price:
            candidates.append(round(support * (1.0 - cfg.support_below_pct), 2))

        # c. ATR止损
        atr = self._get_atr(stock_code, item)
        if atr > 0:
            candidates.append(round(entry_price - atr * cfg.atr_mult, 2))

        # d. 硬止损 5%
        candidates.append(round(entry_price * (1.0 - cfg.max_loss_pct), 2))

        # 取最紧 (最高价)
        stop = max(candidates)
        # 确保止损 < 入场价
        stop = min(stop, entry_price * 0.999)
        return round(stop, 2)

    def _detect_support(self, stock_code: str, item: Dict[str, Any]) -> float:
        """检测支撑位"""
        for key in ("support_price", "support", "key_level"):
            val = item.get(key)
            if val and float(val) > 0:
                return float(val)

        if self._ds is not None:
            try:
                kline = self._ds.get_kline(stock_code, count=30)
                if kline is not None and not kline.empty:
                    low_col = "low" if "low" in kline.columns else "Low"
                    if low_col in kline.columns:
                        return float(kline[low_col].min())
            except Exception as e:
                logger.debug(f"[计划] 获取{stock_code}支撑位失败: {e}")
        return 0.0

    def _get_atr(self, stock_code: str, item: Dict[str, Any]) -> float:
        """获取 ATR(14)"""
        for key in ("atr", "current_atr"):
            val = item.get(key)
            if val and float(val) > 0:
                return float(val)

        if self._ds is not None:
            try:
                kline = self._ds.get_kline(stock_code, count=20)
                if kline is not None and not kline.empty and len(kline) >= 14:
                    return self._calc_atr_from_df(kline, period=14)
            except Exception as e:
                logger.debug(f"[计划] 获取{stock_code} ATR失败: {e}")
        return 0.0

    @staticmethod
    def _calc_atr_from_df(df: pd.DataFrame, period: int = 14) -> float:
        """从DataFrame计算ATR"""
        col_high = "high" if "high" in df.columns else "High"
        col_low  = "low"  if "low"  in df.columns else "Low"
        col_close = "close" if "close" in df.columns else "Close"

        if col_high not in df.columns or col_low not in df.columns or col_close not in df.columns:
            return 0.0

        high = df[col_high].astype(float)
        low  = df[col_low].astype(float)
        close = df[col_close].astype(float)
        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period, min_periods=1).mean()
        return float(atr.iloc[-1])

    # ── 止盈计算 ────────────────────────────────────────

    def _calc_take_profit(self, entry_price: float, stop_loss: float) -> float:
        """
        止盈 = entry + risk × rr_ratio
        risk = entry - stop
        """
        risk = entry_price - stop_loss
        if risk <= 0:
            return round(entry_price * 1.05, 2)  # 保底 5%
        return round(entry_price + risk * self.config.rr_ratio, 2)

    # ── 移动止盈 ────────────────────────────────────────

    def get_trailing_stop(self, entry_price: float, current_price: float) -> float:
        """
        移动止盈规则:
          +20% → 锁 +10% (止损上移到 entry × 1.10)
          +10% → 锁 +5%  (止损上移到 entry × 1.05)
          +5%  → 成本价  (止损上移到 entry)
        返回: 移动止盈后的止损价 (0=未触发)
        """
        if entry_price <= 0:
            return 0.0
        profit_pct = (current_price - entry_price) / entry_price * 100

        for threshold_pct, lock_type in self.config.trailing_rules:
            if profit_pct >= threshold_pct:
                if lock_type == "cost":
                    return round(entry_price, 2)
                elif lock_type == "5pct":
                    return round(entry_price * 1.05, 2)
                elif lock_type == "10pct":
                    return round(entry_price * 1.10, 2)
        return 0.0

    # ── 旧版兼容接口: create_plan() ─────────────────────

    def create_plan(
        self,
        analysis_results: pd.DataFrame,
        screening_results: Optional[pd.DataFrame] = None,
    ) -> List[Position]:
        """
        旧版兼容接口 (供 sa-2 子代理调用)。

        参数:
            analysis_results: DataFrame [code, name, signal, best_strategy, score,
                              entry_price, stop_loss, take_profit, signal_strength]
            screening_results: 选股结果 (含 signal_strength), 可选

        返回:
            List[Position]
        """
        plans: List[Position] = []
        cfg = self.config
        remaining_capital = cfg.capital

        # 筛选有信号的
        if "signal" in analysis_results.columns:
            signals = analysis_results[analysis_results["signal"] == True]
        else:
            signals = analysis_results

        # 限制最大持仓
        signals = signals.head(cfg.max_positions)

        for _, row in signals.iterrows():
            stock = row.get("code", "")
            strength = row.get("signal_strength", "中")
            weight = cfg.position_weights.get(strength, 0.20)

            allocated = cfg.capital * weight
            allocated = min(allocated, remaining_capital)

            entry_price = float(row.get("entry_price", 0) or 0)
            if entry_price <= 0:
                continue

            shares = int(allocated / entry_price / 100) * 100
            actual_capital = shares * entry_price

            stop_loss = float(row.get("stop_loss", entry_price * 0.95) or entry_price * 0.95)
            risk = entry_price - stop_loss
            risk_amount = shares * risk if risk > 0 else 0

            # 单笔风险 ≤ 1%
            if risk_amount > cfg.capital * cfg.risk_per_trade and risk > 0:
                shares = int(cfg.capital * cfg.risk_per_trade / risk / 100) * 100
                actual_capital = shares * entry_price
                risk_amount = shares * risk

            if shares < 100:
                continue

            position = Position(
                stock=stock,
                name=row.get("name", ""),
                strategy=row.get("best_strategy", ""),
                signal_strength=strength,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=float(row.get("take_profit", entry_price * 1.05) or entry_price * 1.05),
                position_pct=actual_capital / cfg.capital,
                shares=shares,
                capital=actual_capital,
                risk_amount=risk_amount,
                score=float(row.get("score", 0) or 0),
            )
            plans.append(position)
            remaining_capital -= actual_capital

        logger.info(f"[Planner] 生成 {len(plans)} 个持仓计划, 剩余资金 {remaining_capital:,.0f}")
        return plans

    def __repr__(self) -> str:
        return f"Planner(max={self.config.max_positions}, capital={self.config.capital:,.0f})"


# ═══════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════

def create_planner(config_path: Optional[str] = None, ds: Optional[DataSource] = None) -> Planner:
    """从 config.yaml 创建 Planner 实例"""
    import os
    import yaml

    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        config_path = os.path.normpath(config_path)

    cfg = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    plan_cfg = PlanConfig.from_dict(cfg)
    return Planner(config=plan_cfg, data_source=ds)


# ═══════════════════════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 60)
    print("  仓位计划模块 (Planner) 自测")
    print("=" * 60)

    # ── 测试1: plan() 新版接口 ──
    print("\n── 测试1: plan() 新版接口 ──")
    mock_results = [
        {
            "stock_code": "600519", "stock_name": "贵州茅台",
            "entry_price": 1680.00, "stop_loss": 1620.00,
            "signal_strength": "强", "strategy_name": "first_board",
            "signal_score": 88, "signal": True,
        },
        {
            "stock_code": "000858", "stock_name": "五粮液",
            "entry_price": 145.00, "stop_loss": 138.00,
            "signal_strength": "中", "strategy_name": "pullback",
            "signal_score": 72, "signal": True,
        },
        {
            "stock_code": "300750", "stock_name": "宁德时代",
            "entry_price": 210.00, "stop_loss": 200.00,
            "signal_strength": "弱", "strategy_name": "wave_point",
            "signal_score": 55, "signal": True,
        },
        {
            "stock_code": "002475", "stock_name": "立讯精密",
            "entry_price": 38.50, "stop_loss": 36.80,
            "signal_strength": "中", "strategy_name": "test_line",
            "signal_score": 68, "signal": True,
        },
    ]

    planner = Planner()
    plans = planner.plan(mock_results)

    print(f"\n📋 交易计划 ({len(plans)} 只):")
    print("-" * 85)
    print(f"{'代码':<8} {'名称':<10} {'入场':>8} {'股数':>6} {'仓位':>6} {'止损':>8} {'止盈':>8} {'风险':>8} {'策略':<14}")
    print("-" * 85)
    for p in plans:
        d = p.to_dict()
        print(
            f"{p.stock_code:<8} {p.stock_name:<10} "
            f"{p.entry_price:>8.2f} {p.position_size:>6} "
            f"{p.position_pct*100:>5.1f}% {p.stop_loss:>8.2f} "
            f"{p.take_profit:>8.2f} {p.risk_amount:>8.0f} "
            f"{p.strategy_name:<14}"
        )

    # ── 测试2: 移动止盈 ──
    print(f"\n── 测试2: get_trailing_stop() ──")
    print(f"{'价格':>8} {'浮盈%':>8} {'移动止损':>10} {'触发?':>6}")
    print("-" * 35)
    for price in [100, 103, 105, 108, 110, 120, 125]:
        trail = planner.get_trailing_stop(100.0, price)
        profit = (price - 100) / 100 * 100
        print(f"{price:>8.2f} {profit:>7.1f}% {trail:>10.2f} {'  ✅' if trail > 0 else '  —'}")

    # ── 测试3: create_plan() 旧版兼容 ──
    print(f"\n── 测试3: create_plan() 旧版兼容 ──")
    df = pd.DataFrame(mock_results)
    df["code"] = df["stock_code"]
    df["name"] = df["stock_name"]
    df["best_strategy"] = df["strategy_name"]
    df["score"] = df["signal_score"]

    old_plans = planner.create_plan(df)
    for p in old_plans:
        print(f"  {p.stock} {p.name}: {p.shares}股 | 止{p.stop_loss:.2f} 盈{p.take_profit:.2f}")

    print(f"\n✅ 自测完成")
