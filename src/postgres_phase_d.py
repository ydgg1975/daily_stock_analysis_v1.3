# -*- coding: utf-8 -*-
"""Narrow Phase D persistence adapter for PostgreSQL-backed scanner/watchlist data."""

from __future__ import annotations

import json
import logging
import re
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    select,
)
from sqlalchemy.orm import Session, sessionmaker

from src.multi_user import OWNERSHIP_SCOPE_SYSTEM, OWNERSHIP_SCOPE_USER, normalize_scope
from src.postgres_phase_a import PhaseABase

logger = logging.getLogger(__name__)

PhaseDBase = PhaseABase

_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")
_PHASE_D_TABLES = {
    "scanner_runs",
    "scanner_candidates",
    "watchlists",
    "watchlist_items",
}
_PHASE_D_INDEXES = {
    "idx_scanner_runs_scope_created",
    "idx_scanner_candidates_symbol_created",
    "idx_watchlists_scope_date",
}
_ALLOWED_TRIGGER_MODES = {"manual", "scheduled", "cli", "api", "scheduler"}


class PhaseDScannerRun(PhaseDBase):
    __tablename__ = "scanner_runs"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    owner_user_id = Column(String(64), ForeignKey("app_users.id"))
    scope = Column(String(16), nullable=False)
    market = Column(Text, nullable=False)
    profile_key = Column(Text, nullable=False)
    universe_name = Column(Text, nullable=False)
    trigger_mode = Column(Text, nullable=False)
    request_source = Column(Text)
    status = Column(Text, nullable=False)
    headline = Column(Text)
    shortlist_size = Column(Integer, nullable=False, default=0)
    universe_size = Column(Integer, nullable=False, default=0)
    preselected_size = Column(Integer, nullable=False, default=0)
    evaluated_size = Column(Integer, nullable=False, default=0)
    source_summary = Column(Text)
    summary_json = Column(JSON, nullable=False, default=dict)
    diagnostics_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    completed_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("scope in ('user', 'system')", name="ck_phase_d_scanner_runs_scope"),
        CheckConstraint(
            "trigger_mode in ('manual', 'scheduled', 'cli', 'api', 'scheduler')",
            name="ck_phase_d_scanner_runs_trigger_mode",
        ),
        CheckConstraint(
            "(scope = 'system' and owner_user_id is null) or (scope = 'user' and owner_user_id is not null)",
            name="ck_phase_d_scanner_runs_owner_scope",
        ),
    )


class PhaseDScannerCandidate(PhaseDBase):
    __tablename__ = "scanner_candidates"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    scanner_run_id = Column(_BIGINT_PK, ForeignKey("scanner_runs.id"), nullable=False, index=True)
    canonical_symbol = Column(Text, nullable=False)
    display_name = Column(Text)
    rank = Column(Integer, nullable=False)
    score = Column(Numeric(18, 6), nullable=False)
    quality_hint = Column(Text)
    reason_summary = Column(Text)
    candidate_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("scanner_run_id", "rank", name="uq_phase_d_scanner_candidates_run_rank"),
        UniqueConstraint(
            "scanner_run_id",
            "canonical_symbol",
            name="uq_phase_d_scanner_candidates_run_symbol",
        ),
    )


class PhaseDWatchlist(PhaseDBase):
    __tablename__ = "watchlists"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    owner_user_id = Column(String(64), ForeignKey("app_users.id"))
    scope = Column(String(16), nullable=False)
    market = Column(Text, nullable=False)
    profile_key = Column(Text, nullable=False)
    watchlist_date = Column(Date, nullable=False)
    source_scanner_run_id = Column(_BIGINT_PK, ForeignKey("scanner_runs.id"))
    status = Column(Text, nullable=False, default="active")
    headline = Column(Text)
    notification_status = Column(Text)
    notification_summary = Column(JSON, nullable=False, default=dict)
    comparison_summary = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint("scope in ('user', 'system')", name="ck_phase_d_watchlists_scope"),
        CheckConstraint(
            "status in ('active', 'archived', 'empty', 'failed')",
            name="ck_phase_d_watchlists_status",
        ),
        CheckConstraint(
            "(scope = 'system' and owner_user_id is null) or (scope = 'user' and owner_user_id is not null)",
            name="ck_phase_d_watchlists_owner_scope",
        ),
    )


