# System Optimization Roadmap

Date: 2026-04-16
Scope: actionable whole-system optimization roadmap for `WOLFY9527/daily_stock_analysis`
Mode: planning pass only; no broad implementation in this document

Companion references:

- [`system-optimization-audit.md`](./system-optimization-audit.md)
- [`postgresql-baseline-gap-audit.md`](./postgresql-baseline-gap-audit.md)
- [`postgresql-baseline-design.md`](./postgresql-baseline-design.md)
- [`postgresql-baseline-plan.md`](./postgresql-baseline-plan.md)
- [`postgresql-baseline-v1.sql`](./postgresql-baseline-v1.sql)

## Executive Summary

The original optimization audit correctly identified the main hotspots, but it was written before the repo was treated as having completed:

- PostgreSQL coexistence migration Phases A-G to the intended slice level
- a closure/stabilization pass
- a deployment-hardening pass
- a repo-green hardening pass

With those assumptions in force, the next move is **not** a broad refactor. The system is stable enough for manual local validation and then server deployment, so the roadmap should now favor:

1. preserving the current stable deployment path
2. capturing reproducible baselines before touching hot paths
3. deploying and observing
4. executing a small number of high-ROI, bounded optimization branches
5. deferring coexistence teardown and broad cleanup until parity is proven in a real observation window

Highest-ROI sequence:

1. benchmark + clean-checkout validation path
2. portfolio snapshot read-path optimization
3. scanner shared-flow consolidation
4. search/provider duplicate-work reduction
5. repository-boundary tightening around `DatabaseManager`
6. control-plane/settings simplification

The audit remains useful, but some of its former “before deployment” findings are now closed prerequisites rather than fresh roadmap items. This document converts the audit into a branch-friendly execution queue that separates:

- deployment blockers
- near-term optimization branches
- simplification and cleanup work
- measurement-gated work
- later optional improvements

## Assumptions

- PostgreSQL coexistence migration across Phases A-G is complete to the intended slice level.
- Closure/stabilization, deployment-hardening, and repo-green hardening are complete.
- The backend is stable enough for manual local validation and then server deployment.
- `.env` remains the active runtime source of truth during coexistence; PostgreSQL shadow/control-plane rows are not yet the sole runtime authority.
- PostgreSQL remains the target system-of-record for product/business/auth/session/hot metadata.
- Parquet plus local/NAS remains the primary store for bulk historical OHLCV and benchmark bodies.
- Scanner and backtest remain separate product capabilities.
- Deterministic scanner ranking remains primary; AI interpretation stays additive.
- User-owned flows remain separate from admin/operator flows.
- This roadmap does not authorize a broad implementation pass, core product-flow rewrites, immediate coexistence teardown, or deployment execution itself.

## Prioritization Framework

### Priority bands

- `P0`: must do before deployment, or before any performance branch starts, because it prevents blind optimization or weak deployment validation
- `P1`: highest-ROI work to do immediately after deployment; bounded, reversible, and behavior-preserving
- `P2`: do after a parity/observation window; cleanup, consolidation, and deprecation removal
- `P3`: later or optional; useful but not urgent for current deployment

### Decision rules

- Prefer changes that improve latency, operational clarity, or maintainability without changing product behavior.
- Require benchmarking first when the likely bottleneck is mixed CPU + I/O + DB + algorithmic work.
- Preserve the current architecture boundaries unless the roadmap item explicitly says otherwise:
  - scanner vs backtest
  - user vs admin/operator
  - PostgreSQL metadata/business records vs Parquet/local/NAS OHLCV bodies
  - coexistence safety nets during the first stability window
- Avoid deleting compatibility layers until one parity/observation window completes without needing them.
- Do not split large files just because they are large; only split when duplication, safety, or operational clarity justify it.

## Audit Findings Already Closed

These items were valid in the original audit, but should not be queued again as new implementation branches unless deployment evidence reopens them:

- `api/app.py` now exposes `/api/health/live`, `/api/health/ready`, and `/api/health` as a readiness alias.
- `docker/Dockerfile` now health-checks `/api/health/ready` directly.
- `api/app.py` now wires task-queue shutdown into app lifecycle.
- `docs/DEPLOY.md` and `docs/DEPLOY_EN.md` already document the current process-local queue/SSE single-process or sticky-routing constraint.
- The dead `api/v1/endpoints/health.py` surface referenced in the audit is already gone.

