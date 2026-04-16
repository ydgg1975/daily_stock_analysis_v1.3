# System Optimization Audit

Date: 2026-04-16
Scope: whole-project audit and planning pass for `WOLFY9527/daily_stock_analysis`
Mode: inspection-based audit only, not a broad implementation pass

## Executive Summary

This codebase is functionally broad and now stable enough for a meaningful full-system optimization review, but the main risks are no longer “missing features.” They are complexity concentration, transitional coexistence drag, duplicated execution paths, and operational ambiguity before long-running deployment.

The highest-leverage findings are:

- `src/storage.py` is still the dominant architecture burden. It combines SQLite ORM models, compatibility reads, shadow-write coordination for PostgreSQL Phases A-G, and multiple domain-specific behaviors in one place.
- The scanner is the clearest post-deployment optimization target. `src/services/market_scanner_service.py` contains duplicated CN/US/HK flows, repeated candidate evaluation loops, and avoidable duplicate work.
- Portfolio snapshots are expensive in the worst possible place: on read. `src/services/portfolio_service.py` replays account state and writes fresh snapshots while serving snapshot requests.
- Long-running server deployment is not fully hardened because task execution and SSE state remain process-local in `src/services/task_queue.py`.
- Health and readiness semantics are too shallow. `api/app.py` returns static `ok`, `docker/Dockerfile` can mask failure via a success fallback, and `api/v1/endpoints/health.py` is effectively dead code because it is not mounted.
- The admin/system settings surface has become a control-plane catch-all. The user/admin split is correct and should be preserved, but the operator page itself is too dense.
- The coexistence migration slice is complete enough to operate, but not yet clean enough to collapse. Several Phase A-G compatibility surfaces should remain for one stability window; others are already good candidates for later deletion.

Recommended priority split:

- Before deployment: harden deployment topology and readiness semantics, clarify runtime source-of-truth, wire graceful shutdown expectations, and remove documentation/runbook ambiguity.
- Soon after deployment: simplify scanner flow, optimize portfolio snapshot reads, reduce direct `DatabaseManager` usage outside repositories, and reduce admin surface density.
- Later: collapse shadow-write scaffolding by phase, retire deprecated aliases/wrappers, and archive non-runtime repo assets.

This audit is evidence-based but inspection-driven. No production load test, benchmark suite, or multi-day soak was run in this pass, so performance findings should be read as “high-confidence hotspots from code structure” rather than measured throughput numbers.

## Current System Map

### Practical Runtime Map

