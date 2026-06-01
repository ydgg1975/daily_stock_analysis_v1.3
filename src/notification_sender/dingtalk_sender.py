# -*- coding: utf-8 -*-
"""
钉钉 发送提醒服务

职责：
1. 通过钉钉自定义机器人 Webhook 发送 Markdown 消息
2. 支持安全设置（签名）
3. 消息超长时自动分批发送

钉钉自定义机器人 Webhook 文档：
- 自定义机器人接入：https://open.dingtalk.com/document/robots/custom-robot-access
- 安全设置（加签/关键词）：https://open.dingtalk.com/document/dingstart/customize-robot-security-settings
- 加签示例：https://open.dingtalk.com/document/dingstart/customize-robot-security-settings-title-ihk-nx8-km3
"""
import base64
import hashlib
import hmac
import json
import logging
import time as _time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from src.config import Config
from src.formatters import chunk_content_by_max_bytes


logger = logging.getLogger(__name__)

# 钉钉 Webhook 默认限制 ~20KB，预留 header 开销后使用
DINGTALK_DEFAULT_MAX_BYTES = 20000


class DingtalkSender:

    def __init__(self, config: Config):
        """
        初始化钉钉配置

        Args:
            config: 配置对象
        """
        self._dingtalk_url = getattr(config, 'dingtalk_webhook_url', None)
        self._dingtalk_secret = (getattr(config, 'dingtalk_webhook_secret', None) or '').strip()
        self._dingtalk_keyword = (getattr(config, 'dingtalk_webhook_keyword', None) or '').strip()
        self._dingtalk_max_bytes = getattr(config, 'dingtalk_max_bytes', DINGTALK_DEFAULT_MAX_BYTES)
        self._webhook_verify_ssl = getattr(config, 'webhook_verify_ssl', True)

    def _get_keyword_prefix(self) -> str:
        """Return the keyword prefix required by DingTalk webhook security settings."""
        if not self._dingtalk_keyword:
            return ""
        return f"{self._dingtalk_keyword}\n"

    def _apply_keyword_prefix(self, content: str) -> str:
        """Prepend the optional keyword so each webhook request passes keyword checks."""
        prefix = self._get_keyword_prefix()
        if not prefix:
            return content
        return f"{prefix}{content}" if content else self._dingtalk_keyword

    def send_to_dingtalk(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """
        推送消息到钉钉机器人

        钉钉自定义机器人 Webhook Markdown 消息格式：
        {
            "msgtype": "markdown",
            "markdown": {
                "title": "股票智能分析报告",
                "text": "markdown 内容"
            }
        }

        支持可选签名校验（安全设置）：

        注意：钉钉消息限制约 20KB，超长内容会自动分批发送
        可通过环境变量 DINGTALK_MAX_BYTES 调整限制值

        Args:
            content: Markdown 格式的消息内容

        Returns:
            是否发送成功
        """
        if not self._dingtalk_url:
            logger.warning("钉钉 Webhook 未配置，跳过推送")
            return False

        max_bytes = self._dingtalk_max_bytes

        # 检查字节长度，超长则分批发送
        content_bytes = len(content.encode('utf-8'))
        if content_bytes > max_bytes:
            logger.info(f"钉钉消息内容超长({content_bytes}字节/{len(content)}字符)，将分批发送")
            return self._send_dingtalk_chunked_msg(content, max_bytes)

        try:
            return self._send_dingtalk_message(content, timeout_seconds=timeout_seconds)
        except Exception as e:
            logger.error(f"发送钉钉消息失败: {e}")
            return False

    def _send_dingtalk_message(self, content: str, *, timeout_seconds: Optional[float] = None) -> bool:
        """发送单条钉钉 Markdown 消息"""
        prepared_content = self._apply_keyword_prefix(content)
        payload = self._build_payload(prepared_content)
        return self._post_dingtalk(payload, timeout_seconds=timeout_seconds)

    def _send_dingtalk_chunked_msg(self, content: str, max_bytes: int) -> bool:
        """
        分批发送长消息到钉钉

        按内容块智能分割，确保每批不超过限制

        Args:
            content: 完整消息内容
            max_bytes: 单条消息最大字节数

        Returns:
            是否全部发送成功
        """
        # 为 payload 开销预留空间
        budget = max(1000, max_bytes - 1500)
        chunks = chunk_content_by_max_bytes(content, budget)
        if not chunks:
            return False

        total = len(chunks)
        success_count = 0

        for i, chunk in enumerate(chunks):
            marker = f"\n\n📄 *({i + 1}/{total})*" if total > 1 else ""
            chunk_with_keyword = self._apply_keyword_prefix(chunk + marker)
            payload = self._build_payload(chunk_with_keyword)

            if self._post_dingtalk(payload, timeout_seconds=30):
                success_count += 1
            else:
                logger.error(f"钉钉第 {i + 1}/{total} 批发送失败")

            if i < total - 1:
                _time.sleep(1)

        return success_count == total

    def _build_payload(self, content: str) -> Dict[str, Any]:
        """构建钉钉消息 payload"""
        payload: Dict[str, Any] = {
            "msgtype": "markdown",
            "markdown": {
                "title": "股票智能分析报告",
                "text": content,
            },
        }

        return payload

    def _post_dingtalk(self, payload: Dict[str, Any], *, timeout_seconds: Optional[float] = None) -> bool:
        """发送 HTTP POST 请求到钉钉 Webhook"""
        if not self._dingtalk_url:
            return False

        url = self._dingtalk_url

        # 加签签名：将 timestamp 和 sign 作为 URL 查询参数，sign 需要 URL 编码
        if self._dingtalk_secret:
            timestamp = str(round(_time.time() * 1000))
            string_to_sign = f"{timestamp}\n{self._dingtalk_secret}"
            sign = base64.b64encode(
                hmac.new(
                    self._dingtalk_secret.encode('utf-8'),
                    string_to_sign.encode('utf-8'),
                    digestmod=hashlib.sha256,
                ).digest()
            ).decode('utf-8')
            params = urlencode({"timestamp": timestamp, "sign": sign})
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{params}"

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=timeout_seconds or 10,
                verify=self._webhook_verify_ssl,
            )

            if response.status_code == 200:
                result = response.json()
                errcode = result.get('errcode', -1)
                if errcode == 0:
                    logger.info("钉钉消息发送成功")
                    return True
                else:
                    errmsg = result.get('errmsg', '未知错误')
                    logger.error(f"钉钉返回错误 [errcode={errcode}]: {errmsg}")
                    return False
            else:
                logger.error(f"钉钉请求失败: HTTP {response.status_code}, {response.text[:200]}")
                return False

        except requests.exceptions.Timeout:
            logger.error("钉钉请求超时")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"钉钉连接失败: {e}")
            return False
        except Exception as e:
            logger.error(f"钉钉请求异常: {e}")
            return False
