#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模拟交易账户 (Paper Trading Account)
============================================
纯模拟账户，不执行真实订单。
- 跟踪现金、持仓、交易历史
- 计算总资产、盈亏、每日盈亏
- 状态持久化到 data/ 目录 JSON
- 带时间戳的交易日志

用法:
    from steps.simulator import SimAccount

    acc = SimAccount(initial_capital=1000000)
    acc.buy("600519", price=1800.00, shares=100, reason="首板起爆")
    acc.sell("600519", price=1850.00, shares=100, reason="止盈")
    print(acc.summary())
    acc.save()  # 保存到 data/sim_state.json
"""

from __future__ import annotations

import json
import logging
import os
import copy
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# 默认配置
# ═══════════════════════════════════════════════════════════════════

# 默认数据目录 (相对于项目根目录)
DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DEFAULT_STATE_FILE = "sim_state.json"
DEFAULT_TRADE_LOG_FILE = "sim_trades.json"

# 交易费用
COMMISSION_RATE = 0.0003   # 佣金 0.03%
STAMP_TAX_RATE = 0.001     # 印花税 (卖出时收取) 0.1%
SLIPPAGE = 0.001           # 滑点 0.1%


# ═══════════════════════════════════════════════════════════════════
# 模拟账户
# ═══════════════════════════════════════════════════════════════════

class SimAccount:
    """
    模拟交易账户 — 纯纸面交易。

    Parameters
    ----------
    initial_capital : float  初始资金 (默认 100万)
    data_dir : str           数据保存目录
    state_file : str         状态文件名
    trade_log_file : str     交易日志文件名
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        data_dir: str | None = None,
        state_file: str | None = None,
        trade_log_file: str | None = None,
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, dict] = {}  # code -> {shares, avg_cost, current_price}
        self.trades: List[dict] = []           # 交易历史
        self.daily_snapshots: Dict[str, dict] = {}  # date_str -> {total_value, cash, ...}
        self._benchmark_prices: Dict[str, float] = {}  # 基准价格 (用于计算盈亏)
        self._current_prices: Dict[str, float] = {}   # 当前实时价格

        # 文件路径
        self.data_dir = Path(data_dir or DEFAULT_DATA_DIR)
        self.state_file = state_file or DEFAULT_STATE_FILE
        self.trade_log_file = trade_log_file or DEFAULT_TRADE_LOG_FILE
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._created_at = datetime.now().isoformat()

    # ── 核心操作 ──────────────────────────────────────────────

    def buy(
        self,
        code: str,
        price: float,
        shares: int,
        reason: str = "",
    ) -> dict:
        """
        买入股票。

        Parameters
        ----------
        code : str     股票代码
        price : float  买入单价
        shares : int   买入股数 (必须是100的整数倍)
        reason : str   买入原因

        Returns
        -------
        dict  {success, order_id, cost, ...}
        """
        code = str(code).strip()
        shares = int(shares)

        if shares <= 0:
            return {"success": False, "error": f"股数必须>0, 实际: {shares}"}

        # 计算费用: 成交金额 + 佣金 + 滑点
        raw_amount = price * shares
        commission = raw_amount * COMMISSION_RATE
        slippage_cost = raw_amount * SLIPPAGE
        total_cost = raw_amount + commission + slippage_cost

        if self.cash < total_cost:
            return {
                "success": False,
                "error": f"资金不足: 需要 {total_cost:.2f}, 可用 {self.cash:.2f}",
                "required": round(total_cost, 2),
                "available": round(self.cash, 2),
            }

        # 执行买入
        self.cash -= total_cost

        if code in self.positions:
            # 加仓: 计算新的均价
            pos = self.positions[code]
            old_total_cost = pos["shares"] * pos["avg_cost"]
            new_total_cost = old_total_cost + raw_amount
            pos["shares"] += shares
            pos["avg_cost"] = new_total_cost / pos["shares"]
        else:
            self.positions[code] = {
                "shares": shares,
                "avg_cost": price,
                "current_price": price,
            }

        # 记录交易
        trade = {
            "order_id": self._next_order_id(),
            "action": "buy",
            "code": code,
            "price": price,
            "shares": shares,
            "amount": raw_amount,
            "commission": round(commission, 2),
            "slippage": round(slippage_cost, 2),
            "total_cost": round(total_cost, 2),
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "cash_after": round(self.cash, 2),
        }
        self.trades.append(trade)

        # 更新当前价格
        self._current_prices[code] = price

        logger.info(
            f"[BUY] {code} x{shares} @ {price:.2f} | "
            f"成本 {total_cost:.2f} | 剩余现金 {self.cash:.2f}"
        )

        return {
            "success": True,
            **trade,
        }

    def sell(
        self,
        code: str,
        price: float,
        shares: int,
        reason: str = "",
    ) -> dict:
        """
        卖出股票。

        Parameters
        ----------
        code : str     股票代码
        price : float  卖出单价
        shares : int   卖出股数 (<=持仓)
        reason : str   卖出原因

        Returns
        -------
        dict  {success, order_id, revenue, pnl, ...}
        """
        code = str(code).strip()
        shares = int(shares)

        if code not in self.positions:
            return {"success": False, "error": f"无持仓: {code}"}

        pos = self.positions[code]
        if shares <= 0:
            return {"success": False, "error": f"股数必须>0, 实际: {shares}"}
        if shares > pos["shares"]:
            return {
                "success": False,
                "error": f"持仓不足: 需要 {shares}, 持有 {pos['shares']}",
            }

        # 计算收入: 成交金额 - 佣金 - 印花税 - 滑点
        raw_amount = price * shares
        commission = raw_amount * COMMISSION_RATE
        stamp_tax = raw_amount * STAMP_TAX_RATE
        slippage_cost = raw_amount * SLIPPAGE
        net_revenue = raw_amount - commission - stamp_tax - slippage_cost

        # 计算盈亏
        cost_basis = shares * pos["avg_cost"]
        pnl = net_revenue - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0

        # 执行卖出
        self.cash += net_revenue

        if shares == pos["shares"]:
            del self.positions[code]
            if code in self._current_prices:
                del self._current_prices[code]
        else:
            pos["shares"] -= shares

        # 记录交易
        trade = {
            "order_id": self._next_order_id(),
            "action": "sell",
            "code": code,
            "price": price,
            "shares": shares,
            "amount": raw_amount,
            "commission": round(commission, 2),
            "stamp_tax": round(stamp_tax, 2),
            "slippage": round(slippage_cost, 2),
            "net_revenue": round(net_revenue, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "cash_after": round(self.cash, 2),
        }
        self.trades.append(trade)

        logger.info(
            f"[SELL] {code} x{shares} @ {price:.2f} | "
            f"盈亏 {pnl:+.2f} ({pnl_pct:+.2f}%) | 剩余现金 {self.cash:.2f}"
        )

        return {
            "success": True,
            **trade,
        }

    def update_price(self, code: str, price: float):
        """更新持仓股票的当前市价"""
        self._current_prices[code] = price
        if code in self.positions:
            self.positions[code]["current_price"] = price

    def update_prices(self, prices: Dict[str, float]):
        """
        批量更新持仓股票市价。

        Parameters
        ----------
        prices : dict  {code: price, ...}
        """
        for code, price in prices.items():
            self.update_price(code, price)

    # ── 属性计算 ──────────────────────────────────────────────

    @property
    def total_value(self) -> float:
        """总资产 = 现金 + 持仓市值"""
        return self.cash + self.positions_value

    @property
    def positions_value(self) -> float:
        """持仓总市值"""
        return sum(
            pos["shares"] * pos.get("current_price", pos["avg_cost"])
            for pos in self.positions.values()
        )

    @property
    def pnl(self) -> float:
        """总盈亏 (相对于初始资金)"""
        return self.total_value - self.initial_capital

    @property
    def pnl_pct(self) -> float:
        """总盈亏百分比"""
        if self.initial_capital <= 0:
            return 0.0
        return (self.pnl / self.initial_capital) * 100

    def position_pnl(self, code: str) -> Tuple[float, float]:
        """单只股票的持仓盈亏 (绝对值, 百分比)"""
        if code not in self.positions:
            return 0.0, 0.0
        pos = self.positions[code]
        current = pos.get("current_price", pos["avg_cost"])
        pnl = (current - pos["avg_cost"]) * pos["shares"]
        cost = pos["avg_cost"] * pos["shares"]
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0
        return round(pnl, 2), round(pnl_pct, 2)

    # ── 快照 (用于每日盈亏) ─────────────────────────────────

    def take_snapshot(self, date_str: str | None = None):
        """
        记录当日快照，供 daily_pnl 计算。

        Parameters
        ----------
        date_str : str  日期字符串 "YYYY-MM-DD", None 为今天
        """
        if date_str is None:
            date_str = date.today().isoformat()

        self.daily_snapshots[date_str] = {
            "total_value": round(self.total_value, 2),
            "cash": round(self.cash, 2),
            "positions_value": round(self.positions_value, 2),
            "positions": {
                code: {
                    "shares": pos["shares"],
                    "price": pos.get("current_price", pos["avg_cost"]),
                }
                for code, pos in self.positions.items()
            },
        }

    def daily_pnl(self, date_str: str | None = None) -> Tuple[float, float]:
        """
        当日盈亏 (绝对值, 百分比)

        与前一天快照比较，若无前一天则与初始资金比较。
        """
        if date_str is None:
            date_str = date.today().isoformat()

        # 确保当天有快照
        if date_str not in self.daily_snapshots:
            self.take_snapshot(date_str)

        current_val = self.daily_snapshots[date_str]["total_value"]

        # 找前一天快照
        sorted_dates = sorted(self.daily_snapshots.keys())
        idx = sorted_dates.index(date_str) if date_str in sorted_dates else -1
        if idx > 0:
            prev_date = sorted_dates[idx - 1]
            prev_val = self.daily_snapshots[prev_date]["total_value"]
        else:
            prev_val = self.initial_capital

        daily_diff = current_val - prev_val
        daily_pct = (daily_diff / prev_val * 100) if prev_val > 0 else 0.0

        return round(daily_diff, 2), round(daily_pct, 2)

    # ── 摘要 ────────────────────────────────────────────────

    def summary(self) -> dict:
        """返回账户摘要字典"""
        positions_detail = []
        for code, pos in self.positions.items():
            pnl_val, pnl_pct_val = self.position_pnl(code)
            positions_detail.append({
                "code": code,
                "shares": pos["shares"],
                "avg_cost": round(pos["avg_cost"], 2),
                "current_price": round(pos.get("current_price", pos["avg_cost"]), 2),
                "market_value": round(pos["shares"] * pos.get("current_price", pos["avg_cost"]), 2),
                "pnl": pnl_val,
                "pnl_pct": pnl_pct_val,
                "weight_pct": round(
                    (pos["shares"] * pos.get("current_price", pos["avg_cost"]))
                    / max(self.total_value, 1) * 100,
                    1,
                ),
            })

        return {
            "initial_capital": self.initial_capital,
            "cash": round(self.cash, 2),
            "positions_value": round(self.positions_value, 2),
            "total_value": round(self.total_value, 2),
            "pnl": round(self.pnl, 2),
            "pnl_pct": round(self.pnl_pct, 2),
            "position_count": len(self.positions),
            "trade_count": len(self.trades),
            "positions": positions_detail,
            "created_at": self._created_at,
            "updated_at": datetime.now().isoformat(),
        }

    def get_trade_df(self) -> pd.DataFrame:
        """交易记录转 DataFrame"""
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame(self.trades)

    def get_position_df(self) -> pd.DataFrame:
        """持仓转 DataFrame"""
        if not self.positions:
            return pd.DataFrame()
        rows = []
        for code, pos in self.positions.items():
            pnl_val, pnl_pct_val = self.position_pnl(code)
            rows.append({
                "code": code,
                "shares": pos["shares"],
                "avg_cost": pos["avg_cost"],
                "current_price": pos.get("current_price", pos["avg_cost"]),
                "market_value": pos["shares"] * pos.get("current_price", pos["avg_cost"]),
                "pnl": pnl_val,
                "pnl_pct": pnl_pct_val,
            })
        return pd.DataFrame(rows)

    # ── 持久化 ──────────────────────────────────────────────

    def save(self):
        """保存账户状态到 JSON"""
        state = {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "positions": {
                code: {
                    "shares": pos["shares"],
                    "avg_cost": pos["avg_cost"],
                    "current_price": pos.get("current_price", pos["avg_cost"]),
                }
                for code, pos in self.positions.items()
            },
            "daily_snapshots": self.daily_snapshots,
            "_current_prices": self._current_prices,
            "created_at": self._created_at,
            "updated_at": datetime.now().isoformat(),
        }

        state_path = self.data_dir / self.state_file
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, default=str)

        # 单独保存交易日志
        trades_path = self.data_dir / self.trade_log_file
        with open(trades_path, "w", encoding="utf-8") as f:
            json.dump(self.trades, f, ensure_ascii=False, indent=2, default=str)

        logger.info(
            f"[SAVE] 状态已保存 → {state_path}  |  交易记录 → {trades_path}"
        )

    def load(self) -> bool:
        """
        从 JSON 加载账户状态。

        Returns
        -------
        bool  是否加载成功
        """
        state_path = self.data_dir / self.state_file
        if not state_path.exists():
            logger.warning(f"[LOAD] 状态文件不存在: {state_path}")
            return False

        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        self.initial_capital = state.get("initial_capital", self.initial_capital)
        self.cash = state.get("cash", self.cash)
        self._created_at = state.get("created_at", self._created_at)

        # 加载持仓
        self.positions = {}
        for code, pos in state.get("positions", {}).items():
            self.positions[code] = {
                "shares": pos["shares"],
                "avg_cost": pos["avg_cost"],
                "current_price": pos.get("current_price", pos["avg_cost"]),
            }

        self.daily_snapshots = state.get("daily_snapshots", {})
        self._current_prices = state.get("_current_prices", {})

        # 加载交易日志
        trades_path = self.data_dir / self.trade_log_file
        if trades_path.exists():
            with open(trades_path, "r", encoding="utf-8") as f:
                self.trades = json.load(f)

        logger.info(
            f"[LOAD] 状态已加载 | 现金 {self.cash:.2f} | "
            f"持仓 {len(self.positions)} 只 | 交易 {len(self.trades)} 笔"
        )
        return True

    def reset(self):
        """重置账户到初始状态"""
        self.cash = self.initial_capital
        self.positions.clear()
        self.trades.clear()
        self.daily_snapshots.clear()
        self._current_prices.clear()
        self._created_at = datetime.now().isoformat()
        logger.info(f"[RESET] 账户已重置, 初始资金 {self.initial_capital:.2f}")

    # ── 内部辅助 ────────────────────────────────────────────

    def _next_order_id(self) -> int:
        return len(self.trades) + 1
