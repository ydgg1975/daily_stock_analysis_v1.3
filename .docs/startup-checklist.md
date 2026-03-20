# Startup Checklist

Status: Required pre-coding checklist before starting the crypto scanner implementation.

## Purpose

Prevent false starts, hidden stock/crypto coupling, and premature AI work before the deterministic scanner lane is stable.

## Phase 0 Outcome

- Phase 0 locked the first implementation bead as a wide, end-to-end scanner foundation.
- Phase 1 is web-first and includes discovery, persistence, API list/detail/refresh/status, and the scanner page with filters and detail drawer.
- `CryptoLaunch` and `CryptoLaunchSnapshot` are part of the Phase 1 schema boundary.
- Settings endpoints, alerting, and selective AI remain deferred until after the core scanner feed is stable.

## Preconditions

- Read `repo-verification-and-comparison.md`
- Read `crypto-integration-architecture.md`
- Read `project-start-plan.md`
- Read `.opencode/memory/project/prd-crypto-new-launch-scanner.md`

## Environment Preflight

### Local Runtime Assumptions

- Shell runtime verified in this repo context:
  - `python3` available
  - `python` may be unavailable locally
  - Node + npm available for web work
- Important local evidence:
  - `AGENTS.md:5`
  - `AGENTS.md:21`
  - `AGENTS.md:25`

### Commands To Re-run Before Coding

```bash
python3 scripts/check_ai_assets.py
cd apps/dsa-web && npm ci && npm run lint && npm run build && npm run test
```

Optional if Python environment is provisioned fully:

```bash
python3 -m pytest -m "not network"
```

## Product Direction Lock

Confirm these decisions before writing code:

- [LOCKED] The local repo remains the product backbone
- [LOCKED] The crypto feature is an additive module, not a stock replacement
- [LOCKED] GeckoTerminal is the discovery backbone
- [LOCKED] DexScreener is an enrichment source, not the only discovery source
- [LOCKED] The 60-second scanner loop remains deterministic
- [LOCKED] `TradingAgents` patterns are reserved for the selective intelligence lane only

If any of the above changes, update:

- `repo-verification-and-comparison.md`
- `crypto-integration-architecture.md`
- `project-start-plan.md`
- the PRD in `.opencode/memory/project/prd-crypto-new-launch-scanner.md`

## Architecture Guardrails

These are hard boundaries for Phase 1-3 work.

### Do Reuse

- `src/scheduler.py:56` for runtime scheduling patterns
- `src/storage.py:64` and `src/storage.py:623` for persistence patterns
- `api/v1/router.py:17` for route registration
- `src/services/system_config_service.py:55` for config persistence
- `src/notification.py:85` for later alert routing
- `apps/dsa-web/src/stores/stockPoolStore.ts:25` as the frontend store pattern reference

### Do Not Reuse Directly

- `src/core/trading_calendar.py:33`
- `data_provider/base.py:65` stock normalization helpers
- `src/analyzer.py:34` and `src/analyzer.py:194`
- stock-only request names and report assumptions

## Build Slice Lock

The first implementation slice should stop at a usable deterministic scanner foundation.
Phase 0 locks this as a web-first, end-to-end slice rather than a backend-only milestone.

### Phase 1 Scope

- discovery fetcher
- persistence model
- repository
- service orchestration
- API list/detail/refresh/status
- scanner page + filters + detail drawer

### Explicitly Deferred

- multi-agent AI reasoning
- complex security-provider fanout
- heavy alerting
- saved settings endpoints
- selective AI analyze endpoint
- desktop-specific polish
- replay/backfill automation beyond basic placeholders

## Schema Decisions To Lock Early

Before implementing storage, confirm these choices from `database-schema.md`:

- [LOCKED] canonical launch key = `chain_id + pair_address`
- [LOCKED] first-class launch entity separated from snapshot entity
- [LOCKED] `CryptoLaunchSecurityScan` stored separately from the main row and deferred beyond Phase 1
- [LOCKED] AI summaries are stored separately from live scan state and deferred beyond Phase 1
- [LOCKED] snapshots are append-only, launch rows are upserted

## API Decisions To Lock Early

Before implementing endpoints, confirm these choices from `api-contracts.md`:

- [LOCKED] dedicated `/api/v1/crypto/*` namespace
- [LOCKED] cursor-based pagination for the launch feed
- [LOCKED] explicit freshness metadata on every feed response
- [LOCKED] partial-data flags instead of silent omission
- [DEFERRED TO PHASE 2+] separate settings endpoints for scanner configuration

## Operational Decisions To Lock Early

Before implementing the 60-second loop, confirm these choices from `security-and-rate-limits.md`:

- [LOCKED] one GeckoTerminal discovery pass per chain per cycle
- [LOCKED] batched DexScreener enrichment
- [LOCKED] cache TTLs for launch, enrichment, and security data
- [LOCKED] retry/backoff policy for `429`, `502`, `503`, `504`
- [LOCKED] non-blocking enrichment and non-blocking security scanning

## Test Readiness

Before merging Phase 1 work, confirm these choices from `testing-strategy.md`:

- [LOCKED] fixtures are committed for external provider payloads
- [LOCKED] backend tests do not require live network by default
- [LOCKED] frontend tests mock crypto endpoints and cover filter logic
- [LOCKED] deterministic time is injected for staleness and cursor tests

## Docs To Keep In Sync During Implementation

- `README.md`
- `docs/full-guide.md`
- `docs/DEPLOY.md`
- `AGENTS.md`
- `.github/instructions/backend.instructions.md`

Minimum crypto-related updates should happen when the first scanner slice lands, not after the whole project is done.

## Go / No-Go Check

Proceed only if all are true:

- [x] Backbone vs boundary decision is still valid
- [x] Schema design is reviewed
- [x] API contract is reviewed
- [x] Source/rate-limit strategy is reviewed
- [x] Testing strategy is reviewed
- [x] No one is trying to push AI into the core scanner loop yet

If any box is unchecked, stop and update the relevant doc first.
