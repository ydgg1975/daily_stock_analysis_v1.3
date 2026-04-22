# -*- coding: utf-8 -*-
"""Image analysis helper for the Telegram stock bot."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

from src.services.image_stock_extractor import (
    EXTRACT_PROMPT,
    extract_stock_codes_from_image,
    parse_stock_items_from_vision_text,
)
from src.services.minimax_mcp_client import MiniMaxMCPError, understand_image_bytes

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelegramImageStockAnalysis:
    items: list[tuple[str, Optional[str], str]]
    raw_text: str
    provider: str


def _truthy_env(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def analyze_stock_image_bytes(image_bytes: bytes, mime_type: str) -> TelegramImageStockAnalysis:
    """Extract stock references from an image, preferring MiniMax MCP vision.

    MiniMax Token Plan MCP is used first because it is already part of the
    user's tool subscription. If it is unavailable, fall back to the existing
    LiteLLM vision pipeline so Telegram still has a chance to answer.
    """

    normalized_mime = (mime_type or "").split(";")[0].strip().lower()
    minimax_enabled = _truthy_env("MINIMAX_IMAGE_UNDERSTANDING_ENABLED", True)
    timeout = int(os.getenv("MINIMAX_IMAGE_UNDERSTANDING_TIMEOUT", "90"))

    if minimax_enabled and normalized_mime in {"image/jpeg", "image/png", "image/webp"}:
        try:
            raw = understand_image_bytes(
                image_bytes=image_bytes,
                mime_type=normalized_mime,
                prompt=EXTRACT_PROMPT,
                timeout_seconds=timeout,
            )
            items = parse_stock_items_from_vision_text(raw)
            return TelegramImageStockAnalysis(items=items, raw_text=raw, provider="MiniMax MCP")
        except MiniMaxMCPError as exc:
            logger.warning("MiniMax image understanding failed, falling back to LiteLLM vision: %s", exc)

    items, raw = extract_stock_codes_from_image(image_bytes, normalized_mime or mime_type)
    return TelegramImageStockAnalysis(items=items, raw_text=raw, provider="LiteLLM Vision")
