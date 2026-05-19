# -*- coding: utf-8 -*-
"""
===================================
Bot Webhook chuliqi
===================================

chuligepingtaide Webhook huidiao，fenfadaominglingchuliqi。
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

# pingtaishilihuancun
_platform_instances: Dict[str, 'BotPlatform'] = {}


def get_platform(platform_name: str) -> Optional['BotPlatform']:
    """
    huoqupingtaishipeiqishili

    shiyonghuancunbimianchongfuchuangjian。

    Args:
        platform_name: pingtaimingcheng

    Returns:
        pingtaishipeiqishili，huo None
    """
    if platform_name not in _platform_instances:
        platform_class = ALL_PLATFORMS.get(platform_name)
        if platform_class:
            _platform_instances[platform_name] = platform_class()
        else:
            logger.warning(f"[BotHandler] weizhipingtai: {platform_name}")
            return None

    return _platform_instances[platform_name]


def handle_webhook(
    platform_name: str,
    headers: Dict[str, str],
    body: bytes,
    query_params: Optional[Dict[str, list]] = None
) -> WebhookResponse:
    """
    chuli Webhook qingqiu

    zheshisuoyoupingtai Webhook detongyirukou。

    Args:
        platform_name: pingtaimingcheng (feishu, dingtalk, wecom, telegram)
        headers: HTTP qingqiutou
        body: qingqiutiyuanshizijie
        query_params: URL chaxuncanshu（yongyumouxiepingtaideyanzheng）

    Returns:
        WebhookResponse xiangyingduixiang
    """
    logger.info(f"[BotHandler] shoudao {platform_name} Webhook qingqiu")

    # jianchajiqirengongnengshifouqiyong
    from src.config import get_config
    config = get_config()

    if not getattr(config, 'bot_enabled', True):
        logger.info("[BotHandler] jiqirengongnengweiqiyong")
        return WebhookResponse.success()

    # huoqupingtaishipeiqi
    platform = get_platform(platform_name)
    if not platform:
        return WebhookResponse.error(f"Unknown platform: {platform_name}", 400)

    # jiexi JSON shuju
    try:
        data = json.loads(body.decode('utf-8')) if body else {}
    except json.JSONDecodeError as e:
        logger.error(f"[BotHandler] JSON jiexishibai: {e}")
        return WebhookResponse.error("Invalid JSON", 400)

    logger.debug(f"[BotHandler] qingqiushuju: {json.dumps(data, ensure_ascii=False)[:500]}")

    # chuli Webhook
    message, immediate_response = platform.handle_webhook(headers, body, data)

    # ruguoshiyanzheng/cuowuxiangyingqiemeiyouxiaoxixuyaochuli，zhijiefanhui
    if immediate_response and not message:
        logger.info("[BotHandler] fanhuiyanzhengxiangying")
        return immediate_response

    # yanchixiangying（ru Discord type 5）：lijifanhui ACK，houtaichulimingling
    if immediate_response and message:
        logger.info("[BotHandler] fanhuiyanchi ACK，houtaichulimingling")

        def _deferred_dispatch() -> None:
            try:
                dispatcher = get_dispatcher()
                response = dispatcher.dispatch(message)
                if response.text:
                    platform.send_followup(response, message)
            except Exception as exc:
                logger.error("[BotHandler] yanchiminglingchulishibai: %s", exc)

        threading.Thread(target=_deferred_dispatch, daemon=True).start()
        return immediate_response

    # ruguomeiyouxiaoxixuyaochuli，fanhuikongxiangying
    if not message:
        logger.debug("[BotHandler] wuxuchulidexiaoxi")
        return WebhookResponse.success()

    logger.info(f"[BotHandler] jiexidaoxiaoxi: user={message.user_name}, content={message.content[:50]}")

    # fenfadaominglingchuliqi
    dispatcher = get_dispatcher()
    response = dispatcher.dispatch(message)

    # geshihuaxiangying
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
    logger.info(f"[BotHandler] shoudao {platform_name} Webhook qingqiu (async)")

    from src.config import get_config
    config = get_config()

    if not getattr(config, 'bot_enabled', True):
        logger.info("[BotHandler] jiqirengongnengweiqiyong")
        return WebhookResponse.success()

    platform = get_platform(platform_name)
    if not platform:
        return WebhookResponse.error(f"Unknown platform: {platform_name}", 400)

    try:
        data = json.loads(body.decode('utf-8')) if body else {}
    except json.JSONDecodeError as e:
        logger.error(f"[BotHandler] JSON jiexishibai: {e}")
        return WebhookResponse.error("Invalid JSON", 400)

    logger.debug(f"[BotHandler] qingqiushuju: {json.dumps(data, ensure_ascii=False)[:500]}")

    message, immediate_response = platform.handle_webhook(headers, body, data)

    if immediate_response and not message:
        logger.info("[BotHandler] fanhuiyanzhengxiangying")
        return immediate_response

    if immediate_response and message:
        logger.info("[BotHandler] fanhuiyanchi ACK，houtaichulimingling (async)")

        async def _deferred_dispatch() -> None:
            try:
                dispatcher = get_dispatcher()
                response = await dispatcher.dispatch_async(message)
                if response.text:
                    await asyncio.to_thread(platform.send_followup, response, message)
            except Exception as exc:
                logger.error("[BotHandler] yanchiminglingchulishibai: %s", exc)

        asyncio.ensure_future(_deferred_dispatch())
        return immediate_response

    if not message:
        logger.debug("[BotHandler] wuxuchulidexiaoxi")
        return WebhookResponse.success()

    logger.info(f"[BotHandler] jiexidaoxiaoxi: user={message.user_name}, content={message.content[:50]}")

    dispatcher = get_dispatcher()
    response = await dispatcher.dispatch_async(message)

    if response.text:
        webhook_response = platform.format_response(response, message)
        return webhook_response

    return WebhookResponse.success()


def handle_feishu_webhook(headers: Dict[str, str], body: bytes) -> WebhookResponse:
    """chulifeishu Webhook"""
    return handle_webhook('feishu', headers, body)


def handle_dingtalk_webhook(headers: Dict[str, str], body: bytes) -> WebhookResponse:
    """chulidingding Webhook"""
    return handle_webhook('dingtalk', headers, body)


def handle_wecom_webhook(headers: Dict[str, str], body: bytes) -> WebhookResponse:
    """chuliqiyeweixin Webhook"""
    return handle_webhook('wecom', headers, body)


def handle_telegram_webhook(headers: Dict[str, str], body: bytes) -> WebhookResponse:
    """chuli Telegram Webhook"""
    return handle_webhook('telegram', headers, body)
