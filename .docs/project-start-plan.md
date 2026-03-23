# Project Start Plan

Status: Verified kickoff plan for starting the crypto scanner project from the current repo baseline.

Phase 0 status: Planning gate passed on 2026-03-20.

## Goal

Start the project in a way that supports a production-grade crypto New Launch Scanner, not only a demo or thin MVP.

## Product Shape

The project should be built as four connected capabilities:

1. Discovery
2. Scanner Product Surface
3. Risk And Alerting
4. Selective AI Reasoning

## Workstreams

### Workstream 1: Discovery And Persistence

Purpose:

- ingest new pools every 60 seconds
- normalize them across chains
- deduplicate them
- persist them safely

Primary files to add or extend:

- `data_provider/crypto_launch_fetcher.py`
- `src/services/crypto_launch_service.py`
- `src/repositories/crypto_launch_repo.py`
- `src/storage.py`
- `src/config.py`
- `main.py`
- `src/scheduler.py`

Exit criteria:

- launches are fetched and persisted every 60 seconds
- duplicates are not reinserted
- one broken source does not take down the whole scanner

### Workstream 2: Crypto API Surface

Purpose:

- expose recent launches, detail views, and refresh/status for the scanner foundation

Primary files to add or extend:

- `api/v1/endpoints/crypto.py`
- `api/v1/schemas/crypto.py`
- `api/v1/router.py`

Exit criteria:

- launch list and launch detail endpoints are queryable
- filters are supported cleanly
- crypto APIs are isolated from stock-only endpoints
- saved settings remain deferred until after the core feed is stable

### Workstream 3: Scanner Web Experience

Purpose:

- deliver the main scanner board and detail interaction

Primary files to add or extend:

- `apps/dsa-web/src/App.tsx`
- `apps/dsa-web/src/pages/CryptoScannerPage.tsx`
- `apps/dsa-web/src/stores/cryptoLaunchStore.ts`
- `apps/dsa-web/src/components/crypto/CryptoLaunchTable.tsx`
- `apps/dsa-web/src/components/crypto/CryptoLaunchFilters.tsx`
- `apps/dsa-web/src/components/crypto/CryptoLaunchDetailDrawer.tsx`
- `apps/dsa-web/src/hooks/useDashboardLifecycle.ts`

Exit criteria:

- scanner page works on desktop and mobile
- filters update results clearly
- detail drawer opens quickly
- DexScreener outbound link is available

### Workstream 4: Risk And Alert Layer

Purpose:

- rank launches deterministically and prepare alerting

Primary files to add or extend:

- `src/services/crypto_risk_service.py`
- `src/services/crypto_launch_service.py`
- `src/notification.py`
- `src/notification_sender/`
- `src/services/system_config_service.py`

Exit criteria:

- launches can be scored by deterministic rules
- watchlist or alert rules can be stored
- notifications can be triggered later without redesigning the pipeline

### Workstream 5: Selective Intelligence Layer

Purpose:

- add TradingAgents-inspired reasoning without slowing the scanner lane

Primary files to add or extend:

- `src/services/crypto_ai_review_service.py`
- `src/services/crypto_launch_service.py`
- `api/v1/endpoints/crypto.py`
- optional new package for the local multi-agent graph if introduced

Suggested role mapping:

- Launch Analyst
- Sentiment Analyst
- On-chain Risk Analyst
- Microstructure Analyst
- Bull Researcher
- Bear Researcher
- Risk Gate
- Final Decision Summarizer

Exit criteria:

- AI runs asynchronously for shortlisted launches only
- the scanner still works fully when AI is disabled

## Delivery Order

The phase labels below refer to the crypto scanner implementation sequence, not the repo-wide Stabilize / Expand / Polish roadmap.

### Crypto Phase 1

- discovery fetcher
- persistence model
- snapshot history
- config keys
- refresh scheduler
- crypto API list/detail/refresh/status
- scanner page
- filters and sort
- detail drawer

### Crypto Phase 2

- deterministic risk scoring
- saved settings endpoints
- saved presets
- watchlist and alert rules

### Crypto Phase 3

- TradingAgents-inspired AI review layer
- decision summaries for shortlisted launches

### Crypto Phase 4

- observability
- replay/backfill support
- tuning and cost controls

## Critical Rules Before Coding

1. Do not route crypto through `src/core/trading_calendar.py`.
2. Do not reuse stock-code normalization for pair or token addresses.
3. Do not run multi-agent reasoning in the 60-second scanner loop.
4. Keep crypto APIs and schemas separate from stock-only request naming.
5. Make partial enrichment non-blocking.

## Verification Strategy

Local repo validation should stay aligned with current project reality.

- Backend deterministic checks: `python3 -m pytest -m "not network"`
- Governance/docs changes: `python3 scripts/check_ai_assets.py`
- Web checks: `cd apps/dsa-web && npm ci && npm run lint && npm run build && npm run test`

## Phase 0 Decisions Locked

1. The first implementation bead is the wide first slice: discovery + persistence + API + scanner page.
2. `CryptoLaunchSnapshot` ships with `CryptoLaunch` in Phase 1.
3. Saved settings endpoints are deferred until after the core scanner feed is stable.
4. The first release is web-first; Electron remains passive reuse only.
5. Security providers remain optional and non-blocking in Phase 1.
6. Alerting and selective AI review remain deferred beyond the deterministic scanner foundation.

## Recommended First Build Slice

If implementation starts now, the Phase 1 slice is already locked as:

1. discovery + enrichment fetcher/service/repository wiring
2. `src/storage.py` crypto models for `CryptoLaunch` + `CryptoLaunchSnapshot`
3. scheduler + config wiring for the 60-second loop
4. `api/v1/crypto/*` list/detail/refresh/status endpoints
5. scanner page + filters + detail drawer in the web app

That slice unlocks a usable, end-to-end scanner foundation without prematurely committing to settings, alerts, or AI complexity.
