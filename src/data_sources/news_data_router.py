"""Unified news/search router built on top of SearchService."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .source_health import SourceHealthRegistry
from .source_models import NewsBundle, SourceAttempt, SourceStatus, utc_now_iso

logger = logging.getLogger(__name__)


class NewsDataRouter:
    def __init__(
        self,
        search_service: Any,
        *,
        enabled: bool = True,
        max_items_per_stock: int = 8,
        health_registry: Optional[SourceHealthRegistry] = None,
    ) -> None:
        self.search_service = search_service
        self.enabled = bool(enabled)
        self.max_items_per_stock = max(1, int(max_items_per_stock or 8))
        self.health = health_registry or SourceHealthRegistry()

    @property
    def is_available(self) -> bool:
        return bool(
            self.enabled
            and self.search_service is not None
            and getattr(self.search_service, "is_available", False)
        )

    def search_stock_intel(
        self,
        *,
        stock_code: str,
        stock_name: str,
        max_searches: int = 5,
    ) -> NewsBundle:
        started_at = utc_now_iso()
        if not self.enabled:
            ended_at = utc_now_iso()
            return NewsBundle(
                stock_code=stock_code,
                stock_name=stock_name,
                source_name=None,
                data_timestamp=ended_at,
                attempts=[
                    SourceAttempt(
                        source_name="news_router",
                        status=SourceStatus.DISABLED,
                        started_at=started_at,
                        ended_at=ended_at,
                        error_message="NEWS_ENABLED=false",
                    )
                ],
                status=SourceStatus.DISABLED,
                insufficient_reason="新闻增强已关闭",
            )

        if self.search_service is None or not getattr(self.search_service, "is_available", False):
            ended_at = utc_now_iso()
            return NewsBundle(
                stock_code=stock_code,
                stock_name=stock_name,
                source_name=None,
                data_timestamp=ended_at,
                attempts=[
                    SourceAttempt(
                        source_name="news_router",
                        status=SourceStatus.EMPTY,
                        started_at=started_at,
                        ended_at=ended_at,
                        error_message="no available news provider",
                    )
                ],
                status=SourceStatus.EMPTY,
                insufficient_reason="未配置可用新闻源，禁止编造新闻、公告或舆情",
            )

        try:
            responses: Dict[str, Any] = self.search_service.search_comprehensive_intel(
                stock_code=stock_code,
                stock_name=stock_name,
                max_searches=max_searches,
            )
            context_text = (
                self.search_service.format_intel_report(responses, stock_name)
                if responses
                else ""
            )
        except Exception as exc:
            ended_at = utc_now_iso()
            self.health.record_failure("news_router", str(exc))
            logger.warning("[news-router] stock intel failed for %s: %s", stock_code, exc)
            return NewsBundle(
                stock_code=stock_code,
                stock_name=stock_name,
                source_name=None,
                data_timestamp=ended_at,
                attempts=[
                    SourceAttempt(
                        source_name="news_router",
                        status=SourceStatus.FAILED,
                        started_at=started_at,
                        ended_at=ended_at,
                        error_message=str(exc),
                    )
                ],
                status=SourceStatus.FAILED,
                insufficient_reason="新闻源/API 全部失败，禁止编造新闻、公告或舆情",
            )

        ended_at = utc_now_iso()
        total_results = sum(
            len(getattr(response, "results", []) or [])
            for response in responses.values()
            if getattr(response, "success", False)
        )
        successful_providers = [
            str(getattr(response, "provider", ""))
            for response in responses.values()
            if getattr(response, "success", False) and getattr(response, "provider", "")
        ]
        source_name = ", ".join(dict.fromkeys(successful_providers)) or None
        status = SourceStatus.OK if total_results > 0 and context_text.strip() else SourceStatus.EMPTY
        attempt_source = source_name or "news_router"
        if status == SourceStatus.OK:
            self.health.record_success(attempt_source)
        else:
            self.health.record_empty(attempt_source, "empty news result")
        return NewsBundle(
            stock_code=stock_code,
            stock_name=stock_name,
            source_name=source_name,
            data_timestamp=ended_at,
            context_text=context_text if status == SourceStatus.OK else "",
            responses=responses,
            result_count=min(total_results, self.max_items_per_stock * max(1, len(responses))),
            attempts=[
                SourceAttempt(
                    source_name=attempt_source,
                    status=status,
                    started_at=started_at,
                    ended_at=ended_at,
                    error_message=None if status == SourceStatus.OK else "empty news result",
                    record_count=total_results,
                )
            ],
            status=status,
            insufficient_reason=None if status == SourceStatus.OK else "未检索到有效新闻、公告或舆情，禁止编造",
        )
