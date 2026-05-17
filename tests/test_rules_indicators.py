# -*- coding: utf-8 -*-
"""Tests for rules engine indicator computation."""

import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _make_ohlcv(rows: int = 120, base_price: float = 100.0) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.bdate_range(end="2024-06-30", periods=rows)
    close = base_price + np.cumsum(np.random.randn(rows) * 0.5)
    return pd.DataFrame({
        "close": close,
        "volume": np.random.randint(500000, 2000000, rows).astype(float),
    }, index=dates)


class TestComputeIndicators(unittest.TestCase):

    def test_returns_dict_with_keys(self):
        from src.rules.indicators import compute_indicators
        df = _make_ohlcv(120)
        result = compute_indicators(df)
        self.assertIsInstance(result, dict)
        self.assertIn("ma5", result)
        self.assertIn("rsi", result)
        self.assertIn("macd_dif", result)
        self.assertIn("boll_upper", result)
        self.assertIn("volume_ratio", result)
        self.assertIn("position_20d", result)

    def test_empty_df_returns_empty_dict(self):
        from src.rules.indicators import compute_indicators
        result = compute_indicators(pd.DataFrame())
        self.assertEqual(result, {})

    def test_none_df_returns_empty_dict(self):
        from src.rules.indicators import compute_indicators
        result = compute_indicators(None)
        self.assertEqual(result, {})

    def test_missing_columns_returns_empty_dict(self):
        from src.rules.indicators import compute_indicators
        df = pd.DataFrame({"open": [1, 2, 3]})
        result = compute_indicators(df)
        self.assertEqual(result, {})

    def test_too_few_rows_returns_empty_dict(self):
        from src.rules.indicators import compute_indicators
        df = pd.DataFrame({"close": [100.0], "volume": [1000.0]})
        result = compute_indicators(df)
        self.assertEqual(result, {})

    def test_ma_values_are_float(self):
        from src.rules.indicators import compute_indicators
        df = _make_ohlcv(120)
        result = compute_indicators(df)
        self.assertIsInstance(result["ma5"], float)
        self.assertIsInstance(result["ma10"], float)
        self.assertIsInstance(result["ma20"], float)

    def test_ma60_none_when_insufficient_data(self):
        from src.rules.indicators import compute_indicators
        df = _make_ohlcv(30)
        result = compute_indicators(df)
        self.assertIsNone(result.get("ma60"))

    def test_rsi_in_range(self):
        from src.rules.indicators import compute_indicators
        df = _make_ohlcv(120)
        result = compute_indicators(df)
        self.assertGreaterEqual(result["rsi"], 0)
        self.assertLessEqual(result["rsi"], 100)

    def test_volume_ratio_positive(self):
        from src.rules.indicators import compute_indicators
        df = _make_ohlcv(120)
        result = compute_indicators(df)
        self.assertGreater(result["volume_ratio"], 0)

    def test_position_between_0_and_1(self):
        from src.rules.indicators import compute_indicators
        df = _make_ohlcv(120)
        result = compute_indicators(df)
        self.assertGreaterEqual(result["position_20d"], 0)
        self.assertLessEqual(result["position_20d"], 1)

    def test_return_values_are_percentages(self):
        from src.rules.indicators import compute_indicators
        df = _make_ohlcv(120)
        result = compute_indicators(df)
        self.assertIsInstance(result["return_5d"], float)

    def test_new_high_low_are_booleans(self):
        from src.rules.indicators import compute_indicators
        df = _make_ohlcv(120)
        result = compute_indicators(df)
        self.assertIsInstance(result["new_high_20d"], bool)
        self.assertIsInstance(result["new_low_20d"], bool)

    def test_ma_alignment_values(self):
        from src.rules.indicators import compute_indicators
        df = _make_ohlcv(120)
        result = compute_indicators(df)
        self.assertIn(result["ma_alignment"], ("bullish", "bearish", "neutral"))

    def test_macd_cross_values(self):
        from src.rules.indicators import compute_indicators
        df = _make_ohlcv(120)
        result = compute_indicators(df)
        self.assertIn(result["macd_cross"], ("golden", "death", "none"))

    def test_boll_position_in_range(self):
        from src.rules.indicators import compute_indicators
        df = _make_ohlcv(120)
        result = compute_indicators(df)
        self.assertGreaterEqual(result["boll_position"], 0)
        self.assertLessEqual(result["boll_position"], 1)

    def test_no_nan_or_inf_in_output(self):
        from src.rules.indicators import compute_indicators
        df = _make_ohlcv(120)
        result = compute_indicators(df)
        for key, val in result.items():
            if val is not None:
                self.assertFalse(
                    isinstance(val, float) and (np.isnan(val) or np.isinf(val)),
                    f"{key} is NaN or inf"
                )


if __name__ == "__main__":
    unittest.main()
