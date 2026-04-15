# Market Scanner (A-share + US + Hong Kong Pre-open)

## Product Boundary

Market Scanner is a distinct WolfyStock product capability for answering one question before the market opens:

> What should I watch today before the open?

Its role is intentionally separate from the existing modules:

- `Scanner`: proactive discovery and daily watchlist generation
- `Analysis`: deeper single-name analysis
- `Ask Stock / Chat`: interactive follow-up and reasoning
- `Backtest`: historical validation for rules and strategies
- `Execution`: **not part of this phase**

Current entry points:

- Web page: `/scanner`
- API: `POST /api/v1/scanner/run`
- API: `GET /api/v1/scanner/runs`
- API: `GET /api/v1/scanner/runs/{id}`
- API: `GET /api/v1/scanner/watchlists/today`
- API: `GET /api/v1/scanner/watchlists/recent`
- API: `GET /api/v1/scanner/status`

## Scope In This Phase

The current production scope now includes three explicit market profiles:

- `cn_preopen_v1`: the original A-share pre-open scanner and the default
- `us_preopen_v1`: a new US pre-open scanner focused on practical watchlist generation
- `hk_preopen_v1`: a Hong Kong pre-open scanner focused on practical HK watchlist generation

Shared behavior remains intentionally stable:

- separate run panel and result flow
- shortlist-first UI instead of a raw backend table
- candidate detail drawer with reasons, feature signals, risks, and watch context
- recent scan history
- hand-off actions into:
  - deeper analysis
  - stock Q&A
  - backtest with prefilled symbol

A-share remains the default A-share-first experience, while the US and Hong Kong profiles are added as clearly separate scanner profiles without changing A-share ranking behavior.

## A-share Universe Definition

The scanner does not blindly scan every possible symbol. It constructs an explicit, bounded A-share universe first.

### Universe Construction

1. Resolve an available China stock list
2. Load an A-share full-market realtime snapshot
3. Intersect the two
4. Keep only common A-share code prefixes:
   - `000/001/002/003`
   - `300/301`
   - `600/601/603/605`
   - `688/689`
5. Remove obviously poor watchlist candidates
6. Keep only the most liquid and active subset for detailed scoring

### Universe Dependency And Fallback Order

After this runtime resilience fix, Scanner no longer treats `Tushare stock_basic` permission as a hard prerequisite.

The current A-share universe resolution order is:

1. local universe cache: `SCANNER_LOCAL_UNIVERSE_PATH` (default `./data/scanner_cn_universe_cache.csv`)
2. `TushareFetcher.get_stock_list()` when the token has `stock_basic` permission
3. local/internal fallbacks:
   - local database (`analysis_history / stock_daily`)
   - built-in `STOCK_NAME_MAP` A-share mapping
4. `AkshareFetcher.get_stock_list()` as the last online supplement

Once a usable universe is found, Scanner writes it back to the local cache so later manual and scheduled runs can reuse it.

### Current Filters

The current `cn_preopen_v1` profile excludes:

- Beijing Stock Exchange names
- `ST` / special-treatment names
- price below `3.0`
- `volume <= 0` or `price <= 0` suspended-like states
- turnover amount below `2e8`
- turnover rate below `0.8%`
- volume ratio below `0.6`

After filtering, the service keeps at most the top `300` candidates for detailed evaluation.

## Scoring And Ranking

The first version is fully deterministic and explainable. No black-box model is used.

### Two-stage Flow

#### Stage 1: Snapshot Pre-rank

The scanner first ranks the broad universe using full-market snapshot features:

- liquidity
- turnover
- volume ratio
- broader trend context
- range quality

This stage narrows the market down to a bounded candidate set.

#### Stage 2: Detailed Daily-history Scoring

For the remaining candidates, the scanner loads daily history with a local-first pattern and computes the final score.

Current score composition:

- `pre_rank`: 25
- `trend`: 20
- `momentum`: 15
- `breakout`: 12
- `liquidity`: 10
- `activity`: 8
- `volatility_quality`: 5
- `relative_strength`: 5
- `sector_bonus`: up to 5
- `penalties`: overheating / excessive volatility / degraded history cases

### Main Feature Groups

- `trend`: whether price is above MA20 / MA60 and whether MA20 is still rising
- `momentum`: 5-day and 20-day returns plus recent up-day count
- `breakout`: distance to the 20-day high and participation confirmation
- `liquidity`: 20-day average turnover and current amount quality
- `activity`: turnover rate, volume ratio, and volume expansion
- `relative_strength`: candidate-vs-candidate recent strength ranking
- `sector_bonus`: small context bonus when a candidate overlaps with strong sectors

