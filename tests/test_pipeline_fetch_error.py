# -*- coding: utf-8 -*-
"""Regression tests for pipeline data-fetch error handling."""

from datetime import date, datetime, timezone
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from src.core.pipeline import StockAnalysisPipeline
from src.enums import ReportType


class PipelineFetchErrorTestCase(unittest.TestCase):
    """`fetch_and_save_stock_data` should preserve the original exception."""

    def test_fetch_and_save_handles_stock_name_lookup_failure(self):
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.fetcher_manager = MagicMock()
        pipeline.db = MagicMock()
        pipeline.fetcher_manager.get_stock_name.side_effect = RuntimeError("name lookup failed")

        success, error = StockAnalysisPipeline.fetch_and_save_stock_data(pipeline, "600519")

        self.assertFalse(success)
        self.assertIn("name lookup failed", error or "")

    @patch.object(
        StockAnalysisPipeline,
        "_resolve_resume_target_date",
        return_value=date(2026, 3, 27),
    )
    def test_fetch_and_save_uses_effective_trading_date_for_resume_check(self, _mock_target):
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.fetcher_manager = MagicMock()
        pipeline.db = MagicMock()
        pipeline.fetcher_manager.get_stock_name.return_value = "贵州茅台"
        pipeline.db.has_today_data.return_value = True
        current_time = datetime(2026, 3, 28, 1, 0, tzinfo=timezone.utc)

        success, error = StockAnalysisPipeline.fetch_and_save_stock_data(
            pipeline,
            "600519",
            current_time=current_time,
        )

        self.assertTrue(success)
        self.assertIsNone(error)
        _mock_target.assert_called_once_with("600519", current_time=current_time)
        pipeline.db.has_today_data.assert_called_once_with("600519", date(2026, 3, 27))
        pipeline.fetcher_manager.get_daily_data.assert_not_called()

    def test_resolve_resume_target_date_normalizes_supported_a_share_formats(self):
        with patch("src.core.pipeline.get_market_for_stock", return_value="cn") as mock_market, patch(
            "src.core.pipeline.get_effective_trading_date",
            return_value=date(2026, 3, 27),
        ) as mock_target:
            for code in ("SH600519", "000001.SZ", "BJ920748"):
                result = StockAnalysisPipeline._resolve_resume_target_date(code)
                self.assertEqual(result, date(2026, 3, 27))

        self.assertEqual(
            [args.args[0] for args in mock_market.call_args_list],
            ["600519", "000001", "920748"],
        )
        self.assertEqual(mock_target.call_count, 3)

    def test_fetch_and_save_stock_data_returns_resolved_code_when_requested(self):
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.fetcher_manager = MagicMock()
        pipeline.db = MagicMock()
        pipeline.fetcher_manager.get_stock_name.return_value = "牧原股份"
        pipeline.db.has_today_data.return_value = False
        daily_df = pd.DataFrame(
            [
                {
                    "date": "2026-03-01",
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                    "volume": 1,
                    "amount": 1.0,
                    "pct_chg": 0.0,
                }
            ]
        )
        pipeline.fetcher_manager.get_daily_data.return_value = (
            daily_df,
            "mock_fetcher",
            "002714",
        )
        pipeline.db.save_daily_data.return_value = 1

        success, error, resolved_code = pipeline.fetch_and_save_stock_data(
            "02714",
            return_resolved_code=True,
        )

        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(resolved_code, "002714")
        pipeline.db.save_daily_data.assert_called_once_with(daily_df, "002714", "mock_fetcher")

    def test_process_single_stock_uses_resolved_code_for_downstream_analysis(self):
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.fetcher_manager = MagicMock()
        pipeline.db = MagicMock()
        pipeline.fetcher_manager.get_stock_name.return_value = "牧原股份"
        pipeline.db.has_today_data.return_value = False
        pipeline.fetcher_manager.get_daily_data.return_value = (
            pd.DataFrame(
                [
                    {
                        "date": "2026-03-01",
                        "open": 1.0,
                        "high": 1.0,
                        "low": 1.0,
                        "close": 1.0,
                        "volume": 1,
                        "amount": 1.0,
                        "pct_chg": 0.0,
                    }
                ]
            ),
            "mock_fetcher",
            "002714",
        )
        pipeline.db.save_daily_data.return_value = 1
        analysis_result = MagicMock(
            success=True,
            operation_advice="持有",
            sentiment_score=50,
        )
        pipeline.analyze_stock = MagicMock(return_value=analysis_result)

        pipeline.process_single_stock(
            "02714",
            single_stock_notify=False,
            report_type=ReportType.SIMPLE,
        )

        args, _kwargs = pipeline.analyze_stock.call_args
        self.assertEqual(args[0], "002714")
        self.assertEqual(args[1], ReportType.SIMPLE)


if __name__ == "__main__":
    unittest.main()
