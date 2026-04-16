# -*- coding: utf-8 -*-
"""Real PostgreSQL validation for the Phase B analysis/chat baseline."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy import create_engine, text

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from src.analyzer import AnalysisResult
from src.config import Config
from src.postgres_phase_b import (
    PhaseBAnalysisRecord,
    PhaseBAnalysisSession,
    PhaseBChatMessage,
    PhaseBChatSession,
)
from src.storage import DatabaseManager

REAL_PG_DSN = str(os.getenv("POSTGRES_PHASE_A_REAL_DSN") or "").strip()


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
        sentiment_score=77,
        trend_prediction="看多",
        operation_advice="持有",
        analysis_summary=f"{name} phase-b",
    )
    result.model_used = "openai/gpt-5.4"
    return result


@unittest.skipUnless(REAL_PG_DSN, "POSTGRES_PHASE_A_REAL_DSN is required for real PostgreSQL validation")
class PostgresPhaseBRealPgTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.pg_engine = create_engine(REAL_PG_DSN, echo=False, pool_pre_ping=True)
        self._drop_phase_b_tables()
        self._configure_environment()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self._drop_phase_b_tables()
        self.pg_engine.dispose()
        self.temp_dir.cleanup()

    def _configure_environment(self) -> None:
        lines = [
            "STOCK_LIST=600519",
            "GEMINI_API_KEY=test",
            "ADMIN_AUTH_ENABLED=true",
            f"DATABASE_PATH={self.sqlite_db_path}",
            f"POSTGRES_PHASE_A_URL={REAL_PG_DSN}",
            "POSTGRES_PHASE_A_APPLY_SCHEMA=true",
        ]
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        os.environ["POSTGRES_PHASE_A_URL"] = REAL_PG_DSN
        os.environ["POSTGRES_PHASE_A_APPLY_SCHEMA"] = "true"
        Config.reset_instance()
        DatabaseManager.reset_instance()
        auth.refresh_auth_state()

    def _db(self) -> DatabaseManager:
        return DatabaseManager.get_instance()

    def _drop_phase_b_tables(self) -> None:
        with self.pg_engine.begin() as conn:
            conn.execute(text("drop table if exists chat_messages cascade"))
            conn.execute(text("drop table if exists chat_sessions cascade"))
            conn.execute(text("drop table if exists analysis_records cascade"))
            conn.execute(text("drop table if exists analysis_sessions cascade"))

    def _pg_scalar(self, sql: str, **params):
        with self.pg_engine.begin() as conn:
            return conn.execute(text(sql), params).scalar()

    def test_real_postgres_phase_b_shadow_writes_and_delete_paths(self) -> None:
        db = self._db()
        db.create_or_update_app_user(user_id="pg-phase-b-user", username="pg-phase-b-user")

        saved = db.save_analysis_history(
            result=_build_result("600519", name="贵州茅台"),
            query_id="pg-phase-b-analysis",
            report_type="simple",
            news_content="pg news",
            context_snapshot={"enhanced_context": {"fixture": True}},
            owner_id="pg-phase-b-user",
        )
        self.assertEqual(saved, 1)
        db.save_conversation_message("pg-phase-b-chat", "user", "hello pg", owner_id="pg-phase-b-user")
        db.save_conversation_message("pg-phase-b-chat", "assistant", "world pg", owner_id="pg-phase-b-user")

        history_rows = db.get_analysis_history(query_id="pg-phase-b-analysis", owner_id="pg-phase-b-user", limit=5)
        self.assertEqual(len(history_rows), 1)
        self.assertEqual([item["session_id"] for item in db.get_chat_sessions(owner_id="pg-phase-b-user")], ["pg-phase-b-chat"])

        self.assertEqual(self._pg_scalar("select count(*) from analysis_sessions"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from analysis_records"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from chat_sessions"), 1)
        self.assertEqual(self._pg_scalar("select count(*) from chat_messages"), 2)
        self.assertEqual(
            self._pg_scalar(
                "select count(*) from chat_sessions where session_key = :session_key",
                session_key="pg-phase-b-chat",
            ),
            1,
        )

        deleted_history = db.delete_analysis_history_records([history_rows[0].id], owner_id="pg-phase-b-user")
        deleted_chat = db.delete_conversation_session("pg-phase-b-chat", owner_id="pg-phase-b-user")

        self.assertEqual(deleted_history, 1)
        self.assertEqual(deleted_chat, 2)
        self.assertEqual(self._pg_scalar("select count(*) from analysis_records"), 0)
        self.assertEqual(self._pg_scalar("select count(*) from analysis_sessions"), 0)
        self.assertEqual(self._pg_scalar("select count(*) from chat_messages"), 0)
        self.assertEqual(self._pg_scalar("select count(*) from chat_sessions"), 0)

    def test_real_postgres_phase_b_store_exposes_models_to_same_runtime_db(self) -> None:
        db = self._db()
        self.assertTrue(db._phase_b_enabled)
        self.assertIsNotNone(db._phase_b_store)

        with db._phase_b_store.session_scope() as session:
            self.assertEqual(session.query(PhaseBAnalysisSession).count(), 0)
            self.assertEqual(session.query(PhaseBAnalysisRecord).count(), 0)
            self.assertEqual(session.query(PhaseBChatSession).count(), 0)
            self.assertEqual(session.query(PhaseBChatMessage).count(), 0)


if __name__ == "__main__":
    unittest.main()
