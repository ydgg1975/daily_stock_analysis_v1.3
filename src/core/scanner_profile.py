# -*- coding: utf-8 -*-
"""Market scanner profile definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ScannerMarketProfile:
    """Static, explainable scanner settings for one market profile."""

    key: str
    market: str
    label: str
    description: str
    implemented: bool = True

    universe_name: str = "scanner_universe"
    shortlist_size: int = 5
    universe_limit: int = 300
    detail_limit: int = 60
    history_days: int = 140
    min_history_bars: int = 60

    min_price: float = 3.0
    min_amount: float = 2.0e8
    min_turnover_rate: float = 0.8
    min_volume_ratio: float = 0.6
    min_avg_amount_20: float = 1.5e8

    sector_context_limit: int = 10
    recent_run_limit: int = 5


CN_A_PREOPEN_V1 = ScannerMarketProfile(
    key="cn_preopen_v1",
    market="cn",
    label="A股盘前扫描 v1",
    description="面向盘前观察名单的 A 股规则型扫描器，强调趋势、量能、活跃度与可解释性。",
    universe_name="cn_a_liquid_watchlist_v1",
    shortlist_size=5,
    universe_limit=300,
    detail_limit=60,
    history_days=140,
    min_history_bars=60,
    min_price=3.0,
    min_amount=2.0e8,
    min_turnover_rate=0.8,
    min_volume_ratio=0.6,
    min_avg_amount_20=1.5e8,
    sector_context_limit=10,
    recent_run_limit=5,
)


US_PREOPEN_V1 = ScannerMarketProfile(
    key="us_preopen_v1",
    market="us",
    label="US Pre-open Scanner v1",
    description="Reserved extension point for a future US market scanner profile.",
    implemented=False,
    universe_name="us_preopen_watchlist_v1",
)


SCANNER_PROFILES: Dict[str, ScannerMarketProfile] = {
    CN_A_PREOPEN_V1.key: CN_A_PREOPEN_V1,
    US_PREOPEN_V1.key: US_PREOPEN_V1,
}


DEFAULT_PROFILE_BY_MARKET: Dict[str, ScannerMarketProfile] = {
    "cn": CN_A_PREOPEN_V1,
    "us": US_PREOPEN_V1,
}


def get_scanner_profile(*, market: str = "cn", profile: Optional[str] = None) -> ScannerMarketProfile:
    """Resolve a scanner profile by market and optional key."""

    normalized_market = (market or "cn").strip().lower()
    if profile:
        resolved = SCANNER_PROFILES.get(profile.strip().lower())
        if resolved is None:
            raise ValueError(f"未知扫描配置: {profile}")
        if resolved.market != normalized_market:
            raise ValueError(f"扫描配置 {resolved.key} 不属于市场 {normalized_market}")
        return resolved

    resolved = DEFAULT_PROFILE_BY_MARKET.get(normalized_market)
    if resolved is None:
        raise ValueError(f"暂不支持市场: {market}")
    return resolved