Operationally, this means the deployment-hardening pass should be treated as a completed prerequisite. The roadmap below only keeps the remaining pre-deployment work that still matters after those fixes.

## Boundaries To Preserve

### Preserve now

- Keep `src/services/market_scanner_service.py` and backtest services as separate capability centers.
- Keep `src/agent/factory.py` as the central agent construction point.
- Keep `src/repositories/scanner_repo.py`, `src/repositories/backtest_repo.py`, `src/repositories/rule_backtest_repo.py`, and `src/repositories/portfolio_repo.py` as the preferred domain seams.
- Keep `.env` runtime authority until a separate control-plane simplification pass intentionally replaces it.
- Keep `src/postgres_phase_a.py` through `src/postgres_phase_g.py` as safety rails through at least one real observation window.

### Do not touch yet

- Do not do a broad rewrite of `src/storage.py` before deployment.
- Do not merge scanner and backtest into a single product flow.
- Do not turn deterministic scanner ranking into AI-first ranking.
- Do not migrate bulk OHLCV into PostgreSQL.
- Do not remove Phase A-G coexistence scaffolding before parity is proven.
- Do not redesign the whole admin/settings UI before real operator observation exists.

## Pre-Deployment Must-Do Items

Because deployment-hardening is already treated as complete, the remaining pre-deployment work is intentionally narrow.

| Priority | Title | Area / module(s) | Why it matters | Expected impact | Risk | Difficulty | Benchmark first | Timing | Own branch / workstream |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | Reproducible baseline benchmark harness | `src/services/market_scanner_service.py`, `src/services/portfolio_service.py`, `src/core/pipeline.py`, `src/search_service.py`, `src/services/backtest_service.py`, `src/services/rule_backtest_service.py`, `scripts/` | The next optimization branches are all mixed-bottleneck work. Without stable baseline capture, later tuning will be guesswork and regressions will be hard to detect. | High decision quality and regression protection | Low | Medium | Yes, this item is the measurement pass | Before local manual validation and before deployment | Yes |
| P0 | Canonical clean-checkout smoke path | `test_backtest_run.py`, `scripts/smoke_backtest_standard.py`, `scripts/smoke_backtest_rule.py`, `docs/DEPLOY.md`, `docs/DEPLOY_EN.md` | The tracked wrapper still depends on root smoke helpers that exist locally but are not tracked. Deployment and collaborator validation should use repo-committed entry points only. | Medium confidence / handoff improvement | Low | Small | No | Before server deployment | No, bundle with baseline-validation work |
| P0 | Target-host queue/SSE proof run | `api/app.py`, `src/services/task_queue.py`, `docs/DEPLOY.md`, `docs/DEPLOY_EN.md` | The current queue model is intentionally process-local. Prove the exact single-process or sticky-routing deployment shape on the target host before shipping. | High operational confidence | Low | Small | No | Before server deployment | No, checklist-driven |
| P0 | Canonical manual-validation and rollback pack | `docs/DEPLOY.md`, `docs/DEPLOY_EN.md`, `docs/full-guide.md`, `docs/full-guide_EN.md` | The backend is stable enough to validate now. Deployment should use one canonical validation flow, one rollback path, and one operator-facing smoke command set. | High operational clarity | Low | Small | No | Before server deployment | No, bundle with validation docs cleanup |
| P0 | Freeze destructive cleanup before first observation window | `src/storage.py`, `src/postgres_phase_*.py`, `main.py`, `webui.py`, `src/agent/strategies/*`, `apps/dsa-web/src/pages/SettingsPage.tsx` | Removing safety nets or splitting large files before real deployment observation will make rollback harder and will contaminate the baseline that later optimization work depends on. | High stability protection | Low | Small | No | Before deployment | No |

### Before local manual validation

- Finish the reproducible benchmark harness and record the initial baseline.
- Ensure the clean-checkout smoke path does not depend on untracked root helpers.

### Before server deployment

- Run the single-process queue/SSE proof run on the real target host or a target-like host.
- Freeze the operator validation and rollback checklist.
- Hold all coexistence teardown, alias deletion, and large-file splitting until after the first observation window.

## Early Post-Deployment Priority Queue

