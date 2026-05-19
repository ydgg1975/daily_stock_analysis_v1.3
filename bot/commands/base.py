# -*- coding: utf-8 -*-

"""

===================================

minglingjilei

===================================



dingyiminglingchuliqidechouxiangjilei竊똲uoyouminglingdoubixujichengcilei??
"""



import asyncio

from abc import ABC, abstractmethod

from typing import List, Optional



from bot.models import BotMessage, BotResponse





class BotCommand(ABC):

    """

    minglingchuliqichouxiangjilei



    suoyouminglingdoubixujichengcileibingshixianchouxiangfangfa??


    shiyongshili竊?
        class MyCommand(BotCommand):

            @property

            def name(self) -> str:

                return "mycommand"



            @property

            def aliases(self) -> List[str]:

                return ["mc", "wodemingling"]



            @property

            def description(self) -> str:

                return "zheshiwodemingling"



            @property

            def usage(self) -> str:

                return "/mycommand [canshu]"



            def execute(self, message: BotMessage, args: List[str]) -> BotResponse:

                return BotResponse.text_response("minglingzhixingchenggong")

    """



    @property

    @abstractmethod

    def name(self) -> str:

        """

        minglingmingcheng竊늒uhanqianzhui竊?


        liru "analyze"竊똹onghushuru "/analyze" chufa

        """

        pass



    @property

    @abstractmethod

    def aliases(self) -> List[str]:

        """

        minglingbiemingliebiao



        liru ["a", "analysis"]竊똹onghushuru "/a" huo "analysis" yenengchufa

        """

        pass



    @property

    @abstractmethod

    def description(self) -> str:

        """Command description for help text."""
        pass



    @property

    @abstractmethod

    def usage(self) -> str:

        """

        shiyongshuoming竊늶ongyubangzhuxinxi竊?


        liru "/analyze <stockdaima>"

        """

        pass



    @property

    def hidden(self) -> bool:

        """

        shifouzaibangzhuliebiaozhongyincang



        moren False竊똲hewei True zebuxianshizai /help liebiaozhong

        """

        return False



    @property

    def admin_only(self) -> bool:

        """

        shifoujinguanliyuankeyong



        moren False竊똲hewei True zexuyaoguanliyuanquanxian

        """

        return False



    @abstractmethod

    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:

        """

        zhixingmingling



        Args:

            message: yuanshixiaoxiduixiang

            args: minglingcanshuliebiao竊늶ifenge竊?


        Returns:

            BotResponse xiangyingduixiang

        """

        pass



    async def execute_async(self, message: BotMessage, args: List[str]) -> BotResponse:

        """Execute the command asynchronously in a worker thread."""

        return await asyncio.to_thread(self.execute, message, args)



    def validate_args(self, args: List[str]) -> Optional[str]:

        """

        yanzhengcanshu



        zileikezhongxiecifangfajinxingcanshujiaoyan??


        Args:

            args: minglingcanshuliebiao



        Returns:

            ruguocanshuyouxiaofanhui None竊똣ouzefanhuicuowuxinxi

        """

        return None



    def get_help_text(self) -> str:

        """huoqubangzhuwenben"""

        return f"**{self.name}** - {self.description}\nyongfa: `{self.usage}`"


