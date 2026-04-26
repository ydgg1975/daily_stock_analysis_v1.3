"""
Unit tests for valuation feature calculation.

Tests the compute_valuation_features() function and ValuationFeatures dataclass.
"""

import unittest
from typing import Dict, List

try:
    from src.market_diagnostic.features.valuation import (
        ValuationFeatures,
        compute_valuation_features,
        _safe_divide,
        _compute_percentile,
        _classify_valuation_level,
    )
except ImportError:
    from market_diagnostic.features.valuation import (  # type: ignore[no-redef]
        ValuationFeatures,
        compute_valuation_features,
        _safe_divide,
        _compute_percentile,
        _classify_valuation_level,
    )


class TestSafeDivide(unittest.TestCase):
    """Tests for _safe_divide helper function."""
    
    def test_normal_division(self):
        """Test normal division."""
        result = _safe_divide(10.0, 2.0)
        self.assertEqual(result, 5.0)
    
    def test_division_by_zero(self):
        """Test division by zero returns default."""
        result = _safe_divide(10.0, 0.0, default=0.0)
        self.assertEqual(result, 0.0)
    
    def test_division_by_infinity(self):
        """Test division by infinity returns default."""
        result = _safe_divide(10.0, float('inf'), default=0.0)
        self.assertEqual(result, 0.0)


class TestComputePercentile(unittest.TestCase):
    """Tests for _compute_percentile helper function."""
    
    def test_percentile_calculation(self):
        """Test percentile calculation with valid data."""
        historical = [10.0, 12.0, 15.0, 18.0, 20.0, 22.0, 25.0, 28.0, 30.0, 35.0]
        percentile = _compute_percentile(20.0, historical)
        self.assertIsNotNone(percentile)
        self.assertGreaterEqual(percentile, 0.0)
        self.assertLessEqual(percentile, 100.0)
    
    def test_insufficient_data(self):
        """Test percentile returns None with insufficient data."""
        historical = [10.0, 12.0, 15.0]
        percentile = _compute_percentile(20.0, historical)
        self.assertIsNone(percentile)
    
    def test_empty_list(self):
        """Test percentile returns None with empty list."""
        percentile = _compute_percentile(20.0, [])
        self.assertIsNone(percentile)


class TestClassifyValuationLevel(unittest.TestCase):
    """Tests for _classify_valuation_level helper function."""
    
    def test_bubble_classification(self):
        """Test bubble classification."""
        # High PE percentile
        level = _classify_valuation_level(95.0, 50.0, 50.0, 0.01)
        self.assertEqual(level, "bubble")
        
        # High PB percentile
        level = _classify_valuation_level(50.0, 95.0, 50.0, 0.01)
        self.assertEqual(level, "bubble")
        
        # High Graham Index
        level = _classify_valuation_level(50.0, 50.0, 120.0, 0.01)
        self.assertEqual(level, "bubble")
        
        # Negative FED spread
        level = _classify_valuation_level(50.0, 50.0, 50.0, -0.03)
        self.assertEqual(level, "bubble")
    
    def test_overvalued_classification(self):
        """Test overvalued classification."""
        # High PE percentile
        level = _classify_valuation_level(75.0, 50.0, 50.0, 0.01)
        self.assertEqual(level, "overvalued")
        
        # High Graham Index
        level = _classify_valuation_level(50.0, 50.0, 70.0, 0.01)
        self.assertEqual(level, "overvalued")
        
        # Negative FED spread
        level = _classify_valuation_level(50.0, 50.0, 50.0, -0.01)
        self.assertEqual(level, "overvalued")
    
    def test_undervalued_classification(self):
        """Test undervalued classification."""
        level = _classify_valuation_level(25.0, 25.0, 20.0, 0.03)
        self.assertEqual(level, "undervalued")
    
    def test_fair_classification(self):
        """Test fair valuation classification."""
        level = _classify_valuation_level(50.0, 50.0, 40.0, 0.01)
        self.assertEqual(level, "fair")