These are the first optimization branches to open once deployment is live and the initial observation window confirms the current deployment path is stable.

| Rank | Title | Area / module(s) | Why it matters | Expected impact | Risk | Difficulty | Benchmark first | Timing | Own branch / workstream |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Portfolio snapshot read-path optimization | `src/services/portfolio_service.py`, `src/repositories/portfolio_repo.py`, `api/v1/endpoints/portfolio.py` | `get_portfolio_snapshot()` still rebuilds account state and writes snapshot rows during reads, while `_build_positions()` performs per-symbol latest-close lookup. This is expensive in a user-facing path. | High latency reduction and lower DB/write amplification | Medium | Medium | Yes | Immediately after deployment | Yes |
| 2 | Scanner shared execution skeleton | `src/services/market_scanner_service.py`, `src/services/market_scanner_ops_service.py`, `src/repositories/scanner_repo.py` | CN/US/HK flows still duplicate pre-rank, candidate expansion, diagnostics assembly, and response shaping. This is the clearest combined performance + maintainability hotspot. | High latency and maintainability gain | Medium | Medium | Yes | Immediately after deployment | Yes |
| 3 | Search/news dedupe and cache strengthening | `src/search_service.py`, `src/core/pipeline.py` | Repeated article fetch/parsing and process-local cache behavior create duplicate network work across analysis runs. | Medium-high latency and cost reduction | Medium | Medium | Yes | Immediately after deployment | Yes |
| 4 | Provider/universe loading reduction | `data_provider/base.py`, `src/services/market_scanner_service.py`, `src/repositories/stock_repo.py` | Scanner and analysis still pay avoidable stock-list load, normalization, and row-iteration costs, especially at universe scale. | High scanner throughput gain | Medium | Medium | Yes | Immediately after deployment | Yes |
| 5 | High-churn `DatabaseManager` boundary tightening | `api/v1/endpoints/auth.py`, `api/v1/endpoints/analysis.py`, `src/services/history_service.py`, `src/services/market_scanner_service.py`, `src/storage.py`, relevant repositories | Direct storage reach-through still competes with repository seams. Tightening the hottest paths first reduces change risk in every later branch. | Medium-high maintainability gain | Medium | Medium | No | Immediately after deployment | Yes |

## High-ROI Optimization Backlog

These items are worthwhile, but they should follow the early post-deployment priority queue rather than compete with it.

| Priority | Title | Area / module(s) | Why it matters | Expected impact | Risk | Difficulty | Benchmark first | Timing | Own branch / workstream |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | Pipeline pacing correction | `src/core/pipeline.py` | The current sleep occurs after completed futures are collected, so real outbound burst control still depends mostly on `max_workers`. Fixing this improves rate-shaping without changing the overall analysis product flow. | Medium latency stability / provider-pressure reduction | Medium | Medium | Yes | Immediately after deployment, after baseline capture | Yes |
| P1 | Backtest sample-preparation optimization | `src/services/backtest_service.py`, `src/services/rule_backtest_service.py`, `src/repositories/backtest_repo.py`, `src/repositories/rule_backtest_repo.py` | Backtest is not the top deployment blocker, but duplicate history-fill and candidate-prep work will become visible once scanner and portfolio hotspots are improved. | Medium throughput gain | Medium | Medium | Yes | After the first post-deploy optimization wave | Yes |
| P1 | Minimal run-level observability gap fill | `src/services/execution_log_service.py`, `src/services/market_scanner_service.py`, `src/services/portfolio_service.py`, `src/core/pipeline.py` | If the benchmark pass shows inconsistent timing, input-size, or cache-hit signals, add only the missing fields needed to guide later work. Do not build a new telemetry system. | High prioritization clarity | Low-Medium | Small-Medium | No, triggered by benchmark findings | Immediately after deployment if required | Yes, only if missing data is real |
| P2 | Control-plane/settings simplification | `apps/dsa-web/src/pages/SettingsPage.tsx`, `src/services/system_config_service.py`, `apps/dsa-web/src/App.tsx` | The user/admin split is right, but the operator surface is still too dense and mixes rare destructive actions with common config tasks. | Medium operator-safety and maintainability gain | Low | Medium | No | After a short operator observation window | Yes |
| P2 | Bot/API task execution convergence decision | `src/services/task_queue.py`, `src/services/task_service.py`, `bot/commands/analyze.py` | There are still two async execution stacks. This should be resolved only after real deployment shows whether the split is a true problem or merely historical. | Medium maintainability gain | Medium | Medium | No | After parity/observation window | Yes |
| P3 | Deep file decomposition of oversized modules | `src/core/pipeline.py`, `src/services/report_renderer.py`, `src/search_service.py`, `data_provider/base.py`, `apps/dsa-web/src/pages/SettingsPage.tsx` | File size alone is not the priority. Split only after the higher-value performance and cleanup work clarifies stable boundaries. | Medium maintainability gain | Medium | Large | No | Later / optional | Yes |

