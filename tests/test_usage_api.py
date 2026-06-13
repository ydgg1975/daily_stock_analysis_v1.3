# -*- coding: utf-8 -*-
"""Tests for LLM usage dashboard API."""

import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import get_database_manager


class FakeUsageDbManager:
    def get_llm_usage_summary(self, from_dt, to_dt):
        return {
            "total_calls": 2,
            "total_prompt_tokens": 30,
            "total_completion_tokens": 70,
            "total_tokens": 100,
            "by_call_type": [
                {
                    "call_type": "analysis",
                    "calls": 2,
                    "prompt_tokens": 30,
                    "completion_tokens": 70,
                    "total_tokens": 100,
                }
            ],
            "by_model": [
                {
                    "model": "openai/gpt-test",
                    "calls": 2,
                    "prompt_tokens": 30,
                    "completion_tokens": 70,
                    "total_tokens": 100,
                    "max_total_tokens": 60,
                }
            ],
        }

    def get_llm_usage_records(self, from_dt, to_dt, limit=50):
        return [
            {
                "id": 7,
                "called_at": datetime(2026, 6, 11, 9, 30, 0),
                "call_type": "analysis",
                "model": "openai/gpt-test",
                "stock_code": "600519",
                "prompt_tokens": 10,
                "completion_tokens": 50,
                "total_tokens": 60,
            }
        ]


class UsageMetadataHelpersTestCase(unittest.TestCase):
    def tearDown(self):
        from api.v1.endpoints import usage as usage_endpoint

        usage_endpoint._resolve_context_window.cache_clear()

    def test_context_window_prefers_window_metadata_over_output_limit(self):
        from api.v1.endpoints import usage as usage_endpoint

        fake_litellm = types.SimpleNamespace(
            model_cost={
                "MiniMax-M3": {"context_window": 512000, "max_tokens": 128000},
                "custom-router": {"context_window": 100000, "max_tokens": 10000},
                "max-only-model": {"max_tokens": 10000},
            }
        )

        with patch.dict(sys.modules, {"litellm": fake_litellm}):
            usage_endpoint._resolve_context_window.cache_clear()

            self.assertEqual(usage_endpoint._resolve_context_window("openai/MiniMax-M3"), 512000)
            self.assertEqual(usage_endpoint._resolve_context_window("openai/custom-router"), 100000)
            self.assertIsNone(usage_endpoint._resolve_context_window("openai/max-only-model"))

    def test_provider_inference_ignores_model_organization_prefixes(self):
        from api.v1.endpoints import usage as usage_endpoint

        self.assertEqual(usage_endpoint._provider_from_model("openai/gpt-4.1-mini"), "openai")
        self.assertEqual(usage_endpoint._provider_from_model("deepseek/deepseek-chat"), "deepseek")
        self.assertIsNone(usage_endpoint._provider_from_model("Qwen/Qwen3-8B"))
        self.assertIsNone(usage_endpoint._provider_from_model("deepseek-ai/DeepSeek-V3"))
        self.assertIsNone(usage_endpoint._provider_from_model("custom-router"))


class UsageDashboardApiTestCase(unittest.TestCase):
    def test_dashboard_returns_context_metadata_and_recent_calls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = create_app(static_dir=Path(temp_dir))
            app.dependency_overrides[get_database_manager] = lambda: FakeUsageDbManager()
            client = TestClient(app)

            with patch("api.v1.endpoints.usage._resolve_context_window", return_value=120):
                response = client.get("/api/v1/usage/dashboard?period=today&limit=10")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["period"], "today")
        self.assertEqual(body["total_tokens"], 100)
        self.assertEqual(body["by_model"][0]["provider"], "openai")
        self.assertEqual(body["by_model"][0]["context_window"], 120)
        self.assertEqual(body["by_model"][0]["context_usage_ratio"], 0.5)
        self.assertEqual(body["recent_calls"][0]["stock_code"], "600519")
        self.assertEqual(body["recent_calls"][0]["context_usage_ratio"], 0.5)


if __name__ == "__main__":
    unittest.main()
