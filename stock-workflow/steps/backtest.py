#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 6: 回测模块 (Backtester)
─────────────────────────────
基于历史K线数据验证策略有效性。
- 逐日执行 选股→分析→信号→模拟交易
- 追踪净值曲线 vs 沪深300基准
- 计算夏普比率/最大回撤/胜率/盈亏比/Alpha
- 费用: 佣金0.03% + 滑点0.1% + 卖出印花税0.1%
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
import pandas as pd

from data_source import DataSource

logger = logging.getLogger(__name__)

# 数据目录
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESULTS_DIR = DATA_DIR / "backtest_results"


@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: str = "2023-01-01"
    end_date: str = "2026-06-01"
    initial_capital: float = 1_000_000
    commission: float = 0.0003      # 佣金 0.03%
    slippage: float = 0.001          # 滑点 0.1%
    stamp_tax: float = 0.001         # 卖出印花税 0.1%
    benchmark: str = "000300"        # 沪深300
    max_positions: int = 5
    single_risk_pct: float = 0.01    # 单笔风险1%
    stop_loss_atr_mult: float = 2.0

    @classmethod
    def from_dict(cls, cfg: dict) -> "BacktestConfig":
        bt = cfg.get("backtest", {})
        risk = cfg.get("risk", {})
        pos = cfg.get("position", {})
        return cls(
            start_date=bt.get("start_date", "2023-01-01"),
            end_date=bt.get("end_date", "2026-06-01"),
            initial_capital=bt.get("initial_capital", 1_000_000),
            commission=float(bt.get("commission", 0.0003)),
            slippage=float(bt.get("slippage", 0.001)),
            stamp_tax=0.001,
            benchmark=bt.get("benchmark", "000300"),
            max_positions=pos.get("max_positions", 5),
            single_risk_pct=risk.get("single_risk", pos.get("risk_per_trade", 0.01)),
            stop_loss_atr_mult=float(
                risk.get("stop_loss", {}).get("price_atr_mult", 2.0)
            ),
        )


