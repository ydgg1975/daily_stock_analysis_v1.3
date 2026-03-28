# -*- coding: utf-8 -*-
"""
Unit tests for src.notification_sender module.

Tests sender classes in isolation (config, request shape, error handling).
Does not duplicate test_notification.py which tests NotificationService.send() flow.
"""
import os
import sys
import unittest
from email.header import decode_header, make_header
from email.utils import parseaddr
from unittest import mock
from typing import Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import Config
from src.notification_sender import (
    AstrbotSender,
    CustomWebhookSender,
    DiscordSender,
    EmailSender,
    FeishuSender,
    PushoverSender,
    PushplusSender,
    Serverchan3Sender,
    SlackSender,
    TelegramSender,
    WechatSender,
    WECHAT_IMAGE_MAX_BYTES,
)


def _config(**overrides):
    """Minimal Config for sender tests."""
    return Config(stock_list=[], **overrides)


def _response(status_code: int, json_body: Optional[dict] = None):
    resp = mock.MagicMock()
    resp.status_code = status_code
    if status_code == 200:
        resp.text = "ok"
    else:
        resp.text = "error"
    if json_body is not None:
        resp.json.return_value = json_body
    return resp


class TestDiscordSender(unittest.TestCase):
    """Unit tests for DiscordSender."""

    def test_send_returns_false_when_not_configured(self):
        cfg = _config()
        sender = DiscordSender(cfg)
        result = sender.send_to_discord("hello")
        self.assertFalse(result)

    def test_is_discord_configured_webhook_only(self):
        cfg = _config(discord_webhook_url="https://discord.com/webhook/1")
        sender = DiscordSender(cfg)
        self.assertTrue(sender._is_discord_configured())

    def test_is_discord_configured_bot_only(self):
        cfg = _config(discord_bot_token="T", discord_main_channel_id="123")
        sender = DiscordSender(cfg)
        self.assertTrue(sender._is_discord_configured())

    def test_is_discord_configured_neither(self):
        cfg = _config()
        sender = DiscordSender(cfg)
        self.assertFalse(sender._is_discord_configured())

    @mock.patch("src.notification_sender.discord_sender.requests.post")
    def test_send_webhook_success_builds_correct_payload(self, mock_post):
        mock_post.return_value = _response(200)
        cfg = _config(discord_webhook_url="https://discord.com/webhook/1")
        sender = DiscordSender(cfg)
        result = sender.send_to_discord("content")
        self.assertTrue(result)
        mock_post.assert_called_once()
        call_kw = mock_post.call_args[1]
        self.assertEqual(call_kw["json"]["content"], "content")
        self.assertIn("username", call_kw["json"])

    @mock.patch("src.notification_sender.discord_sender.requests.post")
    def test_send_webhook_http_error_returns_false(self, mock_post):
        mock_post.return_value = _response(400)
        cfg = _config(discord_webhook_url="https://discord.com/webhook/1")
        sender = DiscordSender(cfg)
        result = sender.send_to_discord("content")
        self.assertFalse(result)

    @mock.patch("src.notification_sender.discord_sender.requests.post")
    def test_send_bot_success_uses_channel_url(self, mock_post):
        mock_post.return_value = _response(200)
        cfg = _config(discord_bot_token="TOKEN", discord_main_channel_id="CH123")
        sender = DiscordSender(cfg)
        result = sender.send_to_discord("content")
        self.assertTrue(result)
        self.assertIn("discord.com/api/v10/channels/CH123/messages", mock_post.call_args[0][0])
        call_kw = mock_post.call_args[1]
        self.assertEqual(call_kw["headers"]["Authorization"], "Bot TOKEN")

    @mock.patch("src.notification_sender.discord_sender.requests.post")
    def test_send_bot_accepts_any_2xx_status(self, mock_post):
        mock_post.return_value = _response(201)
        cfg = _config(discord_bot_token="TOKEN", discord_main_channel_id="CH123")
        sender = DiscordSender(cfg)
        result = sender.send_to_discord("content")
        self.assertTrue(result)

    def test_chunking_prefers_markdown_sections(self):
        cfg = _config(discord_webhook_url="https://discord.com/webhook/1", discord_max_words=120)
        sender = DiscordSender(cfg)
        content = (
            "# Title\n\n"
            "## 重要信息速览\n" + ("A" * 40) + "\n\n"
            "## 核心结论\n" + ("B" * 40) + "\n\n"
            "## 数据透视\n" + ("C" * 40)
        )
        chunks = sender._chunk_discord_content(content)
        self.assertGreaterEqual(len(chunks), 2)
        combined = "\n".join(chunks)
        self.assertIn("## 重要信息速览", combined)
        self.assertIn("## 核心结论", combined)
        self.assertIn("## 数据透视", combined)

    def test_chunking_enforces_discord_char_limit(self):
        cfg = _config(discord_webhook_url="https://discord.com/webhook/1", discord_max_words=2000)
        sender = DiscordSender(cfg)
        content = "## 超长章节\n" + ("甲" * 2600)
        chunks = sender._chunk_discord_content(content)
        self.assertGreaterEqual(len(chunks), 2)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), sender._discord_hard_char_limit)

    def test_optimize_markdown_for_discord_converts_table_to_bullets(self):
        content = "## 当日行情\n|字段|数值|\n|--|--|\n|当前价|125.4|\n|涨跌幅|+1.2%|"
        out = DiscordSender._optimize_markdown_for_discord(content)
        self.assertIn("- **当前价**: 125.4", out)
        self.assertNotIn("|字段|数值|", out)

    def test_optimize_markdown_for_discord_compacts_standard_report_sections(self):
        content = (
            "# 🎯 2026-03-28 股票分析日报\n"
            "> 已分析 **1** 只股票\n"
            "> 报告生成时间（北京时间）: `2026-03-28 21:35:00`\n\n"
            "## 🟡 NVIDIA (NVDA)\n"
            "### 1. 标题区 / Title\n"
            "- **评分**: 78\n"
            "- **买入 / 观望 / 卖出**: 观望\n"
            "- **看多 / 看空 / 震荡**: 看多\n"
            "- **一句话决策**: 等待回踩确认后再考虑加仓\n"
            "### 2. 重要信息速览 / Key Updates\n"
            "- **风险警报**: 估值偏高；波动放大\n"
            "- **利好催化**: AI 订单延续；数据中心需求回暖\n"
            "- **最新动态 / 重要公告**: 公司发布新品并强化生态合作\n"
            "### 4. 当日行情（常规交易时段） / Market (Regular Session)\n"
            "- **当前价**: 125.30\n"
            "- **涨跌额**: 2.30\n"
            "- **涨跌幅**: 1.87%\n"
            "### 5. 技术面 / Technicals\n"
            "- **MA20**: 120.99\n"
            "- **MA60**: 118.88\n"
            "- **RSI14**: 56.78\n"
            "- **支撑位**: 119.11\n"
            "- **压力位**: 129.00\n"
            "### 7. 作战计划 / Battle Plan\n"
            "- **理想买入点**: 120-121\n"
            "- **止损位**: 115\n"
            "- **目标位**: 132\n"
            "- **仓位建议**: 分批试仓\n"
            "### 8. 检查清单 / Checklist\n"
            "- ⚠️ 等待回踩确认\n"
            "- ✅ 量价结构未破坏\n"
        )

        out = DiscordSender._optimize_markdown_for_discord(content)

        self.assertIn("## 🟡 NVIDIA (NVDA)", out)
        self.assertIn("**评分 / 建议 / 趋势**: 78 / 观望 / 看多", out)
        self.assertIn("**核心行情**: 当前价 125.30 | 涨跌幅 1.87% | 涨跌额 2.30", out)
        self.assertIn("**作战计划**: 买点 120-121 | 止损 115 | 目标 132 | 仓位 分批试仓", out)
        self.assertIn("Checklist", out)
        self.assertNotIn("### 4. 当日行情（常规交易时段） / Market (Regular Session)", out)

    def test_send_chunks_continues_after_mid_failure(self):
        cfg = _config(discord_webhook_url="https://discord.com/webhook/1")
        sender = DiscordSender(cfg)
        with mock.patch.object(sender, "_chunk_discord_content", return_value=["c1", "c2", "c3"]), \
                mock.patch.object(sender, "_send_discord_webhook", side_effect=[True, False, True]) as mock_send:
            ok = sender.send_to_discord("any")
        self.assertFalse(ok)
        self.assertEqual(mock_send.call_count, 3)







    def test_send_returns_false_when_no_webhook_url(self):
        cfg = _config()
        sender = WechatSender(cfg)
        result = sender.send_to_wechat("hello")
        self.assertFalse(result)

    @mock.patch("src.notification_sender.wechat_sender.requests.post")
    def test_send_success_returns_true(self, mock_post):
        mock_post.return_value = _response(200, {"errcode": 0})
        cfg = _config(wechat_webhook_url="https://wechat.example/hook")
        sender = WechatSender(cfg)
        result = sender.send_to_wechat("hello")
        self.assertTrue(result)

    def test_gen_wechat_payload_markdown(self):
        cfg = _config(wechat_webhook_url="u", wechat_msg_type="markdown")
        sender = WechatSender(cfg)
        payload = sender._gen_wechat_payload("## title\nbody")
        self.assertEqual(payload["msgtype"], "markdown")
        self.assertEqual(payload["markdown"]["content"], "## title\nbody")

    def test_gen_wechat_payload_text(self):
        cfg = _config(wechat_webhook_url="u", wechat_msg_type="text")
        sender = WechatSender(cfg)
        payload = sender._gen_wechat_payload("plain")
        self.assertEqual(payload["msgtype"], "text")
        self.assertEqual(payload["text"]["content"], "plain")

    @mock.patch("src.notification_sender.wechat_sender.requests.post")
    def test_send_wechat_image_over_limit_returns_false(self, mock_post):
        cfg = _config(wechat_webhook_url="https://wechat.example/hook")
        sender = WechatSender(cfg)
        big = b"x" * (WECHAT_IMAGE_MAX_BYTES + 1)
        result = sender._send_wechat_image(big)
        self.assertFalse(result)
        mock_post.assert_not_called()