## Architecture Simplification Backlog

This is the simplification queue that should run only after the early deployment window proves parity and stability.

| Priority | Title | Area / module(s) | Why it matters | Expected impact | Risk | Difficulty | Benchmark first | Timing | Own branch / workstream |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P2 | Shrink `DatabaseManager` by domain adapter extraction, not rewrite | `src/storage.py`, `src/repositories/*`, selected services/endpoints | `src/storage.py` is still the dominant complexity sink. The right move is to peel repeated domain-facing reads/writes into repositories or narrow adapters, not to restart storage architecture. | High maintainability gain | High | Large | No | After parity/observation window | Yes |
| P2 | Retire Phase D/E shadow helpers first | `src/postgres_phase_d.py`, `src/postgres_phase_e.py`, `src/storage.py`, scanner/backtest repositories | Scanner and backtest shadow paths are better teardown candidates than auth or portfolio once canonical reads/writes are proven. | Medium complexity reduction | Medium-High | Medium | No | After parity/observation window | Yes |
| P2 | Keep Phase A/B/F/G longer | `src/postgres_phase_a.py`, `src/postgres_phase_b.py`, `src/postgres_phase_f.py`, `src/postgres_phase_g.py`, `src/auth.py`, `api/deps.py`, `src/services/system_config_service.py` | Auth/session continuity, portfolio ownership, and runtime config authority are more sensitive than scanner/backtest. Removing these safety nets too early is the wrong tradeoff. | High stability protection | Low | Small | No | After a longer parity window | No, this is a hold decision |
| P2 | Decide the permanent home for analysis auxiliary artifacts | `news_intel`, `fundamental_snapshot`, future analysis artifact rows or tables, `src/services/analysis_service.py`, `src/storage.py`, future analysis repository code | PostgreSQL baseline docs still flag this as unresolved. The decision should happen before deeper analysis persistence cleanup, not during generic optimization work. | Medium architecture clarity | Medium | Medium | No | After deployment, before analysis persistence refactors | Yes |
| P2 | Decide portfolio materialization policy | `portfolio_positions`, `portfolio_position_lots`, `portfolio_daily_snapshots`, `portfolio_fx_rates`, `src/services/portfolio_service.py`, `src/repositories/portfolio_repo.py` | The baseline docs intentionally left open whether these remain durable materializations or become refreshable/derived caches. This must be decided before deeper portfolio cleanup. | High architecture clarity | Medium | Medium | Yes | After the first portfolio optimization wave | Yes |

## Simplification / Merge / Delete Backlog

These items are intentionally lower priority than the post-deployment performance work.

