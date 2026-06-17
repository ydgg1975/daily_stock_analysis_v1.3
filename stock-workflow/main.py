#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A股全流程自动化交易系统 — 主入口
====================================
7 步全流程: 选股 → 分析 → 计划 → 监控 → 模拟 → 回测 → 复盘

用法:
    python main.py                  # 全流程 (选股+监控)
    python main.py --select-only    # 仅选股 (1-3步)
    python main.py --monitor-only   # 仅监控 (4-7步)
    python main.py --dry-run        # 模拟模式 (不推送)
    python main.py --backtest       # 附加回测
    python main.py --once           # 单次执行 (不持续监控)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

# ═══════════════════════════════════════════════════════════════════════════
# 确保项目根目录在 sys.path
# ═══════════════════════════════════════════════════════════════════════════
PROJ_ROOT = Path(__file__).resolve().parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))


# ═══════════════════════════════════════════════════════════════════════════
# ANSI 颜色 (中国红涨绿跌: #f38ba8 / #a6e3a1)
# ═══════════════════════════════════════════════════════════════════════════

class Colors:
    """终端颜色"""
    RED     = "\033[38;2;243;139;168m"   # 红涨 #f38ba8
    GREEN   = "\033[38;2;166;227;161m"   # 绿跌 #a6e3a1
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    WHITE   = "\033[97m"
    GRAY    = "\033[90m"
    BOLD    = "\033[1m"
    RESET   = "\033[0m"

    @staticmethod
    def up(text: str) -> str:
        """涨 (红色)"""
        return f"{Colors.RED}{text}{Colors.RESET}"

    @staticmethod
    def down(text: str) -> str:
        """跌 (绿色)"""
        return f"{Colors.GREEN}{text}{Colors.RESET}"

    @staticmethod
    def bold(text: str) -> str:
        return f"{Colors.BOLD}{text}{Colors.RESET}"

    @staticmethod
    def info(text: str) -> str:
        return f"{Colors.CYAN}{text}{Colors.RESET}"

    @staticmethod
    def warn(text: str) -> str:
        return f"{Colors.YELLOW}{text}{Colors.RESET}"

    @staticmethod
    def gray(text: str) -> str:
        return f"{Colors.GRAY}{text}{Colors.RESET}"


# ═══════════════════════════════════════════════════════════════════════════
# 结构化日志
# ═══════════════════════════════════════════════════════════════════════════

def setup_logging(log_dir: str = "data/logs", level: str = "INFO") -> logging.Logger:
    """配置结构化日志 (控制台 + 文件)"""
    log_path = PROJ_ROOT / log_dir
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("stock_workflow")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复 handler
    if logger.handlers:
        return logger

    # 文件 handler
    log_file = log_path / f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    # 控制台 handler (带颜色)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        f"{Colors.GRAY}%(asctime)s{Colors.RESET} [%(levelname)-7s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(ch)

    logger.info(f"日志文件: {log_file}")
    return logger


# ═══════════════════════════════════════════════════════════════════════════
# 配置加载
# ═══════════════════════════════════════════════════════════════════════════

def load_config(config_path: str = "config.yaml") -> dict:
    """加载 config.yaml"""
    path = PROJ_ROOT / config_path
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


# ═══════════════════════════════════════════════════════════════════════════
# 进度显示
# ═══════════════════════════════════════════════════════════════════════════

def print_header(text: str, logger: Optional[logging.Logger] = None):
    """打印步骤标题"""
    line = "═" * 60
    msg = f"\n{Colors.BOLD}{Colors.CYAN}{line}\n  {text}\n{line}{Colors.RESET}"
    if logger:
        logger.info(text)
    print(msg)


def print_step(step_num: int, name: str, status: str = "running"):
    """打印步骤状态"""
    icons = {
        "running": "⏳",
        "ok": "✅",
        "fail": "❌",
        "skip": "⏭️",
    }
    icon = icons.get(status, "⏳")
    color = {"ok": Colors.GREEN, "fail": Colors.RED, "running": Colors.YELLOW, "skip": Colors.GRAY}.get(status, "")
    print(f"  {color}{icon} Step {step_num}: {name}{Colors.RESET}")


