# Beads PRD Template

**Bead:** daily_stock_analysis-0mr  
**Created:** 2026-03-20  
**Status:** Draft

## Bead Metadata

```yaml
depends_on: []
parallel: true
conflicts_with: []
blocks: []
estimated_hours: 6
```

---

## Problem Statement

### What problem are we solving?

The current product is built around stock analysis workflows, but the highest-priority near-term need is a crypto-first scanner for newly launched tokens and pools. Right now the repo has reusable APIs, scheduling, persistence, and web-shell infrastructure, yet it does not expose a dedicated crypto discovery lane. Without that lane, users cannot monitor launches quickly enough to filter early opportunities across supported chains.

Phase 1 needs to deliver the first end-to-end scanner slice: discovery, persistence, API list/detail/refresh/status, and a web-first scanner page. The scanner must start from the default seed chains `bsc`, `solana`, and `base`, while allowing additional provider-supported chains to be enabled without redesigning the schema or hardcoding a closed enum.

### Why now?

Recent planning work locked the first implementation bead as the scanner foundation rather than a later narrow slice. The cost of delaying this bead is that the app still cannot serve the primary crypto use case, and later work like settings, alerts, and selective AI review has no stable base to build on.

### Who is affected?

- **Primary users:** Individual investors and active traders who want to monitor new token launches quickly and triage them inside the app.
- **Secondary users:** Research-oriented traders and small teams who need a repeatable early-discovery board before deeper manual or AI-assisted review.

---

## Scope

### In-Scope

- Add a parallel crypto scanner lane without removing or rewriting the stock lane.
- Discover new pools from GeckoTerminal on a deterministic 60-second cadence.
- Treat `bsc`, `solana`, and `base` as default seed chains only, while allowing additional provider-supported chain ids.
- Persist `CryptoLaunch` and `CryptoLaunchSnapshot` records for list/detail rendering and short-term history.
- Expose dedicated backend endpoints for launch list, launch detail, refresh trigger, and scanner status.
- Add a web-first `/crypto-scanner` route with filters, sorting, auto-refresh, visibility refresh, detail inspection, and external links.
- Keep partial-data launches visible when enrichment is missing or delayed.

### Out-of-Scope

- Replacing or deleting any existing stock-analysis workflow.
- Persisted settings endpoints or UI for saved scanner defaults.
- Alerts, watchlists, or notification delivery for launches.
- AI review or per-minute LLM enrichment in the scanner loop.
- Desktop-specific UX beyond existing web reuse in Electron.
- Direct on-chain subscriptions or custom indexing infrastructure.

---

## Proposed Solution

### Overview

Add a dedicated crypto discovery module that runs alongside the stock system. A new fetcher/service/repository stack polls GeckoTerminal `new_pools` every 60 seconds for the enabled chain set, normalizes and deduplicates launch records, persists current launch state plus snapshots, and performs non-blocking DexScreener enrichment for links and supplemental metadata. FastAPI exposes a crypto API surface for list/detail/refresh/status, and the React app adds a `/crypto-scanner` page backed by a dedicated Zustand store and existing dashboard lifecycle patterns.

### User Flow (if user-facing)

1. User opens `/crypto-scanner` in the existing web app.
2. The page loads recent launches from the enabled chain set, beginning with default seed chains `bsc`, `solana`, and `base`.
3. The scanner refreshes every 60 seconds and refreshes again when the tab becomes visible.
4. User filters or sorts launches by chain, age, liquidity, volume, and activity.
5. User opens a launch detail view and follows outbound links such as DexScreener when deeper inspection is needed.

---

## Requirements

### Functional Requirements

#### Crypto Launch Discovery

The backend must fetch newly created pools for all enabled provider-supported chains and store new or updated launch records without duplicating canonical pairs.

**Scenarios:**

- **WHEN** the scanner runs **THEN** it fetches discovery results for each enabled supported chain and stores any new launches.
- **WHEN** the same pair appears in later cycles **THEN** the system updates the existing launch instead of creating duplicates.
- **WHEN** a user enables an additional supported chain **THEN** the next eligible scan includes that chain without schema changes.

#### Launch Persistence and Snapshots

The system must persist enough launch and snapshot data to power list, detail, sort, and short-term history surfaces.

**Scenarios:**

- **WHEN** a launch is first discovered **THEN** the system stores a canonical `CryptoLaunch` record keyed by chain and pair identity.
- **WHEN** a later scan observes changed metrics **THEN** the system stores a `CryptoLaunchSnapshot` without losing the latest launch state.

#### Crypto API Surface

The backend must expose crypto-specific endpoints rather than reusing stock-only contracts.

**Scenarios:**

- **WHEN** the client requests recent launches **THEN** it receives a paginated, filterable feed with explicit partial-data semantics.
- **WHEN** the client requests a launch detail **THEN** it receives the latest persisted launch state, recent snapshot data, and external links when available.
- **WHEN** the client triggers a refresh **THEN** the API returns an accepted or completed status using a dedicated crypto flow.

#### Web Scanner Experience

The web app must provide a dedicated crypto scanner page that supports active monitoring and fast triage.

