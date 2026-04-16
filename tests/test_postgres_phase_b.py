# -*- coding: utf-8 -*-
"""Focused coverage for the PostgreSQL Phase B analysis/chat baseline."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.analyzer import AnalysisResult
import src.auth as auth
from src.config import Config
from src.postgres_phase_b import (
    PhaseBAnalysisRecord,
    PhaseBAnalysisSession,
    PhaseBChatMessage,
    PhaseBChatSession,
)
from src.storage import AnalysisHistory, ConversationMessage, ConversationSessionRecord, DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _build_result(code: str, *, name: str) -> AnalysisResult:
    result = AnalysisResult(
        code=code,
        name=name,
        sentiment_score=81,
        trend_prediction="看多",
        operation_advice="持有",
        analysis_summary=f"{name} summary",
    )
    result.model_used = "openai/gpt-5.4"
    result.dashboard = {
        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "128.5元",
                "secondary_buy": "126.0元",
                "stop_loss": "120元",
                "take_profit": "138元",
            }
        }
    }
    return result


class PostgresPhaseBStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.phase_db_path = self.data_dir / "phase-baseline.sqlite"
        self._configure_environment(enable_phase_b=True)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self.temp_dir.cleanup()

    def _configure_environment(self, *, enable_phase_b: bool) -> None:
        lines = [
            "STOCK_LIST=600519",
            "GEMINI_API_KEY=test",
            "ADMIN_AUTH_ENABLED=true",
            f"DATABASE_PATH={self.sqlite_db_path}",
        ]
        if enable_phase_b:
            lines.extend(
                [
                    f"POSTGRES_PHASE_A_URL=sqlite:///{self.phase_db_path}",
                    "POSTGRES_PHASE_A_APPLY_SCHEMA=true",
                ]
            )

        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        if enable_phase_b:
            os.environ["POSTGRES_PHASE_A_URL"] = f"sqlite:///{self.phase_db_path}"
            os.environ["POSTGRES_PHASE_A_APPLY_SCHEMA"] = "true"
        else:
            os.environ.pop("POSTGRES_PHASE_A_URL", None)
            os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)

        Config.reset_instance()
        DatabaseManager.reset_instance()
        auth.refresh_auth_state()

    def _db(self) -> DatabaseManager:
        return DatabaseManager.get_instance()

    def test_phase_b_dual_writes_analysis_history_without_changing_sqlite_history_surface(self) -> None:
        db = self._db()
        db.create_or_update_app_user(user_id="analysis-user", username="analysis-user")

        saved = db.save_analysis_history(
            result=_build_result("600519", name="贵州茅台"),
            query_id="phase-b-analysis",
            report_type="simple",
            news_content="news body",
            context_snapshot={"enhanced_context": {"source": "fixture"}},
            owner_id="analysis-user",
        )

        self.assertEqual(saved, 1)
        self.assertIsNotNone(db._phase_b_store)
        history_rows = db.get_analysis_history(query_id="phase-b-analysis", owner_id="analysis-user", limit=5)
        self.assertEqual(len(history_rows), 1)

        with db.get_session() as session:
            sqlite_row = (
                session.query(AnalysisHistory)
                .filter(AnalysisHistory.query_id == "phase-b-analysis")
                .one()
            )

        with db._phase_b_store.session_scope() as session:
            pg_sessions = session.query(PhaseBAnalysisSession).all()
            pg_records = session.query(PhaseBAnalysisRecord).all()

        self.assertEqual(len(pg_sessions), 1)
        self.assertEqual(len(pg_records), 1)
        self.assertEqual(pg_sessions[0].owner_user_id, "analysis-user")
        self.assertEqual(pg_records[0].legacy_analysis_history_id, sqlite_row.id)
        self.assertEqual(pg_records[0].query_id, "phase-b-analysis")
        self.assertEqual(pg_records[0].canonical_symbol, "600519")
        self.assertEqual(pg_records[0].summary_text, "贵州茅台 summary")

    def test_phase_b_dual_writes_chat_sessions_and_messages_without_changing_current_reads(self) -> None:
        db = self._db()
        db.create_or_update_app_user(user_id="chat-user", username="chat-user")

        db.save_conversation_message("chat-phase-b", "user", "hello", owner_id="chat-user")
        db.save_conversation_message("chat-phase-b", "assistant", "world", owner_id="chat-user")

        sessions = db.get_chat_sessions(owner_id="chat-user")
        messages = db.get_conversation_messages("chat-phase-b", owner_id="chat-user")

        self.assertEqual([item["session_id"] for item in sessions], ["chat-phase-b"])
        self.assertEqual([item["role"] for item in messages], ["user", "assistant"])

        with db.get_session() as session:
            self.assertEqual(
                session.query(ConversationSessionRecord)
                .filter(ConversationSessionRecord.session_id == "chat-phase-b")
                .count(),
                1,
            )
            self.assertEqual(
                session.query(ConversationMessage)
                .filter(ConversationMessage.session_id == "chat-phase-b")
                .count(),
                2,
            )

        with db._phase_b_store.session_scope() as session:
            pg_session = (
                session.query(PhaseBChatSession)
                .filter(PhaseBChatSession.session_key == "chat-phase-b")
                .one()
            )
            pg_messages = (
                session.query(PhaseBChatMessage)
                .filter(PhaseBChatMessage.chat_session_id == pg_session.id)
                .order_by(PhaseBChatMessage.message_index.asc())
                .all()
            )

        self.assertEqual(pg_session.owner_user_id, "chat-user")
        self.assertEqual([row.message_index for row in pg_messages], [0, 1])
        self.assertEqual([row.role for row in pg_messages], ["user", "assistant"])

    def test_phase_b_delete_paths_clear_postgres_shadow_rows(self) -> None:
        db = self._db()
        db.create_or_update_app_user(user_id="cleanup-user", username="cleanup-user")

        saved = db.save_analysis_history(
            result=_build_result("000001", name="平安银行"),
            query_id="cleanup-analysis",
            report_type="simple",
            news_content="cleanup news",
            owner_id="cleanup-user",
        )
        self.assertEqual(saved, 1)
        db.save_conversation_message("cleanup-chat", "user", "cleanup", owner_id="cleanup-user")

        analysis_row = db.get_analysis_history(query_id="cleanup-analysis", owner_id="cleanup-user", limit=1)[0]

        deleted_history = db.delete_analysis_history_records([analysis_row.id], owner_id="cleanup-user")
        deleted_chat = db.delete_conversation_session("cleanup-chat", owner_id="cleanup-user")

        self.assertEqual(deleted_history, 1)
        self.assertEqual(deleted_chat, 1)

        with db._phase_b_store.session_scope() as session:
            self.assertEqual(session.query(PhaseBAnalysisRecord).count(), 0)
            self.assertEqual(session.query(PhaseBAnalysisSession).count(), 0)
            self.assertEqual(session.query(PhaseBChatMessage).count(), 0)
            self.assertEqual(session.query(PhaseBChatSession).count(), 0)

    def test_phase_b_enablement_keeps_legacy_sqlite_analysis_and_chat_visible(self) -> None:
        self._configure_environment(enable_phase_b=False)
        legacy_db = self._db()
        legacy_db.create_or_update_app_user(user_id="legacy-user", username="legacy-user")
        legacy_db.save_analysis_history(
            result=_build_result("AAPL", name="Apple"),
            query_id="legacy-analysis",
            report_type="simple",
            news_content="legacy news",
            owner_id="legacy-user",
        )
        legacy_db.save_conversation_message("legacy-chat", "user", "legacy hello", owner_id="legacy-user")

        self._configure_environment(enable_phase_b=True)
        db = self._db()

        history_rows = db.get_analysis_history(query_id="legacy-analysis", owner_id="legacy-user", limit=5)
        chat_sessions = db.get_chat_sessions(owner_id="legacy-user")

        self.assertEqual(len(history_rows), 1)
        self.assertEqual(history_rows[0].query_id, "legacy-analysis")
        self.assertEqual([item["session_id"] for item in chat_sessions], ["legacy-chat"])

    def test_phase_b_shadow_rows_preserve_owner_partitioning(self) -> None:
        db = self._db()
        db.create_or_update_app_user(user_id="user-a", username="user-a")
        db.create_or_update_app_user(user_id="user-b", username="user-b")

        db.save_analysis_history(
            result=_build_result("600519", name="贵州茅台"),
            query_id="analysis-a",
            report_type="simple",
            news_content=None,
            owner_id="user-a",
        )
        db.save_analysis_history(
            result=_build_result("000001", name="平安银行"),
            query_id="analysis-b",
            report_type="simple",
            news_content=None,
            owner_id="user-b",
        )
        db.save_conversation_message("chat-a", "user", "hello a", owner_id="user-a")
        db.save_conversation_message("chat-b", "user", "hello b", owner_id="user-b")

        self.assertEqual([row.query_id for row in db.get_analysis_history(owner_id="user-a")], ["analysis-a"])
        self.assertEqual([row.query_id for row in db.get_analysis_history(owner_id="user-b")], ["analysis-b"])
        self.assertEqual([item["session_id"] for item in db.get_chat_sessions(owner_id="user-a")], ["chat-a"])
        self.assertEqual([item["session_id"] for item in db.get_chat_sessions(owner_id="user-b")], ["chat-b"])

        with db._phase_b_store.session_scope() as session:
            self.assertEqual(
                {
                    (row.owner_user_id, row.current_query)
                    for row in session.query(PhaseBAnalysisSession).all()
                },
                {("user-a", "analysis-a"), ("user-b", "analysis-b")},
            )
            self.assertEqual(
                {
                    (row.owner_user_id, row.session_key)
                    for row in session.query(PhaseBChatSession).all()
                },
                {("user-a", "chat-a"), ("user-b", "chat-b")},
            )


if __name__ == "__main__":
    unittest.main()