| Surface | Primary files | Current role | Audit note |
| --- | --- | --- | --- |
| CLI / scheduler entry | `main.py`, `server.py`, `webui.py` | Runs analysis, scheduled jobs, scanner schedule, and API service entry modes | Too many serve aliases remain; deployment docs still lean on deprecated names |
| FastAPI backend | `api/app.py`, `api/v1/router.py`, `api/v1/endpoints/*.py` | Main API surface for analysis, auth, scanner, backtest, portfolio, agent/chat, settings | Several endpoints are very large and some still bypass repository boundaries |
| Persistence and coexistence | `src/storage.py`, `src/postgres_phase_a.py` ... `src/postgres_phase_g.py` | SQLite primary runtime plus PostgreSQL coexistence/shadow adapters | Biggest architecture complexity concentration |
| Config / control plane | `src/config.py`, `src/services/system_config_service.py`, `src/core/config_registry.py` | `.env`-centric runtime config, validation, admin mutations, Phase G shadow sync | Stable enough to run, but operational authority is still split conceptually |
| Scanner | `src/services/market_scanner_service.py`, `src/services/market_scanner_ops_service.py`, `src/repositories/scanner_repo.py` | CN/US/HK market scans, scoring, shortlist persistence, diagnostics | Highest post-deploy simplification + performance ROI |
| Backtest | `src/services/backtest_service.py`, `src/services/rule_backtest_service.py`, `src/core/rule_backtest_engine.py`, `src/repositories/backtest_repo.py`, `src/repositories/rule_backtest_repo.py` | Historical evaluation and deterministic rule backtest workflows | Domain split is mostly right; some services are oversized |
| Portfolio | `src/services/portfolio_service.py`, `src/repositories/portfolio_repo.py` | Owner-scoped accounts, ledger events, broker overlay sync, snapshots | Snapshot read path is too expensive |
| Analysis / reporting | `src/core/pipeline.py`, `src/analyzer.py`, `src/search_service.py`, `src/services/report_renderer.py` | AI analysis orchestration, news/search, report generation, notifications | Performance and maintainability risks sit in pipeline/search/report size |
| Agent / chat | `src/agent/*`, `api/v1/endpoints/agent.py`, `apps/dsa-web/src/pages/ChatPage.tsx` | Ask Stock chat, skills, multi-agent compatibility, conversation persistence | Good factory caching exists, but legacy naming/aliases remain |
| Web frontend | `apps/dsa-web/src/App.tsx`, `apps/dsa-web/src/pages/*.tsx` | Guest/user/admin product surfaces and operator UI | User/admin separation is good; Settings surface is overgrown |
| Desktop | `apps/dsa-desktop/main.js` | Electron shell over the web app | Not a primary optimization hotspot in this pass |
| Deployment / CI | `docker/Dockerfile`, `docker/docker-compose.yml`, `.github/workflows/*.yml`, `docs/DEPLOY.md` | Container build, compose deployment, CI gates, release workflows | Readiness semantics and runbook drift matter before deployment |

### Boundaries That Are Good And Should Be Preserved

- Keep scanner and backtest as separate product capabilities. The current code and prior product direction already treat them differently, and that separation remains correct.
- Keep deterministic scanner ranking primary, with AI interpretation only additive. The current scanner service already follows that philosophy and should not be turned into AI-first reranking during optimization.
- Keep user-owned workflows separate from admin/operator workflows. The frontend routes in `apps/dsa-web/src/App.tsx` and owner-aware backend flows are the right shape.
- Keep the broad storage boundary: PostgreSQL for business/auth/session/control-plane data, Parquet/local files for bulk historical OHLCV. That direction remains sound.
- Keep repository seams where they already exist. `src/repositories/scanner_repo.py`, `src/repositories/backtest_repo.py`, `src/repositories/rule_backtest_repo.py`, and `src/repositories/portfolio_repo.py` are useful consolidation points, even if some are large.
- Keep `src/agent/factory.py` as the central construction point for agent execution. It already removes repeated setup and caches expensive tool/skill initialization.

## Architecture And Code-Structure Findings

### A1. `DatabaseManager` Is Still The Largest Complexity Sink

Primary evidence:

- `src/storage.py` is 4645 lines and owns SQLite ORM models, session helpers, app-user/session reads, analysis/chat/scanner/backtest/portfolio persistence, and Phase A-G coexistence wiring.
- It instantiates all PostgreSQL phase stores in one place and gates behavior with `_phase_a_enabled` through `_phase_g_enabled`.
- It also owns domain-specific shadow sync methods such as `sync_phase_e_analysis_backtest_shadow`, `sync_phase_e_rule_backtest_shadow`, `sync_phase_f_portfolio_account_shadow_from_session`, and `sync_phase_g_runtime_config_shadow`.

Why it matters:

- Any change touching auth, chat, scanner, backtest, portfolio, or admin config still risks incidental storage coupling.
- The coexistence logic is no longer just an adapter layer; it materially shapes runtime code paths.
- It slows later simplification because ownership is unclear: many domain rules still “live” in storage instead of staying in repositories or services.

Recommendation:

- Do not do a broad storage rewrite before deployment.
- After deployment stability is proven, shrink `src/storage.py` by moving domain-facing reads/writes behind repositories and demoting Phase A-G shadow calls into narrower adapters.
- Preserve compatibility reads for now where they protect auth/session/history continuity.

Timing: later cleanup, with selective post-deploy boundary tightening.

