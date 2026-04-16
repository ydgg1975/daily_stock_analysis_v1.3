# -*- coding: utf-8 -*-
"""Canonical rule backtest API smoke against a real uvicorn server."""

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
from src.services.rule_backtest_service import RuleBacktestService
from src.storage import DatabaseManager


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    strategy_text = "5日均线上穿20日均线买入，下穿卖出"

    with temporary_backtest_runtime(eval_window_days=5, min_age_days=14, async_delay_ms=1500) as runtime:
        start_date, end_date = seed_local_us_history_fixture(runtime, code="AAPL", days=360)

        with temporary_backtest_server(runtime) as server:
            parse_status, parse_payload = server.request(
                "POST",
                "/api/v1/backtest/rule/parse",
                payload={
                    "code": "AAPL",
                    "strategy_text": strategy_text,
                    "start_date": start_date,
                    "end_date": end_date,
                    "initial_capital": 100000.0,
                    "fee_bps": 0.0,
                    "slippage_bps": 0.0,
                },
            )
            _assert(parse_status == 200, f"rule parse failed: {parse_status}")
            parse_payload = assert_json_keys(
                "rule-parse",
                parse_payload,
                ["parsed_strategy", "normalization_state", "needs_confirmation", "normalized_strategy_family"],
            )

            base_run_payload = {
                "code": "AAPL",
                "strategy_text": strategy_text,
                "parsed_strategy": parse_payload["parsed_strategy"],
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": 100000.0,
                "fee_bps": 0.0,
                "slippage_bps": 0.0,
                "benchmark_mode": "same_symbol_buy_and_hold",
                "confirmed": True,
                "wait_for_completion": False,
            }

            run1_status, run1_payload = server.request(
                "POST",
                "/api/v1/backtest/rule/run",
                payload={**base_run_payload, "lookback_bars": 120},
            )
            _assert(run1_status == 200, f"rule run #1 failed: {run1_status}")
            run1_payload = assert_json_keys("rule-run-1", run1_payload, ["id", "status", "status_history"])

            run2_status, run2_payload = server.request(
                "POST",
                "/api/v1/backtest/rule/run",
                payload={**base_run_payload, "lookback_bars": 140},
            )
            _assert(run2_status == 200, f"rule run #2 failed: {run2_status}")
            run2_payload = assert_json_keys("rule-run-2", run2_payload, ["id", "status", "status_history"])

            cancel_status, cancel_payload = server.request(
                "POST",
                "/api/v1/backtest/rule/run",
                payload={**base_run_payload, "lookback_bars": 100},
            )
            _assert(cancel_status == 200, f"rule cancel target submission failed: {cancel_status}")
            cancel_payload = assert_json_keys("rule-run-cancel-target", cancel_payload, ["id", "status"])

            cancel_response_status, cancel_response = server.request(
                "POST",
                f"/api/v1/backtest/rule/runs/{int(cancel_payload['id'])}/cancel",
            )
            _assert(cancel_response_status == 200, f"rule cancel failed: {cancel_response_status}")
            cancel_response = assert_json_keys(
                "rule-cancel",
                cancel_response,
                ["id", "status", "no_result_reason", "status_history"],
            )
            _assert(cancel_response["status"] == "cancelled", "cancel endpoint did not mark the run as cancelled")
            _assert(cancel_response["no_result_reason"] == "cancelled", "cancel endpoint did not expose cancelled reason")

            run1_snapshot_status, run1_snapshot = server.request(
                "GET",
                f"/api/v1/backtest/rule/runs/{int(run1_payload['id'])}/status",
            )
            _assert(run1_snapshot_status == 200, f"rule status failed: {run1_snapshot_status}")
            run1_snapshot = assert_json_keys("rule-status", run1_snapshot, ["id", "status", "status_history"])

            run1_final = server.wait_for_rule_status(int(run1_payload["id"]), target_statuses={"completed"})
            run2_final = server.wait_for_rule_status(int(run2_payload["id"]), target_statuses={"completed"})
            cancel_final = server.wait_for_rule_status(int(cancel_payload["id"]), target_statuses={"cancelled"})

            history_status, history_payload = server.request(
                "GET",
                "/api/v1/backtest/rule/runs",
                params={"code": "AAPL", "page": 1, "limit": 10},
            )
            _assert(history_status == 200, f"rule history failed: {history_status}")
            history_payload = assert_json_keys("rule-history", history_payload, ["total", "items"])
            _assert(
                isinstance(history_payload["items"], list) and len(history_payload["items"]) >= 3,
                "rule history returned too few runs",
            )

            detail_status, detail_payload = server.request(
                "GET",
                f"/api/v1/backtest/rule/runs/{int(run1_payload['id'])}",
            )
            _assert(detail_status == 200, f"rule detail failed: {detail_status}")
            detail_payload = assert_json_keys(
                "rule-detail",
                detail_payload,
                ["id", "status", "parsed_strategy", "execution_trace", "auditRows"],
            )
            trace_rows = list((detail_payload.get("execution_trace") or {}).get("rows") or [])
            _assert(trace_rows, "rule detail did not include execution trace rows")
            _assert(detail_payload["status"] == "completed", "rule detail did not finish successfully")

        persisted_sources = get_stock_daily_sources(runtime.db, code="AAPL")
        _assert("local_us_parquet" in persisted_sources, f"expected local_us_parquet in persisted sources, got {persisted_sources}")

        DatabaseManager.reset_instance()
        service = RuleBacktestService()
        csv_path = runtime.output_dir / f"AAPL_{int(run1_payload['id'])}_execution_trace.csv"
        json_path = runtime.output_dir / f"AAPL_{int(run1_payload['id'])}_execution_trace.json"
        service.export_execution_trace_csv(int(run1_payload["id"]), str(csv_path))
        service.export_execution_trace_json(int(run1_payload["id"]), str(json_path))

        exported_trace = json.loads(json_path.read_text(encoding="utf-8"))
        _assert(csv_path.exists(), "execution trace CSV export was not created")
        _assert(json_path.exists(), "execution trace JSON export was not created")
        _assert(
            isinstance(exported_trace.get("trace_rows"), list) and exported_trace["trace_rows"],
            "execution trace JSON export is empty",
        )
        _assert(len(exported_trace["trace_rows"]) == len(trace_rows), "execution trace export row count mismatch")

        print(
            json.dumps(
                {
                    "parse": {
                        "normalized_strategy_family": parse_payload["normalized_strategy_family"],
                        "normalization_state": parse_payload["normalization_state"],
                    },
                    "async_runs": [
                        {"id": run1_final["id"], "status": run1_final["status"]},
                        {"id": run2_final["id"], "status": run2_final["status"]},
                    ],
                    "cancelled_run": {
                        "id": cancel_final["id"],
                        "status": cancel_final["status"],
                        "reason": cancel_final["no_result_reason"],
                    },
                    "history_total": history_payload["total"],
                    "detail": {
                        "trade_count": detail_payload.get("trade_count"),
                        "trace_rows": len(trace_rows),
                    },
                    "exports": {
                        "csv": str(csv_path),
                        "json": str(json_path),
                    },
                    "persisted_sources": persisted_sources,
                    "status_snapshot": run1_snapshot["status"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
