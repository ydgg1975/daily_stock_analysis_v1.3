import os
import tempfile
import unittest
from datetime import date, datetime

from src.config import Config
from src.repositories.portfolio_repo import PortfolioRepository
from src.services.portfolio_state_service import PortfolioStateService
from src.storage import DatabaseManager, StockDaily


class PortfolioStateServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_portfolio_state_service.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.repo = PortfolioRepository(self.db)
        self.service = PortfolioStateService(self.repo, self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self._temp_dir.cleanup()

    def test_build_portfolio_state_from_execution_events(self) -> None:
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
        with self.db.get_session() as session:
            session.add(
                StockDaily(
                    code="600519",
                    date=date(2026, 3, 16),
                    close=11.0,
                )
            )
            session.commit()

        state = self.service.build_state(portfolio_id="default", as_of_date=date(2026, 3, 16))

        self.assertEqual(state["portfolio_id"], "default")
        self.assertAlmostEqual(state["cash"], 8995.0)
        self.assertAlmostEqual(state["market_value"], 1100.0)
        self.assertAlmostEqual(state["total_equity"], 10095.0)
        self.assertAlmostEqual(state["total_unrealized_pnl"], 95.0)
        self.assertEqual(len(state["holdings"]), 1)
        holding = state["holdings"][0]
        self.assertEqual(holding["code"], "600519")
        self.assertEqual(holding["quantity"], 100.0)
        self.assertAlmostEqual(holding["avg_cost"], 10.05, places=2)
        self.assertAlmostEqual(holding["latest_price"], 11.0)
        self.assertAlmostEqual(holding["unrealized_pnl"], 95.0)

    def test_sell_updates_realized_pnl_and_removes_empty_position(self) -> None:
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
                "executed_at": datetime(2026, 3, 17, 10, 0, 0),
                "side": "sell",
                "code": "600519",
                "quantity": 100,
                "price": 12.0,
                "fees": 5.0,
            }
        )

        state = self.service.build_state(portfolio_id="default", as_of_date=date(2026, 3, 17))

        self.assertEqual(state["holdings"], [])
        self.assertAlmostEqual(state["cash"], 10190.0)
        self.assertAlmostEqual(state["total_realized_pnl"], 190.0)
        self.assertAlmostEqual(state["market_value"], 0.0)


if __name__ == "__main__":
    unittest.main()
