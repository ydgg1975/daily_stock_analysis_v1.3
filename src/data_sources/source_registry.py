"""Source registry facade over existing fetcher/search services."""

from __future__ import annotations

from typing import Any, List


class SourceRegistry:
    def __init__(self, *, fetcher_manager: Any = None, search_service: Any = None) -> None:
        self.fetcher_manager = fetcher_manager
        self.search_service = search_service

    def market_source_names(self) -> List[str]:
        manager = self.fetcher_manager
        if manager is None:
            return []
        getter = getattr(manager, "_get_fetchers_snapshot", None)
        if not callable(getter):
            return []
        try:
            return [getattr(fetcher, "name", "") for fetcher in getter() if getattr(fetcher, "name", "")]
        except Exception:
            return []

    def news_source_names(self) -> List[str]:
        service = self.search_service
        providers = getattr(service, "_providers", []) if service is not None else []
        return [getattr(provider, "name", "") for provider in providers if getattr(provider, "name", "")]
