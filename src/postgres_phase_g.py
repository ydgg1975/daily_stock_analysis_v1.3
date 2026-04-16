# -*- coding: utf-8 -*-
"""Narrow Phase G persistence adapter for PostgreSQL-backed control-plane data."""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    create_engine,
    delete,
    desc,
    select,
)
from sqlalchemy.orm import Session, sessionmaker

from src.postgres_phase_a import PhaseABase

PhaseGBase = PhaseABase

_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")
_PHASE_G_TABLES = {
    "provider_configs",
    "system_configs",
    "admin_logs",
    "system_actions",
}
_PHASE_G_INDEXES = {
    "idx_admin_logs_occurred",
    "idx_system_actions_created",
}
_SYSTEM_CONFIG_KEYS = {
    "STOCK_LIST",
    "LITELLM_MODEL",
    "AGENT_LITELLM_MODEL",
    "BACKTEST_LITELLM_MODEL",
    "LITELLM_FALLBACK_MODELS",
    "LITELLM_CONFIG",
    "LLM_CHANNELS",
    "AI_PRIMARY_GATEWAY",
    "AI_PRIMARY_MODEL",
    "AI_BACKUP_GATEWAY",
    "AI_BACKUP_MODEL",
    "LLM_TEMPERATURE",
    "REALTIME_SOURCE_PRIORITY",
    "ENABLE_REALTIME_TECHNICAL_INDICATORS",
    "ENABLE_REALTIME_QUOTE",
    "ENABLE_CHIP_DISTRIBUTION",
    "NEWS_MAX_AGE_DAYS",
    "NEWS_STRATEGY_PROFILE",
    "BIAS_THRESHOLD",
    "CUSTOM_DATA_SOURCE_LIBRARY",
    "SCHEDULE_TIME",
    "LOG_LEVEL",
    "RUN_MODE",
    "ENV_FILE",
    "DATABASE_PATH",
    "POSTGRES_PHASE_A_URL",
    "POSTGRES_PHASE_A_APPLY_SCHEMA",
    "ADMIN_AUTH_ENABLED",
}
_PROVIDER_PREFIXES = {
    "GEMINI_": "gemini",
    "OPENAI_": "openai",
    "AIHUBMIX_": "aihubmix",
    "DEEPSEEK_": "deepseek",
    "ZHIPU_": "zhipu",
    "TUSHARE_": "tushare",
    "TICKFLOW_": "tickflow",
    "ALPACA_": "alpaca",
    "TWELVE_DATA_": "twelve_data",
    "TAVILY_": "tavily",
    "SERPAPI_": "serpapi",
    "BRAVE_": "brave",
    "BOCHA_": "bocha",
    "MINIMAX_": "minimax",
    "SEARXNG_": "searxng",
    "PYTDX_": "pytdx",
    "DISCORD_": "discord",
    "TELEGRAM_": "telegram",
    "SLACK_": "slack",
    "SMTP_": "smtp",
    "EMAIL_": "email",
    "WECHAT_": "wechat",
}
_LLM_CHANNEL_PATTERN = re.compile(
    r"^LLM_([A-Z0-9]+)_(API_KEY|BASE_URL|MODELS|PROTOCOL|ENABLED|EXTRA_HEADERS|EXTRA_BODY|TIMEOUT|TIMEOUT_SECONDS)$"
)


