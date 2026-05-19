# -*- coding: utf-8 -*-

"""

===================================

Aguwatchlistguzhinenganalysisxitong - cunchuceng

===================================



zhize竊?
1. guanli SQLite shujukulianjie竊늕anlimoshi竊?
2. dingyi ORM shujumodel

3. tigongshujucunqujiekou

4. shixianzhinenggengxinluoji竊늕uandianxuchuan竊?
"""



import atexit

from contextlib import contextmanager

import hashlib

import json

import logging

import re

import time

from datetime import datetime, date, timedelta

from typing import Optional, List, Dict, Any, TYPE_CHECKING, Tuple, Callable, TypeVar



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

    event,

    func,

)

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from sqlalchemy.orm import (

    declarative_base,

    sessionmaker,

    Session,

)

from sqlalchemy.exc import IntegrityError, OperationalError



from src.config import get_config



logger = logging.getLogger(__name__)

T = TypeVar("T")



# SQLAlchemy ORM jilei

Base = declarative_base()



if TYPE_CHECKING:

    from src.search_service import SearchResponse





# === shujumodeldingyi ===



class StockDaily(Base):

    """

    stockrixianshujumodel

    

    cunchumeiriquoteshujuhejisuandejishuzhibiao

    zhichiduostock?갺uoriqideweiyiyueshu

    """

    __tablename__ = 'stock_daily'

    

    # zhujian

    id = Column(Integer, primary_key=True, autoincrement=True)

    

    # stockdaima竊늭u 600519, 000001竊?
    code = Column(String(10), nullable=False, index=True)

    

    # jiaoyiriqi

    date = Column(Date, nullable=False, index=True)

    

    # OHLC shuju

    open = Column(Float)

    high = Column(Float)

    low = Column(Float)

    close = Column(Float)

    

    # chengjiaoshuju

    volume = Column(Float)  # chengjiaoliang竊늛u竊?
    amount = Column(Float)  # chengjiaoe竊늶uan竊?
    pct_chg = Column(Float)  # zhangdiefu竊?竊?
    

    # jishuzhibiao

    ma5 = Column(Float)

    ma10 = Column(Float)

    ma20 = Column(Float)

    volume_ratio = Column(Float)  # liangbi

    

    # shujulaiyuan

    data_source = Column(String(50))  # recordshujulaiyuan竊늭u AkshareFetcher竊?
    

    # gengxinshijian

    created_at = Column(DateTime, default=datetime.now)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    

    # weiyiyueshu竊쉞ongyistocktongyiriqizhinengyouyitiaoshuju

    __table_args__ = (

        UniqueConstraint('code', 'date', name='uix_code_date'),

        Index('ix_code_date', 'code', 'date'),

    )

    

    def __repr__(self):

        return f"<StockDaily(code={self.code}, date={self.date}, close={self.close})>"

    

    def to_dict(self) -> Dict[str, Any]:

        """zhuanhuanweizidian"""

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

    xinwenqingbaoshujumodel



    cunchusousuodaodexinwenqingbaotiaomu竊똹ongyuhouxuanalysisyuchaxun

    """

    __tablename__ = 'news_intel'



    id = Column(Integer, primary_key=True, autoincrement=True)



    # guanlianyonghuchaxuncaozuo

    query_id = Column(String(64), index=True)



    # stockxinxi

    code = Column(String(10), nullable=False, index=True)

    name = Column(String(50))



    # sousuoshangxiawen

    dimension = Column(String(32), index=True)  # latest_news / risk_check / earnings / market_analysis / industry

    query = Column(String(255))

    provider = Column(String(32), index=True)



    # xinwenneirong

    title = Column(String(300), nullable=False)

    snippet = Column(Text)

    url = Column(String(1000), nullable=False)

    source = Column(String(100))

    published_date = Column(DateTime, index=True)



    # rukushijian

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

    jibenmianshangxiawenkuaizhao竊늁0 write-only竊됥?


    jinyongyuxieru竊똺hulianlubuyilaiduqugaibiao竊똟ianyuhouxuhuice/huaxiangkuozhan??
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





class AnalysisHistory(Base):

    """

    analysisjieguolishirecordmodel



    savemeicianalysisjieguo竊똺hichian query_id/stockdaimajiansuo

    """

    __tablename__ = 'analysis_history'



    id = Column(Integer, primary_key=True, autoincrement=True)



    # guanlianchaxunlianlu

    query_id = Column(String(64), index=True)



    # stockxinxi

    code = Column(String(10), nullable=False, index=True)

    name = Column(String(50))

    report_type = Column(String(16), index=True)



    # hexinjielun

    sentiment_score = Column(Integer)

    operation_advice = Column(String(20))

    trend_prediction = Column(String(50))

    analysis_summary = Column(Text)



    # xiangxishuju

    raw_result = Column(Text)

    news_content = Column(Text)

    context_snapshot = Column(Text)



    # jujidianwei竊늶ongyuhuice竊?
    ideal_buy = Column(Float)

    secondary_buy = Column(Float)

    stop_loss = Column(Float)

    take_profit = Column(Float)



    created_at = Column(DateTime, default=datetime.now, index=True)



    __table_args__ = (

        Index('ix_analysis_code_time', 'code', 'created_at'),

    )



    def to_dict(self) -> Dict[str, Any]:

        """zhuanhuanweizidian"""

        return {

            'id': self.id,

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





class BacktestResult(Base):

    """Backtest result for a single analysis record."""



    __tablename__ = 'backtest_results'



    id = Column(Integer, primary_key=True, autoincrement=True)



    analysis_history_id = Column(

        Integer,

        ForeignKey('analysis_history.id'),

        nullable=False,

        index=True,

    )



    # rongyuziduan竊똟ianyuanstockshaixuan

    code = Column(String(10), nullable=False, index=True)

    analysis_date = Column(Date, index=True)



    # huicecanshu

    eval_window_days = Column(Integer, nullable=False, default=10)

    engine_version = Column(String(16), nullable=False, default='v1')



    # zhuangtai

    eval_status = Column(String(16), nullable=False, default='pending')

    evaluated_at = Column(DateTime, default=datetime.now, index=True)



    # jianyikuaizhao竊늒imianweilaianalysisziduanbianhuadaozhihuicebukejieshi竊?
    operation_advice = Column(String(20))

    position_recommendation = Column(String(8))  # long/cash



    # jiageyushouyi

    start_price = Column(Float)

    end_close = Column(Float)

    max_high = Column(Float)

    min_low = Column(Float)

    stock_return_pct = Column(Float)



    # fangxiangyujieguo

    direction_expected = Column(String(16))  # up/down/flat/not_down

    direction_correct = Column(Boolean, nullable=True)

    outcome = Column(String(16))  # win/loss/neutral



    # mubiaojiamingzhong竊늞in long qieconfiglezhiying/zhisunshiyouyiyi竊?
    stop_loss = Column(Float)

    take_profit = Column(Float)

    hit_stop_loss = Column(Boolean)

    hit_take_profit = Column(Boolean)

    first_hit = Column(String(16))  # take_profit/stop_loss/ambiguous/neither/not_applicable

    first_hit_date = Column(Date)

    first_hit_trading_days = Column(Integer)



    # monizhixing竊늢ong-only竊?
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

        Index('ix_backtest_code_date', 'code', 'analysis_date'),

    )





class BacktestSummary(Base):

    """Backtest summary metrics for one stock or the overall scope."""


    __tablename__ = 'backtest_summaries'



    id = Column(Integer, primary_key=True, autoincrement=True)



    scope = Column(String(16), nullable=False, index=True)  # overall/stock

    code = Column(String(16), index=True)



    eval_window_days = Column(Integer, nullable=False, default=10)

    engine_version = Column(String(16), nullable=False, default='v1')

    computed_at = Column(DateTime, default=datetime.now, index=True)



    # jishu

    total_evaluations = Column(Integer, default=0)

    completed_count = Column(Integer, default=0)

    insufficient_count = Column(Integer, default=0)

    long_count = Column(Integer, default=0)

    cash_count = Column(Integer, default=0)



    win_count = Column(Integer, default=0)

    loss_count = Column(Integer, default=0)

    neutral_count = Column(Integer, default=0)



    # zhunquelv/shenglv

    direction_accuracy_pct = Column(Float)

    win_rate_pct = Column(Float)

    neutral_rate_pct = Column(Float)



    # shouyi

    avg_stock_return_pct = Column(Float)

    avg_simulated_return_pct = Column(Float)



    # mubiaojiachufatongji竊늞in long qieconfigzhiying/zhisunshitongji竊?
    stop_loss_trigger_rate = Column(Float)

    take_profit_trigger_rate = Column(Float)

    ambiguous_rate = Column(Float)

    avg_days_to_first_hit = Column(Float)



    # zhenduanziduan竊뉺SON zifuchuan竊?
    advice_breakdown_json = Column(Text)

    diagnostics_json = Column(Text)



    __table_args__ = (

        UniqueConstraint(

            'scope',

            'code',

            'eval_window_days',

            'engine_version',

            name='uix_backtest_summary_scope_code_window_version',

        ),

    )





class PortfolioAccount(Base):

    """Portfolio account metadata."""



    __tablename__ = 'portfolio_accounts'



    id = Column(Integer, primary_key=True, autoincrement=True)

    owner_id = Column(String(64), index=True)

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

    Agent duihualishirecordbiao

    """

    __tablename__ = 'conversation_messages'



    id = Column(Integer, primary_key=True, autoincrement=True)

    session_id = Column(String(100), index=True, nullable=False)

    role = Column(String(20), nullable=False)  # user, assistant, system

    content = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.now, index=True)





