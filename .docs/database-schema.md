# Database Schema

Status: Phase 0 locked schema boundary for the crypto scanner lane, designed to fit the current SQLAlchemy storage pattern in `src/storage.py`.

## Goal

Define the canonical storage model for:

- newly discovered launches
- per-scan snapshots
- security/risk results
- optional AI summaries

The schema must coexist with the stock schema without bending stock models to fit crypto semantics.

## Local Repo Pattern References

- ORM base and model registry: `src/storage.py:56`
- primary market row example: `src/storage.py:64`
- historical result/archive pattern: `src/storage.py:208`
- DB manager access pattern: `src/storage.py:623`

## Design Principles

1. Launch row is the canonical identity record.
2. Snapshot rows are append-only time series.
3. Security scans are separate from launch rows.
4. AI summaries are separate from live deterministic state.
5. Writes must be idempotent on canonical uniqueness keys.

## Phase 1 Schema Boundary

- [LOCKED] Canonical launch identity is `chain_id + pair_address`.
- [LOCKED] Phase 1 includes `CryptoLaunch` and `CryptoLaunchSnapshot` together.
- [LOCKED] Launch rows are upserted while snapshot rows remain append-only.
- [DEFERRED TO PHASE 2+] `CryptoLaunchSecurityScan` stays separate from the core scanner row.
- [DEFERRED TO PHASE 3+] `CryptoLaunchAiSummary` stays separate from deterministic scanner state.

## Core Entities

### 1. `CryptoLaunch`

Purpose:

- canonical record for one discovered launch/pair
- latest known state for rendering the scanner feed

Suggested fields:

| Field                 | Type                      | Notes                                      |
| --------------------- | ------------------------- | ------------------------------------------ |
| `id`                  | Integer PK                | internal identity                          |
| `chain_id`            | String(32)                | `bsc`, `solana`, `base`                    |
| `dex_id`              | String(64)                | source DEX name/id                         |
| `pair_address`        | String(128)               | canonical pair identifier                  |
| `base_token_address`  | String(128)               | launch token address                       |
| `quote_token_address` | String(128), nullable     | SOL/USDC/WBNB/etc.                         |
| `base_symbol`         | String(64)                | display symbol                             |
| `base_name`           | String(255), nullable     | display name                               |
| `quote_symbol`        | String(64), nullable      | quote symbol                               |
| `pair_name`           | String(255), nullable     | human-readable pair label                  |
| `pair_created_at`     | DateTime, nullable        | upstream creation time                     |
| `first_seen_at`       | DateTime                  | first discovery time in our system         |
| `last_seen_at`        | DateTime                  | most recent successful observation         |
| `last_enriched_at`    | DateTime, nullable        | most recent enrichment timestamp           |
| `source_discovery`    | String(32)                | `geckoterminal`                            |
| `source_enrichment`   | String(32), nullable      | `dexscreener`                              |
| `price_usd`           | Numeric(30, 12), nullable | latest price                               |
| `liquidity_usd`       | Numeric(30, 4), nullable  | latest liquidity                           |
| `fdv_usd`             | Numeric(30, 4), nullable  | latest FDV                                 |
| `market_cap_usd`      | Numeric(30, 4), nullable  | often null for fresh tokens                |
| `volume_m5_usd`       | Numeric(30, 4), nullable  | scanner-friendly latest aggregates         |
| `volume_h1_usd`       | Numeric(30, 4), nullable  | latest aggregates                          |
| `tx_buys_m5`          | Integer, nullable         | latest aggregate                           |
| `tx_sells_m5`         | Integer, nullable         | latest aggregate                           |
| `buyers_m5`           | Integer, nullable         | latest aggregate                           |
| `sellers_m5`          | Integer, nullable         | latest aggregate                           |
| `price_change_m5_pct` | Numeric(12, 4), nullable  | latest aggregate                           |
| `boost_active_count`  | Integer, nullable         | DexScreener boost signal                   |
| `image_url`           | Text, nullable            | token icon                                 |
| `website_url`         | Text, nullable            | primary website                            |
| `twitter_url`         | Text, nullable            | primary social                             |
| `telegram_url`        | Text, nullable            | primary social                             |
| `data_complete`       | Boolean                   | whether latest row has complete enrichment |
| `is_hidden`           | Boolean                   | local mute/hide control                    |
| `created_at`          | DateTime                  | record creation                            |
| `updated_at`          | DateTime                  | record update                              |