## What Users See

Each shortlisted candidate includes:

- `symbol / name`
- `rank`
- `scanner score`
- `quality hint`
- `reason summary`
- `reasons`
- `key metrics`
- `feature signals`
- `risk notes`
- `watch context`
- `scan timestamp`
- run metadata

The output should be read as a pre-open watchlist, not as an execution engine.

## AI Interpretation Layer (Phase 1)

Without changing the existing A-share `cn_preopen_v1` rule-based ranking, Scanner now supports an **optional AI interpretation layer**.

Its role is intentionally secondary:

- explain why a deterministic shortlist candidate is interesting today
- translate scanner reasons into trader-friendly language
- summarize the main risk and what to watch before/after the open
- add a light post-close review note when realized review data is available

It does **not**:

- replace the original `rank / score`
- become the first-pass selector or primary ranking logic
- block Scanner when AI is unavailable
- generate auto-trading or execution instructions

### Current AI Output Surface

The current implementation only interprets the top N shortlisted candidates, with a default cap of `3`. Candidate detail now includes:

- `AI summary`
- `opportunity type`
- `AI risk interpretation`
- `AI watch plan`
- `AI review commentary` (only when review data is ready)

Deterministic fields such as `reason summary / reasons / risk notes / watch context` remain visible alongside the AI layer so users can compare both interpretations directly.

### Fallback And Diagnostics

AI is additive rather than mandatory:

- if `SCANNER_AI_ENABLED=false`, Scanner remains fully rule-based
- if the AI provider/model is unavailable, the UI shows an explicit fallback message instead of a vague failure
- `/scanner` runtime diagnostics show whether AI ran, how many candidates were covered, which model was used, and whether fallback occurred

### AI Configuration

- `SCANNER_AI_ENABLED`
- `SCANNER_AI_TOP_N`

The recommended default is still a small bounded top-N coverage to keep latency and cost predictable.

## Run Diagnostics And Admin Observability

`/scanner` now exposes a compact run-diagnostics block so the page is not just a final-result view:

- `input universe size`
- `eligible after universe fetch`
- `eligible after liquidity/profile filter`
- `eligible after data-availability filter`
- `ranked candidate count`
- `shortlisted count`
- `excluded by reason` with bounded categories such as `filtered_by_profile_constraints`, `missing_history`, and `missing_quote_or_snapshot`

These fields are meant to answer, directly from the product:

- how many symbols were actually scanned
- whether a small shortlist came from a small universe, filtering pressure, or missing data
- whether the user is looking at the final shortlist rather than the broader ranked pool

Each run also keeps bounded provider attribution:

- `configured primary provider`
- `quote / snapshot / history source used`
- `providers used`
- `fallback count`
- `provider failure count`
- `missing data symbol count`

This is intentionally a **run-level summary**, not a fake symbol-level provider trace. The surface only reports attribution the current Scanner pipeline actually records.

`/admin/logs` now records Scanner runs as a separate `scanner` subsystem so admins can inspect:

- scanner run id and market/profile
- shortlist count and coverage summary
- providers used
- whether fallback happened
- provider failure count / missing-data pressure

The goal is bounded explainability, not a full telemetry warehouse.

## Scanner Market-data Providers

This phase adds two practical market-data providers for Scanner without changing the existing per-stock analysis fallback model:

- `Twelve Data`: stays a single-key provider and is primarily used for Hong Kong scanner quote / daily-history enrichment
- `Alpaca`: uses a `key_id + secret_key` credential pair and is primarily used for US scanner realtime quote / snapshot-style enrichment / daily-history enrichment

The credential surface intentionally stays small:

- `TWELVE_DATA_API_KEY` or `TWELVE_DATA_API_KEYS`
- `ALPACA_API_KEY_ID` + `ALPACA_API_SECRET_KEY`
- `ALPACA_DATA_FEED` (default `iex`)

If these providers are not configured, Scanner still falls back to local-first data plus the existing free-source routes.

## US Scanner Profile

Without changing the original A-share `cn_preopen_v1` ranking path, Scanner now adds a separate `us_preopen_v1` profile.

Its role is still bounded:

- it is still a Scanner capability rather than a Backtest or execution module
- deterministic scoring remains the primary shortlist generator
- AI, when enabled, stays secondary and optional
- the first US version favors correctness and structure over full A-share feature parity

### US Universe And Data Assumptions

The first US profile uses a **local-first bounded universe**:

