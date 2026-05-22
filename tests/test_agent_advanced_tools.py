# -*- coding: utf-8 -*-
"""Contract tests for advanced stock-agent tools."""

from datetime import date
from unittest.mock import patch

import pandas as pd

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.agent.factory import get_tool_registry
from src.agent.agents.technical_agent import TechnicalAgent
from src.agent.orchestrator import AgentOrchestrator
from src.agent.protocols import AgentContext, AgentOpinion
from src.agent.tools.action_tools import _handle_prepare_paper_order
from src.agent.tools.analysis_tools import _handle_generate_chart_analysis


def _sample_history() -> pd.DataFrame:
    rows = []
    for idx, close in enumerate([10, 11, 12, 11, 13, 14, 15, 16], start=1):
        rows.append(
            {
                "date": f"2026-03-{idx:02d}",
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1000 + idx * 100,
            }
        )
    return pd.DataFrame(rows)


def test_generate_chart_analysis_tool_returns_compact_metadata_by_default():
    with patch("src.services.history_loader.load_history_df", return_value=(_sample_history(), "test")):
        result = _handle_generate_chart_analysis("AAPL", days=30)

    assert result["status"] == "ok"
    assert result["source"] == "test"
    assert result["svg_omitted"] is True
    assert result["svg_length"] > 0
    assert "svg" not in result
    assert result["metadata"]["pattern"]["name"] == "five_bar_breakout"


def test_generate_chart_analysis_tool_can_include_svg():
    with patch("src.services.history_loader.load_history_df", return_value=(_sample_history(), "test")):
        result = _handle_generate_chart_analysis("AAPL", days=30, include_svg=True)

    assert result["status"] == "ok"
    assert result["svg"].startswith("<svg")


def test_generate_chart_analysis_tool_can_include_vision():
    with patch("src.services.history_loader.load_history_df", return_value=(_sample_history(), "test")), patch(
        "src.services.chart_vision_service.ChartVisionAnalysisService.analyze_chart_image",
        return_value={"status": "ok", "analysis": {"trend": "bullish"}},
    ) as vision_mock:
        result = _handle_generate_chart_analysis("AAPL", days=30, include_vision=True)

    assert result["status"] == "ok"
    assert result["vision_analysis"]["analysis"]["trend"] == "bullish"
    assert result["svg_omitted"] is True
    vision_mock.assert_called_once()


def test_generate_chart_analysis_tool_marks_vision_fallback():
    with patch("src.services.history_loader.load_history_df", return_value=(_sample_history(), "test")), patch(
        "src.services.chart_vision_service.ChartVisionAnalysisService.analyze_chart_image",
        return_value={"status": "not_configured", "reason": "Vision model is not configured."},
    ):
        result = _handle_generate_chart_analysis("AAPL", days=30, include_vision=True)

    assert result["status"] == "ok"
    assert result["metadata"]["pattern"]["name"] == "five_bar_breakout"
    assert result["vision_analysis"]["status"] == "not_configured"
    assert result["vision_fallback_used"] is True
    assert result["vision_fallback_reason"] == "Vision model is not configured."


class _FakePaperTradingService:
    def prepare_order(self, **kwargs):
        return {
            "status": "approval_required",
            "mode": "paper",
            "broker_execution": "disabled",
            "approval_token": "token",
            "order": {
                "account_id": kwargs["account_id"],
                "symbol": kwargs["symbol"],
                "side": kwargs["side"],
                "trade_date": kwargs["trade_date"].isoformat(),
            },
            "risk_checks": [],
            "can_execute_after_approval": True,
        }


def test_prepare_paper_order_tool_never_executes_real_order():
    with patch("src.services.paper_trading_service.PaperTradingService", return_value=_FakePaperTradingService()):
        result = _handle_prepare_paper_order(
            account_id=1,
            stock_code="AAPL",
            side="buy",
            quantity=10,
            price=100,
            trade_date="2026-03-15",
            market="us",
            currency="USD",
            reason="agent paper test",
        )

    assert result["status"] == "approval_required"
    assert result["broker_execution"] == "disabled"
    assert result["order"]["trade_date"] == date(2026, 3, 15).isoformat()


