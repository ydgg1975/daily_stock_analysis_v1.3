# -*- coding: utf-8 -*-
"""
===================================
tongyongxiangyingmodel
===================================

zhize竊?
1. dingyitongyongdexiangyingmodel竊뉸ealthResponse, ErrorResponse deng竊?
2. tigongtongyidexiangyinggeshi
"""

from typing import Optional, Any

from pydantic import BaseModel, Field


class RootResponse(BaseModel):
    """API genluyouxiangying"""
    
    message: str = Field(..., description="API yunxingzhuangtaixiaoxi", example="Daily Stock Analysis API is running")
    version: Optional[str] = Field(None, description="API banben", example="1.0.0")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Daily Stock Analysis API is running",
                "version": "1.0.0"
            }
        }


class HealthResponse(BaseModel):
    """jiankangjianchaxiangying"""
    
    status: str = Field(..., description="fuwuzhuangtai", example="ok")
    timestamp: Optional[str] = Field(None, description="shijianchuo")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "timestamp": "2024-01-01T12:00:00"
            }
        }


class ErrorResponse(BaseModel):
    """cuowuxiangying"""
    
    error: str = Field(..., description="cuowuleixing", example="validation_error")
    message: str = Field(..., description="cuowuxiangqing", example="qingqiucanshucuowu")
    detail: Optional[Any] = Field(None, description="fujiacuowuxinxi")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "not_found",
                "message": "ziyuanbucunzai",
                "detail": None
            }
        }


class SuccessResponse(BaseModel):
    """tongyongchenggongxiangying"""
    
    success: bool = Field(True, description="shifouchenggong")
    message: Optional[str] = Field(None, description="chenggongxiaoxi")
    data: Optional[Any] = Field(None, description="xiangyingshuju")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "caozuochenggong",
                "data": None
            }
        }

