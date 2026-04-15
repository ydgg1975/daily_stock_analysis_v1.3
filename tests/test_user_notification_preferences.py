# -*- coding: utf-8 -*-
"""User notification preference foundation coverage."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.core.pipeline import StockAnalysisPipeline
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.notification import NotificationChannel, NotificationService
from src.services.task_queue import _build_configured_execution_summary
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class UserNotificationPreferencesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "user_notification_preferences.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=true",
                    "EMAIL_SENDER=sender@example.com",
                    "EMAIL_PASSWORD=test-password",
                    "EMAIL_RECEIVERS=ops@example.com",
                    "DISCORD_WEBHOOK_URL=https://example.com/discord-webhook",
                    f"DATABASE_PATH={self.db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()

        self.app = create_app(static_dir=self.data_dir / "empty-static")
        self.user_client = TestClient(self.app)
        self.other_user_client = TestClient(self.app)
        self.db = DatabaseManager.get_instance()

        self.user_id = self._login_user(self.user_client, "alice", "Alice")
        self.other_user_id = self._login_user(self.other_user_client, "bob", "Bob")

    def tearDown(self) -> None:
        self.user_client.close()
        self.other_user_client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _login_user(self, client: TestClient, username: str, display_name: str) -> str:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": username,
                "displayName": display_name,
                "createUser": True,
                "password": "secret123",
                "passwordConfirm": "secret123",
            },
        )
        self.assertEqual(response.status_code, 200)
        user_row = self.db.get_app_user_by_username(username)
        self.assertIsNotNone(user_row)
        return str(user_row.id)

    def test_notification_preferences_are_user_owned_and_exposed_via_current_user_api(self) -> None:
        initial_response = self.user_client.get("/api/v1/auth/preferences/notifications")
        self.assertEqual(initial_response.status_code, 200)
        self.assertEqual(
            initial_response.json(),
            {
                "channel": "email",
                "enabled": False,
                "email": None,
                "emailEnabled": False,
                "discordEnabled": False,
                "discordWebhook": None,
                "deliveryAvailable": True,
                "emailDeliveryAvailable": True,
                "discordDeliveryAvailable": True,
                "updatedAt": None,
            },
        )

        update_response = self.user_client.put(
            "/api/v1/auth/preferences/notifications",
            json={"enabled": True, "email": "alice@example.com"},
        )
        self.assertEqual(update_response.status_code, 200)
        payload = update_response.json()
        self.assertEqual(payload["channel"], "email")
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["email"], "alice@example.com")
        self.assertTrue(payload["emailEnabled"])
        self.assertFalse(payload["discordEnabled"])
        self.assertIsNone(payload["discordWebhook"])
        self.assertTrue(payload["deliveryAvailable"])
        self.assertIsNotNone(payload["updatedAt"])

        other_response = self.other_user_client.get("/api/v1/auth/preferences/notifications")
        self.assertEqual(other_response.status_code, 200)
        self.assertFalse(other_response.json()["enabled"])
        self.assertIsNone(other_response.json()["email"])

    def test_notification_preferences_validation_and_runtime_scope_stay_separate_from_system_channels(self) -> None:
        invalid_response = self.user_client.put(
            "/api/v1/auth/preferences/notifications",
            json={"enabled": True, "email": ""},
        )
        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.json()["error"], "validation_error")

        invalid_discord_response = self.user_client.put(
            "/api/v1/auth/preferences/notifications",
            json={"discordEnabled": True, "discordWebhook": "https://example.com/not-discord"},
        )
        self.assertEqual(invalid_discord_response.status_code, 400)
        self.assertEqual(invalid_discord_response.json()["error"], "validation_error")

        self.db.upsert_user_notification_preferences(
            self.user_id,
            email="alice@example.com",
            enabled=True,
            channel="multi",
            discord_webhook="https://discord.com/api/webhooks/123/token",
            discord_enabled=True,
        )

        user_summary = _build_configured_execution_summary(self.user_id)
        system_summary = _build_configured_execution_summary()

        self.assertEqual(user_summary["notification"]["channels"], ["email", "discord"])
        self.assertEqual(system_summary["notification"]["channels"], ["discord", "email"])

        user_notifier = NotificationService(
            channel_allowlist=[NotificationChannel.EMAIL, NotificationChannel.DISCORD],
            email_receivers_override=["alice@example.com"],
            discord_webhook_url_override="https://discord.com/api/webhooks/123/token",
        )
        self.assertEqual(
            user_notifier.get_available_channels(),
            [NotificationChannel.EMAIL, NotificationChannel.DISCORD],
        )
        self.assertEqual(
            user_notifier._discord_config["webhook_url"],
            "https://discord.com/api/webhooks/123/token",
        )

        system_notifier = NotificationService()
        self.assertIn(NotificationChannel.DISCORD, system_notifier.get_available_channels())
        self.assertIn(NotificationChannel.EMAIL, system_notifier.get_available_channels())

        user_pipeline = StockAnalysisPipeline(owner_id=self.user_id)
        self.assertEqual(
            user_pipeline.notifier.get_available_channels(),
            [NotificationChannel.EMAIL, NotificationChannel.DISCORD],
        )
        self.assertEqual(
            user_pipeline.notifier._discord_config["webhook_url"],
            "https://discord.com/api/webhooks/123/token",
        )

        admin_pipeline = StockAnalysisPipeline(owner_id=BOOTSTRAP_ADMIN_USER_ID)
        self.assertIn(NotificationChannel.DISCORD, admin_pipeline.notifier.get_available_channels())


if __name__ == "__main__":
    unittest.main()
