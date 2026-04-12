# Backtest System

## Service Ownership

- Standard historical-evaluation endpoints are owned by `src/services/backtest_service.py`:
  - `POST /api/v1/backtest/run`
  - `POST /api/v1/backtest/prepare-samples`
  - `GET /api/v1/backtest/results`
  - `GET /api/v1/backtest/sample-status`
  - `GET /api/v1/backtest/runs`
  - `GET /api/v1/backtest/performance`
  - `GET /api/v1/backtest/performance/{code}`
  - `POST /api/v1/backtest/samples/clear`
  - `POST /api/v1/backtest/results/clear`
- Rule-backtest endpoints are owned by `src/services/rule_backtest_service.py`:
  - `POST /api/v1/backtest/rule/parse`
  - `POST /api/v1/backtest/rule/run`
  - `GET /api/v1/backtest/rule/runs`
  - `GET /api/v1/backtest/rule/runs/{run_id}`
  - `GET /api/v1/backtest/rule/runs/{run_id}/status`
  - `POST /api/v1/backtest/rule/runs/{run_id}/cancel`

## Async And Background Execution

- `POST /api/v1/backtest/rule/run` is asynchronous by default and returns one of `queued / parsing / running / summarizing / completed / failed / cancelled`.
- Pass `wait_for_completion=true` to run inline and return the full completed payload.
- `GET /api/v1/backtest/rule/runs/{run_id}/status` is the lightweight polling endpoint for background progress.
- `POST /api/v1/backtest/rule/runs/{run_id}/cancel` is a best-effort cancel endpoint: unfinished runs are marked `cancelled`, while already-finished runs keep their final state.
- `GET /api/v1/backtest/rule/runs/{run_id}` remains the full-detail endpoint and includes `execution_trace`, trades, and audit data.

## Local US Parquet Priority

- US daily history first reads `LOCAL_US_PARQUET_DIR`.
- If `LOCAL_US_PARQUET_DIR` is unset, the code falls back to `US_STOCK_PARQUET_DIR` for backward compatibility.
- A local parquet hit reports `resolved_source=LocalParquet` and skips online fetching.
- If local parquet is missing or invalid, the backtest flow follows the existing fetch fallback path and exposes `requested_mode / resolved_source / fallback_used` in responses.

## Run The API Locally

```bash
.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Optional environment variables:

```bash
export LOCAL_US_PARQUET_DIR=/path/to/local/us/parquet
# Use only for legacy compatibility
export US_STOCK_PARQUET_DIR=/path/to/local/us/parquet
```

## Smoke Scripts

- The root-level smoke suites automatically:
  - boot a temporary uvicorn server
  - disable admin auth
  - create a temporary database
  - prepare a temporary `LOCAL_US_PARQUET_DIR` fixture
  - run assertions and clean everything up

- Standard backtest API smoke:

```bash
python3 test_backtest_basic.py
```

- Rule backtest API smoke:

```bash
python3 test_backtest_rule.py
```

- Run both:

```bash
python3 test_backtest_run.py --mode both
```

## Known Assumptions And Limits

- Real local-parquet reads in production still require `pyarrow` or `fastparquet`; when a parquet engine is unavailable, the repo smoke scripts inject a test-only shim so the `LOCAL_US_PARQUET_DIR` priority path and async endpoints can still be validated.
- Synchronous rule backtests still depend on market data being available locally or through the existing data-source fallback chain.
- `execution_trace` detail and CSV / JSON exports treat persisted `audit_rows` as the source of truth; older runs that do not store it are rebuilt on read and marked with `trace_rebuilt`.
