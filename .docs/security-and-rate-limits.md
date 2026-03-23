# Security And Rate Limits

Status: Phase 0 locked operational source strategy for a production-grade crypto scanner.

## Goal

Document how the scanner should interact with external providers safely at a 60-second cadence.

## Phase 1 Operating Envelope

- [LOCKED] GeckoTerminal stays the discovery backbone.
- [LOCKED] DexScreener stays an enrichment source and not the only discovery lane.
- [LOCKED] The first implementation bead stays within the documented per-minute budgets below.
- [LOCKED] Enrichment, security, and AI failures must remain non-blocking.

## Source Roles

### Discovery Backbone

Provider: GeckoTerminal

Role:

- discover new pools chronologically
- provide basic liquidity, tx, and volume context

Why this role:

- verified support for `new_pools`
- broad chain coverage
- no key required for the public API

### Enrichment Source

Provider: DexScreener

Role:

- enrich launches with chart links
- socials, websites, token images
- extra pair-level metadata

Why this role:

- high request budget for core endpoints
- good pair and token metadata
- easy batch enrichment

### Security Providers

Providers to document early:

- GoPlus
- RugCheck

Role:

- honey pot / tax / mintability / holder concentration / LP lock / risk summaries

These providers must remain optional and slower than the scanner loop.

## Verified / Research-Backed Limits

### GeckoTerminal

- base: `https://api.geckoterminal.com/api/v2`
- auth: none
- public free limit: `30 requests per minute`
- key endpoint: `/networks/{network}/new_pools`

Operational implications:

- use GeckoTerminal only once per chain per cycle where possible
- do not spam page refreshes mid-cycle
- paginate only when needed for overflow/high-volume chains

### DexScreener

- base: `https://api.dexscreener.com`
- auth: none
- core endpoints: `300 requests per minute`
- profile/boost/social endpoints: `60 requests per minute`
- useful batch endpoint supports up to 30 token addresses per request

Operational implications:

- batch enrichments aggressively
- separate core enrichment budget from social/profile budget

### GoPlus

- good EVM coverage
- Solana support is newer / more variable
- exact free rate limits are not cleanly documented

Operational implications:

- treat GoPlus as low-throughput until measured in practice
- cache results aggressively

### RugCheck

- especially useful for Solana
- free read endpoints exist
- exact rate limits are not cleanly documented

Operational implications:

- use only for shortlisted launches or Solana-specific security checks

## Recommended Polling Budget Per 60-Second Loop

### Discovery Pass

- GeckoTerminal:
  - BNB Chain: 1 call
  - Solana: 1 call
  - Base: 1 call
- additional page fetches only when the previous page indicates unprocessed overflow

Safe discovery baseline:

- [LOCKED] `3-9 calls per minute` under normal operation

### Enrichment Pass

- DexScreener core enrichment:
  - batch by token addresses
  - target only new or materially changed launches

Safe enrichment baseline:

- [LOCKED] `1-10 calls per minute` for typical bursty launch traffic

### Security Pass

- GoPlus / RugCheck only for launches that clear a minimum quality threshold
- do not scan every launch every cycle

Safe security baseline:

- [LOCKED] `0-10 calls per minute`, strongly cached

## Retry Policy

Apply the same retry policy across discovery and enrichment clients unless a provider-specific rule overrides it.

```text
max_retries: 3
initial_backoff_seconds: 1
backoff_multiplier: 2
jitter: +-10%
timeout_seconds: 5
```

Retry on:

- `429`
- `502`
- `503`
- `504`

Do not retry automatically on:

- `400`
- `401`
- `403`
- `404`

Provider-specific note:

- a `429` from GeckoTerminal should cool down the source until the next cycle rather than looping aggressively inside the same minute

## Cache Policy

### Discovery Cache

- GeckoTerminal launch lists: `60s`

### Enrichment Cache

- DexScreener pair/token metadata: `30-60s`
- social/profile metadata: `1h`

### Security Cache

- GoPlus / RugCheck results: `10-30m`

### AI Cache

- AI summaries: long-lived until manually refreshed or prompt version changes

## Failure Handling Rules

1. If GeckoTerminal fails for one chain, other chains still run.
2. If DexScreener enrichment fails, launch rows still persist and render.
3. If security providers fail, the system marks security as unavailable instead of blocking the launch.
4. If AI is unavailable, the scanner remains fully usable.
5. The scanner must never hide rows only because enrichment or security data is missing.

## Security Provider Usage Policy

### Phase 1

- [LOCKED] document providers
- [LOCKED] wire adapter boundaries only if cheap enough; do not persist security-provider results in Phase 1
- [LOCKED] do not block launch visibility on security scoring

### Phase 2+

- enrich only launches above minimum liquidity/activity thresholds
- store raw provider payloads for debugging and contract-drift checks

## Secrets And Config Mapping

Suggested keys:

- `CRYPTO_SCANNER_ENABLED`
- `CRYPTO_REFRESH_INTERVAL_SEC`
- `CRYPTO_DISCOVERY_CHAINS`
- `CRYPTO_ENRICHMENT_ENABLED`
- `CRYPTO_SECURITY_ENABLED`
- `GOPLUS_API_KEY` if needed later
- `RUGCHECK_API_KEY` if needed later

All keys must be documented in `.env.example` and `docs/full-guide.md` once implementation is added.

## Operational Risks To Watch

- GeckoTerminal pagination may miss launches on high-volume chains if only page 1 is used
- DexScreener may lack creation timestamps or have null market-cap data for fresh launches
- provider schemas can drift with limited deprecation notice on free APIs
- free providers have no strong SLA guarantees

## Citations To Keep In Mind

- GeckoTerminal public API / FAQ for `new_pools` and limits
- DexScreener OpenAPI and API reference
- GoPlus token security reference
- RugCheck swagger for Solana-specific risk endpoints
