# -*- coding: utf-8 -*-
"""Integration tests for backtest service and repository.

These tests run against a temporary SQLite DB (same approach as other tests)
and validate idempotency/force semantics, result field correctness,
summary creation, and query methods.
"""

import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pandas as pd

from src.config import Config
from src.core.backtest_engine import OVERALL_SENTINEL_CODE
from src.services.backtest_service import BacktestService
from src.storage import AnalysisHistory, BacktestResult, BacktestRun, BacktestSummary, DatabaseManager, StockDaily


class BacktestServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_backtest_service.db")
        self._original_database_path = os.environ.get("DATABASE_PATH")
        self._original_eval_window = os.environ.get("BACKTEST_EVAL_WINDOW_DAYS")
        self._original_min_age = os.environ.get("BACKTEST_MIN_AGE_DAYS")
        os.environ["DATABASE_PATH"] = self._db_path
        os.environ["BACKTEST_EVAL_WINDOW_DAYS"] = "3"
        os.environ["BACKTEST_MIN_AGE_DAYS"] = "14"

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

        # Ensure analysis is old enough for default min_age_days=14
        old_created_at = datetime(2024, 1, 1, 0, 0, 0)

        with self.db.get_session() as session:
            session.add(
                AnalysisHistory(
                    query_id="q1",
                    code="600519",
                    name="贵州茅台",
                    report_type="simple",
                    sentiment_score=80,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="test",
                    stop_loss=95.0,
                    take_profit=110.0,
                    created_at=old_created_at,
                    context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
                )
            )

            # Analysis day close
            session.add(
                StockDaily(
                    code="600519",
                    date=date(2024, 1, 1),
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                )
            )

            # Forward bars (3 days) that hit take-profit on day1
            session.add_all(
                [
                    StockDaily(code="600519", date=date(2024, 1, 2), high=111.0, low=100.0, close=105.0),
                    StockDaily(code="600519", date=date(2024, 1, 3), high=108.0, low=103.0, close=106.0),
                    StockDaily(code="600519", date=date(2024, 1, 4), high=109.0, low=104.0, close=107.0),
                ]
            )
            session.commit()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        if self._original_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = self._original_database_path
        if self._original_eval_window is None:
            os.environ.pop("BACKTEST_EVAL_WINDOW_DAYS", None)
        else:
            os.environ["BACKTEST_EVAL_WINDOW_DAYS"] = self._original_eval_window
        if self._original_min_age is None:
            os.environ.pop("BACKTEST_MIN_AGE_DAYS", None)
        else:
            os.environ["BACKTEST_MIN_AGE_DAYS"] = self._original_min_age
        self._temp_dir.cleanup()

    def _count_results(self) -> int:
        with self.db.get_session() as session:
            return session.query(BacktestResult).count()

    def _count_runs(self) -> int:
        with self.db.get_session() as session:
            return session.query(BacktestRun).count()

    def test_force_semantics(self) -> None:
        service = BacktestService(self.db)

        stats1 = service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)
        self.assertEqual(stats1["saved"], 1)
        self.assertEqual(self._count_results(), 1)

        # Non-force should be idempotent
        stats2 = service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)
        self.assertEqual(stats2["saved"], 0)
        self.assertEqual(self._count_results(), 1)

        # Force should replace existing result without unique constraint errors
        stats3 = service.run_backtest(code="600519", force=True, eval_window_days=3, min_age_days=0, limit=10)
        self.assertEqual(stats3["saved"], 1)
        self.assertEqual(self._count_results(), 1)

    def _run_and_get_result(self) -> BacktestResult:
        """Helper: run backtest and return the single BacktestResult row."""
        service = BacktestService(self.db)
        service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)
        with self.db.get_session() as session:
            return session.query(BacktestResult).one()

    def test_result_fields_correct(self) -> None:
        """Verify BacktestResult row contains correct evaluation values."""
        result = self._run_and_get_result()

        self.assertEqual(result.eval_status, "completed")
        self.assertEqual(result.code, "600519")
        self.assertEqual(result.analysis_date, date(2024, 1, 1))
        self.assertEqual(result.operation_advice, "买入")
        self.assertEqual(result.position_recommendation, "long")
        self.assertEqual(result.direction_expected, "up")

        # Prices
        self.assertAlmostEqual(result.start_price, 100.0)
        self.assertAlmostEqual(result.end_close, 107.0)
        self.assertAlmostEqual(result.stock_return_pct, 7.0)

        # Direction & outcome
        self.assertEqual(result.outcome, "win")
        self.assertTrue(result.direction_correct)

        # Target hits -- day2 high=111 >= take_profit=110
        self.assertTrue(result.hit_take_profit)
        self.assertFalse(result.hit_stop_loss)
        self.assertEqual(result.first_hit, "take_profit")
        self.assertEqual(result.first_hit_trading_days, 1)
        self.assertEqual(result.first_hit_date, date(2024, 1, 2))

        # Simulated execution
        self.assertAlmostEqual(result.simulated_entry_price, 100.0)
        self.assertAlmostEqual(result.simulated_exit_price, 110.0)
        self.assertEqual(result.simulated_exit_reason, "take_profit")
        self.assertAlmostEqual(result.simulated_return_pct, 10.0)

    def test_summaries_created_after_run(self) -> None:
        """Verify both overall and per-stock BacktestSummary rows are created."""
        service = BacktestService(self.db)
        service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        with self.db.get_session() as session:
            # Overall summary uses sentinel code
            overall = session.query(BacktestSummary).filter(
                BacktestSummary.scope == "overall",
                BacktestSummary.code == OVERALL_SENTINEL_CODE,
            ).first()
            self.assertIsNotNone(overall)
            self.assertEqual(overall.total_evaluations, 1)
            self.assertEqual(overall.completed_count, 1)
            self.assertEqual(overall.win_count, 1)
            self.assertEqual(overall.loss_count, 0)
            self.assertAlmostEqual(overall.win_rate_pct, 100.0)

            # Stock-level summary
            stock = session.query(BacktestSummary).filter(
                BacktestSummary.scope == "stock",
                BacktestSummary.code == "600519",
            ).first()
            self.assertIsNotNone(stock)
            self.assertEqual(stock.total_evaluations, 1)
            self.assertEqual(stock.completed_count, 1)
            self.assertEqual(stock.win_count, 1)

    def test_get_summary_overall_returns_sentinel_as_none(self) -> None:
        """Verify get_summary translates __overall__ sentinel back to None."""
        service = BacktestService(self.db)
        service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        summary = service.get_summary(scope="overall", code=None)
        self.assertIsNotNone(summary)
        self.assertIsNone(summary["code"])
        self.assertEqual(summary["scope"], "overall")
        self.assertEqual(summary["win_count"], 1)

    def test_agent_learning_summary_helpers_keep_skill_rollups_neutral_until_supported(self) -> None:
        service = BacktestService(self.db)
        service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        global_summary = service.get_global_summary(eval_window_days=3)
        stock_summary = service.get_stock_summary("600519", eval_window_days=3)
        skill_summary = service.get_skill_summary("bull_trend", eval_window_days=3)
        strategy_summary = service.get_strategy_summary("bull_trend", eval_window_days=3)

        self.assertIsNotNone(global_summary)
        self.assertEqual(global_summary["total_evaluations"], 1)
        self.assertAlmostEqual(global_summary["win_rate"], 1.0)
        self.assertAlmostEqual(global_summary["direction_accuracy"], 1.0)
        self.assertAlmostEqual(global_summary["avg_return"], 0.10)

        self.assertIsNotNone(stock_summary)
        self.assertEqual(stock_summary["code"], "600519")
        self.assertAlmostEqual(stock_summary["win_rate"], 1.0)

        self.assertIsNone(skill_summary)
        self.assertIsNone(strategy_summary)

    def test_get_recent_evaluations(self) -> None:
        """Verify get_recent_evaluations returns correct paginated results."""
        service = BacktestService(self.db)
        service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        data = service.get_recent_evaluations(code="600519", limit=10, page=1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["limit"], 10)
        self.assertEqual(len(data["items"]), 1)

        item = data["items"][0]
        self.assertEqual(item["code"], "600519")
        self.assertEqual(item["outcome"], "win")
        self.assertEqual(item["direction_expected"], "up")
        self.assertTrue(item["direction_correct"])
        self.assertEqual(item["evaluation_window_trading_bars"], 3)
        self.assertIn("execution_assumptions", item)

    def test_historical_source_metadata_fields_appear_in_contract(self) -> None:
        service = BacktestService(self.db)
        stats = service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        self.assertEqual(stats["requested_mode"], "auto")
        self.assertEqual(stats["resolved_source"], "DatabaseCache")
        self.assertFalse(stats["fallback_used"])
        self.assertIn("latest_prepared_sample_date", stats)
        self.assertIn("latest_eligible_sample_date", stats)
        self.assertIn("pricing_resolved_source", stats)
        self.assertIn("pricing_fallback_used", stats)

        history = service.list_backtest_runs(code="600519", page=1, limit=10)
        history_item = history["items"][0]
        self.assertEqual(history_item["requested_mode"], "auto")
        self.assertEqual(history_item["resolved_source"], "DatabaseCache")
        self.assertFalse(history_item["fallback_used"])

        summary = service.get_summary(scope="stock", code="600519", eval_window_days=3)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["requested_mode"], "auto")
        self.assertEqual(summary["resolved_source"], "DatabaseCache")
        self.assertFalse(summary["fallback_used"])

    def test_get_sample_status_allows_zero_maturity_days_from_config(self) -> None:
        os.environ["BACKTEST_MIN_AGE_DAYS"] = "0"
        Config._instance = None

        service = BacktestService(self.db)
        status = service.get_sample_status(code="600519")

        self.assertEqual(status["min_age_days"], 0)
        self.assertEqual(status["maturity_calendar_days"], 0)
        self.assertEqual(status["requested_mode"], "auto")
        self.assertEqual(status["resolved_source"], "Unknown")
        self.assertFalse(status["fallback_used"])

    def test_run_history_is_recorded_and_results_can_be_reopened(self) -> None:
        service = BacktestService(self.db)
        stats = service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        self.assertIsNotNone(stats["run_id"])
        self.assertEqual(self._count_runs(), 1)
        self.assertEqual(stats["evaluation_mode"], "historical_analysis_evaluation")
        self.assertEqual(stats["evaluation_window_trading_bars"], 3)
        self.assertEqual(stats["maturity_calendar_days"], 0)
        self.assertIn("execution_assumptions", stats)

        history = service.list_backtest_runs(code="600519", page=1, limit=10)
        self.assertEqual(history["total"], 1)
        item = history["items"][0]
        self.assertEqual(item["code"], "600519")
        self.assertEqual(item["candidate_count"], 1)
        self.assertGreaterEqual(item["win_rate_pct"], 0)
        self.assertEqual(item["evaluation_mode"], "historical_analysis_evaluation")
        self.assertEqual(item["evaluation_window_trading_bars"], 3)
        self.assertEqual(item["maturity_calendar_days"], 0)

        run_results = service.get_run_results(run_id=item["id"], page=1, limit=10)
        self.assertEqual(run_results["total"], 1)
        self.assertEqual(run_results["items"][0]["code"], "600519")

    def test_run_with_only_recent_analysis_reports_insufficient_history_reason(self) -> None:
        recent_created_at = datetime.now() - timedelta(days=1)
        with self.db.get_session() as session:
            session.add(
                AnalysisHistory(
                    query_id="q-recent",
                    code="000001",
                    name="平安银行",
                    report_type="simple",
                    sentiment_score=55,
                    operation_advice="持有",
                    trend_prediction="震荡",
                    analysis_summary="recent",
                    stop_loss=9.5,
                    take_profit=11.0,
                    created_at=recent_created_at,
                    context_snapshot='{"enhanced_context": {"date": "' + recent_created_at.strftime('%Y-%m-%d') + '"}}',
                )
            )
            session.commit()

        service = BacktestService(self.db)
        stats = service.run_backtest(code="000001", force=False, eval_window_days=3, limit=10)

        self.assertEqual(stats["processed"], 0)
        self.assertEqual(stats["saved"], 0)
        self.assertEqual(stats["candidate_count"], 0)
        self.assertEqual(stats["no_result_reason"], "insufficient_historical_data")
        self.assertIn("14 天", stats["no_result_message"])

    def test_prepare_backtest_samples_populates_analysis_history_and_enables_run(self) -> None:
        with self.db.get_session() as session:
            session.add_all([
                StockDaily(code="000001", date=date(2024, 1, 1), open=10.0, high=10.2, low=9.8, close=10.0),
                StockDaily(code="000001", date=date(2024, 1, 2), open=10.1, high=10.8, low=10.0, close=10.6),
                StockDaily(code="000001", date=date(2024, 1, 3), open=10.6, high=10.7, low=10.2, close=10.3),
                StockDaily(code="000001", date=date(2024, 1, 4), open=10.3, high=10.6, low=10.1, close=10.5),
                StockDaily(code="000001", date=date(2024, 1, 5), open=10.5, high=10.9, low=10.4, close=10.8),
                StockDaily(code="000001", date=date(2024, 1, 8), open=10.8, high=11.1, low=10.7, close=11.0),
                StockDaily(code="000001", date=date(2024, 1, 9), open=11.0, high=11.3, low=10.9, close=11.2),
                StockDaily(code="000001", date=date(2024, 1, 10), open=11.2, high=11.4, low=11.0, close=11.1),
                StockDaily(code="000001", date=date(2024, 1, 11), open=11.1, high=11.5, low=11.0, close=11.4),
                StockDaily(code="000001", date=date(2024, 1, 12), open=11.4, high=11.7, low=11.2, close=11.6),
                StockDaily(code="000001", date=date(2024, 1, 15), open=11.6, high=11.8, low=11.3, close=11.5),
                StockDaily(code="000001", date=date(2024, 1, 16), open=11.5, high=11.9, low=11.4, close=11.8),
                StockDaily(code="000001", date=date(2024, 1, 17), open=11.8, high=12.0, low=11.6, close=11.7),
                StockDaily(code="000001", date=date(2024, 1, 18), open=11.7, high=12.2, low=11.6, close=12.1),
                StockDaily(code="000001", date=date(2024, 1, 19), open=12.1, high=12.4, low=12.0, close=12.3),
            ])
            session.commit()

        service = BacktestService(self.db)
        prep = service.prepare_backtest_samples(code="000001", sample_count=252, eval_window_days=3, min_age_days=14)
        self.assertGreater(prep["prepared"], 0)
        self.assertEqual(prep["sample_count"], 252)

        with self.db.get_session() as session:
            prepared_count = session.query(AnalysisHistory).filter(AnalysisHistory.code == "000001").count()
            self.assertGreater(prepared_count, 0)

        status = service.get_sample_status(code="000001")
        self.assertGreater(status["prepared_count"], 0)
        self.assertIsNotNone(status["prepared_start_date"])
        self.assertIsNotNone(status["prepared_end_date"])

        stats = service.run_backtest(code="000001", force=False, eval_window_days=3, min_age_days=14, limit=10)
        self.assertGreater(stats["saved"], 0)
        self.assertGreater(stats["completed"], 0)

        recent = service.get_recent_evaluations(code="000001", eval_window_days=3, limit=10, page=1)
        self.assertGreater(recent["total"], 0)

    def test_prepare_samples_reports_local_first_source_metadata_on_local_hit(self) -> None:
        frame = pd.DataFrame(
            [
                {"date": "2024-01-01", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10},
                {"date": "2024-01-02", "open": 101.0, "high": 102.0, "low": 100.0, "close": 101.0, "volume": 10},
                {"date": "2024-01-03", "open": 102.0, "high": 103.0, "low": 101.0, "close": 102.0, "volume": 10},
                {"date": "2024-01-04", "open": 103.0, "high": 104.0, "low": 102.0, "close": 103.0, "volume": 10},
                {"date": "2024-01-05", "open": 104.0, "high": 105.0, "low": 103.0, "close": 104.0, "volume": 10},
                {"date": "2024-01-08", "open": 105.0, "high": 106.0, "low": 104.0, "close": 105.0, "volume": 10},
                {"date": "2024-01-09", "open": 106.0, "high": 107.0, "low": 105.0, "close": 106.0, "volume": 10},
            ]
        )
        service = BacktestService(self.db)

        with patch.object(service, "_load_history_with_local_us_fallback", return_value=(frame, "local_us_parquet")):
            prep = service.prepare_backtest_samples(code="AAPL", sample_count=2, eval_window_days=3, min_age_days=14)

        self.assertEqual(prep["requested_mode"], "local_first")
        self.assertEqual(prep["resolved_source"], "LocalParquet")
        self.assertFalse(prep["fallback_used"])
        self.assertEqual(prep["latest_prepared_sample_date"], "2024-01-04")
        self.assertEqual(prep["latest_eligible_sample_date"], "2024-01-04")
        self.assertEqual(prep["excluded_recent_reason"], "evaluation_window_not_satisfied")
        self.assertEqual(prep["pricing_resolved_source"], "LocalParquet")
        self.assertFalse(prep["pricing_fallback_used"])

        status = service.get_sample_status(code="AAPL")
        self.assertEqual(status["latest_prepared_sample_date"], "2024-01-04")
        self.assertEqual(status["latest_eligible_sample_date"], "2024-01-04")
        self.assertEqual(status["excluded_recent_reason"], "evaluation_window_not_satisfied")
        self.assertEqual(status["pricing_resolved_source"], "LocalParquet")
        self.assertFalse(status["pricing_fallback_used"])

    def test_prepare_samples_reports_fallback_used_on_us_api_fallback(self) -> None:
        frame = pd.DataFrame(
            [
                {"date": "2024-01-01", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10},
                {"date": "2024-01-02", "open": 101.0, "high": 102.0, "low": 100.0, "close": 101.0, "volume": 10},
                {"date": "2024-01-03", "open": 102.0, "high": 103.0, "low": 101.0, "close": 102.0, "volume": 10},
                {"date": "2024-01-04", "open": 103.0, "high": 104.0, "low": 102.0, "close": 103.0, "volume": 10},
                {"date": "2024-01-05", "open": 104.0, "high": 105.0, "low": 103.0, "close": 104.0, "volume": 10},
                {"date": "2024-01-08", "open": 105.0, "high": 106.0, "low": 104.0, "close": 105.0, "volume": 10},
                {"date": "2024-01-09", "open": 106.0, "high": 107.0, "low": 105.0, "close": 106.0, "volume": 10},
            ]
        )
        service = BacktestService(self.db)

        with patch.object(service, "_load_history_with_local_us_fallback", return_value=(frame, "yfinance")):
            prep = service.prepare_backtest_samples(code="AAPL", sample_count=2, eval_window_days=3, min_age_days=14)

        self.assertEqual(prep["requested_mode"], "local_first")
        self.assertEqual(prep["resolved_source"], "YfinanceFetcher")
        self.assertTrue(prep["fallback_used"])
        self.assertEqual(prep["pricing_resolved_source"], "YfinanceFetcher")
        self.assertTrue(prep["pricing_fallback_used"])

    def test_sample_status_reports_maturity_window_exclusion_for_recent_samples(self) -> None:
        recent_created_at = datetime.now() - timedelta(days=2)
        old_created_at = datetime.now() - timedelta(days=20)
        with self.db.get_session() as session:
            session.add_all([
                AnalysisHistory(
                    query_id="bt-sample:000001:2024-03-01:w3",
                    code="000001",
                    name="平安银行",
                    report_type="backtest_sample",
                    sentiment_score=60,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="old",
                    raw_result='{"market_data_source":"db_cache"}',
                    context_snapshot='{"enhanced_context": {"date": "2024-03-01"}}',
                    created_at=old_created_at,
                ),
                AnalysisHistory(
                    query_id="bt-sample:000001:2024-03-20:w3",
                    code="000001",
                    name="平安银行",
                    report_type="backtest_sample",
                    sentiment_score=60,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="recent",
                    raw_result='{"market_data_source":"db_cache"}',
                    context_snapshot='{"enhanced_context": {"date": "2024-03-20"}}',
                    created_at=recent_created_at,
                ),
            ])
            session.commit()

        service = BacktestService(self.db)
        status = service.get_sample_status(code="000001")

        self.assertEqual(status["latest_prepared_sample_date"], "2024-03-20")
        self.assertEqual(status["latest_eligible_sample_date"], "2024-03-01")
        self.assertEqual(status["excluded_recent_reason"], "maturity_window_not_satisfied")
        self.assertIn("成熟期", status["excluded_recent_message"])

    def test_clear_samples_and_results_separate_reset_paths(self) -> None:
        service = BacktestService(self.db)
        service.prepare_backtest_samples(code="600519", sample_count=60, eval_window_days=3, min_age_days=14)
        service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=14, limit=10)
        self.assertGreater(self._count_results(), 0)
        self.assertEqual(self._count_runs(), 1)

        cleared_results = service.clear_backtest_results(code="600519")
        self.assertGreaterEqual(cleared_results["deleted_results"], 1)
        self.assertEqual(cleared_results["deleted_samples"], 0)
        self.assertEqual(self._count_runs(), 0)
        self.assertEqual(self._count_results(), 0)

        status_after_results_clear = service.get_sample_status(code="600519")
        self.assertGreater(status_after_results_clear["prepared_count"], 0)

        cleared_samples = service.clear_backtest_samples(code="600519")
        self.assertGreaterEqual(cleared_samples["deleted_samples"], 1)
        self.assertEqual(self._count_runs(), 0)
        self.assertEqual(self._count_results(), 0)
        status_after_samples_clear = service.get_sample_status(code="600519")
        self.assertEqual(status_after_samples_clear["prepared_count"], 0)

    def test_multi_stock_summaries(self) -> None:
        """Verify separate summaries for multiple stocks + correct overall aggregate."""
        old_created_at = datetime(2024, 1, 1, 0, 0, 0)

        with self.db.get_session() as session:
            # Second stock with sell advice -- price drops (win for cash/down)
            session.add(
                AnalysisHistory(
                    query_id="q2",
                    code="000001",
                    name="平安银行",
                    report_type="simple",
                    sentiment_score=30,
                    operation_advice="卖出",
                    trend_prediction="看空",
                    analysis_summary="test2",
                    stop_loss=None,
                    take_profit=None,
                    created_at=old_created_at,
                    context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
                )
            )
            session.add(
                StockDaily(code="000001", date=date(2024, 1, 1), open=10.0, high=10.2, low=9.8, close=10.0)
            )
            session.add_all([
                StockDaily(code="000001", date=date(2024, 1, 2), high=10.0, low=9.5, close=9.6),
                StockDaily(code="000001", date=date(2024, 1, 3), high=9.7, low=9.3, close=9.4),
                StockDaily(code="000001", date=date(2024, 1, 4), high=9.5, low=9.0, close=9.1),
            ])
            session.commit()

        service = BacktestService(self.db)
        stats = service.run_backtest(code=None, force=False, eval_window_days=3, min_age_days=0, limit=10)
        self.assertEqual(stats["saved"], 2)
        self.assertEqual(stats["completed"], 2)

        with self.db.get_session() as session:
            # Each stock has its own summary
            s1 = session.query(BacktestSummary).filter(
                BacktestSummary.scope == "stock", BacktestSummary.code == "600519"
            ).first()
            s2 = session.query(BacktestSummary).filter(
                BacktestSummary.scope == "stock", BacktestSummary.code == "000001"
            ).first()
            self.assertIsNotNone(s1)
            self.assertIsNotNone(s2)
            self.assertEqual(s1.win_count, 1)
            self.assertEqual(s2.win_count, 1)

            # Overall aggregates both
            overall = session.query(BacktestSummary).filter(
                BacktestSummary.scope == "overall",
                BacktestSummary.code == OVERALL_SENTINEL_CODE,
            ).first()
            self.assertIsNotNone(overall)
            self.assertEqual(overall.total_evaluations, 2)
            self.assertEqual(overall.completed_count, 2)
            self.assertEqual(overall.win_count, 2)


if __name__ == "__main__":
    unittest.main()
