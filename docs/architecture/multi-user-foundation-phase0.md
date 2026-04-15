# Multi-User Foundation Phase 0 Audit

## Scope

This document captures the Phase 0 audit and design map for turning WolfyStock from a single shared instance into a real multi-user product with:

- isolated user-owned data
- admin-only system configuration and operator surfaces
- backend-enforced ownership and authorization

The goal of this phase is to define safe boundaries before schema and auth changes begin.

## Current Audit Summary

### Auth and admin behavior

- The current web auth model is admin-password-only and file-backed.
- Auth state is driven by `ADMIN_AUTH_ENABLED` plus `.admin_password_hash` and `.session_secret`.
- Session cookies only prove "valid admin session", not "which user is this".
- There is no persisted user table, no current-user identity model, and no role claim in session data.
- Backend API protection is applied globally by `api/middlewares/auth.py`, but only as a binary "admin session required when auth is enabled".
- Admin-only write-sensitive actions use a second `X-Admin-Unlock-Token` guard for system settings and admin logs.

Relevant files:

- `src/auth.py`
- `api/middlewares/auth.py`
- `api/v1/endpoints/auth.py`
- `api/v1/endpoints/system_config.py`
- `api/v1/endpoints/admin_logs.py`

### Settings and system config

- The frontend currently exposes one mixed `SettingsPage` that combines:
  - UI preferences
  - admin unlock
  - auth mode management
  - global provider/API config
  - global notification config
  - global schedule/system config
- The backend system config service reads and writes global `.env` state.
- System config is inherently instance-wide today.

Relevant files:

- `apps/dsa-web/src/pages/SettingsPage.tsx`
- `apps/dsa-web/src/hooks/useSystemConfig.ts`
- `src/services/system_config_service.py`
- `src/core/config_registry.py`
- `src/config.py`

### Portfolio

- `portfolio_accounts` already includes `owner_id`, but the rest of the stack does not resolve or enforce current-user ownership.
- API callers may pass `owner_id` directly.
- Listing, reads, updates, deletes, snapshot, risk, and event writes are not scoped to the authenticated principal.

Relevant files:

- `src/storage.py`
- `src/repositories/portfolio_repo.py`
- `src/services/portfolio_service.py`
- `api/v1/endpoints/portfolio.py`
- `apps/dsa-web/src/pages/PortfolioPage.tsx`

### Scanner

- Scanner runs and candidates are stored globally in `market_scanner_runs` and `market_scanner_candidates`.
- Manual and scheduled/operator runs share the same persistence layer.
- Trigger metadata is stored in JSON/diagnostics, not in an ownership or scope model.
- Frontend history and "today watchlist" views are global.

Relevant files:

- `src/storage.py`
- `src/repositories/scanner_repo.py`
- `src/services/market_scanner_service.py`
- `src/services/market_scanner_ops_service.py`
- `api/v1/endpoints/scanner.py`
- `apps/dsa-web/src/pages/ScannerPage.tsx`

### Backtest

- Historical backtest data is stored globally in `backtest_runs`, `backtest_results`, `backtest_summaries`.
- Rule backtest data is stored globally in `rule_backtest_runs`, `rule_backtest_trades`.
- There is no owner on runs, result history, or derived summaries.
- Frontend history/result access is global.

Relevant files:

- `src/storage.py`
- `src/repositories/backtest_repo.py`
- `src/repositories/rule_backtest_repo.py`
- `src/services/backtest_service.py`
- `src/services/rule_backtest_service.py`
- `api/v1/endpoints/backtest.py`
- `apps/dsa-web/src/pages/BacktestPage.tsx`

### Analysis history and reports

- `analysis_history` is global and has no owner field.
- History queries, detail lookup, markdown generation, and delete operations are global.
- The homepage archive/history panel reads global history.

Relevant files:

- `src/storage.py`
- `src/repositories/analysis_repo.py`
- `src/services/history_service.py`
- `api/v1/endpoints/history.py`
- `apps/dsa-web/src/api/history.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`

### Chat sessions and messages