### A2. Repository Boundaries Exist, But Usage Is Inconsistent

Primary evidence:

- Good repository seams exist in `src/repositories/scanner_repo.py`, `src/repositories/backtest_repo.py`, `src/repositories/rule_backtest_repo.py`, and `src/repositories/portfolio_repo.py`.
- However, direct `DatabaseManager` usage still appears in endpoint and service layers such as `api/v1/endpoints/auth.py`, `api/v1/endpoints/analysis.py`, `src/services/history_service.py`, `src/services/backtest_service.py`, and `src/services/market_scanner_service.py`.

Why it matters:

- The codebase now has two competing patterns: repository-driven domains and direct database reach-through.
- This makes later cleanup slower because behavior is split across services, endpoints, and storage internals.

Recommendation:

- Preserve repositories as the preferred seam.
- Post-deployment, reduce direct DB access first in the highest-churn surfaces: auth, analysis, scanner, and history.
- Avoid a blanket repository rewrite. Move only the most repeated or most fragile paths first.

Timing: high-value optimization soon after deployment.

### A3. Several Runtime Files Are Too Large To Change Safely

Largest hotspots identified in this audit:

- `src/services/market_scanner_service.py` — 5070 lines
- `src/storage.py` — 4645 lines
- `src/core/pipeline.py` — 4437 lines
- `src/services/report_renderer.py` — 4134 lines
- `src/services/rule_backtest_service.py` — 3768 lines
- `src/search_service.py` — 3066 lines
- `data_provider/base.py` — 3158 lines
- `apps/dsa-web/src/pages/SettingsPage.tsx` — 4592 lines
- `api/v1/endpoints/auth.py` — 1000 lines
- `api/v1/endpoints/analysis.py` — 949 lines
- `api/v1/endpoints/portfolio.py` — 870 lines

Why it matters:

- These files mix orchestration, transformation, validation, persistence wiring, and response shaping in one edit surface.
- They are not all “wrong,” but they are high-friction and high-regression-risk.

Recommendation:

- Do not split all large files just because they are large.
- Prioritize only the ones where size is aligned with duplicated logic or operational risk:
  - `src/services/market_scanner_service.py`
  - `src/services/portfolio_service.py`
  - `apps/dsa-web/src/pages/SettingsPage.tsx`
  - `api/v1/endpoints/auth.py`
  - `api/v1/endpoints/analysis.py`
- Leave `src/core/rule_backtest_engine.py` largely intact unless a concrete pain point appears; its size is less concerning because it holds domain logic more coherently than some service files.

Timing: selective post-deploy simplification.

### A4. There Are Two Async Task Execution Stacks

Primary evidence:

- Web/API analysis uses `src/services/task_queue.py`, which manages `_tasks`, `_analyzing_stocks`, `_futures`, `_subscribers`, and SSE state.
- Bot analysis still uses `src/services/task_service.py`, invoked from `bot/commands/analyze.py`.

Why it matters:

- This is functional duplication, not just naming drift.
- The web path and bot path now have different queueing and observability behaviors.
- Future fixes to dedupe, cancellation, lifecycle, or retry can easily land in one path but not the other.

Recommendation:

- Do not merge both systems before deployment unless a concrete production issue forces it.
- After deployment, decide whether bot analysis should share the main task queue semantics or stay intentionally isolated. Right now the split looks historical rather than principled.

Timing: post-deploy simplification, medium priority.

### A5. One Health Endpoint Is Dead And One Is Live

Primary evidence:

- `api/app.py` serves `/api/health`.
- `api/v1/endpoints/health.py` defines `/api/v1/health`.
- `api/v1/router.py` does not include `health.router`, and `rg` found no live references to `/api/v1/health`.

Why it matters:

- This is low-risk dead code and a small signal of operational surface drift.

Recommendation:

- Remove or fold `api/v1/endpoints/health.py` once the single health/readiness contract is decided.

Timing: small cleanup, can happen any time, but bundle with readiness work rather than as a standalone micro-change.

