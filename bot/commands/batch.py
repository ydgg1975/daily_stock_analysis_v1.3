# -*- coding: utf-8 -*-

"""

===================================

pilianganalysismingling

===================================



pilianganalysiswatchlistguliebiaozhongdesuoyoustock??
"""



import logging

import threading

import uuid

from typing import List



from bot.commands.base import BotCommand

from bot.models import BotMessage, BotResponse



logger = logging.getLogger(__name__)





class BatchCommand(BotCommand):

    """

    pilianganalysismingling

    

    pilianganalysisconfigzhongdewatchlistguliebiao竊똲hengchenghuizongbaogao??
    

    yongfa竊?
        /batch      - analysissuoyouwatchlistgu

        /batch 3    - zhianalysisqian3zhi

    """

    

    @property

    def name(self) -> str:

        return "batch"

    

    @property

    def aliases(self) -> List[str]:

        return ["b", "piliang", "quanbu"]

    

    @property

    def description(self) -> str:

        return "관심 종목을 일괄 분석합니다"

    

    @property

    def usage(self) -> str:

        return "/batch [수량]"

    

    @property

    def admin_only(self) -> bool:

        """Batch analysis requires admin permissions to prevent abuse."""

        return False  # keyigenjuxuyaoshewei True

    

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:

        """zhixingpilianganalysismingling"""

        from src.config import get_config

        

        config = get_config()

        config.refresh_stock_list()

        

        stock_list = config.stock_list

        

        if not stock_list:

            return BotResponse.error_response(

                "관심 종목 목록이 비어 있습니다. 먼저 STOCK_LIST를 설정하세요."

            )

        

        # jiexishuliangcanshu

        limit = None

        if args:

            try:

                limit = int(args[0])

                if limit <= 0:

                    return BotResponse.error_response("분석 수량은 0보다 커야 합니다.")

            except ValueError:

                return BotResponse.error_response(f"유효하지 않은 수량입니다: {args[0]}")

        

        # xianzhianalysisshuliang

        if limit:

            stock_list = stock_list[:limit]

        

        logger.info(f"[BatchCommand] kaishipilianganalysis {len(stock_list)} zhistock")

        

        # zaihoutaixianchengzhongzhixinganalysis

        thread = threading.Thread(

            target=self._run_batch_analysis,

            args=(stock_list, message),

            daemon=True

        )

        thread.start()

        

        return BotResponse.markdown_response(

            f"**일괄 분석 작업이 시작되었습니다**\n\n"

            f"분석 수량: {len(stock_list)}개\n"

            f"종목 목록: {', '.join(stock_list[:5])}"

            f"{'...' if len(stock_list) > 5 else ''}\n\n"

            f"분석이 완료되면 요약 보고서를 자동으로 보냅니다."

        )

    

    def _run_batch_analysis(self, stock_list: List[str], message: BotMessage) -> None:

        """houtaizhixingpilianganalysis"""

        try:

            from src.config import get_config

            from main import StockAnalysisPipeline

            

            config = get_config()

            

            # chuangjiananalysisguandao

            pipeline = StockAnalysisPipeline(

                config=config,

                source_message=message,

                query_id=uuid.uuid4().hex,

                query_source="bot"

            )

            

            # zhixinganalysis竊늜uizidongtuisonghuizongbaogao竊?
            results = pipeline.run(

                stock_codes=stock_list,

                dry_run=False,

                send_notification=True

            )

            

            logger.info(f"[BatchCommand] pilianganalysiswancheng竊똠henggong {len(results)} zhi")

            

        except Exception as e:

            logger.error(f"[BatchCommand] pilianganalysisshibai: {e}")

            logger.exception(e)


