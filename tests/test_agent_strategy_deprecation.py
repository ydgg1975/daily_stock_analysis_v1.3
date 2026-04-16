import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import agent


class AgentStrategyDeprecationTestCase(unittest.TestCase):
    def test_legacy_strategies_endpoint_sets_deprecation_headers(self) -> None:
        app = FastAPI()
        app.include_router(agent.router, prefix="/api/v1/agent")
        skill_manager = SimpleNamespace(
            list_skills=lambda: [
                SimpleNamespace(
                    name="bull_trend",
                    display_name="多头趋势",
                    description="趋势跟随",
                    user_invocable=True,
                    default_priority=20,
                    default_active=True,
                ),
            ]
        )
        config = SimpleNamespace()

        with patch("api.v1.endpoints.agent.get_config", return_value=config), patch(
            "src.agent.factory.get_skill_manager",
            return_value=skill_manager,
        ):
            client = TestClient(app)
            response = client.get("/api/v1/agent/strategies")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Deprecation"), "true")
        self.assertEqual(
            response.headers.get("Link"),
            '</api/v1/agent/skills>; rel="successor-version"',
        )
        self.assertEqual(
            response.headers.get("X-DSA-Deprecated-Reason"),
            "Legacy strategy compatibility endpoint; use /api/v1/agent/skills.",
        )
        self.assertEqual(
            response.json(),
            {
                "strategies": [
                    {
                        "id": "bull_trend",
                        "name": "多头趋势",
                        "description": "趋势跟随",
                    }
                ],
                "default_strategy_id": "bull_trend",
            },
        )

    def test_legacy_strategy_wrapper_modules_are_marked_deprecated(self) -> None:
        modules = [
            "src.agent.strategies",
            "src.agent.strategies.router",
            "src.agent.strategies.aggregator",
            "src.agent.strategies.strategy_agent",
        ]

        for module_name in modules:
            module = asyncio.run(asyncio.to_thread(__import__, module_name, fromlist=["__doc__"]))
            doc = module.__doc__ or ""
            self.assertIn("Deprecated", doc, msg=module_name)
            self.assertIn("src.agent.skills", doc, msg=module_name)


if __name__ == "__main__":
    unittest.main()
