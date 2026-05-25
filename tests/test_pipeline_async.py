# -*- coding: utf-8 -*-
"""
Tests for AsyncStockAnalysisPipeline.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.litellm_stub import ensure_litellm_stub
ensure_litellm_stub()

from src.core.pipeline_async import AsyncStockAnalysisPipeline
from src.analyzer.core import AnalysisResult
from src.enums import ReportType


class TestAsyncStockAnalysisPipeline(unittest.IsolatedAsyncioTestCase):
    """Test cases for AsyncStockAnalysisPipeline using IsolatedAsyncioTestCase."""

    def setUp(self):
        self.mock_config = MagicMock()
        self.mock_config.max_workers = 2
        self.mock_config.save_context_snapshot = False

    @patch('src.core.pipeline_async.StockAnalysisPipeline')
    def test_pipeline_init(self, mock_sync_pipeline_cls):
        """Pipeline should initialize and configure sync pipeline correctly."""
        pipeline = AsyncStockAnalysisPipeline(config=self.mock_config, query_id="test_query")
        
        self.assertEqual(pipeline.query_id, "test_query")
        self.assertEqual(pipeline.query_source, "async_cli")
        mock_sync_pipeline_cls.assert_called_once()

    @patch('src.core.pipeline_async.StockAnalysisPipeline')
    async def test_fetch_and_save_stock_data_async(self, mock_sync_pipeline_cls):
        """fetch_and_save_stock_data_async should run the sync fetcher in a thread and return results."""
        mock_sync_pipeline = MagicMock()
        mock_sync_pipeline.fetch_and_save_stock_data.return_value = (True, None)
        mock_sync_pipeline_cls.return_value = mock_sync_pipeline

        pipeline = AsyncStockAnalysisPipeline(config=self.mock_config)
        success, err = await pipeline.fetch_and_save_stock_data_async("AAPL")

        self.assertTrue(success)
        self.assertNil = err
        mock_sync_pipeline.fetch_and_save_stock_data.assert_called_once_with(
            code="AAPL", force_refresh=False, current_time=None
        )

    @patch('src.core.pipeline_async.StockAnalysisPipeline')
    async def test_analyze_stock_async(self, mock_sync_pipeline_cls):
        """analyze_stock_async should execute analysis in a thread and return AnalysisResult."""
        mock_sync_pipeline = MagicMock()
        mock_result = AnalysisResult(
            code="AAPL", name="Apple Inc.", sentiment_score=75,
            trend_prediction="Bullish", operation_advice="Buy"
        )
        mock_sync_pipeline.analyze_stock.return_value = mock_result
        mock_sync_pipeline_cls.return_value = mock_sync_pipeline

        pipeline = AsyncStockAnalysisPipeline(config=self.mock_config)
        result = await pipeline.analyze_stock_async("AAPL", report_type=ReportType.SIMPLE)

        self.assertEqual(result.code, "AAPL")
        self.assertEqual(result.sentiment_score, 75)
        mock_sync_pipeline.analyze_stock.assert_called_once_with(
            code="AAPL", report_type=ReportType.SIMPLE, query_id=pipeline.query_id
        )

    @patch('src.core.pipeline_async.StockAnalysisPipeline')
    async def test_run_async(self, mock_sync_pipeline_cls):
        """run_async should execute both parallel data fetching and parallel analysis."""
        mock_sync_pipeline = MagicMock()
        mock_sync_pipeline.fetch_and_save_stock_data.side_effect = [
            (True, None),
            (False, "error"),
        ]
        
        result_aapl = AnalysisResult(
            code="AAPL", name="Apple Inc.", sentiment_score=80,
            trend_prediction="Bullish", operation_advice="Buy"
        )
        mock_sync_pipeline.analyze_stock.return_value = result_aapl
        mock_sync_pipeline_cls.return_value = mock_sync_pipeline

        pipeline = AsyncStockAnalysisPipeline(config=self.mock_config)
        results = await pipeline.run_async(["AAPL", "MSFT"], report_type=ReportType.SIMPLE)

        # MSFT fetch failed, so only AAPL should be analyzed
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].code, "AAPL")
        self.assertEqual(mock_sync_pipeline.fetch_and_save_stock_data.call_count, 2)
        mock_sync_pipeline.analyze_stock.assert_called_once_with(
            code="AAPL", report_type=ReportType.SIMPLE, query_id=pipeline.query_id
        )


if __name__ == '__main__':
    unittest.main()
