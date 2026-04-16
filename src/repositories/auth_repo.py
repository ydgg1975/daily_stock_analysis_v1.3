# -*- coding: utf-8 -*-
"""Repository helpers for auth-facing app user, session, and preferences data."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from src.storage import DatabaseManager


class AuthRepository:
    """Narrow persistence seam for auth endpoint data access."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def get_user_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        return self.db.get_user_notification_preferences(user_id)

    def upsert_user_notification_preferences(
        self,
        user_id: str,
        *,
        email: str | None,
        enabled: bool,
        channel: str,
        discord_webhook: str | None,
        discord_enabled: bool,
    ) -> Dict[str, Any]:
        return self.db.upsert_user_notification_preferences(
            user_id,
            email=email,
            enabled=enabled,
            channel=channel,
            discord_webhook=discord_webhook,
            discord_enabled=discord_enabled,
        )

    def create_app_user_session(
        self,
        *,
        session_id: str,
        user_id: str,
        expires_at: datetime,
    ):
        return self.db.create_app_user_session(
            session_id=session_id,
            user_id=user_id,
            expires_at=expires_at,
        )

    def ensure_bootstrap_admin_user(self):
        return self.db.ensure_bootstrap_admin_user()

    def get_app_user(self, user_id: str):
        return self.db.get_app_user(user_id)

    def get_app_user_by_username(self, username: str):
        return self.db.get_app_user_by_username(username)

    def create_or_update_app_user(
        self,
        *,
        user_id: str,
        username: str,
        display_name: str,
        role: str,
        password_hash: str | None,
        is_active: bool,
    ):
        return self.db.create_or_update_app_user(
            user_id=user_id,
            username=username,
            display_name=display_name,
            role=role,
            password_hash=password_hash,
            is_active=is_active,
        )

    def revoke_app_user_session(self, session_id: str) -> bool:
        return self.db.revoke_app_user_session(session_id)

    def revoke_all_app_user_sessions(self, user_id: str) -> int:
        return self.db.revoke_all_app_user_sessions(user_id)