class PhaseDWatchlistItem(PhaseDBase):
    __tablename__ = "watchlist_items"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    watchlist_id = Column(_BIGINT_PK, ForeignKey("watchlists.id"), nullable=False, index=True)
    source_scanner_candidate_id = Column(_BIGINT_PK, ForeignKey("scanner_candidates.id"))
    canonical_symbol = Column(Text, nullable=False)
    display_name = Column(Text)
    rank = Column(Integer, nullable=False)
    score = Column(Numeric(18, 6))
    selection_reason = Column(Text)
    watch_context = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("watchlist_id", "rank", name="uq_phase_d_watchlist_items_rank"),
        UniqueConstraint(
            "watchlist_id",
            "canonical_symbol",
            name="uq_phase_d_watchlist_items_symbol",
        ),
    )


def _phase_d_sql_doc_path() -> Path:
    return Path(__file__).resolve().parent.parent / "docs" / "architecture" / "postgresql-baseline-v1.sql"


def load_phase_d_sql_statements() -> list[str]:
    """Extract only the Phase D DDL statements from the authoritative baseline SQL doc."""
    sql_path = _phase_d_sql_doc_path()
    if not sql_path.exists():
        raise RuntimeError(f"Phase D schema source not found: {sql_path}")

    raw_text = sql_path.read_text(encoding="utf-8")
    text = "\n".join(line for line in raw_text.splitlines() if not line.lstrip().startswith("--"))
    statements = [stmt.strip() for stmt in text.split(";") if stmt.strip()]

    selected: list[str] = []
    table_pattern = re.compile(r"^create table if not exists\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)
    index_pattern = re.compile(r"^create index if not exists\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)

    for statement in statements:
        normalized = re.sub(r"\s+", " ", statement).strip()
        table_match = table_pattern.match(normalized)
        if table_match and table_match.group(1).lower() in _PHASE_D_TABLES:
            selected.append(f"{statement};")
            continue

        index_match = index_pattern.match(normalized)
        if index_match and index_match.group(1).lower() in _PHASE_D_INDEXES:
            selected.append(f"{statement};")

    if not selected:
        raise RuntimeError(f"No Phase D schema statements found in {sql_path}")
    return selected


class PostgresPhaseDStore:
    """Narrow storage adapter for the PostgreSQL Phase D baseline."""

    def __init__(self, db_url: str, *, auto_apply_schema: bool = True):
        if not str(db_url or "").strip():
            raise ValueError("db_url is required for PostgresPhaseDStore")

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
            statements = load_phase_d_sql_statements()
            with self._engine.begin() as conn:
                for statement in statements:
                    conn.exec_driver_sql(statement)
            return

        PhaseDBase.metadata.create_all(self._engine)

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
    def _safe_json_load(value: Any, *, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            if isinstance(default, dict) and isinstance(value, dict):
                return dict(value)
            if isinstance(default, list) and isinstance(value, list):
                return list(value)
            return default
        if isinstance(value, str):
            text_value = value.strip()
            if not text_value:
                return default
            try:
                parsed = json.loads(text_value)
            except Exception:
                return default
            if isinstance(default, dict) and isinstance(parsed, dict):
                return parsed
            if isinstance(default, list) and isinstance(parsed, list):
                return parsed
        return default

    @staticmethod
    def _normalize_scope(scope: Any, *, owner_user_id: Optional[str]) -> str:
        normalized = normalize_scope(scope, default=OWNERSHIP_SCOPE_USER)
        if normalized == OWNERSHIP_SCOPE_SYSTEM:
            return OWNERSHIP_SCOPE_SYSTEM
        if owner_user_id:
            return OWNERSHIP_SCOPE_USER
        return OWNERSHIP_SCOPE_SYSTEM

    @staticmethod
    def _normalize_trigger_mode(trigger_mode: Any, *, scope: str) -> str:
        normalized = str(trigger_mode or "").strip().lower()
        if normalized in _ALLOWED_TRIGGER_MODES:
            return normalized
        return "scheduled" if scope == OWNERSHIP_SCOPE_SYSTEM else "manual"

    @staticmethod
    def _parse_date(value: Any, *, fallback: Optional[datetime]) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        text_value = str(value or "").strip()
        if text_value:
            try:
                return date.fromisoformat(text_value[:10])
            except Exception:
                pass
        if isinstance(fallback, datetime):
            return fallback.date()
        return datetime.now().date()

    @staticmethod
    def _watchlist_status(*, run_status: Any, shortlist_size: Any) -> str:
        normalized_status = str(run_status or "").strip().lower()
        if normalized_status == "failed":
            return "failed"
        if int(shortlist_size or 0) <= 0:
            return "empty"
        return "active"

    def _build_candidate_payload(self, candidate_row: Any) -> Dict[str, Any]:
        return {
            "reasons": self._safe_json_load(getattr(candidate_row, "reasons_json", None), default=[]),
            "key_metrics": self._safe_json_load(getattr(candidate_row, "key_metrics_json", None), default=[]),
            "feature_signals": self._safe_json_load(
                getattr(candidate_row, "feature_signals_json", None),
                default=[],
            ),
            "risk_notes": self._safe_json_load(getattr(candidate_row, "risk_notes_json", None), default=[]),
            "watch_context": self._safe_json_load(getattr(candidate_row, "watch_context_json", None), default=[]),
            "boards": self._safe_json_load(getattr(candidate_row, "boards_json", None), default=[]),
            "diagnostics": self._safe_json_load(getattr(candidate_row, "diagnostics_json", None), default={}),
        }

    def upsert_scanner_run_shadow(
        self,
        *,
        run_row: Any,
        candidate_rows: Sequence[Any],
    ) -> Optional[PhaseDScannerRun]:
        run_id = getattr(run_row, "id", None)
        if run_row is None or run_id is None:
            return None

        owner_user_id = str(getattr(run_row, "owner_id", "") or "").strip() or None
        scope = self._normalize_scope(getattr(run_row, "scope", None), owner_user_id=owner_user_id)
        if scope == OWNERSHIP_SCOPE_SYSTEM:
            owner_user_id = None

        summary_json = self._safe_json_load(getattr(run_row, "summary_json", None), default={})
        diagnostics_json = self._safe_json_load(getattr(run_row, "diagnostics_json", None), default={})
        operation_payload = (
            diagnostics_json.get("operation")
            if isinstance(diagnostics_json.get("operation"), dict)
            else {}
        )
        trigger_mode = self._normalize_trigger_mode(
            summary_json.get("trigger_mode") or operation_payload.get("trigger_mode"),
            scope=scope,
        )
        request_source = (
            str(summary_json.get("request_source") or operation_payload.get("request_source") or "").strip()
            or None
        )
        headline = str(summary_json.get("headline") or "").strip() or None
        created_at = getattr(run_row, "run_at", None) or datetime.now()
        completed_at = getattr(run_row, "completed_at", None)

        with self.session_scope() as session:
            run = session.execute(
                select(PhaseDScannerRun).where(PhaseDScannerRun.id == int(run_id)).limit(1)
            ).scalar_one_or_none()
            if run is None:
                run = PhaseDScannerRun(
                    id=int(run_id),
                    owner_user_id=owner_user_id,
                    scope=scope,
                    market=str(getattr(run_row, "market", "") or "").strip().lower(),
                    profile_key=str(getattr(run_row, "profile", "") or "").strip().lower(),
                    universe_name=str(getattr(run_row, "universe_name", "") or "").strip(),
                    trigger_mode=trigger_mode,
                    request_source=request_source,
                    status=str(getattr(run_row, "status", "") or "").strip().lower() or "completed",
                    headline=headline,
                    shortlist_size=int(getattr(run_row, "shortlist_size", 0) or 0),
                    universe_size=int(getattr(run_row, "universe_size", 0) or 0),
                    preselected_size=int(getattr(run_row, "preselected_size", 0) or 0),
                    evaluated_size=int(getattr(run_row, "evaluated_size", 0) or 0),
                    source_summary=getattr(run_row, "source_summary", None),
                    summary_json=summary_json,
                    diagnostics_json=diagnostics_json,
                    created_at=created_at,
                    completed_at=completed_at,
                )
                session.add(run)
            else:
                run.owner_user_id = owner_user_id
                run.scope = scope
                run.market = str(getattr(run_row, "market", "") or "").strip().lower()
                run.profile_key = str(getattr(run_row, "profile", "") or "").strip().lower()
                run.universe_name = str(getattr(run_row, "universe_name", "") or "").strip()
                run.trigger_mode = trigger_mode
                run.request_source = request_source
                run.status = str(getattr(run_row, "status", "") or "").strip().lower() or run.status
                run.headline = headline
                run.shortlist_size = int(getattr(run_row, "shortlist_size", 0) or 0)
                run.universe_size = int(getattr(run_row, "universe_size", 0) or 0)
                run.preselected_size = int(getattr(run_row, "preselected_size", 0) or 0)
                run.evaluated_size = int(getattr(run_row, "evaluated_size", 0) or 0)
                run.source_summary = getattr(run_row, "source_summary", None)
                run.summary_json = summary_json
                run.diagnostics_json = diagnostics_json
                run.created_at = created_at
                run.completed_at = completed_at
            session.flush()

            watchlist = session.execute(
                select(PhaseDWatchlist)
                .where(PhaseDWatchlist.source_scanner_run_id == run.id)
                .limit(1)
            ).scalar_one_or_none()
            if watchlist is not None:
                session.execute(
                    delete(PhaseDWatchlistItem).where(
                        PhaseDWatchlistItem.watchlist_id == watchlist.id
                    )
                )

            session.execute(
                delete(PhaseDScannerCandidate).where(
                    PhaseDScannerCandidate.scanner_run_id == run.id
                )
            )
            candidate_id_map: Dict[int, int] = {}
            for candidate_row in candidate_rows:
                candidate_id = getattr(candidate_row, "id", None)
                candidate = PhaseDScannerCandidate(
                    id=int(candidate_id) if candidate_id is not None else None,
                    scanner_run_id=run.id,
                    canonical_symbol=str(getattr(candidate_row, "symbol", "") or "").strip().upper(),
                    display_name=str(getattr(candidate_row, "name", "") or "").strip() or None,
                    rank=int(getattr(candidate_row, "rank", 0) or 0),
                    score=float(getattr(candidate_row, "score", 0.0) or 0.0),
                    quality_hint=str(getattr(candidate_row, "quality_hint", "") or "").strip() or None,
                    reason_summary=str(getattr(candidate_row, "reason_summary", "") or "").strip() or None,
                    candidate_payload=self._build_candidate_payload(candidate_row),
                    created_at=getattr(candidate_row, "created_at", None) or created_at,
                )
                session.add(candidate)
                session.flush()
                if candidate_id is not None:
                    candidate_id_map[int(candidate_id)] = int(candidate.id)
            notification_payload = (
                diagnostics_json.get("notification")
                if isinstance(diagnostics_json.get("notification"), dict)
                else {}
            )
            watchlist_date = self._parse_date(
                summary_json.get("watchlist_date") or operation_payload.get("watchlist_date"),
                fallback=getattr(run_row, "run_at", None),
            )
            watchlist_status = self._watchlist_status(
                run_status=getattr(run_row, "status", None),
                shortlist_size=getattr(run_row, "shortlist_size", 0),
            )
            if watchlist is None:
                watchlist = PhaseDWatchlist(
                    owner_user_id=owner_user_id,
                    scope=scope,
                    market=run.market,
                    profile_key=run.profile_key,
                    watchlist_date=watchlist_date,
                    source_scanner_run_id=run.id,
                    status=watchlist_status,
                    headline=headline,
                    notification_status=str(notification_payload.get("status") or "").strip() or None,
                    notification_summary=notification_payload if isinstance(notification_payload, dict) else {},
                    comparison_summary={},
                    created_at=created_at,
                    updated_at=completed_at or created_at,
                )
                session.add(watchlist)
                session.flush()
            else:
                watchlist.owner_user_id = owner_user_id
                watchlist.scope = scope
                watchlist.market = run.market
                watchlist.profile_key = run.profile_key
                watchlist.watchlist_date = watchlist_date
                watchlist.status = watchlist_status
                watchlist.headline = headline
                watchlist.notification_status = str(notification_payload.get("status") or "").strip() or None
                watchlist.notification_summary = (
                    notification_payload if isinstance(notification_payload, dict) else {}
                )
                watchlist.updated_at = completed_at or datetime.now()
                session.flush()
            for candidate_row in candidate_rows:
                candidate_payload = self._build_candidate_payload(candidate_row)
                source_candidate_id = getattr(candidate_row, "id", None)
                watchlist_item = PhaseDWatchlistItem(
                    watchlist_id=watchlist.id,
                    source_scanner_candidate_id=(
                        candidate_id_map.get(int(source_candidate_id))
                        if source_candidate_id is not None
                        else None
                    ),
                    canonical_symbol=str(getattr(candidate_row, "symbol", "") or "").strip().upper(),
                    display_name=str(getattr(candidate_row, "name", "") or "").strip() or None,
                    rank=int(getattr(candidate_row, "rank", 0) or 0),
                    score=float(getattr(candidate_row, "score", 0.0) or 0.0),
                    selection_reason=str(getattr(candidate_row, "reason_summary", "") or "").strip() or None,
                    watch_context=candidate_payload.get("watch_context") or [],
                    created_at=getattr(candidate_row, "created_at", None) or created_at,
                )
                session.add(watchlist_item)

            session.flush()
            return run

    def clear_non_bootstrap_state(self, user_ids: Sequence[str]) -> Dict[str, int]:
        normalized_user_ids = [str(value).strip() for value in user_ids if str(value or "").strip()]
        if not normalized_user_ids:
            return {
                "scanner_runs": 0,
                "scanner_candidates": 0,
                "watchlists": 0,
                "watchlist_items": 0,
            }

        with self.session_scope() as session:
            scanner_run_ids = session.execute(
                select(PhaseDScannerRun.id).where(
                    PhaseDScannerRun.owner_user_id.in_(normalized_user_ids)
                )
            ).scalars().all()
            watchlist_ids = session.execute(
                select(PhaseDWatchlist.id).where(
                    PhaseDWatchlist.owner_user_id.in_(normalized_user_ids)
                )
            ).scalars().all()
            counts = {
                "watchlist_items": session.execute(
                    delete(PhaseDWatchlistItem).where(
                        PhaseDWatchlistItem.watchlist_id.in_(watchlist_ids)
                    )
                ).rowcount or 0 if watchlist_ids else 0,
                "watchlists": session.execute(
                    delete(PhaseDWatchlist).where(
                        PhaseDWatchlist.owner_user_id.in_(normalized_user_ids)
                    )
                ).rowcount or 0,
                "scanner_candidates": session.execute(
                    delete(PhaseDScannerCandidate).where(
                        PhaseDScannerCandidate.scanner_run_id.in_(scanner_run_ids)
                    )
                ).rowcount or 0 if scanner_run_ids else 0,
                "scanner_runs": session.execute(
                    delete(PhaseDScannerRun).where(
                        PhaseDScannerRun.owner_user_id.in_(normalized_user_ids)
                    )
                ).rowcount or 0,
            }
        return counts