## File And Module Deletion Or Archive Candidates

These are candidates, not automatic deletions. Each should be removed only after its compatibility consumers are explicitly handled.

| Candidate | Evidence | Recommendation | Timing / risk |
| --- | --- | --- | --- |
| `api/v1/endpoints/health.py` | Not included in `api/v1/router.py`; no repo references to `/api/v1/health` | Delete or merge into the single real health/readiness surface | Low risk, pre- or post-deploy |
| `webui.py` | Compatibility wrapper only; docs and changelog already mark `--webui` / `--webui-only` as deprecated | Keep for one deprecation cycle, stop using it in new docs, then remove | Medium risk because docs and external habits may still rely on it |
| `main.py` `--webui` / `--webui-only` aliases | Still supported in code and docs, despite deprecation | Hide from current deployment docs first, then remove later | Medium risk |
| `analyzer_service.py` | Repo search found references only from root `SKILL.md` | Archive or move to docs/examples if no external importers depend on it | Medium risk because external/local workflows may import it |
| `src/agent/strategies/*` compatibility wrappers | Files are explicitly labeled compatibility wrappers for legacy strategy namespace | Remove after clients fully standardize on skills terminology and import paths | Medium risk |
| Root backtest smoke convention (`test_backtest_run.py` plus ignored `test_backtest_basic.py` and `test_backtest_rule.py`) | `test_backtest_run.py` is tracked but imports two root scripts that are ignored by `.gitignore`; committed equivalents already exist under `scripts/` | Standardize on `scripts/smoke_backtest_standard.py` and `scripts/smoke_backtest_rule.py`, then retire the root wrapper convention | High repo-readiness value, low runtime risk |
| `sources/` design assets | Tracked 63 MB directory with PSD/AI/icon assets and screenshots, not runtime-critical | Archive to a design-assets location or Git LFS if long-term retention matters | Low runtime risk, low urgency |

### Deletion Candidates That Should Not Be Removed Yet

- `src/postgres_phase_a.py` ... `src/postgres_phase_g.py`: too early to delete while coexistence parity is still the safety net.
- `patch/eastmoney_patch.py`: still actively imported by fetchers.
- `ScannerPage` / `UserScannerPage`: behavior overlap exists, but the admin vs user scanner split is valuable and should be preserved.

## Feature-Surface Audit

### F1. The Admin Settings Surface Is Too Dense For Its Current Value

Primary evidence:

- `apps/dsa-web/src/pages/SettingsPage.tsx` is 4592 lines.
- It mixes AI routing, direct provider setup, runtime control, readiness hints, admin navigation, runtime cache reset, and destructive factory reset in one screen.
- The backend counterpart `src/services/system_config_service.py` is also broad and still `.env`-centric with Phase G shadow sync layered on top.

Recommendation:

- Do not redesign the whole settings experience before deployment.
- Preserve the user/admin split already present in `apps/dsa-web/src/App.tsx`.
- After deployment, hide rare and destructive actions under explicit “advanced” or “maintenance” affordances, and consider splitting system config from maintenance actions.

Priority: high-value optimization soon after deployment.

### F2. Scanner Surface Split Is Correct, But Shared Rendering Could Be Consolidated Later

Primary evidence:

- `apps/dsa-web/src/pages/ScannerSurfacePage.tsx` routes guest, user, and admin modes to `GuestScannerPage`, `UserScannerPage`, and `ScannerPage`.
- This is a correct product boundary, but admin and user scanner pages both carry shortlist/history/detail interaction complexity.

Recommendation:

- Preserve the three-surface split.
- If UI simplification is desired later, extract shared shortlist/detail components instead of merging admin and user workflows.

Priority: later cleanup, not pre-deploy.

### F3. Legacy “Strategy” Naming Still Leaks Into The Agent Surface

Primary evidence:

- `api/v1/endpoints/agent.py` exposes `/skills` but also retains hidden `/strategies` compatibility behavior.
- `src/agent/strategies/*` exists only as compatibility wrappers.
- `src/services/system_config_service.py` still carries display aliases between skill and strategy vocabulary.

