# -*- coding: utf-8 -*-
"""Regression checks for agent evaluation fixtures."""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from src.services.chart_analysis_service import ChartAnalysisService, build_chart_analysis_report
from src.services.paper_trading_service import PaperTradingService
from src.services.portfolio_analysis_service import PortfolioAnalysisService


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "agent_eval"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class _FixturePortfolioService:
    def __init__(self, snapshot: dict, trade_events: list | None = None):
        self.snapshot = snapshot
        self.trade_events = trade_events or []

    def get_portfolio_snapshot(self, **_kwargs):
        return self.snapshot

    def list_trade_events(self, **_kwargs):
        return {
            "items": list(self.trade_events),
            "total": len(self.trade_events),
            "page": 1,
            "page_size": 100,
        }


class _FixtureRiskService:
    def __init__(self, risk_report: dict):
        self.risk_report = risk_report

    def get_risk_report(self, **_kwargs):
        return self.risk_report


def test_agent_eval_manifest_lists_existing_fixtures():
    manifest = _load_fixture("manifest.json")

    assert manifest["version"] == 1
    for item in manifest["fixtures"]:
        assert (FIXTURE_DIR / item["path"]).is_file()


def test_chart_analysis_eval_fixture_matches_expected_metadata():
    fixture = _load_fixture("chart_analysis.json")
    frame = pd.DataFrame(fixture["ohlcv"])
    expected = fixture["expected"]

    result = ChartAnalysisService().analyze(fixture["stock_code"], frame)
    report = build_chart_analysis_report(fixture["stock_code"], frame)

    assert result["status"] == expected["status"]
    assert result["metadata"]["pattern"]["name"] == expected["pattern_name"]
    assert result["metadata"]["visual_signal"] == expected["visual_signal"]
    assert result["metadata"]["support"] == expected["support"]
    assert ("svg" not in report) is expected["report_omits_svg"]


def test_paper_trading_eval_fixture_prepares_guarded_order():
    fixture = _load_fixture("paper_trading.json")
    order = dict(fixture["order"])
    order["trade_date"] = date.fromisoformat(order["trade_date"])
    expected = fixture["expected"]
    service = PaperTradingService(
        portfolio_service=_FixturePortfolioService(
            snapshot=fixture["snapshot"],
            trade_events=fixture["trade_events"],
        )
    )

    prepared = service.prepare_order(**order)

    assert prepared["status"] == expected["status"]
    assert prepared["mode"] == expected["mode"]
    assert prepared["can_execute_after_approval"] is expected["can_execute_after_approval"]
    assert [item["name"] for item in prepared["risk_checks"]] == expected["risk_check_names"]


def test_portfolio_analysis_eval_fixture_builds_report_summary():
    fixture = _load_fixture("portfolio_analysis.json")
    expected = fixture["expected"]
    service = PortfolioAnalysisService(
        portfolio_service=_FixturePortfolioService(snapshot=fixture["snapshot"]),
        risk_service=_FixtureRiskService(risk_report=fixture["risk_report"]),
    )

    analysis = service.analyze(as_of=date.fromisoformat(fixture["as_of"]))
    summary = service.build_report_summary(analysis)

    assert analysis["total_market_value"] == expected["total_market_value"]
    assert analysis["position_count"] == expected["position_count"]
    assert summary["diversification_level"] == expected["diversification_level"]
    assert summary["top_market"]["market"] == expected["top_market"]
    assert summary["top_currency"]["currency"] == expected["top_currency"]
