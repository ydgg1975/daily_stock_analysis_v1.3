# -*- coding: utf-8 -*-
"""LLM thinking-mode routing tests."""

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.agent.llm_adapter import get_thinking_extra_body  # noqa: E402


def test_deepseek_chat_does_not_send_opt_in_thinking_payload():
    assert get_thinking_extra_body("deepseek-chat") is None


def test_native_thinking_models_do_not_need_extra_body():
    assert get_thinking_extra_body("deepseek-reasoner") is None
    assert get_thinking_extra_body("deepseek-r1") is None
    assert get_thinking_extra_body("qwq") is None
