# -*- coding: utf-8 -*-
"""Crypto scanner API endpoints.

Provides list, detail, refresh, and status routes for the crypto launch scanner.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.crypto import (
    CryptoLaunchDetailResponse,
    CryptoLaunchFeedResponse,
    CryptoLaunchRow,
    CryptoRefreshRequest,
    CryptoRefreshResponse,
    CryptoScannerStatusResponse,
    CryptoSnapshotRow,
    FeedMeta,
)
from src.services.crypto_launch_service import CryptoLaunchService

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level singleton — instantiated on first use
_service: Optional[CryptoLaunchService] = None


def _get_service() -> CryptoLaunchService:
    global _service
    if _service is None:
        _service = CryptoLaunchService()
    return _service


# ---------------------------------------------------------------------------
# GET /launches
# ---------------------------------------------------------------------------

@router.get("/launches", response_model=CryptoLaunchFeedResponse)
async def list_launches(
    chains: Optional[str] = Query(None, description="Comma-separated chain ids to filter"),
    min_liquidity_usd: float = Query(0.0, ge=0),
    min_volume_usd: float = Query(0.0, ge=0),
    max_age_minutes: int = Query(1440, ge=1),
    sort: str = Query("newest", pattern="^(newest|liquidity|volume|activity)$"),
    cursor: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """Paginated list of recent crypto launches with filters."""
    chain_list = [c.strip().lower() for c in chains.split(",") if c.strip()] if chains else None

    result = _get_service().list_launches(
        chains=chain_list,
        min_liquidity_usd=min_liquidity_usd,
        min_volume_usd=min_volume_usd,
        max_age_minutes=max_age_minutes,
        sort=sort,
        cursor=cursor,
        limit=limit,
    )

    items = [CryptoLaunchRow(**item) for item in result.get("items", [])]

    # Detect partial data
    has_partial = any(not item.data_complete for item in items)

    meta = FeedMeta(
        total=result.get("total", 0),
        next_cursor=result.get("next_cursor"),
        chains=chain_list or [],
        sort=sort,
        data_complete=not has_partial,
        symbols_partial=has_partial,
    )

    return CryptoLaunchFeedResponse(items=items, meta=meta)


# ---------------------------------------------------------------------------
# GET /launches/{launch_id}
# ---------------------------------------------------------------------------

@router.get("/launches/{launch_id}", response_model=CryptoLaunchDetailResponse)
async def get_launch_detail(launch_id: int):
    """Get a single launch with its recent snapshots."""
    detail = _get_service().get_launch_detail(launch_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Launch not found")

    snapshots_raw = detail.pop("snapshots", [])
    launch = CryptoLaunchRow(**detail)
    snapshots = [CryptoSnapshotRow(**s) for s in snapshots_raw]

    return CryptoLaunchDetailResponse(launch=launch, snapshots=snapshots)


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=CryptoRefreshResponse)
async def trigger_refresh(body: Optional[CryptoRefreshRequest] = None):
    """Manually trigger a scan cycle. Returns the scan result summary."""
    service = _get_service()
    result = service.scan_once()

    return CryptoRefreshResponse(
        status="completed",
        message=f"Scan completed: {result.get('new', 0)} launches processed",
        new=result.get("new", 0),
        updated=result.get("updated", 0),
        failed_chains=result.get("failed_chains", []),
    )


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------

@router.get("/status", response_model=CryptoScannerStatusResponse)
async def get_scanner_status():
    """Return current scanner runtime status."""
    status = _get_service().get_status()
    return CryptoScannerStatusResponse(**status)