Recommendation:

- Standardize on “skills” in product surfaces and operator terminology.
- Keep hidden aliases for one deprecation window, then remove them with the wrapper modules.

Priority: later cleanup.

### F4. Serve / WebUI Entry Surface Is More Complex Than Necessary

Primary evidence:

- Runtime entry options currently include `--serve`, `--serve-only`, `--webui`, `--webui-only`, plus `webui.py`.
- `docs/DEPLOY.md` still tells operators to use deprecated `--webui` forms for direct deployment.

Recommendation:

- Before deployment, update the runbook to prefer one server invocation path.
- Do not remove compatibility aliases until the documentation and operator habit have shifted.

Priority: must clarify before deployment, removal can wait.

### F5. Features That Should Not Be Removed Right Now

- Scanner should remain a first-class product surface.
- Backtest should remain separate from scanner.
- Portfolio should remain owner-scoped and separate from admin/system settings.
- Ask Stock chat should remain available as its own flow; the issue is vocabulary drift and maintainability, not feature value.

## Performance Bottlenecks

These findings are classified by the dominant bottleneck type, but several are mixed CPU + I/O + duplicate-work problems.

| Area | Primary evidence | Likely bottleneck type | Why it matters | Priority |
| --- | --- | --- | --- | --- |
| Scanner run execution | `src/services/market_scanner_service.py` duplicates CN/US/HK run flows, repeatedly converts DataFrames to records, evaluates candidates in per-market loops, and rebuilds similar diagnostics/response payloads | Mixed CPU, I/O, algorithmic, duplicate-work | Most obvious whole-project speedup and simplification target | High, after deployment |
| Portfolio snapshot reads | `src/services/portfolio_service.py:get_portfolio_snapshot()` replays account state and then persists fresh snapshot rows; `_build_positions()` calls `repo.get_latest_close()` per symbol | Mixed CPU, DB-bound, duplicate-write, N+1 query | Expensive read path can degrade normal portfolio usage and database write load | High, after deployment |
| Search / news fetch | `src/search_service.py` uses sync `requests`, retry wrappers, sleeps, and article fetching/parsing; cache is in-memory per process | Network-bound and duplicate-work | Affects analysis latency and long-running API efficiency | Medium-high |
| Provider / universe loading | `data_provider/base.py` still relies on full stock list loads, `iterrows()`, retry/sleep loops, and runtime normalization | Network-bound + CPU-bound | Impacts scanner and data lookup hot paths, especially at market-universe scale | High |
| Analysis concurrency shaping | `src/core/pipeline.py` sleeps after collecting completed futures rather than before dispatch; comment in file already notes peak smoothing is limited | Network-bound / algorithmic control issue | Gives a false sense of request pacing while leaving actual bursts governed by `max_workers` | Medium |
| Backtest sample preparation | `src/services/backtest_service.py` loops candidate-by-candidate and may refill missing history per analysis | Mixed DB / I/O / duplicate-work | Not the top deployment blocker, but a likely medium-term speed target for larger evaluation runs | Medium |
| Control-plane config reload | `src/services/system_config_service.py` validates large config maps and reloads runtime singletons on admin changes | CPU-bound but infrequent | More of a maintainability/control-plane issue than a hot performance path | Low |

### Highest-ROI Speedup Opportunities

1. Optimize the portfolio snapshot path so reads stop replaying and writing whole-account state every time.
2. Consolidate the scanner into one shared market-independent pipeline with market-specific scoring hooks.
3. Reduce repeated stock-list and quote-history loading in the provider/scanner flow.
4. Bound repeated news/article fetch work with stronger cache and dedupe behavior.
5. Make rate limiting explicit in pipeline dispatch instead of relying on a post-completion sleep.

## Algorithm And Data-Flow Improvement Opportunities

### G1. Scanner Ranking Logic Is Deterministic, But Hard-Coded And Duplicated

Primary evidence:

