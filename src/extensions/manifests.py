# -*- coding: utf-8 -*-
"""Plugin manifest schema helpers for built-in extensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PluginManifest:
    """Minimal manifest metadata used before third-party plugin loading exists."""

    id: str
    name: str
    version: str
    kind: str
    description: str = ""
    requires: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    supported_markets: List[str] = field(default_factory=list)
    installation_hints: List[str] = field(default_factory=list)
    setup_doc_url: str = ""
    default_enabled: bool = False
    ui_contributions: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PluginManifest":
        """Build and validate a manifest from a mapping."""
        manifest = cls(
            id=str(payload.get("id", "")).strip(),
            name=str(payload.get("name", "")).strip(),
            version=str(payload.get("version", "")).strip(),
            kind=str(payload.get("kind", "")).strip(),
            description=str(payload.get("description", "")).strip(),
            requires=list(payload.get("requires") or []),
            permissions=list(payload.get("permissions") or []),
            actions=list(payload.get("actions") or []),
            skills=list(payload.get("skills") or []),
            supported_markets=list(payload.get("supported_markets") or []),
            installation_hints=list(payload.get("installation_hints") or []),
            setup_doc_url=str(payload.get("setup_doc_url", "")).strip(),
            default_enabled=bool(payload.get("default_enabled", False)),
            ui_contributions=list(payload.get("ui_contributions") or []),
        )
        manifest.validate()
        return manifest

    def validate(self) -> None:
        """Validate required manifest fields."""
        if not self.id:
            raise ValueError("Plugin manifest id is required")
        if not self.name:
            raise ValueError("Plugin manifest name is required")
        if not self.version:
            raise ValueError("Plugin manifest version is required")
        if not self.kind:
            raise ValueError("Plugin manifest kind is required")
