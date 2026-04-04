# -*- coding: utf-8 -*-
"""AI-assisted rule backtest service."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.agent.llm_adapter import LLMToolAdapter
from src.config import get_config
from src.core.rule_backtest_engine import ParsedStrategy, RuleBacktestEngine, RuleBacktestParser
from src.repositories.rule_backtest_repo import RuleBacktestRepository
from src.repositories.stock_repo import StockRepository
from src.storage import DatabaseManager, RuleBacktestRun, RuleBacktestTrade

logger = logging.getLogger(__name__)


class RuleBacktestService:
    """Orchestrate parsing, deterministic execution, persistence and summary."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None, llm_adapter: Optional[LLMToolAdapter] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self.repo = RuleBacktestRepository(self.db)
        self.stock_repo = StockRepository(self.db)
        self.parser = RuleBacktestParser()
        self.engine = RuleBacktestEngine()
        self._llm_adapter = llm_adapter

    def parse_strategy(self, strategy_text: str) -> Dict[str, Any]:
        parsed = self.parser.parse(strategy_text, llm_adapter=self._get_llm_adapter())
        return self._parsed_to_dict(parsed)

    def run_backtest(
        self,
        *,
        code: str,
        strategy_text: str,
        parsed_strategy: Optional[Dict[str, Any]] = None,
        lookback_bars: int = 252,
        initial_capital: float = 100000.0,
        fee_bps: float = 0.0,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        normalized_code = str(code or "").strip()
        if not normalized_code:
            raise ValueError("code is required")
        raw_text = str(strategy_text or "").strip()
        if not raw_text:
            raise ValueError("strategy_text is required")

        parsed = self._ensure_parsed_strategy(raw_text, parsed_strategy)
        if parsed.needs_confirmation and not confirmed:
            raise ValueError("请先确认解析结果后再运行规则回测。")

        load_count = max(int(lookback_bars) + parsed.max_lookback + 20, int(lookback_bars) + 30)
        rows = self.stock_repo.get_latest(normalized_code, days=load_count)
        bars = list(reversed(rows))
        if len(bars) < max(10, parsed.max_lookback + 1):
            result = self._build_empty_result(
                code=normalized_code,
                parsed=parsed,
                initial_capital=initial_capital,
                lookback_bars=lookback_bars,
                no_result_reason="insufficient_history",
                no_result_message="历史行情不足，无法执行该策略回测。",
            )
            return self._persist_result(result, code=normalized_code, strategy_text=raw_text, lookback_bars=lookback_bars, initial_capital=initial_capital, fee_bps=fee_bps)

        result = self.engine.run(
            code=normalized_code,
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=initial_capital,
            fee_bps=fee_bps,
            lookback_bars=lookback_bars,
        )

        if not result.no_result_reason and result.metrics.get("trade_count", 0) <= 0:
            result.no_result_reason = "no_trades"
            result.no_result_message = "规则已解析并执行，但未产生任何交易。"

        ai_summary = self._build_ai_summary(parsed, result)
        return self._persist_result(
            result,
            code=normalized_code,
            strategy_text=raw_text,
            lookback_bars=lookback_bars,
            initial_capital=initial_capital,
            fee_bps=fee_bps,
            ai_summary=ai_summary,
        )

    def list_runs(self, *, code: Optional[str] = None, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        offset = max(page - 1, 0) * limit
        rows, total = self.repo.get_runs_paginated(code=code, offset=offset, limit=limit)
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "items": [self._run_row_to_dict(row, include_trades=False) for row in rows],
        }

    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        row = self.repo.get_run(run_id)
        if row is None:
            return None
        return self._run_row_to_dict(row, include_trades=True)

    def parse_and_run(
        self,
        *,
        code: str,
        strategy_text: str,
        lookback_bars: int = 252,
        initial_capital: float = 100000.0,
        fee_bps: float = 0.0,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        parsed = self.parse_strategy(strategy_text)
        return self.run_backtest(
            code=code,
            strategy_text=strategy_text,
            parsed_strategy=parsed,
            lookback_bars=lookback_bars,
            initial_capital=initial_capital,
            fee_bps=fee_bps,
            confirmed=confirmed,
        )

    def _ensure_parsed_strategy(self, raw_text: str, parsed_strategy: Optional[Dict[str, Any]]) -> ParsedStrategy:
        if parsed_strategy:
            return self._dict_to_parsed_strategy(parsed_strategy, raw_text)
        parsed_dict = self.parse_strategy(raw_text)
        return self._dict_to_parsed_strategy(parsed_dict, raw_text)

    def _build_empty_result(
        self,
        *,
        code: str,
        parsed: ParsedStrategy,
        initial_capital: float,
        lookback_bars: int,
        no_result_reason: str,
        no_result_message: str,
    ):
        metrics = {
            "initial_capital": float(initial_capital),
            "final_equity": float(initial_capital),
            "total_return_pct": 0.0,
            "trade_count": 0,
            "entry_signal_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate_pct": 0.0,
            "avg_trade_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "avg_holding_days": 0.0,
            "bars_used": 0,
            "lookback_bars": int(lookback_bars),
        }
        from src.core.rule_backtest_engine import RuleBacktestResult

        result = RuleBacktestResult(
            parsed_strategy=parsed,
            trades=[],
            equity_curve=[],
            metrics=metrics,
            no_result_reason=no_result_reason,
            no_result_message=no_result_message,
            warnings=parsed.ambiguities,
        )
        return result

    def _persist_result(
        self,
        result,
        *,
        code: str,
        strategy_text: str,
        lookback_bars: int,
        initial_capital: float,
        fee_bps: float,
        ai_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_at = datetime.now()
        strategy_hash = hashlib.sha256(strategy_text.encode("utf-8")).hexdigest()
        warnings = result.warnings or []
        summary = {
            "metrics": result.metrics,
            "parsed_strategy_summary": result.parsed_strategy.summary,
            "no_result_reason": result.no_result_reason,
            "no_result_message": result.no_result_message,
            "ai_summary": ai_summary,
        }
        run = RuleBacktestRun(
            code=code,
            strategy_text=strategy_text,
            parsed_strategy_json=json.dumps(result.parsed_strategy.to_dict(), ensure_ascii=False),
            strategy_hash=strategy_hash,
            timeframe=result.parsed_strategy.timeframe,
            lookback_bars=int(lookback_bars),
            initial_capital=float(initial_capital),
            fee_bps=float(fee_bps),
            parsed_confidence=result.parsed_strategy.confidence,
            needs_confirmation=bool(result.parsed_strategy.needs_confirmation),
            warnings_json=json.dumps(warnings, ensure_ascii=False),
            run_at=run_at,
            completed_at=run_at,
            status="warning" if result.no_result_reason else "completed",
            no_result_reason=result.no_result_reason,
            no_result_message=result.no_result_message,
            trade_count=result.metrics.get("trade_count", 0),
            win_count=result.metrics.get("win_count", 0),
            loss_count=result.metrics.get("loss_count", 0),
            total_return_pct=result.metrics.get("total_return_pct"),
            win_rate_pct=result.metrics.get("win_rate_pct"),
            avg_trade_return_pct=result.metrics.get("avg_trade_return_pct"),
            max_drawdown_pct=result.metrics.get("max_drawdown_pct"),
            avg_holding_days=result.metrics.get("avg_holding_days"),
            final_equity=result.metrics.get("final_equity"),
            summary_json=json.dumps(summary, ensure_ascii=False),
            ai_summary=ai_summary,
            equity_curve_json=json.dumps([p.to_dict() for p in result.equity_curve], ensure_ascii=False),
        )
        run = self.repo.save_run(run)

        trade_rows = [
            RuleBacktestTrade(
                run_id=run.id,
                trade_index=index,
                code=code,
                entry_date=trade.entry_date,
                exit_date=trade.exit_date,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                entry_signal=trade.entry_signal,
                exit_signal=trade.exit_signal,
                return_pct=trade.return_pct,
                holding_days=trade.holding_days,
                entry_rule_json=json.dumps(trade.entry_rule_json, ensure_ascii=False),
                exit_rule_json=json.dumps(trade.exit_rule_json, ensure_ascii=False),
                notes=trade.notes,
            )
            for index, trade in enumerate(result.trades)
        ]
        if trade_rows:
            self.repo.save_trades(trade_rows)

        return self._run_row_to_dict(
            run,
            include_trades=True,
            trades_override=[trade.to_dict() for trade in result.trades],
            equity_override=[point.to_dict() for point in result.equity_curve],
            parsed_override=result.parsed_strategy.to_dict(),
            ai_summary_override=ai_summary,
        )

    def _build_ai_summary(self, parsed: ParsedStrategy, result) -> str:
        prompt = self._build_summary_prompt(parsed, result.metrics, result.trades)
        adapter = self._get_llm_adapter()
        if adapter is not None:
            try:
                response = adapter.call_text(
                    [
                        {"role": "system", "content": "You summarize deterministic rule-based backtests. Do not invent trades or metrics."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=700,
                )
                content = (response.content or "").strip()
                if content:
                    return content
            except Exception as exc:
                logger.warning("AI summary generation failed: %s", exc)

        return self._fallback_summary(parsed, result.metrics, result.trades)

    def _build_summary_prompt(self, parsed: ParsedStrategy, metrics: Dict[str, Any], trades: List[Any]) -> str:
        sample_trades = [trade.to_dict() for trade in trades[:8]]
        payload = {
            "parsed_strategy": parsed.to_dict(),
            "metrics": metrics,
            "sample_trades": sample_trades,
        }
        return (
            "请基于下面的规则回测结果，用中文输出一段简洁总结。\n"
            "要求：\n"
            "1. 只基于给定数据，不要编造。\n"
            "2. 明确说明策略在做什么、表现如何、优势、弱点、下一步可改进方向。\n"
            "3. 语气务实，避免空话。\n"
            "4. 如果交易次数很少，必须点出统计不稳定。\n"
            f"数据:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _fallback_summary(self, parsed: ParsedStrategy, metrics: Dict[str, Any], trades: List[Any]) -> str:
        total_return = metrics.get("total_return_pct", 0.0) or 0.0
        win_rate = metrics.get("win_rate_pct", 0.0) or 0.0
        trade_count = metrics.get("trade_count", 0) or 0
        max_drawdown = metrics.get("max_drawdown_pct", 0.0) or 0.0
        avg_trade = metrics.get("avg_trade_return_pct", 0.0) or 0.0
        headline = (
            f"该策略以“{parsed.summary.get('entry', '--')}”作为入场，“{parsed.summary.get('exit', '--')}”作为离场。"
        )
        performance = (
            f"回测结果显示总收益 {total_return:.2f}%，共 {trade_count} 笔交易，胜率 {win_rate:.2f}%，"
            f"平均单笔收益 {avg_trade:.2f}%，最大回撤 {max_drawdown:.2f}%。"
        )
        if trade_count == 0:
            return f"{headline} 回测窗口内没有生成交易，当前结果更像是规则过滤效果而不是完整绩效样本。建议放宽条件或扩大样本区间。"

        strengths = "优势是规则足够明确，便于复现和复查。"
        weaknesses = "弱点通常在于单一信号可能过于严格，导致交易次数偏少或回撤控制不稳定。"
        if win_rate < 45:
            weaknesses = "弱点是胜率偏低，说明入场条件可能过严或离场条件反应过慢。"
        elif total_return < 0:
            weaknesses = "弱点是总体收益为负，规则组合在当前样本下没有形成稳定优势。"
        suggestions = "下一步可以先检查入场过滤是否过严，再观察是否需要放宽 RSI 阈值或调整均线周期。"
        return " ".join([headline, performance, strengths, weaknesses, suggestions])

    def _get_llm_adapter(self) -> Optional[LLMToolAdapter]:
        if self._llm_adapter is not None:
            return self._llm_adapter
        try:
            self._llm_adapter = LLMToolAdapter(get_config())
        except Exception as exc:
            logger.warning("Failed to initialize LLM adapter for rule backtest: %s", exc)
            self._llm_adapter = None
        return self._llm_adapter

    @staticmethod
    def _parsed_to_dict(parsed: ParsedStrategy) -> Dict[str, Any]:
        return parsed.to_dict()

    def _dict_to_parsed_strategy(self, parsed_dict: Dict[str, Any], raw_text: str) -> ParsedStrategy:
        entry = parsed_dict.get("entry") or {"type": "group", "op": "and", "rules": []}
        exit_rule = parsed_dict.get("exit") or {"type": "group", "op": "or", "rules": []}
        summary = parsed_dict.get("summary") or {}
        source_text = parsed_dict.get("source_text") or parsed_dict.get("sourceText") or raw_text
        normalized_text = parsed_dict.get("normalized_text") or parsed_dict.get("normalizedText") or raw_text
        confidence_value = parsed_dict.get("confidence")
        if confidence_value is None:
            confidence_value = parsed_dict.get("parsedConfidence")
        needs_confirmation_value = parsed_dict.get("needs_confirmation")
        if needs_confirmation_value is None:
            needs_confirmation_value = parsed_dict.get("needsConfirmation")
        max_lookback_value = parsed_dict.get("max_lookback")
        if max_lookback_value is None:
            max_lookback_value = parsed_dict.get("maxLookback")
        return ParsedStrategy(
            version=str(parsed_dict.get("version") or "v1"),
            timeframe=str(parsed_dict.get("timeframe") or "daily"),
            source_text=str(source_text),
            normalized_text=str(normalized_text),
            entry=entry,
            exit=exit_rule,
            confidence=float(confidence_value or 0.0),
            needs_confirmation=bool(needs_confirmation_value if needs_confirmation_value is not None else True),
            ambiguities=list(parsed_dict.get("ambiguities") or []),
            summary={
                "entry": str(summary.get("entry") or "买入条件：--"),
                "exit": str(summary.get("exit") or "卖出条件：--"),
            },
            max_lookback=int(max_lookback_value or 1),
        )

    def _run_row_to_dict(
        self,
        row: RuleBacktestRun,
        *,
        include_trades: bool,
        trades_override: Optional[List[Any]] = None,
        equity_override: Optional[List[Any]] = None,
        parsed_override: Optional[Dict[str, Any]] = None,
        ai_summary_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        if row.summary_json:
            try:
                summary = json.loads(row.summary_json)
            except Exception:
                summary = {}
        parsed_strategy = parsed_override
        if parsed_strategy is None and row.parsed_strategy_json:
            try:
                parsed_strategy = json.loads(row.parsed_strategy_json)
            except Exception:
                parsed_strategy = {}
        warnings = []
        if row.warnings_json:
            try:
                warnings = json.loads(row.warnings_json)
            except Exception:
                warnings = []
        trade_rows = trades_override or []
        equity_curve = equity_override or []
        if include_trades and not trade_rows:
            stored_trades = self.repo.get_trades_by_run(row.id)
            trade_rows = [self._trade_row_to_dict(trade) for trade in stored_trades]
        if include_trades and not equity_curve and row.equity_curve_json:
            try:
                equity_curve = json.loads(row.equity_curve_json)
            except Exception:
                equity_curve = []

        return {
            "id": row.id,
            "code": row.code,
            "strategy_text": row.strategy_text,
            "parsed_strategy": parsed_strategy or {},
            "strategy_hash": row.strategy_hash,
            "timeframe": row.timeframe,
            "lookback_bars": row.lookback_bars,
            "initial_capital": row.initial_capital,
            "fee_bps": row.fee_bps,
            "parsed_confidence": row.parsed_confidence,
            "needs_confirmation": row.needs_confirmation,
            "warnings": warnings,
            "run_at": row.run_at.isoformat() if row.run_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "status": row.status,
            "no_result_reason": row.no_result_reason,
            "no_result_message": row.no_result_message,
            "trade_count": row.trade_count,
            "win_count": row.win_count,
            "loss_count": row.loss_count,
            "total_return_pct": row.total_return_pct,
            "win_rate_pct": row.win_rate_pct,
            "avg_trade_return_pct": row.avg_trade_return_pct,
            "max_drawdown_pct": row.max_drawdown_pct,
            "avg_holding_days": row.avg_holding_days,
            "final_equity": row.final_equity,
            "summary": summary,
            "ai_summary": ai_summary_override if ai_summary_override is not None else row.ai_summary,
            "equity_curve": equity_curve,
            "trades": trade_rows,
        }

    def _trade_row_to_dict(self, trade: RuleBacktestTrade) -> Dict[str, Any]:
        entry_rule = {}
        exit_rule = {}
        if trade.entry_rule_json:
            try:
                entry_rule = json.loads(trade.entry_rule_json)
            except Exception:
                entry_rule = {}
        if trade.exit_rule_json:
            try:
                exit_rule = json.loads(trade.exit_rule_json)
            except Exception:
                exit_rule = {}
        return {
            "id": trade.id,
            "run_id": trade.run_id,
            "trade_index": trade.trade_index,
            "code": trade.code,
            "entry_date": trade.entry_date.isoformat() if trade.entry_date else None,
            "exit_date": trade.exit_date.isoformat() if trade.exit_date else None,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "entry_signal": trade.entry_signal,
            "exit_signal": trade.exit_signal,
            "return_pct": trade.return_pct,
            "holding_days": trade.holding_days,
            "entry_rule": entry_rule,
            "exit_rule": exit_rule,
            "notes": trade.notes,
        }
