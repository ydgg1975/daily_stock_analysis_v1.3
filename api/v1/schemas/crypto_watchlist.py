# -*- coding: utf-8 -*-
"""Pydantic schemas for crypto watchlist endpoints."""
from typing import List, Optional

from pydantic import BaseModel, Field


class WatchlistEntry(BaseModel):
    """A single watchlist entry."""

    id: int
    launch_id: int
    watched_at: Optional[str] = None
    note: Optional[str] = None


class WatchlistResponse(BaseModel):
    """Response for GET /api/v1/crypto/watchlist."""

    items: List[WatchlistEntry] = Field(default_factory=list)
    total: int = 0


class AddWatchRequest(BaseModel):
    """Request body for POST /api/v1/crypto/watchlist/{launch_id}."""

    note: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional note for this watch entry",
    )


class AddWatchResponse(BaseModel):
    """Response for POST /api/v1/crypto/watchlist/{launch_id}."""

    success: bool = True
    entry: Optional[WatchlistEntry] = None
    message: str = ""


class RemoveWatchResponse(BaseModel):
    """Response for DELETE /api/v1/crypto/watchlist/{launch_id}."""

    success: bool = True
    message: str = ""


class WatchedIdsResponse(BaseModel):
    """Response for GET /api/v1/crypto/watchlist/ids."""

    launch_ids: List[int] = Field(default_factory=list)
