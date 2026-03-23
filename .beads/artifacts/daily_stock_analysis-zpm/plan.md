# Plan: Phase 0 - Lock Pre-Implementation Decisions

## Goal

Resolve the delivery-order inconsistency across the crypto planning docs, record the locked user decisions, and produce an explicit Phase 1 go/no-go handoff so the next implementation bead starts from settled assumptions instead of reopening core design questions.

## Locked Decisions

| #   | Decision                        | Answer                                                                                    |
| --- | ------------------------------- | ----------------------------------------------------------------------------------------- |
| 1   | First implementation bead scope | Wide first slice: discovery + persistence + API + scanner page in one bead                |
| 2   | Snapshot table                  | Include `CryptoLaunch` + `CryptoLaunchSnapshot` together in the first implementation bead |
| 3   | Settings endpoints              | Defer `GET/PUT /api/v1/crypto/settings` until after the core scanner feed is stable       |
| 4   | Platform priority               | Web-first; Electron is passive reuse only for the first release                           |

## Constraints

- Documentation-only bead. No implementation code, runtime behavior changes, schema migrations, API routes, or frontend components.
- Keep edits minimal and decision-focused. Lock what is already agreed rather than rewriting the full planning package.
- Preserve the existing backbone decision: crypto is additive to the stock product, not a replacement.
- Preserve the deterministic 60-second scanner lane and keep AI outside that loop for Phase 1.
- Run `python3 scripts/check_ai_assets.py` before claiming the bead plan is ready for execution if governance or planning docs are changed.

## Primary Alignment Fix

The core inconsistency to resolve is delivery order:

- `.docs/project-start-plan.md` currently splits backend work into Phase 1 and API/UI into Phase 2.
- `.docs/startup-checklist.md` already treats the first build slice as end-to-end: discovery + persistence + API + scanner page.
- `.docs/project-start-plan.md` also recommends an end-to-end first slice in the "Recommended First Build Slice" section.

Phase 0 will explicitly align the delivery order to the locked decision: the first implementation bead is the wide first slice, while settings, alerts, security-provider depth, AI analysis, and desktop-specific work remain deferred.

## Execution Phases

### Phase 1: Lock product direction and architecture guardrails

**Task ID:** `planning-1`

**Files:**

- `.docs/startup-checklist.md`
- `.docs/project-start-plan.md`
- `.opencode/memory/project/prd-crypto-new-launch-scanner.md`

**End state:**

The startup checklist, start plan, and main crypto PRD all agree on backbone, additive-module, deterministic-loop, and AI-boundary decisions, and the delivery-order ambiguity is removed.

**Changes:**

- Add explicit locked markers to the product-direction decisions in `.docs/startup-checklist.md`.
- Rewrite the delivery-order section in `.docs/project-start-plan.md` so Phase 1 matches the wide first slice.
- Mark all 4 open questions as resolved in `.docs/project-start-plan.md`.
- Mark all 4 open questions as resolved in `.opencode/memory/project/prd-crypto-new-launch-scanner.md`.

**Verification:**

- Manual review confirms backbone, additive, deterministic-loop, and AI-boundary rules match across the three planning docs.
- Manual review confirms the delivery-order section in `.docs/project-start-plan.md` matches the wide first slice.

### Phase 2: Lock Phase 1 schema boundary

**Task ID:** `design-1`

**Depends on:** `planning-1`

**Files:**

- `.docs/database-schema.md`
- `.docs/startup-checklist.md`
- `.opencode/memory/project/prd-crypto-new-launch-scanner.md`

**End state:**

The schema docs explicitly state that Phase 1 requires `CryptoLaunch` + `CryptoLaunchSnapshot`, uses `chain_id + pair_address` as the canonical key, and defers security/AI tables to later phases.

**Changes:**

- Add a short Phase 1 schema-boundary section to `.docs/database-schema.md`.
- Convert the current MVP wording into an explicit lock: `CryptoLaunch` + `CryptoLaunchSnapshot` are part of the first implementation bead.
- Mark schema decisions as locked in `.docs/startup-checklist.md`.
- Reflect the resolved snapshot-table decision in `.opencode/memory/project/prd-crypto-new-launch-scanner.md`.

**Verification:**

- Manual review confirms `chain_id + pair_address`, launch/snapshot separation, and deferral of `CryptoLaunchSecurityScan` and `CryptoLaunchAiSummary` are explicit.

### Phase 3: Lock crypto API contract and sequencing boundary

**Task ID:** `design-2`

**Depends on:** `design-1`

**Files:**

- `.docs/api-contracts.md`
- `.docs/project-start-plan.md`
- `.docs/startup-checklist.md`
- `.opencode/memory/project/prd-crypto-new-launch-scanner.md`

