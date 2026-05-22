# -*- coding: utf-8 -*-
"""Tests for portfolio exposure and rebalance analysis."""

from datetime import date

from src.services.portfolio_analysis_service import PortfolioAnalysisService


class _FakePortfolioService:
    def get_portfolio_snapshot(self, **_kwargs):
        return {
            "as_of": "2026-03-15",
            "cost_method": "fifo",
            "currency": "CNY",
            "total_market_value": 100000.0,
            "accounts": [
                {
                    "account_id": 1,
                    "market": "cn",
                    "base_currency": "CNY",
                    "positions": [
                        {
                            "symbol": "600519",
                            "market": "cn",
                            "valuation_currency": "CNY",
                            "market_value_base": 42000.0,
                        },
                        {
                            "symbol": "AAPL",
                            "market": "us",
                            "valuation_currency": "USD",
                            "market_value_base": 28000.0,
                        },
                        {
                            "symbol": "00700",
                            "market": "hk",
                            "valuation_currency": "HKD",
                            "market_value_base": 30000.0,
                        },
                    ],
                }
            ],
        }


class _FakeRiskService:
    def get_risk_report(self, **_kwargs):
        return {
            "concentration": {
                "alert": True,
                "top_weight_pct": 42.0,
                "top_positions": [{"symbol": "600519", "weight_pct": 42.0}],
            },
            "sector_concentration": {
                "alert": True,
                "top_weight_pct": 58.0,
                "top_sectors": [{"sector": "Consumer", "weight_pct": 58.0}],
            },
            "stop_loss": {"near_alert": True},
        }


def test_portfolio_analysis_builds_exposure_and_suggestions():
    service = PortfolioAnalysisService(
        portfolio_service=_FakePortfolioService(),
        risk_service=_FakeRiskService(),
    )

    result = service.analyze(as_of=date(2026, 3, 15))

    assert result["total_market_value"] == 100000.0
    assert result["position_count"] == 3
    assert result["exposure"]["markets"][0] == {
        "market": "cn",
        "market_value_base": 42000.0,
        "weight_pct": 42.0,
    }
    assert result["exposure"]["currencies"][0]["currency"] == "CNY"
    assert result["diversification"]["level"] == "concentrated"
    assert "Top position exceeds concentration threshold." in result["diversification"]["warnings"]
    assert any("600519" in item for item in result["rebalance_suggestions"])
    assert any("Consumer" in item for item in result["rebalance_suggestions"])


def test_portfolio_analysis_reports_candidate_impact():
    service = PortfolioAnalysisService(
        portfolio_service=_FakePortfolioService(),
        risk_service=_FakeRiskService(),
    )

    result = service.analyze(
        as_of=date(2026, 3, 15),
        candidate={
            "symbol": "MSFT",
            "market": "us",
            "valuation_currency": "USD",
            "market_value_base": 25000.0,
        },
    )

    impact = result["candidate_impact"]
    assert impact["symbol"] == "MSFT"
    assert impact["projected_total_market_value"] == 125000.0
    assert impact["projected_weight_pct"] == 20.0
    assert impact["concentration_alert"] is True


def test_portfolio_analysis_builds_report_summary():
    service = PortfolioAnalysisService(
        portfolio_service=_FakePortfolioService(),
        risk_service=_FakeRiskService(),
    )

    analysis = service.analyze(as_of=date(2026, 3, 15))
    summary = service.build_report_summary(analysis)

    assert summary["status"] == "ok"
    assert summary["diversification_level"] == "concentrated"
    assert summary["top_market"]["market"] == "cn"
    assert summary["top_currency"]["currency"] == "CNY"
    assert summary["rebalance_suggestions"]
