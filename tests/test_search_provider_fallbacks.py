# -*- coding: utf-8 -*-
"""Tests for Finnhub/GNews provider integration and dimension fallback."""

import sys
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

if "newspaper" not in sys.modules:
    mock_np = MagicMock()
    mock_np.Article = MagicMock()
    mock_np.Config = MagicMock()
    sys.modules["newspaper"] = mock_np

from src.search_service import SearchResponse, SearchResult, SearchService


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class SearchProviderFallbacksTestCase(unittest.TestCase):
    @patch("src.search_service.requests.get")
    def test_search_stock_news_uses_finnhub_company_news(self, mock_get) -> None:
        published_ts = int(datetime(2026, 3, 27, 13, 0, tzinfo=timezone.utc).timestamp())
        mock_get.return_value = _FakeResponse(
            [
                {
                    "headline": "NVIDIA raises guidance",
                    "summary": "Company updated revenue outlook.",
                    "url": "https://example.com/nvda-guidance",
                    "source": "Reuters",
                    "datetime": published_ts,
                }
            ]
        )
        service = SearchService(
            finnhub_keys=["fh-key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        resp = service.search_stock_news("NVDA", "NVIDIA", max_results=2)
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "Finnhub")
        self.assertEqual(len(resp.results), 1)
        self.assertEqual(resp.results[0].published_date, "2026-03-27")

    @patch("src.search_service.requests.get")
    def test_search_stock_news_falls_back_from_finnhub_to_gnews(self, mock_get) -> None:
        def _side_effect(url, params=None, headers=None, timeout=10):
            if "finnhub.io" in url:
                return _FakeResponse([])
            if "gnews.io" in url:
                return _FakeResponse(
                    {
                        "articles": [
                            {
                                "title": "Oracle signs major cloud deal",
                                "description": "New enterprise cloud order announced.",
                                "url": "https://example.com/orcl-cloud",
                                "publishedAt": "2026-03-27T09:10:00Z",
                                "source": {"name": "GNewsSource"},
                            }
                        ]
                    }
                )
            raise AssertionError(f"Unexpected URL: {url}")

        mock_get.side_effect = _side_effect
        service = SearchService(
            finnhub_keys=["fh-key"],
            gnews_keys=["gnews-key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        resp = service.search_stock_news("ORCL", "Oracle", max_results=2)
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "GNews")
        self.assertEqual(len(resp.results), 1)
        self.assertEqual(resp.results[0].published_date, "2026-03-27")

    def test_search_comprehensive_intel_tries_next_provider_for_dimension(self) -> None:
        service = SearchService(searxng_public_instances_enabled=False)
        p1 = SimpleNamespace(
            is_available=True,
            name="P1",
            search_news=MagicMock(
                return_value=SearchResponse(
                    query="q1",
                    results=[],
                    provider="P1",
                    success=False,
                    error_message="boom",
                )
            ),
        )
        p2 = SimpleNamespace(
            is_available=True,
            name="P2",
            search_news=MagicMock(
                return_value=SearchResponse(
                    query="q2",
                    results=[
                        SearchResult(
                            title="Oracle coverage",
                            snippet="Fresh item",
                            url="https://example.com/orcl",
                            source="example.com",
                            published_date="2026-03-27",
                        )
                    ],
                    provider="P2",
                    success=True,
                )
            ),
        )
        service._providers = [p1, p2]

        intel = service.search_comprehensive_intel("ORCL", "Oracle", max_searches=1)
        self.assertIn("latest_news", intel)
        self.assertEqual(intel["latest_news"].provider, "P2")
        p1.search_news.assert_called_once()
        p2.search_news.assert_called_once()


if __name__ == "__main__":
    unittest.main()
