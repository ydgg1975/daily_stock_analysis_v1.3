# -*- coding: utf-8 -*-
"""Market scanner API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ScannerRunRequest(BaseModel):
    market: Literal["cn", "us", "hk"] = Field("cn", description="目标市场，当前阶段实现 cn / us / hk profile")
    profile: Optional[str] = Field(None, description="扫描配置 key，默认按市场选择")
    shortlist_size: int = Field(5, ge=1, le=20, description="输出观察名单数量")
    universe_limit: Optional[int] = Field(None, ge=50, le=1000, description="进入详细评估前的候选池上限")
    detail_limit: Optional[int] = Field(None, ge=10, le=200, description="进入详细特征计算的候选数")


class ScannerLabeledValue(BaseModel):
    label: str
    value: str


class ScannerNotificationResult(BaseModel):
    attempted: bool = False
    status: str = "not_attempted"
    success: Optional[bool] = None
    channels: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    report_path: Optional[str] = None
    sent_at: Optional[str] = None


class ScannerAiInterpretationResponse(BaseModel):
    available: bool = False
    status: str = "skipped"
    summary: Optional[str] = None
    opportunity_type: Optional[str] = None
    risk_interpretation: Optional[str] = None
    watch_plan: Optional[str] = None
    review_commentary: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    generated_at: Optional[str] = None
    message: Optional[str] = None


class ScannerCandidateOutcomeResponse(BaseModel):
    review_status: str = "pending"
    outcome_label: str = "pending"
    thesis_match: str = "pending"
    review_window_days: int = 3
    anchor_date: Optional[str] = None
    window_end_date: Optional[str] = None
    same_day_close_return_pct: Optional[float] = None
    next_day_return_pct: Optional[float] = None
    review_window_return_pct: Optional[float] = None
    max_favorable_move_pct: Optional[float] = None
    max_adverse_move_pct: Optional[float] = None
    benchmark_code: Optional[str] = None
    benchmark_return_pct: Optional[float] = None
    outperformed_benchmark: Optional[bool] = None


class ScannerReviewSummaryResponse(BaseModel):
    available: bool = False
    review_window_days: int = 3
    review_status: str = "pending"
    candidate_count: int = 0
    reviewed_count: int = 0
    pending_count: int = 0
    hit_rate_pct: Optional[float] = None
    outperform_rate_pct: Optional[float] = None
    avg_same_day_close_return_pct: Optional[float] = None
    avg_review_window_return_pct: Optional[float] = None
    avg_max_favorable_move_pct: Optional[float] = None
    avg_max_adverse_move_pct: Optional[float] = None
    strong_count: int = 0
    mixed_count: int = 0
    weak_count: int = 0
    best_symbol: Optional[str] = None
    best_return_pct: Optional[float] = None
    weakest_symbol: Optional[str] = None
    weakest_return_pct: Optional[float] = None


class ScannerWatchlistDeltaItem(BaseModel):
    symbol: str
    name: Optional[str] = None
    current_rank: Optional[int] = None
    previous_rank: Optional[int] = None
    rank_delta: Optional[int] = None


class ScannerWatchlistComparisonResponse(BaseModel):
    available: bool = False
    previous_run_id: Optional[int] = None
    previous_watchlist_date: Optional[str] = None
    new_count: int = 0
    retained_count: int = 0
    dropped_count: int = 0
    new_symbols: List[ScannerWatchlistDeltaItem] = Field(default_factory=list)
    retained_symbols: List[ScannerWatchlistDeltaItem] = Field(default_factory=list)
    dropped_symbols: List[ScannerWatchlistDeltaItem] = Field(default_factory=list)


class ScannerQualitySummaryResponse(BaseModel):
    available: bool = False
    review_window_days: int = 3
    benchmark_code: Optional[str] = None
    run_count: int = 0
    reviewed_run_count: int = 0
    reviewed_candidate_count: int = 0
    review_coverage_pct: Optional[float] = None
    avg_candidates_per_run: Optional[float] = None
    avg_shortlist_return_pct: Optional[float] = None
    positive_run_rate_pct: Optional[float] = None
    hit_rate_pct: Optional[float] = None
    outperform_rate_pct: Optional[float] = None
    positive_candidate_avg_score: Optional[float] = None
    negative_candidate_avg_score: Optional[float] = None


class ScannerCandidateResponse(BaseModel):
    symbol: str
    name: str
    rank: int
    score: float
    quality_hint: Optional[str] = None
    reason_summary: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)
    key_metrics: List[ScannerLabeledValue] = Field(default_factory=list)
    feature_signals: List[ScannerLabeledValue] = Field(default_factory=list)
    risk_notes: List[str] = Field(default_factory=list)
    watch_context: List[ScannerLabeledValue] = Field(default_factory=list)
    boards: List[str] = Field(default_factory=list)
    appeared_in_recent_runs: int = 0
    last_trade_date: Optional[str] = None
    scan_timestamp: Optional[str] = None
    ai_interpretation: ScannerAiInterpretationResponse = Field(default_factory=ScannerAiInterpretationResponse)
    realized_outcome: ScannerCandidateOutcomeResponse = Field(default_factory=ScannerCandidateOutcomeResponse)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class ScannerRunDetailResponse(BaseModel):
    id: int
    market: str
    profile: str
    profile_label: Optional[str] = None
    status: str
    run_at: Optional[str] = None
    completed_at: Optional[str] = None
    watchlist_date: Optional[str] = None
    trigger_mode: Optional[str] = None
    universe_name: str
    shortlist_size: int
    universe_size: int
    preselected_size: int
    evaluated_size: int
    source_summary: Optional[str] = None
    headline: Optional[str] = None
    universe_notes: List[str] = Field(default_factory=list)
    scoring_notes: List[str] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    notification: ScannerNotificationResult = Field(default_factory=ScannerNotificationResult)
    failure_reason: Optional[str] = None
    comparison_to_previous: ScannerWatchlistComparisonResponse = Field(default_factory=ScannerWatchlistComparisonResponse)
    review_summary: ScannerReviewSummaryResponse = Field(default_factory=ScannerReviewSummaryResponse)
    shortlist: List[ScannerCandidateResponse] = Field(default_factory=list)


class ScannerRunHistoryItem(BaseModel):
    id: int
    market: str
    profile: str
    profile_label: Optional[str] = None
    status: str
    run_at: Optional[str] = None
    completed_at: Optional[str] = None
    watchlist_date: Optional[str] = None
    trigger_mode: Optional[str] = None
    universe_name: str
    shortlist_size: int
    universe_size: int
    preselected_size: int
    evaluated_size: int
    source_summary: Optional[str] = None
    headline: Optional[str] = None
    top_symbols: List[str] = Field(default_factory=list)
    notification_status: Optional[str] = None
    failure_reason: Optional[str] = None
    change_summary: ScannerWatchlistComparisonResponse = Field(default_factory=ScannerWatchlistComparisonResponse)
    review_summary: ScannerReviewSummaryResponse = Field(default_factory=ScannerReviewSummaryResponse)


class ScannerRunHistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[ScannerRunHistoryItem] = Field(default_factory=list)


class ScannerOperationRunSummary(BaseModel):
    id: int
    watchlist_date: Optional[str] = None
    trigger_mode: Optional[str] = None
    status: str
    run_at: Optional[str] = None
    headline: Optional[str] = None
    shortlist_size: int = 0
    notification_status: Optional[str] = None
    failure_reason: Optional[str] = None


class ScannerOperationalStatusResponse(BaseModel):
    market: str
    profile: str
    profile_label: Optional[str] = None
    watchlist_date: str
    today_trading_day: bool
    schedule_enabled: bool
    schedule_time: Optional[str] = None
    schedule_run_immediately: bool = False
    notification_enabled: bool = False
    today_watchlist: Optional[ScannerOperationRunSummary] = None
    last_run: Optional[ScannerOperationRunSummary] = None
    last_scheduled_run: Optional[ScannerOperationRunSummary] = None
    last_manual_run: Optional[ScannerOperationRunSummary] = None
    latest_failure: Optional[ScannerOperationRunSummary] = None
    quality_summary: ScannerQualitySummaryResponse = Field(default_factory=ScannerQualitySummaryResponse)
