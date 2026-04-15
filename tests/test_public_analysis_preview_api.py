# -*- coding: utf-8 -*-
"""Guest analysis preview API coverage."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.storage import AnalysisHistory, DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class PublicAnalysisPreviewApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.db_path = self.data_dir / "guest_preview.db"
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
        self.client = TestClient(self.app)
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        self.client.close()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def test_guest_preview_is_public_and_does_not_request_persistence(self) -> None:
        captured_query_ids: list[str] = []

        def _mock_analyze_stock(*args, **kwargs):
            captured_query_ids.append(str(kwargs["query_id"]))
            query_id = str(kwargs["query_id"])
            return {
                "query_id": query_id,
                "stock_code": "AAPL",
                "stock_name": "Apple",
                "report": {
                    "meta": {
                        "query_id": query_id,
                        "stock_code": "AAPL",
                        "stock_name": "Apple",
                        "report_type": "brief",
                        "report_language": "en",
                        "created_at": "2026-04-14T09:00:00+00:00",
                        "current_price": 188.2,
                        "change_pct": 1.8,
                        "model_used": "openai/gpt-5.4",
                    },
                    "summary": {
                        "analysis_summary": "Momentum remains constructive with earnings support.",
                        "operation_advice": "Wait for pullback",
                        "trend_prediction": "Bullish bias",
                        "sentiment_score": 74,
                        "sentiment_label": "Bullish",
                    },
                    "strategy": {
                        "ideal_buy": "184-186",
                        "stop_loss": "179",
                        "take_profit": "195-198",
                    },
                    "details": {
                        "standard_report": {"should_not": "leak"},
                    },
                },
            }

        with patch(
            "src.services.analysis_service.AnalysisService.analyze_stock",
            side_effect=_mock_analyze_stock,
        ) as analyze_stock:
            response = self.client.post(
                "/api/v1/analysis/preview",
                json={"stock_code": "AAPL", "stock_name": "Apple"},
            )

        self.assertEqual(response.status_code, 200)
        analyze_stock.assert_called_once()
        _, kwargs = analyze_stock.call_args
        self.assertEqual(kwargs["stock_code"], "AAPL")
        self.assertEqual(kwargs["report_type"], "brief")
        self.assertFalse(kwargs["send_notification"])
        self.assertFalse(kwargs["persist_history"])
        self.assertTrue(kwargs["query_id"].startswith("guest:"))
        self.assertTrue(self.client.cookies.get("wolfystock_guest_session"))

        payload = response.json()
        self.assertEqual(payload["preview_scope"], "guest")
        self.assertEqual(payload["stock_code"], "AAPL")
        self.assertEqual(payload["stock_name"], "Apple")
        self.assertEqual(payload["report"]["summary"]["analysis_summary"], "Momentum remains constructive with earnings support.")
        self.assertIsNone(payload["report"]["details"])
        self.assertEqual(payload["query_id"], captured_query_ids[0])

        with self.db.get_session() as session:
            self.assertEqual(session.query(AnalysisHistory).count(), 0)

    def test_guest_preview_uses_isolated_anonymous_session_ids_without_persisting_history(self) -> None:
        captured_query_ids: list[str] = []

        def _mock_analyze_stock(*args, **kwargs):
            captured_query_ids.append(str(kwargs["query_id"]))
            query_id = str(kwargs["query_id"])
            return {
                "query_id": query_id,
                "stock_code": "AAPL",
                "stock_name": "Apple",
                "report": {
                    "meta": {
                        "query_id": query_id,
                        "stock_code": "AAPL",
                        "stock_name": "Apple",
                        "report_type": "brief",
                        "report_language": "en",
                        "created_at": "2026-04-14T09:00:00+00:00",
                        "current_price": 188.2,
                        "change_pct": 1.8,
                        "model_used": "openai/gpt-5.4",
                    },
                    "summary": {
                        "analysis_summary": "Preview summary",
                        "operation_advice": "Wait",
                        "trend_prediction": "Bullish bias",
                        "sentiment_score": 74,
                        "sentiment_label": "Bullish",
                    },
                    "strategy": {
                        "ideal_buy": "184-186",
                        "stop_loss": "179",
                        "take_profit": "195-198",
                    },
                    "details": {
                        "standard_report": {"should_not": "leak"},
                    },
                },
            }

        other_client = TestClient(self.app)
        try:
            with patch(
                "src.services.analysis_service.AnalysisService.analyze_stock",
                side_effect=_mock_analyze_stock,
            ):
                first_response = self.client.post(
                    "/api/v1/analysis/preview",
                    json={"stock_code": "AAPL", "stock_name": "Apple"},
                )
                second_response = self.client.post(
                    "/api/v1/analysis/preview",
                    json={"stock_code": "AAPL", "stock_name": "Apple"},
                )
                third_response = other_client.post(
                    "/api/v1/analysis/preview",
                    json={"stock_code": "AAPL", "stock_name": "Apple"},
                )

            self.assertEqual(first_response.status_code, 200)
            self.assertEqual(second_response.status_code, 200)
            self.assertEqual(third_response.status_code, 200)
            self.assertEqual(len(captured_query_ids), 3)

            first_session = captured_query_ids[0].split(":")[1]
            second_session = captured_query_ids[1].split(":")[1]
            third_session = captured_query_ids[2].split(":")[1]

            self.assertEqual(first_session, second_session)
            self.assertNotEqual(first_session, third_session)
            self.assertEqual(self.client.cookies.get("wolfystock_guest_session"), first_session)
            self.assertEqual(other_client.cookies.get("wolfystock_guest_session"), third_session)

            with self.db.get_session() as session:
                self.assertEqual(session.query(AnalysisHistory).count(), 0)
        finally:
            other_client.close()


if __name__ == "__main__":
    unittest.main()