**End state:**

The docs clearly state which crypto endpoints are part of the first implementation slice and which ones are deferred.

**Changes:**

- Add an explicit Phase 1 API-boundary section to `.docs/api-contracts.md`.
- Confirm Phase 1 includes `GET /api/v1/crypto/launches`, `GET /api/v1/crypto/launches/{launch_id}`, `POST /api/v1/crypto/refresh`, and `GET /api/v1/crypto/status`.
- Mark `GET/PUT /api/v1/crypto/settings` as deferred until after the core feed is stable.
- Mark `POST /api/v1/crypto/launches/{launch_id}/analyze` as deferred beyond Phase 1.
- Update `.docs/startup-checklist.md` deferred items to include settings and AI endpoints explicitly.
- Reflect the resolved settings-endpoint decision in `.opencode/memory/project/prd-crypto-new-launch-scanner.md`.

**Verification:**

- Manual review confirms the dedicated `/api/v1/crypto/*` namespace, cursor pagination, freshness metadata, and partial-data semantics remain intact.
- Manual review confirms the first-slice API boundary is explicit and consistent across docs.

### Phase 4: Lock source budgets and deterministic test policy

**Task ID:** `ops-1`

**Depends on:** `design-2`

**Files:**

- `.docs/security-and-rate-limits.md`
- `.docs/testing-strategy.md`
- `.docs/startup-checklist.md`

**End state:**

The docs clearly define the operating envelope for provider usage and the minimum deterministic verification required for the first implementation bead.

**Changes:**

- Add explicit locked markers for the Phase 1 provider-budget and failure-handling decisions in `.docs/security-and-rate-limits.md`.
- Add a concise Phase 1 minimum-test-expectations section to `.docs/testing-strategy.md`.
- Mark operational and test-readiness decisions as locked in `.docs/startup-checklist.md`.
- Preserve the existing non-blocking enrichment/security and offline-first defaults.

**Verification:**

- Manual review confirms provider budgets, retry policy, cache rules, and non-blocking behavior remain explicit.
- Manual review confirms the deterministic test expectations remain centered on `python3 -m pytest -m "not network"` and `cd apps/dsa-web && npm ci && npm run lint && npm run build && npm run test`.

### Phase 5: Publish Phase 1 go/no-go handoff

**Task ID:** `docs-1`

**Depends on:** `design-1`, `design-2`, `ops-1`

**Files:**

- `.docs/startup-checklist.md`
- `.docs/project-start-plan.md`
- `.docs/README.md`
- `.opencode/memory/project/prd-crypto-new-launch-scanner.md`

**End state:**

The planning package explicitly states that Phase 1 may begin, and every previously open prerequisite is now either resolved or explicitly deferred.

**Changes:**

- Add a Phase 0 outcome section that states the planning gate passed.
- Check all go/no-go boxes in `.docs/startup-checklist.md` once the prerequisite edits are complete.
- Add a short Phase 0 status note to `.docs/project-start-plan.md`.
- Update `.docs/README.md` so the package index reflects that Phase 0 has locked the build-start docs.
- Add a short note to `.opencode/memory/project/prd-crypto-new-launch-scanner.md` that the Phase 0 bead resolved the open implementation-boundary questions.

**Verification:**

- Manual review confirms every go/no-go item is either checked, resolved, or explicitly deferred.
- Run `python3 scripts/check_ai_assets.py` after the doc updates.

## Dependency Graph

```text
planning-1 -> design-1 -> design-2 -> ops-1
                    \        \        /
                     \        \      /
                      ------> docs-1
```

## Wave Plan

- Wave 1: `planning-1`
- Wave 2: `design-1`
- Wave 3: `design-2`
- Wave 4: `ops-1`
- Wave 5: `docs-1`

This bead stays sequential because the files and decisions are tightly coupled.

## Completion Criteria

Phase 0 is complete when all of the following are true:

1. The delivery-order inconsistency is removed.
2. The 4 user decisions are reflected consistently across the planning docs.
3. The first implementation bead is explicitly defined as the wide first slice.
4. `CryptoLaunchSnapshot` is explicitly included in the Phase 1 schema boundary.
5. Settings endpoints and AI analysis endpoints are explicitly deferred.
6. The first release is explicitly web-first, with Electron treated as passive reuse.
7. `.docs/startup-checklist.md` contains a clear go/no-go pass state.
8. `python3 scripts/check_ai_assets.py` passes after the docs are updated.

## Notes For Execution

- Do not drift into implementation work while executing this plan.
- Do not add new open questions unless the docs reveal a true architectural conflict.
- If a new architectural conflict appears, stop and ask before changing scope.
