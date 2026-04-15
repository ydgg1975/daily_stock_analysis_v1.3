# -*- coding: utf-8 -*-
"""Phase 1 multi-user ownership and migration coverage."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from src.multi_user import (
    BOOTSTRAP_ADMIN_USER_ID,
    OWNERSHIP_SCOPE_SYSTEM,
    OWNERSHIP_SCOPE_USER,
    ROLE_ADMIN,
)
from src.services.backtest_service import BacktestService
from src.services.market_scanner_service import MarketScannerService
from src.services.portfolio_service import PortfolioService
from src.storage import AnalysisHistory, DatabaseManager, MarketScannerRun, StockDaily


def _dummy_analysis_result(code: str, *, name: str) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        name=name,
        sentiment_score=65,
        operation_advice="买入",
        trend_prediction="看多",
        analysis_summary=f"{name} analysis",
        raw_result={"summary": f"{name} raw"},
        ideal_buy=None,
        secondary_buy=None,
        stop_loss=9.5,
        take_profit=11.0,
    )


class MultiUserLegacyMigrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "legacy_phase1.db"

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    def test_bootstrap_owner_and_legacy_rows_are_backfilled(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id VARCHAR(64),
                code VARCHAR(10) NOT NULL,
                name VARCHAR(50),
                report_type VARCHAR(16),
                sentiment_score INTEGER,
                operation_advice VARCHAR(20),
                trend_prediction VARCHAR(50),
                analysis_summary TEXT,
                raw_result TEXT,
                news_content TEXT,
                context_snapshot TEXT,
                ideal_buy FLOAT,
                secondary_buy FLOAT,
                stop_loss FLOAT,
                take_profit FLOAT,
                created_at DATETIME
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id VARCHAR(100) NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE market_scanner_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market VARCHAR(8) NOT NULL,
                profile VARCHAR(32) NOT NULL,
                universe_name VARCHAR(64) NOT NULL,
                status VARCHAR(16) NOT NULL,
                shortlist_size INTEGER NOT NULL,
                universe_size INTEGER,
                preselected_size INTEGER,
                evaluated_size INTEGER,
                run_at DATETIME,
                completed_at DATETIME,
                source_summary VARCHAR(255),
                summary_json TEXT,
                diagnostics_json TEXT,
                universe_notes_json TEXT,
                scoring_notes_json TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO analysis_history (
                query_id, code, name, report_type, sentiment_score, operation_advice,
                trend_prediction, analysis_summary, raw_result, context_snapshot, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-q1",
                "600519",
                "贵州茅台",
                "simple",
                70,
                "买入",
                "看多",
                "legacy analysis",
                "{}",
                '{"enhanced_context": {"date": "2026-04-01"}}',
                "2026-04-01T09:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO conversation_messages (session_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("legacy-session", "user", "legacy hello", "2026-04-01T09:00:00"),
        )
        conn.execute(
            """
            INSERT INTO market_scanner_runs (
                market, profile, universe_name, status, shortlist_size, universe_size,
                preselected_size, evaluated_size, run_at, completed_at, source_summary,
                summary_json, diagnostics_json, universe_notes_json, scoring_notes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cn",
                "cn_preopen_v1",
                "legacy",
                "completed",
                1,
                100,
                10,
                5,
                "2026-04-01T08:40:00",
                "2026-04-01T08:41:00",
                "scanner=legacy",
                '{"trigger_mode":"scheduled"}',
                '{"operation":{"trigger_mode":"scheduled","request_source":"scheduler"}}',
                "[]",
                "[]",
            ),
        )
        conn.execute(
            """
            INSERT INTO market_scanner_runs (
                market, profile, universe_name, status, shortlist_size, universe_size,
                preselected_size, evaluated_size, run_at, completed_at, source_summary,
                summary_json, diagnostics_json, universe_notes_json, scoring_notes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cn",
                "cn_preopen_v1",
                "legacy",
                "completed",
                1,
                100,
                10,
                5,
                "2026-04-02T08:40:00",
                "2026-04-02T08:41:00",
                "scanner=legacy",
                '{"trigger_mode":"manual"}',
                '{"operation":{"trigger_mode":"manual","request_source":"api"}}',
                "[]",
                "[]",
            ),
        )
        conn.commit()
        conn.close()

        db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")

        bootstrap = db.get_app_user(BOOTSTRAP_ADMIN_USER_ID)
        self.assertIsNotNone(bootstrap)
        self.assertEqual(bootstrap.role, ROLE_ADMIN)

        with db.get_session() as session:
            analysis_owner = session.execute(
                select(AnalysisHistory.owner_id).where(AnalysisHistory.query_id == "legacy-q1")
            ).scalar_one()
            runs = session.execute(
                select(MarketScannerRun).order_by(MarketScannerRun.id.asc())
            ).scalars().all()

        self.assertEqual(analysis_owner, BOOTSTRAP_ADMIN_USER_ID)
        self.assertEqual(db.get_chat_sessions(owner_id=BOOTSTRAP_ADMIN_USER_ID)[0]["session_id"], "legacy-session")
        self.assertEqual(runs[0].scope, OWNERSHIP_SCOPE_SYSTEM)
        self.assertIsNone(runs[0].owner_id)
        self.assertEqual(runs[1].scope, OWNERSHIP_SCOPE_USER)
        self.assertEqual(runs[1].owner_id, BOOTSTRAP_ADMIN_USER_ID)


class MultiUserOwnershipIsolationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")
        self.db.create_or_update_app_user(user_id="user-a", username="usera")
        self.db.create_or_update_app_user(user_id="user-b", username="userb")

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def test_analysis_history_is_scoped_by_owner(self) -> None:
        saved_a = self.db.save_analysis_history(
            _dummy_analysis_result("600519", name="贵州茅台"),
            query_id="qa",
            report_type="simple",
            news_content=None,
            owner_id="user-a",
        )
        saved_b = self.db.save_analysis_history(
            _dummy_analysis_result("000001", name="平安银行"),
            query_id="qb",
            report_type="simple",
            news_content=None,
            owner_id="user-b",
        )

        self.assertEqual(saved_a, 1)
        self.assertEqual(saved_b, 1)
        self.assertEqual(len(self.db.get_analysis_history(owner_id="user-a")), 1)
        self.assertEqual(self.db.get_analysis_history(owner_id="user-a")[0].query_id, "qa")
        self.assertEqual(len(self.db.get_analysis_history(owner_id="user-a", include_all_owners=True)), 2)
        record_b = self.db.get_analysis_history(owner_id="user-b")[0]
        self.assertIsNone(self.db.get_analysis_history_by_id(record_b.id, owner_id="user-a"))

    def test_chat_sessions_are_scoped_by_owner(self) -> None:
        self.db.save_conversation_message("session-a", "user", "hello a", owner_id="user-a")
        self.db.save_conversation_message("session-b", "user", "hello b", owner_id="user-b")

        sessions_a = self.db.get_chat_sessions(owner_id="user-a")
        self.assertEqual([item["session_id"] for item in sessions_a], ["session-a"])
        with self.assertRaises(ValueError):
            self.db.get_conversation_history("session-b", owner_id="user-a")

    def test_scanner_mixed_visibility_keeps_user_runs_private_and_system_runs_shared(self) -> None:
        service_a = MarketScannerService(self.db, owner_id="user-a")
        service_b = MarketScannerService(self.db, owner_id="user-b")

        run_a = service_a.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="Scanner",
            universe_name="fixture",
            status="completed",
            headline="user a run",
            trigger_mode="manual",
            request_source="api",
            watchlist_date="2026-04-14",
            source_summary="fixture",
            shortlist=[],
        )
        system_run = service_a.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="Scanner",
            universe_name="fixture",
            status="completed",
            headline="system run",
            trigger_mode="scheduled",
            request_source="scheduler",
            watchlist_date="2026-04-14",
            source_summary="fixture",
            shortlist=[],
        )
        run_b = service_b.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="Scanner",
            universe_name="fixture",
            status="completed",
            headline="user b run",
            trigger_mode="manual",
            request_source="api",
            watchlist_date="2026-04-14",
            source_summary="fixture",
            shortlist=[],
        )

        history_a = service_a.list_runs(market="cn", profile="cn_preopen_v1", page=1, limit=10)
        history_b = service_b.list_runs(market="cn", profile="cn_preopen_v1", page=1, limit=10)
        recent_watchlists = service_b.list_recent_watchlists(market="cn", profile="cn_preopen_v1", limit_days=5)

        self.assertEqual({item["id"] for item in history_a["items"]}, {run_a["id"], system_run["id"]})
        self.assertEqual({item["id"] for item in history_b["items"]}, {run_b["id"], system_run["id"]})
        self.assertEqual(recent_watchlists["total"], 1)
        self.assertEqual(recent_watchlists["items"][0]["id"], system_run["id"])

    def test_portfolio_defaults_to_bootstrap_owner_and_hides_other_users_accounts(self) -> None:
        bootstrap_service = PortfolioService()
        service_a = PortfolioService(owner_id="user-a")
        service_b = PortfolioService(owner_id="user-b")

        bootstrap_account = bootstrap_service.create_account(
            name="Bootstrap",
            broker="Demo",
            market="cn",
            base_currency="CNY",
        )
        user_a_account = service_a.create_account(
            name="User A",
            broker="Demo",
            market="cn",
            base_currency="CNY",
        )

        self.assertEqual(bootstrap_account["owner_id"], BOOTSTRAP_ADMIN_USER_ID)
        self.assertEqual(user_a_account["owner_id"], "user-a")
        self.assertEqual([item["id"] for item in bootstrap_service.list_accounts()], [bootstrap_account["id"]])
        self.assertEqual([item["id"] for item in service_a.list_accounts()], [user_a_account["id"]])
        self.assertEqual(service_b.list_accounts(), [])

    def test_backtest_only_evaluates_current_owners_analysis(self) -> None:
        created_at = datetime(2024, 1, 1, 0, 0, 0)
        with self.db.get_session() as session:
            session.add_all(
                [
                    AnalysisHistory(
                        owner_id="user-a",
                        query_id="qa",
                        code="600519",
                        name="贵州茅台",
                        report_type="simple",
                        sentiment_score=80,
                        operation_advice="买入",
                        trend_prediction="看多",
                        analysis_summary="owner a",
                        stop_loss=95.0,
                        take_profit=110.0,
                        created_at=created_at,
                        context_snapshot='{"enhanced_context":{"date":"2024-01-01"}}',
                    ),
                    AnalysisHistory(
                        owner_id="user-b",
                        query_id="qb",
                        code="000001",
                        name="平安银行",
                        report_type="simple",
                        sentiment_score=40,
                        operation_advice="卖出",
                        trend_prediction="看空",
                        analysis_summary="owner b",
                        created_at=created_at,
                        context_snapshot='{"enhanced_context":{"date":"2024-01-01"}}',
                    ),
                ]
            )
            session.add_all(
                [
                    StockDaily(code="600519", date=date(2024, 1, 1), open=100.0, high=101.0, low=99.0, close=100.0),
                    StockDaily(code="600519", date=date(2024, 1, 2), open=105.0, high=111.0, low=100.0, close=105.0),
                    StockDaily(code="600519", date=date(2024, 1, 3), open=106.0, high=108.0, low=103.0, close=106.0),
                    StockDaily(code="600519", date=date(2024, 1, 4), open=107.0, high=109.0, low=104.0, close=107.0),
                    StockDaily(code="000001", date=date(2024, 1, 1), open=10.0, high=10.2, low=9.8, close=10.0),
                    StockDaily(code="000001", date=date(2024, 1, 2), open=9.6, high=10.0, low=9.0, close=9.3),
                    StockDaily(code="000001", date=date(2024, 1, 3), open=9.2, high=9.5, low=9.0, close=9.1),
                    StockDaily(code="000001", date=date(2024, 1, 4), open=9.1, high=9.4, low=8.9, close=9.0),
                ]
            )
            session.commit()

        service_a = BacktestService(self.db, owner_id="user-a")
        service_b = BacktestService(self.db, owner_id="user-b")

        stats_a = service_a.run_backtest(force=False, eval_window_days=3, min_age_days=0, limit=10)
        stats_b = service_b.run_backtest(force=False, eval_window_days=3, min_age_days=0, limit=10)

        self.assertEqual(stats_a["saved"], 1)
        self.assertEqual(stats_b["saved"], 1)
        self.assertEqual(service_a.get_recent_evaluations(code=None)["items"][0]["code"], "600519")
        self.assertEqual(service_b.get_recent_evaluations(code=None)["items"][0]["code"], "000001")


if __name__ == "__main__":
    unittest.main()
