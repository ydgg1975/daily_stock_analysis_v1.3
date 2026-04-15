# -*- coding: utf-8 -*-
"""Integration tests for portfolio API endpoints (P0 PR1 scope)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

# Keep this test runnable when optional LLM runtime deps are not installed.
try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.services.portfolio_ibkr_sync_service import PortfolioIbkrSyncError
from src.services.portfolio_service import PortfolioBusyError
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class PortfolioApiTestCase(unittest.TestCase):
    """Portfolio API contract tests for account/events/snapshot."""

    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "portfolio_api_test.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=false",
                    f"DATABASE_PATH={self.db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()
        app = create_app(static_dir=self.data_dir / "empty-static")
        self.client = TestClient(app)
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _save_close(self, symbol: str, on_date: date, close: float) -> None:
        df = pd.DataFrame(
            [
                {
                    "date": on_date,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1.0,
                    "amount": close,
                    "pct_chg": 0.0,
                }
            ]
        )
        self.db.save_daily_data(df, code=symbol, data_source="portfolio-api-test")

    @staticmethod
    def _ibkr_flex_xml_bytes() -> bytes:
        xml_text = """<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements>
  <FlexStatement accountId="U1234567" fromDate="2026-01-01" toDate="2026-01-31" currency="USD">
    <Trades>
      <Trade assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" tradeDate="2026-01-03" buySell="BUY" quantity="10" tradePrice="150" ibCommission="1.25" taxes="0" ibExecID="AAPL-1" description="AAPL BUY"/>
    </Trades>
    <CashTransactions>
      <CashTransaction reportDate="2026-01-02" currency="USD" amount="5000" description="Deposit"/>
    </CashTransactions>
  </FlexStatement>
