# WolfyStock PostgreSQL Baseline Gap Audit

Companion artifacts:

- [`postgresql-baseline-design.md`](./postgresql-baseline-design.md)
- [`postgresql-baseline-plan.md`](./postgresql-baseline-plan.md)
- [`postgresql-baseline-v1.sql`](./postgresql-baseline-v1.sql)

## Executive Summary

This audit compared the PostgreSQL baseline design against the current real storage layer, starting from `src/storage.py` and tracing outward into auth, API, service, repository, client-local persistence, and file-backed operational state.

The baseline is directionally correct on the biggest architectural decisions:

- PostgreSQL should own business data, access control data, configuration data, run metadata, and hot market-data metadata.
- Parquet/NAS should remain the source-of-record for bulk OHLCV and benchmark bodies.
- Current user/business domains are already mostly modeled as durable rows rather than pure in-memory state.

The baseline was not ready to implement unchanged. This audit found four concrete mismatches and corrected them in the companion baseline docs:

1. Added PostgreSQL execution-observability tables equivalent to current `execution_log_sessions` and `execution_log_events`.
2. Added PostgreSQL `portfolio_sync_cash_balances` for current broker overlay parity.
3. Updated Phase A planning to preserve auth-disabled transitional bootstrap-admin/current-user semantics and legacy signed-cookie compatibility.
4. Updated Phase A planning to normalize only current per-user email/Discord targets while keeping global operator channels `.env`-backed until Phase G.

Additional non-Phase-A clarifications still remain for later phases, especially around analysis auxiliary artifacts, watchlist promotion semantics, portfolio replay materializations, and market-data metadata for non-Parquet fallback sources.

## Audit Scope

Target baseline:

- `docs/architecture/postgresql-baseline-design.md`
- `docs/architecture/postgresql-baseline-plan.md`
- `docs/architecture/postgresql-baseline-v1.sql`

Current storage semantics audited from code and local runtime assets:

- `src/storage.py`
- auth/session/current-user paths in `src/auth.py`, `api/deps.py`, `api/v1/endpoints/auth.py`
- guest preview/session isolation in `api/v1/endpoints/analysis.py`
- analysis/history/task queue paths
- chat persistence and client session-pointer persistence
- scanner run, watchlist, cache, and observability paths
- backtest and rule-backtest storage plus client-local preset persistence
- portfolio ledger, overlay, replay, and import/sync paths
- `.env`-backed provider/system config and admin action logging
- market-data metadata inputs including SQLite `stock_daily`, local Parquet, local CSV cache, and static symbol/index files
- actual local runtime data directory contents and current SQLite tables

Out of scope:

- PostgreSQL runtime integration
- repository/service rewrites
- OHLCV migration into PostgreSQL
- Alembic/migration wiring
- production deployment changes

## Method

1. Read the baseline design, plan, and schema artifacts as the target state.
2. Trace current persistence from `src/storage.py` ORM/table definitions into repository and service callers.
3. Inspect auth, guest, scanner, backtest, portfolio, and config call sites for real ownership and isolation semantics.
4. Inspect browser-local persistence, file-backed stores, and generated artifacts that currently act as persistence, cache, or reproducibility anchors.
5. Classify each store as:
   - source-of-record
   - durable cache
   - derived materialization
   - transient memory state
   - exported/generated artifact
6. Compare those semantics against schema v1 and note:
   - confirmed matches
   - schema omissions
   - misplaced scope
   - cache-vs-record confusion
   - restart/loss risk
   - migration difficulty

## Current Storage Map

