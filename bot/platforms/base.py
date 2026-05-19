# -*- coding: utf-8 -*-
"""
===================================
pingtaishipeiqijilei
===================================

dingyipingtaishipeiqidechouxiangjilei竊똤epingtaibixujichengcilei??
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple

from bot.models import BotMessage, BotResponse, WebhookResponse


class BotPlatform(ABC):
    """
    pingtaishipeiqichouxiangjilei
    
    fuze竊?
    1. yanzheng Webhook qingqiuqianming
    2. jiexipingtaixiaoxiweitongyigeshi
    3. jiangxiangyingzhuanhuanweipingtaigeshi
    
    shiyongshili竊?
        class MyPlatform(BotPlatform):
            @property
            def platform_name(self) -> str:
                return "myplatform"
            
            def verify_request(self, headers, body) -> bool:
                # yanzhengqianmingluoji
                return True
            
            def parse_message(self, data) -> Optional[BotMessage]:
                # jiexixiaoxiluoji
                return BotMessage(...)
            
            def format_response(self, response, message) -> WebhookResponse:
                # geshihuaxiangyingluoji
                return WebhookResponse.success({"text": response.text})
    """
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """
        pingtaibiaoshimingcheng
        
        yongyuluyoupipeiherizhibiaoshi竊똱u "feishu", "dingtalk"
        """
        pass
    
    @abstractmethod
    def verify_request(self, headers: Dict[str, str], body: bytes) -> bool:
        """
        yanzhengqingqiuqianming
        
        gepingtaiyoubutongdeqianmingyanzhengjizhi竊똸uyaodandushixian??
        
        Args:
            headers: HTTP qingqiutou
            body: qingqiutiyuanshizijie
            
        Returns:
            qianmingshifouyouxiao
        """
        pass
    
    @abstractmethod
    def parse_message(self, data: Dict[str, Any]) -> Optional[BotMessage]:
        """
        jiexipingtaixiaoxiweitongyigeshi
        
        jiangpingtaitedingdexiaoxigeshizhuanhuanwei BotMessage??
        ruguobushixuyaochulidexiaoxileixing竊늭ushijianhuidiao竊됵펽fanhui None??
        
        Args:
            data: jiexihoude JSON shuju
            
        Returns:
            BotMessage duixiang竊똦uo None竊늒uxuyaochuli竊?
        """
        pass
    
    @abstractmethod
    def format_response(
        self, 
        response: BotResponse, 
        message: BotMessage
    ) -> WebhookResponse:
        """
        jiangtongyixiangyingzhuanhuanweipingtaigeshi
        
        Args:
            response: tongyixiangyingduixiang
            message: yuanshixiaoxiduixiang竊늶ongyuhuoquhuifumubiaodengxinxi竊?
            
        Returns:
            WebhookResponse duixiang
        """
        pass
    
    def send_followup(
        self,
        response: 'BotResponse',
        message: 'BotMessage',
    ) -> bool:
        """Send a follow-up message after a deferred webhook response.

        Override in platforms that return a deferred acknowledgement
        (e.g. Discord type 5) so the final command result can be delivered
        asynchronously.  The default implementation is a no-op.

        Returns:
            ``True`` if the follow-up was sent successfully.
        """
        return False

    def handle_challenge(self, data: Dict[str, Any]) -> Optional[WebhookResponse]:
        """
        chulipingtaiyanzhengqingqiu
        
        bufenpingtaizaiconfig Webhook shihuisendyanzhengqingqiu竊똸uyaofanhuitedingxiangying??
        zileikezhongxiecifangfa??
        
        Args:
            data: qingqiushuju
            
        Returns:
            yanzhengxiangying竊똦uo None竊늒ushiyanzhengqingqiu竊?
        """
        return None
    
    def handle_webhook(
        self, 
        headers: Dict[str, str], 
        body: bytes,
        data: Dict[str, Any]
    ) -> Tuple[Optional[BotMessage], Optional[WebhookResponse]]:
        """
        chuli Webhook qingqiu
        
        zheshizhurukoufangfa竊똸ietiaoyanzheng?걂iexidengliucheng??
        
        Args:
            headers: HTTP qingqiutou
            body: qingqiutiyuanshizijie
            data: jiexihoude JSON shuju
            
        Returns:
            (BotMessage, WebhookResponse) yuanzu
            - ruguoshiyanzhengqingqiu竊?None, challenge_response)
            - ruguoshiputongxiaoxi竊?message, None) - xiangyingjiangzaiminglingchulihoushengcheng
            - ruguoyanzhengshibaihuowuxuchuli竊?None, error_response huo None)
        """
        # 1. jianchashifoushiyanzhengqingqiu
        challenge_response = self.handle_challenge(data)
        if challenge_response:
            return None, challenge_response
        
        # 2. yanzhengqingqiuqianming
        if not self.verify_request(headers, body):
            return None, WebhookResponse.error("Invalid signature", 403)
        
        # 3. jiexixiaoxi
        message = self.parse_message(data)
        
        return message, None

