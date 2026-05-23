# -*- coding: utf-8 -*-
"""Stock data API schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class StockQuote(BaseModel):
    """Realtime stock quote."""

    stock_code: str = Field(..., description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    current_price: float = Field(..., description="현재가")
    change: Optional[float] = Field(None, description="등락액")
    change_percent: Optional[float] = Field(None, description="등락률(%)")
    open: Optional[float] = Field(None, description="시가")
    high: Optional[float] = Field(None, description="고가")
    low: Optional[float] = Field(None, description="저가")
    prev_close: Optional[float] = Field(None, description="전일 종가")
    volume: Optional[float] = Field(None, description="거래량")
    amount: Optional[float] = Field(None, description="거래대금")
    update_time: Optional[str] = Field(None, description="업데이트 시간")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "current_price": 1800.0,
            "change": 15.0,
            "change_percent": 0.84,
            "open": 1785.0,
            "high": 1810.0,
            "low": 1780.0,
            "prev_close": 1785.0,
            "volume": 10000000,
            "amount": 18000000000,
            "update_time": "2024-01-01T15:00:00",
        }
    })


class KLineData(BaseModel):
    """K-line data point."""

    date: str = Field(..., description="날짜")
    open: float = Field(..., description="시가")
    high: float = Field(..., description="고가")
    low: float = Field(..., description="저가")
    close: float = Field(..., description="종가")
    volume: Optional[float] = Field(None, description="거래량")
    amount: Optional[float] = Field(None, description="거래대금")
    change_percent: Optional[float] = Field(None, description="등락률(%)")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "date": "2024-01-01",
            "open": 178.5,
            "high": 181.0,
            "low": 178.0,
            "close": 180.0,
            "volume": 10000000,
            "amount": 1800000000,
            "change_percent": 0.84,
        }
    })


class ExtractItem(BaseModel):
    """Single extraction result."""

    code: Optional[str] = Field(None, description="종목 코드. 실패 시 None입니다.")
    name: Optional[str] = Field(None, description="종목명")
    confidence: str = Field("medium", description="신뢰도: high/medium/low")


class ExtractFromImageResponse(BaseModel):
    """Image stock-code extraction response."""

    codes: List[str] = Field(..., description="추출된 종목 코드 목록(중복 제거, 하위 호환용)")
    items: List[ExtractItem] = Field(default_factory=list, description="추출 결과 상세 목록(코드, 이름, 신뢰도)")
    raw_text: Optional[str] = Field(None, description="원본 LLM 응답(디버깅용)")


class StockHistoryResponse(BaseModel):
    """Historical stock price response."""

    stock_code: str = Field(..., description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    period: str = Field(..., description="K-line 주기")
    data: List[KLineData] = Field(default_factory=list, description="K-line 데이터 목록")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "AAPL",
            "stock_name": "Apple",
            "period": "daily",
            "data": [],
        }
    })


class StockChartAnalysisResponse(BaseModel):
    """Stock chart analysis preview response."""

    stock_code: str
    source: Optional[str] = None
    requested_days: int
    status: str
    image_format: str = "svg"
    svg: Optional[str] = None
    svg_omitted: bool = False
    svg_length: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = None