class PhaseGProviderConfig(PhaseGBase):
    __tablename__ = "provider_configs"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    provider_key = Column(Text, nullable=False, unique=True)
    config_scope = Column(Text, nullable=False, default="system")
    auth_mode = Column(Text, nullable=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    config_json = Column(JSON, nullable=False, default=dict)
    secret_json = Column(JSON, nullable=False, default=dict)
    rotation_version = Column(Integer, nullable=False, default=1)
    updated_by_user_id = Column(Text, ForeignKey("app_users.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint("config_scope in ('system')", name="ck_phase_g_provider_configs_scope"),
    )


class PhaseGSystemConfig(PhaseGBase):
    __tablename__ = "system_configs"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    config_key = Column(Text, nullable=False, unique=True)
    config_scope = Column(Text, nullable=False, default="system")
    value_type = Column(Text, nullable=False)
    value_json = Column(JSON, nullable=False, default=dict)
    updated_by_user_id = Column(Text, ForeignKey("app_users.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint("config_scope in ('system')", name="ck_phase_g_system_configs_scope"),
    )


class PhaseGAdminLog(PhaseGBase):
    __tablename__ = "admin_logs"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    actor_user_id = Column(Text, ForeignKey("app_users.id"))
    actor_role = Column(Text)
    subsystem = Column(Text, nullable=False)
    category = Column(Text)
    event_type = Column(Text, nullable=False)
    target_type = Column(Text)
    target_id = Column(Text)
    scope = Column(Text, nullable=False, default="system")
    severity = Column(Text, nullable=False, default="info")
    outcome = Column(Text)
    message = Column(Text)
    detail_json = Column(JSON, nullable=False, default=dict)
    related_session_key = Column(Text)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint("scope in ('system')", name="ck_phase_g_admin_logs_scope"),
    )


class PhaseGSystemAction(PhaseGBase):
    __tablename__ = "system_actions"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    action_key = Column(Text, nullable=False)
    actor_user_id = Column(Text, ForeignKey("app_users.id"))
    scope = Column(Text, nullable=False, default="system")
    destructive = Column(Boolean, nullable=False, default=False)
    status = Column(Text, nullable=False)
    request_json = Column(JSON, nullable=False, default=dict)
    result_json = Column(JSON, nullable=False, default=dict)
    admin_log_id = Column(_BIGINT_PK, ForeignKey("admin_logs.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    completed_at = Column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("scope in ('system')", name="ck_phase_g_system_actions_scope"),
    )


def _phase_g_sql_doc_path() -> Path:
    return Path(__file__).resolve().parent.parent / "docs" / "architecture" / "postgresql-baseline-v1.sql"


def load_phase_g_sql_statements() -> list[str]:
    """Extract only the Phase G DDL statements from the authoritative baseline SQL doc."""
    sql_path = _phase_g_sql_doc_path()
    if not sql_path.exists():
        raise RuntimeError(f"Phase G schema source not found: {sql_path}")

    raw_text = sql_path.read_text(encoding="utf-8")
    text = "\n".join(line for line in raw_text.splitlines() if not line.lstrip().startswith("--"))
    statements = [stmt.strip() for stmt in text.split(";") if stmt.strip()]

    selected: list[str] = []
    table_pattern = re.compile(r"^create table if not exists\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)
    index_pattern = re.compile(r"^create index if not exists\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)
    for statement in statements:
        normalized = re.sub(r"\s+", " ", statement).strip()
        table_match = table_pattern.match(normalized)
        if table_match and table_match.group(1).lower() in _PHASE_G_TABLES:
            selected.append(f"{statement};")
            continue
        index_match = index_pattern.match(normalized)
        if index_match and index_match.group(1).lower() in _PHASE_G_INDEXES:
            selected.append(f"{statement};")

    if not selected:
        raise RuntimeError(f"No Phase G schema statements found in {sql_path}")
    return selected


class PostgresPhaseGStore:
    """Narrow storage adapter for the PostgreSQL Phase G baseline."""

    def __init__(self, db_url: str, *, auto_apply_schema: bool = True):
        if not str(db_url or "").strip():
            raise ValueError("db_url is required for PostgresPhaseGStore")

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
            statements = load_phase_g_sql_statements()
            with self._engine.begin() as conn:
                for statement in statements:
                    conn.exec_driver_sql(statement)
            return
        PhaseGBase.metadata.create_all(self._engine)

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
    def _safe_json_dict(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
            except Exception:
                return {}
            if isinstance(parsed, dict):
                return parsed
        return {}

    @staticmethod
    def _safe_json_value(value: Any) -> Any:
        if value is None:
            return {}
        if isinstance(value, (dict, list, bool, int, float)):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return ""
            if raw.startswith("{") or raw.startswith("["):
                try:
                    return json.loads(raw)
                except Exception:
                    return value
        return value

    @staticmethod
    def _normalized_actor_id(updated_by_user_id: Optional[str]) -> Optional[str]:
        normalized = str(updated_by_user_id or "").strip()
        return normalized or None

    @staticmethod
    def _provider_key_for_config_key(key: str) -> Optional[str]:
        normalized_key = str(key or "").strip().upper()
        if not normalized_key or normalized_key in _SYSTEM_CONFIG_KEYS:
            return None

        llm_match = _LLM_CHANNEL_PATTERN.match(normalized_key)
        if llm_match:
            channel_name = llm_match.group(1).strip().lower()
            if channel_name and channel_name != "channels":
                return f"llm_channel:{channel_name}"

        for prefix, provider_key in _PROVIDER_PREFIXES.items():
            if normalized_key.startswith(prefix):
                return provider_key
        return None

    @staticmethod
    def _serialize_system_config_value(key: str, raw_value: str, field_schema: Optional[Dict[str, Any]]) -> tuple[str, Any]:
        schema = field_schema or {}
        value_type = str(schema.get("data_type") or "string").strip().lower() or "string"
        text = "" if raw_value is None else str(raw_value)
        stripped = text.strip()

        if value_type == "boolean":
            return value_type, stripped.lower() in {"1", "true", "yes", "on"}
        if value_type == "integer":
            try:
                return value_type, int(stripped)
            except Exception:
                return value_type, text
        if value_type == "number":
            try:
                return value_type, float(stripped)
            except Exception:
                return value_type, text
        if value_type == "array":
            values = [item.strip() for item in text.split(",") if item.strip()]
            return value_type, values
        return value_type, PostgresPhaseGStore._safe_json_value(text)

    def replace_config_snapshot(
        self,
        *,
        raw_config_map: Dict[str, str],
        field_schema_by_key: Dict[str, Dict[str, Any]],
        updated_by_user_id: Optional[str] = None,
    ) -> None:
        provider_payloads: Dict[str, Dict[str, Any]] = {}
        system_payloads: Dict[str, Dict[str, Any]] = {}
        resolved_actor_id = self._normalized_actor_id(updated_by_user_id)

        for raw_key, raw_value in sorted((raw_config_map or {}).items()):
            key = str(raw_key or "").strip().upper()
            if not key:
                continue
            field_schema = field_schema_by_key.get(key) or {}
            provider_key = self._provider_key_for_config_key(key)
            if provider_key is not None:
                payload = provider_payloads.setdefault(
                    provider_key,
                    {
                        "config_json": {},
                        "secret_json": {},
                    },
                )
                if bool(field_schema.get("is_sensitive", False)):
                    payload["secret_json"][key] = str(raw_value or "")
                else:
                    payload["config_json"][key] = self._safe_json_value(raw_value)
                continue

            value_type, value_json = self._serialize_system_config_value(key, str(raw_value or ""), field_schema)
            system_payloads[key] = {
                "value_type": value_type,
                "value_json": value_json,
            }

        with self.session_scope() as session:
            existing_providers = {
                row.provider_key: row
                for row in session.execute(select(PhaseGProviderConfig)).scalars().all()
            }
            existing_system = {
                row.config_key: row
                for row in session.execute(select(PhaseGSystemConfig)).scalars().all()
            }

            desired_provider_keys = set(provider_payloads.keys())
            desired_system_keys = set(system_payloads.keys())

            if existing_providers:
                session.execute(
                    delete(PhaseGProviderConfig).where(
                        PhaseGProviderConfig.provider_key.in_(
                            [key for key in existing_providers.keys() if key not in desired_provider_keys]
                        )
                    )
                )
            if existing_system:
                session.execute(
                    delete(PhaseGSystemConfig).where(
                        PhaseGSystemConfig.config_key.in_(
                            [key for key in existing_system.keys() if key not in desired_system_keys]
                        )
                    )
                )

            now = datetime.now()
            for provider_key, payload in provider_payloads.items():
                row = existing_providers.get(provider_key)
                if row is None:
                    row = PhaseGProviderConfig(
                        provider_key=provider_key,
                        rotation_version=1,
                        created_at=now,
                    )
                    session.add(row)

                next_config = dict(payload["config_json"])
                next_secret = dict(payload["secret_json"])
                existing_secret = self._safe_json_dict(getattr(row, "secret_json", None))
                if row.id is not None and next_secret != existing_secret and next_secret:
                    row.rotation_version = int(getattr(row, "rotation_version", 1) or 1) + 1

                row.config_scope = "system"
                row.auth_mode = "api_key" if next_secret else "config"
                row.is_enabled = True
                row.config_json = next_config
                row.secret_json = next_secret
                if resolved_actor_id is not None:
                    row.updated_by_user_id = resolved_actor_id
                row.updated_at = now

            for config_key, payload in system_payloads.items():
                row = existing_system.get(config_key)
                if row is None:
                    row = PhaseGSystemConfig(
                        config_key=config_key,
                        created_at=now,
                    )
                    session.add(row)
                row.config_scope = "system"
                row.value_type = str(payload["value_type"] or "string")
                row.value_json = payload["value_json"]
                if resolved_actor_id is not None:
                    row.updated_by_user_id = resolved_actor_id
                row.updated_at = now

    def append_admin_log(
        self,
        *,
        actor_user_id: Optional[str],
        actor_role: Optional[str],
        subsystem: str,
        category: Optional[str],
        event_type: str,
        target_type: Optional[str],
        target_id: Optional[str],
        severity: str,
        outcome: Optional[str],
        message: Optional[str],
        detail_json: Optional[Dict[str, Any]],
        related_session_key: Optional[str],
        occurred_at: Optional[datetime] = None,
    ) -> int:
        with self.session_scope() as session:
            row = PhaseGAdminLog(
                actor_user_id=self._normalized_actor_id(actor_user_id),
                actor_role=str(actor_role or "").strip() or None,
                subsystem=str(subsystem or "").strip(),
                category=str(category or "").strip() or None,
                event_type=str(event_type or "").strip(),
                target_type=str(target_type or "").strip() or None,
                target_id=str(target_id or "").strip() or None,
                scope="system",
                severity=str(severity or "info").strip() or "info",
                outcome=str(outcome or "").strip() or None,
                message=str(message or "").strip() or None,
                detail_json=dict(detail_json or {}),
                related_session_key=str(related_session_key or "").strip() or None,
                occurred_at=occurred_at or datetime.now(),
            )
            session.add(row)
            session.flush()
            return int(row.id)

    def append_system_action(
        self,
        *,
        action_key: str,
        actor_user_id: Optional[str],
        destructive: bool,
        status: str,
        request_json: Optional[Dict[str, Any]],
        result_json: Optional[Dict[str, Any]],
        admin_log_id: Optional[int],
        created_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> int:
        with self.session_scope() as session:
            row = PhaseGSystemAction(
                action_key=str(action_key or "").strip(),
                actor_user_id=self._normalized_actor_id(actor_user_id),
                scope="system",
                destructive=bool(destructive),
                status=str(status or "").strip() or "completed",
                request_json=dict(request_json or {}),
                result_json=dict(result_json or {}),
                admin_log_id=int(admin_log_id) if admin_log_id is not None else None,
                created_at=created_at or datetime.now(),
                completed_at=completed_at,
            )
            session.add(row)
            session.flush()
            return int(row.id)

    def nullify_user_references(self, user_ids: Iterable[str]) -> None:
        normalized_user_ids = sorted({str(value).strip() for value in user_ids if str(value or "").strip()})
        if not normalized_user_ids:
            return

        with self.session_scope() as session:
            provider_rows = session.execute(
                select(PhaseGProviderConfig).where(PhaseGProviderConfig.updated_by_user_id.in_(normalized_user_ids))
            ).scalars().all()
            for row in provider_rows:
                row.updated_by_user_id = None

            system_rows = session.execute(
                select(PhaseGSystemConfig).where(PhaseGSystemConfig.updated_by_user_id.in_(normalized_user_ids))
            ).scalars().all()
            for row in system_rows:
                row.updated_by_user_id = None

            admin_log_rows = session.execute(
                select(PhaseGAdminLog).where(PhaseGAdminLog.actor_user_id.in_(normalized_user_ids))
            ).scalars().all()
            for row in admin_log_rows:
                detail_json = self._safe_json_dict(row.detail_json)
                if row.actor_user_id and "actor_user_id" not in detail_json:
                    detail_json["actor_user_id"] = row.actor_user_id
                if row.actor_role and "actor_role" not in detail_json:
                    detail_json["actor_role"] = row.actor_role
                row.detail_json = detail_json
                row.actor_user_id = None

            system_action_rows = session.execute(
                select(PhaseGSystemAction).where(PhaseGSystemAction.actor_user_id.in_(normalized_user_ids))
            ).scalars().all()
            for row in system_action_rows:
                request_json = self._safe_json_dict(row.request_json)
                if row.actor_user_id and "actor_user_id" not in request_json:
                    request_json["actor_user_id"] = row.actor_user_id
                row.request_json = request_json
                row.actor_user_id = None

    def list_admin_logs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.session_scope() as session:
            rows = session.execute(
                select(PhaseGAdminLog)
                .order_by(desc(PhaseGAdminLog.occurred_at), desc(PhaseGAdminLog.id))
                .limit(max(1, min(int(limit), 200)))
            ).scalars().all()
            return [
                {
                    "id": int(row.id),
                    "actor_user_id": row.actor_user_id,
                    "actor_role": row.actor_role,
                    "subsystem": row.subsystem,
                    "category": row.category,
                    "event_type": row.event_type,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "scope": row.scope,
                    "severity": row.severity,
                    "outcome": row.outcome,
                    "message": row.message,
                    "detail_json": self._safe_json_dict(row.detail_json),
                    "related_session_key": row.related_session_key,
                    "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
                }
                for row in rows
            ]

    def list_system_actions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.session_scope() as session:
            rows = session.execute(
                select(PhaseGSystemAction)
                .order_by(desc(PhaseGSystemAction.created_at), desc(PhaseGSystemAction.id))
                .limit(max(1, min(int(limit), 200)))
            ).scalars().all()
            return [
                {
                    "id": int(row.id),
                    "action_key": row.action_key,
                    "actor_user_id": row.actor_user_id,
                    "scope": row.scope,
                    "destructive": bool(row.destructive),
                    "status": row.status,
                    "request_json": self._safe_json_dict(row.request_json),
                    "result_json": self._safe_json_dict(row.result_json),
                    "admin_log_id": int(row.admin_log_id) if row.admin_log_id is not None else None,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                }
                for row in rows
            ]