| Store | Current location | Class | Current role | PostgreSQL-owned in target baseline |
| --- | --- | --- | --- | --- |
| Auth users | SQLite `app_users` | durable business record | user/admin identity | yes |
| Auth sessions | SQLite `app_user_sessions` + signed cookie | mixed record + signed token | authenticated web sessions | yes for server-side session rows |
| Bootstrap admin credential | `data/.admin_password_hash` | file-backed system secret | bootstrap password SoR | no during transitional coexistence |
| Session signing secret | `data/.session_secret` | file-backed system secret | cookie and unlock-token signing root | no during transitional coexistence |
| Guest preview identity | browser cookie `wolfystock_guest_session` | client-local durable token | guest isolation only | yes as future `guest_sessions`, not yet current runtime |
| User notification prefs | SQLite `user_preferences.notification_preferences_json` | durable business record | per-user email/Discord targets | yes, but normalized into `notification_targets` |
| UI preferences | browser `localStorage` | client-local preference/cache | font size, market color, language, theme | no, unless product scope changes |
| Analysis history | SQLite `analysis_history` | durable business record | saved report history | yes |
| News intel | SQLite `news_intel` | durable supporting record | per-query article list / URL history | yes, but v1 shape is unresolved |
| Fundamental snapshot | SQLite `fundamental_snapshot` | durable supporting snapshot | fail-open query snapshot | yes, but v1 shape is unresolved |
| Task queue state | process memory in `src/services/task_queue.py` | transient memory | in-flight task lifecycle and SSE state | no |
| Chat sessions/messages | SQLite `conversation_sessions` / `conversation_messages` | durable business record | user chat history | yes |
| Chat session context | process memory in `ConversationManager` | transient memory | TTL-bound contextual state | no |
| Scanner runs/candidates | SQLite `market_scanner_runs` / `market_scanner_candidates` | durable business record | scanner execution + shortlist | yes |
| Scanner local universe cache | `data/scanner_cn_universe_cache.csv` | durable cache | A-share universe fallback/input cache | no |
| Scanner markdown watchlist files | notifier output files | generated artifact | notification/report convenience output | no |
| Execution observability | SQLite `execution_log_sessions` / `execution_log_events` | durable observability record | admin log center + run/session event stream | yes, via companion execution-session/event baseline |
| Historical eval backtest | SQLite `backtest_runs` / `backtest_results` / `backtest_summaries` | durable business record | historical analysis evaluation | yes |
| Rule backtest | SQLite `rule_backtest_runs` / `rule_backtest_trades` | durable business record | deterministic backtest history | yes |
| Rule backtest presets | browser `localStorage` | client-local convenience cache | saved/recent presets | no, unless product scope changes |
| Portfolio ledger | SQLite `portfolio_trades` / `portfolio_cash_ledger` / `portfolio_corporate_actions` | durable business record | replay source-of-truth | yes |
| Portfolio materializations | SQLite `portfolio_positions` / `portfolio_position_lots` / `portfolio_daily_snapshots` / `portfolio_fx_rates` | durable derived state | replay snapshots and FX cache | partially; baseline is incomplete |
| Portfolio sync overlay | SQLite `portfolio_broker_sync_states` / `positions` / `cash_balances` | durable overlay record | broker current-state overlay | yes, with companion cash-balance parity fix |
| Provider/system config | `.env` via `ConfigManager` | file-backed system SoR | live runtime config | yes eventually, not yet |
| OHLCV local cache | SQLite `stock_daily` | durable cache/body store | local market-history cache and fallback input | no |
| US local history | local Parquet files | durable external body store | local-first US history | no |
| Symbol/static seed data | `src/data/stock_mapping.py`, generated `apps/dsa-web/public/stocks.index.json` | static seed + generated artifact | symbol fallback and autocomplete | `symbol_master` should own hot metadata; files stay outside PG |

## Domain-By-Domain Findings

## 1. Identity And Access

### 1.1 App users

- Current storage location:
  - SQLite `app_users`
  - bootstrap admin password still originates from `data/.admin_password_hash`
- Current source-of-record:
  - ordinary users: `app_users`
  - bootstrap admin password: file-backed hash mirrored into `app_users.password_hash`
- Persistence type:
  - mixed durable DB row + file-backed bootstrap secret
- Ownership model:
  - system-global identity table; admin is a role on the same user model
- User isolation semantics:
  - user ids are first-class and enforced across downstream domains
- Guest isolation semantics:
  - none here; guests are not represented as users
- Admin/global semantics:
  - bootstrap admin is a normal `app_users` row plus compatibility file behavior
- Reproducibility implications:
  - identity history is stable, but bootstrap credential truth is dual-sourced
- Restart/loss risk:
  - losing SQLite rows breaks identity mapping
  - losing `.admin_password_hash` changes bootstrap password truth
- Migration difficulty:
  - medium; data shape is close, but bootstrap coexistence must be preserved explicitly
- Schema v1 coverage:
  - `app_users` is a direct match
- Missing from schema v1:
  - no schema issue; the gap is coexistence semantics, not table shape
- Must remain outside PostgreSQL:
  - `data/.admin_password_hash` during transitional bootstrap compatibility

### 1.2 Authenticated sessions and current-user semantics

- Current storage location:
  - signed cookie `dsa_session`
  - SQLite `app_user_sessions`
  - file-backed `data/.session_secret`
- Current source-of-record:
  - v2 sessions: signed cookie identity plus `app_user_sessions` row for expiry/revocation
  - legacy admin cookie: signed cookie plus `.session_secret`, no session row
- Persistence type:
  - mixed client token + server row + server secret
- Ownership model:
  - user-owned session rows
- User isolation semantics:
  - session row is tied to `user_id`
  - downstream `resolve_current_user()` loads the DB user row and checks `is_active`
- Guest isolation semantics:
  - none here
- Admin/global semantics:
  - when auth is disabled, `resolve_current_user()` returns a transitional bootstrap-admin current user
  - that current user is `is_admin=true`, `is_authenticated=false`, `transitional=true`
- Reproducibility implications:
  - current-user semantics depend on both env/file state and DB rows
- Restart/loss risk:
  - session rows persist across restart
  - rotating or losing `.session_secret` invalidates all cookies and admin unlock tokens
  - in auth-disabled mode, transitional admin access does not require a session row
