#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Acceptance helpers for exported deterministic execution traces."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"

REPORT_COLUMNS = ["#", "验收项", "检查结果", "备注"]
TRACE_REQUIRED_COLUMNS = [
    "日期",
    "标的收盘价",
    "基准收盘价",
    "信号摘要",
    "动作",
    "成交价",
    "持股数",
    "现金",
    "持仓市值",
    "总资产",
    "当日盈亏",
    "当日收益率",
    "策略累计收益率",
    "基准累计收益率",
    "买入持有累计收益率",
    "仓位",
    "手续费",
    "滑点",
    "备注",
    "fallback",
    "assumptions",
]


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _has_action(rows: Iterable[Dict[str, Any]], *actions: str) -> bool:
    normalized_actions = {str(action).strip().lower() for action in actions}
    for row in rows:
        action = str(row.get("动作") or row.get("action") or "").strip().lower()
        if action in normalized_actions:
            return True
    return False


def _assets_consistent(rows: Iterable[Dict[str, Any]]) -> bool:
    for row in rows:
        total_assets = _safe_float(row.get("总资产") or row.get("total_assets"))
        cash = _safe_float(row.get("现金") or row.get("cash"))
        holdings = _safe_float(row.get("持仓市值") or row.get("position_value"))
        if total_assets is None or cash is None or holdings is None:
            return False
        if abs(total_assets - (cash + holdings)) > 1e-6:
            return False
    return True


def _trace_rows_from_payload(trace_payload: Any) -> List[Dict[str, Any]]:
    if isinstance(trace_payload, dict):
        rows = trace_payload.get("trace_rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def run_acceptance_checks(rows: List[Dict[str, Any]], *, trace_payload: Any | None = None) -> List[Dict[str, Any]]:
    trace_rows = _trace_rows_from_payload(trace_payload)
    assumptions_payload = trace_payload.get("assumptions") if isinstance(trace_payload, dict) else {}
    assumptions_summary = ""
    if isinstance(assumptions_payload, dict):
        assumptions_summary = str(assumptions_payload.get("summary_text") or "").strip()

    results = [
        {
            "#": 1,
            "验收项": "基础通路",
            "检查结果": STATUS_PASS if rows else STATUS_FAIL,
            "备注": f"rows={len(rows)}",
        },
        {
            "#": 2,
            "验收项": "正常路径存在买/卖事件",
            "检查结果": STATUS_PASS if _has_action(rows, "买", "buy", "卖", "sell") else STATUS_WARN,
            "备注": "found buy/sell" if _has_action(rows, "买", "buy", "卖", "sell") else "missing buy/sell",
        },
        {
            "#": 3,
            "验收项": "现金不足场景存在 skip 事件",
            "检查结果": STATUS_PASS if _has_action(rows, "skip", "跳过") else STATUS_WARN,
            "备注": (
                f"skip={sum(1 for row in rows if str(row.get('动作') or row.get('action') or '').strip().lower() in {'skip', '跳过'})}"
            ),
        },
        {
            "#": 4,
            "验收项": "assumptions/defaults 可追溯",
            "检查结果": STATUS_PASS if assumptions_summary or all(str(row.get("assumptions") or "").strip() for row in rows) else STATUS_FAIL,
            "备注": assumptions_summary or "rows-carry-assumptions",
        },
        {
            "#": 5,
            "验收项": "fallback 标记",
            "检查结果": STATUS_PASS if all("fallback" in row for row in rows) else STATUS_FAIL,
            "备注": f"rows={len(rows)}",
        },
        {
            "#": 6,
            "验收项": "资产/现金/持仓一致性",
            "检查结果": STATUS_PASS if _assets_consistent(rows) else STATUS_FAIL,
            "备注": "ok" if _assets_consistent(rows) else "total_assets != cash + holdings",
        },
        {
            "#": 7,
            "验收项": "CSV/JSON 列完整",
            "检查结果": STATUS_PASS if rows and all(column in rows[0] for column in TRACE_REQUIRED_COLUMNS) and bool(trace_rows) else STATUS_FAIL,
            "备注": "csv/json columns present" if rows and trace_rows else "missing csv/json columns",
        },
    ]
    return results


def summarize_acceptance_reports(report_map: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    ordered_items: List[str] = []
    grouped: Dict[str, List[tuple[str, Dict[str, Any]]]] = {}
    for scenario, rows in report_map.items():
        for row in rows:
            item = str(row.get("验收项") or "").strip()
            if not item:
                continue
            if item not in grouped:
                grouped[item] = []
                ordered_items.append(item)
            grouped[item].append((scenario, row))

    priority = {STATUS_FAIL: 2, STATUS_WARN: 1, STATUS_PASS: 0}
    summary_rows: List[Dict[str, Any]] = []
    for index, item in enumerate(ordered_items, start=1):
        scenario_rows = grouped[item]
        worst_status = STATUS_PASS
        for _, row in scenario_rows:
            status = str(row.get("检查结果") or STATUS_PASS)
            if priority.get(status, 2) > priority.get(worst_status, 2):
                worst_status = status
        remarks = "；".join(
            f"{scenario}: {row.get('备注') or row.get('检查结果')}"
            for scenario, row in scenario_rows
        )
        summary_rows.append(
            {
                "#": index,
                "验收项": item,
                "检查结果": worst_status,
                "备注": remarks,
            }
        )
    return summary_rows


def write_acceptance_report(report_rows: List[Dict[str, Any]], *, csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(report_rows)

    json_path.write_text(json.dumps(report_rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json_payload(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
