# -*- coding: utf-8 -*-
"""
Regression tests for prefetch behavior in StockAnalysisPipeline.run().
"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.core.pipeline import StockAnalysisPipeline
from src.enums import ReportType


class TestPipelinePrefetchBehavior(unittest.TestCase):
    @staticmethod
    def _build_pipeline(process_result):
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.max_workers = 1
        pipeline.fetcher_manager = MagicMock()
        pipeline.db = MagicMock()
        pipeline.db.has_today_data.return_value = False
        pipeline.process_single_stock = MagicMock(return_value=process_result)
        pipeline.config = SimpleNamespace(
            stock_list=["000001"],
            refresh_stock_list=lambda: None,
            single_stock_notify=False,
            report_type="simple",
            analysis_delay=0,
        )
        return pipeline

    def test_run_dry_run_skips_stock_name_prefetch(self):
        pipeline = self._build_pipeline(process_result=None)

        pipeline.run(stock_codes=["000001"], dry_run=True, send_notification=False)

        pipeline.fetcher_manager.prefetch_stock_names.assert_not_called()

    def test_run_non_dry_run_prefetches_stock_names(self):
        pipeline = self._build_pipeline(process_result=SimpleNamespace(code="000001"))

        pipeline.run(stock_codes=["000001"], dry_run=False, send_notification=False)

        pipeline.fetcher_manager.prefetch_stock_names.assert_called_once_with(
            ["000001"], use_bulk=False
        )

    def test_run_maps_detailed_report_type_to_full(self):
        pipeline = self._build_pipeline(process_result=SimpleNamespace(code="000001"))
        pipeline.config.report_type = "detailed"

        pipeline.run(stock_codes=["000001"], dry_run=False, send_notification=False)

        self.assertEqual(
            pipeline.process_single_stock.call_args.kwargs["report_type"],
            ReportType.FULL,
        )

    def test_process_single_stock_forwards_force_refresh_to_data_fetch(self):
        pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
        pipeline.fetch_and_save_stock_data = MagicMock(return_value=(True, None))
        pipeline.analyze_stock = MagicMock()

        result = StockAnalysisPipeline.process_single_stock(
            pipeline,
            "000001",
            skip_analysis=True,
            force_refresh=True,
        )

        self.assertIsNone(result)
        pipeline.fetch_and_save_stock_data.assert_called_once_with(
            "000001",
            force_refresh=True,
        )


if __name__ == "__main__":
    unittest.main()
