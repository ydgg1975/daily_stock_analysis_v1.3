# -*- coding: utf-8 -*-
"""
===================================
jiqirenminglingchufaxitong
===================================

tongguo @jiqiren huosendminglingchufastockanalysisdenggongneng??
zhichifeishu?갺ingding?걉iyeweixin?갩elegram dengduopingtai??

mokuaijiegou竊?
- models.py: tongyidexiaoxi/xiangyingmodel
- dispatcher.py: minglingfenfaqi
- commands/: minglingchuliqi
- platforms/: pingtaishipeiqi
- handler.py: Webhook chuliqi

shiyongfangshi竊?
1. confighuanjingbianliang竊늛epingtaide Token deng竊?
2. qidong WebUI fuwu
3. zaigepingtaiconfig Webhook URL竊?
   - feishu: http://your-server/bot/feishu
   - dingding: http://your-server/bot/dingtalk
   - qiyeweixin: http://your-server/bot/wecom
   - Telegram: http://your-server/bot/telegram

zhichidemingling竊?
- /analyze <stockdaima>  - analysiszhidingstock
- /market             - dapanfupan
- /batch              - pilianganalysiswatchlistgu
- /help               - xianshibangzhu
- /status             - xitongzhuangtai
"""

from bot.models import BotMessage, BotResponse, ChatType, WebhookResponse
from bot.dispatcher import CommandDispatcher, get_dispatcher

__all__ = [
    'BotMessage',
    'BotResponse',
    'ChatType',
    'WebhookResponse',
    'CommandDispatcher',
    'get_dispatcher',
]