- `src/services/market_scanner_service.py` contains separate `_compute_pre_rank`, `_compute_us_pre_rank`, and `_compute_hk_pre_rank` families plus market-specific scoring/finalization paths.
- Weighting is hand-tuned and embedded in code.
- The service already persists run histories and review outputs such as `quality_summary` and `comparison_to_previous`.

Opportunity:

- Keep deterministic ranking primary.
- After deployment, use persisted review outcomes to calibrate weights offline rather than continuing to drift by intuition alone.
- Share the non-market-specific stages: universe preparation, detail candidate evaluation, diagnostics assembly, shortlist response assembly.

Value:

- Better maintainability and a path to measurable ranking improvement without converting the scanner into an opaque AI system.

### G2. Scanner And Provider Flows Recompute Too Much

Primary evidence:

- Repeated market-universe fetching, repeated DataFrame row iteration, repeated detailed candidate history assembly, and repeated response/diagnostic building exist across scanner and provider layers.

Opportunity:

- Cache universe snapshots and benchmark-relative inputs per run.
- Precompute or persist small derived indicator bundles for the shortlist seed stage.
- Avoid repeated `to_dict("records")` and repeated per-symbol transformations when a vectorized or batched step would suffice.

Value:

- Large speedup potential in the scanner without changing product behavior.

### G3. Portfolio Should Move Toward Incremental Recomputation

Primary evidence:

- `get_portfolio_snapshot()` replays all events up to `as_of`.
- `_build_positions()` performs per-symbol latest price lookup.
- Snapshot persistence happens as part of the read path.

Opportunity:

- Treat snapshot materialization as event-driven or explicitly refresh-driven instead of mandatory on every read.
- Store reusable projection checkpoints.
- Batch latest-price lookup for the current symbol set.

Value:

- Immediate latency and write-load reduction with clearer semantics.

### G4. Search And News Should Dedupe By Symbol/Window/URL

Primary evidence:

- `src/search_service.py` already has bounded in-memory caches, but they are process-local and request-oriented.
- The service still uses repeated GET/POST flows, sleeps, and content parsing.

Opportunity:

- Reuse normalized search results by stock, query intent, and time window.
- Deduplicate article fetch/parsing by URL.
- Bound fetch fan-out and stop parsing low-value duplicates after the first usable sources arrive.

Value:

- Better latency, lower cost, and fewer transient failures during repeated analysis runs.

### G5. Backtest And Scanner Provenance Is Still Weaker Than It Should Be

Primary evidence:

- Prior baseline work already identified dataset-version / manifest provenance as a gap.
- This matters for scanner outcome review, backtest reproducibility, and server-side operational trust.

Opportunity:

- Add stronger provenance metadata after deployment rather than redesigning domain schemas now.

Value:

- Better confidence in results and easier production debugging.

## Deployment-Readiness Findings

### Must Fix Or Explicitly Resolve Before Deployment

| Finding | Evidence | Why it matters | Recommendation |
| --- | --- | --- | --- |
| Process-local task queue and SSE state | `src/services/task_queue.py` stores task/subscriber/future state in memory and `api/v1/endpoints/analysis.py` streams from that local queue | Multi-worker deployment, non-sticky routing, or future horizontal scale will break task visibility and SSE consistency | Either explicitly deploy as single-process/sticky-routing only and document it, or move task state off-process |
| Health/readiness semantics are too shallow | `api/app.py` returns static `ok`; no DB/config/queue/readiness checks | Health checks can say “ok” while the app is not truly ready | Split liveness and readiness; keep liveness cheap, add readiness checks for core dependencies |
| Docker healthcheck can hide real failures | `docker/Dockerfile` falls back to `python -c "import sys; sys.exit(0)"` after HTTP checks | Containers can remain “healthy” even when the server is failing | Remove the always-success fallback and align healthcheck with the real readiness contract |
| Runtime source-of-truth is still operationally ambiguous | `.env` remains live config source in `src/config.py` and `src/services/system_config_service.py`, while Phase G mirrors config/admin actions into PostgreSQL | Operators can misinterpret PG shadow data as authoritative runtime config | Before deployment, document the real source-of-truth and how config mutations propagate |
| Graceful shutdown for background executors is not fully wired | `AnalysisTaskQueue.shutdown()` exists, but app lifespan in `api/app.py` only manages `SystemConfigService` | Long-running deploys can leave task executors and subscribers unmanaged during shutdown/restart | Wire cleanup behavior into app/server lifecycle or explicitly document process model and restart expectations |
| Deployment and smoke runbook drift | `docs/DEPLOY.md` still leans on deprecated `--webui` paths; `test_backtest_run.py` depends on ignored root files | Clean server bring-up and handoff are harder than necessary | Clean the runbook before deployment, even if deeper cleanup waits |

