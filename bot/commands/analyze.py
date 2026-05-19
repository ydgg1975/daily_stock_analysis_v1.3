# -*- coding: utf-8 -*-

"""

===================================

stockanalysismingling

===================================



analysiszhidingstock竊똡iaoyong AI shengchenganalysisbaogao??
"""



import re

import logging

from typing import List, Optional



from bot.commands.base import BotCommand

from bot.models import BotMessage, BotResponse

from data_provider.base import canonical_stock_code



logger = logging.getLogger(__name__)





class AnalyzeCommand(BotCommand):

    """

    stockanalysismingling

    

    analysiszhidingstockdaima竊똲hengcheng AI analysisbaogaobingtuisong??
    

    yongfa竊?
        /analyze 600519       - analysisSamsung Electronics竊늞ingjianbaogao竊?
        /analyze 600519 full  - analysisbingshengchengwanzhengbaogao

    """

    

    @property

    def name(self) -> str:

        return "analyze"

    

    @property

    def aliases(self) -> List[str]:

        return ["a", "analysis", "cha"]

    

    @property

    def description(self) -> str:

        return "analysiszhidingstock"

    

    @property

    def usage(self) -> str:

        return "/analyze <stockdaima> [full]"

    

    def validate_args(self, args: List[str]) -> Optional[str]:

        """yanzhengcanshu"""

        if not args:

            return "inputrustockdaima"

        

        code = args[0].upper()



        # yanzhengstockdaimageshi

        # Agu竊?weishuzi

        # ganggu竊숰K+5weishuzi

        # meigu竊?-5gedaxiezimu+.+2gehouzhuizimu

        is_a_stock = re.match(r'^\d{6}$', code)

        is_hk_stock = re.match(r'^HK\d{5}$', code)

        is_us_stock = re.match(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$', code)



        if not (is_a_stock or is_hk_stock or is_us_stock):

            return f"Invalid stock code: {code}. Use KR005930, HK00700, AAPL, or CN600519 style codes."

        

        return None

    

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:

        """zhixinganalysismingling"""

        code = canonical_stock_code(args[0])

        

        # jianchashifouxuyaowanzhengbaogao竊늤orenjingjian竊똠huan full/wanzheng/xiangxi qiehuan竊?
        report_type = "simple"

        if len(args) > 1 and args[1].lower() in ["full", "wanzheng", "xiangxi"]:

            report_type = "full"

        logger.info(f"[AnalyzeCommand] analysisstock: {code}, baogaoleixing: {report_type}")

        

        try:

            # diaoyonganalysisfuwu

            from src.services.task_service import get_task_service

            from src.enums import ReportType

            

            service = get_task_service()

            

            # tijiaoyibuanalysisrenwu

            result = service.submit_analysis(

                code=code,

                report_type=ReportType.from_str(report_type),

                source_message=message

            )

            

            if result.get("success"):

                task_id = result.get("task_id", "")

                return BotResponse.markdown_response(

                    f"??**analysisrenwuyitijiao**\n\n"

                    f"??stockdaima: `{code}`\n"

                    f"??baogaoleixing: {ReportType.from_str(report_type).display_name}\n"

                    f"??renwu ID: `{task_id[:20]}...`\n\n"

                    f"analysiswanchenghoujiangzidongtuisongjieguo??"

                )

            else:

                error = result.get("error", "weizhicuowu")

                return BotResponse.error_response(f"tijiaoanalysisrenwushibai: {error}")

                

        except Exception as e:

            logger.error(f"[AnalyzeCommand] zhixingshibai: {e}")

            return BotResponse.error_response(f"analysisshibai: {str(e)[:100]}")