1. `LOCAL_US_PARQUET_DIR` when available
2. `US_STOCK_PARQUET_DIR` as a compatibility fallback
3. local `stock_daily` rows that already contain US ticker history
4. a bounded liquid seed supplement when the local universe is too thin

The scanner does not try to blind-scan the internet for a first-pass universe. It evaluates local history candidates plus a bounded liquid seed supplement when necessary.

The current filters remove:

- ultra-low-price names
- insufficient 20-day average dollar volume
- insufficient 20-day average share volume
- insufficient history length
- the benchmark ticker itself (currently `SPY`) from the candidate ranking set

### What The US Profile Optimizes For

`us_preopen_v1` currently emphasizes:

- liquidity
- recent trend and momentum continuation
- volatility / tradability
- benchmark-relative behavior versus `SPY`
- optional live-quote / gap context

If live quotes are unavailable, the scanner still returns a shortlist and explicitly marks the run as more history-driven in diagnostics and risk notes.

### US Provider Path And Diagnostics

The current US data path is:

1. local-first history / parquet / `stock_daily`
2. Alpaca first for realtime quote and daily-history enrichment when configured
3. YFinance fallback when Alpaca is unavailable or unconfigured

Runtime diagnostics now preserve:

- `coverage_strategy`
- `local_symbol_count`
- `seed_supplement_count`
- the live-quote provider attempt chain
- whether Alpaca was fully configured, accepted, skipped, or failed

This keeps thin-universe behavior explainable instead of making US shortlist quality look arbitrary.

## Hong Kong Scanner Profile

Scanner now also adds a dedicated `hk_preopen_v1` profile without merging HK logic into A-shares or US scoring.

Its boundary stays explicit:

- it is still a Scanner capability, not Backtest or execution
- deterministic scoring still generates the primary shortlist
- it reuses existing run persistence, today/recent watchlists, review/quality, schedule, notification, and diagnostics infrastructure
- it stays bounded, explainable, and local-first instead of trying to blind-scan the whole exchange

### Hong Kong Universe And Data Assumptions

The first `hk_preopen_v1` profile uses a separate HK bounded universe:

1. local HK history first where available
2. a bounded, explainable HK seed list when local coverage is thin
3. `HK02800` as the current benchmark
4. Twelve Data first for quote / daily-history enrichment, then existing free-source fallbacks

The first implementation intentionally prefers:

- a bounded universe
- local-first history
- explicit provider fallback
- readable pre-open shortlist output instead of an exchange-wide dump

### What The Hong Kong Profile Optimizes For

`hk_preopen_v1` currently emphasizes:

- liquidity
- recent trend / momentum continuation
- benchmark-relative behavior versus `HK02800`
- opening confirmation / gap risk
- optional realtime quote context

### UX And Market Context

The `/scanner` page now lets users switch explicitly between:

- `A-share`
- `US`
- `Hong Kong`

Market/profile context is preserved in:

- the active run badge set
- recent watchlist history items
- status / review / quality summaries
- exported scanner summaries

US and Hong Kong reasons, risks, and watch-plan text also use market-appropriate wording such as pre-open context, gap risk, opening confirmation, liquidity, and tradability instead of reusing A-share-specific phrasing.

## Risk Notes And Watch Context

The first version already reflects A-share market realities:

- limit-up / limit-down constraints
- short-term overheating risk
- liquidity/auction acceptance risk
- event-driven volatility risk
- degraded history-data warnings when relevant

Watch context is structured and lightweight, for example:

- watch for a break above the prior 20-day high
- require volume confirmation
- avoid the setup if the open is weak and key support fails
- confirm sector/theme strength continues

## P9: Operational Workflow Layer

Scanner now supports a practical pre-open daily workflow instead of only ad hoc runs:

- an independent pre-open schedule
- persistent daily watchlists
- a simple today/recent watchlist retrieval flow
- notification delivery through existing channels
- lightweight operator visibility for run and delivery status

### Current Operational Surfaces

- Web: `/scanner`
  - today watchlist is the default focus
  - recent watchlists are grouped by watchlist date
  - operational status shows schedule, last scheduled run, notification state, and latest failure
- CLI:
  - `python main.py --scanner`
  - `python main.py --scanner-schedule`
- API:
  - `POST /api/v1/scanner/run`
  - `GET /api/v1/scanner/watchlists/today`
  - `GET /api/v1/scanner/watchlists/recent`
  - `GET /api/v1/scanner/status`

### Scheduling And Config

Scanner uses its own config surface instead of overloading the regular analysis schedule:

