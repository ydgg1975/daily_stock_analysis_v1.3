# -*- coding: utf-8 -*-
"""Tests for read-only IBKR API sync foundation."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from src.config import Config
from src.services.portfolio_ibkr_sync_service import (
    IbkrHttpResult,
    PortfolioIbkrSyncError,
    PortfolioIbkrSyncService,
)
from src.services.portfolio_import_service import PortfolioImportService
from src.services.portfolio_service import PortfolioService
from src.storage import DatabaseManager


class FakeIbkrTransport:
    """Deterministic transport for service-level sync tests."""

    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, *, headers, params, verify, timeout) -> IbkrHttpResult:
        from urllib.parse import urlparse

        path = urlparse(url).path
        self.calls.append(path)
        value = self.responses.get(path)
        if value is None:
            return IbkrHttpResult(status_code=404, payload={"message": f"not mocked: {path}"})
        if isinstance(value, tuple):
            status_code, payload = value
            return IbkrHttpResult(status_code=int(status_code), payload=payload)
        return IbkrHttpResult(status_code=200, payload=value)


class PortfolioIbkrSyncServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temp_dir.name) / ".env"
        self.db_path = Path(self.temp_dir.name) / "portfolio_ibkr_sync.db"
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

        self.db = DatabaseManager.get_instance()
        self.service = PortfolioService()
        self.import_service = PortfolioImportService(portfolio_service=self.service)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

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
        self.db.save_daily_data(df, code=symbol, data_source="portfolio-ibkr-sync-test")

    def _build_transport(self, *, account_ref: str = "U1234567", multi_market: bool = False) -> FakeIbkrTransport:
        positions = [
            {
                "conid": "265598",
                "contractDesc": "AAPL",
                "position": "10",
                "avgCost": "150",
                "mktPrice": "160",
                "mktValue": "1600",
                "unrealizedPnl": "100",
                "currency": "USD",
                "assetClass": "STK",
                "listingExchange": "NASDAQ",
                "countryCode": "US",
            }
        ]
        if multi_market:
            positions.append(
                {
                    "conid": "700",
                    "contractDesc": "700",
                    "position": "100",
                    "avgCost": "320",
                    "mktPrice": "330",
                    "mktValue": "33000",
                    "unrealizedPnl": "1000",
                    "currency": "HKD",
                    "assetClass": "STK",
                    "listingExchange": "SEHK",
                    "countryCode": "HK",
                }
            )
        responses = {
            "/v1/api/portfolio/accounts": [
                {"accountId": account_ref, "displayName": "Primary IBKR", "currency": "USD"}
            ],
            f"/v1/api/portfolio/{account_ref}/summary": {
                "totalcashvalue": {"amount": "5000"},
                "stockmarketvalue": {"amount": "5824" if multi_market else "1600"},
                "netliquidation": {"amount": "10824" if multi_market else "6600"},
                "unrealizedpnl": {"amount": "228" if multi_market else "100"},
            },
            f"/v1/api/portfolio/{account_ref}/ledger": {"USD": {"cashbalance": "5000"}},
            f"/v1/api/portfolio/{account_ref}/positions/0": positions,
            f"/v1/api/portfolio/{account_ref}/positions/1": [],
        }
        return FakeIbkrTransport(responses)

    def test_read_only_sync_creates_user_owned_connection_and_snapshot_overlay(self) -> None:
        account = self.service.create_account(name="IBKR Main", broker="IBKR", market="us", base_currency="USD")
        transport = self._build_transport()
        sync_service = PortfolioIbkrSyncService(portfolio_service=self.service, transport=transport)

        result = sync_service.sync_read_only_account_state(
            account_id=account["id"],
            session_token="unit-test-session",
            api_base_url="https://localhost:5000",
        )

        self.assertEqual(result["broker_account_ref"], "U1234567")
        self.assertEqual(result["position_count"], 1)
        self.assertFalse(result["verify_ssl"])
        connections = self.service.list_broker_connections(portfolio_account_id=account["id"], broker_type="ibkr")
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0]["import_mode"], "api")
        self.assertEqual(connections[0]["broker_account_ref"], "U1234567")
        self.assertEqual(
            connections[0]["sync_metadata"]["ibkr_api"]["api_base_url"],
            "https://localhost:5000/v1/api",
        )

        snapshot_date = date.fromisoformat(result["snapshot_date"])
        snapshot = self.service.get_portfolio_snapshot(
            account_id=account["id"],
            as_of=snapshot_date,
            cost_method="fifo",
        )
        acc = snapshot["accounts"][0]
        self.assertEqual(acc["positions"][0]["symbol"], "AAPL")
        self.assertAlmostEqual(acc["positions"][0]["quantity"], 10.0, places=6)
        self.assertAlmostEqual(acc["total_cash"], 5000.0, places=6)
        self.assertAlmostEqual(acc["total_market_value"], 1600.0, places=6)
        self.assertAlmostEqual(acc["total_equity"], 6600.0, places=6)

        trades = self.service.list_trade_events(account_id=account["id"], page=1, page_size=20)
        self.assertEqual(trades["total"], 0)

    def test_read_only_sync_requires_transient_session_token(self) -> None:
        account = self.service.create_account(name="IBKR Main", broker="IBKR", market="us", base_currency="USD")
        sync_service = PortfolioIbkrSyncService(portfolio_service=self.service, transport=self._build_transport())

        with self.assertRaises(PortfolioIbkrSyncError) as ctx:
            sync_service.sync_read_only_account_state(
                account_id=account["id"],
                session_token="   ",
            )

        self.assertEqual(ctx.exception.code, "ibkr_session_required")

    def test_read_only_sync_surfaces_expired_session_as_safe_error(self) -> None:
        account = self.service.create_account(name="IBKR Main", broker="IBKR", market="us", base_currency="USD")
        transport = FakeIbkrTransport(
            {
                "/v1/api/portfolio/accounts": (401, {"message": "session expired"}),
            }
        )
        sync_service = PortfolioIbkrSyncService(portfolio_service=self.service, transport=transport)

        with self.assertRaises(PortfolioIbkrSyncError) as ctx:
            sync_service.sync_read_only_account_state(
                account_id=account["id"],
                session_token="unit-test-session",
            )

        self.assertEqual(ctx.exception.code, "ibkr_session_expired")
        self.assertEqual(
            self.service.list_broker_connections(portfolio_account_id=account["id"], broker_type="ibkr"),
            [],
        )

    def test_read_only_sync_rejects_accounts_payload_without_supported_identifier(self) -> None:
        account = self.service.create_account(name="IBKR Main", broker="IBKR", market="us", base_currency="USD")
        transport = FakeIbkrTransport(
            {
                "/v1/api/portfolio/accounts": [
                    {"displayName": "Primary Only", "currency": "USD"},
                ],
            }
        )
        sync_service = PortfolioIbkrSyncService(portfolio_service=self.service, transport=transport)

        with self.assertRaises(PortfolioIbkrSyncError) as ctx:
            sync_service.sync_read_only_account_state(
                account_id=account["id"],
                session_token="unit-test-session",
            )

        self.assertEqual(ctx.exception.code, "ibkr_account_identifier_invalid")

    def test_read_only_sync_treats_empty_positions_as_valid_current_state(self) -> None:
        account = self.service.create_account(name="IBKR Cash Only", broker="IBKR", market="us", base_currency="USD")
        transport = FakeIbkrTransport(
            {
                "/v1/api/portfolio/accounts": [
                    {"accountId": "U1234567", "displayName": "Primary IBKR", "currency": "USD"}
                ],
                "/v1/api/portfolio/U1234567/summary": {
                    "totalcashvalue": {"amount": "5000"},
                    "stockmarketvalue": {"amount": "0"},
                    "netliquidation": {"amount": "5000"},
                },
                "/v1/api/portfolio/U1234567/ledger": {"USD": {"cashbalance": "5000"}},
                "/v1/api/portfolio/U1234567/positions/0": [],
            }
        )
        sync_service = PortfolioIbkrSyncService(portfolio_service=self.service, transport=transport)

        result = sync_service.sync_read_only_account_state(
            account_id=account["id"],
            session_token="unit-test-session",
        )

        self.assertEqual(result["position_count"], 0)
        self.assertIn("未返回持仓", " ".join(result["warnings"]))
        snapshot = self.service.get_portfolio_snapshot(
            account_id=account["id"],
            as_of=date.fromisoformat(result["snapshot_date"]),
            cost_method="fifo",
        )
        self.assertAlmostEqual(snapshot["accounts"][0]["total_cash"], 5000.0, places=6)
        self.assertEqual(snapshot["accounts"][0]["positions"], [])

    def test_read_only_sync_coexists_with_existing_ibkr_file_import(self) -> None:
        account = self.service.create_account(name="IBKR History", broker="IBKR", market="us", base_currency="USD")
        parsed = self.import_service.parse_import_file(broker="ibkr", content=self._ibkr_flex_xml_bytes())
        self.import_service.commit_import_records(
            account_id=account["id"],
            broker="ibkr",
            parsed_payload=parsed,
            dry_run=False,
        )
        self.service.repo.save_fx_rate(
            from_currency="HKD",
            to_currency="USD",
            rate_date=date.today(),
            rate=0.128,
            source="unit-test",
            is_stale=False,
        )

        transport = self._build_transport(multi_market=True)
        sync_service = PortfolioIbkrSyncService(portfolio_service=self.service, transport=transport)
        result = sync_service.sync_read_only_account_state(
            account_id=account["id"],
            session_token="unit-test-session",
            broker_account_ref="U1234567",
            api_base_url="https://localhost:5000/v1/api",
        )

        self.assertTrue(result["used_existing_connection"])
        connections = self.service.list_broker_connections(portfolio_account_id=account["id"], broker_type="ibkr")
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0]["import_mode"], "file")
        self.assertIn("last_statement_from", connections[0]["sync_metadata"])
        self.assertIn("ibkr_api", connections[0]["sync_metadata"])

        snapshot_date = date.fromisoformat(result["snapshot_date"])
        current_snapshot = self.service.get_portfolio_snapshot(
            account_id=account["id"],
            as_of=snapshot_date,
            cost_method="fifo",
        )
        current_positions = current_snapshot["accounts"][0]["positions"]
        self.assertEqual({item["symbol"] for item in current_positions}, {"AAPL", "HK00700"})

        historical_snapshot = self.service.get_portfolio_snapshot(
            account_id=account["id"],
            as_of=date(2026, 1, 31),
            cost_method="fifo",
        )
        historical_positions = historical_snapshot["accounts"][0]["positions"]
        self.assertEqual([item["symbol"] for item in historical_positions], ["AAPL"])

        account_after_sync = self.service.get_account(account["id"], include_inactive=True)
        self.assertEqual(account_after_sync["market"], "global")

    def test_read_only_sync_rejects_duplicate_remote_account_link_on_another_portfolio_account(self) -> None:
        account_a = self.service.create_account(name="A", broker="IBKR", market="us", base_currency="USD")
        account_b = self.service.create_account(name="B", broker="IBKR", market="us", base_currency="USD")
        transport = self._build_transport()
        sync_service = PortfolioIbkrSyncService(portfolio_service=self.service, transport=transport)

        sync_service.sync_read_only_account_state(
            account_id=account_a["id"],
            session_token="unit-test-session",
        )
        with self.assertRaises(PortfolioIbkrSyncError) as ctx:
            sync_service.sync_read_only_account_state(
                account_id=account_b["id"],
                session_token="unit-test-session",
                broker_account_ref="U1234567",
            )
        self.assertEqual(ctx.exception.code, "ibkr_account_mapping_conflict")

    def test_read_only_sync_requires_explicit_account_ref_when_session_has_multiple_accounts(self) -> None:
        account = self.service.create_account(name="Need Ref", broker="IBKR", market="us", base_currency="USD")
        transport = FakeIbkrTransport(
            {
                "/v1/api/portfolio/accounts": [
                    {"accountId": "U1234567", "displayName": "Primary", "currency": "USD"},
                    {"accountId": "U7654321", "displayName": "Secondary", "currency": "USD"},
                ]
            }
        )
        sync_service = PortfolioIbkrSyncService(portfolio_service=self.service, transport=transport)

        with self.assertRaises(PortfolioIbkrSyncError) as ctx:
            sync_service.sync_read_only_account_state(
                account_id=account["id"],
                session_token="unit-test-session",
            )
        self.assertEqual(ctx.exception.code, "ibkr_account_ambiguous")

    def test_read_only_sync_is_owner_scoped(self) -> None:
        self.db.create_or_update_app_user(user_id="user-a", username="alice")
        self.db.create_or_update_app_user(user_id="user-b", username="bob")
        service_a = PortfolioService(owner_id="user-a")
        service_b = PortfolioService(owner_id="user-b")
        sync_service_b = PortfolioIbkrSyncService(
            portfolio_service=service_b,
            transport=self._build_transport(),
        )

        account_a = service_a.create_account(name="Alice IBKR", broker="IBKR", market="us", base_currency="USD")
        with self.assertRaisesRegex(ValueError, "Active account not found"):
            sync_service_b.sync_read_only_account_state(
                account_id=account_a["id"],
                session_token="unit-test-session",
            )

    def test_same_user_multi_account_sync_keeps_mapping_stable_and_overlays_isolated(self) -> None:
        account_a = self.service.create_account(name="IBKR Imported", broker="IBKR", market="us", base_currency="USD")
        account_b = self.service.create_account(name="IBKR Secondary", broker="IBKR", market="us", base_currency="USD")
        account_c = self.service.create_account(name="IBKR Conflict", broker="IBKR", market="us", base_currency="USD")
        parsed = self.import_service.parse_import_file(broker="ibkr", content=self._ibkr_flex_xml_bytes())
        self.import_service.commit_import_records(
            account_id=account_a["id"],
            broker="ibkr",
            parsed_payload=parsed,
            dry_run=False,
        )

        first_transport = FakeIbkrTransport(
            {
                "/v1/api/portfolio/accounts": [
                    {"accountId": "U1234567", "displayName": "Primary IBKR", "currency": "USD"},
                    {"accountId": "U7654321", "displayName": "Secondary IBKR", "currency": "USD"},
                ],
                "/v1/api/portfolio/U1234567/summary": {
                    "totalcashvalue": {"amount": "5000"},
                    "stockmarketvalue": {"amount": "1600"},
                    "netliquidation": {"amount": "6600"},
                    "unrealizedpnl": {"amount": "100"},
                },
                "/v1/api/portfolio/U1234567/ledger": {"USD": {"cashbalance": "5000"}},
                "/v1/api/portfolio/U1234567/positions/0": [
                    {
                        "conid": "265598",
                        "contractDesc": "AAPL",
                        "position": "10",
                        "avgCost": "150",
                        "mktPrice": "160",
                        "mktValue": "1600",
                        "unrealizedPnl": "100",
                        "currency": "USD",
                        "assetClass": "STK",
                        "listingExchange": "NASDAQ",
                        "countryCode": "US",
                    }
                ],
                "/v1/api/portfolio/U1234567/positions/1": [],
                "/v1/api/portfolio/U7654321/summary": {
                    "totalcashvalue": {"amount": "2000"},
                    "stockmarketvalue": {"amount": "2000"},
                    "netliquidation": {"amount": "4000"},
                    "unrealizedpnl": {"amount": "100"},
                },
                "/v1/api/portfolio/U7654321/ledger": {"USD": {"cashbalance": "2000"}},
                "/v1/api/portfolio/U7654321/positions/0": [
                    {
                        "conid": "272093",
                        "contractDesc": "MSFT",
                        "position": "5",
                        "avgCost": "380",
                        "mktPrice": "400",
                        "mktValue": "2000",
                        "unrealizedPnl": "100",
                        "currency": "USD",
                        "assetClass": "STK",
                        "listingExchange": "NASDAQ",
                        "countryCode": "US",
                    }
                ],
                "/v1/api/portfolio/U7654321/positions/1": [],
            }
        )

        sync_service_a = PortfolioIbkrSyncService(portfolio_service=self.service, transport=first_transport)
        first_result_a = sync_service_a.sync_read_only_account_state(
            account_id=account_a["id"],
            session_token="unit-test-session",
            broker_account_ref="U1234567",
        )
        first_result_b = sync_service_a.sync_read_only_account_state(
            account_id=account_b["id"],
            session_token="unit-test-session",
            broker_account_ref="U7654321",
        )

        first_connections_a = self.service.list_broker_connections(portfolio_account_id=account_a["id"], broker_type="ibkr")
        first_connections_b = self.service.list_broker_connections(portfolio_account_id=account_b["id"], broker_type="ibkr")
        self.assertEqual(len(first_connections_a), 1)
        self.assertEqual(len(first_connections_b), 1)
        connection_id_a = first_connections_a[0]["id"]
        connection_id_b = first_connections_b[0]["id"]
        self.assertNotEqual(connection_id_a, connection_id_b)

        second_transport = FakeIbkrTransport(
            {
                "/v1/api/portfolio/accounts": [
                    {"accountId": "U1234567", "displayName": "Primary IBKR", "currency": "USD"},
                    {"accountId": "U7654321", "displayName": "Secondary IBKR", "currency": "USD"},
                ],
                "/v1/api/portfolio/U1234567/summary": {
                    "totalcashvalue": {"amount": "4500"},
                    "stockmarketvalue": {"amount": "5450"},
                    "netliquidation": {"amount": "9950"},
                    "unrealizedpnl": {"amount": "250"},
                },
                "/v1/api/portfolio/U1234567/ledger": {"USD": {"cashbalance": "4500"}},
                "/v1/api/portfolio/U1234567/positions/0": [
                    {
                        "conid": "265598",
                        "contractDesc": "AAPL",
                        "position": "12",
                        "avgCost": "150",
                        "mktPrice": "165",
                        "mktValue": "1980",
                        "unrealizedPnl": "180",
                        "currency": "USD",
                        "assetClass": "STK",
                        "listingExchange": "NASDAQ",
                        "countryCode": "US",
                    },
                    {
                        "conid": "208813719",
                        "contractDesc": "GOOG",
                        "position": "1",
                        "avgCost": "3200",
                        "mktPrice": "3470",
                        "mktValue": "3470",
                        "unrealizedPnl": "270",
                        "currency": "USD",
                        "assetClass": "STK",
                        "listingExchange": "NASDAQ",
                        "countryCode": "US",
                    },
                ],
                "/v1/api/portfolio/U1234567/positions/1": [],
            }
        )
        repeat_sync_service = PortfolioIbkrSyncService(portfolio_service=self.service, transport=second_transport)
        second_result_a = repeat_sync_service.sync_read_only_account_state(
            account_id=account_a["id"],
            session_token="unit-test-session",
            broker_connection_id=connection_id_a,
        )

        self.assertTrue(second_result_a["used_existing_connection"])
        second_connections_a = self.service.list_broker_connections(portfolio_account_id=account_a["id"], broker_type="ibkr")
        self.assertEqual(len(second_connections_a), 1)
        self.assertEqual(second_connections_a[0]["id"], connection_id_a)

        latest_sync_a = self.service.get_latest_broker_sync_state(portfolio_account_id=account_a["id"])
        latest_sync_b = self.service.get_latest_broker_sync_state(portfolio_account_id=account_b["id"])
        self.assertEqual([item["symbol"] for item in latest_sync_a["positions"]], ["AAPL", "GOOG"])
        self.assertEqual([item["symbol"] for item in latest_sync_b["positions"]], ["MSFT"])

        snapshot_a = self.service.get_portfolio_snapshot(
            account_id=account_a["id"],
            as_of=date.fromisoformat(second_result_a["snapshot_date"]),
            cost_method="fifo",
        )
        snapshot_b = self.service.get_portfolio_snapshot(
            account_id=account_b["id"],
            as_of=date.fromisoformat(first_result_b["snapshot_date"]),
            cost_method="fifo",
        )
        self.assertEqual({item["symbol"] for item in snapshot_a["accounts"][0]["positions"]}, {"AAPL", "GOOG"})
        self.assertEqual({item["symbol"] for item in snapshot_b["accounts"][0]["positions"]}, {"MSFT"})

        historical_snapshot_a = self.service.get_portfolio_snapshot(
            account_id=account_a["id"],
            as_of=date(2026, 1, 31),
            cost_method="fifo",
        )
        self.assertEqual([item["symbol"] for item in historical_snapshot_a["accounts"][0]["positions"]], ["AAPL"])

        conflict_transport = FakeIbkrTransport(
            {
                "/v1/api/portfolio/accounts": [
                    {"accountId": "U1234567", "displayName": "Primary IBKR", "currency": "USD"},
                    {"accountId": "U7654321", "displayName": "Secondary IBKR", "currency": "USD"},
                ]
            }
        )
        conflict_sync_service = PortfolioIbkrSyncService(portfolio_service=self.service, transport=conflict_transport)
        with self.assertRaises(PortfolioIbkrSyncError) as ctx:
            conflict_sync_service.sync_read_only_account_state(
                account_id=account_c["id"],
                session_token="unit-test-session",
                broker_account_ref="U1234567",
            )

        self.assertEqual(ctx.exception.code, "ibkr_account_mapping_conflict")

    def test_same_day_overlay_resync_refreshes_cached_snapshot(self) -> None:
        account = self.service.create_account(name="Primary IBKR", broker="IBKR", market="us", base_currency="USD")
        first_transport = FakeIbkrTransport(
            {
                "/v1/api/portfolio/accounts": [
                    {"accountId": "U1234567", "displayName": "Primary IBKR", "currency": "USD"},
                ],
                "/v1/api/portfolio/U1234567/summary": {
                    "totalcashvalue": {"amount": "5000"},
                    "stockmarketvalue": {"amount": "1600"},
                    "netliquidation": {"amount": "6600"},
                    "unrealizedpnl": {"amount": "100"},
                },
                "/v1/api/portfolio/U1234567/ledger": {"USD": {"cashbalance": "5000"}},
                "/v1/api/portfolio/U1234567/positions/0": [
                    {
                        "conid": "265598",
                        "contractDesc": "AAPL",
                        "position": "10",
                        "avgCost": "150",
                        "mktPrice": "160",
                        "mktValue": "1600",
                        "unrealizedPnl": "100",
                        "currency": "USD",
                        "assetClass": "STK",
                        "listingExchange": "NASDAQ",
                        "countryCode": "US",
                    }
                ],
                "/v1/api/portfolio/U1234567/positions/1": [],
            }
        )
        sync_service = PortfolioIbkrSyncService(portfolio_service=self.service, transport=first_transport)
        first_result = sync_service.sync_read_only_account_state(
            account_id=account["id"],
            session_token="unit-test-session",
            broker_account_ref="U1234567",
        )
        snapshot_date = date.fromisoformat(first_result["snapshot_date"])
        first_snapshot = self.service.get_portfolio_snapshot(
            account_id=account["id"],
            as_of=snapshot_date,
            cost_method="fifo",
        )
        self.assertEqual([item["symbol"] for item in first_snapshot["accounts"][0]["positions"]], ["AAPL"])

        connection_id = self.service.list_broker_connections(
            portfolio_account_id=account["id"],
            broker_type="ibkr",
        )[0]["id"]
        second_transport = FakeIbkrTransport(
            {
                "/v1/api/portfolio/accounts": [
                    {"accountId": "U1234567", "displayName": "Primary IBKR", "currency": "USD"},
                ],
                "/v1/api/portfolio/U1234567/summary": {
                    "totalcashvalue": {"amount": "4500"},
                    "stockmarketvalue": {"amount": "5450"},
                    "netliquidation": {"amount": "9950"},
                    "unrealizedpnl": {"amount": "250"},
                },
                "/v1/api/portfolio/U1234567/ledger": {"USD": {"cashbalance": "4500"}},
                "/v1/api/portfolio/U1234567/positions/0": [
                    {
                        "conid": "265598",
                        "contractDesc": "AAPL",
                        "position": "12",
                        "avgCost": "150",
                        "mktPrice": "165",
                        "mktValue": "1980",
                        "unrealizedPnl": "180",
                        "currency": "USD",
                        "assetClass": "STK",
                        "listingExchange": "NASDAQ",
                        "countryCode": "US",
                    },
                    {
                        "conid": "208813719",
                        "contractDesc": "GOOG",
                        "position": "1",
                        "avgCost": "3200",
                        "mktPrice": "3470",
                        "mktValue": "3470",
                        "unrealizedPnl": "270",
                        "currency": "USD",
                        "assetClass": "STK",
                        "listingExchange": "NASDAQ",
                        "countryCode": "US",
                    },
                ],
                "/v1/api/portfolio/U1234567/positions/1": [],
            }
        )
        repeat_sync_service = PortfolioIbkrSyncService(portfolio_service=self.service, transport=second_transport)
        second_result = repeat_sync_service.sync_read_only_account_state(
            account_id=account["id"],
            session_token="unit-test-session",
            broker_connection_id=connection_id,
        )

        refreshed_snapshot = self.service.get_portfolio_snapshot(
            account_id=account["id"],
            as_of=date.fromisoformat(second_result["snapshot_date"]),
            cost_method="fifo",
        )
        self.assertEqual(
            {item["symbol"] for item in refreshed_snapshot["accounts"][0]["positions"]},
            {"AAPL", "GOOG"},
        )