class TestFeishuSender(unittest.TestCase):
    """Unit tests for FeishuSender."""

    def test_send_returns_false_when_no_webhook_url(self):
        cfg = _config()
        sender = FeishuSender(cfg)
        result = sender.send_to_feishu("hello")
        self.assertFalse(result)

    @mock.patch("src.notification_sender.feishu_sender.requests.post")
    def test_send_success_returns_true(self, mock_post):
        mock_post.return_value = _response(200, {"code": 0})
        cfg = _config(feishu_webhook_url="https://feishu.example/hook")
        sender = FeishuSender(cfg)
        result = sender.send_to_feishu("hello")
        self.assertTrue(result)

    @mock.patch("src.notification_sender.feishu_sender.requests.post")
    def test_send_http_error_returns_false(self, mock_post):
        mock_post.return_value = _response(400)
        cfg = _config(feishu_webhook_url="https://feishu.example/hook")
        sender = FeishuSender(cfg)
        result = sender.send_to_feishu("hello")
        self.assertFalse(result)


class TestEmailSender(unittest.TestCase):
    """Unit tests for EmailSender (config and receiver logic; send path covered via service)."""

    def test_send_returns_false_when_not_configured(self):
        cfg = _config()
        sender = EmailSender(cfg)
        result = sender.send_to_email("body")
        self.assertFalse(result)

    def test_get_receivers_for_stocks_no_groups_returns_default(self):
        cfg = _config(
            email_sender="a@qq.com",
            email_password="p",
            email_receivers=["b@qq.com", "c@qq.com"],
        )
        sender = EmailSender(cfg)
        self.assertEqual(
            sender.get_receivers_for_stocks(["000001"]),
            ["b@qq.com", "c@qq.com"],
        )

    def test_get_receivers_for_stocks_with_matching_group(self):
        cfg = _config(
            email_sender="a@qq.com",
            email_password="p",
            email_receivers=["default@qq.com"],
            stock_email_groups=[(["000001", "600519"], ["group1@qq.com"])],
        )
        sender = EmailSender(cfg)
        self.assertEqual(
            sender.get_receivers_for_stocks(["000001"]),
            ["group1@qq.com"],
        )

    def test_get_receivers_for_stocks_no_match_falls_back_to_default(self):
        cfg = _config(
            email_sender="a@qq.com",
            email_password="p",
            email_receivers=["default@qq.com"],
            stock_email_groups=[(["000001"], ["group@qq.com"])],
        )
        sender = EmailSender(cfg)
        self.assertEqual(
            sender.get_receivers_for_stocks(["999999"]),
            ["default@qq.com"],
        )

    def test_get_all_email_receivers_returns_union(self):
        cfg = _config(
            email_sender="a@qq.com",
            email_password="p",
            email_receivers=["default@qq.com"],
            stock_email_groups=[
                (["000001"], ["g1@qq.com"]),
                (["600519"], ["g2@qq.com"]),
            ],
        )
        sender = EmailSender(cfg)
        receivers = sender.get_all_email_receivers()
        self.assertIn("g1@qq.com", receivers)
        self.assertIn("g2@qq.com", receivers)
        self.assertIn("default@qq.com", receivers)

    @mock.patch("smtplib.SMTP_SSL")
    def test_send_to_email_encodes_non_ascii_sender_name(self, mock_smtp_ssl):
        cfg = _config(
            email_sender="a@qq.com",
            email_password="p",
            email_receivers=["b@qq.com"],
            email_sender_name="daily_stock_analysis股票分析助手",
        )
        sender = EmailSender(cfg)

        result = sender.send_to_email("body", subject="测试主题")

        self.assertTrue(result)
        server = mock_smtp_ssl.return_value
        server.send_message.assert_called_once()
        msg = server.send_message.call_args[0][0]
        realname, addr = parseaddr(msg["From"])
        self.assertEqual(addr, "a@qq.com")
        self.assertEqual(
            str(make_header(decode_header(realname))),
            "daily_stock_analysis股票分析助手",
        )
        server.quit.assert_called_once()

    @mock.patch("smtplib.SMTP_SSL")
    def test_send_image_email_encodes_non_ascii_sender_name(self, mock_smtp_ssl):
        cfg = _config(
            email_sender="a@qq.com",
            email_password="p",
            email_receivers=["b@qq.com"],
            email_sender_name="daily_stock_analysis股票分析助手",
        )
        sender = EmailSender(cfg)

        result = sender._send_email_with_inline_image(b"PNG_BYTES", receivers=["b@qq.com"])

        self.assertTrue(result)
        server = mock_smtp_ssl.return_value
        server.send_message.assert_called_once()
        msg = server.send_message.call_args[0][0]
        realname, addr = parseaddr(msg["From"])
        self.assertEqual(addr, "a@qq.com")
        self.assertEqual(
            str(make_header(decode_header(realname))),
            "daily_stock_analysis股票分析助手",
        )
        server.quit.assert_called_once()


