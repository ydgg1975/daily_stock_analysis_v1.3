import os
import tempfile
import unittest
from datetime import date, datetime
from types import SimpleNamespace

from src.config import Config
from src.repositories.portfolio_repo import PortfolioRepository
from src.services.holding_review_service import HoldingReviewService
from src.services.portfolio_state_service import PortfolioStateService
from src.storage import BacktestSummary, DatabaseManager, StockDaily


class HoldingReviewServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_holding_review_service.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.repo = PortfolioRepository(self.db)
        self.portfolio_state_service = PortfolioStateService(self.repo, self.db)
        self.service = HoldingReviewService(
            repo=self.repo,
            db_manager=self.db,
            portfolio_state_service=self.portfolio_state_service,
        )

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
            session.add(
                BacktestSummary(
                    scope="stock",
                    code="600519",
                    eval_window_days=10,
                    engine_version="v1",
                    total_evaluations=4,
                    completed_count=4,
                    win_count=3,
                    loss_count=1,
                    win_rate_pct=75.0,
                    computed_at=datetime(2026, 3, 16, 16, 0, 0),
                )
            )
            session.commit()

        self.db.save_analysis_history(
            result=SimpleNamespace(
                code="600519",
                name="贵州茅台",
                sentiment_score=80,
                trend_prediction="看多",
                operation_advice="持有",
                analysis_summary="持仓趋势未破坏。",
                dashboard=None,
            ),
            query_id="query-holding-1",
            report_type="simple",
            news_content="持仓新闻",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.db.save_news_intel(
            code="600519",
            name="贵州茅台",
            dimension="latest_news",
            query="贵州茅台 最新消息",
            response=SimpleNamespace(
                provider="stub",
                results=[
                    SimpleNamespace(
                        title="贵州茅台回购计划推进",
                        snippet="利好持仓信心。",
                        url="https://example.com/holding-news",
                        source="stub",
                        published_date=None,
                    )
                ],
            ),
            query_context={"query_id": "query-holding-1"},
        )

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self._temp_dir.cleanup()

    def test_build_packet_aggregates_holding_analysis_news_and_backtest(self) -> None:
        packet = self.service.build_packet(portfolio_id="default", as_of_date=date(2026, 3, 16))

        self.assertEqual(packet["portfolio_id"], "default")
        self.assertEqual(len(packet["items"]), 1)
        item = packet["items"][0]
        self.assertEqual(item["code"], "600519")
        self.assertEqual(item["latest_analysis"]["analysis_summary"], "持仓趋势未破坏。")
        self.assertEqual(item["news_count"], 1)
        self.assertEqual(item["recent_news"][0]["title"], "贵州茅台回购计划推进")
        self.assertEqual(item["backtest_summary"]["win_rate_pct"], 75.0)


if __name__ == "__main__":
    unittest.main()
