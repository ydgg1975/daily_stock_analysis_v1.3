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
    _pd = ModuleType("pandas")
    _pd.DataFrame = type("DataFrame", (), {})  # type: ignore[attr-defined]
    sys.modules["pandas"] = _pd

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
        # Reset module-level singletons/state between tests
        crypto_endpoint._ai_service = None
        crypto_endpoint._analyze_rate_limit.clear()
        # Mock request with client IP
        self._mock_request = MagicMock(spec=["client"])
        self._mock_request.client = SimpleNamespace(host="127.0.0.1")

    def tearDown(self):
        crypto_endpoint._ai_service = None
        crypto_endpoint._analyze_rate_limit.clear()

    async def test_analyze_launch_returns_403_when_ai_enrichment_disabled(self):
        disabled_config = SimpleNamespace(**{**self.config.__dict__, "crypto_ai_enrichment_enabled": False})

        with patch("src.config.Config.get_instance", return_value=disabled_config):
            with self.assertRaises(HTTPException) as ctx:
                await crypto_endpoint.analyze_launch(101, self._mock_request)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "AI enrichment is disabled")

    async def test_analyze_launch_returns_404_when_launch_does_not_exist(self):
        fake_ai_service = AsyncMock()
        fake_ai_service.analyze.return_value = {"error": "Launch not found", "launch_id": 999}
        crypto_endpoint._ai_service = fake_ai_service

        with patch("src.config.Config.get_instance", return_value=self.config):
            with self.assertRaises(HTTPException) as ctx:
                await crypto_endpoint.analyze_launch(999, self._mock_request)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Launch not found")
        fake_ai_service.analyze.assert_awaited_once_with(999)

    async def test_analyze_launch_returns_502_when_ai_pipeline_raises(self):
        fake_ai_service = AsyncMock()
        fake_ai_service.analyze.side_effect = RuntimeError("llm boom")
        crypto_endpoint._ai_service = fake_ai_service

        with patch("src.config.Config.get_instance", return_value=self.config):
            with self.assertRaises(HTTPException) as ctx:
                await crypto_endpoint.analyze_launch(101, self._mock_request)

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
        crypto_endpoint._ai_service = fake_ai_service

        with patch("src.config.Config.get_instance", return_value=self.config):
            response = await crypto_endpoint.analyze_launch(101, self._mock_request)

        self.assertEqual(response.launch_id, 101)
        self.assertEqual(response.verdict, "HOLD")
        self.assertEqual(response.model_used, "test-deep-model")
        self.assertEqual(response.risks, ["Mintable contract"])
        self.assertFalse(response.cached)
        fake_ai_service.analyze.assert_awaited_once_with(101)

    async def test_analyze_launch_returns_502_when_ai_returns_error(self):
        fake_ai_service = AsyncMock()
        fake_ai_service.analyze.return_value = {"error": "Failed to persist: IntegrityError", "launch_id": 101}
        crypto_endpoint._ai_service = fake_ai_service

        with patch("src.config.Config.get_instance", return_value=self.config):
            with self.assertRaises(HTTPException) as ctx:
                await crypto_endpoint.analyze_launch(101, self._mock_request)

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(ctx.exception.detail, "AI analysis failed. Please try again later.")
        fake_ai_service.analyze.assert_awaited_once_with(101)


if __name__ == "__main__":
    unittest.main()


@pytest.mark.not_network
class CryptoMetricsEndpointTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests for the provider-metrics, SLO, AI-cost, and prompt-comparison endpoints."""

    def _mock_db(self):
        """Return a MagicMock DatabaseManager with sensible defaults."""
        db = MagicMock()
        db.get_provider_metrics.return_value = [
            {
                "chain_id": "solana",
                "total_scans": 10,
                "total_failures": 1,
                "total_duration_ms": 5000,
                "total_pools_discovered": 40,
                "avg_duration_ms": 500,
                "error_rate": 0.1,
            },
        ]
        db.get_scan_slo.return_value = {
            "window_hours": 24,
            "total_scans": 100,
            "successes": 95,
            "failures": 5,
            "success_rate": 0.95,
        }
        db.get_crypto_ai_cost.return_value = {
            "window_days": 7,
            "total_calls": 12,
            "prompt_tokens": 3000,
            "completion_tokens": 1500,
            "total_tokens": 4500,
            "by_model": [
                {"model": "gpt-4o-mini", "calls": 12, "total_tokens": 4500},
            ],
        }
        db.get_prompt_comparison.return_value = [
            {
                "prompt_version": "v1",
                "analyses": 5,
                "avg_confidence": 0.72,
                "total_tokens": 2500,
                "avg_duration_sec": 3.14,
                "verdict_distribution": {"BUY": 2, "HOLD": 2, "AVOID": 1},
            },
        ]
        return db

    async def test_provider_metrics_returns_200(self):
        db = self._mock_db()
        with patch("src.storage.DatabaseManager.get_instance", return_value=db):
            response = await crypto_endpoint.get_provider_metrics()

        self.assertEqual(len(response.chains), 1)
        self.assertEqual(response.chains[0].chain_id, "solana")
        db.get_provider_metrics.assert_called_once()

    async def test_scan_slo_returns_200(self):
        db = self._mock_db()
        with patch("src.storage.DatabaseManager.get_instance", return_value=db):
            response = await crypto_endpoint.get_scan_slo(window_hours=24)

        self.assertEqual(response.total_scans, 100)
        self.assertAlmostEqual(response.success_rate, 0.95)
        db.get_scan_slo.assert_called_once_with(window_hours=24)

    async def test_ai_cost_returns_200(self):
        db = self._mock_db()
        with patch("src.storage.DatabaseManager.get_instance", return_value=db):
            response = await crypto_endpoint.get_ai_cost(window_days=7)

        self.assertEqual(response.total_calls, 12)
        self.assertEqual(response.total_tokens, 4500)
        self.assertEqual(len(response.by_model), 1)
        db.get_crypto_ai_cost.assert_called_once_with(window_days=7)

    async def test_prompt_comparison_returns_200(self):
        db = self._mock_db()
        with patch("src.storage.DatabaseManager.get_instance", return_value=db):
            response = await crypto_endpoint.get_prompt_comparison(versions="v1")

        self.assertEqual(len(response.versions), 1)
        self.assertEqual(response.versions[0].prompt_version, "v1")
        self.assertEqual(response.versions[0].analyses, 5)
        db.get_prompt_comparison.assert_called_once_with(["v1"])

    async def test_prompt_comparison_rejects_empty_versions(self):
        with self.assertRaises(HTTPException) as ctx:
            await crypto_endpoint.get_prompt_comparison(versions="")

        self.assertEqual(ctx.exception.status_code, 400)
