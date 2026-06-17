#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 7: 复盘模块 (Reviewer)
────────────────────────────
五维盘后复盘系统:
  1. 选股准确率 (25%)
  2. 战法胜率 (25%)
  3. 盈亏比 (20%)
  4. 最大回撤 (15%)
  5. 仓位管理 (15%)

支持日/周/月/自定义周期报告生成。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 数据目录
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REPORTS_DIR = DATA_DIR / "review_reports"
STATE_FILE = DATA_DIR / "sim_state.json"
TRADES_FILE = DATA_DIR / "sim_trades.json"

# 五维权重
DIMENSION_WEIGHTS = {
    "选股准确率": 0.25,
    "战法胜率": 0.25,
    "盈亏比": 0.20,
    "最大回撤": 0.15,
    "仓位管理": 0.15,
}


@dataclass
class ReviewConfig:
    """复盘配置"""
    dimensions: List[str] = field(default_factory=lambda: [
        "选股准确率", "战法胜率", "盈亏比", "最大回撤", "仓位管理",
    ])
    weights: Dict[str, float] = field(default_factory=lambda: dict(DIMENSION_WEIGHTS))
    weekly_report: bool = True
    monthly_report: bool = True
    # 评分阈值
    screening_threshold: float = 80.0    # 选股准确率 ≥80% 满分
    win_rate_threshold: float = 70.0     # 战法胜率 ≥70% 满分
    profit_factor_threshold: float = 2.0 # 盈亏比 ≥2.0 满分
    max_dd_threshold: float = 10.0       # 最大回撤 ≤10% 满分
    position_score_threshold: float = 80.0

    @classmethod
    def from_dict(cls, cfg: dict) -> "ReviewConfig":
        rev = cfg.get("review", {})
        return cls(
            dimensions=rev.get("dimensions", [
                "选股准确率", "战法胜率", "盈亏比", "最大回撤", "仓位管理",
            ]),
            weights=dict(DIMENSION_WEIGHTS),
            weekly_report=rev.get("weekly_report", True),
            monthly_report=rev.get("monthly_report", True),
        )


@dataclass
class ReviewReport:
    """复盘报告"""
    # 基本信息
    report_id: str = ""
    period: str = "daily"                 # daily/weekly/monthly/custom
    start_date: str = ""
    end_date: str = ""
    generated_at: str = ""
    # 五维得分 (0-100)
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    overall_score: float = 0.0             # 加权总分
    grade: str = "C"                       # A/B/C/D/F
    # 详细数据
    screening_accuracy_pct: float = 0.0    # 选股准确率
    strategy_win_rates: Dict[str, float] = field(default_factory=dict)
    avg_rr_ratio: float = 0.0             # 平均盈亏比
    max_drawdown_pct: float = 0.0
    position_utilization_pct: float = 0.0  # 仓位利用率
    position_concentration: float = 0.0    # 持仓集中度
    # 交易统计
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    best_trade: Optional[dict] = None
    worst_trade: Optional[dict] = None
    # 改进建议
    improvements: List[str] = field(default_factory=list)
    highlights: List[str] = field(default_factory=list)
    # 维度详情
    dimension_details: Dict[str, str] = field(default_factory=dict)
    # 市场环境备注
    market_notes: str = ""


