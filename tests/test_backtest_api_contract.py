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
    parse_rule_strategy,
    get_rule_backtest_run,
    run_rule_backtest,
)
from api.v1.schemas.backtest import (  # noqa: E402
    BacktestCodeRequest,
    RuleBacktestParseRequest,
    RuleBacktestParseResponse,
    RuleBacktestRunRequest,
    RuleBacktestRunResponse,
)


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
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "period_start": "2025-01-01",
            "period_end": "2025-12-31",
            "lookback_bars": 20,
            "initial_capital": 100000.0,
            "fee_bps": 0.0,
            "slippage_bps": 0.0,
            "status": status,
            "status_history": [{"status": status, "at": "2024-01-01T00:00:00"}],
            "annualized_return_pct": 0.0,
            "benchmark_mode": "auto",
            "benchmark_code": None,
            "benchmark_return_pct": None,
            "excess_return_vs_benchmark_pct": None,
            "buy_and_hold_return_pct": 0.0,
            "excess_return_vs_buy_and_hold_pct": 0.0,
            "summary": {},
            "execution_model": {
                "version": "v1",
                "timeframe": "daily",
                "signal_evaluation_timing": "bar_close",
                "entry_timing": "next_bar_open",
                "exit_timing": "next_bar_open",
                "entry_fill_price_basis": "open",
                "exit_fill_price_basis": "open",
                "position_sizing": "single_position_full_notional",
                "fee_model": "bps_per_side",
                "fee_bps_per_side": 0.0,
                "slippage_model": "bps_per_side",
                "slippage_bps_per_side": 0.0,
                "market_rules": {
                    "trading_day_execution": "available_bars_only",
                    "terminal_bar_fill_fallback": "same_bar_close",
                    "window_end_position_handling": "force_flatten",
                },
            },
            "execution_assumptions": {},
            "benchmark_curve": [],
            "benchmark_summary": {"method": "same_symbol_buy_and_hold", "resolved_mode": "same_symbol_buy_and_hold"},
            "buy_and_hold_curve": [],
            "buy_and_hold_summary": {"method": "same_symbol_buy_and_hold", "resolved_mode": "same_symbol_buy_and_hold"},
            "audit_rows": [],
            "daily_return_series": [],
            "exposure_curve": [],
            "equity_curve": [],
            "trades": [],
        }

    def test_run_rule_backtest_async_path_enqueues_background_processing(self) -> None:
        request = RuleBacktestRunRequest(
            code="600519",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            start_date="2025-01-01",
            end_date="2025-12-31",
            benchmark_mode="index_hs300",
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
        self.assertEqual(service.submit_backtest.call_args.kwargs["start_date"], "2025-01-01")
        self.assertEqual(service.submit_backtest.call_args.kwargs["end_date"], "2025-12-31")
        self.assertEqual(service.submit_backtest.call_args.kwargs["benchmark_mode"], "index_hs300")
        service.run_backtest.assert_not_called()
        self.assertEqual(len(background_tasks.tasks), 1)

    def test_run_rule_backtest_wait_mode_executes_inline(self) -> None:
        request = RuleBacktestRunRequest(
            code="600519",
            strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
            start_date="2025-01-01",
            end_date="2025-12-31",
            benchmark_mode="custom_code",
            benchmark_code="SPY",
            wait_for_completion=True,
            confirmed=True,
        )
        background_tasks = BackgroundTasks()
        service = MagicMock()
        service.run_backtest.return_value = self._rule_run_payload(status="completed")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = run_rule_backtest(request, background_tasks, db_manager=MagicMock())

        self.assertEqual(response.status, "completed")
        self.assertEqual(response.benchmark_summary["method"], "same_symbol_buy_and_hold")
        self.assertEqual(response.execution_model.entry_timing, "next_bar_open")
        service.run_backtest.assert_called_once()
        self.assertEqual(service.run_backtest.call_args.kwargs["start_date"], "2025-01-01")
        self.assertEqual(service.run_backtest.call_args.kwargs["end_date"], "2025-12-31")
        self.assertEqual(service.run_backtest.call_args.kwargs["benchmark_mode"], "custom_code")
        self.assertEqual(service.run_backtest.call_args.kwargs["benchmark_code"], "SPY")
        service.submit_backtest.assert_not_called()
        self.assertEqual(len(background_tasks.tasks), 0)

    def test_run_rule_backtest_request_keeps_legacy_setup_backed_parsed_strategy_payload(self) -> None:
        request = RuleBacktestRunRequest(
            code="AAPL",
            strategy_text="MACD金叉买入，死叉卖出",
            parsed_strategy={
                "strategy_kind": "macd_crossover",
                "setup": {
                    "symbol": "AAPL",
                    "indicator_family": "macd",
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                },
                "strategy_spec": {},
            },
            start_date="2025-01-01",
            end_date="2025-12-31",
            wait_for_completion=True,
            confirmed=True,
        )
        background_tasks = BackgroundTasks()
        service = MagicMock()
        service.run_backtest.return_value = self._rule_run_payload(status="completed")

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            run_rule_backtest(request, background_tasks, db_manager=MagicMock())

        self.assertEqual(service.run_backtest.call_args.kwargs["parsed_strategy"]["setup"]["indicator_family"], "macd")
        self.assertEqual(service.run_backtest.call_args.kwargs["parsed_strategy"]["strategy_spec"], {})

    def test_get_rule_backtest_run_serializes_canonical_audit_rows_field(self) -> None:
        service = MagicMock()
        service.get_run.return_value = self._rule_run_payload(status="completed")
        service.get_run.return_value["parsed_strategy"] = {
            "strategy_kind": "macd_crossover",
            "strategy_spec": {
                "version": "v1",
                "strategy_type": "macd_crossover",
                "strategy_family": "macd_crossover",
                "symbol": "AAPL",
                "timeframe": "daily",
                "max_lookback": 35,
                "date_range": {"start_date": "2025-01-01", "end_date": "2025-12-31"},
                "capital": {"initial_capital": 100000.0, "currency": "USD"},
                "costs": {"fee_bps": 0.0, "slippage_bps": 0.0},
                "signal": {
                    "indicator_family": "macd",
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                    "entry_condition": "macd_crosses_above_signal",
                    "exit_condition": "macd_crosses_below_signal",
                },
                "execution": {
                    "frequency": "daily",
                    "signal_timing": "bar_close",
                    "fill_timing": "next_bar_open",
                },
                "position_behavior": {
                    "direction": "long_only",
                    "entry_sizing": "all_in",
                    "max_positions": 1,
                    "pyramiding": False,
                },
                "end_behavior": {"policy": "liquidate_at_end", "price_basis": "close"},
                "support": {
                    "executable": True,
                    "normalization_state": "assumed",
                    "requires_confirmation": False,
                    "unsupported_reason": None,
                    "detected_strategy_family": "macd_crossover",
                },
            },
        }
        service.get_run.return_value["audit_rows"] = [
            {
                "date": "2025-01-02",
                "symbol_close": 101.0,
                "benchmark_close": 202.0,
                "position": 1.0,
                "shares": 100.0,
                "cash": 0.0,
                "holdings_value": 10100.0,
                "total_portfolio_value": 10100.0,
                "daily_pnl": 100.0,
                "daily_return": 1.0,
                "cumulative_return": 1.0,
                "benchmark_cumulative_return": 0.5,
                "buy_hold_cumulative_return": 0.75,
                "action": "hold",
                "fill_price": None,
            }
        ]

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = get_rule_backtest_run(123, db_manager=MagicMock())

        payload = response.model_dump(by_alias=True)
        self.assertIn("auditRows", payload)
        self.assertNotIn("audit_rows", payload)
        self.assertEqual(len(payload["auditRows"]), 1)
        self.assertEqual(payload["auditRows"][0]["symbol_close"], 101.0)
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["strategy_type"], "macd_crossover")
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["signal"]["signal_period"], 9)
        self.assertNotIn("unexpected_field", payload["parsed_strategy"]["strategy_spec"])

    def test_get_rule_backtest_run_returns_404_not_found_contract(self) -> None:
        service = MagicMock()
        service.get_run.return_value = None

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_rule_backtest_run(123, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")

    def test_rule_backtest_run_response_uses_supported_family_strategy_spec_contract(self) -> None:
        response = RuleBacktestRunResponse(
            **{
                **self._rule_run_payload(status="completed"),
                "parsed_strategy": {
                    "strategy_kind": "periodic_accumulation",
                    "strategy_spec": {
                        "version": "v1",
                        "strategy_type": "periodic_accumulation",
                        "strategy_family": "periodic_accumulation",
                        "symbol": "ORCL",
                        "timeframe": "daily",
                        "max_lookback": 1,
                        "date_range": {"start_date": "2025-01-01", "end_date": "2025-12-31"},
                        "capital": {"initial_capital": 100000.0, "currency": "USD"},
                        "costs": {"fee_bps": 0.0, "slippage_bps": 0.0},
                        "schedule": {"frequency": "daily", "timing": "session_open"},
                        "entry": {
                            "side": "buy",
                            "order": {"mode": "fixed_shares", "quantity": 100.0, "amount": None},
                            "price_basis": "open",
                        },
                        "exit": {"policy": "close_at_end", "price_basis": "close"},
                        "position_behavior": {"accumulate": True, "cash_policy": "stop_when_insufficient_cash"},
                        "support": {
                            "executable": True,
                            "normalization_state": "assumed",
                            "requires_confirmation": True,
                            "unsupported_reason": None,
                            "detected_strategy_family": "periodic_accumulation",
                        },
                        "unexpected_field": "drop_me",
                    },
                },
            }
        )

        payload = response.model_dump()
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["strategy_type"], "periodic_accumulation")
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["entry"]["order"]["mode"], "fixed_shares")
        self.assertNotIn("unexpected_field", payload["parsed_strategy"]["strategy_spec"])

    def test_parse_rule_strategy_returns_normalization_metadata(self) -> None:
        request = RuleBacktestParseRequest(
            code="AAPL",
            strategy_text="MACD金叉买入，死叉卖出",
            start_date="2025-01-01",
            end_date="2025-12-31",
            initial_capital=100000,
        )
        service = MagicMock()
        service.parse_strategy.return_value = {
            "strategy_kind": "macd_crossover",
            "strategy_spec": {"strategy_type": "macd_crossover", "symbol": "AAPL"},
            "confidence": 0.96,
            "needs_confirmation": True,
            "ambiguities": [],
            "summary": {"entry": "买入条件：MACD(12,26,9) 金叉", "exit": "卖出条件：MACD(12,26,9) 死叉"},
            "max_lookback": 35,
            "executable": True,
            "normalization_state": "assumed",
            "assumptions": [{"key": "macd_periods", "value": "12,26,9"}],
            "assumption_groups": [{"key": "indicator_defaults", "label": "指标默认值", "items": [{"key": "macd_periods"}]}],
            "detected_strategy_family": "macd_crossover",
            "unsupported_reason": None,
            "unsupported_details": [],
            "unsupported_extensions": [],
            "core_intent_summary": "已识别为 MACD 金叉 / 死叉主规则。",
            "interpretation_confidence": 0.96,
            "supported_portion_summary": "已识别为 MACD 金叉 / 死叉主规则。",
            "rewrite_suggestions": [],
            "parse_warnings": [],
        }

        with patch("api.v1.endpoints.backtest.RuleBacktestService", return_value=service):
            response = parse_rule_strategy(request, db_manager=MagicMock())

        self.assertEqual(response.normalized_strategy_family, "macd_crossover")
        self.assertEqual(response.detected_strategy_family, "macd_crossover")
        self.assertTrue(response.executable)
        self.assertEqual(response.normalization_state, "assumed")
        self.assertEqual(len(response.assumptions), 1)
        self.assertEqual(len(response.assumption_groups), 1)
        self.assertEqual(response.core_intent_summary, "已识别为 MACD 金叉 / 死叉主规则。")
        self.assertEqual(response.interpretation_confidence, 0.96)
        self.assertEqual(response.supported_portion_summary, "已识别为 MACD 金叉 / 死叉主规则。")
        service.parse_strategy.assert_called_once()
        self.assertEqual(service.parse_strategy.call_args.kwargs["start_date"], "2025-01-01")
        self.assertEqual(service.parse_strategy.call_args.kwargs["end_date"], "2025-12-31")

    def test_parse_response_uses_supported_family_strategy_spec_contract(self) -> None:
        response = RuleBacktestParseResponse(
            code="AAPL",
            strategy_text="RSI 小于 30 买入，大于 70 卖出",
            parsed_strategy={
                "strategy_kind": "rsi_threshold",
                "strategy_spec": {
                    "version": "v1",
                    "strategy_type": "rsi_threshold",
                    "strategy_family": "rsi_threshold",
                    "symbol": "AAPL",
                    "timeframe": "daily",
                    "max_lookback": 14,
                    "date_range": {"start_date": "2025-01-01", "end_date": "2025-12-31"},
                    "capital": {"initial_capital": 100000.0, "currency": "USD"},
                    "costs": {"fee_bps": 0.0, "slippage_bps": 0.0},
                    "signal": {
                        "indicator_family": "rsi",
                        "period": 14,
                        "lower_threshold": 30.0,
                        "upper_threshold": 70.0,
                        "entry_condition": "rsi_crosses_below_lower_threshold",
                        "exit_condition": "rsi_crosses_above_upper_threshold",
                    },
                    "execution": {
                        "frequency": "daily",
                        "signal_timing": "bar_close",
                        "fill_timing": "next_bar_open",
                    },
                    "position_behavior": {
                        "direction": "long_only",
                        "entry_sizing": "all_in",
                        "max_positions": 1,
                        "pyramiding": False,
                    },
                    "end_behavior": {"policy": "liquidate_at_end", "price_basis": "close"},
                    "support": {
                        "executable": True,
                        "normalization_state": "assumed",
                        "requires_confirmation": False,
                        "unsupported_reason": None,
                        "detected_strategy_family": "rsi_threshold",
                    },
                    "unexpected_field": "drop_me",
                },
            },
            normalized_strategy_family="rsi_threshold",
            detected_strategy_family="rsi_threshold",
            executable=True,
            normalization_state="assumed",
        )

        payload = response.model_dump()
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["strategy_type"], "rsi_threshold")
        self.assertEqual(payload["parsed_strategy"]["strategy_spec"]["signal"]["period"], 14)
        self.assertNotIn("unexpected_field", payload["parsed_strategy"]["strategy_spec"])

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