def print_result(rows: list[dict], title: str = ""):
    """打印股票列表"""
    if title:
        print(f"\n  {Colors.BOLD}{title}{Colors.RESET}")

    if not rows:
        print(f"  {Colors.GRAY}(空){Colors.RESET}")
        return

    # 表头
    header = f"  {'代码':<8} {'名称':<10} {'价格':>8} {'评分':>6} {'信号':>6}  {'战法'}"
    print(Colors.GRAY + header + Colors.RESET)
    print(Colors.GRAY + "  " + "─" * 60 + Colors.RESET)

    for r in rows:
        code = r.get("code", r.get("stock", ""))
        name = r.get("name", "")[:10]
        price = r.get("price", r.get("entry_price", 0))
        score = r.get("score", r.get("best_score", 0))
        signal = r.get("signal", r.get("signal_strength", ""))
        strategy = r.get("best_strategy", r.get("strategy", ""))

        price_str = f"{price:>8.2f}" if price else "       -"
        score_str = f"{score:>6.0f}" if score else "     -"

        sig_color = Colors.RED if signal in ("强", True) else (
            Colors.YELLOW if signal in ("中",) else Colors.GREEN
        )
        signal_str = str(signal)[:6]

        line = f"  {code:<8} {name:<10} {price_str} {score_str} {sig_color}{signal_str:<6}{Colors.RESET}  {Colors.GRAY}{strategy}{Colors.RESET}"
        print(line)


# ═══════════════════════════════════════════════════════════════════════════
# 主流程编排器
# ═══════════════════════════════════════════════════════════════════════════

