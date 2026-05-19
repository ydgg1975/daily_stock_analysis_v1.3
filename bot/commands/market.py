# -*- coding: utf-8 -*-

"""

===================================

dapanfupanmingling

===================================



zhixingdapanfupananalysis竊똲hengchengmarketgailanbaogao??
"""



import logging

import threading

from typing import Any, List, Optional



from bot.commands.base import BotCommand

from bot.models import BotMessage, BotResponse



logger = logging.getLogger(__name__)





class MarketCommand(BotCommand):

    """

    dapanfupanmingling



    zhixingdapanfupananalysis竊똟aokuo竊?
    - zhuyaozhishubiaoxian

    - bankuairedian

    - shicquotexu

    - houshizhanwang



    yongfa竊?
        /market - zhixingdapanfupan

    """



    @property

    def name(self) -> str:

        return "market"



    @property

    def aliases(self) -> List[str]:

        return ["m", "dapan", "fupan", "quote"]



    @property

    def description(self) -> str:

        return "시장 리뷰를 실행합니다"



    @property

    def usage(self) -> str:

        return "/market"



    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:

        """zhixingdapanfupanmingling"""

        config = self._get_config()

        lock_token = self._try_acquire_market_review_lock(config)

        if lock_token is None:

            return BotResponse.markdown_response("Market review is already running. Please try again later.")



        thread = threading.Thread(

            target=self._run_market_review,

            args=(message, config, lock_token),

            daemon=True,

        )

        try:

            thread.start()

        except Exception as exc:

            logger.error(

                "[MarketCommand] dapanfupanhoutaixianchengqidongshibai: %s",

                exc,

            )

            self._release_market_review_lock(lock_token)

            return BotResponse.error_response(

                "시장 리뷰 시작에 실패했습니다. 실행 잠금을 해제했으니 잠시 후 다시 시도하세요."

            )



        return BotResponse.markdown_response(

            "**시장 리뷰 작업이 시작되었습니다**\n\n"

            "분석을 진행 중입니다.\n"

            "- 주요 지수 흐름\n"

            "- 업종/테마 동향\n"

            "- 시세 흐름 판단\n"

            "- 향후 전망\n\n"

            "분석이 완료되면 결과를 자동으로 보냅니다."

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

            logger.warning("jiaoyiriguolvshibai竊똞nconfigjixuzhixingdapanfupan: %s", exc)

            return None



    def _run_market_review(

        self,

        message: BotMessage,

        config,

        lock_token: Optional[Any],

    ) -> None:

        """houtaizhixingdapanfupan"""

        try:

            override_region = self._compute_market_review_override_region(config)

            if override_region == "":

                from src.notification import NotificationService

                notifier = NotificationService(source_message=message)

                logger.info("[MarketCommand] jinrirelatedmarketxiushi竊똳iaoguodapanfupan")

                if notifier.is_available():

                    notifier.send(

                        "시장 리뷰\n\n오늘 시장 리뷰 대상 시장이 모두 휴장일이라 시장 리뷰를 건너뜁니다.",

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

                logger.info("[MarketCommand] dapanfupanwanchengbingyituisong")

            else:

                logger.warning("[MarketCommand] dapanfupanfanhuikongjieguo")

        except Exception as e:

            logger.error("[MarketCommand] dapanfupanshibai: %s", e)

            logger.exception(e)

        finally:

            self._release_market_review_lock(lock_token)