Canonical uniqueness:

```python
UniqueConstraint("chain_id", "pair_address", name="uix_crypto_launch_chain_pair")
```

Recommended indexes:

- `Index("ix_crypto_launch_chain_created", "chain_id", "pair_created_at")`
- `Index("ix_crypto_launch_first_seen", "first_seen_at")`
- `Index("ix_crypto_launch_last_seen", "last_seen_at")`
- `Index("ix_crypto_launch_base_token", "chain_id", "base_token_address")`

### 2. `CryptoLaunchSnapshot`

Purpose:

- append-only scan history for charts, trend deltas, replay, and debugging

Suggested fields:

| Field                 | Type                      | Notes                           |
| --------------------- | ------------------------- | ------------------------------- |
| `id`                  | Integer PK                | internal identity               |
| `launch_id`           | FK -> `CryptoLaunch.id`   | canonical parent                |
| `snapshot_at`         | DateTime                  | when this sample was captured   |
| `source_timestamp`    | DateTime, nullable        | upstream timestamp if available |
| `price_usd`           | Numeric(30, 12), nullable | observed value                  |
| `liquidity_usd`       | Numeric(30, 4), nullable  | observed value                  |
| `fdv_usd`             | Numeric(30, 4), nullable  | observed value                  |
| `market_cap_usd`      | Numeric(30, 4), nullable  | observed value                  |
| `volume_m5_usd`       | Numeric(30, 4), nullable  | observed value                  |
| `volume_h1_usd`       | Numeric(30, 4), nullable  | observed value                  |
| `tx_buys_m5`          | Integer, nullable         | observed value                  |
| `tx_sells_m5`         | Integer, nullable         | observed value                  |
| `buyers_m5`           | Integer, nullable         | observed value                  |
| `sellers_m5`          | Integer, nullable         | observed value                  |
| `price_change_m5_pct` | Numeric(12, 4), nullable  | observed value                  |
| `source_discovery`    | String(32)                | origin provider                 |
| `source_enrichment`   | String(32), nullable      | enrichment provider             |
| `data_complete`       | Boolean                   | completeness flag               |
| `created_at`          | DateTime                  | row creation                    |

Canonical uniqueness:

```python
UniqueConstraint("launch_id", "snapshot_at", name="uix_crypto_launch_snapshot_time")
```

Recommended indexes:

- `Index("ix_crypto_snapshot_launch_time", "launch_id", "snapshot_at")`
- `Index("ix_crypto_snapshot_time", "snapshot_at")`

### 3. `CryptoLaunchSecurityScan`

Purpose:

- keep security-provider results separate from the main launch row
- allow slower cache TTL than scanner cadence

Suggested fields:

| Field                   | Type                     | Notes                               |
| ----------------------- | ------------------------ | ----------------------------------- |
| `id`                    | Integer PK               | internal identity                   |
| `launch_id`             | FK -> `CryptoLaunch.id`  | canonical parent                    |
| `provider`              | String(32)               | `goplus`, `rugcheck`, etc.          |
| `provider_report_id`    | String(128), nullable    | provider-native id                  |
| `scanned_at`            | DateTime                 | when the scan was executed          |
| `is_honeypot`           | Boolean, nullable        | provider signal                     |
| `is_mintable`           | Boolean, nullable        | provider signal                     |
| `buy_tax_pct`           | Numeric(10, 4), nullable | provider signal                     |
| `sell_tax_pct`          | Numeric(10, 4), nullable | provider signal                     |
| `top10_holder_rate_pct` | Numeric(10, 4), nullable | provider signal                     |
| `lp_locked_pct`         | Numeric(10, 4), nullable | provider signal                     |
| `risk_score`            | Numeric(10, 4), nullable | normalized local score              |
| `risk_level`            | String(32), nullable     | `low`, `medium`, `high`, `critical` |
| `raw_payload_json`      | JSON/Text                | raw provider response               |
| `created_at`            | DateTime                 | row creation                        |