- Chat persistence uses `conversation_messages` only.
- Session identity is derived from `session_id` strings, not from a first-class session row tied to a user.
- There is an optional `user_id` filter for session prefix matching, mainly for bot-style platform session isolation.
- Web chat does not pass a user identity and persists globally addressable session ids.

Relevant files:

- `src/storage.py`
- `src/agent/conversation.py`
- `api/v1/endpoints/agent.py`
- `apps/dsa-web/src/stores/agentChatStore.ts`
- `apps/dsa-web/src/pages/ChatPage.tsx`

### Existing user/account/contact/auth models

- There is no first-class application `User` model today.
- The only user-like fields found are:
  - `portfolio_accounts.owner_id`
  - requester metadata fields on `news_intel`
  - chat session prefix filtering for bot integrations
- None of these form a reusable application identity system for web multi-user access.

### Frontend routes and nav visibility

- Route access is currently binary:
  - if admin auth is enabled and logged out, redirect to `/login`
  - otherwise show the full app
- Sidebar navigation shows the same product surfaces to the logged-in actor:
  - home
  - scanner
  - chat
  - portfolio
  - backtest
  - settings
- Admin logs exist as `/admin/logs`, but are reachable once inside the product and guarded only by admin unlock semantics.
- There is no role-aware route tree or role-aware nav model.

Relevant files:

- `apps/dsa-web/src/App.tsx`
- `apps/dsa-web/src/components/layout/SidebarNav.tsx`
- `apps/dsa-web/src/contexts/AuthContext.tsx`
- `apps/dsa-web/src/pages/LoginPage.tsx`

### Backend dependency and permission patterns

- There is no `get_current_user` dependency today.
- There is no `require_admin` or ownership dependency used across product APIs.
- The only reusable permission mechanisms are:
  - auth middleware verifying the admin session cookie
  - admin unlock header verification for extra-sensitive admin actions

### Storage pattern

- Persistence is centered on SQLite + SQLAlchemy models in `src/storage.py`.
- Some domains use repositories; some still call `DatabaseManager` directly.
- Many entities are historical/append-like records, which is compatible with adding ownership fields.
- Chat storage likely needs a session table in addition to message rows for clean ownership and deletion semantics.

## Roles

Phase 0 defines two concrete roles only:

- `user`
  - standard product user
  - may only access their own portfolios, history, chat, scanner artifacts, backtests, and personal settings
- `admin`
  - authenticated product user with all `user` capabilities
  - additionally may access global system config, provider/API settings, schedules, notification channels, and operator logs

Future roles can be added later, but Phase 1-6 should not overbuild generic RBAC.

## Entity Classification

### A. Must become user-owned

- portfolios
- portfolio positions
- portfolio transactions and imports
- analysis history
- chat sessions
- chat messages
- UI preferences
- backtest runs/results/history when initiated from user-facing product flows

### B. Must remain global/system-owned

- provider/API config
- global schedules
- notification channel credentials and routing infrastructure
- admin logs / execution logs
- system prompts / model routes / LLM channel definitions
- runtime/system feature flags such as `SHOW_RUNTIME_EXECUTION_SUMMARY`
- market/reference data caches like `stock_daily`, FX cache, and external data snapshots used as shared infrastructure

### C. Needs mixed behavior

- scanner runs/candidates/watchlists
  - user-triggered/manual artifacts should be user-owned
  - scheduled/operator watchlists should remain global/system-owned
- notification preferences
  - per-user opt-in/UX preferences should be user-owned
  - actual destination/channel credentials stay global
- backtest
  - user-run results are user-owned
  - future operator/batch/system evaluation jobs may remain global if introduced explicitly

### D. Needs explicit decision before implementation

- whether to add persisted per-user notification destinations in this foundation, or defer to a later phase
- whether chat should remain `session_id`-centric with a new `owner_id`, or introduce a first-class `conversation_sessions` table now
- whether existing global scanner/manual history should be migrated into a seeded admin owner or marked as `system` scope
- whether existing historical analysis/backtest records should be assigned to a seeded bootstrap admin user or preserved as legacy-system-owned records

## Minimum Ownership Decisions For Upcoming Phases

### Identity foundation

