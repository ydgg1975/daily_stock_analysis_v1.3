# -*- coding: utf-8 -*-
"""Regression tests for backtest endpoint contracts."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi import BackgroundTasks, HTTPException

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from api.v1.endpoints.backtest import (  # noqa: E402
    clear_backtest_samples,
    get_rule_backtest_run,
    run_rule_backtest,
)
from api.v1.schemas.backtest import BacktestCodeRequest, RuleBacktestRunRequest  # noqa: E402


class BacktestApiContractTestCase(unittest.TestCase):
    @staticmethod
    def _rule_run_payload(*, run_id: int = 123, status: str = "queued") -> dict:
        return {
            "id": run_id,
            "code": "600519",
            "strategy_text": "Buy when Close > MA3. Sell when Close < MA3.",
            "parsed_strategy": {},
            "strategy_hash": "abc123",
            "timeframe": "daily",
            "lookback_bars": 20,
            "initial_capital": 100000.0,
            "fee_bps": 0.0,
            "slippage_bps": 0.0,
            "status": status,
            "status_history": [{"status": status, "at": "2024-01-01T00:00:00"}],
            "summary": {},
            "execution_assumptions": {},
            "equity_curve": [],
            "trades": [],
        }

    def test_run_rule_backtest_async_path_enqueues_background_processing(self) -> None:
        request = RuleBacktestRunRequest(
            code="600519",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            wait_for_completion=False,
            confirmed=True,
        )
        background_tasks = BackgroundTasks()
        service = MagicMock()
        service.submit_backtest.return_value = self._rule_run_payload(status="queued")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = run_rule_backtest(request, background_tasks, db_manager=MagicMock())

        self.assertEqual(response.id, 123)
        service.submit_backtest.assert_called_once()
        service.run_backtest.assert_not_called()
        self.assertEqual(len(background_tasks.tasks), 1)

    def test_run_rule_backtest_wait_mode_executes_inline(self) -> None:
        request = RuleBacktestRunRequest(
            code="600519",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            wait_for_completion=True,
            confirmed=True,
        )
        background_tasks = BackgroundTasks()
        service = MagicMock()
        service.run_backtest.return_value = self._rule_run_payload(status="completed")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = run_rule_backtest(request, background_tasks, db_manager=MagicMock())

        self.assertEqual(response.status, "completed")
        service.run_backtest.assert_called_once()
        service.submit_backtest.assert_not_called()
        self.assertEqual(len(background_tasks.tasks), 0)

    def test_get_rule_backtest_run_returns_404_not_found_contract(self) -> None:
        service = MagicMock()
        service.get_run.return_value = None

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_rule_backtest_run(123, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")

    def test_clear_backtest_samples_maps_value_error_to_validation_error(self) -> None:
        service = MagicMock()
        service.clear_backtest_samples.side_effect = ValueError("code is required")

        with patch("api.v1.endpoints.backtest.BacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                clear_backtest_samples(BacktestCodeRequest(code=""), db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["error"], "validation_error")
        self.assertEqual(ctx.exception.detail["message"], "code is required")


if __name__ == "__main__":
    unittest.main()
