# -*- coding: utf-8 -*-
"""Authentication endpoints for Web admin login."""

from __future__ import annotations

import logging
import os
import secrets
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from api.deps import get_system_config_service, resolve_current_user
from src.auth import (
    ADMIN_UNLOCK_MAX_AGE_MINUTES_DEFAULT,
    COOKIE_NAME,
    SESSION_MAX_AGE_HOURS_DEFAULT,
    change_password,
    check_rate_limit,
    clear_rate_limit,
    create_admin_unlock_token,
    create_session,
    get_client_ip,
    get_session_expiry_datetime,
    has_stored_password,
    hash_password_for_storage,
    is_auth_enabled,
    is_password_changeable,
    is_password_set,
    record_login_failure,
    refresh_auth_state,
    rotate_session_secret,
    set_initial_password,
    get_session_identity,
    verify_password_hash_string,
    verify_stored_password,
    ensure_bootstrap_admin_user_password_hash,
)
from src.config import Config, setup_env
from src.core.config_manager import ConfigManager
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID, BOOTSTRAP_ADMIN_USERNAME, ROLE_ADMIN, ROLE_USER
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    """Login or account-bootstrap request body."""

    model_config = {"populate_by_name": True}

    username: str = Field(default="", description="Username")
    display_name: str | None = Field(default=None, alias="displayName", description="Display name for first account creation")
    create_user: bool = Field(default=False, alias="createUser", description="Whether to create a new normal user account")
    password: str = Field(default="", description="Password")
    password_confirm: str | None = Field(default=None, alias="passwordConfirm", description="Confirm (first-time)")


class ChangePasswordRequest(BaseModel):
    """Change password request body."""

    model_config = {"populate_by_name": True}

    current_password: str = Field(default="", alias="currentPassword")
    new_password: str = Field(default="", alias="newPassword")
    new_password_confirm: str = Field(default="", alias="newPasswordConfirm")


class AuthSettingsRequest(BaseModel):
    """Update auth enablement and initial password settings."""

    model_config = {"populate_by_name": True}

    auth_enabled: bool = Field(alias="authEnabled")
    password: str = Field(default="")
    password_confirm: str | None = Field(default=None, alias="passwordConfirm")
    current_password: str = Field(default="", alias="currentPassword")


class VerifyPasswordRequest(BaseModel):
    """Password verification request for unlocking admin settings."""

    model_config = {"populate_by_name": True}

    password: str = Field(default="", description="Admin password")
    password_confirm: str | None = Field(default=None, alias="passwordConfirm", description="Confirm password when setting initial secret")


class CurrentUserResponse(BaseModel):
    id: str
    username: str
    display_name: str | None = Field(default=None, alias="displayName")
    role: str
    is_admin: bool = Field(alias="isAdmin")
    is_authenticated: bool = Field(alias="isAuthenticated")
    transitional: bool = False
    auth_enabled: bool = Field(alias="authEnabled")
    legacy_admin: bool = Field(default=False, alias="legacyAdmin")


class UserNotificationPreferencesRequest(BaseModel):
    """Update current-user notification preferences."""

    model_config = {"populate_by_name": True}

    enabled: bool = Field(default=False)
    email: str | None = Field(default=None)
    email_enabled: bool | None = Field(default=None, alias="emailEnabled")
    discord_enabled: bool = Field(default=False, alias="discordEnabled")
    discord_webhook: str | None = Field(default=None, alias="discordWebhook")


class UserNotificationPreferencesResponse(BaseModel):
    """Current-user notification preferences."""

    channel: str = Field(default="email")
    enabled: bool = Field(default=False)
    email: str | None = Field(default=None)
    email_enabled: bool = Field(default=False, alias="emailEnabled")
    discord_enabled: bool = Field(default=False, alias="discordEnabled")
    discord_webhook: str | None = Field(default=None, alias="discordWebhook")
    delivery_available: bool = Field(default=False, alias="deliveryAvailable")
    email_delivery_available: bool = Field(default=False, alias="emailDeliveryAvailable")
    discord_delivery_available: bool = Field(default=True, alias="discordDeliveryAvailable")
    updated_at: str | None = Field(default=None, alias="updatedAt")