</FlexStatements>
"""
        return xml_text.encode("utf-8")

    def test_account_event_snapshot_flow(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        list_resp = self.client.get("/api/v1/portfolio/accounts")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()["accounts"]), 1)

        cash_resp = self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": account_id,
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 10000,
                "currency": "CNY",
            },
        )
        self.assertEqual(cash_resp.status_code, 200)

        trade_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": 100,
                "price": 100,
                "fee": 0,
                "tax": 0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self.assertEqual(trade_resp.status_code, 200)
        self._save_close("600519", date(2026, 1, 3), 110.0)

        snapshot_resp = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-03"},
        )
        self.assertEqual(snapshot_resp.status_code, 200)
        payload = snapshot_resp.json()
        self.assertEqual(payload["account_count"], 1)
        self.assertEqual(payload["cost_method"], "fifo")
        account_snapshot = payload["accounts"][0]
        self.assertAlmostEqual(account_snapshot["total_cash"], 0.0, places=6)
        self.assertAlmostEqual(account_snapshot["total_market_value"], 11000.0, places=6)
        self.assertAlmostEqual(account_snapshot["total_equity"], 11000.0, places=6)

    def test_snapshot_invalid_cost_method_returns_400(self) -> None:
        resp = self.client.get("/api/v1/portfolio/snapshot", params={"cost_method": "bad"})
        self.assertEqual(resp.status_code, 400)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "validation_error")

    def test_broker_connection_api_flow(self) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Global", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        create_resp = self.client.post(
            "/api/v1/portfolio/broker-connections",
            json={
                "portfolio_account_id": account_id,
                "broker_type": "ibkr",
                "broker_name": "Interactive Brokers",
                "connection_name": "Primary IBKR",
                "broker_account_ref": "U1234567",
                "import_mode": "file",
                "status": "active",
                "sync_metadata": {"source": "flex"},
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        created = create_resp.json()
        self.assertEqual(created["portfolio_account_id"], account_id)
        self.assertEqual(created["broker_type"], "ibkr")
        self.assertEqual(created["sync_metadata"], {"source": "flex"})

        list_resp = self.client.get("/api/v1/portfolio/broker-connections")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()["connections"]), 1)
        self.assertEqual(list_resp.json()["connections"][0]["portfolio_account_name"], "Global")

        update_resp = self.client.put(
            f"/api/v1/portfolio/broker-connections/{created['id']}",
            json={
                "connection_name": "IBKR Flex",
                "status": "disabled",
                "sync_metadata": {"source": "flex", "scope": "global"},
            },
        )
        self.assertEqual(update_resp.status_code, 200)
        updated = update_resp.json()
        self.assertEqual(updated["connection_name"], "IBKR Flex")
        self.assertEqual(updated["status"], "disabled")
        self.assertEqual(updated["sync_metadata"]["scope"], "global")

        duplicate_resp = self.client.post(
            "/api/v1/portfolio/broker-connections",
            json={
                "portfolio_account_id": account_id,
                "broker_type": "ibkr",
                "connection_name": "Duplicate Ref",
                "broker_account_ref": "U1234567",
                "sync_metadata": {},
            },
        )
        self.assertEqual(duplicate_resp.status_code, 409)
        detail = duplicate_resp.json()
        self.assertEqual(detail.get("error"), "conflict")

    def test_generic_broker_import_endpoints_support_ibkr(self) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Global", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        broker_list_resp = self.client.get("/api/v1/portfolio/imports/brokers")
        self.assertEqual(broker_list_resp.status_code, 200)
        brokers = {item["broker"] for item in broker_list_resp.json()["brokers"]}
        self.assertIn("ibkr", brokers)

        parse_resp = self.client.post(
            "/api/v1/portfolio/imports/parse",
            data={"broker": "ibkr"},
            files={"file": ("ibkr-flex.xml", self._ibkr_flex_xml_bytes(), "application/xml")},
        )
        self.assertEqual(parse_resp.status_code, 200)
        parsed = parse_resp.json()
        self.assertEqual(parsed["broker"], "ibkr")
        self.assertEqual(parsed["record_count"], 1)
        self.assertEqual(parsed["cash_record_count"], 1)
        self.assertEqual(parsed["metadata"]["broker_account_ref"], "U1234567")

        commit_resp = self.client.post(
            "/api/v1/portfolio/imports/commit",
            data={"account_id": str(account_id), "broker": "ibkr", "dry_run": "false"},
            files={"file": ("ibkr-flex.xml", self._ibkr_flex_xml_bytes(), "application/xml")},
        )
        self.assertEqual(commit_resp.status_code, 200)
        committed = commit_resp.json()
        self.assertEqual(committed["inserted_count"], 1)
        self.assertEqual(committed["cash_inserted_count"], 1)
        self.assertIsNotNone(committed["broker_connection_id"])

    @patch("api.v1.endpoints.portfolio.PortfolioIbkrSyncService.sync_read_only_account_state")
    def test_ibkr_sync_endpoint_contract(self, sync_mock: MagicMock) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Global", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        sync_mock.return_value = {
            "account_id": account_id,
            "broker_connection_id": 9,
            "broker_account_ref": "U1234567",
            "connection_name": "IBKR U1234567",
            "snapshot_date": "2026-04-15",
            "synced_at": "2026-04-15T09:00:00",
            "base_currency": "USD",
            "total_cash": 5000.0,
            "total_market_value": 1600.0,
            "total_equity": 6600.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 100.0,
            "position_count": 1,
            "cash_balance_count": 1,
            "fx_stale": False,
            "snapshot_overlay_active": True,
            "used_existing_connection": False,
            "api_base_url": "https://localhost:5000/v1/api",
            "verify_ssl": False,
            "warnings": [],
        }

        resp = self.client.post(
            "/api/v1/portfolio/sync/ibkr",
            json={
                "account_id": account_id,
                "session_token": "unit-test-session",
                "api_base_url": "https://localhost:5000",
                "verify_ssl": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["broker_account_ref"], "U1234567")
        self.assertTrue(payload["snapshot_overlay_active"])
        sync_mock.assert_called_once()

    @patch("api.v1.endpoints.portfolio.PortfolioIbkrSyncService.sync_read_only_account_state")
    def test_ibkr_sync_endpoint_surfaces_structured_session_error(self, sync_mock: MagicMock) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Global", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        sync_mock.side_effect = PortfolioIbkrSyncError(
            code="ibkr_session_expired",
            message="当前 IBKR session 已失效、未授权或未连上可访问账户。",
            status_code=400,
        )

        resp = self.client.post(
            "/api/v1/portfolio/sync/ibkr",
            json={
                "account_id": account_id,
                "session_token": "expired-session",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json(),
            {
                "error": "ibkr_session_expired",
                "message": "当前 IBKR session 已失效、未授权或未连上可访问账户。",
            },
        )

    @patch("api.v1.endpoints.portfolio.PortfolioIbkrSyncService.sync_read_only_account_state")
    def test_ibkr_sync_endpoint_surfaces_mapping_conflict(self, sync_mock: MagicMock) -> None:
        account_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Global", "broker": "IBKR", "market": "us", "base_currency": "USD"},
        )
        self.assertEqual(account_resp.status_code, 200)
        account_id = account_resp.json()["id"]

        sync_mock.side_effect = PortfolioIbkrSyncError(
            code="ibkr_account_mapping_conflict",
            message="该 broker account ref 已绑定到当前用户的另一持仓账户。",
            status_code=409,
        )

        resp = self.client.post(
            "/api/v1/portfolio/sync/ibkr",
            json={
                "account_id": account_id,
                "session_token": "unit-test-session",
                "broker_account_ref": "U1234567",
            },
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["error"], "ibkr_account_mapping_conflict")

    def test_duplicate_trade_uid_returns_409(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        payload = {
            "account_id": account_id,
            "symbol": "600519",
            "trade_date": "2026-01-02",
            "side": "buy",
            "quantity": 10,
            "price": 100,
            "fee": 0,
            "tax": 0,
            "market": "cn",
            "currency": "CNY",
            "trade_uid": "dup-uid-1",
        }
        first = self.client.post("/api/v1/portfolio/trades", json=payload)
        self.assertEqual(first.status_code, 200)

        second = self.client.post("/api/v1/portfolio/trades", json=payload)
        self.assertEqual(second.status_code, 409)
        detail = second.json()
        self.assertEqual(detail.get("error"), "conflict")

    def test_oversell_trade_returns_409_with_business_error(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        buy_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": 10,
                "price": 100,
                "fee": 0,
                "tax": 0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self.assertEqual(buy_resp.status_code, 200)

        sell_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-03",
                "side": "sell",
                "quantity": 20,
                "price": 90,
                "fee": 0,
                "tax": 0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self.assertEqual(sell_resp.status_code, 409)
        detail = sell_resp.json()
        self.assertEqual(detail.get("error"), "portfolio_oversell")
        self.assertIn("Oversell detected", detail.get("message", ""))

    def test_duplicate_full_close_sell_still_returns_conflict(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        buy_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-01",
                "side": "buy",
                "quantity": 10,
                "price": 100,
                "fee": 0,
                "tax": 0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        self.assertEqual(buy_resp.status_code, 200)

        payload = {
            "account_id": account_id,
            "symbol": "600519",
            "trade_date": "2026-01-02",
            "side": "sell",
            "quantity": 10,
            "price": 90,
            "fee": 0,
            "tax": 0,
            "market": "cn",
            "currency": "CNY",
            "trade_uid": "dup-full-close-sell-1",
        }
        first_sell = self.client.post("/api/v1/portfolio/trades", json=payload)
        self.assertEqual(first_sell.status_code, 200)

        second_sell = self.client.post("/api/v1/portfolio/trades", json=payload)
        self.assertEqual(second_sell.status_code, 409)
        detail = second_sell.json()
        self.assertEqual(detail.get("error"), "conflict")
        self.assertIn("Duplicate trade_uid", detail.get("message", ""))

    def test_event_list_endpoints_and_filters(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        cash_resp = self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": account_id,
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 10000,
                "currency": "CNY",
            },
        )
        self.assertEqual(cash_resp.status_code, 200)

        trade_payload = {
            "account_id": account_id,
            "symbol": "600519",
            "side": "buy",
            "quantity": 10,
            "price": 100,
            "fee": 1,
            "tax": 0,
            "market": "cn",
            "currency": "CNY",
        }
        self.assertEqual(
            self.client.post("/api/v1/portfolio/trades", json={**trade_payload, "trade_date": "2026-01-02"}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post("/api/v1/portfolio/trades", json={**trade_payload, "trade_date": "2026-01-03"}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/portfolio/corporate-actions",
                json={
                    "account_id": account_id,
                    "symbol": "600519",
                    "effective_date": "2026-01-04",
                    "action_type": "cash_dividend",
                    "market": "cn",
                    "currency": "CNY",
                    "cash_dividend_per_share": 0.5,
                },
            ).status_code,
            200,
        )

        trades_resp = self.client.get(
            "/api/v1/portfolio/trades",
            params={"account_id": account_id, "page": 1, "page_size": 1},
        )
        self.assertEqual(trades_resp.status_code, 200)
        trades_payload = trades_resp.json()
        self.assertEqual(trades_payload["total"], 2)
        self.assertEqual(len(trades_payload["items"]), 1)
        self.assertEqual(trades_payload["items"][0]["trade_date"], "2026-01-03")

        cash_list_resp = self.client.get(
            "/api/v1/portfolio/cash-ledger",
            params={"account_id": account_id, "direction": "in"},
        )
        self.assertEqual(cash_list_resp.status_code, 200)
        cash_payload = cash_list_resp.json()
        self.assertEqual(cash_payload["total"], 1)
        self.assertEqual(cash_payload["items"][0]["direction"], "in")

        corp_list_resp = self.client.get(
            "/api/v1/portfolio/corporate-actions",
            params={"account_id": account_id, "action_type": "cash_dividend"},
        )
        self.assertEqual(corp_list_resp.status_code, 200)
        corp_payload = corp_list_resp.json()
        self.assertEqual(corp_payload["total"], 1)
        self.assertEqual(corp_payload["items"][0]["action_type"], "cash_dividend")

    def test_delete_event_endpoints_remove_records_and_allow_snapshot_recovery(self) -> None:
        create_resp = self.client.post(
            "/api/v1/portfolio/accounts",
            json={"name": "Main", "broker": "Demo", "market": "cn", "base_currency": "CNY"},
        )
        self.assertEqual(create_resp.status_code, 200)
        account_id = create_resp.json()["id"]

        cash_resp = self.client.post(
            "/api/v1/portfolio/cash-ledger",
            json={
                "account_id": account_id,
                "event_date": "2026-01-01",
                "direction": "in",
                "amount": 10000,
                "currency": "CNY",
            },
        )
        trade_resp = self.client.post(
            "/api/v1/portfolio/trades",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "trade_date": "2026-01-02",
                "side": "buy",
                "quantity": 10,
                "price": 100,
                "fee": 0,
                "tax": 0,
                "market": "cn",
                "currency": "CNY",
            },
        )
        corp_resp = self.client.post(
            "/api/v1/portfolio/corporate-actions",
            json={
                "account_id": account_id,
                "symbol": "600519",
                "effective_date": "2026-01-03",
                "action_type": "cash_dividend",
                "market": "cn",
                "currency": "CNY",
                "cash_dividend_per_share": 1.0,
            },
        )
        self.assertEqual(cash_resp.status_code, 200)
        self.assertEqual(trade_resp.status_code, 200)
        self.assertEqual(corp_resp.status_code, 200)

        self._save_close("600519", date(2026, 1, 3), 100.0)
        snapshot_before = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-03"},
        )
        self.assertEqual(snapshot_before.status_code, 200)
        self.assertEqual(snapshot_before.json()["accounts"][0]["positions"][0]["quantity"], 10.0)

        delete_trade = self.client.delete(f"/api/v1/portfolio/trades/{trade_resp.json()['id']}")
        self.assertEqual(delete_trade.status_code, 200)
        self.assertEqual(delete_trade.json()["deleted"], 1)

        snapshot_after_trade = self.client.get(
            "/api/v1/portfolio/snapshot",
            params={"account_id": account_id, "as_of": "2026-01-03"},
        )
        self.assertEqual(snapshot_after_trade.status_code, 200)
        self.assertEqual(snapshot_after_trade.json()["accounts"][0]["positions"], [])

        delete_cash = self.client.delete(f"/api/v1/portfolio/cash-ledger/{cash_resp.json()['id']}")
        self.assertEqual(delete_cash.status_code, 200)
        self.assertEqual(delete_cash.json()["deleted"], 1)

        delete_corp = self.client.delete(f"/api/v1/portfolio/corporate-actions/{corp_resp.json()['id']}")
        self.assertEqual(delete_corp.status_code, 200)
        self.assertEqual(delete_corp.json()["deleted"], 1)

        missing_trade = self.client.delete("/api/v1/portfolio/trades/999999")
        self.assertEqual(missing_trade.status_code, 404)

    def test_create_trade_busy_returns_409(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioService.record_trade",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            resp = self.client.post(
                "/api/v1/portfolio/trades",
                json={
                    "account_id": 1,
                    "symbol": "600519",
                    "trade_date": "2026-01-02",
                    "side": "buy",
                    "quantity": 10,
                    "price": 100,
                    "fee": 0,
                    "tax": 0,
                    "market": "cn",
                    "currency": "CNY",
                },
            )

        self.assertEqual(resp.status_code, 409)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "portfolio_busy")

    def test_delete_trade_busy_returns_409(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioService.delete_trade_event",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            resp = self.client.delete("/api/v1/portfolio/trades/1")

        self.assertEqual(resp.status_code, 409)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "portfolio_busy")

    def test_create_cash_ledger_busy_returns_409(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioService.record_cash_ledger",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            resp = self.client.post(
                "/api/v1/portfolio/cash-ledger",
                json={
                    "account_id": 1,
                    "event_date": "2026-01-02",
                    "direction": "in",
                    "amount": 1000,
                    "currency": "CNY",
                },
            )

        self.assertEqual(resp.status_code, 409)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "portfolio_busy")

    def test_delete_cash_ledger_busy_returns_409(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioService.delete_cash_ledger_event",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            resp = self.client.delete("/api/v1/portfolio/cash-ledger/1")

        self.assertEqual(resp.status_code, 409)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "portfolio_busy")

    def test_create_corporate_action_busy_returns_409(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioService.record_corporate_action",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            resp = self.client.post(
                "/api/v1/portfolio/corporate-actions",
                json={
                    "account_id": 1,
                    "symbol": "600519",
                    "effective_date": "2026-01-02",
                    "action_type": "split_adjustment",
                    "market": "cn",
                    "currency": "CNY",
                    "split_ratio": 2.0,
                },
            )

        self.assertEqual(resp.status_code, 409)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "portfolio_busy")

    def test_delete_corporate_action_busy_returns_409(self) -> None:
        with patch(
            "api.v1.endpoints.portfolio.PortfolioService.delete_corporate_action_event",
            side_effect=PortfolioBusyError("Portfolio ledger is busy; please retry shortly."),
        ):
            resp = self.client.delete("/api/v1/portfolio/corporate-actions/1")

        self.assertEqual(resp.status_code, 409)
        detail = resp.json()
        self.assertEqual(detail.get("error"), "portfolio_busy")

    def test_csv_broker_list_endpoint(self) -> None:
        resp = self.client.get("/api/v1/portfolio/imports/csv/brokers")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        brokers = {item["broker"] for item in payload["brokers"]}
        self.assertIn("huatai", brokers)
        self.assertIn("citic", brokers)
        self.assertIn("cmb", brokers)

    def test_event_list_invalid_page_size_returns_422(self) -> None:
        resp = self.client.get("/api/v1/portfolio/trades", params={"page_size": 101})
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
