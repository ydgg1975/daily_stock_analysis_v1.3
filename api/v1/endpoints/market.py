# -*- coding: utf-8 -*-
"""
===================================
大盘复盘 API 接口
===================================

职责：
1. GET /api/v1/market/overview 获取市场概览
2. POST /api/v1/market/review 触发大盘复盘分析
"""

import logging
from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException

from api.v1.schemas.market import (
    MarketReviewResponse,
    MarketOverview,
    MarketIndex,
    MarketSentiment,
    SectorRankings,
    SectorPerformance,
    MarketReviewRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_cn_indices() -> List[Dict[str, Any]]:
    """获取 A 股主要指数数据（模拟数据，实际应从数据源获取）"""
    # TODO: 集成真实数据源（AkShare/Tushare/YFinance）
    return [
        {"name": "上证指数", "code": "000001", "price": 3450.0, "change": 25.5, "change_percent": 0.74, "status": "up"},
        {"name": "深证成指", "code": "399001", "price": 11200.0, "change": -50.0, "change_percent": -0.44, "status": "down"},
        {"name": "创业板指", "code": "399006", "price": 2350.0, "change": 15.0, "change_percent": 0.64, "status": "up"},
        {"name": "科创 50", "code": "000688", "price": 1050.0, "change": 5.0, "change_percent": 0.48, "status": "up"},
    ]


def _get_us_indices() -> List[Dict[str, Any]]:
    """获取美股主要指数数据（模拟数据，实际应从数据源获取）"""
    # TODO: 集成真实数据源（YFinance）
    return [
        {"name": "标普 500", "code": "SPX", "price": 5200.0, "change": 30.0, "change_percent": 0.58, "status": "up"},
        {"name": "道琼斯", "code": "DJI", "price": 39000.0, "change": -100.0, "change_percent": -0.26, "status": "down"},
        {"name": "纳斯达克", "code": "IXIC", "price": 16500.0, "change": 80.0, "change_percent": 0.49, "status": "up"},
        {"name": "恐慌指数", "code": "VIX", "price": 14.5, "change": -0.5, "change_percent": -3.33, "status": "down"},
    ]


def _get_market_sentiment(market: str) -> Dict[str, int]:
    """获取市场情绪数据（模拟数据）"""
    if market == "us":
        return {
            "advancing": 1850,
            "declining": 1200,
            "unchanged": 150,
            "limit_up": 0,
            "limit_down": 0,
        }
    else:
        return {
            "advancing": 2800,
            "declining": 2100,
            "unchanged": 300,
            "limit_up": 45,
            "limit_down": 12,
        }


def _get_sector_rankings(market: str) -> Dict[str, List[Dict[str, Any]]]:
    """获取板块涨跌榜（模拟数据）"""
    if market == "us":
        return {
            "top": [
                {"name": "半导体", "change_percent": 3.5, "leading_stocks": ["NVDA", "AMD", "INTC"]},
                {"name": "人工智能", "change_percent": 2.8, "leading_stocks": ["MSFT", "GOOGL", "META"]},
                {"name": "电动车", "change_percent": 2.1, "leading_stocks": ["TSLA", "RIVN", "LCID"]},
            ],
            "bottom": [
                {"name": "银行", "change_percent": -1.2, "leading_stocks": ["JPM", "BAC", "WFC"]},
                {"name": "能源", "change_percent": -0.8, "leading_stocks": ["XOM", "CVX", "COP"]},
                {"name": "公用事业", "change_percent": -0.5, "leading_stocks": ["NEE", "DUK", "SO"]},
            ],
        }
    else:
        return {
            "top": [
                {"name": "半导体", "change_percent": 4.2, "leading_stocks": ["中芯国际", "韦尔股份", "卓胜微"]},
                {"name": "人工智能", "change_percent": 3.5, "leading_stocks": ["科大讯飞", "海康威视", "寒武纪"]},
                {"name": "新能源", "change_percent": 2.8, "leading_stocks": ["宁德时代", "比亚迪", "隆基绿能"]},
            ],
            "bottom": [
                {"name": "银行", "change_percent": -1.5, "leading_stocks": ["工商银行", "建设银行", "农业银行"]},
                {"name": "房地产", "change_percent": -1.2, "leading_stocks": ["万科 A", "保利发展", "招商蛇口"]},
                {"name": "建材", "change_percent": -0.8, "leading_stocks": ["海螺水泥", "东方雨虹", "北新建材"]},
            ],
        }


def _build_indices(market: str) -> List[MarketIndex]:
    """构建指数列表"""
    indices_data = []
    if market in ("cn", "both"):
        indices_data.extend(_get_cn_indices())
    if market in ("us", "both"):
        indices_data.extend(_get_us_indices())
    
    return [
        MarketIndex(
            name=item["name"],
            code=item["code"],
            price=item["price"],
            change=item["change"],
            change_percent=item["change_percent"],
            status=item["status"],
        )
        for item in indices_data
    ]


@router.get(
    "/overview",
    response_model=MarketReviewResponse,
    responses={
        200: {"description": "市场概览数据"},
        400: {"description": "参数错误"},
        500: {"description": "服务器错误"},
    },
    summary="获取市场概览",
    description="获取指定市场的概览数据，包括指数、市场情绪和板块涨跌榜",
)
def get_market_overview(
    market: str = "cn",
) -> MarketReviewResponse:
    """
    获取市场概览
    
    Args:
        market: 市场类型 (cn/us/both)
        
    Returns:
        MarketReviewResponse: 市场概览数据
    """
    if market not in ("cn", "us", "both"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": "不支持的市场类型，请使用 cn/us/both"
            }
        )
    
    try:
        now = datetime.now()
        sentiment_data = _get_market_sentiment(market)
        sector_data = _get_sector_rankings(market)
        
        sentiment = MarketSentiment(**sentiment_data)
        indices = _build_indices(market)
        rankings = SectorRankings(
            top=[SectorPerformance(**item) for item in sector_data["top"]],
            bottom=[SectorPerformance(**item) for item in sector_data["bottom"]],
        )
        
        overview = MarketOverview(
            market=market,
            timestamp=now.isoformat(),
            indices=indices,
            market_sentiment=sentiment,
            sector_rankings=rankings,
        )
        
        return MarketReviewResponse(
            overview=overview,
            updated_at=now.isoformat(),
            data_source="mock",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取市场概览失败：{e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"获取市场概览失败：{str(e)}"
            }
        )


@router.post(
    "/review",
    response_model=MarketReviewResponse,
    responses={
        200: {"description": "触发大盘复盘分析"},
        400: {"description": "参数错误"},
        500: {"description": "服务器错误"},
    },
    summary="触发大盘复盘分析",
    description="触发一次大盘复盘分析任务",
)
def trigger_market_review(
    request: MarketReviewRequest,
) -> MarketReviewResponse:
    """
    触发大盘复盘分析
    
    Args:
        request: 大盘复盘请求
        
    Returns:
        MarketReviewResponse: 市场概览数据
    """
    return get_market_overview(request.market)