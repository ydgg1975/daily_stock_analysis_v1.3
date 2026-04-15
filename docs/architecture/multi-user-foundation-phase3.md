# Multi-User Foundation Phase 3

## Phase Objective

Turn the Phase 1 ownership model and Phase 2 current-user foundation into real backend-enforced authorization without drifting into frontend role redesign:

- protect admin-only/system-owned APIs
- enforce owner isolation for user-owned APIs
- block obvious cross-user access paths
- keep scanner mixed scope explicit:
  - manual runs = user-owned
  - scheduled/operator runs = system-owned/admin context

## Authorization Audit Map

### A. User-owned and owner-restricted

- `portfolio` accounts / trades / cash ledger / snapshots
- `history` analysis list / detail / delete
- `analysis` task list / task status / task SSE
- `backtest` runs / results / rule backtest history/detail/status/cancel
- `agent` chat sessions / messages / deletions
- `scanner` manual run history and manual run detail

### B. Admin-only / system-owned

- `system_config` read / schema / update / validate / test-channel
- `admin_logs` sessions / session detail
- `usage` global LLM usage summary
- `agent /chat/send` global notification dispatch
- `scanner` operational status
- `scanner` scheduled/system watchlists (`today`, `recent`)

### C. Mixed behavior with explicit branch logic

- `scanner`
  - `POST /scanner/run` stays user-owned manual execution
  - `GET /scanner/runs` is forced to user scope
  - `GET /scanner/runs/{id}` resolves user scope first and only allows system scope fallback for admins
  - `GET /scanner/watchlists/*` and `GET /scanner/status` are admin-only system views

### D. Transitional compatibility paths

- auth-disabled bootstrap mode still resolves to transitional bootstrap admin
- direct endpoint/unit-test invocation still tolerates unresolved `Depends(...)` placeholders where Phase 2 compatibility already relied on that behavior

## Files Changed

- `api/deps.py`
- `api/v1/endpoints/system_config.py`
- `api/v1/endpoints/admin_logs.py`
- `api/v1/endpoints/usage.py`
- `api/v1/endpoints/agent.py`
- `api/v1/endpoints/scanner.py`
- `api/v1/endpoints/analysis.py`
- `src/services/task_queue.py`
- `src/agent/memory.py`
- `src/agent/agents/base_agent.py`
- `src/agent/orchestrator.py`
- `tests/test_multi_user_phase3.py`
- `docs/CHANGELOG.md`

## Authorization Primitives Added Or Refined

- Added `require_admin_user()` in `api/deps.py` for reusable admin-only endpoint enforcement.
- Added `is_admin_user()` helper for explicit role-aware branching in mixed endpoints.
- Added `ensure_current_user_matches_owner()` for stable owner-id validation when an endpoint accepts an explicit owner field.
- Reused existing `CurrentUser` / `get_current_user()` resolution from Phase 2 instead of introducing a new RBAC layer.

## What Changed

### Admin-only protection

- `system_config` now requires admin identity even for read/schema endpoints, and write/validate/test-channel no longer depend on a second admin-unlock token once the caller is already an authenticated admin.
- `admin_logs` now requires admin identity without a redundant unlock layer; frontend visibility still remains bounded by explicit `Admin Mode`.
- `POST /api/v1/system/actions/runtime-cache/reset` adds one bounded admin-maintenance action, paired with confirmation in the Web control plane instead of a generic unlock wall.
- `usage` summary is now admin-only.
- `agent /chat/send` is now admin-only because it triggers global notification channels.

### Owner isolation and cross-user blocking

- `analysis` sync follow-up history lookup now carries owner context when available.
- `analysis` task list stats are now owner-scoped instead of reporting global counts.
- `analysis` SSE task stream now drops events whose owner does not match the current user.
- task queue duplicate detection is now owner-scoped, so one user’s in-flight analysis no longer blocks another user from analyzing the same stock.
- task queue task lookup/list/stats now filter strictly by owner when an owner is supplied.
- `agent` chat session detail/delete now convert cross-owner access attempts into stable `404 not_found` responses instead of leaking through as generic server errors.
- `agent` chat context now carries `owner_id` into orchestrator memory lookup so agent memory reads stay owner-scoped.

### Scanner mixed-scope enforcement

- manual scanner history endpoint now forces `scope=user`
- system watchlist/status endpoints now require admin identity
- scanner run detail now resolves:
  - current user’s manual run first
  - system/admin run only when requester is admin

## What Was Intentionally Preserved

- Phase 2 auth/session design was not redesigned.
- No frontend role split or settings UX split was attempted here.
- No broader RBAC framework or user-management UI was introduced.
- Portfolio/backtest/history service ownership model from Phase 1 remained intact.
- Admins were not granted blanket read access to every other user-owned record in this phase; only explicit admin/system surfaces were opened.

## Transitional Notes

- Auth-disabled mode still resolves to the bootstrap admin identity, so local transitional setups remain usable.
- Existing Phase 1 mixed scanner persistence model remains the storage truth:
  - manual runs persist as user scope
  - scheduled/operator runs persist as system scope
- Phase 3 now makes those scope boundaries explicit at API access time.

## Verification Performed

### Compile

- `python3 -m py_compile api/deps.py api/v1/endpoints/system_config.py api/v1/endpoints/admin_logs.py api/v1/endpoints/usage.py api/v1/endpoints/agent.py api/v1/endpoints/scanner.py api/v1/endpoints/analysis.py src/services/task_queue.py src/agent/memory.py src/agent/agents/base_agent.py src/agent/orchestrator.py tests/test_multi_user_phase3.py`

### Backend tests

- `python3 -m pytest tests/test_multi_user_phase3.py -q`
- `python3 -m pytest tests/test_auth.py tests/test_auth_api.py tests/test_system_config_api.py tests/test_analysis_api_contract.py tests/test_analysis_history.py tests/test_market_scanner_api_contract.py tests/test_market_scanner_service.py tests/test_market_scanner_ops_service.py tests/test_backtest_api_contract.py tests/test_backtest_service.py tests/test_portfolio_api.py tests/test_portfolio_service.py tests/test_conversation_manager.py tests/test_task_queue_execution_chain.py tests/test_multi_user_phase1.py tests/test_multi_user_phase3.py -q`

## Phase 3 Acceptance Gate

### Result

Passed.

### Why It Passes

- Admin-only endpoints are backend-protected through reusable admin dependencies.
- User-owned endpoints now enforce owner-scoped filtering on the obvious API paths exercised in this phase.
- Cross-user access is blocked in portfolio/history/chat/backtest/scanner regression coverage.
- Scanner mixed behavior is explicit and test-covered:
  - manual runs stay owner-scoped
  - scheduled/system watchlists stay admin/system-scoped
- Phase 1 ownership and Phase 2 auth/session regression suites remained green.

## Remaining Risks Or Limitations

- Full frontend role visibility cleanup is still deferred to the next phase.
- Some older non-primary internal helpers still assume bootstrap/transitional defaults when called without a resolved user; those paths should continue to be reviewed as later phases tighten the product surface.
- Admin override for user-owned records remains intentionally narrow in this phase; if an operator workflow later needs explicit per-user support tooling, that should be designed explicitly instead of widening access implicitly.
