import os
import tempfile
import unittest
from datetime import date, datetime

from src.config import Config
from src.repositories.portfolio_repo import PortfolioRepository
from src.services.daily_pnl_service import DailyPnlService
from src.services.portfolio_state_service import PortfolioStateService
from src.storage import DatabaseManager, StockDaily


class DailyPnlServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_daily_pnl_service.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.repo = PortfolioRepository(self.db)
        self.portfolio_state_service = PortfolioStateService(self.repo, self.db)
        self.service = DailyPnlService(self.repo, self.portfolio_state_service)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self._temp_dir.cleanup()

    def test_generate_daily_snapshot_persists_pnl_log(self) -> None:
        self.repo.add_execution_event(
            {
                "portfolio_id": "default",
                "executed_at": datetime(2026, 3, 16, 9, 30, 0),
                "side": "cash_in",
                "amount": 10000.0,
            }
        )
        self.repo.add_execution_event(
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
        self.repo.add_execution_event(
            {
                "portfolio_id": "default",
                "executed_at": datetime(2026, 3, 16, 14, 0, 0),
                "side": "sell",
                "code": "600519",
                "quantity": 40,
                "price": 12.0,
                "fees": 2.0,
            }
        )
        with self.db.get_session() as session:
            session.add(
                StockDaily(
                    code="600519",
                    date=date(2026, 3, 16),
                    close=11.0,
                )
            )
            session.commit()

        snapshot = self.service.generate_snapshot(portfolio_id="default", trade_date=date(2026, 3, 16))

        self.assertEqual(snapshot["portfolio_id"], "default")
        self.assertEqual(snapshot["trade_date"], "2026-03-16")
        self.assertAlmostEqual(snapshot["realized_pnl"], 76.0)
        self.assertAlmostEqual(snapshot["unrealized_pnl"], 57.0)
        self.assertAlmostEqual(snapshot["total_pnl"], 133.0)
        self.assertEqual(snapshot["win_trade_count"], 1)
        self.assertEqual(snapshot["loss_trade_count"], 0)

        items = self.repo.list_daily_pnl_snapshots(portfolio_id="default")
        self.assertEqual(len(items), 1)
        self.assertAlmostEqual(items[0]["total_pnl"], 133.0)

    def test_generate_daily_snapshot_rejects_sell_without_position(self) -> None:
        self.repo.add_execution_event(
            {
                "portfolio_id": "default",
                "executed_at": datetime(2026, 3, 16, 10, 0, 0),
                "side": "sell",
                "code": "600519",
                "quantity": 10,
                "price": 12.0,
                "fees": 2.0,
            }
        )

        with self.assertRaises(ValueError):
            self.service.generate_snapshot(portfolio_id="default", trade_date=date(2026, 3, 16))

    def test_generate_daily_snapshot_rejects_negative_fee_event(self) -> None:
        self.repo.add_execution_event(
            {
                "portfolio_id": "default",
                "executed_at": datetime(2026, 3, 16, 9, 30, 0),
                "side": "cash_in",
                "amount": 10000.0,
            }
        )
        self.repo.add_execution_event(
            {
                "portfolio_id": "default",
                "executed_at": datetime(2026, 3, 16, 10, 0, 0),
                "side": "buy",
                "code": "600519",
                "quantity": 100,
                "price": 10.0,
                "fees": -1.0,
            }
        )

        with self.assertRaises(ValueError):
            self.service.generate_snapshot(portfolio_id="default", trade_date=date(2026, 3, 16))

    def test_generate_daily_snapshot_rejects_inconsistent_trade_amount(self) -> None:
        self.repo.add_execution_event(
            {
                "portfolio_id": "default",
                "executed_at": datetime(2026, 3, 16, 9, 30, 0),
                "side": "cash_in",
                "amount": 10000.0,
            }
        )
        self.repo.add_execution_event(
            {
                "portfolio_id": "default",
                "executed_at": datetime(2026, 3, 16, 10, 0, 0),
                "side": "buy",
                "code": "600519",
                "quantity": 100,
                "price": 10.0,
                "amount": 1.0,
                "fees": 1.0,
            }
        )

        with self.assertRaises(ValueError):
            self.service.generate_snapshot(portfolio_id="default", trade_date=date(2026, 3, 16))


if __name__ == "__main__":
    unittest.main()
