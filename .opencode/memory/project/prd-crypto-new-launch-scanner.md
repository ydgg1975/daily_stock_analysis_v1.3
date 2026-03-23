# Beads PRD Template

**Bead:** planning artifact aligned by `daily_stock_analysis-zpm`  
**Created:** 2026-03-20  
**Status:** Phase 0 aligned

## Phase 0 Alignment

- The first implementation bead is locked as a wide first slice: discovery, persistence, API list/detail/refresh/status, and the scanner page.
- `CryptoLaunch` and `CryptoLaunchSnapshot` are both part of the Phase 1 schema boundary.
- Settings endpoints, notifications, and selective AI review are deferred until after the deterministic scanner foundation is stable.
- The first release is web-first, with Electron treated as passive reuse of the web surface.

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

The current product is optimized for stock analysis, but the user now needs a crypto-first discovery surface for newly launched tokens and pools across BNB Chain, Solana, and Base. The highest-priority job is not deep report generation for a small watchlist; it is fast discovery, filtering, and triage of newly created pairs so the user can monitor opportunities early.

Today the repo has reusable infrastructure for APIs, scheduling, notifications, persistence, and web UI, but it does not expose a crypto-native scanner workflow. Stock-specific assumptions in trading calendars, code normalization, and analysis schemas make a direct stock-to-crypto replacement risky. Users need a dedicated scanner board that refreshes every 60 seconds, shows new pairs quickly, and lets them filter for quality and risk without leaving the app.

### Why now?

The product direction is shifting from equity-centric analysis toward coin/crypto workflows. The cost of inaction is that the current app cannot support the user's highest-priority crypto use case: discovering launches quickly enough to act on them. Research also confirmed that a practical free-stack MVP is available now: GeckoTerminal can serve as the discovery backbone for `new_pools`, while DexScreener can enrich pairs with links, profiles, and metadata.

### Who is affected?

- **Primary users:** Individual investors and active traders who want to monitor new token launches in real time and filter out low-quality pools quickly.
- **Secondary users:** Research-oriented traders and small teams who want a dashboard for early-stage crypto discovery before doing deeper manual or AI-assisted review.

---

## Scope

### In-Scope

- Add a crypto-specific New Launch Scanner module inside the existing application, without removing current stock features.
- Discover newly created pools on BNB Chain, Solana, and Base.
- Refresh discovery data every 60 seconds.
- Use GeckoTerminal `new_pools` as the primary discovery source.
- Use DexScreener as a secondary enrichment source for chart links, socials, websites, and additional pair metadata.
- Persist discovered launch events and recent snapshots so the UI can show current state and short-term history.
- Provide a dedicated web page for scanner monitoring with table/card views, quick filters, sort controls, and external links.
- Support configurable filters from the UI for chain, age, liquidity, volume, and activity.
- Provide deterministic scanner scoring and risk hints based on launch metrics in V1.
- Expose backend API endpoints for listing recent launches, querying details, and forcing refresh cycles.
- Preserve compatibility with the existing shell, auth model, config system, and notification infrastructure.

### Out-of-Scope

- Replacing or deleting the stock-analysis domain.
- Full crypto portfolio tracking, wallet sync, or order execution.
- Running LLM analysis on every newly discovered token every minute.
- Direct on-chain RPC subscriptions or custom indexer infrastructure in V1.
- Desktop-specific UX optimizations beyond existing web-in-Electron compatibility.
- Advanced social scraping from Telegram, Discord, or X in V1.
- Comprehensive honeypot / contract-security scoring if external provider integration is not yet validated.

---

## Proposed Solution

### Overview

Introduce a parallel crypto module that coexists with the current stock system. A scheduled backend scanner polls GeckoTerminal every 60 seconds for newly created pools on the target chains, deduplicates and stores them, applies deterministic filter logic, then enriches interesting results with DexScreener metadata. The web app adds a dedicated scanner board where users can filter, sort, and inspect launches in real time. The first version emphasizes speed, clarity, and triage. AI analysis remains selective and is reserved for detail views or shortlisted launches in a later phase.

### User Flow (if user-facing)

1. User opens the new Crypto Scanner page in the existing web app.
2. The page loads the newest pools from BNB Chain, Solana, and Base and auto-refreshes every 60 seconds.
3. User applies filters such as age, liquidity, chain, and activity to narrow the feed.
4. User clicks a row/card to view details, links, and metrics, then opens the token in DexScreener when needed.
5. User optionally saves filter presets or watchlist items for repeated monitoring in later iterations.

---

## Requirements

### Functional Requirements

#### Crypto Launch Discovery

The system must fetch newly created pools on the configured target chains using a free, low-friction data source compatible with a 60-second refresh loop.