class LLMUsage(Base):

    """One row per litellm.completion() call ??token-usage audit log."""



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





class AlertRuleRecord(Base):

    """Persisted alert rule managed through the Alert API."""



    __tablename__ = 'alert_rules'



    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String(64), nullable=False)

    target_scope = Column(String(32), nullable=False, default='single_symbol', index=True)

    target = Column(String(64), nullable=False, index=True)

    alert_type = Column(String(32), nullable=False, index=True)

    parameters = Column(Text, nullable=False, default='{}')

    severity = Column(String(16), nullable=False, default='warning', index=True)

    enabled = Column(Boolean, nullable=False, default=True, index=True)

    source = Column(String(16), nullable=False, default='api', index=True)

    cooldown_policy = Column(Text)

    notification_policy = Column(Text)

    created_at = Column(DateTime, default=datetime.now, index=True)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)



    __table_args__ = (

        Index('ix_alert_rule_type_target', 'alert_type', 'target'),

    )





class AlertTriggerRecord(Base):

    """Alert trigger history row.



    P1 exposes read APIs and table shape; runtime writer integration lands in

    later phases.

    """



    __tablename__ = 'alert_triggers'



    id = Column(Integer, primary_key=True, autoincrement=True)

    rule_id = Column(Integer, index=True)

    target = Column(String(64), nullable=False, index=True)

    observed_value = Column(Float)

    threshold = Column(Float)

    reason = Column(Text)

    data_source = Column(String(64))

    data_timestamp = Column(DateTime, index=True)

    triggered_at = Column(DateTime, default=datetime.now, index=True)

    status = Column(String(16), nullable=False, default='triggered', index=True)

    diagnostics = Column(Text)



    __table_args__ = (

        Index('ix_alert_trigger_rule_time', 'rule_id', 'triggered_at'),

    )