- Migration difficulty:
  - medium; row schema is straightforward, but compatibility behavior is easy to break
- Schema v1 coverage:
  - `app_user_sessions` matches the current durable session row model
- Missing from schema v1:
  - no schema gap; the design/plan gap is lack of explicit verification for transitional and legacy compatibility
- Must remain outside PostgreSQL:
  - `.session_secret` during transitional coexistence
  - signed-cookie payloads themselves

### 1.3 Guest sessions

- Current storage location:
  - browser cookie `wolfystock_guest_session`
  - guest preview `query_id = guest:<session_id>:<timestamp>`
- Current source-of-record:
  - cookie value only
- Persistence type:
  - client-local durable token; no server-side guest row
- Ownership model:
  - anonymous cookie-scoped isolation only
- User isolation semantics:
  - guest preview does not write into user-owned history
- Guest isolation semantics:
  - cookie isolates preview chains between visitors
- Admin/global semantics:
  - guests are not mapped onto bootstrap admin or system scope
- Reproducibility implications:
  - guest preview chains are not server-replayable after cookie loss
- Restart/loss risk:
  - cookie loss loses guest identity
  - server restart does not lose guest records because none are persisted
- Migration difficulty:
  - low for additive `guest_sessions`, but dangerous if implementers accidentally persist guest preview as normal user history
- Schema v1 coverage:
  - `guest_sessions` is directionally correct as a future target
- Missing from schema v1:
  - none for Phase A
- Must remain outside PostgreSQL:
  - guest preview should remain non-persistent unless product scope changes

## 2. User-Owned Product Data

### 2.1 User preferences and notification targets

- Current storage location:
  - SQLite `user_preferences`
  - browser localStorage for font size, market-color convention, UI language, theme style
- Current source-of-record:
  - user-owned server preference record currently only matters for `notification_preferences_json`
  - most UI preferences are client-local and not server-backed
- Persistence type:
  - mixed durable DB row + client-local browser persistence
- Ownership model:
  - per-user for notification targets
  - per-browser for UI preferences
- User isolation semantics:
  - DB notification preferences are keyed by `user_id`
  - browser UI preferences are device/browser scoped, not account scoped
- Guest isolation semantics:
  - guests do not get server-side preference rows
- Admin/global semantics:
  - actual email delivery availability depends on global `.env` SMTP config
  - global operator notification channels still live in `.env`, not in `user_preferences`
- Reproducibility implications:
  - personal notification target intent is durable
  - UI preferences are not reproducible across devices/accounts
- Restart/loss risk:
  - SQLite row persists
  - browser-local preference loss resets per-device UI state
- Migration difficulty:
  - medium; JSON normalization is simple, but ownership boundaries are easy to overreach
- Schema v1 coverage:
  - `user_preferences` and `notification_targets` are directionally correct
- Missing from schema v1:
  - not a table omission, but the baseline needs to state that Phase A only migrates current per-user email/Discord targets
  - global operator channels remain system config until Phase G
- Must remain outside PostgreSQL:
  - device-local UI preferences unless product scope explicitly promotes them to account data

### 2.2 Analysis history and supporting records

- Current storage location:
  - SQLite `analysis_history`
  - SQLite `news_intel`
  - SQLite `fundamental_snapshot`
  - SQLite `execution_log_sessions` / `execution_log_events`
  - in-memory `src/services/task_queue.py`
- Current source-of-record:
  - saved report history: `analysis_history`
  - per-query article history: `news_intel`
  - supporting fundamental snapshot: `fundamental_snapshot`
  - operator observability: `execution_log_sessions` / `execution_log_events`
  - task queue state is not durable
- Persistence type:
  - mixed durable DB rows + transient in-memory task lifecycle
- Ownership model:
  - user-owned via `owner_id`
  - auth-disabled mode routes records into bootstrap-admin ownership
- User isolation semantics:
  - history list/detail access is owner-filtered
- Guest isolation semantics:
  - preview explicitly uses `persist_history=False`
- Admin/global semantics:
  - execution logs are admin-only observable global records
- Reproducibility implications:
  - saved report payloads preserve conclusions and snapshots
  - exact dataset-version provenance is missing
  - article-level news and supporting fundamentals survive separately today
- Restart/loss risk:
  - persisted history survives
  - in-flight task queue and SSE progress are lost on restart
- Migration difficulty:
  - medium-high; `analysis_history` is easy, but supporting artifacts and observability are not fully modeled in v1
- Schema v1 coverage:
  - `analysis_sessions` / `analysis_records` cover the main history shape
- Missing from schema v1:
  - no explicit equivalent for current `news_intel`
  - no explicit equivalent for current `fundamental_snapshot`
  - no explicit equivalent for current execution observability stream
- Must remain outside PostgreSQL:
  - transient task-queue state and SSE fanout

