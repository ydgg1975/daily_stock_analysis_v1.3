# Multi-User Foundation Phase 2

## Phase Objective

Establish the minimum real authentication and session foundation for the multi-user transition without drifting into full authorization or UI role-splitting:

- normal-user login
- authenticated cookie-backed sessions
- logout
- backend current-user resolution
- admin auth normalization onto the same app-user identity model
- explicit transitional behavior while auth is disabled

## Files Changed

- `src/auth.py`
- `src/storage.py`
- `api/deps.py`
- `api/middlewares/auth.py`
- `api/v1/endpoints/auth.py`
- `api/v1/endpoints/analysis.py`
- `api/v1/endpoints/history.py`
- `api/v1/endpoints/scanner.py`
- `api/v1/endpoints/backtest.py`
- `api/v1/endpoints/portfolio.py`
- `api/v1/endpoints/agent.py`
- `src/services/task_queue.py`
- `src/services/analysis_service.py`
- `src/core/pipeline.py`
- `src/agent/conversation.py`
- `src/agent/executor.py`
- `src/agent/orchestrator.py`
- `apps/dsa-web/src/api/auth.ts`
- `apps/dsa-web/src/contexts/AuthContext.tsx`
- `apps/dsa-web/src/pages/LoginPage.tsx`
- `apps/dsa-web/src/contexts/__tests__/AuthContext.test.tsx`
- `apps/dsa-web/src/components/settings/SettingsCategoryNav.tsx`
- `tests/test_auth.py`
- `tests/test_auth_api.py`
- `docs/CHANGELOG.md`

## What Was Added

### Authentication and session model

- Added persistent `app_user_sessions` storage for revocable web sessions.
- Reworked `dsa_session` cookies into signed identity-bearing v2 tokens that carry:
  - `user_id`
  - `username`
  - `role`
  - `session_id`
  - issue/expiry timestamps
- Added `/api/v1/auth/me` current-user endpoint.
- Added minimal normal-user account bootstrap via `/api/v1/auth/login`:
  - existing users can sign in
  - new normal users can be created with username + password in the same endpoint
- Added logout behavior that revokes the current persisted session row and clears the cookie.

### Current-user resolution

- Added `CurrentUser` in `api/deps.py`.
- Added `resolve_current_user()` so backend request handling can resolve:
  - authenticated normal users
  - authenticated admins
  - transitional bootstrap admin while auth is disabled
- Added `get_current_user()` / `get_optional_current_user()` dependencies.
- Updated auth middleware to enforce auth by resolved identity, not by the old raw cookie check alone.

### Admin normalization

- Admin is now normalized as a role on `app_users`.
- The seeded bootstrap admin remains the transitional admin identity.
- Legacy `.admin_password_hash` is still supported temporarily, but is mirrored into the bootstrap admin row in `app_users`.
- Legacy admin session/unlock tokens remain readable for compatibility while new sessions use the v2 identity token format.

### Owner-aware request wiring

- Major user-owned entry points now accept authenticated identity and pass resolved `owner_id` into Phase 1 ownership-aware services:
  - analysis
  - history
  - scanner
  - backtest
  - portfolio
  - chat/agent conversation
- Task queue, pipeline, analysis service, and conversation execution paths now carry `owner_id` through execution and persistence.

### Frontend session wiring

- Web auth client now supports:
  - `login`
  - `logout`
  - `getCurrentUser`
  - auth status with `currentUser`
- `AuthContext` now stores `currentUser` and refreshes session state after login/logout.
- `LoginPage` now supports:
  - bootstrap admin setup
  - normal login
  - minimal create-account flow for normal users

## What Was Intentionally Preserved

- Phase 1 ownership model and data migrations were not redesigned.
- No full Phase 3 authorization rollout was attempted.
- No frontend role-aware navigation split was implemented yet.
- No admin-vs-user settings UX split was implemented yet.
- Existing scanner, backtest, analysis, chat, and portfolio core flows remain on their current surfaces.
- The legacy bootstrap admin credential file is preserved temporarily for migration compatibility instead of being hard-cut immediately.

## Auth / Session Design Chosen

- Transport: existing HTTP-only cookie session model was kept.
- Session format: signed v2 identity token in `dsa_session`.
- Session revocation: persisted `app_user_sessions` rows are checked during session resolution and revoked on logout.
- Account model: `app_users` is the single identity table for both normal users and admins.
- Password storage: PBKDF2-hashed password strings, with bootstrap admin credential mirrored from the legacy file into `app_users`.

This was chosen to keep the implementation minimal and compatible with the current app shell instead of introducing OAuth, JWT distribution, or a larger auth rewrite.

