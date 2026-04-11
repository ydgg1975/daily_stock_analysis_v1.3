# -*- coding: utf-8 -*-
"""Run five deterministic backtest scenarios and export Execution Trace files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auto_trace_check import _read_csv_rows, _read_json_payload, run_acceptance_checks, summarize_acceptance_reports, write_acceptance_report
from src.services.rule_backtest_service import run_backtest_automated


DEFAULT_SCENARIOS = [
    "normal_path",
    "cash_insufficiency_skip",
    "benchmark_fallback",
    "macd_crossover",
    "rsi_threshold",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="批量运行 deterministic backtest execution trace 场景。")
    parser.add_argument("--symbol", default="600519", help="回测标的代码，默认 600519")
    parser.add_argument("--initial-capital", type=float, default=100000.0, help="默认初始资金")
    parser.add_argument("--output-dir", default="./backtest_outputs", help="CSV/JSON 输出目录")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    report_map = {}
    for scenario in DEFAULT_SCENARIOS:
        scenario_capital = 1500.0 if scenario == "cash_insufficiency_skip" else float(args.initial_capital)
        result = run_backtest_automated(
            symbol=args.symbol,
            scenario=scenario,
            initial_capital=scenario_capital,
            output_dir=str(output_dir),
        )
        results.append(result)
        csv_rows = _read_csv_rows(Path(result["csv_path"]))
        json_payload = _read_json_payload(Path(result["json_path"]))
        scenario_report = run_acceptance_checks(csv_rows, trace_payload=json_payload)
        report_map[scenario] = scenario_report
        write_acceptance_report(
            scenario_report,
            csv_path=output_dir / f"{scenario}.acceptance.csv",
            json_path=output_dir / f"{scenario}.acceptance.json",
        )
        print(f"[done] {scenario}: {result['csv_path']} | {result['json_path']}")

    summary_path = output_dir / "scenario-run-summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    final_report = summarize_acceptance_reports(report_map)
    write_acceptance_report(
        final_report,
        csv_path=output_dir / "execution-trace-acceptance.csv",
        json_path=output_dir / "execution-trace-acceptance.json",
    )
    print("最终验收表:")
    for row in final_report:
        print(f"[{row['检查结果']}] {row['验收项']} - {row['备注']}")
    print(f"场景汇总: {summary_path}")
    print(f"最终验收 CSV: {output_dir / 'execution-trace-acceptance.csv'}")
    print(f"最终验收 JSON: {output_dir / 'execution-trace-acceptance.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
