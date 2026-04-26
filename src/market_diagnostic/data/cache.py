"""
Data Cache for Market Diagnostic System

Implements file-based caching with date-based keys and 60-day retention.
Cache files are stored as JSON in ~/.cache/market_diagnostic/ by default.

Requirements: 23.1, 23.2
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DiagnosticDataCache:
    """
    File-based cache for market diagnostic data.

    Stores data as JSON files named ``{date}_{key}.json`` in the cache
    directory.  Entries older than ``retention_days`` (default 60) are
    considered expired and can be removed with :meth:`clear_expired`.

    Args:
        cache_dir: Directory used for cache storage.  Defaults to
            ``~/.cache/market_diagnostic/``.
    """

    DEFAULT_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "market_diagnostic")

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir is not None else Path(self.DEFAULT_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"[DiagnosticDataCache] Cache directory: {self.cache_dir}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cache_path(self, key: str, date: str) -> Path:
        """Return the file path for a given (key, date) pair."""
        filename = f"{date}_{key}.json"
        return self.cache_dir / filename

    def _is_expired(self, path: Path, retention_days: int) -> bool:
        """Return True if the cache file is older than *retention_days*."""
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            age = datetime.now() - mtime
            return age > timedelta(days=retention_days)
        except OSError:
            return True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def has(self, key: str, date: str) -> bool:
        """
        Check whether a non-expired cache entry exists.

        Args:
            key: Data identifier (e.g. ``"index_series"``, ``"breadth"``).
            date: Date string in ``YYYY-MM-DD`` format.

        Returns:
            ``True`` if the entry exists and has not expired (60-day
            retention), ``False`` otherwise.
        """
        path = self._cache_path(key, date)
        if not path.exists():
            return False
        if self._is_expired(path, retention_days=60):
            logger.debug(f"[DiagnosticDataCache] Expired entry: {path.name}")
            return False
        return True

    def get(self, key: str, date: str) -> Optional[Any]:
        """
        Retrieve cached data for the given key and date.

        Args:
            key: Data identifier.
            date: Date string in ``YYYY-MM-DD`` format.

        Returns:
            The cached Python object, or ``None`` if the entry does not
            exist or has expired.
        """
        path = self._cache_path(key, date)
        if not path.exists():
            logger.debug(f"[DiagnosticDataCache] Cache miss: {path.name}")
            return None
        if self._is_expired(path, retention_days=60):
            logger.debug(f"[DiagnosticDataCache] Expired cache entry: {path.name}")
            return None
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            logger.debug(f"[DiagnosticDataCache] Cache hit: {path.name}")
            return data
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"[DiagnosticDataCache] Failed to read cache file {path.name}: {exc}")
            return None

    def set(self, key: str, date: str, data: Any) -> None:
        """
        Store data in the cache under the given key and date.

        The data must be JSON-serialisable.  The file is written
        atomically (write to a temp file then rename) to avoid partial
        writes.

        Args:
            key: Data identifier.
            date: Date string in ``YYYY-MM-DD`` format.
            data: JSON-serialisable Python object to cache.
        """
        path = self._cache_path(key, date)
        tmp_path = path.with_suffix(".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            tmp_path.replace(path)
            logger.debug(f"[DiagnosticDataCache] Cached: {path.name}")
        except (OSError, TypeError) as exc:
            logger.error(f"[DiagnosticDataCache] Failed to write cache file {path.name}: {exc}")
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    def clear_expired(self, retention_days: int = 60) -> int:
        """
        Remove cache entries older than *retention_days*.

        Args:
            retention_days: Maximum age in days before an entry is
                considered expired.  Defaults to 60.

        Returns:
            Number of cache files removed.
        """
        removed = 0
        try:
            for path in self.cache_dir.glob("*.json"):
                if self._is_expired(path, retention_days):
                    try:
                        path.unlink()
                        removed += 1
                        logger.debug(f"[DiagnosticDataCache] Removed expired entry: {path.name}")
                    except OSError as exc:
                        logger.warning(f"[DiagnosticDataCache] Could not remove {path.name}: {exc}")
        except OSError as exc:
            logger.warning(f"[DiagnosticDataCache] Error scanning cache directory: {exc}")
        logger.info(f"[DiagnosticDataCache] Cleared {removed} expired cache entries (retention={retention_days}d)")
        return removed

    def clear_all(self) -> None:
        """
        Remove all cache entries from the cache directory.
        """
        removed = 0
        try:
            for path in self.cache_dir.glob("*.json"):
                try:
                    path.unlink()
                    removed += 1
                except OSError as exc:
                    logger.warning(f"[DiagnosticDataCache] Could not remove {path.name}: {exc}")
        except OSError as exc:
            logger.warning(f"[DiagnosticDataCache] Error scanning cache directory: {exc}")
        logger.info(f"[DiagnosticDataCache] Cleared all {removed} cache entries")
