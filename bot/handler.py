# -*- coding: utf-8 -*-
"""
===================================
Bot Webhook 처리기
===================================

각 플랫포의 Webhook 콜백을 처리하고, 명령 처리기에 분배합니다.
"""

import asyncio
import json
import logging
import threading
from typing import Dict, Optional, TYPE_CHECKING

from bot.models import WebhookResponse
from bot.dispatcher import get_dispatcher
from bot.platforms import ALL_PLATFORMS

if TYPE_CHECKING:
    from bot.platforms.base import BotPlatform  # noqa: F401

logger = logging.getLogger(__name__)

_platform_instances: Dict[str, 'BotPlatform'] = {}


def get_platform(platform_name: str) -> Optional['BotPlatform']:
    """
Daily Stock Analysis - Handler
"""
    if platform_name not in _platform_instances:
        platform_class = ALL_PLATFORMS.get(platform_name)
        if platform_class:
            _platform_instances[platform_name] = platform_class()
        else:
            logger.warning(f"[BotHandler] 알 수 없는 플랫폼: {platform_name}")
            return None

    return _platform_instances[platform_name]


def handle_webhook(
    platform_name: str,
    headers: Dict[str, str],
    body: bytes,
    query_params: Optional[Dict[str, list]] = None
) -> WebhookResponse:
    """
Daily Stock Analysis - Handler
"""
    logger.info(f"[BotHandler] 수신 {platform_name} Webhook 요청")

    # 봇 기능 활성화 여부 확인
    from src.config import get_config
    config = get_config()

    if not getattr(config, 'bot_enabled', True):
        logger.info("[BotHandler] 봇 기능 비활성화됨")
        return WebhookResponse.success()

    platform = get_platform(platform_name)
    if not platform:
        return WebhookResponse.error(f"Unknown platform: {platform_name}", 400)

    try:
        data = json.loads(body.decode('utf-8')) if body else {}
    except json.JSONDecodeError as e:
        logger.error(f"[BotHandler] JSON 파싱 실패: {e}")
        return WebhookResponse.error("Invalid JSON", 400)

    logger.debug(f"[BotHandler] 요청 데이터: {json.dumps(data, ensure_ascii=False)[:500]}")

    # Webhook 처리
    message, immediate_response = platform.handle_webhook(headers, body, data)

    if immediate_response and not message:
        logger.info("[BotHandler] 검증 응답 반환")
        return immediate_response

    if immediate_response and message:
        logger.info("[BotHandler] 지연 ACK 반환, 백그라운드 명령 처리")

        def _deferred_dispatch() -> None:
            try:
                dispatcher = get_dispatcher()
                response = dispatcher.dispatch(message)
                if response.text:
                    platform.send_followup(response, message)
            except Exception as exc:
                logger.error("[BotHandler] 지연 명령 처리 실패: %s", exc)

        threading.Thread(target=_deferred_dispatch, daemon=True).start()
        return immediate_response

    if not message:
        logger.debug("[BotHandler] 처리 불필요한 메시지")
        return WebhookResponse.success()

    logger.info(f"[BotHandler] 메시지 수신: user={message.user_name}, content={message.content[:50]}")

    # 명령 처리기에 분배
    dispatcher = get_dispatcher()
    response = dispatcher.dispatch(message)

    # 응답 포맷팅
    if response.text:
        webhook_response = platform.format_response(response, message)
        return webhook_response

    return WebhookResponse.success()


async def handle_webhook_async(
    platform_name: str,
    headers: Dict[str, str],
    body: bytes,
    query_params: Optional[Dict[str, list]] = None
) -> WebhookResponse:
    """Async version of :func:`handle_webhook`.

    Preferred when called from an async context (e.g. FastAPI endpoint)
    to avoid blocking the event loop.
    """
    logger.info(f"[BotHandler] 수신 {platform_name} Webhook 요청 (async)")

    from src.config import get_config
    config = get_config()

    if not getattr(config, 'bot_enabled', True):
        logger.info("[BotHandler] 봇 기능 비활성화됨")
        return WebhookResponse.success()

    platform = get_platform(platform_name)
    if not platform:
        return WebhookResponse.error(f"Unknown platform: {platform_name}", 400)

    try:
        data = json.loads(body.decode('utf-8')) if body else {}
    except json.JSONDecodeError as e:
        logger.error(f"[BotHandler] JSON 파싱 실패: {e}")
        return WebhookResponse.error("Invalid JSON", 400)

    logger.debug(f"[BotHandler] 요청 데이터: {json.dumps(data, ensure_ascii=False)[:500]}")

    message, immediate_response = platform.handle_webhook(headers, body, data)

    if immediate_response and not message:
        logger.info("[BotHandler] 검증 응답 반환")
        return immediate_response

    if immediate_response and message:
        logger.info("[BotHandler] 지연 ACK 반환, 백그라운드 명령 처리 (async)")

        async def _deferred_dispatch() -> None:
            try:
                dispatcher = get_dispatcher()
                response = await dispatcher.dispatch_async(message)
                if response.text:
                    await asyncio.to_thread(platform.send_followup, response, message)
            except Exception as exc:
                logger.error("[BotHandler] 지연 명령 처리 실패: %s", exc)

        asyncio.ensure_future(_deferred_dispatch())
        return immediate_response

    if not message:
        logger.debug("[BotHandler] 처리 불필요한 메시지")
        return WebhookResponse.success()

    logger.info(f"[BotHandler] 메시지 수신: user={message.user_name}, content={message.content[:50]}")

    dispatcher = get_dispatcher()
    response = await dispatcher.dispatch_async(message)

    if response.text:
        webhook_response = platform.format_response(response, message)
        return webhook_response

    return WebhookResponse.success()


def handle_feishu_webhook(headers: Dict[str, str], body: bytes) -> WebhookResponse:
    """Feishu 처리 Webhook"""
    return handle_webhook('feishu', headers, body)


def handle_dingtalk_webhook(headers: Dict[str, str], body: bytes) -> WebhookResponse:
    """DingTalk 처리 Webhook"""
    return handle_webhook('dingtalk', headers, body)


def handle_wecom_webhook(headers: Dict[str, str], body: bytes) -> WebhookResponse:
    """WeCom 처리 Webhook"""
    return handle_webhook('wecom', headers, body)


def handle_telegram_webhook(headers: Dict[str, str], body: bytes) -> WebhookResponse:
    """(pinyin removed) Telegram Webhook"""
    return handle_webhook('telegram', headers, body)