def _cookie_params(request: Request) -> dict:
    """Build cookie params including Secure based on request."""
    secure = False
    if os.getenv("TRUST_X_FORWARDED_FOR", "false").lower() == "true":
        proto = request.headers.get("X-Forwarded-Proto", "").lower()
        secure = proto == "https"
    else:
        # Check URL scheme when not behind proxy
        secure = request.url.scheme == "https"

    try:
        max_age_hours = int(os.getenv("ADMIN_SESSION_MAX_AGE_HOURS", str(SESSION_MAX_AGE_HOURS_DEFAULT)))
    except ValueError:
        max_age_hours = SESSION_MAX_AGE_HOURS_DEFAULT
    max_age = max_age_hours * 3600

    return {
        "httponly": True,
        "samesite": "lax",
        "secure": secure,
        "path": "/",
        "max_age": max_age,
    }


def _apply_auth_enabled(enabled: bool, request: Request | None = None) -> bool:
    """Persist auth toggle to .env and reload runtime config."""
    manager_applied = False
    if request is not None:
        try:
            service = get_system_config_service(request)
            service.apply_simple_updates(
                updates=[("ADMIN_AUTH_ENABLED", "true" if enabled else "false")],
                mask_token="******",
            )
            manager_applied = True
        except Exception as exc:
            logger.warning(
                "Failed to apply auth toggle via shared SystemConfigService, falling back: %s",
                exc,
                exc_info=True,
            )
            manager_applied = False

    if not manager_applied:
        try:
            manager = ConfigManager()
            manager.apply_updates(
                updates=[("ADMIN_AUTH_ENABLED", "true" if enabled else "false")],
                sensitive_keys=set(),
                mask_token="******",
            )
            manager_applied = True
        except Exception as exc:
            logger.error("Failed to apply auth toggle via ConfigManager: %s", exc, exc_info=True)
            manager_applied = False

    if not manager_applied:
        return False

    Config.reset_instance()
    setup_env(override=True)
    refresh_auth_state()
    return True


def _password_set_for_response(auth_enabled: bool) -> bool:
    """Avoid exposing stored-password state when auth is disabled."""
    return is_password_set() if auth_enabled else False


def _set_session_cookie(response: Response, session_value: str, request: Request) -> None:
    """Attach the admin session cookie to a response."""
    params = _cookie_params(request)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_value,
        httponly=params["httponly"],
        samesite=params["samesite"],
        secure=params["secure"],
        path=params["path"],
        max_age=params["max_age"],
    )


def _normalize_username(value: str | None) -> str:
    return str(value or "").strip()


def _serialize_current_user(request: Request) -> dict | None:
    current_user = resolve_current_user(request)
    if current_user is None:
        return None
    return CurrentUserResponse(
        id=current_user.user_id,
        username=current_user.username,
        displayName=current_user.display_name,
        role=current_user.role,
        isAdmin=current_user.is_admin,
        isAuthenticated=current_user.is_authenticated,
        transitional=current_user.transitional,
        authEnabled=current_user.auth_enabled,
        legacyAdmin=current_user.legacy_admin,
    ).model_dump(by_alias=True)


def _clear_current_user_cache(request: Request) -> None:
    state = getattr(request, "state", None)
    if state is not None and hasattr(state, "current_user"):
        delattr(state, "current_user")


def _normalize_notification_email(value: str | None) -> str | None:
    email = str(value or "").strip()
    if not email:
        return None
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("请输入有效的邮箱地址")
    return email


def _normalize_discord_webhook(value: str | None) -> str | None:
    webhook = str(value or "").strip()
    if not webhook:
        return None

    parsed = urlparse(webhook)
    host = str(parsed.netloc or "").lower()
    path = str(parsed.path or "")
    if (
        parsed.scheme != "https"
        or not host
        or "/api/webhooks/" not in path
        or not (host.endswith("discord.com") or host.endswith("discordapp.com"))
    ):
        raise ValueError("请输入有效的 Discord Webhook URL")
    return webhook


