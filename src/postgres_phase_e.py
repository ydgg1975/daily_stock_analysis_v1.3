# -*- coding: utf-8 -*-
"""Narrow Phase E persistence adapter for PostgreSQL-backed backtest data."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    select,
)
from sqlalchemy.orm import Session, sessionmaker

from src.postgres_phase_a import PhaseABase
from src.postgres_phase_c import PhaseCMarketDataUsageRef

logger = logging.getLogger(__name__)

PhaseEBase = PhaseABase

_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")
_PHASE_E_TABLES = {
    "backtest_runs",
    "backtest_artifacts",
}
_PHASE_E_INDEXES = {
    "idx_backtest_runs_user_created",
}
_ANALYSIS_EVAL_SHADOW_OFFSET = 1_000_000_000_000
_RULE_DETERMINISTIC_SHADOW_OFFSET = 2_000_000_000_000
_RULE_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def phase_e_shadow_run_id(run_type: str, legacy_run_id: int) -> int:
    """Return a deterministic negative shadow id for a legacy SQLite run id."""
    normalized_type = str(run_type or "").strip().lower()
    resolved_legacy_id = int(legacy_run_id)
    if resolved_legacy_id <= 0:
        raise ValueError("legacy_run_id must be positive")
    if normalized_type == "analysis_eval":
        return -(_ANALYSIS_EVAL_SHADOW_OFFSET + resolved_legacy_id)
    if normalized_type == "rule_deterministic":
        return -(_RULE_DETERMINISTIC_SHADOW_OFFSET + resolved_legacy_id)
    raise ValueError(f"Unsupported run_type: {run_type}")


class PhaseEBacktestRun(PhaseEBase):
    __tablename__ = "backtest_runs"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    owner_user_id = Column(String(64), ForeignKey("app_users.id"), nullable=False)
    run_type = Column(Text, nullable=False)
    linked_analysis_session_id = Column(_BIGINT_PK, ForeignKey("analysis_sessions.id"))
    linked_analysis_record_id = Column(_BIGINT_PK, ForeignKey("analysis_records.id"))
    canonical_symbol = Column(Text)
    strategy_family = Column(Text)
    strategy_hash = Column(Text)
    status = Column(Text, nullable=False)
    request_payload = Column(JSON, nullable=False, default=dict)
    metrics_json = Column(JSON, nullable=False, default=dict)
    parsed_strategy_json = Column(JSON, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint(
            "run_type in ('analysis_eval', 'rule_deterministic')",
            name="ck_phase_e_backtest_runs_type",
        ),
    )


class PhaseEBacktestArtifact(PhaseEBase):
    __tablename__ = "backtest_artifacts"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    backtest_run_id = Column(_BIGINT_PK, ForeignKey("backtest_runs.id"), nullable=False, index=True)
    artifact_kind = Column(Text, nullable=False)
    storage_mode = Column(Text, nullable=False, default="inline_json")
    payload_json = Column(JSON, nullable=False, default=dict)
    file_ref_uri = Column(Text)
    content_hash = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("backtest_run_id", "artifact_kind", name="uq_phase_e_backtest_artifacts_run_kind"),
        CheckConstraint(
            "artifact_kind in ('summary', 'evaluation_rows', 'trade_events', 'audit_rows', 'execution_trace', 'comparison', 'equity_curve', 'export_index')",
            name="ck_phase_e_backtest_artifacts_kind",
        ),
        CheckConstraint(
            "storage_mode in ('inline_json', 'external_file_ref')",
            name="ck_phase_e_backtest_artifacts_storage_mode",
        ),
    )


def _phase_e_sql_doc_path() -> Path:
    return Path(__file__).resolve().parent.parent / "docs" / "architecture" / "postgresql-baseline-v1.sql"


def load_phase_e_sql_statements() -> list[str]:
    """Extract only the Phase E DDL statements from the authoritative baseline SQL doc."""
    sql_path = _phase_e_sql_doc_path()
    if not sql_path.exists():
        raise RuntimeError(f"Phase E schema source not found: {sql_path}")

    raw_text = sql_path.read_text(encoding="utf-8")
    text = "\n".join(line for line in raw_text.splitlines() if not line.lstrip().startswith("--"))
    statements = [stmt.strip() for stmt in text.split(";") if stmt.strip()]

    selected: list[str] = []
    table_pattern = re.compile(r"^create table if not exists\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)
    index_pattern = re.compile(r"^create index if not exists\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)

    for statement in statements:
        normalized = re.sub(r"\s+", " ", statement).strip()
        table_match = table_pattern.match(normalized)
        if table_match and table_match.group(1).lower() in _PHASE_E_TABLES:
            selected.append(f"{statement};")
            continue

        index_match = index_pattern.match(normalized)
        if index_match and index_match.group(1).lower() in _PHASE_E_INDEXES:
            selected.append(f"{statement};")

    if not selected:
        raise RuntimeError(f"No Phase E schema statements found in {sql_path}")
    return selected


class PostgresPhaseEStore:
    """Narrow storage adapter for the PostgreSQL Phase E baseline."""

    def __init__(self, db_url: str, *, auto_apply_schema: bool = True):
        if not str(db_url or "").strip():
            raise ValueError("db_url is required for PostgresPhaseEStore")

        self.db_url = str(db_url).strip()
        self._engine = create_engine(
            self.db_url,
            echo=False,
            pool_pre_ping=True,
        )
        self._SessionLocal = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

        if auto_apply_schema:
            self.apply_schema()

    def dispose(self) -> None:
        self._engine.dispose()

    def apply_schema(self) -> None:
        dialect = self._engine.dialect.name
        if dialect == "postgresql":
            statements = load_phase_e_sql_statements()
            with self._engine.begin() as conn:
                for statement in statements:
                    conn.exec_driver_sql(statement)
            return

        PhaseEBase.metadata.create_all(self._engine)

    def get_session(self) -> Session:
        return self._SessionLocal()

    @contextmanager
    def session_scope(self):
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _safe_json_value(value: Any, *, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            if isinstance(default, dict) and isinstance(value, dict):
                return dict(value)
            if isinstance(default, list) and isinstance(value, list):
                return list(value)
            return default
        if isinstance(value, str):
            raw_text = value.strip()
            if not raw_text:
                return default
            try:
                parsed = json.loads(raw_text)
            except Exception:
                return default
            if isinstance(default, dict) and isinstance(parsed, dict):
                return parsed
            if isinstance(default, list) and isinstance(parsed, list):
                return parsed
        return default

    @staticmethod
    def _safe_date(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return None
        return str(value or "").strip() or None

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _json_hash(payload: Any) -> str:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _replace_artifacts(
        self,
        session: Session,
        *,
        backtest_run_id: int,
        artifacts: Sequence[tuple[str, Any]],
    ) -> None:
        session.execute(
            delete(PhaseEBacktestArtifact).where(
                PhaseEBacktestArtifact.backtest_run_id == int(backtest_run_id)
            )
        )
        for artifact_kind, payload in artifacts:
            session.add(
                PhaseEBacktestArtifact(
                    backtest_run_id=int(backtest_run_id),
                    artifact_kind=str(artifact_kind),
                    storage_mode="inline_json",
                    payload_json=payload,
                    content_hash=self._json_hash(payload),
                    created_at=datetime.now(),
                )
            )

    def _delete_usage_refs(self, session: Session, *, run_ids: Sequence[int]) -> int:
        if not run_ids:
            return 0
        return int(
            session.execute(
                delete(PhaseCMarketDataUsageRef).where(
                    PhaseCMarketDataUsageRef.entity_type == "backtest_run",
                    PhaseCMarketDataUsageRef.entity_id.in_([int(run_id) for run_id in run_ids]),
                )
            ).rowcount
            or 0
        )

    @staticmethod
    def _serialize_backtest_result(row: Any) -> Dict[str, Any]:
        return {
            "analysis_history_id": int(getattr(row, "analysis_history_id", 0) or 0),
            "code": str(getattr(row, "code", "") or "").strip().upper() or None,
            "analysis_date": PostgresPhaseEStore._safe_date(getattr(row, "analysis_date", None)),
            "eval_window_days": int(getattr(row, "eval_window_days", 0) or 0),
            "engine_version": str(getattr(row, "engine_version", "") or "").strip() or None,
            "eval_status": str(getattr(row, "eval_status", "") or "").strip() or None,
            "evaluated_at": (
                getattr(row, "evaluated_at", None).isoformat()
                if getattr(row, "evaluated_at", None) is not None
                else None
            ),
            "operation_advice": getattr(row, "operation_advice", None),
            "position_recommendation": getattr(row, "position_recommendation", None),
            "start_price": PostgresPhaseEStore._safe_float(getattr(row, "start_price", None)),
            "end_close": PostgresPhaseEStore._safe_float(getattr(row, "end_close", None)),
            "max_high": PostgresPhaseEStore._safe_float(getattr(row, "max_high", None)),
            "min_low": PostgresPhaseEStore._safe_float(getattr(row, "min_low", None)),
            "stock_return_pct": PostgresPhaseEStore._safe_float(getattr(row, "stock_return_pct", None)),
            "direction_expected": getattr(row, "direction_expected", None),
            "direction_correct": getattr(row, "direction_correct", None),
            "outcome": getattr(row, "outcome", None),
            "stop_loss": PostgresPhaseEStore._safe_float(getattr(row, "stop_loss", None)),
            "take_profit": PostgresPhaseEStore._safe_float(getattr(row, "take_profit", None)),
            "hit_stop_loss": getattr(row, "hit_stop_loss", None),
            "hit_take_profit": getattr(row, "hit_take_profit", None),
            "first_hit": getattr(row, "first_hit", None),
            "first_hit_date": PostgresPhaseEStore._safe_date(getattr(row, "first_hit_date", None)),
            "first_hit_trading_days": PostgresPhaseEStore._safe_int(getattr(row, "first_hit_trading_days", None)),
            "simulated_entry_price": PostgresPhaseEStore._safe_float(getattr(row, "simulated_entry_price", None)),
            "simulated_exit_price": PostgresPhaseEStore._safe_float(getattr(row, "simulated_exit_price", None)),
            "simulated_exit_reason": getattr(row, "simulated_exit_reason", None),
            "simulated_return_pct": PostgresPhaseEStore._safe_float(getattr(row, "simulated_return_pct", None)),
        }

    @staticmethod
    def _serialize_backtest_summary(row: Any) -> Dict[str, Any]:
        diagnostics = PostgresPhaseEStore._safe_json_value(getattr(row, "diagnostics_json", None), default={})
        advice_breakdown = PostgresPhaseEStore._safe_json_value(getattr(row, "advice_breakdown_json", None), default={})
        return {
            "scope": str(getattr(row, "scope", "") or "").strip() or None,
            "code": getattr(row, "code", None),
            "eval_window_days": int(getattr(row, "eval_window_days", 0) or 0),
            "engine_version": str(getattr(row, "engine_version", "") or "").strip() or None,
            "computed_at": (
                getattr(row, "computed_at", None).isoformat()
                if getattr(row, "computed_at", None) is not None
                else None
            ),
            "total_evaluations": int(getattr(row, "total_evaluations", 0) or 0),
            "completed_count": int(getattr(row, "completed_count", 0) or 0),
            "insufficient_count": int(getattr(row, "insufficient_count", 0) or 0),
            "long_count": int(getattr(row, "long_count", 0) or 0),
            "cash_count": int(getattr(row, "cash_count", 0) or 0),
            "win_count": int(getattr(row, "win_count", 0) or 0),
            "loss_count": int(getattr(row, "loss_count", 0) or 0),
            "neutral_count": int(getattr(row, "neutral_count", 0) or 0),
            "direction_accuracy_pct": PostgresPhaseEStore._safe_float(getattr(row, "direction_accuracy_pct", None)),
            "win_rate_pct": PostgresPhaseEStore._safe_float(getattr(row, "win_rate_pct", None)),
            "neutral_rate_pct": PostgresPhaseEStore._safe_float(getattr(row, "neutral_rate_pct", None)),
            "avg_stock_return_pct": PostgresPhaseEStore._safe_float(getattr(row, "avg_stock_return_pct", None)),
            "avg_simulated_return_pct": PostgresPhaseEStore._safe_float(getattr(row, "avg_simulated_return_pct", None)),
            "stop_loss_trigger_rate": PostgresPhaseEStore._safe_float(getattr(row, "stop_loss_trigger_rate", None)),
            "take_profit_trigger_rate": PostgresPhaseEStore._safe_float(getattr(row, "take_profit_trigger_rate", None)),
            "ambiguous_rate": PostgresPhaseEStore._safe_float(getattr(row, "ambiguous_rate", None)),
            "avg_days_to_first_hit": PostgresPhaseEStore._safe_float(getattr(row, "avg_days_to_first_hit", None)),
            "advice_breakdown": advice_breakdown,
            "diagnostics": diagnostics,
        }

    @staticmethod
    def _serialize_rule_backtest_trade(row: Any) -> Dict[str, Any]:
        return {
            "trade_index": int(getattr(row, "trade_index", 0) or 0),
            "code": str(getattr(row, "code", "") or "").strip().upper() or None,
            "entry_date": PostgresPhaseEStore._safe_date(getattr(row, "entry_date", None)),
            "exit_date": PostgresPhaseEStore._safe_date(getattr(row, "exit_date", None)),
            "entry_price": PostgresPhaseEStore._safe_float(getattr(row, "entry_price", None)),
            "exit_price": PostgresPhaseEStore._safe_float(getattr(row, "exit_price", None)),
            "entry_signal": getattr(row, "entry_signal", None),
            "exit_signal": getattr(row, "exit_signal", None),
            "return_pct": PostgresPhaseEStore._safe_float(getattr(row, "return_pct", None)),
            "holding_days": PostgresPhaseEStore._safe_int(getattr(row, "holding_days", None)),
            "entry_rule": PostgresPhaseEStore._safe_json_value(getattr(row, "entry_rule_json", None), default={}),
            "exit_rule": PostgresPhaseEStore._safe_json_value(getattr(row, "exit_rule_json", None), default={}),
            "notes": PostgresPhaseEStore._safe_json_value(getattr(row, "notes", None), default={}),
        }

    @staticmethod
    def _extract_strategy_family(parsed_strategy_json: Dict[str, Any]) -> Optional[str]:
        if not parsed_strategy_json:
            return None
        strategy_spec = parsed_strategy_json.get("strategy_spec")
        if isinstance(strategy_spec, dict):
            value = str(strategy_spec.get("strategy_family") or strategy_spec.get("strategy_type") or "").strip()
            if value:
                return value
        value = str(parsed_strategy_json.get("strategy_kind") or "").strip()
        return value or None

    def upsert_analysis_eval_run_shadow(
        self,
        *,
        run_row: Any,
        result_rows: Sequence[Any],
        summary_rows: Sequence[Any],
    ) -> Optional[PhaseEBacktestRun]:
        legacy_run_id = getattr(run_row, "id", None)
        if run_row is None or legacy_run_id is None:
            return None

        summary_json = self._safe_json_value(getattr(run_row, "summary_json", None), default={})
        serialized_summaries = [self._serialize_backtest_summary(row) for row in summary_rows]
        stock_summary = next(
            (item for item in serialized_summaries if item.get("scope") == "stock"),
            None,
        )
        overall_summary = next(
            (item for item in serialized_summaries if item.get("scope") == "overall"),
            None,
        )
        request_payload = {
            "legacy_run_id": int(legacy_run_id),
            "legacy_source_table": "backtest_runs",
            "eval_window_days": int(getattr(run_row, "eval_window_days", 0) or 0),
            "min_age_days": int(getattr(run_row, "min_age_days", 0) or 0),
            "force": bool(getattr(run_row, "force", False)),
        }
        metrics_json = {
            "processed": int(getattr(run_row, "processed", 0) or 0),
            "saved": int(getattr(run_row, "saved", 0) or 0),
            "completed": int(getattr(run_row, "completed", 0) or 0),
            "insufficient": int(getattr(run_row, "insufficient", 0) or 0),
            "errors": int(getattr(run_row, "errors", 0) or 0),
            "candidate_count": int(getattr(run_row, "candidate_count", 0) or 0),
            "result_count": int(getattr(run_row, "result_count", 0) or 0),
            "total_evaluations": int(getattr(run_row, "total_evaluations", 0) or 0),
            "completed_count": int(getattr(run_row, "completed_count", 0) or 0),
            "insufficient_count": int(getattr(run_row, "insufficient_count", 0) or 0),
            "long_count": int(getattr(run_row, "long_count", 0) or 0),
            "cash_count": int(getattr(run_row, "cash_count", 0) or 0),
            "win_count": int(getattr(run_row, "win_count", 0) or 0),
            "loss_count": int(getattr(run_row, "loss_count", 0) or 0),
            "neutral_count": int(getattr(run_row, "neutral_count", 0) or 0),
            "win_rate_pct": self._safe_float(getattr(run_row, "win_rate_pct", None)),
            "avg_stock_return_pct": self._safe_float(getattr(run_row, "avg_stock_return_pct", None)),
            "avg_simulated_return_pct": self._safe_float(getattr(run_row, "avg_simulated_return_pct", None)),
            "direction_accuracy_pct": self._safe_float(getattr(run_row, "direction_accuracy_pct", None)),
            "no_result_reason": getattr(run_row, "no_result_reason", None),
            "no_result_message": getattr(run_row, "no_result_message", None),
        }
        artifacts = [
            (
                "summary",
                {
                    "run_summary": summary_json,
                    "stock_summary": stock_summary,
                    "overall_summary": overall_summary,
                },
            ),
            (
                "evaluation_rows",
                {
                    "rows": [self._serialize_backtest_result(row) for row in result_rows],
                },
            ),
        ]
        shadow_id = phase_e_shadow_run_id("analysis_eval", int(legacy_run_id))
        owner_user_id = str(getattr(run_row, "owner_id", "") or "").strip()
        if not owner_user_id:
            raise ValueError("owner_id is required for analysis_eval Phase E shadow sync")

        with self.session_scope() as session:
            row = session.execute(
                select(PhaseEBacktestRun).where(PhaseEBacktestRun.id == shadow_id).limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = PhaseEBacktestRun(id=shadow_id, owner_user_id=owner_user_id)
                session.add(row)
            row.run_type = "analysis_eval"
            row.owner_user_id = owner_user_id
            row.linked_analysis_session_id = None
            row.linked_analysis_record_id = None
            row.canonical_symbol = str(getattr(run_row, "code", "") or "").strip().upper() or None
            row.strategy_family = "historical_analysis_evaluation"
            row.strategy_hash = None
            row.status = str(getattr(run_row, "status", "") or "").strip().lower() or "completed"
            row.request_payload = request_payload
            row.metrics_json = metrics_json
            row.parsed_strategy_json = {}
            row.started_at = getattr(run_row, "run_at", None) or datetime.now()
            row.completed_at = getattr(run_row, "completed_at", None)
            row.created_at = getattr(run_row, "run_at", None) or datetime.now()
            row.updated_at = getattr(run_row, "completed_at", None) or getattr(run_row, "run_at", None) or datetime.now()
            session.flush()
            self._replace_artifacts(session, backtest_run_id=int(row.id), artifacts=artifacts)
            session.flush()
            return row

    def upsert_rule_backtest_run_shadow(
        self,
        *,
        run_row: Any,
        trade_rows: Sequence[Any],
    ) -> Optional[PhaseEBacktestRun]:
        legacy_run_id = getattr(run_row, "id", None)
        if run_row is None or legacy_run_id is None:
            return None

        owner_user_id = str(getattr(run_row, "owner_id", "") or "").strip()
        if not owner_user_id:
            raise ValueError("owner_id is required for rule_deterministic Phase E shadow sync")

        summary_json = self._safe_json_value(getattr(run_row, "summary_json", None), default={})
        parsed_strategy_json = self._safe_json_value(getattr(run_row, "parsed_strategy_json", None), default={})
        request_section = dict(summary_json.get("request") or {}) if isinstance(summary_json.get("request"), dict) else {}
        metrics_section = dict(summary_json.get("metrics") or {}) if isinstance(summary_json.get("metrics"), dict) else {}
        visualization_section = dict(summary_json.get("visualization") or {}) if isinstance(summary_json.get("visualization"), dict) else {}
        comparison_payload = dict(visualization_section.get("comparison") or {}) if isinstance(visualization_section.get("comparison"), dict) else {}
        audit_rows = list(visualization_section.get("audit_rows") or []) if isinstance(visualization_section.get("audit_rows"), list) else []
        execution_trace = dict(summary_json.get("execution_trace") or {}) if isinstance(summary_json.get("execution_trace"), dict) else {}
        equity_curve = self._safe_json_value(getattr(run_row, "equity_curve_json", None), default=[])

        metrics_json = dict(metrics_section)
        metrics_json.setdefault("trade_count", int(getattr(run_row, "trade_count", 0) or 0))
        metrics_json.setdefault("win_count", int(getattr(run_row, "win_count", 0) or 0))
        metrics_json.setdefault("loss_count", int(getattr(run_row, "loss_count", 0) or 0))
        metrics_json.setdefault("total_return_pct", self._safe_float(getattr(run_row, "total_return_pct", None)))
        metrics_json.setdefault("win_rate_pct", self._safe_float(getattr(run_row, "win_rate_pct", None)))
        metrics_json.setdefault("avg_trade_return_pct", self._safe_float(getattr(run_row, "avg_trade_return_pct", None)))
        metrics_json.setdefault("max_drawdown_pct", self._safe_float(getattr(run_row, "max_drawdown_pct", None)))
        metrics_json.setdefault("avg_holding_days", self._safe_float(getattr(run_row, "avg_holding_days", None)))
        metrics_json.setdefault("final_equity", self._safe_float(getattr(run_row, "final_equity", None)))
        metrics_json.setdefault("no_result_reason", getattr(run_row, "no_result_reason", None))
        metrics_json.setdefault("no_result_message", getattr(run_row, "no_result_message", None))

        request_payload = dict(request_section)
        request_payload.update(
            {
                "legacy_run_id": int(legacy_run_id),
                "legacy_source_table": "rule_backtest_runs",
                "lookback_bars": int(getattr(run_row, "lookback_bars", 0) or request_section.get("lookback_bars") or 0),
                "initial_capital": self._safe_float(getattr(run_row, "initial_capital", None)),
                "fee_bps": self._safe_float(getattr(run_row, "fee_bps", None)),
                "start_date": request_section.get("start_date"),
                "end_date": request_section.get("end_date"),
                "benchmark_mode": request_section.get("benchmark_mode"),
                "benchmark_code": request_section.get("benchmark_code"),
                "confirmed": bool(request_section.get("confirmed", False)),
            }
        )

        normalized_status = str(getattr(run_row, "status", "") or "").strip().lower() or "completed"
        artifacts: list[tuple[str, Any]] = [("summary", summary_json)]
        if trade_rows or normalized_status in _RULE_TERMINAL_STATUSES:
            artifacts.append(
                (
                    "trade_events",
                    {"trades": [self._serialize_rule_backtest_trade(row) for row in trade_rows]},
                )
            )
        if audit_rows:
            artifacts.append(("audit_rows", {"rows": audit_rows}))
        if execution_trace:
            artifacts.append(("execution_trace", execution_trace))
        if comparison_payload:
            artifacts.append(("comparison", comparison_payload))
        if equity_curve or visualization_section.get("daily_return_series") or visualization_section.get("exposure_curve"):
            artifacts.append(
                (
                    "equity_curve",
                    {
                        "equity_curve": equity_curve,
                        "daily_return_series": list(visualization_section.get("daily_return_series") or []),
                        "exposure_curve": list(visualization_section.get("exposure_curve") or []),
                    },
                )
            )

        shadow_id = phase_e_shadow_run_id("rule_deterministic", int(legacy_run_id))
        with self.session_scope() as session:
            row = session.execute(
                select(PhaseEBacktestRun).where(PhaseEBacktestRun.id == shadow_id).limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = PhaseEBacktestRun(id=shadow_id, owner_user_id=owner_user_id)
                session.add(row)
            row.run_type = "rule_deterministic"
            row.owner_user_id = owner_user_id
            row.linked_analysis_session_id = None
            row.linked_analysis_record_id = None
            row.canonical_symbol = str(getattr(run_row, "code", "") or "").strip().upper() or None
            row.strategy_family = self._extract_strategy_family(parsed_strategy_json)
            row.strategy_hash = str(getattr(run_row, "strategy_hash", "") or "").strip() or None
            row.status = normalized_status
            row.request_payload = request_payload
            row.metrics_json = metrics_json
            row.parsed_strategy_json = parsed_strategy_json
            row.started_at = getattr(run_row, "run_at", None) or datetime.now()
            row.completed_at = getattr(run_row, "completed_at", None)
            row.created_at = getattr(run_row, "run_at", None) or datetime.now()
            row.updated_at = getattr(run_row, "completed_at", None) or datetime.now()
            session.flush()
            self._replace_artifacts(session, backtest_run_id=int(row.id), artifacts=artifacts)
            session.flush()
            return row

    def delete_backtest_shadows_by_code(
        self,
        *,
        run_type: str,
        code: str,
        owner_user_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        normalized_type = str(run_type or "").strip().lower()
        normalized_code = str(code or "").strip().upper()
        normalized_owner = str(owner_user_id or "").strip()
        with self.session_scope() as session:
            query = select(PhaseEBacktestRun.id).where(PhaseEBacktestRun.run_type == normalized_type)
            query = query.where(PhaseEBacktestRun.canonical_symbol == normalized_code)
            if not include_all_owners:
                if not normalized_owner:
                    return 0
                query = query.where(PhaseEBacktestRun.owner_user_id == normalized_owner)
            run_ids = [int(value) for value in session.execute(query).scalars().all()]
            if not run_ids:
                return 0
            self._delete_usage_refs(session, run_ids=run_ids)
            session.execute(
                delete(PhaseEBacktestArtifact).where(
                    PhaseEBacktestArtifact.backtest_run_id.in_(run_ids)
                )
            )
            deleted = session.execute(
                delete(PhaseEBacktestRun).where(PhaseEBacktestRun.id.in_(run_ids))
            ).rowcount or 0
            return int(deleted)

    def clear_non_bootstrap_state(self, user_ids: Sequence[str]) -> Dict[str, int]:
        normalized_user_ids = [str(value).strip() for value in user_ids if str(value or "").strip()]
        if not normalized_user_ids:
            return {
                "backtest_runs": 0,
                "backtest_artifacts": 0,
                "market_data_usage_refs": 0,
            }

        with self.session_scope() as session:
            run_ids = [
                int(value)
                for value in session.execute(
                    select(PhaseEBacktestRun.id).where(
                        PhaseEBacktestRun.owner_user_id.in_(normalized_user_ids)
                    )
                ).scalars().all()
            ]
            usage_refs_deleted = self._delete_usage_refs(session, run_ids=run_ids)
            artifacts_deleted = int(
                session.execute(
                    delete(PhaseEBacktestArtifact).where(
                        PhaseEBacktestArtifact.backtest_run_id.in_(run_ids)
                    )
                ).rowcount
                or 0
            ) if run_ids else 0
            runs_deleted = int(
                session.execute(
                    delete(PhaseEBacktestRun).where(
                        PhaseEBacktestRun.owner_user_id.in_(normalized_user_ids)
                    )
                ).rowcount
                or 0
            )
            return {
                "backtest_runs": runs_deleted,
                "backtest_artifacts": artifacts_deleted,
                "market_data_usage_refs": usage_refs_deleted,
            }
