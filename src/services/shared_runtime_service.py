# -*- coding: utf-8 -*-
"""Shared runtime object export helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class SharedRuntimeService:
    """Persist shared runtime objects as stable JSON envelopes."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir) if output_dir is not None else Path("./runtime/shared_runtime")

    def export_object(self, *, object_name: str, schema_version: str, data: Dict[str, Any]) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "object_name": object_name,
            "schema_version": schema_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        target_path = self.output_dir / f"{object_name}.json"
        temp_path = target_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temp_path.replace(target_path)
        return target_path
