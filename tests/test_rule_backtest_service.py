# -*- coding: utf-8 -*-
"""Tests for AI-assisted rule backtesting."""

import os
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

from src.config import Config
from src.core.rule_backtest_engine import RuleBacktestEngine, RuleBacktestParser
from src.services.rule_backtest_service import RuleBacktestService
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
        self.assertEqual(result.execution_assumptions.indicator_price_basis, "close")
        self.assertEqual(result.execution_assumptions.entry_fill_timing, "next_bar_open")

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
        self.assertIn("execution_assumptions", history["items"][0])

        detail = service.get_run(history["items"][0]["id"])
        self.assertIsNotNone(detail)
        self.assertEqual(len(detail["trades"]), response["trade_count"])
        self.assertGreaterEqual(len(detail["status_history"]), 1)
        self.assertIn(detail["status"], {"completed"})
        if detail["trades"]:
            first_trade = detail["trades"][0]
            self.assertIn("entry_trigger", first_trade)
            self.assertIn("price_basis", first_trade)
            self.assertIn("holding_bars", first_trade)

    def test_submit_and_process_backtest_records_async_status_history(self) -> None:
        service = RuleBacktestService(self.db)
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            submitted = service.submit_backtest(
                code="600519",
                strategy_text=strategy_text,
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
        self.assertEqual(detail["summary"]["request"]["confirmed"], True)
        self.assertIn("execution_assumptions", detail["summary"])
        statuses = [item.get("status") for item in detail["status_history"]]
        self.assertIn("running", statuses)
        self.assertIn("summarizing", statuses)
        self.assertIn("completed", statuses)
        self.assertIn("buy_and_hold_return_pct", detail)
        self.assertIn("excess_return_vs_buy_and_hold_pct", detail)


if __name__ == "__main__":
    unittest.main()