Phase 1-2 should introduce a first-class application user model.

Recommended minimum fields:

- `id`
- `username` or `email` as login identifier
- `password_hash`
- `role` with values `user` or `admin`
- `is_active`
- `created_at`
- `updated_at`

### Session foundation

The current cookie format should evolve to resolve a real principal, not just "admin session valid".

Minimum session requirements:

- current user id
- role
- issue time / expiry
- logout support

The implementation may stay cookie-based for pragmatism, but must resolve an actual application user.

### Ownership field strategy

Use explicit ownership fields on user-facing records.

Recommended direction:

- `user_id` for records directly owned by an application user
- `scope` for domains that need `user` vs `system`
- `created_by_user_id` only when audit provenance matters separately from ownership

Avoid ambiguous nullable ownership without a matching scope definition.

## Transitional and Migration Strategy

No existing data should be silently dropped.

Recommended transitional strategy:

1. Create a bootstrap admin user during migration/startup when multi-user auth is first enabled.
2. Re-home existing single-instance user-facing data to that bootstrap admin user where safe:
   - portfolio accounts and related ledger data
   - analysis history
   - historical backtests
   - rule backtests
   - existing web chat sessions
3. For mixed domains, mark legacy records explicitly:
   - manual/user-facing artifacts -> bootstrap admin owner
   - scheduled/operator artifacts -> `system` scope
4. Keep global config in `.env` and operator tables unchanged except for stronger admin authorization.

This preserves current data while making the transition explicit.

## Module-by-Module Design Notes

### Portfolio

- Existing `owner_id` field is a useful foothold.
- The API must stop accepting arbitrary `owner_id` from normal clients.
- Service/repository methods need current-user scoping for:
  - list accounts
  - get/update/delete account
  - all event writes
  - snapshot/risk reads

### Analysis and history

- `analysis_history` should gain `user_id`.
- Task queue and history reads must associate persisted reports with the current user.
- Deletes must be owner-scoped.

### Backtest

- `backtest_runs`, `backtest_results`, `backtest_summaries`, `rule_backtest_runs`, and derived trade/result history should gain user ownership or user scope.
- Historical evaluation derived from `analysis_history` must not cross users.

### Scanner

- Scanner persistence needs both ownership and scope semantics.
- Suggested minimum model:
  - `owner_user_id` nullable
  - `scope` enum-like string: `user` or `system`
- Candidate rows inherit scope from their parent run.
- UI should stop merging scheduled/operator runs into the same "my watchlists" surface for normal users.

### Chat

- Current message-only model is weak for ownership enforcement.
- Preferred direction:
  - add `conversation_sessions` with `id`, `user_id`, title, timestamps
  - point messages to session row
- If kept minimal in Phase 1, add `user_id` to messages and enforce session ownership by prefix-independent lookups, but this is a weaker long-term shape.

### Settings split

Recommended product split:

- `User Settings`
  - font size
  - market color convention
  - future theme/personal notification preferences
- `Admin/System Settings`
  - auth mode management
  - provider/API keys
  - LLM routing/channels
  - data source routing
  - notification channels
  - schedules
  - operator flags
  - admin logs entry

### Admin/operator surfaces

Admin-only surfaces should be grouped intentionally rather than sprinkled through the default user settings shell.

Recommended direction:

- keep `/settings` as user settings
- move system configuration to an admin route such as `/admin/settings`
- keep `/admin/logs` admin-only

## Phase 0 Gate Decision

Phase 0 gate can pass when:

- the current shared/global assumptions are mapped
- user-owned vs system-owned domains are classified
- role definitions are clear
- mixed domains and migration decisions are called out explicitly

Status: pass

Reason:

- the current codebase has been audited across auth, settings, portfolio, scanner, backtest, history, chat, frontend routes, backend permissions, and storage
- the ownership and authorization gaps are now concrete enough to begin Phase 1 safely

## Recommended Next Step

Proceed to Phase 1 with the smallest viable ownership foundation:

1. add the application user model
2. add ownership fields to clearly user-owned tables
3. add scope/owner separation for mixed scanner artifacts
4. document the bootstrap migration path for legacy shared data
