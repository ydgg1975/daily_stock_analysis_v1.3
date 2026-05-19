# -*- coding: utf-8 -*-
import unittest
import sys
import os
import tempfile
import threading
from datetime import date
from unittest.mock import patch

import pandas as pd
from sqlalchemy import and_, select
from sqlalchemy.sql import func

# Ensure src module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import Config
from src.storage import DatabaseManager, StockDaily

class TestStorage(unittest.TestCase):
    
    def test_parse_sniper_value(self):
        """
Daily Stock Analysis - Test Storage
"""
        
        # 1. zhengchangshuzhi
        self.assertEqual(DatabaseManager._parse_sniper_value(100), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value(100.5), 100.5)
        self.assertEqual(DatabaseManager._parse_sniper_value("100"), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("100.5"), 100.5)
        
        # 2. baohanzhongwenmiaoshuhe"yuan"
        self.assertEqual(DatabaseManager._parse_sniper_value("jianyizai 100 yuanfujinmairu"), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("jiage：100.5yuan"), 100.5)
        
        # 3. baohanganraoshuzi（xiufudeBugchangjing）
        # zhiqian "MA5" huibeicuowutiquwei 5.0，xianzaiyinggaitiqu "yuan" qianmiande 100
        text_bug = "wufageichu。xudengdaiMA5shujuhuifu，zaigujiahuicaiMA5qieguaililv<2%shikaolv100yuan"
        self.assertEqual(DatabaseManager._parse_sniper_value(text_bug), 100.0)
        
        # 4. gengduoganraochangjing
        text_complex = "MA10wei20.5，jianyizai30yuanmairu"
        self.assertEqual(DatabaseManager._parse_sniper_value(text_complex), 30.0)
        
        text_multiple = "zhichengwei10yuan，zuliwei20yuan" # yinggaitiquzuihouyige"yuan"qianmiandeshuzi，ji20，huozhegengfuzadeluoji？
        # dangqianluojishizhaozuihouyigemaohao，ranhouzhaozhihoudediyige"yuan"，tiquzhongjiandeshuzi。
        self.assertEqual(DatabaseManager._parse_sniper_value("30yuan"), 30.0)
        
        self.assertEqual(DatabaseManager._parse_sniper_value("MA5 10 20yuan"), 20.0)
        
        # 5. Fallback: no "yuan" character — extracts last non-MA number
        self.assertEqual(DatabaseManager._parse_sniper_value("102.10-103.00（MA5fujin）"), 103.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("97.62-98.50（MA10fujin）"), 98.5)
        self.assertEqual(DatabaseManager._parse_sniper_value("93.40xiafang（MA20zhicheng）"), 93.4)
        self.assertEqual(DatabaseManager._parse_sniper_value("108.00-110.00（qianqigaodianzuli）"), 110.0)

        # 6. wuxiaoshuru
        self.assertIsNone(DatabaseManager._parse_sniper_value(None))
        self.assertIsNone(DatabaseManager._parse_sniper_value(""))
        self.assertIsNone(DatabaseManager._parse_sniper_value("meiyoushuzi"))
        self.assertIsNone(DatabaseManager._parse_sniper_value("MA5danmeiyouyuan"))

        # 7. huigui：kuohaoneijishuzhibiaoshuzibuyingbeitiqu
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.52-1.53 (huicaiMA5/10fujin)"), 10.0)
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.55-1.56(MA5/M20zhicheng)"), 20.0)
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.49-1.50(MA60fujinqiwen)"), 60.0)
        # yanzhengzhengquezhizaiqujiannei
        self.assertIn(DatabaseManager._parse_sniper_value("1.52-1.53 (huicaiMA5/10fujin)"), [1.52, 1.53])
        self.assertIn(DatabaseManager._parse_sniper_value("1.55-1.56(MA5/M20zhicheng)"), [1.55, 1.56])
        self.assertIn(DatabaseManager._parse_sniper_value("1.49-1.50(MA60fujinqiwen)"), [1.49, 1.50])

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

if __name__ == '__main__':
    unittest.main()