class StockWorkflow:
    """
    A股全流程自动化交易系统 — 7 步流水线

    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ 1.选股  │ → │ 2.分析  │ → │ 3.计划  │ → │ 4.监控  │ → │ 5.模拟  │ → │ 6.回测  │ → │ 7.复盘  │
    │Screener │    │Analyzer │    │ Planner │    │ Monitor │    │SimAcct  │    │Backtest │    │ Review  │
    └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
    """

    def __init__(self, config: dict, args: argparse.Namespace):
        self.config = config
        self.args = args
        self.logger = logging.getLogger("stock_workflow")

        # 状态
        self.dry_run = args.dry_run or config.get("system", {}).get("dry_run", False)
        self.select_only = args.select_only
        self.monitor_only = args.monitor_only
        self.do_backtest = args.backtest

        # 初始化组件 (延迟加载)
        self.ds = None
        self.screener = None
        self.analyzer = None
        self.planner = None
        self.monitor = None
        self.account = None
        self.backtester = None
        self.reviewer = None
        self.notifier = None

        # 中间结果
        self.screening_result: Optional[pd.DataFrame] = None
        self.analysis_result: Optional[pd.DataFrame] = None
        self.plans: list = []
        self.alerts: list = []

    # ── 组件初始化 ────────────────────────────────────────────────────

    def _init_components(self):
        """延迟导入并初始化所有组件"""
        self.logger.info("初始化组件...")

        # DataSource
        try:
            from data_source import DataSource, get_ds
            data_cfg = self.config.get("data", {})
            self.ds = DataSource(data_cfg)
            self.logger.info(f"  数据源: {self.ds}")
        except Exception as e:
            self.logger.warning(f"  数据源初始化失败: {e}")
            self.ds = None

        # StockScreener
        try:
            from steps.screener import StockScreener, ScreenerConfig
            screen_cfg = self.config.get("screening", {})
            screener_config = ScreenerConfig.from_dict(screen_cfg) if screen_cfg else None
            self.screener = StockScreener(self.ds, screener_config) if self.ds else None
            self.logger.info("  选股器: ✓")
        except Exception as e:
            self.logger.warning(f"  选股器初始化失败: {e}")
            self.screener = None

        # Analyzer
        try:
            from steps.analyzer import Analyzer
            config_path = str(PROJ_ROOT / "config.yaml")
            self.analyzer = Analyzer(config_path=config_path)
            self.logger.info("  分析器: ✓ (4大战法)")
        except Exception as e:
            self.logger.warning(f"  分析器初始化失败: {e}")
            self.analyzer = None

        # Planner
        try:
            from steps.planner import Planner, PlanConfig
            plan_config = PlanConfig.from_dict(self.config)
            self.planner = Planner(plan_config)
            self.logger.info(f"  计划器: ✓ (资金{plan_config.capital:,.0f})")
        except Exception as e:
            self.logger.warning(f"  计划器初始化失败: {e}")
            self.planner = None

        # Monitor
        try:
            from steps.monitor import Monitor, MonitorConfig
            mon_config = MonitorConfig.from_dict(self.config)
            self.monitor = Monitor(
                data_source=self.ds,
                config=mon_config,
                on_alert=self._on_alert,
            )
            self.logger.info(f"  监控器: ✓ (间隔{mon_config.interval}s)")
        except Exception as e:
            self.logger.warning(f"  监控器初始化失败: {e}")
            self.monitor = None

        # SimAccount
        try:
            from steps.simulator import SimAccount
            capital = self.config.get("position", {}).get("capital", 1_000_000)
            self.account = SimAccount(initial_capital=capital)
            self.logger.info(f"  模拟账户: ✓ (初始资金{capital:,.0f})")
        except Exception as e:
            self.logger.warning(f"  模拟账户初始化失败: {e}")
            self.account = None

        # Backtester
        try:
            from steps.backtest import Backtester, BacktestConfig
            bt_config = BacktestConfig.from_dict(self.config)
            self.backtester = Backtester(bt_config)
            self.logger.info("  回测器: ✓")
        except Exception as e:
            self.logger.warning(f"  回测器初始化失败: {e}")
            self.backtester = None

        # Reviewer
        try:
            from steps.review import Reviewer, ReviewConfig
            rev_config = ReviewConfig.from_dict(self.config)
            self.reviewer = Reviewer(rev_config)
            self.logger.info("  复盘器: ✓")
        except Exception as e:
            self.logger.warning(f"  复盘器初始化失败: {e}")
            self.reviewer = None

        # Notifier
        try:
            from notify.pusher import Notifier, create_notifier_from_config
            self.notifier = create_notifier_from_config(self.config, dry_run=self.dry_run)
            self.logger.info(f"  推送器: {self.notifier}")
        except Exception as e:
            self.logger.warning(f"  推送器初始化失败: {e}")
            self.notifier = None

    # ── 预警回调 ──────────────────────────────────────────────────────

    def _on_alert(self, alert):
        """监控预警回调 — 推送到 Server酱"""
        self.alerts.append(alert)

        if not self.notifier or self.dry_run:
            return

        try:
            if alert.alert_type == "stop_loss":
                self.notifier.stop_loss_alert(alert.stock, 0)  # loss_pct 由 alert.message 包含
            elif alert.alert_type == "take_profit":
                self.notifier.take_profit_alert(alert.stock, 0)
            else:
                self.notifier.send_text(
                    f"[{alert.severity.upper()}] {alert.stock}",
                    alert.message,
                )
        except Exception as e:
            self.logger.error(f"推送预警失败: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # Step 1: 选股
    # ═══════════════════════════════════════════════════════════════════

    def step1_screening(self):
        """Step 1: 选股 — 粗筛 → 精筛 → 竞价承接力"""
        if self.monitor_only:
            print_step(1, "选股", "skip")
            return None

        print_step(1, "选股 (粗筛 → 精筛 → 竞价承接力)", "running")

        if not self.screener:
            self.logger.warning("[Step1] 选股器未初始化，跳过")
            print_step(1, "选股", "fail")
            return None

        try:
            result = self.screener.run()
            self.screening_result = result

            if result is not None and not result.empty:
                print_result(
                    result.to_dict("records"),
                    f"选股结果: Top {len(result)} 只",
                )
                print_step(1, f"选股完成 — {len(result)} 只入选", "ok")
            else:
                print_step(1, "选股 — 无股票通过筛选", "fail")

            return result
        except Exception as e:
            self.logger.error(f"[Step1] 选股异常: {e}\n{traceback.format_exc()}")
            print_step(1, f"选股失败: {e}", "fail")
            return None

    # ═══════════════════════════════════════════════════════════════════
    # Step 2: 分析
    # ═══════════════════════════════════════════════════════════════════

    def step2_analysis(self):
        """Step 2: 分析 — 4大战法并行检测"""
        if self.monitor_only:
            print_step(2, "分析", "skip")
            return None

        print_step(2, "分析 (4大战法检测)", "running")

        if not self.analyzer:
            self.logger.warning("[Step2] 分析器未初始化，跳过")
            print_step(2, "分析", "fail")
            return None

        if self.screening_result is None or self.screening_result.empty:
            self.logger.warning("[Step2] 无选股结果，跳过分析")
            print_step(2, "分析 — 无候选股票", "skip")
            return None

        try:
            codes = self.screening_result["code"].tolist()
            results = self.analyzer.analyze_batch(codes, ds=self.ds)

            # 转为 DataFrame
            if hasattr(self.analyzer, "get_signal_summary"):
                self.analysis_result = self.analyzer.get_signal_summary(results)
            else:
                records = []
                for sym, r in results.items():
                    records.append({
                        "code": sym,
                        "signal": r.signal,
                        "best_strategy": r.best_strategy,
                        "score": r.best_score,
                        "entry_price": r.entry_price,
                        "stop_loss": r.stop_loss,
                        "take_profit": r.take_profit,
                        "reason": r.reason,
                    })
                self.analysis_result = pd.DataFrame(records)

            # 打印结果
            signals = self.analysis_result[self.analysis_result["signal"] == True]
            print_result(
                self.analysis_result.to_dict("records"),
                f"分析结果: {len(signals)} 只有信号 / 共 {len(codes)} 只",
            )
            print_step(2, f"分析完成 — {len(signals)} 只触发买入信号", "ok")

            return self.analysis_result
        except Exception as e:
            self.logger.error(f"[Step2] 分析异常: {e}\n{traceback.format_exc()}")
            print_step(2, f"分析失败: {e}", "fail")
            return None

    # ═══════════════════════════════════════════════════════════════════
    # Step 3: 计划
    # ═══════════════════════════════════════════════════════════════════

    def step3_planning(self):
        """Step 3: 计划 — 仓位分配"""
        if self.monitor_only:
            print_step(3, "仓位计划", "skip")
            return None

        print_step(3, "仓位计划", "running")

        if not self.planner:
            self.logger.warning("[Step3] 计划器未初始化，跳过")
            print_step(3, "仓位计划", "fail")
            return None

        if self.analysis_result is None or self.analysis_result.empty:
            self.logger.warning("[Step3] 无分析结果，跳过计划")
            print_step(3, "仓位计划 — 无信号", "skip")
            return None

        try:
            self.plans = self.planner.create_plan(
                self.analysis_result,
                screening_results=self.screening_result,
            )

            if self.plans:
                for p in self.plans:
                    print(
                        f"    {Colors.BOLD}{p.stock}{Colors.RESET}  "
                        f"{p.shares}股 @{p.entry_price:.2f}  "
                        f"仓位{p.position_pct:.1f}%  "
                        f"止损{p.stop_loss:.2f} 止盈{p.take_profit:.2f}"
                    )
                print_step(3, f"仓位计划完成 — {len(self.plans)} 个持仓", "ok")
            else:
                print_step(3, "仓位计划 — 无合适仓位", "skip")

            return self.plans
        except Exception as e:
            self.logger.error(f"[Step3] 计划异常: {e}\n{traceback.format_exc()}")
            print_step(3, f"计划失败: {e}", "fail")
            return None

    # ═══════════════════════════════════════════════════════════════════
    # Step 4: 监控
    # ═══════════════════════════════════════════════════════════════════

    def step4_monitor(self):
        """Step 4: 监控 — 实时跟踪持仓"""
        if self.select_only:
            print_step(4, "监控", "skip")
            return

        print_step(4, "实时监控", "running")

        if not self.monitor:
            self.logger.warning("[Step4] 监控器未初始化，跳过")
            print_step(4, "监控", "fail")
            return

        # 同步持仓到监控器
        if self.plans:
            self.monitor.positions = self.plans

        if self.args.once:
            # 单次检查
            self.logger.info("[Step4] 单次监控检查...")
            if self.plans:
                for p in self.plans:
                    alerts = self.monitor._check_position(p)
                    for alert in alerts:
                        self._on_alert(alert)
            print_step(4, f"单次检查完成 — {len(self.alerts)} 条预警", "ok")
        else:
            # 持续监控
            self.logger.info("[Step4] 启动实时监控...")
            self.monitor.start(background=False)  # 阻塞运行

    # ═══════════════════════════════════════════════════════════════════
    # Step 5: 模拟交易
    # ═══════════════════════════════════════════════════════════════════

    def step5_simulation(self):
        """Step 5: 模拟 — 纸面交易跟踪"""
        if self.monitor_only:
            print_step(5, "模拟交易", "skip")
            return

        print_step(5, "模拟交易", "running")

        if not self.account:
            self.logger.warning("[Step5] 模拟账户未初始化，跳过")
            print_step(5, "模拟交易", "fail")
            return

        try:
            # 按计划开仓
            opened = 0
            for p in (self.plans or []):
                trade = self.account.open_position(
                    stock=p.stock,
                    name=p.name,
                    shares=p.shares,
                    price=p.entry_price,
                    strategy=p.strategy,
                )
                if trade:
                    opened += 1

            self.logger.info(f"[Step5] 模拟开仓 {opened}/{len(self.plans) if self.plans else 0} 笔")
            print(f"  {self.account}")
            print_step(5, f"模拟交易完成 — {opened} 笔开仓", "ok")
        except Exception as e:
            self.logger.error(f"[Step5] 模拟交易异常: {e}\n{traceback.format_exc()}")
            print_step(5, f"模拟交易失败: {e}", "fail")

    # ═══════════════════════════════════════════════════════════════════
    # Step 6: 回测
    # ═══════════════════════════════════════════════════════════════════

    def step6_backtest(self):
        """Step 6: 回测 — 历史数据验证"""
        if not self.do_backtest:
            print_step(6, "回测", "skip")
            return None

        print_step(6, "回测", "running")

        if not self.backtester:
            self.logger.warning("[Step6] 回测器未初始化，跳过")
            print_step(6, "回测", "fail")
            return None

        try:
            codes = None
            if self.screening_result is not None and not self.screening_result.empty:
                codes = self.screening_result["code"].tolist()

            result = self.backtester.run(
                screener=self.screener,
                analyzer=self.analyzer,
                data_source=self.ds,
                symbols=codes,
            )

            # 打印回测结果
            print(f"\n  {Colors.BOLD}回测结果{Colors.RESET}")
            print(f"    总收益:   {Colors.up(f'{result.total_return:+.2f}%') if result.total_return > 0 else Colors.down(f'{result.total_return:+.2f}%')}")
            print(f"    年化收益: {result.annual_return:+.2f}%")
            print(f"    最大回撤: {Colors.down(f'{result.max_drawdown:.2f}%')}")
            print(f"    夏普比率: {result.sharpe_ratio}")
            print(f"    胜率:     {result.win_rate}%")
            print(f"    盈亏比:   {result.profit_factor}")
            print_step(6, f"回测完成 — 总收益{result.total_return:+.2f}%", "ok")

            return result
        except Exception as e:
            self.logger.error(f"[Step6] 回测异常: {e}\n{traceback.format_exc()}")
            print_step(6, f"回测失败: {e}", "fail")
            return None

    # ═══════════════════════════════════════════════════════════════════
    # Step 7: 复盘
    # ═══════════════════════════════════════════════════════════════════

    def step7_review(self):
        """Step 7: 复盘 — 盘后总结"""
        if self.select_only:
            print_step(7, "复盘", "skip")
            return None

        print_step(7, "复盘总结", "running")

        if not self.reviewer:
            self.logger.warning("[Step7] 复盘器未初始化，跳过")
            print_step(7, "复盘", "fail")
            return None

        try:
            report = self.reviewer.review(
                account=self.account,
                analysis_results=self.analysis_result,
                plans=self.plans,
                alerts=self.alerts,
            )

            # 打印复盘结果
            print(f"\n  {Colors.BOLD}复盘报告 — {report.date}{Colors.RESET}")
            print(f"    选股准确率: {report.screening_accuracy:.1f}% ({report.valid_signals}/{report.total_signals})")

            if report.strategy_stats:
                print(f"    战法统计:")
                for name, stats in report.strategy_stats.items():
                    print(f"      {name}: {stats['count']}次 信号{stats['signals']}次 均分{stats['avg_score']}")

            if report.improvements:
                print(f"\n  {Colors.YELLOW}改进建议:{Colors.RESET}")
                for tip in report.improvements:
                    print(f"    💡 {tip}")

            print_step(7, f"复盘完成", "ok")

            # 推送每日汇总
            if self.notifier and not self.select_only:
                summary = {
                    "date": report.date,
                    "total_signals": report.total_signals,
                    "buy_signals": report.valid_signals,
                    "stop_loss_alerts": sum(1 for a in self.alerts if a.alert_type == "stop_loss"),
                    "take_profit_alerts": sum(1 for a in self.alerts if a.alert_type == "take_profit"),
                    "pnl": self.account.total_pnl if self.account else 0,
                    "pnl_pct": self.account.total_pnl_pct if self.account else 0,
                    "positions": self.account.summary()["holdings"] if self.account else [],
                    "top_picks": [
                        {"stock": p.stock, "signal": p.strategy, "score": p.score}
                        for p in (self.plans or [])
                    ] if self.plans else [],
                    "market_comment": "复盘完成，详见日志。",
                }
                try:
                    self.notifier.daily_summary(summary)
                except Exception as e:
                    self.logger.error(f"推送每日汇总失败: {e}")

            return report
        except Exception as e:
            self.logger.error(f"[Step7] 复盘异常: {e}\n{traceback.format_exc()}")
            print_step(7, f"复盘失败: {e}", "fail")
            return None

    # ── 全流程入口 ────────────────────────────────────────────────────

    def run(self):
        """执行全流程"""
        print_header("A股全流程自动化交易系统 v1.0", self.logger)
        print(f"  模式: {Colors.info('模拟' if self.dry_run else '实盘')} | "
              f"{Colors.info('选股' if not self.monitor_only else '监控')} | "
              f"{ Colors.info('回测' if self.do_backtest else '无回测')}")

        # 初始化
        self._init_components()

        if not self.ds:
            self.logger.error("数据源初始化失败，流程终止")
            return 1

        start_ts = time.time()

        # Step 1: 选股
        self.step1_screening()

        # Step 2: 分析
        self.step2_analysis()

        # Step 3: 计划
        self.step3_planning()

        # Step 4: 监控
        self.step4_monitor()

        # Step 5: 模拟
        self.step5_simulation()

        # Step 6: 回测
        self.step6_backtest()

        # Step 7: 复盘
        self.step7_review()

        elapsed = time.time() - start_ts
        print_header(f"流程结束 — 耗时 {elapsed:.1f} 秒", self.logger)

        if self.notifier:
            print(f"  推送统计: {self.notifier.stats}")

        return 0


# ═══════════════════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="A股全流程自动化交易系统 — 选股→分析→计划→监控→模拟→回测→复盘",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                  # 全流程
  python main.py --select-only    # 仅选股(1-3步)
  python main.py --monitor-only   # 仅监控(4-7步)
  python main.py --dry-run        # 模拟模式(不推送)
  python main.py --backtest       # 附加回测
  python main.py --once           # 单次执行(不持续监控)
  python main.py --config my_config.yaml  # 指定配置文件
        """,
    )
    parser.add_argument(
        "--select-only",
        action="store_true",
        help="仅执行选股→分析→计划 (Step 1-3)",
    )
    parser.add_argument(
        "--monitor-only",
        action="store_true",
        help="仅执行监控→模拟→复盘 (Step 4-7)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="模拟模式: 不实际推送通知",
    )
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="附加回测 (Step 6)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="单次执行，不进入持续监控循环",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="配置文件路径 (默认: config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别 (默认: INFO)",
    )

    args = parser.parse_args()

    # 互斥检查
    if args.select_only and args.monitor_only:
        parser.error("--select-only 和 --monitor-only 不能同时使用")

    return args


def main():
    """主入口"""
    args = parse_args()

    # 加载配置
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"{Colors.RED}错误: {e}{Colors.RESET}")
        return 1
    except Exception as e:
        print(f"{Colors.RED}配置加载失败: {e}{Colors.RESET}")
        return 1

    # 从配置读取日志级别 (命令行优先)
    log_level = args.log_level or config.get("system", {}).get("log_level", "INFO")
    setup_logging(level=log_level)

    # 运行工作流
    workflow = StockWorkflow(config, args)
    return workflow.run()


if __name__ == "__main__":
    sys.exit(main())
