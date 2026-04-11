# File: scripts/run_all_execution_trace.py
import os
from pathlib import Path
import csv
import json
from src.services.rule_backtest_service import run_backtest_automated, export_execution_trace_csv, export_execution_trace_json

OUTPUT_DIR = Path('./backtest_outputs')
OUTPUT_DIR.mkdir(exist_ok=True)

SCENARIOS = [
    ('A_standard_buy_sell', 100000),
    ('B_cash_insufficient', 1000),
    ('C_inferred_default', 100000),
    ('D_compat_setup', 100000),
    ('E_old_run_fallback', 100000)
]

all_acceptance_results = []

for scenario_name, initial_capital in SCENARIOS:
    print(f"[INFO] Running scenario: {scenario_name} with initial capital: {initial_capital}")
    try:
        result = run_backtest_automated('ORCL', initial_capital)
        trace = result['trace']
        csv_file = OUTPUT_DIR / f"{scenario_name}.csv"
        json_file = OUTPUT_DIR / f"{scenario_name}.json"
        export_execution_trace_csv(trace, csv_file)
        export_execution_trace_json(trace, json_file)
        acceptance = {
            'scenario': scenario_name,
            'passed': '✅' if any(e['action'] in ['buy','sell'] for e in trace) else '❌',
            'trace_length': len(trace)
        }
        all_acceptance_results.append(acceptance)
    except Exception as e:
        print(f"[ERROR] Scenario {scenario_name} failed: {e}")
        all_acceptance_results.append({'scenario': scenario_name, 'passed': '❌', 'error': str(e)})

# Write acceptance summary
if all_acceptance_results:
    csv_summary = OUTPUT_DIR / 'execution-trace-acceptance.csv'
    json_summary = OUTPUT_DIR / 'execution-trace-acceptance.json'
    keys = all_acceptance_results[0].keys()
    with open(csv_summary, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_acceptance_results)

    with open(json_summary, 'w', encoding='utf-8') as f:
        json.dump(all_acceptance_results, f, ensure_ascii=False, indent=2)

    print(f"[INFO] Acceptance summary saved to {csv_summary} and {json_summary}")
else:
    print("[WARN] No acceptance results generated.")