# -*- coding: utf-8 -*-
"""Focused coverage for the PostgreSQL Phase A identity/preferences baseline."""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from starlette.requests import Request

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.deps import resolve_current_user
from src.config import Config
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID, BOOTSTRAP_ADMIN_USERNAME, ROLE_ADMIN
from src.postgres_phase_a import (
    PhaseAAppUser,
    PhaseAAppUserSession,
    PhaseAGuestSession,
    PhaseANotificationTarget,
)
from src.storage import AnalysisHistory, AppUser, AppUserSession, DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _make_request(*, cookies: dict[str, str] | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookies:
        cookie_header = "; ".join(f"{key}={value}" for key, value in cookies.items())
        headers.append((b"cookie", cookie_header.encode("utf-8")))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/auth/me",
        "raw_path": b"/api/v1/auth/me",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


class PostgresPhaseAStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.phase_a_db_path = self.data_dir / "phase_a.sqlite"
        self._configure_environment(auth_enabled=True, enable_phase_a=True)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self.temp_dir.cleanup()

    def _configure_environment(self, *, auth_enabled: bool, enable_phase_a: bool) -> None:
        lines = [
            "STOCK_LIST=600519",
            "GEMINI_API_KEY=test",
            f"ADMIN_AUTH_ENABLED={'true' if auth_enabled else 'false'}",
            f"DATABASE_PATH={self.sqlite_db_path}",
        ]
        if enable_phase_a:
            lines.extend(
                [
                    f"POSTGRES_PHASE_A_URL=sqlite:///{self.phase_a_db_path}",
                    "POSTGRES_PHASE_A_APPLY_SCHEMA=true",
                ]
            )

        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        if enable_phase_a:
            os.environ["POSTGRES_PHASE_A_URL"] = f"sqlite:///{self.phase_a_db_path}"
            os.environ["POSTGRES_PHASE_A_APPLY_SCHEMA"] = "true"
        else:
            os.environ.pop("POSTGRES_PHASE_A_URL", None)
            os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)

        Config.reset_instance()
        DatabaseManager.reset_instance()
        auth.refresh_auth_state()

    def _db(self) -> DatabaseManager:
        return DatabaseManager.get_instance()

    def test_phase_a_disabled_keeps_current_sqlite_auth_storage(self) -> None:
        self._configure_environment(auth_enabled=True, enable_phase_a=False)
        db = self._db()

        db.create_or_update_app_user(
            user_id="user-local",
            username="local-user",
            display_name="Local User",
            role="user",
            password_hash="hash",
            is_active=True,
        )
        db.create_app_user_session(
            session_id="session-local",
            user_id="user-local",
            expires_at=datetime.now() + timedelta(hours=1),
        )

        with db.get_session() as session:
            self.assertEqual(
                session.query(AppUser).filter(AppUser.id == "user-local").count(),
                1,
            )
            self.assertEqual(
                session.query(AppUserSession).filter(AppUserSession.session_id == "session-local").count(),
                1,
            )

    def test_phase_a_store_moves_new_users_sessions_and_notification_targets_off_legacy_sqlite(self) -> None:
        db = self._db()
        user = db.create_or_update_app_user(
            user_id="user-phase-a",
            username="phase-a-user",
            display_name="Phase A User",
            role="user",
            password_hash="hash",
            is_active=True,
        )
        session_row = db.create_app_user_session(
            session_id="session-phase-a",
            user_id=str(user.id),
            expires_at=datetime.now() + timedelta(hours=1),
        )
        preferences = db.upsert_user_notification_preferences(
            str(user.id),
            email="phasea@example.com",
            enabled=True,
            channel="multi",
            discord_webhook="https://discord.com/api/webhooks/123/token",
            discord_enabled=True,
        )

        self.assertEqual(str(user.id), "user-phase-a")
        self.assertEqual(str(session_row.user_id), "user-phase-a")
        self.assertTrue(preferences["email_enabled"])
        self.assertTrue(preferences["discord_enabled"])
        self.assertIsNotNone(db._phase_a_store)

        with db.get_session() as session:
            self.assertEqual(
                session.query(AppUser).filter(AppUser.id == "user-phase-a").count(),
                0,
            )
            self.assertEqual(
                session.query(AppUserSession).filter(AppUserSession.session_id == "session-phase-a").count(),
                0,
            )

        with db._phase_a_store.session_scope() as session:
            self.assertEqual(
                session.query(PhaseAAppUser).filter(PhaseAAppUser.id == "user-phase-a").count(),
                1,
            )
            self.assertEqual(
                session.query(PhaseAAppUserSession)
                .filter(PhaseAAppUserSession.session_id == "session-phase-a")
                .count(),
                1,
            )
            targets = (
                session.query(PhaseANotificationTarget)
                .filter(PhaseANotificationTarget.user_id == "user-phase-a")
                .order_by(PhaseANotificationTarget.channel_type.asc())
                .all()
            )
            self.assertEqual([target.channel_type for target in targets], ["discord", "email"])

    def test_phase_a_lazily_backfills_legacy_sqlite_phase_a_rows(self) -> None:
        self._configure_environment(auth_enabled=True, enable_phase_a=False)
        legacy_db = self._db()
        legacy_user = legacy_db.create_or_update_app_user(
            user_id="legacy-user",
            username="legacy-user",
            display_name="Legacy User",
            role="user",
            password_hash="legacy-hash",
            is_active=True,
        )
        legacy_db.create_app_user_session(
            session_id="legacy-session",
            user_id=str(legacy_user.id),
            expires_at=datetime.now() + timedelta(hours=1),
        )
        legacy_db.upsert_user_notification_preferences(
            str(legacy_user.id),
            email="legacy@example.com",
            enabled=True,
            channel="email",
        )

        self._configure_environment(auth_enabled=True, enable_phase_a=True)
        db = self._db()

        user = db.get_app_user("legacy-user")
        session_row = db.get_app_user_session("legacy-session")
        preferences = db.get_user_notification_preferences("legacy-user")

        self.assertIsNotNone(user)
        self.assertIsNotNone(session_row)
        self.assertEqual(preferences["email"], "legacy@example.com")
        self.assertTrue(preferences["email_enabled"])

        with db._phase_a_store.session_scope() as session:
            self.assertEqual(
                session.query(PhaseAAppUser).filter(PhaseAAppUser.id == "legacy-user").count(),
                1,
            )
            self.assertEqual(
                session.query(PhaseAAppUserSession)
                .filter(PhaseAAppUserSession.session_id == "legacy-session")
                .count(),
                1,
            )
            self.assertEqual(
                session.query(PhaseANotificationTarget)
                .filter(PhaseANotificationTarget.user_id == "legacy-user")
                .count(),
                1,
            )

    def test_auth_disabled_bootstrap_admin_and_legacy_cookie_compatibility_survive_phase_a_enablement(self) -> None:
        self._configure_environment(auth_enabled=False, enable_phase_a=True)
        current_user = resolve_current_user(_make_request())

        self.assertIsNotNone(current_user)
        self.assertEqual(current_user.user_id, BOOTSTRAP_ADMIN_USER_ID)
        self.assertTrue(current_user.is_admin)
        self.assertTrue(current_user.transitional)
        self.assertFalse(current_user.is_authenticated)
        self.assertFalse(current_user.auth_enabled)

        self._configure_environment(auth_enabled=True, enable_phase_a=True)
        self.assertIsNone(auth.set_initial_password("passwd6"))
        secret = auth._get_session_secret()
        self.assertIsNotNone(secret)

        nonce = "legacynonce"
        issued_at = int(time.time())
        payload = f"{nonce}.{issued_at}"
        signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        token = f"{nonce}.{issued_at}.{signature}"

        legacy_user = resolve_current_user(_make_request(cookies={auth.COOKIE_NAME: token}))
        self.assertIsNotNone(legacy_user)
        self.assertEqual(legacy_user.user_id, BOOTSTRAP_ADMIN_USER_ID)
        self.assertEqual(legacy_user.username, BOOTSTRAP_ADMIN_USERNAME)
        self.assertEqual(legacy_user.role, ROLE_ADMIN)
        self.assertTrue(legacy_user.is_authenticated)
        self.assertTrue(legacy_user.legacy_admin)

    def test_guest_preview_keeps_guest_sessions_non_persistent_under_phase_a(self) -> None:
        from api.app import create_app

        app = create_app(static_dir=self.data_dir / "empty-static")
        client = TestClient(app)
        try:
            with patch(
                "src.services.analysis_service.AnalysisService.analyze_stock",
                return_value={
                    "query_id": "guest:test-session:20260416090000000000",
                    "stock_code": "AAPL",
                    "stock_name": "Apple",
                    "report": {
                        "meta": {
                            "query_id": "guest:test-session:20260416090000000000",
                            "stock_code": "AAPL",
                            "stock_name": "Apple",
                            "report_type": "brief",
                            "report_language": "en",
                            "created_at": "2026-04-16T09:00:00+00:00",
                            "current_price": 188.2,
                            "change_pct": 1.8,
                            "model_used": "openai/gpt-5.4",
                        },
                        "summary": {
                            "analysis_summary": "Preview summary",
                            "operation_advice": "Wait",
                            "trend_prediction": "Bullish bias",
                            "sentiment_score": 74,
                            "sentiment_label": "Bullish",
                        },
                        "strategy": {
                            "ideal_buy": "184-186",
                            "stop_loss": "179",
                            "take_profit": "195-198",
                        },
                        "details": {
                            "standard_report": {"should_not": "leak"},
                        },
                    },
                },
            ):
                response = client.post(
                    "/api/v1/analysis/preview",
                    json={"stock_code": "AAPL", "stock_name": "Apple"},
                )

            self.assertEqual(response.status_code, 200)
            db = self._db()
            with db.get_session() as session:
                self.assertEqual(session.query(AnalysisHistory).count(), 0)
            with db._phase_a_store.session_scope() as session:
                self.assertEqual(session.query(PhaseAGuestSession).count(), 0)
        finally:
            client.close()

    def test_phase_a_enabled_auth_api_and_notification_preferences_round_trip(self) -> None:
        from api.app import create_app

        app = create_app(static_dir=self.data_dir / "empty-static")
        client = TestClient(app)
        try:
            login_response = client.post(
                "/api/v1/auth/login",
                json={
                    "username": "api-user",
                    "displayName": "API User",
                    "createUser": True,
                    "password": "secret123",
                    "passwordConfirm": "secret123",
                },
            )
            self.assertEqual(login_response.status_code, 200)

            me_response = client.get("/api/v1/auth/me")
            self.assertEqual(me_response.status_code, 200)
            self.assertEqual(me_response.json()["username"], "api-user")
            self.assertTrue(me_response.json()["isAuthenticated"])

            update_response = client.put(
                "/api/v1/auth/preferences/notifications",
                json={
                    "enabled": True,
                    "email": "api-user@example.com",
                    "discordEnabled": True,
                    "discordWebhook": "https://discord.com/api/webhooks/123/token",
                },
            )
            self.assertEqual(update_response.status_code, 200)
            self.assertTrue(update_response.json()["emailEnabled"])
            self.assertTrue(update_response.json()["discordEnabled"])

            db = self._db()
            user_row = db.get_app_user_by_username("api-user")
            self.assertIsNotNone(user_row)
            with db.get_session() as session:
                self.assertEqual(
                    session.query(AppUser).filter(AppUser.username == "api-user").count(),
                    0,
                )
            with db._phase_a_store.session_scope() as session:
                self.assertEqual(
                    session.query(PhaseAAppUser).filter(PhaseAAppUser.username == "api-user").count(),
                    1,
                )
                self.assertEqual(
                    session.query(PhaseANotificationTarget)
                    .filter(PhaseANotificationTarget.user_id == str(user_row.id))
                    .count(),
                    2,
                )
        finally:
            client.close()

    def test_factory_reset_clears_phase_a_identity_rows_and_sqlite_user_owned_history(self) -> None:
        db = self._db()
        db.create_or_update_app_user(
            user_id="user-reset",
            username="reset-user",
            display_name="Reset User",
            role="user",
            password_hash="hash",
            is_active=True,
        )
        db.create_app_user_session(
            session_id="session-reset",
            user_id="user-reset",
            expires_at=datetime.now() + timedelta(hours=1),
        )
        db.upsert_user_notification_preferences(
            "user-reset",
            email="reset@example.com",
            enabled=True,
            channel="email",
        )
        db.save_analysis_history(
            SimpleNamespace(
                code="AAPL",
                name="Apple",
                sentiment_score=66,
                operation_advice="buy",
                trend_prediction="up",
                analysis_summary="summary",
                raw_result={"summary": "summary"},
                ideal_buy=None,
                secondary_buy=None,
                stop_loss=10.0,
                take_profit=12.0,
            ),
            query_id="query-reset",
            report_type="daily",
            news_content="news",
            owner_id="user-reset",
        )
        db.save_conversation_message("chat-reset", "user", "hello", owner_id="user-reset")

        result = db.factory_reset_non_bootstrap_state()

        self.assertIn("app_users", result["counts"])
        self.assertIsNone(db.get_app_user("user-reset"))
        self.assertIsNone(db.get_app_user_session("session-reset"))
        with db.get_session() as session:
            self.assertEqual(session.query(AnalysisHistory).count(), 0)
        with db._phase_a_store.session_scope() as session:
            self.assertEqual(
                session.query(PhaseAAppUser).filter(PhaseAAppUser.id == "user-reset").count(),
                0,
            )
            self.assertEqual(
                session.query(PhaseAAppUserSession)
                .filter(PhaseAAppUserSession.session_id == "session-reset")
                .count(),
                0,
            )
            self.assertEqual(
                session.query(PhaseANotificationTarget)
                .filter(PhaseANotificationTarget.user_id == "user-reset")
                .count(),
                0,
            )


if __name__ == "__main__":
    unittest.main()
