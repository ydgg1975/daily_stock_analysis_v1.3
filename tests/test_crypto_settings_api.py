# -*- coding: utf-8 -*-
"""Tests for crypto settings API endpoints."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.deps import get_system_config_service
from api.v1.endpoints.crypto_settings import router
from src.services.system_config_service import ConfigConflictError, ConfigValidationError


class CryptoSettingsApiTestCase(unittest.TestCase):
    """Contract tests for crypto settings endpoints."""

    def setUp(self) -> None:
        self.service = MagicMock()
        app = FastAPI()
        app.dependency_overrides[get_system_config_service] = lambda: self.service
        app.include_router(router, prefix="/api/v1/crypto")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    def test_get_crypto_settings_filters_crypto_keys_only(self) -> None:
        self.service.get_config.return_value = {
            "config_version": "v1",
            "updated_at": "2026-03-21T00:00:00Z",
            "items": [
                {"key": "CRYPTO_ENABLED", "value": "true", "raw_value_exists": True},
                {"key": "APP_ENV", "value": "dev", "raw_value_exists": True},
                {"key": "CRYPTO_RISK_ENABLED", "value": "false", "raw_value_exists": True},
            ],
        }

        response = self.client.get("/api/v1/crypto/settings")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["config_version"], "v1")
        self.assertEqual(payload["updated_at"], "2026-03-21T00:00:00Z")
        self.assertEqual([item["key"] for item in payload["items"]], ["CRYPTO_ENABLED", "CRYPTO_RISK_ENABLED"])

    def test_get_crypto_settings_includes_schema_info(self) -> None:
        self.service.get_config.return_value = {
            "config_version": "v2",
            "items": [
                {
                    "key": "CRYPTO_SECURITY_PROVIDER",
                    "value": "auto",
                    "raw_value_exists": True,
                    "schema": {"key": "CRYPTO_SECURITY_PROVIDER", "data_type": "string"},
                }
            ],
        }

        response = self.client.get("/api/v1/crypto/settings")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["items"][0]["schema_info"], {"key": "CRYPTO_SECURITY_PROVIDER", "data_type": "string"})

    def test_update_crypto_settings_success(self) -> None:
        self.service.update.return_value = {
            "success": True,
            "config_version": "v3",
            "issues": [],
        }

        response = self.client.put(
            "/api/v1/crypto/settings",
            json={
                "config_version": "v2",
                "reload_now": True,
                "items": [
                    {"key": "CRYPTO_RISK_ENABLED", "value": "true"},
                    {"key": "CRYPTO_MIN_LIQUIDITY_USD", "value": "1500"},
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["config_version"], "v3")
        self.assertEqual(payload["updated_keys"], ["CRYPTO_RISK_ENABLED", "CRYPTO_MIN_LIQUIDITY_USD"])
        self.assertEqual(payload["issues"], [])
        self.service.update.assert_called_once_with(
            config_version="v2",
            items=[
                {"key": "CRYPTO_RISK_ENABLED", "value": "true"},
                {"key": "CRYPTO_MIN_LIQUIDITY_USD", "value": "1500"},
            ],
            reload_now=True,
        )

    def test_update_crypto_settings_rejects_non_crypto_key(self) -> None:
        response = self.client.put(
            "/api/v1/crypto/settings",
            json={
                "config_version": "v2",
                "items": [{"key": "APP_ENV", "value": "prod"}],
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["detail"]["error"], "validation_failed")
        self.assertIn("APP_ENV", payload["detail"]["message"])
        self.service.update.assert_not_called()

    def test_update_crypto_settings_handles_conflict(self) -> None:
        self.service.update.side_effect = ConfigConflictError(current_version="v9")

        response = self.client.put(
            "/api/v1/crypto/settings",
            json={
                "config_version": "v8",
                "items": [{"key": "CRYPTO_ENABLED", "value": "true"}],
            },
        )

        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["detail"]["error"], "config_version_conflict")
        self.assertEqual(payload["detail"]["current_config_version"], "v9")

    def test_update_crypto_settings_handles_validation_error(self) -> None:
        self.service.update.side_effect = ConfigValidationError(
            issues=[
                {
                    "key": "CRYPTO_RISK_MIN_LIQUIDITY_USD",
                    "code": "invalid_number",
                    "message": "Must be positive",
                    "severity": "error",
                }
            ]
        )

        response = self.client.put(
            "/api/v1/crypto/settings",
            json={
                "config_version": "v8",
                "items": [{"key": "CRYPTO_RISK_MIN_LIQUIDITY_USD", "value": "-1"}],
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["detail"]["error"], "validation_failed")
        self.assertEqual(payload["detail"]["issues"][0]["key"], "CRYPTO_RISK_MIN_LIQUIDITY_USD")


if __name__ == "__main__":
    unittest.main()
