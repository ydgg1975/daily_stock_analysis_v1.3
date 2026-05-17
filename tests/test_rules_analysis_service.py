# -*- coding: utf-8 -*-
"""Tests for RulesAnalysisService."""

import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _make_ohlcv(rows: int = 120) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.bdate_range(end="2024-06-30", periods=rows)
    return pd.DataFrame({
        "close": 100 + np.cumsum(np.random.randn(rows) * 0.5),
        "volume": np.random.randint(500000, 2000000, rows).astype(float),
    }, index=dates)


class TestComputeRulesForDf(unittest.TestCase):

    def test_compute_with_valid_df(self):
        from src.services.rules_analysis_service import RulesAnalysisService
        svc = RulesAnalysisService()
        result = svc.compute_rules_for_df(_make_ohlcv(120), symbol="600519")
        self.assertIsNotNone(result)
        self.assertIsInstance(result.rules_tags, str)
        self.assertIsInstance(result.total_score, float)
        self.assertIsInstance(result.matched_rules, list)
        self.assertEqual(len(result.matched_rules), 22)

    def test_compute_with_empty_df(self):
        from src.services.rules_analysis_service import RulesAnalysisService
        svc = RulesAnalysisService()
        result = svc.compute_rules_for_df(pd.DataFrame())
        self.assertEqual(result.rules_tags, "")
        self.assertEqual(result.total_score, 0.0)

    def test_compute_with_none(self):
        from src.services.rules_analysis_service import RulesAnalysisService
        svc = RulesAnalysisService()
        result = svc.compute_rules_for_df(None)
        self.assertEqual(result.rules_tags, "")


if __name__ == "__main__":
    unittest.main()
