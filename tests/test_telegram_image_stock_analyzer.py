# -*- coding: utf-8 -*-
"""Tests for Telegram image stock analysis routing."""

from unittest.mock import patch

from src.services.minimax_mcp_client import MiniMaxMCPError
from src.services.telegram_image_stock_analyzer import analyze_stock_image_bytes


def test_analyze_stock_image_prefers_minimax_mcp(monkeypatch):
    monkeypatch.setenv("MINIMAX_IMAGE_UNDERSTANDING_ENABLED", "true")

    raw = '[{"code":"002497","name":"雅化集团","confidence":"high"}]'
    with patch(
        "src.services.telegram_image_stock_analyzer.understand_image_bytes",
        return_value=raw,
    ) as mcp_call:
        result = analyze_stock_image_bytes(b"fake-png", "image/png")

    assert result.provider == "MiniMax MCP"
    assert result.items == [("002497", "雅化集团", "high")]
    assert result.raw_text == raw
    mcp_call.assert_called_once()


def test_analyze_stock_image_falls_back_to_litellm(monkeypatch):
    monkeypatch.setenv("MINIMAX_IMAGE_UNDERSTANDING_ENABLED", "true")

    with patch(
        "src.services.telegram_image_stock_analyzer.understand_image_bytes",
        side_effect=MiniMaxMCPError("mcp down"),
    ), patch(
        "src.services.telegram_image_stock_analyzer.extract_stock_codes_from_image",
        return_value=([("920402", "硅烷科技", "medium")], "fallback raw"),
    ) as fallback:
        result = analyze_stock_image_bytes(b"fake-png", "image/png")

    assert result.provider == "LiteLLM Vision"
    assert result.items == [("920402", "硅烷科技", "medium")]
    assert result.raw_text == "fallback raw"
    fallback.assert_called_once()
