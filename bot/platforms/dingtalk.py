# -*- coding: utf-8 -*-
"""
===================================
dingdingpingtaishipeiqi
===================================

chulidingdingjiqirende Webhook huidiao??

dingdingjiqirenwendang：
https://open.dingtalk.com/document/robots/robot-overview
"""

import hashlib
import hmac
import base64
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import quote_plus

from bot.platforms.base import BotPlatform
from bot.models import BotMessage, BotResponse, WebhookResponse, ChatType

logger = logging.getLogger(__name__)


class DingtalkPlatform(BotPlatform):
    """
Daily Stock Analysis - Dingtalk
"""
    
    def __init__(self):
        from src.config import get_config
        config = get_config()
        
        self._app_key = getattr(config, 'dingtalk_app_key', None)
        self._app_secret = getattr(config, 'dingtalk_app_secret', None)
    
    @property
    def platform_name(self) -> str:
        return "dingtalk"
    
    def verify_request(self, headers: Dict[str, str], body: bytes) -> bool:
        """
Daily Stock Analysis - Dingtalk
"""
        if not self._app_secret:
            logger.warning("[DingTalk] weiconfig app_secret竊똳iaoguoqianmingyanzheng")
            return True
        
        timestamp = headers.get('timestamp', '')
        sign = headers.get('sign', '')
        
        if not timestamp or not sign:
            logger.warning("[DingTalk] queshaoqianmingcanshu")
            return True  # kenengshibuxuyaoqianmingdeqingqiu
        
        # yanzhengshijianchuo：xiaoshineiyouxiao：
        try:
            request_time = int(timestamp)
            current_time = int(time.time() * 1000)
            if abs(current_time - request_time) > 3600 * 1000:
                logger.warning("[DingTalk] shijianchuoguoqi")
                return False
        except ValueError:
            logger.warning("[DingTalk] wuxiaodeshijianchuo")
            return False
        
        # jisuanqianming
        string_to_sign = f"{timestamp}\n{self._app_secret}"
        hmac_code = hmac.new(
            self._app_secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        expected_sign = base64.b64encode(hmac_code).decode('utf-8')
        
        if sign != expected_sign:
            logger.warning(f"[DingTalk] qianmingyanzhengshibai")
            return False
        
        return True
    
    def handle_challenge(self, data: Dict[str, Any]) -> Optional[WebhookResponse]:
        """dingdingbuxuyao URL yanzheng"""
        return None
    
    def parse_message(self, data: Dict[str, Any]) -> Optional[BotMessage]:
        """
        jiexidingdingxiaoxi
        
        dingding Outgoing jiqirenxiaoxigeshi：
        {
            "msgtype": "text",
            "text": {
                "content": "@jiqiren /analyze 600519"
            },
            "msgId": "xxx",
            "createAt": "1234567890",
            "conversationType": "2",  # 1=danliao, 2=qunliao
            "conversationId": "xxx",
            "conversationTitle": "qunming",
            "senderId": "xxx",
            "senderNick": "yonghunicheng",
            "senderCorpId": "xxx",
            "senderStaffId": "xxx",
            "chatbotUserId": "xxx",
            "atUsers": [{"dingtalkId": "xxx", "staffId": "xxx"}],
            "isAdmin": false,
            "sessionWebhook": "https://oapi.dingtalk.com/robot/sendBySession?session=xxx",
            "sessionWebhookExpiredTime": 1234567890
        }
        """
        # jianchaxiaoxileixing
        msg_type = data.get('msgtype', '')
        if msg_type != 'text':
            logger.debug(f"[DingTalk] hulvefeiwenbenxiaoxi: {msg_type}")
            return None
        
        text_content = data.get('text', {})
        raw_content = text_content.get('content', '')
        
        content = self._extract_command(raw_content)
        
        # jianchashifou @lejiqiren
        at_users = data.get('atUsers', [])
        mentioned = len(at_users) > 0
        
        # huihualeixing
        conversation_type = data.get('conversationType', '')
        if conversation_type == '1':
            chat_type = ChatType.PRIVATE
        elif conversation_type == '2':
            chat_type = ChatType.GROUP
        else:
            chat_type = ChatType.UNKNOWN
        
        # chuangjianshijian
        create_at = data.get('createAt', '')
        try:
            timestamp = datetime.fromtimestamp(int(create_at) / 1000)
        except (ValueError, TypeError):
            timestamp = datetime.now()
        
        # save session webhook yongyuhuifu
        session_webhook = data.get('sessionWebhook', '')
        
        return BotMessage(
            platform=self.platform_name,
            message_id=data.get('msgId', ''),
            user_id=data.get('senderId', ''),
            user_name=data.get('senderNick', ''),
            chat_id=data.get('conversationId', ''),
            chat_type=chat_type,
            content=content,
            raw_content=raw_content,
            mentioned=mentioned,
            mentions=[u.get('dingtalkId', '') for u in at_users],
            timestamp=timestamp,
            raw_data={
                **data,
                '_session_webhook': session_webhook,
            },
        )
    
    def _extract_command(self, text: str) -> str:
        """
Daily Stock Analysis - Dingtalk
"""
        import re
        text = re.sub(r'^@[\S]+\s*', '', text.strip())
        return text.strip()
    
    def format_response(
        self, 
        response: BotResponse, 
        message: BotMessage
    ) -> WebhookResponse:
        """
Daily Stock Analysis - Dingtalk
"""
        if not response.text:
            return WebhookResponse.success()
        
        # goujianxiangying
        if response.markdown:
            body = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "stockanalysiszhushou",
                    "text": response.text,
                }
            }
        else:
            body = {
                "msgtype": "text",
                "text": {
                    "content": response.text,
                }
            }
        
        # @sendzhe
        if response.at_user and message.user_id:
            body["at"] = {
                "atUserIds": [message.user_id],
                "isAtAll": False,
            }
        
        return WebhookResponse.success(body)
    
    def send_by_session_webhook(
        self, 
        session_webhook: str, 
        response: BotResponse,
        message: BotMessage
    ) -> bool:
        """
Daily Stock Analysis - Dingtalk
"""
        if not session_webhook:
            logger.warning("[DingTalk] meiyoukeyongde sessionWebhook")
            return False
        
        import requests
        
        try:
            # goujianxiaoxi
            if response.markdown:
                payload = {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": "stockanalysiszhushou",
                        "text": response.text,
                    }
                }
            else:
                payload = {
                    "msgtype": "text",
                    "text": {
                        "content": response.text,
                    }
                }
            
            # @sendzhe
            if response.at_user and message.user_id:
                payload["at"] = {
                    "atUserIds": [message.user_id],
                    "isAtAll": False,
                }
            
            # sendqingqiu
            resp = requests.post(
                session_webhook,
                json=payload,
                timeout=10
            )
            
            if resp.status_code == 200:
                result = resp.json()
                if result.get('errcode') == 0:
                    logger.info("[DingTalk] sessionWebhook sendchenggong")
                    return True
                else:
                    logger.error(f"[DingTalk] sessionWebhook sendshibai: {result}")
                    return False
            else:
                logger.error(f"[DingTalk] sessionWebhook request_failed: {resp.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"[DingTalk] sessionWebhook sendyichang: {e}")
            return False

