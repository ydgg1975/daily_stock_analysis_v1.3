"""
Valuation Feature Calculation

Computes valuation indicators including index PE/PB, historical percentiles,
FED Spread, Graham Index, term spread, and valuation level classification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np


@dataclass
class ValuationFeatures:
    """Valuation-related features for market diagnostic."""
    
    # Index PE/PB metrics
    csi300_pe: float                           # CSI300 PE ratio
    csi300_pb: float                           # CSI300 PB ratio
    csi500_pe: float                           # CSI500 PE ratio
    csi500_pb: float                           # CSI500 PB ratio
    csi1000_pe: float                          # CSI1000 PE ratio
    csi1000_pb: float                          # CSI1000 PB ratio
    
    # Historical percentiles
    csi300_pe_percentile: Optional[float]      # PE percentile (0-100)
    csi300_pb_percentile: Optional[float]      # PB percentile (0-100)
    csi500_pe_percentile: Optional[float]
    csi500_pb_percentile: Optional[float]
    csi1000_pe_percentile: Optional[float]
    csi1000_pb_percentile: Optional[float]
    
    # Valuation metrics
    fed_spread_csi300: float                   # 1/PE - bond_yield_10y
    fed_spread_csi500: float
    fed_spread_csi1000: float
    graham_index_csi300: float                 # PE * PB
    graham_index_csi500: float
    graham_index_csi1000: float
    
    # Bond metrics
    bond_yield_10y: float                      # 10-year bond yield (%)
    bond_yield_1y: float                       # 1-year bond yield (%)
    term_spread: float                         # 10Y - 1Y spread
    
    # Valuation level classification
    valuation_level: str                       # "undervalued" / "fair" / "overvalued" / "bubble"
    risk_premium_csi300: float                 # Earnings yield - bond yield
    
    # Data availability
    has_historical_data: bool                  # Whether historical percentiles are available


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division that returns default when denominator is zero."""
    if denominator == 0 or not np.isfinite(denominator):
        return default
    result = numerator / denominator
    return result if np.isfinite(result) else default


def _compute_percentile(value: float, historical_values: List[float]) -> Optional[float]:
    """
    Compute percentile of value relative to historical distribution.
    
    Parameters
    ----------
    value : float
        Current value
    historical_values : List[float]
        Historical values for comparison
        
    Returns
    -------
    Optional[float]
        Percentile (0-100) or None if insufficient data
    """
    if not historical_values or len(historical_values) < 10:
        return None
    
    # Filter out invalid values
    valid_values = [v for v in historical_values if np.isfinite(v) and v > 0]
    if len(valid_values) < 10:
        return None
    
    # Calculate percentile
    percentile = float(np.sum(np.array(valid_values) <= value) / len(valid_values) * 100)
    return percentile


def _classify_valuation_level(
    pe_percentile: Optional[float],
    pb_percentile: Optional[float],
    graham_index: float,
    fed_spread: float
) -> str:
    """
    Classify valuation level based on multiple metrics.
    
    Classification rules:
    - "bubble": PE/PB percentiles > 90 OR graham_index > 100 OR fed_spread < -2%
    - "overvalued": PE/PB percentiles > 70 OR graham_index > 60 OR fed_spread < 0%
    - "undervalued": PE/PB percentiles < 30 AND graham_index < 30 AND fed_spread > 2%
    - "fair": default
    
    Parameters
    ----------
    pe_percentile : Optional[float]
        PE percentile (0-100)
    pb_percentile : Optional[float]
        PB percentile (0-100)
    graham_index : float
        Graham Index (PE * PB)
    fed_spread : float
        FED Spread (1/PE - bond_yield)
        
    Returns
    -------
    str
        Valuation level classification
    """
    # Bubble conditions
    if pe_percentile is not None and pe_percentile > 90:
        return "bubble"
    if pb_percentile is not None and pb_percentile > 90:
        return "bubble"
    if graham_index > 100:
        return "bubble"
    if fed_spread < -0.02:  # -2%
        return "bubble"
    
    # Overvalued conditions
    if pe_percentile is not None and pe_percentile > 70:
        return "overvalued"
    if pb_percentile is not None and pb_percentile > 70:
        return "overvalued"
    if graham_index > 60:
        return "overvalued"
    if fed_spread < 0:
        return "overvalued"
    
    # Undervalued conditions (all must be true)
    undervalued_conditions = []
    if pe_percentile is not None:
        undervalued_conditions.append(pe_percentile < 30)
    if pb_percentile is not None:
        undervalued_conditions.append(pb_percentile < 30)
    undervalued_conditions.append(graham_index < 30)
    undervalued_conditions.append(fed_spread > 0.02)  # 2%
    
    if len(undervalued_conditions) >= 3 and all(undervalued_conditions):
        return "undervalued"
    
    # Default: fair valuation
    return "fair"


