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


@dataclass(frozen=True)
class BacktestSourceMetadata:
    requested_mode: str
    resolved_source: str
    fallback_used: bool


class BacktestService:
    """Service layer for historical analysis evaluation and sample preparation."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ):
        self.db = db_manager or DatabaseManager.get_instance()
        self.repo = BacktestRepository(self.db)
        self.stock_repo = StockRepository(self.db)
        self.owner_id = owner_id
        self.include_all_owners = bool(include_all_owners)

    def _owner_kwargs(self) -> Dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "include_all_owners": self.include_all_owners,
        }

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
        resolved_owner_id = self.db.require_user_id(self.owner_id)

        eval_config = EvaluationConfig(
            eval_window_days=settings.eval_window_days,
            neutral_band_pct=settings.neutral_band_pct,
            engine_version=settings.engine_version,
        )

        total_history_count = self.repo.count_analysis_history(code=code, **self._owner_kwargs())
        age_eligible_count = self.repo.count_analysis_history(
            code=code,
            created_before=cutoff_dt,
            **self._owner_kwargs(),
        )

        candidates = self.repo.get_candidates(
            code=code,
            min_age_days=settings.min_age_days,
            limit=int(limit),
            eval_window_days=settings.eval_window_days,
            engine_version=settings.engine_version,
            force=force,
            **self._owner_kwargs(),
        )
        sample_observability = self._build_sample_observability(
            code=code,
            settings=settings,
            candidates=candidates,
        )

        processed = 0
        completed = 0
        insufficient = 0
        errors = 0
        touched_codes: set[str] = set()

        results_to_save: List[BacktestResult] = []
        run_runtime_sources: List[str] = []
        run_fallback_used = False

        for analysis in candidates:
            processed += 1
            touched_codes.add(analysis.code)
            analysis_runtime_source = "DatabaseCache"
            analysis_fallback_used = False

            try:
                analysis_date = self._resolve_analysis_date(analysis)
                if analysis_date is None:
                    errors += 1
                    results_to_save.append(
                        BacktestResult(
                            owner_id=resolved_owner_id,
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
                    fill_source_meta = self._try_fill_daily_data(
                        code=analysis.code,
                        analysis_date=analysis_date,
                        eval_window_days=settings.eval_window_days,
                    )
                    if fill_source_meta is not None:
                        analysis_runtime_source = fill_source_meta.resolved_source
                        analysis_fallback_used = analysis_fallback_used or fill_source_meta.fallback_used
                    start_daily = self.stock_repo.get_start_daily(code=analysis.code, analysis_date=analysis_date)

                if start_daily is None or start_daily.close is None:
                    insufficient += 1
                    run_runtime_sources.append(analysis_runtime_source)
                    run_fallback_used = run_fallback_used or analysis_fallback_used
                    results_to_save.append(
                        BacktestResult(
                            owner_id=resolved_owner_id,
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
                    fill_source_meta = self._try_fill_daily_data(
                        code=analysis.code,
                        analysis_date=start_daily.date,
                        eval_window_days=settings.eval_window_days,
                    )
                    if fill_source_meta is not None:
                        analysis_runtime_source = fill_source_meta.resolved_source
                        analysis_fallback_used = analysis_fallback_used or fill_source_meta.fallback_used
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
                run_runtime_sources.append(analysis_runtime_source)
                run_fallback_used = run_fallback_used or analysis_fallback_used

                results_to_save.append(
                    BacktestResult(
                        owner_id=resolved_owner_id,
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
                run_runtime_sources.append(analysis_runtime_source)
                run_fallback_used = run_fallback_used or analysis_fallback_used
                results_to_save.append(
                    BacktestResult(
                        owner_id=resolved_owner_id,
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
            run_source_metadata = self._build_source_metadata_from_runtime_sources(
                code=code,
                runtime_sources=run_runtime_sources,
                fallback_used=run_fallback_used,
            )
            summary_snapshot.update({
                "requested_mode": run_source_metadata.requested_mode,
                "resolved_source": run_source_metadata.resolved_source,
                "fallback_used": run_source_metadata.fallback_used,
            })

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
            owner_id=resolved_owner_id,
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

        run_source_metadata = self._build_source_metadata_from_runtime_sources(
            code=code,
            runtime_sources=run_runtime_sources,
            fallback_used=run_fallback_used,
        )

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
            "latest_prepared_sample_date": sample_observability.get("latest_prepared_sample_date"),
            "latest_eligible_sample_date": sample_observability.get("latest_eligible_sample_date"),
            "excluded_recent_reason": sample_observability.get("excluded_recent_reason"),
            "excluded_recent_message": sample_observability.get("excluded_recent_message"),
            "evaluation_mode": "historical_analysis_evaluation",
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
            "requested_mode": run_source_metadata.requested_mode,
            "resolved_source": run_source_metadata.resolved_source,
            "fallback_used": run_source_metadata.fallback_used,
            "pricing_resolved_source": run_source_metadata.resolved_source,
            "pricing_fallback_used": run_source_metadata.fallback_used,
            "execution_assumptions": self._signal_evaluation_assumptions(),
        }

    def list_backtest_runs(self, *, code: Optional[str] = None, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        offset = max(page - 1, 0) * limit
        rows, total = self.repo.get_runs_paginated(
            code=code,
            offset=offset,
            limit=limit,
            **self._owner_kwargs(),
        )
        items = [self._run_to_dict(row) for row in rows]
        return {"total": total, "page": page, "limit": limit, "items": items}

    def get_run_results(self, *, run_id: int, page: int = 1, limit: int = 20) -> Optional[Dict[str, Any]]:
        run = self.repo.get_run(run_id, **self._owner_kwargs())
        if run is None:
            return None
        offset = max(page - 1, 0) * limit
        rows, total = self.repo.get_results_paginated(
            code=None,
            eval_window_days=None,
            run_id=run_id,
            days=None,
            offset=offset,
            limit=limit,
            **self._owner_kwargs(),
        )
        items = [self._result_to_dict(r) for r in rows]
        return {"total": total, "page": page, "limit": limit, "items": items}

    def get_sample_status(self, *, code: str) -> Dict[str, Any]:
        settings = self._resolve_runtime_settings()
        rows = self.repo.get_sample_rows(code=code, **self._owner_kwargs())
        parsed_dates: List[date] = []
        latest_created_at: Optional[datetime] = None
        for row in rows:
            parsed = self.repo.parse_analysis_date_from_snapshot(row.context_snapshot)
            if parsed:
                parsed_dates.append(parsed)
            if row.created_at and (latest_created_at is None or row.created_at > latest_created_at):
                latest_created_at = row.created_at
        source_metadata = self._build_source_metadata_for_samples(code=code, sample_rows=rows)
        sample_observability = self._build_sample_observability(
            code=code,
            settings=settings,
            sample_rows=rows,
        )

        return {
            "code": code,
            "prepared_count": len(rows),
            "prepared_start_date": min(parsed_dates).isoformat() if parsed_dates else None,
            "prepared_end_date": max(parsed_dates).isoformat() if parsed_dates else None,
            "latest_prepared_at": latest_created_at.isoformat() if latest_created_at else None,
            "latest_prepared_sample_date": sample_observability.get("latest_prepared_sample_date"),
            "latest_eligible_sample_date": sample_observability.get("latest_eligible_sample_date"),
            "excluded_recent_reason": sample_observability.get("excluded_recent_reason"),
            "excluded_recent_message": sample_observability.get("excluded_recent_message"),
            "eval_window_days": settings.eval_window_days,
            "min_age_days": settings.min_age_days,
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
            "requested_mode": source_metadata.requested_mode,
            "resolved_source": source_metadata.resolved_source,
            "fallback_used": source_metadata.fallback_used,
            "pricing_resolved_source": source_metadata.resolved_source,
            "pricing_fallback_used": source_metadata.fallback_used,
        }

    def clear_backtest_samples(self, *, code: str) -> Dict[str, Any]:
        return self._clear_backtest_artifacts(code=code, include_samples=True)

    def clear_backtest_results(self, *, code: str) -> Dict[str, Any]:
        return self._clear_backtest_artifacts(code=code, include_samples=False)

    def get_recent_evaluations(self, *, code: Optional[str], eval_window_days: Optional[int] = None, limit: int = 50, page: int = 1) -> Dict[str, Any]:
        offset = max(page - 1, 0) * limit
        rows, total = self.repo.get_results_paginated(
            code=code,
            eval_window_days=eval_window_days,
            days=None,
            offset=offset,
            limit=limit,
            **self._owner_kwargs(),
        )
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
            **self._owner_kwargs(),
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

        market_rows_saved, warmup_source_metadata = self._ensure_market_history(
            code=normalized_code,
            min_age_days=settings.min_age_days,
            eval_window_days=settings.eval_window_days,
            sample_count=sample_count,
            force_refresh=force_refresh,
        )

        rows = self._load_stock_daily_rows(normalized_code)
        candidate_rows = self._select_preparable_rows(rows, eval_window_days=settings.eval_window_days)
        if not candidate_rows:
            source_metadata = warmup_source_metadata or self._build_source_metadata_from_runtime_sources(
                code=normalized_code,
                runtime_sources=["DatabaseCache"] if rows else [],
                fallback_used=False,
            )
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
                "requested_mode": source_metadata.requested_mode,
                "resolved_source": source_metadata.resolved_source,
                "fallback_used": source_metadata.fallback_used,
            }

        selected_rows = candidate_rows[-sample_count:]
        prepared = 0
        skipped_existing = 0
        now = datetime.now()

        resolved_owner_id = self.db.require_user_id(self.owner_id)
        with self.db.get_session() as session:
            for index, row_index in enumerate(selected_rows):
                row = rows[row_index]
                query_id = self._prepare_sample_query_id(normalized_code, row.date, settings.eval_window_days)
                existing = session.execute(
                    select(AnalysisHistory).where(
                        and_(
                            AnalysisHistory.query_id == query_id,
                            AnalysisHistory.owner_id == resolved_owner_id,
                        )
                    ).limit(1)
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
                        owner_id=resolved_owner_id,
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
                    owner_id=resolved_owner_id,
                )
                session.add(sample)
                prepared += 1

            session.commit()

        source_metadata = warmup_source_metadata or self._build_source_metadata_for_stock_rows(
            code=normalized_code,
            rows=rows,
            default_to_cache=bool(rows),
        )
        sample_observability = self._build_sample_observability(
            code=normalized_code,
            settings=settings,
            sample_rows=self.repo.get_sample_rows(code=normalized_code, **self._owner_kwargs()),
            stock_rows=rows,
        )

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
            "latest_prepared_sample_date": sample_observability.get("latest_prepared_sample_date"),
            "latest_eligible_sample_date": sample_observability.get("latest_eligible_sample_date"),
            "excluded_recent_reason": sample_observability.get("excluded_recent_reason"),
            "excluded_recent_message": sample_observability.get("excluded_recent_message"),
            "no_result_reason": None if prepared > 0 else "no_samples_prepared",
            "no_result_message": (
                f"已准备 {prepared} 条历史分析评估样本，可重新运行评估。"
                if prepared > 0
                else "没有生成新的历史分析评估样本。"
            ),
            "evaluation_window_trading_bars": settings.eval_window_days,
            "maturity_calendar_days": settings.min_age_days,
            "requested_mode": source_metadata.requested_mode,
            "resolved_source": source_metadata.resolved_source,
            "fallback_used": source_metadata.fallback_used,
            "pricing_resolved_source": source_metadata.resolved_source,
            "pricing_fallback_used": source_metadata.fallback_used,
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
        deleted_runs = self.repo.delete_runs_by_code(code=normalized_code, **self._owner_kwargs())
        deleted_results = self.repo.delete_results_by_code(code=normalized_code, **self._owner_kwargs())
        deleted_samples = self.repo.delete_sample_rows(code=normalized_code, **self._owner_kwargs()) if include_samples else 0
        deleted_summaries = self.repo.delete_summaries_by_code(code=normalized_code, **self._owner_kwargs())
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

    def _try_fill_daily_data(self, *, code: str, analysis_date: date, eval_window_days: int) -> Optional[BacktestSourceMetadata]:
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
                return None
            self.db.save_daily_data(df, code=code, data_source=source)
            return self._build_source_metadata_from_fetch_source(code=code, source=source)
        except Exception as exc:
            logger.warning(f"补全历史分析评估日线数据失败({code}): {exc}")
            return None

    def _ensure_market_history(
        self,
        *,
        code: str,
        min_age_days: int,
        eval_window_days: int,
        sample_count: int,
        force_refresh: bool,
    ) -> tuple[int, Optional[BacktestSourceMetadata]]:
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
                return 0, self._build_source_metadata_for_stock_rows(code=code, rows=rows, default_to_cache=True)

        try:
            df, source = self._load_history_with_local_us_fallback(
                code=code,
                start_date=start_date,
                end_date=end_date,
                days=lookback_days,
                log_context="[historical-eval warmup]",
            )
            if df is None or df.empty:
                return 0, None
            saved_count = self.db.save_daily_data(df, code=code, data_source=source)
            return saved_count, self._build_source_metadata_from_fetch_source(code=code, source=source)
        except Exception as exc:
            logger.warning(f"准备历史分析评估样本时补全日线数据失败({code}): {exc}")
            return 0, None

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

    def _build_prepared_analysis_sample(
        self,
        *,
        code: str,
        row: StockDaily,
        previous_close: Optional[float],
        average_close: Optional[float],
        min_age_days: int,
        eval_window_days: int,
        created_at: datetime,
        query_id: str,
        owner_id: str,
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
            owner_id=owner_id,
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
        rows = self.repo.get_sample_rows(code=code, **self._owner_kwargs())
        dates = [self.repo.parse_analysis_date_from_snapshot(row.context_snapshot) for row in rows]
        dates = [d for d in dates if d is not None]
        return min(dates).isoformat() if dates else None

    def _prepared_sample_end_date(self, code: str) -> Optional[str]:
        rows = self.repo.get_sample_rows(code=code, **self._owner_kwargs())
        dates = [self.repo.parse_analysis_date_from_snapshot(row.context_snapshot) for row in rows]
        dates = [d for d in dates if d is not None]
        return max(dates).isoformat() if dates else None

    def _latest_prepared_at(self, code: str) -> Optional[str]:
        rows = self.repo.get_sample_rows(code=code, **self._owner_kwargs())
        latest = None
        for row in rows:
            if row.created_at and (latest is None or row.created_at > latest):
                latest = row.created_at
        return latest.isoformat() if latest else None

    def _build_sample_observability(
        self,
        *,
        code: Optional[str],
        settings: BacktestRuntimeSettings,
        candidates: Optional[List[AnalysisHistory]] = None,
        sample_rows: Optional[List[AnalysisHistory]] = None,
        stock_rows: Optional[List[StockDaily]] = None,
    ) -> Dict[str, Any]:
        normalized_code = str(code or "").strip()
        if not normalized_code:
            return {
                "latest_prepared_sample_date": None,
                "latest_eligible_sample_date": None,
                "excluded_recent_reason": None,
                "excluded_recent_message": None,
            }

        sample_rows = sample_rows if sample_rows is not None else self.repo.get_sample_rows(
            code=normalized_code,
            **self._owner_kwargs(),
        )
        stock_rows = stock_rows if stock_rows is not None else self._load_stock_daily_rows(normalized_code)
        candidates = candidates if candidates is not None else self.repo.get_candidates(
            code=normalized_code,
            min_age_days=settings.min_age_days,
            limit=max(self.repo.count_analysis_history(code=normalized_code, **self._owner_kwargs()), 1),
            eval_window_days=settings.eval_window_days,
            engine_version=settings.engine_version,
            force=True,
            **self._owner_kwargs(),
        )

        prepared_dates = [
            parsed for parsed in
            (self.repo.parse_analysis_date_from_snapshot(row.context_snapshot) for row in sample_rows)
            if parsed is not None
        ]
        latest_prepared_sample_date = max(prepared_dates).isoformat() if prepared_dates else None

        eligible_dates = [
            parsed for parsed in
            (self._resolve_analysis_date(candidate) for candidate in candidates)
            if parsed is not None
        ]
        latest_eligible_sample_date = max(eligible_dates).isoformat() if eligible_dates else None

        latest_market_date = stock_rows[-1].date if stock_rows else None
        preparable_indexes = self._select_preparable_rows(stock_rows, eval_window_days=settings.eval_window_days)
        latest_preparable_market_date = stock_rows[preparable_indexes[-1]].date if preparable_indexes else None

        excluded_recent_reason: Optional[str] = None
        excluded_recent_message: Optional[str] = None
        if latest_prepared_sample_date and latest_eligible_sample_date and latest_prepared_sample_date > latest_eligible_sample_date:
            excluded_recent_reason = "maturity_window_not_satisfied"
            excluded_recent_message = (
                f"最新已准备样本到 {latest_prepared_sample_date}，但最近样本尚未满足 {settings.min_age_days} 天成熟期，"
                f"因此本次最新可评估日期只到 {latest_eligible_sample_date}。"
            )
        elif latest_market_date and latest_preparable_market_date and latest_market_date > latest_preparable_market_date:
            excluded_recent_reason = "evaluation_window_not_satisfied"
            excluded_recent_message = (
                f"最新行情到 {latest_market_date.isoformat()}，但评估需要完整的 {settings.eval_window_days} 根未来窗口，"
                f"所以最新可用于样本生成的日期只到 {latest_preparable_market_date.isoformat()}。"
            )
        elif latest_market_date and latest_prepared_sample_date and latest_market_date.isoformat() > latest_prepared_sample_date:
            excluded_recent_reason = "no_newer_analysis_samples"
            excluded_recent_message = (
                f"最新行情到 {latest_market_date.isoformat()}，但没有更晚日期的历史分析样本，"
                f"所以当前已准备样本只到 {latest_prepared_sample_date}。"
            )

        return {
            "latest_prepared_sample_date": latest_prepared_sample_date,
            "latest_eligible_sample_date": latest_eligible_sample_date,
            "excluded_recent_reason": excluded_recent_reason,
            "excluded_recent_message": excluded_recent_message,
        }

    def _recompute_global_summaries_if_needed(self) -> None:
        config = get_config()
        eval_window_days = int(getattr(config, "backtest_eval_window_days", 10))
        engine_version = str(getattr(config, "backtest_engine_version", "v1"))
        self._recompute_summaries_for_window(eval_window_days=eval_window_days, engine_version=engine_version)

    def _recompute_summaries_for_window(self, *, eval_window_days: int, engine_version: str) -> None:
        resolved_owner_id = self.db.require_user_id(self.owner_id)
        with self.db.get_session() as session:
            overall_rows = session.execute(
                select(BacktestResult).where(
                    and_(
                        BacktestResult.owner_id == resolved_owner_id,
                        BacktestResult.eval_window_days == eval_window_days,
                        BacktestResult.engine_version == engine_version,
                    )
                )
            ).scalars().all()
            if not overall_rows:
                self.repo.delete_all_summaries_for_window(
                    eval_window_days=eval_window_days,
                    engine_version=engine_version,
                    owner_id=resolved_owner_id,
                )
                return
            overall_data = BacktestEngine.compute_summary(
                results=overall_rows,
                scope="overall",
                code=OVERALL_SENTINEL_CODE,
                eval_window_days=eval_window_days,
                engine_version=engine_version,
            )
            overall_data.update(self._build_source_metadata_for_result_rows(overall_rows, code=None))
            overall_summary = self._build_summary_model(overall_data, owner_id=resolved_owner_id)
            self.repo.upsert_summary(overall_summary)

            codes = self.repo.list_backtest_codes(
                eval_window_days=eval_window_days,
                engine_version=engine_version,
                owner_id=resolved_owner_id,
            )
            for code in codes:
                rows = session.execute(
                    select(BacktestResult).where(
                        and_(
                            BacktestResult.owner_id == resolved_owner_id,
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
                data.update(self._build_source_metadata_for_result_rows(rows, code=code))
                summary = self._build_summary_model(data, owner_id=resolved_owner_id)
                self.repo.upsert_summary(summary)

    def _recompute_summaries(self, *, touched_codes: List[str], eval_window_days: int, engine_version: str) -> None:
        resolved_owner_id = self.db.require_user_id(self.owner_id)
        with self.db.get_session() as session:
            # overall
            overall_rows = session.execute(
                select(BacktestResult).where(
                    and_(
                        BacktestResult.owner_id == resolved_owner_id,
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
            overall_data.update(self._build_source_metadata_for_result_rows(overall_rows, code=None))
            overall_summary = self._build_summary_model(overall_data, owner_id=resolved_owner_id)
            self.repo.upsert_summary(overall_summary)

            for code in touched_codes:
                rows = session.execute(
                    select(BacktestResult).where(
                        and_(
                            BacktestResult.owner_id == resolved_owner_id,
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
                data.update(self._build_source_metadata_for_result_rows(rows, code=code))
                summary = self._build_summary_model(data, owner_id=resolved_owner_id)
                self.repo.upsert_summary(summary)

    @staticmethod
    def _build_summary_model(summary_data: Dict[str, Any], *, owner_id: str) -> BacktestSummary:
        diagnostics = dict(summary_data.get("diagnostics") or {})
        for key in ("requested_mode", "resolved_source", "fallback_used"):
            if key in summary_data:
                diagnostics[key] = summary_data.get(key)
        return BacktestSummary(
            owner_id=owner_id,
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
            diagnostics_json=json.dumps(diagnostics, ensure_ascii=False),
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
            "requested_mode": summary.get("requested_mode"),
            "resolved_source": summary.get("resolved_source"),
            "fallback_used": summary.get("fallback_used"),
            "execution_assumptions": self._signal_evaluation_assumptions(),
        }

    def _summary_to_dict(self, row: BacktestSummary) -> Dict[str, Any]:
        diagnostics = json.loads(row.diagnostics_json) if row.diagnostics_json else {}
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
            "diagnostics": diagnostics,
            "evaluation_mode": "historical_analysis_evaluation",
            "requested_mode": diagnostics.get("requested_mode"),
            "resolved_source": diagnostics.get("resolved_source"),
            "fallback_used": diagnostics.get("fallback_used"),
            "execution_assumptions": self._signal_evaluation_assumptions(),
        }

    @staticmethod
    def _requested_mode_for_code(code: Optional[str]) -> str:
        normalized_code = str(code or "").strip().upper()
        if normalized_code and normalized_code.isascii() and normalized_code.isalpha():
            return "local_first"
        return "auto"

    @staticmethod
    def _normalize_resolved_source_label(source: Optional[str]) -> Optional[str]:
        normalized = str(source or "").strip()
        if not normalized:
            return None
        lower = normalized.lower()
        if lower == "databasecache":
            return "DatabaseCache"
        if lower in {"local_us_parquet", "localparquet"} or "parquet" in lower or "stooq" in lower:
            return "LocalParquet"
        if "yfinance" in lower:
            return "YfinanceFetcher"
        if "cache" in lower or lower.startswith("db_") or lower == "db":
            return "DatabaseCache"
        return "ProviderAPI"

    def _build_source_metadata_from_fetch_source(self, *, code: str, source: Optional[str]) -> BacktestSourceMetadata:
        requested_mode = self._requested_mode_for_code(code)
        normalized_source = self._normalize_resolved_source_label(source) or "Unknown"
        fallback_used = requested_mode == "local_first" and normalized_source != "LocalParquet"
        return BacktestSourceMetadata(
            requested_mode=requested_mode,
            resolved_source=normalized_source,
            fallback_used=fallback_used,
        )

    def _build_source_metadata_from_runtime_sources(
        self,
        *,
        code: Optional[str],
        runtime_sources: List[str],
        fallback_used: bool,
    ) -> BacktestSourceMetadata:
        requested_mode = self._requested_mode_for_code(code)
        unique_sources: List[str] = []
        for source in runtime_sources:
            normalized = self._normalize_resolved_source_label(source) or source
            if normalized and normalized not in unique_sources:
                unique_sources.append(normalized)
        if not unique_sources:
            resolved_source = "Unknown"
        elif len(unique_sources) == 1:
            resolved_source = unique_sources[0]
        else:
            resolved_source = "MixedFallback"
            fallback_used = True
        return BacktestSourceMetadata(
            requested_mode=requested_mode,
            resolved_source=resolved_source,
            fallback_used=bool(fallback_used),
        )

    def _build_source_metadata_for_stock_rows(
        self,
        *,
        code: str,
        rows: List[StockDaily],
        default_to_cache: bool,
    ) -> BacktestSourceMetadata:
        sources = [str(row.data_source) for row in rows if getattr(row, "data_source", None)]
        if default_to_cache and not sources:
            return self._build_source_metadata_from_runtime_sources(
                code=code,
                runtime_sources=["DatabaseCache"],
                fallback_used=False,
            )
        return self._build_source_metadata_from_runtime_sources(
            code=code,
            runtime_sources=sources,
            fallback_used=len(set(sources)) > 1,
        )

    def _build_source_metadata_for_samples(
        self,
        *,
        code: str,
        sample_rows: List[AnalysisHistory],
    ) -> BacktestSourceMetadata:
        sources: List[str] = []
        for row in sample_rows:
            try:
                raw = json.loads(row.raw_result) if row.raw_result else {}
            except Exception:
                raw = {}
            value = raw.get("market_data_source")
            if value:
                sources.append(str(value))
        if sample_rows and not sources:
            return self._build_source_metadata_from_runtime_sources(
                code=code,
                runtime_sources=["DatabaseCache"],
                fallback_used=False,
            )
        return self._build_source_metadata_from_runtime_sources(
            code=code,
            runtime_sources=sources,
            fallback_used=len(set(sources)) > 1,
        )

    def _build_source_metadata_for_result_rows(
        self,
        rows: List[BacktestResult],
        *,
        code: Optional[str],
    ) -> Dict[str, Any]:
        runtime_sources: List[str] = []
        for row in rows:
            runtime_sources.extend(
                self._collect_market_data_sources(
                    code=row.code,
                    analysis_date=row.analysis_date,
                    eval_window_days=row.eval_window_days,
                )
            )
        metadata = self._build_source_metadata_from_runtime_sources(
            code=code,
            runtime_sources=runtime_sources if runtime_sources else (["DatabaseCache"] if rows else []),
            fallback_used=len(set(runtime_sources)) > 1,
        )
        return {
            "requested_mode": metadata.requested_mode,
            "resolved_source": metadata.resolved_source,
            "fallback_used": metadata.fallback_used,
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
