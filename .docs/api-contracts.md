# API Contracts

Status: Phase 0 locked API surface for the crypto scanner lane.

## Goal

Define stable request/response contracts for the crypto scanner without bending the existing stock API naming or semantics.

## Design Principles

1. Dedicated `/api/v1/crypto/*` namespace.
2. Cursor-based feed pagination for live launch data.
3. Explicit freshness metadata on every feed response.
4. Partial-data states are surfaced, not hidden.
5. Settings and AI review are optional layers on top of the deterministic scanner.

## Local Repo Pattern References

- Route aggregation: `api/v1/router.py:17`
- Existing task-oriented analysis endpoint style: `api/v1/endpoints/analysis.py:71`
- Existing pagination response pattern: `api/v1/schemas/history.py:49`

## Base Response Shape

Every crypto endpoint should follow this broad structure:

```json
{
  "meta": {
    "request_id": "req_123",
    "as_of": "2026-03-20T10:00:00Z",
    "data_complete": true,
    "symbols_partial": [],
    "backfill_active": false,
    "staleness_s": 12
  },
  "data": {}
}
```

For list endpoints, `data` is a collection wrapper. For detail endpoints, `data` is a single launch object.

## Phase 1 API Boundary

- [LOCKED] Phase 1 ships `GET /api/v1/crypto/launches`.
- [LOCKED] Phase 1 ships `GET /api/v1/crypto/launches/{launch_id}`.
- [LOCKED] Phase 1 ships `POST /api/v1/crypto/refresh`.
- [LOCKED] Phase 1 ships `GET /api/v1/crypto/status`.
- [DEFERRED TO PHASE 2+] `GET /api/v1/crypto/settings` and `PUT /api/v1/crypto/settings`.
- [DEFERRED TO PHASE 3+] `POST /api/v1/crypto/launches/{launch_id}/analyze`.

## Launch Feed Endpoints

### `GET /api/v1/crypto/launches`

Purpose:

- main scanner feed for the web UI

Query parameters:

| Param               | Type            | Notes                                       |
| ------------------- | --------------- | ------------------------------------------- |
| `chains`            | repeated string | `bsc`, `solana`, `base`                     |
| `dexes`             | repeated string | optional dex filter                         |
| `min_liquidity_usd` | number          | optional lower bound                        |
| `max_liquidity_usd` | number          | optional upper bound                        |
| `min_volume_usd`    | number          | optional lower bound                        |
| `max_age_minutes`   | integer         | age filter relative to `now`                |
| `min_tx_buys_m5`    | integer         | optional activity filter                    |
| `sort_by`           | string          | `newest`, `liquidity`, `volume`, `activity` |
| `sort_order`        | string          | `asc`, `desc`                               |
| `cursor`            | opaque string   | live feed pagination                        |
| `limit`             | integer         | recommended max 100                         |
| `include_hidden`    | boolean         | admin/debug only                            |

Response contract:

```json
{
  "meta": {
    "request_id": "req_123",
    "as_of": "2026-03-20T10:00:00Z",
    "data_complete": false,
    "symbols_partial": ["base:0xabc..."],
    "backfill_active": false,
    "staleness_s": 18,
    "next_cursor": "opaque_cursor",
    "has_more": true
  },
  "data": {
    "items": [
      {
        "id": 101,
        "chain_id": "solana",
        "dex_id": "pump-fun",
        "pair_address": "...",
        "base_token_address": "...",
        "base_symbol": "ABC",
        "base_name": "Alpha Beta Coin",
        "pair_created_at": "2026-03-20T09:58:00Z",
        "age_minutes": 2,
        "price_usd": "0.00042",
        "liquidity_usd": "52000.12",
        "fdv_usd": "840000.00",
        "volume_m5_usd": "18000.00",
        "tx_buys_m5": 27,
        "tx_sells_m5": 8,
        "website_url": "https://...",
        "twitter_url": "https://x.com/...",
        "image_url": "https://...",
        "data_complete": true
      }
    ]
  }
}
```

Notes:

- `cursor` must remain stable under concurrent inserts
- `next_cursor` is null when there is no next page
- this endpoint is optimized for the scanner UI, not historical analytics
- `risk_badges` are intentionally left out of the Phase 1 feed until deterministic derivation rules are specified

### `GET /api/v1/crypto/launches/{launch_id}`

Purpose:

- detail drawer or detail page payload

Response contract:

- all feed fields
- snapshot summary block
- latest security scan block once Phase 2+ security data exists
- latest AI summary block once Phase 3+ AI data exists
- outbound links block

Phase 1 note:

- `security` is `null` until Phase 2+ security-provider results are available
- `ai_summary` is `null` until Phase 3+ selective AI review is available

Additional fields:

```json
{
  "data": {
    "launch": { "...": "..." },
    "latest_snapshot": { "...": "..." },
    "security": null,
    "ai_summary": null,
    "links": {
      "dexscreener": "https://dexscreener.com/...",
      "website": "https://...",
      "twitter": "https://x.com/...",
      "telegram": "https://t.me/..."
    }
  }
}
```

## Control / Operations Endpoints

### `POST /api/v1/crypto/refresh`

Purpose:

- manual trigger for a scan cycle

Request body:

```json
{
  "chains": ["bsc", "solana", "base"],
  "force_full_enrichment": false
}
```

Response:

- `202 Accepted` when background work is queued
- payload includes `task_id`, `status`, `message`

Recommended response shape:

```json
{
  "task_id": "crypto-refresh-001",
  "status": "pending",
  "message": "Crypto scanner refresh accepted"
}
```

### `GET /api/v1/crypto/status`

Purpose:

- expose scanner health and freshness for UI and ops checks

Response fields:

- `scanner_enabled`
- `last_scan_started_at`
- `last_scan_finished_at`
- `last_successful_scan_at`
- `backfill_active`
- `degraded_providers`
- `scan_interval_seconds`

### `GET /api/v1/crypto/settings`

Purpose:

- load UI-facing scanner settings stored through the config service
- deferred until after the core scanner feed is stable

Suggested fields:

- `chains`
- `refresh_interval_seconds`
- `default_sort`
- `default_min_liquidity_usd`
- `default_max_age_minutes`
- `notifications_enabled`
- `ai_enrichment_enabled`

### `PUT /api/v1/crypto/settings`

Purpose:

- persist scanner settings through the existing config system
- deferred until after the core scanner feed is stable

Body shape should follow existing config update semantics used by `SystemConfigService`.

## Optional AI Endpoint

### `POST /api/v1/crypto/launches/{launch_id}/analyze`

Purpose:

- run selective AI review only for a shortlisted launch
- deferred beyond Phase 1 and reserved for selective AI review only

Request body:

```json
{
  "analysis_mode": "detail",
  "force_refresh": false
}
```

Response:

- `202 Accepted` when background AI work is queued
- or `200 OK` if a cached AI summary is returned immediately

## Error Semantics

Use the existing repo error conventions where possible.

Recommended codes:

| Code  | Meaning                                   |
| ----- | ----------------------------------------- |
| `200` | success                                   |
| `202` | async task accepted                       |
| `206` | partial data returned intentionally       |
| `400` | invalid filter or payload                 |
| `404` | launch not found                          |
| `409` | conflicting refresh or duplicate work     |
| `429` | local service-level throttle              |
| `500` | internal error                            |
| `503` | scanner unavailable / backfill-only state |

Recommended error response:

```json
{
  "error": {
    "type": "validation_error",
    "message": "max_age_minutes must be greater than 0",
    "detail": {
      "field": "max_age_minutes"
    }
  }
}
```

## Partial Data Semantics

These states must be explicit.

### Complete

- `data_complete = true`
- `symbols_partial = []`

### Partial

- `data_complete = false`
- `symbols_partial` contains affected launch ids or source keys
- data is still useful to render

### Unavailable / Backfill

- `data_complete = false`
- `backfill_active = true` or `service_unavailable = true`
- UI should show degraded state, not empty success state

## Pagination Strategy

Use cursor-based pagination for live feed endpoints because new inserts make page-based offsets unstable.

Recommended cursor payload:

- `first_seen_at`
- `id`

Encoded as an opaque token.

The cursor contract should guarantee:

- stable ordering under inserts
- short TTL (for example 15 minutes)
- no schema leakage to clients

## Backward Compatibility Rules

- keep all current stock endpoints untouched
- do not rename `/analysis`, `/history`, or `/stocks` to make room for crypto
- add crypto as a new namespace only
- only add non-breaking fields to responses within the same API version

## Notes For Implementation

- existing list/history APIs in this repo use `page`/`limit`, but the crypto feed is a justified exception because it is live and insert-heavy
- detail and settings endpoints can still use the repo's more conventional response style
