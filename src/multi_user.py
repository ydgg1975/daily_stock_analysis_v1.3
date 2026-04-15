"""Shared multi-user constants and small normalization helpers."""

from __future__ import annotations

from typing import Optional

ROLE_USER = "user"
ROLE_ADMIN = "admin"
VALID_ROLES = {ROLE_USER, ROLE_ADMIN}

OWNERSHIP_SCOPE_USER = "user"
OWNERSHIP_SCOPE_SYSTEM = "system"
VALID_OWNERSHIP_SCOPES = {OWNERSHIP_SCOPE_USER, OWNERSHIP_SCOPE_SYSTEM}

BOOTSTRAP_ADMIN_USER_ID = "bootstrap-admin"
BOOTSTRAP_ADMIN_USERNAME = "admin"
BOOTSTRAP_ADMIN_DISPLAY_NAME = "Bootstrap Admin"


def normalize_role(role: Optional[str], default: str = ROLE_USER) -> str:
    value = str(role or default).strip().lower()
    if value not in VALID_ROLES:
        raise ValueError(f"role must be one of: {', '.join(sorted(VALID_ROLES))}")
    return value


def normalize_scope(scope: Optional[str], default: str = OWNERSHIP_SCOPE_USER) -> str:
    value = str(scope or default).strip().lower()
    if value not in VALID_OWNERSHIP_SCOPES:
        raise ValueError(
            "scope must be one of: "
            + ", ".join(sorted(VALID_OWNERSHIP_SCOPES))
        )
    return value
