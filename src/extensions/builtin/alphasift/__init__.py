# -*- coding: utf-8 -*-
"""Built-in AlphaSift manifest helpers.

P1 only loads the manifest so the runtime can report the opt-in plugin
boundary. Executable AlphaSift actions are introduced in a later phase.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.extensions.manifests import PluginManifest


def get_alphasift_manifest() -> PluginManifest:
    """Load the built-in AlphaSift manifest from plugin.yaml."""
    manifest_path = Path(__file__).with_name("plugin.yaml")
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    return PluginManifest.from_dict(payload)


__all__ = ["get_alphasift_manifest"]
