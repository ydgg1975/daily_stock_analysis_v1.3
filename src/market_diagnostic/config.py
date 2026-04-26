"""
Configuration for Market Diagnostic System

Defines index pools, style pairs, industry codes, thresholds, and mappings.
"""

from typing import Dict, List, Tuple

# ============================================================================
# Index Pool Configuration
# ============================================================================

INDEX_POOL: Dict[str, str] = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sh000016": "上证50",
    "sh000300": "沪深300",
    "sh000905": "中证500",
    "sh000852": "中证1000",
    "sh000015": "微盘股指数",  # Note: Using sh000015 as proxy for 微盘股指数
}

# Primary index for trend classification
PRIMARY_INDEX = "sh000300"  # 沪深300

# ============================================================================
# Style Pair Configuration
# ============================================================================

STYLE_PAIRS: List[Tuple[str, str, str]] = [
    ("sh000016", "sz399006", "大盘vs创业板"),      # Large-cap vs Growth
    ("sh000300", "sh000852", "沪深300vs中证1000"),  # Mid-cap vs Small-cap
    ("sh000905", "sh000852", "中证500vs中证1000"),  # Mid-cap vs Small-cap
]

# ============================================================================
# Shenwan Level-1 Industry Codes (31 industries)
# ============================================================================

SHENWAN_INDUSTRIES: Dict[str, str] = {
    "BK0447": "电子",
    "BK0448": "计算机",
    "BK0449": "传媒",
    "BK0450": "通信",
    "BK0451": "国防军工",
    "BK0452": "电力设备",
    "BK0453": "机械设备",
    "BK0454": "汽车",
    "BK0455": "家用电器",
    "BK0456": "轻工制造",
    "BK0457": "建筑材料",
    "BK0458": "建筑装饰",
    "BK0459": "钢铁",
    "BK0460": "有色金属",
    "BK0461": "化工",
    "BK0462": "石油石化",
    "BK0463": "煤炭",
    "BK0464": "基础化工",
    "BK0465": "房地产",
    "BK0466": "交通运输",
    "BK0467": "公用事业",
    "BK0468": "银行",
    "BK0469": "非银金融",
    "BK0470": "医药生物",
    "BK0471": "食品饮料",
    "BK0472": "农林牧渔",
    "BK0473": "商贸零售",
    "BK0474": "社会服务",
    "BK0475": "纺织服饰",
    "BK0476": "美容护理",
    "BK0477": "环保",
}

# ============================================================================
# State Classification Thresholds
# ============================================================================

# Breadth state thresholds (based on above_ma20_ratio)
BREADTH_THRESHOLDS = {
    "extreme_weak": 0.20,   # < 20%: 极弱
    "weak": 0.35,           # 20-35%: 偏弱
    "neutral": 0.55,        # 35-55%: 中性
    "strong": 0.70,         # 55-70%: 偏强
    # >= 70%: 过热
}

# Trend classification thresholds
TREND_THRESHOLDS = {
    "rsrs_strong": 0.7,     # RSRS > 0.7: Strong trend
    "rsrs_weak": 0.3,       # RSRS < 0.3: Weak trend
    "macd_threshold": 0.0,  # MACD near zero threshold
}

# Sentiment classification thresholds
SENTIMENT_THRESHOLDS = {
    "limit_up_rate_low": 0.01,      # < 1%: Low sentiment
    "limit_up_rate_high": 0.03,     # > 3%: High sentiment
    "seal_rate_low": 0.50,          # < 50%: Low seal rate
    "seal_rate_high": 0.80,         # > 80%: High seal rate
}

# Sector strength thresholds
SECTOR_THRESHOLDS = {
    "strength_strong": 2.0,         # strength_score > 2.0: Strong
    "strength_moderate": 1.5,       # strength_score > 1.5: Moderate
    "strength_weak": -0.5,          # strength_score < -0.5: Weak
    "persistence_high": 0.7,        # persistence_score > 0.7: High persistence
    "persistence_moderate": 0.4,    # persistence_score > 0.4: Moderate persistence
}

