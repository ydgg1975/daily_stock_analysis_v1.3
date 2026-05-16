## Context

This change fixes four stability issues in PR #1297 that currently block merge:

1. **Dividend TTM overwriting**: `src/analyzer.py:_inject_financial_data_to_dashboard()` recalculates dividend TTM from raw events, overwriting properly normalized `ttm_dividend_yield_pct` already computed by the fundamental adapter. The fallback logic has no time window filter and lacks None-safety.

2. **Post-analysis network calls**: `stabilize_decision_with_structure()` now calls `_inject_financial_data_to_dashboard()`, which calls `_enrich_belong_boards_with_quote()` that creates a new `DataFetcherManager()` to fetch sector realtime quotes. This violates the fail-open contract for post-analysis paths.

3. **NaN rendering**: Reports render literal "NaN" strings when change_pct or price is missing, degrading user experience. The archived spec defines graceful degradation (show only sector names), but implementation shows NaN.

4. **Stale docs**: PR body shows 4 commits/21 files but actual is 8 commits/23 files. Active specs missing `sector-realtime-quote` capability and don't reflect change_pct/graceful degradation semantics.

## Goals / Non-Goals

**Goals:**
- Fix dividend TTM calculation to respect pre-computed adapter values and apply 365-day filter for fallback
- Move sector quote fetching back to pipeline data-fetch phase, keeping analyzer/report injection fully fail-open
- Replace NaN strings with graceful degradation (hide column, show name-only, or hyphen)
- Sync PR description and active specs with actual implementation

**Non-Goals:**
- No new capabilities or features
- No changes to API contracts or data schemas that affect external consumers
- No refactoring of fundamental adapter or data provider infrastructure beyond what's necessary

## Decisions

### D1: Dividend TTM Priority

**Decision**: `_inject_financial_data_to_dashboard()` will check for pre-existing `ttm_dividend_yield_pct` in dividend_metrics before any fallback calculation. Fallback only triggers when TTM fields are absent.

**Rationale**: The fundamental adapter already normalizes dividend data with proper TTM logic (date filtering, yield calculation). Overwriting with a naive event sum loses this work.

**Alternative considered**: Always use adapter values and remove event fallback entirely. Rejected because some data providers may not provide pre-computed TTM values.

### D2: Sector Quote Fetch Location

**Decision**: Move sector realtime quote enrichment from analyzer/report injection phase back to `src/core/pipeline.py`'s data-fetch phase. The analyzer phase will only consume already-enriched data.

**Rationale**: Post-analysis paths should be fail-open and network-free. Current design puts external calls in the stability guard, which is architecturally backwards.

**Alternative considered**: Keep quote fetch in analyzer but wrap with aggressive timeout/cache. Rejected because it still risks blocking report generation under load.

### D3: NaN Handling Strategy

**Decision**: Reports will use conditional rendering:
- Empty table cells → show sector name list only (no table)
- Missing change_pct → omit the column, show name + price only
- Missing price → omit the column, show name + change only
- All metrics missing → show simple name list

**Rationale**: Matches archived spec behavior. Avoids confusing users with "NaN" while preserving available information.

### D4: Spec Activation

**Decision**: Create active spec for `sector-realtime-quote` in `openspec/specs/` (not just archived), and update `email-report-details` with change_pct rendering and graceful degradation scenarios.

**Rationale**: Active specs should reflect current implementation state. The archived changes are still active in the codebase.

## Risks / Trade-offs

- [Risk] Fallback TTM calculation may produce different values than adapter → **Mitigation**: Only use fallback when adapter value is missing; test both paths
- [Risk] Pipeline phase change may affect timing/ordering → **Mitigation**: Verify in local test; pipeline already fetches belong_boards, this adds quote enrichment
- [Risk] Report rendering changes may affect existing integrations → **Mitigation**: Changes are purely cosmetic (NaN → empty); no API/schema changes
- [Risk] PR sync may miss some details → **Mitigation**: Manual verification against git diff and actual file list

## Migration Plan

1. Implement fixes in order: pipeline → analyzer → notification
2. Run `./scripts/ci_gate.sh` to verify no regressions
3. Update PR description with verification evidence
4. Push spec updates to active specs

**Rollback**: Each fix is independently reversible via git revert of specific commits. PR can be amended before merge.

## Open Questions

- None identified. All four issues have clear root causes and implementation paths.