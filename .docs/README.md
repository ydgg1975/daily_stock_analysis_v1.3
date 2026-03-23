# Project Docs Index

This folder contains the verified kickoff docs for the crypto scanner project built on top of the current repo.

## Phase 0 Status

- Phase 0 planning gate passed on 2026-03-20.
- The first implementation bead is locked as the wide first slice: discovery + persistence + API + scanner page.
- `CryptoLaunch` and `CryptoLaunchSnapshot` are both part of the Phase 1 schema boundary.
- Settings endpoints, alerting, and selective AI remain deferred until after the core scanner foundation is stable.

## Read Order

1. `repo-verification-and-comparison.md`
   - Verified comparison between the local repo and `TradingAgents`
   - Confirms what should be reused, isolated, or borrowed

2. `crypto-integration-architecture.md`
   - Target combined architecture for stock lane + crypto scanner + selective AI lane

3. `project-start-plan.md`
   - Workstreams, file mapping, delivery order, and what to build first

4. `startup-checklist.md`
   - Pre-coding checklist and locked go/no-go checks before Phase 1

5. `database-schema.md`
   - Canonical schema design for launch, snapshot, security, and AI summary data

6. `api-contracts.md`
   - API surface, request/response shape, cursoring, and partial-data semantics

7. `security-and-rate-limits.md`
   - Source strategy, rate budgets, retry/backoff, cache TTLs, and security providers

8. `testing-strategy.md`
   - Offline, integration, contract, and UI validation strategy

9. `config-reference.md`
   - Proposed crypto config keys, defaults, and feature-flag behavior

10. `observability-runbook.md`
    - Metrics, logging, alerts, backfill visibility, and incident checks

11. `tradingagents-integration-plan.md`
    - How to borrow `TradingAgents` patterns without adopting it as the product runtime

12. `desktop-impact.md`
    - Electron-specific impacts, build considerations, and QA checks

## Related Documents Outside `.docs/`

- PRD: `.opencode/memory/project/prd-crypto-new-launch-scanner.md`
- Planning context: `.opencode/memory/project/project.md`
- Roadmap: `.opencode/memory/project/roadmap.md`
- State: `.opencode/memory/project/state.md`

## Core Decisions Already Verified

- The current repo should remain the product backbone.
- `TradingAgents` should be borrowed as an intelligence pattern, not adopted as the primary runtime.
- GeckoTerminal should be the discovery backbone for new launches.
- DexScreener should be used as an enrichment source, not the sole discovery source.
- The 60-second scanner loop must remain deterministic; AI must run only on shortlisted launches.

## Start Here If You Want To Build

- For architecture first: open `crypto-integration-architecture.md`
- For implementation sequencing first: open `project-start-plan.md`
- For proof that the architecture fits both codebases: open `repo-verification-and-comparison.md`
- For immediate execution safety: open `startup-checklist.md`

## Current Package

- Strategy and verification
  - `repo-verification-and-comparison.md`
  - `crypto-integration-architecture.md`
  - `project-start-plan.md`
- Build-start docs
  - `startup-checklist.md`
  - `database-schema.md`
  - `api-contracts.md`
  - `security-and-rate-limits.md`
  - `testing-strategy.md`

These build-start docs are now Phase 0 locked inputs for the next implementation bead.

- `config-reference.md`
- `observability-runbook.md`
- `tradingagents-integration-plan.md`
- `desktop-impact.md`