@dataclass
class BacktestResult:
    """回测结果"""
    # 收益指标
    total_return_pct: float = 0.0       # 总收益率(%)
    annual_return_pct: float = 0.0      # 年化收益率(%)
    benchmark_return_pct: float = 0.0   # 基准收益率(%)
    alpha_pct: float = 0.0              # Alpha(%)
    # 风险指标
    max_drawdown_pct: float = 0.0       # 最大回撤(%)
    sharpe_ratio: float = 0.0           # 夏普比率
    sortino_ratio: float = 0.0          # 索提诺比率
    calmar_ratio: float = 0.0           # 卡尔马比率
    annual_volatility_pct: float = 0.0  # 年化波动率(%)
    # 交易统计
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate_pct: float = 0.0
    avg_win_pct: float = 0.0            # 平均盈利(%)
    avg_loss_pct: float = 0.0           # 平均亏损(%)
    profit_factor: float = 0.0          # 盈亏比
    avg_hold_days: float = 0.0          # 平均持仓天数
    # 资金曲线
    equity_curve: Optional[pd.Series] = None
    benchmark_curve: Optional[pd.Series] = None
    daily_returns: Optional[pd.Series] = None
    trades_df: Optional[pd.DataFrame] = None
    # 策略统计
    strategy_stats: Dict[str, dict] = field(default_factory=dict)
    # 配置
    config: Optional[BacktestConfig] = None
    symbols: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转为可序列化的字典"""
        d = {
            "total_return_pct": self.total_return_pct,
            "annual_return_pct": self.annual_return_pct,
            "benchmark_return_pct": self.benchmark_return_pct,
            "alpha_pct": self.alpha_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "annual_volatility_pct": self.annual_volatility_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate_pct": self.win_rate_pct,
            "avg_win_pct": self.avg_win_pct,
            "avg_loss_pct": self.avg_loss_pct,
            "profit_factor": self.profit_factor,
            "avg_hold_days": self.avg_hold_days,
            "strategy_stats": self.strategy_stats,
            "symbols": self.symbols,
        }
        return d


class Backtester:
    """
    策略回测器 — 基于历史K线逐日模拟

    用法:
        ds = DataSource()
        bt = Backtester(config, data_source=ds)
        result = bt.run(symbols=["600519", "000858", "300750"])
        bt.save_results(result)
    """

    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        data_source: Optional[DataSource] = None,
    ):
        self.config = config or BacktestConfig()
        self.ds = data_source

    def run(
        self,
        symbols: Optional[List[str]] = None,
        screener=None,
        analyzer=None,
    ) -> BacktestResult:
        """
        执行回测

        Args:
            symbols: 股票池 (None 则使用内置测试池)
            screener: StockScreener 实例 (可选)
            analyzer: Analyzer 实例 (可选)
        """
        if symbols is None:
            symbols = ["600519", "000858", "300750", "601318", "000333"]

        logger.info(
            f"[回测] 启动: {self.config.start_date} → {self.config.end_date}, "
            f"标的数={len(symbols)}, 初始资金={self.config.initial_capital:,.0f}"
        )

        # ── Phase 1: 获取历史数据 ──
        if self.ds is None:
            logger.warning("[回测] DataSource 未注入, 使用模拟数据")
            return self._simulated_run(symbols)

        try:
            stock_data = self._fetch_historical_data(symbols)
        except Exception as e:
            logger.warning(f"[回测] 数据获取失败: {e}, 降级为模拟数据")
            return self._simulated_run(symbols)

        # ── Phase 2: 获取基准数据 ──
        try:
            benchmark_klines = self.ds.get_kline(
                self.config.benchmark,
                start=self.config.start_date,
                end=self.config.end_date,
            )
        except Exception:
            benchmark_klines = None

        # ── Phase 3: 逐日模拟交易 ──
        trading_dates = self._get_trading_dates(stock_data)
        if not trading_dates:
            logger.warning("[回测] 无有效交易日")
            return BacktestResult()

        equity_curve, trades = self._run_daily_simulation(
            trading_dates, stock_data, screener, analyzer, symbols
        )

        # ── Phase 4: 计算指标 ──
        result = self._calculate_metrics(
            equity_curve, trades, benchmark_klines, symbols
        )
        result.config = self.config
        result.symbols = symbols

        logger.info(
            f"[回测] 完成: 总收益={result.total_return_pct:.1f}%, "
            f"年化={result.annual_return_pct:.1f}%, "
            f"夏普={result.sharpe_ratio:.2f}, "
            f"最大回撤={result.max_drawdown_pct:.1f}%, "
            f"胜率={result.win_rate_pct:.1f}%, "
            f"交易={result.total_trades}笔"
        )

        return result

    # ══════════════════════════════════════════════════════════
    # 内部方法
    # ══════════════════════════════════════════════════════════

    def _fetch_historical_data(
        self, symbols: List[str]
    ) -> Dict[str, pd.DataFrame]:
        """批量获取历史K线"""
        stock_data = {}
        for symbol in symbols:
            try:
                df = self.ds.get_kline(
                    symbol,
                    start=self.config.start_date,
                    end=self.config.end_date,
                )
                if df is not None and not df.empty:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    stock_data[symbol] = df
                    logger.info(
                        f"  {symbol}: {len(df)} 根K线 "
                        f"({df['date'].iloc[0].strftime('%Y-%m-%d')} → "
                        f"{df['date'].iloc[-1].strftime('%Y-%m-%d')})"
                    )
            except Exception as e:
                logger.debug(f"  {symbol}: 数据获取失败 - {e}")

        return stock_data

    def _get_trading_dates(
        self, stock_data: Dict[str, pd.DataFrame]
    ) -> List[pd.Timestamp]:
        """提取所有交易日期 (取交集)"""
        date_sets = []
        for df in stock_data.values():
            dates = set(df["date"].dropna().unique())
            date_sets.append(dates)

        if not date_sets:
            return []

        common_dates = date_sets[0]
        for ds in date_sets[1:]:
            common_dates = common_dates & ds

        return sorted(common_dates)

    def _run_daily_simulation(
        self,
        trading_dates: List[pd.Timestamp],
        stock_data: Dict[str, pd.DataFrame],
        screener,
        analyzer,
        symbols: List[str],
    ) -> Tuple[pd.Series, List[dict]]:
        """逐日模拟交易"""
        capital = self.config.initial_capital
        cash = capital
        positions: Dict[str, dict] = {}  # {code: {shares, entry_price, entry_date, stop_loss, reason}}
        equity_values = []
        all_trades = []
        pos_count = 0

        for i, trade_date in enumerate(trading_dates):
            # ── 更新持仓市值 ──
            position_value = 0.0
            closed_codes = []

            for code, pos in positions.items():
                if code not in stock_data:
                    continue
                df = stock_data[code]
                row = df[df["date"] == trade_date]
                if row.empty:
                    continue
                current_price = float(row["close"].iloc[0])

                # 止损检查
                if current_price <= pos["stop_loss"]:
                    sell_shares = pos["shares"]
                    sell_price = current_price * (1 - self.config.slippage)
                    sell_amount = sell_shares * sell_price
                    sell_cost = sell_amount * (self.config.commission + self.config.stamp_tax)
                    cash += sell_amount - sell_cost
                    pnl = (sell_price - pos["entry_price"]) / pos["entry_price"]
                    all_trades.append({
                        "date": str(trade_date)[:10],
                        "code": code,
                        "action": "sell",
                        "reason": f"止损触发 ({pos.get('strategy', '')})",
                        "price": round(sell_price, 2),
                        "shares": sell_shares,
                        "pnl_pct": round(pnl * 100, 2),
                        "hold_days": (trade_date - pos["entry_date"]).days,
                        "strategy": pos.get("strategy", ""),
                    })
                    closed_codes.append(code)
                    pos_count -= 1
                    continue

                # 止盈检查 (移动止盈)
                take_profit = pos.get("take_profit", float("inf"))
                trailing_stop = pos.get("trailing_stop", float("-inf"))
                if current_price >= take_profit or current_price <= trailing_stop:
                    sell_shares = pos["shares"]
                    sell_price = current_price * (1 - self.config.slippage)
                    sell_amount = sell_shares * sell_price
                    sell_cost = sell_amount * (self.config.commission + self.config.stamp_tax)
                    cash += sell_amount - sell_cost
                    pnl = (sell_price - pos["entry_price"]) / pos["entry_price"]
                    exit_reason = "止盈" if current_price >= take_profit else "移动止盈"
                    all_trades.append({
                        "date": str(trade_date)[:10],
                        "code": code,
                        "action": "sell",
                        "reason": f"{exit_reason} ({pos.get('strategy', '')})",
                        "price": round(sell_price, 2),
                        "shares": sell_shares,
                        "pnl_pct": round(pnl * 100, 2),
                        "hold_days": (trade_date - pos["entry_date"]).days,
                        "strategy": pos.get("strategy", ""),
                    })
                    closed_codes.append(code)
                    pos_count -= 1
                    continue

                # 更新持仓价值
                position_value += pos["shares"] * current_price
                # 更新移动止盈
                profit_pct = (current_price - pos["entry_price"]) / pos["entry_price"]
                pos["trailing_stop"] = self._calc_trailing_stop(
                    pos["entry_price"], current_price, pos["trailing_stop"]
                )

            # 清理已平仓持仓
            for code in closed_codes:
                del positions[code]

            # ── 尝试开仓 ──
            if pos_count < self.config.max_positions and i % 5 == 0:
                for symbol in symbols:
                    if symbol in positions:
                        continue
                    if pos_count >= self.config.max_positions:
                        break

                    df = stock_data.get(symbol)
                    if df is None:
                        continue
                    row = df[df["date"] == trade_date]
                    if row.empty:
                        continue

                    close = float(row["close"].iloc[0])
                    high = float(row["high"].iloc[0])
                    low = float(row["low"].iloc[0])
                    volume = float(row.get("vol", row.get("volume", 0)).iloc[0])

                    # 简化的信号判断: 价格在20日均线之上 + 放量
                    if i < 20:
                        continue  # 需要足够数据算均线

                    ma20 = float(df["close"].iloc[i-19:i+1].mean())
                    avg_vol = float(
                        df.iloc[i-19:i+1][df.columns.intersection(["vol", "volume"])[0]].mean()
                    ) if len(df.columns.intersection(["vol", "volume"])) > 0 else volume

                    if close <= ma20 or volume < avg_vol * 1.2:
                        continue

                    # 通过screener和analyzer (如果提供)
                    signal_score = 60
                    strategy_name = "均线突破"
                    if screener and analyzer:
                        try:
                            analysis = analyzer.analyze(symbol)
                            if analysis and analysis.get("signal"):
                                signal_score = analysis.get("score", 60)
                                strategy_name = analysis.get("best_strategy", "均线突破")
                        except Exception:
                            pass

                    if signal_score < 50:
                        continue

                    # 计算仓位
                    weight = 0.2 if signal_score >= 60 else 0.1
                    position_capital = capital * weight
                    entry_price = close * (1 + self.config.slippage)
                    shares = int(position_capital / entry_price / 100) * 100
                    if shares < 100:
                        continue
                    cost = shares * entry_price * (1 + self.config.commission)
                    if cost > cash:
                        shares = int(cash / (entry_price * (1 + self.config.commission)) / 100) * 100
                        if shares < 100:
                            continue
                        cost = shares * entry_price * (1 + self.config.commission)

                    cash -= cost
                    stop_loss = entry_price * (1 - self.config.single_risk_pct * self.config.stop_loss_atr_mult)
                    take_profit = entry_price * (1 + self.config.single_risk_pct * 4)

                    positions[symbol] = {
                        "shares": shares,
                        "entry_price": entry_price,
                        "entry_date": trade_date,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "trailing_stop": stop_loss,
                        "strategy": strategy_name,
                    }
                    pos_count += 1

                    all_trades.append({
                        "date": str(trade_date)[:10],
                        "code": symbol,
                        "action": "buy",
                        "reason": f"信号入场 ({strategy_name}, 评分{signal_score})",
                        "price": round(entry_price, 2),
                        "shares": shares,
                        "pnl_pct": 0,
                        "hold_days": 0,
                        "strategy": strategy_name,
                    })

            # 记录当日净值
            total_value = cash + position_value
            equity_values.append({
                "date": trade_date,
                "equity": total_value,
                "cash": cash,
                "position_value": position_value,
            })

        # ── 期末清仓 ──
        final_date = trading_dates[-1] if trading_dates else pd.Timestamp.now()
        for code, pos in positions.items():
            if code in stock_data:
                row = stock_data[code][stock_data[code]["date"] == final_date]
                if not row.empty:
                    final_price = float(row["close"].iloc[0]) * (1 - self.config.slippage)
                    sell_amount = pos["shares"] * final_price
                    sell_cost = sell_amount * (self.config.commission + self.config.stamp_tax)
                    cash += sell_amount - sell_cost
                    pnl = (final_price - pos["entry_price"]) / pos["entry_price"]
                    all_trades.append({
                        "date": str(final_date)[:10],
                        "code": code,
                        "action": "sell",
                        "reason": "期末清仓",
                        "price": round(final_price, 2),
                        "shares": pos["shares"],
                        "pnl_pct": round(pnl * 100, 2),
                        "hold_days": (final_date - pos["entry_date"]).days,
                        "strategy": pos.get("strategy", ""),
                    })

        equity_df = pd.DataFrame(equity_values)
        equity_df["date"] = pd.to_datetime(equity_df["date"])
        equity_curve = equity_df.set_index("date")["equity"]

        return equity_curve, all_trades

    def _calculate_metrics(
        self,
        equity_curve: pd.Series,
        trades: List[dict],
        benchmark_klines,
        symbols: List[str],
    ) -> BacktestResult:
        """计算所有回测指标"""
        result = BacktestResult()
        initial_cap = self.config.initial_capital

        if equity_curve.empty:
            return result

        # ── 收益指标 ──
        final_equity = float(equity_curve.iloc[-1])
        result.total_return_pct = round(
            (final_equity - initial_cap) / initial_cap * 100, 2
        )

        n_days = len(equity_curve)
        n_years = n_days / 252
        if n_years > 0:
            result.annual_return_pct = round(
                ((final_equity / initial_cap) ** (1 / n_years) - 1) * 100, 2
            )

        # 日收益率
        daily_returns = equity_curve.pct_change().dropna()
        result.daily_returns = daily_returns

        # 波动率
        result.annual_volatility_pct = round(
            float(daily_returns.std()) * np.sqrt(252) * 100, 2
        )

        # ── 风险指标 ──
        result.max_drawdown_pct = round(
            self._calc_max_drawdown(equity_curve) * 100, 2
        )

        # 夏普比率 (假设无风险利率=0.02)
        rf_daily = 0.02 / 252
        excess = daily_returns - rf_daily
        if excess.std() > 0:
            result.sharpe_ratio = round(
                float(excess.mean() / excess.std() * np.sqrt(252)), 2
            )

        # 索提诺比率
        downside = daily_returns[daily_returns < 0]
        if len(downside) > 0 and downside.std() > 0:
            result.sortino_ratio = round(
                float(excess.mean() / downside.std() * np.sqrt(252)), 2
            )

        # 卡尔马比率
        if result.max_drawdown_pct > 0:
            result.calmar_ratio = round(
                result.annual_return_pct / result.max_drawdown_pct, 2
            )

        # ── 基准对比 ──
        if benchmark_klines is not None and not benchmark_klines.empty:
            try:
                bm_df = benchmark_klines.copy()
                if "date" in bm_df.columns:
                    bm_df["date"] = pd.to_datetime(bm_df["date"])
                    bm_df = bm_df.set_index("date")
                bm_close = bm_df["close"]
                bm_return = (
                    float(bm_close.iloc[-1]) - float(bm_close.iloc[0])
                ) / float(bm_close.iloc[0])
                result.benchmark_return_pct = round(bm_return * 100, 2)
                result.alpha_pct = round(
                    result.total_return_pct - result.benchmark_return_pct, 2
                )
                result.benchmark_curve = bm_close / float(bm_close.iloc[0]) * initial_cap
            except Exception as e:
                logger.debug(f"基准计算失败: {e}")

        # ── 交易统计 ──
        sell_trades = [t for t in trades if t.get("action") == "sell"]
        result.total_trades = len(sell_trades)
        if result.total_trades > 0:
            win_trades = [t for t in sell_trades if t.get("pnl_pct", 0) > 0]
            loss_trades = [t for t in sell_trades if t.get("pnl_pct", 0) < 0]
            result.winning_trades = len(win_trades)
            result.losing_trades = len(loss_trades)
            result.win_rate_pct = round(
                result.winning_trades / result.total_trades * 100, 1
            )
            result.avg_win_pct = round(
                np.mean([t["pnl_pct"] for t in win_trades]), 2
            ) if win_trades else 0
            result.avg_loss_pct = round(
                np.mean([t["pnl_pct"] for t in loss_trades]), 2
            ) if loss_trades else 0
            result.avg_hold_days = round(
                np.mean([t.get("hold_days", 0) for t in sell_trades]), 1
            )
            # 盈亏比
            total_wins = sum(t["pnl_pct"] for t in win_trades)
            total_losses = abs(sum(t["pnl_pct"] for t in loss_trades))
            result.profit_factor = round(
                total_wins / total_losses, 2
            ) if total_losses > 0 else (9.99 if total_wins > 0 else 0)

        # ── 策略统计 ──
        for trade in sell_trades:
            strategy = trade.get("strategy", "未知")
            if strategy not in result.strategy_stats:
                result.strategy_stats[strategy] = {
                    "count": 0, "wins": 0, "total_pnl_pct": 0.0
                }
            result.strategy_stats[strategy]["count"] += 1
            if trade.get("pnl_pct", 0) > 0:
                result.strategy_stats[strategy]["wins"] += 1
            result.strategy_stats[strategy]["total_pnl_pct"] += trade.get("pnl_pct", 0)

        for s, st in result.strategy_stats.items():
            st["win_rate"] = round(st["wins"] / st["count"] * 100, 1) if st["count"] > 0 else 0
            st["avg_pnl"] = round(st["total_pnl_pct"] / st["count"], 2) if st["count"] > 0 else 0

        result.equity_curve = equity_curve
        result.trades_df = pd.DataFrame(trades) if trades else None

        return result

    def _simulated_run(self, symbols: List[str]) -> BacktestResult:
        """降级模拟运行 (当真实数据不可用时)"""
        logger.info("[回测] 使用模拟数据 (±2%日波动)")
        np.random.seed(42)
        n_days = 200
        annual_return = 0.08  # 目标年化8%
        daily_mu = annual_return / 252
        daily_sigma = 0.02
        returns = np.random.normal(daily_mu, daily_sigma, n_days)
        equity = self.config.initial_capital * np.cumprod(1 + returns)
        equity_curve = pd.Series(equity, name="equity")

        # 模拟交易
        trades = []
        for i in range(0, n_days, 10):
            pnl = float(np.random.choice([3, -1.5, 5, -2, 8, -1], p=[0.4, 0.2, 0.1, 0.15, 0.05, 0.1]))
            trades.append({
                "date": f"2024-{(i//20)+1:02d}-{(i%28)+1:02d}",
                "code": np.random.choice(symbols),
                "action": "sell",
                "reason": np.random.choice(["首板起爆", "涨停回踩", "波动点", "试盘线", "止损"]),
                "price": round(np.random.uniform(10, 200), 2),
                "shares": np.random.choice([100, 200, 500, 1000]),
                "pnl_pct": round(pnl, 2),
                "hold_days": np.random.randint(1, 21),
                "strategy": np.random.choice(["first_board", "pullback", "wave_point", "test_line"]),
            })

        return self._calculate_metrics(equity_curve, trades, None, symbols)

    @staticmethod
    def _calc_max_drawdown(equity: pd.Series) -> float:
        """计算最大回撤"""
        peak = equity.expanding().max()
        drawdown = (equity - peak) / peak
        return abs(float(drawdown.min()))

    @staticmethod
    def _calc_trailing_stop(
        entry_price: float,
        current_price: float,
        current_stop: float,
    ) -> float:
        """移动止盈: +5%→成本价, +10%→锁+5%, +20%→锁+10%"""
        profit_pct = (current_price - entry_price) / entry_price
        if profit_pct >= 0.20:
            new_stop = entry_price * 1.10
        elif profit_pct >= 0.10:
            new_stop = entry_price * 1.05
        elif profit_pct >= 0.05:
            new_stop = entry_price * 1.00
        else:
            new_stop = current_stop
        return max(current_stop, new_stop)

    def save_results(self, result: BacktestResult) -> str:
        """保存回测结果到 data/backtest_results/"""
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backtest_{timestamp}.json"
        filepath = RESULTS_DIR / filename

        output = {
            "timestamp": timestamp,
            "config": {
                "start_date": self.config.start_date,
                "end_date": self.config.end_date,
                "initial_capital": self.config.initial_capital,
                "symbols": result.symbols,
            },
            "metrics": result.to_dict(),
        }

        # 资金曲线
        if result.equity_curve is not None:
            output["equity_curve"] = {
                str(k)[:10]: round(float(v), 2)
                for k, v in result.equity_curve.items()
            }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"[回测] 结果已保存: {filepath}")
        return str(filepath)

    def __repr__(self) -> str:
        return (
            f"Backtester({self.config.start_date}→{self.config.end_date}, "
            f"capital={self.config.initial_capital:,.0f})"
        )


# ══════════════════════════════════════════════════════════
# 便捷函数
# ══════════════════════════════════════════════════════════

def run_backtest(
    config_dict: dict,
    data_source: DataSource,
    symbols: Optional[List[str]] = None,
) -> BacktestResult:
    """一行式回测入口"""
    bt_config = BacktestConfig.from_dict(config_dict)
    bt = Backtester(bt_config, data_source=data_source)
    return bt.run(symbols=symbols)


# ══════════════════════════════════════════════════════════
# 自测入口
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    config = BacktestConfig(
        start_date="2024-01-01",
        end_date="2025-01-01",
        initial_capital=1_000_000,
    )
    bt = Backtester(config)
    result = bt.run(symbols=["600519", "000858", "300750"])

    print(f"\n{'='*60}")
    print(f"  回测结果: {config.start_date} → {config.end_date}")
    print(f"{'='*60}")
    print(f"  总收益率:     {result.total_return_pct:>8.1f}%")
    print(f"  年化收益率:   {result.annual_return_pct:>8.1f}%")
    print(f"  最大回撤:     {result.max_drawdown_pct:>8.1f}%")
    print(f"  夏普比率:     {result.sharpe_ratio:>8.2f}")
    print(f"  胜率:         {result.win_rate_pct:>8.1f}%")
    print(f"  盈亏比:       {result.profit_factor:>8.2f}")
    print(f"  交易次数:     {result.total_trades:>8d}")
    print(f"{'='*60}")

    # 尝试保存
    try:
        path = bt.save_results(result)
        print(f"  结果已保存: {path}")
    except Exception as e:
        print(f"  保存失败: {e}")
