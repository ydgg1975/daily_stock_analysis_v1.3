# src/services/auto_trace_check.py
import csv
import json
from pathlib import Path
from typing import List, Dict

# --- Execution Trace Acceptance Checker ---

ACCEPTANCE_FIELDS = [
    "date",
    "close",
    "signal",
    "action",
    "price",
    "shares",
    "cash",
    "position_value",
    "total_assets",
    "daily_pnl",
    "daily_return",
    "strategy_cum_return",
    "benchmark_cum_return",
    "buy_hold_cum_return",
    "assumptions",
    "fallback"
]

ACCEPTANCE_ITEMS = [
    "基础通路",
    "交易事件完整性",
    "assumptions/defaults 可追溯",
    "fallback 标记",
    "资产/现金/持仓一致性",
    "CSV/JSON 列完整"
]

def run_execution_trace_check(trace: List[Dict], csv_path: str = None, json_path: str = None) -> List[Dict]:
    """
    自动验收 execution trace。
    返回验收结果列表，每项 dict 包含: # / 验收项 / 检查结果 / 备注
    """
    results = []

    # 1. 基础通路: 是否有数据
    results.append({
        "#": 1,
        "验收项": "基础通路",
        "检查结果": "✅" if trace else "❌",
        "备注": "Trace 非空" if trace else "Trace 为空"
    })

    # 2. 交易事件完整性 (buy/sell/skip)
    actions = {row.get("action") for row in trace}
    missing_events = set(["buy", "sell", "skip"]) - actions
    results.append({
        "#": 2,
        "验收项": "交易事件完整性",
        "检查结果": "✅" if not missing_events else "❌",
        "备注": f"缺失事件: {missing_events}" if missing_events else ""
    })

    # 3. assumptions/defaults 可追溯
    assumptions_ok = all("assumptions" in row and row["assumptions"] for row in trace)
    results.append({
        "#": 3,
        "验收项": "assumptions/defaults 可追溯",
        "检查结果": "✅" if assumptions_ok else "❌",
        "备注": "" if assumptions_ok else "部分行缺 assumptions"
    })

    # 4. fallback 标记
    fallback_ok = all("fallback" in row for row in trace)
    results.append({
        "#": 4,
        "验收项": "fallback 标记",
        "检查结果": "✅" if fallback_ok else "❌",
        "备注": "" if fallback_ok else "部分行缺 fallback"
    })

    # 5. 资产/现金/持仓一致性
    assets_ok = all(
        row.get("total_assets") == row.get("cash", 0) + row.get("position_value", 0)
        for row in trace
    )
    results.append({
        "#": 5,
        "验收项": "资产/现金/持仓一致性",
        "检查结果": "✅" if assets_ok else "❌",
        "备注": "" if assets_ok else "存在 total_assets 与 cash+position_value 不一致"
    })

    # 6. CSV/JSON 列完整
    first_row = trace[0] if trace else {}
    columns_ok = all(field in first_row for field in ACCEPTANCE_FIELDS)
    results.append({
        "#": 6,
        "验收项": "CSV/JSON 列完整",
        "检查结果": "✅" if columns_ok else "❌",
        "备注": "" if columns_ok else "列缺失"
    })

    # 可选保存
    if csv_path:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    if json_path:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    return results