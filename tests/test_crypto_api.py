# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch, AsyncMock
import json
import pytest
import unittest

# Mock optional modules before importing project code
for optional_module in ("litellm", "json_repair"):
    try:
        __import__(optional_module)
    except ModuleNotFoundError:
        sys.modules[optional_module] = MagicMock()

if "pandas" not in sys.modules:
    sys.modules["pandas"] = ModuleType("pandas")

from fastapi import HTTPException

from api.v1.endpoints import crypto as crypto_endpoint


@pytest.mark.not_network
class CryptoApiAnalyzeEndpointTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = SimpleNamespace(
            crypto_ai_enrichment_enabled=True,
            crypto_ai_quick_model="test-quick-model",
            crypto_ai_deep_model="test-deep-model",
            crypto_ai_cache_ttl_sec=21600,
            litellm_model="fallback-model",
        )

    async def test_analyze_launch_returns_403_when_ai_enrichment_disabled(self):
        disabled_config = SimpleNamespace(**{**self.config.__dict__, "crypto_ai_enrichment_enabled": False})

        with patch("src.config.Config.get_instance", return_value=disabled_config):
            with self.assertRaises(HTTPException) as ctx:
                await crypto_endpoint.analyze_launch(101)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "AI enrichment is disabled")

    async def test_analyze_launch_returns_404_when_launch_does_not_exist(self):
        fake_ai_service = AsyncMock()
        fake_ai_service.analyze.return_value = {"error": "Launch not found", "launch_id": 999}

        with patch("src.config.Config.get_instance", return_value=self.config), patch(
            "src.services.crypto_ai_service.CryptoAiService", return_value=fake_ai_service
        ):
            with self.assertRaises(HTTPException) as ctx:
                await crypto_endpoint.analyze_launch(999)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Launch not found")
        fake_ai_service.analyze.assert_awaited_once_with(999)

    async def test_analyze_launch_returns_502_when_ai_pipeline_raises(self):
        fake_ai_service = AsyncMock()
        fake_ai_service.analyze.side_effect = RuntimeError("llm boom")

        with patch("src.config.Config.get_instance", return_value=self.config), patch(
            "src.services.crypto_ai_service.CryptoAiService", return_value=fake_ai_service
        ):
            with self.assertRaises(HTTPException) as ctx:
                await crypto_endpoint.analyze_launch(101)

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(ctx.exception.detail, "AI analysis failed. Please try again later.")
        fake_ai_service.analyze.assert_awaited_once_with(101)

    async def test_analyze_launch_returns_200_success_with_mocked_ai_service(self):
        ai_result = {
            "launch_id": 101,
            "verdict": "HOLD",
            "confidence": 0.66,
            "bull_case": "Healthy liquidity and steady buys.",
            "bear_case": "Still early and volatile.",
            "risks": ["Mintable contract"],
            "recommended_action": "Wait for another confirmation candle.",
            "model_used": "test-deep-model",
            "prompt_version": "v1",
            "analyzed_at": "2026-03-23T10:00:00",
            "error": None,
            "cached": False,
        }
        fake_ai_service = AsyncMock()
        fake_ai_service.analyze.return_value = ai_result

        with patch("src.config.Config.get_instance", return_value=self.config), patch(
            "src.services.crypto_ai_service.CryptoAiService", return_value=fake_ai_service
        ):
            response = await crypto_endpoint.analyze_launch(101)

        self.assertEqual(response.launch_id, 101)
        self.assertEqual(response.verdict, "HOLD")
        self.assertEqual(response.model_used, "test-deep-model")
        self.assertEqual(response.risks, ["Mintable contract"])
        self.assertFalse(response.cached)
        fake_ai_service.analyze.assert_awaited_once_with(101)

    async def test_analyze_launch_returns_502_when_ai_returns_error(self):
        fake_ai_service = AsyncMock()
        fake_ai_service.analyze.return_value = {"error": "Failed to persist: IntegrityError", "launch_id": 101}

        with patch("src.config.Config.get_instance", return_value=self.config), patch(
            "src.services.crypto_ai_service.CryptoAiService", return_value=fake_ai_service
        ):
            with self.assertRaises(HTTPException) as ctx:
                await crypto_endpoint.analyze_launch(101)

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(ctx.exception.detail, "AI analysis failed. Please try again later.")
        fake_ai_service.analyze.assert_awaited_once_with(101)


if __name__ == "__main__":
    unittest.main()
