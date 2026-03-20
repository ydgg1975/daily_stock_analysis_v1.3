# -*- coding: utf-8 -*-
"""
===================================
Crypto Launch Data Access Layer
===================================

Responsibilities:
1. Encapsulate database operations for CryptoLaunch and CryptoLaunchSnapshot.
2. Provide upsert, list, detail, and snapshot persistence APIs.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, select, update

from src.storage import CryptoLaunch, CryptoLaunchSnapshot, DatabaseManager

logger = logging.getLogger(__name__)


class CryptoLaunchRepository:
    """Data access layer for crypto launch records and snapshots."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert_launch(self, data: Dict[str, Any]) -> Optional[int]:
        """Insert or update a launch record keyed by (chain_id, pair_address).

        Returns the launch id on success, None on failure.
        """
        chain_id = data.get("chain_id")
        pair_address = data.get("pair_address")
        if not chain_id or not pair_address:
            logger.warning("upsert_launch: missing chain_id or pair_address")
            return None

        try:
            with self.db.get_session() as session:
                existing = session.execute(
                    select(CryptoLaunch).where(
                        and_(
                            CryptoLaunch.chain_id == chain_id,
                            CryptoLaunch.pair_address == pair_address,
                        )
                    )
                ).scalar_one_or_none()

                now = datetime.now()

                if existing:
                    # Update mutable fields
                    for key in (
                        "dex_id", "pair_url", "pair_created_at",
                        "base_token_address", "base_token_symbol", "base_token_name",
                        "quote_token_address", "quote_token_symbol", "quote_token_name",
                        "liquidity_usd", "volume_usd_24h", "buys_24h", "sells_24h",
                        "price_usd", "price_change_pct_24h", "fdv_usd", "market_cap_usd",
                        "dexscreener_url", "website_url", "socials_json", "labels_json",
                        "raw_payload", "data_complete",
                    ):
                        if key in data and data[key] is not None:
                            setattr(existing, key, data[key])
                    existing.last_seen_at = now
                    existing.updated_at = now
                    session.flush()
                    return existing.id
                else:
                    launch = CryptoLaunch(
                        chain_id=chain_id,
                        pair_address=pair_address,
                        dex_id=data.get("dex_id"),
                        pair_url=data.get("pair_url"),
                        pair_created_at=data.get("pair_created_at"),
                        base_token_address=data.get("base_token_address"),
                        base_token_symbol=data.get("base_token_symbol"),
                        base_token_name=data.get("base_token_name"),
                        quote_token_address=data.get("quote_token_address"),
                        quote_token_symbol=data.get("quote_token_symbol"),
                        quote_token_name=data.get("quote_token_name"),
                        liquidity_usd=data.get("liquidity_usd"),
                        volume_usd_24h=data.get("volume_usd_24h"),
                        buys_24h=data.get("buys_24h"),
                        sells_24h=data.get("sells_24h"),
                        price_usd=data.get("price_usd"),
                        price_change_pct_24h=data.get("price_change_pct_24h"),
                        fdv_usd=data.get("fdv_usd"),
                        market_cap_usd=data.get("market_cap_usd"),
                        dexscreener_url=data.get("dexscreener_url"),
                        website_url=data.get("website_url"),
                        socials_json=data.get("socials_json"),
                        labels_json=data.get("labels_json"),
                        raw_payload=data.get("raw_payload"),
                        data_complete=data.get("data_complete", False),
                        first_seen_at=now,
                        last_seen_at=now,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(launch)
                    session.flush()
                    return launch.id
        except Exception:
            logger.exception("upsert_launch failed for %s/%s", chain_id, pair_address)
            return None

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def append_snapshot(self, launch_id: int, data: Dict[str, Any]) -> bool:
        """Append a snapshot for the given launch. Returns True on success."""
        try:
            with self.db.get_session() as session:
                snapshot = CryptoLaunchSnapshot(
                    launch_id=launch_id,
                    snapshot_at=data.get("snapshot_at", datetime.now()),
                    liquidity_usd=data.get("liquidity_usd"),
                    volume_usd_24h=data.get("volume_usd_24h"),
                    buys_24h=data.get("buys_24h"),
                    sells_24h=data.get("sells_24h"),
                    price_usd=data.get("price_usd"),
                    price_change_pct_24h=data.get("price_change_pct_24h"),
                    fdv_usd=data.get("fdv_usd"),
                    market_cap_usd=data.get("market_cap_usd"),
                    data_complete=data.get("data_complete", False),
                    raw_payload=data.get("raw_payload"),
                )
                session.add(snapshot)
                return True
        except Exception:
            logger.exception("append_snapshot failed for launch_id=%s", launch_id)
            return False

    # ------------------------------------------------------------------
    # List queries
    # ------------------------------------------------------------------

    def list_launches(
        self,
        *,
        chains: Optional[List[str]] = None,
        min_liquidity_usd: float = 0.0,
        min_volume_usd: float = 0.0,
        max_age_minutes: int = 1440,
        sort: str = "newest",
        cursor: Optional[int] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Return a paginated list of launches matching the given filters.

        Returns ``{"items": [...], "next_cursor": int|None, "total": int}``.
        """
        try:
            with self.db.get_session() as session:
                stmt = select(CryptoLaunch)
                conditions = []

                if chains:
                    conditions.append(CryptoLaunch.chain_id.in_(chains))
                if min_liquidity_usd > 0:
                    conditions.append(CryptoLaunch.liquidity_usd >= min_liquidity_usd)
                if min_volume_usd > 0:
                    conditions.append(CryptoLaunch.volume_usd_24h >= min_volume_usd)
                if max_age_minutes > 0:
                    cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
                    conditions.append(CryptoLaunch.first_seen_at >= cutoff)
                if cursor is not None:
                    conditions.append(CryptoLaunch.id < cursor)

                if conditions:
                    stmt = stmt.where(and_(*conditions))

                # Sort
                sort_map = {
                    "newest": desc(CryptoLaunch.first_seen_at),
                    "liquidity": desc(CryptoLaunch.liquidity_usd),
                    "volume": desc(CryptoLaunch.volume_usd_24h),
                    "activity": desc(CryptoLaunch.buys_24h + CryptoLaunch.sells_24h),
                }
                order = sort_map.get(sort, desc(CryptoLaunch.first_seen_at))
                stmt = stmt.order_by(order, desc(CryptoLaunch.id))

                # Count (without cursor for total)
                count_stmt = select(CryptoLaunch)
                count_conditions = [c for c in conditions if "id < " not in str(c)]
                if count_conditions:
                    count_stmt = count_stmt.where(and_(*count_conditions))
                total = len(session.execute(count_stmt).scalars().all())

                # Fetch page
                rows = session.execute(stmt.limit(limit + 1)).scalars().all()
                has_more = len(rows) > limit
                items = rows[:limit]

                next_cursor = items[-1].id if has_more and items else None

                return {
                    "items": [self._launch_to_dict(r) for r in items],
                    "next_cursor": next_cursor,
                    "total": total,
                }
        except Exception:
            logger.exception("list_launches failed")
            return {"items": [], "next_cursor": None, "total": 0}

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------

    def get_launch_detail(self, launch_id: int) -> Optional[Dict[str, Any]]:
        """Get a single launch with its recent snapshots."""
        try:
            with self.db.get_session() as session:
                launch = session.execute(
                    select(CryptoLaunch).where(CryptoLaunch.id == launch_id)
                ).scalar_one_or_none()

                if not launch:
                    return None

                # Recent snapshots (last 20)
                snapshots = session.execute(
                    select(CryptoLaunchSnapshot)
                    .where(CryptoLaunchSnapshot.launch_id == launch_id)
                    .order_by(desc(CryptoLaunchSnapshot.snapshot_at))
                    .limit(20)
                ).scalars().all()

                result = self._launch_to_dict(launch)
                result["snapshots"] = [self._snapshot_to_dict(s) for s in snapshots]
                return result
        except Exception:
            logger.exception("get_launch_detail failed for id=%s", launch_id)
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _launch_to_dict(launch: CryptoLaunch) -> Dict[str, Any]:
        return {
            "id": launch.id,
            "chain_id": launch.chain_id,
            "dex_id": launch.dex_id,
            "pair_address": launch.pair_address,
            "pair_url": launch.pair_url,
            "pair_created_at": launch.pair_created_at.isoformat() if launch.pair_created_at else None,
            "base_token_address": launch.base_token_address,
            "base_token_symbol": launch.base_token_symbol,
            "base_token_name": launch.base_token_name,
            "quote_token_address": launch.quote_token_address,
            "quote_token_symbol": launch.quote_token_symbol,
            "quote_token_name": launch.quote_token_name,
            "liquidity_usd": launch.liquidity_usd,
            "volume_usd_24h": launch.volume_usd_24h,
            "buys_24h": launch.buys_24h,
            "sells_24h": launch.sells_24h,
            "price_usd": launch.price_usd,
            "price_change_pct_24h": launch.price_change_pct_24h,
            "fdv_usd": launch.fdv_usd,
            "market_cap_usd": launch.market_cap_usd,
            "dexscreener_url": launch.dexscreener_url,
            "website_url": launch.website_url,
            "socials_json": launch.socials_json,
            "labels_json": launch.labels_json,
            "data_complete": launch.data_complete,
            "first_seen_at": launch.first_seen_at.isoformat() if launch.first_seen_at else None,
            "last_seen_at": launch.last_seen_at.isoformat() if launch.last_seen_at else None,
            "created_at": launch.created_at.isoformat() if launch.created_at else None,
            "updated_at": launch.updated_at.isoformat() if launch.updated_at else None,
        }

    @staticmethod
    def _snapshot_to_dict(snapshot: CryptoLaunchSnapshot) -> Dict[str, Any]:
        return {
            "id": snapshot.id,
            "launch_id": snapshot.launch_id,
            "snapshot_at": snapshot.snapshot_at.isoformat() if snapshot.snapshot_at else None,
            "liquidity_usd": snapshot.liquidity_usd,
            "volume_usd_24h": snapshot.volume_usd_24h,
            "buys_24h": snapshot.buys_24h,
            "sells_24h": snapshot.sells_24h,
            "price_usd": snapshot.price_usd,
            "price_change_pct_24h": snapshot.price_change_pct_24h,
            "fdv_usd": snapshot.fdv_usd,
            "market_cap_usd": snapshot.market_cap_usd,
            "data_complete": snapshot.data_complete,
        }
