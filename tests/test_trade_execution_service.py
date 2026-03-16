import os
import tempfile
import unittest
from datetime import datetime

from src.config import Config
from src.repositories.portfolio_repo import PortfolioRepository
from src.services.trade_execution_service import TradeExecutionService
from src.storage import DatabaseManager


class TradeExecutionServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_trade_execution_service.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.repo = PortfolioRepository(self.db)
        self.service = TradeExecutionService(self.repo)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self._temp_dir.cleanup()

    def test_record_trade_normalizes_code_and_computes_amount(self) -> None:
        record = self.service.record_execution(
            portfolio_id="default",
            executed_at=datetime(2026, 3, 16, 10, 0, 0),
            side="buy",
            code="hk00700",
            quantity=2,
            price=500.0,
            fees=3.0,
        )

        self.assertEqual(record["code"], "HK00700")
        self.assertEqual(record["gross_amount"], 1000.0)
        self.assertEqual(record["net_cash_flow"], -1003.0)

    def test_record_execution_rejects_unknown_side(self) -> None:
        with self.assertRaises(ValueError):
            self.service.record_execution(
                portfolio_id="default",
                executed_at=datetime(2026, 3, 16, 10, 0, 0),
                side="unknown",
            )


if __name__ == "__main__":
    unittest.main()
