# -*- coding: utf-8 -*-
"""
===================================
봇 명령 트리거 시스템
===================================

멘션 또는 명령어 입력으로 주식 분석 기능을 실행합니다.
Feishu, DingTalk, WeCom, Telegram 등 여러 플랫폼을 지원합니다.

모듈 구조:
- models.py: 공통 메시지/응답 모델
- dispatcher.py: 명령 디스패처
- commands/: 명령 핸들러
- platforms/: 플랫폼 어댑터
- handler.py: Webhook 핸들러

사용 방법:
1. 각 플랫폼 Token 등 환경 변수를 설정합니다.
2. WebUI 서비스를 시작합니다.
3. 각 플랫폼에 Webhook URL을 설정합니다.
   - Feishu: http://your-server/bot/feishu
   - DingTalk: http://your-server/bot/dingtalk
   - WeCom: http://your-server/bot/wecom
   - Telegram: http://your-server/bot/telegram

지원 명령:
- /analyze <종목 코드> - 지정 종목 분석
- /market             - 시장 리뷰
- /batch              - 관심 종목 일괄 분석
- /help               - 도움말 표시
- /status             - 시스템 상태
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
