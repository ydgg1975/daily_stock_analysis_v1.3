# Beads PRD Template

**Bead:** daily_stock_analysis-zpm  
**Created:** 2026-03-20  
**Status:** Draft

## Bead Metadata

```yaml
depends_on: []
parallel: true
conflicts_with: []
blocks: []
estimated_hours: 3
```

---

## Problem Statement

### What problem are we solving?

The crypto scanner docs already describe a Phase 1 implementation path, but they also show that coding should not start until a small set of foundational decisions is locked first. Without an explicit Phase 0 bead, the project risks false starts: stock-specific assumptions can leak into crypto work, schema/API decisions can drift across documents, rate-limit constraints can be overlooked, and AI scope can expand into the 60-second scanner loop before the deterministic lane is stable.

### Why now?

The repo already has a verified crypto planning package under `.docs/` plus the working PRD at `.opencode/memory/project/prd-crypto-new-launch-scanner.md`. The next step is not implementation yet; it is converting those docs into a single planning bead that locks Phase 1 entry criteria so later implementation work starts from settled assumptions instead of reopening core design questions.

### Who is affected?

- **Primary users:** Maintainers implementing the crypto scanner lane and any future agent/session that will execute Phase 1 work.
- **Secondary users:** Traders and investors who depend on the first crypto scanner release staying stable, deterministic, and isolated from the existing stock workflows.

---

## Scope

### In-Scope

- Lock the product-direction decisions that Phase 1 depends on.
- Confirm the Phase 1 schema boundary using the existing crypto schema proposal.
- Confirm the Phase 1 API contract and sequencing boundary using the existing API contract docs.
- Confirm source roles, rate-limit budgets, retry/cache policy, and no-network-first testing rules.
- Produce an explicit go/no-go package for starting implementation in the next bead.
- Keep the docs and planning artifacts aligned on what is blocked now versus what is deferred.

### Out-of-Scope

- Writing any crypto scanner implementation code.
- Adding database tables, API routes, frontend pages, or config keys in production code.
- Finalizing later-phase alerting, security-provider fanout, or AI review implementation.
- Replacing or restructuring the stock-analysis product backbone.
- Changing runtime behavior in `main.py`, `src/storage.py`, `api/v1/router.py`, or the web app during this bead.

---

## Proposed Solution

### Overview

Create a documentation-first Phase 0 bead that turns the current crypto planning package into an explicit pre-implementation checkpoint. The work should reconcile the startup checklist, schema doc, API contract doc, rate-limit doc, testing strategy, and main crypto PRD so that Phase 1 can begin with a locked scope: additive crypto lane, deterministic 60-second discovery loop, separate crypto schema/API boundaries, and explicit deferrals for security-provider depth and AI reasoning.

### User Flow (if user-facing)

1. A maintainer reviews the current crypto planning docs and resolves the decisions that are marked as Phase 1 prerequisites.
2. The project records which choices are locked now, which are deferred, and which remain open but non-blocking.
3. The next implementation bead starts from the approved Phase 1 boundary without re-debating schema, API, rate-limit, or test assumptions.

---

## Requirements

### Functional Requirements

#### Product Direction Lock

Phase 0 must restate and preserve the already-validated product direction for the crypto scanner lane.

**Scenarios:**

- **WHEN** Phase 0 completes **THEN** the docs clearly say that the current repo remains the product backbone and crypto is an additive lane, not a stock replacement.
- **WHEN** a future maintainer reads the Phase 0 outputs **THEN** they can see that AI remains outside the 60-second scanner loop for Phase 1.

#### Schema Boundary Lock

Phase 0 must confirm what crypto data model Phase 1 is allowed to rely on.

**Scenarios:**

- **WHEN** storage planning is reviewed **THEN** the canonical launch key remains `chain_id + pair_address` and launch rows stay separate from snapshot, security, and AI history rows.
- **WHEN** implementation scope needs to stay narrow **THEN** the docs explicitly allow an MVP schema centered on `CryptoLaunch` and `CryptoLaunchSnapshot`, with security and AI tables deferred.

#### API Contract Lock

Phase 0 must confirm the stable crypto API boundary before any endpoint code is written.

**Scenarios:**

- **WHEN** API planning is reviewed **THEN** the crypto surface uses a dedicated `/api/v1/crypto/*` namespace instead of reusing stock-only request naming.
- **WHEN** the live launch feed contract is reviewed **THEN** cursor pagination, freshness metadata, and partial-data semantics remain explicit rather than implicit.

