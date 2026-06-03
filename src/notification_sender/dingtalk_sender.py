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

        # Pre-compute per-message overheads so send/chunk decisions use actual payload sizes.
        # keyword prefix bytes (empty string when no keyword configured)
        self._keyword_prefix_bytes = len(self._get_keyword_prefix().encode('utf-8'))
        # JSON payload skeleton without text content
        _empty_payload = self._build_payload("")
        self._payload_skeleton_bytes = len(json.dumps(_empty_payload, ensure_ascii=False).encode('utf-8'))
        # Maximum marker overhead for chunked messages: "\n\n📄 *(999/999)*" + safety margin
        self._page_marker_max_bytes = max(
            len("\n\n📄 *(99/99)*".encode('utf-8')),
            len("\n\n📄 *(999/999)*".encode('utf-8')),
        ) + 4  # modest safety margin for emoji width variance

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
        # Effective budget for raw content: max_bytes minus payload skeleton and keyword prefix.
        # This matches the actual bytes that _send_dingtalk_message will POST.
        content_budget = max_bytes - self._payload_skeleton_bytes - self._keyword_prefix_bytes

        if content_budget <= 0:
            logger.error(f"钉钉消息限制({max_bytes}字节)不足以容纳最小通知结构")
            return False

        # Judge against raw content bytes — if it exceeds the effective budget,
        # chunking is needed.  The chunked path accounts for per-chunk marker overhead.
        content_bytes = len(content.encode('utf-8'))
        if content_bytes > content_budget:
            logger.info(f"钉钉消息内容超长({content_bytes}字节/{len(content)}字符)，将分批发送")
            return self._send_dingtalk_chunked_msg(content, content_budget)

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

    def _send_dingtalk_chunked_msg(self, content: str, content_budget: int) -> bool:
        """
        分批发送长消息到钉钉

        按内容块智能分割，确保每批不超过 max_bytes。

        ``content_budget`` is the maximum raw content bytes a single chunk payload
        may contain, already reduced by payload skeleton + keyword prefix overhead.
        This method further subtracts per-chunk marker overhead.

        Args:
            content: 完整消息内容
            content_budget: 单条消息对raw content的预算

        Returns:
            是否全部发送成功
        """
        # Per-chunk budget must also reserve room for the page marker "\n\n📄 *(N/T)*"
        chunk_budget = content_budget - self._page_marker_max_bytes
        if chunk_budget < 100:
            logger.error(
                f"钉钉消息限制太小，单条 chunk 可用预算 {chunk_budget} 字节，无法发送 "
                f"(max_bytes={self._dingtalk_max_bytes}, "
                f"keyword_bytes={self._keyword_prefix_bytes}, "
                f"payload_overhead={self._payload_skeleton_bytes})"
            )
            return False

        chunks = chunk_content_by_max_bytes(content, chunk_budget)
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
