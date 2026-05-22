# -*- coding: utf-8 -*-
"""Tests for guarded paper trading preparation and execution."""

from datetime import date

import pytest

from src.services.paper_trading_service import PaperTradingLimits, PaperTradingService


class _FakePortfolioService:
    def __init__(self):
        self.recorded = []
        self.trade_events = []

    def get_portfolio_snapshot(self, **_kwargs):
        return {
            "total_equity": 100000.0,
            "total_market_value": 60000.0,
            "accounts": [
                {
                    "account_id": 1,
                    "unrealized_pnl": -1000.0,
                    "positions": [
                        {
                            "symbol": "AAPL",
                            "market_value_base": 20000.0,
                            "total_cost": 21000.0,
                            "last_price": 110.0,
                            "price_available": True,
                        }
                    ],
                }
            ],
        }

    def list_trade_events(self, **_kwargs):
        return {"items": list(self.trade_events), "total": len(self.trade_events), "page": 1, "page_size": 100}

    def record_trade(self, **kwargs):
        self.recorded.append(kwargs)
        return {"id": 77}


def test_prepare_order_requires_approval_and_reports_risk_checks():
    service = PaperTradingService(portfolio_service=_FakePortfolioService())

    prepared = service.prepare_order(
        account_id=1,
        symbol="MSFT",
        side="buy",
        quantity=10,
        price=100,
        trade_date=date(2026, 3, 15),
        market="us",
        currency="USD",
        reason="test thesis",
    )

    assert prepared["status"] == "approval_required"
    assert prepared["mode"] == "paper"
    assert prepared["broker_execution"] == "disabled"
    assert prepared["can_execute_after_approval"] is True
    assert prepared["approval_token"]
    assert [item["name"] for item in prepared["risk_checks"]] == [
        "max_order_value_pct",
        "max_position_weight_pct",
        "daily_trade_limit",
        "max_loss_pct",
    ]


def test_prepare_order_blocks_when_position_weight_exceeds_limit():
    service = PaperTradingService(
        portfolio_service=_FakePortfolioService(),
        limits=PaperTradingLimits(max_position_weight_pct=25.0),
    )

    prepared = service.prepare_order(
        account_id=1,
        symbol="AAPL",
        side="buy",
        quantity=100,
        price=100,
        trade_date=date(2026, 3, 15),
    )

    assert prepared["can_execute_after_approval"] is False
    assert any(item["name"] == "max_position_weight_pct" and item["level"] == "block" for item in prepared["risk_checks"])


def test_execute_approved_order_records_paper_trade_only_after_approval():
    fake = _FakePortfolioService()
    service = PaperTradingService(portfolio_service=fake)
    prepared = service.prepare_order(
        account_id=1,
        symbol="MSFT",
        side="buy",
        quantity=10,
        price=100,
        trade_date=date(2026, 3, 15),
        reason="breakout",
    )

    rejected = service.execute_approved_order(
        prepared_order=prepared,
        approval_token=prepared["approval_token"],
        approved=False,
    )
    assert rejected["status"] == "rejected"
    assert fake.recorded == []

    executed = service.execute_approved_order(
        prepared_order=prepared,
        approval_token=prepared["approval_token"],
        approved=True,
    )

    assert executed["status"] == "executed"
    assert executed["trade_id"] == 77
    assert fake.recorded[0]["trade_uid"].startswith("paper:")
    assert "paper_trade; reason=breakout" in fake.recorded[0]["note"]


def test_execute_rejects_token_mismatch():
    service = PaperTradingService(portfolio_service=_FakePortfolioService())
    prepared = service.prepare_order(
        account_id=1,
        symbol="MSFT",
        side="buy",
        quantity=10,
        price=100,
        trade_date=date(2026, 3, 15),
    )

    with pytest.raises(ValueError, match="approval_token"):
        service.execute_approved_order(
            prepared_order=prepared,
            approval_token="bad-token",
            approved=True,
        )


def test_get_performance_tracks_open_and_closed_paper_trades(monkeypatch):
    fake = _FakePortfolioService()
    fake.trade_events = [
        {
            "id": 1,
            "account_id": 1,
            "trade_uid": "paper:buy-aapl",
            "symbol": "AAPL",
            "trade_date": "2026-03-01",
            "side": "buy",
            "quantity": 10,
            "price": 100,
            "note": "paper_trade; reason=breakout",
        },
        {
            "id": 2,
            "account_id": 1,
            "trade_uid": "paper:sell-aapl",
            "symbol": "AAPL",
            "trade_date": "2026-03-06",
            "side": "sell",
            "quantity": 4,
            "price": 120,
            "note": "paper_trade; reason=trim",
        },
        {
            "id": 3,
            "account_id": 1,
            "trade_uid": "manual",
            "symbol": "MSFT",
            "trade_date": "2026-03-02",
            "side": "buy",
            "quantity": 1,
            "price": 10,
            "note": "manual",
        },
    ]

    class _Backtest:
        def get_global_summary(self, eval_window_days=None):
            return {
                "scope": "overall",
                "eval_window_days": eval_window_days,
                "win_rate_pct": 55.0,
                "avg_simulated_return_pct": 3.5,
                "total_evaluations": 20,
            }

    monkeypatch.setattr("src.services.backtest_service.BacktestService", lambda: _Backtest())
    service = PaperTradingService(portfolio_service=fake)

    result = service.get_performance(account_id=1, as_of=date(2026, 3, 10), eval_window_days=10)

    assert result["total_trades"] == 1
    assert result["open_trades"] == 1
    assert result["win_count"] == 1
    item = result["items"][0]
    assert item["symbol"] == "AAPL"
    assert item["remaining_quantity"] == 6
    assert item["holding_days"] == 9
    assert item["return_pct"] == 14.0
    assert result["backtest_comparison"]["avg_return_pct"] == 3.5