def _notification_delivery_available() -> bool:
    config = Config.get_instance()
    return bool(getattr(config, "email_sender", None) and getattr(config, "email_password", None))


def _serialize_user_notification_preferences(user_id: str) -> dict:
    db = DatabaseManager.get_instance()
    preferences = db.get_user_notification_preferences(user_id)
    email_delivery_available = _notification_delivery_available()
    return UserNotificationPreferencesResponse(
        channel=str(preferences.get("channel") or "email"),
        enabled=bool(preferences.get("enabled")),
        email=preferences.get("email"),
        emailEnabled=bool(preferences.get("email_enabled")),
        discordEnabled=bool(preferences.get("discord_enabled")),
        discordWebhook=preferences.get("discord_webhook"),
        deliveryAvailable=email_delivery_available,
        emailDeliveryAvailable=email_delivery_available,
        discordDeliveryAvailable=True,
        updatedAt=preferences.get("updated_at"),
    ).model_dump(by_alias=True)


def _require_admin_current_user(request: Request):
    current_user = resolve_current_user(request)
    if current_user is None:
        return None, JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Login required"},
        )
    if not current_user.is_admin:
        return None, JSONResponse(
            status_code=403,
            content={"error": "admin_required", "message": "Admin access required"},
        )
    return current_user, None


def _persist_session_for_user(*, request: Request, user_id: str, username: str, role: str) -> str:
    session_id = secrets.token_hex(16)
    expires_at = get_session_expiry_datetime()
    db = DatabaseManager.get_instance()
    db.create_app_user_session(
        session_id=session_id,
        user_id=user_id,
        expires_at=expires_at,
    )
    return create_session(
        user_id=user_id,
        username=username,
        role=role,
        session_id=session_id,
        expires_at=int(expires_at.timestamp()),
    )


def _delete_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


def _get_auth_status_dict(request: Request | None = None) -> dict:
    """Helper to build consistent auth status response body."""
    auth_enabled = is_auth_enabled()
    current_user_payload = _serialize_current_user(request) if request is not None else None
    logged_in = bool(current_user_payload and current_user_payload.get("isAuthenticated"))

    # setupState determination:
    # - enabled: auth is active
    # - password_retained: auth disabled but password exists
    # - no_password: auth disabled and no password exists
    if auth_enabled:
        setup_state = "enabled"
    elif has_stored_password():
        setup_state = "password_retained"
    else:
        setup_state = "no_password"

    return {
        "authEnabled": auth_enabled,
        "loggedIn": logged_in,
        "passwordSet": _password_set_for_response(auth_enabled),
        "passwordChangeable": is_password_changeable() if auth_enabled else False,
        "setupState": setup_state,
        "currentUser": current_user_payload,
    }


@router.get(
    "/status",
    summary="Get auth status",
    description="Returns whether auth is enabled and if the current request is logged in.",
)
async def auth_status(request: Request):
    """Return authEnabled, loggedIn, passwordSet, passwordChangeable, setupState without requiring auth."""
    return _get_auth_status_dict(request)


@router.get(
    "/me",
    summary="Get current user",
    description="Returns the resolved current user identity for the request.",
)
async def auth_me(request: Request):
    current_user = _serialize_current_user(request)
    if current_user is None:
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Login required"},
        )
    return current_user


@router.get(
    "/preferences/notifications",
    summary="Get current-user notification preferences",
    description="Returns the personal notification target configuration for the authenticated user.",
)
async def auth_get_notification_preferences(request: Request):
    current_user = resolve_current_user(request)
    if current_user is None or not current_user.is_authenticated:
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Login required"},
        )
    return _serialize_user_notification_preferences(current_user.user_id)


