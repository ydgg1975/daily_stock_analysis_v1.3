# -*- coding: utf-8 -*-
"""Tests for bot /status command output."""

from bot.commands.status import StatusCommand
from src.config import Config


def test_status_command_reports_unified_llm_and_notification_channels():
    config = Config(
        stock_list=["600519", "AAPL"],
        litellm_model="deepseek/deepseek-v4-flash",
        agent_litellm_model="openai/gpt-4o-mini",
        llm_channels=[{"name": "deepseek", "models": ["deepseek/deepseek-v4-flash"]}],
        llm_models_source="llm_channels",
        llm_model_list=[
            {
                "model_name": "deepseek/deepseek-v4-flash",
                "litellm_params": {"model": "deepseek/deepseek-v4-flash", "api_key": "sk-test"},
            }
        ],
        custom_webhook_urls=["https://example.com/webhook"],
        slack_webhook_url="https://hooks.slack.com/services/T/B/C",
        serverchan3_sendkey="SCT123",
    )
    command = StatusCommand()

    status = command._collect_status(config)
    text = command._format_status(status, "telegram")

    assert status["ai_available"] is True
    assert "주 모델: deepseek/deepseek-v4-flash" in text
    assert "Agent 모델: openai/gpt-4o-mini" in text
    assert "LLM 채널: deepseek" in text
    assert "Custom Webhook: ✅" in text
    assert "Slack: ✅" in text
    assert "PushPlus/Pushover/ServerChan3: ✅" in text
    assert "시스템 준비 완료" in text


def test_status_command_warns_when_no_llm_source_configured():
    config = Config(stock_list=["600519"])
    command = StatusCommand()

    status = command._collect_status(config)
    text = command._format_status(status, "telegram")

    assert status["ai_available"] is False
    assert "주 모델: 미설정" in text
    assert "AI 서비스가 설정되지 않아" in text
    assert "LITELLM_MODEL" in text


def test_status_command_does_not_treat_managed_model_name_as_ready():
    config = Config(stock_list=["600519"], litellm_model="openai/gpt-4o-mini", llm_model_list=[])
    command = StatusCommand()

    status = command._collect_status(config)
    text = command._format_status(status, "telegram")

    assert status["ai_available"] is False
    assert "AI 서비스가 설정되지 않아" in text


def test_status_command_treats_direct_env_provider_model_as_ready():
    config = Config(stock_list=["600519"], litellm_model="cohere/command-r-plus", llm_model_list=[])
    command = StatusCommand()

    status = command._collect_status(config)
    text = command._format_status(status, "telegram")

    assert status["ai_available"] is True
    assert "시스템 준비 완료" in text


def test_status_command_supports_legacy_key_compatibility_without_explicit_litellm_model(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(env_file))
    for key in (
        "GEMINI_API_KEYS",
        "GEMINI_API_KEY",
        "ANTHROPIC_API_KEYS",
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEYS",
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEYS",
        "AIHUBMIX_KEY",
        "LITELLM_MODEL",
        "LLM_CHANNELS",
        "LITELLM_CONFIG",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-legacy-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")

    Config.reset_instance()
    try:
        config = Config.get_instance()
        command = StatusCommand()

        status = command._collect_status(config)
        text = command._format_status(status, "telegram")

        assert status["ai_available"] is True
        assert "주 모델: openai/gpt-4o-mini" in text
        assert "AI 서비스가 설정되지 않아" not in text
    finally:
        Config.reset_instance()
