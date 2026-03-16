import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
import src.auth as auth
from src.config import Config
from src.repositories.portfolio_repo import PortfolioRepository
from src.storage import DatabaseManager, StockDaily


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class RuntimeApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=false\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.data_dir / "test.db")

        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        repo = PortfolioRepository(self.db)
        repo.add_execution_event(
            {
                "portfolio_id": "default",
                "executed_at": datetime(2026, 3, 16, 9, 30, 0),
                "side": "cash_in",
                "amount": 10000.0,
            }
        )
        repo.add_execution_event(
            {
                "portfolio_id": "default",
                "executed_at": datetime(2026, 3, 16, 10, 0, 0),
                "side": "buy",
                "code": "600519",
                "quantity": 100,
                "price": 10.0,
                "fees": 5.0,
            }
        )
        with self.db.get_session() as session:
            session.add(StockDaily(code="600519", date=date(2026, 3, 16), close=11.0))
            session.commit()

        self.client = TestClient(create_app(static_dir=self.data_dir / "empty-static"))

    def tearDown(self) -> None:
        _reset_auth_globals()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def test_list_runtime_objects(self) -> None:
        response = self.client.get("/api/v1/runtime/objects")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("portfolio_state", payload["items"])
        self.assertIn("noon_monitor_packet", payload["items"])

    def test_get_runtime_object_returns_envelope(self) -> None:
        response = self.client.get(
            "/api/v1/runtime/portfolio_state",
            params={"portfolio_id": "default", "as_of_date": "2026-03-16"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["object_name"], "portfolio_state")
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["data"]["portfolio_id"], "default")
        self.assertEqual(payload["data"]["as_of_date"], "2026-03-16")

    def test_get_runtime_object_returns_404_for_unknown_name(self) -> None:
        response = self.client.get("/api/v1/runtime/not-exists")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
