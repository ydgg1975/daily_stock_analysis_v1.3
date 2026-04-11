# -*- coding: utf-8 -*-
"""Tests for AI-assisted rule backtesting."""

import csv
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from src.config import Config
from src.core.rule_backtest_engine import RuleBacktestEngine, RuleBacktestParser
from src.services.rule_backtest_service import RuleBacktestService, run_backtest_automated
from src.storage import DatabaseManager, StockDaily


class RuleBacktestTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_rule_backtest.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

        with self.db.get_session() as session:
            closes = [10, 10.2, 10.1, 10.5, 11.0, 11.6, 11.8, 11.2, 10.8, 10.2, 9.9, 10.3, 10.9, 11.4, 11.9, 12.1, 11.7, 11.1, 10.7, 10.4, 10.8, 11.3, 11.8, 12.2]
            for index, close in enumerate(closes):
                session.add(
                    StockDaily(
                        code="600519",
                        date=date(2024, 1, 1).fromordinal(date(2024, 1, 1).toordinal() + index),
                        open=close - 0.1,
                        high=close + 0.2,
                        low=close - 0.3,
                        close=float(close),
                    )
                )
            session.commit()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    @staticmethod
    def _make_bars(closes: list[float], *, start: date = date(2024, 1, 1)) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                code="TEST",
                date=start + timedelta(days=index),
                open=float(close) - 0.1,
                high=float(close) + 0.2,
                low=max(0.01, float(close) - 0.3),
                close=float(close),
            )
            for index, close in enumerate(closes)
        ]

    def test_parse_simple_ma_rsi_strategy(self) -> None:
        parser = RuleBacktestParser()
        parsed = parser.parse("Buy when MA5 > MA20 and RSI6 < 40. Sell when MA5 < MA20 or RSI6 > 70.")

        self.assertEqual(parsed.timeframe, "daily")
        self.assertFalse(parsed.needs_confirmation)
        self.assertGreater(parsed.confidence, 0.9)
        self.assertEqual(parsed.summary["entry"], "买入条件：MA5 > MA20 且 RSI6 < 40")
        self.assertEqual(parsed.summary["exit"], "卖出条件：MA5 < MA20 或 RSI6 > 70")

    def test_parse_typo_ris6_suggests_rsi6(self) -> None:
        parser = RuleBacktestParser()
        parsed = parser.parse("Buy when MA5 > MA20 and RIS6 < 40. Sell when MA5 < MA20 or RSI6 > 70.")

        self.assertTrue(parsed.needs_confirmation)
        self.assertTrue(any("RSI6" in str(item.get("suggestion", "")) for item in parsed.ambiguities))

    def test_parse_chinese_periodic_buy_instruction_into_structured_draft(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy("资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止")

        self.assertEqual(parsed["strategy_kind"], "periodic_accumulation")
        self.assertEqual(parsed["strategy_spec"]["strategy_type"], "periodic_accumulation")
        self.assertEqual(parsed["strategy_spec"]["strategy_family"], "periodic_accumulation")
        self.assertEqual(parsed["strategy_spec"]["symbol"], "ORCL")
        self.assertEqual(parsed["strategy_spec"]["date_range"]["start_date"], "2025-01-01")
        self.assertEqual(parsed["strategy_spec"]["date_range"]["end_date"], "2025-12-31")
        self.assertEqual(parsed["strategy_spec"]["capital"]["initial_capital"], 100000.0)
        self.assertEqual(parsed["strategy_spec"]["schedule"]["frequency"], "daily")
        self.assertEqual(parsed["strategy_spec"]["entry"]["order"]["mode"], "fixed_shares")
        self.assertEqual(parsed["strategy_spec"]["entry"]["order"]["quantity"], 100.0)
        self.assertEqual(parsed["strategy_spec"]["position_behavior"]["cash_policy"], "stop_when_insufficient_cash")
        self.assertEqual(parsed["strategy_spec"]["entry"]["price_basis"], "open")
        self.assertTrue(parsed["strategy_spec"]["support"]["executable"])
        self.assertTrue(parsed["needs_confirmation"])

    def test_normalize_moving_average_crossover_strategy_spec(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "5日均线上穿20日均线买入，下穿卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertEqual(parsed["strategy_kind"], "moving_average_crossover")
        self.assertEqual(parsed["strategy_spec"]["strategy_type"], "moving_average_crossover")
        self.assertEqual(parsed["strategy_spec"]["signal"]["indicator_family"], "moving_average")
        self.assertEqual(parsed["strategy_spec"]["signal"]["fast_period"], 5)
        self.assertEqual(parsed["strategy_spec"]["signal"]["slow_period"], 20)
        self.assertEqual(parsed["strategy_spec"]["signal"]["fast_type"], "simple")
        self.assertEqual(parsed["strategy_spec"]["signal"]["entry_condition"], "fast_crosses_above_slow")
        self.assertEqual(parsed["strategy_spec"]["execution"]["signal_timing"], "bar_close")
        self.assertEqual(parsed["strategy_spec"]["execution"]["fill_timing"], "next_bar_open")
        self.assertTrue(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "assumed")
        self.assertTrue(any(item.get("key") == "fast_type" for item in parsed["assumptions"]))

    def test_normalize_macd_crossover_strategy_spec(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "MACD金叉买入，死叉卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertEqual(parsed["strategy_kind"], "macd_crossover")
        self.assertEqual(parsed["strategy_spec"]["strategy_type"], "macd_crossover")
        self.assertEqual(parsed["strategy_spec"]["signal"]["indicator_family"], "macd")
        self.assertEqual(parsed["strategy_spec"]["signal"]["fast_period"], 12)
        self.assertEqual(parsed["strategy_spec"]["signal"]["slow_period"], 26)
        self.assertEqual(parsed["strategy_spec"]["signal"]["signal_period"], 9)
        self.assertTrue(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "assumed")
        self.assertTrue(any(item.get("key") == "macd_periods" for item in parsed["assumptions"]))
        self.assertTrue(any(group.get("key") == "indicator_defaults" for group in parsed["assumption_groups"]))

    def test_normalize_rsi_threshold_strategy_spec(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "RSI 小于 30 买入，大于 70 卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertEqual(parsed["strategy_kind"], "rsi_threshold")
        self.assertEqual(parsed["strategy_spec"]["strategy_type"], "rsi_threshold")
        self.assertEqual(parsed["strategy_spec"]["signal"]["indicator_family"], "rsi")
        self.assertEqual(parsed["strategy_spec"]["signal"]["period"], 14)
        self.assertEqual(parsed["strategy_spec"]["signal"]["lower_threshold"], 30.0)
        self.assertEqual(parsed["strategy_spec"]["signal"]["upper_threshold"], 70.0)
        self.assertEqual(parsed["strategy_spec"]["strategy_family"], "rsi_threshold")
        self.assertTrue(parsed["strategy_spec"]["support"]["executable"])
        self.assertTrue(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "assumed")
        self.assertTrue(any(item.get("key") == "rsi_period" for item in parsed["assumptions"]))

    def test_parse_strategy_returns_compact_unsupported_rewrite_guidance(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "AAPL和NVDA各半仓，MACD金叉买入，止损 5%",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertFalse(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "unsupported")
        self.assertIn("单一标的", parsed["unsupported_reason"])
        self.assertEqual(parsed["strategy_spec"]["support"]["normalization_state"], "unsupported")
        self.assertIn("单一标的", parsed["strategy_spec"]["support"]["unsupported_reason"])
        self.assertEqual(parsed["detected_strategy_family"], "macd_crossover")
        self.assertIn("MACD", parsed["core_intent_summary"])
        self.assertTrue(parsed["supported_portion_summary"])
        self.assertTrue(parsed["unsupported_details"])
        self.assertEqual(parsed["unsupported_details"][0]["code"], "unsupported_multi_symbol")
        self.assertGreaterEqual(len(parsed["unsupported_extensions"]), 2)
        self.assertGreaterEqual(len(parsed["rewrite_suggestions"]), 1)
        self.assertTrue(any("AAPL" in item["strategy_text"] or "NVDA" in item["strategy_text"] for item in parsed["rewrite_suggestions"]))

    def test_re_normalization_prefers_explicit_indicator_strategy_spec_over_setup_defaults(self) -> None:
        service = RuleBacktestService(self.db)
        parsed_dict = service.parse_strategy(
            "5日均线上穿20日均线买入，下穿卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )
        parsed_dict["setup"]["fast_period"] = 5
        parsed_dict["setup"]["slow_period"] = 20
        parsed_dict["setup"]["fast_type"] = "simple"
        parsed_dict["strategy_spec"]["signal"]["fast_period"] = 8
        parsed_dict["strategy_spec"]["signal"]["slow_period"] = 21
        parsed_dict["strategy_spec"]["signal"]["fast_type"] = "ema"
        parsed_dict["strategy_spec"]["signal"]["slow_type"] = "ema"
        parsed_dict["strategy_spec"]["capital"]["initial_capital"] = 75000.0
        parsed_dict["strategy_spec"]["signal"]["unexpected_field"] = "drop_me"
        parsed_dict["strategy_spec"]["execution"]["unexpected_field"] = "drop_me"
        parsed_dict["strategy_spec"]["unexpected_field"] = "drop_me"

        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        normalized = service._normalize_parsed_strategy(parsed)

        self.assertEqual(normalized.strategy_spec["signal"]["fast_period"], 8)
        self.assertEqual(normalized.strategy_spec["signal"]["slow_period"], 21)
        self.assertEqual(normalized.strategy_spec["signal"]["fast_type"], "ema")
        self.assertEqual(normalized.strategy_spec["signal"]["slow_type"], "ema")
        self.assertEqual(normalized.strategy_spec["capital"]["initial_capital"], 75000.0)
        self.assertEqual(normalized.strategy_spec["strategy_family"], "moving_average_crossover")
        self.assertTrue(normalized.strategy_spec["support"]["executable"])
        self.assertNotIn("unexpected_field", normalized.strategy_spec)
        self.assertNotIn("unexpected_field", normalized.strategy_spec["signal"])
        self.assertNotIn("unexpected_field", normalized.strategy_spec["execution"])

    def test_re_normalization_prefers_explicit_periodic_strategy_spec_over_setup_defaults(self) -> None:
        service = RuleBacktestService(self.db)
        parsed_dict = service.parse_strategy("资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止")
        parsed_dict["setup"]["order_mode"] = "fixed_shares"
        parsed_dict["setup"]["quantity_per_trade"] = 100
        parsed_dict["strategy_spec"]["entry"]["order"]["mode"] = "fixed_amount"
        parsed_dict["strategy_spec"]["entry"]["order"]["quantity"] = None
        parsed_dict["strategy_spec"]["entry"]["order"]["amount"] = 5000.0
        parsed_dict["strategy_spec"]["capital"]["initial_capital"] = 120000.0
        parsed_dict["strategy_spec"]["entry"]["order"]["unexpected_field"] = "drop_me"
        parsed_dict["strategy_spec"]["schedule"]["unexpected_field"] = "drop_me"
        parsed_dict["strategy_spec"]["unexpected_field"] = "drop_me"

        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        normalized = service._normalize_parsed_strategy(parsed)

        self.assertEqual(normalized.strategy_spec["entry"]["order"]["mode"], "fixed_amount")
        self.assertIsNone(normalized.strategy_spec["entry"]["order"]["quantity"])
        self.assertEqual(normalized.strategy_spec["entry"]["order"]["amount"], 5000.0)
        self.assertEqual(normalized.strategy_spec["capital"]["initial_capital"], 120000.0)
        self.assertEqual(normalized.strategy_spec["strategy_family"], "periodic_accumulation")
        self.assertTrue(normalized.strategy_spec["support"]["executable"])
        self.assertNotIn("unexpected_field", normalized.strategy_spec)
        self.assertNotIn("unexpected_field", normalized.strategy_spec["entry"]["order"])
        self.assertNotIn("unexpected_field", normalized.strategy_spec["schedule"])

    def test_normalize_legacy_setup_backed_indicator_strategy_into_canonical_family_shape(self) -> None:
        service = RuleBacktestService(self.db)
        parsed_dict = service.parse_strategy(
            "MACD金叉买入，死叉卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )
        parsed_dict["strategy_spec"] = {}
        parsed_dict["setup"]["symbol"] = "AAPL"
        parsed_dict["setup"]["indicator_family"] = "macd"
        parsed_dict["setup"]["fast_period"] = 12
        parsed_dict["setup"]["slow_period"] = 26
        parsed_dict["setup"]["signal_period"] = 9
        parsed_dict["setup"]["initial_capital"] = 50000

        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        normalized = service._normalize_parsed_strategy(
            parsed,
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertEqual(normalized.strategy_spec["strategy_type"], "macd_crossover")
        self.assertEqual(normalized.strategy_spec["strategy_family"], "macd_crossover")
        self.assertEqual(normalized.strategy_spec["signal"]["indicator_family"], "macd")
        self.assertEqual(normalized.strategy_spec["signal"]["fast_period"], 12)
        self.assertEqual(normalized.strategy_spec["signal"]["slow_period"], 26)
        self.assertEqual(normalized.strategy_spec["signal"]["signal_period"], 9)
        self.assertEqual(normalized.strategy_spec["execution"]["signal_timing"], "bar_close")
        self.assertEqual(normalized.strategy_spec["execution"]["fill_timing"], "next_bar_open")
        self.assertEqual(normalized.strategy_spec["position_behavior"]["direction"], "long_only")
        self.assertEqual(normalized.strategy_spec["end_behavior"]["policy"], "liquidate_at_end")

    def test_request_normalization_prefers_camel_case_strategy_spec_over_legacy_setup_defaults(self) -> None:
        service = RuleBacktestService(self.db)
        base = service.parse_strategy(
            "MACD金叉买入，死叉卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )
        request_payload = {
            "version": "v1",
            "timeframe": "daily",
            "sourceText": base["source_text"],
            "normalizedText": base["normalized_text"],
            "entry": base["entry"],
            "exit": base["exit"],
            "confidence": base["confidence"],
            "needsConfirmation": base["needs_confirmation"],
            "ambiguities": base["ambiguities"],
            "summary": base["summary"],
            "maxLookback": base["max_lookback"],
            "setup": {
                "symbol": "AAPL",
                "indicatorFamily": "macd",
                "fastPeriod": 5,
                "slowPeriod": 20,
                "signalPeriod": 7,
                "initialCapital": 50000,
            },
            "strategySpec": {
                "strategyType": "macd_crossover",
                "symbol": "AAPL",
                "dateRange": {"startDate": "2024-01-01", "endDate": "2024-12-31"},
                "capital": {"initialCapital": 75000.0, "currency": "USD"},
                "costs": {"feeBps": 1.5, "slippageBps": 2.5},
                "signal": {
                    "indicatorFamily": "macd",
                    "fastPeriod": 12,
                    "slowPeriod": 26,
                    "signalPeriod": 9,
                },
                "execution": {
                    "frequency": "daily",
                    "signalTiming": "bar_close",
                    "fillTiming": "next_bar_open",
                },
                "positionBehavior": {
                    "direction": "long_only",
                    "entrySizing": "all_in",
                    "maxPositions": 1,
                    "pyramiding": False,
                },
                "endBehavior": {"policy": "liquidate_at_end", "priceBasis": "close"},
            },
        }

        parsed = service._dict_to_parsed_strategy(request_payload, base["source_text"])
        normalized = service._normalize_parsed_strategy(parsed)

        self.assertEqual(parsed.strategy_kind, "macd_crossover")
        self.assertEqual(parsed.setup["fast_period"], 5)
        self.assertEqual(parsed.strategy_spec["signal"]["signal_period"], 9)
        self.assertEqual(normalized.strategy_spec["signal"]["fast_period"], 12)
        self.assertEqual(normalized.strategy_spec["signal"]["slow_period"], 26)
        self.assertEqual(normalized.strategy_spec["signal"]["signal_period"], 9)
        self.assertEqual(normalized.strategy_spec["capital"]["initial_capital"], 75000.0)
        self.assertEqual(normalized.strategy_spec["costs"]["fee_bps"], 1.5)
        self.assertEqual(normalized.strategy_spec["costs"]["slippage_bps"], 2.5)

    def test_request_normalization_accepts_camel_case_periodic_setup_legacy_input(self) -> None:
        service = RuleBacktestService(self.db)
        request_payload = {
            "version": "v1",
            "timeframe": "daily",
            "sourceText": "从2025-01-01到2025-12-31，每天买100股ORCL",
            "normalizedText": "从2025-01-01到2025-12-31，每天买100股ORCL",
            "entry": {"type": "group", "op": "and", "rules": []},
            "exit": {"type": "group", "op": "or", "rules": []},
            "confidence": 0.9,
            "needsConfirmation": True,
            "ambiguities": [],
            "summary": {"entry": "买入条件：--", "exit": "卖出条件：--", "strategy": "区间定投策略"},
            "maxLookback": 1,
            "strategyKind": "periodic_accumulation",
            "setup": {
                "symbol": "ORCL",
                "startDate": "2025-01-01",
                "endDate": "2025-12-31",
                "initialCapital": 100000,
                "orderMode": "fixed_shares",
                "quantityPerTrade": 100,
                "executionFrequency": "daily",
                "executionTiming": "session_open",
                "executionPriceBasis": "open",
                "cashPolicy": "stop_when_insufficient_cash",
            },
            "strategySpec": {},
        }

        parsed = service._dict_to_parsed_strategy(request_payload, request_payload["sourceText"])
        normalized = service._normalize_parsed_strategy(parsed)

        self.assertEqual(parsed.setup["start_date"], "2025-01-01")
        self.assertEqual(parsed.setup["quantity_per_trade"], 100)
        self.assertEqual(normalized.strategy_spec["strategy_type"], "periodic_accumulation")
        self.assertEqual(normalized.strategy_spec["symbol"], "ORCL")
        self.assertEqual(normalized.strategy_spec["date_range"]["start_date"], "2025-01-01")
        self.assertEqual(normalized.strategy_spec["entry"]["order"]["mode"], "fixed_shares")
        self.assertEqual(normalized.strategy_spec["entry"]["order"]["quantity"], 100.0)

    def test_request_normalization_preserves_generic_fallback_for_unsupported_structured_input(self) -> None:
        service = RuleBacktestService(self.db)
        request_payload = {
            "version": "v1",
            "timeframe": "daily",
            "sourceText": "如果指数跌破均线则空仓，否则执行自定义逻辑",
            "normalizedText": "如果指数跌破均线则空仓，否则执行自定义逻辑",
            "entry": {"type": "group", "op": "and", "rules": []},
            "exit": {"type": "group", "op": "or", "rules": []},
            "confidence": 0.8,
            "needsConfirmation": True,
            "ambiguities": [],
            "summary": {"entry": "买入条件：--", "exit": "卖出条件：--", "strategy": "自定义策略"},
            "maxLookback": 5,
            "setup": {
                "indicatorFamily": "macd",
                "fastPeriod": 12,
                "slowPeriod": 26,
            },
            "strategySpec": {
                "strategyType": "custom_branching_strategy",
                "strategyFamily": "custom_branching_strategy",
                "customBranching": {"if": "index_below_ma", "then": "flat"},
                "customThreshold": 5,
            },
        }

        parsed = service._dict_to_parsed_strategy(request_payload, request_payload["sourceText"])
        normalized = service._normalize_parsed_strategy(parsed)

        self.assertEqual(parsed.strategy_kind, "custom_branching_strategy")
        self.assertEqual(normalized.strategy_spec["strategy_type"], "custom_branching_strategy")
        self.assertEqual(normalized.strategy_spec["strategy_family"], "custom_branching_strategy")
        self.assertEqual(normalized.strategy_spec["customBranching"]["if"], "index_below_ma")
        self.assertEqual(normalized.strategy_spec["customThreshold"], 5)
        self.assertNotIn("signal", normalized.strategy_spec)

    def test_parse_strategy_marks_strategy_combination_unsupported_with_rewrite(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "MACD金叉买入，止损5%，死叉卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertFalse(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "unsupported")
        self.assertIn("止损", parsed["unsupported_reason"])
        self.assertEqual(parsed["detected_strategy_family"], "macd_crossover")
        self.assertIn("MACD", parsed["core_intent_summary"])
        self.assertEqual(parsed["unsupported_details"][0]["code"], "unsupported_strategy_combination")
        self.assertIn("MACD", parsed["supported_portion_summary"])
        self.assertTrue(any("MACD金叉买入，死叉卖出" in item["strategy_text"] for item in parsed["rewrite_suggestions"]))

    def test_parse_strategy_marks_scaling_request_unsupported_with_rsi_rewrite(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "RSI低于30分三批买入，高于70卖出",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertFalse(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "unsupported")
        self.assertEqual(parsed["detected_strategy_family"], "rsi_threshold")
        self.assertIn("RSI", parsed["core_intent_summary"])
        self.assertEqual(parsed["unsupported_details"][0]["code"], "unsupported_position_scaling")
        self.assertIn("RSI", parsed["supported_portion_summary"])
        self.assertTrue(any("RSI14 低于30买入，高于70卖出" in item["strategy_text"] for item in parsed["rewrite_suggestions"]))

    def test_parse_strategy_marks_parameter_optimization_unsupported_with_fixed_parameter_rewrite(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "优化 2020 到 2025 最佳 MACD 参数",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertFalse(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "unsupported")
        self.assertEqual(parsed["detected_strategy_family"], "macd_crossover")
        self.assertIn("MACD", parsed["core_intent_summary"])
        self.assertEqual(parsed["unsupported_details"][0]["code"], "unsupported_parameter_optimization")
        self.assertIn("MACD", parsed["supported_portion_summary"])
        self.assertTrue(any("MACD金叉买入，死叉卖出" in item["strategy_text"] for item in parsed["rewrite_suggestions"]))

    def test_parse_strategy_surfaces_partial_family_guidance_for_generic_indicator_requests(self) -> None:
        service = RuleBacktestService(self.db)
        cases = [
            ("均线策略", "均线", "5日均线上穿20日均线买入，下穿卖出"),
            ("MACD策略", "MACD", "MACD金叉买入，死叉卖出"),
            ("RSI策略", "RSI", "RSI14 低于30买入，高于70卖出"),
        ]

        for text, expected_summary_token, expected_rewrite in cases:
            with self.subTest(text=text):
                parsed = service.parse_strategy(
                    text,
                    code="AAPL",
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    initial_capital=50000,
                )

                self.assertFalse(parsed["executable"])
                self.assertEqual(parsed["normalization_state"], "unsupported")
                self.assertEqual(parsed["unsupported_details"][0]["code"], "unsupported_missing_exit_rule")
                self.assertIsNotNone(parsed["detected_strategy_family"])
                self.assertIsNotNone(parsed["core_intent_summary"])
                self.assertIn(expected_summary_token, parsed["supported_portion_summary"])
                self.assertTrue(any(expected_rewrite in item["strategy_text"] for item in parsed["rewrite_suggestions"]))

    def test_parse_strategy_preserves_ma_core_intent_when_stop_extension_is_unsupported(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy(
            "5日线上穿20日线买入，跌破10日线止损",
            code="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_capital=50000,
        )

        self.assertFalse(parsed["executable"])
        self.assertEqual(parsed["normalization_state"], "unsupported")
        self.assertEqual(parsed["detected_strategy_family"], "moving_average_crossover")
        self.assertIn("均线交叉", parsed["core_intent_summary"])
        self.assertTrue(any(item["code"] == "unsupported_strategy_combination" for item in parsed["unsupported_extensions"]))
        self.assertTrue(any("5日均线上穿20日均线买入，下穿卖出" in item["strategy_text"] for item in parsed["rewrite_suggestions"]))

    def test_engine_evaluates_sample_history_deterministically(self) -> None:
        parser = RuleBacktestParser()
        parsed = parser.parse("Buy when Close > MA3. Sell when Close < MA3.")
        engine = RuleBacktestEngine()

        with self.db.get_session() as session:
            bars = session.query(StockDaily).filter(StockDaily.code == "600519").order_by(StockDaily.date).all()

        result = engine.run(
            code="600519",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=0.0,
            lookback_bars=20,
        )

        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertIsNone(result.no_result_reason)
        self.assertGreater(len(result.equity_curve), 0)
        self.assertIn("buy_and_hold_return_pct", result.metrics)
        self.assertIn("excess_return_vs_buy_and_hold_pct", result.metrics)
        self.assertGreater(len(result.benchmark_curve), 0)
        self.assertEqual(result.benchmark_summary["method"], "same_symbol_buy_and_hold")
        self.assertEqual(result.execution_model.signal_evaluation_timing, "bar_close")
        self.assertEqual(result.execution_model.entry_timing, "next_bar_open")
        self.assertEqual(result.execution_model.entry_fill_price_basis, "open")
        self.assertEqual(result.execution_model.market_rules["terminal_bar_fill_fallback"], "same_bar_close")
        result_payload = result.to_dict()
        self.assertGreater(len(result_payload["benchmark_curve"]), 0)
        self.assertEqual(result_payload["execution_model"]["entry_timing"], "next_bar_open")
        self.assertIn("cash", result_payload["equity_curve"][0])
        self.assertIn("shares_held", result_payload["equity_curve"][0])
        self.assertIn("total_portfolio_value", result_payload["equity_curve"][0])
        self.assertEqual(result.execution_assumptions.indicator_price_basis, "close")
        self.assertEqual(result.execution_assumptions.entry_fill_timing, "next_bar_open")

    def test_service_runs_periodic_accumulation_with_existing_result_shape(self) -> None:
        service = RuleBacktestService(self.db)
        parsed = service.parse_strategy("资金100000，从2024-01-05到2024-01-20，每天买100股ORCL，买到资金耗尽为止", code="600519")
        parsed["setup"] = {}

        with patch.object(service, "_ensure_market_history", return_value=0):
            response = service.run_backtest(
                code="600519",
                strategy_text=parsed["source_text"],
                parsed_strategy=parsed,
                start_date="2024-01-05",
                end_date="2024-01-20",
                initial_capital=100000.0,
                confirmed=True,
            )

        self.assertEqual(response["parsed_strategy"]["strategy_kind"], "periodic_accumulation")
        self.assertEqual(response["parsed_strategy"]["strategy_spec"]["strategy_type"], "periodic_accumulation")
        self.assertEqual(response["start_date"], "2024-01-05")
        self.assertEqual(response["end_date"], "2024-01-20")
        self.assertEqual(response["period_start"], "2024-01-05")
        self.assertEqual(response["period_end"], "2024-01-20")
        self.assertGreater(len(response["equity_curve"]), 0)
        self.assertGreater(len(response["trades"]), 0)
        self.assertGreater(len(response["benchmark_curve"]), 0)
        self.assertEqual(response["benchmark_summary"]["method"], "same_symbol_buy_and_hold")
        self.assertGreater(len(response["buy_and_hold_curve"]), 0)
        self.assertEqual(response["buy_and_hold_summary"]["resolved_mode"], "same_symbol_buy_and_hold")
        self.assertGreater(len(response["audit_rows"]), 0)
        self.assertEqual(response["summary"]["visualization"]["audit_rows"], response["audit_rows"])
        self.assertEqual(response["execution_model"]["entry_timing"], "same_bar_open")
        self.assertEqual(response["execution_model"]["exit_timing"], "forced_close_at_window_end_close")
        self.assertEqual(response["summary"]["execution_model"]["entry_fill_price_basis"], "open")
        self.assertIn("total_portfolio_value", response["audit_rows"][0])
        self.assertIn("cumulative_return", response["audit_rows"][0])
        self.assertIn("position", response["audit_rows"][0])
        self.assertGreater(len(response["daily_return_series"]), 0)
        self.assertGreater(len(response["exposure_curve"]), 0)
        self.assertIn("execution_assumptions", response)
        self.assertIn("total_return_pct", response)

    def test_service_uses_market_appropriate_auto_benchmark_defaults(self) -> None:
        service = RuleBacktestService(self.db)

        self.assertEqual(service._default_benchmark_mode_for_code("600519"), "index_hs300")
        self.assertEqual(service._default_benchmark_mode_for_code("AAPL"), "etf_qqq")
        self.assertEqual(service._default_benchmark_mode_for_code("BTC-USD"), "same_symbol_buy_and_hold")

    def test_engine_honors_explicit_start_end_date_window(self) -> None:
        parser = RuleBacktestParser()
        parsed = parser.parse("Buy when Close > MA3. Sell when Close < MA3.")
        engine = RuleBacktestEngine()

        with self.db.get_session() as session:
            bars = session.query(StockDaily).filter(StockDaily.code == "600519").order_by(StockDaily.date).all()

        result = engine.run(
            code="600519",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=0.0,
            lookback_bars=20,
            start_date=date(2024, 1, 8),
            end_date=date(2024, 1, 18),
        )

        self.assertEqual(result.metrics["period_start"], "2024-01-08")
        self.assertEqual(result.metrics["period_end"], "2024-01-18")
        self.assertTrue(all(point.date >= date(2024, 1, 8) for point in result.equity_curve))
        self.assertTrue(all(point.date <= date(2024, 1, 18) for point in result.equity_curve))
        self.assertTrue(all((point.get("date") or "") >= "2024-01-08" for point in result.benchmark_curve))
        self.assertTrue(all((point.get("date") or "") <= "2024-01-18" for point in result.benchmark_curve))
        self.assertTrue(all(trade.entry_date >= date(2024, 1, 8) for trade in result.trades))
        self.assertTrue(all(trade.exit_date <= date(2024, 1, 18) for trade in result.trades))

    def test_auto_benchmark_falls_back_to_same_symbol_when_external_series_unavailable(self) -> None:
        service = RuleBacktestService(self.db)
        parser = RuleBacktestParser()
        parsed = parser.parse("Buy when Close > MA3. Sell when Close < MA3.")
        engine = RuleBacktestEngine()

        with self.db.get_session() as session:
            bars = session.query(StockDaily).filter(StockDaily.code == "600519").order_by(StockDaily.date).all()

        result = engine.run(
            code="600519",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            fee_bps=0.0,
            lookback_bars=20,
        )

        with patch.object(
            service,
            "_load_external_benchmark_context",
            return_value=([], {"label": "沪深300", "resolved_mode": "index_hs300", "return_pct": None}, "沪深300 在当前窗口没有可用行情。"),
        ):
            service._apply_benchmark_context(
                result,
                instrument_code="600519",
                benchmark_mode="auto",
                benchmark_code=None,
                start_date=None,
                end_date=None,
            )

        self.assertEqual(result.benchmark_summary["requested_mode"], "auto")
        self.assertEqual(result.benchmark_summary["resolved_mode"], "same_symbol_buy_and_hold")
        self.assertTrue(result.benchmark_summary["auto_resolved"])
        self.assertTrue(result.benchmark_summary["fallback_used"])
        self.assertIn("沪深300", result.benchmark_summary["unavailable_reason"])
        self.assertGreater(len(result.benchmark_curve), 0)
        self.assertEqual(result.metrics["benchmark_return_pct"], result.metrics["buy_and_hold_return_pct"])

    def test_service_persists_canonical_benchmark_comparison_payload(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        comparison = response["summary"]["visualization"].get("comparison") or {}
        self.assertEqual(comparison.get("version"), "v1")
        self.assertEqual(comparison.get("source"), "stored")
        self.assertEqual(comparison.get("benchmark_summary"), response["benchmark_summary"])
        self.assertEqual(comparison.get("buy_and_hold_summary"), response["buy_and_hold_summary"])
        self.assertEqual(comparison.get("benchmark_curve"), response["benchmark_curve"])
        self.assertEqual(comparison.get("buy_and_hold_curve"), response["buy_and_hold_curve"])
        self.assertEqual(comparison.get("metrics", {}).get("benchmark_return_pct"), response["benchmark_return_pct"])
        self.assertEqual(comparison.get("metrics", {}).get("buy_and_hold_return_pct"), response["buy_and_hold_return_pct"])

    def test_service_exports_execution_trace_csv_and_json_from_stored_result(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        self.assertIn("execution_trace", response)
        self.assertGreater(len(response["execution_trace"]["rows"]), 0)
        self.assertTrue(response["execution_trace"]["assumptions_defaults"]["summary_text"])

        csv_path = os.path.join(self._temp_dir.name, "trace.csv")
        json_path = os.path.join(self._temp_dir.name, "trace.json")
        service.export_execution_trace_csv(run_id=response["id"], output_path=csv_path)
        service.export_execution_trace_json(run_id=response["id"], output_path=json_path)

        with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertGreater(len(rows), 0)
        self.assertEqual(
            list(rows[0].keys()),
            [
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
                "assumptions",
                "fallback",
            ],
        )
        self.assertIn("fallback", rows[0])
        self.assertIn("assumptions", rows[0])
        self.assertIn("仓位", rows[0])
        self.assertIn("现金", rows[0])
        self.assertIn("总资产", rows[0])
        self.assertTrue(any((row.get("动作") or "") in {"买", "卖"} for row in rows))
        self.assertTrue(all((row.get("fallback") or "") for row in rows))

        with open(json_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertIn("trace_rows", payload)
        self.assertEqual(payload["trace_rows"], rows)
        self.assertIn("assumptions", payload)
        self.assertIn("execution_model", payload)

    def test_periodic_trace_marks_skip_and_python_automation_can_auto_confirm(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service,
            "_ensure_market_history",
            return_value=0,
        ):
            with self.assertRaises(ValueError):
                service.parse_and_run(
                    code="600519",
                    strategy_text="资金1500，从2024-01-05到2024-01-20，每天买100股ORCL，买到资金耗尽为止",
                    confirmed=False,
                )

            response = service.parse_and_run_automated(
                code="600519",
                strategy_text="资金1500，从2024-01-05到2024-01-20，每天买100股ORCL，买到资金耗尽为止",
                start_date="2024-01-05",
                end_date="2024-01-20",
                initial_capital=1500.0,
            )

        trace_rows = list(response["execution_trace"]["rows"])
        self.assertTrue(any(row.get("event_type") == "buy" for row in trace_rows))
        self.assertTrue(any(row.get("event_type") == "skip" for row in trace_rows))
        self.assertTrue(any("默认/推断" in str(row.get("assumptions_defaults") or "") for row in trace_rows))

    def test_execution_trace_marks_benchmark_fallback_without_recomputing_rows(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service,
            "_load_external_benchmark_context",
            return_value=(
                [],
                {
                    "label": "沪深300",
                    "code": "000300.SH",
                    "method": "benchmark_security",
                    "requested_mode": "index_hs300",
                    "resolved_mode": "index_hs300",
                    "price_basis": "close",
                    "return_pct": None,
                    "unavailable_reason": "沪深300 在当前窗口没有可用行情。",
                },
                "沪深300 在当前窗口没有可用行情。",
            ),
        ):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                benchmark_mode="auto",
                confirmed=True,
            )

        self.assertTrue(response["execution_trace"]["fallback"]["run_fallback"])
        self.assertTrue(all(str(row.get("fallback") or "").strip() not in {"", "无"} for row in response["execution_trace"]["rows"]))

    def test_get_run_rebuilds_execution_trace_for_legacy_run_with_provenance(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        run_row = service.repo.get_run(response["id"])
        assert run_row is not None
        summary = json.loads(run_row.summary_json)
        summary.pop("execution_trace", None)
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["execution_trace"]["source"], "rebuilt_from_stored_audit_rows")
        self.assertTrue(detail["execution_trace"]["fallback"]["trace_rebuilt"])
        self.assertTrue(all("历史运行回补trace" in str(row.get("fallback") or "") for row in detail["execution_trace"]["rows"]))

    def test_module_level_run_backtest_automated_exports_trace_files(self) -> None:
        with patch.object(RuleBacktestService, "_ensure_market_history", return_value=0), patch.object(
            RuleBacktestService,
            "_get_llm_adapter",
            return_value=None,
        ):
            result = run_backtest_automated(
                symbol="600519",
                scenario="cash_insufficiency_skip",
                initial_capital=1500.0,
                output_dir=self._temp_dir.name,
            )

        self.assertTrue(os.path.exists(result["csv_path"]))
        self.assertTrue(os.path.exists(result["json_path"]))
        self.assertEqual(result["scenario"], "cash_insufficiency_skip")

    def test_service_persists_explicit_benchmark_unavailable_reason_without_fabricated_returns(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None), patch.object(
            service,
            "_load_external_benchmark_context",
            return_value=(
                [],
                {
                    "label": "沪深300",
                    "code": "000300.SH",
                    "method": "benchmark_security",
                    "requested_mode": "index_hs300",
                    "resolved_mode": "index_hs300",
                    "price_basis": "close",
                    "return_pct": None,
                    "unavailable_reason": "沪深300 在当前窗口没有可用行情。",
                },
                "沪深300 在当前窗口没有可用行情。",
            ),
        ):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                benchmark_mode="index_hs300",
                confirmed=True,
            )

        comparison = response["summary"]["visualization"].get("comparison") or {}
        self.assertEqual(response["benchmark_summary"]["resolved_mode"], "index_hs300")
        self.assertIn("沪深300", response["benchmark_summary"]["unavailable_reason"])
        self.assertEqual(response["benchmark_curve"], [])
        self.assertIsNone(response["benchmark_return_pct"])
        self.assertIsNotNone(response["buy_and_hold_return_pct"])
        self.assertEqual(comparison.get("benchmark_summary"), response["benchmark_summary"])
        self.assertIsNone(comparison.get("metrics", {}).get("benchmark_return_pct"))
        self.assertEqual(
            comparison.get("metrics", {}).get("buy_and_hold_return_pct"),
            response["buy_and_hold_return_pct"],
        )

    def test_engine_executes_moving_average_crossover_from_normalized_spec(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10, 9.8, 9.6, 9.4, 9.2, 9.4, 9.8, 10.2, 10.8, 11.2, 11.6, 11.1, 10.7, 10.2, 9.8, 9.4, 9.0, 9.3, 9.7, 10.1, 10.5, 10.9, 11.3, 11.7, 12.1, 11.6, 11.0, 10.4, 9.8, 9.2])
        parsed_dict = service.parse_strategy(
            "5日均线上穿20日均线买入，下穿卖出",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-01-30",
            initial_capital=100000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            lookback_bars=30,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 30),
        )

        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertGreater(len(result.equity_curve), 0)
        self.assertEqual(result.parsed_strategy.strategy_spec["strategy_type"], "moving_average_crossover")

    def test_engine_executes_macd_crossover_from_normalized_spec(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10, 10.1, 10.2, 10.4, 10.7, 11.1, 11.5, 11.8, 12.0, 11.7, 11.2, 10.8, 10.4, 10.0, 9.7, 9.5, 9.8, 10.2, 10.7, 11.2, 11.8, 12.3, 12.6, 12.2, 11.7, 11.1, 10.6, 10.2, 9.9, 9.6, 9.9, 10.4, 10.9, 11.4, 11.9, 12.4, 12.8, 12.3, 11.7, 11.0])
        parsed_dict = service.parse_strategy(
            "MACD金叉买入，死叉卖出",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-02-09",
            initial_capital=100000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            lookback_bars=40,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 9),
        )

        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertGreater(len(result.equity_curve), 0)
        self.assertEqual(result.parsed_strategy.strategy_spec["strategy_type"], "macd_crossover")

    def test_engine_executes_rsi_threshold_from_normalized_spec(self) -> None:
        service = RuleBacktestService(self.db)
        bars = self._make_bars([10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 9, 8, 9, 10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 9, 8, 9, 10, 11, 12, 13])
        parsed_dict = service.parse_strategy(
            "RSI6 小于 30 买入，RSI6 大于 70 卖出",
            code="TEST",
            start_date="2024-01-01",
            end_date="2024-02-01",
            initial_capital=100000,
        )
        parsed = service._dict_to_parsed_strategy(parsed_dict, parsed_dict["source_text"])
        engine = RuleBacktestEngine()

        result = engine.run(
            code="TEST",
            parsed_strategy=parsed,
            bars=bars,
            initial_capital=100000.0,
            lookback_bars=32,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 1),
        )

        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertGreater(len(result.equity_curve), 0)
        self.assertEqual(result.parsed_strategy.strategy_spec["strategy_type"], "rsi_threshold")

    def test_service_generates_fallback_ai_summary_and_persists_runs(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text=strategy_text,
                lookback_bars=20,
                confirmed=True,
            )

        self.assertGreater(response["trade_count"], 0)
        self.assertIn("总收益", response["ai_summary"])

        history = service.list_runs(code="600519", page=1, limit=10)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["trade_count"], response["trade_count"])
        self.assertIn("buy_and_hold_return_pct", history["items"][0])
        self.assertIn("benchmark_curve", history["items"][0])
        self.assertIn("benchmark_summary", history["items"][0])
        self.assertIn("execution_model", history["items"][0])
        self.assertIn("execution_assumptions", history["items"][0])

        detail = service.get_run(history["items"][0]["id"])
        self.assertIsNotNone(detail)
        self.assertEqual(len(detail["trades"]), response["trade_count"])
        self.assertGreaterEqual(len(detail["status_history"]), 1)
        self.assertIn(detail["status"], {"completed"})
        self.assertIn("annualized_return_pct", detail)
        self.assertIn("benchmark_curve", detail)
        self.assertIn("benchmark_summary", detail)
        self.assertIn("execution_model", detail)
        self.assertIn("audit_rows", detail)
        self.assertIn("daily_return_series", detail)
        self.assertIn("exposure_curve", detail)
        self.assertGreater(len(detail["audit_rows"]), 0)
        self.assertIn("action", detail["audit_rows"][0])
        self.assertIn("cumulative_return", detail["audit_rows"][0])
        self.assertIn("signal_summary", detail["audit_rows"][0])
        if detail["trades"]:
            first_trade = detail["trades"][0]
            self.assertIn("entry_trigger", first_trade)
            self.assertIn("price_basis", first_trade)
            self.assertIn("holding_bars", first_trade)

    def test_service_persists_requested_date_range_and_period(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text=strategy_text,
                lookback_bars=20,
                confirmed=True,
            )
            ranged = service.run_backtest(
                code="600519",
                strategy_text=strategy_text,
                parsed_strategy=response["parsed_strategy"],
                start_date="2024-01-08",
                end_date="2024-01-18",
                lookback_bars=20,
                confirmed=True,
            )

        self.assertEqual(ranged["start_date"], "2024-01-08")
        self.assertEqual(ranged["end_date"], "2024-01-18")
        self.assertEqual(ranged["period_start"], "2024-01-08")
        self.assertEqual(ranged["period_end"], "2024-01-18")
        self.assertEqual(ranged["summary"]["request"]["start_date"], "2024-01-08")
        self.assertEqual(ranged["summary"]["request"]["end_date"], "2024-01-18")
        self.assertTrue(all((point.get("date") or "") >= "2024-01-08" for point in ranged["equity_curve"]))
        self.assertTrue(all((point.get("date") or "") <= "2024-01-18" for point in ranged["equity_curve"]))
        self.assertTrue(all((point.get("date") or "") >= "2024-01-08" for point in ranged["benchmark_curve"]))
        self.assertTrue(all((point.get("date") or "") <= "2024-01-18" for point in ranged["benchmark_curve"]))
        self.assertTrue(all((point.get("date") or "") >= "2024-01-08" for point in ranged["daily_return_series"]))
        self.assertTrue(all((point.get("date") or "") <= "2024-01-18" for point in ranged["daily_return_series"]))

    def test_submit_and_process_backtest_records_async_status_history(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            submitted = service.submit_backtest(
                code="600519",
                strategy_text=strategy_text,
                start_date="2024-01-08",
                end_date="2024-01-18",
                lookback_bars=20,
                confirmed=True,
            )

            self.assertIn(submitted["status"], {"parsing", "queued"})
            self.assertGreaterEqual(len(submitted["status_history"]), 1)

            service.process_submitted_run(submitted["id"])

        detail = service.get_run(submitted["id"])
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["status"], "completed")
        self.assertGreaterEqual(len(detail["status_history"]), 3)
        self.assertEqual(detail["summary"]["request"]["lookback_bars"], 20)
        self.assertEqual(detail["summary"]["request"]["start_date"], "2024-01-08")
        self.assertEqual(detail["summary"]["request"]["end_date"], "2024-01-18")
        self.assertEqual(detail["summary"]["request"]["confirmed"], True)
        self.assertEqual(detail["start_date"], "2024-01-08")
        self.assertEqual(detail["end_date"], "2024-01-18")
        self.assertIn("execution_assumptions", detail["summary"])
        statuses = [item.get("status") for item in detail["status_history"]]
        self.assertIn("running", statuses)
        self.assertIn("summarizing", statuses)
        self.assertIn("completed", statuses)
        self.assertIn("buy_and_hold_return_pct", detail)
        self.assertIn("excess_return_vs_buy_and_hold_pct", detail)
        self.assertIn("benchmark_curve", detail)
        self.assertIn("benchmark_summary", detail)
        self.assertIn("audit_rows", detail)

    def test_get_run_prefers_persisted_audit_ledger_over_reconstruction(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text=strategy_text,
                lookback_bars=20,
                confirmed=True,
            )

        run_row = service.repo.get_run(response["id"])
        assert run_row is not None
        summary = json.loads(run_row.summary_json)
        summary["visualization"]["audit_rows"] = [
            {
                "date": "2024-01-20",
                "symbol_close": 999.0,
                "benchmark_close": None,
                "position": 0.0,
                "shares": None,
                "cash": 123456.0,
                "holdings_value": 0.0,
                "total_portfolio_value": 123456.0,
                "daily_pnl": 3456.0,
                "daily_return": 2.88,
                "cumulative_return": 23.456,
                "benchmark_cumulative_return": None,
                "buy_hold_cumulative_return": None,
                "action": "buy",
                "fill_price": 12.34,
                "signal_summary": "stored-ledger-row",
                "drawdown_pct": -0.5,
                "position_state": "flat",
                "fees": None,
                "slippage": None,
                "notes": "persisted-ledger",
                "unavailable_reason": "stored-only",
            }
        ]
        summary["visualization"]["daily_return_series"] = []
        summary["visualization"]["exposure_curve"] = []
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["audit_rows"], summary["visualization"]["audit_rows"])
        self.assertEqual(detail["audit_rows"][0]["symbol_close"], 999.0)
        self.assertEqual(detail["audit_rows"][0]["signal_summary"], "stored-ledger-row")
        self.assertEqual(detail["daily_return_series"][0]["equity"], 123456.0)
        self.assertEqual(detail["daily_return_series"][0]["daily_return_pct"], 2.88)
        self.assertEqual(detail["exposure_curve"][0]["executed_action"], "buy")
        self.assertEqual(detail["exposure_curve"][0]["position_state"], "flat")

    def test_get_run_prefers_persisted_benchmark_comparison_payload_over_legacy_fields(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        run_row = service.repo.get_run(response["id"])
        assert run_row is not None
        summary = json.loads(run_row.summary_json)
        summary["visualization"]["benchmark_curve"] = []
        summary["visualization"]["benchmark_summary"] = {
            "label": "legacy benchmark",
            "requested_mode": "auto",
            "resolved_mode": "etf_qqq",
            "method": "benchmark_security",
            "price_basis": "close",
            "return_pct": 1.1,
            "unavailable_reason": None,
        }
        summary["visualization"]["buy_and_hold_curve"] = []
        summary["visualization"]["buy_and_hold_summary"] = {
            "label": "legacy buy hold",
            "requested_mode": "same_symbol_buy_and_hold",
            "resolved_mode": "same_symbol_buy_and_hold",
            "method": "same_symbol_buy_and_hold",
            "price_basis": "close",
            "return_pct": 2.2,
            "unavailable_reason": None,
        }
        summary["metrics"]["benchmark_return_pct"] = 1.1
        summary["metrics"]["buy_and_hold_return_pct"] = 2.2
        summary["metrics"]["excess_return_vs_benchmark_pct"] = 0.1
        summary["metrics"]["excess_return_vs_buy_and_hold_pct"] = -1.0
        summary["visualization"]["comparison"] = {
            "version": "v1",
            "source": "stored",
            "benchmark_curve": [
                {
                    "date": "2024-01-20",
                    "close": 321.0,
                    "normalized_value": 1.099,
                    "cumulative_return_pct": 9.9,
                }
            ],
            "benchmark_summary": {
                "label": "stored benchmark",
                "requested_mode": "auto",
                "resolved_mode": "etf_qqq",
                "method": "benchmark_security",
                "price_basis": "close",
                "return_pct": 9.9,
                "unavailable_reason": "stored benchmark reason",
            },
            "buy_and_hold_curve": [
                {
                    "date": "2024-01-20",
                    "close": 205.5,
                    "normalized_value": 1.055,
                    "cumulative_return_pct": 5.5,
                }
            ],
            "buy_and_hold_summary": {
                "label": "stored buy hold",
                "requested_mode": "same_symbol_buy_and_hold",
                "resolved_mode": "same_symbol_buy_and_hold",
                "method": "same_symbol_buy_and_hold",
                "price_basis": "close",
                "return_pct": 5.5,
                "unavailable_reason": None,
            },
            "metrics": {
                "benchmark_return_pct": 9.9,
                "excess_return_vs_benchmark_pct": -4.4,
                "buy_and_hold_return_pct": 5.5,
                "excess_return_vs_buy_and_hold_pct": 0.0,
            },
        }
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["benchmark_summary"]["label"], "stored benchmark")
        self.assertEqual(detail["benchmark_summary"]["unavailable_reason"], "stored benchmark reason")
        self.assertEqual(detail["benchmark_curve"][0]["close"], 321.0)
        self.assertEqual(detail["buy_and_hold_summary"]["label"], "stored buy hold")
        self.assertEqual(detail["buy_and_hold_curve"][0]["cumulative_return_pct"], 5.5)
        self.assertEqual(detail["benchmark_return_pct"], 9.9)
        self.assertEqual(detail["buy_and_hold_return_pct"], 5.5)
        self.assertEqual(detail["excess_return_vs_benchmark_pct"], -4.4)

        history = service.list_runs(code="600519", page=1, limit=10)
        self.assertEqual(history["items"][0]["benchmark_summary"]["label"], "stored benchmark")
        self.assertEqual(history["items"][0]["benchmark_return_pct"], 9.9)

    def test_history_reads_prefer_stored_summary_metrics_over_row_columns(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        run_row = service.repo.get_run(response["id"])
        assert run_row is not None
        summary = json.loads(run_row.summary_json)
        summary["metrics"].update(
            {
                "trade_count": 7,
                "win_count": 6,
                "loss_count": 1,
                "total_return_pct": 88.8,
                "annualized_return_pct": 44.4,
                "win_rate_pct": 85.7143,
                "avg_trade_return_pct": 12.34,
                "max_drawdown_pct": 9.87,
                "avg_holding_days": 8.0,
                "avg_holding_bars": 8.0,
                "avg_holding_calendar_days": 10.0,
                "final_equity": 188800.0,
            }
        )
        summary["visualization"]["daily_return_series"] = [
            {
                "date": "2024-01-20",
                "equity": 188800.0,
                "daily_return_pct": 3.21,
                "daily_pnl": 5875.0,
            }
        ]
        summary["visualization"]["exposure_curve"] = [
            {
                "date": "2024-01-20",
                "exposure": 0.25,
                "position_state": "custom-stored",
                "executed_action": "hold",
                "fill_price": 321.0,
            }
        ]
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["trade_count"], 7)
        self.assertEqual(detail["win_count"], 6)
        self.assertEqual(detail["loss_count"], 1)
        self.assertEqual(detail["total_return_pct"], 88.8)
        self.assertEqual(detail["annualized_return_pct"], 44.4)
        self.assertEqual(detail["win_rate_pct"], 85.7143)
        self.assertEqual(detail["avg_trade_return_pct"], 12.34)
        self.assertEqual(detail["max_drawdown_pct"], 9.87)
        self.assertEqual(detail["avg_holding_days"], 8.0)
        self.assertEqual(detail["avg_holding_bars"], 8.0)
        self.assertEqual(detail["avg_holding_calendar_days"], 10.0)
        self.assertEqual(detail["final_equity"], 188800.0)
        self.assertEqual(detail["daily_return_series"], summary["visualization"]["daily_return_series"])
        self.assertEqual(detail["exposure_curve"], summary["visualization"]["exposure_curve"])

        history = service.list_runs(code="600519", page=1, limit=10)
        self.assertEqual(history["items"][0]["trade_count"], 7)
        self.assertEqual(history["items"][0]["total_return_pct"], 88.8)
        self.assertEqual(history["items"][0]["annualized_return_pct"], 44.4)
        self.assertEqual(history["items"][0]["final_equity"], 188800.0)

    def test_get_run_uses_explicit_legacy_fallback_when_stored_replay_payload_is_missing(self) -> None:
        service = RuleBacktestService(self.db)

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        run_row = service.repo.get_run(response["id"])
        assert run_row is not None
        summary = json.loads(run_row.summary_json)
        summary["metrics"] = {}
        summary["visualization"].pop("comparison", None)
        summary["visualization"]["audit_rows"] = []
        summary["visualization"]["daily_return_series"] = []
        summary["visualization"]["exposure_curve"] = []
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertGreater(len(detail["audit_rows"]), 0)
        self.assertGreater(len(detail["daily_return_series"]), 0)
        self.assertGreater(len(detail["exposure_curve"]), 0)
        self.assertEqual(detail["trade_count"], run_row.trade_count)
        self.assertEqual(detail["total_return_pct"], run_row.total_return_pct)
        self.assertEqual(detail["benchmark_return_pct"], detail["benchmark_summary"]["return_pct"])

    def test_get_run_derives_execution_model_for_legacy_runs_without_structured_config(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            response = service.parse_and_run(
                code="600519",
                strategy_text=strategy_text,
                lookback_bars=20,
                confirmed=True,
            )

        run_row = service.repo.get_run(response["id"])
        assert run_row is not None
        summary = json.loads(run_row.summary_json)
        summary.pop("execution_model", None)
        summary["execution_assumptions"] = {
            "timeframe": "daily",
            "signal_evaluation_timing": "evaluate rules on each bar close",
            "entry_fill_timing": "next_bar_open",
            "exit_fill_timing": "next_bar_open; last openless bar falls back to same-bar close",
            "default_fill_price_basis": "open",
            "position_sizing": "single_position_full_notional",
            "fee_model": "bps_per_side",
            "fee_bps_per_side": 1.5,
            "slippage_model": "bps_per_side",
            "slippage_bps_per_side": 2.5,
        }
        service.repo.update_run(run_row.id, summary_json=service._serialize_json(summary))

        detail = service.get_run(run_row.id)
        assert detail is not None
        self.assertEqual(detail["execution_model"]["signal_evaluation_timing"], "bar_close")
        self.assertEqual(detail["execution_model"]["entry_timing"], "next_bar_open")
        self.assertEqual(detail["execution_model"]["entry_fill_price_basis"], "open")
        self.assertEqual(detail["execution_model"]["fee_bps_per_side"], 1.5)
        self.assertEqual(detail["execution_model"]["slippage_bps_per_side"], 2.5)
        self.assertEqual(detail["execution_model"]["market_rules"]["terminal_bar_fill_fallback"], "same_bar_close")


if __name__ == "__main__":
    unittest.main()
