"""Announcement router using focused news search dimensions."""

from __future__ import annotations

from .news_data_router import NewsDataRouter


class AnnouncementRouter(NewsDataRouter):
    """Reserved facade for announcement-specific routing.

    The current SearchService already has an "announcements" dimension inside
    comprehensive intelligence search, so this class intentionally reuses the
    same implementation while giving callers a stable import path.
    """
