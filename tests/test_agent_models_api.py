# -*- coding: utf-8 -*-
"""Tests for the Agent models discovery service and endpoint."""

import asyncio
import os
import unittest
from unittest.mock import patch

from api.v1.endpoints import agent
from src.config import Config
from src.services.agent_model_service import list_agent_model_deployments


def _build_config(**overrides):
    config = Config(
        litellm_model="gemini/gemini-2.5-flash",
        litellm_fallback_models=["openai/gpt-4o-mini"],
        llm_model_list=[],
        llm_channels=[],
        litellm_config_path=None,
        llm_models_source="legacy_env",
        openai_base_url=None,
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


class AgentModelsApiTestCase(unittest.TestCase):
    def test_models_endpoint_returns_litellm_config_deployments(self) -> None:
        config = _build_config(
            litellm_config_path="config/litellm.yaml",
            llm_models_source="litellm_config",
            llm_model_list=[
                {
                    "model_name": "gemini-primary",
                    "litellm_params": {"model": "gemini/gemini-2.5-flash", "api_key": "secret-1"},
                },
                {
                    "model_name": "openai-fallback",
                    "litellm_params": {"model": "openai/gpt-4o-mini", "api_key": "secret-2"},
                },
            ],
        )

        deployments = list_agent_model_deployments(config)

        self.assertEqual(len(deployments), 2)
        self.assertEqual(deployments[0]["source"], "litellm_config")
        self.assertTrue(deployments[0]["is_primary"])
        self.assertFalse("api_key" in str(deployments))

    def test_models_endpoint_returns_channel_deployments_with_api_base(self) -> None:
        config = _build_config(
            llm_channels=[{"name": "openai"}],
            llm_models_source="llm_channels",
            llm_model_list=[
                {
                    "model_name": "openai/gpt-4o-mini",
                    "litellm_params": {
                        "model": "openai/gpt-4o-mini",
                        "api_key": "secret-1",
                        "api_base": "https://api.example.com/v1",
                    },
                }
            ],
        )

        deployments = list_agent_model_deployments(config)

        self.assertEqual(deployments[0]["source"], "llm_channels")
        self.assertEqual(deployments[0]["api_base"], "https://api.example.com/v1")

    def test_models_endpoint_resolves_legacy_placeholders_to_real_models(self) -> None:
        config = _build_config(
            llm_model_list=[
                {"model_name": "__legacy_gemini__", "litellm_params": {"model": "__legacy_gemini__", "api_key": "g-1"}},
                {"model_name": "__legacy_gemini__", "litellm_params": {"model": "__legacy_gemini__", "api_key": "g-2"}},
                {"model_name": "__legacy_openai__", "litellm_params": {"model": "__legacy_openai__", "api_key": "o-1"}},
            ],
            openai_base_url="https://openai.example.com/v1",
        )

        deployments = list_agent_model_deployments(config)

        self.assertEqual(len(deployments), 3)
        self.assertEqual(deployments[0]["model"], "gemini/gemini-2.5-flash")
        self.assertEqual(deployments[1]["model"], "gemini/gemini-2.5-flash")
        self.assertEqual(deployments[2]["model"], "openai/gpt-4o-mini")
        self.assertEqual(deployments[2]["api_base"], "https://openai.example.com/v1")
        self.assertEqual(deployments[2]["source"], "legacy_env")
        self.assertTrue(all(not item["deployment_name"].startswith("__legacy_") for item in deployments))

    def test_models_endpoint_resolves_unprefixed_legacy_openai_model_names(self) -> None:
        config = _build_config(
            litellm_model="gpt-4o-mini",
            litellm_fallback_models=[],
            llm_model_list=[
                {"model_name": "__legacy_openai__", "litellm_params": {"model": "__legacy_openai__", "api_key": "o-1"}},
            ],
            openai_base_url="https://openai.example.com/v1",
        )

        deployments = list_agent_model_deployments(config)

        self.assertEqual(len(deployments), 1)
        self.assertEqual(deployments[0]["model"], "gpt-4o-mini")
        self.assertEqual(deployments[0]["provider"], "openai")
        self.assertEqual(deployments[0]["source"], "legacy_env")
        self.assertEqual(deployments[0]["api_base"], "https://openai.example.com/v1")

    def test_models_endpoint_returns_empty_list_when_no_model_is_configured(self) -> None:
        config = _build_config(
            litellm_model="",
            litellm_fallback_models=[],
            llm_model_list=[],
        )

        self.assertEqual(list_agent_model_deployments(config), [])


class AgentModelsEndpointTestCase(unittest.TestCase):
    def test_endpoint_returns_sorted_models_without_secrets(self) -> None:
        config = _build_config(
            llm_channels=[{"name": "primary"}, {"name": "secondary"}],
            llm_model_list=[
                {
                    "model_name": "openai/gpt-4o-mini",
                    "litellm_params": {
                        "model": "openai/gpt-4o-mini",
                        "api_key": "secret-openai",
                        "api_base": "https://api.openai.example/v1",
                    },
                },
                {
                    "model_name": "gemini/gemini-2.5-flash",
                    "litellm_params": {
                        "model": "gemini/gemini-2.5-flash",
                        "api_key": "secret-gemini",
                    },
                },
            ],
        )

        with patch("api.v1.endpoints.agent.get_config", return_value=config):
            payload = asyncio.run(agent.get_agent_models()).model_dump()

        self.assertEqual(len(payload["models"]), 2)
        self.assertEqual(payload["models"][0]["model"], "gemini/gemini-2.5-flash")
        self.assertTrue(payload["models"][0]["is_primary"])
        self.assertEqual(payload["models"][1]["model"], "openai/gpt-4o-mini")
        self.assertTrue(payload["models"][1]["is_fallback"])
        self.assertNotIn("api_key", str(payload))


class AgentModelsSourceDetectionTestCase(unittest.TestCase):
    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_load_from_env_marks_channels_as_actual_source_after_yaml_fallback(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "LITELLM_CONFIG": "config/missing.yaml",
            "LLM_CHANNELS": "primary",
            "LLM_PRIMARY_API_KEY": "channel-secret-key",
            "LLM_PRIMARY_MODELS": "openai/gpt-4o-mini",
            "OPENAI_API_KEY": "",
            "AIHUBMIX_KEY": "",
            "GEMINI_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "DEEPSEEK_API_KEY": "",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertEqual(config.llm_models_source, "llm_channels")
        self.assertEqual(config.llm_model_list[0]["litellm_params"]["model"], "openai/gpt-4o-mini")

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_load_from_env_marks_legacy_as_actual_source_after_yaml_fallback(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "LITELLM_CONFIG": "config/missing.yaml",
            "LLM_CHANNELS": "",
            "OPENAI_API_KEY": "legacy-openai-key",
            "LITELLM_MODEL": "gpt-4o-mini",
            "AIHUBMIX_KEY": "",
            "GEMINI_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "DEEPSEEK_API_KEY": "",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertEqual(config.llm_models_source, "legacy_env")
        self.assertTrue(config.llm_model_list)
        self.assertEqual(config.llm_model_list[0]["model_name"], "__legacy_openai__")


if __name__ == "__main__":
    unittest.main()
