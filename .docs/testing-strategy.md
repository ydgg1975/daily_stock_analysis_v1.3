# Testing Strategy

Status: Phase 0 locked validation strategy for the crypto scanner lane built on top of the current repo.

## Goal

Keep the scanner deterministic, mostly offline-testable, and non-regressive against the stock lane.

## Phase 1 Minimum Test Expectations

- [LOCKED] Backend offline coverage includes normalization, deduplication, cursor, staleness, and fallback behavior.
- [LOCKED] Web coverage includes scanner rendering, filter reloads, degraded states, visibility refresh, and detail drawer gaps.
- [LOCKED] The stock lane must still pass its existing touched validation paths.
- [LOCKED] Default verification remains `python3 -m pytest -m "not network"` plus `cd apps/dsa-web && npm ci && npm run lint && npm run build && npm run test`.

## Local Repo Pattern References

- backend test discovery config: `setup.cfg:19`
- backend storage/reset patterns: local repo tests under `tests/test_*.py`
- web state/store pattern: `apps/dsa-web/src/stores/stockPoolStore.ts:25`
- web testing stack already validated through `npm run test`

## Principles

1. Offline tests are the default.
2. External provider payloads are fixture-driven.
3. Time-sensitive logic uses injected/frozen time.
4. Crypto tests must not break stock tests.
5. Live-provider checks are separate from normal CI.

## Test Pyramid

### Unit Tests

Targets:

- launch normalization
- deduplication rules
- filter evaluation
- cursor encoding/decoding
- staleness calculations
- partial-data flag derivation

Examples:

- `tests/test_crypto_launch_normalization.py`
- `tests/test_crypto_cursor.py`
- `tests/test_crypto_filtering.py`

### Integration Tests

Targets:

- fetcher -> service -> repository flow using fixtures
- API endpoint -> service -> repository flow using temp DB
- config persistence for scanner feature flags and scheduler defaults

Examples:

- `tests/test_crypto_launch_service.py`
- `tests/test_crypto_api.py`
- `tests/test_crypto_config.py`

### UI Tests

Targets:

- scanner page rendering
- filter changes
- detail drawer behavior
- auto-refresh behavior
- degraded/partial-data UI states

Examples:

- `apps/dsa-web/src/pages/__tests__/CryptoScannerPage.test.tsx`
- `apps/dsa-web/src/stores/__tests__/cryptoLaunchStore.test.ts`

### Contract Tests

Targets:

- provider payload compatibility against saved fixtures
- optional internal API contract checks if multiple consumers appear

### Live / Manual Smoke

Targets:

- controlled live check of discovery source
- controlled live check of DexScreener enrichment

These must not run by default in local deterministic validation.

## Fixture Strategy

Use committed JSON fixtures for providers.

Suggested layout:

```text
tests/fixtures/crypto/
  geckoterminal/
    new_pools_bsc_page1.json
    new_pools_solana_page1.json
    new_pools_base_page1.json
    new_pools_partial_failure.json
  dexscreener/
    token_batch_success.json
    token_batch_partial.json
    token_batch_empty.json
  security/
    goplus_success.json
    rugcheck_success.json
    provider_timeout.json
```

Rules:

- fixtures are versioned in git
- each fixture is tied to a named scenario, not just a raw file path
- malformed, partial, and empty payloads are first-class test cases

## Deterministic Time

All logic that depends on `now` must accept an injected clock or frozen time.

This applies to:

- `age_minutes`
- `staleness_s`
- cursor generation
- backfill-gap detection
- refresh eligibility

Do not let tests rely on raw `datetime.now()` or browser wall-clock time.

## Backend Test Rules

### Isolation

- use temp DBs
- reset config/database singletons in setup/teardown
- mock external clients at the provider adapter boundary

### No-Network Default

The backend deterministic suite should remain runnable via:

```bash
python3 -m pytest -m "not network"
```

Network tests, if added, should be explicitly marked.

### Minimum Scenarios

- new launch inserted
- same pair rediscovered and upserted
- partial enrichment failure still renders a row
- one chain fails while other chains continue
- cursor remains stable across inserts

## UI Test Rules

### Required Scenarios

- empty scanner state
- normal feed state
- partial-data/degraded state
- filter update triggers store reload
- refresh on visibility regain
- detail drawer with missing enrichment fields

### Verification Command

```bash
cd apps/dsa-web && npm ci && npm run lint && npm run build && npm run test
```

## Manual Verification Checklist

Before claiming a phase works:

- [ ] launch rows appear for all configured chains
- [ ] filters change the result set correctly
- [ ] detail drawer shows core metrics and DexScreener link
- [ ] partial-data state is visible, not silently hidden
- [ ] stock routes/pages still work

## Suggested Test File Map

```text
tests/
  test_crypto_launch_normalization.py
  test_crypto_launch_service.py
  test_crypto_launch_repo.py
  test_crypto_api.py
  test_crypto_config.py
  test_crypto_security_fallback.py

apps/dsa-web/src/pages/__tests__/
  CryptoScannerPage.test.tsx

apps/dsa-web/src/stores/__tests__/
  cryptoLaunchStore.test.ts
```

## CI Guidance

### Always Run

- backend offline tests
- web lint/build/test

### Optional Scheduled / Manual

- live-provider contract checks
- smoke tests against GeckoTerminal / DexScreener

## Non-Regression Rule

Every crypto PR must still prove that the stock lane is not broken.

Minimum expectation:

- crypto-specific tests pass
- existing web checks pass
- touched backend deterministic tests pass

## Recommended Commands

```bash
python3 -m pytest -m "not network"
cd apps/dsa-web && npm ci && npm run lint && npm run build && npm run test
```
