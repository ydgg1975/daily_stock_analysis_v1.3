# -*- coding: utf-8 -*-
"""
市场数据结构 Schema
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class MarketIndex(BaseModel):
    """市场指数数据"""
    name: str = Field(..., description="指数名称")
    code: str = Field(..., description="指数代码")
    price: float = Field(..., description="当前点位")
    change: float = Field(..., description="涨跌额")
    change_percent: float = Field(..., description="涨跌幅百分比")
    status: str = Field(..., description="状态：up/down/flat", pattern="^(up|down|flat)$")


class MarketSentiment(BaseModel):
    """市场情绪数据"""
    advancing: int = Field(..., description="上涨家数")
    declining: int = Field(..., description="下跌家数")
    unchanged: int = Field(..., description="平盘家数")
    limit_up: int = Field(..., description="涨停家数")
    limit_down: int = Field(..., description="跌停家数")


class SectorPerformance(BaseModel):
    """板块表现数据"""
    name: str = Field(..., description="板块名称")
    change_percent: float = Field(..., description="涨跌幅百分比")
    leading_stocks: Optional[List[str]] = Field(None, description="领涨股票列表")


class SectorRankings(BaseModel):
    """板块涨跌榜"""
    top: List[SectorPerformance] = Field(..., description="领涨板块")
    bottom: List[SectorPerformance] = Field(..., description="领跌板块")


class MarketOverview(BaseModel):
    """市场概览数据"""
    market: str = Field(..., description="市场类型：cn/us/both", pattern="^(cn|us|both)$")
    timestamp: str = Field(..., description="数据时间戳")
    indices: List[MarketIndex] = Field(..., description="主要指数")
    market_sentiment: MarketSentiment = Field(..., description="市场情绪")
    sector_rankings: SectorRankings = Field(..., description="板块涨跌榜")


class MarketReviewResponse(BaseModel):
    """大盘复盘响应"""
    overview: MarketOverview = Field(..., description="市场概览")
    updated_at: str = Field(..., description="更新时间")
    data_source: str = Field(..., description="数据来源")


class MarketReviewRequest(BaseModel):
    """大盘复盘请求"""
    market: str = Field(default="cn", description="市场类型：cn/us/both", pattern="^(cn|us|both)$")