class TestComputeValuationFeatures(unittest.TestCase):
    """Tests for compute_valuation_features function."""
    
    def test_basic_calculation(self):
        """Test basic valuation feature calculation."""
        valuation_data = {
            'csi300_pe': 12.5,
            'csi300_pb': 1.5,
            'csi500_pe': 18.0,
            'csi500_pb': 2.0,
            'csi1000_pe': 25.0,
            'csi1000_pb': 2.5,
            'bond_yield_10y': 2.8,
            'bond_yield_1y': 2.0,
        }
        
        features = compute_valuation_features(valuation_data)
        
        # Verify PE/PB values
        self.assertEqual(features.csi300_pe, 12.5)
        self.assertEqual(features.csi300_pb, 1.5)
        self.assertEqual(features.csi500_pe, 18.0)
        self.assertEqual(features.csi500_pb, 2.0)
        self.assertEqual(features.csi1000_pe, 25.0)
        self.assertEqual(features.csi1000_pb, 2.5)
        
        # Verify bond yields
        self.assertEqual(features.bond_yield_10y, 2.8)
        self.assertEqual(features.bond_yield_1y, 2.0)
        
        # Verify term spread
        self.assertAlmostEqual(features.term_spread, 0.8, places=2)
        
        # Verify Graham Index (PE * PB)
        self.assertAlmostEqual(features.graham_index_csi300, 18.75, places=2)
        self.assertAlmostEqual(features.graham_index_csi500, 36.0, places=2)
        self.assertAlmostEqual(features.graham_index_csi1000, 62.5, places=2)
        
        # Verify FED Spread (1/PE - bond_yield)
        # CSI300: 1/12.5 = 0.08, bond_yield = 0.028, spread = 0.052
        self.assertAlmostEqual(features.fed_spread_csi300, 0.052, places=3)
        
        # Verify no historical data
        self.assertFalse(features.has_historical_data)
        self.assertIsNone(features.csi300_pe_percentile)
    
    def test_with_historical_data(self):
        """Test valuation calculation with historical percentiles."""
        valuation_data = {
            'csi300_pe': 15.0,
            'csi300_pb': 1.8,
            'csi500_pe': 20.0,
            'csi500_pb': 2.2,
            'csi1000_pe': 28.0,
            'csi1000_pb': 2.8,
            'bond_yield_10y': 3.0,
            'bond_yield_1y': 2.2,
        }
        
        historical_pe = {
            'csi300': [10.0, 12.0, 13.0, 14.0, 15.0, 16.0, 18.0, 20.0, 22.0, 25.0],
            'csi500': [15.0, 17.0, 18.0, 19.0, 20.0, 21.0, 23.0, 25.0, 27.0, 30.0],
            'csi1000': [20.0, 22.0, 24.0, 26.0, 28.0, 30.0, 32.0, 35.0, 38.0, 40.0],
        }
        
        historical_pb = {
            'csi300': [1.2, 1.4, 1.5, 1.6, 1.7, 1.8, 2.0, 2.2, 2.4, 2.6],
            'csi500': [1.5, 1.7, 1.9, 2.0, 2.1, 2.2, 2.4, 2.6, 2.8, 3.0],
            'csi1000': [2.0, 2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6, 3.8],
        }
        
        features = compute_valuation_features(
            valuation_data,
            historical_pe=historical_pe,
            historical_pb=historical_pb
        )
        
        # Verify historical data flag
        self.assertTrue(features.has_historical_data)
        
        # Verify percentiles are calculated
        self.assertIsNotNone(features.csi300_pe_percentile)
        self.assertIsNotNone(features.csi300_pb_percentile)
        self.assertIsNotNone(features.csi500_pe_percentile)
        self.assertIsNotNone(features.csi500_pb_percentile)
        self.assertIsNotNone(features.csi1000_pe_percentile)
        self.assertIsNotNone(features.csi1000_pb_percentile)
        
        # Verify percentiles are in valid range
        self.assertGreaterEqual(features.csi300_pe_percentile, 0.0)
        self.assertLessEqual(features.csi300_pe_percentile, 100.0)
    
    def test_zero_pe_handling(self):
        """Test handling of zero PE values."""
        valuation_data = {
            'csi300_pe': 0.0,  # Invalid PE
            'csi300_pb': 1.5,
            'csi500_pe': 18.0,
            'csi500_pb': 2.0,
            'csi1000_pe': 25.0,
            'csi1000_pb': 2.5,
            'bond_yield_10y': 2.8,
            'bond_yield_1y': 2.0,
        }
        
        features = compute_valuation_features(valuation_data)
        
        # When PE is 0, earnings yield = 1/0 = 0 (safe_divide returns 0)
        # FED spread = 0 - bond_yield = -bond_yield
        self.assertAlmostEqual(features.fed_spread_csi300, -0.028, places=3)
        
        # Verify Graham Index is 0 for zero PE
        self.assertEqual(features.graham_index_csi300, 0.0)
    
    def test_missing_data_handling(self):
        """Test handling of missing valuation data."""
        valuation_data = {
            # Missing some fields
            'csi300_pe': 12.5,
            'bond_yield_10y': 2.8,
        }
        
        features = compute_valuation_features(valuation_data)
        
        # Verify defaults are used for missing fields
        self.assertEqual(features.csi300_pb, 0.0)
        self.assertEqual(features.csi500_pe, 0.0)
        self.assertEqual(features.bond_yield_1y, 0.0)
    
    def test_valuation_level_classification(self):
        """Test valuation level classification."""
        # Undervalued scenario
        valuation_data = {
            'csi300_pe': 10.0,
            'csi300_pb': 1.2,
            'csi500_pe': 15.0,
            'csi500_pb': 1.5,
            'csi1000_pe': 20.0,
            'csi1000_pb': 2.0,
            'bond_yield_10y': 2.0,
            'bond_yield_1y': 1.5,
        }
        
        historical_pe = {
            'csi300': [10.0, 12.0, 15.0, 18.0, 20.0, 22.0, 25.0, 28.0, 30.0, 35.0],
        }
        
        historical_pb = {
            'csi300': [1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 2.8, 3.0, 3.2, 3.5],
        }
        
        features = compute_valuation_features(
            valuation_data,
            historical_pe=historical_pe,
            historical_pb=historical_pb
        )
        
        # Should be undervalued (low percentiles, low Graham Index, high FED spread)
        self.assertEqual(features.valuation_level, "undervalued")
    
    def test_risk_premium_calculation(self):
        """Test risk premium calculation."""
        valuation_data = {
            'csi300_pe': 15.0,
            'csi300_pb': 1.8,
            'csi500_pe': 20.0,
            'csi500_pb': 2.2,
            'csi1000_pe': 25.0,
            'csi1000_pb': 2.5,
            'bond_yield_10y': 3.0,
            'bond_yield_1y': 2.5,
        }
        
        features = compute_valuation_features(valuation_data)
        
        # Risk premium = earnings yield - bond yield
        # Earnings yield = 1/15 = 0.0667
        # Bond yield = 0.03
        # Risk premium = 0.0667 - 0.03 = 0.0367
        self.assertAlmostEqual(features.risk_premium_csi300, 0.0367, places=3)
        
        # Risk premium should equal FED spread
        self.assertEqual(features.risk_premium_csi300, features.fed_spread_csi300)


if __name__ == '__main__':
    unittest.main()
