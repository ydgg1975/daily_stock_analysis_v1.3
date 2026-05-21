# -*- coding: utf-8 -*-
"""
===================================
Base platform adapter
===================================

Defines the abstract base class that platform adapters inherit.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple

from bot.models import BotMessage, BotResponse, WebhookResponse


class BotPlatform(ABC):
    """
    Abstract base class for platform adapters.

    Responsible for:
    1. Validate Webhook request signature.
    2. Parse platform messages into a shared format.
    3. Convert responses into platform-specific format.

    使用示例：
        class MyPlatform(BotPlatform):
            @property
            def platform_name(self) -> str:
                return "myplatform"

            def verify_request(self, headers, body) -> bool:
                # 验证签名逻辑
                return True

            def parse_message(self, data) -> Optional[BotMessage]:
                # 解析消息逻辑
                return BotMessage(...)

            def format_response(self, response, message) -> WebhookResponse:
                # 格式化响应逻辑
                return WebhookResponse.success({"text": response.text})
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """
        Platform identifier.

        Used for routing and log identifiers such as "feishu" and "dingtalk".
        """
        pass

    @abstractmethod
    def verify_request(self, headers: Dict[str, str], body: bytes) -> bool:
        """
        验证请求签名

        Each platform has its own signature validation mechanism.

        Args:
            headers: HTTP 请求头
            body: 请求体原始字节

        Returns:
            Whether the signature is valid.
        """
        pass

    @abstractmethod
    def parse_message(self, data: Dict[str, Any]) -> Optional[BotMessage]:
        """
        Parse platform messages into a shared format.

        将平台特定的消息格式转换为 BotMessage。
        如果不是需要处理的消息类型（如事件回调），返回 None。

        Args:
            data: Parsed JSON data.

        Returns:
            BotMessage object, or None when no handling is needed.
        """
        pass

    @abstractmethod
    def format_response(
        self,
        response: BotResponse,
        message: BotMessage
    ) -> WebhookResponse:
        """
        将统一响应转换为平台格式

        Args:
            response: 统一响应对象
            message: Original message object.（用于获取回复目标等信息）

        Returns:
            WebhookResponse object.
        """
        pass

    def send_followup(
        self,
        response: 'BotResponse',
        message: 'BotMessage',
    ) -> bool:
        """Send a follow-up message after a deferred webhook response.

        Override in platforms that return a deferred acknowledgement
        (e.g. Discord type 5) so the final command result can be delivered
        asynchronously.  The default implementation is a no-op.

        Returns:
            ``True`` if the follow-up was sent successfully.
        """
        return False

    def handle_challenge(self, data: Dict[str, Any]) -> Optional[WebhookResponse]:
        """
        Handle platform verification request.

        部分平台在配置 Webhook 时会发送验证请求，需要返回特定响应。
        子类可重写此方法。

        Args:
            data: 请求数据

        Returns:
            Verification response, or None when not a verification request.
        """
        return None

    def handle_webhook(
        self,
        headers: Dict[str, str],
        body: bytes,
        data: Dict[str, Any]
    ) -> Tuple[Optional[BotMessage], Optional[WebhookResponse]]:
        """
        处理 Webhook 请求

        这是主入口方法，协调验证、解析等流程。

        Args:
            headers: HTTP 请求头
            body: 请求体原始字节
            data: Parsed JSON data.

        Returns:
            (BotMessage, WebhookResponse) 元组
            - 如果是验证请求：(None, challenge_response)
            - 如果是普通消息：(message, None) - 响应将在命令处理后生成
            - 如果验证失败或无需处理：(None, error_response 或 None)
        """
        # 1. 检查是否是验证请求
        challenge_response = self.handle_challenge(data)
        if challenge_response:
            return None, challenge_response

        # 2. 验证请求签名
        if not self.verify_request(headers, body):
            return None, WebhookResponse.error("Invalid signature", 403)

        # 3. 解析消息
        message = self.parse_message(data)

        return message, None