class TestAstrbotSender(unittest.TestCase):
    """Unit tests for AstrbotSender."""

    def test_send_returns_false_when_no_url(self):
        cfg = _config()
        sender = AstrbotSender(cfg)
        result = sender.send_to_astrbot("hello")
        self.assertFalse(result)

    @mock.patch("src.notification_sender.astrbot_sender.requests.post")
    def test_send_success_returns_true(self, mock_post):
        mock_post.return_value = _response(200)
        cfg = _config(astrbot_url="https://astrbot.example/api")
        sender = AstrbotSender(cfg)
        result = sender.send_to_astrbot("hello")
        self.assertTrue(result)
        self.assertEqual(mock_post.call_args[0][0], "https://astrbot.example/api")


class TestCustomWebhookSender(unittest.TestCase):
    """Unit tests for CustomWebhookSender."""

    def test_send_returns_false_when_no_urls(self):
        cfg = _config()
        sender = CustomWebhookSender(cfg)
        result = sender.send_to_custom("hello")
        self.assertFalse(result)

    @mock.patch("src.notification_sender.custom_webhook_sender.requests.post")
    def test_send_success_payload_has_text_and_content(self, mock_post):
        mock_post.return_value = _response(200)
        cfg = _config(custom_webhook_urls=["https://example.com/webhook"])
        sender = CustomWebhookSender(cfg)
        result = sender.send_to_custom("hello")
        self.assertTrue(result)
        body = mock_post.call_args[1]["data"].decode("utf-8")
        self.assertIn("hello", body)


