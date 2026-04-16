# -*- coding: utf-8 -*-
"""Canonical standard backtest API smoke against a real uvicorn server."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.backtest_smoke_support import (
    assert_json_keys,
    get_stock_daily_sources,
    seed_local_us_history_fixture,
    temporary_backtest_runtime,
    temporary_backtest_server,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    with temporary_backtest_runtime(eval_window_days=5, min_age_days=14) as runtime:
        seed_local_us_history_fixture(runtime, code="AAPL", days=320)

        with temporary_backtest_server(runtime) as server:
            prepare_status, prepare_payload = server.request(
                "POST",
                "/api/v1/backtest/prepare-samples",
                payload={
                    "code": "AAPL",
                    "sample_count": 5,
                    "eval_window_days": 5,
                    "min_age_days": 14,
                    "force_refresh": False,
                },
            )
            _assert(prepare_status == 200, f"prepare-samples failed: {prepare_status}")
            prepare_payload = assert_json_keys(
                "prepare-samples",
                prepare_payload,
                ["code", "prepared", "resolved_source", "requested_mode", "fallback_used"],
            )
            _assert(prepare_payload["code"] == "AAPL", "prepare-samples returned the wrong code")
            _assert(int(prepare_payload["prepared"]) > 0, "prepare-samples did not generate any samples")
            _assert(prepare_payload["requested_mode"] == "local_first", "prepare-samples did not use local-first mode")
            _assert(prepare_payload["resolved_source"] == "LocalParquet", "prepare-samples did not prioritize local parquet")
            _assert(prepare_payload["fallback_used"] is False, "prepare-samples unexpectedly used fallback")

            status_code, sample_status = server.request(
                "GET",
                "/api/v1/backtest/sample-status",
                params={"code": "AAPL"},
            )
            _assert(status_code == 200, f"sample-status failed: {status_code}")
            sample_status = assert_json_keys(
                "sample-status",
                sample_status,
                ["code", "prepared_count", "resolved_source", "requested_mode"],
            )
            _assert(
                int(sample_status["prepared_count"]) >= int(prepare_payload["prepared"]),
                "sample-status prepared_count mismatch",
            )

            run_status, run_payload = server.request(
                "POST",
                "/api/v1/backtest/run",
                payload={
                    "code": "AAPL",
                    "force": False,
                    "eval_window_days": 5,
                    "min_age_days": 14,
                    "limit": 20,
                },
            )
            _assert(run_status == 200, f"run failed: {run_status}")
            run_payload = assert_json_keys(
                "run",
                run_payload,
                ["run_id", "processed", "saved", "completed", "errors", "execution_assumptions"],
            )
            _assert(int(run_payload["saved"]) > 0, "standard run did not persist results")
            _assert(int(run_payload["completed"]) > 0, "standard run did not complete any evaluations")
            _assert(int(run_payload["errors"]) == 0, "standard run returned unexpected errors")

            runs_status, runs_payload = server.request(
                "GET",
                "/api/v1/backtest/runs",
                params={"code": "AAPL", "page": 1, "limit": 10},
            )
            _assert(runs_status == 200, f"runs failed: {runs_status}")
            runs_payload = assert_json_keys("runs", runs_payload, ["total", "items"])
            _assert(isinstance(runs_payload["items"], list) and runs_payload["items"], "runs returned no history items")

            results_status, results_payload = server.request(
                "GET",
                "/api/v1/backtest/results",
                params={"run_id": int(run_payload["run_id"]), "page": 1, "limit": 20},
            )
            _assert(results_status == 200, f"results failed: {results_status}")
            results_payload = assert_json_keys("results", results_payload, ["total", "items"])
            _assert(isinstance(results_payload["items"], list) and results_payload["items"], "results returned no items")

            performance_status, performance_payload = server.request(
                "GET",
                "/api/v1/backtest/performance/AAPL",
                params={"eval_window_days": 5},
            )
            _assert(performance_status == 200, f"performance failed: {performance_status}")
            performance_payload = assert_json_keys(
                "performance",
                performance_payload,
                ["code", "eval_window_days", "requested_mode", "resolved_source"],
            )

        persisted_sources = get_stock_daily_sources(runtime.db, code="AAPL")
        _assert("local_us_parquet" in persisted_sources, f"expected local_us_parquet in persisted sources, got {persisted_sources}")

        print(
            json.dumps(
                {
                    "prepare": {
                        "prepared": prepare_payload["prepared"],
                        "resolved_source": prepare_payload["resolved_source"],
                        "requested_mode": prepare_payload["requested_mode"],
                    },
                    "sample_status": {
                        "prepared_count": sample_status["prepared_count"],
                        "latest_prepared_sample_date": sample_status.get("latest_prepared_sample_date"),
                    },
                    "run": {
                        "run_id": run_payload["run_id"],
                        "saved": run_payload["saved"],
                        "completed": run_payload["completed"],
                        "errors": run_payload["errors"],
                    },
                    "results_total": results_payload["total"],
                    "runs_total": runs_payload["total"],
                    "performance": {
                        "requested_mode": performance_payload.get("requested_mode"),
                        "resolved_source": performance_payload.get("resolved_source"),
                    },
                    "persisted_sources": persisted_sources,
                    "local_parquet_dir": str(runtime.local_parquet_dir),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
