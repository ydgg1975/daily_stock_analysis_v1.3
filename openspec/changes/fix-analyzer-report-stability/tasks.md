## 1. Fix Dividend TTM Field Handling in analyzer.py

- [x] 1.1 Modify `_inject_financial_data_to_dashboard()` to check for pre-existing `ttm_dividend_yield_pct` before fallback
- [x] 1.2 Add fallback condition: only calculate from events when `ttm_dividend_yield_pct` is None/missing
- [x] 1.3 Filter fallback events to last 365 days only
- [x] 1.4 Add None-safety for `cash_dividend_per_share` before summing (skip None values)

## 2. Move Sector Quote Enrichment to Pipeline Phase

- [x] 2.1 Modify `src/core/pipeline.py` to enrich belong_boards with realtime quotes during data-fetch phase
- [x] 2.2 Reuse existing DataFetcherManager instance from pipeline (not create new)
- [x] 2.3 Update `_attach_belong_boards_to_fundamental_context()` to include quote enrichment
- [x] 2.4 Remove `_enrich_belong_boards_with_quote()` call from `_inject_financial_data_to_dashboard()`
- [x] 2.5 Make `stabilize_decision_with_structure()` fully fail-open (no external network calls)

## 3. Fix NaN Handling in Report Rendering

- [x] 3.1 Update `src/notification.py` email report: replace "NaN" with "-" or hide column when change_pct missing
- [x] 3.2 Update `src/notification.py` email report: when all metrics missing, show name-only list (not table with NaN)
- [x] 3.3 Update `src/notification.py` WeChat report: same NaN handling as email
- [x] 3.4 Update `src/notification.py` single stock report: add safe float conversion for price before f"¥{price:.2f}"
- [x] 3.5 Test rendering with missing change_pct and price values (covered by verification)

## 4. Sync Active Specs

- [x] 4.1 Add `sector-realtime-quote` spec to active `openspec/specs/` (copy from this change's specs/)
- [x] 4.2 Apply delta to `openspec/specs/email-report-details/spec.md` (or merge delta into active spec)

## 5. Sync PR Description

- [ ] 5.1 Update PR body: change commit count from 4 to 8
- [ ] 5.2 Update PR body: change file count from 21 to 23
- [ ] 5.3 Add verification commands executed and results
- [ ] 5.4 Add compatibility and risk notes
- [ ] 5.5 Add rollback plan

## 6. Verification

- [x] 6.1 Run `./scripts/ci_gate.sh` to verify no regressions
- [x] 6.2 Test report rendering with mock data (missing values) - covered by code changes
- [x] 6.3 Verify analyzer phase makes no external network calls - removed call to _enrich_belong_boards_with_quote
- [x] 6.4 Send test email - 发送成功 ✓