# Risk classification thresholds
RISK_THRESHOLDS = {
    "volatility_spike_multiplier": 2.0,     # Vol > 2x historical mean
    "breadth_collapse_threshold": 0.10,     # Single-day drop > 10pct
    "sector_overcrowding_sigma": 2.0,       # Amount share > mean + 2σ
    "northbound_outflow_days": 3,           # Consecutive outflow days
    "leadership_breakdown_threshold": 0.02, # Average drop > 2%
}

# ============================================================================
# Composite Score Weights
# ============================================================================

# Regime score formula weights
REGIME_SCORE_WEIGHTS = {
    "trend": 0.20,
    "breadth": 0.15,
    "sentiment": 0.15,
    "style": 0.15,
    "sector": 0.15,
    "risk": -0.20,  # Negative weight (risk reduces score)
}

# Sector strength score formula weights
SECTOR_STRENGTH_WEIGHTS = {
    "ret_5d_excess": 0.25,
    "ret_20d_excess": 0.20,
    "breadth_20": 0.20,
    "new_high_ratio": 0.10,
    "amount_share_delta": 0.10,
    "leadership_score": 0.10,
    "crowding_score": -0.05,  # Negative weight (crowding reduces score)
}

# ============================================================================
# Risk Flags
# ============================================================================

RISK_FLAGS = [
    "vol_spike",            # Realized volatility > 2x historical mean
    "breadth_collapse",     # above_ma20_ratio drops > 10pct in single day
    "sector_overcrowding",  # Single sector amount_share > mean + 2σ
    "northbound_outflow",   # North Bound Capital outflow for 3+ consecutive days
    "leadership_breakdown", # Top 5 sector leaders average drop > 2%
    "index_break_support",  # CSI300 breaks below MA60
]

# ============================================================================
# Regime to Strategy Mapping
# ============================================================================

REGIME_STRATEGY_MAPPING: Dict[str, List[str]] = {
    "trend_risk_on_growth": [
        "趋势ETF组",
        "行业轮动组",
        "小市值进攻组",
    ],
    "trend_risk_on_smallcap": [
        "趋势ETF组",
        "小市值进攻组",
    ],
    "balanced_rotation": [
        "行业轮动组",
        "红利价值组",
        "股债平衡组",
    ],
    "defensive_dividend": [
        "红利价值组",
        "股债平衡组",
        "全天候组",
    ],
    "high_volatility_warning": [
        "红利价值组",
        "股债平衡组",
        "全天候组",
        "高现金配置",
    ],
    "panic_bottoming": [
        "趋势ETF组小仓试探",
        "小市值观察",
    ],
    "broad_weakness_hold": [
        "股债平衡组",
        "全天候组",
        "高现金配置",
    ],
}

# ============================================================================
# Data Quality and Caching
# ============================================================================

# Cache TTL (time-to-live) in seconds
CACHE_TTL = {
    "intraday": 1200,       # 20 minutes for intraday data
    "daily": 86400,         # 24 hours for daily data
    "historical": 5184000,  # 60 days for historical data
}

# Stock filtering criteria
STOCK_FILTERS = {
    "exclude_st": True,             # Exclude ST stocks
    "exclude_suspended": True,      # Exclude suspended stocks
    "min_listing_days": 60,         # Exclude stocks listed < 60 days
    "exclude_anomalous": True,      # Exclude anomalous samples
}

# ============================================================================
# Confidence Scoring Parameters
# ============================================================================

CONFIDENCE_PARAMS = {
    "base_confidence": 1.0,
    "missing_core_indicator_penalty": 0.15,
    "signal_consistency_bonus": 0.10,
    "extreme_anomaly_penalty": 0.10,
    "estimated_data_penalty": 0.05,
    "min_confidence": 0.1,
    "max_confidence": 1.0,
}

# ============================================================================
# Performance Targets
# ============================================================================

PERFORMANCE_TARGETS = {
    "max_execution_time_seconds": 60,  # Full diagnostic run should complete in < 60s
    "api_rate_limit_delay_seconds": 3,  # Delay between API calls to avoid rate limiting
}
