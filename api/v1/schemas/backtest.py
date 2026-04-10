# -*- coding: utf-8 -*-
"""Backtest API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BacktestRunRequest(BaseModel):
    code: Optional[str] = Field(None, description="仅回测指定股票")
    force: bool = Field(False, description="强制重新计算")
    eval_window_days: Optional[int] = Field(None, ge=1, le=120, description="评估窗口（交易 bars）")
    min_age_days: Optional[int] = Field(None, ge=0, le=365, description="分析记录成熟期（日历天，0=不限）")
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
    latest_prepared_sample_date: Optional[str] = None
    latest_eligible_sample_date: Optional[str] = None
    excluded_recent_reason: Optional[str] = None
    excluded_recent_message: Optional[str] = None
    evaluation_mode: Optional[str] = None
    evaluation_window_trading_bars: Optional[int] = None
    maturity_calendar_days: Optional[int] = None
    requested_mode: Optional[str] = None
    resolved_source: Optional[str] = None
    fallback_used: Optional[bool] = None
    pricing_resolved_source: Optional[str] = None
    pricing_fallback_used: Optional[bool] = None
    execution_assumptions: Dict[str, Any] = Field(default_factory=dict)


class PrepareBacktestSamplesRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    sample_count: int = Field(20, ge=1, le=365, description="需要准备的分析样本条数")
    eval_window_days: Optional[int] = Field(None, ge=1, le=120, description="评估窗口（交易 bars）")
    min_age_days: Optional[int] = Field(None, ge=0, le=365, description="样本成熟期（日历天）")
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
    latest_prepared_sample_date: Optional[str] = None
    latest_eligible_sample_date: Optional[str] = None
    excluded_recent_reason: Optional[str] = None
    excluded_recent_message: Optional[str] = None
    no_result_reason: Optional[str] = None
    no_result_message: Optional[str] = None
    evaluation_window_trading_bars: Optional[int] = None
    maturity_calendar_days: Optional[int] = None
    requested_mode: Optional[str] = None
    resolved_source: Optional[str] = None
    fallback_used: Optional[bool] = None
    pricing_resolved_source: Optional[str] = None
    pricing_fallback_used: Optional[bool] = None


class BacktestCodeRequest(BaseModel):
    code: str = Field(..., description="股票代码")


class BacktestRunHistoryItem(BaseModel):
    id: int
    code: Optional[str] = None
    eval_window_days: int
    evaluation_window_trading_bars: Optional[int] = None
    min_age_days: int
    maturity_calendar_days: Optional[int] = None
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
    summary: Dict[str, Any] = Field(default_factory=dict)
    evaluation_mode: Optional[str] = None
    requested_mode: Optional[str] = None
    resolved_source: Optional[str] = None
    fallback_used: Optional[bool] = None
    execution_assumptions: Dict[str, Any] = Field(default_factory=dict)


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
    latest_prepared_sample_date: Optional[str] = None
    latest_eligible_sample_date: Optional[str] = None
    excluded_recent_reason: Optional[str] = None
    excluded_recent_message: Optional[str] = None
    eval_window_days: int
    min_age_days: int
    evaluation_window_trading_bars: Optional[int] = None
    maturity_calendar_days: Optional[int] = None
    requested_mode: Optional[str] = None
    resolved_source: Optional[str] = None
    fallback_used: Optional[bool] = None
    pricing_resolved_source: Optional[str] = None
    pricing_fallback_used: Optional[bool] = None


class BacktestClearResponse(BaseModel):
    code: str
    deleted_runs: int = 0
    deleted_results: int = 0
    deleted_samples: int = 0
    deleted_summaries: int = 0
    message: Optional[str] = None


class RuleBacktestParseRequest(BaseModel):
    code: Optional[str] = Field(None, description="股票代码")
    strategy_text: str = Field(..., description="策略文本")
    start_date: Optional[str] = Field(None, description="回测开始日期（YYYY-MM-DD）")
    end_date: Optional[str] = Field(None, description="回测结束日期（YYYY-MM-DD）")
    initial_capital: Optional[float] = Field(None, gt=0, description="初始资金")
    fee_bps: float = Field(0.0, ge=0, le=500, description="单边手续费（bp）")
    slippage_bps: float = Field(0.0, ge=0, le=500, description="单边滑点（bp）")


class RuleBacktestParseResponse(BaseModel):
    code: Optional[str] = None
    strategy_text: str
    parsed_strategy: Dict[str, Any]
    normalized_strategy_family: Optional[str] = None
    detected_strategy_family: Optional[str] = None
    executable: bool = False
    normalization_state: str = "pending"
    assumptions: List[Dict[str, Any]] = Field(default_factory=list)
    assumption_groups: List[Dict[str, Any]] = Field(default_factory=list)
    unsupported_reason: Optional[str] = None
    unsupported_details: List[Dict[str, Any]] = Field(default_factory=list)
    unsupported_extensions: List[Dict[str, Any]] = Field(default_factory=list)
    core_intent_summary: Optional[str] = None
    interpretation_confidence: float = 0.0
    supported_portion_summary: Optional[str] = None
    rewrite_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    parse_warnings: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    needs_confirmation: bool = False
    ambiguities: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, str] = Field(default_factory=dict)
    max_lookback: int = 1


class RuleBacktestRunRequest(BaseModel):
    code: str = Field(..., description="股票代码")
    strategy_text: str = Field(..., description="策略文本")
    parsed_strategy: Optional[Dict[str, Any]] = Field(None, description="用户确认后的结构化规则")
    start_date: Optional[str] = Field(None, description="回测开始日期（YYYY-MM-DD）")
    end_date: Optional[str] = Field(None, description="回测结束日期（YYYY-MM-DD）")
    lookback_bars: int = Field(252, ge=10, le=5000, description="回测窗口（交易 bars）")
    initial_capital: float = Field(100000.0, gt=0, description="初始资金")
    fee_bps: float = Field(0.0, ge=0, le=500, description="单边手续费（bp）")
    slippage_bps: float = Field(0.0, ge=0, le=500, description="单边滑点（bp）")
    benchmark_mode: str = Field("auto", description="基准模式")
    benchmark_code: Optional[str] = Field(None, description="自定义基准代码")
    confirmed: bool = Field(False, description="是否已确认解析结果")
    wait_for_completion: bool = Field(False, description="是否阻塞等待回测完成；默认异步提交并轮询状态")


class RuleBacktestTradeItem(BaseModel):
    id: Optional[int] = None
    run_id: Optional[int] = None
    trade_index: Optional[int] = None
    code: str
    entry_signal_date: Optional[str] = None
    exit_signal_date: Optional[str] = None
    entry_date: Optional[str] = None
    exit_date: Optional[str] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    entry_signal: Optional[str] = None
    exit_signal: Optional[str] = None
    entry_trigger: Optional[str] = None
    exit_trigger: Optional[str] = None
    return_pct: Optional[float] = None
    holding_days: Optional[int] = None
    holding_bars: Optional[int] = None
    holding_calendar_days: Optional[int] = None
    entry_rule: Dict[str, Any] = Field(default_factory=dict)
    exit_rule: Dict[str, Any] = Field(default_factory=dict)
    entry_indicators: Dict[str, Any] = Field(default_factory=dict)
    exit_indicators: Dict[str, Any] = Field(default_factory=dict)
    entry_fill_basis: Optional[str] = None
    exit_fill_basis: Optional[str] = None
    signal_price_basis: Optional[str] = None
    price_basis: Optional[str] = None
    fee_bps: Optional[float] = None
    slippage_bps: Optional[float] = None
    entry_fee_amount: Optional[float] = None
    exit_fee_amount: Optional[float] = None
    entry_slippage_amount: Optional[float] = None
    exit_slippage_amount: Optional[float] = None
    notes: Optional[str] = None


class RuleBacktestAuditRowItem(BaseModel):
    date: str
    symbol_close: Optional[float] = None
    benchmark_close: Optional[float] = None
    position: Optional[float] = None
    shares: Optional[float] = None
    cash: Optional[float] = None
    holdings_value: Optional[float] = None
    total_portfolio_value: Optional[float] = None
    daily_pnl: Optional[float] = None
    daily_return: Optional[float] = None
    cumulative_return: Optional[float] = None
    benchmark_cumulative_return: Optional[float] = None
    buy_hold_cumulative_return: Optional[float] = None
    action: Optional[str] = None
    fill_price: Optional[float] = None
    signal_summary: Optional[str] = None
    drawdown_pct: Optional[float] = None
    position_state: Optional[str] = None
    fees: Optional[float] = None
    slippage: Optional[float] = None
    notes: Optional[str] = None
    unavailable_reason: Optional[str] = None


class RuleBacktestHistoryItem(BaseModel):
    id: int
    code: str
    strategy_text: str
    parsed_strategy: Dict[str, Any] = Field(default_factory=dict)
    strategy_hash: str
    timeframe: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    lookback_bars: int
    initial_capital: float
    fee_bps: float
    slippage_bps: float = 0.0
    parsed_confidence: Optional[float] = None
    needs_confirmation: bool = False
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    run_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: str
    status_message: Optional[str] = None
    status_history: List[Dict[str, Any]] = Field(default_factory=list)
    no_result_reason: Optional[str] = None
    no_result_message: Optional[str] = None
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    total_return_pct: Optional[float] = None
    annualized_return_pct: Optional[float] = None
    benchmark_mode: Optional[str] = None
    benchmark_code: Optional[str] = None
    benchmark_return_pct: Optional[float] = None
    excess_return_vs_benchmark_pct: Optional[float] = None
    buy_and_hold_return_pct: Optional[float] = None
    excess_return_vs_buy_and_hold_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None
    avg_trade_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    avg_holding_days: Optional[float] = None
    avg_holding_bars: Optional[float] = None
    avg_holding_calendar_days: Optional[float] = None
    final_equity: Optional[float] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    execution_assumptions: Dict[str, Any] = Field(default_factory=dict)
    benchmark_curve: List[Dict[str, Any]] = Field(default_factory=list)
    benchmark_summary: Dict[str, Any] = Field(default_factory=dict)
    buy_and_hold_curve: List[Dict[str, Any]] = Field(default_factory=list)
    buy_and_hold_summary: Dict[str, Any] = Field(default_factory=dict)
    audit_rows: List[RuleBacktestAuditRowItem] = Field(default_factory=list)
    daily_return_series: List[Dict[str, Any]] = Field(default_factory=list)
    exposure_curve: List[Dict[str, Any]] = Field(default_factory=list)


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
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    lookback_bars: int
    initial_capital: float
    fee_bps: float
    slippage_bps: float = 0.0
    parsed_confidence: Optional[float] = None
    needs_confirmation: bool = False
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    run_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: str
    status_message: Optional[str] = None
    status_history: List[Dict[str, Any]] = Field(default_factory=list)
    no_result_reason: Optional[str] = None
    no_result_message: Optional[str] = None
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    total_return_pct: Optional[float] = None
    annualized_return_pct: Optional[float] = None
    benchmark_mode: Optional[str] = None
    benchmark_code: Optional[str] = None
    benchmark_return_pct: Optional[float] = None
    excess_return_vs_benchmark_pct: Optional[float] = None
    buy_and_hold_return_pct: Optional[float] = None
    excess_return_vs_buy_and_hold_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None
    avg_trade_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    avg_holding_days: Optional[float] = None
    avg_holding_bars: Optional[float] = None
    avg_holding_calendar_days: Optional[float] = None
    final_equity: Optional[float] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    execution_assumptions: Dict[str, Any] = Field(default_factory=dict)
    benchmark_curve: List[Dict[str, Any]] = Field(default_factory=list)
    benchmark_summary: Dict[str, Any] = Field(default_factory=dict)
    buy_and_hold_curve: List[Dict[str, Any]] = Field(default_factory=list)
    buy_and_hold_summary: Dict[str, Any] = Field(default_factory=dict)
    audit_rows: List[RuleBacktestAuditRowItem] = Field(default_factory=list)
    daily_return_series: List[Dict[str, Any]] = Field(default_factory=list)
    exposure_curve: List[Dict[str, Any]] = Field(default_factory=list)
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
    evaluation_window_trading_bars: Optional[int] = None
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
    market_data_sources: List[str] = Field(default_factory=list)
    execution_assumptions: Dict[str, Any] = Field(default_factory=dict)


class BacktestResultsResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[BacktestResultItem] = Field(default_factory=list)


class PerformanceMetrics(BaseModel):
    scope: str
    code: Optional[str] = None
    eval_window_days: int
    evaluation_window_trading_bars: Optional[int] = None
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
    evaluation_mode: Optional[str] = None
    requested_mode: Optional[str] = None
    resolved_source: Optional[str] = None
    fallback_used: Optional[bool] = None
    execution_assumptions: Dict[str, Any] = Field(default_factory=dict)