def test_prepare_paper_order_tool_rejects_bad_date():
    result = _handle_prepare_paper_order(
        account_id=1,
        stock_code="AAPL",
        side="buy",
        quantity=10,
        price=100,
        trade_date="2026/03/15",
    )

    assert result["error"] == "trade_date must be YYYY-MM-DD"


def test_default_registry_includes_advanced_agent_tools():
    registry = get_tool_registry()

    assert "generate_chart_analysis" in registry.list_names()
    assert "prepare_paper_order" in registry.list_names()
    assert registry.get("prepare_paper_order").category == "action"


def test_technical_agent_can_select_chart_analysis_tool():
    agent = TechnicalAgent(tool_registry=get_tool_registry(), llm_adapter=None)

    assert "generate_chart_analysis" in agent.tool_names
    assert "generate_chart_analysis" in agent.system_prompt(AgentContext(stock_code="AAPL"))


def test_analysis_map_summarizes_new_agent_tools():
    orchestrator = AgentOrchestrator(tool_registry=get_tool_registry(), llm_adapter=None)
    ctx = AgentContext(stock_code="AAPL")
    ctx.add_opinion(AgentOpinion(agent_name="technical", signal="buy", confidence=0.7, reasoning="chart confirmed"))
    ctx.add_opinion(AgentOpinion(agent_name="intel", signal="hold", confidence=0.6, reasoning="no headline risk"))
    ctx.add_opinion(AgentOpinion(agent_name="risk", signal="hold", confidence=0.6, reasoning="risk acceptable"))
    ctx.add_opinion(AgentOpinion(agent_name="decision", signal="buy", confidence=0.65, reasoning="controlled entry"))
    ctx.set_data("realtime_quote", {"price": 101})
    ctx.set_data("tool_calls_log", [
        {
            "step": 1,
            "tool": "generate_chart_analysis",
            "arguments": {"stock_code": "AAPL"},
            "success": True,
            "duration": 0.2,
        },
        {
            "step": 2,
            "tool": "get_portfolio_snapshot",
            "arguments": {"account_id": 1},
            "success": True,
            "duration": 0.1,
        },
        {
            "step": 3,
            "tool": "prepare_paper_order",
            "arguments": {"account_id": 1, "stock_code": "AAPL", "side": "buy"},
            "success": True,
            "duration": 0.1,
        },
    ])

    analysis_map = orchestrator._build_analysis_map(
        ctx,
        {"data_perspective": {"price_position": {}}, "intelligence": {}},
        {"decision_type": "buy"},
    )

    nodes = {node["id"]: node for node in analysis_map["nodes"]}
    trace = {item["tool"]: item for item in analysis_map["tool_trace"]}

    assert nodes["chart"]["status"] == "completed"
    assert nodes["portfolio"]["status"] == "completed"
    assert nodes["paper_trading"]["status"] == "completed"
    assert trace["generate_chart_analysis"]["node"] == "chart"
    assert "support/resistance" in trace["generate_chart_analysis"]["reason"]
    assert trace["get_portfolio_snapshot"]["node"] == "portfolio"
    assert trace["prepare_paper_order"]["node"] == "paper_trading"
    assert analysis_map["tool_metrics"]["total_calls"] == 3
    assert analysis_map["tool_metrics"]["success_rate"] == 1.0
    chart_metrics = {
        item["tool"]: item
        for item in analysis_map["tool_metrics"]["tools"]
    }["generate_chart_analysis"]
    assert chart_metrics["calls"] == 1
    assert chart_metrics["avg_duration"] == 0.2
    assert analysis_map["coverage"]["required_ratio"] == 1.0
