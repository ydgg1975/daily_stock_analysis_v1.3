# -*- coding: utf-8 -*-
"""Narrow Phase C persistence adapter for PostgreSQL-backed market metadata."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    create_engine,
    select,
    text,
)
from sqlalchemy.orm import Session, sessionmaker

from src.core.trading_calendar import get_market_for_stock
from src.data.stock_mapping import STOCK_NAME_MAP
from src.postgres_phase_a import PhaseABase
from src.services.us_history_helper import LOCAL_US_PARQUET_SOURCE, get_us_stock_parquet_dir

logger = logging.getLogger(__name__)

PhaseCBase = PhaseABase

_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")
_PHASE_C_TABLES = {
    "symbol_master",
    "market_data_manifests",
    "market_dataset_versions",
    "market_data_usage_refs",
}
_PHASE_C_INDEXES = {
    "idx_symbol_master_market_active",
}
_PHASE_C_CONSTRAINTS = {
    ("market_data_manifests", "fk_market_data_manifests_active_version"),
}
_US_LOCAL_PARQUET_MANIFEST_KEY = "us.local_parquet.daily"
_ALLOWED_STORAGE_BACKENDS = {"parquet_local", "parquet_nas", "hybrid"}
_ALLOWED_ENTITY_TYPES = {
    "analysis_record",
    "scanner_run",
    "watchlist",
    "backtest_run",
    "portfolio_sync_state",
}
_ALLOWED_USAGE_ROLES = {
    "primary_bars",
    "benchmark_bars",
    "universe_snapshot",
    "symbol_master_snapshot",
}


class PhaseCSymbolMaster(PhaseCBase):
    __tablename__ = "symbol_master"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    canonical_symbol = Column(Text, nullable=False, unique=True, index=True)
    display_symbol = Column(Text)
    market = Column(Text, nullable=False, index=True)
    exchange_code = Column(Text)
    asset_type = Column(Text, nullable=False, index=True)
    display_name = Column(Text)
    currency = Column(Text)
    lot_size = Column(Numeric(24, 8))
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    search_aliases = Column(JSON, nullable=False, default=list)
    source = Column(Text)
    source_payload_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        Index("ix_phase_c_symbol_master_market_active", "market", "is_active", "canonical_symbol"),
    )


class PhaseCMarketDataManifest(PhaseCBase):
    __tablename__ = "market_data_manifests"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    manifest_key = Column(Text, nullable=False, unique=True, index=True)
    dataset_family = Column(Text, nullable=False)
    market = Column(Text, nullable=False, index=True)
    asset_scope = Column(Text)
    storage_backend = Column(Text, nullable=False)
    root_uri = Column(Text, nullable=False)
    file_format = Column(Text, nullable=False, default="parquet")
    partition_strategy = Column(Text)
    symbol_namespace = Column(Text)
    description = Column(Text)
    config_json = Column(JSON, nullable=False, default=dict)
    active_version_id = Column(_BIGINT_PK, ForeignKey("market_dataset_versions.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint(
            "storage_backend in ('parquet_local', 'parquet_nas', 'hybrid')",
            name="ck_phase_c_market_data_manifests_storage_backend",
        ),
    )


class PhaseCMarketDatasetVersion(PhaseCBase):
    __tablename__ = "market_dataset_versions"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    manifest_id = Column(_BIGINT_PK, ForeignKey("market_data_manifests.id"), nullable=False, index=True)
    version_label = Column(Text, nullable=False)
    version_hash = Column(Text, nullable=False)
    source_kind = Column(Text)
    generated_at = Column(DateTime(timezone=True))
    as_of_date = Column(Date)
    coverage_start = Column(Date)
    coverage_end = Column(Date)
    symbol_count = Column(Integer)
    row_count = Column(BigInteger)
    partition_count = Column(Integer)
    file_inventory_json = Column(JSON, nullable=False, default=dict)
    content_stats_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("manifest_id", "version_label", name="uq_phase_c_market_dataset_versions_label"),
        UniqueConstraint("manifest_id", "version_hash", name="uq_phase_c_market_dataset_versions_hash"),
    )


class PhaseCMarketDataUsageRef(PhaseCBase):
    __tablename__ = "market_data_usage_refs"

    id = Column(_BIGINT_PK, primary_key=True, autoincrement=True)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(_BIGINT_PK, nullable=False, index=True)
    usage_role = Column(Text, nullable=False)
    manifest_id = Column(_BIGINT_PK, ForeignKey("market_data_manifests.id"), nullable=False, index=True)
    dataset_version_id = Column(_BIGINT_PK, ForeignKey("market_dataset_versions.id"), nullable=False, index=True)
    detail_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "usage_role",
            "dataset_version_id",
            name="uq_phase_c_market_data_usage_refs_entity_usage_version",
        ),
        CheckConstraint(
            "entity_type in ('analysis_record', 'scanner_run', 'watchlist', 'backtest_run', 'portfolio_sync_state')",
            name="ck_phase_c_market_data_usage_refs_entity_type",
        ),
        CheckConstraint(
            "usage_role in ('primary_bars', 'benchmark_bars', 'universe_snapshot', 'symbol_master_snapshot')",
            name="ck_phase_c_market_data_usage_refs_usage_role",
        ),
    )


def _phase_c_sql_doc_path() -> Path:
    return Path(__file__).resolve().parent.parent / "docs" / "architecture" / "postgresql-baseline-v1.sql"


def load_phase_c_sql_statements() -> list[str]:
    """Extract only the Phase C DDL statements from the authoritative baseline SQL doc."""
    sql_path = _phase_c_sql_doc_path()
    if not sql_path.exists():
        raise RuntimeError(f"Phase C schema source not found: {sql_path}")

    raw_text = sql_path.read_text(encoding="utf-8")
    text_body = "\n".join(
        line for line in raw_text.splitlines() if not line.lstrip().startswith("--")
    )
    statements = [stmt.strip() for stmt in text_body.split(";") if stmt.strip()]

    selected: list[str] = []
    table_pattern = re.compile(r"^create table if not exists\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)
    index_pattern = re.compile(r"^create index if not exists\s+([a-z_][a-z0-9_]*)", re.IGNORECASE)
    alter_pattern = re.compile(
        r"^alter table\s+([a-z_][a-z0-9_]*)\s+add constraint\s+([a-z_][a-z0-9_]*)",
        re.IGNORECASE,
    )

    for statement in statements:
        normalized = re.sub(r"\s+", " ", statement).strip()
        table_match = table_pattern.match(normalized)
        if table_match and table_match.group(1).lower() in _PHASE_C_TABLES:
            selected.append(f"{statement};")
            continue

        index_match = index_pattern.match(normalized)
        if index_match and index_match.group(1).lower() in _PHASE_C_INDEXES:
            selected.append(f"{statement};")
            continue

        alter_match = alter_pattern.match(normalized)
        if alter_match and (
            alter_match.group(1).lower(),
            alter_match.group(2).lower(),
        ) in _PHASE_C_CONSTRAINTS:
            selected.append(f"{statement};")

    if not selected:
        raise RuntimeError(f"No Phase C schema statements found in {sql_path}")
    return selected


class PostgresPhaseCStore:
    """Narrow storage adapter for the PostgreSQL Phase C baseline."""

    def __init__(self, db_url: str, *, auto_apply_schema: bool = True):
        if not str(db_url or "").strip():
            raise ValueError("db_url is required for PostgresPhaseCStore")

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
            statements = load_phase_c_sql_statements()
            alter_pattern = re.compile(
                r"^alter table\s+([a-z_][a-z0-9_]*)\s+add constraint\s+([a-z_][a-z0-9_]*)",
                re.IGNORECASE,
            )
            with self._engine.begin() as conn:
                for statement in statements:
                    normalized = re.sub(r"\s+", " ", statement).strip().rstrip(";")
                    alter_match = alter_pattern.match(normalized)
                    if alter_match:
                        constraint_name = alter_match.group(2)
                        exists = conn.execute(
                            text("select 1 from pg_constraint where conname = :constraint_name"),
                            {"constraint_name": constraint_name},
                        ).scalar()
                        if exists:
                            continue
                    conn.exec_driver_sql(statement)
            return

        PhaseCBase.metadata.create_all(self._engine)

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
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            text_value = value.strip()
            if not text_value:
                return {}
            try:
                parsed = json.loads(text_value)
            except Exception:
                return {}
            return dict(parsed) if isinstance(parsed, dict) else {}
        return {}

    @staticmethod
    def _normalize_aliases(values: Optional[Iterable[Any]], *, canonical_symbol: str) -> list[str]:
        seen: set[str] = set()
        aliases: list[str] = []
        normalized_symbol = str(canonical_symbol or "").strip().upper()
        for value in list(values or []):
            alias = str(value or "").strip()
            if not alias:
                continue
            dedup_key = alias.upper()
            if dedup_key == normalized_symbol:
                continue
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            aliases.append(alias)
        return aliases

    @staticmethod
    def _normalize_market(value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip().lower()
        return normalized or None

    @staticmethod
    def _infer_currency(market: Optional[str]) -> Optional[str]:
        normalized_market = str(market or "").strip().lower()
        return {
            "cn": "CNY",
            "hk": "HKD",
            "us": "USD",
        }.get(normalized_market)

    def get_symbol_master_entry(self, canonical_symbol: str) -> Optional[PhaseCSymbolMaster]:
        normalized_symbol = str(canonical_symbol or "").strip().upper()
        if not normalized_symbol:
            return None
        with self.get_session() as session:
            return session.execute(
                select(PhaseCSymbolMaster)
                .where(PhaseCSymbolMaster.canonical_symbol == normalized_symbol)
                .limit(1)
            ).scalar_one_or_none()

    def upsert_symbol_master_entry(
        self,
        *,
        canonical_symbol: str,
        display_symbol: Optional[str] = None,
        market: str,
        asset_type: str,
        display_name: Optional[str] = None,
        exchange_code: Optional[str] = None,
        currency: Optional[str] = None,
        lot_size: Optional[Any] = None,
        is_active: bool = True,
        search_aliases: Optional[Iterable[Any]] = None,
        source: Optional[str] = None,
        source_payload: Optional[Any] = None,
    ) -> PhaseCSymbolMaster:
        normalized_symbol = str(canonical_symbol or "").strip().upper()
        normalized_market = self._normalize_market(market)
        normalized_asset_type = str(asset_type or "").strip().lower()
        if not normalized_symbol:
            raise ValueError("canonical_symbol is required")
        if not normalized_market:
            raise ValueError("market is required")
        if not normalized_asset_type:
            raise ValueError("asset_type is required")

        now = datetime.now()
        aliases = self._normalize_aliases(search_aliases, canonical_symbol=normalized_symbol)
        payload = self._safe_json_dict(source_payload)

        with self.session_scope() as session:
            row = session.execute(
                select(PhaseCSymbolMaster)
                .where(PhaseCSymbolMaster.canonical_symbol == normalized_symbol)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = PhaseCSymbolMaster(
                    canonical_symbol=normalized_symbol,
                    created_at=now,
                )
                session.add(row)

            row.display_symbol = str(display_symbol or "").strip() or normalized_symbol
            row.market = normalized_market
            row.exchange_code = str(exchange_code or "").strip() or None
            row.asset_type = normalized_asset_type
            row.display_name = str(display_name or "").strip() or None
            row.currency = str(currency or "").strip() or self._infer_currency(normalized_market)
            row.lot_size = lot_size
            row.is_active = bool(is_active)
            row.search_aliases = aliases
            row.source = str(source or "").strip() or None
            row.source_payload_json = payload
            row.updated_at = now
            session.flush()
            return row

    def seed_symbol_master_from_stock_mapping(self, *, symbols: Optional[Sequence[str]] = None) -> int:
        selected_symbols = {
            str(symbol or "").strip().upper()
            for symbol in (symbols or STOCK_NAME_MAP.keys())
            if str(symbol or "").strip()
        }
        count = 0
        for canonical_symbol in sorted(selected_symbols):
            display_name = STOCK_NAME_MAP.get(canonical_symbol)
            if not display_name:
                continue
            market = self._normalize_market(get_market_for_stock(canonical_symbol))
            if not market:
                continue
            self.upsert_symbol_master_entry(
                canonical_symbol=canonical_symbol,
                display_symbol=canonical_symbol,
                market=market,
                asset_type="equity",
                display_name=display_name,
                currency=self._infer_currency(market),
                is_active=True,
                search_aliases=[display_name],
                source="stock_mapping",
                source_payload={"seed_source": "STOCK_NAME_MAP"},
            )
            count += 1
        return count

    def get_market_data_manifest(self, manifest_key: str) -> Optional[PhaseCMarketDataManifest]:
        normalized_key = str(manifest_key or "").strip()
        if not normalized_key:
            return None
        with self.get_session() as session:
            return session.execute(
                select(PhaseCMarketDataManifest)
                .where(PhaseCMarketDataManifest.manifest_key == normalized_key)
                .limit(1)
            ).scalar_one_or_none()

    def upsert_market_data_manifest(
        self,
        *,
        manifest_key: str,
        dataset_family: str,
        market: str,
        storage_backend: str,
        root_uri: str,
        asset_scope: Optional[str] = None,
        file_format: str = "parquet",
        partition_strategy: Optional[str] = None,
        symbol_namespace: Optional[str] = None,
        description: Optional[str] = None,
        config: Optional[Any] = None,
        active_version_id: Optional[int] = None,
    ) -> PhaseCMarketDataManifest:
        normalized_key = str(manifest_key or "").strip()
        normalized_market = self._normalize_market(market)
        normalized_storage_backend = str(storage_backend or "").strip().lower()
        normalized_dataset_family = str(dataset_family or "").strip().lower()
        normalized_root_uri = str(root_uri or "").strip()
        normalized_file_format = str(file_format or "").strip().lower() or "parquet"
        if not normalized_key:
            raise ValueError("manifest_key is required")
        if not normalized_dataset_family:
            raise ValueError("dataset_family is required")
        if not normalized_market:
            raise ValueError("market is required")
        if normalized_storage_backend not in _ALLOWED_STORAGE_BACKENDS:
            raise ValueError(f"Unsupported storage_backend: {storage_backend}")
        if not normalized_root_uri:
            raise ValueError("root_uri is required")

        now = datetime.now()
        with self.session_scope() as session:
            row = session.execute(
                select(PhaseCMarketDataManifest)
                .where(PhaseCMarketDataManifest.manifest_key == normalized_key)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = PhaseCMarketDataManifest(
                    manifest_key=normalized_key,
                    created_at=now,
                )
                session.add(row)

            row.dataset_family = normalized_dataset_family
            row.market = normalized_market
            row.asset_scope = str(asset_scope or "").strip() or None
            row.storage_backend = normalized_storage_backend
            row.root_uri = normalized_root_uri
            row.file_format = normalized_file_format
            row.partition_strategy = str(partition_strategy or "").strip() or None
            row.symbol_namespace = str(symbol_namespace or "").strip() or None
            row.description = str(description or "").strip() or None
            row.config_json = self._safe_json_dict(config)
            if active_version_id is not None:
                row.active_version_id = int(active_version_id)
            row.updated_at = now
            session.flush()
            return row

    def get_market_dataset_version(
        self,
        dataset_version_id: int,
    ) -> Optional[PhaseCMarketDatasetVersion]:
        if dataset_version_id is None:
            return None
        with self.get_session() as session:
            return session.execute(
                select(PhaseCMarketDatasetVersion)
                .where(PhaseCMarketDatasetVersion.id == int(dataset_version_id))
                .limit(1)
            ).scalar_one_or_none()

    def register_market_dataset_version(
        self,
        *,
        manifest_key: str,
        version_label: str,
        version_hash: str,
        source_kind: Optional[str] = None,
        generated_at: Optional[datetime] = None,
        as_of_date: Optional[date] = None,
        coverage_start: Optional[date] = None,
        coverage_end: Optional[date] = None,
        symbol_count: Optional[int] = None,
        row_count: Optional[int] = None,
        partition_count: Optional[int] = None,
        file_inventory: Optional[Any] = None,
        content_stats: Optional[Any] = None,
        set_active: bool = False,
    ) -> PhaseCMarketDatasetVersion:
        manifest = self.get_market_data_manifest(manifest_key)
        if manifest is None:
            raise ValueError(f"Unknown manifest_key: {manifest_key}")

        normalized_label = str(version_label or "").strip()
        normalized_hash = str(version_hash or "").strip()
        if not normalized_label:
            raise ValueError("version_label is required")
        if not normalized_hash:
            raise ValueError("version_hash is required")

        generated = generated_at or datetime.now()
        with self.session_scope() as session:
            manifest_row = session.execute(
                select(PhaseCMarketDataManifest)
                .where(PhaseCMarketDataManifest.id == int(manifest.id))
                .limit(1)
            ).scalar_one()

            row = session.execute(
                select(PhaseCMarketDatasetVersion)
                .where(PhaseCMarketDatasetVersion.manifest_id == int(manifest.id))
                .where(PhaseCMarketDatasetVersion.version_hash == normalized_hash)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = session.execute(
                    select(PhaseCMarketDatasetVersion)
                    .where(PhaseCMarketDatasetVersion.manifest_id == int(manifest.id))
                    .where(PhaseCMarketDatasetVersion.version_label == normalized_label)
                    .limit(1)
                ).scalar_one_or_none()

            if row is None:
                row = PhaseCMarketDatasetVersion(
                    manifest_id=int(manifest.id),
                    version_label=normalized_label,
                    version_hash=normalized_hash,
                    created_at=datetime.now(),
                )
                session.add(row)

            row.version_label = normalized_label
            row.version_hash = normalized_hash
            row.source_kind = str(source_kind or "").strip() or None
            row.generated_at = generated
            row.as_of_date = as_of_date
            row.coverage_start = coverage_start
            row.coverage_end = coverage_end
            row.symbol_count = int(symbol_count) if symbol_count is not None else None
            row.row_count = int(row_count) if row_count is not None else None
            row.partition_count = int(partition_count) if partition_count is not None else None
            row.file_inventory_json = self._safe_json_dict(file_inventory)
            row.content_stats_json = self._safe_json_dict(content_stats)
            session.flush()

            if set_active:
                manifest_row.active_version_id = int(row.id)
                manifest_row.updated_at = datetime.now()
                session.flush()

            return row

    def get_market_data_usage_refs(
        self,
        *,
        entity_type: str,
        entity_id: int,
    ) -> list[PhaseCMarketDataUsageRef]:
        normalized_entity_type = str(entity_type or "").strip()
        if not normalized_entity_type or entity_id is None:
            return []
        with self.get_session() as session:
            return list(
                session.execute(
                    select(PhaseCMarketDataUsageRef)
                    .where(PhaseCMarketDataUsageRef.entity_type == normalized_entity_type)
                    .where(PhaseCMarketDataUsageRef.entity_id == int(entity_id))
                    .order_by(PhaseCMarketDataUsageRef.created_at.asc(), PhaseCMarketDataUsageRef.id.asc())
                ).scalars().all()
            )

    def record_market_data_usage_ref(
        self,
        *,
        entity_type: str,
        entity_id: int,
        usage_role: str,
        manifest_key: str,
        dataset_version_id: int,
        detail: Optional[Any] = None,
    ) -> PhaseCMarketDataUsageRef:
        normalized_entity_type = str(entity_type or "").strip()
        normalized_usage_role = str(usage_role or "").strip()
        if normalized_entity_type not in _ALLOWED_ENTITY_TYPES:
            raise ValueError(f"Unsupported entity_type: {entity_type}")
        if normalized_usage_role not in _ALLOWED_USAGE_ROLES:
            raise ValueError(f"Unsupported usage_role: {usage_role}")
        if entity_id is None:
            raise ValueError("entity_id is required")

        manifest = self.get_market_data_manifest(manifest_key)
        if manifest is None:
            raise ValueError(f"Unknown manifest_key: {manifest_key}")
        dataset_version = self.get_market_dataset_version(int(dataset_version_id))
        if dataset_version is None:
            raise ValueError(f"Unknown dataset_version_id: {dataset_version_id}")
        if int(dataset_version.manifest_id) != int(manifest.id):
            raise ValueError("dataset_version_id does not belong to manifest_key")

        with self.session_scope() as session:
            row = session.execute(
                select(PhaseCMarketDataUsageRef)
                .where(PhaseCMarketDataUsageRef.entity_type == normalized_entity_type)
                .where(PhaseCMarketDataUsageRef.entity_id == int(entity_id))
                .where(PhaseCMarketDataUsageRef.usage_role == normalized_usage_role)
                .where(PhaseCMarketDataUsageRef.dataset_version_id == int(dataset_version_id))
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = PhaseCMarketDataUsageRef(
                    entity_type=normalized_entity_type,
                    entity_id=int(entity_id),
                    usage_role=normalized_usage_role,
                    manifest_id=int(manifest.id),
                    dataset_version_id=int(dataset_version_id),
                    created_at=datetime.now(),
                )
                session.add(row)

            row.manifest_id = int(manifest.id)
            row.dataset_version_id = int(dataset_version_id)
            row.detail_json = self._safe_json_dict(detail)
            session.flush()
            return row

    @staticmethod
    def _normalize_date_value(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text_value = str(value or "").strip()
        if not text_value:
            return None
        if "T" in text_value:
            text_value = text_value.split("T", 1)[0]
        try:
            return date.fromisoformat(text_value[:10])
        except Exception:
            return None

    @staticmethod
    def _compute_file_content_hash(file_path: Path) -> Optional[str]:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def build_local_us_parquet_usage_detail(
        self,
        *,
        stock_code: str,
        file_path: Path | str,
        dataframe: Optional[Any],
        source_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_path = Path(file_path).expanduser().resolve()
        coverage_dates: list[date] = []
        if dataframe is not None and hasattr(dataframe, "__len__"):
            columns_attr = getattr(dataframe, "columns", None)
            columns = list(columns_attr) if columns_attr is not None else []
            if "date" in columns:
                for value in dataframe["date"]:
                    normalized = self._normalize_date_value(value)
                    if normalized is not None:
                        coverage_dates.append(normalized)
        coverage_start = min(coverage_dates).isoformat() if coverage_dates else None
        coverage_end = max(coverage_dates).isoformat() if coverage_dates else None
        file_size_bytes = None
        if resolved_path.exists() and resolved_path.is_file():
            file_size_bytes = int(resolved_path.stat().st_size)

        return {
            "symbol": str(stock_code or "").strip().upper() or None,
            "resolved_source": str(source_name or "").strip() or LOCAL_US_PARQUET_SOURCE,
            "resolved_path": str(resolved_path),
            "file_name": resolved_path.name,
            "file_size_bytes": file_size_bytes,
            "content_hash": self._compute_file_content_hash(resolved_path),
            "coverage_start": coverage_start,
            "coverage_end": coverage_end,
            "row_count": int(len(dataframe)) if dataframe is not None else None,
        }

    @staticmethod
    def _build_inventory_fingerprint(root_uri: str, files: list[dict[str, Any]]) -> str:
        payload = {
            "root_uri": root_uri,
            "files": files,
        }
        raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def register_local_us_parquet_dataset_version(
        self,
        *,
        root_path: Optional[Path | str] = None,
        activate: bool = True,
    ) -> PhaseCMarketDatasetVersion:
        resolved_root = Path(root_path) if root_path is not None else get_us_stock_parquet_dir()
        resolved_root = resolved_root.expanduser().resolve()
        if not resolved_root.exists() or not resolved_root.is_dir():
            raise FileNotFoundError(f"Local US parquet root does not exist: {resolved_root}")

        files: list[dict[str, Any]] = []
        for file_path in sorted(resolved_root.glob("*.parquet")):
            stat = file_path.stat()
            files.append(
                {
                    "symbol": file_path.stem.upper(),
                    "relative_path": file_path.relative_to(resolved_root).as_posix(),
                    "size_bytes": int(stat.st_size),
                    "modified_at_ns": int(stat.st_mtime_ns),
                }
            )

        root_uri = str(resolved_root)
        version_hash = self._build_inventory_fingerprint(root_uri, files)
        version_label = f"inventory:{version_hash[:12]}"

        self.upsert_market_data_manifest(
            manifest_key=_US_LOCAL_PARQUET_MANIFEST_KEY,
            dataset_family="daily_ohlcv",
            market="us",
            asset_scope="equity",
            storage_backend="parquet_local",
            root_uri=root_uri,
            file_format="parquet",
            partition_strategy="symbol_file",
            symbol_namespace="us_equity",
            description="Local-first US daily parquet metadata registry",
            config={
                "env_keys": ["LOCAL_US_PARQUET_DIR", "US_STOCK_PARQUET_DIR"],
                "source_name": LOCAL_US_PARQUET_SOURCE,
            },
        )
        return self.register_market_dataset_version(
            manifest_key=_US_LOCAL_PARQUET_MANIFEST_KEY,
            version_label=version_label,
            version_hash=version_hash,
            source_kind="local_parquet_inventory",
            generated_at=datetime.now(),
            symbol_count=len(files),
            row_count=None,
            partition_count=len(files),
            file_inventory={
                "root_uri": root_uri,
                "files": files,
            },
            content_stats={
                "file_count": len(files),
                "fingerprint_kind": "path_size_mtime_ns",
            },
            set_active=activate,
        )
