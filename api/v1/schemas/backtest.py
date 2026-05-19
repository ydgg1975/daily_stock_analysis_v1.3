# -*- coding: utf-8 -*-

"""Backtest API schemas."""



from __future__ import annotations



from typing import Any, Dict, List, Optional



from pydantic import BaseModel, Field





class BacktestRunRequest(BaseModel):

    code: Optional[str] = Field(None, description="jinhuicezhidingstock")

    force: bool = Field(False, description="qiangzhichongxinjisuan")

    eval_window_days: Optional[int] = Field(None, ge=1, le=120, description="pingguchuangkou(chinese removed)늞iaoyirishu:")

    min_age_days: Optional[int] = Field(None, ge=0, le=365, description="analysisrecordzuixiaotianling:=buxian:")

    limit: int = Field(200, ge=1, le=2000, description="zuiduochulideanalysisrecordshu")





class BacktestRunResponse(BaseModel):

    processed: int = Field(..., description="houxuanrecordshu")

    saved: int = Field(..., description="xieruhuicejieguoshu")

    completed: int = Field(..., description="wanchenghuiceshu")

    insufficient: int = Field(..., description="shujubuzushu")

    errors: int = Field(..., description="cuowushu")





class BacktestResultItem(BaseModel):

    analysis_history_id: int

    code: str

    stock_name: Optional[str] = None

    analysis_date: Optional[str] = None

    eval_window_days: int

    engine_version: str

    eval_status: str

    evaluated_at: Optional[str] = None

    operation_advice: Optional[str] = None

    trend_prediction: Optional[str] = None

    position_recommendation: Optional[str] = None

    start_price: Optional[float] = None

    end_close: Optional[float] = None

    max_high: Optional[float] = None

    min_low: Optional[float] = None

    stock_return_pct: Optional[float] = None

    actual_return_pct: Optional[float] = None

    actual_movement: Optional[str] = None

    direction_expected: Optional[str] = None

    direction_correct: Optional[bool] = None

    outcome: Optional[str] = None

    stop_loss: Optional[float] = None

    take_profit: Optional[float] = None

    hit_stop_loss: Optional[bool] = None

    hit_take_profit: Optional[bool] = None

    first_hit: Optional[str] = None

    first_hit_date: Optional[str] = None

    first_hit_trading_days: Optional[int] = None

    simulated_entry_price: Optional[float] = None

    simulated_exit_price: Optional[float] = None

    simulated_exit_reason: Optional[str] = None

    simulated_return_pct: Optional[float] = None





class BacktestResultsResponse(BaseModel):

    total: int

    page: int

    limit: int

    items: List[BacktestResultItem] = Field(default_factory=list)





class PerformanceMetrics(BaseModel):

    scope: str

    code: Optional[str] = None

    eval_window_days: int

    engine_version: str

    computed_at: Optional[str] = None



    total_evaluations: int

    completed_count: int

    insufficient_count: int

    long_count: int

    cash_count: int

    win_count: int

    loss_count: int

    neutral_count: int



    direction_accuracy_pct: Optional[float] = None

    win_rate_pct: Optional[float] = None

    neutral_rate_pct: Optional[float] = None

    avg_stock_return_pct: Optional[float] = None

    avg_simulated_return_pct: Optional[float] = None



    stop_loss_trigger_rate: Optional[float] = None

    take_profit_trigger_rate: Optional[float] = None

    ambiguous_rate: Optional[float] = None

    avg_days_to_first_hit: Optional[float] = None



    advice_breakdown: Dict[str, Any] = Field(default_factory=dict)

    diagnostics: Dict[str, Any] = Field(default_factory=dict)


