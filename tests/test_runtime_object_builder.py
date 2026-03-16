import os
import tempfile
import unittest
from datetime import date, datetime
from types import SimpleNamespace

from sqlalchemy import select

from src.config import Config
from src.repositories.portfolio_repo import PortfolioRepository
from src.services.daily_pnl_service import DailyPnlService
from src.services.portfolio_state_service import PortfolioStateService
from src.services.runtime_object_builder import RuntimeObjectBuilder
from src.storage import AnalysisHistory, BacktestSummary, DatabaseManager, ScreeningCandidate, ScreeningRun, StockDaily


class RuntimeObjectBuilderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_runtime_object_builder.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.repo = PortfolioRepository(self.db)
        self.portfolio_state_service = PortfolioStateService(self.repo, self.db)
        self.daily_pnl_service = DailyPnlService(self.repo, self.portfolio_state_service)
        self.builder = RuntimeObjectBuilder(
            repo=self.repo,
            db_manager=self.db,
            portfolio_state_service=self.portfolio_state_service,
            daily_pnl_service=self.daily_pnl_service,
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
            session.add(StockDaily(code="000001", date=date(2026, 3, 16), close=12.0))
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
            session.add(
                BacktestSummary(
                    scope="stock",
                    code="000001",
                    eval_window_days=10,
                    engine_version="v1",
                    total_evaluations=5,
                    completed_count=5,
                    win_count=4,
                    loss_count=1,
                    win_rate_pct=80.0,
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
        self.db.save_analysis_history(
            result=SimpleNamespace(
                code="000001",
                name="平安银行",
                sentiment_score=78,
                trend_prediction="看多",
                operation_advice="买入",
                analysis_summary="候选股突破结构明确。",
                dashboard=None,
            ),
            query_id="query-candidate-1",
            report_type="simple",
            news_content="候选新闻",
            context_snapshot=None,
            save_snapshot=False,
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
        self.daily_pnl_service.generate_snapshot(portfolio_id="default", trade_date=date(2026, 3, 16))

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self._temp_dir.cleanup()

    def test_build_holding_review_capital_gate_and_noon_monitor(self) -> None:
        holding_review = self.builder.build_object("holding_review_packet", portfolio_id="default", as_of_date=date(2026, 3, 16))
        capital_gate = self.builder.build_object("capital_allocation_gate", portfolio_id="default", as_of_date=date(2026, 3, 16))
        noon_monitor = self.builder.build_object("noon_monitor_packet", portfolio_id="default", as_of_date=date(2026, 3, 16))

        self.assertEqual(holding_review["portfolio_id"], "default")
        self.assertEqual(len(holding_review["items"]), 1)
        self.assertEqual(holding_review["items"][0]["code"], "600519")
        self.assertEqual(holding_review["items"][0]["latest_analysis"]["analysis_summary"], "持仓趋势未破坏。")
        self.assertEqual(holding_review["items"][0]["news_count"], 1)

        self.assertTrue(capital_gate["allow_new_positions"])
        self.assertGreater(capital_gate["available_position_ratio"], 0.0)

        self.assertEqual(noon_monitor["portfolio_id"], "default")
        self.assertEqual(len(noon_monitor["holdings"]), 1)
        self.assertEqual(len(noon_monitor["watchlist"]), 1)

    def test_build_candidate_pool_and_stock_research_packet(self) -> None:
        candidate_pool = self.builder.build_object("candidate_pool", as_of_date=date(2026, 3, 16))
        research_packet = self.builder.build_object("stock_research_packet", as_of_date=date(2026, 3, 16))

        self.assertEqual(candidate_pool["run_id"], "run-1")
        self.assertEqual(len(candidate_pool["items"]), 1)
        self.assertEqual(candidate_pool["items"][0]["code"], "000001")

        self.assertEqual(research_packet["run_id"], "run-1")
        self.assertEqual(research_packet["items"][0]["code"], "000001")
        self.assertEqual(research_packet["items"][0]["latest_analysis"]["analysis_summary"], "候选股突破结构明确。")
        self.assertEqual(research_packet["items"][0]["recent_news"][0]["title"], "平安银行业绩超预期")

    def test_as_of_date_filters_future_runtime_data(self) -> None:
        self.db.save_analysis_history(
            result=SimpleNamespace(
                code="600519",
                name="贵州茅台",
                sentiment_score=50,
                trend_prediction="转弱",
                operation_advice="减仓",
                analysis_summary="这是一条未来分析，不应出现在历史快照中。",
                dashboard=None,
            ),
            query_id="query-holding-future",
            report_type="simple",
            news_content="未来新闻",
            context_snapshot=None,
            save_snapshot=False,
        )
        with self.db.get_session() as session:
            future_analysis = session.execute(
                select(AnalysisHistory)
                .where(AnalysisHistory.query_id == "query-holding-future")
                .limit(1)
            ).scalar_one()
            future_analysis.created_at = datetime(2026, 3, 17, 10, 0, 0)
            future_backtest = session.execute(
                select(BacktestSummary)
                .where(BacktestSummary.code == "600519")
                .limit(1)
            ).scalar_one()
            future_backtest.computed_at = datetime(2026, 3, 17, 16, 0, 0)
            session.commit()

        self.db.save_news_intel(
            code="600519",
            name="贵州茅台",
            dimension="latest_news",
            query="贵州茅台 未来消息",
            response=SimpleNamespace(
                provider="stub",
                results=[
                    SimpleNamespace(
                        title="未来新闻不应泄漏",
                        snippet="未来数据",
                        url="https://example.com/future-news",
                        source="stub",
                        published_date="2026-03-17T12:00:00",
                    )
                ],
            ),
            query_context={"query_id": "query-holding-future"},
        )

        holding_review = self.builder.build_object("holding_review_packet", portfolio_id="default", as_of_date=date(2026, 3, 16))
        latest_analysis = holding_review["items"][0]["latest_analysis"]
        news_titles = [item["title"] for item in holding_review["items"][0]["recent_news"]]
        backtest_summary = holding_review["items"][0]["backtest_summary"]

        self.assertEqual(latest_analysis["analysis_summary"], "持仓趋势未破坏。")
        self.assertNotIn("未来新闻不应泄漏", news_titles)
        self.assertIsNone(backtest_summary)

    def test_build_daily_pnl_log_does_not_write_snapshot_as_side_effect(self) -> None:
        empty_repo = PortfolioRepository(self.db)
        empty_builder = RuntimeObjectBuilder(
            repo=empty_repo,
            db_manager=self.db,
            portfolio_state_service=PortfolioStateService(empty_repo, self.db),
            daily_pnl_service=DailyPnlService(empty_repo, PortfolioStateService(empty_repo, self.db)),
        )

        items_before = empty_repo.list_daily_pnl_snapshots(portfolio_id="new-portfolio")
        payload = empty_builder.build_object("daily_pnl_log", portfolio_id="new-portfolio", as_of_date=date(2026, 3, 16))
        items_after = empty_repo.list_daily_pnl_snapshots(portfolio_id="new-portfolio")

        self.assertEqual(items_before, [])
        self.assertEqual(payload["items"], [])
        self.assertEqual(items_after, [])

    def test_candidate_pool_as_of_date_does_not_include_future_news_enrichment(self) -> None:
        self.db.save_news_intel(
            code="000001",
            name="平安银行",
            dimension="latest_news",
            query="平安银行 未来消息",
            response=SimpleNamespace(
                provider="stub",
                results=[
                    SimpleNamespace(
                        title="未来候选新闻",
                        snippet="未来数据",
                        url="https://example.com/future-candidate-news",
                        source="stub",
                        published_date="2026-03-17T12:00:00",
                    )
                ],
            ),
            query_context={"query_id": "query-candidate-1"},
        )

        candidate_pool = self.builder.build_object("candidate_pool", as_of_date=date(2026, 3, 16))

        self.assertEqual(candidate_pool["items"][0]["news_count"], 1)
        self.assertEqual(candidate_pool["items"][0]["news_summary"], "平安银行业绩超预期")


if __name__ == "__main__":
    unittest.main()
