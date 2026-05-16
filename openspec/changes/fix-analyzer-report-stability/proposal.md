## Why

The current PR #1297 for email report enhancements introduces stability issues that block merge:
1. Dividend TTM recalculation overwrites properly normalized fields from the fundamental adapter
2. Post-analysis "stabilize" path triggers new external network requests (sector quotes), breaking the fail-open contract
3. Reports render "NaN" for missing data instead of graceful degradation
4. Single stock report has potential TypeError when price is a string from data source
5. PR description and active specs are stale relative to actual changes

## What Changes

### Fix 1: Dividend TTM Field Handling
- Modify `_inject_financial_data_to_dashboard()` to prioritize pre-computed `ttm_*` fields from fundamental adapter
- Add fallback logic: only sum from events when `ttm_dividend_yield_pct` is missing
- Filter fallback sum to last 365 days only
- Add None-safety for `cash_dividend_per_share` before summing

### Fix 2: Remove External Requests from Post-Analysis Path
- Move sector quote enrichment to pipeline data-fetching phase
- Reuse existing DataFetcherManager instance with its timeout/cache/fallback
- Make `stabilize_decision_with_structure()` fully fail-open (no network calls)

### Fix 3: Graceful NaN Handling in Reports
- Replace "NaN" strings with empty/hyphen when change_pct or price is missing
- For boards without metrics: show only name list, not table with NaN cells
- For partial metrics: show only available columns
- Add safe float conversion for price before formatting in single stock reports

### Fix 4: PR Description Sync
- Update PR body with actual commit count (8) and file count (23)
- Add verification commands, results, compatibility notes, rollback plan

### Fix 5: Active Specs Sync
- Add `sector-realtime-quote` capability to active specs
- Update `email-report-details` spec with change_pct and graceful degradation semantics

## Capabilities

### New Capabilities
- `sector-realtime-quote`: Real-time sector/sboard quote fetching with fallback (moved from archived to active)

### Modified Capabilities
- `email-report-details`: Add change_pct rendering and graceful degradation when data missing

## Impact

**Code Changes:**
- `src/analyzer.py`: `_inject_financial_data_to_dashboard()`, `_enrich_belong_boards_with_quote()`, `stabilize_decision_with_structure()`
- `src/notification.py`: Report rendering for belong_boards, single stock price formatting
- `src/core/pipeline.py`: Add sector quote fetching during data-fetch phase
- `openspec/specs/`: Add sector-realtime-quote spec, update email-report-details spec

**Breaking Changes:**
- None expected - all changes are internal fixes

**Risk:**
- Low: All changes are defensive/cleanup; testing covered by existing test suite