- `SCANNER_PROFILE` (currently `cn_preopen_v1`, `us_preopen_v1`, or `hk_preopen_v1`)
- `SCANNER_SCHEDULE_ENABLED`
- `SCANNER_SCHEDULE_TIME`
- `SCANNER_SCHEDULE_RUN_IMMEDIATELY`
- `SCANNER_NOTIFICATION_ENABLED`
- `SCANNER_LOCAL_UNIVERSE_PATH`
- `LOCAL_US_PARQUET_DIR`
- `US_STOCK_PARQUET_DIR` (legacy compatibility name)
- `TWELVE_DATA_API_KEY` / `TWELVE_DATA_API_KEYS`
- `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET_KEY` / `ALPACA_DATA_FEED`
- `SCANNER_AI_ENABLED`
- `SCANNER_AI_TOP_N`

The intended first operational setup is a China pre-open run such as `08:40`. Regular analysis and Scanner schedules can coexist in one process while remaining separate product capabilities.

### Daily Watchlist Persistence

P9 intentionally avoids introducing a risky migration layer. It reuses the existing Scanner tables:

- `market_scanner_runs`
- `market_scanner_candidates`

Operational metadata is stored in the existing JSON fields and now includes:

- `watchlist_date`
- `trigger_mode` (`manual` / `scheduled`)
- `request_source`
- notification result
- failure reason

This keeps the first daily-watchlist implementation additive and easy to inspect.

### Notifications

The first delivery path reuses the existing `NotificationService` and does not depend on an active UI session.

When `SCANNER_NOTIFICATION_ENABLED=true` and a scheduled run finishes, the system:

1. builds a compact Markdown watchlist summary
2. saves a local report file for traceability
3. sends the summary through configured channels
4. records success/failure on the run metadata

The notification includes:

- rank
- symbol / name
- score
- concise reason
- primary risk note
- primary watch / trigger context

### Failure And No-candidate Behavior

P9 treats non-ideal outcomes as explicit states, not silent failures:

- `completed`: shortlist generated
- `empty`: the run succeeded but no candidate passed the threshold
- `failed`: the run failed and the reason is persisted
- `skipped`: schedule-layer outcome such as a non-trading-day skip

This makes “no shortlist today” visible and reviewable instead of looking like the scanner never ran.

## Local-first Transparency And Persistence

The scanner reuses the repo's existing local-first patterns:

- stock list first from the local universe cache, then provider/local fallbacks
- realtime snapshot through the existing market-data loaders with explicit multi-fetcher attempts
- daily history first from local `stock_daily`
- provider fetch only when local history is insufficient
- run metadata and shortlisted candidates persisted for later review

Current persisted metadata includes:

- scan timestamps
- market / profile
- universe name
- universe size, preselected size, evaluated size
- source summary
- scoring notes
- shortlist payload
- watchlist date / trigger mode / request source
- notification state
- failure reason when applicable

### A-share Snapshot Fallback And Degraded Mode

The current realtime snapshot resolution order is:

1. `AkshareFetcher`
   - first `ak.stock_zh_a_spot_em`
   - then `ak.stock_zh_a_spot` as the Sina fallback
2. `EfinanceFetcher`
3. if both fail, attempt `local_history_degraded`

`local_history_degraded` only activates when local `stock_daily` has enough recent history, and the run stays clearly labeled:

- `source_summary` shows `snapshot=local_history_degraded`
- `diagnostics.scanner_data.degraded_mode_used=true`
- universe notes warn that the result is better for pre-open reference than for high-confidence screening

If degraded mode also cannot be built, Scanner now returns a more precise failure path instead of a vague `no_supported_fetcher`.

### Visible Failure Reasons And Diagnostics

The run metadata, failed-run persistence, and the secondary diagnostics area on `/scanner` now preserve:

- universe source
- snapshot source
- fetcher attempt chain
- whether degraded mode was used

Common reason codes include:

- `tushare_permission_denied`
- `universe_source_unavailable`
- `akshare_snapshot_fetch_failed`
- `efinance_snapshot_fetch_failed`
- `no_realtime_snapshot_available`

Recommended diagnosis order:

1. check whether the universe came from `local_universe_cache / db_local_fallback / builtin_stock_mapping`
2. inspect whether snapshot attempts failed on AkShare, efinance, or both
3. if `local_history_degraded` was used, confirm local `stock_daily` is fresh enough and has enough bars
4. if the final reason is still `no_realtime_snapshot_available`, both full-market snapshot fetch and degraded mode were unavailable, so local history or the free realtime sources need attention

