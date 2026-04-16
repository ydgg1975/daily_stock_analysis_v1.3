# WolfyStock PostgreSQL Baseline Implementation Plan

Companion artifacts:

- [`postgresql-baseline-design.md`](./postgresql-baseline-design.md)
- [`postgresql-baseline-v1.sql`](./postgresql-baseline-v1.sql)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the product from the current SQLite/file-mixed runtime toward PostgreSQL-backed business data and metadata without migrating bulk historical market bars out of Parquet/NAS.

**Architecture:** Keep the current repository/service boundaries, migrate low-risk identity and workspace records first, add dataset-version metadata before scanner/backtest cutovers, and leave Parquet/NAS as the primary historical-bar body store throughout the plan.

**Tech Stack:** PostgreSQL, current SQLAlchemy-backed repositories/services, FastAPI, React/Electron clients, local/NAS Parquet datasets.

---

## File / Module Map

- Current identity and auth:
  - `src/auth.py`
  - `api/deps.py`
  - `api/v1/endpoints/auth.py`
  - `src/storage.py`
- Current analysis and chat persistence:
  - `src/services/analysis_service.py`
  - `src/services/history_service.py`
  - `src/agent/conversation.py`
  - `src/storage.py`
- Current scanner persistence:
  - `src/services/market_scanner_service.py`
  - `src/services/market_scanner_ops_service.py`
  - `src/repositories/scanner_repo.py`
- Current backtest persistence:
  - `src/services/backtest_service.py`
  - `src/services/rule_backtest_service.py`
  - `src/repositories/backtest_repo.py`
  - `src/repositories/rule_backtest_repo.py`
- Current portfolio persistence:
  - `src/services/portfolio_service.py`
  - `src/repositories/portfolio_repo.py`
  - `src/services/portfolio_import_service.py`
  - `src/services/portfolio_ibkr_sync_service.py`
- Current system/provider config and admin observability:
  - `src/services/system_config_service.py`
  - `src/core/config_manager.py`
  - `src/services/execution_log_service.py`
- Current market-data body and metadata edges:
  - `src/services/us_history_helper.py`
  - `src/repositories/stock_repo.py`
  - `src/data/stock_mapping.py`
  - `scripts/generate_stock_index.py`

## Migration Rules

- [ ] Keep Parquet/NAS as the primary historical-bar body store in every phase.
- [ ] Treat PostgreSQL as the target source-of-record for product and hot metadata only.
- [ ] Do not cut over a domain until owner semantics, source-of-record semantics, and coexistence rules are written down.
- [ ] Prefer adapting current repositories/services over introducing a second parallel application architecture.
- [ ] Keep bootstrap-admin compatibility explicit until Phase A is complete and verified.
- [ ] Keep `.env` as live config until Phase G is fully implemented and rollback-tested.
- [ ] Preserve auth-disabled transitional bootstrap-admin/current-user behavior and legacy signed-cookie compatibility until Phase A parity is proven.

### Task 1: Phase A identity baseline

- [ ] Create PostgreSQL-backed `app_users`, `app_user_sessions`, `guest_sessions`, `user_preferences`, and `notification_targets`.
- [ ] Add a compatibility layer that can resolve bootstrap admin and current signed cookie semantics without changing user-visible behavior.
- [ ] Split personal notification targets out of `user_preferences.notification_preferences_json`.
- [ ] Normalize only the current per-user email/Discord target semantics in this phase; keep global operator notification channels in `.env` until Phase G.
- [ ] Keep guest preview isolated by guest session without writing guest data into normal user history.
- [ ] Verification target:
  - auth login/logout/current-user
  - auth-disabled transitional bootstrap-admin/current-user semantics
  - legacy signed admin-cookie compatibility during coexistence
  - guest preview cookie isolation without history persistence
  - per-user email/Discord target reads/writes while global operator channels stay `.env`-backed

### Task 2: Phase B analysis and chat

- [ ] Introduce `analysis_sessions` and `analysis_records` without changing report payload shape.
- [ ] Introduce `chat_sessions` and `chat_messages` while preserving owner isolation and current history list/detail behavior.
- [ ] Map current `analysis_history` and `conversation_*` data into the new shape with a compatibility read path.
- [ ] Preserve the current external chat `session_id` contract and a narrow bridge back to legacy `analysis_history.id` while Phase B coexists with SQLite-backed downstream domains.
- [ ] Keep guest preview as a separate `analysis_sessions.session_kind = 'guest_preview'` branch if guest persistence is enabled later.
- [ ] Verification target:
  - analysis history list/detail/delete
  - chat session list/detail/delete
  - cross-owner isolation