| Priority | Title | Area / module(s) | Why it matters | Expected impact | Risk | Difficulty | Benchmark first | Timing | Own branch / workstream |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P2 | Hide and split destructive admin actions | `apps/dsa-web/src/pages/SettingsPage.tsx`, `src/services/system_config_service.py` | The current control-plane page mixes routine settings with rare maintenance actions. Simplifying the surface lowers operator error without changing backend semantics. | Medium | Low | Medium | No | After a short observation window | Yes |
| P2 | Retire `--webui` and `--webui-only` aliases after one deployment window | `main.py`, `webui.py`, `docs/DEPLOY.md`, `docs/DEPLOY_EN.md`, `README.md` | Current docs already prefer `--serve` and `--serve-only`. Code-level alias cleanup should wait until operator habits have actually shifted. | Medium clarity / smaller entry surface | Medium | Small | No | After parity/observation window | Yes |
| P2 | Remove legacy agent “strategy” wrappers | `src/agent/strategies/*`, `api/v1/endpoints/agent.py`, `src/services/system_config_service.py` | The product surface already prefers “skills”. Wrapper removal should happen only after import paths and compatibility consumers are proven clean. | Medium maintainability gain | Medium | Small | No | After parity/observation window | Yes |
| P1 | Normalize backtest smoke entry points | `test_backtest_run.py`, `scripts/smoke_backtest_standard.py`, `scripts/smoke_backtest_rule.py` | This is partly a pre-deploy cleanliness issue and partly a simplification issue. After the canonical path is adopted, the wrapper convention should be collapsed. | Medium repo-hygiene gain | Low | Small | No | Before deployment, then finish cleanup after observation window | No, bundle with benchmark/validation work |
| P3 | Archive large design assets out of the runtime repo | `sources/` | The tracked `sources/` directory is about 63 MB and not runtime-critical. Moving it to a design-assets location or Git LFS reduces repo weight without affecting runtime behavior. | Medium repo-hygiene gain | Low | Small | No | Later / optional | Yes |
| P3 | Re-evaluate `analyzer_service.py` as an integration asset | `analyzer_service.py`, `SKILL.md` | The file appears to serve local skill/integration usage rather than core runtime. Archive or relocate only after checking external usage and skill expectations. | Low-Medium cleanup gain | Medium | Small | No | Later / optional | Yes |

## Deletion / Archive Candidates

### Good candidates after observation

- `webui.py` and `main.py` `--webui` / `--webui-only`
  - Delete only after the deployment docs and operator habits have clearly moved to `--serve` / `--serve-only`.
- `src/agent/strategies/*`
  - Delete only after the import surface is fully standardized on `skills`.
- Backtest smoke wrapper convention
  - Collapse to repo-committed `scripts/smoke_backtest_standard.py` and `scripts/smoke_backtest_rule.py`.
- `sources/`
  - Archive out of the runtime repo if long-term retention still matters.

### Not deletion candidates yet

- `src/postgres_phase_a.py` through `src/postgres_phase_g.py`
- `src/storage.py` coexistence gating and compatibility reads
- user/admin scanner surface split
- scanner vs backtest product split

## Items Requiring Measurement Before Action

The following items should not be optimized from code inspection alone. They need a stable benchmark capture first.

| Item | Area / module(s) | What to measure first | Why measurement matters | Target timing |
| --- | --- | --- | --- | --- |
| Scanner pipeline consolidation | `src/services/market_scanner_service.py`, `src/services/market_scanner_ops_service.py` | Per-market wall-clock duration, candidate counts at each stage, universe-load duration, detail-evaluation count, provider fallback count, peak memory | The scanner hotspot is a mixed CPU + I/O + duplicate-work problem. Without stage-level timing, it is easy to optimize the wrong stage. | Before opening the scanner branch |
| Portfolio snapshot optimization | `src/services/portfolio_service.py`, `src/repositories/portfolio_repo.py` | Snapshot duration by account size, ledger-event replay count, symbol count, number of latest-close lookups, number of writebacks during read | The current pain is likely a mix of replay cost, price-lookup cost, and unnecessary writes. The dominant cost should drive the fix shape. | Before opening the portfolio branch |
| Search/news dedupe | `src/search_service.py`, `src/core/pipeline.py` | External request count per analysis, duplicate URL rate, article parse time, cache-hit ratio, total analysis latency with and without news | This is network-bound duplicate work. Measurement prevents overbuilding cache layers that do not materially change end-to-end latency. | Before opening the search branch |
| Provider/universe loading optimization | `data_provider/base.py`, `src/repositories/stock_repo.py`, `src/services/market_scanner_service.py` | Universe-load duration, row count, retry count, fallback count, normalization time, cache-hit ratio | Provider/universe work mixes local data, fallback fetchers, and in-process transformation. Measurement reveals whether the win is caching, batching, or algorithmic cleanup. | Before opening the provider branch |
| Backtest preparation optimization | `src/services/backtest_service.py`, `src/services/rule_backtest_service.py` | Time split between sample preparation, history fill, rule execution, persistence, and export generation | Backtest is important but not the first ROI target. Measurement determines whether it is truly a second-wave branch or can stay deferred. | Before any backtest optimization branch |
| Pipeline pacing correction | `src/core/pipeline.py` | Concurrency distribution, outbound request burst shape, provider error/retry rate, end-to-end analysis duration | The current pacing comment in code suggests the existing delay is weak. Measurement shows whether the fix should be dispatch-side throttling, provider-specific pacing, or simply lower concurrency. | Before opening the pacing branch |

