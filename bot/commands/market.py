# -*- coding: utf-8 -*-
"""
Market review bot command.
"""

import logging
import threading
from typing import Any, List, Optional

from bot.commands.base import BotCommand
from bot.models import BotMessage, BotResponse

logger = logging.getLogger(__name__)


class MarketCommand(BotCommand):
    """Run a market review in the background."""

    @property
    def name(self) -> str:
        return "market"

    @property
    def aliases(self) -> List[str]:
        return ["m", "시장", "리뷰", "시황"]

    @property
    def description(self) -> str:
        return "시장 리뷰를 실행합니다"

    @property
    def usage(self) -> str:
        return "/market"

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """Execute the market review command."""
        config = self._get_config()
        lock_token = self._try_acquire_market_review_lock(config)
        if lock_token is None:
            return BotResponse.markdown_response("⚠️ 시장 리뷰가 이미 실행 중입니다. 잠시 후 다시 시도하세요.")

        thread = threading.Thread(
            target=self._run_market_review,
            args=(message, config, lock_token),
            daemon=True,
        )
        try:
            thread.start()
        except Exception as exc:
            logger.error("[MarketCommand] 시장 리뷰 백그라운드 스레드 시작 실패: %s", exc)
            self._release_market_review_lock(lock_token)
            return BotResponse.error_response(
                "시장 리뷰 시작에 실패했습니다. 실행 잠금을 해제했으니 잠시 후 다시 시도하세요."
            )

        return BotResponse.markdown_response(
            "✅ **시장 리뷰 작업을 시작했습니다**\n\n"
            "분석 항목:\n"
            "• 주요 지수 흐름\n"
            "• 섹터/테마 동향\n"
            "• 시장 심리 판단\n"
            "• 향후 전망\n\n"
            "분석이 완료되면 결과를 자동으로 전송합니다."
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
                compute_effective_region,
                get_open_markets_today,
            )

            open_markets = get_open_markets_today()
            return compute_effective_region(
                getattr(config, "market_review_region", "cn") or "cn",
                open_markets,
            )
        except Exception as exc:
            logger.warning("거래일 필터링에 실패해 기본 설정대로 시장 리뷰를 계속 실행합니다: %s", exc)
            return None

    def _run_market_review(
        self,
        message: BotMessage,
        config,
        lock_token: Optional[Any],
    ) -> None:
        """Run market review in the background."""
        try:
            override_region = self._compute_market_review_override_region(config)
            if override_region == "":
                from src.notification import NotificationService

                notifier = NotificationService(source_message=message)
                logger.info("[MarketCommand] 오늘 관련 시장이 휴장이라 시장 리뷰를 건너뜁니다")
                if notifier.is_available():
                    notifier.send(
                        "📊 시장 리뷰\n\n오늘 관련 시장이 휴장이라 시장 리뷰를 건너뛰었습니다.",
                        email_send_to_all=True,
                        route_type="report",
                    )
                return

            from src.core.market_review import run_market_review
            from src.core.market_review_runtime import build_market_review_runtime

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
                logger.info("[MarketCommand] 시장 리뷰 완료 및 전송 완료")
            else:
                logger.warning("[MarketCommand] 시장 리뷰가 빈 결과를 반환했습니다")
        except Exception as e:
            logger.error("[MarketCommand] 시장 리뷰 실패: %s", e)
            logger.exception(e)
        finally:
            self._release_market_review_lock(lock_token)
