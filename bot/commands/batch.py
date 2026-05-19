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

        return "pilianganalysiswatchlistgu"

    

    @property

    def usage(self) -> str:

        return "/batch [shuliang]"

    

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

                "watchlistguliebiaoweikong竊똰ingxianconfig STOCK_LIST"

            )

        

        # jiexishuliangcanshu

        limit = None

        if args:

            try:

                limit = int(args[0])

                if limit <= 0:

                    return BotResponse.error_response("shuliangbixudayu0")

            except ValueError:

                return BotResponse.error_response(f"wuxiaodeshuliang: {args[0]}")

        

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

            f"??**pilianganalysisrenwuyiqidong**\n\n"

            f"??analysisshuliang: {len(stock_list)} zhi\n"

            f"??stockliebiao: {', '.join(stock_list[:5])}"

            f"{'...' if len(stock_list) > 5 else ''}\n\n"

            f"analysiswanchenghoujiangzidongtuisonghuizongbaogao??"

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


