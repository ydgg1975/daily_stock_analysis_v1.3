# -*- coding: utf-8 -*-

"""

===================================

jiqirenxiaoximodel

===================================



dingyitongyidexiaoxihexiangyingmodel竊똯ingbigepingtaichayi??
"""



from dataclasses import dataclass, field

from datetime import datetime

from enum import Enum

from typing import Dict, Any, Optional, List





class ChatType(str, Enum):

    """huihualeixing"""

    GROUP = "group"      # qunliao

    PRIVATE = "private"  # siliao

    UNKNOWN = "unknown"  # weizhi





class Platform(str, Enum):

    """pingtaileixing"""

    FEISHU = "feishu"        # feishu

    DINGTALK = "dingtalk"    # dingding

    WECOM = "wecom"          # qiyeweixin

    TELEGRAM = "telegram"    # Telegram

    UNKNOWN = "unknown"      # weizhi





@dataclass

class BotMessage:

    """

    tongyidejiqirenxiaoximodel

    

    jianggepingtaidexiaoxigeshitongyiweicimodel竊똟ianyuminglingchuliqichuli??
    

    Attributes:

        platform: pingtaibiaoshi

        message_id: xiaoxi ID竊늩ingtaiyuanshi ID竊?
        user_id: sendzhe ID

        user_name: sendzhemingcheng

        chat_id: huihua ID竊늫unliao ID huosiliao ID竊?
        chat_type: huihualeixing

        content: xiaoxiwenbenneirong竊늶iquchu @jiqiren bufen竊?
        raw_content: yuanshixiaoxineirong

        mentioned: shifou @lejiqiren

        mentions: @deyonghuliebiao

        timestamp: xiaoxishijianchuo

        raw_data: yuanshiqingqiushuju竊늩ingtaiteding竊똹ongyutiaoshi竊?
    """

    platform: str

    message_id: str

    user_id: str

    user_name: str

    chat_id: str

    chat_type: ChatType

    content: str

    raw_content: str = ""

    mentioned: bool = False

    mentions: List[str] = field(default_factory=list)

    timestamp: datetime = field(default_factory=datetime.now)

    raw_data: Dict[str, Any] = field(default_factory=dict)

    

    def get_command_and_args(self, prefix: str = "/") -> tuple:

        """

        jieximinglinghecanshu

        

        Args:

            prefix: minglingqianzhui竊똫oren "/"

            

        Returns:

            (command, args) yuanzu竊똱u ("analyze", ["600519"])

            ruguobushimingling竊똣anhui (None, [])

        """

        text = self.content.strip()

        

        # jianchashifouyiminglingqianzhuikaitou

        if not text.startswith(prefix):

            # changshipipeizhongwenmingling竊늳uqianzhui竊?
            chinese_commands = {

                'analysis': 'analyze',

                'dapan': 'market',

                'piliang': 'batch',

                'bangzhu': 'help',

                'zhuangtai': 'status',

            }

            for cn_cmd, en_cmd in chinese_commands.items():

                if text.startswith(cn_cmd):

                    args = text[len(cn_cmd):].strip().split()

                    return en_cmd, args

            return None, []

        

        # quchuqianzhui

        text = text[len(prefix):]

        

        # fengeminglinghecanshu

        parts = text.split()

        if not parts:

            return None, []

        

        command = parts[0].lower()

        args = parts[1:] if len(parts) > 1 else []

        

        return command, args

    

    def is_command(self, prefix: str = "/") -> bool:

        """jianchaxiaoxishifoushimingling"""

        cmd, _ = self.get_command_and_args(prefix)

        return cmd is not None





@dataclass

class BotResponse:

    """

    tongyidejiqirenxiangyingmodel

    

    minglingchuliqifanhuicimodel竊똹oupingtaishipeiqizhuanhuanweipingtaitedinggeshi??
    

    Attributes:

        text: huifuwenben

        markdown: shifouwei Markdown geshi

        at_user: shifou @sendzhe

        reply_to_message: shifouhuifuyuanxiaoxi

        extra: ewaishuju竊늩ingtaiteding竊?
    """

    text: str

    markdown: bool = False

    at_user: bool = True

    reply_to_message: bool = True

    extra: Dict[str, Any] = field(default_factory=dict)

    

    @classmethod

    def text_response(cls, text: str, at_user: bool = True) -> 'BotResponse':

        """chuangjianchunwenbenxiangying"""

        return cls(text=text, markdown=False, at_user=at_user)

    

    @classmethod

    def markdown_response(cls, text: str, at_user: bool = True) -> 'BotResponse':

        """chuangjian Markdown xiangying"""

        return cls(text=text, markdown=True, at_user=at_user)

    

    @classmethod

    def error_response(cls, message: str) -> 'BotResponse':

        """chuangjiancuowuxiangying"""

        return cls(text=f"Error: {message}", markdown=False, at_user=True)




@dataclass

class WebhookResponse:

    """

    Webhook xiangyingmodel

    

    pingtaishipeiqifanhuicimodel竊똟aohan HTTP xiangyingneirong??
    

    Attributes:

        status_code: HTTP zhuangtaima

        body: xiangyingti竊늷idian竊똨iangbei JSON xuliehua竊?
        headers: ewaidexiangyingtou

    """

    status_code: int = 200

    body: Dict[str, Any] = field(default_factory=dict)

    headers: Dict[str, str] = field(default_factory=dict)

    

    @classmethod

    def success(cls, body: Optional[Dict] = None) -> 'WebhookResponse':

        """chuangjianchenggongxiangying"""

        return cls(status_code=200, body=body or {})

    

    @classmethod

    def challenge(cls, challenge: str) -> 'WebhookResponse':

        """Create a challenge response for platform URL verification."""

        return cls(status_code=200, body={"challenge": challenge})

    

    @classmethod

    def error(cls, message: str, status_code: int = 400) -> 'WebhookResponse':

        """chuangjiancuowuxiangying"""

        return cls(status_code=status_code, body={"error": message})