@router.put(
    "/preferences/notifications",
    summary="Update current-user notification preferences",
    description="Updates the personal notification target configuration for the authenticated user.",
)
async def auth_update_notification_preferences(request: Request, body: UserNotificationPreferencesRequest):
    current_user = resolve_current_user(request)
    if current_user is None or not current_user.is_authenticated:
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Login required"},
        )

    try:
        normalized_email = _normalize_notification_email(body.email)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": "validation_error", "message": str(exc)},
        )
    try:
        normalized_discord_webhook = _normalize_discord_webhook(body.discord_webhook)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": "validation_error", "message": str(exc)},
        )

    email_enabled = body.email_enabled if body.email_enabled is not None else body.enabled

    if email_enabled and not normalized_email:
        return JSONResponse(
            status_code=400,
            content={"error": "validation_error", "message": "启用邮件通知前请先填写邮箱地址"},
        )
    if body.discord_enabled and not normalized_discord_webhook:
        return JSONResponse(
            status_code=400,
            content={"error": "validation_error", "message": "启用 Discord 通知前请先填写 Webhook URL"},
        )

    DatabaseManager.get_instance().upsert_user_notification_preferences(
        current_user.user_id,
        email=normalized_email,
        enabled=email_enabled,
        channel="multi" if email_enabled and body.discord_enabled else ("discord" if body.discord_enabled else "email"),
        discord_webhook=normalized_discord_webhook,
        discord_enabled=body.discord_enabled,
    )
    return _serialize_user_notification_preferences(current_user.user_id)


@router.post(
    "/verify-password",
    summary="Verify admin password for settings unlock",
    description=(
        "Verifies the admin password and returns a short-lived unlock token for admin-only "
        "settings edits. If no stored password exists yet, accepts password + passwordConfirm "
        "to bootstrap the initial admin password."
    ),
)
async def auth_verify_password(request: Request, body: VerifyPasswordRequest):
    """Verify or initialize admin password and return a short-lived unlock token."""
    current_user, error_response = _require_admin_current_user(request)
    if error_response is not None:
        return error_response

    password = (body.password or "").strip()
    if not password:
        return JSONResponse(
            status_code=400,
            content={"error": "password_required", "message": "请输入管理员密码"},
        )

    ip = get_client_ip(request)
    if not check_rate_limit(ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "message": "Too many failed attempts. Please try again later.",
            },
        )

    bootstrap_admin = current_user.user_id == BOOTSTRAP_ADMIN_USER_ID

    if bootstrap_admin and not has_stored_password():
        confirm = (body.password_confirm or "").strip()
        if not confirm:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "password_confirm_required",
                    "message": "当前尚未设置管理员密码，请输入并确认初始密码。",
                },
            )
        if password != confirm:
            record_login_failure(ip)
            return JSONResponse(
                status_code=400,
                content={"error": "password_mismatch", "message": "两次输入的密码不一致"},
            )
        err = set_initial_password(password)
        if err:
            record_login_failure(ip)
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_password", "message": err},
            )
    else:
        verified = False
        if bootstrap_admin:
            ensure_bootstrap_admin_user_password_hash()
            verified = verify_stored_password(password)
        else:
            user_row = DatabaseManager.get_instance().get_app_user(current_user.user_id)
            verified = bool(user_row and verify_password_hash_string(password, getattr(user_row, "password_hash", None)))
        if not verified:
            record_login_failure(ip)
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_password", "message": "管理员密码错误"},
            )

    clear_rate_limit(ip)
    unlock_token = create_admin_unlock_token(
        user_id=current_user.user_id,
        username=current_user.username,
        role=current_user.role,
    )
    if not unlock_token:
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Failed to create admin unlock token"},
        )

    try:
        ttl_minutes = int(os.getenv("ADMIN_UNLOCK_MAX_AGE_MINUTES", str(ADMIN_UNLOCK_MAX_AGE_MINUTES_DEFAULT)))
    except ValueError:
        ttl_minutes = ADMIN_UNLOCK_MAX_AGE_MINUTES_DEFAULT
    expires_in_seconds = max(60, ttl_minutes * 60)

    return {
        "ok": True,
        "unlockToken": unlock_token,
        "expiresInSeconds": expires_in_seconds,
    }


