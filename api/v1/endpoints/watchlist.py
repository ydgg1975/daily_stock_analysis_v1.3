"""Watchlist (favorites) API endpoints."""
from __future__ import annotations
from typing import List
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from src.services.watchlist_service import WatchlistService
from src.services.watchlist_enrichment_service import WatchlistEnrichmentService
from src.services.stock_identity_service import normalize_stock_identity, StockIdentityNotFound
from src.storage import DatabaseManager

router = APIRouter()


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------

class AddWatchlistRequest(BaseModel):
    stock_code: str = Field(..., alias="stockCode", min_length=1, max_length=10)
    stock_name: str | None = Field(None, alias="stockName")
    model_config = {"populate_by_name": True}


class ReorderItem(BaseModel):
    stock_code: str = Field(alias="stockCode")
    sort_order: int = Field(alias="sortOrder")
    group_id: str = Field(alias="groupId")
    model_config = {"populate_by_name": True}


class ReorderRequest(BaseModel):
    items: List[ReorderItem]


class CreateGroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class RenameGroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)


# ------------------------------------------------------------------
# Service factories
# ------------------------------------------------------------------

def _get_service() -> WatchlistService:
    db = DatabaseManager.get_instance()
    return WatchlistService(db._SessionLocal)


def _get_enrichment_service() -> WatchlistEnrichmentService:
    db = DatabaseManager.get_instance()
    return WatchlistEnrichmentService(db._SessionLocal)


# ------------------------------------------------------------------
# Endpoints — static paths MUST come before parameterized routes
# ------------------------------------------------------------------

@router.get("")
def list_watchlist(request: Request):
    user_id = request.state.user_id
    items = _get_service().list(user_id)
    return {"items": items}


@router.post("")
def add_to_watchlist(request: Request, body: AddWatchlistRequest):
    user_id = request.state.user_id
    try:
        canonical_code, canonical_name = normalize_stock_identity(body.stock_code)
    except StockIdentityNotFound as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "stock.identity_not_found", "message": str(exc)},
        )
    item = _get_service().add(user_id, canonical_code, canonical_name)
    return item


@router.get("/enriched")
def get_enriched_watchlist(request: Request):
    user_id = request.state.user_id
    return _get_enrichment_service().get_enriched(user_id)


@router.put("/reorder")
def reorder_watchlist(request: Request, body: ReorderRequest):
    user_id = request.state.user_id
    items = [
        {"stock_code": i.stock_code, "sort_order": i.sort_order, "group_id": i.group_id}
        for i in body.items
    ]
    _get_service().reorder(user_id, items)
    return {"ok": True}


@router.post("/groups")
def create_group(request: Request, body: CreateGroupRequest):
    user_id = request.state.user_id
    return _get_service().create_group(user_id, body.name)


@router.put("/groups/{group_id}")
def rename_group(request: Request, group_id: str, body: RenameGroupRequest):
    user_id = request.state.user_id
    if not _get_service().rename_group(user_id, group_id, body.name):
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return {"ok": True}


@router.delete("/groups/{group_id}")
def delete_group(request: Request, group_id: str):
    user_id = request.state.user_id
    if not _get_service().delete_group(user_id, group_id):
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return {"ok": True}


# Parameterized route — MUST be last
@router.delete("/{stock_code}")
def remove_from_watchlist(request: Request, stock_code: str):
    user_id = request.state.user_id
    removed = _get_service().remove(user_id, stock_code)
    if not removed:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    return {"ok": True}
