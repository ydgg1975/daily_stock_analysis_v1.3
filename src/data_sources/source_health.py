"""In-process source health bookkeeping for router decisions and reports."""

from __future__ import annotations

from threading import RLock
from typing import Dict, List, Optional

from .source_models import SourceHealthSnapshot, SourceStatus, utc_now_iso


class SourceHealthRegistry:
    def __init__(self) -> None:
        self._items: Dict[str, SourceHealthSnapshot] = {}
        self._lock = RLock()

    def record_success(self, source_name: str) -> None:
        self._record(source_name, SourceStatus.OK, None)

    def record_empty(self, source_name: str, message: Optional[str] = None) -> None:
        self._record(source_name, SourceStatus.EMPTY, message)

    def record_failure(self, source_name: str, message: Optional[str] = None) -> None:
        self._record(source_name, SourceStatus.FAILED, message)

    def _record(self, source_name: str, status: SourceStatus, message: Optional[str]) -> None:
        name = str(source_name or "unknown").strip() or "unknown"
        with self._lock:
            previous = self._items.get(name)
            success_count = previous.success_count if previous else 0
            failure_count = previous.failure_count if previous else 0
            if status == SourceStatus.OK:
                success_count += 1
            elif status in {SourceStatus.EMPTY, SourceStatus.FAILED}:
                failure_count += 1
            self._items[name] = SourceHealthSnapshot(
                source_name=name,
                status=status,
                last_checked_at=utc_now_iso(),
                error_message=message,
                success_count=success_count,
                failure_count=failure_count,
            )

    def snapshot(self) -> List[SourceHealthSnapshot]:
        with self._lock:
            return list(self._items.values())

    def get(self, source_name: str) -> Optional[SourceHealthSnapshot]:
        with self._lock:
            return self._items.get(source_name)