def compute_valuation_features(
    valuation_data: Dict[str, float],
    historical_pe: Optional[Dict[str, List[float]]] = None,
    historical_pb: Optional[Dict[str, List[float]]] = None,
) -> ValuationFeatures:
    """
    Compute valuation features from valuation data.
    
    Parameters
    ----------
    valuation_data : Dict[str, float]
        Dictionary containing PE/PB values and bond yields
        Expected keys: csi300_pe, csi300_pb, csi500_pe, csi500_pb, csi1000_pe, csi1000_pb,
                      bond_yield_10y, bond_yield_1y
    historical_pe : Optional[Dict[str, List[float]]]
        Historical PE values for percentile calculation
        Keys: 'csi300', 'csi500', 'csi1000'
    historical_pb : Optional[Dict[str, List[float]]]
        Historical PB values for percentile calculation
        Keys: 'csi300', 'csi500', 'csi1000'
        
    Returns
    -------
    ValuationFeatures
        Computed valuation indicators
        
    Requirements
    ------------
    24.1: Calculate index PE/PB for CSI300, CSI500, CSI1000
    24.1: Calculate FED Spread (1/PE - bond yield)
    24.2: Calculate Graham Index (PE * PB)
    24.2: Calculate historical percentiles for PE/PB
    24.3: Calculate term spread (10Y - 1Y bond yield)
    24.3: Determine valuation level (undervalued/fair/overvalued/bubble)
    24.3: Calculate risk premium
    """
    # Requirement 24.1: Extract index PE/PB values
    csi300_pe = valuation_data.get('csi300_pe', 0.0)
    csi300_pb = valuation_data.get('csi300_pb', 0.0)
    csi500_pe = valuation_data.get('csi500_pe', 0.0)
    csi500_pb = valuation_data.get('csi500_pb', 0.0)
    csi1000_pe = valuation_data.get('csi1000_pe', 0.0)
    csi1000_pb = valuation_data.get('csi1000_pb', 0.0)
    
    # Extract bond yields
    bond_yield_10y = valuation_data.get('bond_yield_10y', 0.0)
    bond_yield_1y = valuation_data.get('bond_yield_1y', 0.0)
    
    # Requirement 24.2: Calculate historical percentiles
    has_historical_data = historical_pe is not None and historical_pb is not None
    
    csi300_pe_percentile = None
    csi300_pb_percentile = None
    csi500_pe_percentile = None
    csi500_pb_percentile = None
    csi1000_pe_percentile = None
    csi1000_pb_percentile = None
    
    if has_historical_data:
        csi300_pe_percentile = _compute_percentile(csi300_pe, historical_pe.get('csi300', []))
        csi300_pb_percentile = _compute_percentile(csi300_pb, historical_pb.get('csi300', []))
        csi500_pe_percentile = _compute_percentile(csi500_pe, historical_pe.get('csi500', []))
        csi500_pb_percentile = _compute_percentile(csi500_pb, historical_pb.get('csi500', []))
        csi1000_pe_percentile = _compute_percentile(csi1000_pe, historical_pe.get('csi1000', []))
        csi1000_pb_percentile = _compute_percentile(csi1000_pb, historical_pb.get('csi1000', []))
    
    # Requirement 24.1: Calculate FED Spread (1/PE - bond_yield)
    # Convert bond yield from percentage to decimal
    bond_yield_10y_decimal = bond_yield_10y / 100.0
    
    # Earnings yield = 1/PE
    earnings_yield_csi300 = _safe_divide(1.0, csi300_pe, default=0.0)
    earnings_yield_csi500 = _safe_divide(1.0, csi500_pe, default=0.0)
    earnings_yield_csi1000 = _safe_divide(1.0, csi1000_pe, default=0.0)
    
    # FED Spread = Earnings Yield - Bond Yield
    fed_spread_csi300 = earnings_yield_csi300 - bond_yield_10y_decimal
    fed_spread_csi500 = earnings_yield_csi500 - bond_yield_10y_decimal
    fed_spread_csi1000 = earnings_yield_csi1000 - bond_yield_10y_decimal
    
    # Requirement 24.2: Calculate Graham Index (PE * PB)
    graham_index_csi300 = csi300_pe * csi300_pb
    graham_index_csi500 = csi500_pe * csi500_pb
    graham_index_csi1000 = csi1000_pe * csi1000_pb
    
    # Requirement 24.3: Calculate term spread (10Y - 1Y)
    term_spread = bond_yield_10y - bond_yield_1y
    
    # Requirement 24.3: Determine valuation level
    valuation_level = _classify_valuation_level(
        csi300_pe_percentile,
        csi300_pb_percentile,
        graham_index_csi300,
        fed_spread_csi300
    )
    
    # Requirement 24.3: Calculate risk premium (earnings yield - bond yield)
    risk_premium_csi300 = fed_spread_csi300  # Same as FED spread
    
    return ValuationFeatures(
        csi300_pe=csi300_pe,
        csi300_pb=csi300_pb,
        csi500_pe=csi500_pe,
        csi500_pb=csi500_pb,
        csi1000_pe=csi1000_pe,
        csi1000_pb=csi1000_pb,
        csi300_pe_percentile=csi300_pe_percentile,
        csi300_pb_percentile=csi300_pb_percentile,
        csi500_pe_percentile=csi500_pe_percentile,
        csi500_pb_percentile=csi500_pb_percentile,
        csi1000_pe_percentile=csi1000_pe_percentile,
        csi1000_pb_percentile=csi1000_pb_percentile,
        fed_spread_csi300=fed_spread_csi300,
        fed_spread_csi500=fed_spread_csi500,
        fed_spread_csi1000=fed_spread_csi1000,
        graham_index_csi300=graham_index_csi300,
        graham_index_csi500=graham_index_csi500,
        graham_index_csi1000=graham_index_csi1000,
        bond_yield_10y=bond_yield_10y,
        bond_yield_1y=bond_yield_1y,
        term_spread=term_spread,
        valuation_level=valuation_level,
        risk_premium_csi300=risk_premium_csi300,
        has_historical_data=has_historical_data,
    )