@router.post(
    "/settings",
    summary="Update auth settings",
    description=(
        "Enable or disable password login. When enabling without an existing password, "
        "password + passwordConfirm are required. When re-enabling with a stored password, "
        "currentPassword is required."
    ),
)
async def auth_update_settings(request: Request, body: AuthSettingsRequest):
    """Manage auth enablement from the settings page."""
    current_user, error_response = _require_admin_current_user(request)
    if error_response is not None:
        return error_response

    target_enabled = body.auth_enabled
    current_enabled = is_auth_enabled()
    stored_password_exists = has_stored_password()

    password = (body.password or "").strip()
    confirm = (body.password_confirm or "").strip()
    current_password = (body.current_password or "").strip()

    if target_enabled:
        if password or confirm:
            if stored_password_exists:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "password_already_set",
                        "message": "已存在管理员密码，请启用认证后通过修改密码功能更新",
                    },
                )
            if not password:
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_required", "message": "请输入要设置的管理员密码"},
                )
            if password != confirm:
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_mismatch", "message": "两次输入的密码不一致"},
                )
            if has_stored_password():
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "password_already_set",
                        "message": "已存在管理员密码，请启用认证后通过修改密码功能更新",
                    },
                )
            err = set_initial_password(password)
            if err:
                return JSONResponse(
                    status_code=400,
                    content={"error": "invalid_password", "message": err},
                )
        elif not stored_password_exists:
            return JSONResponse(
                status_code=400,
                content={"error": "password_required", "message": "开启密码登录前请先设置密码"},
            )
        else:
            # P1 Vulnerability Fix: Enforce current-password check independent of global cached flag
            # We must verify they actually possess a valid admin session, otherwise an attacker
            # could hit a race condition when auth becomes enabled mid-flight.
            # This triggers whenever trying to enable/keep enabled an existing auth setup.
            cookie_val = request.cookies.get(COOKIE_NAME)
            # if target_enabled is True here, they are requesting to enable or keep auth enabled
            is_valid_session = cookie_val and get_session_identity(cookie_val) is not None
            
            if not is_valid_session:
                if not current_password:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "current_required", "message": "重新开启认证前请输入当前密码"},
                    )
                ip = get_client_ip(request)
                if not check_rate_limit(ip):
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "rate_limited",
                            "message": "Too many failed attempts. Please try again later.",
                        },
                    )
                if not verify_stored_password(current_password):
                    record_login_failure(ip)
                    return JSONResponse(
                        status_code=401,
                        content={"error": "invalid_password", "message": "当前密码错误"},
                    )
                clear_rate_limit(ip)
    else:
        if current_enabled:
            cookie_val = request.cookies.get(COOKIE_NAME)
            is_valid_session = cookie_val and get_session_identity(cookie_val) is not None

            if not is_valid_session:
                if not current_password:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "current_required", "message": "关闭认证前请输入当前密码"},
                    )
                ip = get_client_ip(request)
                if not check_rate_limit(ip):
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "rate_limited",
                            "message": "Too many failed attempts. Please try again later.",
                        },
                    )
                if not verify_stored_password(current_password):
                    record_login_failure(ip)
                    return JSONResponse(
                        status_code=401,
                        content={"error": "invalid_password", "message": "当前密码错误"},
                    )
                clear_rate_limit(ip)

    if target_enabled != current_enabled:
        if not _apply_auth_enabled(target_enabled, request=request):
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to update auth settings"},
            )
        if not rotate_session_secret():
            rollback_ok = _apply_auth_enabled(current_enabled, request=request)
            if not rollback_ok:
                logger.error("Failed to roll back auth state after session secret rotation failure")
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to rotate session secret"},
            )
    else:
        if not _apply_auth_enabled(target_enabled, request=request):
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to update auth settings"},
            )

    if target_enabled:
        session_val = _persist_session_for_user(
            request=request,
            user_id=current_user.user_id,
            username=current_user.username,
            role=current_user.role,
        )
        if not session_val:
            rollback_ok = _apply_auth_enabled(current_enabled, request=request)
            if not rollback_ok:
                logger.error("Failed to roll back auth state after session creation failure")
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to create session"},
            )
        _clear_current_user_cache(request)
        # We manually set loggedIn=True because the cookie is being set in this response
        # and won't be visible in request.cookies until the NEXT request.
        content = _get_auth_status_dict(request)
        content["loggedIn"] = True
        content["currentUser"] = CurrentUserResponse(
            id=current_user.user_id,
            username=current_user.username,
            displayName=current_user.display_name,
            role=current_user.role,
            isAdmin=current_user.is_admin,
            isAuthenticated=True,
            transitional=False,
            authEnabled=True,
            legacyAdmin=current_user.legacy_admin,
        ).model_dump(by_alias=True)
        resp = JSONResponse(content=content)
        _set_session_cookie(resp, session_val, request)
        return resp

    _clear_current_user_cache(request)
    resp = JSONResponse(content=_get_auth_status_dict(request))
    _delete_session_cookie(resp)
    return resp



