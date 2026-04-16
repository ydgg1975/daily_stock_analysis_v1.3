# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 存储层
===================================

职责：
1. 管理 SQLite 数据库连接（单例模式）
2. 定义 ORM 数据模型
3. 提供数据存取接口
4. 实现智能更新逻辑（断点续传）
"""

import atexit
from contextlib import contextmanager
import hashlib
import json
import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, TYPE_CHECKING, Tuple
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    Integer,
    ForeignKey,
    Index,
    UniqueConstraint,
    Text,
    select,
    and_,
    or_,
    delete,
    desc,
    asc,
    func,
    inspect,
)
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    Session,
)
from sqlalchemy.exc import IntegrityError

from src.config import get_config
from src.core.trading_calendar import MARKET_TIMEZONE, get_market_for_stock
from src.multi_user import (
    BOOTSTRAP_ADMIN_DISPLAY_NAME,
    BOOTSTRAP_ADMIN_USER_ID,
    BOOTSTRAP_ADMIN_USERNAME,
    OWNERSHIP_SCOPE_SYSTEM,
    OWNERSHIP_SCOPE_USER,
    ROLE_ADMIN,
    ROLE_USER,
    normalize_role,
    normalize_scope,
)
from src.services.us_history_helper import LOCAL_US_PARQUET_SOURCE
from src.postgres_phase_a import PostgresPhaseAStore
from src.postgres_phase_b import PostgresPhaseBStore
from src.postgres_phase_c import PostgresPhaseCStore
from src.postgres_phase_d import PostgresPhaseDStore
from src.postgres_phase_e import PostgresPhaseEStore

logger = logging.getLogger(__name__)

# SQLAlchemy ORM 基类
Base = declarative_base()

if TYPE_CHECKING:
    from src.search_service import SearchResponse


# === 数据模型定义 ===

class StockDaily(Base):
    """
    股票日线数据模型
    
    存储每日行情数据和计算的技术指标
    支持多股票、多日期的唯一约束
    """
    __tablename__ = 'stock_daily'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 股票代码（如 600519, 000001）
    code = Column(String(10), nullable=False, index=True)
    
    # 交易日期
    date = Column(Date, nullable=False, index=True)
    
    # OHLC 数据
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    
    # 成交数据
    volume = Column(Float)  # 成交量（股）
    amount = Column(Float)  # 成交额（元）
    pct_chg = Column(Float)  # 涨跌幅（%）
    
    # 技术指标
    ma5 = Column(Float)
    ma10 = Column(Float)
    ma20 = Column(Float)
    volume_ratio = Column(Float)  # 量比
    
    # 数据来源
    data_source = Column(String(50))  # 记录数据来源（如 AkshareFetcher）
    
    # 更新时间
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 唯一约束：同一股票同一日期只能有一条数据
    __table_args__ = (
        UniqueConstraint('code', 'date', name='uix_code_date'),
        Index('ix_code_date', 'code', 'date'),
    )
    
    def __repr__(self):
        return f"<StockDaily(code={self.code}, date={self.date}, close={self.close})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'date': self.date,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'amount': self.amount,
            'pct_chg': self.pct_chg,
            'ma5': self.ma5,
            'ma10': self.ma10,
            'ma20': self.ma20,
            'volume_ratio': self.volume_ratio,
            'data_source': self.data_source,
        }


class NewsIntel(Base):
    """
    新闻情报数据模型

    存储搜索到的新闻情报条目，用于后续分析与查询
    """
    __tablename__ = 'news_intel'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 关联用户查询操作
    query_id = Column(String(64), index=True)

    # 股票信息
    code = Column(String(10), nullable=False, index=True)
    name = Column(String(50))

    # 搜索上下文
    dimension = Column(String(32), index=True)  # latest_news / risk_check / earnings / market_analysis / industry
    query = Column(String(255))
    provider = Column(String(32), index=True)

    # 新闻内容
    title = Column(String(300), nullable=False)
    snippet = Column(Text)
    url = Column(String(1000), nullable=False)
    source = Column(String(100))
    published_date = Column(DateTime, index=True)

    # 入库时间
    fetched_at = Column(DateTime, default=datetime.now, index=True)
    query_source = Column(String(32), index=True)  # bot/web/cli/system
    requester_platform = Column(String(20))
    requester_user_id = Column(String(64))
    requester_user_name = Column(String(64))
    requester_chat_id = Column(String(64))
    requester_message_id = Column(String(64))
    requester_query = Column(String(255))

    __table_args__ = (
        UniqueConstraint('url', name='uix_news_url'),
        Index('ix_news_code_pub', 'code', 'published_date'),
    )

    def __repr__(self) -> str:
        return f"<NewsIntel(code={self.code}, title={self.title[:20]}...)>"


class FundamentalSnapshot(Base):
    """
    基本面上下文快照（P0 write-only）。

    仅用于写入，主链路不依赖读取该表，便于后续回测/画像扩展。
    """
    __tablename__ = 'fundamental_snapshot'

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String(64), nullable=False, index=True)
    code = Column(String(10), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    source_chain = Column(Text)
    coverage = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        Index('ix_fundamental_snapshot_query_code', 'query_id', 'code'),
        Index('ix_fundamental_snapshot_created', 'created_at'),
    )

    def __repr__(self) -> str:
        return f"<FundamentalSnapshot(query_id={self.query_id}, code={self.code})>"


class AppUser(Base):
    """Persisted application user identity for the multi-user foundation."""

    __tablename__ = 'app_users'

    id = Column(String(64), primary_key=True)
    username = Column(String(128), nullable=False, unique=True, index=True)
    display_name = Column(String(128))
    password_hash = Column(String(255))
    role = Column(String(16), nullable=False, default=ROLE_USER, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_app_user_role_active', 'role', 'is_active'),
    )


class AppUserSession(Base):
    """Persistent authenticated session record for cookie-based auth."""

    __tablename__ = 'app_user_sessions'

    session_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey('app_users.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    last_seen_at = Column(DateTime, default=datetime.now, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, index=True)

    __table_args__ = (
        Index('ix_app_user_session_user_expiry', 'user_id', 'expires_at'),
        Index('ix_app_user_session_revoked', 'revoked_at'),
    )


class UserPreference(Base):
    """User-owned preferences kept separate from global system configuration."""

    __tablename__ = 'user_preferences'

    user_id = Column(String(64), ForeignKey('app_users.id'), primary_key=True)
    ui_preferences_json = Column(Text)
    notification_preferences_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AnalysisHistory(Base):
    """
    分析结果历史记录模型

    保存每次分析结果，支持按 query_id/股票代码检索
    """
    __tablename__ = 'analysis_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)

    # 关联查询链路
    query_id = Column(String(64), index=True)

    # 股票信息
    code = Column(String(10), nullable=False, index=True)
    name = Column(String(50))
    report_type = Column(String(16), index=True)

    # 核心结论
    sentiment_score = Column(Integer)
    operation_advice = Column(String(20))
    trend_prediction = Column(String(50))
    analysis_summary = Column(Text)

    # 详细数据
    raw_result = Column(Text)
    news_content = Column(Text)
    context_snapshot = Column(Text)

    # 狙击点位（用于回测）
    ideal_buy = Column(Float)
    secondary_buy = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)

    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        Index('ix_analysis_owner_created', 'owner_id', 'created_at'),
        Index('ix_analysis_owner_query', 'owner_id', 'query_id'),
        Index('ix_analysis_code_time', 'code', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'owner_id': self.owner_id,
            'query_id': self.query_id,
            'code': self.code,
            'name': self.name,
            'report_type': self.report_type,
            'sentiment_score': self.sentiment_score,
            'operation_advice': self.operation_advice,
            'trend_prediction': self.trend_prediction,
            'analysis_summary': self.analysis_summary,
            'raw_result': self.raw_result,
            'news_content': self.news_content,
            'context_snapshot': self.context_snapshot,
            'ideal_buy': self.ideal_buy,
            'secondary_buy': self.secondary_buy,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ExecutionLogSession(Base):
    """
    管理员可观测执行会话（D2）。

    每次分析任务对应一个会话，存储执行总体状态与关联信息。
    """

    __tablename__ = 'execution_log_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, unique=True, index=True)
    task_id = Column(String(64), index=True)
    query_id = Column(String(64), index=True)
    analysis_history_id = Column(Integer, ForeignKey('analysis_history.id'), index=True)
    code = Column(String(10), index=True)
    name = Column(String(50))
    overall_status = Column(String(32), nullable=False, default='running', index=True)
    truth_level = Column(String(16), nullable=False, default='mixed')
    summary_json = Column(Text)
    started_at = Column(DateTime, default=datetime.now, index=True)
    ended_at = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_exec_session_code_started', 'code', 'started_at'),
        Index('ix_exec_session_query_started', 'query_id', 'started_at'),
    )


class ExecutionLogEvent(Base):
    """
    执行会话的结构化事件流（D2）。

    phase 示例：
    - ai
    - data.market / data.fundamentals / data.news / data.sentiment
    - notification
    """

    __tablename__ = 'execution_log_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    event_at = Column(DateTime, default=datetime.now, index=True)
    phase = Column(String(48), nullable=False, index=True)
    step = Column(String(48), index=True)
    target = Column(String(128), index=True)
    status = Column(String(32), nullable=False, index=True)
    truth_level = Column(String(16), nullable=False, default='inferred', index=True)
    message = Column(Text)
    error_code = Column(String(64))
    detail_json = Column(Text)

    __table_args__ = (
        Index('ix_exec_event_session_time', 'session_id', 'event_at'),
        Index('ix_exec_event_phase_status', 'phase', 'status'),
    )


class BacktestResult(Base):
    """单条分析记录的回测结果。"""

    __tablename__ = 'backtest_results'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)

    analysis_history_id = Column(
        Integer,
        ForeignKey('analysis_history.id'),
        nullable=False,
        index=True,
    )

    # 冗余字段，便于按股票筛选
    code = Column(String(10), nullable=False, index=True)
    analysis_date = Column(Date, index=True)

    # 回测参数
    eval_window_days = Column(Integer, nullable=False, default=10)
    engine_version = Column(String(16), nullable=False, default='v1')

    # 状态
    eval_status = Column(String(16), nullable=False, default='pending')
    evaluated_at = Column(DateTime, default=datetime.now, index=True)

    # 建议快照（避免未来分析字段变化导致回测不可解释）
    operation_advice = Column(String(20))
    position_recommendation = Column(String(8))  # long/cash

    # 价格与收益
    start_price = Column(Float)
    end_close = Column(Float)
    max_high = Column(Float)
    min_low = Column(Float)
    stock_return_pct = Column(Float)

    # 方向与结果
    direction_expected = Column(String(16))  # up/down/flat/not_down
    direction_correct = Column(Boolean, nullable=True)
    outcome = Column(String(16))  # win/loss/neutral

    # 目标价命中（仅 long 且配置了止盈/止损时有意义）
    stop_loss = Column(Float)
    take_profit = Column(Float)
    hit_stop_loss = Column(Boolean)
    hit_take_profit = Column(Boolean)
    first_hit = Column(String(16))  # take_profit/stop_loss/ambiguous/neither/not_applicable
    first_hit_date = Column(Date)
    first_hit_trading_days = Column(Integer)

    # 模拟执行（long-only）
    simulated_entry_price = Column(Float)
    simulated_exit_price = Column(Float)
    simulated_exit_reason = Column(String(24))  # stop_loss/take_profit/window_end/cash/ambiguous_stop_loss
    simulated_return_pct = Column(Float)

    __table_args__ = (
        UniqueConstraint(
            'analysis_history_id',
            'eval_window_days',
            'engine_version',
            name='uix_backtest_analysis_window_version',
        ),
        Index('ix_backtest_result_owner_evaluated', 'owner_id', 'evaluated_at'),
        Index('ix_backtest_code_date', 'code', 'analysis_date'),
    )


class BacktestSummary(Base):
    """回测汇总指标（按股票或全局）。"""

    __tablename__ = 'backtest_summaries'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), nullable=False, index=True, default=BOOTSTRAP_ADMIN_USER_ID)

    scope = Column(String(16), nullable=False, index=True)  # overall/stock
    code = Column(String(16), index=True)

    eval_window_days = Column(Integer, nullable=False, default=10)
    engine_version = Column(String(16), nullable=False, default='v1')
    computed_at = Column(DateTime, default=datetime.now, index=True)

    # 计数
    total_evaluations = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    insufficient_count = Column(Integer, default=0)
    long_count = Column(Integer, default=0)
    cash_count = Column(Integer, default=0)

    win_count = Column(Integer, default=0)
    loss_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)

    # 准确率/胜率
    direction_accuracy_pct = Column(Float)
    win_rate_pct = Column(Float)
    neutral_rate_pct = Column(Float)

    # 收益
    avg_stock_return_pct = Column(Float)
    avg_simulated_return_pct = Column(Float)

    # 目标价触发统计（仅 long 且配置止盈/止损时统计）
    stop_loss_trigger_rate = Column(Float)
    take_profit_trigger_rate = Column(Float)
    ambiguous_rate = Column(Float)
    avg_days_to_first_hit = Column(Float)

    # 诊断字段（JSON 字符串）
    advice_breakdown_json = Column(Text)
    diagnostics_json = Column(Text)

    __table_args__ = (
        UniqueConstraint(
            'owner_id',
            'scope',
            'code',
            'eval_window_days',
            'engine_version',
            name='uix_backtest_summary_owner_scope_code_window_version',
        ),
    )


class BacktestRun(Base):
    """One persisted backtest execution."""

    __tablename__ = 'backtest_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)

    code = Column(String(16), index=True)
    eval_window_days = Column(Integer, nullable=False, default=10, index=True)
    min_age_days = Column(Integer, nullable=False, default=14)
    force = Column(Boolean, nullable=False, default=False)

    run_at = Column(DateTime, default=datetime.now, index=True)
    completed_at = Column(DateTime, index=True)

    processed = Column(Integer, default=0)
    saved = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    insufficient = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    candidate_count = Column(Integer, default=0)

    result_count = Column(Integer, default=0)
    no_result_reason = Column(String(64))
    no_result_message = Column(Text)
    status = Column(String(16), nullable=False, default='completed', index=True)

    total_evaluations = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    insufficient_count = Column(Integer, default=0)
    long_count = Column(Integer, default=0)
    cash_count = Column(Integer, default=0)
    win_count = Column(Integer, default=0)
    loss_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)
    win_rate_pct = Column(Float)
    avg_stock_return_pct = Column(Float)
    avg_simulated_return_pct = Column(Float)
    direction_accuracy_pct = Column(Float)
    summary_json = Column(Text)

    __table_args__ = (
        Index('ix_backtest_run_owner_time', 'owner_id', 'run_at'),
        Index('ix_backtest_run_code_time', 'code', 'run_at'),
    )


class RuleBacktestRun(Base):
    """Persisted AI-assisted rule backtest run."""

    __tablename__ = 'rule_backtest_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    code = Column(String(16), nullable=False, index=True)
    strategy_text = Column(Text, nullable=False)
    parsed_strategy_json = Column(Text, nullable=False)
    strategy_hash = Column(String(64), nullable=False, index=True)

    timeframe = Column(String(16), nullable=False, default='daily')
    lookback_bars = Column(Integer, nullable=False, default=252)
    initial_capital = Column(Float, nullable=False, default=100000.0)
    fee_bps = Column(Float, nullable=False, default=0.0)

    parsed_confidence = Column(Float)
    needs_confirmation = Column(Boolean, nullable=False, default=False)
    warnings_json = Column(Text)

    run_at = Column(DateTime, default=datetime.now, index=True)
    completed_at = Column(DateTime, index=True)
    status = Column(String(16), nullable=False, default='completed', index=True)
    no_result_reason = Column(String(64))
    no_result_message = Column(Text)

    trade_count = Column(Integer, default=0)
    win_count = Column(Integer, default=0)
    loss_count = Column(Integer, default=0)
    total_return_pct = Column(Float)
    win_rate_pct = Column(Float)
    avg_trade_return_pct = Column(Float)
    max_drawdown_pct = Column(Float)
    avg_holding_days = Column(Float)
    final_equity = Column(Float)

    summary_json = Column(Text)
    ai_summary = Column(Text)
    equity_curve_json = Column(Text)

    __table_args__ = (
        Index('ix_rule_backtest_owner_time', 'owner_id', 'run_at'),
        Index('ix_rule_backtest_run_code_time', 'code', 'run_at'),
        Index('ix_rule_backtest_run_code_status', 'code', 'status'),
    )


class RuleBacktestTrade(Base):
    """Persisted trade row for a rule backtest run."""

    __tablename__ = 'rule_backtest_trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey('rule_backtest_runs.id'), nullable=False, index=True)
    trade_index = Column(Integer, nullable=False, default=0)
    code = Column(String(16), nullable=False, index=True)

    entry_date = Column(Date, index=True)
    exit_date = Column(Date, index=True)
    entry_price = Column(Float)
    exit_price = Column(Float)
    entry_signal = Column(Text)
    exit_signal = Column(Text)
    return_pct = Column(Float)
    holding_days = Column(Integer)
    entry_rule_json = Column(Text)
    exit_rule_json = Column(Text)
    notes = Column(Text)

    __table_args__ = (
        Index('ix_rule_backtest_trade_run_index', 'run_id', 'trade_index'),
        Index('ix_rule_backtest_trade_code_date', 'code', 'entry_date'),
    )


class MarketScannerRun(Base):
    """Persisted market scanner run metadata."""

    __tablename__ = 'market_scanner_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    scope = Column(String(16), nullable=False, default=OWNERSHIP_SCOPE_USER, index=True)
    market = Column(String(8), nullable=False, default='cn', index=True)
    profile = Column(String(32), nullable=False, default='cn_preopen_v1', index=True)
    universe_name = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default='completed', index=True)

    shortlist_size = Column(Integer, nullable=False, default=5)
    universe_size = Column(Integer, default=0)
    preselected_size = Column(Integer, default=0)
    evaluated_size = Column(Integer, default=0)

    run_at = Column(DateTime, default=datetime.now, index=True)
    completed_at = Column(DateTime, index=True)

    source_summary = Column(String(255))
    summary_json = Column(Text)
    diagnostics_json = Column(Text)
    universe_notes_json = Column(Text)
    scoring_notes_json = Column(Text)

    __table_args__ = (
        Index('ix_market_scanner_run_scope_time', 'scope', 'run_at'),
        Index('ix_market_scanner_run_owner_time', 'owner_id', 'run_at'),
        Index('ix_market_scanner_run_market_time', 'market', 'run_at'),
        Index('ix_market_scanner_run_profile_time', 'profile', 'run_at'),
    )


class MarketScannerCandidate(Base):
    """Persisted shortlisted candidate rows for one market scanner run."""

    __tablename__ = 'market_scanner_candidates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey('market_scanner_runs.id'), nullable=False, index=True)
    symbol = Column(String(16), nullable=False, index=True)
    name = Column(String(64))
    rank = Column(Integer, nullable=False, index=True)
    score = Column(Float, nullable=False)
    quality_hint = Column(String(16))
    reason_summary = Column(Text)

    reasons_json = Column(Text)
    key_metrics_json = Column(Text)
    feature_signals_json = Column(Text)
    risk_notes_json = Column(Text)
    watch_context_json = Column(Text)
    boards_json = Column(Text)
    diagnostics_json = Column(Text)

    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        Index('ix_market_scanner_candidate_run_rank', 'run_id', 'rank'),
        Index('ix_market_scanner_candidate_symbol_created', 'symbol', 'created_at'),
    )


class PortfolioAccount(Base):
    """Portfolio account metadata."""

    __tablename__ = 'portfolio_accounts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    name = Column(String(64), nullable=False)
    broker = Column(String(64))
    market = Column(String(8), nullable=False, default='cn', index=True)  # cn/hk/us
    base_currency = Column(String(8), nullable=False, default='CNY')
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_portfolio_account_owner_active', 'owner_id', 'is_active'),
    )


class PortfolioBrokerConnection(Base):
    """User-owned broker connection metadata for file import and future read-only sync."""

    __tablename__ = 'portfolio_broker_connections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    portfolio_account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    broker_type = Column(String(32), nullable=False, index=True)
    broker_name = Column(String(64))
    connection_name = Column(String(64), nullable=False)
    broker_account_ref = Column(String(128), index=True)
    import_mode = Column(String(16), nullable=False, default='file')
    status = Column(String(16), nullable=False, default='active', index=True)
    last_imported_at = Column(DateTime)
    last_import_source = Column(String(32))
    last_import_fingerprint = Column(String(64))
    sync_metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            'owner_id',
            'broker_type',
            'broker_account_ref',
            name='uix_portfolio_broker_connection_owner_ref',
        ),
        Index('ix_portfolio_broker_connection_owner_status', 'owner_id', 'status'),
    )


class PortfolioBrokerSyncState(Base):
    """Current read-only broker sync snapshot kept separate from ledger source events."""

    __tablename__ = 'portfolio_broker_sync_states'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    broker_connection_id = Column(Integer, ForeignKey('portfolio_broker_connections.id'), nullable=False, index=True)
    portfolio_account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    broker_type = Column(String(32), nullable=False, index=True)
    broker_account_ref = Column(String(128), index=True)
    sync_source = Column(String(32), nullable=False, default='api', index=True)
    sync_status = Column(String(16), nullable=False, default='success', index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    synced_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    base_currency = Column(String(8), nullable=False, default='USD')
    total_cash = Column(Float, nullable=False, default=0.0)
    total_market_value = Column(Float, nullable=False, default=0.0)
    total_equity = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    fx_stale = Column(Boolean, nullable=False, default=False)
    payload_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint('broker_connection_id', name='uix_portfolio_broker_sync_connection'),
        Index('ix_portfolio_broker_sync_owner_account_time', 'owner_id', 'portfolio_account_id', 'synced_at'),
    )


class PortfolioBrokerSyncPosition(Base):
    """Current synced positions for one broker connection."""

    __tablename__ = 'portfolio_broker_sync_positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    broker_connection_id = Column(Integer, ForeignKey('portfolio_broker_connections.id'), nullable=False, index=True)
    portfolio_account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    broker_position_ref = Column(String(64), index=True)
    symbol = Column(String(16), nullable=False, index=True)
    market = Column(String(8), nullable=False, default='us')
    currency = Column(String(8), nullable=False, default='USD')
    quantity = Column(Float, nullable=False, default=0.0)
    avg_cost = Column(Float, nullable=False, default=0.0)
    last_price = Column(Float, nullable=False, default=0.0)
    market_value_base = Column(Float, nullable=False, default=0.0)
    unrealized_pnl_base = Column(Float, nullable=False, default=0.0)
    valuation_currency = Column(String(8), nullable=False, default='USD')
    payload_json = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            'broker_connection_id',
            'symbol',
            'market',
            'currency',
            name='uix_portfolio_broker_sync_position_key',
        ),
        Index('ix_portfolio_broker_sync_position_owner_account', 'owner_id', 'portfolio_account_id'),
    )


class PortfolioBrokerSyncCashBalance(Base):
    """Current synced cash balances for one broker connection."""

    __tablename__ = 'portfolio_broker_sync_cash_balances'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    broker_connection_id = Column(Integer, ForeignKey('portfolio_broker_connections.id'), nullable=False, index=True)
    portfolio_account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    currency = Column(String(8), nullable=False, default='USD')
    amount = Column(Float, nullable=False, default=0.0)
    amount_base = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            'broker_connection_id',
            'currency',
            name='uix_portfolio_broker_sync_cash_key',
        ),
        Index('ix_portfolio_broker_sync_cash_owner_account', 'owner_id', 'portfolio_account_id'),
    )


class PortfolioTrade(Base):
    """Executed trade events used as the source of truth for replay."""

    __tablename__ = 'portfolio_trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    trade_uid = Column(String(128))
    symbol = Column(String(16), nullable=False, index=True)
    market = Column(String(8), nullable=False, default='cn')
    currency = Column(String(8), nullable=False, default='CNY')
    trade_date = Column(Date, nullable=False, index=True)
    side = Column(String(8), nullable=False)  # buy/sell
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    fee = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    note = Column(String(255))
    dedup_hash = Column(String(64), index=True)
    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        UniqueConstraint('account_id', 'trade_uid', name='uix_portfolio_trade_uid'),
        UniqueConstraint('account_id', 'dedup_hash', name='uix_portfolio_trade_dedup_hash'),
        Index('ix_portfolio_trade_account_date', 'account_id', 'trade_date'),
    )


class PortfolioCashLedger(Base):
    """Cash in/out events."""

    __tablename__ = 'portfolio_cash_ledger'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    event_date = Column(Date, nullable=False, index=True)
    direction = Column(String(8), nullable=False)  # in/out
    amount = Column(Float, nullable=False)
    currency = Column(String(8), nullable=False, default='CNY')
    note = Column(String(255))
    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        Index('ix_portfolio_cash_account_date', 'account_id', 'event_date'),
    )


class PortfolioCorporateAction(Base):
    """Corporate actions that impact cash or share quantity."""

    __tablename__ = 'portfolio_corporate_actions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    symbol = Column(String(16), nullable=False, index=True)
    market = Column(String(8), nullable=False, default='cn')
    currency = Column(String(8), nullable=False, default='CNY')
    effective_date = Column(Date, nullable=False, index=True)
    action_type = Column(String(24), nullable=False)  # cash_dividend/split_adjustment
    cash_dividend_per_share = Column(Float)
    split_ratio = Column(Float)
    note = Column(String(255))
    created_at = Column(DateTime, default=datetime.now, index=True)

    __table_args__ = (
        Index('ix_portfolio_ca_account_date', 'account_id', 'effective_date'),
    )


class PortfolioPosition(Base):
    """Latest replayed position snapshot for each symbol in one account."""

    __tablename__ = 'portfolio_positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    cost_method = Column(String(8), nullable=False, default='fifo')
    symbol = Column(String(16), nullable=False, index=True)
    market = Column(String(8), nullable=False, default='cn')
    currency = Column(String(8), nullable=False, default='CNY')
    quantity = Column(Float, nullable=False, default=0.0)
    avg_cost = Column(Float, nullable=False, default=0.0)
    total_cost = Column(Float, nullable=False, default=0.0)
    last_price = Column(Float, nullable=False, default=0.0)
    market_value_base = Column(Float, nullable=False, default=0.0)
    unrealized_pnl_base = Column(Float, nullable=False, default=0.0)
    valuation_currency = Column(String(8), nullable=False, default='CNY')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)

    __table_args__ = (
        UniqueConstraint(
            'account_id',
            'symbol',
            'market',
            'currency',
            'cost_method',
            name='uix_portfolio_position_account_symbol_market_currency',
        ),
    )


class PortfolioPositionLot(Base):
    """Lot-level remaining quantities used by FIFO replay."""

    __tablename__ = 'portfolio_position_lots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    cost_method = Column(String(8), nullable=False, default='fifo')
    symbol = Column(String(16), nullable=False, index=True)
    market = Column(String(8), nullable=False, default='cn')
    currency = Column(String(8), nullable=False, default='CNY')
    open_date = Column(Date, nullable=False, index=True)
    remaining_quantity = Column(Float, nullable=False, default=0.0)
    unit_cost = Column(Float, nullable=False, default=0.0)
    source_trade_id = Column(Integer, ForeignKey('portfolio_trades.id'))
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)

    __table_args__ = (
        Index('ix_portfolio_lot_account_symbol', 'account_id', 'symbol'),
    )


class PortfolioDailySnapshot(Base):
    """Daily account snapshot generated by read-time replay."""

    __tablename__ = 'portfolio_daily_snapshots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('portfolio_accounts.id'), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    cost_method = Column(String(8), nullable=False, default='fifo')  # fifo/avg
    base_currency = Column(String(8), nullable=False, default='CNY')
    total_cash = Column(Float, nullable=False, default=0.0)
    total_market_value = Column(Float, nullable=False, default=0.0)
    total_equity = Column(Float, nullable=False, default=0.0)
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    fee_total = Column(Float, nullable=False, default=0.0)
    tax_total = Column(Float, nullable=False, default=0.0)
    fx_stale = Column(Boolean, nullable=False, default=False)
    payload = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            'account_id',
            'snapshot_date',
            'cost_method',
            name='uix_portfolio_snapshot_account_date_method',
        ),
    )


class PortfolioFxRate(Base):
    """Cached FX rates used for cross-currency portfolio conversion."""

    __tablename__ = 'portfolio_fx_rates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_currency = Column(String(8), nullable=False, index=True)
    to_currency = Column(String(8), nullable=False, index=True)
    rate_date = Column(Date, nullable=False, index=True)
    rate = Column(Float, nullable=False)
    source = Column(String(32), nullable=False, default='manual')
    is_stale = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            'from_currency',
            'to_currency',
            'rate_date',
            name='uix_portfolio_fx_pair_date',
        ),
    )


class ConversationMessage(Base):
    """
    Agent 对话历史记录表
    """
    __tablename__ = 'conversation_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), index=True, nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now, index=True)


class ConversationSessionRecord(Base):
    """First-class chat session ownership row for user-scoped conversation history."""

    __tablename__ = 'conversation_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, unique=True, index=True)
    owner_id = Column(String(64), ForeignKey('app_users.id'), index=True, default=BOOTSTRAP_ADMIN_USER_ID)
    title = Column(String(255))
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)

    __table_args__ = (
        Index('ix_conversation_session_owner_updated', 'owner_id', 'updated_at'),
    )


class LLMUsage(Base):
    """One row per litellm.completion() call — token-usage audit log."""

    __tablename__ = 'llm_usage'

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 'analysis' | 'agent' | 'market_review'
    call_type = Column(String(32), nullable=False, index=True)
    model = Column(String(128), nullable=False)
    stock_code = Column(String(16), nullable=True)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    called_at = Column(DateTime, default=datetime.now, index=True)


class DatabaseManager:
    """
    数据库管理器 - 单例模式
    
    职责：
    1. 管理数据库连接池
    2. 提供 Session 上下文管理
    3. 封装数据存取操作
    """
    
    _instance: Optional['DatabaseManager'] = None
    _initialized: bool = False
    
    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_url: Optional[str] = None):
        """
        初始化数据库管理器
        
        Args:
            db_url: 数据库连接 URL（可选，默认从配置读取）
        """
        if getattr(self, '_initialized', False):
            return
        
        if db_url is None:
            config = get_config()
            db_url = config.get_db_url()
        else:
            config = get_config()

        # 创建数据库引擎
        self._engine = create_engine(
            db_url,
            echo=False,  # 设为 True 可查看 SQL 语句
            pool_pre_ping=True,  # 连接健康检查
        )
        
        # 创建 Session 工厂
        self._SessionLocal = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
        )
        
        # 创建所有表
        Base.metadata.create_all(self._engine)
        self._run_multi_user_migrations()
        self._phase_a_store: Optional[PostgresPhaseAStore] = None
        self._phase_a_enabled = False
        self._phase_b_store: Optional[PostgresPhaseBStore] = None
        self._phase_b_enabled = False
        self._phase_c_store: Optional[PostgresPhaseCStore] = None
        self._phase_c_enabled = False
        self._phase_d_store: Optional[PostgresPhaseDStore] = None
        self._phase_d_enabled = False
        self._phase_e_store: Optional[PostgresPhaseEStore] = None
        self._phase_e_enabled = False
        phase_a_url = str(getattr(config, "postgres_phase_a_url", "") or "").strip()
        if phase_a_url:
            try:
                self._phase_a_store = PostgresPhaseAStore(
                    phase_a_url,
                    auto_apply_schema=bool(getattr(config, "postgres_phase_a_apply_schema", True)),
                )
                self._phase_a_enabled = True
                self._phase_b_store = PostgresPhaseBStore(
                    phase_a_url,
                    auto_apply_schema=bool(getattr(config, "postgres_phase_a_apply_schema", True)),
                )
                self._phase_b_enabled = True
                self._phase_c_store = PostgresPhaseCStore(
                    phase_a_url,
                    auto_apply_schema=bool(getattr(config, "postgres_phase_a_apply_schema", True)),
                )
                self._phase_c_enabled = True
                self._phase_d_store = PostgresPhaseDStore(
                    phase_a_url,
                    auto_apply_schema=bool(getattr(config, "postgres_phase_a_apply_schema", True)),
                )
                self._phase_d_enabled = True
                self._phase_e_store = PostgresPhaseEStore(
                    phase_a_url,
                    auto_apply_schema=bool(getattr(config, "postgres_phase_a_apply_schema", True)),
                )
                self._phase_e_enabled = True
            except Exception as exc:
                raise RuntimeError(
                    "Failed to initialize PostgreSQL Phase A/B/C/D/E storage. "
                    "Check POSTGRES_PHASE_A_URL / POSTGRES_PHASE_A_APPLY_SCHEMA configuration."
                ) from exc

        self._initialized = True
        logger.info(f"数据库初始化完成: {db_url}")

        # 注册退出钩子，确保程序退出时关闭数据库连接
        atexit.register(DatabaseManager._cleanup_engine, self._engine)
    
    @classmethod
    def get_instance(cls) -> 'DatabaseManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（用于测试）"""
        if cls._instance is not None:
            if getattr(cls._instance, "_phase_a_store", None) is not None:
                cls._instance._phase_a_store.dispose()
            if getattr(cls._instance, "_phase_b_store", None) is not None:
                cls._instance._phase_b_store.dispose()
            if getattr(cls._instance, "_phase_c_store", None) is not None:
                cls._instance._phase_c_store.dispose()
            if getattr(cls._instance, "_phase_d_store", None) is not None:
                cls._instance._phase_d_store.dispose()
            if getattr(cls._instance, "_phase_e_store", None) is not None:
                cls._instance._phase_e_store.dispose()
            if hasattr(cls._instance, '_engine') and cls._instance._engine is not None:
                cls._instance._engine.dispose()
            cls._instance._initialized = False
            cls._instance = None

    @classmethod
    def _cleanup_engine(cls, engine) -> None:
        """
        清理数据库引擎（atexit 钩子）

        确保程序退出时关闭所有数据库连接，避免 ResourceWarning

        Args:
            engine: SQLAlchemy 引擎对象
        """
        try:
            if engine is not None:
                engine.dispose()
                logger.debug("数据库引擎已清理")
        except Exception as e:
            logger.warning(f"清理数据库引擎时出错: {e}")
    
    def get_session(self) -> Session:
        """
        获取数据库 Session
        
        使用示例:
            with db.get_session() as session:
                # 执行查询
                session.commit()  # 如果需要
        """
        if not getattr(self, '_initialized', False) or not hasattr(self, '_SessionLocal'):
            raise RuntimeError(
                "DatabaseManager 未正确初始化。"
                "请确保通过 DatabaseManager.get_instance() 获取实例。"
            )
        session = self._SessionLocal()
        try:
            return session
        except Exception:
            session.close()
            raise

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _run_multi_user_migrations(self) -> None:
        """Apply lightweight SQLite-safe schema migrations for Phase 1 ownership."""
        bootstrap_user_id = BOOTSTRAP_ADMIN_USER_ID
        with self._engine.begin() as conn:
            self._ensure_bootstrap_admin_user_row(conn)

            self._add_column_if_missing(conn, "analysis_history", "owner_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "backtest_results", "owner_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "backtest_runs", "owner_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "rule_backtest_runs", "owner_id", "VARCHAR(64)")
            self._add_column_if_missing(conn, "market_scanner_runs", "owner_id", "VARCHAR(64)")
            self._add_column_if_missing(
                conn,
                "market_scanner_runs",
                "scope",
                f"VARCHAR(16) NOT NULL DEFAULT '{OWNERSHIP_SCOPE_USER}'",
            )

            self._create_index_if_missing(
                conn,
                "ix_analysis_owner_created",
                "analysis_history",
                "owner_id, created_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_analysis_owner_query",
                "analysis_history",
                "owner_id, query_id",
            )
            self._create_index_if_missing(
                conn,
                "ix_backtest_result_owner_evaluated",
                "backtest_results",
                "owner_id, evaluated_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_backtest_run_owner_time",
                "backtest_runs",
                "owner_id, run_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_rule_backtest_owner_time",
                "rule_backtest_runs",
                "owner_id, run_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_market_scanner_run_scope_time",
                "market_scanner_runs",
                "scope, run_at",
            )
            self._create_index_if_missing(
                conn,
                "ix_market_scanner_run_owner_time",
                "market_scanner_runs",
                "owner_id, run_at",
            )

            self._migrate_backtest_summaries_table(conn, bootstrap_user_id=bootstrap_user_id)

            conn.exec_driver_sql(
                "UPDATE portfolio_accounts SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            conn.exec_driver_sql(
                "UPDATE analysis_history SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            conn.exec_driver_sql(
                "UPDATE backtest_results SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            conn.exec_driver_sql(
                "UPDATE backtest_runs SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            conn.exec_driver_sql(
                "UPDATE rule_backtest_runs SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )

            self._backfill_market_scanner_ownership(conn, bootstrap_user_id=bootstrap_user_id)
            self._backfill_conversation_sessions(conn, bootstrap_user_id=bootstrap_user_id)

    @staticmethod
    def _table_columns(conn, table_name: str) -> set[str]:
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row[1]) for row in rows}

    def _add_column_if_missing(self, conn, table_name: str, column_name: str, column_sql: str) -> None:
        if column_name in self._table_columns(conn, table_name):
            return
        conn.exec_driver_sql(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
        )

    @staticmethod
    def _create_index_if_missing(conn, index_name: str, table_name: str, columns_sql: str) -> None:
        conn.exec_driver_sql(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_sql})"
        )

    @staticmethod
    def _ensure_bootstrap_admin_user_row(conn) -> None:
        now = datetime.now()
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO app_users (
                id,
                username,
                display_name,
                password_hash,
                role,
                is_active,
                created_at,
                updated_at
            ) VALUES (
                :id,
                :username,
                :display_name,
                NULL,
                :role,
                1,
                :created_at,
                :updated_at
            )
            """,
            {
                "id": BOOTSTRAP_ADMIN_USER_ID,
                "username": BOOTSTRAP_ADMIN_USERNAME,
                "display_name": BOOTSTRAP_ADMIN_DISPLAY_NAME,
                "role": ROLE_ADMIN,
                "created_at": now,
                "updated_at": now,
            },
        )

    def _migrate_backtest_summaries_table(self, conn, *, bootstrap_user_id: str) -> None:
        columns = self._table_columns(conn, "backtest_summaries")
        if "owner_id" in columns:
            conn.exec_driver_sql(
                "UPDATE backtest_summaries SET owner_id = :owner_id "
                "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
                {"owner_id": bootstrap_user_id},
            )
            return

        conn.exec_driver_sql(
            """
            CREATE TABLE backtest_summaries__new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id VARCHAR(64) NOT NULL,
                scope VARCHAR(16) NOT NULL,
                code VARCHAR(16),
                eval_window_days INTEGER NOT NULL DEFAULT 10,
                engine_version VARCHAR(16) NOT NULL DEFAULT 'v1',
                computed_at DATETIME,
                total_evaluations INTEGER DEFAULT 0,
                completed_count INTEGER DEFAULT 0,
                insufficient_count INTEGER DEFAULT 0,
                long_count INTEGER DEFAULT 0,
                cash_count INTEGER DEFAULT 0,
                win_count INTEGER DEFAULT 0,
                loss_count INTEGER DEFAULT 0,
                neutral_count INTEGER DEFAULT 0,
                direction_accuracy_pct FLOAT,
                win_rate_pct FLOAT,
                neutral_rate_pct FLOAT,
                avg_stock_return_pct FLOAT,
                avg_simulated_return_pct FLOAT,
                stop_loss_trigger_rate FLOAT,
                take_profit_trigger_rate FLOAT,
                ambiguous_rate FLOAT,
                avg_days_to_first_hit FLOAT,
                advice_breakdown_json TEXT,
                diagnostics_json TEXT,
                CONSTRAINT uix_backtest_summary_owner_scope_code_window_version
                    UNIQUE (owner_id, scope, code, eval_window_days, engine_version)
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO backtest_summaries__new (
                id,
                owner_id,
                scope,
                code,
                eval_window_days,
                engine_version,
                computed_at,
                total_evaluations,
                completed_count,
                insufficient_count,
                long_count,
                cash_count,
                win_count,
                loss_count,
                neutral_count,
                direction_accuracy_pct,
                win_rate_pct,
                neutral_rate_pct,
                avg_stock_return_pct,
                avg_simulated_return_pct,
                stop_loss_trigger_rate,
                take_profit_trigger_rate,
                ambiguous_rate,
                avg_days_to_first_hit,
                advice_breakdown_json,
                diagnostics_json
            )
            SELECT
                id,
                :owner_id,
                scope,
                code,
                eval_window_days,
                engine_version,
                computed_at,
                total_evaluations,
                completed_count,
                insufficient_count,
                long_count,
                cash_count,
                win_count,
                loss_count,
                neutral_count,
                direction_accuracy_pct,
                win_rate_pct,
                neutral_rate_pct,
                avg_stock_return_pct,
                avg_simulated_return_pct,
                stop_loss_trigger_rate,
                take_profit_trigger_rate,
                ambiguous_rate,
                avg_days_to_first_hit,
                advice_breakdown_json,
                diagnostics_json
            FROM backtest_summaries
            """,
            {"owner_id": bootstrap_user_id},
        )
        conn.exec_driver_sql("DROP TABLE backtest_summaries")
        conn.exec_driver_sql("ALTER TABLE backtest_summaries__new RENAME TO backtest_summaries")

    def _backfill_market_scanner_ownership(self, conn, *, bootstrap_user_id: str) -> None:
        rows = conn.exec_driver_sql(
            """
            SELECT id, owner_id, scope, summary_json, diagnostics_json
            FROM market_scanner_runs
            ORDER BY id ASC
            """
        ).fetchall()
        for row in rows:
            row_id = int(row[0])
            owner_id = str(row[1] or "").strip() or None
            current_scope = str(row[2] or "").strip().lower()
            summary = self._safe_json_loads(row[3], {})
            diagnostics = self._safe_json_loads(row[4], {})
            operation = diagnostics.get("operation") if isinstance(diagnostics, dict) else {}
            trigger_mode = ""
            request_source = ""
            if isinstance(operation, dict):
                trigger_mode = str(operation.get("trigger_mode") or "").strip().lower()
                request_source = str(operation.get("request_source") or "").strip().lower()
            if not trigger_mode and isinstance(summary, dict):
                trigger_mode = str(summary.get("trigger_mode") or "").strip().lower()
                request_source = request_source or str(summary.get("request_source") or "").strip().lower()

            inferred_scope = OWNERSHIP_SCOPE_SYSTEM if (
                trigger_mode == "scheduled" or request_source in {"scheduler", "system"}
            ) else OWNERSHIP_SCOPE_USER
            if inferred_scope == OWNERSHIP_SCOPE_SYSTEM:
                next_scope = OWNERSHIP_SCOPE_SYSTEM
            elif current_scope in {OWNERSHIP_SCOPE_USER, OWNERSHIP_SCOPE_SYSTEM}:
                next_scope = current_scope
            else:
                next_scope = inferred_scope
            next_owner_id = None if next_scope == OWNERSHIP_SCOPE_SYSTEM else (owner_id or bootstrap_user_id)
            conn.exec_driver_sql(
                "UPDATE market_scanner_runs SET owner_id = :owner_id, scope = :scope WHERE id = :id",
                {"id": row_id, "owner_id": next_owner_id, "scope": next_scope},
            )

    def _backfill_conversation_sessions(self, conn, *, bootstrap_user_id: str) -> None:
        rows = conn.exec_driver_sql(
            """
            SELECT
                session_id,
                MIN(created_at) AS created_at,
                MAX(created_at) AS updated_at
            FROM conversation_messages
            GROUP BY session_id
            """
        ).fetchall()
        for row in rows:
            session_id = str(row[0] or "").strip()
            if not session_id:
                continue
            title_row = conn.exec_driver_sql(
                """
                SELECT content
                FROM conversation_messages
                WHERE session_id = :session_id AND role = 'user'
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """,
                {"session_id": session_id},
            ).fetchone()
            title = str(title_row[0])[:255] if title_row and title_row[0] else None
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO conversation_sessions (
                    session_id,
                    owner_id,
                    title,
                    created_at,
                    updated_at
                ) VALUES (
                    :session_id,
                    :owner_id,
                    :title,
                    :created_at,
                    :updated_at
                )
                """,
                {
                    "session_id": session_id,
                    "owner_id": bootstrap_user_id,
                    "title": title,
                    "created_at": row[1],
                    "updated_at": row[2],
                },
            )
        conn.exec_driver_sql(
            "UPDATE conversation_sessions SET owner_id = :owner_id "
            "WHERE owner_id IS NULL OR TRIM(owner_id) = ''",
            {"owner_id": bootstrap_user_id},
        )

    @staticmethod
    def _safe_json_loads(value: Any, fallback: Any) -> Any:
        if not value:
            return fallback
        try:
            return json.loads(value)
        except Exception:
            return fallback

    def _sqlite_get_app_user(self, user_id: str) -> Optional[AppUser]:
        normalized = str(user_id or "").strip()
        if not normalized:
            return None
        with self.get_session() as session:
            return session.execute(
                select(AppUser).where(AppUser.id == normalized).limit(1)
            ).scalar_one_or_none()

    def _sqlite_get_app_user_by_username(self, username: str) -> Optional[AppUser]:
        normalized = str(username or "").strip()
        if not normalized:
            return None
        with self.get_session() as session:
            return session.execute(
                select(AppUser).where(AppUser.username == normalized).limit(1)
            ).scalar_one_or_none()

    def _sqlite_create_or_update_app_user(
        self,
        *,
        user_id: str,
        username: str,
        role: str = ROLE_USER,
        display_name: Optional[str] = None,
        password_hash: Optional[str] = None,
        is_active: bool = True,
    ) -> AppUser:
        normalized_id = str(user_id or "").strip()
        normalized_username = str(username or "").strip()
        if not normalized_id:
            raise ValueError("user_id is required")
        if not normalized_username:
            raise ValueError("username is required")
        normalized_role = normalize_role(role)

        with self.get_session() as session:
            row = session.execute(
                select(AppUser).where(AppUser.id == normalized_id).limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = AppUser(
                    id=normalized_id,
                    username=normalized_username,
                    display_name=(display_name or "").strip() or None,
                    password_hash=password_hash,
                    role=normalized_role,
                    is_active=bool(is_active),
                )
                session.add(row)
            else:
                row.username = normalized_username
                row.display_name = (display_name or "").strip() or row.display_name
                row.password_hash = password_hash if password_hash is not None else row.password_hash
                row.role = normalized_role
                row.is_active = bool(is_active)
                row.updated_at = datetime.now()
            session.commit()
            session.refresh(row)
            return row

    def _sqlite_get_app_user_session(self, session_id: str) -> Optional[AppUserSession]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return None
        with self.get_session() as session:
            return session.execute(
                select(AppUserSession).where(AppUserSession.session_id == normalized_session_id).limit(1)
            ).scalar_one_or_none()

    def _sqlite_create_or_update_app_user_session(
        self,
        *,
        session_id: str,
        user_id: str,
        expires_at: datetime,
        created_at: Optional[datetime] = None,
        last_seen_at: Optional[datetime] = None,
        revoked_at: Optional[datetime] = None,
    ) -> AppUserSession:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            raise ValueError("session_id is required")
        resolved_user_id = self.require_user_id(user_id)
        if not isinstance(expires_at, datetime):
            raise ValueError("expires_at must be a datetime")

        with self.get_session() as session:
            row = session.execute(
                select(AppUserSession).where(AppUserSession.session_id == normalized_session_id).limit(1)
            ).scalar_one_or_none()
            now = datetime.now()
            if row is None:
                row = AppUserSession(
                    session_id=normalized_session_id,
                    user_id=resolved_user_id,
                    created_at=created_at or now,
                    last_seen_at=last_seen_at or now,
                    expires_at=expires_at,
                    revoked_at=revoked_at,
                )
                session.add(row)
            else:
                row.user_id = resolved_user_id
                row.last_seen_at = last_seen_at or now
                row.expires_at = expires_at
                row.revoked_at = revoked_at
            session.commit()
            session.refresh(row)
            return row

    def _sqlite_touch_app_user_session(self, session_id: str) -> bool:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        with self.get_session() as session:
            row = session.execute(
                select(AppUserSession).where(AppUserSession.session_id == normalized_session_id).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return False
            row.last_seen_at = datetime.now()
            session.commit()
            return True

    def _sqlite_revoke_app_user_session(self, session_id: str) -> bool:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        with self.get_session() as session:
            row = session.execute(
                select(AppUserSession).where(AppUserSession.session_id == normalized_session_id).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return False
            row.revoked_at = datetime.now()
            row.last_seen_at = datetime.now()
            session.commit()
            return True

    def _sqlite_revoke_all_app_user_sessions(self, user_id: str) -> int:
        resolved_user_id = self.require_user_id(user_id)
        with self.get_session() as session:
            rows = session.execute(
                select(AppUserSession).where(
                    and_(
                        AppUserSession.user_id == resolved_user_id,
                        AppUserSession.revoked_at.is_(None),
                    )
                )
            ).scalars().all()
            if not rows:
                return 0
            now = datetime.now()
            for row in rows:
                row.revoked_at = now
                row.last_seen_at = now
            session.commit()
            return len(rows)

    def _sqlite_get_user_preference_row(self, user_id: str) -> Optional[UserPreference]:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return None
        with self.get_session() as session:
            return session.execute(
                select(UserPreference).where(UserPreference.user_id == normalized_user_id).limit(1)
            ).scalar_one_or_none()

    def _collect_known_user_ids(self) -> List[str]:
        with self.get_session() as session:
            sqlite_user_ids = {
                str(value)
                for value in session.execute(
                    select(AppUser.id).where(AppUser.id != BOOTSTRAP_ADMIN_USER_ID)
                ).scalars().all()
                if str(value or "").strip()
            }
        if self._phase_a_enabled and self._phase_a_store is not None:
            sqlite_user_ids.update(self._phase_a_store.list_non_bootstrap_user_ids())
        return sorted(sqlite_user_ids)

    def _sync_phase_a_user_from_legacy(self, row: AppUser) -> Any:
        if not self._phase_a_enabled or self._phase_a_store is None or row is None:
            return row
        return self._phase_a_store.upsert_app_user(
            user_id=str(row.id),
            username=str(row.username),
            role=str(row.role),
            display_name=getattr(row, "display_name", None),
            password_hash=getattr(row, "password_hash", None),
            is_active=bool(getattr(row, "is_active", True)),
            created_at=getattr(row, "created_at", None),
            updated_at=getattr(row, "updated_at", None),
        )

    def _sync_phase_a_session_from_legacy(self, row: AppUserSession) -> Any:
        if not self._phase_a_enabled or self._phase_a_store is None or row is None:
            return row
        user_row = self.get_app_user(str(row.user_id))
        if user_row is None:
            return None
        return self._phase_a_store.upsert_app_user_session(
            session_id=str(row.session_id),
            user_id=str(row.user_id),
            expires_at=row.expires_at,
            created_at=getattr(row, "created_at", None),
            last_seen_at=getattr(row, "last_seen_at", None),
            revoked_at=getattr(row, "revoked_at", None),
        )

    def _sync_phase_a_notification_preferences_from_legacy(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not self._phase_a_enabled or self._phase_a_store is None:
            return None
        row = self._sqlite_get_user_preference_row(user_id)
        if row is None:
            return None
        payload = self._safe_json_loads(
            getattr(row, "notification_preferences_json", None),
            {},
        )
        if not isinstance(payload, dict):
            return None
        self.get_app_user(user_id)
        return self._phase_a_store.import_legacy_notification_preferences(
            user_id,
            payload,
            updated_at=getattr(row, "updated_at", None),
        )

    def ensure_bootstrap_admin_user(self) -> AppUser:
        existing = self.get_app_user(BOOTSTRAP_ADMIN_USER_ID)
        if existing is not None:
            return existing
        return self.create_or_update_app_user(
            user_id=BOOTSTRAP_ADMIN_USER_ID,
            username=BOOTSTRAP_ADMIN_USERNAME,
            role=ROLE_ADMIN,
            display_name=BOOTSTRAP_ADMIN_DISPLAY_NAME,
            password_hash=None,
            is_active=True,
        )

    def get_default_owner_id(self) -> str:
        user = self.ensure_bootstrap_admin_user()
        return str(user.id)

    def require_user_id(self, owner_id: Optional[str], *, allow_none: bool = False) -> Optional[str]:
        normalized = str(owner_id or "").strip()
        if not normalized:
            return None if allow_none else self.get_default_owner_id()
        if self.get_app_user(normalized) is None:
            raise ValueError(f"Unknown app user: {normalized}")
        return normalized

    def get_app_user(self, user_id: str) -> Optional[AppUser]:
        normalized = str(user_id or "").strip()
        if not normalized:
            return None
        if self._phase_a_enabled and self._phase_a_store is not None:
            row = self._phase_a_store.get_app_user(normalized)
            if row is not None:
                return row
            legacy_row = self._sqlite_get_app_user(normalized)
            if legacy_row is None:
                return None
            return self._sync_phase_a_user_from_legacy(legacy_row)
        return self._sqlite_get_app_user(normalized)

    def get_app_user_by_username(self, username: str) -> Optional[AppUser]:
        normalized = str(username or "").strip()
        if not normalized:
            return None
        if self._phase_a_enabled and self._phase_a_store is not None:
            row = self._phase_a_store.get_app_user_by_username(normalized)
            if row is not None:
                return row
            legacy_row = self._sqlite_get_app_user_by_username(normalized)
            if legacy_row is None:
                return None
            return self._sync_phase_a_user_from_legacy(legacy_row)
        return self._sqlite_get_app_user_by_username(normalized)

    def create_or_update_app_user(
        self,
        *,
        user_id: str,
        username: str,
        role: str = ROLE_USER,
        display_name: Optional[str] = None,
        password_hash: Optional[str] = None,
        is_active: bool = True,
    ) -> AppUser:
        normalized_id = str(user_id or "").strip()
        normalized_username = str(username or "").strip()
        if not normalized_id:
            raise ValueError("user_id is required")
        if not normalized_username:
            raise ValueError("username is required")
        normalized_role = normalize_role(role)

        if self._phase_a_enabled and self._phase_a_store is not None:
            return self._phase_a_store.upsert_app_user(
                user_id=normalized_id,
                username=normalized_username,
                role=normalized_role,
                display_name=display_name,
                password_hash=password_hash,
                is_active=bool(is_active),
            )

        return self._sqlite_create_or_update_app_user(
            user_id=normalized_id,
            username=normalized_username,
            role=normalized_role,
            display_name=display_name,
            password_hash=password_hash,
            is_active=bool(is_active),
        )

    def create_app_user_session(
        self,
        *,
        session_id: str,
        user_id: str,
        expires_at: datetime,
    ) -> AppUserSession:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            raise ValueError("session_id is required")
        resolved_user_id = self.require_user_id(user_id)
        if not isinstance(expires_at, datetime):
            raise ValueError("expires_at must be a datetime")

        if self._phase_a_enabled and self._phase_a_store is not None:
            return self._phase_a_store.upsert_app_user_session(
                session_id=normalized_session_id,
                user_id=resolved_user_id,
                expires_at=expires_at,
                revoked_at=None,
            )

        return self._sqlite_create_or_update_app_user_session(
            session_id=normalized_session_id,
            user_id=resolved_user_id,
            expires_at=expires_at,
            revoked_at=None,
        )

    def get_app_user_session(self, session_id: str) -> Optional[AppUserSession]:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return None
        if self._phase_a_enabled and self._phase_a_store is not None:
            row = self._phase_a_store.get_app_user_session(normalized_session_id)
            if row is not None:
                return row
            legacy_row = self._sqlite_get_app_user_session(normalized_session_id)
            if legacy_row is None:
                return None
            return self._sync_phase_a_session_from_legacy(legacy_row)
        return self._sqlite_get_app_user_session(normalized_session_id)

    def touch_app_user_session(self, session_id: str) -> bool:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        if self._phase_a_enabled and self._phase_a_store is not None:
            if self._phase_a_store.touch_app_user_session(normalized_session_id):
                return True
            legacy_row = self._sqlite_get_app_user_session(normalized_session_id)
            if legacy_row is None:
                return False
            synced = self._sync_phase_a_session_from_legacy(legacy_row)
            if synced is None:
                return False
            return self._phase_a_store.touch_app_user_session(normalized_session_id)
        return self._sqlite_touch_app_user_session(normalized_session_id)

    def revoke_app_user_session(self, session_id: str) -> bool:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return False
        if self._phase_a_enabled and self._phase_a_store is not None:
            phase_a_revoked = self._phase_a_store.revoke_app_user_session(normalized_session_id)
            legacy_revoked = self._sqlite_revoke_app_user_session(normalized_session_id)
            if phase_a_revoked:
                return True
            legacy_row = self._sqlite_get_app_user_session(normalized_session_id)
            if legacy_row is not None:
                self._sync_phase_a_session_from_legacy(self._sqlite_get_app_user_session(normalized_session_id))
                return self._phase_a_store.revoke_app_user_session(normalized_session_id) or legacy_revoked
            return legacy_revoked
        return self._sqlite_revoke_app_user_session(normalized_session_id)

    def revoke_all_app_user_sessions(self, user_id: str) -> int:
        resolved_user_id = self.require_user_id(user_id)
        if self._phase_a_enabled and self._phase_a_store is not None:
            phase_a_count = self._phase_a_store.revoke_all_app_user_sessions(resolved_user_id)
            legacy_count = self._sqlite_revoke_all_app_user_sessions(resolved_user_id)
            return max(phase_a_count, legacy_count)
        return self._sqlite_revoke_all_app_user_sessions(resolved_user_id)

    def factory_reset_non_bootstrap_state(self) -> Dict[str, Any]:
        """Clear bounded non-bootstrap user-owned state while preserving system bootstrap rows."""
        user_ids = self._collect_known_user_ids()
        if not user_ids:
            return {
                "cleared": [],
                "counts": {},
            }

        with self.session_scope() as session:
            counts: Dict[str, int] = {}

            session_ids = session.execute(
                select(ConversationSessionRecord.session_id)
                .where(ConversationSessionRecord.owner_id.in_(user_ids))
            ).scalars().all()
            if session_ids:
                counts["conversation_messages"] = session.execute(
                    delete(ConversationMessage).where(ConversationMessage.session_id.in_(session_ids))
                ).rowcount or 0
            else:
                counts["conversation_messages"] = 0
            counts["conversation_sessions"] = session.execute(
                delete(ConversationSessionRecord).where(ConversationSessionRecord.owner_id.in_(user_ids))
            ).rowcount or 0

            analysis_ids = session.execute(
                select(AnalysisHistory.id).where(AnalysisHistory.owner_id.in_(user_ids))
            ).scalars().all()
            if analysis_ids:
                counts["backtest_results"] = session.execute(
                    delete(BacktestResult).where(BacktestResult.analysis_history_id.in_(analysis_ids))
                ).rowcount or 0
            else:
                counts["backtest_results"] = 0
            counts["analysis_history"] = session.execute(
                delete(AnalysisHistory).where(AnalysisHistory.owner_id.in_(user_ids))
            ).rowcount or 0
            counts["backtest_summaries"] = session.execute(
                delete(BacktestSummary).where(BacktestSummary.owner_id.in_(user_ids))
            ).rowcount or 0
            counts["backtest_runs"] = session.execute(
                delete(BacktestRun).where(BacktestRun.owner_id.in_(user_ids))
            ).rowcount or 0

            rule_run_ids = session.execute(
                select(RuleBacktestRun.id).where(RuleBacktestRun.owner_id.in_(user_ids))
            ).scalars().all()
            if rule_run_ids:
                counts["rule_backtest_trades"] = session.execute(
                    delete(RuleBacktestTrade).where(RuleBacktestTrade.run_id.in_(rule_run_ids))
                ).rowcount or 0
            else:
                counts["rule_backtest_trades"] = 0
            counts["rule_backtest_runs"] = session.execute(
                delete(RuleBacktestRun).where(RuleBacktestRun.owner_id.in_(user_ids))
            ).rowcount or 0

            scanner_run_ids = session.execute(
                select(MarketScannerRun.id).where(MarketScannerRun.owner_id.in_(user_ids))
            ).scalars().all()
            if scanner_run_ids:
                counts["scanner_candidates"] = session.execute(
                    delete(MarketScannerCandidate).where(MarketScannerCandidate.run_id.in_(scanner_run_ids))
                ).rowcount or 0
            else:
                counts["scanner_candidates"] = 0
            counts["scanner_runs"] = session.execute(
                delete(MarketScannerRun).where(MarketScannerRun.owner_id.in_(user_ids))
            ).rowcount or 0

            account_ids = session.execute(
                select(PortfolioAccount.id).where(PortfolioAccount.owner_id.in_(user_ids))
            ).scalars().all()
            connection_ids = session.execute(
                select(PortfolioBrokerConnection.id).where(PortfolioBrokerConnection.owner_id.in_(user_ids))
            ).scalars().all()

            counts["portfolio_sync_positions"] = session.execute(
                delete(PortfolioBrokerSyncPosition).where(PortfolioBrokerSyncPosition.owner_id.in_(user_ids))
            ).rowcount or 0
            counts["portfolio_sync_cash_balances"] = session.execute(
                delete(PortfolioBrokerSyncCashBalance).where(PortfolioBrokerSyncCashBalance.owner_id.in_(user_ids))
            ).rowcount or 0
            counts["portfolio_sync_states"] = session.execute(
                delete(PortfolioBrokerSyncState).where(PortfolioBrokerSyncState.owner_id.in_(user_ids))
            ).rowcount or 0

            if account_ids:
                counts["portfolio_position_lots"] = session.execute(
                    delete(PortfolioPositionLot).where(PortfolioPositionLot.account_id.in_(account_ids))
                ).rowcount or 0
                counts["portfolio_positions"] = session.execute(
                    delete(PortfolioPosition).where(PortfolioPosition.account_id.in_(account_ids))
                ).rowcount or 0
                counts["portfolio_daily_snapshots"] = session.execute(
                    delete(PortfolioDailySnapshot).where(PortfolioDailySnapshot.account_id.in_(account_ids))
                ).rowcount or 0
                counts["portfolio_corporate_actions"] = session.execute(
                    delete(PortfolioCorporateAction).where(PortfolioCorporateAction.account_id.in_(account_ids))
                ).rowcount or 0
                counts["portfolio_cash_ledger"] = session.execute(
                    delete(PortfolioCashLedger).where(PortfolioCashLedger.account_id.in_(account_ids))
                ).rowcount or 0
                counts["portfolio_trades"] = session.execute(
                    delete(PortfolioTrade).where(PortfolioTrade.account_id.in_(account_ids))
                ).rowcount or 0
            else:
                counts["portfolio_position_lots"] = 0
                counts["portfolio_positions"] = 0
                counts["portfolio_daily_snapshots"] = 0
                counts["portfolio_corporate_actions"] = 0
                counts["portfolio_cash_ledger"] = 0
                counts["portfolio_trades"] = 0

            if connection_ids:
                counts["portfolio_broker_connections"] = session.execute(
                    delete(PortfolioBrokerConnection).where(PortfolioBrokerConnection.id.in_(connection_ids))
                ).rowcount or 0
            else:
                counts["portfolio_broker_connections"] = 0
            counts["portfolio_accounts"] = session.execute(
                delete(PortfolioAccount).where(PortfolioAccount.owner_id.in_(user_ids))
            ).rowcount or 0

            counts["user_preferences"] = session.execute(
                delete(UserPreference).where(UserPreference.user_id.in_(user_ids))
            ).rowcount or 0
            counts["app_user_sessions"] = session.execute(
                delete(AppUserSession).where(AppUserSession.user_id.in_(user_ids))
            ).rowcount or 0
            counts["app_users"] = session.execute(
                delete(AppUser).where(AppUser.id.in_(user_ids))
            ).rowcount or 0

        if self._phase_b_enabled and self._phase_b_store is not None:
            phase_b_counts = self._phase_b_store.clear_non_bootstrap_state(user_ids)
            counts["conversation_messages"] = counts.get("conversation_messages", 0) + int(
                phase_b_counts.get("chat_messages", 0)
            )
            counts["conversation_sessions"] = counts.get("conversation_sessions", 0) + int(
                phase_b_counts.get("chat_sessions", 0)
            )
            counts["analysis_history"] = counts.get("analysis_history", 0) + int(
                phase_b_counts.get("analysis_records", 0)
            )
            counts["analysis_sessions"] = int(phase_b_counts.get("analysis_sessions", 0))
        if self._phase_d_enabled and self._phase_d_store is not None:
            phase_d_counts = self._phase_d_store.clear_non_bootstrap_state(user_ids)
            counts["scanner_candidates"] = counts.get("scanner_candidates", 0) + int(
                phase_d_counts.get("scanner_candidates", 0)
            )
            counts["scanner_runs"] = counts.get("scanner_runs", 0) + int(
                phase_d_counts.get("scanner_runs", 0)
            )
            counts["watchlist_items"] = int(phase_d_counts.get("watchlist_items", 0))
            counts["watchlists"] = int(phase_d_counts.get("watchlists", 0))
        if self._phase_e_enabled and self._phase_e_store is not None:
            phase_e_counts = self._phase_e_store.clear_non_bootstrap_state(user_ids)
            counts["backtest_runs"] = counts.get("backtest_runs", 0) + int(
                phase_e_counts.get("backtest_runs", 0)
            )
            counts["backtest_artifacts"] = int(phase_e_counts.get("backtest_artifacts", 0))
            counts["market_data_usage_refs"] = counts.get("market_data_usage_refs", 0) + int(
                phase_e_counts.get("market_data_usage_refs", 0)
            )
        if self._phase_a_enabled and self._phase_a_store is not None:
            phase_a_counts = self._phase_a_store.clear_non_bootstrap_state(user_ids)
            counts["user_preferences"] = counts.get("user_preferences", 0) + int(
                phase_a_counts.get("user_preferences", 0)
            )
            counts["app_user_sessions"] = counts.get("app_user_sessions", 0) + int(
                phase_a_counts.get("app_user_sessions", 0)
            )
            counts["app_users"] = counts.get("app_users", 0) + int(
                phase_a_counts.get("app_users", 0)
            )
            counts["notification_targets"] = int(
                phase_a_counts.get("notification_targets", 0)
            )

        cleared = [key for key, value in counts.items() if int(value or 0) > 0]
        return {
            "cleared": cleared,
            "counts": counts,
        }

    def get_user_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        resolved_user_id = self.require_user_id(user_id)
        if self._phase_a_enabled and self._phase_a_store is not None:
            preferences = self._phase_a_store.get_user_notification_preferences(resolved_user_id)
            if (
                preferences.get("updated_at") is not None
                or preferences.get("email") is not None
                or preferences.get("discord_webhook") is not None
            ):
                return preferences
            legacy_preferences = self._sync_phase_a_notification_preferences_from_legacy(resolved_user_id)
            if legacy_preferences is not None:
                return legacy_preferences
            return preferences

        row = self._sqlite_get_user_preference_row(resolved_user_id)
        payload = self._safe_json_loads(
            getattr(row, "notification_preferences_json", None),
            {},
        )
        if not isinstance(payload, dict):
            payload = {}

        email = str(payload.get("email") or "").strip() or None
        email_enabled = bool(payload.get("email_enabled", payload.get("enabled"))) and bool(email)
        discord_webhook = str(payload.get("discord_webhook") or "").strip() or None
        discord_enabled = bool(payload.get("discord_enabled")) and bool(discord_webhook)
        channel = str(payload.get("channel") or "email").strip().lower() or "email"
        if email_enabled and discord_enabled:
            channel = "multi"
        elif discord_enabled and not email_enabled:
            channel = "discord"
        else:
            channel = "email"
        updated_at = getattr(row, "updated_at", None)
        return {
            "channel": channel,
            "enabled": email_enabled,
            "email": email,
            "email_enabled": email_enabled,
            "discord_webhook": discord_webhook,
            "discord_enabled": discord_enabled,
            "updated_at": updated_at.isoformat() if updated_at else None,
        }

    def get_symbol_master_entry(self, canonical_symbol: str) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.get_symbol_master_entry(canonical_symbol)

    def upsert_symbol_master_entry(
        self,
        *,
        canonical_symbol: str,
        display_symbol: Optional[str] = None,
        market: str,
        asset_type: str,
        display_name: Optional[str] = None,
        exchange_code: Optional[str] = None,
        currency: Optional[str] = None,
        lot_size: Optional[Any] = None,
        is_active: bool = True,
        search_aliases: Optional[List[Any]] = None,
        source: Optional[str] = None,
        source_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.upsert_symbol_master_entry(
            canonical_symbol=canonical_symbol,
            display_symbol=display_symbol,
            market=market,
            asset_type=asset_type,
            display_name=display_name,
            exchange_code=exchange_code,
            currency=currency,
            lot_size=lot_size,
            is_active=is_active,
            search_aliases=search_aliases,
            source=source,
            source_payload=source_payload,
        )

    def seed_symbol_master_from_stock_mapping(self, *, symbols: Optional[List[str]] = None) -> int:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return 0
        return self._phase_c_store.seed_symbol_master_from_stock_mapping(symbols=symbols)

    def get_market_data_manifest(self, manifest_key: str) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.get_market_data_manifest(manifest_key)

    def upsert_market_data_manifest(
        self,
        *,
        manifest_key: str,
        dataset_family: str,
        market: str,
        storage_backend: str,
        root_uri: str,
        asset_scope: Optional[str] = None,
        file_format: str = "parquet",
        partition_strategy: Optional[str] = None,
        symbol_namespace: Optional[str] = None,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        active_version_id: Optional[int] = None,
    ) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.upsert_market_data_manifest(
            manifest_key=manifest_key,
            dataset_family=dataset_family,
            market=market,
            storage_backend=storage_backend,
            root_uri=root_uri,
            asset_scope=asset_scope,
            file_format=file_format,
            partition_strategy=partition_strategy,
            symbol_namespace=symbol_namespace,
            description=description,
            config=config,
            active_version_id=active_version_id,
        )

    def get_market_dataset_version(self, dataset_version_id: int) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.get_market_dataset_version(dataset_version_id)

    def register_market_dataset_version(
        self,
        *,
        manifest_key: str,
        version_label: str,
        version_hash: str,
        source_kind: Optional[str] = None,
        generated_at: Optional[datetime] = None,
        as_of_date: Optional[date] = None,
        coverage_start: Optional[date] = None,
        coverage_end: Optional[date] = None,
        symbol_count: Optional[int] = None,
        row_count: Optional[int] = None,
        partition_count: Optional[int] = None,
        file_inventory: Optional[Dict[str, Any]] = None,
        content_stats: Optional[Dict[str, Any]] = None,
        set_active: bool = False,
    ) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.register_market_dataset_version(
            manifest_key=manifest_key,
            version_label=version_label,
            version_hash=version_hash,
            source_kind=source_kind,
            generated_at=generated_at,
            as_of_date=as_of_date,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            symbol_count=symbol_count,
            row_count=row_count,
            partition_count=partition_count,
            file_inventory=file_inventory,
            content_stats=content_stats,
            set_active=set_active,
        )

    def get_market_data_usage_refs(
        self,
        *,
        entity_type: str,
        entity_id: int,
    ) -> List[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return []
        return self._phase_c_store.get_market_data_usage_refs(
            entity_type=entity_type,
            entity_id=entity_id,
        )

    def record_market_data_usage_ref(
        self,
        *,
        entity_type: str,
        entity_id: int,
        usage_role: str,
        manifest_key: str,
        dataset_version_id: int,
        detail: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.record_market_data_usage_ref(
            entity_type=entity_type,
            entity_id=entity_id,
            usage_role=usage_role,
            manifest_key=manifest_key,
            dataset_version_id=dataset_version_id,
            detail=detail,
        )

    def register_local_us_parquet_dataset_version(
        self,
        *,
        root_path: Optional[Any] = None,
        activate: bool = True,
    ) -> Optional[Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return None
        return self._phase_c_store.register_local_us_parquet_dataset_version(
            root_path=root_path,
            activate=activate,
        )

    def build_local_us_parquet_usage_detail(
        self,
        *,
        stock_code: str,
        file_path: Any,
        dataframe: Optional[Any],
        source_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._phase_c_enabled or self._phase_c_store is None:
            return {}
        return self._phase_c_store.build_local_us_parquet_usage_detail(
            stock_code=stock_code,
            file_path=file_path,
            dataframe=dataframe,
            source_name=source_name,
        )

    def sync_phase_e_analysis_backtest_shadow(self, run_id: int) -> Optional[Any]:
        if not self._phase_e_enabled or self._phase_e_store is None:
            return None

        with self.get_session() as session:
            run_row = session.execute(
                select(BacktestRun).where(BacktestRun.id == int(run_id)).limit(1)
            ).scalar_one_or_none()
            if run_row is None:
                return None

            evaluated_at = getattr(run_row, "completed_at", None) or getattr(run_row, "run_at", None)
            result_rows = session.execute(
                select(BacktestResult)
                .where(
                    and_(
                        BacktestResult.owner_id == run_row.owner_id,
                        BacktestResult.evaluated_at == evaluated_at,
                    )
                )
                .order_by(BacktestResult.analysis_history_id.asc(), BacktestResult.id.asc())
            ).scalars().all() if evaluated_at is not None else []

            summary_rows: List[BacktestSummary] = []
            engine_versions = sorted({str(getattr(row, "engine_version", "") or "").strip() for row in result_rows if str(getattr(row, "engine_version", "") or "").strip()})
            if engine_versions:
                engine_version = engine_versions[0]
                summary_conditions = [
                    BacktestSummary.owner_id == run_row.owner_id,
                    BacktestSummary.eval_window_days == run_row.eval_window_days,
                    BacktestSummary.engine_version == engine_version,
                ]
                code_values = [run_row.code] if str(getattr(run_row, "code", "") or "").strip() else []
                code_values.append("__overall__")
                summary_rows = session.execute(
                    select(BacktestSummary)
                    .where(and_(*summary_conditions))
                    .where(BacktestSummary.code.in_(code_values))
                    .order_by(BacktestSummary.scope.asc(), BacktestSummary.code.asc())
                ).scalars().all()

        shadow_row = self._phase_e_store.upsert_analysis_eval_run_shadow(
            run_row=run_row,
            result_rows=result_rows,
            summary_rows=summary_rows,
        )
        self._record_phase_e_analysis_usage_ref(run_row=run_row, shadow_row=shadow_row)
        return shadow_row

    def _record_phase_e_analysis_usage_ref(self, *, run_row: BacktestRun, shadow_row: Optional[Any]) -> None:
        if shadow_row is None:
            return
        if not self._phase_c_enabled or self._phase_c_store is None:
            return

        summary = self._safe_json_loads(getattr(run_row, "summary_json", None), {})
        resolved_source = str(summary.get("resolved_source") or "").strip()
        if resolved_source != "LocalParquet":
            return

        canonical_symbol = str(getattr(run_row, "code", "") or "").strip().upper()
        if not canonical_symbol:
            return

        try:
            version = self.register_local_us_parquet_dataset_version()
            if version is None:
                return
            self.record_market_data_usage_ref(
                entity_type="backtest_run",
                entity_id=int(shadow_row.id),
                usage_role="primary_bars",
                manifest_key="us.local_parquet.daily",
                dataset_version_id=int(version.id),
                detail={
                    "symbol": canonical_symbol,
                    "resolved_source": LOCAL_US_PARQUET_SOURCE,
                    "provenance_granularity": "manifest_version",
                },
            )
        except Exception as exc:
            logger.warning("Failed to record Phase E market-data usage ref for run %s: %s", run_row.id, exc)

    def delete_phase_e_analysis_backtest_shadow_by_code(
        self,
        *,
        code: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        if not self._phase_e_enabled or self._phase_e_store is None:
            return 0
        resolved_owner_id = None if include_all_owners else self.require_user_id(owner_id)
        return self._phase_e_store.delete_backtest_shadows_by_code(
            run_type="analysis_eval",
            code=code,
            owner_user_id=resolved_owner_id,
            include_all_owners=include_all_owners,
        )

    def sync_phase_e_rule_backtest_shadow(self, run_id: int) -> Optional[Any]:
        if not self._phase_e_enabled or self._phase_e_store is None:
            return None

        with self.get_session() as session:
            run_row = session.execute(
                select(RuleBacktestRun).where(RuleBacktestRun.id == int(run_id)).limit(1)
            ).scalar_one_or_none()
            if run_row is None:
                return None
            trade_rows = session.execute(
                select(RuleBacktestTrade)
                .where(RuleBacktestTrade.run_id == int(run_id))
                .order_by(RuleBacktestTrade.trade_index.asc(), RuleBacktestTrade.id.asc())
            ).scalars().all()

        return self._phase_e_store.upsert_rule_backtest_run_shadow(
            run_row=run_row,
            trade_rows=trade_rows,
        )

    def delete_phase_e_rule_backtest_shadow_by_code(
        self,
        *,
        code: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        if not self._phase_e_enabled or self._phase_e_store is None:
            return 0
        resolved_owner_id = None if include_all_owners else self.require_user_id(owner_id)
        return self._phase_e_store.delete_backtest_shadows_by_code(
            run_type="rule_deterministic",
            code=code,
            owner_user_id=resolved_owner_id,
            include_all_owners=include_all_owners,
        )

    def upsert_user_notification_preferences(
        self,
        user_id: str,
        *,
        email: Optional[str],
        enabled: bool,
        channel: str = "email",
        discord_webhook: Optional[str] = None,
        discord_enabled: bool = False,
    ) -> Dict[str, Any]:
        resolved_user_id = self.require_user_id(user_id)
        normalized_channel = str(channel or "email").strip().lower() or "email"
        if normalized_channel not in {"email", "discord", "multi"}:
            raise ValueError("unsupported notification channel")

        normalized_email = str(email or "").strip() or None
        normalized_enabled = bool(enabled) and bool(normalized_email)
        normalized_discord_webhook = str(discord_webhook or "").strip() or None
        normalized_discord_enabled = bool(discord_enabled) and bool(normalized_discord_webhook)
        if normalized_enabled and normalized_discord_enabled:
            normalized_channel = "multi"
        elif normalized_discord_enabled and not normalized_enabled:
            normalized_channel = "discord"
        else:
            normalized_channel = "email"
        if self._phase_a_enabled and self._phase_a_store is not None:
            return self._phase_a_store.upsert_user_notification_preferences(
                resolved_user_id,
                email=normalized_email,
                enabled=normalized_enabled,
                channel=normalized_channel,
                discord_webhook=normalized_discord_webhook,
                discord_enabled=normalized_discord_enabled,
            )

        payload = {
            "version": 2,
            "channel": normalized_channel,
            "enabled": normalized_enabled,
            "email": normalized_email,
            "email_enabled": normalized_enabled,
            "discord_webhook": normalized_discord_webhook,
            "discord_enabled": normalized_discord_enabled,
        }

        with self.get_session() as session:
            row = session.execute(
                select(UserPreference).where(UserPreference.user_id == resolved_user_id).limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = UserPreference(
                    user_id=resolved_user_id,
                    notification_preferences_json=json.dumps(payload, ensure_ascii=False),
                )
                session.add(row)
            else:
                row.notification_preferences_json = json.dumps(payload, ensure_ascii=False)
                row.updated_at = datetime.now()
            session.commit()

        return self.get_user_notification_preferences(resolved_user_id)
    
    def has_today_data(self, code: str, target_date: Optional[date] = None) -> bool:
        """
        检查是否已有指定日期的数据
        
        用于断点续传逻辑：如果已有数据则跳过网络请求
        
        Args:
            code: 股票代码
            target_date: 目标日期（默认今天）
            
        Returns:
            是否存在数据
        """
        if target_date is None:
            target_date = date.today()
        # 注意：这里的 target_date 语义是“自然日”，而不是“最新交易日”。
        # 在周末/节假日/非交易日运行时，即使数据库已有最新交易日数据，这里也会返回 False。
        # 该行为目前保留（按需求不改逻辑）。
        
        with self.get_session() as session:
            result = session.execute(
                select(StockDaily).where(
                    and_(
                        StockDaily.code == code,
                        StockDaily.date == target_date
                    )
                )
            ).scalar_one_or_none()
            
            return result is not None
    
    def get_latest_data(
        self, 
        code: str, 
        days: int = 2
    ) -> List[StockDaily]:
        """
        获取最近 N 天的数据
        
        用于计算"相比昨日"的变化
        
        Args:
            code: 股票代码
            days: 获取天数
            
        Returns:
            StockDaily 对象列表（按日期降序）
        """
        with self.get_session() as session:
            results = session.execute(
                select(StockDaily)
                .where(StockDaily.code == code)
                .order_by(desc(StockDaily.date))
                .limit(days)
            ).scalars().all()
            
            return list(results)

    def save_news_intel(
        self,
        code: str,
        name: str,
        dimension: str,
        query: str,
        response: 'SearchResponse',
        query_context: Optional[Dict[str, str]] = None
    ) -> int:
        """
        保存新闻情报到数据库

        去重策略：
        - 优先按 URL 去重（唯一约束）
        - URL 缺失时按 title + source + published_date 进行软去重

        关联策略：
        - query_context 记录用户查询信息（平台、用户、会话、原始指令等）
        """
        if not response or not response.results:
            return 0

        saved_count = 0
        query_ctx = query_context or {}
        current_query_id = (query_ctx.get("query_id") or "").strip()

        with self.get_session() as session:
            try:
                for item in response.results:
                    title = (item.title or '').strip()
                    url = (item.url or '').strip()
                    source = (item.source or '').strip()
                    snippet = (item.snippet or '').strip()
                    published_date = self._parse_published_date(item.published_date)

                    if not title and not url:
                        continue

                    url_key = url or self._build_fallback_url_key(
                        code=code,
                        title=title,
                        source=source,
                        published_date=published_date
                    )

                    # 优先按 URL 或兜底键去重
                    existing = session.execute(
                        select(NewsIntel).where(NewsIntel.url == url_key)
                    ).scalar_one_or_none()

                    if existing:
                        existing.name = name or existing.name
                        existing.dimension = dimension or existing.dimension
                        existing.query = query or existing.query
                        existing.provider = response.provider or existing.provider
                        existing.snippet = snippet or existing.snippet
                        existing.source = source or existing.source
                        existing.published_date = published_date or existing.published_date
                        existing.fetched_at = datetime.now()

                        if query_context:
                            # Keep the first query_id to avoid overwriting historical links.
                            if not existing.query_id and current_query_id:
                                existing.query_id = current_query_id
                            existing.query_source = (
                                query_context.get("query_source") or existing.query_source
                            )
                            existing.requester_platform = (
                                query_context.get("requester_platform") or existing.requester_platform
                            )
                            existing.requester_user_id = (
                                query_context.get("requester_user_id") or existing.requester_user_id
                            )
                            existing.requester_user_name = (
                                query_context.get("requester_user_name") or existing.requester_user_name
                            )
                            existing.requester_chat_id = (
                                query_context.get("requester_chat_id") or existing.requester_chat_id
                            )
                            existing.requester_message_id = (
                                query_context.get("requester_message_id") or existing.requester_message_id
                            )
                            existing.requester_query = (
                                query_context.get("requester_query") or existing.requester_query
                            )
                    else:
                        try:
                            with session.begin_nested():
                                record = NewsIntel(
                                    code=code,
                                    name=name,
                                    dimension=dimension,
                                    query=query,
                                    provider=response.provider,
                                    title=title,
                                    snippet=snippet,
                                    url=url_key,
                                    source=source,
                                    published_date=published_date,
                                    fetched_at=datetime.now(),
                                    query_id=current_query_id or None,
                                    query_source=query_ctx.get("query_source"),
                                    requester_platform=query_ctx.get("requester_platform"),
                                    requester_user_id=query_ctx.get("requester_user_id"),
                                    requester_user_name=query_ctx.get("requester_user_name"),
                                    requester_chat_id=query_ctx.get("requester_chat_id"),
                                    requester_message_id=query_ctx.get("requester_message_id"),
                                    requester_query=query_ctx.get("requester_query"),
                                )
                                session.add(record)
                                session.flush()
                            saved_count += 1
                        except IntegrityError:
                            # 单条 URL 唯一约束冲突（如并发插入），仅跳过本条，保留本批其余成功项
                            logger.debug("新闻情报重复（已跳过）: %s %s", code, url_key)

                session.commit()
                logger.info(f"保存新闻情报成功: {code}, 新增 {saved_count} 条")

            except Exception as e:
                session.rollback()
                logger.error(f"保存新闻情报失败: {e}")
                raise

        return saved_count

    def save_fundamental_snapshot(
        self,
        query_id: str,
        code: str,
        payload: Optional[Dict[str, Any]],
        source_chain: Optional[Any] = None,
        coverage: Optional[Any] = None,
    ) -> int:
        """
        保存基本面快照（P0 write-only）。失败不抛异常，返回写入条数 0/1。
        """
        if not query_id or not code or payload is None:
            return 0

        with self.get_session() as session:
            try:
                session.add(
                    FundamentalSnapshot(
                        query_id=query_id,
                        code=code,
                        payload=self._safe_json_dumps(payload),
                        source_chain=self._safe_json_dumps(source_chain or []),
                        coverage=self._safe_json_dumps(coverage or {}),
                    )
                )
                session.commit()
                return 1
            except Exception as e:
                session.rollback()
                logger.debug(
                    "基本面快照写入失败（fail-open）: query_id=%s code=%s err=%s",
                    query_id,
                    code,
                    e,
                )
                return 0

    def get_latest_fundamental_snapshot(
        self,
        query_id: str,
        code: str,
    ) -> Optional[Dict[str, Any]]:
        """
        获取指定 query_id + code 的最新基本面快照 payload。

        读取失败或不存在时返回 None（fail-open）。
        """
        if not query_id or not code:
            return None

        with self.get_session() as session:
            try:
                row = session.execute(
                    select(FundamentalSnapshot)
                    .where(
                        and_(
                            FundamentalSnapshot.query_id == query_id,
                            FundamentalSnapshot.code == code,
                        )
                    )
                    .order_by(desc(FundamentalSnapshot.created_at))
                    .limit(1)
                ).scalar_one_or_none()
            except Exception as e:
                logger.debug(
                    "基本面快照读取失败（fail-open）: query_id=%s code=%s err=%s",
                    query_id,
                    code,
                    e,
                )
                return None

            if row is None:
                return None
            try:
                payload = json.loads(row.payload or "{}")
                return payload if isinstance(payload, dict) else None
            except Exception:
                return None

    def get_recent_news(self, code: str, days: int = 7, limit: int = 20) -> List[NewsIntel]:
        """
        获取指定股票最近 N 天的新闻情报
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.get_session() as session:
            results = session.execute(
                select(NewsIntel)
                .where(
                    and_(
                        NewsIntel.code == code,
                        NewsIntel.fetched_at >= cutoff_date
                    )
                )
                .order_by(desc(NewsIntel.fetched_at))
                .limit(limit)
            ).scalars().all()

            return list(results)

    def get_news_intel_by_query_id(self, query_id: str, limit: int = 20) -> List[NewsIntel]:
        """
        根据 query_id 获取新闻情报列表

        Args:
            query_id: 分析记录唯一标识
            limit: 返回数量限制

        Returns:
            NewsIntel 列表（按发布时间或抓取时间倒序）
        """
        from sqlalchemy import func

        with self.get_session() as session:
            results = session.execute(
                select(NewsIntel)
                .where(NewsIntel.query_id == query_id)
                .order_by(
                    desc(func.coalesce(NewsIntel.published_date, NewsIntel.fetched_at)),
                    desc(NewsIntel.fetched_at)
                )
                .limit(limit)
            ).scalars().all()

            return list(results)

    def save_analysis_history(
        self,
        result: Any,
        query_id: str,
        report_type: str,
        news_content: Optional[str],
        context_snapshot: Optional[Dict[str, Any]] = None,
        save_snapshot: bool = True,
        owner_id: Optional[str] = None,
    ) -> int:
        """
        保存分析结果历史记录
        """
        if result is None:
            return 0

        sniper_points = self._extract_sniper_points(result)
        raw_result = self._build_raw_result(result)
        context_text = None
        if save_snapshot and context_snapshot is not None:
            context_text = self._safe_json_dumps(context_snapshot)
        resolved_owner_id = self.require_user_id(owner_id)

        record = AnalysisHistory(
            owner_id=resolved_owner_id,
            query_id=query_id,
            code=result.code,
            name=result.name,
            report_type=report_type,
            sentiment_score=result.sentiment_score,
            operation_advice=result.operation_advice,
            trend_prediction=result.trend_prediction,
            analysis_summary=result.analysis_summary,
            raw_result=self._safe_json_dumps(raw_result),
            news_content=news_content,
            context_snapshot=context_text,
            ideal_buy=sniper_points.get("ideal_buy"),
            secondary_buy=sniper_points.get("secondary_buy"),
            stop_loss=sniper_points.get("stop_loss"),
            take_profit=sniper_points.get("take_profit"),
            created_at=datetime.now(),
        )

        with self.get_session() as session:
            try:
                session.add(record)
                session.flush()
                if self._phase_b_enabled and self._phase_b_store is not None:
                    self._phase_b_store.upsert_analysis_history_shadow(
                        legacy_analysis_history_id=int(record.id),
                        owner_user_id=resolved_owner_id,
                        query_id=query_id,
                        canonical_symbol=str(result.code or ""),
                        display_name=getattr(result, "name", None),
                        report_type=report_type,
                        sentiment_score=getattr(result, "sentiment_score", None),
                        operation_advice=getattr(result, "operation_advice", None),
                        trend_prediction=getattr(result, "trend_prediction", None),
                        summary_text=getattr(result, "analysis_summary", None),
                        raw_result=record.raw_result,
                        news_content=news_content,
                        context_snapshot=context_text,
                        created_at=record.created_at,
                    )
                session.commit()
                return 1
            except Exception as e:
                session.rollback()
                logger.error(f"保存分析历史失败: {e}")
                return 0

    def get_analysis_history(
        self,
        code: Optional[str] = None,
        query_id: Optional[str] = None,
        days: int = 30,
        limit: int = 50,
        exclude_query_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[AnalysisHistory]:
        """
        Query analysis history records.

        Notes:
        - If query_id is provided, perform exact lookup and ignore days window.
        - If query_id is not provided, apply days-based time filtering.
        - exclude_query_id: exclude records with this query_id (for history comparison).
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        with self.get_session() as session:
            conditions = []
            if not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.require_user_id(owner_id))

            if query_id:
                conditions.append(AnalysisHistory.query_id == query_id)
            else:
                conditions.append(AnalysisHistory.created_at >= cutoff_date)

            if code:
                conditions.append(AnalysisHistory.code == code)

            # exclude_query_id only applies when not doing exact lookup (query_id is None)
            if exclude_query_id and not query_id:
                conditions.append(AnalysisHistory.query_id != exclude_query_id)

            results = session.execute(
                select(AnalysisHistory)
                .where(and_(*conditions))
                .order_by(desc(AnalysisHistory.created_at))
                .limit(limit)
            ).scalars().all()

            return list(results)
    
    def get_analysis_history_paginated(
        self,
        code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        offset: int = 0,
        limit: int = 20,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Tuple[List[AnalysisHistory], int]:
        """
        分页查询分析历史记录（带总数）
        
        Args:
            code: 股票代码筛选
            start_date: 开始日期（含）
            end_date: 结束日期（含）
            offset: 偏移量（跳过前 N 条）
            limit: 每页数量
            
        Returns:
            Tuple[List[AnalysisHistory], int]: (记录列表, 总数)
        """
        from sqlalchemy import func
        
        with self.get_session() as session:
            conditions = []
            if not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.require_user_id(owner_id))
            
            if code:
                conditions.append(AnalysisHistory.code == code)
            if start_date:
                # created_at >= start_date 00:00:00
                conditions.append(AnalysisHistory.created_at >= datetime.combine(start_date, datetime.min.time()))
            if end_date:
                # created_at < end_date+1 00:00:00 (即 <= end_date 23:59:59)
                conditions.append(AnalysisHistory.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()))
            
            # 构建 where 子句
            where_clause = and_(*conditions) if conditions else True
            
            # 查询总数
            total_query = select(func.count(AnalysisHistory.id)).where(where_clause)
            total = session.execute(total_query).scalar() or 0
            
            # 查询分页数据
            data_query = (
                select(AnalysisHistory)
                .where(where_clause)
                .order_by(desc(AnalysisHistory.created_at))
                .offset(offset)
                .limit(limit)
            )
            results = session.execute(data_query).scalars().all()
            
            return list(results), total
    
    def get_analysis_history_by_id(
        self,
        record_id: int,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[AnalysisHistory]:
        """
        根据数据库主键 ID 查询单条分析历史记录
        
        由于 query_id 可能重复（批量分析时多条记录共享同一 query_id），
        使用主键 ID 确保精确查询唯一记录。
        
        Args:
            record_id: 分析历史记录的主键 ID
            
        Returns:
            AnalysisHistory 对象，不存在返回 None
        """
        with self.get_session() as session:
            conditions = [AnalysisHistory.id == record_id]
            if not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.require_user_id(owner_id))
            result = session.execute(
                select(AnalysisHistory).where(and_(*conditions))
            ).scalars().first()
            return result

    def delete_analysis_history_records(
        self,
        record_ids: List[int],
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        """
        删除指定的分析历史记录。

        同时清理依赖这些历史记录的回测结果，避免外键约束失败。

        Args:
            record_ids: 要删除的历史记录主键 ID 列表

        Returns:
            实际删除的历史记录数量
        """
        ids = sorted({int(record_id) for record_id in record_ids if record_id is not None})
        if not ids:
            return 0

        with self.session_scope() as session:
            owner_filter = []
            if not include_all_owners:
                owner_filter.append(AnalysisHistory.owner_id == self.require_user_id(owner_id))
            matching_analysis_ids = session.execute(
                select(AnalysisHistory.id).where(
                    and_(AnalysisHistory.id.in_(ids), *owner_filter) if owner_filter else AnalysisHistory.id.in_(ids)
                )
            ).scalars().all()
            if not matching_analysis_ids:
                return 0
            if self._phase_b_enabled and self._phase_b_store is not None:
                self._phase_b_store.delete_analysis_history_shadow(matching_analysis_ids)
            session.execute(
                delete(BacktestResult).where(BacktestResult.analysis_history_id.in_(matching_analysis_ids))
            )
            result = session.execute(
                delete(AnalysisHistory).where(AnalysisHistory.id.in_(matching_analysis_ids))
            )
            return result.rowcount or 0

    def get_latest_analysis_by_query_id(
        self,
        query_id: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> Optional[AnalysisHistory]:
        """
        根据 query_id 查询最新一条分析历史记录

        query_id 在批量分析时可能重复，故返回最近创建的一条。

        Args:
            query_id: 分析记录关联的 query_id

        Returns:
            AnalysisHistory 对象，不存在返回 None
        """
        with self.get_session() as session:
            conditions = [AnalysisHistory.query_id == query_id]
            if not include_all_owners:
                conditions.append(AnalysisHistory.owner_id == self.require_user_id(owner_id))
            result = session.execute(
                select(AnalysisHistory)
                .where(and_(*conditions))
                .order_by(desc(AnalysisHistory.created_at))
                .limit(1)
            ).scalars().first()
            return result

    def create_execution_log_session(
        self,
        *,
        session_id: str,
        task_id: Optional[str] = None,
        query_id: Optional[str] = None,
        code: Optional[str] = None,
        name: Optional[str] = None,
        overall_status: str = "running",
        truth_level: str = "mixed",
        summary: Optional[Dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
    ) -> None:
        """Create or update an execution log session."""
        if not session_id:
            return
        now = datetime.now()
        with self.session_scope() as session:
            row = session.execute(
                select(ExecutionLogSession).where(ExecutionLogSession.session_id == session_id)
            ).scalars().first()
            if row is None:
                row = ExecutionLogSession(
                    session_id=session_id,
                    task_id=task_id,
                    query_id=query_id,
                    code=code,
                    name=name,
                    overall_status=overall_status,
                    truth_level=truth_level,
                    summary_json=self._safe_json_dumps(summary or {}),
                    started_at=started_at or now,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.task_id = task_id or row.task_id
                row.query_id = query_id or row.query_id
                row.code = code or row.code
                row.name = name or row.name
                row.overall_status = overall_status or row.overall_status
                row.truth_level = truth_level or row.truth_level
                if summary is not None:
                    row.summary_json = self._safe_json_dumps(summary)
                if started_at is not None:
                    row.started_at = started_at
                row.updated_at = now

    def append_execution_log_event(
        self,
        *,
        session_id: str,
        phase: str,
        status: str,
        step: Optional[str] = None,
        target: Optional[str] = None,
        truth_level: str = "inferred",
        message: Optional[str] = None,
        error_code: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        event_at: Optional[datetime] = None,
    ) -> None:
        """Append a structured event into execution logs."""
        if not session_id or not phase:
            return
        row = ExecutionLogEvent(
            session_id=session_id,
            event_at=event_at or datetime.now(),
            phase=str(phase).strip(),
            step=str(step).strip() if step else None,
            target=str(target).strip() if target else None,
            status=str(status or "unknown").strip(),
            truth_level=str(truth_level or "inferred").strip(),
            message=(str(message).strip() or None) if message is not None else None,
            error_code=(str(error_code).strip() or None) if error_code is not None else None,
            detail_json=self._safe_json_dumps(detail or {}),
        )
        with self.session_scope() as session:
            session.add(row)

    def finalize_execution_log_session(
        self,
        *,
        session_id: str,
        overall_status: str,
        truth_level: str = "mixed",
        query_id: Optional[str] = None,
        analysis_history_id: Optional[int] = None,
        summary: Optional[Dict[str, Any]] = None,
        ended_at: Optional[datetime] = None,
    ) -> None:
        """Finalize a session status and enrich linkage fields."""
        if not session_id:
            return
        now = datetime.now()
        with self.session_scope() as session:
            row = session.execute(
                select(ExecutionLogSession).where(ExecutionLogSession.session_id == session_id)
            ).scalars().first()
            if row is None:
                return
            row.overall_status = str(overall_status or row.overall_status).strip()
            row.truth_level = str(truth_level or row.truth_level).strip()
            if query_id:
                row.query_id = query_id
            if analysis_history_id is not None:
                row.analysis_history_id = int(analysis_history_id)
            if summary is not None:
                row.summary_json = self._safe_json_dumps(summary)
            row.ended_at = ended_at or now
            row.updated_at = now

    def attach_execution_session_to_query(
        self,
        *,
        session_id: str,
        query_id: Optional[str],
    ) -> None:
        """Attach query_id/history_id linkage once history is persisted."""
        if not session_id:
            return
        with self.session_scope() as session:
            row = session.execute(
                select(ExecutionLogSession).where(ExecutionLogSession.session_id == session_id)
            ).scalars().first()
            if row is None:
                return
            if query_id:
                row.query_id = query_id
                latest = session.execute(
                    select(AnalysisHistory)
                    .where(AnalysisHistory.query_id == query_id)
                    .order_by(desc(AnalysisHistory.created_at))
                    .limit(1)
                ).scalars().first()
                if latest is not None:
                    row.analysis_history_id = latest.id
            row.updated_at = datetime.now()

    def list_execution_log_sessions(
        self,
        *,
        stock_code: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        channel: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List execution sessions with optional event-level filtering."""
        with self.get_session() as session:
            session_filters = []
            if stock_code:
                session_filters.append(ExecutionLogSession.code == stock_code)
            if status:
                session_filters.append(ExecutionLogSession.overall_status == status)
            if date_from:
                session_filters.append(ExecutionLogSession.started_at >= date_from)
            if date_to:
                session_filters.append(ExecutionLogSession.started_at <= date_to)

            event_filters = []
            if category:
                event_filters.append(ExecutionLogEvent.phase == category)
            if provider:
                event_filters.append(ExecutionLogEvent.target.ilike(f"%{provider}%"))
            if model:
                event_filters.append(
                    and_(
                        ExecutionLogEvent.phase.in_(["ai", "ai_model"]),
                        ExecutionLogEvent.target.ilike(f"%{model}%"),
                    )
                )
            if channel:
                event_filters.append(and_(ExecutionLogEvent.phase == "notification", ExecutionLogEvent.target.ilike(f"%{channel}%")))

            where_clause = and_(*session_filters) if session_filters else True
            if event_filters:
                event_where = and_(*event_filters)
                matched_session_ids = session.execute(
                    select(ExecutionLogEvent.session_id).where(event_where).distinct()
                ).scalars().all()
                if not matched_session_ids:
                    return [], 0
                where_clause = and_(where_clause, ExecutionLogSession.session_id.in_(matched_session_ids))

            total = session.execute(
                select(func.count(ExecutionLogSession.id)).where(where_clause)
            ).scalar() or 0

            rows = session.execute(
                select(ExecutionLogSession)
                .where(where_clause)
                .order_by(desc(ExecutionLogSession.started_at))
                .offset(max(0, int(offset)))
                .limit(max(1, min(int(limit), 200)))
            ).scalars().all()

            items: List[Dict[str, Any]] = []
            for row in rows:
                summary = {}
                try:
                    summary = json.loads(row.summary_json or "{}")
                except Exception:
                    summary = {}
                items.append(
                    {
                        "session_id": row.session_id,
                        "task_id": row.task_id,
                        "query_id": row.query_id,
                        "analysis_history_id": row.analysis_history_id,
                        "code": row.code,
                        "name": row.name,
                        "overall_status": row.overall_status,
                        "truth_level": row.truth_level,
                        "started_at": row.started_at.isoformat() if row.started_at else None,
                        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
                        "summary": summary if isinstance(summary, dict) else {},
                    }
                )
            return items, int(total)

    def get_execution_log_session_detail(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return one execution session with its event timeline."""
        if not session_id:
            return None
        with self.get_session() as session:
            row = session.execute(
                select(ExecutionLogSession).where(ExecutionLogSession.session_id == session_id)
            ).scalars().first()
            if row is None:
                return None

            event_rows = session.execute(
                select(ExecutionLogEvent)
                .where(ExecutionLogEvent.session_id == session_id)
                .order_by(asc(ExecutionLogEvent.event_at), asc(ExecutionLogEvent.id))
            ).scalars().all()
            events: List[Dict[str, Any]] = []
            for event in event_rows:
                detail = {}
                try:
                    detail = json.loads(event.detail_json or "{}")
                except Exception:
                    detail = {}
                events.append(
                    {
                        "id": event.id,
                        "event_at": event.event_at.isoformat() if event.event_at else None,
                        "phase": event.phase,
                        "step": event.step,
                        "target": event.target,
                        "status": event.status,
                        "truth_level": event.truth_level,
                        "message": event.message,
                        "error_code": event.error_code,
                        "detail": detail if isinstance(detail, dict) else {},
                    }
                )

            summary = {}
            try:
                summary = json.loads(row.summary_json or "{}")
            except Exception:
                summary = {}

            return {
                "session_id": row.session_id,
                "task_id": row.task_id,
                "query_id": row.query_id,
                "analysis_history_id": row.analysis_history_id,
                "code": row.code,
                "name": row.name,
                "overall_status": row.overall_status,
                "truth_level": row.truth_level,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "ended_at": row.ended_at.isoformat() if row.ended_at else None,
                "summary": summary if isinstance(summary, dict) else {},
                "events": events,
            }
    
    def get_data_range(
        self, 
        code: str, 
        start_date: date, 
        end_date: date
    ) -> List[StockDaily]:
        """
        获取指定日期范围的数据
        
        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            StockDaily 对象列表
        """
        with self.get_session() as session:
            results = session.execute(
                select(StockDaily)
                .where(
                    and_(
                        StockDaily.code == code,
                        StockDaily.date >= start_date,
                        StockDaily.date <= end_date
                    )
                )
                .order_by(StockDaily.date)
            ).scalars().all()
            
            return list(results)
    
    def save_daily_data(
        self, 
        df: pd.DataFrame, 
        code: str,
        data_source: str = "Unknown"
    ) -> int:
        """
        保存日线数据到数据库
        
        策略：
        - 使用 UPSERT 逻辑（存在则更新，不存在则插入）
        - 跳过已存在的数据，避免重复
        
        Args:
            df: 包含日线数据的 DataFrame
            code: 股票代码
            data_source: 数据来源名称
            
        Returns:
            新增/更新的记录数
        """
        if df is None or df.empty:
            logger.warning(f"保存数据为空，跳过 {code}")
            return 0
        
        saved_count = 0
        
        with self.get_session() as session:
            try:
                for _, row in df.iterrows():
                    # 解析日期
                    row_date = row.get('date')
                    if isinstance(row_date, str):
                        row_date = datetime.strptime(row_date, '%Y-%m-%d').date()
                    elif isinstance(row_date, datetime):
                        row_date = row_date.date()
                    elif isinstance(row_date, pd.Timestamp):
                        row_date = row_date.date()
                    
                    # 检查是否已存在
                    existing = session.execute(
                        select(StockDaily).where(
                            and_(
                                StockDaily.code == code,
                                StockDaily.date == row_date
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if existing:
                        # 更新现有记录
                        existing.open = row.get('open')
                        existing.high = row.get('high')
                        existing.low = row.get('low')
                        existing.close = row.get('close')
                        existing.volume = row.get('volume')
                        existing.amount = row.get('amount')
                        existing.pct_chg = row.get('pct_chg')
                        existing.ma5 = row.get('ma5')
                        existing.ma10 = row.get('ma10')
                        existing.ma20 = row.get('ma20')
                        existing.volume_ratio = row.get('volume_ratio')
                        existing.data_source = data_source
                        existing.updated_at = datetime.now()
                    else:
                        # 创建新记录
                        record = StockDaily(
                            code=code,
                            date=row_date,
                            open=row.get('open'),
                            high=row.get('high'),
                            low=row.get('low'),
                            close=row.get('close'),
                            volume=row.get('volume'),
                            amount=row.get('amount'),
                            pct_chg=row.get('pct_chg'),
                            ma5=row.get('ma5'),
                            ma10=row.get('ma10'),
                            ma20=row.get('ma20'),
                            volume_ratio=row.get('volume_ratio'),
                            data_source=data_source,
                        )
                        session.add(record)
                        saved_count += 1
                
                session.commit()
                logger.info(f"保存 {code} 数据成功，新增 {saved_count} 条")
                
            except Exception as e:
                session.rollback()
                logger.error(f"保存 {code} 数据失败: {e}")
                raise
        
        return saved_count
    
    def get_analysis_context(
        self, 
        code: str,
        target_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取分析所需的上下文数据
        
        返回今日数据 + 昨日数据的对比信息
        
        Args:
            code: 股票代码
            target_date: 目标日期（默认今天）
            
        Returns:
            包含今日数据、昨日对比等信息的字典
        """
        if target_date is None:
            target_date = date.today()
        # 注意：尽管入参提供了 target_date，但当前实现实际使用的是“最新两天数据”（get_latest_data），
        # 并不会按 target_date 精确取当日/前一交易日的上下文。
        # 因此若未来需要支持“按历史某天复盘/重算”的可解释性，这里需要调整。
        # 该行为目前保留（按需求不改逻辑）。
        
        # 获取最近2天数据
        recent_data = self.get_latest_data(code, days=5)
        recent_data = self._filter_future_dated_rows(code, recent_data)[:2]
        
        if not recent_data:
            logger.warning(f"未找到 {code} 的数据")
            return None
        
        today_data = recent_data[0]
        yesterday_data = recent_data[1] if len(recent_data) > 1 else None
        
        context = {
            'code': code,
            'date': today_data.date.isoformat(),
            'today': today_data.to_dict(),
        }
        
        if yesterday_data:
            context['yesterday'] = yesterday_data.to_dict()
            
            # 计算相比昨日的变化
            if yesterday_data.volume and yesterday_data.volume > 0:
                context['volume_change_ratio'] = round(
                    today_data.volume / yesterday_data.volume, 2
                )
            
            if yesterday_data.close and yesterday_data.close > 0:
                context['price_change_ratio'] = round(
                    (today_data.close - yesterday_data.close) / yesterday_data.close * 100, 2
                )
            
            # 均线形态判断
            context['ma_status'] = self._analyze_ma_status(today_data)
        
        return context

    @staticmethod
    def _filter_future_dated_rows(code: str, rows: List[StockDaily]) -> List[StockDaily]:
        market = get_market_for_stock(code)
        tz_name = MARKET_TIMEZONE.get(market or "")
        if not tz_name or not rows:
            return rows
        market_today = datetime.now(ZoneInfo(tz_name)).date()
        filtered = [
            row for row in rows
            if getattr(row, "date", None) is not None and row.date <= market_today
        ]
        return filtered or rows
    
    def _analyze_ma_status(self, data: StockDaily) -> str:
        """
        分析均线形态
        
        判断条件：
        - 多头排列：close > ma5 > ma10 > ma20
        - 空头排列：close < ma5 < ma10 < ma20
        - 震荡整理：其他情况
        """
        # 注意：这里的均线形态判断基于“close/ma5/ma10/ma20”静态比较，
        # 未考虑均线拐点、斜率、或不同数据源复权口径差异。
        # 该行为目前保留（按需求不改逻辑）。
        close = data.close or 0
        ma5 = data.ma5 or 0
        ma10 = data.ma10 or 0
        ma20 = data.ma20 or 0
        
        if close > ma5 > ma10 > ma20 > 0:
            return "多头排列 📈"
        elif close < ma5 < ma10 < ma20 and ma20 > 0:
            return "空头排列 📉"
        elif close > ma5 and ma5 > ma10:
            return "短期向好 🔼"
        elif close < ma5 and ma5 < ma10:
            return "短期走弱 🔽"
        else:
            return "震荡整理 ↔️"

    @staticmethod
    def _parse_published_date(value: Optional[str]) -> Optional[datetime]:
        """
        解析发布时间字符串（失败返回 None）
        """
        if not value:
            return None

        if isinstance(value, datetime):
            return value

        text = str(value).strip()
        if not text:
            return None

        # 优先尝试 ISO 格式
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass

        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d",
        ):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue

        return None

    @staticmethod
    def _safe_json_dumps(data: Any) -> str:
        """
        安全序列化为 JSON 字符串
        """
        try:
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            return json.dumps(str(data), ensure_ascii=False)

    @staticmethod
    def _build_raw_result(result: Any) -> Dict[str, Any]:
        """
        生成完整分析结果字典
        """
        data = result.to_dict() if hasattr(result, "to_dict") else {}
        data.update({
            'data_sources': getattr(result, 'data_sources', ''),
            'raw_response': getattr(result, 'raw_response', None),
        })
        return data

    @staticmethod
    def _parse_sniper_value(value: Any) -> Optional[float]:
        """
        Parse a sniper point value from various formats to float.

        Handles: numeric types, plain number strings, Chinese price formats
        like "18.50元", range formats like "18.50-19.00", and text with
        embedded numbers while filtering out MA indicators.
        """
        if value is None:
            return None
        if isinstance(value, (int, float)):
            v = float(value)
            return v if v > 0 else None

        text = str(value).replace(',', '').replace('，', '').strip()
        if not text or text == '-' or text == '—' or text == 'N/A':
            return None

        # 尝试直接解析纯数字字符串
        try:
            return float(text)
        except ValueError:
            pass

        # 优先截取 "：" 到 "元" 之间的价格，避免误提取 MA5/MA10 等技术指标数字
        colon_pos = max(text.rfind("："), text.rfind(":"))
        yuan_pos = text.find("元", colon_pos + 1 if colon_pos != -1 else 0)
        if yuan_pos != -1:
            segment_start = colon_pos + 1 if colon_pos != -1 else 0
            segment = text[segment_start:yuan_pos]
            
            # 使用 finditer 并过滤掉 MA 开头的数字
            matches = list(re.finditer(r"-?\d+(?:\.\d+)?", segment))
            valid_numbers = []
            for m in matches:
                # 检查前面是否是 "MA" (忽略大小写)
                start_idx = m.start()
                if start_idx >= 2:
                    prefix = segment[start_idx-2:start_idx].upper()
                    if prefix == "MA":
                        continue
                valid_numbers.append(m.group())
            
            if valid_numbers:
                try:
                    return abs(float(valid_numbers[-1]))
                except ValueError:
                    pass

        # 兜底：无"元"字时，先截去第一个括号后的内容，避免误提取括号内技术指标数字
        # 例如 "1.52-1.53 (回踩MA5/10附近)" → 仅在 "1.52-1.53 " 中搜索
        paren_pos = len(text)
        for paren_char in ('(', '（'):
            pos = text.find(paren_char)
            if pos != -1:
                paren_pos = min(paren_pos, pos)
        search_text = text[:paren_pos].strip() or text  # 括号前为空时降级用全文

        valid_numbers = []
        for m in re.finditer(r"\d+(?:\.\d+)?", search_text):
            start_idx = m.start()
            if start_idx >= 2 and search_text[start_idx-2:start_idx].upper() == "MA":
                continue
            valid_numbers.append(m.group())
        if valid_numbers:
            try:
                return float(valid_numbers[-1])
            except ValueError:
                pass
        return None

    def _extract_sniper_points(self, result: Any) -> Dict[str, Optional[float]]:
        """
        Extract sniper point values from an AnalysisResult.

        Tries multiple extraction paths to handle different dashboard structures:
        1. result.get_sniper_points() (standard path)
        2. Direct dashboard dict traversal with various nesting levels
        3. Fallback from raw_result dict if available
        """
        raw_points = {}

        # Path 1: standard method
        if hasattr(result, "get_sniper_points"):
            raw_points = result.get_sniper_points() or {}

        # Path 2: direct dashboard traversal when standard path yields empty values
        if not any(raw_points.get(k) for k in ("ideal_buy", "secondary_buy", "stop_loss", "take_profit")):
            dashboard = getattr(result, "dashboard", None)
            if isinstance(dashboard, dict):
                raw_points = self._find_sniper_in_dashboard(dashboard) or raw_points

        # Path 3: try raw_result for agent mode results
        if not any(raw_points.get(k) for k in ("ideal_buy", "secondary_buy", "stop_loss", "take_profit")):
            raw_response = getattr(result, "raw_response", None)
            if isinstance(raw_response, dict):
                raw_points = self._find_sniper_in_dashboard(raw_response) or raw_points

        return {
            "ideal_buy": self._parse_sniper_value(raw_points.get("ideal_buy")),
            "secondary_buy": self._parse_sniper_value(raw_points.get("secondary_buy")),
            "stop_loss": self._parse_sniper_value(raw_points.get("stop_loss")),
            "take_profit": self._parse_sniper_value(raw_points.get("take_profit")),
        }

    @staticmethod
    def _find_sniper_in_dashboard(d: dict) -> Optional[Dict[str, Any]]:
        """
        Recursively search for sniper_points in a dashboard dict.
        Handles various nesting: dashboard.battle_plan.sniper_points,
        dashboard.dashboard.battle_plan.sniper_points, etc.
        """
        if not isinstance(d, dict):
            return None

        # Direct: d has sniper_points keys at top level
        if "ideal_buy" in d:
            return d

        # d.sniper_points
        sp = d.get("sniper_points")
        if isinstance(sp, dict) and sp:
            return sp

        # d.battle_plan.sniper_points
        bp = d.get("battle_plan")
        if isinstance(bp, dict):
            sp = bp.get("sniper_points")
            if isinstance(sp, dict) and sp:
                return sp

        # d.dashboard.battle_plan.sniper_points (double-nested)
        inner = d.get("dashboard")
        if isinstance(inner, dict):
            bp = inner.get("battle_plan")
            if isinstance(bp, dict):
                sp = bp.get("sniper_points")
                if isinstance(sp, dict) and sp:
                    return sp

        return None

    @staticmethod
    def _build_fallback_url_key(
        code: str,
        title: str,
        source: str,
        published_date: Optional[datetime]
    ) -> str:
        """
        生成无 URL 时的去重键（确保稳定且较短）
        """
        date_str = published_date.isoformat() if published_date else ""
        raw_key = f"{code}|{title}|{source}|{date_str}"
        digest = hashlib.md5(raw_key.encode("utf-8")).hexdigest()
        return f"no-url:{code}:{digest}"

    def ensure_conversation_session(
        self,
        session_id: str,
        *,
        owner_id: Optional[str] = None,
        title: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> ConversationSessionRecord:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            raise ValueError("session_id is required")
        resolved_owner_id = self.require_user_id(owner_id)

        def _upsert(active_session: Session) -> ConversationSessionRecord:
            row = active_session.execute(
                select(ConversationSessionRecord)
                .where(ConversationSessionRecord.session_id == normalized_session_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = ConversationSessionRecord(
                    session_id=normalized_session_id,
                    owner_id=resolved_owner_id,
                    title=(title or "").strip()[:255] or None,
                )
                active_session.add(row)
                active_session.flush()
            else:
                if resolved_owner_id and row.owner_id and resolved_owner_id != row.owner_id:
                    raise ValueError(
                        f"Conversation session {normalized_session_id} belongs to another owner"
                    )
                if row.owner_id is None:
                    row.owner_id = resolved_owner_id
                if title and not row.title:
                    row.title = title.strip()[:255] or row.title
                row.updated_at = datetime.now()
                active_session.flush()
            return row

        if session is not None:
            return _upsert(session)
        with self.session_scope() as active_session:
            return _upsert(active_session)

    def save_conversation_message(
        self,
        session_id: str,
        role: str,
        content: str,
        owner_id: Optional[str] = None,
    ) -> None:
        """
        保存 Agent 对话消息
        """
        resolved_owner_id = self.require_user_id(owner_id)
        with self.session_scope() as session:
            session_row = self.ensure_conversation_session(
                session_id,
                owner_id=resolved_owner_id,
                title=content if role == "user" else None,
                session=session,
            )
            msg = ConversationMessage(
                session_id=session_id,
                role=role,
                content=content
            )
            session.add(msg)
            session_row.updated_at = datetime.now()
            if role == "user" and not session_row.title:
                session_row.title = str(content or "").strip()[:255] or None
            session.flush()
            if self._phase_b_enabled and self._phase_b_store is not None:
                self._phase_b_store.append_chat_message_shadow(
                    session_key=session_id,
                    owner_user_id=resolved_owner_id,
                    role=role,
                    content=content,
                    title_hint=content if role == "user" else None,
                    created_at=msg.created_at,
                )

    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 20,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        获取 Agent 对话历史
        """
        with self.session_scope() as session:
            if not include_all_owners:
                self._require_conversation_session_access(
                    session=session,
                    session_id=session_id,
                    owner_id=owner_id,
                )
            stmt = select(ConversationMessage).filter(
                ConversationMessage.session_id == session_id
            ).order_by(ConversationMessage.created_at.desc()).limit(limit)
            messages = session.execute(stmt).scalars().all()

            # 倒序返回，保证时间顺序
            return [{"role": msg.role, "content": msg.content} for msg in reversed(messages)]

    def conversation_session_exists(self, session_id: str) -> bool:
        """Return True when at least one message exists for the given session."""
        with self.session_scope() as session:
            stmt = (
                select(ConversationSessionRecord.id)
                .where(ConversationSessionRecord.session_id == session_id)
                .limit(1)
            )
            return session.execute(stmt).scalar() is not None

    def get_chat_sessions(
        self,
        limit: int = 50,
        session_prefix: Optional[str] = None,
        extra_session_ids: Optional[List[str]] = None,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        获取聊天会话列表（从 conversation_messages 聚合）

        Args:
            limit: Maximum number of sessions to return.
            session_prefix: If provided, only return sessions whose session_id
                starts with this prefix.  Used for per-user isolation (e.g.
                ``"telegram_12345"``).
            extra_session_ids: Optional exact session ids to include in
                addition to the scoped prefix.

        Returns:
            按最近活跃时间倒序的会话列表，每条包含 session_id, title, message_count, last_active
        """
        with self.session_scope() as session:
            normalized_prefix = None
            if session_prefix:
                normalized_prefix = session_prefix if session_prefix.endswith(":") else f"{session_prefix}:"
            exact_ids = [sid for sid in (extra_session_ids or []) if sid]

            ownership_conditions = []
            if not include_all_owners:
                ownership_conditions.append(
                    ConversationSessionRecord.owner_id == self.require_user_id(owner_id)
                )
            session_id_filters = []
            if normalized_prefix:
                session_id_filters.append(
                    ConversationSessionRecord.session_id.startswith(normalized_prefix)
                )
            if exact_ids:
                session_id_filters.append(ConversationSessionRecord.session_id.in_(exact_ids))
            query = select(ConversationSessionRecord)
            if ownership_conditions:
                query = query.where(and_(*ownership_conditions))
            if session_id_filters:
                query = query.where(or_(*session_id_filters))
            stmt = (
                query
                .order_by(desc(ConversationSessionRecord.updated_at), desc(ConversationSessionRecord.id))
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()

            results = []
            for row in rows:
                sid = row.session_id
                message_count = int(
                    session.execute(
                        select(func.count(ConversationMessage.id))
                        .where(ConversationMessage.session_id == sid)
                    ).scalar() or 0
                )
                title = ((row.title or "新对话")[:60]) if row.title else "新对话"

                results.append({
                    "session_id": sid,
                    "title": title,
                    "message_count": message_count,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "last_active": row.updated_at.isoformat() if row.updated_at else None,
                })
            return results

    def get_conversation_messages(
        self,
        session_id: str,
        limit: int = 100,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        获取单个会话的完整消息列表（用于前端恢复历史）
        """
        with self.session_scope() as session:
            if not include_all_owners:
                self._require_conversation_session_access(
                    session=session,
                    session_id=session_id,
                    owner_id=owner_id,
                )
            stmt = (
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.created_at)
                .limit(limit)
            )
            messages = session.execute(stmt).scalars().all()
            return [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in messages
            ]

    def delete_conversation_session(
        self,
        session_id: str,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> int:
        """
        删除指定会话的所有消息

        Returns:
            删除的消息数
        """
        with self.session_scope() as session:
            if not include_all_owners:
                self._require_conversation_session_access(
                    session=session,
                    session_id=session_id,
                    owner_id=owner_id,
                )
            if self._phase_b_enabled and self._phase_b_store is not None:
                self._phase_b_store.delete_chat_session_shadow(
                    session_id,
                    owner_user_id=None if include_all_owners else self.require_user_id(owner_id),
                )
            result = session.execute(
                delete(ConversationMessage).where(
                    ConversationMessage.session_id == session_id
                )
            )
            session.execute(
                delete(ConversationSessionRecord).where(
                    ConversationSessionRecord.session_id == session_id
                )
            )
            return result.rowcount

    def _require_conversation_session_access(
        self,
        *,
        session: Session,
        session_id: str,
        owner_id: Optional[str] = None,
    ) -> ConversationSessionRecord:
        resolved_owner_id = self.require_user_id(owner_id)
        row = session.execute(
            select(ConversationSessionRecord)
            .where(
                and_(
                    ConversationSessionRecord.session_id == session_id,
                    ConversationSessionRecord.owner_id == resolved_owner_id,
                )
            )
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            raise ValueError(f"Conversation session not found for owner: {session_id}")
        return row

    # ------------------------------------------------------------------
    # LLM usage tracking
    # ------------------------------------------------------------------

    def record_llm_usage(
        self,
        call_type: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        stock_code: Optional[str] = None,
    ) -> None:
        """Append one LLM call record to llm_usage."""
        row = LLMUsage(
            call_type=call_type,
            model=model or "unknown",
            stock_code=stock_code,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        with self.session_scope() as session:
            session.add(row)

    def get_llm_usage_summary(
        self,
        from_dt: datetime,
        to_dt: datetime,
    ) -> Dict[str, Any]:
        """Return aggregated token usage between from_dt and to_dt.

        Returns a dict with keys:
          total_calls, total_tokens,
          by_call_type: list of {call_type, calls, total_tokens},
          by_model:     list of {model, calls, total_tokens}
        """
        with self.session_scope() as session:
            base_filter = and_(
                LLMUsage.called_at >= from_dt,
                LLMUsage.called_at <= to_dt,
            )

            # Overall totals
            totals = session.execute(
                select(
                    func.count(LLMUsage.id).label("calls"),
                    func.coalesce(func.sum(LLMUsage.total_tokens), 0).label("tokens"),
                ).where(base_filter)
            ).one()

            # Breakdown by call_type
            by_type_rows = session.execute(
                select(
                    LLMUsage.call_type,
                    func.count(LLMUsage.id).label("calls"),
                    func.coalesce(func.sum(LLMUsage.total_tokens), 0).label("tokens"),
                )
                .where(base_filter)
                .group_by(LLMUsage.call_type)
                .order_by(desc(func.sum(LLMUsage.total_tokens)))
            ).all()

            # Breakdown by model
            by_model_rows = session.execute(
                select(
                    LLMUsage.model,
                    func.count(LLMUsage.id).label("calls"),
                    func.coalesce(func.sum(LLMUsage.total_tokens), 0).label("tokens"),
                )
                .where(base_filter)
                .group_by(LLMUsage.model)
                .order_by(desc(func.sum(LLMUsage.total_tokens)))
            ).all()

        return {
            "total_calls": totals.calls,
            "total_tokens": totals.tokens,
            "by_call_type": [
                {"call_type": r.call_type, "calls": r.calls, "total_tokens": r.tokens}
                for r in by_type_rows
            ],
            "by_model": [
                {"model": r.model, "calls": r.calls, "total_tokens": r.tokens}
                for r in by_model_rows
            ],
        }


# 便捷函数
def get_db() -> DatabaseManager:
    """获取数据库管理器实例的快捷方式"""
    return DatabaseManager.get_instance()


def persist_llm_usage(
    usage: Dict[str, Any],
    model: str,
    call_type: str,
    stock_code: Optional[str] = None,
) -> None:
    """Fire-and-forget: write one LLM call record to llm_usage. Never raises."""
    try:
        db = DatabaseManager.get_instance()
        db.record_llm_usage(
            call_type=call_type,
            model=model,
            prompt_tokens=usage.get("prompt_tokens", 0) or 0,
            completion_tokens=usage.get("completion_tokens", 0) or 0,
            total_tokens=usage.get("total_tokens", 0) or 0,
            stock_code=stock_code,
        )
    except Exception as exc:
        logging.getLogger(__name__).warning("[LLM usage] failed to persist usage record: %s", exc)


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    db = get_db()
    
    print("=== 数据库测试 ===")
    print(f"数据库初始化成功")
    
    # 测试检查今日数据
    has_data = db.has_today_data('600519')
    print(f"茅台今日是否有数据: {has_data}")
    
    # 测试保存数据
    test_df = pd.DataFrame({
        'date': [date.today()],
        'open': [1800.0],
        'high': [1850.0],
        'low': [1780.0],
        'close': [1820.0],
        'volume': [10000000],
        'amount': [18200000000],
        'pct_chg': [1.5],
        'ma5': [1810.0],
        'ma10': [1800.0],
        'ma20': [1790.0],
        'volume_ratio': [1.2],
    })
    
    saved = db.save_daily_data(test_df, '600519', 'TestSource')
    print(f"保存测试数据: {saved} 条")
    
    # 测试获取上下文
    context = db.get_analysis_context('600519')
    print(f"分析上下文: {context}")