### 2.3 Chat sessions and messages

- Current storage location:
  - SQLite `conversation_sessions`
  - SQLite `conversation_messages`
  - in-memory `ConversationManager._sessions`
  - browser localStorage key `dsa_chat_session_id`
- Current source-of-record:
  - durable transcript and ownership: `conversation_sessions` + `conversation_messages`
  - in-memory context is only a transient accelerator
- Persistence type:
  - mixed durable DB transcript + transient in-memory context + client-local active-session pointer
- Ownership model:
  - user-owned; API chat endpoints pass `owner_id=current_user.user_id`
- User isolation semantics:
  - access checks enforce owner match
  - client localStorage only remembers which session to reopen
- Guest isolation semantics:
  - no persisted guest chat model exists today
- Admin/global semantics:
  - none, except bootstrap-admin ownership when auth is disabled
- Reproducibility implications:
  - transcript is reproducible
  - in-memory conversation context is not durable and may diverge from replay
- Restart/loss risk:
  - transcript persists
  - in-memory context is lost on process restart/TTL cleanup
- Migration difficulty:
  - medium; transcript mapping is easy, but context durability remains intentionally partial
- Schema v1 coverage:
  - `chat_sessions` / `chat_messages` are a good target
- Missing from schema v1:
  - no blocker; the baseline intentionally leaves transient chat context outside DB
- Must remain outside PostgreSQL:
  - in-memory agent execution context
  - browser active-session pointer

### 2.4 Watchlists

- Current storage location:
  - no first-class watchlist table
  - derived from SQLite `market_scanner_runs` / `market_scanner_candidates` plus JSON metadata
- Current source-of-record:
  - scanner run rows are the underlying durable record
  - watchlist is a promoted read model
- Persistence type:
  - derived from durable rows
- Ownership model:
  - manual watchlists are user-owned via underlying scanner run
  - scheduled/operator watchlists are system-scoped via underlying scanner run
- User isolation semantics:
  - inherited from scanner run ownership filters
- Guest isolation semantics:
  - none
- Admin/global semantics:
  - scheduled watchlists are global/operator space
- Reproducibility implications:
  - watchlist promotion logic depends on JSON metadata and current preference rules
- Restart/loss risk:
  - underlying run rows persist
  - watchlist read model is recomputed
- Migration difficulty:
  - medium-high; current semantics allow multiple runs per date and then select a preferred watchlist view
- Schema v1 coverage:
  - `watchlists` / `watchlist_items` are directionally correct
- Missing from schema v1:
  - promotion/uniqueness rules are not fully decided
  - current JSON-only fields must be promoted carefully
- Must remain outside PostgreSQL:
  - nothing inherently, but current markdown watchlist files remain artifacts

## 3. Scanner

- Current storage location:
  - SQLite `market_scanner_runs`
  - SQLite `market_scanner_candidates`
  - SQLite `execution_log_sessions` / `execution_log_events`
  - `data/scanner_cn_universe_cache.csv`
  - markdown watchlist notification files
- Current source-of-record:
  - business record: `market_scanner_runs` + `market_scanner_candidates`
  - observability: execution-log tables
  - input cache: local universe CSV
- Persistence type:
  - mixed durable business rows + durable observability rows + durable local cache + file artifacts
- Ownership model:
  - manual runs: `scope='user'`, `owner_id` set
  - scheduled runs: `scope='system'`, `owner_id=NULL`
- User isolation semantics:
  - repository and service visibility enforce owner/scope filters
- Guest isolation semantics:
  - no guest scanner persistence
- Admin/global semantics:
  - system-scoped scheduled runs and their observability are admin/operator space
- Reproducibility implications:
  - current reproducibility is partial only
  - `watchlist_date`, `trigger_mode`, `request_source`, notification result, coverage summary, provider fallback notes, and previous-watchlist comparison live in JSON blobs and/or execution logs
  - data provenance can currently only be inferred from source strings and local input paths
- Restart/loss risk:
  - run rows and observability rows persist
  - local CSV can be regenerated
  - markdown notification files are expendable artifacts
- Migration difficulty:
  - high for semantics, not storage volume
- Schema v1 coverage:
  - `scanner_runs`, `scanner_candidates`, `watchlists`, `watchlist_items`, and the companion execution-session/event baseline are directionally right
- Missing from schema v1:
  - watchlist promotion/uniqueness semantics are not fully defined
  - no dataset-version references yet for current local cache / DB / Parquet / provider fallback chains
- Must remain outside PostgreSQL:
  - local universe CSV cache
  - markdown watchlist report files
  - OHLCV bodies used for follow-through review

## 4. Backtest

- Current storage location:
  - SQLite `backtest_runs`
  - SQLite `backtest_results`
  - SQLite `backtest_summaries`
  - SQLite `rule_backtest_runs`
  - SQLite `rule_backtest_trades`
  - browser localStorage `wolfystock.ruleBacktestPresets.v1`
  - optional exported CSV/JSON artifacts
