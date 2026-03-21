# -*- coding: utf-8 -*-
"""Data access layer for crypto watchlist operations."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select

from src.storage import CryptoLaunch, CryptoWatchlist, DatabaseManager

logger = logging.getLogger(__name__)


class CryptoWatchlistRepository:
    """Data access for crypto watchlist entries."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def add_watch(self, launch_id: int, note: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Add a launch to the watchlist.

        Returns the watchlist entry dict, or None if the launch does not exist.
        If the launch is already watched, returns the existing entry.
        """
        try:
            with self.db.get_session() as session:
                launch = session.execute(
                    select(CryptoLaunch).where(CryptoLaunch.id == launch_id)
                ).scalar_one_or_none()
                if not launch:
                    return None

                existing = session.execute(
                    select(CryptoWatchlist).where(CryptoWatchlist.launch_id == launch_id)
                ).scalar_one_or_none()
                if existing:
                    return self._to_dict(existing)

                entry = CryptoWatchlist(
                    launch_id=launch_id,
                    watched_at=datetime.now(),
                    note=note,
                )
                session.add(entry)
                session.flush()
                session.commit()
                session.refresh(entry)
                return self._to_dict(entry)
        except Exception:
            logger.exception("add_watch failed for launch_id=%s", launch_id)
            return None

    def remove_watch(self, launch_id: int) -> bool:
        """Remove a launch from the watchlist. Returns True if removed."""
        try:
            with self.db.get_session() as session:
                result = session.execute(
                    delete(CryptoWatchlist).where(CryptoWatchlist.launch_id == launch_id)
                )
                if result.rowcount and result.rowcount > 0:
                    session.commit()
                    return True
                session.rollback()
                return False
        except Exception:
            logger.exception("remove_watch failed for launch_id=%s", launch_id)
            return False

    def list_watched(self) -> List[Dict[str, Any]]:
        """Return all watched launches with their watchlist metadata."""
        try:
            with self.db.get_session() as session:
                entries = session.execute(
                    select(CryptoWatchlist).order_by(CryptoWatchlist.watched_at.desc())
                ).scalars().all()
                return [self._to_dict(entry) for entry in entries]
        except Exception:
            logger.exception("list_watched failed")
            return []

    def is_watched(self, launch_id: int) -> bool:
        """Check whether a launch is on the watchlist."""
        try:
            with self.db.get_session() as session:
                result = session.execute(
                    select(CryptoWatchlist).where(CryptoWatchlist.launch_id == launch_id)
                ).scalar_one_or_none()
                return result is not None
        except Exception:
            logger.exception("is_watched failed for launch_id=%s", launch_id)
            return False

    def get_watched_launch_ids(self) -> List[int]:
        """Return all watched launch ids for lightweight bulk checks."""
        try:
            with self.db.get_session() as session:
                launch_ids = session.execute(select(CryptoWatchlist.launch_id)).scalars().all()
                return list(launch_ids)
        except Exception:
            logger.exception("get_watched_launch_ids failed")
            return []

    @staticmethod
    def _to_dict(entry: CryptoWatchlist) -> Dict[str, Any]:
        return {
            "id": entry.id,
            "launch_id": entry.launch_id,
            "watched_at": entry.watched_at.isoformat() if entry.watched_at else None,
            "note": entry.note,
        }