#### Operational Source Strategy Lock

Phase 0 must confirm the provider and rate-limit strategy that the scanner will follow.

**Scenarios:**

- **WHEN** discovery behavior is reviewed **THEN** GeckoTerminal remains the discovery backbone and DexScreener remains an enrichment source.
- **WHEN** provider failures or throttling are considered **THEN** the docs require retries, backoff, caching, and non-blocking partial-data handling instead of hiding launches.

#### Test Readiness Lock

Phase 0 must confirm how Phase 1 will be verified without turning live network access into a default requirement.

**Scenarios:**

- **WHEN** backend validation is planned **THEN** the default deterministic command remains `python3 -m pytest -m "not network"`.
- **WHEN** frontend validation is planned **THEN** the strategy requires mocked crypto endpoints and filter/refresh coverage instead of relying on live provider behavior.

#### Go / No-Go Handoff

Phase 0 must end with a clear statement of whether Phase 1 can begin and what remains deferred.

**Scenarios:**

- **WHEN** all Phase 1 prerequisites are reviewed **THEN** the next bead can begin implementation without reopening the same design decisions.
- **WHEN** any prerequisite is still unresolved **THEN** the docs mark it as blocking or explicitly deferred instead of leaving it ambiguous.

### Non-Functional Requirements

- **Performance:** Phase 0 remains documentation-only and does not introduce runtime work, but it must preserve the requirement that the scanner loop stays compatible with a 60-second cadence.
- **Security:** No secrets or provider keys are introduced during this bead; all future secret handling stays config-driven.
- **Accessibility:** Documentation should remain direct and readable so future implementers can follow the locked decisions without interpreting hidden assumptions.
- **Compatibility:** All planning outcomes must preserve compatibility with the existing stock module, the current Python 3 shell reality, and the current React/Electron surfaces.
- **Reliability:** The Phase 1 implementation bead should be able to start from these outputs without redoing foundational architecture review.

---

## Success Criteria

- [ ] Product-direction guardrails are explicitly aligned across the startup checklist, start plan, and crypto PRD.
  - Verify: manual review of `.docs/startup-checklist.md`, `.docs/project-start-plan.md`, and `.opencode/memory/project/prd-crypto-new-launch-scanner.md`
- [ ] Phase 1 schema decisions are locked with a clear MVP boundary and deferred tables documented separately.
  - Verify: manual review of `.docs/database-schema.md` and `.docs/startup-checklist.md`
- [ ] Phase 1 API contract decisions are locked with dedicated namespace, live-feed pagination, freshness metadata, and partial-data semantics.
  - Verify: manual review of `.docs/api-contracts.md` and `.docs/startup-checklist.md`
- [ ] Source budgets, retry/cache rules, and deterministic test strategy are locked for the first implementation slice.
  - Verify: manual review of `.docs/security-and-rate-limits.md` and `.docs/testing-strategy.md`
- [ ] A Phase 1 go/no-go package exists and any planning-doc edits remain governance-clean.
  - Verify: `python3 scripts/check_ai_assets.py` if governance or planning docs are changed while executing this bead

---

## Technical Context

### Existing Patterns

- Pattern 1: `src/scheduler.py:56` - Existing scheduling patterns are the reference for the future 60-second crypto loop, but Phase 0 should only lock rules around its use.
- Pattern 2: `src/storage.py:64` - Existing SQLAlchemy market-row conventions are the persistence reference for crypto schema planning.
- Pattern 3: `src/storage.py:623` - Existing `DatabaseManager` access patterns show how crypto repository design should align with the current storage layer.
- Pattern 4: `api/v1/router.py:17` - Existing route registration is the reference point for a dedicated crypto namespace.
- Pattern 5: `src/services/system_config_service.py:55` - Existing settings persistence is the reference for future scanner settings endpoints.
- Pattern 6: `apps/dsa-web/src/stores/stockPoolStore.ts:25` - Existing frontend store shape is the pattern reference for future crypto scanner state.
- Pattern 7: `src/core/trading_calendar.py:33` - This file is relevant because Phase 0 must explicitly keep crypto work out of stock trading-calendar assumptions.
- Pattern 8: `data_provider/base.py:65` - Stock normalization helpers are relevant because they are a documented do-not-reuse boundary for crypto identifiers.
- Pattern 9: `src/analyzer.py:34` - Stock-oriented AI analysis boundaries are relevant because Phase 0 must keep AI out of the deterministic scanner loop.

