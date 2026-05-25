# -*- coding: utf-8 -*-
"""Unit tests for the OpenAI Web Search provider."""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

if "data_provider.us_index_mapping" not in sys.modules:
    mock_data_provider = types.ModuleType("data_provider")
    mock_us_index_mapping = types.ModuleType("data_provider.us_index_mapping")
    mock_us_index_mapping.is_us_index_code = lambda code: False
    sys.modules.setdefault("data_provider", mock_data_provider)
    sys.modules["data_provider.us_index_mapping"] = mock_us_index_mapping

if "newspaper" not in sys.modules:
    mock_np = MagicMock()
    mock_np.Article = MagicMock()
    mock_np.Config = MagicMock()
    sys.modules["newspaper"] = mock_np

from src.search_service import OpenAIWebSearchProvider, SearchService


class TestOpenAIWebSearchProvider(unittest.TestCase):
    @staticmethod
    def _response(status_code=200, json_payload=None, text="", headers=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = text
        resp.headers = headers or {"content-type": "application/json"}
        resp.json.return_value = {} if json_payload is None else json_payload
        return resp

    @patch("src.search_service._post_with_retry")
    def test_search_parses_responses_output_text(self, mock_post):
        mock_post.return_value = self._response(
            json_payload={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"results":[{"title":"招商银行发布公告",'
                                    '"snippet":"招商银行披露最新经营情况。",'
                                    '"url":"https://example.com/news/1",'
                                    '"source":"Example Finance",'
                                    '"published_date":"2026-05-25"}]}'
                                ),
                            }
                        ],
                    }
                ]
            }
        )

        provider = OpenAIWebSearchProvider(["sk-test"])
        resp = provider.search("招商银行 600036 股票 最新消息", max_results=3, days=3)

        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "OpenAI Web Search")
        self.assertEqual(len(resp.results), 1)
        self.assertEqual(resp.results[0].title, "招商银行发布公告")
        self.assertEqual(resp.results[0].source, "Example Finance")

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "gpt-5.5")
        self.assertEqual(payload["tools"], [{"type": "web_search", "search_context_size": "low"}])
        self.assertEqual(payload["tool_choice"], "required")
        self.assertIn("/responses", mock_post.call_args.args[0])

    def test_search_service_adds_openai_web_search_provider(self):
        service = SearchService(
            openai_web_search_keys=["sk-test"],
            searxng_public_instances_enabled=False,
        )

        self.assertTrue(service.is_available)
        self.assertTrue(
            any(provider.name == "OpenAI Web Search" for provider in service._providers)
        )


if __name__ == "__main__":
    unittest.main()
