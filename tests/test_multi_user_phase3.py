# -*- coding: utf-8 -*-
"""Phase 3 authorization and isolation coverage."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import Future
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# Keep this test runnable when optional LLM runtime deps are not installed.
try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from api.deps import CurrentUser
from api.v1.endpoints.analysis import get_task_list
from src.config import Config
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.services.market_scanner_service import MarketScannerService
from src.services.portfolio_service import PortfolioService
from src.services.task_queue import AnalysisTaskQueue, TaskStatus
from src.storage import BacktestRun, DatabaseManager, RuleBacktestRun


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _dummy_analysis_result(code: str, *, name: str) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        name=name,
        sentiment_score=66,
        operation_advice="买入",
        trend_prediction="看多",
        analysis_summary=f"{name} analysis",
        raw_result={"summary": f"{name} raw"},
        ideal_buy=None,
        secondary_buy=None,
        stop_loss=9.5,
        take_profit=11.0,
    )


class MultiUserAuthorizationApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "phase3_authz.db"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=true",
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

        self.app = create_app(static_dir=self.data_dir / "empty-static")
        self.admin_client = TestClient(self.app)
        self.user_a_client = TestClient(self.app)
        self.user_b_client = TestClient(self.app)
        self.db = DatabaseManager.get_instance()

        self._login_admin()
        self.admin_unlock_token = self._verify_admin_password()
        self.user_a_id = self._login_user(self.user_a_client, "alice", "Alice")
        self.user_b_id = self._login_user(self.user_b_client, "bob", "Bob")

    def tearDown(self) -> None:
        self.admin_client.close()
        self.user_a_client.close()
        self.user_b_client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _login_admin(self) -> None:
        response = self.admin_client.post(
            "/api/v1/auth/login",
            json={
                "password": "admin-pass-123",
                "passwordConfirm": "admin-pass-123",
            },
        )
        self.assertEqual(response.status_code, 200)

    def _verify_admin_password(self) -> str:
        response = self.admin_client.post(
            "/api/v1/auth/verify-password",
            json={"password": "admin-pass-123"},
        )
        self.assertEqual(response.status_code, 200)
        token = response.json().get("unlockToken")
        self.assertTrue(token)
        return str(token)

    def _login_user(self, client: TestClient, username: str, display_name: str) -> str:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": username,
                "displayName": display_name,
                "createUser": True,
                "password": "secret123",
                "passwordConfirm": "secret123",
            },
        )
        self.assertEqual(response.status_code, 200)
        user_row = self.db.get_app_user_by_username(username)
        self.assertIsNotNone(user_row)
        return str(user_row.id)

    def _admin_unlock_headers(self) -> dict[str, str]:
        return {"X-Admin-Unlock-Token": self.admin_unlock_token}

    @staticmethod
    def _ibkr_flex_xml_bytes() -> bytes:
        xml_text = """<?xml version="1.0" encoding="UTF-8"?>
<FlexStatements>
  <FlexStatement accountId="U1234567" fromDate="2026-01-01" toDate="2026-01-31" currency="USD">
    <Trades>
      <Trade assetCategory="STK" symbol="AAPL" exchange="NASDAQ" currency="USD" tradeDate="2026-01-03" buySell="BUY" quantity="10" tradePrice="150" ibCommission="1.25" taxes="0" ibExecID="AAPL-1" description="AAPL BUY"/>
    </Trades>
  </FlexStatement>