### Key Files

- `.docs/startup-checklist.md` - Defines the pre-coding checklist and go/no-go conditions Phase 0 is meant to lock.
- `.docs/project-start-plan.md` - Defines the workstreams and delivery order that Phase 0 must interpret consistently.
- `.docs/database-schema.md` - Defines the proposed launch, snapshot, security, and AI schema split for crypto.
- `.docs/api-contracts.md` - Defines the dedicated `/api/v1/crypto/*` contract and feed/detail/settings semantics.
- `.docs/security-and-rate-limits.md` - Defines provider roles, rate budgets, retry/backoff rules, and cache policy.
- `.docs/testing-strategy.md` - Defines fixture-driven offline validation and non-regression expectations.
- `.opencode/memory/project/prd-crypto-new-launch-scanner.md` - Holds the current authoritative feature PRD that Phase 0 must refine into executable Phase 1 boundaries.
- `src/scheduler.py` - Future implementation reference for scanner cadence decisions.
- `src/storage.py` - Future implementation reference for schema placement decisions.
- `api/v1/router.py` - Future implementation reference for route registration decisions.

### Affected Files

Files this bead will modify (for conflict detection):

```yaml
files:
  - .docs/startup-checklist.md # Lock Phase 1 prerequisites and go/no-go criteria
  - .docs/project-start-plan.md # Align delivery order and first-slice expectations
  - .docs/database-schema.md # Confirm MVP schema boundary and deferred tables
  - .docs/api-contracts.md # Confirm API namespace and live-feed contract rules
  - .docs/security-and-rate-limits.md # Confirm source roles, retry policy, and rate budgets
  - .docs/testing-strategy.md # Confirm deterministic validation requirements
  - .opencode/memory/project/prd-crypto-new-launch-scanner.md # Keep the main crypto PRD aligned with Phase 0 decisions
```

---

## Risks & Mitigations

| Risk                                                                                           | Likelihood | Impact | Mitigation                                                                                         |
| ---------------------------------------------------------------------------------------------- | ---------- | ------ | -------------------------------------------------------------------------------------------------- |
| Phase 0 restates the docs without actually resolving blocking choices                          | Medium     | High   | Convert each prerequisite into an explicit keep/defer/resolve outcome instead of a passive summary |
| Stock-specific assumptions still leak into Phase 1 because guardrails stay informal            | Medium     | High   | Keep the do-not-reuse boundaries explicit in the checklist and PRD                                 |
| The bead grows into implementation work instead of staying planning-only                       | Low        | High   | Keep scope documentation-only and treat code work as the next bead                                 |
| Delivery-order ambiguity remains between the roadmap phase split and the first shippable slice | Medium     | Medium | Record the distinction explicitly: roadmap phases versus first end-to-end build slice              |

---

## Open Questions

| Question                                                                                                                                                                       | Owner        | Due Date | Status |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------ | -------- | ------ |
| Should the first implementation bead follow the narrow roadmap Phase 1 (discovery and persistence only) or the wider first shippable slice that includes API and scanner page? | Product/User | TBD      | Open   |
| Should `CryptoLaunchSnapshot` be mandatory in the first implementation bead, or can the team start with only `CryptoLaunch` if execution pressure is high?                     | Engineering  | TBD      | Open   |
| Should saved settings endpoints be treated as part of the first release boundary or deferred until the main scanner feed is stable?                                            | Product/User | TBD      | Open   |
| Should the first release be explicitly web-first, with Electron treated as passive reuse only?                                                                                 | Product/User | TBD      | Open   |

---

## Tasks

Write tasks in a machine-convertible format for `prd-task` skill.

**Rules:**

- Each task is a `### <Title> [category]` heading
- Provide one sentence describing the end state
- Include `**Metadata:**` with dependency info
- Include `**Verification:**` with bullet steps proving it works

### Lock product direction and architecture guardrails [planning]

The startup checklist, start plan, and main crypto PRD agree on backbone, additive-module, deterministic-loop, and AI-boundary decisions.

**Metadata:**

```yaml
depends_on: []
parallel: false
conflicts_with: []
files:
  - .docs/startup-checklist.md
  - .docs/project-start-plan.md
  - .opencode/memory/project/prd-crypto-new-launch-scanner.md
```

**Verification:**

