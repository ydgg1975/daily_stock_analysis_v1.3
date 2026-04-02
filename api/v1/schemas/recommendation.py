# -*- coding: utf-8 -*-
"""
===================================
推荐选股相关模型
===================================

职责：
1. 定义推荐请求和响应模型
2. 定义推荐任务状态模型
"""

from typing import Optional, List, Any

from pydantic import BaseModel, Field


class RecommendedStock(BaseModel):
    """单只推荐股票"""

    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    market: str = Field(..., description="所属市场 (a_share/hk/us)")
    price: Optional[float] = Field(None, description="当前价格")
    change_pct: Optional[float] = Field(None, description="涨跌幅 (%)")
    score: Optional[int] = Field(None, description="推荐评分 (1-100)", ge=1, le=100)
    reason: Optional[str] = Field(None, description="推荐理由")
    risk: Optional[str] = Field(None, description="风险提示")
    target_price: Optional[str] = Field(None, description="目标价位")
    stop_loss: Optional[str] = Field(None, description="止损价位")


class RecommendationResult(BaseModel):
    """推荐结果"""

    task_id: str = Field(..., description="任务 ID")
    markets: str = Field(..., description="目标市场")
    price_min: Optional[float] = Field(None, description="最低价格")
    price_max: Optional[float] = Field(None, description="最高价格")
    candidates_count: int = Field(0, description="候选股票数量")
    stocks: List[RecommendedStock] = Field(default_factory=list, description="推荐股票列表")
    analysis_summary: Optional[str] = Field(None, description="整体分析摘要")
    model_used: Optional[str] = Field(None, description="使用的 LLM 模型")
    created_at: Optional[str] = Field(None, description="创建时间")


class RecommendTaskAccepted(BaseModel):
    """推荐任务接受响应"""

    task_id: str = Field(..., description="任务 ID")
    status: str = Field("pending", description="任务状态")
    message: Optional[str] = Field(None, description="提示信息")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "rec_abc123",
                "status": "pending",
                "message": "推荐任务已提交",
            }
        }


class RecommendTaskStatus(BaseModel):
    """推荐任务状态"""

    task_id: str = Field(..., description="任务 ID")
    status: str = Field(
        ...,
        description="任务状态",
        pattern="^(pending|processing|completed|failed)$",
    )
    progress: Optional[int] = Field(None, description="进度百分比 (0-100)", ge=0, le=100)
    result: Optional[RecommendationResult] = Field(None, description="推荐结果（仅 completed 时存在）")
    error: Optional[str] = Field(None, description="错误信息（仅 failed 时存在）")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "rec_abc123",
                "status": "completed",
                "progress": 100,
                "result": None,
                "error": None,
            }
        }


class RecommendHistoryItem(BaseModel):
    """推荐历史列表项"""

    id: int = Field(..., description="记录 ID")
    task_id: str = Field(..., description="任务 ID")
    markets: str = Field(..., description="目标市场")
    price_min: Optional[float] = Field(None, description="最低价格")
    price_max: Optional[float] = Field(None, description="最高价格")
    stock_count: int = Field(0, description="推荐股票数量")
    status: str = Field(..., description="任务状态")
    model_used: Optional[str] = Field(None, description="使用的模型")
    created_at: Optional[str] = Field(None, description="创建时间")


class RecommendHistoryResponse(BaseModel):
    """推荐历史分页响应"""

    total: int = Field(..., description="总记录数")
    items: List[RecommendHistoryItem] = Field(default_factory=list, description="历史列表")
    limit: int = Field(20, description="每页数量")
    offset: int = Field(0, description="偏移量")
