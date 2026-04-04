# -*- coding: utf-8 -*-
"""Backtest API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BacktestRunRequest(BaseModel):
    code: Optional[str] = Field(None, description="仅回测指定股票")
    force: bool = Field(False, description="强制重新计算")
    eval_window_days: Optional[int] = Field(None, ge=1, le=120, description="评估窗口（交易日数）")
    min_age_days: Optional[int] = Field(None, ge=0, le=365, description="分析记录最小天龄（0=不限）")
    limit: int = Field(200, ge=1, le=2000, description="最多处理的分析记录数")


class BacktestRunResponse(BaseModel):
    run_id: Optional[int] = Field(None, description="回测运行记录ID")
    run_at: Optional[str] = Field(None, description="回测运行时间")
    processed: int = Field(..., description="候选记录数")
    saved: int = Field(..., description="写入回测结果数")
    completed: int = Field(..., description="完成回测数")
    insufficient: int = Field(..., description="数据不足数")
    errors: int = Field(..., description="错误数")
    candidate_count: int = Field(0, description="实际进入执行的候选数")
    no_result_reason: Optional[str] = Field(None, description="本次未生成结果的原因")
    no_result_message: Optional[str] = Field(None, description="本次未生成结果的可读说明")


class PrepareBacktestSamplesRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    sample_count: int = Field(20, ge=1, le=365, description="需要准备的样本数量")
    eval_window_days: Optional[int] = Field(None, ge=1, le=120, description="评估窗口（交易日数）")
    min_age_days: Optional[int] = Field(None, ge=0, le=365, description="样本成熟天数")
    force_refresh: bool = Field(False, description="是否刷新已有样本")


class PrepareBacktestSamplesResponse(BaseModel):
    code: str
    sample_count: int
    prepared: int
    skipped_existing: int
    market_rows_saved: int
    candidate_rows: int
    eval_window_days: int
    min_age_days: int
    prepared_start_date: Optional[str] = None
    prepared_end_date: Optional[str] = None
    latest_prepared_at: Optional[str] = None
    no_result_reason: Optional[str] = None
    no_result_message: Optional[str] = None


class BacktestCodeRequest(BaseModel):
    code: str = Field(..., description="股票代码")


class BacktestRunHistoryItem(BaseModel):
    id: int
    code: Optional[str] = None
    eval_window_days: int
    min_age_days: int
    force: bool
    run_at: Optional[str] = None
    completed_at: Optional[str] = None
    processed: int
    saved: int
    completed: int
    insufficient: int
    errors: int
    candidate_count: int
    result_count: int
    no_result_reason: Optional[str] = None
    no_result_message: Optional[str] = None
    status: str
    total_evaluations: int = 0
    completed_count: int = 0
    insufficient_count: int = 0
    long_count: int = 0
    cash_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    neutral_count: int = 0
    win_rate_pct: Optional[float] = None
    avg_stock_return_pct: Optional[float] = None
    avg_simulated_return_pct: Optional[float] = None
    direction_accuracy_pct: Optional[float] = None


class BacktestRunHistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[BacktestRunHistoryItem] = Field(default_factory=list)


class BacktestSampleStatusResponse(BaseModel):
    code: str
    prepared_count: int
    prepared_start_date: Optional[str] = None
    prepared_end_date: Optional[str] = None
    latest_prepared_at: Optional[str] = None
    eval_window_days: int
    min_age_days: int


class BacktestClearResponse(BaseModel):
    code: str
    deleted_runs: int = 0
    deleted_results: int = 0
    deleted_samples: int = 0
    deleted_summaries: int = 0
    message: Optional[str] = None


class RuleBacktestParseRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    strategy_text: str = Field(..., description="策略文本")


class RuleBacktestParseResponse(BaseModel):
    code: str
    strategy_text: str
    parsed_strategy: Dict[str, Any]
    confidence: float = 0.0
    needs_confirmation: bool = False
    ambiguities: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, str] = Field(default_factory=dict)
    max_lookback: int = 1


class RuleBacktestRunRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    strategy_text: str = Field(..., description="策略文本")
    parsed_strategy: Optional[Dict[str, Any]] = Field(None, description="用户确认后的结构化规则")
    lookback_bars: int = Field(252, ge=10, le=5000, description="回测窗口（交易日数）")
    initial_capital: float = Field(100000.0, gt=0, description="初始资金")
    fee_bps: float = Field(0.0, ge=0, le=500, description="单边手续费（bp）")
    confirmed: bool = Field(False, description="是否已确认解析结果")


class RuleBacktestTradeItem(BaseModel):
    id: Optional[int] = None
    run_id: Optional[int] = None
    trade_index: Optional[int] = None
    code: str
    entry_date: Optional[str] = None
    exit_date: Optional[str] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    entry_signal: Optional[str] = None
    exit_signal: Optional[str] = None
    return_pct: Optional[float] = None
    holding_days: Optional[int] = None
    entry_rule: Dict[str, Any] = Field(default_factory=dict)
    exit_rule: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class RuleBacktestHistoryItem(BaseModel):
    id: int
    code: str
    strategy_text: str
    parsed_strategy: Dict[str, Any] = Field(default_factory=dict)
    strategy_hash: str
    timeframe: str
    lookback_bars: int
    initial_capital: float
    fee_bps: float
    parsed_confidence: Optional[float] = None
    needs_confirmation: bool = False
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    run_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: str
    no_result_reason: Optional[str] = None
    no_result_message: Optional[str] = None
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    total_return_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None
    avg_trade_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    avg_holding_days: Optional[float] = None
    final_equity: Optional[float] = None
    summary: Dict[str, Any] = Field(default_factory=dict)


class RuleBacktestHistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[RuleBacktestHistoryItem] = Field(default_factory=list)


class RuleBacktestRunResponse(BaseModel):
    id: int
    code: str
    strategy_text: str
    parsed_strategy: Dict[str, Any] = Field(default_factory=dict)
    strategy_hash: str
    timeframe: str
    lookback_bars: int
    initial_capital: float
    fee_bps: float
    parsed_confidence: Optional[float] = None
    needs_confirmation: bool = False
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    run_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: str
    no_result_reason: Optional[str] = None
    no_result_message: Optional[str] = None
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    total_return_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None
    avg_trade_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    avg_holding_days: Optional[float] = None
    final_equity: Optional[float] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    ai_summary: Optional[str] = None
    equity_curve: List[Dict[str, Any]] = Field(default_factory=list)
    trades: List[RuleBacktestTradeItem] = Field(default_factory=list)


class RuleBacktestDetailResponse(RuleBacktestRunResponse):
    pass


class BacktestResultItem(BaseModel):
    analysis_history_id: int
    code: str
    analysis_date: Optional[str] = None
    eval_window_days: int
    engine_version: str
    eval_status: str
    evaluated_at: Optional[str] = None
    operation_advice: Optional[str] = None
    position_recommendation: Optional[str] = None
    start_price: Optional[float] = None
    end_close: Optional[float] = None
    max_high: Optional[float] = None
    min_low: Optional[float] = None
    stock_return_pct: Optional[float] = None
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
