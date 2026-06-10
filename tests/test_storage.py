# -*- coding: utf-8 -*-
import unittest
import sys
import os
import tempfile
import threading
from datetime import date
from unittest.mock import patch

import pandas as pd
from sqlalchemy import and_, create_engine as sqlalchemy_create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.sql import func

# Ensure src module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import Config
from src.storage import Base, CURRENT_SCHEMA_VERSION, DatabaseManager, DatabaseSchemaMigration, StockDaily

class TestStorage(unittest.TestCase):

    def test_database_initialization_records_schema_version(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        with db.get_session() as session:
            row = session.get(DatabaseSchemaMigration, CURRENT_SCHEMA_VERSION)

        self.assertIsNotNone(row)
        self.assertEqual(row.version, CURRENT_SCHEMA_VERSION)
        self.assertIn("metadata.create_all", row.description)

        DatabaseManager.reset_instance()

    def test_schema_migration_record_is_idempotent(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db._ensure_schema_migration_record()
        db._ensure_schema_migration_record()

        with db.get_session() as session:
            count = session.execute(
                select(func.count()).select_from(DatabaseSchemaMigration)
            ).scalar_one()

        self.assertEqual(count, 1)

        DatabaseManager.reset_instance()

    def test_schema_migration_record_handles_concurrent_initialization(self):
        DatabaseManager.reset_instance()
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "schema_migration_race.db")
        db = DatabaseManager(db_url=f"sqlite:///{db_path}")
        worker_count = 8
        barrier = threading.Barrier(worker_count)
        errors = []
        state_lock = threading.Lock()

        with db.get_session() as session:
            session.query(DatabaseSchemaMigration).delete()
            session.commit()

        def ensure_record() -> None:
            try:
                barrier.wait(timeout=5)
                db._ensure_schema_migration_record()
            except Exception as exc:
                with state_lock:
                    errors.append(exc)

        threads = [threading.Thread(target=ensure_record) for _ in range(worker_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        with db.get_session() as session:
            rows = session.execute(select(DatabaseSchemaMigration)).scalars().all()

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].version, CURRENT_SCHEMA_VERSION)

        DatabaseManager.reset_instance()
        temp_dir.cleanup()
    
    def test_parse_sniper_value(self):
        """测试解析狙击点位数值"""
        
        # 1. 正常数值
        self.assertEqual(DatabaseManager._parse_sniper_value(100), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value(100.5), 100.5)
        self.assertEqual(DatabaseManager._parse_sniper_value("100"), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("100.5"), 100.5)
        
        # 2. 包含中文描述和"元"
        self.assertEqual(DatabaseManager._parse_sniper_value("建议在 100 元附近买入"), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("价格：100.5元"), 100.5)
        
        # 3. 包含干扰数字（修复的Bug场景）
        # 之前 "MA5" 会被错误提取为 5.0，现在应该提取 "元" 前面的 100
        text_bug = "无法给出。需等待MA5数据恢复，在股价回踩MA5且乖离率<2%时考虑100元"
        self.assertEqual(DatabaseManager._parse_sniper_value(text_bug), 100.0)
        
        # 4. 更多干扰场景
        text_complex = "MA10为20.5，建议在30元买入"
        self.assertEqual(DatabaseManager._parse_sniper_value(text_complex), 30.0)
        
        text_multiple = "支撑位10元，阻力位20元" # 应该提取最后一个"元"前面的数字，即20，或者更复杂的逻辑？
        # 当前逻辑是找最后一个冒号，然后找之后的第一个"元"，提取中间的数字。
        # 测试没有冒号的情况
        self.assertEqual(DatabaseManager._parse_sniper_value("30元"), 30.0)
        
        # 测试多个数字在"元"之前
        self.assertEqual(DatabaseManager._parse_sniper_value("MA5 10 20元"), 20.0)
        
        # 5. Fallback: no "元" character — extracts last non-MA number
        self.assertEqual(DatabaseManager._parse_sniper_value("102.10-103.00（MA5附近）"), 103.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("97.62-98.50（MA10附近）"), 98.5)
        self.assertEqual(DatabaseManager._parse_sniper_value("93.40下方（MA20支撑）"), 93.4)
        self.assertEqual(DatabaseManager._parse_sniper_value("108.00-110.00（前期高点阻力）"), 110.0)

        # 6. 无效输入
        self.assertIsNone(DatabaseManager._parse_sniper_value(None))
        self.assertIsNone(DatabaseManager._parse_sniper_value(""))
        self.assertIsNone(DatabaseManager._parse_sniper_value("没有数字"))
        self.assertIsNone(DatabaseManager._parse_sniper_value("MA5但没有元"))

        # 7. 回归：括号内技术指标数字不应被提取
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.52-1.53 (回踩MA5/10附近)"), 10.0)
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.55-1.56(MA5/M20支撑)"), 20.0)
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.49-1.50(MA60附近企稳)"), 60.0)
        # 验证正确值在区间内
        self.assertIn(DatabaseManager._parse_sniper_value("1.52-1.53 (回踩MA5/10附近)"), [1.52, 1.53])
        self.assertIn(DatabaseManager._parse_sniper_value("1.55-1.56(MA5/M20支撑)"), [1.55, 1.56])
        self.assertIn(DatabaseManager._parse_sniper_value("1.49-1.50(MA60附近企稳)"), [1.49, 1.50])

    def test_get_chat_sessions_prefix_is_scoped_by_colon_boundary(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_conversation_message("telegram_12345:chat", "user", "first user")
        db.save_conversation_message("telegram_123456:chat", "user", "second user")

        sessions = db.get_chat_sessions(session_prefix="telegram_12345")

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], "telegram_12345:chat")

        DatabaseManager.reset_instance()

    def test_get_chat_sessions_can_include_legacy_exact_session_id(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_conversation_message("feishu_u1", "user", "legacy chat")
        db.save_conversation_message("feishu_u1:ask_600519", "user", "ask session")

        sessions = db.get_chat_sessions(
            session_prefix="feishu_u1:",
            extra_session_ids=["feishu_u1"],
        )

        self.assertEqual({item["session_id"] for item in sessions}, {"feishu_u1", "feishu_u1:ask_600519"})

        DatabaseManager.reset_instance()

    def test_conversation_summary_upsert_and_delete_with_session(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_conversation_message("summary-session", "user", "hello")
        db.upsert_conversation_summary(
            "summary-session",
            "first summary",
            covered_message_id=1,
            source_message_count=1,
            estimated_tokens=10,
        )
        db.upsert_conversation_summary(
            "summary-session",
            "updated summary",
            covered_message_id=2,
            source_message_count=2,
            estimated_tokens=12,
        )

        summary = db.get_conversation_summary("summary-session")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["summary"], "updated summary")
        self.assertEqual(summary["covered_message_id"], 2)
        self.assertEqual(summary["source_message_count"], 2)

        deleted = db.delete_conversation_session("summary-session")

        self.assertEqual(deleted, 1)
        self.assertIsNone(db.get_conversation_summary("summary-session"))

        DatabaseManager.reset_instance()

    def test_conversation_message_save_returns_id(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        message_id = db.save_conversation_message("message-id-session", "user", "hello")

        self.assertIsInstance(message_id, int)
        self.assertGreater(message_id, 0)

        DatabaseManager.reset_instance()

    def test_provider_turn_round_trip_preserves_protocol_fields_and_flags(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        user_id = db.save_conversation_message("trace-session", "user", "question")
        assistant_id = db.save_conversation_message("trace-session", "assistant", "final")
        trace_messages = [
            {
                "role": "assistant",
                "content": "checking",
                "reasoning_content": "reasoning",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": "echo",
                        "arguments": {"message": "hello"},
                        "provider_specific_fields": {"thought_signature": "sig"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "{\"ok\": true}"},
        ]

        turn_id = db.save_agent_provider_turn(
            session_id="trace-session",
            run_id="run-1",
            provider="deepseek",
            model="deepseek/deepseek-chat",
            anchor_user_message_id=user_id,
            anchor_assistant_message_id=assistant_id,
            messages=trace_messages,
            contains_reasoning=True,
            contains_tool_calls=True,
            contains_thinking_blocks=False,
            must_roundtrip=True,
            estimated_tokens=42,
        )
        rows = db.get_agent_provider_turns("trace-session")

        self.assertIsInstance(turn_id, int)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["messages"], trace_messages)
        self.assertTrue(rows[0]["contains_reasoning"])
        self.assertTrue(rows[0]["contains_tool_calls"])
        self.assertTrue(rows[0]["must_roundtrip"])
        self.assertEqual(rows[0]["estimated_tokens"], 42)

        DatabaseManager.reset_instance()

    def test_provider_turns_do_not_appear_in_visible_or_web_messages_and_delete_with_session(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        user_id = db.save_conversation_message("trace-hidden", "user", "visible question")
        assistant_id = db.save_conversation_message("trace-hidden", "assistant", "visible answer")
        db.save_agent_provider_turn(
            session_id="trace-hidden",
            run_id="run-hidden",
            provider="deepseek",
            model="deepseek/deepseek-chat",
            anchor_user_message_id=user_id,
            anchor_assistant_message_id=assistant_id,
            messages=[{"role": "assistant", "reasoning_content": "SECRET_REASONING", "tool_calls": []}],
            contains_reasoning=True,
            contains_tool_calls=True,
            contains_thinking_blocks=False,
            must_roundtrip=True,
            estimated_tokens=5,
        )

        self.assertEqual(
            [(m["role"], m["content"]) for m in db.get_visible_conversation_messages("trace-hidden")],
            [("user", "visible question"), ("assistant", "visible answer")],
        )
        self.assertEqual(
            [(m["role"], m["content"]) for m in db.get_conversation_history("trace-hidden")],
            [("user", "visible question"), ("assistant", "visible answer")],
        )
        self.assertEqual(
            [(m["role"], m["content"]) for m in db.get_conversation_messages("trace-hidden")],
            [("user", "visible question"), ("assistant", "visible answer")],
        )

        deleted = db.delete_conversation_session("trace-hidden")

        self.assertEqual(deleted, 2)
        self.assertEqual(db.get_agent_provider_turns("trace-hidden"), [])

        DatabaseManager.reset_instance()

    def test_provider_turn_retention_is_bucketed_by_session_provider_model(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        for idx in range(5):
            user_id = db.save_conversation_message("retention", "user", f"q{idx}")
            assistant_id = db.save_conversation_message("retention", "assistant", f"a{idx}")
            db.save_agent_provider_turn(
                session_id="retention",
                run_id=f"run-{idx}",
                provider="deepseek",
                model="deepseek/deepseek-chat",
                anchor_user_message_id=user_id,
                anchor_assistant_message_id=assistant_id,
                messages=[{"role": "assistant", "reasoning_content": f"r{idx}", "tool_calls": [{"id": f"c{idx}", "name": "echo", "arguments": {}}]}],
                contains_reasoning=True,
                contains_tool_calls=True,
                contains_thinking_blocks=False,
                must_roundtrip=True,
                estimated_tokens=idx + 1,
            )
        user_id = db.save_conversation_message("retention", "user", "other")
        assistant_id = db.save_conversation_message("retention", "assistant", "other")
        db.save_agent_provider_turn(
            session_id="retention",
            run_id="run-other",
            provider="anthropic",
            model="anthropic/claude-test",
            anchor_user_message_id=user_id,
            anchor_assistant_message_id=assistant_id,
            messages=[{"role": "assistant", "provider_blocks": [{"type": "thinking"}], "tool_calls": [{"id": "c-other", "name": "echo", "arguments": {}}]}],
            contains_reasoning=False,
            contains_tool_calls=True,
            contains_thinking_blocks=True,
            must_roundtrip=True,
            estimated_tokens=1,
        )

        deepseek_rows = db.get_agent_provider_turns(
            "retention",
            provider="deepseek",
            model="deepseek/deepseek-chat",
        )
        anthropic_rows = db.get_agent_provider_turns(
            "retention",
            provider="anthropic",
            model="anthropic/claude-test",
        )

        self.assertEqual(len(deepseek_rows), 3)
        self.assertEqual([row["run_id"] for row in deepseek_rows], ["run-2", "run-3", "run-4"])
        self.assertEqual(len(anthropic_rows), 1)

        DatabaseManager.reset_instance()

    def test_get_visible_conversation_messages_returns_ordered_visible_content(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_conversation_message("visible-session", "system", "hidden")
        db.save_conversation_message("visible-session", "user", "question")
        db.save_conversation_message("visible-session", "assistant", "answer")

        messages = db.get_visible_conversation_messages("visible-session")

        self.assertEqual(
            [(item["role"], item["content"]) for item in messages],
            [("user", "question"), ("assistant", "answer")],
        )
        self.assertIsInstance(messages[0]["id"], int)

        DatabaseManager.reset_instance()

    def test_get_visible_conversation_messages_limit_returns_ordered_tail(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        for idx in range(25):
            db.save_conversation_message("visible-limit", "user", f"msg-{idx}")

        messages = db.get_visible_conversation_messages("visible-limit", limit=20)

        self.assertEqual(len(messages), 20)
        self.assertEqual(messages[0]["content"], "msg-5")
        self.assertEqual(messages[-1]["content"], "msg-24")

        DatabaseManager.reset_instance()

    def test_file_sqlite_enables_wal_and_busy_timeout(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "sqlite_pragmas.db")
        original_env = {
            "DATABASE_PATH": os.environ.get("DATABASE_PATH"),
            "SQLITE_BUSY_TIMEOUT_MS": os.environ.get("SQLITE_BUSY_TIMEOUT_MS"),
            "SQLITE_WAL_ENABLED": os.environ.get("SQLITE_WAL_ENABLED"),
        }

        try:
            os.environ["DATABASE_PATH"] = db_path
            os.environ["SQLITE_BUSY_TIMEOUT_MS"] = "1234"
            os.environ["SQLITE_WAL_ENABLED"] = "true"
            Config.reset_instance()
            DatabaseManager.reset_instance()

            db = DatabaseManager.get_instance()
            with db.get_session() as session:
                journal_mode = session.connection().exec_driver_sql("PRAGMA journal_mode").scalar()
                busy_timeout = session.connection().exec_driver_sql("PRAGMA busy_timeout").scalar()

            self.assertEqual(str(journal_mode).lower(), "wal")
            self.assertEqual(int(busy_timeout), 1234)
        finally:
            DatabaseManager.reset_instance()
            Config.reset_instance()
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            temp_dir.cleanup()

    def test_get_instance_waits_for_cold_start_initialization(self):
        DatabaseManager.reset_instance()
        Config.reset_instance()
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "sqlite_cold_start.db")
        original_database_path = os.environ.get("DATABASE_PATH")
        create_all_entered = threading.Event()
        competitor_entered = threading.Event()
        release_create_all = threading.Event()
        competitor_done = threading.Event()
        state_lock = threading.Lock()
        init_errors = []
        competitor_errors = []
        instances = []
        query_values = []
        original_create_all = Base.metadata.create_all

        def delayed_create_all(bind, *args, **kwargs):
            create_all_entered.set()
            if not release_create_all.wait(timeout=5):
                raise TimeoutError("Timed out waiting to release create_all")
            return original_create_all(bind, *args, **kwargs)

        def initialize_manager() -> None:
            try:
                db = DatabaseManager.get_instance()
                with state_lock:
                    instances.append(db)
            except Exception as exc:
                with state_lock:
                    init_errors.append(exc)

        def use_manager() -> None:
            try:
                competitor_entered.set()
                db = DatabaseManager.get_instance()
                session = db.get_session()
                try:
                    value = session.connection().exec_driver_sql("SELECT 1").scalar()
                finally:
                    session.close()
                with state_lock:
                    instances.append(db)
                    query_values.append(value)
            except Exception as exc:
                with state_lock:
                    competitor_errors.append(exc)
            finally:
                competitor_done.set()

        try:
            os.environ["DATABASE_PATH"] = db_path
            Config.reset_instance()
            with patch.object(Base.metadata, "create_all", side_effect=delayed_create_all):
                init_thread = threading.Thread(target=initialize_manager)
                competitor_thread = threading.Thread(target=use_manager)

                init_thread.start()
                self.assertTrue(create_all_entered.wait(timeout=5))

                competitor_thread.start()
                self.assertTrue(competitor_entered.wait(timeout=5))
                self.assertFalse(
                    competitor_done.wait(timeout=0.2),
                    "DatabaseManager.get_instance() returned before initialization completed",
                )

                release_create_all.set()
                init_thread.join(timeout=5)
                competitor_thread.join(timeout=5)

                self.assertFalse(init_thread.is_alive())
                self.assertFalse(competitor_thread.is_alive())

            self.assertEqual(init_errors, [])
            self.assertEqual(competitor_errors, [])
            self.assertEqual(query_values, [1])
            self.assertEqual(len({id(instance) for instance in instances}), 1)
        finally:
            release_create_all.set()
            DatabaseManager.reset_instance()
            Config.reset_instance()
            if original_database_path is None:
                os.environ.pop("DATABASE_PATH", None)
            else:
                os.environ["DATABASE_PATH"] = original_database_path
            temp_dir.cleanup()

    def test_direct_construction_serializes_before_get_instance(self):
        DatabaseManager.reset_instance()
        Config.reset_instance()
        temp_dir = tempfile.TemporaryDirectory()
        direct_db_path = os.path.join(temp_dir.name, "direct.db")
        env_db_path = os.path.join(temp_dir.name, "env.db")
        direct_db_url = f"sqlite:///{direct_db_path}"
        original_database_path = os.environ.get("DATABASE_PATH")
        direct_init_entered = threading.Event()
        competitor_entered = threading.Event()
        allow_direct_init = threading.Event()
        competitor_done = threading.Event()
        state_lock = threading.Lock()
        errors = []
        instances = []
        query_values = []
        original_init = DatabaseManager.__init__

        def delayed_direct_init(self, db_url=None):
            if db_url == direct_db_url:
                direct_init_entered.set()
                if not competitor_entered.wait(timeout=5):
                    raise TimeoutError("Timed out waiting for competitor")
                if not allow_direct_init.wait(timeout=5):
                    raise TimeoutError("Timed out waiting to initialize direct instance")
            return original_init(self, db_url=db_url)

        def construct_directly() -> None:
            try:
                db = DatabaseManager(db_url=direct_db_url)
                with state_lock:
                    instances.append(db)
            except Exception as exc:
                with state_lock:
                    errors.append(exc)

        def use_get_instance() -> None:
            try:
                competitor_entered.set()
                db = DatabaseManager.get_instance()
                session = db.get_session()
                try:
                    value = session.connection().exec_driver_sql("SELECT 1").scalar()
                finally:
                    session.close()
                with state_lock:
                    instances.append(db)
                    query_values.append(value)
            except Exception as exc:
                with state_lock:
                    errors.append(exc)
            finally:
                competitor_done.set()

        try:
            os.environ["DATABASE_PATH"] = env_db_path
            Config.reset_instance()
            with patch.object(DatabaseManager, "__init__", new=delayed_direct_init):
                direct_thread = threading.Thread(target=construct_directly)
                competitor_thread = threading.Thread(target=use_get_instance)

                direct_thread.start()
                self.assertTrue(direct_init_entered.wait(timeout=5))

                competitor_thread.start()
                self.assertTrue(competitor_entered.wait(timeout=5))
                self.assertFalse(
                    competitor_done.wait(timeout=0.2),
                    "get_instance() should not initialize over an in-flight direct construction",
                )

                allow_direct_init.set()
                direct_thread.join(timeout=5)
                competitor_thread.join(timeout=5)

                self.assertFalse(direct_thread.is_alive())
                self.assertFalse(competitor_thread.is_alive())

            self.assertEqual(errors, [])
            self.assertEqual(query_values, [1])
            self.assertEqual(len({id(instance) for instance in instances}), 1)
            self.assertEqual(DatabaseManager._instance._db_url, direct_db_url)
        finally:
            allow_direct_init.set()
            DatabaseManager.reset_instance()
            Config.reset_instance()
            if original_database_path is None:
                os.environ.pop("DATABASE_PATH", None)
            else:
                os.environ["DATABASE_PATH"] = original_database_path
            temp_dir.cleanup()

    def test_init_cleanup_preserves_original_initialization_error(self):
        DatabaseManager.reset_instance()
        original_error = RuntimeError("create all failed")
        cleanup_error = RuntimeError("dispose failed")

        def create_engine_with_failing_dispose(*args, **kwargs):
            engine = sqlalchemy_create_engine(*args, **kwargs)

            def failing_dispose() -> None:
                raise cleanup_error

            engine.dispose = failing_dispose
            return engine

        try:
            with patch("src.storage.create_engine", side_effect=create_engine_with_failing_dispose):
                with patch.object(Base.metadata, "create_all", side_effect=original_error):
                    with self.assertRaisesRegex(RuntimeError, "create all failed") as ctx:
                        DatabaseManager.get_instance()

            self.assertIs(ctx.exception, original_error)
            self.assertIsNone(DatabaseManager._instance)
        finally:
            DatabaseManager.reset_instance()

    def test_sqlite_write_transactions_begin_immediate(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        session = db.get_session()
        connection = session.connection()

        try:
            with patch.object(db, "get_session", return_value=session):
                with patch.object(connection, "exec_driver_sql", wraps=connection.exec_driver_sql) as mock_exec:
                    result = db._run_write_transaction("unit-test", lambda current_session: 7)

            self.assertEqual(result, 7)
            self.assertTrue(
                any(call.args == ("BEGIN IMMEDIATE",) for call in mock_exec.call_args_list)
            )
        finally:
            DatabaseManager.reset_instance()

    def test_save_daily_data_sqlite_concurrent_same_code_date_counts_only_new_rows(self):
        DatabaseManager.reset_instance()
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "sqlite_daily_concurrency.db")
        db = DatabaseManager(db_url=f"sqlite:///{db_path}")

        results = []
        results_lock = threading.Lock()
        start_barrier = threading.Barrier(2)

        def worker() -> None:
            start_barrier.wait()
            count = db.save_daily_data(
                pd.DataFrame(
                    [
                        {
                            'date': date(2026, 4, 1),
                            'open': 10,
                            'high': 11,
                            'low': 9,
                            'close': 10.5,
                            'volume': 100,
                            'amount': 1050,
                            'pct_chg': 1.2,
                            'ma5': 10.1,
                            'ma10': 10.2,
                            'ma20': 10.3,
                            'volume_ratio': 1.0,
                        }
                    ]
                ),
                code='600519',
                data_source='test',
            )
            with results_lock:
                results.append(count)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        try:
            self.assertCountEqual(results, [1, 0])

            with db.get_session() as session:
                total = session.execute(
                    select(func.count()).select_from(StockDaily).where(
                        and_(
                            StockDaily.code == '600519',
                            StockDaily.date == date(2026, 4, 1),
                        )
                    )
                ).scalar()

            self.assertEqual(total, 1)
        finally:
            temp_dir.cleanup()
            DatabaseManager.reset_instance()

    # ------------------------------------------------------------------
    # NewsIntel url_hash / cross-DB unique-constraint compatibility
    # ------------------------------------------------------------------

    def test_news_intel_schema_uses_url_hash_for_unique_constraint(self):
        """uix_news_url on VARCHAR(1000) exceeds MySQL InnoDB key-length limit."""
        from src.storage import NewsIntel
        constraint_map = {
            c.name: [col.name for col in c.columns]
            for c in NewsIntel.__table__.constraints
        }
        self.assertNotIn('uix_news_url', constraint_map,
                         'VARCHAR(1000) unique index incompatible with MySQL utf8mb4')
        self.assertIn('uix_news_url_hash', constraint_map,
                      'url_hash unique constraint required for cross-DB dedup')
        self.assertIn('url_hash', constraint_map.get('uix_news_url_hash', []))

    def test_compute_url_hash_deterministic_and_64_hex_chars(self):
        db = DatabaseManager(db_url="sqlite:///:memory:")
        try:
            h1 = db._compute_url_hash("https://example.com/a")
            h2 = db._compute_url_hash("https://example.com/a")
            h3 = db._compute_url_hash("https://example.com/b")
            self.assertEqual(h1, h2)
            self.assertNotEqual(h1, h3)
            self.assertEqual(len(h1), 64)
            self.assertTrue(all(c in '0123456789abcdef' for c in h1))
        finally:
            DatabaseManager.reset_instance()

    def test_save_news_intel_dedup_by_url_hash(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        class _R:
            title = "T"; url = "https://x.com/1"; source = "S"
            snippet = "s"; published_date = "2026-06-01"

        class _Resp:
            provider = "p"; results = [_R]

        c1 = db.save_news_intel(code="600519", name="n", dimension="d",
                                query="q", response=_Resp)
        c2 = db.save_news_intel(code="600519", name="n", dimension="d",
                                query="q", response=_Resp)
        self.assertEqual(c1, 1)
        self.assertEqual(c2, 0, "duplicate URL must be rejected by url_hash constraint")

        from src.storage import NewsIntel
        with db.get_session() as s:
            rows = s.execute(select(NewsIntel).where(NewsIntel.code == "600519")).scalars().all()
        self.assertEqual(len(rows), 1)
        self.assertIsNotNone(rows[0].url_hash)
        self.assertEqual(len(rows[0].url_hash), 64)
        DatabaseManager.reset_instance()

    def test_save_news_intel_fallback_key_also_hashed_for_mysql_compat(self):
        """When url is empty, the fallback key is hashed so unique index stays short."""
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        class _R:
            title = "NoUrl"; url = ""; source = "S"
            snippet = "s"; published_date = "2026-06-01"

        class _Resp:
            provider = "p"; results = [_R]

        c1 = db.save_news_intel(code="600519", name="n", dimension="d",
                                query="q", response=_Resp)
        c2 = db.save_news_intel(code="600519", name="n", dimension="d",
                                query="q", response=_Resp)
        self.assertEqual(c1, 1)
        self.assertEqual(c2, 0)
        DatabaseManager.reset_instance()

    # ------------------------------------------------------------------
    # save_daily_data cross-DB atomic upsert
    # ------------------------------------------------------------------

    def test_save_daily_data_atomic_upsert_replaces_existing_row(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        import pandas as pd
        d = date(2026, 5, 15)
        df1 = pd.DataFrame([{'date': d, 'open': 100, 'high': 105, 'low': 98,
                              'close': 102, 'volume': 10000, 'amount': 1020000,
                              'pct_chg': 2.0, 'ma5': 101, 'ma10': 100, 'ma20': 99,
                              'volume_ratio': 1.1}])
        self.assertEqual(db.save_daily_data(df1, code='000001', data_source='src_a'), 1)

        df2 = pd.DataFrame([{'date': d, 'open': 102, 'high': 107, 'low': 100,
                              'close': 104, 'volume': 12000, 'amount': 1248000,
                              'pct_chg': 3.0, 'ma5': 103, 'ma10': 102, 'ma20': 101,
                              'volume_ratio': 1.2}])
        self.assertEqual(db.save_daily_data(df2, code='000001', data_source='src_b'), 0,
                         'upsert of existing (code,date) should return 0 new rows')

        with db.get_session() as s:
            row = s.execute(
                select(StockDaily).where(
                    and_(StockDaily.code == '000001', StockDaily.date == d)
                )
            ).scalar_one()
        self.assertEqual(row.close, 104)
        self.assertEqual(row.data_source, 'src_b')
        DatabaseManager.reset_instance()

    def test_save_daily_data_batch_chunk_handles_large_volume(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        import pandas as pd
        base = date(2026, 1, 5)
        rows = [{'date': base + pd.Timedelta(days=i),
                 'open': 50 + i * 0.1, 'high': 55, 'low': 48, 'close': 52,
                 'volume': 5000, 'amount': 260000, 'pct_chg': 0.5,
                 'ma5': 51, 'ma10': 50, 'ma20': 49, 'volume_ratio': 1.0}
                for i in range(120)]
        count = db.save_daily_data(pd.DataFrame(rows), code='000001',
                                   data_source='batch')
        self.assertEqual(count, 120)

        with db.get_session() as s:
            total = s.execute(
                select(func.count()).select_from(StockDaily).where(StockDaily.code == '000001')
            ).scalar()
        self.assertEqual(total, 120)
        DatabaseManager.reset_instance()

    # ------------------------------------------------------------------
    # _ensure_schema_migration_record idempotency
    # ------------------------------------------------------------------

    def test_schema_migration_record_idempotent_across_calls(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        for _ in range(3):
            db._ensure_schema_migration_record()
        with db.get_session() as s:
            cnt = s.execute(
                select(func.count()).select_from(DatabaseSchemaMigration)
            ).scalar_one()
        self.assertEqual(cnt, 1)
        DatabaseManager.reset_instance()


# ---------------------------------------------------------------------------
# Cross-database integration tests (require real MySQL / PostgreSQL)
# ---------------------------------------------------------------------------
# Set TEST_MYSQL_URL / TEST_POSTGRESQL_URL env vars to enable.
#   TEST_MYSQL_URL=mysql+pymysql://root:pwd@127.0.0.1:3306/test_db
#   TEST_POSTGRESQL_URL=postgresql+psycopg2://postgres:pwd@127.0.0.1:5432/test_db

def _real_db_reachable(db_url: str) -> bool:
    try:
        from sqlalchemy import text as _text
        eng = sqlalchemy_create_engine(db_url, pool_pre_ping=True)
        with eng.connect() as conn:
            conn.execute(_text("SELECT 1"))
        eng.dispose()
        return True
    except Exception:
        return False


_MYSQL_URL = (os.environ.get("TEST_MYSQL_URL") or "").strip()
_PG_URL = (os.environ.get("TEST_POSTGRESQL_URL") or "").strip()
_MYSQL_OK = bool(_MYSQL_URL) and _real_db_reachable(_MYSQL_URL)
_PG_OK = bool(_PG_URL) and _real_db_reachable(_PG_URL)

_ALL_TABLES = {
    'schema_migrations', 'stock_daily', 'news_intel',
    'fundamental_snapshot', 'analysis_history', 'backtest_results',
    'backtest_summaries', 'portfolio_accounts', 'portfolio_trades',
    'portfolio_cash_ledger', 'portfolio_corporate_actions',
    'portfolio_positions', 'portfolio_position_lots',
    'portfolio_daily_snapshots', 'portfolio_fx_rates',
    'conversation_messages', 'conversation_summaries',
    'agent_provider_turns', 'llm_usage', 'alert_rules',
    'alert_triggers', 'alert_notifications', 'alert_cooldowns',
    'decision_signals',
}


class TestMultiDatabaseIntegration(unittest.TestCase):
    """Real-database tests — skipped when TEST_{MYSQL,POSTGRESQL}_URL not set."""

    @classmethod
    def _table_names(cls, db):
        from sqlalchemy import inspect as _inspect
        with db.get_session() as s:
            return set(_inspect(s.get_bind()).get_table_names())

    # -- MySQL ---------------------------------------------------------------

    @unittest.skipUnless(_MYSQL_OK, "TEST_MYSQL_URL not set or unreachable")
    def test_mysql_create_all_produces_all_tables(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url=_MYSQL_URL)
        try:
            missing = _ALL_TABLES - self._table_names(db)
            self.assertSetEqual(missing, set(),
                f"Tables missing on MySQL: {missing}")
        finally:
            DatabaseManager.reset_instance()

    @unittest.skipUnless(_MYSQL_OK, "TEST_MYSQL_URL not set or unreachable")
    def test_mysql_save_daily_data_upsert(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url=_MYSQL_URL)
        import pandas as pd
        d = date(2026, 5, 20)
        row = {'date': d, 'open': 50, 'high': 55, 'low': 48, 'close': 52,
               'volume': 5000, 'amount': 260000, 'pct_chg': 1.0,
               'ma5': 51, 'ma10': 50, 'ma20': 49, 'volume_ratio': 1.0}
        self.assertEqual(db.save_daily_data(pd.DataFrame([row]), 'MYSQL001', 'v1'), 1)
        row2 = dict(row, close=57, data_source='v2')
        self.assertEqual(db.save_daily_data(pd.DataFrame([row2]), 'MYSQL001', 'v2'), 0)
        with db.get_session() as s:
            r = s.execute(select(StockDaily).where(
                and_(StockDaily.code == 'MYSQL001', StockDaily.date == d)
            )).scalar_one()
        self.assertEqual(r.close, 57)
        self.assertEqual(r.data_source, 'v2')
        # cleanup
        with db.get_session() as s:
            from sqlalchemy import delete as _del
            s.execute(_del(StockDaily).where(StockDaily.code == 'MYSQL001'))
            s.commit()
        DatabaseManager.reset_instance()

    @unittest.skipUnless(_MYSQL_OK, "TEST_MYSQL_URL not set or unreachable")
    def test_mysql_news_intel_url_hash_unique_constraint(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url=_MYSQL_URL)
        from src.storage import NewsIntel

        class _R:
            title = "MySQL Test"; url = "https://x.com/mysql-unique-test"
            source = "S"; snippet = "s"; published_date = "2026-06-01"
        class _Resp:
            provider = "p"; results = [_R]

        c1 = db.save_news_intel("600519", "n", "d", "q", _Resp)
        c2 = db.save_news_intel("600519", "n", "d", "q", _Resp)
        self.assertEqual(c1, 1)
        self.assertEqual(c2, 0)
        with db.get_session() as s:
            rows = s.execute(select(NewsIntel).where(NewsIntel.code == "600519")).scalars().all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].url, "https://x.com/mysql-unique-test")
        self.assertEqual(len(rows[0].url_hash), 64)
        with db.get_session() as s:
            from sqlalchemy import delete as _del
            s.execute(_del(NewsIntel).where(NewsIntel.code == "600519"))
            s.commit()
        DatabaseManager.reset_instance()

    @unittest.skipUnless(_MYSQL_OK, "TEST_MYSQL_URL not set or unreachable")
    def test_mysql_schema_migration_record_idempotent(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url=_MYSQL_URL)
        for _ in range(3):
            db._ensure_schema_migration_record()
        with db.get_session() as s:
            cnt = s.execute(
                select(func.count()).select_from(DatabaseSchemaMigration)
            ).scalar_one()
        self.assertEqual(cnt, 1)
        DatabaseManager.reset_instance()

    # -- PostgreSQL ----------------------------------------------------------

    @unittest.skipUnless(_PG_OK, "TEST_POSTGRESQL_URL not set or unreachable")
    def test_postgresql_create_all_produces_all_tables(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url=_PG_URL)
        try:
            missing = _ALL_TABLES - self._table_names(db)
            self.assertSetEqual(missing, set(),
                f"Tables missing on PostgreSQL: {missing}")
        finally:
            DatabaseManager.reset_instance()

    @unittest.skipUnless(_PG_OK, "TEST_POSTGRESQL_URL not set or unreachable")
    def test_postgresql_save_daily_data_upsert(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url=_PG_URL)
        import pandas as pd
        d = date(2026, 5, 21)
        row = {'date': d, 'open': 60, 'high': 65, 'low': 58, 'close': 62,
               'volume': 7000, 'amount': 434000, 'pct_chg': 2.5,
               'ma5': 61, 'ma10': 60, 'ma20': 59, 'volume_ratio': 1.2}
        self.assertEqual(db.save_daily_data(pd.DataFrame([row]), 'PG0001', 'v1'), 1)
        row2 = dict(row, close=67, data_source='v2')
        self.assertEqual(db.save_daily_data(pd.DataFrame([row2]), 'PG0001', 'v2'), 0)
        with db.get_session() as s:
            r = s.execute(select(StockDaily).where(
                and_(StockDaily.code == 'PG0001', StockDaily.date == d)
            )).scalar_one()
        self.assertEqual(r.close, 67)
        self.assertEqual(r.data_source, 'v2')
        with db.get_session() as s:
            from sqlalchemy import delete as _del
            s.execute(_del(StockDaily).where(StockDaily.code == 'PG0001'))
            s.commit()
        DatabaseManager.reset_instance()

    @unittest.skipUnless(_PG_OK, "TEST_POSTGRESQL_URL not set or unreachable")
    def test_postgresql_news_intel_url_hash_unique_constraint(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url=_PG_URL)
        from src.storage import NewsIntel

        class _R:
            title = "PG Test"; url = "https://x.com/pg-unique-test"
            source = "S"; snippet = "s"; published_date = "2026-06-02"
        class _Resp:
            provider = "p"; results = [_R]

        c1 = db.save_news_intel("000001", "n", "d", "q", _Resp)
        c2 = db.save_news_intel("000001", "n", "d", "q", _Resp)
        self.assertEqual(c1, 1)
        self.assertEqual(c2, 0)
        with db.get_session() as s:
            rows = s.execute(select(NewsIntel).where(NewsIntel.code == "000001")).scalars().all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].url, "https://x.com/pg-unique-test")
        with db.get_session() as s:
            from sqlalchemy import delete as _del
            s.execute(_del(NewsIntel).where(NewsIntel.code == "000001"))
            s.commit()
        DatabaseManager.reset_instance()

    @unittest.skipUnless(_PG_OK, "TEST_POSTGRESQL_URL not set or unreachable")
    def test_postgresql_schema_migration_record_idempotent(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url=_PG_URL)
        for _ in range(3):
            db._ensure_schema_migration_record()
        with db.get_session() as s:
            cnt = s.execute(
                select(func.count()).select_from(DatabaseSchemaMigration)
            ).scalar_one()
        self.assertEqual(cnt, 1)
        DatabaseManager.reset_instance()

    # -- SQLite regression ---------------------------------------------------

    def test_sqlite_regression_all_tables_still_created(self):
        """Cross-DB refactoring must not break default SQLite path."""
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        names = self._table_names(db)
        for tbl in ('stock_daily', 'news_intel', 'schema_migrations',
                     'agent_provider_turns', 'alert_cooldowns'):
            self.assertIn(tbl, names)
        DatabaseManager.reset_instance()

    # -- Driver-missing guard ------------------------------------------------

    def test_missing_pymysql_raises_clear_install_hint(self):
        real_import = __import__

        def _block(name, *a, **kw):
            if name == 'pymysql':
                raise ImportError("No module named 'pymysql'")
            return real_import(name, *a, **kw)

        DatabaseManager.reset_instance()
        Config.reset_instance()
        try:
            for k, v in [('DATABASE_TYPE', 'mysql'), ('DATABASE_HOST', '127.0.0.1'),
                          ('DATABASE_NAME', 'test'), ('DATABASE_USERNAME', 'u'),
                          ('DATABASE_PASSWORD', 'p')]:
                os.environ[k] = v
            with patch('builtins.__import__', side_effect=_block):
                with self.assertRaises(ImportError) as ctx:
                    DatabaseManager.get_instance()
                self.assertIn('pymysql', str(ctx.exception))
                self.assertIn('pip install pymysql', str(ctx.exception))
        finally:
            DatabaseManager.reset_instance()
            Config.reset_instance()
            for k in ('DATABASE_TYPE', 'DATABASE_HOST', 'DATABASE_NAME',
                      'DATABASE_USERNAME', 'DATABASE_PASSWORD'):
                os.environ.pop(k, None)

    def test_missing_psycopg2_raises_clear_install_hint(self):
        real_import = __import__

        def _block(name, *a, **kw):
            if name == 'psycopg2':
                raise ImportError("No module named 'psycopg2'")
            return real_import(name, *a, **kw)

        DatabaseManager.reset_instance()
        Config.reset_instance()
        try:
            for k, v in [('DATABASE_TYPE', 'postgresql'), ('DATABASE_HOST', '127.0.0.1'),
                          ('DATABASE_NAME', 'test'), ('DATABASE_USERNAME', 'u'),
                          ('DATABASE_PASSWORD', 'p')]:
                os.environ[k] = v
            with patch('builtins.__import__', side_effect=_block):
                with self.assertRaises(ImportError) as ctx:
                    DatabaseManager.get_instance()
                self.assertIn('psycopg2', str(ctx.exception))
                self.assertIn('pip install psycopg2-binary', str(ctx.exception))
        finally:
            DatabaseManager.reset_instance()
            Config.reset_instance()
            for k in ('DATABASE_TYPE', 'DATABASE_HOST', 'DATABASE_NAME',
                      'DATABASE_USERNAME', 'DATABASE_PASSWORD'):
                os.environ.pop(k, None)

    # -- Special-character password URL encoding -----------------------------

    def test_structured_config_encodes_password_special_chars(self):
        """URL.create must safely encode @ : / ? # in passwords."""
        DatabaseManager.reset_instance()
        Config.reset_instance()
        try:
            for k, v in [('DATABASE_TYPE', 'mysql'), ('DATABASE_HOST', '127.0.0.1'),
                          ('DATABASE_NAME', 'db'), ('DATABASE_USERNAME', 'u'),
                          ('DATABASE_PASSWORD', 'p@ss:w/rd?#')]:
                os.environ[k] = v
            config = Config.get_instance()
            url = config.get_db_url()
            parsed = make_url(url)
            self.assertEqual(parsed.password, 'p@ss:w/rd?#',
                             f"Password not properly encoded/decoded in {url}")
            self.assertEqual(parsed.host, '127.0.0.1')
            self.assertEqual(parsed.database, 'db')
            self.assertEqual(parsed.username, 'u')
        finally:
            DatabaseManager.reset_instance()
            Config.reset_instance()
            for k in ('DATABASE_TYPE', 'DATABASE_HOST', 'DATABASE_NAME',
                      'DATABASE_USERNAME', 'DATABASE_PASSWORD'):
                os.environ.pop(k, None)

    # -- Unknown backend guard -----------------------------------------------

    def test_save_daily_data_raises_on_unsupported_backend(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        db._is_sqlite_engine = False
        db._db_backend_name = "oracle"

        import pandas as pd
        df = pd.DataFrame([{
            'date': date(2026, 1, 1), 'open': 10, 'high': 11, 'low': 9,
            'close': 10.5, 'volume': 100, 'amount': 1050, 'pct_chg': 1.0,
            'ma5': 10, 'ma10': 10, 'ma20': 10, 'volume_ratio': 1.0,
        }])
        with self.assertRaises(RuntimeError) as ctx:
            db.save_daily_data(df, code='TEST', data_source='test')
        self.assertIn('Unsupported database backend', str(ctx.exception))
        self.assertIn('oracle', str(ctx.exception))
        DatabaseManager.reset_instance()


if __name__ == '__main__':
    unittest.main()