- Manual review confirms the same backbone/additive/AI-boundary rules appear across the three planning docs
- `rg "product backbone|additive|deterministic|TradingAgents|AI" .docs/startup-checklist.md .docs/project-start-plan.md .opencode/memory/project/prd-crypto-new-launch-scanner.md`

### Lock Phase 1 schema boundary [design]

The schema docs clearly define canonical launch identity, launch-versus-snapshot separation, and which tables are deferred beyond the first implementation bead.

**Metadata:**

```yaml
depends_on: ["Lock product direction and architecture guardrails"]
parallel: false
conflicts_with: []
files:
  - .docs/database-schema.md
  - .docs/startup-checklist.md
  - .opencode/memory/project/prd-crypto-new-launch-scanner.md
```

**Verification:**

- Manual review confirms `chain_id + pair_address`, launch/snapshot separation, and deferred security/AI tables are explicit
- `rg "chain_id|pair_address|CryptoLaunchSnapshot|CryptoLaunchSecurityScan|CryptoLaunchAiSummary|Minimum MVP Schema" .docs/database-schema.md .docs/startup-checklist.md`

### Lock crypto API contract and sequencing boundary [design]

The planning docs clearly state the dedicated crypto API namespace, live-feed semantics, and where the first implementation slice stops versus later phases.

**Metadata:**

```yaml
depends_on: ["Lock Phase 1 schema boundary"]
parallel: false
conflicts_with: []
files:
  - .docs/api-contracts.md
  - .docs/project-start-plan.md
  - .docs/startup-checklist.md
  - .opencode/memory/project/prd-crypto-new-launch-scanner.md
```

**Verification:**

- Manual review confirms `/api/v1/crypto/*`, cursor pagination, freshness metadata, partial-data behavior, and the first-slice boundary are explicit
- `rg "/api/v1/crypto|cursor|freshness|partial|settings|Phase 1 Scope|Phase 2" .docs/api-contracts.md .docs/project-start-plan.md .docs/startup-checklist.md`

### Lock source budgets and deterministic test policy [ops]

The project docs clearly define provider roles, retry/cache behavior, and offline-first validation rules for the first implementation bead.

**Metadata:**

```yaml
depends_on: ["Lock crypto API contract and sequencing boundary"]
parallel: false
conflicts_with: []
files:
  - .docs/security-and-rate-limits.md
  - .docs/testing-strategy.md
  - .docs/startup-checklist.md
```

**Verification:**

- Manual review confirms provider budgets, retry codes, cache TTLs, fixture usage, and no-network defaults are explicit and compatible with the first implementation slice
- `rg '30 requests per minute|300 requests per minute|max_retries|timeout_seconds|python3 -m pytest -m "not network"|npm run lint && npm run build && npm run test' .docs/security-and-rate-limits.md .docs/testing-strategy.md .docs/startup-checklist.md`

### Publish Phase 1 go/no-go handoff [docs]

The planning package explicitly states whether implementation can begin next and which unresolved items are blocking versus deferred.

**Metadata:**

```yaml
depends_on:
  - "Lock Phase 1 schema boundary"
  - "Lock crypto API contract and sequencing boundary"
  - "Lock source budgets and deterministic test policy"
parallel: false
conflicts_with: []
files:
  - .docs/startup-checklist.md
  - .docs/project-start-plan.md
  - .docs/README.md
  - .opencode/memory/project/prd-crypto-new-launch-scanner.md
```

**Verification:**

- Manual review confirms every go/no-go item is either resolved, marked blocking, or explicitly deferred
- `python3 scripts/check_ai_assets.py` if governance or planning docs are modified while executing this bead

---

## Dependency Legend

| Field            | Purpose                                           | Example                                    |
| ---------------- | ------------------------------------------------- | ------------------------------------------ |
| `depends_on`     | Must complete before this task starts             | `["Setup database", "Create schema"]`      |
| `parallel`       | Can run concurrently with other parallel tasks    | `true` / `false`                           |
| `conflicts_with` | Cannot run in parallel (same files)               | `["Update config"]`                        |
| `files`          | Files this task modifies (for conflict detection) | `["src/db/schema.ts", "src/db/client.ts"]` |

---

## Notes

- This bead is specification-only and must not introduce implementation code.
- The Phase 0 purpose is to turn the existing crypto docs into a clear entry gate for the next implementation bead.
- In this shell, verification commands should use `python3`, not bare `python`.
