# -*- coding: utf-8 -*-
"""AI-assisted deterministic rule backtest service."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from src.agent.llm_adapter import LLMToolAdapter
from src.config import get_config
from src.core.rule_backtest_engine import ParsedStrategy, RuleBacktestEngine, RuleBacktestParser
from src.repositories.rule_backtest_repo import RuleBacktestRepository
from src.repositories.stock_repo import StockRepository
from src.services.us_history_helper import fetch_daily_history_with_local_us_fallback
from src.storage import DatabaseManager, RuleBacktestRun, RuleBacktestTrade

logger = logging.getLogger(__name__)
_UNSET = object()
_CONFIRMATION_REQUIRED_ERROR = "请先确认解析结果后再运行规则回测。"


class RuleBacktestService:
    """Orchestrate parsing, deterministic execution, persistence, and async submissions."""

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
        slippage_bps: float = 0.0,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """Run a deterministic rule backtest synchronously and persist the completed result."""

        normalized_code, raw_text = self._validate_submission_inputs(code=code, strategy_text=strategy_text)
        parsed = self._ensure_parsed_strategy(raw_text, parsed_strategy)
        if parsed.needs_confirmation and not confirmed:
            raise ValueError(_CONFIRMATION_REQUIRED_ERROR)

        result = self._execute_rule_backtest(
            code=normalized_code,
            parsed=parsed,
            lookback_bars=lookback_bars,
            initial_capital=initial_capital,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )
        ai_summary = self._build_ai_summary(parsed, result)
        return self._store_result(
            result,
            code=normalized_code,
            strategy_text=raw_text,
            lookback_bars=lookback_bars,
            initial_capital=initial_capital,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            confirmed=confirmed,
            ai_summary=ai_summary,
        )

    def submit_backtest(
        self,
        *,
        code: str,
        strategy_text: str,
        parsed_strategy: Optional[Dict[str, Any]] = None,
        lookback_bars: int = 252,
        initial_capital: float = 100000.0,
        fee_bps: float = 0.0,
        slippage_bps: float = 0.0,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """Create a non-blocking rule backtest run and return immediately."""

        normalized_code, raw_text = self._validate_submission_inputs(code=code, strategy_text=strategy_text)
        parsed: Optional[ParsedStrategy] = None
        if parsed_strategy:
            parsed = self._dict_to_parsed_strategy(parsed_strategy, raw_text)
            if parsed.needs_confirmation and not confirmed:
                raise ValueError(_CONFIRMATION_REQUIRED_ERROR)

        submitted_at = datetime.now()
        initial_status = "queued" if parsed is not None else "parsing"
        initial_status_message = "策略已提交，等待开始执行。" if parsed is not None else "正在解析策略文本。"
        summary = self._update_summary_payload(
            {},
            request_payload=self._build_request_payload(
                lookback_bars=lookback_bars,
                initial_capital=initial_capital,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                confirmed=confirmed,
            ),
            execution_assumptions=self._build_execution_assumptions_payload(
                timeframe=(parsed.timeframe if parsed is not None else "daily"),
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
            ),
            parsed_strategy=parsed if parsed is not None else _UNSET,
            status=initial_status,
            status_message=initial_status_message,
            at=submitted_at,
        )

        run = RuleBacktestRun(
            code=normalized_code,
            strategy_text=raw_text,
            parsed_strategy_json=self._serialize_json(parsed.to_dict() if parsed is not None else {}),
            strategy_hash=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            timeframe=parsed.timeframe if parsed is not None else "daily",
            lookback_bars=int(lookback_bars),
            initial_capital=float(initial_capital),
            fee_bps=float(fee_bps),
            parsed_confidence=(parsed.confidence if parsed is not None else None),
            needs_confirmation=bool(parsed.needs_confirmation) if parsed is not None else False,
            warnings_json=self._serialize_json(parsed.ambiguities if parsed is not None else []),
            run_at=submitted_at,
            completed_at=None,
            status=initial_status,
            no_result_reason=None,
            no_result_message=None,
            trade_count=0,
            win_count=0,
            loss_count=0,
            total_return_pct=None,
            win_rate_pct=None,
            avg_trade_return_pct=None,
            max_drawdown_pct=None,
            avg_holding_days=None,
            final_equity=None,
            summary_json=self._serialize_json(summary),
            ai_summary=None,
            equity_curve_json=self._serialize_json([]),
        )
        run = self.repo.save_run(run)
        return self._run_row_to_dict(run, include_trades=False)

    def process_submitted_run(self, run_id: int) -> None:
        """Continue a submitted run in the background."""

        row = self.repo.get_run(run_id)
        if row is None:
            logger.warning("Rule backtest submission %s no longer exists.", run_id)
            return

        request_payload = self._extract_request_payload(row.summary_json)
        try:
            raw_text = str(row.strategy_text or "").strip()
            parsed_strategy = self._load_parsed_strategy(row.parsed_strategy_json, raw_text)
            if parsed_strategy is None:
                self._update_run_state(run_id, status="parsing", status_message="正在解析策略文本。")
                parsed_dict = self.parse_strategy(raw_text)
                parsed_strategy = self._dict_to_parsed_strategy(parsed_dict, raw_text)
                self._update_run_state(
                    run_id,
                    status="queued",
                    parsed_strategy=parsed_strategy,
                    status_message="策略解析完成，等待开始执行。",
                )

            if parsed_strategy.needs_confirmation and not request_payload["confirmed"]:
                self._mark_run_failed(
                    run_id,
                    no_result_reason="confirmation_required",
                    no_result_message="解析结果仍存在歧义，请先确认规则结构后再运行。",
                )
                return

            self._update_run_state(run_id, status="running", parsed_strategy=parsed_strategy, status_message="正在执行规则回测。")
            result = self._execute_rule_backtest(
                code=row.code,
                parsed=parsed_strategy,
                lookback_bars=request_payload["lookback_bars"],
                initial_capital=request_payload["initial_capital"],
                fee_bps=request_payload["fee_bps"],
                slippage_bps=request_payload["slippage_bps"],
            )

            self._update_run_state(
                run_id,
                status="summarizing",
                parsed_strategy=parsed_strategy,
                metrics=result.metrics,
                no_result_reason=result.no_result_reason,
                no_result_message=result.no_result_message,
                status_message="执行完成，正在整理摘要与交易审计。",
            )
            ai_summary = self._build_ai_summary(parsed_strategy, result)
            self._store_result(
                result,
                code=row.code,
                strategy_text=raw_text,
                lookback_bars=request_payload["lookback_bars"],
                initial_capital=request_payload["initial_capital"],
                fee_bps=request_payload["fee_bps"],
                slippage_bps=request_payload["slippage_bps"],
                confirmed=request_payload["confirmed"],
                ai_summary=ai_summary,
                existing_run_id=run_id,
            )
        except Exception as exc:
            logger.error("Rule backtest async execution failed for run %s: %s", run_id, exc, exc_info=True)
            self._mark_run_failed(
                run_id,
                no_result_reason="execution_failed",
                no_result_message=f"规则回测执行失败：{exc}",
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
        slippage_bps: float = 0.0,
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
            slippage_bps=slippage_bps,
            confirmed=confirmed,
        )

    def _validate_submission_inputs(self, *, code: str, strategy_text: str) -> tuple[str, str]:
        normalized_code = str(code or "").strip()
        if not normalized_code:
            raise ValueError("code is required")
        raw_text = str(strategy_text or "").strip()
        if not raw_text:
            raise ValueError("strategy_text is required")
        return normalized_code, raw_text

    def _execute_rule_backtest(
        self,
        *,
        code: str,
        parsed: ParsedStrategy,
        lookback_bars: int,
        initial_capital: float,
        fee_bps: float,
        slippage_bps: float,
    ):
        load_count = max(int(lookback_bars) + parsed.max_lookback + 20, int(lookback_bars) + 30)
        self._ensure_market_history(code=code, load_count=load_count)
        rows = self.stock_repo.get_latest(code, days=load_count)
        bars = list(reversed(rows))
        if len(bars) < max(10, parsed.max_lookback + 2):
            return self._build_empty_result(
                parsed=parsed,
                initial_capital=initial_capital,
                lookback_bars=lookback_bars,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                no_result_reason="insufficient_history",
                no_result_message="历史行情不足，无法执行该策略回测。",
            )

        result = self.engine.run(
            code=code,
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=initial_capital,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            lookback_bars=lookback_bars,
        )

        if not result.no_result_reason and result.metrics.get("trade_count", 0) <= 0:
            result.no_result_reason = "no_trades"
            result.no_result_message = "规则已解析并执行，但未产生任何交易。"
        return result

    def _ensure_market_history(self, *, code: str, load_count: int) -> int:
        recent_rows = self.stock_repo.get_latest(code, days=load_count)
        if len(recent_rows) >= load_count:
            latest_date = recent_rows[0].date if recent_rows else None
            if latest_date and latest_date >= datetime.now().date() - timedelta(days=3):
                return 0

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=max(load_count * 2, 180))
        try:
            df, source = self._load_history_with_local_us_fallback(
                code=code,
                start_date=start_date,
                end_date=end_date,
                days=load_count,
                log_context="[rule-backtest history]",
            )
            if df is None or df.empty:
                return 0
            return self.stock_repo.save_dataframe(df, code=code, data_source=source or "Unknown")
        except Exception as exc:
            logger.warning("Failed to ensure rule backtest history for %s: %s", code, exc)
            return 0

    def _load_history_with_local_us_fallback(
        self,
        *,
        code: str,
        start_date: date,
        end_date: date,
        days: int,
        log_context: str,
    ) -> tuple[Optional[Any], Optional[str]]:
        return fetch_daily_history_with_local_us_fallback(
            code,
            start_date=start_date,
            end_date=end_date,
            days=days,
            log_context=log_context,
        )

    def _ensure_parsed_strategy(self, raw_text: str, parsed_strategy: Optional[Dict[str, Any]]) -> ParsedStrategy:
        if parsed_strategy:
            return self._dict_to_parsed_strategy(parsed_strategy, raw_text)
        parsed_dict = self.parse_strategy(raw_text)
        return self._dict_to_parsed_strategy(parsed_dict, raw_text)

    def _load_parsed_strategy(self, parsed_strategy_json: Optional[str], raw_text: str) -> Optional[ParsedStrategy]:
        if not parsed_strategy_json:
            return None
        try:
            parsed_dict = json.loads(parsed_strategy_json)
        except Exception:
            return None
        if not isinstance(parsed_dict, dict) or not parsed_dict:
            return None
        return self._dict_to_parsed_strategy(parsed_dict, raw_text)

    def _build_empty_result(
        self,
        *,
        parsed: ParsedStrategy,
        initial_capital: float,
        lookback_bars: int,
        fee_bps: float,
        slippage_bps: float,
        no_result_reason: str,
        no_result_message: str,
    ):
        metrics = {
            "initial_capital": float(initial_capital),
            "final_equity": float(initial_capital),
            "total_return_pct": 0.0,
            "buy_and_hold_return_pct": 0.0,
            "excess_return_vs_buy_and_hold_pct": 0.0,
            "trade_count": 0,
            "entry_signal_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate_pct": 0.0,
            "avg_trade_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "avg_holding_days": 0.0,
            "avg_holding_bars": 0.0,
            "avg_holding_calendar_days": 0.0,
            "bars_used": 0,
            "lookback_bars": int(lookback_bars),
            "period_start": None,
            "period_end": None,
        }
        from src.core.rule_backtest_engine import RuleBacktestResult

        assumptions = self.engine._build_execution_assumptions(
            timeframe=parsed.timeframe,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )
        return RuleBacktestResult(
            parsed_strategy=parsed,
            execution_assumptions=assumptions,
            trades=[],
            equity_curve=[],
            metrics=metrics,
            no_result_reason=no_result_reason,
            no_result_message=no_result_message,
            warnings=parsed.ambiguities,
        )

    def _store_result(
        self,
        result,
        *,
        code: str,
        strategy_text: str,
        lookback_bars: int,
        initial_capital: float,
        fee_bps: float,
        slippage_bps: float,
        confirmed: bool,
        ai_summary: Optional[str] = None,
        existing_run_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        run_at = datetime.now()
        strategy_hash = hashlib.sha256(strategy_text.encode("utf-8")).hexdigest()
        warnings = result.warnings or []
        summary_patch = self._update_summary_payload(
            {},
            request_payload=self._build_request_payload(
                lookback_bars=lookback_bars,
                initial_capital=initial_capital,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                confirmed=confirmed,
            ),
            metrics=result.metrics,
            parsed_strategy=result.parsed_strategy,
            execution_assumptions=result.execution_assumptions.to_dict(),
            no_result_reason=result.no_result_reason,
            no_result_message=result.no_result_message,
            ai_summary=ai_summary,
            status="completed",
            status_message="规则回测已完成，可查看交易明细与执行假设。",
            at=run_at,
        )

        if existing_run_id is None:
            run = RuleBacktestRun(
                code=code,
                strategy_text=strategy_text,
                parsed_strategy_json=self._serialize_json(result.parsed_strategy.to_dict()),
                strategy_hash=strategy_hash,
                timeframe=result.parsed_strategy.timeframe,
                lookback_bars=int(lookback_bars),
                initial_capital=float(initial_capital),
                fee_bps=float(fee_bps),
                parsed_confidence=result.parsed_strategy.confidence,
                needs_confirmation=bool(result.parsed_strategy.needs_confirmation),
                warnings_json=self._serialize_json(warnings),
                run_at=run_at,
                completed_at=run_at,
                status="completed",
                no_result_reason=result.no_result_reason,
                no_result_message=result.no_result_message,
                trade_count=result.metrics.get("trade_count", 0),
                win_count=result.metrics.get("win_count", 0),
                loss_count=result.metrics.get("loss_count", 0),
                total_return_pct=result.metrics.get("total_return_pct"),
                win_rate_pct=result.metrics.get("win_rate_pct"),
                avg_trade_return_pct=result.metrics.get("avg_trade_return_pct"),
                max_drawdown_pct=result.metrics.get("max_drawdown_pct"),
                avg_holding_days=self._resolve_avg_holding_days(result.metrics),
                final_equity=result.metrics.get("final_equity"),
                summary_json=self._serialize_json(summary_patch),
                ai_summary=ai_summary,
                equity_curve_json=self._serialize_json([p.to_dict() for p in result.equity_curve]),
            )
            run = self.repo.save_run(run)
        else:
            existing = self.repo.get_run(existing_run_id)
            merged_summary = self._update_summary_payload(
                self._load_summary_payload(existing.summary_json if existing is not None else None),
                request_payload=summary_patch.get("request"),
                metrics=result.metrics,
                parsed_strategy=result.parsed_strategy,
                execution_assumptions=summary_patch.get("execution_assumptions"),
                no_result_reason=result.no_result_reason,
                no_result_message=result.no_result_message,
                ai_summary=ai_summary,
                status="completed",
                status_message="规则回测已完成，可查看交易明细与执行假设。",
                at=run_at,
            )
            run = self.repo.update_run(
                existing_run_id,
                parsed_strategy_json=self._serialize_json(result.parsed_strategy.to_dict()),
                strategy_hash=strategy_hash,
                timeframe=result.parsed_strategy.timeframe,
                lookback_bars=int(lookback_bars),
                initial_capital=float(initial_capital),
                fee_bps=float(fee_bps),
                parsed_confidence=result.parsed_strategy.confidence,
                needs_confirmation=bool(result.parsed_strategy.needs_confirmation),
                warnings_json=self._serialize_json(warnings),
                completed_at=run_at,
                status="completed",
                no_result_reason=result.no_result_reason,
                no_result_message=result.no_result_message,
                trade_count=result.metrics.get("trade_count", 0),
                win_count=result.metrics.get("win_count", 0),
                loss_count=result.metrics.get("loss_count", 0),
                total_return_pct=result.metrics.get("total_return_pct"),
                win_rate_pct=result.metrics.get("win_rate_pct"),
                avg_trade_return_pct=result.metrics.get("avg_trade_return_pct"),
                max_drawdown_pct=result.metrics.get("max_drawdown_pct"),
                avg_holding_days=self._resolve_avg_holding_days(result.metrics),
                final_equity=result.metrics.get("final_equity"),
                summary_json=self._serialize_json(merged_summary),
                ai_summary=ai_summary,
                equity_curve_json=self._serialize_json([p.to_dict() for p in result.equity_curve]),
            )
            if run is None:
                raise ValueError(f"Run {existing_run_id} not found.")
            self.repo.delete_trades_by_run_ids([run.id])

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
                holding_days=trade.holding_bars,
                entry_rule_json=self._serialize_json(
                    {
                        "rule": trade.entry_rule_json,
                        "signal_date": trade.entry_signal_date.isoformat(),
                        "trigger": trade.entry_trigger,
                        "indicators": trade.entry_indicators,
                        "signal_price_basis": trade.signal_price_basis,
                        "fill_basis": trade.entry_fill_basis,
                    }
                ),
                exit_rule_json=self._serialize_json(
                    {
                        "rule": trade.exit_rule_json,
                        "signal_date": trade.exit_signal_date.isoformat(),
                        "trigger": trade.exit_trigger,
                        "indicators": trade.exit_indicators,
                        "signal_price_basis": trade.signal_price_basis,
                        "fill_basis": trade.exit_fill_basis,
                    }
                ),
                notes=self._serialize_json(
                    {
                        "entry_fill_basis": trade.entry_fill_basis,
                        "exit_fill_basis": trade.exit_fill_basis,
                        "signal_price_basis": trade.signal_price_basis,
                        "price_basis": trade.price_basis,
                        "fee_bps": trade.fee_bps,
                        "slippage_bps": trade.slippage_bps,
                        "entry_fee_amount": trade.entry_fee_amount,
                        "exit_fee_amount": trade.exit_fee_amount,
                        "entry_slippage_amount": trade.entry_slippage_amount,
                        "exit_slippage_amount": trade.exit_slippage_amount,
                        "holding_bars": trade.holding_bars,
                        "holding_calendar_days": trade.holding_calendar_days,
                        "notes": trade.notes,
                    }
                ),
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
            summary_override=(summary_patch if existing_run_id is None else self._load_summary_payload(run.summary_json)),
        )

    def _update_run_state(
        self,
        run_id: int,
        *,
        status: str,
        status_message: Optional[str] = None,
        parsed_strategy: Optional[ParsedStrategy] = None,
        metrics: Optional[Dict[str, Any]] = None,
        no_result_reason: Optional[str] = None,
        no_result_message: Optional[str] = None,
    ) -> None:
        row = self.repo.get_run(run_id)
        if row is None:
            return
        summary = self._update_summary_payload(
            self._load_summary_payload(row.summary_json),
            parsed_strategy=parsed_strategy if parsed_strategy is not None else _UNSET,
            metrics=metrics if metrics is not None else _UNSET,
            no_result_reason=no_result_reason if no_result_reason is not None else _UNSET,
            no_result_message=no_result_message if no_result_message is not None else _UNSET,
            status=status,
            status_message=status_message,
        )
        self.repo.update_run(
            run_id,
            status=status,
            parsed_strategy_json=(
                self._serialize_json(parsed_strategy.to_dict())
                if parsed_strategy is not None
                else row.parsed_strategy_json
            ),
            timeframe=(parsed_strategy.timeframe if parsed_strategy is not None else row.timeframe),
            parsed_confidence=(parsed_strategy.confidence if parsed_strategy is not None else row.parsed_confidence),
            needs_confirmation=(
                bool(parsed_strategy.needs_confirmation)
                if parsed_strategy is not None
                else row.needs_confirmation
            ),
            warnings_json=(
                self._serialize_json(parsed_strategy.ambiguities)
                if parsed_strategy is not None
                else row.warnings_json
            ),
            no_result_reason=row.no_result_reason if no_result_reason is None else no_result_reason,
            no_result_message=row.no_result_message if no_result_message is None else no_result_message,
            summary_json=self._serialize_json(summary),
        )

    def _mark_run_failed(self, run_id: int, *, no_result_reason: str, no_result_message: str) -> None:
        row = self.repo.get_run(run_id)
        if row is None:
            return
        summary = self._update_summary_payload(
            self._load_summary_payload(row.summary_json),
            no_result_reason=no_result_reason,
            no_result_message=no_result_message,
            status="failed",
            status_message=no_result_message,
        )
        self.repo.update_run(
            run_id,
            status="failed",
            completed_at=datetime.now(),
            no_result_reason=no_result_reason,
            no_result_message=no_result_message,
            summary_json=self._serialize_json(summary),
        )

    @staticmethod
    def _load_summary_payload(summary_json: Optional[str]) -> Dict[str, Any]:
        if not summary_json:
            return {}
        try:
            parsed = json.loads(summary_json)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _serialize_json(payload: Any) -> str:
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _extract_request_payload(summary_json: Optional[str]) -> Dict[str, Any]:
        summary = RuleBacktestService._load_summary_payload(summary_json)
        request = summary.get("request") or {}
        return {
            "lookback_bars": int(request.get("lookback_bars") or 252),
            "initial_capital": float(request.get("initial_capital") or 100000.0),
            "fee_bps": float(request.get("fee_bps") or 0.0),
            "slippage_bps": float(request.get("slippage_bps") or 0.0),
            "confirmed": bool(request.get("confirmed", False)),
        }

    @staticmethod
    def _build_request_payload(
        *,
        lookback_bars: int,
        initial_capital: float,
        fee_bps: float,
        slippage_bps: float,
        confirmed: bool,
    ) -> Dict[str, Any]:
        return {
            "lookback_bars": int(lookback_bars),
            "initial_capital": float(initial_capital),
            "fee_bps": float(fee_bps),
            "slippage_bps": float(slippage_bps),
            "confirmed": bool(confirmed),
        }

    @staticmethod
    def _append_status_history(
        summary: Dict[str, Any],
        status: str,
        *,
        status_message: Optional[str] = None,
        at: Optional[datetime] = None,
    ) -> None:
        status_history = list(summary.get("status_history") or [])
        timestamp = at or datetime.now()
        status_history.append({"status": status, "at": timestamp.isoformat()})
        summary["status_history"] = status_history
        if status_message:
            summary["status_message"] = status_message

    def _build_execution_assumptions_payload(
        self,
        *,
        timeframe: str,
        fee_bps: float,
        slippage_bps: float,
    ) -> Dict[str, Any]:
        return self.engine._build_execution_assumptions(
            timeframe=timeframe,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        ).to_dict()

    def _update_summary_payload(
        self,
        summary: Dict[str, Any],
        *,
        request_payload: Any = _UNSET,
        parsed_strategy: Any = _UNSET,
        metrics: Any = _UNSET,
        execution_assumptions: Any = _UNSET,
        no_result_reason: Any = _UNSET,
        no_result_message: Any = _UNSET,
        ai_summary: Any = _UNSET,
        status: Optional[str] = None,
        status_message: Optional[str] = None,
        at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        payload = dict(summary or {})
        if request_payload is not _UNSET:
            payload["request"] = request_payload
        if parsed_strategy is not _UNSET:
            payload["parsed_strategy_summary"] = (
                parsed_strategy.summary if isinstance(parsed_strategy, ParsedStrategy) else parsed_strategy
            )
        if metrics is not _UNSET:
            payload["metrics"] = metrics
        if execution_assumptions is not _UNSET:
            payload["execution_assumptions"] = execution_assumptions
        if no_result_reason is not _UNSET:
            payload["no_result_reason"] = no_result_reason
        if no_result_message is not _UNSET:
            payload["no_result_message"] = no_result_message
        if ai_summary is not _UNSET:
            payload["ai_summary"] = ai_summary
        if status is not None:
            self._append_status_history(payload, status, status_message=status_message, at=at)
        return payload

    @staticmethod
    def _resolve_avg_holding_days(metrics: Dict[str, Any]) -> Optional[float]:
        value = metrics.get("avg_holding_days")
        if value is None:
            value = metrics.get("avg_holding_bars")
        return float(value) if value is not None else None

    def _build_ai_summary(self, parsed: ParsedStrategy, result) -> str:
        prompt = self._build_summary_prompt(parsed, result.execution_assumptions.to_dict(), result.metrics, result.trades)
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

    def _build_summary_prompt(
        self,
        parsed: ParsedStrategy,
        execution_assumptions: Dict[str, Any],
        metrics: Dict[str, Any],
        trades: List[Any],
    ) -> str:
        sample_trades = [trade.to_dict() for trade in trades[:8]]
        payload = {
            "parsed_strategy": parsed.to_dict(),
            "execution_assumptions": execution_assumptions,
            "metrics": metrics,
            "sample_trades": sample_trades,
        }
        return (
            "请基于下面的规则回测结果，用中文输出一段简洁总结。\n"
            "要求：\n"
            "1. 只基于给定数据，不要编造。\n"
            "2. 明确说明策略在做什么、表现如何、相对 buy-and-hold 是否有优势、主要假设是什么。\n"
            "3. 语气务实，避免空话。\n"
            "4. 如果交易次数很少，必须点出统计不稳定。\n"
            f"数据:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    def _fallback_summary(self, parsed: ParsedStrategy, metrics: Dict[str, Any], trades: List[Any]) -> str:
        total_return = metrics.get("total_return_pct", 0.0) or 0.0
        buy_hold = metrics.get("buy_and_hold_return_pct", 0.0) or 0.0
        excess = metrics.get("excess_return_vs_buy_and_hold_pct", 0.0) or 0.0
        win_rate = metrics.get("win_rate_pct", 0.0) or 0.0
        trade_count = metrics.get("trade_count", 0) or 0
        max_drawdown = metrics.get("max_drawdown_pct", 0.0) or 0.0
        avg_trade = metrics.get("avg_trade_return_pct", 0.0) or 0.0
        headline = (
            f"该策略以“{parsed.summary.get('entry', '--')}”作为入场，“{parsed.summary.get('exit', '--')}”作为离场。"
        )
        performance = (
            f"回测总收益 {total_return:.2f}%，同期 buy-and-hold 为 {buy_hold:.2f}%，超额收益 {excess:.2f}%。"
            f" 共 {trade_count} 笔交易，胜率 {win_rate:.2f}%，平均单笔收益 {avg_trade:.2f}%，最大回撤 {max_drawdown:.2f}%。"
        )
        if trade_count == 0:
            return f"{headline} 回测窗口内没有生成交易，当前结果更像是规则过滤效果而不是完整绩效样本。建议放宽条件或扩大样本区间。"

        strengths = "优势是规则明确、交易触发可复查，适合继续做参数敏感性分析。"
        weaknesses = "弱点通常在于条件过严时样本偏少，统计稳定性不足。"
        if win_rate < 45:
            weaknesses = "弱点是胜率偏低，说明入场条件可能过严或离场条件反应过慢。"
        elif total_return < buy_hold:
            weaknesses = "弱点是策略跑输同期 buy-and-hold，说明择时规则尚未带来稳定超额收益。"
        suggestions = "下一步建议结合交易明细检查哪些触发最常导致回撤，再决定是否放宽阈值或调整均线/RSI 周期。"
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
        summary_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        summary = summary_override if summary_override is not None else self._load_summary_payload(row.summary_json)
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

        request = summary.get("request") or {}
        execution_assumptions = summary.get("execution_assumptions") or {}
        metrics = summary.get("metrics") or {}
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
            "slippage_bps": float(request.get("slippage_bps") or 0.0),
            "parsed_confidence": row.parsed_confidence,
            "needs_confirmation": row.needs_confirmation,
            "warnings": warnings,
            "run_at": row.run_at.isoformat() if row.run_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "status": row.status,
            "status_message": summary.get("status_message"),
            "status_history": list(summary.get("status_history") or []),
            "no_result_reason": row.no_result_reason,
            "no_result_message": row.no_result_message,
            "trade_count": row.trade_count,
            "win_count": row.win_count,
            "loss_count": row.loss_count,
            "total_return_pct": row.total_return_pct,
            "buy_and_hold_return_pct": metrics.get("buy_and_hold_return_pct"),
            "excess_return_vs_buy_and_hold_pct": metrics.get("excess_return_vs_buy_and_hold_pct"),
            "win_rate_pct": row.win_rate_pct,
            "avg_trade_return_pct": row.avg_trade_return_pct,
            "max_drawdown_pct": row.max_drawdown_pct,
            "avg_holding_days": row.avg_holding_days,
            "avg_holding_bars": metrics.get("avg_holding_bars", row.avg_holding_days),
            "avg_holding_calendar_days": metrics.get("avg_holding_calendar_days"),
            "final_equity": row.final_equity,
            "summary": summary,
            "execution_assumptions": execution_assumptions,
            "ai_summary": ai_summary_override if ai_summary_override is not None else row.ai_summary,
            "equity_curve": equity_curve,
            "trades": trade_rows,
        }

    def _trade_row_to_dict(self, trade: RuleBacktestTrade) -> Dict[str, Any]:
        entry_payload = self._load_summary_payload(trade.entry_rule_json)
        exit_payload = self._load_summary_payload(trade.exit_rule_json)
        notes_payload = self._load_summary_payload(trade.notes)
        entry_rule = entry_payload.get("rule") or entry_payload
        exit_rule = exit_payload.get("rule") or exit_payload
        return {
            "id": trade.id,
            "run_id": trade.run_id,
            "trade_index": trade.trade_index,
            "code": trade.code,
            "entry_signal_date": entry_payload.get("signal_date"),
            "exit_signal_date": exit_payload.get("signal_date"),
            "entry_date": trade.entry_date.isoformat() if trade.entry_date else None,
            "exit_date": trade.exit_date.isoformat() if trade.exit_date else None,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "entry_signal": trade.entry_signal,
            "exit_signal": trade.exit_signal,
            "entry_trigger": entry_payload.get("trigger") or trade.entry_signal,
            "exit_trigger": exit_payload.get("trigger") or trade.exit_signal,
            "return_pct": trade.return_pct,
            "holding_days": trade.holding_days,
            "holding_bars": notes_payload.get("holding_bars", trade.holding_days),
            "holding_calendar_days": notes_payload.get("holding_calendar_days"),
            "entry_rule": entry_rule if isinstance(entry_rule, dict) else {},
            "exit_rule": exit_rule if isinstance(exit_rule, dict) else {},
            "entry_indicators": entry_payload.get("indicators") or {},
            "exit_indicators": exit_payload.get("indicators") or {},
            "entry_fill_basis": notes_payload.get("entry_fill_basis"),
            "exit_fill_basis": notes_payload.get("exit_fill_basis"),
            "signal_price_basis": notes_payload.get("signal_price_basis"),
            "price_basis": notes_payload.get("price_basis"),
            "fee_bps": notes_payload.get("fee_bps"),
            "slippage_bps": notes_payload.get("slippage_bps"),
            "entry_fee_amount": notes_payload.get("entry_fee_amount"),
            "exit_fee_amount": notes_payload.get("exit_fee_amount"),
            "entry_slippage_amount": notes_payload.get("entry_slippage_amount"),
            "exit_slippage_amount": notes_payload.get("exit_slippage_amount"),
            "notes": notes_payload.get("notes"),
        }
