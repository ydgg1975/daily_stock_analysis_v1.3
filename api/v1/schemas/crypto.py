# -*- coding: utf-8 -*-
"""Pydantic request/response models for the crypto scanner API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Feed row and detail
# ---------------------------------------------------------------------------

class CryptoLaunchRow(BaseModel):
    """A single launch in the list feed."""

    id: int
    chain_id: str
    dex_id: Optional[str] = None
    pair_address: str
    pair_url: Optional[str] = None
    pair_created_at: Optional[str] = None

    base_token_address: Optional[str] = None
    base_token_symbol: Optional[str] = None
    base_token_name: Optional[str] = None
    quote_token_address: Optional[str] = None
    quote_token_symbol: Optional[str] = None
    quote_token_name: Optional[str] = None

    liquidity_usd: Optional[float] = None
    volume_usd_24h: Optional[float] = None
    buys_24h: Optional[int] = None
    sells_24h: Optional[int] = None
    price_usd: Optional[float] = None
    price_change_pct_24h: Optional[float] = None
    fdv_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None

    dexscreener_url: Optional[str] = None
    website_url: Optional[str] = None
    socials_json: Optional[str] = None
    labels_json: Optional[str] = None
    data_complete: bool = False

    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None


class CryptoSnapshotRow(BaseModel):
    """A single snapshot entry for the detail view."""

    id: int
    launch_id: int
    snapshot_at: Optional[str] = None
    liquidity_usd: Optional[float] = None
    volume_usd_24h: Optional[float] = None
    buys_24h: Optional[int] = None
    sells_24h: Optional[int] = None
    price_usd: Optional[float] = None
    price_change_pct_24h: Optional[float] = None
    fdv_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    data_complete: bool = False


# ---------------------------------------------------------------------------
# Feed response
# ---------------------------------------------------------------------------

class FeedMeta(BaseModel):
    """Metadata about the feed response."""

    total: int = 0
    next_cursor: Optional[int] = None
    chains: List[str] = Field(default_factory=list)
    sort: str = "newest"
    data_complete: bool = True
    symbols_partial: bool = False


class CryptoLaunchFeedResponse(BaseModel):
    """Response for GET /api/v1/crypto/launches."""

    items: List[CryptoLaunchRow] = Field(default_factory=list)
    meta: FeedMeta = Field(default_factory=FeedMeta)


# ---------------------------------------------------------------------------
# Detail response
# ---------------------------------------------------------------------------

class CryptoLaunchDetailResponse(BaseModel):
    """Response for GET /api/v1/crypto/launches/{launch_id}."""

    launch: CryptoLaunchRow
    snapshots: List[CryptoSnapshotRow] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

class CryptoRefreshRequest(BaseModel):
    """Request body for POST /api/v1/crypto/refresh."""

    chains: Optional[List[str]] = Field(
        None,
        description="Chains to refresh. If omitted, uses the configured default set.",
    )


class CryptoRefreshResponse(BaseModel):
    """Response for POST /api/v1/crypto/refresh."""

    status: str = "accepted"
    message: str = "Scan triggered"
    new: int = 0
    updated: int = 0
    failed_chains: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class CryptoScannerStatusResponse(BaseModel):
    """Response for GET /api/v1/crypto/status."""

    enabled: bool = False
    is_scanning: bool = False
    refresh_interval_sec: int = 60
    enabled_chains: List[str] = Field(default_factory=list)
    last_scan_at: Optional[str] = None
    last_scan_duration_sec: float = 0.0
    last_scan_chains: List[str] = Field(default_factory=list)
    last_scan_failed_chains: List[str] = Field(default_factory=list)
    last_scan_new_launches: int = 0
    last_scan_updated_launches: int = 0
    total_scans: int = 0


# ---------------------------------------------------------------------------
# AI Summary
# ---------------------------------------------------------------------------

class CryptoAiSummaryResponse(BaseModel):
    """Response for POST /api/v1/crypto/launches/{id}/analyze."""

    launch_id: int
    verdict: Optional[str] = None  # BUY, HOLD, AVOID
    confidence: Optional[float] = None  # 0.0 - 1.0
    bull_case: Optional[str] = None
    bear_case: Optional[str] = None
    risks: Optional[List[str]] = None
    recommended_action: Optional[str] = None
    model_used: Optional[str] = None
    prompt_version: str = "v1"
    analyzed_at: Optional[str] = None
    error: Optional[str] = None
    cached: bool = False
