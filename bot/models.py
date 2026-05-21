# -*- coding: utf-8 -*-
"""
Bot message and response models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List


class ChatType(str, Enum):
    """Chat type."""
    GROUP = "group"
    PRIVATE = "private"
    UNKNOWN = "unknown"


class Platform(str, Enum):
    """Bot platform type."""
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    WECOM = "wecom"
    TELEGRAM = "telegram"
    UNKNOWN = "unknown"


@dataclass
class BotMessage:
    """
    Normalized inbound bot message.

    Attributes:
        platform: Platform name.
        message_id: Message identifier.
        user_id: Sender user id.
        user_name: Sender display name.
        chat_id: Chat or group id.
        chat_type: Chat type.
        content: Normalized message text.
        raw_content: Original message text.
        mentioned: Whether the bot was mentioned.
        mentions: Mentioned user ids.
        timestamp: Message timestamp.
        raw_data: Original platform payload.
    """

    platform: str
    message_id: str
    user_id: str
    user_name: str
    chat_id: str
    chat_type: ChatType
    content: str
    raw_content: str = ""
    mentioned: bool = False
    mentions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def get_command_and_args(self, prefix: str = "/") -> tuple:
        """
        Parse command name and arguments from the message content.

        Returns:
            ``(command, args)`` when a command is found, otherwise ``(None, [])``.
        """
        text = self.content.strip()

        if not text.startswith(prefix):
            localized_commands = {
                "분석": "analyze",
                "시장": "market",
                "리뷰": "market",
                "일괄": "batch",
                "도움말": "help",
                "상태": "status",
            }
            for local_cmd, en_cmd in localized_commands.items():
                if text.startswith(local_cmd):
                    args = text[len(local_cmd):].strip().split()
                    return en_cmd, args
            return None, []

        text = text[len(prefix):]
        parts = text.split()
        if not parts:
            return None, []

        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        return command, args

    def is_command(self, prefix: str = "/") -> bool:
        """Return whether the message contains a command."""
        cmd, _ = self.get_command_and_args(prefix)
        return cmd is not None


@dataclass
class BotResponse:
    """
    Normalized bot command response.

    Attributes:
        text: Response text.
        markdown: Whether text should be rendered as Markdown.
        at_user: Whether to mention the sender.
        reply_to_message: Whether to reply to the original message.
        extra: Platform-specific response metadata.
    """

    text: str
    markdown: bool = False
    at_user: bool = True
    reply_to_message: bool = True
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def text_response(cls, text: str, at_user: bool = True) -> "BotResponse":
        """Create a plain text response."""
        return cls(text=text, markdown=False, at_user=at_user)

    @classmethod
    def markdown_response(cls, text: str, at_user: bool = True) -> "BotResponse":
        """Create a Markdown response."""
        return cls(text=text, markdown=True, at_user=at_user)

    @classmethod
    def error_response(cls, message: str) -> "BotResponse":
        """Create an error response."""
        return cls(text=f"Error: {message}", markdown=False, at_user=True)


@dataclass
class WebhookResponse:
    """Normalized webhook HTTP response."""

    status_code: int = 200
    body: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def success(cls, body: Optional[Dict] = None) -> "WebhookResponse":
        """Create a successful response."""
        return cls(status_code=200, body=body or {})

    @classmethod
    def challenge(cls, challenge: str) -> "WebhookResponse":
        """Create a URL verification challenge response."""
        return cls(status_code=200, body={"challenge": challenge})

    @classmethod
    def error(cls, message: str, status_code: int = 400) -> "WebhookResponse":
        """Create an error response."""
        return cls(status_code=status_code, body={"error": message})
