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
    min_avg_volume_20: float = 0.0

    sector_context_limit: int = 10
    recent_run_limit: int = 5
    benchmark_code: str = "000300"


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
    description="面向美股盘前候选发现的规则型扫描器，强调流动性、趋势延续、相对强度与可交易性。",
    implemented=True,
    universe_name="us_preopen_watchlist_v1",
    shortlist_size=5,
    universe_limit=180,
    detail_limit=40,
    history_days=180,
    min_history_bars=70,
    min_price=5.0,
    min_amount=2.5e7,
    min_turnover_rate=0.0,
    min_volume_ratio=0.0,
    min_avg_amount_20=2.5e7,
    min_avg_volume_20=1.5e6,
    sector_context_limit=0,
    recent_run_limit=5,
    benchmark_code="SPY",
)


HK_PREOPEN_V1 = ScannerMarketProfile(
    key="hk_preopen_v1",
    market="hk",
    label="港股盘前扫描 v1",
    description="面向港股开盘前候选发现的规则型扫描器，强调流动性、趋势延续、相对强度与开盘确认。",
    implemented=True,
    universe_name="hk_preopen_watchlist_v1",
    shortlist_size=5,
    universe_limit=120,
    detail_limit=30,
    history_days=180,
    min_history_bars=70,
    min_price=3.0,
    min_amount=8.0e7,
    min_turnover_rate=0.0,
    min_volume_ratio=0.0,
    min_avg_amount_20=8.0e7,
    min_avg_volume_20=1.2e6,
    sector_context_limit=0,
    recent_run_limit=5,
    benchmark_code="HK02800",
)


SCANNER_PROFILES: Dict[str, ScannerMarketProfile] = {
    CN_A_PREOPEN_V1.key: CN_A_PREOPEN_V1,
    US_PREOPEN_V1.key: US_PREOPEN_V1,
    HK_PREOPEN_V1.key: HK_PREOPEN_V1,
}


DEFAULT_PROFILE_BY_MARKET: Dict[str, ScannerMarketProfile] = {
    "cn": CN_A_PREOPEN_V1,
    "us": US_PREOPEN_V1,
    "hk": HK_PREOPEN_V1,
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


def get_scanner_profile_by_key(profile: str) -> ScannerMarketProfile:
    """Resolve a scanner profile directly from its key."""

    normalized_profile = (profile or "").strip().lower()
    resolved = SCANNER_PROFILES.get(normalized_profile)
    if resolved is None:
        raise ValueError(f"未知扫描配置: {profile}")
    return resolved