class TestPushoverSender(unittest.TestCase):
    """Unit tests for PushoverSender."""

    def test_send_returns_false_when_not_configured(self):
        cfg = _config()
        sender = PushoverSender(cfg)
        result = sender.send_to_pushover("hello")
        self.assertFalse(result)

    @mock.patch("src.notification_sender.pushover_sender.requests.post")
    def test_send_success_returns_true(self, mock_post):
        mock_post.return_value = _response(200, {"status": 1})
        cfg = _config(pushover_user_key="U", pushover_api_token="T")
        sender = PushoverSender(cfg)
        result = sender.send_to_pushover("hello")
        self.assertTrue(result)
        call_data = mock_post.call_args[1]["data"]
        self.assertEqual(call_data["user"], "U")
        self.assertEqual(call_data["token"], "T")


class TestPushplusSender(unittest.TestCase):
    """Unit tests for PushplusSender."""

    def test_send_returns_false_when_no_token(self):
        cfg = _config()
        sender = PushplusSender(cfg)
        result = sender.send_to_pushplus("hello")
        self.assertFalse(result)

    @mock.patch("src.notification_sender.pushplus_sender.requests.post")
    def test_send_success_returns_true(self, mock_post):
        mock_post.return_value = _response(200, {"code": 200})
        cfg = _config(pushplus_token="TOKEN")
        sender = PushplusSender(cfg)
        result = sender.send_to_pushplus("hello")
        self.assertTrue(result)

    @mock.patch("src.notification_sender.pushplus_sender.time.sleep")
    @mock.patch("src.notification_sender.pushplus_sender.requests.post")
    def test_send_long_message_chunks_pushplus_requests(self, mock_post, _mock_sleep):
        mock_post.return_value = _response(200, {"code": 200})
        cfg = _config(pushplus_token="TOKEN")
        sender = PushplusSender(cfg)

        result = sender.send_to_pushplus("A" * 25000)

        self.assertTrue(result)
        self.assertGreaterEqual(mock_post.call_count, 2)