class AlertNotificationRecord(Base):

    """Notification attempt row for alert triggers.



    P1 exposes read APIs and table shape; runtime writer integration lands in

    later phases.

    """



    __tablename__ = 'alert_notifications'



    id = Column(Integer, primary_key=True, autoincrement=True)

    trigger_id = Column(Integer, index=True)

    channel = Column(String(32), nullable=False, index=True)

    attempt = Column(Integer, nullable=False, default=1)

    success = Column(Boolean, nullable=False, default=False, index=True)

    error_code = Column(String(64))

    retryable = Column(Boolean, nullable=False, default=False)

    latency_ms = Column(Integer)

    diagnostics = Column(Text)

    created_at = Column(DateTime, default=datetime.now, index=True)



    __table_args__ = (

        Index('ix_alert_notification_trigger_channel', 'trigger_id', 'channel'),

    )





class AlertCooldownRecord(Base):

    """Persisted alert cooldown state for DB-managed alert rules."""



    __tablename__ = 'alert_cooldowns'



    id = Column(Integer, primary_key=True, autoincrement=True)

    rule_id = Column(Integer, index=True)

    # Reserved for future non-DB/expanded-scope rules; P4 queries by rule_id.

    rule_key = Column(String(255), index=True)

    target = Column(String(64), nullable=False, index=True)

    severity = Column(String(16), nullable=False, default='warning', index=True)

    last_triggered_at = Column(DateTime, index=True)

    cooldown_until = Column(DateTime, index=True)

    reason = Column(Text)

    state = Column(String(16), nullable=False, default='active', index=True)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, index=True)



    __table_args__ = (

        UniqueConstraint('rule_id', 'target', 'severity', name='uix_alert_cooldown_rule_target_severity'),

    )