## Route A: Daily Review And Quality Workflow

After P9 made Scanner operational with schedules, persistent watchlists, and notifications, this phase turns it into a more complete daily product workflow:

- `today / recent watchlists` remain the default entry point, but the focus now includes “how is today changing versus recent days?”
- `/scanner` compares the current watchlist against the prior watchlist day
- shortlisted candidates now expose realized follow-through instead of stopping at the morning list
- the page includes a lightweight quality summary so users can tell whether Scanner is still producing useful names
- users can export a compact daily Markdown summary for review and sharing

### Today And Recent Watchlists

The page now treats “today” and “recent” as separate but connected review layers:

- today’s or the currently selected watchlist stays as the main view
- recent watchlists act as a lightweight review workflow instead of a plain archive
- each history item can now show:
  - notification state
  - top symbols
  - new / retained / dropped names versus the prior watchlist day
  - a compact review summary when local daily bars are available

This keeps today’s shortlist front and center while making recent runs easier to learn from.

### Cross-day Comparison

The comparison layer stays intentionally simple and explainable:

- `New`: symbols entering the shortlist today
- `Retained`: symbols that stayed on the shortlist
- `Dropped`: symbols that were on the prior watchlist but not today
- retained names also show rank movement so users can quickly see whether attention improved or faded

This is not intended to be a full attribution system. It is just enough to explain how the watchlist is changing day to day.

### Post-close Review And Outcome Tracking

The current version reuses local `stock_daily` data for deterministic, explainable follow-through tracking. No new persistence layer or black-box evaluation engine is introduced.

Default review behavior:

1. anchor on the last close known at scan time
2. review the next `3` trading days by default
3. compute for each shortlisted name:
   - `same_day_close_return_pct`
   - `next_day_return_pct`
   - `review_window_return_pct`
   - `max_favorable_move_pct`
   - `max_adverse_move_pct`
   - benchmark outperformance when local benchmark data is available (currently `000300`)

The UI then maps those numbers into simple product-facing labels such as:

- `Worked well`
- `Mixed`
- `Weak follow-through`
- `Thesis validated / Partially validated / Not validated`

This review layer is meant to answer “what happened after the shortlist?” rather than replace historical strategy validation.

### What The Quality Metrics Mean

The quality summary is intentionally lightweight and interpretable. It helps answer:

- what recent average shortlist return looks like
- how often shortlisted candidates followed through
- how often candidates beat the benchmark
- how many usable reviewed names each run tends to produce
- whether winning candidates still carry higher average scanner scores than weaker ones

The goal is to assess whether Scanner is still producing useful candidates, not to turn it into a full quant-evaluation platform.

### Boundary Versus Backtest

Route A keeps the Scanner vs Backtest boundary intact:

- `Scanner review`: recent realized follow-through for real watchlists
- `Backtest`: broader historical validation for rules or strategies

So the review layer helps users judge recent usefulness, but it is not the same as proving long-run strategy robustness.

### Export Summary

`/scanner` now supports exporting a compact daily Markdown summary that includes:

- watchlist date
- shortlisted candidates
- concise reason / risk / watch context
- cross-day watchlist change summary
- lightweight review summary for the selected run

This export is meant for manual review and sharing, not as a replacement for the full research/report pipeline.

## Known Limits

This phase intentionally does **not** build:

- automated execution or order placement
- ML / black-box ranking
- unbounded full-market scanning
- a merged Scanner + Backtest product
- tick-level or order-book-level execution attribution
- mandatory news / announcement integration
- a full strategy-programming engine
- a visual scheduling control center
- multi-tenant notification orchestration
- paper trading or auto-execution

There are also a few explicit review limitations in the current implementation:

- outcome tracking depends on local `stock_daily` completeness; stale data will show up as pending or partial review
- benchmark comparison only appears when the required local benchmark bars exist
- realized follow-through is currently based on daily close/high/low data, not auction detail, intraday path, or actual fillability

## Future Expansion Path

The project now ships `cn_preopen_v1`, `us_preopen_v1`, and `hk_preopen_v1`, but a few next steps are still explicit:

- expand the bounded US / HK universes without jumping straight to exchange-wide live scanning
- add fuller key rotation and provider-health diagnostics for Twelve Data
- add richer pre-open event / earnings / gap features for US and Hong Kong workflows
- continue improving diagnostics so provider fallback and thin-universe behavior stay transparent
- keep Scanner, Analysis, Backtest, and future Execution clearly separated
