# -*- coding: utf-8 -*-
"""Tests for MiniMax provider integration.

Covers:
- MINIMAX_API_KEY / MINIMAX_API_KEYS environment variable parsing
- Auto-inference of LITELLM_MODEL when only MiniMax key is set
- Legacy model_list generation for MiniMax keys
- get_api_keys_for_model() for MiniMax models
- extra_litellm_params() for MiniMax models
- validate_structured() with MiniMax keys
"""
import os
import pytest
from unittest.mock import patch

from src.config import Config, get_api_keys_for_model, extra_litellm_params


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**kwargs) -> Config:
    """Build a minimal Config object with sensible defaults for testing."""
    defaults = dict(
        stock_list=["600519"],
        tushare_token=None,
        llm_model_list=[{"model_name": "openai/MiniMax-M2.5", "litellm_params": {"api_key": "sk-test"}}],
        litellm_model="openai/MiniMax-M2.5",
        gemini_api_keys=[],
        anthropic_api_keys=[],
        openai_api_keys=[],
        deepseek_api_keys=[],
        minimax_api_keys=[],
        bocha_api_keys=[],
        tavily_api_keys=[],
        brave_api_keys=[],
        serpapi_keys=[],
        wechat_webhook_url="https://example.com/webhook",
        feishu_webhook_url=None,
        telegram_bot_token=None,
        telegram_chat_id=None,
        email_sender=None,
        email_password=None,
        pushover_user_key=None,
        pushover_api_token=None,
        pushplus_token=None,
        serverchan3_sendkey=None,
        custom_webhook_urls=[],
        discord_bot_token=None,
        discord_main_channel_id=None,
        discord_webhook_url=None,
        llm_channels=[],
        litellm_config_path=None,
        gemini_api_key=None,
        anthropic_api_key=None,
        openai_api_key=None,
        openai_base_url=None,
        openai_vision_model=None,
    )
    defaults.update(kwargs)
    return Config(**defaults)


# ---------------------------------------------------------------------------
# MINIMAX_API_KEY parsing via _load_from_env
# ---------------------------------------------------------------------------

class TestMiniMaxKeyParsing:
    def test_single_minimax_key_parsed(self):
        """MINIMAX_API_KEY should be parsed into minimax_api_keys list."""
        env = {
            "MINIMAX_API_KEY": "sk-minimax-test-key-12345678",
            "STOCK_LIST": "600519",
        }
        Config.reset_instance()
        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()
        assert config.minimax_api_keys == ["sk-minimax-test-key-12345678"]

    def test_multi_minimax_keys_parsed(self):
        """MINIMAX_API_KEYS (comma-separated) should take priority over single key."""
        env = {
            "MINIMAX_API_KEYS": "sk-key1-abcdefgh,sk-key2-ijklmnop",
            "MINIMAX_API_KEY": "sk-single-should-be-ignored",
            "STOCK_LIST": "600519",
        }
        Config.reset_instance()
        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()
        assert config.minimax_api_keys == ["sk-key1-abcdefgh", "sk-key2-ijklmnop"]

    def test_no_minimax_key_empty_list(self):
        """When no MiniMax key is set, minimax_api_keys should be empty."""
        env = {"STOCK_LIST": "600519"}
        Config.reset_instance()
        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()
        assert config.minimax_api_keys == []


# ---------------------------------------------------------------------------
# Auto-inference of LITELLM_MODEL
# ---------------------------------------------------------------------------

class TestMiniMaxModelInference:
    def test_minimax_only_infers_model(self):
        """When only MINIMAX_API_KEY is set, LITELLM_MODEL should be openai/MiniMax-M2.5."""
        env = {
            "MINIMAX_API_KEY": "sk-minimax-test-key-12345678",
            "STOCK_LIST": "600519",
        }
        Config.reset_instance()
        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()
        assert config.litellm_model == "openai/MiniMax-M2.5"

    def test_gemini_takes_priority_over_minimax(self):
        """Gemini should take priority over MiniMax in model inference."""
        env = {
            "GEMINI_API_KEY": "sk-gemini-test-key-12345678",
            "MINIMAX_API_KEY": "sk-minimax-test-key-12345678",
            "STOCK_LIST": "600519",
        }
        Config.reset_instance()
        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()
        assert config.litellm_model.startswith("gemini/")


# ---------------------------------------------------------------------------
# Legacy model_list generation
# ---------------------------------------------------------------------------