### High-Value Operational Hardening Soon After Deployment

| Finding | Evidence | Recommendation |
| --- | --- | --- |
| Observability is still uneven across subsystems | Scanner has useful run-level diagnostics, but readiness/queue/backfill visibility is still shallow | Extend operational visibility at run/job level without inventing fake telemetry |
| One health endpoint is dead and one is live | `api/v1/endpoints/health.py` exists but is not mounted | Remove ambiguity after readiness work lands |
| CI validates code quality but not real deployment topology | `.github/workflows/ci.yml` covers backend gate, Docker build/import, and frontend build, but not queue topology/readiness semantics | Add deployment-focused checks later if server deployment becomes a long-lived supported path |

## A-G Coexistence Cleanup Audit

The coexistence slice is complete enough to operate, but the cleanup order should be conservative. The right question is not “what can be deleted immediately?” but “what compatibility surfaces are still earning their keep?”

| Phase | Current role | Keep for now? | Cleanup guidance |
| --- | --- | --- | --- |
| Phase A (`src/postgres_phase_a.py`) | Identity, sessions, notification preferences | Yes | Keep through at least one deployment stability window. Auth/bootstrap/session continuity is too sensitive to collapse early. |
| Phase B (`src/postgres_phase_b.py`) | Analysis and chat shadow persistence | Yes | Keep while history/chat compatibility still matters and while `DatabaseManager` owns analysis/chat persistence. |
| Phase C (`src/postgres_phase_c.py`) | Market metadata and usage/provenance references | Partly | Likely to survive longer in some form because provenance remains a real gap. Collapse only after a permanent manifest/provenance design is settled. |
| Phase D (`src/postgres_phase_d.py`) | Scanner run and candidate shadow persistence | Short-term yes | Good candidate for earlier cleanup once scanner history/admin reads are trusted from the chosen canonical store and no shadow-only protections remain. |
| Phase E (`src/postgres_phase_e.py`) | Backtest shadow persistence | Short-term yes | Remove only after historical evaluation, rule backtest results, and export/report flows are proven against the canonical path. |
| Phase F (`src/postgres_phase_f.py`) | Portfolio/account shadow persistence | Yes, likely longer | Portfolio ownership and broker-sync semantics are more sensitive than scanner; keep until real server use proves parity. |
| Phase G (`src/postgres_phase_g.py`) | Runtime config, admin logs, system actions shadow/control-plane persistence | Yes | Keep while `.env` remains runtime authority. Collapse only after the control-plane authority is intentionally simplified. |

### Compatibility Read Surfaces That Should Likely Remain For Now

- `.env`-driven runtime config in `src/config.py`
- Auth/bootstrap/session compatibility reads in `src/auth.py`, `api/deps.py`, and `src/storage.py`
- Guest session cookie boundary (`wolfystock_guest_session`) behavior
- Analysis/chat/history compatibility reads through `DatabaseManager`

### Leftovers That Are Future Cleanup Candidates

- Phase-gated `_phase_*_enabled` branching inside `src/storage.py`
- Domain-specific shadow sync helpers inside `DatabaseManager`
- Mixed control-plane semantics where admin actions are mirrored to PostgreSQL but runtime still reads `.env`

