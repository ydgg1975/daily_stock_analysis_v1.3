# -*- coding: utf-8 -*-
"""Crypto scanner API endpoints.

Provides list, detail, refresh, and status routes for the crypto launch scanner.
"""

import logging
import time
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.auth import get_client_ip

from api.v1.schemas.crypto import (
    AiCostResponse,
    CryptoAiSummaryResponse,
    CryptoLaunchDetailResponse,
    CryptoLaunchFeedResponse,
    CryptoLaunchRow,
    CryptoRefreshRequest,
    CryptoRefreshResponse,
    CryptoScannerStatusResponse,
    CryptoSnapshotRow,
    FeedMeta,
    PromptComparisonResponse,
    ProviderMetricsResponse,
    ScanSloResponse,
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


# Module-level AI service singleton — reuses locks across requests
_ai_service = None


def _get_ai_service():
    global _ai_service
    if _ai_service is None:
        from src.config import Config
        from src.services.crypto_ai_service import CryptoAiService

        _ai_service = CryptoAiService(config=Config.get_instance())
    return _ai_service


# Simple in-memory rate limiter: client_ip -> list of request timestamps
_analyze_rate_limit: dict = defaultdict(list)
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 60.0  # seconds


def _check_rate_limit(client_ip: str) -> None:
    """Raise 429 if client exceeds 5 analyses per 60s."""
    now = time.monotonic()
    timestamps = _analyze_rate_limit[client_ip]
    _analyze_rate_limit[client_ip] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
    if len(_analyze_rate_limit[client_ip]) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {_RATE_LIMIT_MAX} analyses per {int(_RATE_LIMIT_WINDOW)}s",
        )
    _analyze_rate_limit[client_ip].append(now)


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
# POST /launches/{launch_id}/analyze
# ---------------------------------------------------------------------------

@router.post("/launches/{launch_id}/analyze", response_model=CryptoAiSummaryResponse)
async def analyze_launch(launch_id: int, request: Request):
    """Trigger AI analysis for a specific launch. Returns the AI summary."""
    from src.config import Config

    config = Config.get_instance()

    if not config.crypto_ai_enrichment_enabled:
        raise HTTPException(status_code=403, detail="AI enrichment is disabled")

    _check_rate_limit(get_client_ip(request))

    try:
        ai_service = _get_ai_service()
        result = await ai_service.analyze(launch_id)
        if result.get("error") and "not found" in result["error"].lower():
            raise HTTPException(status_code=404, detail="Launch not found")
        if result.get("error"):
            raise HTTPException(status_code=502, detail="AI analysis failed. Please try again later.")
        return CryptoAiSummaryResponse(**result)
    except HTTPException:
        raise
    except Exception:
        logger.exception("AI analysis failed for launch_id=%s", launch_id)
        raise HTTPException(status_code=502, detail="AI analysis failed. Please try again later.")


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


# ---------------------------------------------------------------------------
# GET /metrics/providers
# ---------------------------------------------------------------------------

@router.get("/metrics/providers", response_model=ProviderMetricsResponse)
async def get_provider_metrics():
    """Per-chain scan stats aggregated from recent scan metrics."""
    from src.storage import DatabaseManager

    db = DatabaseManager.get_instance()
    chain_rows = db.get_provider_metrics()
    return ProviderMetricsResponse(chains=chain_rows)


# ---------------------------------------------------------------------------
# GET /metrics/slo
# ---------------------------------------------------------------------------

@router.get("/metrics/slo", response_model=ScanSloResponse)
async def get_scan_slo(
    window_hours: int = Query(24, ge=1, le=720),
):
    """Scan success ratio over a rolling window."""
    from src.storage import DatabaseManager

    db = DatabaseManager.get_instance()
    slo = db.get_scan_slo(window_hours=window_hours)
    return ScanSloResponse(**slo)


# ---------------------------------------------------------------------------
# GET /ai/cost
# ---------------------------------------------------------------------------

@router.get("/ai/cost", response_model=AiCostResponse)
async def get_ai_cost(
    window_days: int = Query(7, ge=1, le=90),
):
    """Crypto AI token spend aggregated from LLM usage records."""
    from src.storage import DatabaseManager

    db = DatabaseManager.get_instance()
    cost = db.get_crypto_ai_cost(window_days=window_days)
    return AiCostResponse(**cost)


# ---------------------------------------------------------------------------
# GET /ai/prompt-comparison
# ---------------------------------------------------------------------------

@router.get("/ai/prompt-comparison", response_model=PromptComparisonResponse)
async def get_prompt_comparison(
    versions: str = Query(..., description="Comma-separated prompt versions, e.g. v1,v2"),
):
    """Compare analysis stats across prompt versions."""
    from src.storage import DatabaseManager

    version_list = [v.strip() for v in versions.split(",") if v.strip()]
    if not version_list:
        raise HTTPException(status_code=400, detail="At least one version is required")

    db = DatabaseManager.get_instance()
    rows = db.get_prompt_comparison(version_list)
    return PromptComparisonResponse(versions=rows)