@router.post(
    "/login",
    summary="Login or create initial user credentials",
    description="Verify a user password and set the session cookie. Can bootstrap the admin password or create a new normal-user account.",
)
async def auth_login(request: Request, body: LoginRequest):
    """Login or create a minimal app-user credential and issue an authenticated session."""
    if not is_auth_enabled():
        return JSONResponse(
            status_code=400,
            content={"error": "auth_disabled", "message": "Authentication is not configured"},
        )

    username = _normalize_username(body.username) or BOOTSTRAP_ADMIN_USERNAME
    password = (body.password or "").strip()
    confirm = (body.password_confirm or "").strip()
    create_user = bool(body.create_user)
    if not password:
        return JSONResponse(
            status_code=400,
            content={"error": "password_required", "message": "请输入密码"},
        )

    ip = get_client_ip(request)
    if not check_rate_limit(ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "message": "Too many failed attempts. Please try again later.",
            },
        )

    db = DatabaseManager.get_instance()
    user_row = db.get_app_user_by_username(username)
    created_user = False

    if username == BOOTSTRAP_ADMIN_USERNAME:
        ensure_bootstrap_admin_user_password_hash()
        if user_row is None:
            user_row = db.ensure_bootstrap_admin_user()
        if not has_stored_password():
            if not confirm:
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_confirm_required", "message": "请确认管理员初始密码"},
                )
            if password != confirm:
                record_login_failure(ip)
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_mismatch", "message": "两次输入的密码不一致"},
                )
            err = set_initial_password(password)
            if err:
                record_login_failure(ip)
                return JSONResponse(
                    status_code=400,
                    content={"error": "invalid_password", "message": err},
                )
            ensure_bootstrap_admin_user_password_hash()
            user_row = db.get_app_user(BOOTSTRAP_ADMIN_USER_ID)
            created_user = True
        elif not verify_stored_password(password):
            record_login_failure(ip)
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_password", "message": "管理员密码错误"},
            )
    else:
        if user_row is None:
            if not create_user and not confirm:
                record_login_failure(ip)
                return JSONResponse(
                    status_code=404,
                    content={"error": "user_not_found", "message": "用户不存在，请先创建账户"},
                )
            if password != confirm:
                record_login_failure(ip)
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_mismatch", "message": "两次输入的密码不一致"},
                )
            try:
                password_hash = hash_password_for_storage(password)
            except ValueError as exc:
                record_login_failure(ip)
                return JSONResponse(
                    status_code=400,
                    content={"error": "invalid_password", "message": str(exc)},
                )
            user_row = db.create_or_update_app_user(
                user_id=f"user-{secrets.token_hex(8)}",
                username=username,
                display_name=(body.display_name or "").strip() or username,
                role=ROLE_USER,
                password_hash=password_hash,
                is_active=True,
            )
            created_user = True
        else:
            if not getattr(user_row, "is_active", True):
                record_login_failure(ip)
                return JSONResponse(
                    status_code=403,
                    content={"error": "user_inactive", "message": "该账户已停用"},
                )
            stored_hash = getattr(user_row, "password_hash", None)
            if not stored_hash:
                if not confirm:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "password_not_initialized", "message": "该账户尚未设置密码"},
                    )
                if password != confirm:
                    record_login_failure(ip)
                    return JSONResponse(
                        status_code=400,
                        content={"error": "password_mismatch", "message": "两次输入的密码不一致"},
                    )
                try:
                    password_hash = hash_password_for_storage(password)
                except ValueError as exc:
                    record_login_failure(ip)
                    return JSONResponse(
                        status_code=400,
                        content={"error": "invalid_password", "message": str(exc)},
                    )
                user_row = db.create_or_update_app_user(
                    user_id=str(user_row.id),
                    username=str(user_row.username),
                    display_name=getattr(user_row, "display_name", None) or str(user_row.username),
                    role=str(user_row.role),
                    password_hash=password_hash,
                    is_active=bool(getattr(user_row, "is_active", True)),
                )
            elif not verify_password_hash_string(password, stored_hash):
                record_login_failure(ip)
                return JSONResponse(
                    status_code=401,
                    content={"error": "invalid_password", "message": "密码错误"},
                )

    clear_rate_limit(ip)
    session_val = _persist_session_for_user(
        request=request,
        user_id=str(user_row.id),
        username=str(user_row.username),
        role=str(user_row.role),
    )
    if not session_val:
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Failed to create session"},
        )

    resp = JSONResponse(
        content={
            "ok": True,
            "createdUser": created_user,
            "currentUser": CurrentUserResponse(
                id=str(user_row.id),
                username=str(user_row.username),
                displayName=getattr(user_row, "display_name", None),
                role=str(user_row.role),
                isAdmin=str(user_row.role) == ROLE_ADMIN,
                isAuthenticated=True,
                transitional=False,
                authEnabled=True,
                legacyAdmin=False,
            ).model_dump(by_alias=True),
        }
    )
    _set_session_cookie(resp, session_val, request)
    return resp


