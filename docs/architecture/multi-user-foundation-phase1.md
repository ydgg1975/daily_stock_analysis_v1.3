# Multi-User Foundation Phase 1

## Phase Objective

Introduce the minimum correct data ownership foundation for multi-user support without rewriting the whole product:

- tie user-owned entities to a concrete app user identity
- keep global/system-owned data separate
- define an explicit transitional owner for legacy single-user rows
- preserve current scanner, backtest, analysis, chat, and portfolio flows in transitional mode

## Files Changed

- `src/multi_user.py`
- `src/storage.py`
- `src/repositories/analysis_repo.py`
- `src/repositories/backtest_repo.py`
- `src/repositories/rule_backtest_repo.py`
- `src/repositories/scanner_repo.py`
- `src/repositories/portfolio_repo.py`
- `src/services/history_service.py`
- `src/services/backtest_service.py`
- `src/services/rule_backtest_service.py`
- `src/services/market_scanner_service.py`
- `src/services/market_scanner_ops_service.py`
- `src/services/portfolio_service.py`
- `tests/test_multi_user_phase1.py`
- `docs/CHANGELOG.md`

## What Was Added Or Changed

### Ownership primitives

- Added shared multi-user constants in `src/multi_user.py`.
- Added first-class `app_users`, `user_preferences`, and `conversation_sessions` models.
- Added a seeded transitional bootstrap admin identity:
  - `id = bootstrap-admin`
  - `username = admin`
  - `role = admin`

### Ownership fields and defaults

- Added `owner_id` to user-owned persistence domains:
  - `analysis_history`
  - `backtest_results`
  - `backtest_runs`
  - `backtest_summaries`
  - `rule_backtest_runs`
  - `market_scanner_runs`
  - `portfolio_accounts`
  - `conversation_sessions`
- Added ORM-side bootstrap defaults so transitional inserts that still build model rows directly do not silently become ownerless.

### Mixed scanner scope

- Added `scope` to `market_scanner_runs`.
- Implemented mixed scanner behavior:
  - manual/user runs => `scope=user` plus `owner_id`
  - scheduled/operator runs => `scope=system` plus `owner_id=NULL`
- Updated scanner service/repository visibility so normal user views see:
  - their own user-scoped runs
  - system-scoped watchlists
- Updated operator/watchlist flows to resolve scheduled runs as system-scoped.

### Repository and service ownership wiring

- Analysis/history queries and deletes now filter by owner unless explicitly asked to include all owners.
- Historical backtest runs/results/summaries now resolve through owner-aware repositories and owner-aware sample preparation.
- Rule backtest runs now persist and query by owner.
- Portfolio account CRUD and account-scoped event listings now resolve through owner-aware account visibility instead of global account lists.
- Chat persistence now creates/uses first-class conversation session ownership rows and blocks cross-owner session access.

### Transitional migration behavior

- Startup migration now:
  - ensures the bootstrap admin user exists
  - adds missing owner/scope columns
  - backfills legacy `analysis_history`, `backtest_*`, `rule_backtest_runs`, and `portfolio_accounts` rows to the bootstrap owner
  - recreates legacy `backtest_summaries` uniqueness around owner-aware keys
  - infers legacy scanner run scope from stored trigger metadata
  - materializes `conversation_sessions` from legacy `conversation_messages`

## What Was Intentionally Preserved

- Existing scanner, backtest, analysis history, chat, and portfolio APIs/services continue to work in transitional single-user mode.
- No frontend role split or auth/session rewrite was attempted in this phase.
- No admin/system settings UI was merged into user settings.
- No global/system config surface was moved or removed yet.
- Scheduled scanner/operator artifacts remain distinct from user-owned scanner history rather than being collapsed into one bucket.

## Verification Performed

### Compile

- `python3 -m py_compile src/multi_user.py src/storage.py src/repositories/analysis_repo.py src/repositories/backtest_repo.py src/repositories/rule_backtest_repo.py src/repositories/scanner_repo.py src/repositories/portfolio_repo.py src/services/history_service.py src/services/backtest_service.py src/services/rule_backtest_service.py src/services/market_scanner_service.py src/services/market_scanner_ops_service.py src/services/portfolio_service.py`
- `python3 -m py_compile tests/test_multi_user_phase1.py`

### Existing backend regression coverage

- `python3 -m pytest tests/test_market_scanner_service.py tests/test_market_scanner_ops_service.py tests/test_portfolio_service.py tests/test_backtest_service.py tests/test_storage.py -q`
- `python3 -m pytest tests/test_analysis_history.py -q`

### New Phase 1 ownership coverage

- `python3 -m pytest tests/test_multi_user_phase1.py -q`

Covered behaviors:

- bootstrap admin creation and legacy backfill
- analysis history owner isolation
- chat session owner isolation
- scanner mixed `user/system` visibility
- portfolio bootstrap default owner plus per-owner account isolation
- backtest evaluation isolation by owner

## Phase 1 Acceptance Gate

### Result

Passed.

### Why It Passes

- Ownership model is implemented for the intended user-owned entities.
- Scanner mixed behavior now distinguishes user-owned manual runs from system-owned scheduled runs.
- Transitional behavior is explicit and tested through bootstrap-owner migration/backfill coverage.
- Existing backend flows for analysis, scanner, backtest, chat, and portfolio continue to pass relevant regression tests.

## Remaining Risks Or Blockers

- Authentication/session identity for normal users is not implemented yet. Current transitional behavior still resolves unnamed callers to the bootstrap admin owner.
- Backend authorization is not fully enforced yet at the API layer; Phase 3 still needs current-user and admin permission gates.
- Frontend route/nav/settings splitting is not started yet.
- Rule backtest ownership is wired and compile-covered, but Phase 1 does not yet add a dedicated rule-backtest ownership regression test.
- Mixed scanner visibility is now correct at the storage/service layer, but role-aware frontend exposure still belongs to later phases.
