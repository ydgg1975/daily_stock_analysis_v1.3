# -*- coding: utf-8 -*-
"""Historical analysis evaluation orchestration service."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select

from src.config import get_config
from src.core.backtest_engine import OVERALL_SENTINEL_CODE, BacktestEngine, EvaluationConfig
from src.repositories.backtest_repo import BacktestRepository
from src.repositories.stock_repo import StockRepository
from src.services.us_history_helper import fetch_daily_history_with_local_us_fallback
from src.storage import AnalysisHistory, BacktestResult, BacktestRun, BacktestSummary, DatabaseManager, StockDaily

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BacktestRuntimeSettings:
    """Normalized backtest config shared by evaluation and sample-prep flows."""

    eval_window_days: int
    min_age_days: int
    engine_version: str
    neutral_band_pct: float


class BacktestService:
    """Service layer for historical analysis evaluation and sample preparation."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self.repo = BacktestRepository(self.db)
        self.stock_repo = StockRepository(self.db)

    def run_backtest(
        self,
        *,
        code: Optional[str] = None,
        force: bool = False,
        eval_window_days: Optional[int] = None,
        min_age_days: Optional[int] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """Evaluate historical analysis snapshots against later market bars."""
        config = get_config()
        settings = self._resolve_runtime_settings(
            config,
            eval_window_days=eval_window_days,
            min_age_days=min_age_days,
        )
        cutoff_dt = datetime.now() - timedelta(days=settings.min_age_days)
        run_at = datetime.now()

        eval_config = EvaluationConfig(
            eval_window_days=settings.eval_window_days,
            neutral_band_pct=settings.neutral_band_pct,
            engine_version=settings.engine_version,
        )

        total_history_count = self.repo.count_analysis_history(code=code)
        age_eligible_count = self.repo.count_analysis_history(code=code, created_before=cutoff_dt)

        candidates = self.repo.get_candidates(
            code=code,
            min_age_days=settings.min_age_days,
            limit=int(limit),
            eval_window_days=settings.eval_window_days,
            engine_version=settings.engine_version,
            force=force,
        )

        processed = 0
        completed = 0
        insufficient = 0
        errors = 0
        touched_codes: set[str] = set()

        results_to_save: List[BacktestResult] = []

        for analysis in candidates:
            processed += 1
            touched_codes.add(analysis.code)

            try:
                analysis_date = self._resolve_analysis_date(analysis)
                if analysis_date is None:
                    errors += 1
                    results_to_save.append(
                        BacktestResult(
                            analysis_history_id=analysis.id,
                            code=analysis.code,
                            eval_window_days=settings.eval_window_days,
                            engine_version=settings.engine_version,
                            eval_status="error",
                            evaluated_at=run_at,
                            operation_advice=analysis.operation_advice,
                        )
                    )
                    continue
                start_daily = self.stock_repo.get_start_daily(code=analysis.code, analysis_date=analysis_date)

                if start_daily is None or start_daily.close is None:
                    self._try_fill_daily_data(
                        code=analysis.code,
                        analysis_date=analysis_date,
                        eval_window_days=settings.eval_window_days,
                    )
                    start_daily = self.stock_repo.get_start_daily(code=analysis.code, analysis_date=analysis_date)

                if start_daily is None or start_daily.close is None:
                    insufficient += 1
                    results_to_save.append(
                        BacktestResult(
                            analysis_history_id=analysis.id,
                            code=analysis.code,
                            analysis_date=analysis_date,
                            eval_window_days=settings.eval_window_days,
                            engine_version=settings.engine_version,
                            eval_status="insufficient_data",
                            evaluated_at=run_at,
                            operation_advice=analysis.operation_advice,
                        )
                    )
                    continue

                forward_bars = self.stock_repo.get_forward_bars(
                    code=analysis.code,
                    analysis_date=start_daily.date,
                    eval_window_days=settings.eval_window_days,
                )

                if len(forward_bars) < settings.eval_window_days:
                    self._try_fill_daily_data(
                        code=analysis.code,
                        analysis_date=start_daily.date,
                        eval_window_days=settings.eval_window_days,
                    )
                    forward_bars = self.stock_repo.get_forward_bars(
                        code=analysis.code,
                        analysis_date=start_daily.date,
                        eval_window_days=settings.eval_window_days,
                    )

                evaluation = BacktestEngine.evaluate_single(
                    operation_advice=analysis.operation_advice,
                    analysis_date=start_daily.date,
                    start_price=float(start_daily.close),
                    forward_bars=forward_bars,
                    stop_loss=analysis.stop_loss,
                    take_profit=analysis.take_profit,
                    config=eval_config,
                )

                status = evaluation.get("eval_status")
                if status == "insufficient_data":
                    insufficient += 1
                elif status == "completed":
                    completed += 1
                else:
                    errors += 1

                results_to_save.append(
                    BacktestResult(
                        analysis_history_id=analysis.id,
                        code=analysis.code,
                        analysis_date=evaluation.get("analysis_date"),
                        eval_window_days=int(evaluation.get("eval_window_days") or settings.eval_window_days),
                        engine_version=str(evaluation.get("engine_version") or settings.engine_version),
                        eval_status=str(evaluation.get("eval_status") or "error"),
                        evaluated_at=run_at,
                        operation_advice=evaluation.get("operation_advice"),
                        position_recommendation=evaluation.get("position_recommendation"),
                        start_price=evaluation.get("start_price"),
                        end_close=evaluation.get("end_close"),
                        max_high=evaluation.get("max_high"),
                        min_low=evaluation.get("min_low"),
                        stock_return_pct=evaluation.get("stock_return_pct"),
                        direction_expected=evaluation.get("direction_expected"),
                        direction_correct=evaluation.get("direction_correct"),
                        outcome=evaluation.get("outcome"),
                        stop_loss=evaluation.get("stop_loss"),
                        take_profit=evaluation.get("take_profit"),
                        hit_stop_loss=evaluation.get("hit_stop_loss"),
                        hit_take_profit=evaluation.get("hit_take_profit"),
                        first_hit=evaluation.get("first_hit"),
                        first_hit_date=evaluation.get("first_hit_date"),
                        first_hit_trading_days=evaluation.get("first_hit_trading_days"),
                        simulated_entry_price=evaluation.get("simulated_entry_price"),
                        simulated_exit_price=evaluation.get("simulated_exit_price"),
                        simulated_exit_reason=evaluation.get("simulated_exit_reason"),
                        simulated_return_pct=evaluation.get("simulated_return_pct"),
                    )
                )

            except Exception as exc:
                errors += 1
                logger.error(f"历史分析评估失败: {analysis.code}#{analysis.id}: {exc}")
                results_to_save.append(
                    BacktestResult(
                        analysis_history_id=analysis.id,
                        code=analysis.code,
                        analysis_date=self._resolve_analysis_date(analysis),
                        eval_window_days=settings.eval_window_days,
                        engine_version=settings.engine_version,
                        eval_status="error",
                        evaluated_at=run_at,
                        operation_advice=analysis.operation_advice,
                    )
                )

        no_result_reason: Optional[str] = None
        no_result_message: Optional[str] = None
        summary_snapshot: Dict[str, Any] = {}
        if results_to_save:
            summary_snapshot = BacktestEngine.compute_summary(
                results=results_to_save,
                scope="stock" if code else "overall",
                code=code or OVERALL_SENTINEL_CODE,
                eval_window_days=settings.eval_window_days,
                engine_version=settings.engine_version,
            )

        saved = 0
        if results_to_save:
            saved = self.repo.save_results_batch(results_to_save, replace_existing=force)

        if saved:
            self._recompute_summaries(
                touched_codes=sorted(touched_codes),
                eval_window_days=settings.eval_window_days,
                engine_version=settings.engine_version,
            )

        if saved == 0:
            no_result_reason, no_result_message = self._resolve_run_no_result(
                code=code,
                processed=processed,
                completed=completed,
                insufficient=insufficient,
                errors=errors,
                total_history_count=total_history_count,
                age_eligible_count=age_eligible_count,
                force=force,
                min_age_days=settings.min_age_days,
            )

        run_record = BacktestRun(
            code=code,
            eval_window_days=settings.eval_window_days,
            min_age_days=settings.min_age_days,
            force=force,
            run_at=run_at,
            completed_at=run_at,
            processed=processed,
            saved=saved,
            completed=completed,
            insufficient=insufficient,
            errors=errors,
            candidate_count=len(candidates),
            result_count=saved,
            no_result_reason=no_result_reason,
            no_result_message=no_result_message,
            status="completed" if errors == 0 else "error",
            total_evaluations=summary_snapshot.get("total_evaluations") or 0,
            completed_count=summary_snapshot.get("completed_count") or 0,
            insufficient_count=summary_snapshot.get("insufficient_count") or 0,
            long_count=summary_snapshot.get("long_count") or 0,
            cash_count=summary_snapshot.get("cash_count") or 0,
            win_count=summary_snapshot.get("win_count") or 0,
            loss_count=summary_snapshot.get("loss_count") or 0,
            neutral_count=summary_snapshot.get("neutral_count") or 0,
            win_rate_pct=summary_snapshot.get("win_rate_pct"),
            avg_stock_return_pct=summary_snapshot.get("avg_stock_return_pct"),
            avg_simulated_return_pct=summary_snapshot.get("avg_simulated_return_pct"),
            direction_accuracy_pct=summary_snapshot.get("direction_accuracy_pct"),
            summary_json=json.dumps(summary_snapshot or {}, ensure_ascii=False),
        )
        run_record = self.repo.save_run(run_record)

        return {
            "run_id": run_record.id,
            "run_at": run_record.run_at.isoformat() if run_record.run_at else None,
            "processed": processed,
            "saved": saved,
            "completed": completed,
            "insufficient": insufficient,
            "errors": errors,
            "candidate_count": len(candidates),
            "no_result_reason": no_result_reason,
            "no_result_message": no_result_message,
            "evaluation_mode": "historical_analysis_evaluation",
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
            "execution_assumptions": self._signal_evaluation_assumptions(),
        }

    def list_backtest_runs(self, *, code: Optional[str] = None, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        offset = max(page - 1, 0) * limit
        rows, total = self.repo.get_runs_paginated(code=code, offset=offset, limit=limit)
        items = [self._run_to_dict(row) for row in rows]
        return {"total": total, "page": page, "limit": limit, "items": items}

    def get_run_results(self, *, run_id: int, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        offset = max(page - 1, 0) * limit
        rows, total = self.repo.get_results_paginated(code=None, eval_window_days=None, run_id=run_id, days=None, offset=offset, limit=limit)
        items = [self._result_to_dict(r) for r in rows]
        return {"total": total, "page": page, "limit": limit, "items": items}

    def get_sample_status(self, *, code: str) -> Dict[str, Any]:
        settings = self._resolve_runtime_settings()
        rows = self.repo.get_sample_rows(code=code)
        parsed_dates: List[date] = []
        latest_created_at: Optional[datetime] = None
        for row in rows:
            parsed = self.repo.parse_analysis_date_from_snapshot(row.context_snapshot)
            if parsed:
                parsed_dates.append(parsed)
            if row.created_at and (latest_created_at is None or row.created_at > latest_created_at):
                latest_created_at = row.created_at

        return {
            "code": code,
            "prepared_count": len(rows),
            "prepared_start_date": min(parsed_dates).isoformat() if parsed_dates else None,
            "prepared_end_date": max(parsed_dates).isoformat() if parsed_dates else None,
            "latest_prepared_at": latest_created_at.isoformat() if latest_created_at else None,
            "eval_window_days": settings.eval_window_days,
            "min_age_days": settings.min_age_days,
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
        }

    def clear_backtest_samples(self, *, code: str) -> Dict[str, Any]:
        return self._clear_backtest_artifacts(code=code, include_samples=True)

    def clear_backtest_results(self, *, code: str) -> Dict[str, Any]:
        return self._clear_backtest_artifacts(code=code, include_samples=False)

    def get_recent_evaluations(self, *, code: Optional[str], eval_window_days: Optional[int] = None, limit: int = 50, page: int = 1) -> Dict[str, Any]:
        offset = max(page - 1, 0) * limit
        rows, total = self.repo.get_results_paginated(code=code, eval_window_days=eval_window_days, days=None, offset=offset, limit=limit)
        items = [self._result_to_dict(r) for r in rows]
        return {"total": total, "page": page, "limit": limit, "items": items}

    def get_summary(self, *, scope: str, code: Optional[str], eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        config = get_config()
        engine_version = str(getattr(config, "backtest_engine_version", "v1"))
        lookup_code = OVERALL_SENTINEL_CODE if scope == "overall" else code
        summary = self.repo.get_summary(
            scope=scope,
            code=lookup_code,
            eval_window_days=eval_window_days,
            engine_version=engine_version,
        )
        if summary is None:
            return None
        return self._summary_to_dict(summary)

    def get_global_summary(self, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Return overall backtest metrics normalized for Agent memory consumers."""
        return self._normalize_learning_summary(
            self.get_summary(scope="overall", code=None, eval_window_days=eval_window_days)
        )

    def get_stock_summary(self, code: str, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Return per-stock backtest metrics normalized for Agent memory consumers."""
        return self._normalize_learning_summary(
            self.get_summary(scope="stock", code=code, eval_window_days=eval_window_days)
        )

    def get_skill_summary(self, skill_id: str, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Return skill-like summary metrics for Agent memory consumers.

        The current backtest storage layer only persists overall / per-stock rollups.
        Re-using the overall rollup here would fabricate skill-specific performance
        and mislead auto-weighting. Until real skill-tagged summaries exist, return
        ``None`` so downstream callers fall back to neutral weighting.
        """
        return None

    def get_strategy_summary(self, strategy_id: str, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Compatibility wrapper for legacy strategy-based callers."""
        summary = self.get_skill_summary(strategy_id, eval_window_days=eval_window_days)
        if summary is None:
            return None
        normalized = dict(summary)
        normalized["strategy_id"] = strategy_id
        return normalized

    def prepare_backtest_samples(
        self,
        *,
        code: str,
        sample_count: int = 20,
        eval_window_days: Optional[int] = None,
        min_age_days: Optional[int] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Generate historical analysis snapshots that can be consumed by evaluation."""
        normalized_code = self._require_code(code)
        settings = self._resolve_runtime_settings(
            eval_window_days=eval_window_days,
            min_age_days=min_age_days,
        )
        sample_count = max(1, int(sample_count))

        market_rows_saved = self._ensure_market_history(
            code=normalized_code,
            min_age_days=settings.min_age_days,
            eval_window_days=settings.eval_window_days,
            sample_count=sample_count,
            force_refresh=force_refresh,
        )

        rows = self._load_stock_daily_rows(normalized_code)
        candidate_rows = self._select_preparable_rows(rows, eval_window_days=settings.eval_window_days)
        if not candidate_rows:
            return {
                "code": normalized_code,
                "sample_count": sample_count,
                "prepared": 0,
                "skipped_existing": 0,
                "market_rows_saved": market_rows_saved,
                "candidate_rows": 0,
                "eval_window_days": settings.eval_window_days,
                "min_age_days": settings.min_age_days,
                "no_result_reason": "missing_market_history",
                "no_result_message": "当前没有足够的历史行情数据，无法生成历史分析评估样本。",
            }

        selected_rows = candidate_rows[-sample_count:]
        prepared = 0
        skipped_existing = 0
        now = datetime.now()

        with self.db.get_session() as session:
            for index, row_index in enumerate(selected_rows):
                row = rows[row_index]
                query_id = self._prepare_sample_query_id(normalized_code, row.date, settings.eval_window_days)
                existing = session.execute(
                    select(AnalysisHistory).where(AnalysisHistory.query_id == query_id).limit(1)
                ).scalar_one_or_none()
                if existing is not None and not force_refresh:
                    skipped_existing += 1
                    continue
                if existing is not None and force_refresh:
                    sample = self._build_prepared_analysis_sample(
                        code=normalized_code,
                        row=row,
                        previous_close=rows[row_index - 1].close if row_index > 0 else None,
                        average_close=self._moving_average(rows, row_index, window=3),
                        min_age_days=settings.min_age_days,
                        eval_window_days=settings.eval_window_days,
                        created_at=now - timedelta(days=settings.min_age_days + 1 + index),
                        query_id=query_id,
                    )
                    existing.name = sample.name
                    existing.report_type = sample.report_type
                    existing.sentiment_score = sample.sentiment_score
                    existing.operation_advice = sample.operation_advice
                    existing.trend_prediction = sample.trend_prediction
                    existing.analysis_summary = sample.analysis_summary
                    existing.raw_result = sample.raw_result
                    existing.news_content = sample.news_content
                    existing.context_snapshot = sample.context_snapshot
                    existing.ideal_buy = sample.ideal_buy
                    existing.secondary_buy = sample.secondary_buy
                    existing.stop_loss = sample.stop_loss
                    existing.take_profit = sample.take_profit
                    existing.created_at = sample.created_at
                    prepared += 1
                    continue

                sample = self._build_prepared_analysis_sample(
                    code=normalized_code,
                    row=row,
                    previous_close=rows[row_index - 1].close if row_index > 0 else None,
                    average_close=self._moving_average(rows, row_index, window=3),
                    min_age_days=settings.min_age_days,
                    eval_window_days=settings.eval_window_days,
                    created_at=now - timedelta(days=settings.min_age_days + 1 + index),
                    query_id=query_id,
                )
                session.add(sample)
                prepared += 1

            session.commit()

        return {
            "code": normalized_code,
            "sample_count": sample_count,
            "prepared": prepared,
            "skipped_existing": skipped_existing,
            "market_rows_saved": market_rows_saved,
            "candidate_rows": len(candidate_rows),
            "eval_window_days": settings.eval_window_days,
            "min_age_days": settings.min_age_days,
            "prepared_start_date": self._prepared_sample_start_date(normalized_code),
            "prepared_end_date": self._prepared_sample_end_date(normalized_code),
            "latest_prepared_at": self._latest_prepared_at(normalized_code),
            "no_result_reason": None if prepared > 0 else "no_samples_prepared",
            "no_result_message": (
                f"已准备 {prepared} 条历史分析评估样本，可重新运行评估。"
                if prepared > 0
                else "没有生成新的历史分析评估样本。"
            ),
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
        }

    @staticmethod
    def _require_code(code: str) -> str:
        normalized_code = str(code or "").strip()
        if not normalized_code:
            raise ValueError("code is required")
        return normalized_code

    @staticmethod
    def _resolve_runtime_settings(
        config: Optional[Any] = None,
        *,
        eval_window_days: Optional[int] = None,
        min_age_days: Optional[int] = None,
    ) -> BacktestRuntimeSettings:
        resolved_config = config or get_config()
        resolved_eval_window_days = int(
            eval_window_days
            if eval_window_days is not None
            else getattr(resolved_config, "backtest_eval_window_days", 10)
        )
        resolved_min_age_days = int(
            min_age_days
            if min_age_days is not None
            else getattr(resolved_config, "backtest_min_age_days", 14)
        )
        return BacktestRuntimeSettings(
            eval_window_days=max(1, resolved_eval_window_days),
            min_age_days=max(0, resolved_min_age_days),
            engine_version=str(getattr(resolved_config, "backtest_engine_version", "v1")),
            neutral_band_pct=float(getattr(resolved_config, "backtest_neutral_band_pct", 2.0)),
        )

    @staticmethod
    def _resolve_run_no_result(
        *,
        code: Optional[str],
        processed: int,
        completed: int,
        insufficient: int,
        errors: int,
        total_history_count: int,
        age_eligible_count: int,
        force: bool,
        min_age_days: int,
    ) -> tuple[str, str]:
        if processed == 0:
            if total_history_count == 0:
                return "no_analysis_history", "没有找到可评估的历史分析记录。"
            if age_eligible_count == 0:
                scope_label = f"股票 {code}" if code else "当前筛选条件"
                return (
                    "insufficient_historical_data",
                    f"{scope_label} 下没有满足 {min_age_days} 天成熟窗口的分析记录，因此本次历史分析评估未生成结果。",
                )
            if not force:
                return (
                    "already_backtested",
                    "符合条件的分析记录已经有相同窗口的历史分析评估结果，因此没有写入新结果。",
                )
            return "no_eligible_candidates", "没有可执行的历史分析评估候选记录。"
        if completed == 0 and insufficient > 0:
            return (
                "insufficient_forward_data",
                "候选记录都缺少足够的前向行情窗口，因此未生成可完成的历史分析评估结果。",
            )
        if completed == 0 and errors > 0:
            return "execution_failed", f"{errors} 条候选记录在历史分析评估执行中出错。"
        return "persistence_noop", "历史分析评估已执行，但没有写入新的结果。"

    def _clear_backtest_artifacts(self, *, code: str, include_samples: bool) -> Dict[str, Any]:
        normalized_code = self._require_code(code)
        deleted_runs = self.repo.delete_runs_by_code(code=normalized_code)
        deleted_results = self.repo.delete_results_by_code(code=normalized_code)
        deleted_samples = self.repo.delete_sample_rows(code=normalized_code) if include_samples else 0
        deleted_summaries = self.repo.delete_summaries_by_code(code=normalized_code)
        self._recompute_global_summaries_if_needed()
        return {
            "code": normalized_code,
            "deleted_runs": deleted_runs,
            "deleted_results": deleted_results,
            "deleted_samples": deleted_samples,
            "deleted_summaries": deleted_summaries,
        }

    def _resolve_analysis_date(self, analysis) -> Optional[date]:
        parsed = self.repo.parse_analysis_date_from_snapshot(analysis.context_snapshot)
        if parsed:
            return parsed
        if getattr(analysis, "created_at", None):
            return analysis.created_at.date()
        logger.warning(f"无法确定分析日期，跳过记录: {analysis.code}#{getattr(analysis, 'id', '?')}")
        return None

    @staticmethod
    def _signal_evaluation_assumptions() -> Dict[str, Any]:
        return {
            "module_type": "historical_analysis_evaluation",
            "evaluation_window_unit": "trading_bars",
            "maturity_unit": "calendar_days",
            "price_basis": "close",
            "analysis_signal_timing": "analysis snapshot on analysis_date",
            "simulated_entry_timing": "analysis_date close",
            "simulated_exit_timing": "first forward bar target touch or evaluation-window end close",
            "position_sizing": "binary long_or_cash; simulated long leg uses 100% notional exposure",
            "fees_slippage": "not applied",
        }

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

    def _collect_market_data_sources(self, *, code: str, analysis_date: Optional[date], eval_window_days: int) -> List[str]:
        if analysis_date is None:
            return []
        sources: List[str] = []
        start_daily = self.stock_repo.get_start_daily(code=code, analysis_date=analysis_date)
        if start_daily and start_daily.data_source:
            sources.append(str(start_daily.data_source))
        for bar in self.stock_repo.get_forward_bars(code=code, analysis_date=analysis_date, eval_window_days=eval_window_days):
            if bar.data_source:
                sources.append(str(bar.data_source))
        deduped: List[str] = []
        for item in sources:
            if item not in deduped:
                deduped.append(item)
        return deduped

    def _try_fill_daily_data(self, *, code: str, analysis_date: date, eval_window_days: int) -> None:
        try:
            # Fetch a window that covers the analysis bar plus the forward evaluation bars.
            end_date = analysis_date + timedelta(days=max(eval_window_days * 2, 30))
            df, source = self._load_history_with_local_us_fallback(
                code=code,
                start_date=analysis_date,
                end_date=end_date,
                days=eval_window_days * 2,
                log_context="[historical-eval fill]",
            )
            if df is None or df.empty:
                return
            self.db.save_daily_data(df, code=code, data_source=source)
        except Exception as exc:
            logger.warning(f"补全历史分析评估日线数据失败({code}): {exc}")

    def _ensure_market_history(
        self,
        *,
        code: str,
        min_age_days: int,
        eval_window_days: int,
        sample_count: int,
        force_refresh: bool,
    ) -> int:
        """Ensure enough market history exists for sample generation."""
        lookback_days = max(min_age_days + eval_window_days + sample_count + 30, 90)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=lookback_days)

        rows = self._load_stock_daily_rows(code)
        if force_refresh:
            rows = []

        if rows:
            earliest = rows[0].date
            latest = rows[-1].date
            if earliest <= start_date and latest >= end_date - timedelta(days=1):
                return 0

        try:
            df, source = self._load_history_with_local_us_fallback(
                code=code,
                start_date=start_date,
                end_date=end_date,
                days=lookback_days,
                log_context="[historical-eval warmup]",
            )
            if df is None or df.empty:
                return 0
            return self.db.save_daily_data(df, code=code, data_source=source)
        except Exception as exc:
            logger.warning(f"准备历史分析评估样本时补全日线数据失败({code}): {exc}")
            return 0

    def _load_stock_daily_rows(self, code: str) -> List[StockDaily]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(StockDaily)
                .where(StockDaily.code == code)
                .order_by(StockDaily.date)
            ).scalars().all()
            return list(rows)

    @staticmethod
    def _select_preparable_rows(rows: List[StockDaily], *, eval_window_days: int) -> List[int]:
        if not rows:
            return []
        cutoff = max(0, len(rows) - int(eval_window_days))
        return [idx for idx in range(3, cutoff) if rows[idx].close is not None]

    @staticmethod
    def _prepare_sample_query_id(code: str, sample_date: date, eval_window_days: int) -> str:
        return f"bt-sample:{code}:{sample_date.isoformat()}:w{int(eval_window_days)}"

    @staticmethod
    def _build_prepared_analysis_sample(
        *,
        code: str,
        row: StockDaily,
        previous_close: Optional[float],
        average_close: Optional[float],
        min_age_days: int,
        eval_window_days: int,
        created_at: datetime,
        query_id: str,
    ) -> AnalysisHistory:
        if row.close is None:
            operation_advice = "持有"
            trend_prediction = "震荡"
            sentiment_score = 50
        else:
            trend_gap = 0.0
            if previous_close:
                trend_gap = (float(row.close) - float(previous_close)) / float(previous_close) * 100.0
            ma_gap = 0.0
            if average_close:
                ma_gap = (float(row.close) - float(average_close)) / float(average_close) * 100.0
            if trend_gap >= 1.5 or ma_gap >= 1.0:
                operation_advice = "买入"
                trend_prediction = "看多"
                sentiment_score = 72
            elif trend_gap <= -1.5 or ma_gap <= -1.0:
                operation_advice = "卖出"
                trend_prediction = "看空"
                sentiment_score = 28
            else:
                operation_advice = "持有"
                trend_prediction = "震荡"
                sentiment_score = 50

        current_close = float(row.close) if row.close is not None else None
        stop_loss = round(current_close * 0.97, 2) if current_close is not None and operation_advice == "买入" else None
        take_profit = round(current_close * 1.05, 2) if current_close is not None and operation_advice == "买入" else None

        context_snapshot = {
            "enhanced_context": {
                "date": row.date.isoformat(),
                "market_session_date": row.date.isoformat(),
            }
        }

        raw_result = {
            "generated_for": "backtest_sample",
            "code": code,
            "analysis_date": row.date.isoformat(),
            "operation_advice": operation_advice,
            "trend_prediction": trend_prediction,
            "sentiment_score": sentiment_score,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "sample_source": "local_preparation",
            "market_data_source": row.data_source,
            "eval_window_days": eval_window_days,
            "evaluation_window_unit": "trading_bars",
            "min_age_days": min_age_days,
            "maturity_unit": "calendar_days",
        }

        return AnalysisHistory(
            query_id=query_id,
            code=code,
            name=code,
            report_type="backtest_sample",
            sentiment_score=sentiment_score,
            operation_advice=operation_advice,
            trend_prediction=trend_prediction,
            analysis_summary=(
                f"本地准备的历史分析评估样本，基于 {row.date.isoformat()} 的历史行情生成。"
            ),
            raw_result=json.dumps(raw_result, ensure_ascii=False),
            news_content=None,
            context_snapshot=json.dumps(context_snapshot, ensure_ascii=False),
            ideal_buy=current_close,
            secondary_buy=None,
            stop_loss=stop_loss,
            take_profit=take_profit,
            created_at=created_at,
        )

    @staticmethod
    def _moving_average(rows: List[StockDaily], index: int, *, window: int = 3) -> Optional[float]:
        if index <= 0:
            return None
        start = max(0, index - window)
        closes = [float(row.close) for row in rows[start:index] if row.close is not None]
        if not closes:
            return None
        return sum(closes) / len(closes)

    def _prepared_sample_start_date(self, code: str) -> Optional[str]:
        rows = self.repo.get_sample_rows(code=code)
        dates = [self.repo.parse_analysis_date_from_snapshot(row.context_snapshot) for row in rows]
        dates = [d for d in dates if d is not None]
        return min(dates).isoformat() if dates else None

    def _prepared_sample_end_date(self, code: str) -> Optional[str]:
        rows = self.repo.get_sample_rows(code=code)
        dates = [self.repo.parse_analysis_date_from_snapshot(row.context_snapshot) for row in rows]
        dates = [d for d in dates if d is not None]
        return max(dates).isoformat() if dates else None

    def _latest_prepared_at(self, code: str) -> Optional[str]:
        rows = self.repo.get_sample_rows(code=code)
        latest = None
        for row in rows:
            if row.created_at and (latest is None or row.created_at > latest):
                latest = row.created_at
        return latest.isoformat() if latest else None

    def _recompute_global_summaries_if_needed(self) -> None:
        config = get_config()
        eval_window_days = int(getattr(config, "backtest_eval_window_days", 10))
        engine_version = str(getattr(config, "backtest_engine_version", "v1"))
        self._recompute_summaries_for_window(eval_window_days=eval_window_days, engine_version=engine_version)

    def _recompute_summaries_for_window(self, *, eval_window_days: int, engine_version: str) -> None:
        with self.db.get_session() as session:
            overall_rows = session.execute(
                select(BacktestResult).where(
                    and_(
                        BacktestResult.eval_window_days == eval_window_days,
                        BacktestResult.engine_version == engine_version,
                    )
                )
            ).scalars().all()
            if not overall_rows:
                self.repo.delete_all_summaries_for_window(
                    eval_window_days=eval_window_days,
                    engine_version=engine_version,
                )
                return
            overall_data = BacktestEngine.compute_summary(
                results=overall_rows,
                scope="overall",
                code=OVERALL_SENTINEL_CODE,
                eval_window_days=eval_window_days,
                engine_version=engine_version,
            )
            overall_summary = self._build_summary_model(overall_data)
            self.repo.upsert_summary(overall_summary)

            codes = self.repo.list_backtest_codes(eval_window_days=eval_window_days, engine_version=engine_version)
            for code in codes:
                rows = session.execute(
                    select(BacktestResult).where(
                        and_(
                            BacktestResult.code == code,
                            BacktestResult.eval_window_days == eval_window_days,
                            BacktestResult.engine_version == engine_version,
                        )
                    )
                ).scalars().all()
                data = BacktestEngine.compute_summary(
                    results=rows,
                    scope="stock",
                    code=code,
                    eval_window_days=eval_window_days,
                    engine_version=engine_version,
                )
                summary = self._build_summary_model(data)
                self.repo.upsert_summary(summary)

    def _recompute_summaries(self, *, touched_codes: List[str], eval_window_days: int, engine_version: str) -> None:
        with self.db.get_session() as session:
            # overall
            overall_rows = session.execute(
                select(BacktestResult).where(
                    and_(
                        BacktestResult.eval_window_days == eval_window_days,
                        BacktestResult.engine_version == engine_version,
                    )
                )
            ).scalars().all()
            overall_data = BacktestEngine.compute_summary(
                results=overall_rows,
                scope="overall",
                code=OVERALL_SENTINEL_CODE,
                eval_window_days=eval_window_days,
                engine_version=engine_version,
            )
            overall_summary = self._build_summary_model(overall_data)
            self.repo.upsert_summary(overall_summary)

            for code in touched_codes:
                rows = session.execute(
                    select(BacktestResult).where(
                        and_(
                            BacktestResult.code == code,
                            BacktestResult.eval_window_days == eval_window_days,
                            BacktestResult.engine_version == engine_version,
                        )
                    )
                ).scalars().all()
                data = BacktestEngine.compute_summary(
                    results=rows,
                    scope="stock",
                    code=code,
                    eval_window_days=eval_window_days,
                    engine_version=engine_version,
                )
                summary = self._build_summary_model(data)
                self.repo.upsert_summary(summary)

    @staticmethod
    def _build_summary_model(summary_data: Dict[str, Any]) -> BacktestSummary:
        return BacktestSummary(
            scope=summary_data.get("scope"),
            code=summary_data.get("code"),
            eval_window_days=summary_data.get("eval_window_days"),
            engine_version=summary_data.get("engine_version"),
            computed_at=datetime.now(),
            total_evaluations=summary_data.get("total_evaluations") or 0,
            completed_count=summary_data.get("completed_count") or 0,
            insufficient_count=summary_data.get("insufficient_count") or 0,
            long_count=summary_data.get("long_count") or 0,
            cash_count=summary_data.get("cash_count") or 0,
            win_count=summary_data.get("win_count") or 0,
            loss_count=summary_data.get("loss_count") or 0,
            neutral_count=summary_data.get("neutral_count") or 0,
            direction_accuracy_pct=summary_data.get("direction_accuracy_pct"),
            win_rate_pct=summary_data.get("win_rate_pct"),
            neutral_rate_pct=summary_data.get("neutral_rate_pct"),
            avg_stock_return_pct=summary_data.get("avg_stock_return_pct"),
            avg_simulated_return_pct=summary_data.get("avg_simulated_return_pct"),
            stop_loss_trigger_rate=summary_data.get("stop_loss_trigger_rate"),
            take_profit_trigger_rate=summary_data.get("take_profit_trigger_rate"),
            ambiguous_rate=summary_data.get("ambiguous_rate"),
            avg_days_to_first_hit=summary_data.get("avg_days_to_first_hit"),
            advice_breakdown_json=json.dumps(summary_data.get("advice_breakdown") or {}, ensure_ascii=False),
            diagnostics_json=json.dumps(summary_data.get("diagnostics") or {}, ensure_ascii=False),
        )

    def _result_to_dict(self, row: BacktestResult) -> Dict[str, Any]:
        assumptions = self._signal_evaluation_assumptions()
        market_data_sources = self._collect_market_data_sources(
            code=row.code,
            analysis_date=row.analysis_date,
            eval_window_days=row.eval_window_days,
        )
        return {
            "analysis_history_id": row.analysis_history_id,
            "code": row.code,
            "analysis_date": row.analysis_date.isoformat() if row.analysis_date else None,
            "eval_window_days": row.eval_window_days,
            "evaluation_window_trading_bars": row.eval_window_days,
            "engine_version": row.engine_version,
            "eval_status": row.eval_status,
            "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
            "operation_advice": row.operation_advice,
            "position_recommendation": row.position_recommendation,
            "start_price": row.start_price,
            "end_close": row.end_close,
            "max_high": row.max_high,
            "min_low": row.min_low,
            "stock_return_pct": row.stock_return_pct,
            "direction_expected": row.direction_expected,
            "direction_correct": row.direction_correct,
            "outcome": row.outcome,
            "stop_loss": row.stop_loss,
            "take_profit": row.take_profit,
            "hit_stop_loss": row.hit_stop_loss,
            "hit_take_profit": row.hit_take_profit,
            "first_hit": row.first_hit,
            "first_hit_date": row.first_hit_date.isoformat() if row.first_hit_date else None,
            "first_hit_trading_days": row.first_hit_trading_days,
            "simulated_entry_price": row.simulated_entry_price,
            "simulated_exit_price": row.simulated_exit_price,
            "simulated_exit_reason": row.simulated_exit_reason,
            "simulated_return_pct": row.simulated_return_pct,
            "market_data_sources": market_data_sources,
            "execution_assumptions": assumptions,
        }

    def _run_to_dict(self, row: BacktestRun) -> Dict[str, Any]:
        summary = {}
        if getattr(row, "summary_json", None):
            try:
                summary = json.loads(row.summary_json)
            except Exception:
                summary = {}
        return {
            "id": row.id,
            "code": row.code,
            "eval_window_days": row.eval_window_days,
            "evaluation_window_trading_bars": row.eval_window_days,
            "min_age_days": row.min_age_days,
            "maturity_calendar_days": row.min_age_days,
            "force": bool(row.force),
            "run_at": row.run_at.isoformat() if row.run_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "processed": row.processed,
            "saved": row.saved,
            "completed": row.completed,
            "insufficient": row.insufficient,
            "errors": row.errors,
            "candidate_count": row.candidate_count,
            "result_count": row.result_count,
            "no_result_reason": row.no_result_reason,
            "no_result_message": row.no_result_message,
            "status": row.status,
            "total_evaluations": row.total_evaluations,
            "completed_count": row.completed_count,
            "insufficient_count": row.insufficient_count,
            "long_count": row.long_count,
            "cash_count": row.cash_count,
            "win_count": row.win_count,
            "loss_count": row.loss_count,
            "neutral_count": row.neutral_count,
            "win_rate_pct": row.win_rate_pct,
            "avg_stock_return_pct": row.avg_stock_return_pct,
            "avg_simulated_return_pct": row.avg_simulated_return_pct,
            "direction_accuracy_pct": row.direction_accuracy_pct,
            "summary": summary,
            "evaluation_mode": "historical_analysis_evaluation",
            "execution_assumptions": self._signal_evaluation_assumptions(),
        }

    def _summary_to_dict(self, row: BacktestSummary) -> Dict[str, Any]:
        return {
            "scope": row.scope,
            "code": None if row.code == OVERALL_SENTINEL_CODE else row.code,
            "eval_window_days": row.eval_window_days,
            "evaluation_window_trading_bars": row.eval_window_days,
            "engine_version": row.engine_version,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
            "total_evaluations": row.total_evaluations,
            "completed_count": row.completed_count,
            "insufficient_count": row.insufficient_count,
            "long_count": row.long_count,
            "cash_count": row.cash_count,
            "win_count": row.win_count,
            "loss_count": row.loss_count,
            "neutral_count": row.neutral_count,
            "direction_accuracy_pct": row.direction_accuracy_pct,
            "win_rate_pct": row.win_rate_pct,
            "neutral_rate_pct": row.neutral_rate_pct,
            "avg_stock_return_pct": row.avg_stock_return_pct,
            "avg_simulated_return_pct": row.avg_simulated_return_pct,
            "stop_loss_trigger_rate": row.stop_loss_trigger_rate,
            "take_profit_trigger_rate": row.take_profit_trigger_rate,
            "ambiguous_rate": row.ambiguous_rate,
            "avg_days_to_first_hit": row.avg_days_to_first_hit,
            "advice_breakdown": json.loads(row.advice_breakdown_json) if row.advice_breakdown_json else {},
            "diagnostics": json.loads(row.diagnostics_json) if row.diagnostics_json else {},
            "evaluation_mode": "historical_analysis_evaluation",
            "execution_assumptions": self._signal_evaluation_assumptions(),
        }

    @staticmethod
    def _normalize_learning_summary(summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Normalize summary metrics to the ratio-based shape expected by Agent memory."""
        if summary is None:
            return None

        normalized = dict(summary)
        normalized["win_rate"] = BacktestService._pct_to_ratio(summary.get("win_rate_pct"), default=0.5)
        normalized["direction_accuracy"] = BacktestService._pct_to_ratio(
            summary.get("direction_accuracy_pct"),
            default=0.5,
        )

        avg_return_pct = summary.get("avg_simulated_return_pct")
        if avg_return_pct is None:
            avg_return_pct = summary.get("avg_stock_return_pct")
        normalized["avg_return"] = BacktestService._pct_to_ratio(avg_return_pct, default=0.0)
        return normalized

    @staticmethod
    def _pct_to_ratio(value: Optional[float], default: float = 0.0) -> float:
        try:
            return float(value) / 100.0
        except (TypeError, ValueError):
            return default
