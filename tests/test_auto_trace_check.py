# -*- coding: utf-8 -*-
"""Tests for execution trace acceptance checker."""

import csv
import json
import os
import tempfile
import unittest

import auto_trace_check


class AutoTraceCheckTestCase(unittest.TestCase):
    def test_run_acceptance_checks_reports_expected_statuses(self) -> None:
        rows = [
            {
                "日期": "2024-01-05",
                "标的收盘价": "10.0",
                "基准收盘价": "10.0",
                "信号摘要": "买入",
                "动作": "买",
                "成交价": "10.0",
                "持股数": "100",
                "现金": "500.0",
                "持仓市值": "1000.0",
                "总资产": "1500.0",
                "当日盈亏": "0.0",
                "当日收益率": "0.0",
                "策略累计收益率": "0.0",
                "基准累计收益率": "0.0",
                "买入持有累计收益率": "0.0",
                "仓位": "0.666667",
                "手续费": "0.0",
                "滑点": "0.0",
                "备注": "ok",
                "fallback": "否",
                "assumptions": "默认/推断 2 项；执行假设已记录",
            },
            {
                "日期": "2024-01-06",
                "标的收盘价": "10.0",
                "基准收盘价": "10.0",
                "信号摘要": "现金不足",
                "动作": "skip",
                "成交价": "10.0",
                "持股数": "100",
                "现金": "500.0",
                "持仓市值": "1000.0",
                "总资产": "1500.0",
                "当日盈亏": "0.0",
                "当日收益率": "0.0",
                "策略累计收益率": "0.0",
                "基准累计收益率": "0.0",
                "买入持有累计收益率": "0.0",
                "仓位": "0.666667",
                "手续费": "0.0",
                "滑点": "0.0",
                "备注": "ok",
                "fallback": "是",
                "assumptions": "默认/推断 2 项；执行假设已记录",
            },
        ]

        report = auto_trace_check.run_acceptance_checks(rows, trace_payload={"assumptions": {"summary_text": "ok"}, "trace_rows": rows})
        self.assertEqual(report[0]["检查结果"], auto_trace_check.STATUS_PASS)
        self.assertEqual(report[1]["检查结果"], auto_trace_check.STATUS_PASS)
        self.assertEqual(report[2]["检查结果"], auto_trace_check.STATUS_PASS)
        self.assertEqual(report[3]["检查结果"], auto_trace_check.STATUS_PASS)
        self.assertEqual(report[4]["检查结果"], auto_trace_check.STATUS_PASS)
        self.assertEqual(report[5]["检查结果"], auto_trace_check.STATUS_PASS)
        self.assertEqual(report[6]["检查结果"], auto_trace_check.STATUS_PASS)

    def test_summarize_acceptance_reports_aggregates_statuses(self) -> None:
        report_map = {
            "normal_path": [
                {"#": 1, "验收项": "正常路径存在买/卖事件", "检查结果": auto_trace_check.STATUS_PASS, "备注": "ok"},
                {"#": 2, "验收项": "现金不足场景存在 skip 事件", "检查结果": auto_trace_check.STATUS_WARN, "备注": "skip=0"},
            ],
            "cash_insufficiency_skip": [
                {"#": 1, "验收项": "正常路径存在买/卖事件", "检查结果": auto_trace_check.STATUS_PASS, "备注": "ok"},
                {"#": 2, "验收项": "现金不足场景存在 skip 事件", "检查结果": auto_trace_check.STATUS_PASS, "备注": "skip=3"},
            ],
        }
        summary = auto_trace_check.summarize_acceptance_reports(report_map)
        self.assertEqual(summary[0]["检查结果"], auto_trace_check.STATUS_PASS)
        self.assertEqual(summary[1]["检查结果"], auto_trace_check.STATUS_WARN)
        self.assertIn("normal_path", summary[0]["备注"])

    def test_write_acceptance_report_outputs_csv_and_json(self) -> None:
        report_rows = [
            {"#": 1, "验收项": "正常路径存在买/卖事件", "检查结果": auto_trace_check.STATUS_PASS, "备注": "ok"},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = os.path.join(temp_dir, "acceptance.csv")
            json_path = os.path.join(temp_dir, "acceptance.json")
            auto_trace_check.write_acceptance_report(
                report_rows,
                csv_path=auto_trace_check.Path(csv_path),
                json_path=auto_trace_check.Path(json_path),
            )

            with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["检查结果"], auto_trace_check.STATUS_PASS)

            with open(json_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload[0]["备注"], "ok")


if __name__ == "__main__":
    unittest.main()