### Task 3: Phase C dataset manifests and version metadata

- [ ] Create `symbol_master`, `market_data_manifests`, `market_dataset_versions`, and `market_data_usage_refs`.
- [ ] Inventory current local/NAS parquet datasets and assign stable manifest keys and version-seeding rules.
- [ ] Define version-hash generation and file-inventory rollup logic before scanner/backtest cutovers.
- [ ] Seed symbol metadata from current static map plus generated stock index without treating those files as the long-term source-of-record.
- [ ] Verification target:
  - manifest lookup
  - version registration
  - run-to-dataset reference writes

### Task 4: Phase D scanner

- [ ] Migrate scanner run persistence into `scanner_runs` and `scanner_candidates`.
- [ ] Promote daily watchlist semantics into first-class `watchlists` and `watchlist_items`.
- [ ] Keep system-scoped scheduled watchlists separate from user-owned manual runs.
- [ ] Preserve current `watchlist_date`, `trigger_mode`, notification state, and operator visibility rules.
- [ ] Verification target:
  - manual scanner run history
  - admin-only system watchlists
  - today/recent watchlist lookup
  - coexistence with local universe cache CSV

### Task 5: Phase E backtest

- [ ] Introduce unified `backtest_runs` and `backtest_artifacts`.
- [ ] Preserve deterministic backtest comparison, benchmark, audit-row, and execution-trace semantics as stored artifacts.
- [ ] Keep current standard evaluation and rule backtest workflows behaviorally unchanged during coexistence.
- [ ] Ensure every persisted run records dataset-version provenance through `market_data_usage_refs`.
- [ ] Verification target:
  - historical evaluation runs/results
  - deterministic parse/run/detail/history
  - stored benchmark comparison payloads
  - stored audit-row and execution-trace replay

### Task 6: Phase F portfolio and broker sync

- [ ] Introduce `broker_connections`, `portfolio_accounts`, `portfolio_ledger`, `portfolio_positions`, `portfolio_sync_states`, `portfolio_sync_positions`, and `portfolio_sync_cash_balances`.
- [ ] Preserve current source-event semantics for trades, cash, and corporate actions.
- [ ] Keep broker sync as overlay state, not ledger truth.
- [ ] Preserve import dedup, broker-account-ref uniqueness, oversell checks, and current account ownership boundaries.
- [ ] Verification target:
  - account CRUD
  - import parse/commit
  - broker sync overlays
  - replayed positions/snapshots

### Task 7: Phase G system/provider config and admin observability

- [ ] Introduce `provider_configs`, `system_configs`, `execution_sessions`, `execution_events`, `admin_logs`, and `system_actions`.
- [ ] Dual-write or bridge current execution-log writes before cutover.
- [ ] Preserve global admin-only read semantics for logs and system actions.
- [ ] Replace `.env` as source-of-record only after runtime reload behavior and rollback behavior are explicitly validated.
- [ ] Verification target:
  - config read/update/validate/test-channel
  - runtime cache reset
  - factory reset audit
  - execution session/event list/detail
  - admin log list/detail

## Domain Dependencies

- [ ] Phase C must land before Phases D and E so scanner/backtest records can reference dataset versions.
- [ ] Phase A should land before any domain that needs user/guest ownership in PostgreSQL.
- [ ] Phase F should not cut over before Phase A owner semantics and broker-connection ownership are stable.
- [ ] Phase G should be last because it changes global runtime behavior and secret handling.

## Temporary Coexistence Requirements

- [ ] SQLite and PostgreSQL will coexist during migration; do not delete old tables before parity is proven.
- [ ] `.env` and PostgreSQL config rows will coexist during Phase G.
- [ ] Local/NAS parquet bodies remain live throughout every phase.
- [ ] Existing JSON-heavy payloads may temporarily remain the compatibility truth while first-class PostgreSQL rows are backfilled.

## Deferred Items

- [ ] Full historical OHLCV migration into PostgreSQL is intentionally excluded.
- [ ] Mini-program-specific frontend/state changes are intentionally excluded.
- [ ] Broad repository or ORM rewrites are intentionally excluded.
- [ ] Large-scale product behavior redesign is intentionally excluded.