- Current source-of-record:
  - historical evaluation: `backtest_*` tables
  - deterministic rule backtest: `rule_backtest_runs` + `rule_backtest_trades`
  - client presets are convenience state only, not server truth
- Persistence type:
  - durable DB rows + client-local convenience persistence + optional exported artifacts
- Ownership model:
  - user-owned via `owner_id`
  - auth-disabled mode routes to bootstrap admin
- User isolation semantics:
  - owner filtering in service/repository layer
- Guest isolation semantics:
  - no guest backtest persistence
- Admin/global semantics:
  - none
- Reproducibility implications:
  - current anchors include `engine_version`, request payloads, parsed strategy JSON, `strategy_hash`, benchmark selection/result, and resolved source labels
  - exact dataset version, file inventory, and content hash provenance are missing
- Restart/loss risk:
  - persisted runs survive restart
  - exported artifacts and client presets are expendable
- Migration difficulty:
  - medium-high because the current domain uses two different storage shapes
- Schema v1 coverage:
  - `backtest_runs` + `backtest_artifacts` can absorb the current JSON-heavy deterministic payloads
- Missing from schema v1:
  - no first-class dataset-version linkage until `market_data_usage_refs` is actually wired
  - standard historical evaluation result/summarization mapping into the unified run/artifact model still needs explicit backfill rules
- Must remain outside PostgreSQL:
  - exported CSV/JSON traces and comparison files
  - browser-local rule backtest presets unless product scope changes
  - OHLCV and benchmark bodies

## 5. Portfolio

- Current storage location:
  - SQLite `portfolio_accounts`
  - SQLite `portfolio_broker_connections`
  - SQLite `portfolio_trades`
  - SQLite `portfolio_cash_ledger`
  - SQLite `portfolio_corporate_actions`
  - SQLite `portfolio_positions`
  - SQLite `portfolio_position_lots`
  - SQLite `portfolio_daily_snapshots`
  - SQLite `portfolio_fx_rates`
  - SQLite `portfolio_broker_sync_states`
  - SQLite `portfolio_broker_sync_positions`
  - SQLite `portfolio_broker_sync_cash_balances`
- Current source-of-record:
  - ledger truth:
    - `portfolio_trades`
    - `portfolio_cash_ledger`
    - `portfolio_corporate_actions`
  - overlay truth:
    - `portfolio_broker_sync_states`
    - `portfolio_broker_sync_positions`
    - `portfolio_broker_sync_cash_balances`
  - derived materializations:
    - `portfolio_positions`
    - `portfolio_position_lots`
    - `portfolio_daily_snapshots`
    - `portfolio_fx_rates`
- Persistence type:
  - durable DB rows only; import files and IBKR session tokens are intentionally transient
- Ownership model:
  - end-to-end user-owned
- User isolation semantics:
  - account, connection, ledger, and sync operations are owner-scoped
- Guest isolation semantics:
  - none
- Admin/global semantics:
  - none
- Reproducibility implications:
  - replayable ledger truth exists
  - overlay state is clearly separate from ledger truth
  - FX rates and replayed snapshots affect derived numbers and need an explicit policy if re-derived rather than persisted
- Restart/loss risk:
  - durable rows survive
  - import raw files and IBKR session token do not
- Migration difficulty:
  - high; this is the most semantics-heavy domain
- Schema v1 coverage:
  - `portfolio_accounts`, `broker_connections`, `portfolio_ledger`, `portfolio_positions`, `portfolio_sync_states`, and `portfolio_sync_positions` are only a partial match
- Missing from schema v1:
  - initial schema v1 was missing `portfolio_sync_cash_balances`; this audit adds it in the companion baseline docs
  - no explicit policy for current `portfolio_position_lots`
  - no explicit policy for current `portfolio_daily_snapshots`
  - no explicit policy for current `portfolio_fx_rates`
- Must remain outside PostgreSQL:
  - imported raw files
  - live IBKR session token

## 6. Provider / System / Admin

### 6.1 Provider and system config

- Current storage location:
  - `.env`
  - in-memory loaded `Config` singleton
- Current source-of-record:
  - `.env`
- Persistence type:
  - file-backed durable config + in-memory loaded runtime state
- Ownership model:
  - system-global, admin-only mutation
- User isolation semantics:
  - none
- Guest isolation semantics:
  - none
- Admin/global semantics:
  - runtime config reload and maintenance actions are admin-only
- Reproducibility implications:
  - behavior depends on mutable file state, not versioned DB config rows
- Restart/loss risk:
  - `.env` persists
  - loaded singletons/caches do not
- Migration difficulty:
  - high for eventual cutover, but this is intentionally later-phase work
- Schema v1 coverage:
  - `provider_configs` and `system_configs` are directionally correct targets
- Missing from schema v1:
  - not a table gap; the main requirement is coexistence with `.env` until Phase G
