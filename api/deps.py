# -*- coding: utf-8 -*-
"""
===================================
API 依赖注入模块
===================================

职责：
1. 提供数据库 Session 依赖
2. 提供配置依赖
3. 提供服务层依赖
"""

from dataclasses import dataclass
from typing import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.auth import COOKIE_NAME, get_session_identity, is_auth_enabled
from src.storage import DatabaseManager
from src.config import get_config, Config
from src.services.system_config_service import SystemConfigService


@dataclass(frozen=True)
class CurrentUser:
    """Resolved current-user view shared by API dependencies and middleware."""

    user_id: str
    username: str
    display_name: str | None
    role: str
    is_admin: bool
    is_authenticated: bool
    transitional: bool
    auth_enabled: bool
    session_id: str | None = None
    legacy_admin: bool = False


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库 Session 依赖
    
    使用 FastAPI 依赖注入机制，确保请求结束后自动关闭 Session
    
    Yields:
        Session: SQLAlchemy Session 对象
        
    Example:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            ...
    """
    db_manager = DatabaseManager.get_instance()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def get_config_dep() -> Config:
    """
    获取配置依赖
    
    Returns:
        Config: 配置单例对象
    """
    return get_config()


def get_database_manager() -> DatabaseManager:
    """
    获取数据库管理器依赖
    
    Returns:
        DatabaseManager: 数据库管理器单例对象
    """
    return DatabaseManager.get_instance()


def get_system_config_service(request: Request) -> SystemConfigService:
    """Get app-lifecycle shared SystemConfigService instance."""
    service = getattr(request.app.state, "system_config_service", None)
    if service is None:
        service = SystemConfigService()
        request.app.state.system_config_service = service
    return service


def resolve_current_user(request: Request) -> CurrentUser | None:
    """Resolve the effective current user from session cookie or transitional fallback."""
    state = getattr(request, "state", None)
    cache_miss = object()
    if state is not None:
        cached = getattr(state, "current_user", cache_miss)
        if cached is not cache_miss:
            return cached

    db = DatabaseManager.get_instance()
    auth_enabled = is_auth_enabled()
    cookies = getattr(request, "cookies", {}) or {}
    cookie_val = cookies.get(COOKIE_NAME)
    identity = get_session_identity(cookie_val) if cookie_val else None

    if identity is not None:
        user_row = db.get_app_user(identity.user_id)
        if user_row is not None and getattr(user_row, "is_active", True):
            current_user = CurrentUser(
                user_id=str(user_row.id),
                username=str(user_row.username),
                display_name=getattr(user_row, "display_name", None),
                role=str(user_row.role),
                is_admin=str(user_row.role) == "admin",
                is_authenticated=True,
                transitional=False,
                auth_enabled=auth_enabled,
                session_id=identity.session_id,
                legacy_admin=identity.legacy_admin,
            )
            if state is not None:
                state.current_user = current_user
            return current_user

    if not auth_enabled:
        bootstrap_user = db.ensure_bootstrap_admin_user()
        current_user = CurrentUser(
            user_id=str(bootstrap_user.id),
            username=str(bootstrap_user.username),
            display_name=getattr(bootstrap_user, "display_name", None),
            role=str(bootstrap_user.role),
            is_admin=str(bootstrap_user.role) == "admin",
            is_authenticated=False,
            transitional=True,
            auth_enabled=False,
            session_id=None,
            legacy_admin=False,
        )
        if state is not None:
            state.current_user = current_user
        return current_user

    if state is not None:
        state.current_user = None
    return None


def get_optional_current_user(request: Request) -> CurrentUser | None:
    """Return the resolved current user when available."""
    return resolve_current_user(request)


def get_current_user_id(current_user: object | None) -> str | None:
    """Extract a user id from a resolved current-user object when available."""
    user_id = getattr(current_user, "user_id", None)
    if not user_id:
        return None
    return str(user_id)


def is_admin_user(current_user: object | None) -> bool:
    """Return True when the resolved current user has the admin role."""
    return bool(getattr(current_user, "is_admin", False))


def ensure_current_user_matches_owner(
    owner_id: str | None,
    current_user: object | None,
    *,
    allow_admin_override: bool = False,
) -> None:
    """Validate that an explicit owner id matches the resolved current user."""
    normalized_owner_id = str(owner_id or "").strip()
    if not normalized_owner_id:
        return

    current_user_id = get_current_user_id(current_user)
    if current_user_id and normalized_owner_id == current_user_id:
        return
    if allow_admin_override and is_admin_user(current_user):
        return

    raise HTTPException(
        status_code=403,
        detail={
            "error": "owner_mismatch",
            "message": "The requested owner_id does not match the current user",
        },
    )


def get_current_user(request: Request) -> CurrentUser:
    """Require an authenticated or transitional current user."""
    current_user = resolve_current_user(request)
    if current_user is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Login required"},
        )
    return current_user


def require_admin_user(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Require the resolved current user to be an admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail={"error": "admin_required", "message": "Admin access required"},
        )
    return current_user