class DatabaseManager:

    """

    shujukuguanliqi - danlimoshi

    

    zhize竊?
    1. guanlishujukulianjiechi

    2. tigong Session shangxiawenguanli

    3. fengzhuangshujucunqucaozuo

    """

    

    _instance: Optional['DatabaseManager'] = None

    _initialized: bool = False

    

    def __new__(cls, *args, **kwargs):

        """danlimoshishixian"""

        if cls._instance is None:

            cls._instance = super().__new__(cls)

            cls._instance._initialized = False

        return cls._instance

    

    def __init__(self, db_url: Optional[str] = None):

        """

        chushihuashujukuguanliqi

        

        Args:

            db_url: shujukulianjie URL竊늟exuan竊똫orencongconfigduqu竊?
        """

        if getattr(self, '_initialized', False):

            return



        config = get_config()

        if db_url is None:

            db_url = config.get_db_url()



        self._db_url = db_url

        self._sqlite_wal_enabled = config.sqlite_wal_enabled

        self._sqlite_busy_timeout_ms = config.sqlite_busy_timeout_ms

        self._sqlite_write_retry_max = config.sqlite_write_retry_max

        self._sqlite_write_retry_base_delay = config.sqlite_write_retry_base_delay



        engine_kwargs = {

            "echo": False,

            "pool_pre_ping": True,

        }

        if str(db_url).startswith("sqlite:") and self._sqlite_busy_timeout_ms > 0:

            engine_kwargs["connect_args"] = {

                "timeout": self._sqlite_busy_timeout_ms / 1000,

            }



        # chuangjianshujukuyinqing

        self._engine = create_engine(

            db_url,

            **engine_kwargs,

        )

        self._is_sqlite_engine = self._engine.url.get_backend_name() == 'sqlite'

        self._sqlite_file_db = self._is_sqlite_engine and self._is_file_sqlite_database()

        self._install_sqlite_pragma_handler()

        

        # chuangjian Session gongchang

        self._SessionLocal = sessionmaker(

            bind=self._engine,

            autocommit=False,

            autoflush=False,

        )

        

        # chuangjiansuoyoubiao

        Base.metadata.create_all(self._engine)



        self._initialized = True

        logger.info(f"shujukuchushihuawancheng: {db_url}")



        # zhucetuichugouzi竊똰uebaochengxutuichushicloseshujukulianjie

        atexit.register(DatabaseManager._cleanup_engine, self._engine)

    

    @classmethod

    def get_instance(cls) -> 'DatabaseManager':

        """huoqudanlishili"""

        if cls._instance is None:

            cls._instance = cls()

        return cls._instance

    

    @classmethod

    def reset_instance(cls) -> None:

        """Reset the singleton instance for tests."""

        if cls._instance is not None:

            if hasattr(cls._instance, '_engine') and cls._instance._engine is not None:

                cls._instance._engine.dispose()

            cls._instance._initialized = False

            cls._instance = None



    @classmethod

    def _cleanup_engine(cls, engine) -> None:

        """

        qinglishujukuyinqing竊늏texit gouzi竊?


        quebaochengxutuichushiclosesuoyoushujukulianjie竊똟imian ResourceWarning



        Args:

            engine: SQLAlchemy yinqingduixiang

        """

        try:

            if engine is not None:

                engine.dispose()

                logger.debug("shujukuyinqingyiqingli")

        except Exception as e:

            logger.warning(f"qinglishujukuyinqingshichucuo: {e}")



    def _install_sqlite_pragma_handler(self) -> None:

        """Install contention protection settings for SQLite connections."""

        if not self._is_sqlite_engine:

            return



        @event.listens_for(self._engine, "connect")

        def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:

            cursor = dbapi_connection.cursor()

            try:

                cursor.execute(f"PRAGMA busy_timeout={int(self._sqlite_busy_timeout_ms)}")

                if self._sqlite_file_db and self._sqlite_wal_enabled:

                    cursor.execute("PRAGMA journal_mode=WAL")

            except Exception as exc:

                logger.warning("chushihua SQLite PRAGMA shibai: %s", exc)

            finally:

                cursor.close()



    def _is_file_sqlite_database(self) -> bool:

        database = (self._engine.url.database or "").strip()

        return bool(database) and database.lower() != ":memory:"



    def _run_write_transaction(

        self,

        operation_name: str,

        write_operation: Callable[[Session], T],

    ) -> T:

        max_retries = self._sqlite_write_retry_max if self._is_sqlite_engine else 0



        for attempt in range(max_retries + 1):

            session = self.get_session()

            try:

                if self._is_sqlite_engine:

                    # Acquire the SQLite writer lock before any reads inside

                    # `write_operation()` so pre-write existence checks and the

                    # later upsert share one consistent write window.

                    session.connection().exec_driver_sql("BEGIN IMMEDIATE")

                result = write_operation(session)

                session.commit()

                return result

            except OperationalError as exc:

                session.rollback()

                if (

                    self._is_sqlite_engine

                    and self._is_sqlite_locked_error(exc)

                    and attempt < max_retries

                ):

                    delay = self._sqlite_write_retry_base_delay * (2 ** attempt)

                    logger.warning(

                        "SQLite xierusuochongtu竊똺hunbeiretry: %s (%s/%s, %.2fs)",

                        operation_name,

                        attempt + 1,

                        max_retries,

                        delay,

                    )

                    if delay > 0:

                        time.sleep(delay)

                    continue

                raise

            except Exception:

                session.rollback()

                raise

            finally:

                session.close()



    @staticmethod

    def _is_sqlite_locked_error(exc: OperationalError) -> bool:

        err_text = str(getattr(exc, "orig", exc)).lower()

        return any(

            token in err_text

            for token in (

                "database is locked",

                "database schema is locked",

                "database table is locked",

            )

        )



    @staticmethod

    def _normalize_daily_date(value: Any) -> Any:

        if isinstance(value, str):

            return datetime.strptime(value, '%Y-%m-%d').date()

        if isinstance(value, pd.Timestamp):

            return value.date()

        if isinstance(value, datetime):

            return value.date()

        return value



    @staticmethod

    def _normalize_sql_value(value: Any) -> Any:

        return None if pd.isna(value) else value

    

    def get_session(self) -> Session:

        """

        huoqushujuku Session

        

        shiyongshili:

            with db.get_session() as session:

                # zhixingchaxun

                session.commit()  # ruguoxuyao

        """

        if not getattr(self, '_initialized', False) or not hasattr(self, '_SessionLocal'):

            raise RuntimeError(

                "DatabaseManager is not initialized correctly. "
                "Use DatabaseManager.get_instance() to obtain an instance."

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

    

    def has_today_data(self, code: str, target_date: Optional[date] = None) -> bool:

        """

        jianchashifouyiyouzhidingriqideshuju

        

        yongyuduandianxuchuanluoji竊쉜uguoyiyoushujuzetiaoguowangluoqingqiu

        

        Args:

            code: stockdaima

            target_date: mubiaoriqi竊늤orenjintian竊?
            

        Returns:

            shifoucunzaishuju

        """

        if target_date is None:

            target_date = date.today()

        # zhuyi竊쉦helide target_date yuyishi?쐚iranri?앾펽erbushi?쐚uixinjiaoyiri?앫?
        # zaizhoumo/jiejiari/feijiaoyiriyunxingshi竊똨ishishujukuyiyouzuixinjiaoyirishuju竊똺heliyehuifanhui False??
        # gaixingweimuqianbaoliu竊늏nxuqiubugailuoji竊됥?
        

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

        huoquzuijin N tiandeshuju

        

        yongyujisuan"xiangbizuori"debianhua

        

        Args:

            code: stockdaima

            days: huoqutianshu

            

        Returns:

            StockDaily duixiangliebiao竊늏nriqijiangxu竊?
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

        savexinwenqingbaodaoshujuku



        quzhongcelve竊?
        - youxianan URL quzhong竊늳eiyiyueshu竊?
        - URL queshishian title + source + published_date jinxingruanquzhong



        guanliancelve竊?
        - query_context recordyonghuchaxunxinxi竊늩ingtai?걓onghu?갿uihua?걓uanshizhilingdeng竊?
        """

        if not response or not response.results:

            return 0



        saved_count = 0

        query_ctx = query_context or {}

        current_query_id = (query_ctx.get("query_id") or "").strip()



        def _write(session: Session) -> int:

            local_saved_count = 0



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

                    continue



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

                    local_saved_count += 1

                except IntegrityError:

                    logger.debug("xinwenqingbaochongfu竊늶itiaoguo竊? %s %s", code, url_key)



            return local_saved_count



        try:

            saved_count = self._run_write_transaction(

                f"save_news_intel[{code}]",

                _write,

            )

            logger.info(f"savexinwenqingbaochenggong: {code}, xinzeng {saved_count} tiao")

        except Exception as e:

            logger.error(f"savexinwenqingbaoshibai: {e}")

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

        Save a fundamental snapshot. Failures are swallowed and the method returns 0 or 1.
        """

        if not query_id or not code or payload is None:

            return 0



        try:

            def _write(session: Session) -> int:

                session.add(

                    FundamentalSnapshot(

                        query_id=query_id,

                        code=code,

                        payload=self._safe_json_dumps(payload),

                        source_chain=self._safe_json_dumps(source_chain or []),

                        coverage=self._safe_json_dumps(coverage or {}),

                    )

                )

                return 1

            return self._run_write_transaction(

                f"save_fundamental_snapshot[{query_id}:{code}]",

                _write,

            )

        except Exception as e:

            logger.debug(

                "jibenmiankuaizhaoxierushibai竊늗ail-open竊? query_id=%s code=%s err=%s",

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

        Return the latest fundamental snapshot payload for a query_id and code.


        Return None when no snapshot exists or a read fails.
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

                    "jibenmiankuaizhaoduqushibai竊늗ail-open竊? query_id=%s code=%s err=%s",

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

        huoquzhidingstockzuijin N tiandexinwenqingbao

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

        genju query_id huoquxinwenqingbaoliebiao



        Args:

            query_id: analysisrecordweiyibiaoshi

            limit: fanhuishuliangxianzhi



        Returns:

            NewsIntel liebiao竊늏nfabushijianhuozhuaqushijiandaoxu竊?
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

        save_snapshot: bool = True

    ) -> int:

        """

        saveanalysisjieguolishirecord

        """

        if result is None:

            return 0



        sniper_points = self._extract_sniper_points(result)

        raw_result = self._build_raw_result(result)

        context_text = None

        if save_snapshot and context_snapshot is not None:

            context_text = self._safe_json_dumps(context_snapshot)



        try:

            def _write(session: Session) -> int:

                session.add(

                    AnalysisHistory(

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

                )

                return 1

            return self._run_write_transaction(

                f"save_analysis_history[{result.code}]",

                _write,

            )

        except Exception as e:

            logger.error(f"saveanalysislishishibai: {e}")

            return 0



    def get_analysis_history(

        self,

        code: Optional[str] = None,

        query_id: Optional[str] = None,

        days: int = 30,

        limit: int = 50,

        exclude_query_id: Optional[str] = None,

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

        limit: int = 20

    ) -> Tuple[List[AnalysisHistory], int]:

        """

        fenyechaxunanalysislishirecord竊늕aizongshu竊?
        

        Args:

            code: stockdaimashaixuan

            start_date: kaishiriqi竊늜an竊?
            end_date: jieshuriqi竊늜an竊?
            offset: pianyiliang竊늯iaoguoqian N tiao竊?
            limit: meiyeshuliang

            

        Returns:

            Tuple[List[AnalysisHistory], int]: (recordliebiao, zongshu)

        """

        from sqlalchemy import func

        

        with self.get_session() as session:

            conditions = []

            

            if code:

                conditions.append(AnalysisHistory.code == code)

            if start_date:

                # created_at >= start_date 00:00:00

                conditions.append(AnalysisHistory.created_at >= datetime.combine(start_date, datetime.min.time()))

            if end_date:

                # created_at < end_date+1 00:00:00 (ji <= end_date 23:59:59)

                conditions.append(AnalysisHistory.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()))

            

            # goujian where ziju

            where_clause = and_(*conditions) if conditions else True

            

            # chaxunzongshu

            total_query = select(func.count(AnalysisHistory.id)).where(where_clause)

            total = session.execute(total_query).scalar() or 0

            

            # chaxunfenyeshuju

            data_query = (

                select(AnalysisHistory)

                .where(where_clause)

                .order_by(desc(AnalysisHistory.created_at))

                .offset(offset)

                .limit(limit)

            )

            results = session.execute(data_query).scalars().all()

            

            return list(results), total

    

    def get_analysis_history_by_id(self, record_id: int) -> Optional[AnalysisHistory]:

        """

        genjushujukuzhujian ID chaxundantiaoanalysislishirecord

        

        youyu query_id kenengchongfu竊늩ilianganalysisshiduotiaorecordgongxiangtongyi query_id竊됵펽

        shiyongzhujian ID quebaojingquechaxunweiyirecord??
        

        Args:

            record_id: analysislishirecorddezhujian ID

            

        Returns:

            AnalysisHistory duixiang竊똟ucunzaifanhui None

        """

        with self.get_session() as session:

            result = session.execute(

                select(AnalysisHistory).where(AnalysisHistory.id == record_id)

            ).scalars().first()

            return result



    def delete_analysis_history_records(self, record_ids: List[int]) -> int:

        """

        deletezhidingdeanalysislishirecord??


        tongshiqingliyilaizhexielishirecorddehuicejieguo竊똟imianwaijianyueshushibai??


        Args:

            record_ids: yaodeletedelishirecordzhujian ID liebiao



        Returns:

            shijideletedelishirecordshuliang

        """

        ids = sorted({int(record_id) for record_id in record_ids if record_id is not None})

        if not ids:

            return 0



        with self.session_scope() as session:

            session.execute(

                delete(BacktestResult).where(BacktestResult.analysis_history_id.in_(ids))

            )

            result = session.execute(

                delete(AnalysisHistory).where(AnalysisHistory.id.in_(ids))

            )

            return result.rowcount or 0



    def get_latest_analysis_by_query_id(self, query_id: str) -> Optional[AnalysisHistory]:

        """

        genju query_id chaxunzuixinyitiaoanalysislishirecord



        query_id zaipilianganalysisshikenengchongfu竊똤ufanhuizuijinchuangjiandeyitiao??


        Args:

            query_id: analysisrecordguanliande query_id



        Returns:

            AnalysisHistory duixiang竊똟ucunzaifanhui None

        """

        with self.get_session() as session:

            result = session.execute(

                select(AnalysisHistory)

                .where(AnalysisHistory.query_id == query_id)

                .order_by(desc(AnalysisHistory.created_at))

                .limit(1)

            ).scalars().first()

            return result

    

    def get_data_range(

        self, 

        code: str, 

        start_date: date, 

        end_date: date

    ) -> List[StockDaily]:

        """

        huoquzhidingriqifanweideshuju

        

        Args:

            code: stockdaima

            start_date: kaishiriqi

            end_date: jieshuriqi

            

        Returns:

            StockDaily duixiangliebiao

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

        saverixianshujudaoshujuku

        

        celve竊?
        - an `(code, date)` zuopiliang UPSERT竊똹icunzairecordhuifugaigengxin

        - tongyipicineiruocunzaichongfuriqi竊똹izuihouyitiaorecordweizhun

        - SQLite fenzhian chunk xieruyibimianbangdingcanshushangxian

        

        Args:

            df: baohanrixianshujude DataFrame

            code: stockdaima

            data_source: shujulaiyuanmingcheng

            

        Returns:

            bencishijixinzengderecordshu竊늒uhangengxin竊?
        """

        if df is None or df.empty:

            logger.warning(f"saveshujuweikong竊똳iaoguo {code}")

            return 0



        now = datetime.now()

        records_by_date: Dict[date, Dict[str, Any]] = {}

        for row in df.to_dict(orient='records'):

            row_date = self._normalize_daily_date(row.get('date'))

            records_by_date[row_date] = {

                'code': code,

                'date': row_date,

                'open': self._normalize_sql_value(row.get('open')),

                'high': self._normalize_sql_value(row.get('high')),

                'low': self._normalize_sql_value(row.get('low')),

                'close': self._normalize_sql_value(row.get('close')),

                'volume': self._normalize_sql_value(row.get('volume')),

                'amount': self._normalize_sql_value(row.get('amount')),

                'pct_chg': self._normalize_sql_value(row.get('pct_chg')),

                'ma5': self._normalize_sql_value(row.get('ma5')),

                'ma10': self._normalize_sql_value(row.get('ma10')),

                'ma20': self._normalize_sql_value(row.get('ma20')),

                'volume_ratio': self._normalize_sql_value(row.get('volume_ratio')),

                'data_source': data_source,

                'created_at': now,

                'updated_at': now,

            }



        if not records_by_date:

            return 0



        records = list(records_by_date.values())

        batch_dates = list(records_by_date.keys())



        def _write(session: Session) -> int:

            if self._is_sqlite_engine:

                # SQLite has a per-statement bind-parameter limit (commonly 999).

                # Each record has ~15 columns, so chunk upserts to stay within bounds.

                _SQLITE_CHUNK = 50

                # `_run_write_transaction()` opens SQLite writes with

                # `BEGIN IMMEDIATE`, so existence checks and upsert execute

                # within one stable write window.

                existing_dates = set()

                _COUNT_CHUNK = 500

                for j in range(0, len(batch_dates), _COUNT_CHUNK):

                    chunk_dates = batch_dates[j : j + _COUNT_CHUNK]

                    if not chunk_dates:

                        continue

                    existing_dates.update(

                        session.execute(

                            select(StockDaily.date).where(

                                and_(

                                    StockDaily.code == code,

                                    StockDaily.date.in_(chunk_dates),

                                )

                            )

                        ).scalars().all()

                    )

                new_records = [

                    record for record in records if record['date'] not in existing_dates

                ]

                for i in range(0, len(records), _SQLITE_CHUNK):

                    chunk = records[i : i + _SQLITE_CHUNK]

                    stmt = sqlite_insert(StockDaily).values(chunk)

                    excluded = stmt.excluded

                    session.execute(

                        stmt.on_conflict_do_update(

                            index_elements=['code', 'date'],

                            set_={

                                'open': excluded.open,

                                'high': excluded.high,

                                'low': excluded.low,

                                'close': excluded.close,

                                'volume': excluded.volume,

                                'amount': excluded.amount,

                                'pct_chg': excluded.pct_chg,

                                'ma5': excluded.ma5,

                                'ma10': excluded.ma10,

                                'ma20': excluded.ma20,

                                'volume_ratio': excluded.volume_ratio,

                                'data_source': excluded.data_source,

                                'updated_at': excluded.updated_at,

                            },

                        )

                    )

                return len(new_records)

            else:

                existing_rows = {

                    row.date: row

                    for row in session.execute(

                        select(StockDaily).where(

                            and_(

                                StockDaily.code == code,

                                StockDaily.date.in_(batch_dates),

                            )

                        )

                    ).scalars().all()

                }

                new_count = 0

                for record in records:

                    existing = existing_rows.get(record['date'])

                    if existing is None:

                        session.add(StockDaily(**record))

                        new_count += 1

                        continue

                    existing.open = record['open']

                    existing.high = record['high']

                    existing.low = record['low']

                    existing.close = record['close']

                    existing.volume = record['volume']

                    existing.amount = record['amount']

                    existing.pct_chg = record['pct_chg']

                    existing.ma5 = record['ma5']

                    existing.ma10 = record['ma10']

                    existing.ma20 = record['ma20']

                    existing.volume_ratio = record['volume_ratio']

                    existing.data_source = record['data_source']

                    existing.updated_at = record['updated_at']

                return new_count



        try:

            saved_count = self._run_write_transaction(

                f"save_daily_data[{code}]",

                _write,

            )

            logger.info(f"save {code} shujuchenggong竊똸inzeng {saved_count} tiao")

            return saved_count

        except Exception as e:

            logger.error(f"save {code} shujushibai: {e}")

            raise

    

    def get_analysis_context(

        self, 

        code: str,

        target_date: Optional[date] = None

    ) -> Optional[Dict[str, Any]]:

        """

        huoquanalysissuoxudeshangxiawenshuju

        

        fanhuijinrishuju + zuorishujudeduibixinxi

        

        Args:

            code: stockdaima

            target_date: mubiaoriqi竊늤orenjintian竊?
            

        Returns:

            baohanjinrishuju?걕uoriduibidengxinxidezidian

        """

        if target_date is None:

            target_date = date.today()

        # zhuyi竊쉒inguanrucantigongle target_date竊똡andangqianshixianshijishiyongdeshi?쐚uixinliangtianshuju?앾펷get_latest_data竊됵펽

        # bingbuhuian target_date jingquequdangri/qianyijiaoyirideshangxiawen??
        # yinciruoweilaixuyaozhichi?쏿nlishimoutianfupan/zhongsuan?쓉ekejieshixing竊똺helixuyaotiaozheng??
        # gaixingweimuqianbaoliu竊늏nxuqiubugailuoji竊됥?
        

        # huoquzuijin2tianshuju

        recent_data = self.get_latest_data(code, days=2)

        

        if not recent_data:

            logger.warning(f"weizhaodao {code} deshuju")

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

            

            # jisuanxiangbizuoridebianhua

            if yesterday_data.volume and yesterday_data.volume > 0:

                context['volume_change_ratio'] = round(

                    today_data.volume / yesterday_data.volume, 2

                )

            

            if yesterday_data.close and yesterday_data.close > 0:

                context['price_change_ratio'] = round(

                    (today_data.close - yesterday_data.close) / yesterday_data.close * 100, 2

                )

            

            # junxianxingtaipanduan

            context['ma_status'] = self._analyze_ma_status(today_data)

        

        return context

    

    def _analyze_ma_status(self, data: StockDaily) -> str:

        """

        analysisjunxianxingtai

        

        panduantiaojian竊?
        - duotoupailie竊쉉lose > ma5 > ma10 > ma20

        - kongtoupailie竊쉉lose < ma5 < ma10 < ma20

        - zhendangzhengli竊쉛itaqingkuang

        """

        # zhuyi竊쉦helidejunxianxingtaipanduanjiyu?쐁lose/ma5/ma10/ma20?쓏ingtaibijiao竊?
        # weikaolvjunxianguaidian?걒ielv?갿uobutongshujuyuanfuquankoujingchayi??
        # gaixingweimuqianbaoliu竊늏nxuqiubugailuoji竊됥?
        close = data.close or 0

        ma5 = data.ma5 or 0

        ma10 = data.ma10 or 0

        ma20 = data.ma20 or 0

        

        if close > ma5 > ma10 > ma20 > 0:

            return "duotoupailie ?뱢"

        elif close < ma5 < ma10 < ma20 and ma20 > 0:

            return "kongtoupailie ?뱣"

        elif close > ma5 and ma5 > ma10:

            return "duanqixianghao ?뵾"

        elif close < ma5 and ma5 < ma10:

            return "duanqizouruo ?뵿"

        else:

            return "zhendangzhengli ?뷂툘"



    @staticmethod

    def _parse_published_date(value: Optional[str]) -> Optional[datetime]:

        """

        jiexifabushijianzifuchuan竊늮hibaifanhui None竊?
        """

        if not value:

            return None



        if isinstance(value, datetime):

            return value



        text = str(value).strip()

        if not text:

            return None



        # youxianchangshi ISO geshi

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

        anquanxuliehuawei JSON zifuchuan

        """

        try:

            return json.dumps(data, ensure_ascii=False, default=str)

        except Exception:

            return json.dumps(str(data), ensure_ascii=False)



    @staticmethod

    def _build_raw_result(result: Any) -> Dict[str, Any]:

        """

        shengchengwanzhenganalysisjieguozidian

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

        like "18.50yuan", range formats like "18.50-19.00", and text with

        embedded numbers while filtering out MA indicators.

        """

        if value is None:

            return None

        if isinstance(value, (int, float)):

            v = float(value)

            return v if v > 0 else None



        text = str(value).replace(',', '').replace('%', '').strip()

        if not text or text == '-' or text == '--' or text == 'N/A':

            return None



        # changshizhijiejiexichunshuzizifuchuan

        try:

            return float(text)

        except ValueError:

            pass



        # youxianjiequ "竊? dao "yuan" zhijiandejiage竊똟imianwutiqu MA5/MA10 dengjishuzhibiaoshuzi

        colon_pos = text.rfind(":")

        yuan_pos = text.find("yuan", colon_pos + 1 if colon_pos != -1 else 0)

        if yuan_pos != -1:

            segment_start = colon_pos + 1 if colon_pos != -1 else 0

            segment = text[segment_start:yuan_pos]

            

            # shiyong finditer bingguolvdiao MA kaitoudeshuzi

            matches = list(re.finditer(r"-?\d+(?:\.\d+)?", segment))

            valid_numbers = []

            for m in matches:

                # jianchaqianmianshifoushi "MA" (hulvedaxiaoxie)

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



        # doudi竊쉢u"yuan"zishi竊똸ianjiequdiyigekuohaohoudeneirong竊똟imianwutiqukuohaoneijishuzhibiaoshuzi

        # liru "1.52-1.53 (huicaiMA5/10fujin)" ??jinzai "1.52-1.53 " zhongsousuo

        paren_pos = len(text)

        for paren_char in ('(',):

            pos = text.find(paren_char)

            if pos != -1:

                paren_pos = min(paren_pos, pos)

        search_text = text[:paren_pos].strip() or text  # kuohaoqianweikongshijiangjiyongquanwen



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

        shengchengwu URL shidequzhongjian竊늫uebaowendingqiejiaoduan竊?
        """

        date_str = published_date.isoformat() if published_date else ""

        raw_key = f"{code}|{title}|{source}|{date_str}"

        digest = hashlib.md5(raw_key.encode("utf-8")).hexdigest()

        return f"no-url:{code}:{digest}"



    def save_conversation_message(self, session_id: str, role: str, content: str) -> None:

        """

        save Agent duihuaxiaoxi

        """

        with self.session_scope() as session:

            msg = ConversationMessage(

                session_id=session_id,

                role=role,

                content=content

            )

            session.add(msg)



    def get_conversation_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:

        """

        huoqu Agent duihualishi

        """

        with self.session_scope() as session:

            stmt = select(ConversationMessage).filter(

                ConversationMessage.session_id == session_id

            ).order_by(ConversationMessage.created_at.desc()).limit(limit)

            messages = session.execute(stmt).scalars().all()



            # daoxufanhui竊똟aozhengshijianshunxu

            return [{"role": msg.role, "content": msg.content} for msg in reversed(messages)]



    def conversation_session_exists(self, session_id: str) -> bool:

        """Return True when at least one message exists for the given session."""

        with self.session_scope() as session:

            stmt = (

                select(ConversationMessage.id)

                .where(ConversationMessage.session_id == session_id)

                .limit(1)

            )

            return session.execute(stmt).scalar() is not None



    def get_chat_sessions(

        self,

        limit: int = 50,

        session_prefix: Optional[str] = None,

        extra_session_ids: Optional[List[str]] = None,

    ) -> List[Dict[str, Any]]:

        """

        huoquliaotianhuihualiebiao竊늓ong conversation_messages juhe竊?


        Args:

            limit: Maximum number of sessions to return.

            session_prefix: If provided, only return sessions whose session_id

                starts with this prefix.  Used for per-user isolation (e.g.

                ``"telegram_12345"``).

            extra_session_ids: Optional exact session ids to include in

                addition to the scoped prefix.



        Returns:

            anzuijinhuoyueshijiandaoxudehuihualiebiao竊똫eitiaobaohan session_id, title, message_count, last_active

        """

        from sqlalchemy import func



        with self.session_scope() as session:

            normalized_prefix = None

            if session_prefix:

                normalized_prefix = session_prefix if session_prefix.endswith(":") else f"{session_prefix}:"

            exact_ids = [sid for sid in (extra_session_ids or []) if sid]



            # juhemeige session dexiaoxishuhezuihouhuoyueshijian

            base = (

                select(

                    ConversationMessage.session_id,

                    func.count(ConversationMessage.id).label("message_count"),

                    func.min(ConversationMessage.created_at).label("created_at"),

                    func.max(ConversationMessage.created_at).label("last_active"),

                )

            )

            conditions = []

            if normalized_prefix:

                conditions.append(ConversationMessage.session_id.startswith(normalized_prefix))

            if exact_ids:

                conditions.append(ConversationMessage.session_id.in_(exact_ids))

            if conditions:

                base = base.where(or_(*conditions))

            stmt = (

                base

                .group_by(ConversationMessage.session_id)

                .order_by(desc(func.max(ConversationMessage.created_at)))

                .limit(limit)

            )

            rows = session.execute(stmt).all()



            results = []

            for row in rows:

                sid = row.session_id

                # qugaihuihuadiyitiao user xiaoxizuoweibiaoti

                first_user_msg = session.execute(

                    select(ConversationMessage.content)

                    .where(

                        and_(

                            ConversationMessage.session_id == sid,

                            ConversationMessage.role == "user",

                        )

                    )

                    .order_by(ConversationMessage.created_at)

                    .limit(1)

                ).scalar()

                title = (first_user_msg or "xinduihua")[:60]



                results.append({

                    "session_id": sid,

                    "title": title,

                    "message_count": row.message_count,

                    "created_at": row.created_at.isoformat() if row.created_at else None,

                    "last_active": row.last_active.isoformat() if row.last_active else None,

                })

            return results



    def get_conversation_messages(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:

        """

        huoqudangehuihuadewanzhengxiaoxiliebiao竊늶ongyuqianduanhuifulishi竊?
        """

        with self.session_scope() as session:

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



    def delete_conversation_session(self, session_id: str) -> int:

        """

        deletezhidinghuihuadesuoyouxiaoxi



        Returns:

            deletedexiaoxishu

        """

        with self.session_scope() as session:

            result = session.execute(

                delete(ConversationMessage).where(

                    ConversationMessage.session_id == session_id

                )

            )

            return result.rowcount



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





# bianjiehanshu

def get_db() -> DatabaseManager:

    """huoqushujukuguanliqishilidekuaijiefangshi"""

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

    # testdaima

    logging.basicConfig(level=logging.DEBUG)

    

    db = get_db()

    

    print("=== shujukutest ===")

    print(f"shujukuchushihuachenggong")

    

    # testjianchajinrishuju

    has_data = db.has_today_data('600519')

    print(f"Samsungjinrishifouyoushuju: {has_data}")

    

    # testsaveshuju

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

    print(f"savetestshuju: {saved} tiao")

    

    # testhuoqushangxiawen

    context = db.get_analysis_context('600519')

    print(f"analysisshangxiawen: {context}")