class TestServerchan3Sender(unittest.TestCase):
    """Unit tests for Serverchan3Sender."""

    def test_send_returns_false_when_no_sendkey(self):
        cfg = _config()
        sender = Serverchan3Sender(cfg)
        result = sender.send_to_serverchan3("hello")
        self.assertFalse(result)

    @mock.patch("src.notification_sender.serverchan3_sender.requests.post")
    def test_send_success_returns_true(self, mock_post):
        mock_post.return_value = _response(200, {"code": 0})
        cfg = _config(serverchan3_sendkey="SCT123")
        sender = Serverchan3Sender(cfg)
        result = sender.send_to_serverchan3("hello")
        self.assertTrue(result)


class TestSlackSender(unittest.TestCase):
    """Unit tests for SlackSender."""

    def test_send_returns_false_when_not_configured(self):
        cfg = _config()
        sender = SlackSender(cfg)
        result = sender.send_to_slack("hello")
        self.assertFalse(result)

    def test_is_slack_configured_webhook_only(self):
        cfg = _config(slack_webhook_url="https://hooks.slack.com/services/T/B/xxx")
        sender = SlackSender(cfg)
        self.assertTrue(sender._is_slack_configured())

    def test_is_slack_configured_bot_only(self):
        cfg = _config(slack_bot_token="xoxb-test", slack_channel_id="C123")
        sender = SlackSender(cfg)
        self.assertTrue(sender._is_slack_configured())

    def test_is_slack_configured_neither(self):
        cfg = _config()
        sender = SlackSender(cfg)
        self.assertFalse(sender._is_slack_configured())

    @mock.patch("src.notification_sender.slack_sender.requests.post")
    def test_send_webhook_success(self, mock_post):
        resp = mock.MagicMock()
        resp.status_code = 200
        resp.text = "ok"
        mock_post.return_value = resp
        cfg = _config(slack_webhook_url="https://hooks.slack.com/services/T/B/xxx")
        sender = SlackSender(cfg)
        result = sender.send_to_slack("hello")
        self.assertTrue(result)
        mock_post.assert_called_once()

    @mock.patch("src.notification_sender.slack_sender.requests.post")
    def test_send_webhook_http_error_returns_false(self, mock_post):
        resp = mock.MagicMock()
        resp.status_code = 400
        resp.text = "invalid_payload"
        mock_post.return_value = resp
        cfg = _config(slack_webhook_url="https://hooks.slack.com/services/T/B/xxx")
        sender = SlackSender(cfg)
        result = sender.send_to_slack("hello")
        self.assertFalse(result)

    @mock.patch("src.notification_sender.slack_sender.requests.post")
    def test_send_bot_success(self, mock_post):
        mock_post.return_value = _response(200, {"ok": True})
        cfg = _config(slack_bot_token="xoxb-test", slack_channel_id="C123")
        sender = SlackSender(cfg)
        result = sender.send_to_slack("hello")
        self.assertTrue(result)
        self.assertIn("chat.postMessage", mock_post.call_args[0][0])

    @mock.patch("src.notification_sender.slack_sender.requests.post")
    def test_send_bot_error_returns_false(self, mock_post):
        mock_post.return_value = _response(200, {"ok": False, "error": "channel_not_found"})
        cfg = _config(slack_bot_token="xoxb-test", slack_channel_id="C123")
        sender = SlackSender(cfg)
        result = sender.send_to_slack("hello")
        self.assertFalse(result)

    def test_build_blocks_splits_long_content(self):
        cfg = _config(slack_webhook_url="https://hooks.slack.com/services/T/B/xxx")
        sender = SlackSender(cfg)
        content = "A" * 6500  # > 3000 * 2, should produce 3 blocks
        blocks = sender._build_blocks(content)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0]["type"], "section")
        self.assertEqual(blocks[0]["text"]["type"], "mrkdwn")

    @mock.patch("src.notification_sender.slack_sender.requests.post")
    def test_send_text_prefers_bot_when_both_configured(self, mock_post):
        """When both webhook and bot are configured, text must go via bot
        so it lands in the same channel as images."""
        mock_post.return_value = _response(200, {"ok": True})
        cfg = _config(
            slack_webhook_url="https://hooks.slack.com/services/T/B/xxx",
            slack_bot_token="xoxb-test",
            slack_channel_id="C123",
        )
        sender = SlackSender(cfg)
        result = sender.send_to_slack("hello")
        self.assertTrue(result)
        self.assertIn("chat.postMessage", mock_post.call_args[0][0])

    @mock.patch("src.notification_sender.slack_sender.requests.post")
    def test_send_image_bot_success(self, mock_post):
        # Mock three sequential calls: getUploadURLExternal, PUT upload, completeUploadExternal
        mock_post.side_effect = [
            _response(200, {"ok": True, "upload_url": "https://files.slack.com/upload/v1/test", "file_id": "F123"}),
            _response(200, {}),
            _response(200, {"ok": True}),
        ]
        cfg = _config(slack_bot_token="xoxb-test", slack_channel_id="C123")
        sender = SlackSender(cfg)
        result = sender._send_slack_image(b"PNG_BYTES")
        self.assertTrue(result)
        self.assertEqual(mock_post.call_count, 3)
        self.assertIn("getUploadURLExternal", mock_post.call_args_list[0][0][0])
        # Step 2: upload must send raw bytes (not multipart) to match declared length
        upload_call_kwargs = mock_post.call_args_list[1][1]
        self.assertEqual(upload_call_kwargs.get("data"), b"PNG_BYTES")
        self.assertNotIn("files", upload_call_kwargs)
        self.assertIn("completeUploadExternal", mock_post.call_args_list[2][0][0])

    @mock.patch("src.notification_sender.slack_sender.requests.post")
    def test_send_image_fallback_to_text_when_no_bot(self, mock_post):
        resp = mock.MagicMock()
        resp.status_code = 200
        resp.text = "ok"
        mock_post.return_value = resp
        cfg = _config(slack_webhook_url="https://hooks.slack.com/services/T/B/xxx")
        sender = SlackSender(cfg)
        result = sender._send_slack_image(b"PNG_BYTES", fallback_content="fallback text")
        self.assertTrue(result)


class TestTelegramSender(unittest.TestCase):
    """Unit tests for TelegramSender."""

    def test_send_returns_false_when_not_configured(self):
        cfg = _config()
        sender = TelegramSender(cfg)
        result = sender.send_to_telegram("hello")
        self.assertFalse(result)

    @mock.patch("src.notification_sender.telegram_sender.requests.post")
    def test_send_success_returns_true(self, mock_post):
        mock_post.return_value = _response(200, {"ok": True})
        cfg = _config(telegram_bot_token="BOT", telegram_chat_id="CHAT")
        sender = TelegramSender(cfg)
        result = sender.send_to_telegram("hello")
        self.assertTrue(result)
        self.assertIn("sendMessage", mock_post.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