**Scenarios:**

- **WHEN** the scheduled scanner runs **THEN** it fetches newly created pools for BNB Chain, Solana, and Base and stores any new launch events.
- **WHEN** the upstream source returns the same pair on multiple cycles **THEN** the system deduplicates it and updates the existing record instead of creating duplicates.

#### Crypto Launch Enrichment

The system must enrich discovered launches with secondary metadata where available.

**Scenarios:**

- **WHEN** a newly discovered pair has a matching DexScreener record **THEN** the system stores pair address, chart link, socials, website, and available metadata for UI use.
- **WHEN** enrichment data is unavailable or delayed **THEN** the launch still appears in the scanner with partial data instead of being dropped.

#### Scanner Filtering and Sorting

The web UI must allow users to narrow the stream quickly using scan-friendly filters.

**Scenarios:**

- **WHEN** a user changes chain, liquidity, age, or volume filters **THEN** the list updates without requiring a full page change.
- **WHEN** a user changes sort mode to newest, volume, or activity **THEN** the scanner reorders items consistently using server or client-supported sorting.

#### Real-Time Refresh

The scanner must support near-real-time monitoring suitable for new launch discovery.

**Scenarios:**

- **WHEN** the scanner page is open **THEN** it refreshes data every 60 seconds.
- **WHEN** the browser tab becomes visible again after being hidden **THEN** the scanner refreshes promptly.

#### Launch Detail View

The scanner must provide a focused detail surface for each launch.

**Scenarios:**

- **WHEN** a user opens a launch detail **THEN** they can see token name/symbol, chain, DEX, age, liquidity, volume, buy/sell counts, and external links.
- **WHEN** DexScreener data is present **THEN** the detail view includes a primary CTA to open the pair on DexScreener.

#### Backward Compatibility

The new crypto module must not break existing stock workflows.

**Scenarios:**

- **WHEN** the crypto module is added **THEN** the existing stock analysis routes, APIs, and report flows continue to work unchanged.
- **WHEN** crypto scanning is disabled by config **THEN** the stock product still behaves as it does today.

#### Selective AI Enrichment (Post-MVP Hook)

The architecture must allow later AI analysis without forcing it into V1 as a per-minute requirement.

**Scenarios:**

- **WHEN** a launch is shortlisted later for AI review **THEN** the system can generate a crypto-specific decision summary without depending on stock-only analyzer fields.
- **WHEN** V1 ships without AI enrichment **THEN** the scanner still provides usable deterministic triage and decision support.

### Non-Functional Requirements

- **Performance:** The scanner should refresh every 60 seconds and return the first page of recent launches quickly enough for interactive monitoring under normal API conditions.
- **Security:** No secrets are hardcoded. If an external security provider is added later, its keys must be handled through config and `.env.example`.
- **Accessibility:** The web scanner should remain keyboard navigable and readable in the existing app shell.
- **Compatibility:** The feature must work inside the current React/Vite web app and remain compatible with the Electron wrapper via the existing web surface.
- **Reliability:** Temporary upstream failures must degrade gracefully; partial results are preferred over total failure.

---

## Success Criteria

- [ ] The backend discovers new pools for BNB Chain, Solana, and Base on a 60-second loop using the configured source strategy.
  - Verify: `python3 -m pytest -m "not network"` for any deterministic backend tests added, plus targeted manual verification of recent launch records.
- [ ] The web UI exposes a scanner page showing recent launches with chain, age, liquidity, activity, and external links.
  - Verify: `cd apps/dsa-web && npm ci && npm run lint && npm run build && npm run test`
- [ ] Users can filter the scanner by chain, age, liquidity, and activity from the UI.
  - Verify: manual UI check on the scanner page plus targeted component/store tests.
- [ ] The feature does not break the current stock module or app shell.
  - Verify: existing backend/web validation paths continue to pass for touched surfaces.
- [ ] Discovery and enrichment tolerate missing data without hiding launches completely.
  - Verify: test or manual scenario where enrichment fails but launch records still render.

---

## Technical Context

### Existing Patterns

- Pattern 1: `api/v1/endpoints/analysis.py` - Existing async task and SSE status pattern is relevant for crypto refresh/status flows.
- Pattern 2: `apps/dsa-web/src/hooks/useDashboardLifecycle.ts` - Existing polling and visibility-refresh lifecycle is relevant for a 60-second scanner board.
- Pattern 3: `src/services/system_config_service.py` - Existing settings/config persistence pattern is relevant for scanner filters and feature toggles.
- Pattern 4: `src/notification.py` and `src/notification_sender/` - Existing multi-channel notification infrastructure is reusable if crypto alerts are added later.

### Key Files

