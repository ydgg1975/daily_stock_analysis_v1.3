import os
import tempfile
import unittest
from datetime import date, datetime

from src.config import Config
from src.repositories.portfolio_repo import PortfolioRepository
from src.storage import DatabaseManager


class PortfolioStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_portfolio_storage.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.repo = PortfolioRepository(self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self._temp_dir.cleanup()

    def test_add_and_list_execution_events(self) -> None:
        self.repo.add_execution_event(
            {
                "portfolio_id": "default",
                "executed_at": datetime(2026, 3, 16, 9, 30, 0),
                "side": "cash_in",
                "amount": 20000.0,
                "note": "initial funding",
            }
        )
        self.repo.add_execution_event(
            {
                "portfolio_id": "default",
                "executed_at": datetime(2026, 3, 16, 10, 0, 0),
                "side": "buy",
                "code": "600519",
                "quantity": 10,
                "price": 1500.0,
                "fees": 5.0,
                "plan_id": "plan-1",
            }
        )

        items = self.repo.list_execution_events(portfolio_id="default")

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["side"], "cash_in")
        self.assertEqual(items[1]["side"], "buy")
        self.assertEqual(items[1]["code"], "600519")
        self.assertEqual(items[1]["plan_id"], "plan-1")

    def test_upsert_daily_pnl_snapshot_replaces_same_day_record(self) -> None:
        self.repo.upsert_daily_pnl_snapshot(
            {
                "portfolio_id": "default",
                "trade_date": date(2026, 3, 16),
                "cash": 1000.0,
                "market_value": 5000.0,
                "total_equity": 6000.0,
                "realized_pnl": 100.0,
                "unrealized_pnl": 50.0,
                "total_pnl": 150.0,
                "position_ratio": 0.83,
                "win_trade_count": 1,
                "loss_trade_count": 0,
            }
        )
        self.repo.upsert_daily_pnl_snapshot(
            {
                "portfolio_id": "default",
                "trade_date": date(2026, 3, 16),
                "cash": 1200.0,
                "market_value": 4800.0,
                "total_equity": 6000.0,
                "realized_pnl": 120.0,
                "unrealized_pnl": 40.0,
                "total_pnl": 160.0,
                "position_ratio": 0.8,
                "win_trade_count": 2,
                "loss_trade_count": 0,
            }
        )

        items = self.repo.list_daily_pnl_snapshots(portfolio_id="default")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["cash"], 1200.0)
        self.assertEqual(items[0]["total_pnl"], 160.0)
        self.assertEqual(items[0]["win_trade_count"], 2)


if __name__ == "__main__":
    unittest.main()
