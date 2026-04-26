"""
Feature Layer

Transforms raw data into quantitative indicators.
"""

from .breadth import BreadthFeatures, compute_breadth_features
from .capital import CapitalFeatures, compute_capital_features
from .risk import RiskFeatures, compute_risk_features
from .sentiment import SentimentFeatures, compute_sentiment_features
from .style import StyleFeatures, compute_style_features
from .trend import TrendFeatures, compute_trend_features
from .sector import (
    SectorFeatureResult,
    compute_sector_features,
    compute_sector_strength_score,
    compute_sector_persistence_score,
    classify_sector_state,
)

__all__ = [
    # Breadth
    "BreadthFeatures",
    "compute_breadth_features",
    # Capital
    "CapitalFeatures",
    "compute_capital_features",
    # Risk
    "RiskFeatures",
    "compute_risk_features",
    # Sentiment
    "SentimentFeatures",
    "compute_sentiment_features",
    # Style
    "StyleFeatures",
    "compute_style_features",
    # Trend
    "TrendFeatures",
    "compute_trend_features",
    # Sector
    "SectorFeatureResult",
    "compute_sector_features",
    "compute_sector_strength_score",
    "compute_sector_persistence_score",
    "classify_sector_state",
]
