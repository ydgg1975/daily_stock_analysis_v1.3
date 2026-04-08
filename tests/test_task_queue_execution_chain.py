# -*- coding: utf-8 -*-
"""Focused regression tests for task queue execution-chain ownership."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.services.task_queue import AnalysisTaskQueue, TaskInfo, TaskStatus, _dedupe_stock_code_key


class TaskQueueExecutionChainTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._original_instance = AnalysisTaskQueue._instance
        AnalysisTaskQueue._instance = None
        self._execution_log_service = MagicMock()
        self._execution_log_service.start_session.return_value = "session-1"
        self._execution_log_patcher = patch(
            "src.services.task_queue.ExecutionLogService",
            return_value=self._execution_log_service,
        )
        self._execution_log_patcher.start()

    def tearDown(self) -> None:
        self._execution_log_patcher.stop()
        queue = AnalysisTaskQueue._instance
        if queue is not None and queue is not self._original_instance:
            executor = getattr(queue, "_executor", None)
            if executor is not None and hasattr(executor, "shutdown"):
                executor.shutdown(wait=False)
        AnalysisTaskQueue._instance = self._original_instance

    def test_execute_task_uses_top_level_result_artifacts_for_completion(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)
        queue._broadcast_event = MagicMock()

        task_id = "task-1"
        stock_code = "600519"
        queue._tasks[task_id] = TaskInfo(task_id=task_id, stock_code=stock_code)
        queue._analyzing_stocks[_dedupe_stock_code_key(stock_code)] = task_id

        normalized_result = {
            "stock_code": stock_code,
            "stock_name": "贵州茅台",
            "query_id": "query-top-level",
            "runtime_execution": {"steps": [{"key": "notification", "status": "ok"}]},
            "notification_result": {"attempted": True, "status": "ok", "success": True},
            "report": {"meta": {"query_id": "query-from-nested-report"}},
        }

        with patch("src.services.analysis_service.AnalysisService") as service_cls:
            service_cls.return_value.analyze_stock.return_value = normalized_result
            result = queue._execute_task(
                task_id=task_id,
                stock_code=stock_code,
                report_type="detailed",
                force_refresh=False,
            )

        self.assertEqual(result, normalized_result)
        task = queue._tasks[task_id]
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.stock_name, "贵州茅台")
        self.assertEqual(task.execution, normalized_result["runtime_execution"])
        self.assertNotIn(_dedupe_stock_code_key(stock_code), queue._analyzing_stocks)
        self._execution_log_service.append_runtime_result.assert_called_once_with(
            session_id="session-1",
            runtime_execution=normalized_result["runtime_execution"],
            notification_result=normalized_result["notification_result"],
            query_id="query-top-level",
            overall_status="completed",
        )


if __name__ == "__main__":
    unittest.main()