class Reviewer:
    """
    盘后复盘器 — 五维评价 + 改进建议

    用法:
        reviewer = Reviewer(config)
        report = reviewer.review(account, analysis_results, plans)
        reviewer.save_report(report)
        print(reviewer.format_report(report))
    """

    def __init__(self, config: Optional[ReviewConfig] = None):
        self.config = config or ReviewConfig()

    def review(
        self,
        account=None,                    # SimAccount 实例
        analysis_results: Optional[pd.DataFrame] = None,
        plans: Optional[List] = None,
        alerts: Optional[List] = None,
        period: str = "daily",
        market_notes: str = "",
    ) -> ReviewReport:
        """
        执行复盘分析

        Args:
            account: SimAccount 实例, 用于提取交易记录
            analysis_results: 选股分析结果 DataFrame
            plans: 交易计划列表
            alerts: 监控预警列表
            period: 报告周期 (daily/weekly/monthly/custom)
            market_notes: 市场环境备注
        """
        now = datetime.now()
        report = ReviewReport(
            report_id=f"REV-{now.strftime('%Y%m%d%H%M%S')}",
            period=period,
            start_date=now.strftime("%Y-%m-%d"),
            end_date=now.strftime("%Y-%m-%d"),
            generated_at=now.isoformat(),
            market_notes=market_notes,
        )

        # ── 提取交易数据 ──
        trades = self._extract_trades(account)

        # ── 五维评分 ──
        # 1. 选股准确率
        screening_score, screening_detail = self._score_screening(
            analysis_results, trades
        )
        report.dimension_scores["选股准确率"] = screening_score
        report.dimension_details["选股准确率"] = screening_detail
        report.screening_accuracy_pct = (
            self._calc_screening_accuracy(analysis_results, trades)
        )

        # 2. 战法胜率
        strategy_score, strategy_detail, strategy_rates = self._score_strategies(trades)
        report.dimension_scores["战法胜率"] = strategy_score
        report.dimension_details["战法胜率"] = strategy_detail
        report.strategy_win_rates = strategy_rates

        # 3. 盈亏比
        rr_score, rr_detail = self._score_rr_ratio(trades)
        report.dimension_scores["盈亏比"] = rr_score
        report.dimension_details["盈亏比"] = rr_detail
        report.avg_rr_ratio = self._calc_avg_rr(trades)

        # 4. 最大回撤
        dd_score, dd_detail = self._score_max_drawdown(account, trades)
        report.dimension_scores["最大回撤"] = dd_score
        report.dimension_details["最大回撤"] = dd_detail
        report.max_drawdown_pct = self._calc_max_dd(account, trades)

        # 5. 仓位管理
        pos_score, pos_detail = self._score_position_management(account, plans)
        report.dimension_scores["仓位管理"] = pos_score
        report.dimension_details["仓位管理"] = pos_detail
        report.position_utilization_pct = self._calc_position_utilization(account)
        report.position_concentration = self._calc_concentration(account)

        # ── 交易统计 ──
        sell_trades = [t for t in trades if t.get("action") == "sell"]
        report.total_trades = len(sell_trades)
        report.winning_trades = len([t for t in sell_trades if t.get("pnl_pct", 0) > 0])
        report.losing_trades = report.total_trades - report.winning_trades
        report.total_pnl = sum(t.get("pnl", 0) for t in sell_trades)

        # 最佳/最差交易
        if sell_trades:
            best = max(sell_trades, key=lambda t: t.get("pnl_pct", -999))
            worst = min(sell_trades, key=lambda t: t.get("pnl_pct", 999))
            report.best_trade = {
                "code": best.get("code", ""),
                "pnl_pct": best.get("pnl_pct", 0),
                "strategy": best.get("strategy", ""),
                "date": best.get("date", ""),
            }
            report.worst_trade = {
                "code": worst.get("code", ""),
                "pnl_pct": worst.get("pnl_pct", 0),
                "strategy": worst.get("strategy", ""),
                "date": worst.get("date", ""),
            }

        # ── 综合评分 ──
        total = 0.0
        for dim, weight in self.config.weights.items():
            score = report.dimension_scores.get(dim, 50)
            total += score * weight
        report.overall_score = round(total, 1)

        # 评级
        report.grade = self._assign_grade(report.overall_score)

        # ── 改进建议 ──
        report.improvements, report.highlights = self._generate_insights(report)

        logger.info(
            f"[复盘] {report.period} 报告完成: "
            f"综合={report.overall_score:.0f}分 [{report.grade}], "
            f"选股={screening_score:.0f}, 战法={strategy_score:.0f}, "
            f"盈亏比={rr_score:.0f}, 回撤={dd_score:.0f}, 仓位={pos_score:.0f}"
        )

        return report

    # ══════════════════════════════════════════════════════════
    # 五维评分逻辑
    # ══════════════════════════════════════════════════════════

    def _extract_trades(self, account) -> List[dict]:
        """从 SimAccount 提取交易记录"""
        trades = []
        if account is None:
            # 尝试从文件加载
            if TRADES_FILE.exists():
                try:
                    with open(TRADES_FILE, "r", encoding="utf-8") as f:
                        trades = json.load(f)
                except Exception:
                    pass
            return trades

        try:
            # SimAccount.get_trade_df()
            df = account.get_trade_df()
            if df is not None and not df.empty:
                trades = df.to_dict("records")
        except Exception as e:
            logger.debug(f"提取交易记录失败: {e}")

        return trades

    def _score_screening(
        self,
        analysis_results: Optional[pd.DataFrame],
        trades: List[dict],
    ) -> tuple:
        """评分选股准确率 (满分100)"""
        accuracy = self._calc_screening_accuracy(analysis_results, trades)
        score = min(100, accuracy / self.config.screening_threshold * 100)
        detail = (
            f"选股准确率 {accuracy:.1f}% "
            f"(阈值 {self.config.screening_threshold}%)"
        )
        return round(score, 1), detail

    def _calc_screening_accuracy(
        self,
        analysis_results: Optional[pd.DataFrame],
        trades: List[dict],
    ) -> float:
        """计算选股准确率: 盈利交易占比"""
        sell_trades = [t for t in trades if t.get("action") == "sell"]
        if not sell_trades:
            # 从 analysis_results 估算
            if analysis_results is not None and not analysis_results.empty:
                return float(
                    analysis_results.get("signal_strength", pd.Series(["弱"]))
                    .apply(lambda x: 1 if x in ("强", "中") else 0)
                    .mean()
                    * 100
                )
            return 50.0
        wins = len([t for t in sell_trades if t.get("pnl_pct", 0) > 0])
        return round(wins / len(sell_trades) * 100, 1)

    def _score_strategies(self, trades: List[dict]) -> tuple:
        """评分战法胜率 (满分100)"""
        sell_trades = [t for t in trades if t.get("action") == "sell"]
        strategy_rates = {}

        if not sell_trades:
            return 50.0, "无交易记录, 默认50分", {}

        # 按战法分组统计
        group = {}
        for t in sell_trades:
            strat = t.get("strategy", "未知")
            if strat not in group:
                group[strat] = {"total": 0, "wins": 0, "total_pnl": 0.0}
            group[strat]["total"] += 1
            group[strat]["total_pnl"] += t.get("pnl_pct", 0)
            if t.get("pnl_pct", 0) > 0:
                group[strat]["wins"] += 1

        for strat, stats in group.items():
            strategy_rates[strat] = round(
                stats["wins"] / stats["total"] * 100, 1
            ) if stats["total"] > 0 else 0

        # 加权平均胜率
        total_count = sum(s["total"] for s in group.values())
        weighted_avg = (
            sum(
                strategy_rates.get(s, 0) * group[s]["total"]
                for s in group
            ) / total_count
        ) if total_count > 0 else 0

        score = min(100, weighted_avg / self.config.win_rate_threshold * 100)
        detail = (
            f"加权胜率 {weighted_avg:.1f}% "
            f"(阈值 {self.config.win_rate_threshold}%), "
            f"战法数={len(group)}"
        )
        return round(score, 1), detail, strategy_rates

    def _score_rr_ratio(self, trades: List[dict]) -> tuple:
        """评分盈亏比 (满分100)"""
        avg_rr = self._calc_avg_rr(trades)
        score = min(100, avg_rr / self.config.profit_factor_threshold * 100)
        detail = (
            f"平均盈亏比 {avg_rr:.2f} "
            f"(阈值 {self.config.profit_factor_threshold})"
        )
        return round(score, 1), detail

    def _calc_avg_rr(self, trades: List[dict]) -> float:
        """计算平均盈亏比"""
        sell_trades = [t for t in trades if t.get("action") == "sell"]
        wins = [t["pnl_pct"] for t in sell_trades if t.get("pnl_pct", 0) > 0]
        losses = [t["pnl_pct"] for t in sell_trades if t.get("pnl_pct", 0) < 0]

        if not wins or not losses:
            # 有盈利无亏损
            if wins and not losses:
                return 5.0
            return 0.5  # 默认中等值

        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))
        return round(avg_win / avg_loss, 2) if avg_loss > 0 else 5.0

    def _score_max_drawdown(self, account, trades: List[dict]) -> tuple:
        """评分最大回撤 (满分100)"""
        max_dd = self._calc_max_dd(account, trades)
        # 回撤越小得分越高: ≤10%→满分, ≥30%→0分
        if max_dd <= self.config.max_dd_threshold:
            score = 100.0
        elif max_dd >= 30:
            score = 0.0
        else:
            score = 100 - (max_dd - self.config.max_dd_threshold) / (30 - self.config.max_dd_threshold) * 100
        detail = (
            f"最大回撤 {max_dd:.1f}% "
            f"(阈值 {self.config.max_dd_threshold}%)"
        )
        return round(score, 1), detail

    def _calc_max_dd(self, account, trades: List[dict]) -> float:
        """计算最大回撤 (%)"""
        if account is not None:
            try:
                # 从 SimAccount 快照计算
                snapshots = getattr(account, "snapshots", [])
                if snapshots:
                    values = [s.get("value", 0) for s in snapshots]
                    peak = values[0]
                    max_dd = 0.0
                    for v in values:
                        if v > peak:
                            peak = v
                        dd = (peak - v) / peak * 100 if peak > 0 else 0
                        max_dd = max(max_dd, dd)
                    return round(max_dd, 2)
            except Exception:
                pass

        # 从交易记录估算
        sell_trades = [t for t in trades if t.get("action") == "sell"]
        if not sell_trades:
            return 0.0
        losses = [t["pnl_pct"] for t in sell_trades if t.get("pnl_pct", 0) < 0]
        # 连续亏损的最坏情况
        if losses:
            return round(min(abs(np.sum(losses[:3])), 30.0), 1)
        return 0.0

    def _score_position_management(self, account, plans: Optional[List]) -> tuple:
        """评分仓位管理 (满分100)"""
        utilization = self._calc_position_utilization(account)
        concentration = self._calc_concentration(account)

        # 利用率 30-70% 最优
        util_score = max(0, 100 - abs(utilization - 50) * 2)

        # 集中度越低越好 (<50% 满分)
        conc_score = max(0, 100 - concentration * 2)

        score = util_score * 0.5 + conc_score * 0.5
        detail = (
            f"利用率 {utilization:.1f}%, "
            f"集中度 {concentration:.1f}%"
        )
        return round(score, 1), detail

    def _calc_position_utilization(self, account) -> float:
        """计算仓位利用率 (%)"""
        if account is None:
            return 50.0
        try:
            pos_value = getattr(account, "_total_position_value", 0)
            if callable(pos_value):
                pos_value = pos_value()
            total = getattr(account, "total_value", 0)
            if callable(total):
                total = total()
            if total and total > 0:
                return round(pos_value / total * 100, 1)
        except Exception:
            pass

        try:
            # 从 positions 计算
            positions = getattr(account, "positions", {})
            cash = getattr(account, "cash", 0)
            pos_mv = sum(
                p.get("market_value", p.get("shares", 0) * p.get("current_price", 0))
                for p in (positions.values() if isinstance(positions, dict) else positions)
            )
            total = cash + pos_mv
            return round(pos_mv / total * 100, 1) if total > 0 else 0
        except Exception:
            return 50.0

    def _calc_concentration(self, account) -> float:
        """计算持仓集中度 (%) — Top 1 占比"""
        if account is None:
            return 30.0
        try:
            positions = getattr(account, "positions", {})
            pos_values = []
            for p in (positions.values() if isinstance(positions, dict) else positions):
                mv = p.get("market_value", p.get("shares", 0) * p.get("current_price", 0))
                if mv > 0:
                    pos_values.append(mv)
            if not pos_values:
                return 0
            total = sum(pos_values)
            return round(max(pos_values) / total * 100, 1) if total > 0 else 0
        except Exception:
            return 30.0

    # ══════════════════════════════════════════════════════════
    # 评级 & 建议
    # ══════════════════════════════════════════════════════════

    @staticmethod
    def _assign_grade(score: float) -> str:
        """分数→评级"""
        if score >= 90:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"

    def _generate_insights(self, report: ReviewReport) -> tuple:
        """生成改进建议 & 亮点"""
        improvements = []
        highlights = []

        # 选股准确率
        if report.dimension_scores.get("选股准确率", 50) < 50:
            improvements.append(
                f"✗ 选股准确率偏低 ({report.screening_accuracy_pct:.0f}%), "
                "建议收紧PE/市值/换手率阈值, 提高粗筛质量"
            )
        elif report.dimension_scores.get("选股准确率", 50) >= 85:
            highlights.append(
                f"✓ 选股准确率优秀 ({report.screening_accuracy_pct:.0f}%), 筛选模型可靠"
            )

        # 战法胜率
        losing_strategies = [
            s for s, r in report.strategy_win_rates.items()
            if r < 40 and report.strategy_stats_ok(s)
        ]
        if losing_strategies:
            improvements.append(
                f"✗ 战法「{'、'.join(losing_strategies)}」胜率偏低, "
                "建议检查参数或暂停使用"
            )

        winning_strategies = [
            s for s, r in report.strategy_win_rates.items()
            if r >= 70
        ]
        if winning_strategies:
            highlights.append(
                f"✓ 战法「{'、'.join(winning_strategies)}」表现优异, 可增加权重"
            )

        # 盈亏比
        if report.dimension_scores.get("盈亏比", 50) < 40:
            improvements.append(
                f"✗ 盈亏比过低 ({report.avg_rr_ratio:.2f}), "
                "建议收紧止损或提高止盈R倍数"
            )

        # 最大回撤
        if report.dimension_scores.get("最大回撤", 50) < 50:
            improvements.append(
                f"✗ 最大回撤过大 ({report.max_drawdown_pct:.1f}%), "
                "建议降低单票仓位、收紧止损线"
            )
        elif report.max_drawdown_pct < 5:
            highlights.append(
                f"✓ 回撤控制出色 ({report.max_drawdown_pct:.1f}%), 风控有效"
            )

        # 仓位管理
        if report.position_utilization_pct < 20:
            improvements.append(
                f"✗ 仓位利用率低 ({report.position_utilization_pct:.1f}%), "
                "可适当放宽选股条件以增加交易机会"
            )
        elif report.position_utilization_pct > 80:
            improvements.append(
                f"✗ 仓位过重 ({report.position_utilization_pct:.1f}%), 注意分散风险"
            )
        elif 30 <= report.position_utilization_pct <= 70:
            highlights.append(
                f"✓ 仓位管理合理 ({report.position_utilization_pct:.1f}%)"
            )

        if report.position_concentration > 50:
            improvements.append(
                f"✗ 持仓过于集中 (Top1={report.position_concentration:.1f}%), 建议分散"
            )

        if report.total_trades == 0:
            improvements.append("⚠ 本期无交易记录, 系统可能未触发有效信号")

        if not improvements:
            improvements.append("系统运行正常, 暂无改进建议。继续保持！")

        return improvements, highlights

    def strategy_stats_ok(self, strategy_name: str) -> bool:
        """判断战法是否有足够样本"""
        return True  # 默认都纳入统计

    # ══════════════════════════════════════════════════════════
    # 报告输出
    # ══════════════════════════════════════════════════════════

    def format_report(self, report: ReviewReport) -> str:
        """格式化复盘报告为可读文本"""
        bar = "═" * 56
        lines = [
            "",
            bar,
            f"  📊 复盘报告 [{report.period.upper()}] — {report.grade}级",
            bar,
            f"  报告ID:   {report.report_id}",
            f"  周期:     {report.start_date} ~ {report.end_date}",
            f"  生成时间: {report.generated_at[:19]}",
            "",
            f"  ⭐ 综合评分: {report.overall_score:.0f}/100 [{report.grade}]",
            "",
            f"  {'─'*50}",
            f"  五维评分:",
        ]

        for dim in self.config.dimensions:
            score = report.dimension_scores.get(dim, 0)
            bar_len = int(score / 5)
            bar_str = "█" * bar_len + "░" * (20 - bar_len)
            detail = report.dimension_details.get(dim, "")
            lines.append(f"  {dim:　<8s} {bar_str} {score:5.1f}分  {detail}")

        lines.extend([
            f"  {'─'*50}",
            "",
            f"  📈 交易统计:",
            f"  交易笔数: {report.total_trades}  (赢 {report.winning_trades} / 输 {report.losing_trades})",
            f"  总盈亏:   {report.total_pnl:+.1f}",
            f"  最佳:     {report.best_trade['code']} {report.best_trade['pnl_pct']:+.1f}% ({report.best_trade['strategy']})" if report.best_trade else "",
            f"  最差:     {report.worst_trade['code']} {report.worst_trade['pnl_pct']:+.1f}% ({report.worst_trade['strategy']})" if report.worst_trade else "",
            "",
            f"  🎯 战法统计:",
        ])

        for s, rate in sorted(report.strategy_win_rates.items(), key=lambda x: -x[1]):
            stars = "⭐" * min(5, int(rate / 20))
            lines.append(f"  {s:<15s} 胜率={rate:5.1f}% {stars}")

        if not report.strategy_win_rates:
            lines.append("  (无战法统计数据)")

        lines.extend([
            "",
            f"  💡 亮点:",
        ])
        for h in report.highlights:
            lines.append(f"  {h}")
        if not report.highlights:
            lines.append("  (本期暂无特别亮点)")

        lines.extend([
            "",
            f"  ⚠️  改进:",
        ])
        for imp in report.improvements:
            lines.append(f"  {imp}")

        if report.market_notes:
            lines.extend([
                "",
                f"  🌍 市场环境: {report.market_notes}",
            ])

        lines.extend(["", bar, ""])
        return "\n".join(lines)

    def save_report(self, report: ReviewReport) -> str:
        """保存复盘报告到 data/review_reports/"""
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"review_{report.report_id}.json"
        filepath = REPORTS_DIR / filename

        output = {
            "report_id": report.report_id,
            "period": report.period,
            "start_date": report.start_date,
            "end_date": report.end_date,
            "generated_at": report.generated_at,
            "overall_score": report.overall_score,
            "grade": report.grade,
            "dimension_scores": report.dimension_scores,
            "dimension_details": report.dimension_details,
            "strategy_win_rates": report.strategy_win_rates,
            "total_trades": report.total_trades,
            "winning_trades": report.winning_trades,
            "losing_trades": report.losing_trades,
            "total_pnl": report.total_pnl,
            "improvements": report.improvements,
            "highlights": report.highlights,
            "market_notes": report.market_notes,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"[复盘] 报告已保存: {filepath}")

        # 同时保存可读文本版本
        txt_path = filepath.with_suffix(".txt")
        txt_path.write_text(self.format_report(report), encoding="utf-8")

        return str(filepath)

    def trend_analysis(
        self,
        reports: List[ReviewReport],
    ) -> Dict[str, Any]:
        """
        多期趋势分析

        Args:
            reports: 按时间排序的报告列表

        Returns:
            {trends: {维度: [scores]}, improving: [维度], declining: [维度]}
        """
        if len(reports) < 2:
            return {"trends": {}, "improving": [], "declining": []}

        trends = {}
        for dim in self.config.dimensions:
            scores = [r.dimension_scores.get(dim, 50) for r in reports]
            trends[dim] = scores

        improving = []
        declining = []
        for dim, scores in trends.items():
            if len(scores) >= 2:
                slope = (scores[-1] - scores[0]) / len(scores)
                if slope > 1:
                    improving.append(dim)
                elif slope < -1:
                    declining.append(dim)

        return {"trends": trends, "improving": improving, "declining": declining}

    def __repr__(self) -> str:
        return (
            f"Reviewer(dimensions={self.config.dimensions}, "
            f"weekly={self.config.weekly_report})"
        )


