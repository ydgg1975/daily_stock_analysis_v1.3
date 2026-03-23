# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch, AsyncMock
import json
import pytest
import unittest
from datetime import datetime, timedelta

# Mock optional modules before importing project code
for optional_module in ("litellm", "json_repair"):
    try:
        __import__(optional_module)
    except ModuleNotFoundError:
        sys.modules[optional_module] = MagicMock()

if "pandas" not in sys.modules:
    _pd = ModuleType("pandas")
    _pd.DataFrame = MagicMock()  # type: ignore[attr-defined]
    sys.modules["pandas"] = _pd

from src.services.crypto_ai_service import (
    CryptoAiService,
    PROMPT_VERSION,
    _MARKET_ANALYST_PROMPT,
)
from src.storage import (
    DatabaseManager,
    CryptoLaunch,
    CryptoLaunchSnapshot,
    CryptoLaunchAiSummary,
    CryptoLaunchSecurityScan,
)


def seed_test_launch(db_manager, **overrides):
    now = datetime.now()
    with db_manager.get_session() as session:
        launch = CryptoLaunch(
            chain_id=overrides.get("chain_id", "bsc"),
            dex_id="pancakeswap",
            pair_address=overrides.get("pair_address", "0xpair-ai-test"),
            pair_url="https://dex.example/pair/0xpair-ai-test",
            pair_created_at=overrides.get("pair_created_at", now - timedelta(hours=3)),
            base_token_address=overrides.get("base_token_address", "0xbase-ai-test"),
            base_token_symbol=overrides.get("base_token_symbol", "MOON"),
            base_token_name=overrides.get("base_token_name", "Moon Token"),
            quote_token_address="0xquote",
            quote_token_symbol="USDT",
            quote_token_name="Tether",
            liquidity_usd=overrides.get("liquidity_usd", 125000.0),
            volume_usd_24h=overrides.get("volume_usd_24h", 450000.0),
            buys_24h=overrides.get("buys_24h", 120),
            sells_24h=overrides.get("sells_24h", 45),
            price_usd=overrides.get("price_usd", 0.0123),
            price_change_pct_24h=overrides.get("price_change_pct_24h", 18.4),
            fdv_usd=overrides.get("fdv_usd", 2400000.0),
            market_cap_usd=overrides.get("market_cap_usd", 1800000.0),
            dexscreener_url="https://dexscreener.com/bsc/0xpair-ai-test",
            website_url="https://moon.example",
            socials_json=json.dumps({"twitter": "https://x.com/moon"}),
            labels_json=json.dumps(["meme", "new"]),
            raw_payload=json.dumps({"source": "test"}),
            data_complete=True,
            first_seen_at=now - timedelta(hours=2),
            last_seen_at=now,
        )
        session.add(launch)
        session.commit()
        session.refresh(launch)

        snapshot = CryptoLaunchSnapshot(
            launch_id=launch.id,
            snapshot_at=now,
            liquidity_usd=launch.liquidity_usd,
            volume_usd_24h=launch.volume_usd_24h,
            buys_24h=launch.buys_24h,
            sells_24h=launch.sells_24h,
            price_usd=launch.price_usd,
            price_change_pct_24h=launch.price_change_pct_24h,
            fdv_usd=launch.fdv_usd,
            market_cap_usd=launch.market_cap_usd,
            data_complete=True,
            raw_payload=json.dumps({"snapshot": 1}),
        )
        session.add(snapshot)

        older_snapshot = CryptoLaunchSnapshot(
            launch_id=launch.id,
            snapshot_at=now - timedelta(minutes=30),
            liquidity_usd=120000.0,
            volume_usd_24h=380000.0,
            buys_24h=95,
            sells_24h=40,
            price_usd=0.0105,
            price_change_pct_24h=11.0,
            fdv_usd=2100000.0,
            market_cap_usd=1600000.0,
            data_complete=True,
            raw_payload=json.dumps({"snapshot": 0}),
        )
        session.add(older_snapshot)

        security = CryptoLaunchSecurityScan(
            launch_id=launch.id,
            provider="goplus",
            risk_score=overrides.get("risk_score", 42.0),
            risk_level=overrides.get("risk_level", "medium"),
            is_honeypot=overrides.get("is_honeypot", False),
            is_mintable=overrides.get("is_mintable", True),
            buy_tax_pct=overrides.get("buy_tax_pct", 2.0),
            sell_tax_pct=overrides.get("sell_tax_pct", 4.0),
            lp_locked_pct=overrides.get("lp_locked_pct", 88.0),
            top10_holder_rate_pct=overrides.get("top10_holder_rate_pct", 31.0),
            raw_payload_json=json.dumps({"provider": "goplus"}),
            scanned_at=now,
        )
        session.add(security)
        session.commit()
        session.refresh(snapshot)

        return launch.id, snapshot.id


