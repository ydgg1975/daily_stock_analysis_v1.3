from src.services.rule_backtest_service import parse_and_run_automated

scenarios = [
    {"name": "A_standard_buy_sell", "capital": 100000},
    {"name": "B_cash_insufficient", "capital": 1000},
    {"name": "C_inferred_default", "capital": 100000},
    {"name": "D_compat_setup", "capital": 100000},
    {"name": "E_old_run_fallback", "capital": 100000},
]

output_dir = "./backtest_outputs"

for s in scenarios:
    parse_and_run_automated(
        symbol="ORCL",
        scenario=s["name"],
        initial_capital=s["capital"],
        output_dir=output_dir
    )

print("✅ 所有场景 CSV/JSON 已生成，可直接用于 Execution Trace 验收")