**Scenarios:**

- **WHEN** a user visits `/crypto-scanner` **THEN** the page renders recent launches with filter and sort controls.
- **WHEN** filters or sort mode change **THEN** the list updates without a full-page navigation.
- **WHEN** the page remains open **THEN** it refreshes every 60 seconds and also refreshes on visibility regain.

#### Partial-Data Tolerance

Enrichment failures or missing metadata must not hide valid discoveries.

**Scenarios:**

- **WHEN** DexScreener enrichment is unavailable **THEN** the launch still appears with the discovery data that exists.
- **WHEN** one chain fetch fails **THEN** other enabled chains still complete the scan cycle.

#### Backward Compatibility

The new crypto lane must not break existing stock workflows.

**Scenarios:**

- **WHEN** the crypto module is enabled **THEN** current stock routes, APIs, and report flows continue to work unchanged.
- **WHEN** the crypto module is disabled **THEN** the application behaves as it does today for stock-only usage.

### Non-Functional Requirements

- **Performance:** The scanner loop targets a 60-second cadence and the first feed page must remain suitable for interactive monitoring under normal upstream conditions.
- **Security:** No secrets or provider keys are hardcoded; future credentials must remain config-driven.
- **Accessibility:** The scanner page must remain keyboard navigable and readable inside the existing app shell.
- **Compatibility:** The feature must work in the current FastAPI backend and React/Vite web app, with Electron reusing the web surface.
- **Reliability:** Partial upstream failure is acceptable; total feed collapse for a single failing chain is not.

---

## Success Criteria

- [ ] The backend discovers launches for all enabled chains on a 60-second loop, starting from default seed chains `bsc`, `solana`, and `base`.
  - Verify: `python3 -m pytest -m "not network"`
- [ ] The backend persists `CryptoLaunch` and `CryptoLaunchSnapshot` records with canonical deduplication and list/detail query support.
  - Verify: `python3 -m pytest -m "not network"`
- [ ] The API exposes `/api/v1/crypto/launches`, `/api/v1/crypto/launches/{launch_id}`, `/api/v1/crypto/refresh`, and `/api/v1/crypto/status` with explicit partial-data behavior.
  - Verify: `python3 -m pytest -m "not network"`
- [ ] The web app exposes `/crypto-scanner` with filter, sort, detail, and auto-refresh behavior.
  - Verify: `cd apps/dsa-web && npm ci && npm run lint && npm run build && npm run test`
- [ ] Existing stock routes and app-shell behavior remain intact after the crypto scanner is added.
  - Verify: `cd apps/dsa-web && npm ci && npm run lint && npm run build && npm run test`

---

## Technical Context

### Existing Patterns

- Pattern 1: `api/v1/endpoints/analysis.py` - Existing async request, status, and acceptance-response patterns are the closest backend model for crypto refresh and status endpoints.
- Pattern 2: `src/repositories/stock_repo.py` - Existing repository structure is the nearest persistence pattern to mirror for crypto launch queries and upserts.
- Pattern 3: `apps/dsa-web/src/hooks/useDashboardLifecycle.ts` - Existing polling plus visibility-refresh lifecycle is the right base pattern for a 60-second scanner page.
- Pattern 4: `apps/dsa-web/src/stores/stockPoolStore.ts` - Existing Zustand store request sequencing and UI-state coordination are reusable for the crypto launch store.

### Key Files

- `src/config.py` - Adds crypto config keys, enabled-chain normalization, and provider settings.
- `src/scheduler.py` - Extends daily-only scheduling to support a 60-second interval scanner.
- `src/storage.py` - Adds `CryptoLaunch` and `CryptoLaunchSnapshot` ORM models.
- `main.py` - Wires scanner startup without depending on stock trading-day logic.
- `api/v1/router.py` - Registers the new crypto API router.
- `apps/dsa-web/src/App.tsx` - Adds the `/crypto-scanner` route.
- `apps/dsa-web/src/components/layout/SidebarNav.tsx` - Adds scanner navigation entry in the existing shell.
- `data_provider/base.py` - Boundary reference showing stock-specific normalization that must not be reused for crypto identifiers.

### Affected Files

Files this bead will modify (for conflict detection):

```yaml
files:
  - data_provider/crypto_launch_fetcher.py # GeckoTerminal discovery and DexScreener enrichment hooks
  - src/config.py # Crypto config namespace and enabled-chain normalization
  - src/scheduler.py # Interval scheduling support for the scanner loop
  - src/storage.py # CryptoLaunch and CryptoLaunchSnapshot models
  - src/repositories/crypto_launch_repo.py # Launch upsert, list, detail, and snapshot persistence
  - src/services/crypto_launch_service.py # Scanner orchestration and status tracking
  - main.py # Runtime registration for the scanner
  - api/v1/endpoints/crypto.py # Launch list/detail/refresh/status endpoints
  - api/v1/schemas/crypto.py # Crypto request and response contracts
  - api/v1/router.py # Router registration for /api/v1/crypto
  - apps/dsa-web/src/api/crypto.ts # Frontend client for crypto endpoints
  - apps/dsa-web/src/types/crypto.ts # Typed DTOs for launch feed and detail data
  - apps/dsa-web/src/stores/cryptoLaunchStore.ts # Scanner state, filtering, and refresh actions
  - apps/dsa-web/src/pages/CryptoScannerPage.tsx # Scanner page layout and data binding
  - apps/dsa-web/src/components/crypto/* # Filter, table/card, and detail components
  - apps/dsa-web/src/components/layout/SidebarNav.tsx # Navigation entry for the scanner page
  - apps/dsa-web/src/App.tsx # Route registration for /crypto-scanner
```

