import os
import tempfile
import unittest
from datetime import date, datetime
from types import SimpleNamespace

from src.config import Config
from src.repositories.portfolio_repo import PortfolioRepository
from src.services.holding_review_service import HoldingReviewService
from src.services.noon_monitor_service import NoonMonitorService
from src.services.portfolio_state_service import PortfolioStateService
from src.services.candidate_pool_service import CandidatePoolService
from src.storage import DatabaseManager, ScreeningCandidate, ScreeningRun, StockDaily


class NoonMonitorServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_noon_monitor_service.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.repo = PortfolioRepository(self.db)
        self.portfolio_state_service = PortfolioStateService(self.repo, self.db)
        self.holding_review_service = HoldingReviewService(
            repo=self.repo,
            db_manager=self.db,
            portfolio_state_service=self.portfolio_state_service,
        )
        self.candidate_pool_service = CandidatePoolService(self.db)
        self.service = NoonMonitorService(
            holding_review_service=self.holding_review_service,
            candidate_pool_service=self.candidate_pool_service,
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
                ScreeningRun(
                    run_id="run-1",
                    trade_date=date(2026, 3, 16),
                    market="cn",
                    status="completed",
                    candidate_count=1,
                    ai_top_k=1,
                    config_snapshot='{"mode":"balanced"}',
                    started_at=datetime(2026, 3, 16, 15, 0, 0),
                )
            )
            session.commit()

        with self.db.get_session() as session:
            session.add(
                ScreeningCandidate(
                    run_id="run-1",
                    code="000001",
                    name="平安银行",
                    rank=1,
                    rule_score=90.0,
                    selected_for_ai=True,
                    rule_hits_json='["trend_aligned"]',
                    factor_snapshot_json='{"close": 12.0}',
                    ai_query_id="query-candidate-1",
                    ai_summary="量价结构健康。",
                    ai_operation_advice="买入",
                    created_at=datetime(2026, 3, 16, 15, 30, 0),
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
        self.db.save_news_intel(
            code="000001",
            name="平安银行",
            dimension="latest_news",
            query="平安银行 最新消息",
            response=SimpleNamespace(
                provider="stub",
                results=[
                    SimpleNamespace(
                        title="平安银行业绩超预期",
                        snippet="基本面改善。",
                        url="https://example.com/candidate-news",
                        source="stub",
                        published_date=None,
                    )
                ],
            ),
            query_context={"query_id": "query-candidate-1"},
        )

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self._temp_dir.cleanup()

    def test_build_packet_combines_holdings_and_watchlist(self) -> None:
        payload = self.service.build_packet(portfolio_id="default", as_of_date=date(2026, 3, 16))

        self.assertEqual(payload["portfolio_id"], "default")
        self.assertEqual(len(payload["holdings"]), 1)
        self.assertEqual(payload["holdings"][0]["code"], "600519")
        self.assertEqual(len(payload["watchlist"]), 1)
        self.assertEqual(payload["watchlist"][0]["code"], "000001")


if __name__ == "__main__":
    unittest.main()