class TestMiniMaxLegacyModelList:
    def test_minimax_keys_in_legacy_model_list(self):
        """MiniMax keys should produce __legacy_minimax__ entries in model_list."""
        model_list = Config._legacy_keys_to_model_list(
            gemini_keys=[],
            anthropic_keys=[],
            openai_keys=[],
            openai_base_url=None,
            deepseek_keys=[],
            minimax_keys=["sk-minimax-test-key-12345678"],
        )
        minimax_entries = [m for m in model_list if m["model_name"] == "__legacy_minimax__"]
        assert len(minimax_entries) == 1
        assert minimax_entries[0]["litellm_params"]["api_base"] == "https://api.minimax.io/v1"
        assert minimax_entries[0]["litellm_params"]["api_key"] == "sk-minimax-test-key-12345678"

    def test_short_minimax_key_filtered(self):
        """MiniMax keys shorter than 8 chars should be filtered out."""
        model_list = Config._legacy_keys_to_model_list(
            gemini_keys=[],
            anthropic_keys=[],
            openai_keys=[],
            openai_base_url=None,
            deepseek_keys=[],
            minimax_keys=["short"],
        )
        minimax_entries = [m for m in model_list if m["model_name"] == "__legacy_minimax__"]
        assert len(minimax_entries) == 0

    def test_minimax_keys_none_safe(self):
        """Passing None for minimax_keys should not crash."""
        model_list = Config._legacy_keys_to_model_list(
            gemini_keys=[],
            anthropic_keys=[],
            openai_keys=[],
            openai_base_url=None,
            deepseek_keys=[],
            minimax_keys=None,
        )
        minimax_entries = [m for m in model_list if m["model_name"] == "__legacy_minimax__"]
        assert len(minimax_entries) == 0


# ---------------------------------------------------------------------------
# get_api_keys_for_model
# ---------------------------------------------------------------------------

class TestGetApiKeysForMiniMax:
    def test_minimax_model_returns_minimax_keys(self):
        """openai/MiniMax-M2.5 should return minimax_api_keys."""
        cfg = _make_config(minimax_api_keys=["sk-minimax-test-key-12345678"])
        keys = get_api_keys_for_model("openai/MiniMax-M2.5", cfg)
        assert keys == ["sk-minimax-test-key-12345678"]

    def test_minimax_highspeed_model_returns_keys(self):
        """openai/MiniMax-M2.5-highspeed should also return minimax_api_keys."""
        cfg = _make_config(minimax_api_keys=["sk-minimax-test-key-12345678"])
        keys = get_api_keys_for_model("openai/MiniMax-M2.5-highspeed", cfg)
        assert keys == ["sk-minimax-test-key-12345678"]

    def test_minimax_short_keys_filtered(self):
        """Short keys should be filtered out."""
        cfg = _make_config(minimax_api_keys=["short", "sk-minimax-test-key-12345678"])
        keys = get_api_keys_for_model("openai/MiniMax-M2.5", cfg)
        assert keys == ["sk-minimax-test-key-12345678"]


# ---------------------------------------------------------------------------
# extra_litellm_params
# ---------------------------------------------------------------------------

class TestExtraLitellmParamsMiniMax:
    def test_minimax_model_gets_api_base(self):
        """MiniMax models should get api_base set to minimax.io."""
        cfg = _make_config()
        params = extra_litellm_params("openai/MiniMax-M2.5", cfg)
        assert params.get("api_base") == "https://api.minimax.io/v1"

    def test_minimax_highspeed_gets_api_base(self):
        """MiniMax-M2.5-highspeed should also get the correct api_base."""
        cfg = _make_config()
        params = extra_litellm_params("openai/MiniMax-M2.5-highspeed", cfg)
        assert params.get("api_base") == "https://api.minimax.io/v1"


# ---------------------------------------------------------------------------
# validate_structured with MiniMax
# ---------------------------------------------------------------------------

class TestValidateStructuredMiniMax:
    def test_minimax_only_no_llm_error(self):
        """MiniMax keys populated via llm_model_list should NOT trigger LLM error."""
        model_list = [
            {"model_name": "__legacy_minimax__", "litellm_params": {"model": "__legacy_minimax__", "api_key": "sk-mm"}},
        ]
        cfg = _make_config(
            llm_model_list=model_list,
            minimax_api_keys=["sk-mm-test-key-12345678"],
            gemini_api_keys=[],
            anthropic_api_keys=[],
            openai_api_keys=[],
            deepseek_api_keys=[],
        )
        issues = cfg.validate_structured()
        assert not any(i.severity == "error" and "LLM" in i.message for i in issues)
