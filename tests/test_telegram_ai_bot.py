# -*- coding: utf-8 -*-
"""Tests for the Telegram AI polling entrypoint helpers."""

import os
import unittest
from unittest.mock import patch

from scripts.telegram_ai_bot import (
    TelegramIdentity,
    build_reply_chat_prompt,
    extract_stock_code,
    get_allowed_chat_ids_from_env,
    prepare_message,
)


class TelegramAIBotHelperTests(unittest.TestCase):
    def test_allowed_chat_ids_prefers_explicit_allowlist(self):
        with patch.dict(
            os.environ,
            {
                "TELEGRAM_ALLOWED_CHAT_IDS": "1, 2",
                "TELEGRAM_CHAT_ID": "3",
            },
            clear=False,
        ):
            self.assertEqual(get_allowed_chat_ids_from_env(), {"1", "2"})

    def test_allowed_chat_ids_falls_back_to_notification_chat_id(self):
        with patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "-100123"}, clear=True):
            self.assertEqual(get_allowed_chat_ids_from_env(), {"-100123"})

    def test_prepare_message_strips_command_bot_username(self):
        message = {
            "message_id": 10,
            "text": "/ask@DailyStockBot 920402",
            "chat": {"id": "1", "type": "group"},
            "from": {"id": 9},
        }

        prepared = prepare_message(message, TelegramIdentity(bot_id=42, username="DailyStockBot"))

        self.assertTrue(prepared.should_dispatch)
        self.assertEqual(prepared.text, "/ask 920402")

    def test_reply_to_report_becomes_chat_with_context(self):
        report = "硅烷科技 (920402)\n检查项5：筹码健康（数据缺失）"
        message = {
            "message_id": 11,
            "text": "这个还能拿吗？",
            "chat": {"id": "1", "type": "group"},
            "from": {"id": 9},
            "reply_to_message": {
                "text": report,
                "from": {"id": 42, "is_bot": True},
            },
        }

        prepared = prepare_message(message, TelegramIdentity(bot_id=42, username="DailyStockBot"))

        self.assertTrue(prepared.should_dispatch)
        self.assertEqual(prepared.reason, "reply-report")
        self.assertTrue(prepared.text.startswith("/chat "))
        self.assertIn("股票代码：920402", prepared.text)
        self.assertIn("这个还能拿吗？", prepared.text)

    def test_extract_stock_code_prefers_parenthesized_code(self):
        self.assertEqual(extract_stock_code("报告生成时间：2026-04-22\n硅烷科技（920402）"), "920402")

    def test_build_reply_chat_prompt_truncates_long_report(self):
        prompt = build_reply_chat_prompt("风险在哪里？", "硅烷科技 (920402)\n" + "x" * 4000)

        self.assertIn("股票代码：920402", prompt)
        self.assertIn("...（报告已截断）", prompt)
        self.assertIn("风险在哪里？", prompt)


if __name__ == "__main__":
    unittest.main()
