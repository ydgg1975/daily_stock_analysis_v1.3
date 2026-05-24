# -*- coding: utf-8 -*-
"""Tests for built-in DSA core actions used by extension workflows."""

from __future__ import annotations

from types import SimpleNamespace

from src.extensions import ActionContext, ExtensionRuntime, ExtensionStatus
from src.extensions.builtin.dsa import build_dsa_core_actions
from src.extensions.catalog import ExtensionCatalog


def _action(actions, action_id: str):
    return next(action for action in actions if action.id == action_id)


def test_dsa_core_actions_are_internal_and_registered():
    actions = build_dsa_core_actions()

    assert _action(actions, "dsa.analyze_stock").metadata["internal"] is True
    assert _action(actions, "stock_pool.import").supported_callers == ["system"]


def test_dsa_analyze_stock_action_submits_batch(monkeypatch):
    submitted = {}

    class FakeTaskQueue:
        def submit_tasks_batch(self, stock_codes, **kwargs):
            submitted["stock_codes"] = stock_codes
            submitted["kwargs"] = kwargs
            return [
                SimpleNamespace(
                    task_id="task-1",
                    stock_code=stock_codes[0],
                    report_type=kwargs["report_type"],
                    to_dict=lambda: {
                        "task_id": "task-1",
                        "stock_code": stock_codes[0],
                        "report_type": kwargs["report_type"],
                    },
                )
            ], []

    monkeypatch.setattr("src.services.task_queue.get_task_queue", lambda: FakeTaskQueue())

    catalog = ExtensionCatalog()
    catalog.register(_action(build_dsa_core_actions(), "dsa.analyze_stock"))
    runtime = ExtensionRuntime(catalog)

    result = runtime.execute(
        "dsa.analyze_stock",
        {"stock_codes": ["600519", "600519.SH"], "report_type": "detailed"},
        context=ActionContext(
            action_id="dsa.analyze_stock",
            input={"stock_codes": ["600519", "600519.SH"], "report_type": "detailed"},
            caller="system",
        ),
    )

    assert result.status == ExtensionStatus.COMPLETED.value
    assert submitted["stock_codes"] == ["600519", "600519.SH"]
    assert result.result["tasks"][0]["task_id"] == "task-1"


def test_dsa_analyze_stock_respects_max_items_budget():
    catalog = ExtensionCatalog()
    catalog.register(_action(build_dsa_core_actions(), "dsa.analyze_stock"))
    runtime = ExtensionRuntime(catalog)

    result = runtime.execute(
        "dsa.analyze_stock",
        {"stock_codes": ["600519", "000001"]},
        context=ActionContext(
            action_id="dsa.analyze_stock",
            input={"stock_codes": ["600519", "000001"]},
            caller="system",
            budget={"max_items": 1},
        ),
    )

    assert result.status == ExtensionStatus.FAILED.value
    assert result.error_code == "E_BUDGET_EXCEEDED"