@pytest.mark.not_network
class CryptoAiServiceTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        DatabaseManager.reset_instance()
        self.db = DatabaseManager("sqlite:///:memory:")
        self.config = SimpleNamespace(
            crypto_ai_enrichment_enabled=True,
            crypto_ai_quick_model="test-quick-model",
            crypto_ai_deep_model="test-deep-model",
            crypto_ai_cache_ttl_sec=21600,
            crypto_ai_prompt_version="v1",
            litellm_model="fallback-model",
        )
        self.service = CryptoAiService(config=self.config, db_manager=self.db)
        self.launch_id, self.snapshot_id = seed_test_launch(self.db)

    def tearDown(self):
        DatabaseManager.reset_instance()

    async def test_prompt_construction_with_real_launch_data(self):
        data = self.service._gather_launch_data(self.launch_id)

        self.assertIsNotNone(data)
        self.assertEqual(data["launch_id"], self.launch_id)
        self.assertEqual(data["latest_snapshot_id"], self.snapshot_id)
        self.assertEqual(len(data["snapshot_history"]), 2)

        prompt = _MARKET_ANALYST_PROMPT.format(**data)

        self.assertIn("Moon Token", prompt)
        self.assertIn("MOON", prompt)
        self.assertIn("bsc", prompt)
        self.assertIn("$0.0123", prompt)
        self.assertIn("$125000.0", prompt)
        self.assertIn("24h Buys: 120 | Sells: 45", prompt)
        self.assertIn("Age:", prompt)

    async def test_call_llm_parses_valid_json_response(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"verdict": "BUY", "confidence": 0.77}'))],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18),
        )

        with patch("src.services.crypto_ai_service.litellm.acompletion", new=AsyncMock(return_value=response)):
            result, usage = await self.service._call_llm("test prompt", "test-model")

        self.assertEqual(result, {"verdict": "BUY", "confidence": 0.77})
        self.assertEqual(usage["prompt_tokens"], 11)
        self.assertEqual(usage["completion_tokens"], 7)
        self.assertEqual(usage["total_tokens"], 18)

    async def test_call_llm_returns_raw_text_for_malformed_json(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="not-json at all"))],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2, total_tokens=7),
        )

        with patch("src.services.crypto_ai_service.litellm.acompletion", new=AsyncMock(return_value=response)):
            result, usage = await self.service._call_llm("bad prompt", "test-model")

        self.assertEqual(result, {"raw_text": "not-json at all"})
        self.assertEqual(usage["prompt_tokens"], 5)

    async def test_run_analysts_handles_partial_failure(self):
        data = self.service._gather_launch_data(self.launch_id)
        _zero_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        side_effects = [
            ({"assessment": "Market strong", "signal": "bullish", "confidence": 0.9}, _zero_usage),
            RuntimeError("security timeout"),
            ({"assessment": "Community active", "signal": "strong", "confidence": 0.8}, _zero_usage),
            ({"assessment": "Trend intact", "signal": "bullish", "confidence": 0.75}, _zero_usage),
        ]

        with patch.object(self.service, "_call_llm", new=AsyncMock(side_effect=side_effects)) as mock_call:
            result, usage = await self.service._run_analysts(data, "test-quick-model")

        self.assertEqual(mock_call.await_count, 4)
        self.assertEqual(result["market"]["signal"], "bullish")
        self.assertEqual(result["social"]["signal"], "strong")
        self.assertEqual(result["technical"]["signal"], "bullish")
        self.assertEqual(result["security"]["signal"], "neutral")
        self.assertEqual(result["security"]["confidence"], 0.0)
        self.assertIn("security timeout", result["security"]["assessment"])

    async def test_analyze_persists_summary_row_roundtrip(self):
        analyst_result = {
            "market": {"assessment": "Strong liquidity", "signal": "bullish", "confidence": 0.9},
            "security": {"assessment": "Moderate risk", "signal": "safe", "confidence": 0.8},
            "social": {"assessment": "Growing attention", "signal": "strong", "confidence": 0.7},
            "technical": {"assessment": "Uptrend", "signal": "bullish", "confidence": 0.75},
        }
        debate_result = {
            "bull_case": "Liquidity and momentum are strong.",
            "bear_case": "Contract still has mint risk.",
            "key_tension": "Momentum versus contract trust.",
        }
        manager_result = {
            "verdict": "BUY",
            "confidence": 0.82,
            "recommended_action": "Start with a small position.",
            "risks": ["Mintable contract"],
        }

        _zero_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        with patch.object(self.service, "_run_analysts", new=AsyncMock(return_value=(analyst_result, _zero_usage))), patch.object(
            self.service, "_run_debate", new=AsyncMock(return_value=(debate_result, _zero_usage))
        ), patch.object(self.service, "_run_research_manager", new=AsyncMock(return_value=(manager_result, _zero_usage))):
            result = await self.service.analyze(self.launch_id)

        self.assertEqual(result["launch_id"], self.launch_id)
        self.assertEqual(result["verdict"], "BUY")
        self.assertFalse(result["cached"])
        self.assertEqual(result["prompt_version"], PROMPT_VERSION)

        with self.db.get_session() as session:
            row = session.query(CryptoLaunchAiSummary).filter_by(launch_id=self.launch_id).one()

        self.assertEqual(row.snapshot_id, self.snapshot_id)
        self.assertEqual(row.verdict, "BUY")
        self.assertEqual(row.model_used, "test-deep-model")
        self.assertEqual(json.loads(row.risks), ["Mintable contract"])
        self.assertEqual(row.prompt_version, PROMPT_VERSION)
        self.assertIsNotNone(row.analyzed_at)

    async def test_analyze_returns_cached_summary_on_second_call_within_ttl(self):
        analyst_result = {
            "market": {"assessment": "Strong liquidity", "signal": "bullish", "confidence": 0.9},
            "security": {"assessment": "Moderate risk", "signal": "safe", "confidence": 0.8},
            "social": {"assessment": "Growing attention", "signal": "strong", "confidence": 0.7},
            "technical": {"assessment": "Uptrend", "signal": "bullish", "confidence": 0.75},
        }
        debate_result = {
            "bull_case": "Liquidity and momentum are strong.",
            "bear_case": "Contract still has mint risk.",
            "key_tension": "Momentum versus contract trust.",
        }
        manager_result = {
            "verdict": "BUY",
            "confidence": 0.82,
            "recommended_action": "Start with a small position.",
            "risks": ["Mintable contract"],
        }

        _zero_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        with patch.object(self.service, "_run_analysts", new=AsyncMock(return_value=(analyst_result, _zero_usage))) as mock_analysts, patch.object(
            self.service, "_run_debate", new=AsyncMock(return_value=(debate_result, _zero_usage))
        ), patch.object(self.service, "_run_research_manager", new=AsyncMock(return_value=(manager_result, _zero_usage))):
            first = await self.service.analyze(self.launch_id)
            second = await self.service.analyze(self.launch_id)

        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(first["verdict"], second["verdict"])
        self.assertEqual(mock_analysts.await_count, 1)

        with self.db.get_session() as session:
            rows = session.query(CryptoLaunchAiSummary).filter_by(launch_id=self.launch_id).all()

        self.assertEqual(len(rows), 1)

    async def test_call_llm_tracks_usage_with_crypto_ai_call_type(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"signal": "bullish"}'))],
            usage=SimpleNamespace(prompt_tokens=21, completion_tokens=8, total_tokens=29),
        )

        with patch("src.services.crypto_ai_service.litellm.acompletion", new=AsyncMock(return_value=response)), patch(
            "src.services.crypto_ai_service.persist_llm_usage"
        ) as mock_persist:
            result, usage = await self.service._call_llm("usage test", "tracked-model")

        self.assertEqual(result, {"signal": "bullish"})
        self.assertEqual(usage, {"prompt_tokens": 21, "completion_tokens": 8, "total_tokens": 29})
        mock_persist.assert_called_once_with(
            usage={"prompt_tokens": 21, "completion_tokens": 8, "total_tokens": 29},
            model="tracked-model",
            call_type="crypto_ai",
        )

    async def test_apply_risk_gate_forces_avoid_on_honeypot(self):
        data = self.service._gather_launch_data(self.launch_id)
        data["is_honeypot"] = True
        manager = {
            "verdict": "BUY",
            "confidence": 0.61,
            "recommended_action": "Consider entry.",
            "risks": ["Tax structure needs review"],
        }
        debate = {"bull_case": "Momentum strong", "bear_case": "Contract risk", "key_tension": "security"}

        result = self.service._apply_risk_gate(data, manager, debate)

        self.assertEqual(result["verdict"], "AVOID")
        self.assertGreaterEqual(result["confidence"], 0.95)
        self.assertEqual(result["recommended_action"], "Do not trade. Honeypot contract detected.")
        self.assertIn("HONEYPOT DETECTED", result["risks"][0])

    async def test_apply_risk_gate_overrides_buy_when_risk_score_is_extreme(self):
        data = self.service._gather_launch_data(self.launch_id)
        data["risk_score"] = 80
        manager = {
            "verdict": "BUY",
            "confidence": 0.73,
            "recommended_action": "Take a starter position.",
            "risks": ["Concentrated holders"],
        }
        debate = {"bull_case": "Momentum strong", "bear_case": "Concentration risk", "key_tension": "risk"}

        result = self.service._apply_risk_gate(data, manager, debate)

        self.assertEqual(result["verdict"], "AVOID")
        self.assertEqual(result["recommended_action"], "Risk score 80/100 meets or exceeds threshold 80/100. Avoid this token.")
        self.assertIn("Critical risk score (80/100)", result["risks"][0])

    async def test_apply_risk_gate_overrides_hold_when_risk_score_is_extreme(self):
        data = self.service._gather_launch_data(self.launch_id)
        data["risk_score"] = 85
        manager = {
            "verdict": "HOLD",
            "confidence": 0.65,
            "recommended_action": "Wait for confirmation.",
            "risks": ["Concentrated holders"],
        }
        debate = {"bull_case": "Some momentum", "bear_case": "High risk", "key_tension": "risk"}

        result = self.service._apply_risk_gate(data, manager, debate)

        self.assertEqual(result["verdict"], "AVOID")
        self.assertIn("Critical risk score (85/100)", result["risks"][0])
        self.assertLess(result["confidence"], 0.65)

    async def test_apply_risk_gate_preserves_avoid_verdict_at_extreme_risk(self):
        data = self.service._gather_launch_data(self.launch_id)
        data["risk_score"] = 90
        manager = {
            "verdict": "AVOID",
            "confidence": 0.95,
            "recommended_action": "Do not buy.",
            "risks": ["Very risky"],
        }
        debate = {"bull_case": "None", "bear_case": "Extreme risk", "key_tension": "risk"}

        result = self.service._apply_risk_gate(data, manager, debate)

        self.assertEqual(result["verdict"], "AVOID")
        self.assertNotIn("Critical risk score", result["risks"][0] if result["risks"] else "")

    async def test_analyze_returns_error_for_nonexistent_launch(self):
        result = await self.service.analyze(99999)

        self.assertEqual(result["error"], "Launch not found")
        self.assertEqual(result["launch_id"], 99999)

    async def test_run_debate_fallback_on_llm_failure(self):
        data = self.service._gather_launch_data(self.launch_id)
        analysts = {
            "market": {"assessment": "Strong liquidity", "signal": "bullish", "confidence": 0.9},
            "security": {"assessment": "Moderate risk", "signal": "safe", "confidence": 0.8},
            "social": {"assessment": "Growing attention", "signal": "strong", "confidence": 0.7},
            "technical": {"assessment": "Uptrend", "signal": "bullish", "confidence": 0.75},
        }

        with patch.object(self.service, "_call_llm", new=AsyncMock(side_effect=RuntimeError("debate LLM down"))):
            result, usage = await self.service._run_debate(data, analysts, "test-model")

        self.assertIn("bull_case", result)
        self.assertIn("bear_case", result)
        self.assertIn("key_tension", result)
        self.assertIn("Synthesized from analyst signals", result["bull_case"])
        self.assertIn("Debate stage failed", result["key_tension"])
        self.assertEqual(usage["prompt_tokens"], 0)
        self.assertEqual(usage["total_tokens"], 0)

    async def test_run_research_manager_fallback_on_llm_failure(self):
        data = self.service._gather_launch_data(self.launch_id)
        debate = {"bull_case": "Good momentum", "bear_case": "Some risk", "key_tension": "momentum vs risk"}

        with patch.object(self.service, "_call_llm", new=AsyncMock(side_effect=RuntimeError("manager LLM down"))):
            result, usage = await self.service._run_research_manager(data, debate, "test-model")

        self.assertEqual(result["verdict"], "HOLD")
        self.assertLessEqual(result["confidence"], 0.4)
        self.assertIn("risks", result)
        self.assertEqual(usage["prompt_tokens"], 0)
        self.assertEqual(usage["total_tokens"], 0)

    async def test_resolve_model_falls_back_to_litellm_model_when_tier_empty(self):
        empty_config = SimpleNamespace(
            crypto_ai_enrichment_enabled=True,
            crypto_ai_quick_model="",
            crypto_ai_deep_model="",
            crypto_ai_cache_ttl_sec=21600,
            litellm_model="global-fallback-model",
        )
        service = CryptoAiService(config=empty_config, db_manager=self.db)

        quick_model = service._resolve_model("quick")
        deep_model = service._resolve_model("deep")

        self.assertEqual(quick_model, "global-fallback-model")
        self.assertEqual(deep_model, "global-fallback-model")


    async def test_persisted_summary_has_aggregated_token_fields(self):
        """Task 3: token fields on CryptoLaunchAiSummary reflect totals."""
        analyst_result = {
            "market": {"assessment": "ok", "signal": "bullish", "confidence": 0.8},
            "security": {"assessment": "ok", "signal": "safe", "confidence": 0.7},
            "social": {"assessment": "ok", "signal": "strong", "confidence": 0.6},
            "technical": {"assessment": "ok", "signal": "bullish", "confidence": 0.7},
        }
        debate_result = {
            "bull_case": "Strong.",
            "bear_case": "Risky.",
            "key_tension": "momentum vs risk.",
        }
        manager_result = {
            "verdict": "BUY",
            "confidence": 0.75,
            "recommended_action": "Enter now.",
            "risks": ["Contract risk"],
        }

        analyst_usage = {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140}
        debate_usage = {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}
        manager_usage = {"prompt_tokens": 30, "completion_tokens": 15, "total_tokens": 45}

        with patch.object(self.service, "_run_analysts", new=AsyncMock(return_value=(analyst_result, analyst_usage))), \
             patch.object(self.service, "_run_debate", new=AsyncMock(return_value=(debate_result, debate_usage))), \
             patch.object(self.service, "_run_research_manager", new=AsyncMock(return_value=(manager_result, manager_usage))):
            result = await self.service.analyze(self.launch_id)

        self.assertFalse(result["cached"])
        self.assertEqual(result["verdict"], "BUY")

        with self.db.get_session() as session:
            row = session.query(CryptoLaunchAiSummary).filter_by(launch_id=self.launch_id).one()

        self.assertEqual(row.prompt_tokens, 180)    # 100 + 50 + 30
        self.assertEqual(row.completion_tokens, 75)  # 40 + 20 + 15
        self.assertEqual(row.total_tokens, 255)      # 140 + 70 + 45

    async def test_prompt_version_from_config_v2(self):
        """Task 3: prompt_version stored in DB matches config value."""
        v2_config = SimpleNamespace(
            crypto_ai_enrichment_enabled=True,
            crypto_ai_quick_model="test-quick-model",
            crypto_ai_deep_model="test-deep-model",
            crypto_ai_cache_ttl_sec=21600,
            crypto_ai_prompt_version="v2",
            litellm_model="fallback-model",
        )
        service = CryptoAiService(config=v2_config, db_manager=self.db)

        analyst_result = {
            "market": {"assessment": "ok", "signal": "bullish", "confidence": 0.8},
            "security": {"assessment": "ok", "signal": "safe", "confidence": 0.7},
            "social": {"assessment": "ok", "signal": "strong", "confidence": 0.6},
            "technical": {"assessment": "ok", "signal": "bullish", "confidence": 0.7},
        }
        debate_result = {
            "bull_case": "Strong.",
            "bear_case": "Risky.",
            "key_tension": "momentum vs risk.",
        }
        manager_result = {
            "verdict": "HOLD",
            "confidence": 0.55,
            "recommended_action": "Wait.",
            "risks": ["Uncertain"],
        }

        _zero_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        with patch.object(service, "_run_analysts", new=AsyncMock(return_value=(analyst_result, _zero_usage))), \
             patch.object(service, "_run_debate", new=AsyncMock(return_value=(debate_result, _zero_usage))), \
             patch.object(service, "_run_research_manager", new=AsyncMock(return_value=(manager_result, _zero_usage))):
            result = await service.analyze(self.launch_id)

        self.assertEqual(result["prompt_version"], "v2")

        with self.db.get_session() as session:
            row = session.query(CryptoLaunchAiSummary).filter_by(launch_id=self.launch_id).one()

        self.assertEqual(row.prompt_version, "v2")


if __name__ == "__main__":
    unittest.main()