## Recommended Branch / Workstream Breakdown

Keep the execution queue intentionally finite. Each branch should have one main responsibility and a clear stop condition.

| Workstream | Scope | Includes | Excludes | Suggested timing |
| --- | --- | --- | --- | --- |
| WS1: Baseline and validation | Pre-deployment measurement and clean-checkout validation | benchmark harness, canonical smoke commands, target-host queue/SSE proof run, rollback checklist cleanup | no runtime optimization, no product-flow changes | Before deployment |
| WS2: Portfolio read-path | Optimize portfolio snapshot reads without changing account semantics | snapshot replay/writeback reduction, batched latest-close lookup, targeted repo/service cleanup | no portfolio product redesign, no ownership model changes | Immediately after deployment |
| WS3: Scanner shared pipeline | Reduce duplicated scanner flow while preserving market-specific ranking hooks | shared execution skeleton, deduped diagnostics/response shaping, targeted provider interaction cleanup | no ranking philosophy change, no scanner/backtest merge | Immediately after deployment |
| WS4: Search/provider dedupe | Reduce duplicate network and universe-loading work | search/article dedupe, cache strengthening, provider/universe caching or batching, optional pacing follow-up | no new search provider stack, no broad pipeline rewrite | Immediately after deployment |
| WS5: Boundary tightening | Reduce `DatabaseManager` reach-through in highest-churn paths | auth/analysis/history/scanner repository alignment, narrow adapter extraction | no broad storage rewrite | After WS2 and WS3 stabilize |
| WS6: Settings simplification | Simplify the operator/control-plane surface | advanced/maintenance split, destructive-action hiding, UI/backend cleanup limited to current semantics | no full UI redesign, no config-authority migration | After a short operator observation window |
| WS7: Cleanup and deprecation | Remove proven-dead aliases/wrappers and archive non-runtime assets | `--webui`/`webui.py`, strategy wrappers, smoke wrapper cleanup, `sources/` archive, `analyzer_service.py` review | no coexistence teardown | After parity/observation window |
| WS8: Coexistence reduction | Retire selected Phase D/E shadow scaffolding and shrink `src/storage.py` safely | phase-specific cleanup, shadow-helper removal, adapter extraction | no Phase A/F/G early teardown, no all-at-once storage rewrite | After a longer parity window |

## Suggested Execution Order

1. Treat deployment-hardening items from the original audit as closed prerequisites, not active backlog.
2. Execute `WS1: Baseline and validation`.
3. Run local manual validation using the canonical clean-checkout path.
4. Deploy using the current single-process/sticky-routing constraint.
5. Let one parity/observation window complete.
   - minimum bar: representative scanner, analysis, portfolio, and backtest usage plus one re-run of the benchmark harness
6. Execute `WS2: Portfolio read-path`.
7. Execute `WS3: Scanner shared pipeline`.
8. Execute `WS4: Search/provider dedupe`.
9. Execute `WS5: Boundary tightening`.
10. Execute `WS6: Settings simplification`.
11. Execute `WS7: Cleanup and deprecation`.
12. Only then consider `WS8: Coexistence reduction`.

## What Should Not Be Touched Yet

- `src/storage.py` should not be broadly refactored before deployment.
- Phase A/B/F/G coexistence scaffolding should not be retired in the first post-deploy wave.
- `src/core/pipeline.py` and `src/services/report_renderer.py` should not be split solely because they are large.
- The scanner/user/admin surface split should not be collapsed.
- Runtime config should not be moved fully off `.env` during the same wave as optimization work.

## Recommended Next Prompt

Use a bounded next prompt such as:

> Using `docs/architecture/system-optimization-roadmap.md` as the source of truth, implement only `WS1: Baseline and validation`. Create or update the minimal scripts/docs needed to run reproducible scanner, portfolio snapshot, analysis/search, and backtest baselines on a clean checkout; normalize the canonical backtest smoke entry points; and update deployment validation docs if needed. Do not optimize scanner, portfolio internals, or storage architecture yet. Verify the exact commands you add or change.