@router.post(
    "/change-password",
    summary="Change password",
    description="Change password. Requires valid session.",
)
async def auth_change_password(request: Request, body: ChangePasswordRequest):
    """Change password. Requires login."""
    if not is_password_changeable():
        return JSONResponse(
            status_code=400,
            content={"error": "not_changeable", "message": "Password cannot be changed via web"},
        )

    current = (body.current_password or "").strip()
    new_pwd = (body.new_password or "").strip()
    new_confirm = (body.new_password_confirm or "").strip()

    if not current:
        return JSONResponse(
            status_code=400,
            content={"error": "current_required", "message": "请输入当前密码"},
        )
    if new_pwd != new_confirm:
        return JSONResponse(
            status_code=400,
            content={"error": "password_mismatch", "message": "两次输入的新密码不一致"},
        )

    current_user = resolve_current_user(request)
    if current_user is None:
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized", "message": "Login required"},
        )

    if current_user.user_id == BOOTSTRAP_ADMIN_USER_ID:
        err = change_password(current, new_pwd)
        if err:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_password", "message": err},
            )
    else:
        db = DatabaseManager.get_instance()
        user_row = db.get_app_user(current_user.user_id)
        if user_row is None:
            return JSONResponse(
                status_code=404,
                content={"error": "user_not_found", "message": "Current user not found"},
            )
        if not verify_password_hash_string(current, getattr(user_row, "password_hash", None)):
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_password", "message": "当前密码错误"},
            )
        try:
            new_hash = hash_password_for_storage(new_pwd)
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_password", "message": str(exc)},
            )
        db.create_or_update_app_user(
            user_id=str(user_row.id),
            username=str(user_row.username),
            display_name=getattr(user_row, "display_name", None) or str(user_row.username),
            role=str(user_row.role),
            password_hash=new_hash,
            is_active=bool(getattr(user_row, "is_active", True)),
        )
        if current_user.session_id:
            db.revoke_all_app_user_sessions(current_user.user_id)

    return Response(status_code=204)


@router.post(
    "/logout",
    summary="Logout",
    description="Clear session cookie.",
)
async def auth_logout(request: Request):
    """Clear session cookie."""
    current_user = resolve_current_user(request)
    if current_user and current_user.session_id:
        DatabaseManager.get_instance().revoke_app_user_session(current_user.session_id)
    resp = Response(status_code=204)
    _delete_session_cookie(resp)
    return resp