</FlexStatements>
"""
        return xml_text.encode("utf-8")

    @staticmethod
    def _error_code(response) -> str | None:
        payload = response.json()
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if isinstance(detail, dict):
            return detail.get("error")
        if isinstance(payload, dict):
            return payload.get("error")
        return None

    def _seed_scanner_runs(self) -> tuple[dict, dict, dict]:
        today = datetime.now().date().isoformat()
        service_a = MarketScannerService(self.db, owner_id=self.user_a_id)
        service_b = MarketScannerService(self.db, owner_id=self.user_b_id)
        run_a = service_a.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="Scanner",
            universe_name="fixture",
            status="completed",
            headline="user a manual run",
            trigger_mode="manual",
            request_source="api",
            watchlist_date=today,
            source_summary="fixture",
            shortlist=[],
        )
        system_run = service_a.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="Scanner",
            universe_name="fixture",
            status="completed",
            headline="system scheduled run",
            trigger_mode="scheduled",
            request_source="scheduler",
            watchlist_date=today,
            source_summary="fixture",
            shortlist=[],
        )
        run_b = service_b.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="Scanner",
            universe_name="fixture",
            status="completed",
            headline="user b manual run",
            trigger_mode="manual",
            request_source="api",
            watchlist_date=today,
            source_summary="fixture",
            shortlist=[],
        )
        return run_a, system_run, run_b

    def test_admin_only_surfaces_are_backend_protected(self) -> None:
        user_resp = self.user_a_client.get("/api/v1/system/config")
        self.assertEqual(user_resp.status_code, 403)
        self.assertEqual(self._error_code(user_resp), "admin_required")

        user_schema_resp = self.user_a_client.get("/api/v1/system/config/schema")
        self.assertEqual(user_schema_resp.status_code, 403)
        self.assertEqual(self._error_code(user_schema_resp), "admin_required")

        usage_resp = self.user_a_client.get("/api/v1/usage/summary")
        self.assertEqual(usage_resp.status_code, 403)
        self.assertEqual(self._error_code(usage_resp), "admin_required")

        logs_resp = self.user_a_client.get("/api/v1/admin/logs/sessions")
        self.assertEqual(logs_resp.status_code, 403)
        self.assertEqual(self._error_code(logs_resp), "admin_required")

        send_resp = self.user_a_client.post("/api/v1/agent/chat/send", json={"content": "hello"})
        self.assertEqual(send_resp.status_code, 403)
        self.assertEqual(self._error_code(send_resp), "admin_required")

        admin_config_resp = self.admin_client.get("/api/v1/system/config")
        self.assertEqual(admin_config_resp.status_code, 200)

        admin_schema_resp = self.admin_client.get("/api/v1/system/config/schema")
        self.assertEqual(admin_schema_resp.status_code, 200)

        admin_usage_resp = self.admin_client.get("/api/v1/usage/summary")
        self.assertEqual(admin_usage_resp.status_code, 200)

        admin_logs_resp = self.admin_client.get(
            "/api/v1/admin/logs/sessions",
            headers=self._admin_unlock_headers(),
        )
        self.assertEqual(admin_logs_resp.status_code, 200)

        with patch("src.notification.NotificationService.send", return_value=True):
            admin_send_resp = self.admin_client.post(
                "/api/v1/agent/chat/send",
                json={"content": "hello"},
            )
        self.assertEqual(admin_send_resp.status_code, 200)
        self.assertTrue(admin_send_resp.json()["success"])

    def test_scanner_system_scope_is_admin_only_and_manual_runs_are_owner_scoped(self) -> None:
        run_a, system_run, run_b = self._seed_scanner_runs()

        runs_a_resp = self.user_a_client.get("/api/v1/scanner/runs")
        self.assertEqual(runs_a_resp.status_code, 200)
        self.assertEqual(
            {item["id"] for item in runs_a_resp.json()["items"]},
            {run_a["id"]},
        )

        runs_b_resp = self.user_b_client.get("/api/v1/scanner/runs")
        self.assertEqual(runs_b_resp.status_code, 200)
        self.assertEqual(
            {item["id"] for item in runs_b_resp.json()["items"]},
            {run_b["id"]},
        )

        user_detail_resp = self.user_a_client.get(f"/api/v1/scanner/runs/{system_run['id']}")
        self.assertEqual(user_detail_resp.status_code, 404)

        user_watchlist_resp = self.user_a_client.get("/api/v1/scanner/watchlists/today")
        self.assertEqual(user_watchlist_resp.status_code, 403)
        self.assertEqual(self._error_code(user_watchlist_resp), "admin_required")

        admin_watchlist_resp = self.admin_client.get("/api/v1/scanner/watchlists/today")
        self.assertEqual(admin_watchlist_resp.status_code, 200)
        self.assertEqual(admin_watchlist_resp.json()["id"], system_run["id"])

        admin_status_resp = self.admin_client.get("/api/v1/scanner/status")
        self.assertEqual(admin_status_resp.status_code, 200)
        self.assertEqual(admin_status_resp.json()["today_watchlist"]["id"], system_run["id"])

        admin_detail_resp = self.admin_client.get(f"/api/v1/scanner/runs/{system_run['id']}")
        self.assertEqual(admin_detail_resp.status_code, 200)
        self.assertEqual(admin_detail_resp.json()["id"], system_run["id"])

    def test_user_owned_domains_block_cross_user_access(self) -> None:
        account_a = PortfolioService(owner_id=self.user_a_id).create_account(
            name="Alice Account",
            broker="Demo",
            market="cn",
            base_currency="CNY",
        )
        account_b = PortfolioService(owner_id=self.user_b_id).create_account(
            name="Bob Account",
            broker="Demo",
            market="cn",
            base_currency="CNY",
        )

        self.db.save_analysis_history(
            _dummy_analysis_result("600519", name="贵州茅台"),
            query_id="history-a",
            report_type="simple",
            news_content=None,
            owner_id=self.user_a_id,
        )
        self.db.save_analysis_history(
            _dummy_analysis_result("000001", name="平安银行"),
            query_id="history-b",
            report_type="simple",
            news_content=None,
            owner_id=self.user_b_id,
        )
        history_a_id = self.db.get_analysis_history(query_id="history-a", owner_id=self.user_a_id, limit=1)[0].id
        history_b_id = self.db.get_analysis_history(query_id="history-b", owner_id=self.user_b_id, limit=1)[0].id

        self.db.save_conversation_message("session-a", "user", "hello a", owner_id=self.user_a_id)
        self.db.save_conversation_message("session-b", "user", "hello b", owner_id=self.user_b_id)

        with self.db.get_session() as session:
            session.add(
                BacktestRun(
                    owner_id=self.user_a_id,
                    code="600519",
                    eval_window_days=10,
                    min_age_days=14,
                    force=False,
                    status="completed",
                    summary_json=json.dumps({"summary": "alice"}),
                )
            )
            session.add(
                BacktestRun(
                    owner_id=self.user_b_id,
                    code="000001",
                    eval_window_days=10,
                    min_age_days=14,
                    force=False,
                    status="completed",
                    summary_json=json.dumps({"summary": "bob"}),
                )
            )
            session.add(
                RuleBacktestRun(
                    owner_id=self.user_a_id,
                    code="600519",
                    strategy_text="ma cross",
                    parsed_strategy_json="{}",
                    strategy_hash="rule-a",
                    timeframe="daily",
                    lookback_bars=30,
                    initial_capital=100000.0,
                    fee_bps=0.0,
                    status="completed",
                    summary_json="{}",
                    warnings_json="[]",
                    equity_curve_json="[]",
                )
            )
            session.commit()
            rule_run_a_id = session.query(RuleBacktestRun.id).filter_by(strategy_hash="rule-a").scalar()

        portfolio_resp = self.user_a_client.get("/api/v1/portfolio/accounts")
        self.assertEqual(portfolio_resp.status_code, 200)
        self.assertEqual([item["id"] for item in portfolio_resp.json()["accounts"]], [account_a["id"]])

        portfolio_update_resp = self.user_a_client.put(
            f"/api/v1/portfolio/accounts/{account_b['id']}",
            json={"name": "hacked"},
        )
        self.assertEqual(portfolio_update_resp.status_code, 404)

        history_resp = self.user_a_client.get(f"/api/v1/history/{history_b_id}")
        self.assertEqual(history_resp.status_code, 404)

        chat_detail_resp = self.user_a_client.get("/api/v1/agent/chat/sessions/session-b")
        self.assertEqual(chat_detail_resp.status_code, 404)
        self.assertEqual(self._error_code(chat_detail_resp), "not_found")

        chat_delete_resp = self.user_a_client.delete("/api/v1/agent/chat/sessions/session-b")
        self.assertEqual(chat_delete_resp.status_code, 404)
        self.assertEqual(self._error_code(chat_delete_resp), "not_found")

        backtest_runs_resp = self.user_a_client.get("/api/v1/backtest/runs")
        self.assertEqual(backtest_runs_resp.status_code, 200)
        self.assertEqual(len(backtest_runs_resp.json()["items"]), 1)
        self.assertEqual(backtest_runs_resp.json()["items"][0]["code"], "600519")

        rule_detail_resp = self.user_b_client.get(f"/api/v1/backtest/rule/runs/{rule_run_a_id}")
        self.assertEqual(rule_detail_resp.status_code, 404)

        own_history_resp = self.user_a_client.get(f"/api/v1/history/{history_a_id}")
        self.assertEqual(own_history_resp.status_code, 200)

    def test_portfolio_events_and_broker_connections_stay_owner_scoped(self) -> None:
        service_a = PortfolioService(owner_id=self.user_a_id)
        account_a = service_a.create_account(
            name="Alice Global",
            broker="IBKR",
            market="us",
            base_currency="USD",
        )

        trade_id = service_a.record_trade(
            account_id=account_a["id"],
            symbol="AAPL",
            trade_date=datetime(2026, 4, 10).date(),
            side="buy",
            quantity=10,
            price=150,
            market="us",
            currency="USD",
        )["id"]
        cash_id = service_a.record_cash_ledger(
            account_id=account_a["id"],
            event_date=datetime(2026, 4, 10).date(),
            direction="in",
            amount=5000,
            currency="USD",
        )["id"]
        action_id = service_a.record_corporate_action(
            account_id=account_a["id"],
            symbol="AAPL",
            effective_date=datetime(2026, 4, 11).date(),
            action_type="cash_dividend",
            market="us",
            currency="USD",
            cash_dividend_per_share=0.24,
        )["id"]
        connection = service_a.create_broker_connection(
            portfolio_account_id=account_a["id"],
            broker_type="ibkr",
            broker_name="Interactive Brokers",
            connection_name="Alice IBKR",
            broker_account_ref="U7654321",
            sync_metadata={"source": "flex"},
        )

        self.assertEqual(self.user_b_client.delete(f"/api/v1/portfolio/trades/{trade_id}").status_code, 404)
        self.assertEqual(self.user_b_client.delete(f"/api/v1/portfolio/cash-ledger/{cash_id}").status_code, 404)
        self.assertEqual(
            self.user_b_client.delete(f"/api/v1/portfolio/corporate-actions/{action_id}").status_code,
            404,
        )

        list_b_resp = self.user_b_client.get("/api/v1/portfolio/broker-connections")
        self.assertEqual(list_b_resp.status_code, 200)
        self.assertEqual(list_b_resp.json()["connections"], [])

        update_b_resp = self.user_b_client.put(
            f"/api/v1/portfolio/broker-connections/{connection['id']}",
            json={"connection_name": "Bob Hack"},
        )
        self.assertEqual(update_b_resp.status_code, 404)

        list_a_resp = self.user_a_client.get("/api/v1/portfolio/broker-connections")
        self.assertEqual(list_a_resp.status_code, 200)
        self.assertEqual(len(list_a_resp.json()["connections"]), 1)
        self.assertEqual(list_a_resp.json()["connections"][0]["broker_account_ref"], "U7654321")

    def test_broker_import_commit_is_owner_scoped(self) -> None:
        account_a = PortfolioService(owner_id=self.user_a_id).create_account(
            name="Alice Import",
            broker="IBKR",
            market="us",
            base_currency="USD",
        )

        bob_commit = self.user_b_client.post(
            "/api/v1/portfolio/imports/commit",
            data={"account_id": str(account_a["id"]), "broker": "ibkr", "dry_run": "false"},
            files={"file": ("ibkr-flex.xml", self._ibkr_flex_xml_bytes(), "application/xml")},
        )
        self.assertEqual(bob_commit.status_code, 400)
        self.assertEqual(self._error_code(bob_commit), "validation_error")

        alice_commit = self.user_a_client.post(
            "/api/v1/portfolio/imports/commit",
            data={"account_id": str(account_a["id"]), "broker": "ibkr", "dry_run": "false"},
            files={"file": ("ibkr-flex.xml", self._ibkr_flex_xml_bytes(), "application/xml")},
        )
        self.assertEqual(alice_commit.status_code, 200)
        self.assertEqual(alice_commit.json()["inserted_count"], 1)

        bob_connections = self.user_b_client.get("/api/v1/portfolio/broker-connections")
        self.assertEqual(bob_connections.status_code, 200)
        self.assertEqual(bob_connections.json()["connections"], [])


class AnalysisAuthorizationContractTestCase(unittest.TestCase):
    def test_get_task_list_uses_owner_scoped_stats(self) -> None:
        current_user = CurrentUser(
            user_id="user-a",
            username="alice",
            display_name="Alice",
            role="user",
            is_admin=False,
            is_authenticated=True,
            transitional=False,
            auth_enabled=True,
        )
        task = SimpleNamespace(
            task_id="task-a",
            stock_code="600519",
            stock_name="贵州茅台",
            status=TaskStatus.PENDING,
            progress=0,
            message="任务已加入队列",
            result=None,
            report_type="detailed",
            created_at=datetime(2026, 4, 14, 8, 0, 0),
            started_at=None,
            completed_at=None,
            error=None,
            original_query=None,
            selection_source=None,
            execution=None,
        )
        queue = MagicMock()
        queue.list_all_tasks.return_value = [task]
        queue.get_task_stats.return_value = {
            "total": 1,
            "pending": 1,
            "processing": 0,
            "completed": 0,
            "failed": 0,
        }

        with patch("api.v1.endpoints.analysis.get_task_queue", return_value=queue):
            response = get_task_list(status=None, limit=20, current_user=current_user)

        self.assertEqual(response.total, 1)
        self.assertEqual(response.tasks[0].task_id, "task-a")
        queue.list_all_tasks.assert_called_once_with(limit=20, owner_id="user-a")
        queue.get_task_stats.assert_called_once_with(owner_id="user-a")


class TaskQueueIsolationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._original_instance = AnalysisTaskQueue._instance
        AnalysisTaskQueue._instance = None

    def tearDown(self) -> None:
        queue = AnalysisTaskQueue._instance
        if queue is not None and queue is not self._original_instance:
            executor = getattr(queue, "_executor", None)
            if executor is not None and hasattr(executor, "shutdown"):
                executor.shutdown(wait=False, cancel_futures=True)
        AnalysisTaskQueue._instance = self._original_instance

    def test_duplicate_detection_is_owner_scoped(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)
        queue._executor = type("ExecutorStub", (), {"submit": lambda self, *args, **kwargs: Future()})()

        accepted_a, duplicates_a = queue.submit_tasks_batch(["600519"], owner_id="user-a")
        accepted_b, duplicates_b = queue.submit_tasks_batch(["600519.SH"], owner_id="user-b")

        self.assertEqual(len(accepted_a), 1)
        self.assertEqual(len(accepted_b), 1)
        self.assertEqual(duplicates_a, [])
        self.assertEqual(duplicates_b, [])
        self.assertTrue(queue.is_analyzing("600519", owner_id="user-a"))
        self.assertTrue(queue.is_analyzing("600519", owner_id="user-b"))
        self.assertNotEqual(
            queue.get_analyzing_task_id("600519", owner_id="user-a"),
            queue.get_analyzing_task_id("600519", owner_id="user-b"),
        )

    def test_task_stats_filter_by_owner(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)
        queue._tasks = {
            "task-a": SimpleNamespace(status=TaskStatus.PENDING, owner_id="user-a"),
            "task-b": SimpleNamespace(status=TaskStatus.PROCESSING, owner_id="user-b"),
        }

        user_a_stats = queue.get_task_stats(owner_id="user-a")

        self.assertEqual(
            user_a_stats,
            {
                "total": 1,
                "pending": 1,
                "processing": 0,
                "completed": 0,
                "failed": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