- Must remain outside PostgreSQL:
  - live `.env` during coexistence
  - bootstrap auth files during coexistence

### 6.2 Admin logs, system actions, and run observability

- Current storage location:
  - SQLite `execution_log_sessions`
  - SQLite `execution_log_events`
- Current source-of-record:
  - these tables already serve as the admin execution-log center and structured observability stream for analysis/scanner/admin actions
- Persistence type:
  - durable DB rows
- Ownership model:
  - admin-visible global observability; rows contain actor metadata and session kind
- User isolation semantics:
  - not user-visible, but actor/owner metadata is recorded
- Guest isolation semantics:
  - not applicable
- Admin/global semantics:
  - this is current system observability truth
  - destructive actions such as factory reset are also logged here
- Reproducibility implications:
  - current operator/debug workflows depend on session/event granularity
- Restart/loss risk:
  - durable rows survive restart
- Migration difficulty:
  - medium; shape is already explicit
- Schema v1 coverage:
  - companion `execution_sessions` / `execution_events` restore the per-run session/event stream
  - `admin_logs` / `system_actions` remain useful as coarse audit records
- Missing from schema v1:
  - no remaining Phase-A blocker after the companion baseline correction
- Must remain outside PostgreSQL:
  - nothing inherently; this domain should move into PostgreSQL, but the baseline must model it first

## 7. Market Data Metadata

- Current storage location:
  - SQLite `stock_daily`
  - local US Parquet under `LOCAL_US_PARQUET_DIR` / `US_STOCK_PARQUET_DIR`
  - `data/scanner_cn_universe_cache.csv`
  - static symbol seed `src/data/stock_mapping.py`
  - generated autocomplete index `apps/dsa-web/public/stocks.index.json`
- Current source-of-record:
  - bulk OHLCV bodies: external Parquet/local datasets plus other upstream fetchers
  - local `stock_daily` is a durable cache/body store, not a clean metadata registry
  - scanner universe CSV and static symbol files are cache/seed inputs
  - no current manifest/version registry exists
- Persistence type:
  - mixed SQLite body cache + external Parquet + CSV cache + static code/data + generated file artifact
- Ownership model:
  - system-global
- User isolation semantics:
  - none
- Guest isolation semantics:
  - none
- Admin/global semantics:
  - all global
- Reproducibility implications:
  - current runs can often say which source label was used (`LocalParquet`, `stock_daily`, fetcher names), but cannot point to a stable manifest/version/hash
- Restart/loss risk:
  - Parquet and SQLite cache survive
  - generated index can be regenerated
  - scanner CSV cache can be regenerated
- Migration difficulty:
  - medium for metadata only, but only if current non-Parquet fallback inputs are classified correctly
- Schema v1 coverage:
  - `symbol_master`, `market_data_manifests`, `market_dataset_versions`, and `market_data_usage_refs` are conceptually right
- Missing from schema v1:
  - current baseline does not fully explain how `stock_daily`, scanner universe CSV, and static seed data participate in provenance when they materially affect scanner/backtest output
- Must remain outside PostgreSQL:
  - OHLCV and benchmark bodies
  - scanner universe CSV cache
  - generated stock index file
  - static source files

## PostgreSQL Coverage Assessment

### Confirmed matches

- `app_users` and `app_user_sessions` are close to current durable auth storage.
- `guest_sessions` is a reasonable additive model for guest isolation.
- `analysis_sessions` / `analysis_records` correctly separate workspace/session identity from saved report records.
- `chat_sessions` / `chat_messages` match the current durable transcript model.
- `scanner_runs` / `scanner_candidates` preserve the current run/candidate boundary.
- `watchlists` / `watchlist_items` correctly recognize that current watchlists are a product concept, not just scanner rows.
- `backtest_artifacts` is the right direction for current JSON-heavy deterministic backtest outputs.
- `portfolio_ledger` and `portfolio_sync_states` preserve the important ledger-vs-overlay split.
- `provider_configs` / `system_configs` correctly target eventual `.env` replacement rather than mixing everything into business tables.
- `symbol_master` + manifest/version metadata is the right long-term boundary while keeping OHLCV outside PostgreSQL.

### Too shallow or missing

- Initial schema v1 lacked an `execution_log_sessions` / `execution_log_events` equivalent; this audit resolves that in the companion baseline docs.
- Initial schema v1 lacked `portfolio_sync_cash_balances`; this audit resolves that in the companion baseline docs.
- No explicit mapping for current `news_intel` and `fundamental_snapshot`.
- No explicit policy for current `portfolio_position_lots`, `portfolio_daily_snapshots`, or `portfolio_fx_rates`.
- No explicit provenance classification for current `stock_daily`, scanner CSV cache, or static symbol/index seeds when they affect runs.

### Too broad or not yet grounded in current semantics

