# -*- coding: utf-8 -*-
"""Small security helpers for extension adapters."""

from __future__ import annotations

from typing import Any, Dict

DEFAULT_CLI_STDOUT_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_CLI_STDERR_MAX_BYTES = 1024 * 1024
SENSITIVE_KEYS = {
    "access_key",
    "accesskey",
    "api_key",
    "apikey",
    "client_secret",
    "clientsecret",
    "password",
    "private_key",
    "privatekey",
    "refresh_token",
    "refreshtoken",
    "secret",
    "token",
}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return (
        normalized in SENSITIVE_KEYS
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
        or normalized.endswith("_password")
    )


def redact_sensitive_mapping(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow redacted copy for diagnostics."""
    redacted: Dict[str, Any] = {}
    for key, value in payload.items():
        if _is_sensitive_key(str(key)):
            redacted[key] = "***"
        else:
            redacted[key] = value
    return redacted