Recommended indexes:

- `Index("ix_crypto_security_launch_scan", "launch_id", "scanned_at")`
- `Index("ix_crypto_security_provider_time", "provider", "scanned_at")`

### 4. `CryptoLaunchAiSummary`

Purpose:

- store selective AI summaries without polluting deterministic scanner state

Suggested fields:

| Field               | Type                     | Notes                                         |
| ------------------- | ------------------------ | --------------------------------------------- |
| `id`                | Integer PK               | internal identity                             |
| `launch_id`         | FK -> `CryptoLaunch.id`  | canonical parent                              |
| `analysis_mode`     | String(32)               | `detail`, `shortlist`, `alert_review`         |
| `model_name`        | String(128)              | model used                                    |
| `prompt_version`    | String(64)               | prompt/schema traceability                    |
| `summary_markdown`  | Text                     | user-facing summary                           |
| `verdict`           | String(32), nullable     | `watch`, `ignore`, `high_risk`, `interesting` |
| `confidence`        | Numeric(10, 4), nullable | optional model confidence                     |
| `raw_response_json` | JSON/Text                | structured response if any                    |
| `created_at`        | DateTime                 | when analysis ran                             |

Recommended indexes:

- `Index("ix_crypto_ai_launch_created", "launch_id", "created_at")`
- `Index("ix_crypto_ai_mode_created", "analysis_mode", "created_at")`

## Relationships

```text
CryptoLaunch 1 --- N CryptoLaunchSnapshot
CryptoLaunch 1 --- N CryptoLaunchSecurityScan
CryptoLaunch 1 --- N CryptoLaunchAiSummary
```

The `CryptoLaunch` row is the latest state. Snapshot, security, and AI tables are append-only histories.

## ORM Placement Strategy

To stay aligned with local repo conventions:

- register the SQLAlchemy models in `src/storage.py`
- expose read/write helpers via `DatabaseManager` only where shared access is needed
- put higher-level query methods in `src/repositories/crypto_launch_repo.py`

Do not extend `StockDaily` to hold crypto launches. The semantics are different enough that mixing the domains would create future migration pain.

## Retention Guidance

- `CryptoLaunch`: keep indefinitely unless manually archived
- `CryptoLaunchSnapshot`: keep high-resolution samples for 7-30 days, then aggregate or prune
- `CryptoLaunchSecurityScan`: keep all historical scans, but prefer latest for UI rendering
- `CryptoLaunchAiSummary`: keep all records for prompt/version auditing

## Upsert Rules

### `CryptoLaunch`

- upsert by `(chain_id, pair_address)`
- update latest-value fields on every fresh observation
- never overwrite `first_seen_at`

### `CryptoLaunchSnapshot`

- insert-only
- if the exact `(launch_id, snapshot_at)` already exists, skip or merge idempotently

### `CryptoLaunchSecurityScan`

- insert a new row per scan
- latest row per provider is the active UI candidate

### `CryptoLaunchAiSummary`

- insert a new row per AI run
- never overwrite previous summaries silently

## Minimum MVP Schema

Phase 1 is explicitly locked to ship with:

- `CryptoLaunch`
- `CryptoLaunchSnapshot`

Deferred beyond Phase 1:

- `CryptoLaunchSecurityScan` in Phase 2+
- `CryptoLaunchAiSummary` in Phase 3+

## Migration Notes

- Add the new tables without changing existing stock tables
- Keep crypto feature flags disabled by default until API + UI are ready
- Document any new env/config keys in `.env.example`, `docs/full-guide.md`, and `AGENTS.md` once the implementation lands