- `data_provider/base.py` - Relevant because current normalization and market tagging are stock-specific and must not be reused blindly.
- `src/core/trading_calendar.py` - Relevant because current calendar logic is incompatible with crypto's 24/7 market structure.
- `main.py` - Relevant for scheduler integration and avoiding stock-specific trading-day filtering in crypto flows.
- `api/v1/endpoints/analysis.py` - Relevant for async patterns and status streaming.
- `apps/dsa-web/src/App.tsx` - Relevant for adding the scanner route.
- `apps/dsa-web/src/hooks/useDashboardLifecycle.ts` - Relevant for refresh cadence and page lifecycle behavior.
- `src/analyzer.py` - Relevant as a boundary marker showing why stock-specific AI logic should not be forced into V1 crypto discovery.

### Affected Files

Files this bead will modify (for conflict detection):

```yaml
files:
  - data_provider/crypto_launch_fetcher.py # New discovery source integration for GeckoTerminal and enrichment flow
  - src/services/crypto_launch_service.py # Scanner orchestration and business logic
  - src/storage.py # New crypto launch persistence models or schema extensions
  - src/repositories/crypto_launch_repo.py # Query and persistence abstraction for launch records
  - src/config.py # Scanner-specific config keys and feature toggles
  - main.py # Scheduler wiring and optional CLI/serve hooks for scanner refresh
  - api/v1/endpoints/crypto.py # New crypto scanner endpoints
  - api/v1/schemas/crypto.py # Request/response schemas for crypto launch APIs
  - api/v1/router.py # Route registration
  - apps/dsa-web/src/pages/CryptoScannerPage.tsx # New scanner UI page
  - apps/dsa-web/src/stores/cryptoLaunchStore.ts # Client state for scanner data and filters
  - apps/dsa-web/src/App.tsx # Route registration for scanner page
```

---

## Risks & Mitigations

| Risk                                                                                        | Likelihood | Impact | Mitigation                                                                                   |
| ------------------------------------------------------------------------------------------- | ---------- | ------ | -------------------------------------------------------------------------------------------- |
| GeckoTerminal pagination may miss launches on high-volume chains if only one page is polled | High       | High   | Use `pool_created_at` high-water mark logic and fetch additional pages when needed           |
| DexScreener alone cannot discover all new pairs                                             | High       | High   | Use DexScreener for enrichment, not primary discovery                                        |
| Stock-specific abstractions may accidentally leak into crypto logic                         | Medium     | High   | Create a parallel crypto pipeline and schema set instead of forcing reuse of stock analyzers |
| Upstream API rate limits are not fully documented                                           | Medium     | Medium | Add lightweight caching, backoff, and explicit source strategy flags                         |
| LLM analysis can become too expensive or slow if used on every new token                    | High       | Medium | Keep V1 deterministic; restrict AI to detail view or shortlist flows later                   |
| Missing social/security metadata may create incomplete rows                                 | Medium     | Medium | Render partial records and make enrichment non-blocking                                      |

---

## Phase 0 Decisions Resolved

| Decision                                                                                                                        | Owner        | Resolved On | Outcome                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------- | ------------ | ----------- | ------------------------------------------------------------------------- |
| Should V1 include only deterministic scoring, or also a first-pass AI summary in the detail drawer?                             | Product/User | 2026-03-20  | Deterministic scanner foundation only; AI summary deferred beyond Phase 1 |
| Should notifications be included in the first scanner release or deferred until the UI is stable?                               | Product/User | 2026-03-20  | Deferred until after the core scanner feed is stable                      |
| Should launch history be stored in a dedicated crypto table from day one, or can a simpler schema ship first and migrate later? | Engineering  | 2026-03-20  | Ship `CryptoLaunch` and `CryptoLaunchSnapshot` together from day one      |
| Should the first release be web-only, with Electron treated as passive reuse of the web build?                                  | Product/User | 2026-03-20  | Web-first; Electron remains passive reuse only                            |

---

## Tasks

### Build crypto launch discovery and persistence [backend]

The backend can discover new pools every 60 seconds, deduplicate them, and store recent launch records with enough fields for filtering and rendering.

**Metadata:**

```yaml
depends_on: []
parallel: true
conflicts_with: []
files:
  - data_provider/crypto_launch_fetcher.py
  - src/services/crypto_launch_service.py
  - src/storage.py
  - src/repositories/crypto_launch_repo.py
  - src/config.py
  - main.py
```

**Verification:**

- Add deterministic tests for normalization, deduplication, and fallback behavior where practical
- Run `python3 -m pytest -m "not network"`

### Add crypto scanner API surface [backend]

The app exposes dedicated endpoints for recent launches, launch detail, and scanner refresh/status without reusing stock-only request schemas.

**Metadata:**