---

## Risks & Mitigations

| Risk                                                                       | Likelihood | Impact | Mitigation                                                                                                      |
| -------------------------------------------------------------------------- | ---------- | ------ | --------------------------------------------------------------------------------------------------------------- |
| GeckoTerminal pagination or cadence may miss launches on busy chains       | Medium     | High   | Use high-water-mark and pagination-aware fetch logic instead of assuming a single page is complete              |
| Stock-specific helpers leak into crypto discovery or identifiers           | Medium     | High   | Keep a parallel crypto fetcher/service/schema lane and avoid stock code normalization or trading-calendar logic |
| Upstream rate limits or data gaps make enrichment flaky                    | Medium     | Medium | Keep enrichment non-blocking, cache conservatively, and render partial rows explicitly                          |
| Hardcoding the default three chains as a closed set blocks later expansion | High       | Medium | Normalize open string chain ids and validate against provider-supported mappings instead of enums               |

---

## Tasks

### Build crypto discovery, config, scheduling, and persistence foundation [backend]

The backend has the config, interval scheduling, fetcher, and ORM model foundation required to scan enabled chains every 60 seconds and store canonical launch state.

**Metadata:**

```yaml
depends_on: []
parallel: true
conflicts_with: []
files:
  - data_provider/crypto_launch_fetcher.py
  - src/config.py
  - src/scheduler.py
  - src/storage.py
```

**Verification:**

- `python3 -m pytest -m "not network"`

### Add crypto repository, service orchestration, and runtime wiring [backend]

The backend can run scan cycles, tolerate per-chain failure, persist launches and snapshots, and expose scanner runtime state without affecting stock scheduling.

**Metadata:**

```yaml
depends_on: ["Build crypto discovery, config, scheduling, and persistence foundation"]
parallel: false
conflicts_with: []
files:
  - src/repositories/crypto_launch_repo.py
  - src/services/crypto_launch_service.py
  - main.py
```

**Verification:**

- `python3 -m pytest -m "not network"`

### Add crypto API contracts and endpoints [api]

FastAPI exposes dedicated list, detail, refresh, and status endpoints for the crypto scanner using explicit partial-data semantics.

**Metadata:**

```yaml
depends_on: ["Add crypto repository, service orchestration, and runtime wiring"]
parallel: false
conflicts_with: []
files:
  - api/v1/schemas/crypto.py
  - api/v1/endpoints/crypto.py
  - api/v1/router.py
```

**Verification:**

- `python3 -m pytest -m "not network"`

### Build the web scanner route, store, and detail experience [frontend]

The web app exposes `/crypto-scanner` with launch feed rendering, filtering, sorting, auto-refresh, detail inspection, and shell navigation.

**Metadata:**

```yaml
depends_on: ["Add crypto API contracts and endpoints"]
parallel: false
conflicts_with: []
files:
  - apps/dsa-web/src/api/crypto.ts
  - apps/dsa-web/src/types/crypto.ts
  - apps/dsa-web/src/stores/cryptoLaunchStore.ts
  - apps/dsa-web/src/pages/CryptoScannerPage.tsx
  - apps/dsa-web/src/components/crypto/*
  - apps/dsa-web/src/components/layout/SidebarNav.tsx
  - apps/dsa-web/src/App.tsx
  - apps/dsa-web/src/hooks/useDashboardLifecycle.ts
```

**Verification:**

- `cd apps/dsa-web && npm ci && npm run lint && npm run build && npm run test`

### Validate non-regression, partial-data behavior, and doc alignment [verification]

The bead ships with verification coverage for partial-data handling and confirmation that the stock lane and app shell still behave correctly.

**Metadata:**

```yaml
depends_on:
  - "Build the web scanner route, store, and detail experience"
parallel: false
conflicts_with: []
files:
  - tests/**
  - apps/dsa-web/src/**/__tests__/*
  - README.md
  - docs/full-guide.md
```

**Verification:**

- `python3 -m pytest -m "not network"`
- `cd apps/dsa-web && npm ci && npm run lint && npm run build && npm run test`

---

## Notes

- Phase 1 is intentionally the wide first slice: discovery, persistence, API list/detail/refresh/status, and the scanner page.
- `bsc`, `solana`, and `base` are default seed chains, not a closed enum or permanent cap.
- GeckoTerminal remains the discovery backbone and DexScreener remains enrichment-only for this bead.
- AI review, saved settings, alerts, and desktop-specific UX remain deferred beyond this bead.
