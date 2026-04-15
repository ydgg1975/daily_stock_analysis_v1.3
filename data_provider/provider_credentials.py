# -*- coding: utf-8 -*-
"""Lightweight provider credential helpers for market-data integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Sequence, Tuple

from src.config import Config, get_config


def _coerce_non_empty(value: object) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _collect_non_empty_strings(config: object, attr_names: Sequence[str]) -> Tuple[str, ...]:
    values: list[str] = []
    for attr_name in attr_names:
        if not hasattr(config, attr_name):
            continue
        raw_value = getattr(config, attr_name)
        if isinstance(raw_value, (list, tuple)):
            for item in raw_value:
                token = _coerce_non_empty(item)
                if token:
                    values.append(token)
        else:
            token = _coerce_non_empty(raw_value)
            if token:
                values.append(token)
    deduped: list[str] = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)


@dataclass(frozen=True)
class ProviderCredentialBundle:
    """Normalized provider credential payload."""

    provider: str
    auth_mode: str
    api_keys: Tuple[str, ...] = ()
    key_id: Optional[str] = None
    secret_key: Optional[str] = None
    extras: Dict[str, str] = field(default_factory=dict)

    @property
    def primary_api_key(self) -> Optional[str]:
        return self.api_keys[0] if self.api_keys else None

    @property
    def is_configured(self) -> bool:
        if self.auth_mode == "single_key":
            return bool(self.primary_api_key)
        if self.auth_mode == "key_secret":
            return bool(self.key_id and self.secret_key)
        return False

    @property
    def is_partial(self) -> bool:
        if self.auth_mode != "key_secret":
            return False
        return bool(self.key_id or self.secret_key) and not self.is_configured

    @property
    def missing_fields(self) -> Tuple[str, ...]:
        if self.auth_mode == "single_key":
            return ("api_key",) if not self.primary_api_key else ()
        if self.auth_mode == "key_secret":
            missing: list[str] = []
            if not self.key_id:
                missing.append("key_id")
            if not self.secret_key:
                missing.append("secret_key")
            return tuple(missing)
        return ()


def get_provider_credentials(
    provider: str,
    *,
    config: Optional[Config | Mapping[str, object]] = None,
) -> ProviderCredentialBundle:
    """Resolve provider credentials from the current config."""

    normalized = str(provider or "").strip().lower()
    config_obj: object = config if config is not None else get_config()
    if isinstance(config_obj, Mapping):
        config_obj = type("ProviderCredentialMap", (), dict(config_obj))()

    if normalized in {"twelve_data", "twelvedata"}:
        api_keys = _collect_non_empty_strings(
            config_obj,
            (
                "twelve_data_api_keys",
                "twelve_data_api_key",
            ),
        )
        return ProviderCredentialBundle(
            provider="twelve_data",
            auth_mode="single_key",
            api_keys=api_keys,
        )

    if normalized == "alpaca":
        return ProviderCredentialBundle(
            provider="alpaca",
            auth_mode="key_secret",
            key_id=_coerce_non_empty(getattr(config_obj, "alpaca_api_key_id", None)),
            secret_key=_coerce_non_empty(getattr(config_obj, "alpaca_api_secret_key", None)),
            extras={
                "data_feed": _coerce_non_empty(getattr(config_obj, "alpaca_data_feed", None)) or "iex",
            },
        )

    raise ValueError(f"Unsupported provider credential lookup: {provider}")