## Top Optimization Opportunities Ranked By Impact / Effort / Risk

| Rank | Opportunity | Impact | Effort | Risk | Timing |
| --- | --- | --- | --- | --- | --- |
| 1 | Resolve task queue deployment topology and SSE semantics | Very high | Medium | Medium-high | Before deployment |
| 2 | Replace shallow/fake health with real liveness/readiness and fix Docker healthcheck | High | Small | Low | Before deployment |
| 3 | Clarify runtime source-of-truth and deployment runbook | High | Small | Low | Before deployment |
| 4 | Fix the clean-checkout smoke path by standardizing on committed scripts/docs | Medium | Small | Low | Before deployment |
| 5 | Optimize portfolio snapshot reads and batch latest-price lookup | High | Medium | Medium | Soon after deployment |
| 6 | Consolidate scanner shared flow and reduce repeated per-market work | High | Medium | Medium | Soon after deployment |
| 7 | Reduce direct `DatabaseManager` reach-through outside repositories | Medium-high | Medium | Medium | Soon after deployment |
| 8 | Simplify admin settings/control-plane surface | Medium | Medium | Low | Soon after deployment |
| 9 | Collapse coexistence shadow logic by phase after parity window | Medium-high | Large | High | Later |
| 10 | Remove deprecated aliases/wrappers and archive non-runtime assets | Medium | Small | Low | Later |

## Recommended Roadmap

### Before Deployment

1. Decide and document the allowed server topology.
   - If the task queue remains in-memory, deploy the API as a single-process service and document that constraint explicitly.
2. Establish a real health contract.
   - Keep liveness cheap.
   - Add readiness for the dependencies that actually matter in this deployment mode.
   - Remove the Docker healthcheck success fallback.
3. Clarify the control-plane source-of-truth.
   - Make it explicit that `.env` is still the active runtime authority if that remains true.
   - Explain what Phase G shadows are for and what they are not for.
4. Wire or document graceful shutdown behavior for background task execution.
5. Clean the operational runbook.
   - Prefer current `--serve` / `--serve-only` terminology in deployment docs.
   - Stop depending on ignored root smoke scripts in documentation or validation instructions.

### Shortly After Deployment

1. Simplify the scanner by extracting one shared execution skeleton with market-specific ranking/finalization hooks.
2. Optimize portfolio snapshot generation so reads stop doing full replay plus writeback.
3. Reduce direct `DatabaseManager` access in auth, analysis, scanner, and history paths.
4. Split or hide the highest-friction settings/admin controls, especially destructive maintenance actions.
5. Strengthen caching and dedupe in search/provider flows where repeated analysis causes duplicate network work.
6. Revisit pipeline pacing so outbound request bursts are governed intentionally.

### Later / Optional

1. Collapse Phase A-G coexistence scaffolding domain by domain after a measured parity window.
2. Remove deprecated serve aliases and `webui.py` once operators have moved to the canonical server path.
3. Remove agent “strategy” compatibility wrappers after the skills vocabulary is fully standardized.
4. Archive `sources/` design assets out of the main runtime repo if they continue to grow.
5. Consider deeper file decomposition for the biggest service/page files only after the higher-ROI operational fixes land.

## What Not To Do In The Next Pass

- Do not launch a repo-wide refactor of `src/storage.py` before deployment.
- Do not merge scanner and backtest into one product surface.
- Do not convert deterministic scanner scoring into an AI-first ranking system.
- Do not migrate all runtime config into PostgreSQL in the same pass as deployment hardening.
- Do not split every large file just because it is large.

## Recommended Next Execution Prompt

Use a bounded follow-up prompt such as:

> Implement only the pre-deployment hardening items from `docs/architecture/system-optimization-audit.md`: task queue deployment stance, real liveness/readiness checks, Docker healthcheck cleanup, graceful shutdown wiring for background task execution, and deployment/smoke runbook cleanup. Do not do the scanner or portfolio optimization work yet. Update the relevant docs and verify the exact commands you changed.
