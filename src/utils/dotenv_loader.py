"""Helpers for robust `.env` loading across shell-style local files."""

from __future__ import annotations

import logging
from io import StringIO
from pathlib import Path
from typing import Dict, Optional

from dotenv import dotenv_values, load_dotenv

logger = logging.getLogger(__name__)

_SHELL_DIRECTIVE_PREFIXES = (
    "source ",
    ". ",
    "set -a",
    "set +a",
)
_WARNED_DIRECTIVES: set[tuple[str, int]] = set()


def _sanitize_dotenv_text(raw_text: str, env_path: Path) -> str:
    sanitized_lines: list[str] = []
    for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#") and not "=" in raw_line:
            lowered = stripped.lower()
            if lowered.startswith(_SHELL_DIRECTIVE_PREFIXES):
                warning_key = (str(env_path), line_number)
                if warning_key not in _WARNED_DIRECTIVES:
                    _WARNED_DIRECTIVES.add(warning_key)
                    logger.warning(
                        "忽略 .env 中不受 python-dotenv 支持的 shell 指令: %s:%s",
                        env_path,
                        line_number,
                    )
                continue
        sanitized_lines.append(raw_line)
    return "\n".join(sanitized_lines)


def load_dotenv_file(env_path: Path, *, override: bool = False) -> None:
    """Load `.env` contents while tolerating shell-only prelude lines."""
    if not env_path.exists():
        return

    raw_text = env_path.read_text(encoding="utf-8-sig")
    sanitized_text = _sanitize_dotenv_text(raw_text, env_path)
    load_dotenv(stream=StringIO(sanitized_text), override=override)


def read_dotenv_values(env_path: Path) -> Dict[str, Optional[str]]:
    """Parse `.env` key-values while tolerating shell-only prelude lines."""
    if not env_path.exists():
        return {}

    raw_text = env_path.read_text(encoding="utf-8-sig")
    sanitized_text = _sanitize_dotenv_text(raw_text, env_path)
    return dotenv_values(stream=StringIO(sanitized_text))