- `notification_targets` is broader than the current per-user model; current reality only persists user-owned email and Discord targets.
- `guest_sessions` is broader than current runtime; current guest mode has isolation only, not durable guest workspaces.

### Misplaced if implemented naively

- Moving global operator channels from `.env` into per-user `notification_targets` would be incorrect.
- Treating browser localStorage convenience state as PostgreSQL business data would be scope creep.
- Treating `stock_daily` as PostgreSQL-owned business data would violate the agreed boundary that OHLCV bodies stay outside PostgreSQL.

## Source-Of-Record Matrix

| Data class | Current source-of-record | Persistent type | PostgreSQL baseline ownership | Keep outside PostgreSQL |
| --- | --- | --- | --- | --- |
| App users | SQLite `app_users` | DB row | yes | no |
| Bootstrap admin password | `data/.admin_password_hash` | file | transitional only | yes during coexistence |
| Authenticated session revocation/expiry | SQLite `app_user_sessions` | DB row | yes | no |
| Session signing root | `data/.session_secret` | file | transitional only | yes during coexistence |
| Guest isolation | guest cookie | client token | future `guest_sessions` | current runtime yes |
| Per-user notification targets | `user_preferences.notification_preferences_json` | DB row | yes | no |
| Global operator notification channels | `.env` | file | later `system_configs` / `provider_configs` | yes during coexistence |
| UI/browser preferences | browser localStorage | client storage | no current scope | yes |
| Saved analysis history | SQLite `analysis_history` | DB row | yes | no |
| News article history | SQLite `news_intel` | DB row | yes, but target shape unresolved | no |
| Fundamental snapshot | SQLite `fundamental_snapshot` | DB row | yes, but target shape unresolved | no |
| Chat transcript | SQLite conversation tables | DB row | yes | no |
| In-flight task queue | process memory | memory | no | yes |
| Scanner run record | SQLite scanner tables | DB row | yes | no |
| Scanner observability | SQLite execution-log tables | DB row | yes, via companion execution-session/event baseline | no |
| Scanner local universe cache | local CSV | file cache | no | yes |
| Historical eval backtest | SQLite backtest tables | DB row | yes | no |
| Rule backtest results | SQLite rule backtest tables | DB row | yes | no |
| Rule presets | browser localStorage | client storage | no current scope | yes |
| Portfolio ledger | SQLite trade/cash/corporate-action tables | DB row | yes | no |
| Portfolio sync overlay | SQLite sync tables | DB row | yes | no |
| Portfolio replay materializations | SQLite positions/lots/snapshots/fx | DB row | partially | possibly, depends on later phase policy |
| Provider/system config | `.env` | file | eventually yes | yes during coexistence |
| Admin/system action audit | SQLite execution-log tables | DB row | yes, with execution-session/event fidelity restored in companion baseline docs | no |
| Symbol hot metadata | static files + generated index | static/generated | yes via `symbol_master` | source files yes |
| OHLCV bodies | Parquet + SQLite cache + upstream fetchers | file/db cache | no | yes |

## Cache / Derived-State / Artifact Classification

### Durable business/system records

- `app_users`
- `app_user_sessions`
- `user_preferences.notification_preferences_json`
- `analysis_history`
- `news_intel`
- `fundamental_snapshot`
- `conversation_sessions`
- `conversation_messages`
- `market_scanner_runs`
- `market_scanner_candidates`
- `backtest_runs`
- `backtest_results`
- `backtest_summaries`
- `rule_backtest_runs`
- `rule_backtest_trades`
- `portfolio_accounts`
- `portfolio_broker_connections`
- `portfolio_trades`
- `portfolio_cash_ledger`
- `portfolio_corporate_actions`
- `portfolio_broker_sync_states`
- `portfolio_broker_sync_positions`
- `portfolio_broker_sync_cash_balances`
- `execution_log_sessions`
- `execution_log_events`

### Durable caches

- `stock_daily` local market-history cache/body store
- `data/scanner_cn_universe_cache.csv`
- browser task list cache `dsa-task-queue-v1`
- browser selected-history pointer `dsa-selected-history-id`
- browser active chat session pointer `dsa_chat_session_id`
- browser rule backtest preset cache `wolfystock.ruleBacktestPresets.v1`
- `portfolio_fx_rates`

### Durable derived materializations

- `portfolio_positions`
- `portfolio_position_lots`
- `portfolio_daily_snapshots`
- scanner comparison/review summaries rebuilt from persisted run data plus current market history
- readable execution-log summaries derived from structured execution events

### Transient memory state

- task queue worker state, duplicate-submission map, SSE fanout
- `ConversationManager` in-memory TTL session/context map
- loaded config/runtime singletons
- live IBKR session token

### Generated/exported artifacts

- scanner watchlist markdown files
- backtest CSV/JSON exports and trace files
- generated `apps/dsa-web/public/stocks.index.json`
- saved analysis/market-review report files

## Schema Gaps

