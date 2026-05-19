# -*- coding: utf-8 -*-
"""
===================================
jiankangjianchajiekou
===================================

zhize：
1. tigong /api/v1/health jiankangjianchajiekou
2. yongyufuzaijunhengqihejiankongxitong
"""

from datetime import datetime

from fastapi import APIRouter

from api.v1.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    jiankangjianchajiekou
    
    yongyufuzaijunhengqihuojiankongxitongjianchafuwuzhuangtai
    
    Returns:
        HealthResponse: baohanfuwuzhuangtaiheshijianchuo
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat()
    )
