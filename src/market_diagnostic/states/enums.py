"""
State Layer Enumerations

Defines all market state enums used by the diagnostic system.
"""

from enum import Enum


class TrendState(str, Enum):
    STRONG_UP = "强趋势上行"
    PULLBACK_IN_UPTREND = "趋势上行中的回调"
    RANGING = "震荡"
    WEAKENING = "趋势转弱"
    BREAKDOWN = "破位下行"


class BreadthState(str, Enum):
    EXTREME_WEAK = "极弱"      # above_ma20 < 20%
    WEAK = "偏弱"              # 20-35%
    NEUTRAL = "中性"           # 35-55%
    STRONG = "偏强"            # 55-70%
    OVERHEATED = "过热"        # > 70%


class SentimentState(str, Enum):
    FROZEN = "冰点"
    WARMING = "回暖"
    NEUTRAL = "中性"
    ACTIVE = "活跃"
    EUPHORIC = "狂热"


class StyleState(str, Enum):
    LARGE_CAP_DEFENSIVE = "大盘防守"
    SMALL_CAP_OFFENSIVE = "小盘进攻"
    GROWTH_DOMINANT = "成长主导"
    DIVIDEND_DEFENSIVE = "红利防守"
    STYLE_CONFLICT = "风格冲突"


class SectorState(str, Enum):
    NO_THEME = "无主线"
    SINGLE_THEME = "单主线"
    DUAL_THEME = "双主线并行"
    FAST_ROTATION = "高速轮动"
    FADING = "退潮分化"


class RiskState(str, Enum):
    LOW = "低风险"
    NEUTRAL = "中性风险"
    HIGH = "高风险"
    EXTREME = "极端风险"


class CompositeRegime(str, Enum):
    TREND_RISK_ON_GROWTH = "trend_risk_on_growth"
    TREND_RISK_ON_SMALLCAP = "trend_risk_on_smallcap"
    BALANCED_ROTATION = "balanced_rotation"
    DEFENSIVE_DIVIDEND = "defensive_dividend"
    HIGH_VOL_WARNING = "high_volatility_warning"
    PANIC_BOTTOMING = "panic_bottoming"
    BROAD_WEAKNESS_HOLD = "broad_weakness_hold"
