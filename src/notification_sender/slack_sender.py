# -*- coding: utf-8 -*-
"""
Slack 发送提醒服务

职责：
1. 通过 Incoming Webhook 或 Slack Bot API 发送 Slack 消息
"""
import logging
import json
import requests

from src.config import Config
from src.formatters import chunk_content_by_max_bytes

logger = logging.getLogger(__name__)

# Slack Block Kit 中单个 section block 的 text 字段上限为 3000 字符
_BLOCK_TEXT_LIMIT = 3000
# Slack chat.postMessage / Webhook 的 text 字段上限约 40000 字符，保守取 39000
_TEXT_LIMIT = 39000


class SlackSender:

    def __init__(self, config: Config):
        """
        初始化 Slack 配置

        Args:
            config: 配置对象
        """
        self._slack_webhook_url = getattr(config, 'slack_webhook_url', None)
        self._slack_bot_token = getattr(config, 'slack_bot_token', None)
        self._slack_channel_id = getattr(config, 'slack_channel_id', None)
        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)

    def _is_slack_configured(self) -> bool:
        """检查 Slack 配置是否完整（支持 Webhook 或 Bot API）"""
        webhook_ok = bool(self._slack_webhook_url)
        bot_ok = bool(self._slack_bot_token and self._slack_channel_id)
        return webhook_ok or bot_ok

    def send_to_slack(self, content: str) -> bool:
        """
        推送消息到 Slack（支持 Webhook 和 Bot API）

        Args:
            content: Markdown 格式的消息内容

        Returns:
            是否发送成功
        """
        # 按字节分块，避免单条消息超限
        try:
            chunks = chunk_content_by_max_bytes(content, _TEXT_LIMIT, add_page_marker=True)
        except Exception as e:
            logger.error(f"分割 Slack 消息失败: {e}, 尝试整段发送。")
            chunks = [content]

        # 优先使用 Webhook（配置简单）
        if self._slack_webhook_url:
            return all(self._send_slack_webhook(chunk) for chunk in chunks)

        # 其次使用 Bot API
        if self._slack_bot_token and self._slack_channel_id:
            return all(self._send_slack_bot(chunk) for chunk in chunks)

        logger.warning("Slack 配置不完整，跳过推送")
        return False

    def _build_blocks(self, content: str) -> list:
        """
        将内容构建为 Slack Block Kit 格式

        如果内容超过单个 section block 限制，会自动拆分为多个 block。
        """
        blocks = []
        # 按 block text 上限拆分
        pos = 0
        while pos < len(content):
            segment = content[pos:pos + _BLOCK_TEXT_LIMIT]
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": segment
                }
            })
            pos += _BLOCK_TEXT_LIMIT
        return blocks

    def _send_slack_webhook(self, content: str) -> bool:
        """
        使用 Incoming Webhook 发送消息到 Slack

        Args:
            content: 消息内容

        Returns:
            是否发送成功
        """
        try:
            payload = {
                "text": content,
                "blocks": self._build_blocks(content),
            }
            response = requests.post(
                self._slack_webhook_url,
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type': 'application/json; charset=utf-8'},
                timeout=15,
                verify=self._webhook_verify_ssl,
            )
            if response.status_code == 200 and response.text == "ok":
                logger.info("Slack Webhook 消息发送成功")
                return True
            logger.error(f"Slack Webhook 发送失败: HTTP {response.status_code} {response.text[:200]}")
            return False
        except Exception as e:
            logger.error(f"Slack Webhook 发送异常: {e}")
            return False

    def _send_slack_bot(self, content: str) -> bool:
        """
        使用 Bot API (chat.postMessage) 发送消息到 Slack

        Args:
            content: 消息内容

        Returns:
            是否发送成功
        """
        try:
            headers = {
                'Authorization': f'Bearer {self._slack_bot_token}',
                'Content-Type': 'application/json; charset=utf-8',
            }
            payload = {
                "channel": self._slack_channel_id,
                "text": content,
                "blocks": self._build_blocks(content),
            }
            response = requests.post(
                'https://slack.com/api/chat.postMessage',
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                headers=headers,
                timeout=15,
            )
            result = response.json()
            if result.get("ok"):
                logger.info("Slack Bot 消息发送成功")
                return True
            logger.error(f"Slack Bot 发送失败: {result.get('error', 'unknown')}")
            return False
        except Exception as e:
            logger.error(f"Slack Bot 发送异常: {e}")
            return False

    def _send_slack_image(self, image_bytes: bytes, fallback_content: str = "") -> bool:
        """
        发送图片到 Slack

        Bot 模式下使用 files.upload v2 接口；Webhook 模式下回退为文本。

        Args:
            image_bytes: PNG 图片字节
            fallback_content: 图片发送失败时的回退文本

        Returns:
            是否发送成功
        """
        # Bot 模式：使用 files.upload
        if self._slack_bot_token and self._slack_channel_id:
            try:
                response = requests.post(
                    'https://slack.com/api/files.uploadV2',
                    headers={'Authorization': f'Bearer {self._slack_bot_token}'},
                    data={
                        'channel_id': self._slack_channel_id,
                        'title': '股票分析报告',
                        'filename': 'report.png',
                    },
                    files={'file': ('report.png', image_bytes, 'image/png')},
                    timeout=30,
                )
                result = response.json()
                if result.get("ok"):
                    logger.info("Slack Bot 图片发送成功")
                    return True
                logger.error(f"Slack Bot 图片发送失败: {result.get('error', 'unknown')}")
            except Exception as e:
                logger.error(f"Slack Bot 图片发送异常: {e}")

        # Webhook 模式或 Bot 上传失败：回退为文本
        if fallback_content:
            logger.info("Slack 图片不支持或失败，回退为文本发送")
            return self.send_to_slack(fallback_content)

        logger.warning("Slack 图片发送失败，且无回退内容")
        return False