## Admin Normalization Strategy

- `bootstrap-admin` remains the seeded transitional admin owner from Phase 1.
- That admin now also resolves as a normal `app_users` row with `role=admin`.
- Existing admin unlock flows remain available, but now sit on top of the same current-user identity model.
- Phase 3 can later enforce admin-only endpoints by checking `CurrentUser.is_admin` instead of relying on a separate admin-only auth universe.

## Current-User Resolution Strategy

- Middleware and endpoint dependencies resolve identity from the session cookie through `resolve_current_user()`.
- If auth is enabled:
  - requests without a valid session resolve to unauthenticated
  - requests with a valid persisted session resolve to the matching `app_users` row
- If auth is disabled:
  - requests resolve to the transitional bootstrap admin identity
  - that identity is marked `transitional=True` and `is_authenticated=False`
- Endpoint/service wiring uses resolved `owner_id` when present and keeps older direct-call test paths compatible when no runtime request identity exists.

## Transitional Behavior

- Auth disabled:
  - the system remains usable in transitional bootstrap mode
  - current-user resolution returns the bootstrap admin owner for compatibility
  - this preserves current usability while the product is migrating
- Auth enabled:
  - callers must establish a real session through login
  - admin/system flows resolve through the same current-user model as normal users
- Legacy admin credential/session compatibility:
  - old bootstrap admin password storage remains supported temporarily
  - legacy admin session/unlock tokens still parse
  - new login/logout/session behavior uses persisted app-user sessions

This transitional behavior is explicit and intended only as a migration bridge, not as the end-state model.

## Verification Performed

### Backend compile

- `python3 -m py_compile api/v1/endpoints/auth.py api/v1/endpoints/portfolio.py api/v1/endpoints/scanner.py api/v1/endpoints/backtest.py api/v1/endpoints/history.py api/v1/endpoints/analysis.py api/v1/endpoints/agent.py api/deps.py api/middlewares/auth.py src/auth.py src/storage.py src/services/task_queue.py src/services/analysis_service.py src/core/pipeline.py src/agent/conversation.py src/agent/executor.py src/agent/orchestrator.py`
- `python3 -m py_compile api/deps.py api/v1/endpoints/analysis.py api/v1/endpoints/scanner.py api/v1/endpoints/backtest.py api/v1/endpoints/history.py src/services/task_queue.py`

### Backend tests

- `python3 -m pytest tests/test_auth.py tests/test_auth_api.py tests/test_auth_status_setup_state.py tests/test_portfolio_api.py -q`
- `python3 -m pytest tests/test_analysis_history.py tests/test_market_scanner_service.py tests/test_market_scanner_ops_service.py tests/test_backtest_service.py tests/test_portfolio_service.py tests/test_conversation_manager.py tests/test_agent_executor.py tests/test_task_queue_execution_chain.py tests/test_multi_user_phase1.py -q`
- `python3 -m pytest tests/test_system_config_api.py tests/test_analysis_api_contract.py tests/test_market_scanner_api_contract.py tests/test_backtest_api_contract.py -q`
- `python3 -m pytest tests/test_analysis_api_contract.py tests/test_market_scanner_api_contract.py tests/test_backtest_api_contract.py -q`

### Frontend verification

- `npm test -- src/contexts/__tests__/AuthContext.test.tsx src/pages/__tests__/LoginPage.test.tsx`
- `npm run lint`
- `npm run build`

## Phase 2 Acceptance Gate

### Result

Passed.

### Why It Passes

- Normal-user authentication works.
- Logout works and revokes persisted sessions.
- Backend current-user resolution works through a shared identity model.
- Admin auth is normalized onto `app_users` and current-user resolution.
- Phase 1 ownership wiring remains intact and continues to pass ownership regression tests.
- Core product APIs for analysis, scanner, backtest, history, portfolio, and chat-related execution paths passed focused regression coverage.
- Frontend auth/session wiring builds, lints, and passes focused auth tests.

## Remaining Risks Or Limitations

- Phase 3 authorization still needs to enforce admin-only and cross-user access rules consistently across all endpoints.
- Frontend still exposes the pre-Phase-4 product shell; role-aware nav/settings splitting is intentionally deferred.
- Normal-user creation is intentionally minimal and does not include account recovery, invitation flows, or user management UI.
- Transitional bootstrap mode still exists while auth is disabled and should be reduced later once the migration is complete.
- Some unrelated frontend files were already dirty in the branch; only a minimal no-behavior-change cleanup was made where lint/build would otherwise fail.
