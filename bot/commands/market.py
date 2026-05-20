# -*- coding: utf-8 -*-
"""
===================================
시장 리뷰 명령
===================================

시장 리뷰 분석을 실행하고 시장 개요 보고서를 생성합니다.
"""

import logging
import threading
from typing import Any, List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse

logger = logging.getLogger(__name__)


class MarketCommand(BotCommand):
    """
    시장 리뷰 명령

    시장 리뷰 분석을 실행합니다:
    - 主要指数表现
    - 板块热点
    - 市场情绪
    - 后市展望

    用法：
        /market - 시장 리뷰 실행
    """

    @property
    def name(self) -> str:
        return "market"

    @property
    def aliases(self) -> List[str]:
        return ["m", "大盘", "复盘", "行情"]

    @property
    def description(self) -> str:
        return "시장 리뷰 분석"

    @property
    def usage(self) -> str:
        return "/market"

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """시장 리뷰 명령을 실행합니다."""
        config = self._get_config()
        lock_token = self._try_acquire_market_review_lock(config)
        if lock_token is None:
            return BotResponse.markdown_response("⚠️ 시장 리뷰가 실행 중입니다. 잠시 후 다시 시도하세요.")

        thread = threading.Thread(
            target=self._run_market_review,
            args=(message, config, lock_token),
            daemon=True,
        )
        try:
            thread.start()
        except Exception as exc:
            logger.error(
                "[MarketCommand] 시장 리뷰 백그라운드 스레드 시작 실패: %s",
                exc,
            )
            self._release_market_review_lock(lock_token)
            return BotResponse.error_response(
                "시장 리뷰 시작에 실패했습니다. 실행 잠금을 해제했으니 잠시 후 다시 시도하세요."
            )

        return BotResponse.markdown_response(
            "✅ **시장 리뷰 작업이 시작되었습니다**\n\n"
            "正在分析：\n"
            "• 主要指数表现\n"
            "• 板块热点分析\n"
            "• 市场情绪判断\n"
            "• 后市展望\n\n"
            "分析完成后将自动推送结果。"
        )

    def _get_config(self):
        from src.config import get_config
        return get_config()

    def _try_acquire_market_review_lock(self, config):
        from src.core.market_review_lock import try_acquire_market_review_lock
        return try_acquire_market_review_lock(config)

    def _release_market_review_lock(self, lock_token: Optional[Any]) -> None:
        from src.core.market_review_lock import release_market_review_lock
        release_market_review_lock(lock_token)

    def _compute_market_review_override_region(self, config) -> Optional[str]:
        if not getattr(config, "trading_day_check_enabled", True):
            return None

        try:
            from src.core.trading_calendar import (
                get_open_markets_today,
                compute_effective_region,
            )

            open_markets = get_open_markets_today()
            return compute_effective_region(
                getattr(config, "market_review_region", "cn") or "cn",
                open_markets,
            )
        except Exception as exc:
            logger.warning("거래일 필터링에 실패해 설정대로 시장 리뷰를 계속 실행합니다: %s", exc)
            return None

    def _run_market_review(
        self,
        message: BotMessage,
        config,
        lock_token: Optional[Any],
    ) -> None:
        """백그라운드에서 시장 리뷰를 실행합니다."""
        try:
            override_region = self._compute_market_review_override_region(config)
            if override_region == "":
                from src.notification import NotificationService
                notifier = NotificationService(source_message=message)
                logger.info("[MarketCommand] 오늘 관련 시장이 휴장이라 시장 리뷰를 건너뜁니다.")
                if notifier.is_available():
                    notifier.send(
                        "🎯 시장 리뷰\n\n오늘 관련 시장이 휴장이라 시장 리뷰를 건너뛰었습니다.",
                        email_send_to_all=True,
                        route_type="report",
                    )
                return

            from src.core.market_review_runtime import build_market_review_runtime
            from src.core.market_review import run_market_review

            notifier, analyzer, search_service = build_market_review_runtime(
                config,
                source_message=message,
            )
            review_report = run_market_review(
                notifier=notifier,
                analyzer=analyzer,
                search_service=search_service,
                send_notification=True,
                override_region=override_region,
            )
            if review_report:
                logger.info("[MarketCommand] 시장 리뷰 완료 및 전송됨")
            else:
                logger.warning("[MarketCommand] 시장 리뷰가 빈 결과를 반환했습니다.")
        except Exception as e:
            logger.error("[MarketCommand] 시장 리뷰 실패: %s", e)
            logger.exception(e)
        finally:
            self._release_market_review_lock(lock_token)
