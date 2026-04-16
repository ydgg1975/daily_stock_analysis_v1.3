# -*- coding: utf-8 -*-
"""Real PostgreSQL validation for the Phase A identity/preferences baseline."""

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
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from starlette.requests import Request

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.deps import resolve_current_user
from src.config import Config
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID, BOOTSTRAP_ADMIN_USERNAME, ROLE_ADMIN
from src.storage import AnalysisHistory, AppUser, AppUserSession, DatabaseManager

REAL_PG_DSN = str(os.getenv("POSTGRES_PHASE_A_REAL_DSN") or "").strip()


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


@unittest.skipUnless(REAL_PG_DSN, "POSTGRES_PHASE_A_REAL_DSN is required for real PostgreSQL validation")
class PostgresPhaseARealPgTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.pg_engine = create_engine(REAL_PG_DSN, echo=False, pool_pre_ping=True)
        self._drop_phase_a_tables()
        self._configure_environment(auth_enabled=True, enable_phase_a=True)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self._drop_phase_a_tables()
        self.pg_engine.dispose()
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
                    f"POSTGRES_PHASE_A_URL={REAL_PG_DSN}",
                    "POSTGRES_PHASE_A_APPLY_SCHEMA=true",
                ]
            )

        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        if enable_phase_a:
            os.environ["POSTGRES_PHASE_A_URL"] = REAL_PG_DSN
            os.environ["POSTGRES_PHASE_A_APPLY_SCHEMA"] = "true"
        else:
            os.environ.pop("POSTGRES_PHASE_A_URL", None)
            os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)

        Config.reset_instance()
        DatabaseManager.reset_instance()
        auth.refresh_auth_state()

    def _db(self) -> DatabaseManager:
        return DatabaseManager.get_instance()

    def _drop_phase_a_tables(self) -> None:
        with self.pg_engine.begin() as conn:
            conn.execute(text("drop table if exists notification_targets cascade"))
            conn.execute(text("drop table if exists user_preferences cascade"))
            conn.execute(text("drop table if exists guest_sessions cascade"))
            conn.execute(text("drop table if exists app_user_sessions cascade"))
            conn.execute(text("drop table if exists app_users cascade"))

    def _pg_scalar(self, sql: str, **params):
        with self.pg_engine.begin() as conn:
            return conn.execute(text(sql), params).scalar()

    def _pg_all(self, sql: str, **params):
        with self.pg_engine.begin() as conn:
            return conn.execute(text(sql), params).all()

    def test_real_postgres_bootstrap_auth_flow_and_docs_ddl_path(self) -> None:
        from api.app import create_app

        app = create_app(static_dir=self.data_dir / "empty-static")
        client = TestClient(app)
        try:
            db = self._db()
            self.assertTrue(db._phase_a_enabled)
            self.assertIsNotNone(db._phase_a_store)

            existing_tables = {
                row[0]
                for row in self._pg_all(
                    """
                    select table_name
                    from information_schema.tables
                    where table_schema = 'public'
                      and table_name in (
                        'app_users',
                        'app_user_sessions',
                        'guest_sessions',
                        'user_preferences',
                        'notification_targets'
                      )
                    """
                )
            }
            self.assertEqual(
                existing_tables,
                {
                    "app_users",
                    "app_user_sessions",
                    "guest_sessions",
                    "user_preferences",
                    "notification_targets",
                },
            )

            login_response = client.post(
                "/api/v1/auth/login",
                json={
                    "username": "pg-user",
                    "displayName": "PG User",
                    "createUser": True,
                    "password": "secret123",
                    "passwordConfirm": "secret123",
                },
            )
            self.assertEqual(login_response.status_code, 200)

            me_response = client.get("/api/v1/auth/me")
            self.assertEqual(me_response.status_code, 200)
            self.assertEqual(me_response.json()["username"], "pg-user")
            self.assertTrue(me_response.json()["isAuthenticated"])

            user_row = db.get_app_user_by_username("pg-user")
            self.assertIsNotNone(user_row)
            self.assertEqual(
                self._pg_scalar(
                    "select count(*) from app_users where username = :username",
                    username="pg-user",
                ),
                1,
            )
            self.assertEqual(
                self._pg_scalar("select count(*) from app_user_sessions"),
                1,
            )

            logout_response = client.post("/api/v1/auth/logout")
            self.assertEqual(logout_response.status_code, 204)
            self.assertEqual(
                self._pg_scalar(
                    """
                    select count(*)
                    from app_user_sessions
                    where user_id = :user_id
                      and revoked_at is not null
                    """,
                    user_id=str(user_row.id),
                ),
                1,
            )

            self.assertIsNone(auth.set_initial_password("passwd6"))
            secret = auth._get_session_secret()
            self.assertIsNotNone(secret)
            nonce = "legacyrealpg"
            issued_at = int(time.time())
            payload = f"{nonce}.{issued_at}"
            signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
            token = f"{nonce}.{issued_at}.{signature}"

            current_user = resolve_current_user(_make_request(cookies={auth.COOKIE_NAME: token}))
            self.assertIsNotNone(current_user)
            self.assertEqual(current_user.user_id, BOOTSTRAP_ADMIN_USER_ID)
            self.assertEqual(current_user.username, BOOTSTRAP_ADMIN_USERNAME)
            self.assertEqual(current_user.role, ROLE_ADMIN)
            self.assertTrue(current_user.legacy_admin)
        finally:
            client.close()

    def test_real_postgres_notification_preferences_and_guest_preview_non_persistence(self) -> None:
        from api.app import create_app

        app = create_app(static_dir=self.data_dir / "empty-static")
        client = TestClient(app)
        try:
            login_response = client.post(
                "/api/v1/auth/login",
                json={
                    "username": "notify-user",
                    "displayName": "Notify User",
                    "createUser": True,
                    "password": "secret123",
                    "passwordConfirm": "secret123",
                },
            )
            self.assertEqual(login_response.status_code, 200)

            update_response = client.put(
                "/api/v1/auth/preferences/notifications",
                json={
                    "enabled": True,
                    "email": "notify@example.com",
                    "discordEnabled": True,
                    "discordWebhook": "https://discord.com/api/webhooks/123/token",
                },
            )
            self.assertEqual(update_response.status_code, 200)
            self.assertTrue(update_response.json()["emailEnabled"])
            self.assertTrue(update_response.json()["discordEnabled"])

            self.assertEqual(
                self._pg_scalar(
                    """
                    select count(*)
                    from notification_targets
                    where channel_type in ('email', 'discord')
                    """
                ),
                2,
            )
            self.assertEqual(
                self._pg_scalar(
                    """
                    select count(*)
                    from notification_targets
                    where channel_type not in ('email', 'discord')
                    """
                ),
                0,
            )

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
                preview_response = client.post(
                    "/api/v1/analysis/preview",
                    json={"stock_code": "AAPL", "stock_name": "Apple"},
                )

            self.assertEqual(preview_response.status_code, 200)
            self.assertEqual(self._pg_scalar("select count(*) from guest_sessions"), 0)
            db = self._db()
            with db.get_session() as session:
                self.assertEqual(session.query(AnalysisHistory).count(), 0)
        finally:
            client.close()

    def test_real_postgres_lazy_backfill_and_factory_reset_mixed_storage(self) -> None:
        self._configure_environment(auth_enabled=True, enable_phase_a=False)
        legacy_db = self._db()
        user = legacy_db.create_or_update_app_user(
            user_id="legacy-user",
            username="legacy-user",
            display_name="Legacy User",
            role="user",
            password_hash="legacy-hash",
            is_active=True,
        )
        legacy_db.create_app_user_session(
            session_id="legacy-session",
            user_id=str(user.id),
            expires_at=datetime.now() + timedelta(hours=1),
        )
        legacy_db.upsert_user_notification_preferences(
            str(user.id),
            email="legacy@example.com",
            enabled=True,
            channel="email",
        )

        self._configure_environment(auth_enabled=True, enable_phase_a=True)
        db = self._db()

        self.assertIsNotNone(db.get_app_user("legacy-user"))
        self.assertIsNotNone(db.get_app_user_session("legacy-session"))
        preferences = db.get_user_notification_preferences("legacy-user")
        self.assertEqual(preferences["email"], "legacy@example.com")

        self.assertEqual(
            self._pg_scalar("select count(*) from app_users where id = :user_id", user_id="legacy-user"),
            1,
        )
        self.assertEqual(
            self._pg_scalar(
                "select count(*) from app_user_sessions where session_id = :session_id",
                session_id="legacy-session",
            ),
            1,
        )
        self.assertEqual(
            self._pg_scalar(
                """
                select count(*)
                from notification_targets
                where user_id = :user_id
                """,
                user_id="legacy-user",
            ),
            1,
        )

        reset_result = db.factory_reset_non_bootstrap_state()
        self.assertIn("app_users", reset_result["counts"])
        self.assertIsNone(db.get_app_user("legacy-user"))
        self.assertIsNone(db.get_app_user_session("legacy-session"))
        self.assertEqual(
            self._pg_scalar("select count(*) from app_users where id = :user_id", user_id="legacy-user"),
            0,
        )
        self.assertEqual(
            self._pg_scalar(
                "select count(*) from app_user_sessions where user_id = :user_id",
                user_id="legacy-user",
            ),
            0,
        )
        self.assertEqual(
            self._pg_scalar(
                "select count(*) from notification_targets where user_id = :user_id",
                user_id="legacy-user",
            ),
            0,
        )
        self.assertIsNotNone(db.get_app_user(BOOTSTRAP_ADMIN_USER_ID))

    def test_real_postgres_auth_disabled_bootstrap_admin_behavior(self) -> None:
        self._configure_environment(auth_enabled=False, enable_phase_a=True)
        current_user = resolve_current_user(_make_request())

        self.assertIsNotNone(current_user)
        self.assertEqual(current_user.user_id, BOOTSTRAP_ADMIN_USER_ID)
        self.assertTrue(current_user.is_admin)
        self.assertTrue(current_user.transitional)
        self.assertFalse(current_user.is_authenticated)
        self.assertFalse(current_user.auth_enabled)
        self.assertEqual(
            self._pg_scalar(
                "select count(*) from app_users where id = :user_id",
                user_id=BOOTSTRAP_ADMIN_USER_ID,
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
