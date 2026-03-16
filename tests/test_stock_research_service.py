import os
import tempfile
import unittest
from datetime import date, datetime
from types import SimpleNamespace

from src.config import Config
from src.services.stock_research_service import StockResearchService
from src.storage import DatabaseManager, ScreeningCandidate, ScreeningRun


class StockResearchServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_stock_research_service.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()
        self.service = StockResearchService(self.db)

        with self.db.get_session() as session:
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

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)
        self._temp_dir.cleanup()

    def test_build_packet_enriches_candidates_with_analysis_and_news(self) -> None:
        payload = self.service.build_packet(as_of_date=date(2026, 3, 16))

        self.assertEqual(payload["run_id"], "run-1")
        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertEqual(item["code"], "000001")
        self.assertEqual(item["latest_analysis"]["analysis_summary"], "候选股突破结构明确。")
        self.assertEqual(item["recent_news"][0]["title"], "平安银行业绩超预期")

    def test_build_packet_prefers_analysis_matching_candidate_query_id(self) -> None:
        self.db.save_analysis_history(
            result=SimpleNamespace(
                code="000001",
                name="平安银行",
                sentiment_score=60,
                trend_prediction="震荡",
                operation_advice="观察",
                analysis_summary="这是后续的非候选分析。",
                dashboard=None,
            ),
            query_id="query-other",
            report_type="simple",
            news_content="其他新闻",
            context_snapshot=None,
            save_snapshot=False,
        )

        payload = self.service.build_packet(as_of_date=date(2026, 3, 16))

        item = payload["items"][0]
        self.assertEqual(item["latest_analysis"]["query_id"], "query-candidate-1")
        self.assertEqual(item["latest_analysis"]["analysis_summary"], "候选股突破结构明确。")


if __name__ == "__main__":
    unittest.main()
