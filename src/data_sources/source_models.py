"""Typed contracts for unified data source routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    import pandas as pd


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SourceStatus(str, Enum):
    OK = "ok"
    EMPTY = "empty"
    FAILED = "failed"
    DISABLED = "disabled"
    NOT_SUPPORTED = "not_supported"


@dataclass(frozen=True)
class SourceAttempt:
    source_name: str
    status: SourceStatus
    started_at: str
    ended_at: str
    error_message: Optional[str] = None
    record_count: int = 0

    @property
    def success(self) -> bool:
        return self.status == SourceStatus.OK

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "source_name": self.source_name,
            "status": self.status.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "record_count": self.record_count,
        }
        if self.error_message:
            payload["error_message"] = self.error_message
        return payload


@dataclass
class MarketDataBundle:
    stock_code: str
    source_name: Optional[str]
    data_timestamp: str
    realtime_quote: Any = None
    kline_daily: Optional["pd.DataFrame"] = None
    fundamental_context: Optional[Dict[str, Any]] = None
    attempts: List[SourceAttempt] = field(default_factory=list)
    status: SourceStatus = SourceStatus.EMPTY
    insufficient_reason: Optional[str] = None

    @property
    def has_trade_observation_data(self) -> bool:
        if self.realtime_quote is not None:
            return True
        if self.kline_daily is not None and not self.kline_daily.empty:
            return True
        return False

    def to_context_metadata(self) -> Dict[str, Any]:
        return {
            "stock_code": self.stock_code,
            "source_name": self.source_name,
            "data_timestamp": self.data_timestamp,
            "status": self.status.value,
            "insufficient_reason": self.insufficient_reason,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }


@dataclass
class NewsBundle:
    stock_code: str
    stock_name: str
    source_name: Optional[str]
    data_timestamp: str
    context_text: str = ""
    responses: Dict[str, Any] = field(default_factory=dict)
    attempts: List[SourceAttempt] = field(default_factory=list)
    result_count: int = 0
    status: SourceStatus = SourceStatus.EMPTY
    insufficient_reason: Optional[str] = None

    def to_context_metadata(self) -> Dict[str, Any]:
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "source_name": self.source_name,
            "data_timestamp": self.data_timestamp,
            "status": self.status.value,
            "result_count": self.result_count,
            "insufficient_reason": self.insufficient_reason,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }


@dataclass
class AnnouncementBundle(NewsBundle):
    """Announcement evidence uses the same search response shape as news."""


@dataclass(frozen=True)
class SourceHealthSnapshot:
    source_name: str
    status: SourceStatus
    last_checked_at: str
    error_message: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "source_name": self.source_name,
            "status": self.status.value,
            "last_checked_at": self.last_checked_at,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }
        if self.error_message:
            payload["error_message"] = self.error_message
        return payload
