# -*- coding: utf-8 -*-
"""Tests for history fallback published_date hard filtering (Issue #697)."""

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.services.history_service import HistoryService


class HistoryNewsFallbackTestCase(unittest.TestCase):
    def test_get_history_list_uses_analysis_repository_boundary(self) -> None:
        db_manager = MagicMock()
        repo = MagicMock()
        repo.get_paginated.return_value = (
            [
                SimpleNamespace(
                    id=1,
                    query_id="q-1",
                    code="600519",
                    name="贵州茅台",
                    report_type="standard",
                    sentiment_score=80,
                    operation_advice="hold",
                    created_at=datetime(2026, 4, 17, 8, 0, 0),
                )
            ],
            1,
        )

        with patch("src.services.history_service.AnalysisRepository", create=True) as repo_cls:
            repo_cls.return_value = repo
            service = HistoryService(db_manager=db_manager, owner_id="user-1")
            result = service.get_history_list(page=1, limit=20)

        repo_cls.assert_called_once_with(db_manager, owner_id="user-1", include_all_owners=False)
        repo.get_paginated.assert_called_once_with(
            code=None,
            start_date=None,
            end_date=None,
            offset=0,
            limit=20,
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["query_id"], "q-1")

    def test_fallback_filters_by_published_date_window(self) -> None:
        now = datetime.now()
        analysis = SimpleNamespace(code="600519", created_at=now)

        # All entries are within fetched_at window; only one should pass published_date window.
        candidates = [
            SimpleNamespace(
                fetched_at=now,
                published_date=now - timedelta(days=20),  # too old
                title="old",
            ),
            SimpleNamespace(
                fetched_at=now,
                published_date=None,  # unknown -> drop
                title="unknown",
            ),
            SimpleNamespace(
                fetched_at=now,
                published_date=now - timedelta(days=1),  # valid
                title="fresh",
            ),
        ]

        mock_db = MagicMock()
        mock_db.get_analysis_history.return_value = [analysis]
        mock_db.get_recent_news.return_value = candidates

        svc = HistoryService(db_manager=mock_db)
        fake_cfg = SimpleNamespace(news_max_age_days=30, news_strategy_profile="short")
        with patch("src.services.history_service.get_config", return_value=fake_cfg):
            result = svc._fallback_news_by_analysis_context("q-1", limit=20)

        self.assertEqual([item.title for item in result], ["fresh"])

    def test_fallback_uses_analysis_date_as_window_anchor(self) -> None:
        analysis_time = datetime.now() - timedelta(days=40)
        analysis = SimpleNamespace(code="600519", created_at=analysis_time)

        candidates = [
            SimpleNamespace(
                fetched_at=analysis_time,
                published_date=analysis_time - timedelta(days=10),  # too old for short profile
                title="too_old_for_analysis_window",
            ),
            SimpleNamespace(
                fetched_at=analysis_time,
                published_date=analysis_time - timedelta(days=1),  # valid around analysis date
                title="valid_near_analysis_date",
            ),
        ]

        mock_db = MagicMock()
        mock_db.get_analysis_history.return_value = [analysis]
        mock_db.get_recent_news.return_value = candidates

        svc = HistoryService(db_manager=mock_db)
        fake_cfg = SimpleNamespace(news_max_age_days=30, news_strategy_profile="short")
        with patch("src.services.history_service.get_config", return_value=fake_cfg):
            result = svc._fallback_news_by_analysis_context("q-1", limit=20)

        self.assertEqual([item.title for item in result], ["valid_near_analysis_date"])


if __name__ == "__main__":
    unittest.main()
