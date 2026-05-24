# -*- coding: utf-8 -*-
"""Shared text sanitizers for logs, diagnostics, and API payloads."""

from __future__ import annotations

import re
from typing import Any


_REDACTED = "[REDACTED]"
_SENSITIVE_KEY_PARTS = {
    "authorization",
    "cookie",
    "password",
    "secret",
    "sendkey",
    "token",
    "webhook",
}
_SENSITIVE_KEY_PHRASES = {
    "access_token",
    "accesstoken",
    "api_key",
    "apikey",
    "auth_token",
    "authtoken",
    "authorization_header",
    "authorizationheader",
    "license_key",
    "licensekey",
    "private_key",
    "privatekey",
    "refresh_token",
    "refreshtoken",
    "secret_key",
    "secretkey",
    "send_key",
    "sendkey",
    "webhook_url",
    "webhookurl",
}


def sanitize_diagnostic_text(text: Any, *, max_length: int = 300) -> str:
    """Redact common secrets and URLs from diagnostic text."""
    sanitized = str(text or "").strip()
    if not sanitized:
        return ""
    sanitized = re.sub(r"(?i)(bearer\s+)[a-z0-9._\-:]+", r"\1[REDACTED]", sanitized)
    sanitized = re.sub(r"(?i)(token|secret|password|sendkey)([=:]\s*)[^\s,;&]+", r"\1\2[REDACTED]", sanitized)
    sanitized = re.sub(r"https?://[^\s]+", "[REDACTED_URL]", sanitized)
    return " ".join(sanitized.split())[:max_length]


def redact_sensitive_mapping(obj: Any) -> Any:
    """Recursively redact sensitive values from mappings by key name only.

    This helper intentionally does not inspect arbitrary string values. P1 only
    needs a deterministic serializer for AnalysisContextPack dictionaries.
    """
    if isinstance(obj, dict):
        redacted = {}
        for key, value in obj.items():
            if _is_sensitive_mapping_key(key):
                redacted[key] = _REDACTED
            else:
                redacted[key] = redact_sensitive_mapping(value)
        return redacted
    if isinstance(obj, list):
        return [redact_sensitive_mapping(item) for item in obj]
    return obj


def _is_sensitive_mapping_key(key: Any) -> bool:
    key_text = str(key or "").strip()
    if not key_text:
        return False
    key_lower = key_text.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", key_lower).strip("_")
    if any(
        normalized == phrase or normalized.endswith(f"_{phrase}")
        for phrase in _SENSITIVE_KEY_PHRASES
    ):
        return True
    parts = _mapping_key_parts(key_text)
    return bool(parts & _SENSITIVE_KEY_PARTS)


def _mapping_key_parts(key_text: str) -> set[str]:
    split_camel = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key_text)
    return {part.lower() for part in re.split(r"[^A-Za-z0-9]+", split_camel) if part}
