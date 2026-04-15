# -*- coding: utf-8 -*-
"""Backtest ownership isolation regression coverage."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.storage import AnalysisHistory, BacktestResult, BacktestRun, DatabaseManager


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
        sentiment_score=61,
        operation_advice="买入",
        trend_prediction="看多",
        analysis_summary=f"{name} analysis",
        raw_result={"summary": f"{name} raw"},
        ideal_buy=None,
        secondary_buy=None,
        stop_loss=9.5,
        take_profit=11.0,
    )


class BacktestAccessIsolationTestCase(unittest.TestCase):
    @staticmethod
    def _error_code(response) -> str | None:
        payload = response.json()
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if isinstance(detail, dict):
            return detail.get("error")
        if isinstance(payload, dict):
            return payload.get("error")
        return None

    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "backtest_access_isolation.db"
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
        self.user_client = TestClient(self.app)
        self.db = DatabaseManager.get_instance()

        self._login_admin()
        self.user_id = self._login_user("alice", "Alice")

    def tearDown(self) -> None:
        self.admin_client.close()
        self.user_client.close()
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

    def _login_user(self, username: str, display_name: str) -> str:
        response = self.user_client.post(
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

    def _seed_backtest_fixture(self) -> tuple[int, int]:
        self.db.save_analysis_history(
            _dummy_analysis_result("600519", name="贵州茅台"),
            query_id="legacy-bootstrap-run",
            report_type="simple",
            news_content=None,
            owner_id=BOOTSTRAP_ADMIN_USER_ID,
        )
        self.db.save_analysis_history(
            _dummy_analysis_result("AAPL", name="Apple"),
            query_id="user-run",
            report_type="simple",
            news_content=None,
            owner_id=self.user_id,
        )

        legacy_history = self.db.get_analysis_history(
            query_id="legacy-bootstrap-run",
            owner_id=BOOTSTRAP_ADMIN_USER_ID,
            limit=1,
        )[0]
        user_history = self.db.get_analysis_history(
            query_id="user-run",
            owner_id=self.user_id,
            limit=1,
        )[0]

        legacy_completed_at = datetime(2026, 4, 14, 9, 0, 0)
        user_completed_at = datetime(2026, 4, 14, 10, 0, 0)

        with self.db.get_session() as session:
            legacy_run = BacktestRun(
                owner_id=BOOTSTRAP_ADMIN_USER_ID,
                code="600519",
                eval_window_days=10,
                min_age_days=14,
                force=False,
                completed_at=legacy_completed_at,
                status="completed",
                summary_json='{"scope":"legacy"}',
            )
            user_run = BacktestRun(
                owner_id=self.user_id,
                code="AAPL",
                eval_window_days=10,
                min_age_days=14,
                force=False,
                completed_at=user_completed_at,
                status="completed",
                summary_json='{"scope":"user"}',
            )
            session.add_all([legacy_run, user_run])
            session.flush()
            session.add_all(
                [
                    BacktestResult(
                        owner_id=BOOTSTRAP_ADMIN_USER_ID,
                        analysis_history_id=legacy_history.id,
                        code="600519",
                        eval_window_days=10,
                        engine_version="v1",
                        eval_status="completed",
                        evaluated_at=legacy_completed_at,
                        operation_advice="买入",
                    ),
                    BacktestResult(
                        owner_id=self.user_id,
                        analysis_history_id=user_history.id,
                        code="AAPL",
                        eval_window_days=10,
                        engine_version="v1",
                        eval_status="completed",
                        evaluated_at=user_completed_at,
                        operation_advice="买入",
                    ),
                ]
            )
            session.commit()
            return int(legacy_run.id), int(user_run.id)

    def test_normal_user_only_sees_owned_backtest_history_and_results(self) -> None:
        legacy_run_id, user_run_id = self._seed_backtest_fixture()

        history_response = self.user_client.get("/api/v1/backtest/runs")
        self.assertEqual(history_response.status_code, 200)
        payload = history_response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual([item["code"] for item in payload["items"]], ["AAPL"])

        recent_results_response = self.user_client.get("/api/v1/backtest/results")
        self.assertEqual(recent_results_response.status_code, 200)
        result_payload = recent_results_response.json()
        self.assertEqual(result_payload["total"], 1)
        self.assertEqual([item["code"] for item in result_payload["items"]], ["AAPL"])

        own_run_response = self.user_client.get(f"/api/v1/backtest/results?run_id={user_run_id}")
        self.assertEqual(own_run_response.status_code, 200)
        own_run_payload = own_run_response.json()
        self.assertEqual(own_run_payload["total"], 1)
        self.assertEqual(own_run_payload["items"][0]["code"], "AAPL")

        leaked_run_response = self.user_client.get(f"/api/v1/backtest/results?run_id={legacy_run_id}")
        self.assertEqual(leaked_run_response.status_code, 404)
        self.assertEqual(self._error_code(leaked_run_response), "not_found")

        admin_history_response = self.admin_client.get("/api/v1/backtest/runs")
        self.assertEqual(admin_history_response.status_code, 200)
        admin_history_payload = admin_history_response.json()
        self.assertEqual(admin_history_payload["total"], 1)
        self.assertEqual(admin_history_payload["items"][0]["code"], "600519")

        admin_results_response = self.admin_client.get(f"/api/v1/backtest/results?run_id={legacy_run_id}")
        self.assertEqual(admin_results_response.status_code, 200)
        admin_results_payload = admin_results_response.json()
        self.assertEqual(admin_results_payload["total"], 1)
        self.assertEqual(admin_results_payload["items"][0]["code"], "600519")


if __name__ == "__main__":
    unittest.main()
