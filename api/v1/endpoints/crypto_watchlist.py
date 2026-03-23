# -*- coding: utf-8 -*-
"""Crypto watchlist API endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from api.v1.schemas.crypto_watchlist import (
    AddWatchRequest,
    AddWatchResponse,
    RemoveWatchResponse,
    WatchedIdsResponse,
    WatchlistEntry,
    WatchlistResponse,
)
from src.repositories.crypto_watchlist_repo import CryptoWatchlistRepository

logger = logging.getLogger(__name__)

router = APIRouter()

_repo: Optional[CryptoWatchlistRepository] = None


def _get_repo() -> CryptoWatchlistRepository:
    global _repo
    if _repo is None:
        _repo = CryptoWatchlistRepository()
    return _repo


@router.get("/watchlist", response_model=WatchlistResponse)
async def list_watchlist() -> WatchlistResponse:
    """List all watched crypto launches."""
    items = _get_repo().list_watched()
    entries = [WatchlistEntry(**item) for item in items]
    return WatchlistResponse(items=entries, total=len(entries))


@router.get("/watchlist/ids", response_model=WatchedIdsResponse)
async def get_watched_ids() -> WatchedIdsResponse:
    """Get all watched launch ids for lightweight UI checks."""
    launch_ids = _get_repo().get_watched_launch_ids()
    return WatchedIdsResponse(launch_ids=launch_ids)


@router.post("/watchlist/{launch_id}", response_model=AddWatchResponse)
async def add_to_watchlist(
    launch_id: int,
    body: Optional[AddWatchRequest] = None,
) -> AddWatchResponse:
    """Add a crypto launch to the watchlist."""
    note = body.note if body else None
    entry = _get_repo().add_watch(launch_id, note=note)
    if entry is None:
        raise HTTPException(status_code=404, detail="Launch not found")
    return AddWatchResponse(
        success=True,
        entry=WatchlistEntry(**entry),
        message="Added to watchlist",
    )


@router.delete("/watchlist/{launch_id}", response_model=RemoveWatchResponse)
async def remove_from_watchlist(launch_id: int) -> RemoveWatchResponse:
    """Remove a crypto launch from the watchlist."""
    removed = _get_repo().remove_watch(launch_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Watch entry not found")
    return RemoveWatchResponse(success=True, message="Removed from watchlist")
