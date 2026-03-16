import os
import tempfile
import unittest
from datetime import date, datetime

from src.config import Config
from src.repositories.portfolio_repo import PortfolioRepository
from src.services.capital_allocation_service import CapitalAllocationService
from src.services.portfolio_state_service import PortfolioStateService
from src.storage import DatabaseManager, StockDaily


class CapitalAllocationServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_capital_allocation_service.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.repo = PortfolioRepository(self.db)
        self.portfolio_state_service = PortfolioStateService(self.repo, self.db)
        self.service = CapitalAllocationService(portfolio_state_service=self.portfolio_state_service)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self._temp_dir.cleanup()

    def test_build_gate_allows_new_positions_when_exposure_below_limit(self) -> None:
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
            session.add(StockDaily(code="600519", date=date(2026, 3, 16), close=11.0))
            session.commit()

        gate = self.service.build_gate(portfolio_id="default", as_of_date=date(2026, 3, 16))

        self.assertTrue(gate["allow_new_positions"])
        self.assertGreater(gate["available_position_ratio"], 0.0)
        self.assertEqual(gate["reasons"], [])

    def test_build_gate_blocks_when_position_limit_is_reached(self) -> None:
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
                "quantity": 900,
                "price": 10.0,
                "fees": 0.0,
            }
        )
        with self.db.get_session() as session:
            session.add(StockDaily(code="600519", date=date(2026, 3, 16), close=10.0))
            session.commit()

        gate = self.service.build_gate(portfolio_id="default", as_of_date=date(2026, 3, 16))

        self.assertFalse(gate["allow_new_positions"])
        self.assertIn("position_limit_reached", gate["reasons"])


if __name__ == "__main__":
    unittest.main()
