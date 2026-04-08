# -*- coding: utf-8 -*-
"""Regression tests for shared US history loading helpers."""

from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from src.services.us_history_helper import (
    LOCAL_US_PARQUET_SOURCE,
    LocalUsHistoryLoadResult,
    fetch_daily_history_with_local_us_fallback,
)


class UsHistoryHelperTestCase(unittest.TestCase):
    def test_fetch_daily_history_prefers_local_us_parquet_hit(self) -> None:
        local_df = pd.DataFrame({"date": ["2024-01-01"], "close": [100.0]})
        manager = MagicMock()

        with patch(
            "src.services.us_history_helper.load_local_us_daily_history",
            return_value=LocalUsHistoryLoadResult(
                stock_code="AAPL",
                path=Path("/tmp/AAPL.parquet"),
                status="hit",
                dataframe=local_df,
            ),
        ):
            df, source = fetch_daily_history_with_local_us_fallback(
                "AAPL",
                days=20,
                manager=manager,
                log_context="[test history]",
            )

        self.assertIs(df, local_df)
        self.assertEqual(source, LOCAL_US_PARQUET_SOURCE)
        manager.get_daily_data.assert_not_called()

    def test_fetch_daily_history_falls_back_to_api_with_normalized_dates(self) -> None:
        fallback_df = pd.DataFrame({"date": ["2024-01-01"], "close": [100.0]})
        manager = MagicMock()
        manager.get_daily_data.return_value = (fallback_df, "stub_api")

        with patch(
            "src.services.us_history_helper.load_local_us_daily_history",
            return_value=LocalUsHistoryLoadResult(
                stock_code="AAPL",
                path=Path("/tmp/AAPL.parquet"),
                status="missing",
            ),
        ):
            df, source = fetch_daily_history_with_local_us_fallback(
                "aapl",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                days=20,
                manager=manager,
                log_context="[test history]",
            )

        self.assertIs(df, fallback_df)
        self.assertEqual(source, "stub_api")
        manager.get_daily_data.assert_called_once_with(
            stock_code="AAPL",
            start_date="2024-01-01",
            end_date="2024-01-31",
            days=20,
        )


if __name__ == "__main__":
    unittest.main()