1. `execution_log_sessions` / `execution_log_events` gap:
   - current runtime has durable session/event observability
   - initial schema v1 did not
   - `admin_logs` / `system_actions` are not enough to preserve current list/detail filtering and event replay semantics
   - status: resolved in companion `postgresql-baseline-design.md`, `postgresql-baseline-plan.md`, and `postgresql-baseline-v1.sql`
2. `portfolio_sync_cash_balances` gap:
   - current broker overlay stores per-currency cash rows separately
   - initial schema v1 only stored aggregate cash totals on `portfolio_sync_states`
   - status: resolved in companion `postgresql-baseline-design.md`, `postgresql-baseline-plan.md`, and `postgresql-baseline-v1.sql`
3. Analysis auxiliary artifact gap:
   - current history detail relies on `news_intel`
   - current analysis pipeline also persists `fundamental_snapshot`
   - schema v1 does not decide whether these become first-class rows or analysis-scoped artifacts
4. Notification-scope gap:
   - current per-user persisted targets are only email/Discord
   - global operator channels are system config, not user-owned targets
   - status: resolved for Phase A scope/verification in companion `postgresql-baseline-design.md` and `postgresql-baseline-plan.md`; future phase design is still required for broader notification/config migration
5. Watchlist promotion gap:
   - current watchlists are derived from runs and preferred-per-date selection logic
   - schema v1 has first-class watchlists but no explicit uniqueness/promotion rule
6. Portfolio materialization gap:
   - current implementation persists lots, daily snapshots, and FX rates
   - schema v1 only partially models current materialized state
7. Market-metadata scope gap:
   - schema v1 handles Parquet/NAS metadata well
   - current reproducibility also depends on `stock_daily`, scanner CSV cache, and static seeds
   - the baseline needs an explicit stance on whether these are registrable metadata inputs or out-of-band caches

## Migration Blockers

### Phase A blockers found by the audit

The following issues existed in the original baseline artifacts and are now resolved in the companion docs updated by this audit:

1. Auth transitional semantics were not explicit enough in the implementation plan.
2. Personal notification-target scope was easy to over-migrate.
3. Schema v1 omitted portfolio sync cash overlay rows.
4. Schema v1 omitted execution-session/event observability.

After those corrections, no remaining blocker was found for starting Phase A.

### Not a Phase-A blocker, but must be resolved before later phases

1. Analysis/news/fundamental auxiliary artifact mapping before Phase B.
2. Watchlist promotion/uniqueness rules before Phase D.
3. Market-data fallback metadata policy before Phase C/D/E provenance wiring.
4. Portfolio lots/snapshots/fx materialization policy before Phase F cutover.

## Required Design Corrections Before Implementation

### Applied now, before Phase A implementation

1. Added PostgreSQL tables for execution-session/event observability equivalent to current `execution_log_sessions` and `execution_log_events`.
2. Added PostgreSQL `portfolio_sync_cash_balances` for parity with current broker overlay semantics.
3. Updated Phase A scope and verification to preserve:
   - auth-disabled transitional bootstrap-admin current-user semantics
   - legacy signed admin-cookie compatibility during coexistence
4. Updated Phase A scope to state:
   - only current per-user email/Discord targets are normalized into `notification_targets`
   - global operator channels remain in `.env` / system config until Phase G

### Required before later phases, but not a Phase-A blocker

1. Decide whether `news_intel` and `fundamental_snapshot` become first-class analysis tables or analysis-scoped artifact rows.
2. Decide whether `watchlists` are unique per `(scope, owner, market, profile, date)` or versioned/promoted from multiple runs.
3. Decide whether `portfolio_position_lots`, `portfolio_daily_snapshots`, and `portfolio_fx_rates` remain persisted materializations or become re-derivable caches.
4. Decide how `market_data_manifests`/`market_data_usage_refs` should reference current `stock_daily`, scanner CSV cache, and static symbol/index seeds when they materially influence run results.

## Final Readiness Verdict

**READY FOR PHASE A**

Rationale:

- The current codebase is already close enough to the baseline in auth, user-owned business data, scanner/backtest/portfolio ownership boundaries, and the OHLCV-vs-business-data storage split.
- The original baseline had a few under-modeled or omitted semantics, but the companion design/plan/schema docs were corrected in this audit.
- After those targeted corrections, Phase A can begin without hidden identity/session or notification-scope surprises.

## Recommended Next Exact Step

Use the corrected baseline docs and start Phase A with a narrow implementation prompt:

1. Preserve current auth-disabled transitional bootstrap-admin behavior and legacy cookie compatibility.
2. Introduce PostgreSQL-backed `app_users`, `app_user_sessions`, `guest_sessions`, `user_preferences`, and `notification_targets` only.
3. Migrate only current per-user email/Discord target semantics.
4. Do not change guest preview persistence semantics.
5. Do not touch scanner/backtest/portfolio runtime paths yet.
