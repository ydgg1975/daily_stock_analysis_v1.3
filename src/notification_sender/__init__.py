# -*- coding: utf-8 -*-
"""알림 발송 채널 모듈."""

import logging

logger = logging.getLogger(__name__)


class _UnavailableSender:
    """깨진 선택 채널이 전체 앱 import를 막지 않도록 하는 대체 클래스."""

    def __init__(self, *args, **kwargs):
        pass


def _safe_import(module_name: str, class_name: str):
    try:
        module = __import__(f"{__name__}.{module_name}", fromlist=[class_name])
        return getattr(module, class_name)
    except Exception as exc:
        logger.warning("알림 sender %s.%s 로드 실패: %s", module_name, class_name, exc)
        return type(class_name, (_UnavailableSender,), {})


AstrbotSender = _safe_import("astrbot_sender", "AstrbotSender")
CustomWebhookSender = _safe_import("custom_webhook_sender", "CustomWebhookSender")
DiscordSender = _safe_import("discord_sender", "DiscordSender")
EmailSender = _safe_import("email_sender", "EmailSender")
FeishuSender = _safe_import("feishu_sender", "FeishuSender")
GotifySender = _safe_import("gotify_sender", "GotifySender")
NtfySender = _safe_import("ntfy_sender", "NtfySender")
PushoverSender = _safe_import("pushover_sender", "PushoverSender")
PushplusSender = _safe_import("pushplus_sender", "PushplusSender")
Serverchan3Sender = _safe_import("serverchan3_sender", "Serverchan3Sender")
SlackSender = _safe_import("slack_sender", "SlackSender")
TelegramSender = _safe_import("telegram_sender", "TelegramSender")
WechatSender = _safe_import("wechat_sender", "WechatSender")

try:
    from .gotify_sender import resolve_gotify_message_endpoint
except Exception:
    def resolve_gotify_message_endpoint(base_url: str) -> str:
        return base_url

try:
    from .ntfy_sender import resolve_ntfy_endpoint
except Exception:
    def resolve_ntfy_endpoint(base_url: str) -> str:
        return base_url

try:
    from .wechat_sender import WECHAT_IMAGE_MAX_BYTES
except Exception:
    WECHAT_IMAGE_MAX_BYTES = 2 * 1024 * 1024
