# -*- coding: utf-8 -*-
"""Tests for extension metadata on generic task queue work."""

from __future__ import annotations

import pytest
from concurrent.futures import Future

from src.services.task_queue import AnalysisTaskQueue, TaskStatus


class _PendingExecutor:
    def submit(self, *args, **kwargs):
        return Future()

    def shutdown(self, wait=True, cancel_futures=False):
        return None


class _SyncExecutor:
    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future

    def shutdown(self, wait=True, cancel_futures=False):
        return None


@pytest.fixture
def queue():
    original_instance = AnalysisTaskQueue._instance
    AnalysisTaskQueue._instance = None
    current = AnalysisTaskQueue(max_workers=1)
    try:
        yield current
    finally:
        executor = getattr(current, "_executor", None)
        if executor is not None and hasattr(executor, "shutdown"):
            executor.shutdown(wait=False, cancel_futures=True)
        AnalysisTaskQueue._instance = original_instance


def test_background_task_carries_extension_metadata(queue):
    queue._executor = _PendingExecutor()

    task = queue.submit_background_task(
        lambda: {"ok": True},
        stock_code="extension",
        task_type="extension",
        plugin_id="alphasift",
        action_id="alphasift.screen",
        run_id="run_123",
        subject="cn-market",
        dedupe_key="alphasift.screen:hash",
    )

    assert task.task_type == "extension"
    assert task.plugin_id == "alphasift"
    assert task.action_id == "alphasift.screen"
    assert task.run_id == "run_123"
    assert task.subject == "cn-market"
    assert task.dedupe_key == "alphasift.screen:hash"
    payload = task.to_dict()
    assert payload["task_type"] == "extension"
    assert payload["plugin_id"] == "alphasift"
    assert payload["action_id"] == "alphasift.screen"
    assert payload["run_id"] == "run_123"
    assert payload["subject"] == "cn-market"
    assert payload["dedupe_key"] == "alphasift.screen:hash"


def test_background_dedupe_rejects_duplicate_without_affecting_stock_dedupe(queue):
    queue._executor = _PendingExecutor()

    background = queue.submit_background_task(
        lambda: {"ok": True},
        stock_code="extension",
        task_type="extension",
        action_id="alphasift.screen",
        dedupe_key="600519",
    )
    accepted, duplicates = queue.submit_tasks_batch(["600519"], report_type="detailed")

    assert background.task_id != accepted[0].task_id
    assert len(accepted) == 1
    assert duplicates == []
    assert queue.get_analyzing_task_id("600519") == accepted[0].task_id

    with pytest.raises(ValueError, match="后台任务已存在: 600519"):
        queue.submit_background_task(
            lambda: {"ok": True},
            stock_code="extension",
            task_type="extension",
            dedupe_key="600519",
        )


def test_background_dedupe_key_is_released_on_completion(queue):
    queue._executor = _SyncExecutor()

    first = queue.submit_background_task(
        lambda: {"ok": True},
        stock_code="extension",
        task_type="extension",
        dedupe_key="alphasift.screen:hash",
    )
    second = queue.submit_background_task(
        lambda: {"ok": True},
        stock_code="extension",
        task_type="extension",
        dedupe_key="alphasift.screen:hash",
    )

    assert queue.get_task(first.task_id).status == TaskStatus.COMPLETED
    assert queue.get_task(second.task_id).status == TaskStatus.COMPLETED