```yaml
depends_on: ["Build crypto launch discovery and persistence"]
parallel: false
conflicts_with: []
files:
  - api/v1/endpoints/crypto.py
  - api/v1/schemas/crypto.py
  - api/v1/router.py
```

**Verification:**

- Add endpoint tests or targeted schema/service tests as appropriate
- Run `python3 -m pytest -m "not network"`

### Build scanner page and client store [frontend]

The web app shows a dedicated Crypto Scanner page with list rendering, filter state, sorting, and 60-second refresh behavior.

**Metadata:**

```yaml
depends_on: ["Add crypto scanner API surface"]
parallel: false
conflicts_with: []
files:
  - apps/dsa-web/src/pages/CryptoScannerPage.tsx
  - apps/dsa-web/src/stores/cryptoLaunchStore.ts
  - apps/dsa-web/src/App.tsx
  - apps/dsa-web/src/hooks/useDashboardLifecycle.ts
```

**Verification:**

- Add component/store tests for filter and refresh behavior
- Run `cd apps/dsa-web && npm ci && npm run lint && npm run build && npm run test`

### Add launch detail enrichment and outbound links [frontend]

Users can inspect details for a launch and open the token/pair in DexScreener from the app.

**Metadata:**

```yaml
depends_on: ["Build scanner page and client store"]
parallel: false
conflicts_with: []
files:
  - apps/dsa-web/src/pages/CryptoScannerPage.tsx
  - apps/dsa-web/src/components/crypto/*
```

**Verification:**

- Manual check that detail panels render with partial and full data states
- Run `cd apps/dsa-web && npm run lint && npm run test`

Deferred follow-on tasks begin here. The first implementation bead stops after the scanner foundation tasks above; the tasks below remain intentionally deferred.

### Add scanner settings and saved defaults [product]

Deferred beyond the first implementation bead, the app persists scanner-relevant settings such as enabled chains, refresh cadence, and default filter thresholds.

**Metadata:**

```yaml
depends_on: ["Add crypto scanner API surface", "Build scanner page and client store"]
phase: 2
parallel: true
conflicts_with: []
files:
  - src/config.py
  - src/services/system_config_service.py
  - api/v1/endpoints/crypto.py
  - apps/dsa-web/src/pages/SettingsPage.tsx
  - apps/dsa-web/src/components/settings/*
```

**Verification:**

- Manual check that settings persist and reload correctly
- Run closest backend tests and `cd apps/dsa-web && npm run lint && npm run test`

### Reserve AI enrichment for shortlist/detail flows [ai]

Deferred beyond the first implementation bead, the architecture supports future crypto-specific AI summaries without making them mandatory for every scanner refresh cycle.

**Metadata:**

```yaml
depends_on: ["Build crypto launch discovery and persistence", "Add crypto scanner API surface"]
phase: 3
parallel: true
conflicts_with: []
files:
  - src/analyzer.py
  - src/services/crypto_launch_service.py
  - api/v1/endpoints/crypto.py
```

**Verification:**

- Confirm V1 works fully without AI enrichment enabled
- If implemented, add focused tests around prompt selection and response shaping

### Validate docs, filters, and non-regression [docs]

The new scanner ships with updated docs and validation notes while keeping the stock product stable.

**Metadata:**

```yaml
depends_on:
  - "Build crypto launch discovery and persistence"
  - "Add crypto scanner API surface"
  - "Build scanner page and client store"
parallel: false
conflicts_with: []
files:
  - README.md
  - docs/full-guide.md
  - AGENTS.md
```

**Verification:**

- Run `python3 scripts/check_ai_assets.py` if governance/docs change
- Run closest backend validation plus `cd apps/dsa-web && npm run lint && npm run build`

---

## Dependency Legend

| Field            | Purpose                                           | Example                                             |
| ---------------- | ------------------------------------------------- | --------------------------------------------------- |
| `depends_on`     | Must complete before this task starts             | `["Build crypto launch discovery and persistence"]` |
| `parallel`       | Can run concurrently with other parallel tasks    | `true` / `false`                                    |
| `conflicts_with` | Cannot run in parallel (same files)               | `["Add scanner settings and saved defaults"]`       |
| `files`          | Files this task modifies (for conflict detection) | `["api/v1/endpoints/crypto.py"]`                    |

---

## Notes

- Research-backed source strategy for V1: GeckoTerminal `new_pools` for discovery, DexScreener for enrichment.
- DexScreener should not be treated as the sole discovery backbone because it does not expose a reliable new-pairs feed.
- The correct architecture for this repo is additive, not destructive: a parallel crypto module alongside the current stock module.
- If the team later decides to go crypto-only, that should be a separate migration PRD rather than expanding the scope of this feature.
