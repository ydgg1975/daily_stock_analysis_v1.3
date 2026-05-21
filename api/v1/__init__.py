# -*- coding: utf-8 -*-
"""
API v1 패키지 초기화.

역할:
1. v1 API 라우터를 공용 인터페이스로 노출합니다.
"""

from api.v1.router import router as api_v1_router

__all__ = ["api_v1_router"]