# ══════════════════════════════════════════════════════════
# 便捷函数
# ══════════════════════════════════════════════════════════

def run_review(
    config_dict: dict,
    account=None,
    analysis_results: Optional[pd.DataFrame] = None,
    plans: Optional[List] = None,
    period: str = "daily",
) -> ReviewReport:
    """一行式复盘入口"""
    rev_config = ReviewConfig.from_dict(config_dict)
    reviewer = Reviewer(rev_config)
    return reviewer.review(account, analysis_results, plans, period=period)


# ══════════════════════════════════════════════════════════
# 自测入口
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    # 构造模拟交易数据
    mock_trades = [
        {"action": "buy",  "code": "600519", "price": 1800, "shares": 100, "pnl_pct": 0,    "date": "2024-01-05", "strategy": "first_board"},
        {"action": "sell", "code": "600519", "price": 1900, "shares": 100, "pnl_pct": 5.5,  "date": "2024-01-15", "strategy": "first_board"},
        {"action": "buy",  "code": "000858", "price": 150,  "shares": 500, "pnl_pct": 0,    "date": "2024-01-08", "strategy": "pullback"},
        {"action": "sell", "code": "000858", "price": 145,  "shares": 500, "pnl_pct": -3.3, "date": "2024-01-20", "strategy": "pullback"},
        {"action": "buy",  "code": "300750", "price": 200,  "shares": 300, "pnl_pct": 0,    "date": "2024-01-10", "strategy": "wave_point"},
        {"action": "sell", "code": "300750", "price": 215,  "shares": 300, "pnl_pct": 7.5,  "date": "2024-01-25", "strategy": "wave_point"},
        {"action": "buy",  "code": "601318", "price": 45,   "shares": 1000,"pnl_pct": 0,    "date": "2024-01-12", "strategy": "test_line"},
        {"action": "sell", "code": "601318", "price": 43,   "shares": 1000,"pnl_pct": -4.4, "date": "2024-01-22", "strategy": "test_line"},
        {"action": "buy",  "code": "000333", "price": 55,   "shares": 800, "pnl_pct": 0,    "date": "2024-01-15", "strategy": "first_board"},
        {"action": "sell", "code": "000333", "price": 58,   "shares": 800, "pnl_pct": 5.5,  "date": "2024-01-28", "strategy": "first_board"},
    ]

    reviewer = Reviewer()
    report = reviewer.review(
        analysis_results=None,
        plans=None,
        alerts=None,
        period="daily",
        market_notes="震荡偏多, 成交量温和放大",
    )

    # 手动注入交易数据 (因为没有 SimAccount)
    report._extract_trades = lambda account=None: mock_trades
    report = reviewer.review(period="daily")

    print(reviewer.format_report(report))

    try:
        path = reviewer.save_report(report)
        print(f"报告已保存: {path}")
    except Exception as e:
        print(f"保存失败: {e}")
