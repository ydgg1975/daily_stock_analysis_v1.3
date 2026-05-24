# -*- coding: utf-8 -*-
"""Helpers for action run ids and stable input hashes."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any


def new_run_id() -> str:
    """Return a stable run id with the extension run prefix."""
    return f"run_{uuid.uuid4().hex}"


def canonical_json(value: Any) -> str:
    """Serialize a value into canonical JSON used for input hashing."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def input_hash(value: Any) -> str:
    """Return a sha256 hash for canonicalized action input."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
