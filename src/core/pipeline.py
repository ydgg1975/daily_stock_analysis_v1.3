# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 核心分析流水线
===================================

职责：
1. 管理整个分析流程
2. 协调数据获取、存储、搜索、分析、通知等模块
3. 实现并发控制和异常处理
4. 提供股票分析的核心功能
"""

import logging
import math
import time
import uuid
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone, time as clock_time
from typing import List, Dict, Any, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

from src.config import get_config, Config
from src.storage import get_db
from data_provider import DataFetcherManager
from data_provider.realtime_types import ChipDistribution, RealtimeSource, UnifiedRealtimeQuote
from src.analyzer import GeminiAnalyzer, AnalysisResult, fill_chip_structure_if_needed, fill_price_position_if_needed
from src.data.stock_mapping import STOCK_NAME_MAP
from src.notification import NotificationService, NotificationChannel
from src.report_language import (
    get_unknown_text,
    localize_confidence_level,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from src.search_service import SearchService
from src.services.social_sentiment_service import SocialSentimentService
from src.enums import ReportType
from src.stock_analyzer import StockTrendAnalyzer, TrendAnalysisResult
from src.core.trading_calendar import get_market_for_stock, is_market_open
from data_provider.us_index_mapping import is_us_stock_code
from bot.models import BotMessage
from data_provider.alphavantage_provider import (
    get_rsi,
    get_sma,
    get_shares_outstanding,
    get_company_overview,
    get_income_statement_quarterly,
)
from data_provider.us_fundamentals_provider import (
    get_finnhub_metrics,
    get_finnhub_quote,
    get_fmp_fundamentals,
    get_fmp_historical_prices,
    get_fmp_technical_indicators,
    get_fmp_quarterly_financials,
    get_fmp_quote,
    get_yfinance_fundamentals,
    get_yfinance_quarterly_financials,
)


logger = logging.getLogger(__name__)
_MARKET_TZ = {
    "us": "America/New_York",
    "cn": "Asia/Shanghai",
}


class StockAnalysisPipeline:
    """
    股票分析主流程调度器
    
    职责：
    1. 管理整个分析流程
    2. 协调数据获取、存储、搜索、分析、通知等模块
    3. 实现并发控制和异常处理
    """
    
    def __init__(
        self,
        config: Optional[Config] = None,
        max_workers: Optional[int] = None,
        source_message: Optional[BotMessage] = None,
        query_id: Optional[str] = None,
        query_source: Optional[str] = None,
        save_context_snapshot: Optional[bool] = None
    ):
        """
        初始化调度器
        
        Args:
            config: 配置对象（可选，默认使用全局配置）
            max_workers: 最大并发线程数（可选，默认从配置读取）
        """
        self.config = config or get_config()
        self.max_workers = max_workers or self.config.max_workers
        self.source_message = source_message
        self.query_id = query_id
        self.query_source = self._resolve_query_source(query_source)
        self.save_context_snapshot = (
            self.config.save_context_snapshot if save_context_snapshot is None else save_context_snapshot
        )
        
        # 初始化各模块
        self.db = get_db()
        self.fetcher_manager = DataFetcherManager()
        # 不再单独创建 akshare_fetcher，统一使用 fetcher_manager 获取增强数据
        self.trend_analyzer = StockTrendAnalyzer()  # 趋势分析器
        self.analyzer = GeminiAnalyzer()
        self.notifier = NotificationService(source_message=source_message)
        
        # 初始化搜索服务
        self.search_service = SearchService(
            bocha_keys=self.config.bocha_api_keys,
            tavily_keys=self.config.tavily_api_keys,
            brave_keys=self.config.brave_api_keys,
            serpapi_keys=self.config.serpapi_keys,
            gnews_keys=self.config.gnews_api_keys,
            finnhub_keys=self.config.finnhub_api_keys,
            minimax_keys=self.config.minimax_api_keys,
            searxng_base_urls=self.config.searxng_base_urls,
            searxng_public_instances_enabled=self.config.searxng_public_instances_enabled,
            news_max_age_days=self.config.news_max_age_days,
            news_strategy_profile=getattr(self.config, "news_strategy_profile", "short"),
        )
        
        logger.info(f"调度器初始化完成，最大并发数: {self.max_workers}")
        logger.info("已启用趋势分析器 (MA5>MA10>MA20 多头判断)")
        # 打印实时行情/筹码配置状态
        if self.config.enable_realtime_quote:
            logger.info(f"实时行情已启用 (优先级: {self.config.realtime_source_priority})")
        else:
            logger.info("实时行情已禁用，将使用历史收盘价")
        if self.config.enable_chip_distribution:
            logger.info("筹码分布分析已启用")
        else:
            logger.info("筹码分布分析已禁用")
        if self.search_service.is_available:
            logger.info("搜索服务已启用")
        else:
            logger.warning("搜索服务未启用（未配置搜索能力）")

        # 初始化社交舆情服务（仅美股）
        self.social_sentiment_service = SocialSentimentService(
            api_key=self.config.social_sentiment_api_key,
            api_url=self.config.social_sentiment_api_url,
        )
        if self.social_sentiment_service.is_available:
            logger.info("Social sentiment service enabled (Reddit/X/Polymarket, US stocks only)")

    def fetch_and_save_stock_data(
        self, 
        code: str,
        force_refresh: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        获取并保存单只股票数据
        
        断点续传逻辑：
        1. 检查数据库是否已有今日数据
        2. 如果有且不强制刷新，则跳过网络请求
        3. 否则从数据源获取并保存
        
        Args:
            code: 股票代码
            force_refresh: 是否强制刷新（忽略本地缓存）
            
        Returns:
            Tuple[是否成功, 错误信息]
        """
        stock_name = code
        try:
            # 首先获取股票名称
            stock_name = self.fetcher_manager.get_stock_name(code)

            today = date.today()
            is_us_stock = is_us_stock_code(code)
            required_history_bars = 60 if is_us_stock else 1
            # 注意：这里用自然日 date.today() 做“断点续传”判断。
            # 若在周末/节假日/非交易日运行，或机器时区不在中国，可能出现：
            # - 数据库已有最新交易日数据但仍会重复拉取（has_today_data 返回 False）
            # - 或在跨日/时区偏移时误判“今日已有数据”
            # 该行为目前保留（按需求不改逻辑），但如需更严谨可改为“最新交易日/数据源最新日期”判断。
            
            # 断点续传检查：如果今日数据已存在，跳过
            if not force_refresh and self.db.has_today_data(code, today):
                has_sufficient_history = (
                    not is_us_stock or self._has_sufficient_local_history(code, min_bars=required_history_bars)
                )
                if has_sufficient_history:
                    logger.info(f"{stock_name}({code}) 今日数据已存在，跳过获取（断点续传）")
                    return True, None
                logger.info(
                    f"{stock_name}({code}) 今日已有快照数据，但本地历史少于 {required_history_bars} 根，继续补拉历史日线"
                )

            # 从数据源获取数据
            logger.info(f"{stock_name}({code}) 开始从数据源获取数据...")
            df = None
            source_name = ""
            history_fetch_error = None
            history_days = 180 if is_us_stock else 30
            try:
                if df is None:
                    df, source_name = self.fetcher_manager.get_daily_data(code, days=history_days)
            except Exception as e:
                history_fetch_error = e
                logger.warning(f"{stock_name}({code}) 历史日线获取失败: {e}")
                # 美股容错：若历史拉取失败，尝试用已成功的实时行情快照兜底写入
                if is_us_stock and df is None:
                    df, source_name = self._build_us_realtime_snapshot_df(code)
                    if df is not None and not df.empty:
                        logger.warning(
                            f"{stock_name}({code}) 历史失败但实时成功，使用实时快照入库继续流程 "
                            f"(来源: {source_name})"
                        )

            if (df is None or df.empty) and is_us_stock:
                df, source_name = self._build_us_realtime_snapshot_df(code)
                if df is not None and not df.empty:
                    logger.warning(
                        f"{stock_name}({code}) 历史日线为空，回退到实时快照入库 "
                        f"(来源: {source_name})"
                    )

            if df is None or df.empty:
                if history_fetch_error is not None:
                    return False, f"历史日线获取失败且无可用实时快照: {history_fetch_error}"
                return False, "获取数据为空"

            # 保存到数据库
            saved_count = self.db.save_daily_data(df, code, source_name)
            logger.info(f"{stock_name}({code}) 数据保存成功（来源: {source_name}，新增 {saved_count} 条）")

            return True, None

        except Exception as e:
            error_msg = f"获取/保存数据失败: {str(e)}"
            logger.error(f"{stock_name}({code}) {error_msg}")
            return False, error_msg

    def _has_sufficient_local_history(self, code: str, *, min_bars: int) -> bool:
        try:
            return len(self.db.get_latest_data(code, days=min_bars) or []) >= min_bars
        except Exception as exc:
            logger.debug(f"{code} 本地历史充足性检查失败: {exc}")
            return False

    def _build_us_realtime_snapshot_df(self, code: str) -> Tuple[Optional[pd.DataFrame], str]:
        quote = self.fetcher_manager.get_realtime_quote(code)
        if not quote or not getattr(quote, "has_basic_data", lambda: False)():
            return None, ""

        trade_date = self._resolve_market_trade_date(code, quote)
        price = getattr(quote, "price", None)
        if price is None:
            return None, ""

        open_price = getattr(quote, "open_price", None) or getattr(quote, "pre_close", None) or price
        high = getattr(quote, "high", None) or price
        low = getattr(quote, "low", None) or price
        volume = getattr(quote, "volume", None)
        amount = getattr(quote, "amount", None)
        pct_chg = getattr(quote, "change_pct", None)

        snapshot = pd.DataFrame([{
            "code": code,
            "date": trade_date,
            "open": open_price,
            "high": high,
            "low": low,
            "close": price,
            "volume": volume,
            "amount": amount,
            "pct_chg": pct_chg,
            "ma5": None,
            "ma10": None,
            "ma20": None,
            "volume_ratio": None,
        }])
        source = getattr(getattr(quote, "source", None), "value", "realtime_snapshot")
        return snapshot, f"{source}_realtime_snapshot"

    def _resolve_market_trade_date(self, code: str, quote: Any) -> str:
        market_tz_name = self._get_market_timezone_name(code)
        market_tz = ZoneInfo(market_tz_name)
        raw_market_timestamp = getattr(quote, "market_timestamp", None) if quote is not None else None
        market_timestamp = self._parse_time_contract_datetime(raw_market_timestamp)
        if market_timestamp is None:
            return datetime.now(market_tz).date().isoformat()
        if market_timestamp.tzinfo is None:
            market_timestamp = market_timestamp.replace(tzinfo=market_tz)
        return market_timestamp.astimezone(market_tz).date().isoformat()
    
    def analyze_stock(self, code: str, report_type: ReportType, query_id: str) -> Optional[AnalysisResult]:
        """
        分析单只股票（增强版：含量比、换手率、筹码分析、多维度情报）
        
        流程：
        1. 获取实时行情（量比、换手率）- 通过 DataFetcherManager 自动故障切换
        2. 获取筹码分布 - 通过 DataFetcherManager 带熔断保护
        3. 进行趋势分析（基于交易理念）
        4. 多维度情报搜索（最新消息+风险排查+业绩预期）
        5. 从数据库获取分析上下文
        6. 调用 AI 进行综合分析
        
        Args:
            query_id: 查询链路关联 id
            code: 股票代码
            report_type: 报告类型
            
        Returns:
            AnalysisResult 或 None（如果分析失败）
        """
        try:
            # 获取股票名称（优先从实时行情获取真实名称）
            stock_name = self.fetcher_manager.get_stock_name(code)
            diagnostics: Dict[str, Any] = {
                "stock_code": code,
                "history_data_status": "unknown",
                "realtime_fallback_triggered": False,
                "realtime_source": None,
                "alpha_vantage_status": "unknown",
                "ma20_source": "unknown",
                "fundamentals_status": "unknown",
                "earnings_status": "unknown",
                "sentiment_status": "unknown",
                "search_enabled": bool(self.search_service.is_available),
                "news_status": "unknown",
                "news_provider": None,
                "news_provider_chain": [],
                "news_attempt_chain": [],
                "news_fallback_triggered": False,
                "sentiment_provider": None,
                "market_source_chain": [],
                "ai_attempt_chain": [],
                "failure_reasons": [],
            }

            # Step 1: 获取实时行情（量比、换手率等）- 使用统一入口，自动故障切换
            realtime_quote = None
            try:
                realtime_quote = self.fetcher_manager.get_realtime_quote(code)
                market_source_chain = (
                    self.fetcher_manager.get_last_realtime_quote_trace()
                    if hasattr(self.fetcher_manager, "get_last_realtime_quote_trace")
                    else []
                )
                diagnostics["market_source_chain"] = (
                    market_source_chain if isinstance(market_source_chain, list) else []
                )
                if realtime_quote:
                    diagnostics["realtime_source"] = (
                        realtime_quote.source.value if hasattr(realtime_quote, "source") else "unknown"
                    )
                    # 使用实时行情返回的真实股票名称
                    if realtime_quote.name:
                        stock_name = realtime_quote.name
                    # 兼容不同数据源的字段（有些数据源可能没有 volume_ratio）
                    volume_ratio = getattr(realtime_quote, 'volume_ratio', None)
                    turnover_rate = getattr(realtime_quote, 'turnover_rate', None)
                    logger.info(f"{stock_name}({code}) 实时行情: 价格={realtime_quote.price}, "
                              f"量比={volume_ratio}, 换手率={turnover_rate}% "
                              f"(来源: {realtime_quote.source.value if hasattr(realtime_quote, 'source') else 'unknown'})")
                else:
                    diagnostics["failure_reasons"].append("realtime_quote_unavailable")
                    logger.info(f"{stock_name}({code}) 实时行情获取失败或已禁用，将使用历史数据进行分析")
            except Exception as e:
                diagnostics["failure_reasons"].append(f"realtime_quote_error: {e}")
                logger.warning(f"{stock_name}({code}) 获取实时行情失败: {e}")

            # 如果还是没有名称，使用代码作为名称
            if not stock_name:
                stock_name = f'股票{code}'

            # Step 2: 获取筹码分布 - 使用统一入口，带熔断保护
            chip_data = None
            is_us_stock = is_us_stock_code(code)
            try:
                if is_us_stock:
                    logger.debug(f"{stock_name}({code}) 美股暂不支持筹码分布，跳过获取")
                else:
                    chip_data = self.fetcher_manager.get_chip_distribution(code)
                    if chip_data:
                        logger.info(f"{stock_name}({code}) 筹码分布: 获利比例={chip_data.profit_ratio:.1%}, "
                                  f"90%集中度={chip_data.concentration_90:.2%}")
                    else:
                        logger.debug(f"{stock_name}({code}) 筹码分布获取失败或已禁用")
            except Exception as e:
                logger.warning(f"{stock_name}({code}) 获取筹码分布失败: {e}")

            # If agent mode is explicitly enabled, or specific agent skills are configured, use the Agent analysis pipeline.
            # NOTE: use config.agent_mode (explicit opt-in) instead of
            # config.is_agent_available() so that users who only configured an
            # API Key for the traditional analysis path are not silently
            # switched to Agent mode (which is slower and more expensive).
            use_agent = getattr(self.config, 'agent_mode', False)
            if not use_agent:
                # Auto-enable agent mode when specific skills are configured (e.g., scheduled task with strategy)
                configured_skills = getattr(self.config, 'agent_skills', [])
                if configured_skills and configured_skills != ['all']:
                    use_agent = True
                    logger.info(f"{stock_name}({code}) Auto-enabled agent mode due to configured skills: {configured_skills}")

            # Step 2.5: 基本面能力聚合（统一入口，异常降级）
            # - 失败时返回 partial/failed，不影响既有技术面/新闻链路
            # - 关闭开关时仍返回 not_supported 结构
            fundamental_context = None
            try:
                fundamental_context = self.fetcher_manager.get_fundamental_context(
                    code,
                    budget_seconds=getattr(self.config, 'fundamental_stage_timeout_seconds', 1.5),
                )
            except Exception as e:
                logger.warning(f"{stock_name}({code}) 基本面聚合失败: {e}")
                fundamental_context = self.fetcher_manager.build_failed_fundamental_context(code, str(e))
                diagnostics["failure_reasons"].append(f"fundamental_context_error: {e}")

            # P0: write-only snapshot, fail-open, no read dependency on this table.
            try:
                self.db.save_fundamental_snapshot(
                    query_id=query_id,
                    code=code,
                    payload=fundamental_context,
                    source_chain=fundamental_context.get("source_chain", []),
                    coverage=fundamental_context.get("coverage", {}),
                )
            except Exception as e:
                logger.debug(f"{stock_name}({code}) 基本面快照写入失败: {e}")

            # Step 3: 趋势分析（基于交易理念）— 在 Agent 分支之前执行，供两条路径共用
            trend_result: Optional[TrendAnalysisResult] = None
            try:
                end_date = date.today()
                start_date = end_date - timedelta(days=89)  # ~60 trading days for MA60
                historical_bars = self.db.get_data_range(code, start_date, end_date)
                if historical_bars:
                    df = pd.DataFrame([bar.to_dict() for bar in historical_bars])
                    # Issue #234: Augment with realtime for intraday MA calculation
                    if self.config.enable_realtime_quote and realtime_quote:
                        df = self._augment_historical_with_realtime(df, realtime_quote, code)
                    trend_result = self.trend_analyzer.analyze(df, code)
                    logger.info(f"{stock_name}({code}) 趋势分析: {trend_result.trend_status.value}, "
                              f"买入信号={trend_result.buy_signal.value}, 评分={trend_result.signal_score}")
            except Exception as e:
                logger.warning(f"{stock_name}({code}) 趋势分析失败: {e}", exc_info=True)

            if use_agent:
                logger.info(f"{stock_name}({code}) 启用 Agent 模式进行分析")
                return self._analyze_with_agent(
                    code,
                    report_type,
                    query_id,
                    stock_name,
                    realtime_quote,
                    chip_data,
                    fundamental_context,
                    trend_result,
                )

            # Step 4: 多维度情报搜索（最新消息+风险排查+业绩预期）
            news_context = None
            news_items: List[Dict[str, Any]] = []
            social_context = None
            if self.search_service.is_available:
                logger.info(f"{stock_name}({code}) 开始多维度情报搜索...")

                # 使用多维度搜索（最多5次搜索）
                intel_results = self.search_service.search_comprehensive_intel(
                    stock_code=code,
                    stock_name=stock_name,
                    max_searches=5
                )

                # 格式化情报报告
                if intel_results:
                    news_items = self._collect_news_items_from_intel(intel_results)
                    news_context = self.search_service.format_intel_report(intel_results, stock_name)
                    total_results = sum(
                        len(r.results) for r in intel_results.values() if r.success
                    )
                    provider_chain: List[str] = []
                    news_attempt_chain: List[Dict[str, Any]] = []
                    for response in intel_results.values():
                        if response and isinstance(getattr(response, "attempts", None), list):
                            for attempt in getattr(response, "attempts", []) or []:
                                if isinstance(attempt, dict):
                                    news_attempt_chain.append(dict(attempt))
                        if not response or not getattr(response, "success", False):
                            continue
                        provider_name = str(getattr(response, "provider", "") or "").strip()
                        if not provider_name:
                            continue
                        normalized_provider = provider_name.lower()
                        if normalized_provider in {"none", "filtered"}:
                            continue
                        if provider_name not in provider_chain:
                            provider_chain.append(provider_name)
                    diagnostics["news_provider_chain"] = provider_chain
                    diagnostics["news_attempt_chain"] = news_attempt_chain
                    diagnostics["news_provider"] = provider_chain[0] if provider_chain else None
                    diagnostics["news_fallback_triggered"] = len(provider_chain) > 1
                    diagnostics["news_status"] = "ok" if total_results > 0 else "configured_not_used"
                    logger.info(f"{stock_name}({code}) 情报搜索完成: 共 {total_results} 条结果")
                    logger.debug(f"{stock_name}({code}) 情报搜索结果:\n{news_context}")

                    # 保存新闻情报到数据库（用于后续复盘与查询）
                    try:
                        query_context = self._build_query_context(query_id=query_id)
                        for dim_name, response in intel_results.items():
                            if response and response.success and response.results:
                                self.db.save_news_intel(
                                    code=code,
                                    name=stock_name,
                                    dimension=dim_name,
                                    query=response.query,
                                    response=response,
                                    query_context=query_context
                                )
                    except Exception as e:
                        logger.warning(f"{stock_name}({code}) 保存新闻情报失败: {e}")
            else:
                diagnostics["news_status"] = "not_configured"
                logger.info(f"{stock_name}({code}) 搜索服务不可用，跳过情报搜索")

            # Step 4.5: Social sentiment intelligence (US stocks only)
            if self.social_sentiment_service.is_available and is_us_stock_code(code):
                try:
                    social_context = self.social_sentiment_service.get_social_context(code)
                    if social_context:
                        diagnostics["sentiment_provider"] = "social_sentiment_service"
                        logger.info(f"{stock_name}({code}) Social sentiment data retrieved")
                        if news_context:
                            news_context = news_context + "\n\n" + social_context
                        else:
                            news_context = social_context
                except Exception as e:
                    logger.warning(f"{stock_name}({code}) Social sentiment fetch failed: {e}")
            if not diagnostics.get("sentiment_provider"):
                diagnostics["sentiment_provider"] = diagnostics.get("news_provider")

            # Step 5: 获取分析上下文（技术面数据）
            context = self.db.get_analysis_context(code)

            if context is None:
                diagnostics["history_data_status"] = "unavailable"
                logger.warning(f"{stock_name}({code}) 无法获取历史行情数据，将仅基于新闻和实时行情分析")
                context = {
                    'code': code,
                    'stock_name': stock_name,
                    'date': date.today().isoformat(),
                    'data_missing': True,
                    'today': {},
                    'yesterday': {}
                }
                if realtime_quote:
                    diagnostics["realtime_fallback_triggered"] = True
                    diagnostics["failure_reasons"].append("history_context_missing_realtime_fallback")
            else:
                diagnostics["history_data_status"] = "ok"

            # Step 5.5: 获取 Alpha Vantage 技术指标（失败时降级，不影响主流程）
            rsi = None
            sma20 = None
            sma60 = None
            shares_outstanding = None
            alpha_overview = None
            alpha_quarterly_income = []
            yfinance_fundamentals = {}
            yfinance_quarterly_income = []
            finnhub_quote = {}
            finnhub_fundamentals = {}
            fmp_quote = {}
            fmp_fundamentals = {}
            fmp_quarterly_income: List[Dict[str, Any]] = []
            external_price_history: List[Dict[str, Any]] = []
            api_indicators: Dict[str, Dict[str, Any]] = {}
            alpha_errors: List[str] = []
            yfinance_errors: List[str] = []
            if is_us_stock:
                try:
                    yfinance_fundamentals = get_yfinance_fundamentals(code)
                    yfinance_quarterly_income = get_yfinance_quarterly_financials(code)
                    logger.info(
                        f"{stock_name}({code}) YFinance 基本面: "
                        f"fundamental_fields={len([v for v in yfinance_fundamentals.values() if v not in (None, '', 'N/A')])}, "
                        f"income_quarters={len(yfinance_quarterly_income)}"
                    )
                except Exception as e:
                    yfinance_errors.append(str(e))
                    diagnostics["failure_reasons"].append(f"yfinance_fundamentals_error: {e}")
                try:
                    finnhub_quote = get_finnhub_quote(code)
                    finnhub_fundamentals = get_finnhub_metrics(code)
                except Exception as e:
                    diagnostics["failure_reasons"].append(f"finnhub_error: {e}")
                    logger.warning(f"{stock_name}({code}) 获取 Finnhub 补数失败: {e}")
                try:
                    fmp_quote = get_fmp_quote(code)
                    fmp_fundamentals = get_fmp_fundamentals(code)
                    fmp_quarterly_income = get_fmp_quarterly_financials(code)
                except Exception as e:
                    diagnostics["failure_reasons"].append(f"fmp_error: {e}")
                    logger.warning(f"{stock_name}({code}) 获取 FMP 补数失败: {e}")
                try:
                    external_price_history = get_fmp_historical_prices(code, days=180)
                    api_indicators = get_fmp_technical_indicators(code)
                except Exception as e:
                    diagnostics["failure_reasons"].append(f"fmp_technical_error: {e}")
                    logger.warning(f"{stock_name}({code}) 获取 FMP 技术指标失败: {e}")
            try:
                rsi = get_rsi(code)
                sma20 = get_sma(code, 20)
                sma60 = get_sma(code, 60)
                if is_us_stock:
                    alpha_overview = get_company_overview(code)
                    alpha_quarterly_income = get_income_statement_quarterly(code)
                    shares_outstanding = get_shares_outstanding(code)
                diagnostics["alpha_vantage_status"] = "ok"
                logger.info(
                    f"{stock_name}({code}) AlphaVantage 指标: RSI14={rsi}, SMA20={sma20}, SMA60={sma60}, "
                    f"SharesOutstanding={shares_outstanding}, income_quarters={len(alpha_quarterly_income)}"
                )
            except Exception as e:
                logger.warning(f"{stock_name}({code}) 获取 AlphaVantage 指标失败: {e}")
                alpha_errors.append(str(e))
                diagnostics["alpha_vantage_status"] = "unavailable"
                diagnostics["failure_reasons"].append(f"alpha_vantage_error: {e}")

            if is_us_stock:
                realtime_quote = self._merge_us_quote_fallbacks(
                    realtime_quote,
                    code=code,
                    stock_name=stock_name,
                    payloads=[finnhub_quote, fmp_quote],
                )
                if realtime_quote:
                    diagnostics["realtime_source"] = (
                        realtime_quote.source.value if hasattr(realtime_quote, "source") else diagnostics["realtime_source"]
                    )
                shares_outstanding = (
                    shares_outstanding
                    or yfinance_fundamentals.get("sharesOutstanding")
                    or fmp_fundamentals.get("sharesOutstanding")
                )
                api_indicators = self._merge_api_indicator_overrides(
                    api_indicators=api_indicators,
                    external_price_history=external_price_history,
                    alpha_indicators={"rsi14": rsi, "sma20": sma20, "sma60": sma60},
                )
            
            # Step 6: 增强上下文数据（添加实时行情、筹码、趋势分析结果、股票名称）
            enhanced_context = self._enhance_context(
                context, 
                realtime_quote, 
                chip_data,
                trend_result,
                stock_name,  # 传入股票名称
                fundamental_context,
                shares_outstanding=shares_outstanding,
                fallback_history=external_price_history,
            )
            multidim_blocks = self._build_multidim_blocks(
                code=code,
                context=enhanced_context,
                fundamental_context=fundamental_context,
                news_context=news_context,
                news_items=news_items,
                diagnostics=diagnostics,
                alpha_indicators={"rsi14": rsi, "sma20": sma20, "sma60": sma60},
                api_indicators=api_indicators,
                alpha_overview=alpha_overview,
                yfinance_fundamentals=yfinance_fundamentals,
                yfinance_quarterly_income=yfinance_quarterly_income,
                fmp_fundamentals=fmp_fundamentals,
                fmp_quarterly_income=fmp_quarterly_income,
                finnhub_fundamentals=finnhub_fundamentals,
                external_price_history=external_price_history,
                alpha_quarterly_income=alpha_quarterly_income,
                alpha_errors=alpha_errors + yfinance_errors,
            )
            enhanced_context.update(multidim_blocks)
            if social_context:
                enhanced_context["social_context"] = social_context
            tech = multidim_blocks.get("technicals", {})
            diagnostics["ma20_source"] = (tech.get("ma20") or {}).get("source", "unknown")
            diagnostics["fundamentals_status"] = (multidim_blocks.get("fundamentals") or {}).get("status", "unknown")
            diagnostics["earnings_status"] = (multidim_blocks.get("earnings_analysis") or {}).get("status", "unknown")
            diagnostics["sentiment_status"] = (multidim_blocks.get("sentiment_analysis") or {}).get("status", "unknown")
            if getattr(self.config, "diagnostic_mode", False):
                enhanced_context["diagnostics"] = diagnostics
            enhanced_context['technical_indicators'] = {
                'rsi14': tech.get("rsi14", {}).get("value", 'N/A'),
                'sma20': tech.get("ma20", {}).get("value", 'N/A'),
                'sma60': tech.get("ma60", {}).get("value", 'N/A'),
                'sources': {k: v.get("source") for k, v in tech.items() if isinstance(v, dict)},
            }
            
            
            # Step 7: 调用 AI 分析（传入增强的上下文和新闻）
            result = self.analyzer.analyze(enhanced_context, news_context=news_context)
            if result:
                ai_attempt_chain = getattr(result, "ai_attempt_chain", [])
                diagnostics["ai_attempt_chain"] = ai_attempt_chain if isinstance(ai_attempt_chain, list) else []
                self._inject_structured_blocks_into_result(result, enhanced_context)

            # Step 7.5: 填充分析时的价格信息到 result
            if result:
                result.query_id = query_id
                realtime_data = enhanced_context.get('realtime', {})
                result.current_price = realtime_data.get('price')
                result.change_pct = realtime_data.get('change_pct')

            # Step 7.6: chip_structure fallback (Issue #589)
            if result and chip_data:
                fill_chip_structure_if_needed(result, chip_data)

            # Step 7.7: price_position fallback
            if result:
                fill_price_position_if_needed(result, trend_result, realtime_quote)
                result = self._stabilize_analysis_result(
                    code=code,
                    query_id=query_id,
                    result=result,
                )
                result.runtime_execution = self._build_runtime_execution_summary(
                    result=result,
                    enhanced_context=enhanced_context,
                    diagnostics=diagnostics,
                )

            # Step 8: 保存分析历史记录
            if result:
                try:
                    context_snapshot = self._build_context_snapshot(
                        enhanced_context=enhanced_context,
                        news_content=news_context,
                        realtime_quote=realtime_quote,
                        chip_data=chip_data
                    )
                    self.db.save_analysis_history(
                        result=result,
                        query_id=query_id,
                        report_type=report_type.value,
                        news_content=news_context,
                        context_snapshot=context_snapshot,
                        save_snapshot=self.save_context_snapshot
                    )
                except Exception as e:
                    logger.warning(f"{stock_name}({code}) 保存分析历史失败: {e}")

            return result

        except Exception as e:
            logger.error(f"{stock_name}({code}) 分析失败: {e}")
            logger.exception(f"{stock_name}({code}) 详细错误信息:")
            return None

    @staticmethod
    def _inject_structured_blocks_into_result(result: AnalysisResult, enhanced_context: Dict[str, Any]) -> None:
        dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}
        dashboard.setdefault("structured_analysis", {})
        structured = dashboard["structured_analysis"] if isinstance(dashboard.get("structured_analysis"), dict) else {}
        structured["time_context"] = {
            "market_timestamp": enhanced_context.get("market_timestamp"),
            "market_session_date": enhanced_context.get("market_session_date"),
            "report_generated_at": enhanced_context.get("report_generated_at"),
            "news_published_at": enhanced_context.get("news_published_at"),
            "session_type": enhanced_context.get("session_type"),
            "market_timezone": enhanced_context.get("market_timezone"),
        }
        structured["technicals"] = enhanced_context.get("technicals", {})
        structured["trend_analysis"] = enhanced_context.get("trend_analysis", {})
        structured["fundamentals"] = enhanced_context.get("fundamentals", {})
        structured["earnings_analysis"] = enhanced_context.get("earnings_analysis", {})
        structured["sentiment_analysis"] = enhanced_context.get("sentiment_analysis", {})
        if enhanced_context.get("social_context"):
            sentiment_block = structured["sentiment_analysis"] if isinstance(structured.get("sentiment_analysis"), dict) else {}
            sentiment_block.setdefault("social_context", enhanced_context.get("social_context"))
            structured["sentiment_analysis"] = sentiment_block
        structured["data_quality"] = enhanced_context.get("data_quality", {})
        structured["realtime_context"] = enhanced_context.get("realtime", {})
        structured["market_context"] = {
            "today": enhanced_context.get("today", {}),
            "yesterday": enhanced_context.get("yesterday", {}),
        }
        structured["fundamental_context"] = enhanced_context.get("fundamental_context", {})
        dashboard["structured_analysis"] = structured

        intel = dashboard.get("intelligence") if isinstance(dashboard.get("intelligence"), dict) else {}
        sentiment = enhanced_context.get("sentiment_analysis", {})
        if isinstance(sentiment, dict):
            intel.setdefault("sentiment_summary", sentiment.get("sentiment_summary"))
            intel.setdefault("company_sentiment", sentiment.get("company_sentiment"))
            intel.setdefault("industry_sentiment", sentiment.get("industry_sentiment"))
            intel.setdefault("regulatory_sentiment", sentiment.get("regulatory_sentiment"))
            intel.setdefault("overall_confidence", sentiment.get("overall_confidence"))
        if enhanced_context.get("social_context"):
            intel.setdefault("social_context", enhanced_context.get("social_context"))
        dashboard["intelligence"] = intel
        result.dashboard = dashboard

    @staticmethod
    def _runtime_truth(value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"actual", "inferred", "unavailable"}:
            return normalized
        return "unavailable"

    @staticmethod
    def _first_non_empty(items: List[Any]) -> Optional[str]:
        for item in items:
            text = str(item).strip() if item is not None else ""
            if text:
                return text
        return None

    @staticmethod
    def _safe_runtime_status(value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {
            "ok",
            "partial",
            "failed",
            "unknown",
            "skipped",
            "not_configured",
            "configured_not_used",
            "used_unrecorded",
        }:
            return normalized
        return "unknown"

    @staticmethod
    def _pick_success_provider_from_chain(chain: Any) -> tuple[Optional[str], bool]:
        if not isinstance(chain, list):
            return None, False
        ordered = [item for item in chain if isinstance(item, dict)]
        if not ordered:
            return None, False
        success_idx = -1
        success_provider: Optional[str] = None
        for idx, item in enumerate(ordered):
            action = str(item.get("action") or "").strip().lower()
            if action in {"selected", "switched", "switched_to_fallback", "skipped"}:
                continue
            result = str(item.get("result") or item.get("status") or item.get("outcome") or "").strip().lower()
            provider = str(item.get("provider") or item.get("source") or item.get("target") or "").strip()
            if result in {"ok", "success", "partial", "succeeded", "completed", "partial_success"} and provider:
                success_idx = idx
                success_provider = provider
                break
        if success_provider:
            return success_provider, success_idx > 0
        first_provider = (
            str(ordered[0].get("provider") or ordered[0].get("source") or ordered[0].get("target") or "").strip()
            or None
        )
        return first_provider, len(ordered) > 1

    @staticmethod
    def _parse_provider_from_model(model: Optional[str]) -> Optional[str]:
        model_name = str(model or "").strip()
        if "/" in model_name:
            provider = model_name.split("/", 1)[0].strip()
            return provider or None
        return None

    @staticmethod
    def _extract_final_reason_from_chain(chain: Any) -> Optional[str]:
        if not isinstance(chain, list):
            return None
        for item in reversed(chain):
            if not isinstance(item, dict):
                continue
            for key in ("reason", "message", "note"):
                value = str(item.get(key) or "").strip()
                if value:
                    return value
        return None

    def _build_runtime_execution_summary(
        self,
        *,
        result: AnalysisResult,
        enhanced_context: Dict[str, Any],
        diagnostics: Dict[str, Any],
    ) -> Dict[str, Any]:
        model_used = str(getattr(result, "model_used", "") or "").strip()
        provider = self._parse_provider_from_model(model_used)
        llm_channels = getattr(self.config, "llm_channels", []) or []
        primary_gateway = None
        backup_gateway = None
        if llm_channels and isinstance(llm_channels[0], dict):
            primary_gateway = str(llm_channels[0].get("name") or "").strip() or None
        if len(llm_channels) > 1 and isinstance(llm_channels[1], dict):
            backup_gateway = str(llm_channels[1].get("name") or "").strip() or None
        configured_primary = str(getattr(self.config, "litellm_model", "") or "").strip()
        configured_fallbacks = {
            str(item).strip()
            for item in (getattr(self.config, "litellm_fallback_models", []) or [])
            if str(item).strip()
        }

        ai_fallback_occurred = False
        ai_fallback_truth = "unavailable"
        if model_used:
            ai_fallback_truth = "inferred"
            ai_fallback_occurred = bool(
                configured_fallbacks and model_used in configured_fallbacks
            ) or (
                configured_primary
                and configured_primary != model_used
                and model_used in configured_fallbacks
            )

        realtime_context = enhanced_context.get("realtime") if isinstance(enhanced_context.get("realtime"), dict) else {}
        market_source_chain = diagnostics.get("market_source_chain")
        if not isinstance(market_source_chain, list):
            market_source_chain = []
        market_source, market_fallback = self._pick_success_provider_from_chain(market_source_chain)
        if not market_source:
            market_source = str(realtime_context.get("source") or "").strip() or None
            market_fallback = bool(
                market_source and "fallback" in market_source.lower()
            ) or bool(diagnostics.get("realtime_fallback_triggered"))

        fundamental_context = enhanced_context.get("fundamental_context")
        fundamental_chain = []
        if isinstance(fundamental_context, dict):
            fundamental_chain = fundamental_context.get("source_chain") or []
        fundamental_source, fundamental_fallback = self._pick_success_provider_from_chain(fundamental_chain)

        sentiment_block = enhanced_context.get("sentiment_analysis") if isinstance(enhanced_context.get("sentiment_analysis"), dict) else {}
        sentiment_status = self._safe_runtime_status(sentiment_block.get("status"))
        sentiment_provider = self._first_non_empty([
            diagnostics.get("sentiment_provider"),
            ((enhanced_context.get("data_quality") or {}).get("provider_notes") or {}).get("sentiment")
            if isinstance((enhanced_context.get("data_quality") or {}), dict) else None,
        ])

        fundamentals_block = enhanced_context.get("fundamentals") if isinstance(enhanced_context.get("fundamentals"), dict) else {}
        fundamentals_status = self._safe_runtime_status(fundamentals_block.get("status"))
        news_provider = self._first_non_empty([
            diagnostics.get("news_provider"),
            ((enhanced_context.get("data_quality") or {}).get("provider_notes") or {}).get("news")
            if isinstance((enhanced_context.get("data_quality") or {}), dict) else None,
        ])
        news_provider_chain = diagnostics.get("news_provider_chain")
        if not isinstance(news_provider_chain, list):
            news_provider_chain = []
        news_attempt_chain = diagnostics.get("news_attempt_chain")
        if not isinstance(news_attempt_chain, list):
            news_attempt_chain = []
        if news_attempt_chain:
            picked_news_provider, picked_news_fallback = self._pick_success_provider_from_chain(news_attempt_chain)
            if picked_news_provider:
                news_provider = picked_news_provider
                news_provider_chain = news_attempt_chain
                if picked_news_fallback:
                    diagnostics["news_fallback_triggered"] = True
        news_status = self._safe_runtime_status(diagnostics.get("news_status"))
        if news_status == "unknown":
            if diagnostics.get("search_enabled"):
                news_status = "configured_not_used"
            else:
                news_status = "not_configured"
        if sentiment_status == "unknown":
            sentiment_status = "configured_not_used" if diagnostics.get("search_enabled") else "not_configured"
        news_truth = "actual" if news_provider else ("inferred" if diagnostics.get("search_enabled") else "unavailable")
        sentiment_truth = "actual" if sentiment_provider else ("inferred" if diagnostics.get("search_enabled") else "unavailable")
        ai_attempt_chain = diagnostics.get("ai_attempt_chain")
        if not isinstance(ai_attempt_chain, list):
            ai_attempt_chain = []

        return {
            "ai": {
                "model": model_used or None,
                "provider": provider,
                "gateway": primary_gateway,
                "model_truth": "actual" if model_used else "unavailable",
                "provider_truth": "inferred" if provider else "unavailable",
                "gateway_truth": "inferred" if primary_gateway else "unavailable",
                "fallback_occurred": ai_fallback_occurred,
                "fallback_truth": ai_fallback_truth,
                "configured_primary_gateway": primary_gateway,
                "configured_backup_gateway": backup_gateway,
                "configured_primary_model": configured_primary or None,
                "attempt_chain": ai_attempt_chain,
            },
            "data": {
                "market": {
                    "source": market_source,
                    "truth": "actual" if market_source else "unavailable",
                    "fallback_occurred": market_fallback,
                    "status": "ok" if market_source else "unknown",
                    "source_chain": market_source_chain,
                    "final_reason": self._extract_final_reason_from_chain(market_source_chain),
                },
                "fundamentals": {
                    "source": fundamental_source,
                    "truth": "actual" if fundamental_source else "unavailable",
                    "fallback_occurred": fundamental_fallback,
                    "status": fundamentals_status,
                    "source_chain": fundamental_chain if isinstance(fundamental_chain, list) else [],
                    "final_reason": self._extract_final_reason_from_chain(fundamental_chain),
                },
                "news": {
                    "source": news_provider,
                    "truth": self._runtime_truth(news_truth),
                    "fallback_occurred": bool(diagnostics.get("news_fallback_triggered")),
                    "status": news_status,
                    "source_chain": news_provider_chain,
                    "final_reason": self._extract_final_reason_from_chain(news_provider_chain),
                },
                "sentiment": {
                    "source": sentiment_provider,
                    "truth": self._runtime_truth(sentiment_truth),
                    "fallback_occurred": False,
                    "status": sentiment_status,
                    "final_reason": self._first_non_empty([
                        diagnostics.get("sentiment_reason"),
                        sentiment_block.get("reason") if isinstance(sentiment_block, dict) else None,
                    ]),
                },
            },
            "notification": getattr(result, "notification_result", None),
            "steps": [
                {
                    "key": "data_fetch",
                    "status": "ok" if market_source else "unknown",
                },
                {
                    "key": "ai_analysis",
                    "status": "ok" if model_used else "unknown",
                },
                {
                    "key": "notification",
                    "status": self._safe_runtime_status(
                        (getattr(result, "notification_result", {}) or {}).get("status")
                    ),
                },
            ],
        }

    @staticmethod
    def _load_raw_result_payload(raw_result: Any) -> Dict[str, Any]:
        if isinstance(raw_result, dict):
            return raw_result
        if isinstance(raw_result, str):
            try:
                parsed = json.loads(raw_result)
            except Exception:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    @staticmethod
    def _canonical_operation_advice(value: Any) -> str:
        text = str(value or "").strip().lower()
        mapping = {
            "强烈买入": "strong_buy",
            "strong buy": "strong_buy",
            "strong_buy": "strong_buy",
            "买入": "buy",
            "buy": "buy",
            "加仓": "buy",
            "accumulate": "buy",
            "add position": "buy",
            "持有": "hold",
            "hold": "hold",
            "观望": "watch",
            "watch": "watch",
            "wait": "watch",
            "wait and see": "watch",
            "减仓": "reduce",
            "reduce": "reduce",
            "trim": "reduce",
            "卖出": "sell",
            "sell": "sell",
            "强烈卖出": "strong_sell",
            "strong sell": "strong_sell",
            "strong_sell": "strong_sell",
        }
        return mapping.get(text, "watch")

    @staticmethod
    def _canonical_trend_prediction(value: Any) -> str:
        text = str(value or "").strip().lower()
        mapping = {
            "强烈看多": "strong_bullish",
            "strong bullish": "strong_bullish",
            "very bullish": "strong_bullish",
            "看多": "bullish",
            "bullish": "bullish",
            "uptrend": "bullish",
            "震荡": "sideways",
            "neutral": "sideways",
            "sideways": "sideways",
            "range-bound": "sideways",
            "看空": "bearish",
            "bearish": "bearish",
            "downtrend": "bearish",
            "强烈看空": "strong_bearish",
            "strong bearish": "strong_bearish",
            "very bearish": "strong_bearish",
        }
        return mapping.get(text, "sideways")

    @staticmethod
    def _normalize_signature_text(value: Any, *, limit: int = 120) -> str:
        text = " ".join(str(value or "").strip().lower().split())
        if not text:
            return ""
        return text[:limit]

    @staticmethod
    def _signature_number(value: Any, *, digits: int = 2) -> Optional[float]:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(parsed):
            return None
        return round(parsed, digits)

    @classmethod
    def _build_stability_signature(
        cls,
        *,
        dashboard: Dict[str, Any],
        structured: Dict[str, Any],
    ) -> str:
        trend_analysis = structured.get("trend_analysis") if isinstance(structured.get("trend_analysis"), dict) else {}
        fundamentals = structured.get("fundamentals") if isinstance(structured.get("fundamentals"), dict) else {}
        sentiment = structured.get("sentiment_analysis") if isinstance(structured.get("sentiment_analysis"), dict) else {}
        market_ctx = structured.get("market_context") if isinstance(structured.get("market_context"), dict) else {}
        realtime_ctx = structured.get("realtime_context") if isinstance(structured.get("realtime_context"), dict) else {}
        technicals = structured.get("technicals") if isinstance(structured.get("technicals"), dict) else {}
        time_ctx = structured.get("time_context") if isinstance(structured.get("time_context"), dict) else {}
        intelligence = dashboard.get("intelligence") if isinstance(dashboard.get("intelligence"), dict) else {}

        today = market_ctx.get("today") if isinstance(market_ctx.get("today"), dict) else {}
        yesterday = market_ctx.get("yesterday") if isinstance(market_ctx.get("yesterday"), dict) else {}
        normalized_fundamentals = fundamentals.get("normalized") if isinstance(fundamentals.get("normalized"), dict) else {}
        derived_profiles = fundamentals.get("derived_profiles") if isinstance(fundamentals.get("derived_profiles"), dict) else {}
        field_sources = fundamentals.get("field_sources") if isinstance(fundamentals.get("field_sources"), dict) else {}

        def _technical_value(name: str, *, zero_is_missing: bool = False) -> Optional[float]:
            node = technicals.get(name)
            if not isinstance(node, dict):
                return None
            return cls._safe_indicator_number(node.get("value"), zero_is_missing=zero_is_missing)

        latest_news = intelligence.get("latest_news")
        if isinstance(latest_news, list):
            latest_news = latest_news[0] if latest_news else ""

        signature_payload = {
            "market_session_date": str(time_ctx.get("market_session_date") or ""),
            "session_type": str(time_ctx.get("session_type") or ""),
            "close": cls._signature_number(today.get("close")),
            "prev_close": cls._signature_number(yesterday.get("close")),
            "pct_chg": cls._signature_number(today.get("pct_chg")),
            "price": cls._signature_number(realtime_ctx.get("price") or today.get("close")),
            "ma20": cls._signature_number(_technical_value("ma20", zero_is_missing=True) or today.get("ma20")),
            "ma60": cls._signature_number(_technical_value("ma60", zero_is_missing=True)),
            "rsi14": cls._signature_number(_technical_value("rsi14"), digits=1),
            "trend_status": cls._normalize_signature_text(trend_analysis.get("trend_status")),
            "ma_alignment": cls._normalize_signature_text(trend_analysis.get("ma_alignment")),
            "volume_status": cls._normalize_signature_text(trend_analysis.get("volume_status")),
            "growth_profile": str(derived_profiles.get("growth_profile") or ""),
            "profitability_profile": str(derived_profiles.get("profitability_profile") or ""),
            "cashflow_profile": str(derived_profiles.get("cashflow_profile") or ""),
            "leverage_profile": str(derived_profiles.get("leverage_profile") or ""),
            "roe": cls._signature_number(normalized_fundamentals.get("returnOnEquity"), digits=3),
            "roa": cls._signature_number(normalized_fundamentals.get("returnOnAssets"), digits=3),
            "company_sentiment": str(sentiment.get("company_sentiment") or ""),
            "regulatory_sentiment": str(sentiment.get("regulatory_sentiment") or ""),
            "sentiment_summary": cls._normalize_signature_text(sentiment.get("sentiment_summary")),
            "latest_news": cls._normalize_signature_text(latest_news),
            "positive_count": len(intelligence.get("positive_catalysts") or []) if isinstance(intelligence.get("positive_catalysts"), list) else 0,
            "risk_count": len(intelligence.get("risk_alerts") or []) if isinstance(intelligence.get("risk_alerts"), list) else 0,
            "sources": {
                "ma20": str((technicals.get("ma20") or {}).get("source") or ""),
                "ma60": str((technicals.get("ma60") or {}).get("source") or ""),
                "rsi14": str((technicals.get("rsi14") or {}).get("source") or ""),
                "freeCashflow": str(field_sources.get("freeCashflow") or ""),
                "operatingCashflow": str(field_sources.get("operatingCashflow") or ""),
                "returnOnEquity": str(field_sources.get("returnOnEquity") or ""),
                "returnOnAssets": str(field_sources.get("returnOnAssets") or ""),
            },
        }
        return json.dumps(signature_payload, sort_keys=True, ensure_ascii=False)

    @classmethod
    def _recent_signal_baseline(
        cls,
        records: List[Any],
        *,
        exclude_query_id: Optional[str] = None,
        current_market_session_date: Optional[str] = None,
        current_session_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        exact_matches: List[Dict[str, Any]] = []
        fallback_matches: List[Dict[str, Any]] = []
        for record in records or []:
            if exclude_query_id and getattr(record, "query_id", None) == exclude_query_id:
                continue
            raw_payload = cls._load_raw_result_payload(getattr(record, "raw_result", None))
            dashboard = raw_payload.get("dashboard") if isinstance(raw_payload.get("dashboard"), dict) else {}
            structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
            quality = structured.get("data_quality") if isinstance(structured.get("data_quality"), dict) else {}
            time_ctx = structured.get("time_context") if isinstance(structured.get("time_context"), dict) else {}
            decision_ctx = dashboard.get("decision_context") if isinstance(dashboard.get("decision_context"), dict) else {}
            candidate = {
                "score": getattr(record, "sentiment_score", None),
                "operation_advice": getattr(record, "operation_advice", None),
                "trend_prediction": getattr(record, "trend_prediction", None),
                "missing_fields": quality.get("missing_fields") if isinstance(quality.get("missing_fields"), list) else [],
                "market_session_date": time_ctx.get("market_session_date"),
                "session_type": time_ctx.get("session_type"),
                "decision_context": decision_ctx,
                "signature": cls._build_stability_signature(dashboard=dashboard, structured=structured),
            }
            if (
                current_market_session_date
                and current_session_type
                and candidate.get("market_session_date") == current_market_session_date
                and candidate.get("session_type") == current_session_type
            ):
                exact_matches.append(candidate)
            else:
                fallback_matches.append(candidate)
        if exact_matches:
            return exact_matches[0]
        if fallback_matches:
            return fallback_matches[0]
        return None

    def _stabilize_analysis_result(
        self,
        *,
        code: str,
        query_id: str,
        result: AnalysisResult,
    ) -> AnalysisResult:
        dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}
        structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
        if not structured:
            return result

        trend_analysis = structured.get("trend_analysis") if isinstance(structured.get("trend_analysis"), dict) else {}
        fundamentals = structured.get("fundamentals") if isinstance(structured.get("fundamentals"), dict) else {}
        sentiment = structured.get("sentiment_analysis") if isinstance(structured.get("sentiment_analysis"), dict) else {}
        quality = structured.get("data_quality") if isinstance(structured.get("data_quality"), dict) else {}
        market_ctx = structured.get("market_context") if isinstance(structured.get("market_context"), dict) else {}
        realtime_ctx = structured.get("realtime_context") if isinstance(structured.get("realtime_context"), dict) else {}
        technicals = structured.get("technicals") if isinstance(structured.get("technicals"), dict) else {}
        time_ctx = structured.get("time_context") if isinstance(structured.get("time_context"), dict) else {}
        core = dashboard.get("core_conclusion") if isinstance(dashboard.get("core_conclusion"), dict) else {}
        position_advice = core.get("position_advice") if isinstance(core.get("position_advice"), dict) else {}
        intelligence = dashboard.get("intelligence") if isinstance(dashboard.get("intelligence"), dict) else {}
        battle_plan = dashboard.get("battle_plan") if isinstance(dashboard.get("battle_plan"), dict) else {}

        today = market_ctx.get("today") if isinstance(market_ctx.get("today"), dict) else {}
        yesterday = market_ctx.get("yesterday") if isinstance(market_ctx.get("yesterday"), dict) else {}
        normalized_fundamentals = fundamentals.get("normalized") if isinstance(fundamentals.get("normalized"), dict) else {}
        derived_profiles = fundamentals.get("derived_profiles") if isinstance(fundamentals.get("derived_profiles"), dict) else {}
        current_missing = {
            str(item)
            for item in (quality.get("missing_fields") or [])
            if isinstance(item, str)
        }

        current_session_type = str(time_ctx.get("session_type") or "").strip()
        current_market_session_date = str(time_ctx.get("market_session_date") or "").strip()

        previous_records = self.db.get_analysis_history(
            code=code,
            days=60,
            limit=5,
            exclude_query_id=query_id,
        )
        baseline = self._recent_signal_baseline(
            previous_records,
            exclude_query_id=query_id,
            current_market_session_date=current_market_session_date if current_session_type == "last_completed_session" else None,
            current_session_type=current_session_type if current_session_type == "last_completed_session" else None,
        )
        previous_score = baseline.get("score") if isinstance(baseline, dict) else None
        previous_missing = {
            str(item)
            for item in ((baseline or {}).get("missing_fields") or [])
            if isinstance(item, str)
        }
        same_session_window = bool(
            current_session_type == "last_completed_session"
            and isinstance(baseline, dict)
            and baseline.get("market_session_date") == current_market_session_date
            and baseline.get("session_type") == current_session_type
        )
        newly_completed_metrics = [
            metric.upper()
            for metric in ("ma5", "ma10", "ma20", "ma60", "rsi14", "vwap")
            if f"technicals.{metric}" in previous_missing and f"technicals.{metric}" not in current_missing
        ]

        def _node_value(name: str) -> Optional[float]:
            node = technicals.get(name)
            if not isinstance(node, dict):
                return None
            return self._safe_indicator_number(
                node.get("value"),
                zero_is_missing=name in {"ma5", "ma10", "ma20", "ma60", "vwap"},
            )

        def _float_or_none(value: Any) -> Optional[float]:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                return None
            if math.isnan(parsed):
                return None
            return parsed

        current_price = _float_or_none(realtime_ctx.get("price"))
        if current_price is None:
            current_price = _float_or_none(today.get("close"))
        prev_close = _float_or_none(yesterday.get("close"))
        close_price = _float_or_none(today.get("close")) or current_price
        open_price = _float_or_none(today.get("open"))
        high_price = _float_or_none(today.get("high"))
        low_price = _float_or_none(today.get("low"))
        session_change_pct = _float_or_none(today.get("pct_chg"))
        if session_change_pct is None and close_price is not None and prev_close not in (None, 0):
            session_change_pct = ((close_price - prev_close) / prev_close) * 100
        ma20 = _node_value("ma20") or _float_or_none(today.get("ma20"))
        ma60 = _node_value("ma60")
        rsi14 = _node_value("rsi14")
        trend_strength = _float_or_none(trend_analysis.get("trend_strength"))
        ma_alignment = str(trend_analysis.get("ma_alignment") or "").strip()
        trend_status = str(trend_analysis.get("trend_status") or "").strip().lower()
        volume_status = str(trend_analysis.get("volume_status") or "").strip()
        negative_signals: List[str] = []
        positive_signals: List[str] = []
        def _clamp_score(value: float, low: float, high: float) -> int:
            return int(round(max(low, min(high, value))))

        market_score = 50.0
        market_reasons: List[str] = []
        if session_change_pct is not None:
            if session_change_pct <= -5:
                market_score -= 12
                market_reasons.append("日线跌幅较大")
            elif session_change_pct <= -3:
                market_score -= 8
                market_reasons.append("日线明显走弱")
            elif session_change_pct <= -1:
                market_score -= 4
                market_reasons.append("日线收跌")
            elif session_change_pct >= 5:
                market_score += 10
                market_reasons.append("日线强势收涨")
            elif session_change_pct >= 3:
                market_score += 7
                market_reasons.append("日线明显走强")
            elif session_change_pct >= 1:
                market_score += 3
                market_reasons.append("日线收涨")
        if close_price is not None and open_price is not None:
            if close_price < open_price:
                market_score -= 2
                market_reasons.append("收盘弱于开盘")
            elif close_price > open_price:
                market_score += 2
                market_reasons.append("收盘强于开盘")
        if high_price is not None and low_price is not None and prev_close not in (None, 0):
            amplitude_pct = ((high_price - low_price) / prev_close) * 100
            if amplitude_pct > 6 and session_change_pct is not None and session_change_pct < 0:
                market_score -= 2
                market_reasons.append("振幅偏大且收跌")
            elif amplitude_pct < 3 and session_change_pct is not None and session_change_pct > 0:
                market_score += 1
                market_reasons.append("震荡收敛且走强")
        market_score = _clamp_score(market_score, 25, 75)

        technical_score = 50.0
        if "空头" in ma_alignment or "bear" in trend_status:
            technical_score -= 8
            negative_signals.append("均线结构偏空")
        elif "多头" in ma_alignment or "bull" in trend_status:
            technical_score += 8
            positive_signals.append("均线结构偏强")
        if current_price is not None and ma20 is not None:
            if current_price < ma20:
                technical_score -= 4
                negative_signals.append("价格位于 MA20 下方")
            else:
                technical_score += 3
                positive_signals.append("价格位于 MA20 上方")
        if current_price is not None and ma60 is not None:
            if current_price < ma60:
                technical_score -= 4
                negative_signals.append("价格位于 MA60 下方")
            else:
                technical_score += 2
                positive_signals.append("价格位于 MA60 上方")
        if volume_status == "放量下跌":
            technical_score -= 4
            negative_signals.append("放量下跌")
        elif volume_status == "放量上涨":
            technical_score += 3
            positive_signals.append("放量上涨")
        elif volume_status == "缩量回调":
            technical_score += 1
            positive_signals.append("缩量回调")
        if rsi14 is not None:
            if rsi14 < 30:
                technical_score -= 2
                negative_signals.append("RSI 接近超卖")
            elif rsi14 < 40:
                technical_score -= 1
                negative_signals.append("RSI 偏弱")
            elif 45 <= rsi14 <= 65:
                technical_score += 1
                positive_signals.append("RSI 位于中强区")
            elif rsi14 > 75:
                technical_score -= 1
                negative_signals.append("RSI 偏热")
        if trend_strength is not None:
            if trend_strength <= 25:
                technical_score -= 4
            elif trend_strength <= 40:
                technical_score -= 2
            elif trend_strength >= 70:
                technical_score += 4
            elif trend_strength >= 58:
                technical_score += 2
        technical_score = _clamp_score(technical_score, 20, 80)

        fundamental_score = 50.0
        fundamental_reasons: List[str] = []
        growth_profile = str(derived_profiles.get("growth_profile") or "")
        profitability_profile = str(derived_profiles.get("profitability_profile") or "")
        cashflow_profile = str(derived_profiles.get("cashflow_profile") or "")
        leverage_profile = str(derived_profiles.get("leverage_profile") or "")
        if growth_profile == "high_growth":
            fundamental_score += 7
            fundamental_reasons.append("增长质量较强")
        elif growth_profile == "negative_growth":
            fundamental_score -= 7
            fundamental_reasons.append("增长承压")
        if profitability_profile in {"profitable", "gross_margin_positive"}:
            fundamental_score += 6
            fundamental_reasons.append("盈利能力良好")
        elif profitability_profile == "near_breakeven_or_loss":
            fundamental_score -= 8
            fundamental_reasons.append("盈利质量承压")
        if cashflow_profile == "cashflow_healthy":
            fundamental_score += 6
            fundamental_reasons.append("现金流健康")
        elif cashflow_profile == "cashflow_pressure":
            fundamental_score -= 6
            fundamental_reasons.append("现金流偏弱")
        if leverage_profile == "leverage_controllable":
            fundamental_score += 4
            fundamental_reasons.append("杠杆可控")
        elif leverage_profile == "high_leverage":
            fundamental_score -= 4
            fundamental_reasons.append("杠杆压力偏高")
        roe = _float_or_none(normalized_fundamentals.get("returnOnEquity"))
        if roe is not None:
            if roe > 0.25:
                fundamental_score += 6
                fundamental_reasons.append("ROE 维持高位")
            elif roe > 0.12:
                fundamental_score += 4
            elif roe > 0.05:
                fundamental_score += 2
            elif roe < 0:
                fundamental_score -= 6
                fundamental_reasons.append("ROE 转负")
        roa = _float_or_none(normalized_fundamentals.get("returnOnAssets"))
        if roa is not None:
            if roa > 0.12:
                fundamental_score += 5
                fundamental_reasons.append("ROA 表现优异")
            elif roa > 0.05:
                fundamental_score += 3
            elif roa < 0:
                fundamental_score -= 4
                fundamental_reasons.append("ROA 转弱")
        revenue = _float_or_none(normalized_fundamentals.get("totalRevenue"))
        net_income = _float_or_none(normalized_fundamentals.get("netIncome"))
        if revenue is not None and revenue > 0 and net_income is not None and net_income > 0:
            fundamental_score += 4
            fundamental_reasons.append("营收与净利润为正")
        elif net_income is not None and net_income < 0:
            fundamental_score -= 7
            fundamental_reasons.append("净利润为负")
        fundamental_score = _clamp_score(fundamental_score, 25, 85)

        news_score = 50.0
        news_reasons: List[str] = []
        company_sentiment = str(sentiment.get("company_sentiment") or "")
        regulatory_sentiment = str(sentiment.get("regulatory_sentiment") or "")
        overall_confidence = str(sentiment.get("overall_confidence") or sentiment.get("confidence") or "")
        positive_catalysts = intelligence.get("positive_catalysts") if isinstance(intelligence.get("positive_catalysts"), list) else []
        risk_alerts = intelligence.get("risk_alerts") if isinstance(intelligence.get("risk_alerts"), list) else []
        if company_sentiment == "positive":
            news_score += 5
            news_reasons.append("公司情绪偏正面")
        elif company_sentiment == "negative":
            news_score -= 6
            news_reasons.append("公司情绪偏负面")
        if regulatory_sentiment == "positive":
            news_score += 2
            news_reasons.append("监管边际友好")
        elif regulatory_sentiment == "negative":
            news_score -= 5
            news_reasons.append("监管压力偏高")
        if overall_confidence == "high":
            news_score += 3
        elif overall_confidence == "medium":
            news_score += 1
        news_score += min(len(positive_catalysts), 3)
        news_score -= min(len(risk_alerts), 3) * 1.5
        news_score = _clamp_score(news_score, 30, 75)

        risk_adjustment = 0.0
        risk_reasons: List[str] = []
        action_checklist = battle_plan.get("action_checklist") if isinstance(battle_plan.get("action_checklist"), list) else []
        fail_count = 0
        warn_count = 0
        pass_count = 0
        for item in action_checklist:
            text = str(item or "").strip()
            if text.startswith("❌"):
                fail_count += 1
            elif text.startswith("⚠"):
                warn_count += 1
            elif text.startswith("✅"):
                pass_count += 1
        risk_adjustment -= min(fail_count, 3) * 2.0
        risk_adjustment -= min(warn_count, 3) * 1.0
        if fail_count:
            risk_reasons.append(f"{fail_count} 项执行条件未满足")
        elif warn_count:
            risk_reasons.append(f"{warn_count} 项条件待确认")
        elif pass_count and not action_checklist:
            pass
        elif pass_count and fail_count == 0 and warn_count == 0:
            risk_adjustment += 1.5
            risk_reasons.append("Checklist 通过度较高")

        quality_warnings = quality.get("warnings") if isinstance(quality.get("warnings"), list) else []
        conflict_penalty = sum(
            1
            for warning in quality_warnings
            if isinstance(warning, str) and ("provider_conflict" in warning or "recomputed" in warning)
        )
        if conflict_penalty:
            risk_adjustment -= min(conflict_penalty, 2) * 1.0
            risk_reasons.append("行情源口径仍需复核")
        risk_adjustment = max(-8.0, min(4.0, risk_adjustment))

        strong_fundamentals = fundamental_score >= 65
        weak_fundamentals = fundamental_score <= 40
        technical_bearish = technical_score <= 40
        technical_bullish = technical_score >= 60
        technical_pressure = round(max(0.0, (50.0 - technical_score) / 8.0), 2)

        raw_composite_score = _clamp_score(
            market_score * 0.15
            + technical_score * 0.25
            + fundamental_score * 0.40
            + news_score * 0.20
            + risk_adjustment,
            0,
            100,
        )
        stabilized_score = raw_composite_score
        score_adjustment_notes: List[str] = []
        previous_score_int: Optional[int] = None
        change_reasons: List[str] = []

        current_signature = self._build_stability_signature(dashboard=dashboard, structured=structured)
        try:
            current_signature_payload = json.loads(current_signature)
        except (TypeError, ValueError, json.JSONDecodeError):
            current_signature_payload = {}
        previous_signature = baseline.get("signature") if isinstance(baseline, dict) else None
        try:
            previous_signature_payload = json.loads(previous_signature) if previous_signature else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            previous_signature_payload = {}
        same_signature = bool(previous_signature and previous_signature == current_signature)

        current_news_signature = "|".join(
            filter(
                None,
                [
                    str(current_signature_payload.get("latest_news") or ""),
                    str(current_signature_payload.get("sentiment_summary") or ""),
                    str(current_signature_payload.get("positive_count") or ""),
                    str(current_signature_payload.get("risk_count") or ""),
                ],
            )
        )
        previous_news_signature = "|".join(
            filter(
                None,
                [
                    str(previous_signature_payload.get("latest_news") or ""),
                    str(previous_signature_payload.get("sentiment_summary") or ""),
                    str(previous_signature_payload.get("positive_count") or ""),
                    str(previous_signature_payload.get("risk_count") or ""),
                ],
            )
        )
        current_sources = current_signature_payload.get("sources") if isinstance(current_signature_payload.get("sources"), dict) else {}
        previous_sources = previous_signature_payload.get("sources") if isinstance(previous_signature_payload.get("sources"), dict) else {}
        current_provider_signature = json.dumps(current_sources, sort_keys=True, ensure_ascii=False)
        previous_provider_signature = json.dumps(previous_sources, sort_keys=True, ensure_ascii=False)
        has_previous_provider_source = any(str(value or "").strip() for value in previous_sources.values())
        current_technical_state = "|".join(
            filter(
                None,
                [
                    str(current_signature_payload.get("trend_status") or ""),
                    str(current_signature_payload.get("ma_alignment") or ""),
                    str(current_signature_payload.get("volume_status") or ""),
                ],
            )
        )
        previous_technical_state = "|".join(
            filter(
                None,
                [
                    str(previous_signature_payload.get("trend_status") or ""),
                    str(previous_signature_payload.get("ma_alignment") or ""),
                    str(previous_signature_payload.get("volume_status") or ""),
                ],
            )
        )

        if previous_score is not None:
            try:
                previous_score_int = int(previous_score)
            except (TypeError, ValueError):
                previous_score_int = None
            if previous_score_int is not None:
                clamp_limit = 8
                if same_session_window and same_signature:
                    clamp_limit = 3
                elif same_session_window:
                    clamp_limit = 5
                if newly_completed_metrics:
                    clamp_limit = min(clamp_limit, 5 if same_session_window else 6)
                    change_reasons.append("技术指标补齐导致")
                if current_news_signature and previous_news_signature and current_news_signature != previous_news_signature:
                    clamp_limit = 8 if same_session_window else 10
                    change_reasons.append("新闻新增导致")
                if current_provider_signature != previous_provider_signature and has_previous_provider_source:
                    clamp_limit = min(clamp_limit, 5 if same_session_window else 7)
                    change_reasons.append("provider改口径导致")
                if current_technical_state and previous_technical_state and current_technical_state != previous_technical_state:
                    clamp_limit = max(clamp_limit, 7 if same_session_window else 8)
                delta = stabilized_score - previous_score_int
                if same_session_window and same_signature and delta != 0:
                    change_reasons.append("评分结构重算导致")
                if delta > clamp_limit:
                    stabilized_score = previous_score_int + clamp_limit
                    score_adjustment_notes.append("已限制单次上调幅度，避免同一标的短时间内分数漂移")
                elif delta < -clamp_limit:
                    stabilized_score = previous_score_int - clamp_limit
                    score_adjustment_notes.append("已限制单次下调幅度，避免技术补齐或口径微调引发剧烈跳变")

        if strong_fundamentals and technical_bearish and stabilized_score < 42:
            stabilized_score = 42
            score_adjustment_notes.append("短线偏弱但基本面与现金流仍有支撑")

        if technical_score <= 38:
            trend_key = "bearish"
        elif technical_score >= 64:
            trend_key = "bullish"
        else:
            trend_key = "sideways"

        if weak_fundamentals and technical_bearish:
            advice_key = "reduce" if stabilized_score >= 35 else "sell"
        elif strong_fundamentals and technical_bearish:
            advice_key = "watch"
        elif stabilized_score >= 72 and technical_bullish and fundamental_score >= 68:
            advice_key = "buy"
        elif stabilized_score >= 60:
            advice_key = "hold"
        elif stabilized_score >= 42:
            advice_key = "watch"
        elif stabilized_score >= 32:
            advice_key = "reduce"
        else:
            advice_key = "sell"

        language = normalize_report_language(getattr(result, "report_language", "zh"))
        result.sentiment_score = max(0, min(100, int(stabilized_score)))
        result.trend_prediction = localize_trend_prediction(trend_key, language)
        result.operation_advice = localize_operation_advice(advice_key, language)
        result.decision_type = {
            "strong_buy": "buy",
            "buy": "buy",
            "hold": "hold",
            "watch": "hold",
            "reduce": "sell",
            "sell": "sell",
            "strong_sell": "sell",
        }.get(advice_key, result.decision_type or "hold")

        if technical_bearish:
            signal_text = "、".join(dict.fromkeys(negative_signals[:3])) or "均线与价格结构偏弱"
            short_term_view = f"短线技术偏弱，{signal_text}。"
        elif technical_bullish:
            signal_text = "、".join(dict.fromkeys(positive_signals[:3])) or "均线与价格结构偏强"
            short_term_view = f"短线技术偏强，{signal_text}。"
        else:
            short_term_view = "短线技术仍偏震荡，趋势方向需要继续确认。"

        if strong_fundamentals and technical_bearish:
            composite_view = f"短线技术承压，但基本面、盈利质量与现金流仍有支撑，综合建议以{result.operation_advice}为主。"
        elif weak_fundamentals and technical_bearish:
            composite_view = f"技术面与基本面共振偏弱，综合建议转向{result.operation_advice}，优先防守。"
        elif strong_fundamentals and technical_bullish:
            composite_view = f"技术面与基本面相互印证，综合建议以{result.operation_advice}为主。"
        else:
            composite_view = f"综合建议为{result.operation_advice}，结合技术、基本面与情绪继续跟踪。"

        score_breakdown = [
            {
                "label": "行情/趋势分",
                "score": market_score,
                "note": "、".join(dict.fromkeys(market_reasons[:2])) or "日线波动中性",
                "tone": "danger" if market_score < 45 else "success" if market_score > 55 else "default",
            },
            {
                "label": "技术分",
                "score": technical_score,
                "note": "、".join(dict.fromkeys((negative_signals or positive_signals)[:3])) or "关键指标中性",
                "tone": "danger" if technical_score < 45 else "success" if technical_score > 55 else "warning",
            },
            {
                "label": "基本面分",
                "score": fundamental_score,
                "note": "、".join(dict.fromkeys(fundamental_reasons[:3])) or "基本面暂无明显偏离",
                "tone": "success" if fundamental_score >= 60 else "danger" if fundamental_score <= 40 else "default",
            },
            {
                "label": "新闻/情绪分",
                "score": news_score,
                "note": "、".join(dict.fromkeys(news_reasons[:3])) or "暂无新增高价值情绪扰动",
                "tone": "success" if news_score >= 58 else "danger" if news_score <= 42 else "default",
            },
            {
                "label": "风险修正项",
                "score": round(risk_adjustment, 1),
                "note": "、".join(dict.fromkeys(risk_reasons[:2])) or "风险修正中性",
                "tone": "danger" if risk_adjustment < 0 else "success" if risk_adjustment > 0 else "default",
            },
        ]

        adjustment_reasons: List[str] = []
        if newly_completed_metrics:
            adjustment_reasons.append(f"{'/'.join(newly_completed_metrics)} 已补齐，短线结构判断更完整")
        adjustment_reasons.extend(score_adjustment_notes)
        if strong_fundamentals and technical_bearish:
            adjustment_reasons.append("已保留基本面缓冲，避免单一技术因子压制综合评分")
        adjustment_reason = "；".join(dict.fromkeys([text for text in adjustment_reasons if text])) or None
        change_reason = "；".join(dict.fromkeys([text for text in change_reasons if text])) or None

        one_sentence = core.get("one_sentence") if isinstance(core.get("one_sentence"), str) else ""
        if strong_fundamentals and technical_bearish:
            core["one_sentence"] = f"短线技术偏弱，但基本面仍有支撑，综合建议以{result.operation_advice}为主。"
        elif adjustment_reason and not one_sentence:
            core["one_sentence"] = composite_view

        if not position_advice:
            position_advice = {}
        if strong_fundamentals and technical_bearish:
            position_advice["no_position"] = position_advice.get("no_position") or f"新仓以{result.operation_advice}为主，等待短线企稳后再评估。"
            position_advice["has_position"] = position_advice.get("has_position") or "已有仓位以观察为主，不追反弹，跌破风控位再处理。"
        elif weak_fundamentals and technical_bearish:
            position_advice["no_position"] = position_advice.get("no_position") or "避免左侧逆势参与，优先等待风险释放。"
            position_advice["has_position"] = position_advice.get("has_position") or "控制仓位并严守止损，避免弱势放大回撤。"
        core["position_advice"] = position_advice
        dashboard["core_conclusion"] = core
        dashboard["decision_context"] = {
            "short_term_view": short_term_view,
            "composite_view": composite_view,
            "adjustment_reason": adjustment_reason,
            "change_reason": change_reason,
            "previous_score": previous_score,
            "score_change": (result.sentiment_score - previous_score_int) if previous_score_int is not None else None,
            "technical_pressure": round(technical_pressure, 2),
            "fundamental_support": round((fundamental_score - 50) / 5, 1),
            "score_breakdown": score_breakdown,
        }
        result.dashboard = dashboard
        if composite_view and (not result.analysis_summary or result.analysis_summary.strip() in {"观望", "持有", "买入", "减仓", "卖出"}):
            result.analysis_summary = composite_view
        return result
    
    def _enhance_context(
        self,
        context: Dict[str, Any],
        realtime_quote,
        chip_data: Optional[ChipDistribution],
        trend_result: Optional[TrendAnalysisResult],
        stock_name: str = "",
        fundamental_context: Optional[Dict[str, Any]] = None,
        shares_outstanding: Optional[int] = None,
        fallback_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        增强分析上下文
        
        将实时行情、筹码分布、趋势分析结果、股票名称添加到上下文中
        
        Args:
            context: 原始上下文
            realtime_quote: 实时行情数据（UnifiedRealtimeQuote 或 None）
            chip_data: 筹码分布数据
            trend_result: 趋势分析结果
            stock_name: 股票名称
            
        Returns:
            增强后的上下文
        """
        enhanced = context.copy()
        enhanced["report_language"] = normalize_report_language(getattr(self.config, "report_language", "zh"))
        time_context = self._build_time_context(context=context, realtime_quote=realtime_quote)
        enhanced.update(time_context)
        enhanced["time_context"] = {
            "market_timestamp": enhanced.get("market_timestamp"),
            "market_session_date": enhanced.get("market_session_date"),
            "news_published_at": enhanced.get("news_published_at"),
            "report_generated_at": enhanced.get("report_generated_at"),
            "market_timezone": enhanced.get("market_timezone"),
            "session_type": enhanced.get("session_type"),
        }
        
        # 添加股票名称
        if stock_name:
            enhanced['stock_name'] = stock_name
        elif realtime_quote and getattr(realtime_quote, 'name', None):
            enhanced['stock_name'] = realtime_quote.name

        # 将运行时搜索窗口透传给 analyzer，避免与全局配置重新读取产生窗口不一致
        enhanced['news_window_days'] = getattr(self.search_service, "news_window_days", 3)
        
        # 添加实时行情（兼容不同数据源的字段差异）
        if realtime_quote:
            # 使用 getattr 安全获取字段，缺失字段返回 None 或默认值
            volume_ratio = getattr(realtime_quote, 'volume_ratio', None)
            volume_ratio_desc = '无数据'
            if is_us_stock_code(context.get('code', '')):
                computed_volume_ratio = self._compute_volume_ratio(
                    context,
                    realtime_quote,
                    fallback_history=fallback_history,
                )
                if computed_volume_ratio is not None:
                    volume_ratio = computed_volume_ratio
                elif self._quote_field_missing(volume_ratio, zero_is_missing=True):
                    volume_ratio = "数据缺失"
                computed_turnover_rate = self._compute_turnover_rate(
                    context=context,
                    realtime_quote=realtime_quote,
                    shares_outstanding=shares_outstanding,
                )
            else:
                computed_turnover_rate = None
            turnover_rate = (
                computed_turnover_rate
                if computed_turnover_rate is not None
                else getattr(realtime_quote, 'turnover_rate', None)
            )
            if self._quote_field_missing(turnover_rate, zero_is_missing=True):
                turnover_rate = "数据缺失"
            if isinstance(volume_ratio, (int, float)):
                volume_ratio_desc = self._describe_volume_ratio(float(volume_ratio))
            enhanced['realtime'] = {
                'name': getattr(realtime_quote, 'name', ''),
                'price': getattr(realtime_quote, 'price', None),
                'change_pct': getattr(realtime_quote, 'change_pct', None),
                'change_amount': getattr(realtime_quote, 'change_amount', None),
                'volume': getattr(realtime_quote, 'volume', None),
                'amount': getattr(realtime_quote, 'amount', None),
                'volume_ratio': volume_ratio,
                'volume_ratio_desc': volume_ratio_desc,
                'turnover_rate': turnover_rate,
                'amplitude': getattr(realtime_quote, 'amplitude', None),
                'open_price': getattr(realtime_quote, 'open_price', None),
                'high': getattr(realtime_quote, 'high', None),
                'low': getattr(realtime_quote, 'low', None),
                'pre_close': getattr(realtime_quote, 'pre_close', None),
                'pe_ratio': getattr(realtime_quote, 'pe_ratio', None),
                'pb_ratio': getattr(realtime_quote, 'pb_ratio', None),
                'total_mv': getattr(realtime_quote, 'total_mv', None),
                'circ_mv': getattr(realtime_quote, 'circ_mv', None),
                'change_60d': getattr(realtime_quote, 'change_60d', None),
                'high_52w': getattr(realtime_quote, 'high_52w', None),
                'low_52w': getattr(realtime_quote, 'low_52w', None),
                'source': getattr(getattr(realtime_quote, 'source', None), 'value', getattr(realtime_quote, 'source', None)),
                'snapshot_type': enhanced.get("session_type"),
                'market_timestamp': getattr(realtime_quote, 'market_timestamp', None) or enhanced.get("market_timestamp"),
            }
            # 移除 None 值以减少上下文大小
            enhanced['realtime'] = {k: v for k, v in enhanced['realtime'].items() if v is not None}
        
        # 添加筹码分布
        if chip_data:
            current_price = getattr(realtime_quote, 'price', 0) if realtime_quote else 0
            enhanced['chip'] = {
                'profit_ratio': chip_data.profit_ratio,
                'avg_cost': chip_data.avg_cost,
                'concentration_90': chip_data.concentration_90,
                'concentration_70': chip_data.concentration_70,
                'chip_status': chip_data.get_chip_status(current_price or 0),
            }
        
        # 添加趋势分析结果
        if trend_result:
            enhanced['trend_analysis'] = {
                'trend_status': trend_result.trend_status.value,
                'ma_alignment': trend_result.ma_alignment,
                'trend_strength': trend_result.trend_strength,
                'bias_ma5': trend_result.bias_ma5,
                'bias_ma10': trend_result.bias_ma10,
                'volume_status': trend_result.volume_status.value,
                'volume_trend': trend_result.volume_trend,
                'buy_signal': trend_result.buy_signal.value,
                'signal_score': trend_result.signal_score,
                'signal_reasons': trend_result.signal_reasons,
                'risk_factors': trend_result.risk_factors,
            }

        # Issue #234: Override today with realtime OHLC + trend MA for intraday analysis only.
        # For last_completed_session we keep the existing EOD market context to avoid
        # mixing official close context with realtime snapshot fields.
        if (
            realtime_quote
            and trend_result
            and trend_result.ma5 > 0
            and enhanced.get("session_type") == "intraday_snapshot"
        ):
            price = getattr(realtime_quote, 'price', None)
            if price is not None and price > 0:
                yesterday_close = None
                if enhanced.get('yesterday') and isinstance(enhanced['yesterday'], dict):
                    yesterday_close = enhanced['yesterday'].get('close')
                orig_today = enhanced.get('today') or {}
                open_p = getattr(realtime_quote, 'open_price', None) or getattr(
                    realtime_quote, 'pre_close', None
                ) or yesterday_close or orig_today.get('open') or price
                high_p = getattr(realtime_quote, 'high', None) or price
                low_p = getattr(realtime_quote, 'low', None) or price
                vol = getattr(realtime_quote, 'volume', None)
                amt = getattr(realtime_quote, 'amount', None)
                pct = getattr(realtime_quote, 'change_pct', None)
                realtime_today = {
                    'close': price,
                    'open': open_p,
                    'high': high_p,
                    'low': low_p,
                    'data_source': getattr(getattr(realtime_quote, 'source', None), 'value', getattr(realtime_quote, 'source', None)),
                    'ma5': trend_result.ma5,
                    'ma10': trend_result.ma10,
                    'ma20': trend_result.ma20,
                }
                if vol is not None:
                    realtime_today['volume'] = vol
                if amt is not None:
                    realtime_today['amount'] = amt
                if pct is not None:
                    realtime_today['pct_chg'] = pct
                for k, v in orig_today.items():
                    if k not in realtime_today and v is not None:
                        realtime_today[k] = v
                enhanced['today'] = realtime_today
                enhanced['ma_status'] = self._compute_ma_status(
                    price, trend_result.ma5, trend_result.ma10, trend_result.ma20
                )
                enhanced['date'] = date.today().isoformat()
                if yesterday_close is not None:
                    try:
                        yc = float(yesterday_close)
                        if yc > 0:
                            enhanced['price_change_ratio'] = round(
                                (price - yc) / yc * 100, 2
                            )
                    except (TypeError, ValueError):
                        pass
                if vol is not None and enhanced.get('yesterday'):
                    yest_vol = enhanced['yesterday'].get('volume') if isinstance(
                        enhanced['yesterday'], dict
                    ) else None
                    if yest_vol is not None:
                        try:
                            yv = float(yest_vol)
                            if yv > 0:
                                enhanced['volume_change_ratio'] = round(
                                    float(vol) / yv, 2
                                )
                        except (TypeError, ValueError):
                            pass

        # ETF/index flag for analyzer prompt (Fixes #274)
        enhanced['is_index_etf'] = SearchService.is_index_or_etf(
            context.get('code', ''), enhanced.get('stock_name', stock_name)
        )

        # P0: append unified fundamental block; keep as additional context only
        enhanced["fundamental_context"] = (
            fundamental_context
            if isinstance(fundamental_context, dict)
            else self.fetcher_manager.build_failed_fundamental_context(
                context.get("code", ""),
                "invalid fundamental context",
            )
        )

        return enhanced

    def _build_time_context(self, context: Dict[str, Any], realtime_quote: Any) -> Dict[str, Any]:
        code = context.get("code", "")
        market_tz_name = self._get_market_timezone_name(code)
        market_tz = ZoneInfo(market_tz_name)
        market_now = datetime.now(market_tz)
        raw_market_timestamp = getattr(realtime_quote, "market_timestamp", None) if realtime_quote is not None else None
        market_timestamp = self._parse_time_contract_datetime(raw_market_timestamp)
        if market_timestamp is not None:
            if market_timestamp.tzinfo is None:
                market_timestamp = market_timestamp.replace(tzinfo=market_tz)
            market_now = market_timestamp.astimezone(market_tz)
        report_generated_at = datetime.now(timezone.utc).isoformat()
        market_session_date = market_now.date().isoformat()
        if market_timestamp is None:
            market_session_date = context.get("date") or market_session_date
        has_realtime_price = (
            realtime_quote is not None
            and getattr(realtime_quote, "price", None) is not None
        )
        market = get_market_for_stock(code)
        is_trading_day = is_market_open(market, market_now.date()) if market else False
        is_regular_hours = self._is_regular_session_clock(market, market_now)
        session_type = "intraday_snapshot" if (has_realtime_price and is_trading_day and is_regular_hours) else "last_completed_session"
        return {
            "market_timezone": market_tz_name,
            "market_timestamp": market_now.isoformat(),
            "market_session_date": market_session_date,
            "news_published_at": None,
            "report_generated_at": report_generated_at,
            "session_type": session_type,
        }

    @staticmethod
    def _is_regular_session_clock(market: Optional[str], market_dt: datetime) -> bool:
        current_time = market_dt.timetz().replace(tzinfo=None)
        if market == "us":
            return clock_time(9, 30) <= current_time < clock_time(16, 0)
        if market == "cn":
            return (
                clock_time(9, 30) <= current_time < clock_time(11, 30)
                or clock_time(13, 0) <= current_time < clock_time(15, 0)
            )
        if market == "hk":
            return (
                clock_time(9, 30) <= current_time < clock_time(12, 0)
                or clock_time(13, 0) <= current_time < clock_time(16, 0)
            )
        return False

    @staticmethod
    def _parse_time_contract_datetime(value: Any) -> Optional[datetime]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        raw = str(value).strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _get_market_timezone_name(code: str) -> str:
        market = get_market_for_stock(code)
        return _MARKET_TZ.get(market, "UTC")

    @staticmethod
    def _parse_published_at_iso(value: Any) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            raw = str(value).strip()
            if not raw:
                return None
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                for fmt in ("%Y-%m-%d", "%b %d, %Y", "%Y/%m/%d"):
                    try:
                        dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
                else:
                    return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    def _collect_news_items_from_intel(self, intel_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for dimension, response in (intel_results or {}).items():
            results = getattr(response, "results", None) or []
            for result in results:
                item = {
                    "title": getattr(result, "title", "") or "",
                    "snippet": getattr(result, "snippet", "") or "",
                    "url": getattr(result, "url", "") or "",
                    "dimension": dimension,
                }
                published_at = self._parse_published_at_iso(getattr(result, "published_date", None))
                if published_at:
                    item["news_published_at"] = published_at
                items.append(item)
        return items

    @staticmethod
    def _quote_field_missing(value: Any, *, zero_is_missing: bool = True) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return True
            if text.lower() in {"n/a", "na", "none", "null", "nan", "数据缺失", "-", "--"}:
                return True
            try:
                parsed = float(text.rstrip("%"))
            except (TypeError, ValueError):
                return False
            if math.isnan(parsed):
                return True
            if zero_is_missing and parsed == 0.0:
                return True
            return False
        if isinstance(value, (int, float)):
            if math.isnan(float(value)):
                return True
            if zero_is_missing and float(value) == 0.0:
                return True
        return False

    @staticmethod
    def _realtime_source_from_name(name: str) -> RealtimeSource:
        normalized = str(name or "").strip().lower()
        if normalized == "finnhub":
            return RealtimeSource.FINNHUB
        if normalized == "fmp":
            return RealtimeSource.FMP
        return RealtimeSource.FALLBACK

    def _merge_us_quote_fallbacks(
        self,
        realtime_quote: Any,
        *,
        code: str,
        stock_name: str,
        payloads: List[Dict[str, Any]],
    ) -> Any:
        active_payloads = [payload for payload in payloads if isinstance(payload, dict) and payload]
        if not active_payloads:
            return realtime_quote

        merged = realtime_quote
        if merged is None:
            first_payload = active_payloads[0]
            merged = UnifiedRealtimeQuote(
                code=code,
                name=str(first_payload.get("name") or stock_name or code),
                source=self._realtime_source_from_name(str(first_payload.get("source") or "fallback")),
            )

        field_specs = {
            "price": True,
            "change_pct": False,
            "change_amount": False,
            "volume": True,
            "amount": True,
            "volume_ratio": True,
            "turnover_rate": True,
            "amplitude": True,
            "open_price": True,
            "high": True,
            "low": True,
            "pre_close": True,
            "pe_ratio": True,
            "pb_ratio": True,
            "total_mv": True,
            "circ_mv": True,
            "change_60d": True,
            "high_52w": True,
            "low_52w": True,
            "market_timestamp": False,
        }
        alias_map = {
            "pre_close": (
                "pre_close",
                "previous_close",
                "previousClose",
                "regularMarketPreviousClose",
                "chartPreviousClose",
            ),
            "open_price": ("open_price", "open"),
            "high": ("high",),
            "low": ("low",),
            "high_52w": ("high_52w", "fiftyTwoWeekHigh"),
            "low_52w": ("low_52w", "fiftyTwoWeekLow"),
            "total_mv": ("total_mv", "marketCap"),
            "circ_mv": ("circ_mv", "floatMarketCap"),
            "pb_ratio": ("pb_ratio", "priceToBook"),
            "market_timestamp": ("market_timestamp", "timestamp", "quote_time"),
        }

        for payload in active_payloads:
            if getattr(merged, "source", None) == RealtimeSource.FALLBACK:
                payload_source = self._realtime_source_from_name(str(payload.get("source") or "fallback"))
                if payload_source != RealtimeSource.FALLBACK:
                    merged.source = payload_source
            if not getattr(merged, "name", None) and payload.get("name"):
                merged.name = str(payload.get("name"))
            for field_name, zero_is_missing in field_specs.items():
                current_value = getattr(merged, field_name, None)
                if not self._quote_field_missing(current_value, zero_is_missing=zero_is_missing):
                    continue
                for key in alias_map.get(field_name, (field_name,)):
                    candidate = payload.get(key)
                    if not self._quote_field_missing(candidate, zero_is_missing=zero_is_missing):
                        setattr(merged, field_name, candidate)
                        break

        return merged

    @staticmethod
    def _build_external_volume_samples(history_rows: Optional[List[Dict[str, Any]]], max_count: int = 5) -> List[float]:
        samples: List[float] = []
        for row in reversed(history_rows or []):
            if not isinstance(row, dict):
                continue
            volume = row.get("volume")
            try:
                volume_value = float(volume)
            except (TypeError, ValueError):
                continue
            if volume_value <= 0:
                continue
            samples.append(volume_value)
            if len(samples) >= max_count:
                break
        return list(reversed(samples))

    def _compute_volume_ratio(
        self,
        context: Dict[str, Any],
        realtime_quote: Any,
        fallback_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[float]:
        code = context.get("code", "")
        today_volume = getattr(realtime_quote, "volume", None)
        if today_volume in (None, 0):
            today_volume = (context.get("today") or {}).get("volume")
        try:
            today_volume = float(today_volume)
            if today_volume <= 0:
                return None
        except (TypeError, ValueError):
            return None

        bars = self.db.get_latest_data(code, days=8)
        today_date = context.get("date")
        historical_volumes = self._collect_recent_volumes_from_bars(
            bars=bars or [],
            today_date=today_date,
            max_count=5,
        )
        if len(historical_volumes) < 5 and fallback_history:
            seen_dates = {str(today_date or "").strip()}
            for bar in bars or []:
                bar_date = getattr(getattr(bar, "date", None), "isoformat", lambda: getattr(bar, "date", None))()
                if bar_date:
                    seen_dates.add(str(bar_date))
            extra_samples: List[float] = []
            for row in reversed(fallback_history or []):
                if not isinstance(row, dict):
                    continue
                row_date = str(row.get("date") or "").strip()
                if row_date and row_date in seen_dates:
                    continue
                volume = row.get("volume")
                try:
                    volume_value = float(volume)
                except (TypeError, ValueError):
                    continue
                if volume_value <= 0:
                    continue
                extra_samples.append(volume_value)
                if len(historical_volumes) + len(extra_samples) >= 5:
                    break
            historical_volumes = historical_volumes + extra_samples
        if len(historical_volumes) < 5:
            return None
        avg_volume_5d = sum(historical_volumes) / len(historical_volumes)
        if avg_volume_5d <= 0:
            return None
        return round(today_volume / avg_volume_5d, 2)

    @staticmethod
    def _collect_recent_volumes_from_bars(
        bars: List[Any],
        today_date: Optional[str],
        max_count: int = 5,
    ) -> List[float]:
        volumes: List[float] = []
        for bar in bars:
            bar_date = getattr(getattr(bar, "date", None), "isoformat", lambda: None)()
            if today_date and bar_date == today_date:
                continue
            bar_volume = getattr(bar, "volume", None)
            if bar_volume and bar_volume > 0:
                volumes.append(float(bar_volume))
            if len(volumes) >= max_count:
                break
        return volumes

    @staticmethod
    def _compute_turnover_rate(
        context: Dict[str, Any],
        realtime_quote: Any,
        shares_outstanding: Optional[int],
    ) -> Optional[float]:
        if not shares_outstanding or shares_outstanding <= 0:
            return None
        volume = getattr(realtime_quote, "volume", None)
        if volume in (None, 0):
            volume = (context.get("today") or {}).get("volume")
        try:
            volume = float(volume)
            if volume <= 0:
                return None
        except (TypeError, ValueError):
            return None
        return round(volume / float(shares_outstanding) * 100, 4)

    def _build_multidim_blocks(
        self,
        code: str,
        context: Dict[str, Any],
        fundamental_context: Optional[Dict[str, Any]],
        news_context: Optional[str],
        news_items: Optional[List[Dict[str, Any]]],
        diagnostics: Optional[Dict[str, Any]],
        alpha_indicators: Dict[str, Optional[float]],
        alpha_overview: Optional[Dict[str, Any]],
        yfinance_fundamentals: Optional[Dict[str, Any]],
        yfinance_quarterly_income: Optional[List[Dict[str, Any]]] = None,
        fmp_fundamentals: Optional[Dict[str, Any]] = None,
        fmp_quarterly_income: Optional[List[Dict[str, Any]]] = None,
        finnhub_fundamentals: Optional[Dict[str, Any]] = None,
        external_price_history: Optional[List[Dict[str, Any]]] = None,
        alpha_quarterly_income: Optional[List[Dict[str, Any]]] = None,
        alpha_errors: Optional[List[str]] = None,
        api_indicators: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        technicals = self._build_technicals_block(
            code,
            alpha_indicators,
            external_price_history=external_price_history,
            api_indicators=api_indicators,
        )
        fundamentals = self._build_fundamentals_block(
            fundamental_context,
            alpha_overview=alpha_overview,
            yfinance_fundamentals=yfinance_fundamentals,
            yfinance_quarterly_income=yfinance_quarterly_income,
            fmp_fundamentals=fmp_fundamentals,
            fmp_quarterly_income=fmp_quarterly_income,
            finnhub_fundamentals=finnhub_fundamentals,
        )
        earnings_analysis = self._build_earnings_analysis_block(
            fundamental_context,
            yfinance_quarterly_income=yfinance_quarterly_income,
            fmp_quarterly_income=fmp_quarterly_income,
            alpha_quarterly_income=alpha_quarterly_income,
        )
        sentiment_analysis = self._build_sentiment_analysis_block(
            news_context=news_context,
            news_items=news_items,
            stock_code=code,
            stock_name=context.get("stock_name", ""),
            business_keywords=self._extract_business_keywords(fundamental_context),
        )
        if not context.get("news_published_at"):
            context["news_published_at"] = sentiment_analysis.get("news_published_at")
        data_quality = self._build_data_quality_block(
            technicals=technicals,
            fundamentals=fundamentals,
            earnings_analysis=earnings_analysis,
            sentiment_analysis=sentiment_analysis,
            alpha_errors=alpha_errors or [],
            context=context,
            diagnostics=diagnostics,
        )
        return {
            "technicals": technicals,
            "fundamentals": fundamentals,
            "earnings_analysis": earnings_analysis,
            "sentiment_analysis": sentiment_analysis,
            "data_quality": data_quality,
        }

    @staticmethod
    def _history_row_date_key(value: Any) -> str:
        if hasattr(value, "isoformat"):
            try:
                return str(value.isoformat())
            except Exception:
                return str(value)
        return str(value or "")

    @classmethod
    def _merge_price_history_rows(
        cls,
        local_rows: List[Dict[str, Any]],
        external_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for row in external_rows:
            if not isinstance(row, dict):
                continue
            key = cls._history_row_date_key(row.get("date"))
            if not key:
                continue
            merged[key] = {
                "date": row.get("date"),
                "close": row.get("close"),
                "volume": row.get("volume"),
                "vwap": row.get("vwap"),
            }
        for row in local_rows:
            if not isinstance(row, dict):
                continue
            key = cls._history_row_date_key(row.get("date"))
            if not key:
                continue
            base = merged.get(key, {})
            merged[key] = {
                **base,
                "date": row.get("date") or base.get("date"),
                "close": row.get("close") if row.get("close") is not None else base.get("close"),
                "volume": row.get("volume") if row.get("volume") is not None else base.get("volume"),
                "vwap": row.get("vwap") if row.get("vwap") is not None else base.get("vwap"),
            }
        return [
            merged[key]
            for key in sorted(
                merged.keys(),
                key=lambda item: cls._history_row_date_key(item),
            )
        ]

    @staticmethod
    def _safe_indicator_number(value: Any, *, zero_is_missing: bool = False) -> Optional[float]:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(parsed):
            return None
        if zero_is_missing and parsed == 0:
            return None
        return round(parsed, 4)

    @classmethod
    def _merge_api_indicator_overrides(
        cls,
        *,
        api_indicators: Optional[Dict[str, Dict[str, Any]]],
        external_price_history: Optional[List[Dict[str, Any]]],
        alpha_indicators: Optional[Dict[str, Optional[float]]],
    ) -> Dict[str, Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {
            key: dict(value)
            for key, value in (api_indicators or {}).items()
            if isinstance(value, dict)
        }

        if "vwap" not in merged:
            for row in reversed(external_price_history or []):
                if not isinstance(row, dict):
                    continue
                value = cls._safe_indicator_number(row.get("vwap"), zero_is_missing=True)
                if value is not None:
                    merged["vwap"] = {
                        "value": value,
                        "status": "ok",
                        "source": "fmp_historical_price",
                    }
                    break

        alpha = alpha_indicators or {}
        legacy_map = {
            "ma20": ("sma20", True),
            "ma60": ("sma60", True),
            "rsi14": ("rsi14", False),
        }
        for metric, (alpha_key, zero_is_missing) in legacy_map.items():
            if metric in merged:
                continue
            value = cls._safe_indicator_number(alpha.get(alpha_key), zero_is_missing=zero_is_missing)
            if value is None:
                continue
            merged[metric] = {
                "value": value,
                "status": "ok",
                "source": "alpha_vantage",
            }

        return merged

    def _build_technicals_block(
        self,
        code: str,
        alpha_indicators: Dict[str, Optional[float]],
        external_price_history: Optional[List[Dict[str, Any]]] = None,
        api_indicators: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        bars = self.db.get_latest_data(code, days=300) or []

        rows: List[Dict[str, Any]] = []
        for bar in reversed(bars):
            rows.append(
                {
                    "date": getattr(getattr(bar, "date", None), "isoformat", lambda: getattr(bar, "date", None))(),
                    "close": getattr(bar, "close", None),
                    "volume": getattr(bar, "volume", None),
                }
            )
        source_name = "local_from_ohlcv"
        if external_price_history:
            external_rows = []
            for row in external_price_history:
                if not isinstance(row, dict):
                    continue
                external_rows.append(
                    {
                        "date": row.get("date"),
                        "close": row.get("close"),
                        "volume": row.get("volume"),
                        "vwap": row.get("vwap"),
                    }
                )
            if external_rows:
                rows = self._merge_price_history_rows(rows, external_rows)
                if len(bars) < 60:
                    source_name = "fmp_historical_price"

        preferred_api_indicators = self._merge_api_indicator_overrides(
            api_indicators=api_indicators,
            external_price_history=external_price_history,
            alpha_indicators=alpha_indicators,
        )

        if not rows:
            technicals = {
                k: {"value": None, "status": "data_unavailable", "source": source_name}
                for k in ("ma5", "ma10", "ma20", "ma60", "rsi14", "macd", "macd_signal", "macd_hist", "vwap")
            }
        else:
            df = pd.DataFrame(rows)
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df = df.dropna(subset=["close"]).copy()
            if df.empty:
                technicals = {
                    k: {"value": None, "status": "data_unavailable", "source": source_name}
                    for k in ("ma5", "ma10", "ma20", "ma60", "rsi14", "macd", "macd_signal", "macd_hist", "vwap")
                }
            else:
                close = df["close"]
                ma5 = close.rolling(window=5).mean()
                ma10 = close.rolling(window=10).mean()
                ma20 = close.rolling(window=20).mean()
                ma60 = close.rolling(window=60).mean()
                diff = close.diff()
                gain = diff.clip(lower=0)
                loss = -diff.clip(upper=0)
                avg_gain = gain.rolling(14).mean()
                avg_loss = loss.rolling(14).mean()
                rs = avg_gain / avg_loss.replace(0, pd.NA)
                rsi14 = 100 - (100 / (1 + rs))
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                macd = ema12 - ema26
                macd_signal = macd.ewm(span=9, adjust=False).mean()
                macd_hist = macd - macd_signal

                def _latest(series: pd.Series, min_len: int) -> Tuple[Optional[float], str]:
                    if len(close) < min_len:
                        return None, "insufficient_history"
                    val = series.iloc[-1]
                    if pd.isna(val):
                        return None, "data_unavailable"
                    return round(float(val), 4), "ok"

                technicals = {}
                series_map = {
                    "ma5": (ma5, 5),
                    "ma10": (ma10, 10),
                    "ma20": (ma20, 20),
                    "ma60": (ma60, 60),
                    "rsi14": (rsi14, 15),
                    "macd": (macd, 35),
                    "macd_signal": (macd_signal, 35),
                    "macd_hist": (macd_hist, 35),
                }
                for name, (series, min_len) in series_map.items():
                    value, status = _latest(series, min_len)
                    technicals[name] = {
                        "value": value,
                        "status": status,
                        "source": source_name,
                    }

                vwap_value = None
                vwap_status = "data_unavailable"
                if "vwap" in df.columns:
                    df["vwap"] = pd.to_numeric(df["vwap"], errors="coerce")
                    vwap_series = df["vwap"].dropna()
                    if not vwap_series.empty:
                        vwap_value = round(float(vwap_series.iloc[-1]), 4)
                        vwap_status = "ok"
                technicals["vwap"] = {
                    "value": vwap_value,
                    "status": vwap_status,
                    "source": source_name,
                }

        for metric_name, zero_is_missing in (
            ("ma5", True),
            ("ma10", True),
            ("ma20", True),
            ("ma60", True),
            ("rsi14", False),
            ("vwap", True),
        ):
            node = preferred_api_indicators.get(metric_name)
            if not isinstance(node, dict):
                continue
            value = self._safe_indicator_number(node.get("value"), zero_is_missing=zero_is_missing)
            if value is None:
                continue
            technicals[metric_name] = {
                "value": value,
                "status": str(node.get("status") or "ok"),
                "source": str(node.get("source") or "api"),
            }

        return technicals

    @staticmethod
    def _build_fundamentals_block(
        fundamental_context: Optional[Dict[str, Any]],
        alpha_overview: Optional[Dict[str, Any]] = None,
        yfinance_fundamentals: Optional[Dict[str, Any]] = None,
        yfinance_quarterly_income: Optional[List[Dict[str, Any]]] = None,
        fmp_fundamentals: Optional[Dict[str, Any]] = None,
        fmp_quarterly_income: Optional[List[Dict[str, Any]]] = None,
        finnhub_fundamentals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = ((fundamental_context or {}).get("valuation") or {}).get("data", {})
        raw = payload if isinstance(payload, dict) else {}
        alpha = alpha_overview if isinstance(alpha_overview, dict) else {}
        yf_data = yfinance_fundamentals if isinstance(yfinance_fundamentals, dict) else {}
        yf_quarterly = yfinance_quarterly_income if isinstance(yfinance_quarterly_income, list) else []
        fmp_data = fmp_fundamentals if isinstance(fmp_fundamentals, dict) else {}
        fmp_quarterly = fmp_quarterly_income if isinstance(fmp_quarterly_income, list) else []
        finnhub_data = finnhub_fundamentals if isinstance(finnhub_fundamentals, dict) else {}
        yf_meta = yf_data.get("_meta") if isinstance(yf_data.get("_meta"), dict) else {}
        fmp_meta = fmp_data.get("_meta") if isinstance(fmp_data.get("_meta"), dict) else {}
        source_meta_periods = {
            "yfinance": yf_meta.get("field_periods") if isinstance(yf_meta.get("field_periods"), dict) else {},
            "fmp": fmp_meta.get("field_periods") if isinstance(fmp_meta.get("field_periods"), dict) else {},
        }
        source_meta_sources = {
            "yfinance": yf_meta.get("field_sources") if isinstance(yf_meta.get("field_sources"), dict) else {},
            "fmp": fmp_meta.get("field_sources") if isinstance(fmp_meta.get("field_sources"), dict) else {},
        }
        field_sources: Dict[str, str] = {}
        field_periods: Dict[str, str] = {}

        def is_missing(value: Any) -> bool:
            if value is None:
                return True
            if isinstance(value, str):
                return str(value).strip() in {"", "N/A", "None", "null", "nan"}
            return False

        zero_invalid_fields = {
            "marketCap",
            "trailingPE",
            "forwardPE",
            "priceToBook",
            "beta",
            "fiftyTwoWeekHigh",
            "fiftyTwoWeekLow",
            "sharesOutstanding",
            "floatShares",
            "totalRevenue",
        }

        def infer_period(field_name: str, source_name: str, raw_key: str) -> str:
            meta_period = source_meta_periods.get(source_name, {}).get(field_name)
            if isinstance(meta_period, str) and meta_period.strip():
                return meta_period
            if field_name == "trailingPE":
                return "ttm"
            if field_name == "forwardPE":
                return "consensus"
            if field_name in {"marketCap", "priceToBook", "sharesOutstanding", "floatShares", "debtToEquity", "currentRatio"}:
                return "latest"
            if field_name in {"fiftyTwoWeekHigh", "fiftyTwoWeekLow"}:
                return "rolling_52w"
            if field_name in {"grossMargins", "operatingMargins", "returnOnEquity", "returnOnAssets"}:
                return "ttm"
            if raw_key in {"QuarterlyRevenueGrowthYOY", "QuarterlyEarningsGrowthYOY"}:
                return "latest_quarter_yoy"
            if field_name in {"revenueGrowth", "netIncomeGrowth"}:
                return "provider_reported_growth"
            if field_name in {"totalRevenue", "netIncome", "freeCashflow", "operatingCashflow"}:
                if source_name in {"yfinance", "fmp", "finnhub", "fmp_quarterly", "yfinance_quarterly"}:
                    return "ttm"
                return "provider_reported_total"
            return "latest"

        def resolve_source_label(field_name: str, source_name: str) -> str:
            meta_source = source_meta_sources.get(source_name, {}).get(field_name)
            if isinstance(meta_source, str) and meta_source.strip():
                return meta_source
            return source_name

        def first_numeric(value: Any) -> Optional[float]:
            if isinstance(value, bool) or value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            try:
                return float(str(value).strip())
            except (TypeError, ValueError):
                return None

        def sum_recent_quarters(rows: List[Dict[str, Any]], key: str, quarters: int = 4) -> Optional[float]:
            samples: List[float] = []
            for row in rows[:quarters]:
                if not isinstance(row, dict):
                    return None
                value = first_numeric(row.get(key))
                if value is None:
                    return None
                samples.append(value)
            if len(samples) != quarters:
                return None
            return round(sum(samples), 4)

        def growth_from_values(curr: Any, prev: Any) -> Optional[float]:
            curr_value = first_numeric(curr)
            prev_value = first_numeric(prev)
            if curr_value is None or prev_value is None or prev_value == 0:
                return None
            return round((curr_value - prev_value) / abs(prev_value), 4)

        def derive_quarterly_metric(rows: List[Dict[str, Any]], key: str) -> Tuple[Optional[float], Optional[str]]:
            ttm_value = sum_recent_quarters(rows, key, quarters=4)
            if ttm_value is not None:
                return ttm_value, "ttm"
            latest_value = first_numeric(rows[0].get(key)) if rows else None
            if latest_value is not None:
                return latest_value, "latest_quarter"
            return None, None

        def derive_quarterly_growth(rows: List[Dict[str, Any]], key: str) -> Tuple[Optional[float], Optional[str]]:
            latest_ttm = sum_recent_quarters(rows, key, quarters=4)
            previous_ttm = sum_recent_quarters(rows[4:], key, quarters=4) if len(rows) >= 8 else None
            growth = growth_from_values(latest_ttm, previous_ttm)
            if growth is not None:
                return growth, "ttm_yoy"
            if len(rows) >= 5:
                growth = growth_from_values(rows[0].get(key), rows[4].get(key))
                if growth is not None:
                    return growth, "latest_quarter_yoy"
            if len(rows) >= 2:
                growth = growth_from_values(rows[0].get(key), rows[1].get(key))
                if growth is not None:
                    return growth, "latest_quarter_qoq"
            return None, None

        source_datasets = {
            "yfinance": yf_data,
            "fundamental_context": raw,
            "fmp": fmp_data,
            "finnhub": finnhub_data,
            "alpha_vantage_overview": alpha,
        }
        source_priority_map = {
            "returnOnEquity": ("fmp", "finnhub", "yfinance", "fundamental_context", "alpha_vantage_overview"),
            "returnOnAssets": ("fmp", "finnhub", "yfinance", "fundamental_context", "alpha_vantage_overview"),
            "grossMargins": ("fmp", "finnhub", "yfinance", "fundamental_context", "alpha_vantage_overview"),
            "operatingMargins": ("fmp", "finnhub", "yfinance", "fundamental_context", "alpha_vantage_overview"),
            "debtToEquity": ("fmp", "finnhub", "yfinance", "fundamental_context", "alpha_vantage_overview"),
            "currentRatio": ("fmp", "finnhub", "yfinance", "fundamental_context", "alpha_vantage_overview"),
            "freeCashflow": ("fmp", "yfinance", "fundamental_context", "finnhub", "alpha_vantage_overview"),
            "operatingCashflow": ("fmp", "yfinance", "fundamental_context", "finnhub", "alpha_vantage_overview"),
            "totalRevenue": ("fmp", "yfinance", "fundamental_context", "finnhub", "alpha_vantage_overview"),
            "netIncome": ("fmp", "yfinance", "fundamental_context", "finnhub", "alpha_vantage_overview"),
        }

        def pick(field_name: str, *keys: str) -> Any:
            source_names = source_priority_map.get(
                field_name,
                ("yfinance", "fundamental_context", "fmp", "finnhub", "alpha_vantage_overview"),
            )
            for source_name in source_names:
                dataset = source_datasets.get(source_name, {})
                for key in keys:
                    val = dataset.get(key)
                    if is_missing(val):
                        continue
                    numeric_val = first_numeric(val)
                    if field_name in zero_invalid_fields and numeric_val == 0:
                        continue
                    field_sources[field_name] = resolve_source_label(field_name, source_name)
                    field_periods[field_name] = infer_period(field_name, source_name, key)
                    return val
            return None

        quarterly_candidates: List[Tuple[str, List[Dict[str, Any]]]] = []
        if fmp_quarterly:
            quarterly_candidates.append(("fmp_quarterly", fmp_quarterly))
        if yf_quarterly:
            quarterly_candidates.append(("yfinance_quarterly", yf_quarterly))

        derived_ttm: Dict[str, Any] = {}
        for source_name, rows in quarterly_candidates:
            revenue_value, revenue_period = derive_quarterly_metric(rows, "revenue")
            net_income_value, net_income_period = derive_quarterly_metric(rows, "net_income")
            operating_cashflow_value, operating_cashflow_period = derive_quarterly_metric(rows, "operating_cashflow")
            free_cashflow_value, free_cashflow_period = derive_quarterly_metric(rows, "free_cash_flow")
            revenue_growth_value, revenue_growth_period = derive_quarterly_growth(rows, "revenue")
            net_income_growth_value, net_income_growth_period = derive_quarterly_growth(rows, "net_income")

            if revenue_value is not None and "totalRevenue" not in derived_ttm:
                derived_ttm["totalRevenue"] = revenue_value
                field_sources["totalRevenue"] = resolve_source_label("totalRevenue", source_name)
                field_periods["totalRevenue"] = revenue_period or "ttm"
            if net_income_value is not None and "netIncome" not in derived_ttm:
                derived_ttm["netIncome"] = net_income_value
                field_sources["netIncome"] = resolve_source_label("netIncome", source_name)
                field_periods["netIncome"] = net_income_period or "ttm"
            if operating_cashflow_value is not None and "operatingCashflow" not in derived_ttm:
                derived_ttm["operatingCashflow"] = operating_cashflow_value
                field_sources["operatingCashflow"] = resolve_source_label("operatingCashflow", source_name)
                field_periods["operatingCashflow"] = operating_cashflow_period or "ttm"
            if free_cashflow_value is not None and "freeCashflow" not in derived_ttm:
                derived_ttm["freeCashflow"] = free_cashflow_value
                field_sources["freeCashflow"] = resolve_source_label("freeCashflow", source_name)
                field_periods["freeCashflow"] = free_cashflow_period or "ttm"
            if revenue_growth_value is not None and "revenueGrowth" not in derived_ttm:
                derived_ttm["revenueGrowth"] = revenue_growth_value
                field_sources["revenueGrowth"] = resolve_source_label("revenueGrowth", source_name)
                field_periods["revenueGrowth"] = revenue_growth_period or "ttm_yoy"
            if net_income_growth_value is not None and "netIncomeGrowth" not in derived_ttm:
                derived_ttm["netIncomeGrowth"] = net_income_growth_value
                field_sources["netIncomeGrowth"] = resolve_source_label("netIncomeGrowth", source_name)
                field_periods["netIncomeGrowth"] = net_income_growth_period or "ttm_yoy"

        normalized = {
            "marketCap": pick("marketCap", "marketCap", "total_market_cap", "market_cap", "MarketCapitalization"),
            "trailingPE": pick("trailingPE", "trailingPE", "pe_ttm", "pe", "PERatio"),
            "forwardPE": pick("forwardPE", "forwardPE", "forward_pe", "ForwardPE"),
            "priceToBook": pick("priceToBook", "priceToBook", "pb_ratio", "pb", "PriceToBookRatio"),
            "beta": pick("beta", "beta", "Beta"),
            "fiftyTwoWeekHigh": pick("fiftyTwoWeekHigh", "fiftyTwoWeekHigh", "52week_high", "52WeekHigh"),
            "fiftyTwoWeekLow": pick("fiftyTwoWeekLow", "fiftyTwoWeekLow", "52week_low", "52WeekLow"),
            "sharesOutstanding": pick("sharesOutstanding", "sharesOutstanding", "shares_outstanding", "SharesOutstanding"),
            "floatShares": pick("floatShares", "floatShares", "float_shares", "FloatShares"),
            "totalRevenue": derived_ttm.get("totalRevenue") if "totalRevenue" in derived_ttm else pick("totalRevenue", "totalRevenue", "total_revenue", "revenue", "RevenueTTM"),
            "revenueGrowth": derived_ttm.get("revenueGrowth") if "revenueGrowth" in derived_ttm else pick("revenueGrowth", "revenueGrowth", "revenue_growth", "QuarterlyRevenueGrowthYOY"),
            "netIncome": derived_ttm.get("netIncome") if "netIncome" in derived_ttm else pick("netIncome", "netIncome", "net_income", "NetIncome", "NetIncomeTTM"),
            "netIncomeGrowth": derived_ttm.get("netIncomeGrowth") if "netIncomeGrowth" in derived_ttm else pick("netIncomeGrowth", "netIncomeGrowth", "net_income_growth", "QuarterlyEarningsGrowthYOY"),
            "grossMargins": pick("grossMargins", "grossMargins", "gross_margin", "GrossMargin"),
            "operatingMargins": pick("operatingMargins", "operatingMargins", "operating_margin", "OperatingMarginTTM"),
            "freeCashflow": derived_ttm.get("freeCashflow") if "freeCashflow" in derived_ttm else pick("freeCashflow", "freeCashflow", "free_cashflow"),
            "operatingCashflow": derived_ttm.get("operatingCashflow") if "operatingCashflow" in derived_ttm else pick("operatingCashflow", "operatingCashflow", "operating_cashflow"),
            "debtToEquity": pick("debtToEquity", "debtToEquity", "debt_to_equity"),
            "currentRatio": pick("currentRatio", "currentRatio", "current_ratio"),
            "returnOnEquity": pick("returnOnEquity", "returnOnEquity", "roe", "ReturnOnEquityTTM"),
            "returnOnAssets": pick("returnOnAssets", "returnOnAssets", "roa", "ReturnOnAssetsTTM"),
        }

        for field_name in ("returnOnEquity", "returnOnAssets"):
            period = str(field_periods.get(field_name) or "").strip().lower().replace("-", "_")
            source = str(field_sources.get(field_name) or "").strip().lower().replace("-", "_")
            if normalized.get(field_name) is None:
                continue
            if period and period != "ttm":
                field_periods[field_name] = "ttm_pending_validation"
            elif source in {"fundamental_context", "alpha_vantage_overview"}:
                field_periods[field_name] = "ttm_pending_validation"

        for field_name in ("freeCashflow", "operatingCashflow"):
            period = str(field_periods.get(field_name) or "").strip().lower().replace("-", "_")
            source = str(field_sources.get(field_name) or "").strip().lower().replace("-", "_")
            if normalized.get(field_name) is None:
                continue
            if not period:
                field_periods[field_name] = "ttm_pending_validation"
                continue
            if period == "provider_reported_total" and source in {"fundamental_context", "alpha_vantage_overview", "finnhub"}:
                field_periods[field_name] = "ttm_pending_validation"
        missing = [k for k, v in normalized.items() if v in (None, "", "N/A")]
        insights = {}
        pe = normalized.get("trailingPE")
        rev_growth = normalized.get("revenueGrowth")
        op_margin = normalized.get("operatingMargins")
        gross_margin = normalized.get("grossMargins")
        fcf = normalized.get("freeCashflow")
        ocf = normalized.get("operatingCashflow")
        leverage = normalized.get("debtToEquity")
        if pe in (None, "", "N/A"):
            insights["valuation_profile"] = "valuation_unavailable"
        elif isinstance(pe, (int, float)) and pe > 40:
            insights["valuation_profile"] = "valuation_high"
        elif isinstance(pe, (int, float)) and pe < 15:
            insights["valuation_profile"] = "valuation_low"
        else:
            insights["valuation_profile"] = "valuation_neutral"
        if isinstance(rev_growth, (int, float)):
            if rev_growth > 0.15:
                insights["growth_profile"] = "high_growth"
            elif rev_growth < 0:
                insights["growth_profile"] = "negative_growth"
            else:
                insights["growth_profile"] = "stable_growth"
        else:
            insights["growth_profile"] = "growth_unavailable"
        if isinstance(op_margin, (int, float)):
            insights["profitability_profile"] = "profitable" if op_margin > 0 else "near_breakeven_or_loss"
        elif isinstance(gross_margin, (int, float)):
            insights["profitability_profile"] = "gross_margin_positive"
        else:
            insights["profitability_profile"] = "profitability_unavailable"
        if isinstance(fcf, (int, float)) or isinstance(ocf, (int, float)):
            fcf_val = fcf if isinstance(fcf, (int, float)) else ocf
            insights["cashflow_profile"] = "cashflow_healthy" if isinstance(fcf_val, (int, float)) and fcf_val > 0 else "cashflow_pressure"
        else:
            insights["cashflow_profile"] = "cashflow_unavailable"
        if isinstance(leverage, (int, float)):
            insights["leverage_profile"] = "high_leverage" if leverage > 180 else "leverage_controllable"
        else:
            insights["leverage_profile"] = "leverage_unavailable"
        derived_insights = [v for v in insights.values() if v]
        return {
            "raw": normalized,
            "normalized": normalized,
            "derived_insights": derived_insights,
            "derived_profiles": insights,
            "summary_flags": derived_insights,
            "status": "partial" if missing else "ok",
            "missing_fields": missing,
            "field_sources": field_sources,
            "field_periods": field_periods,
            "source": "yfinance_overview_fallback_chain" if field_sources else "fundamental_pipeline",
        }

    @staticmethod
    def _build_earnings_analysis_block(
        fundamental_context: Optional[Dict[str, Any]],
        yfinance_quarterly_income: Optional[List[Dict[str, Any]]] = None,
        fmp_quarterly_income: Optional[List[Dict[str, Any]]] = None,
        alpha_quarterly_income: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        earnings_data = ((fundamental_context or {}).get("earnings") or {}).get("data", {})
        yfinance_income = yfinance_quarterly_income if isinstance(yfinance_quarterly_income, list) else []
        fmp_income = fmp_quarterly_income if isinstance(fmp_quarterly_income, list) else []
        alpha_income = alpha_quarterly_income if isinstance(alpha_quarterly_income, list) else []
        if not isinstance(earnings_data, dict) and not yfinance_income and not fmp_income and not alpha_income:
            return {
                "quarterly_series": [],
                "derived_metrics": {},
                "summary_flags": ["earnings_data_unavailable"],
                "narrative_insights": ["财报数据不足，无法形成完整趋势判断"],
                "field_sources": {},
                "reporting_basis": "latest_quarter",
                "summary_basis": None,
                "status": "partial",
            }
        field_sources: Dict[str, str] = {}
        quarterly = (earnings_data.get("quarterly_series", []) if isinstance(earnings_data, dict) else [])
        if quarterly:
            field_sources["quarterly_series"] = "fundamental_context"
        elif yfinance_income:
            quarterly = yfinance_income
            field_sources["quarterly_series"] = "yfinance"
        elif fmp_income:
            quarterly = fmp_income
            field_sources["quarterly_series"] = "fmp_income_statement"
        elif alpha_income:
            quarterly = alpha_income
            field_sources["quarterly_series"] = "alpha_vantage_income_statement"
        if not isinstance(quarterly, list):
            quarterly = []
        quarterly = quarterly[:8]
        trend = {}
        flags = []
        if quarterly:
            flags.append("quarterly_series_available")
        if earnings_data.get("financial_report"):
            flags.append("financial_report_available")
        if earnings_data.get("dividend"):
            flags.append("dividend_metrics_available")

        def _delta(curr: Any, prev: Any) -> Optional[float]:
            if not isinstance(curr, (int, float)) or not isinstance(prev, (int, float)) or prev == 0:
                return None
            return round((curr - prev) / abs(prev), 4)

        if len(quarterly) >= 2:
            q0, q1 = quarterly[0], quarterly[1]
            trend["qoq_revenue_growth"] = _delta(q0.get("revenue"), q1.get("revenue"))
            trend["qoq_net_income_change"] = _delta(q0.get("net_income"), q1.get("net_income"))
            trend["loss_status"] = "loss" if isinstance(q0.get("net_income"), (int, float)) and q0.get("net_income") < 0 else "profit"
            if isinstance(q0.get("revenue"), (int, float)) and isinstance(q0.get("gross_profit"), (int, float)) and q0.get("revenue"):
                trend["margin_trend"] = round(q0.get("gross_profit") / q0.get("revenue"), 4)
        if len(quarterly) >= 5:
            q0, q4 = quarterly[0], quarterly[4]
            trend["yoy_revenue_growth"] = _delta(q0.get("revenue"), q4.get("revenue"))
            trend["yoy_net_income_change"] = _delta(q0.get("net_income"), q4.get("net_income"))

        recent_net_income = [x.get("net_income") for x in quarterly if isinstance(x, dict)]
        if recent_net_income:
            losses = [x for x in recent_net_income if isinstance(x, (int, float)) and x < 0]
            if len(losses) >= 2:
                flags.append("continuous_loss")
            if len(losses) >= 2 and abs(losses[0]) < abs(losses[1]):
                flags.append("loss_narrowing")
        if isinstance(trend.get("yoy_revenue_growth"), (int, float)) and isinstance(trend.get("yoy_net_income_change"), (int, float)):
            if trend["yoy_revenue_growth"] > 0 and trend["yoy_net_income_change"] <= 0:
                flags.append("revenue_up_profit_not_following")

        narrative = []
        if "continuous_loss" in flags:
            narrative.append("连续亏损，盈利质量偏弱")
        if "loss_narrowing" in flags:
            narrative.append("亏损收窄，边际改善")
        if "revenue_up_profit_not_following" in flags:
            narrative.append("存在增收不增利迹象")
        if not narrative:
            narrative.append("财报趋势中性，建议结合下一季数据确认。")
        return {
            "quarterly_series": quarterly,
            "derived_metrics": {**(earnings_data.get("derived_metrics", {}) or {}), **trend},
            "summary_flags": flags or ["earnings_partial"],
            "earnings_flags": flags or ["earnings_partial"],
            "narrative_insights": narrative,
            "field_sources": field_sources,
            "reporting_basis": "latest_quarter",
            "summary_basis": "yoy" if isinstance(trend.get("yoy_revenue_growth"), (int, float)) or isinstance(trend.get("yoy_net_income_change"), (int, float)) else (
                "qoq" if isinstance(trend.get("qoq_revenue_growth"), (int, float)) or isinstance(trend.get("qoq_net_income_change"), (int, float)) else None
            ),
            "status": "ok" if flags else "partial",
        }

    @staticmethod
    def _extract_business_keywords(fundamental_context: Optional[Dict[str, Any]]) -> List[str]:
        keywords: List[str] = []
        profile = ((fundamental_context or {}).get("profile") or {}).get("data", {})
        if isinstance(profile, dict):
            for k in ("industry", "sector", "main_business", "company_intro"):
                val = profile.get(k)
                if isinstance(val, str):
                    keywords.extend([x.strip().lower() for x in val.replace("/", " ").split() if x.strip()])
        return list(dict.fromkeys([x for x in keywords if len(x) > 2]))[:20]

    @staticmethod
    def _build_sentiment_analysis_block(
        news_context: Optional[str],
        news_items: Optional[List[Dict[str, Any]]] = None,
        stock_code: str = "",
        stock_name: str = "",
        business_keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        text = (news_context or "").strip()
        items = news_items or []
        if not text and not items:
            return {
                "top_positive_items": [],
                "top_negative_items": [],
                "sentiment_summary": "no_reliable_news",
                "confidence": "low",
                "summary_flags": ["no_reliable_news"],
                "status": "weak",
                "relevance_type": "low_relevance",
                "relevance_score": 0.0,
                "news_published_at": None,
                "company_sentiment": "no_reliable_news",
                "industry_sentiment": "background_only",
                "regulatory_sentiment": "unknown",
                "overall_confidence": "low",
            }

        company_tokens = {
            stock_code.lower(),
            stock_name.lower(),
            stock_name.replace(" ", "").lower(),
        }
        company_tokens = {t for t in company_tokens if t and t != "股票"}
        event_words = ("earnings", "guidance", "lawsuit", "regulation", "partnership", "product")
        regulatory_words = ("sec", "investigation", "antitrust", "regulator", "compliance", "regulation")
        industry_words = ("industry", "sector", "market", "macro", "peer", "supply chain")
        business_words = tuple((business_keywords or [])[:20])

        classified_items: List[Dict[str, Any]] = []
        for item in items:
            title = str(item.get("title", "")).lower()
            snippet = str(item.get("snippet", "")).lower()
            content = f"{title} {snippet}".strip()
            token_hit = any(tok in content for tok in company_tokens)
            business_hit = any(k and k in content for k in business_words)
            event_hit = any(w in content for w in event_words)
            reg_hit = any(w in content for w in regulatory_words)
            industry_hit = any(w in content for w in industry_words)
            score = 0.15
            rel_type = "low_relevance"
            if token_hit:
                score += 0.45
            if business_hit:
                score += 0.2
            if event_hit:
                score += 0.15
            if reg_hit:
                score += 0.15

            if token_hit and reg_hit:
                rel_type = "regulatory"
            elif token_hit or (business_hit and event_hit):
                rel_type = "company_specific"
            elif reg_hit:
                rel_type = "regulatory"
            elif industry_hit:
                rel_type = "industry_general"
            score = round(min(score, 1.0), 2)
            classified_items.append(
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "news_published_at": item.get("news_published_at"),
                    "relevance_type": rel_type,
                    "relevance_score": score,
                }
            )

        eligible = [
            x for x in classified_items
            if x["relevance_type"] == "company_specific"
            or (x["relevance_type"] == "regulatory" and x["relevance_score"] >= 0.65)
        ]
        if not eligible:
            fail_reason = "source_empty" if not classified_items else "relevance_too_low"
            return {
                "top_positive_items": [],
                "top_negative_items": [],
                "sentiment_summary": "no_reliable_news",
                "confidence": "low",
                "summary_flags": ["no_reliable_news", "industry_noise_filtered"],
                "failure_reason": fail_reason,
                "status": "weak",
                "relevance_type": "low_relevance",
                "relevance_score": 0.0,
                "classified_items": classified_items[:5],
                "news_published_at": classified_items[0]["news_published_at"] if classified_items else None,
                "company_sentiment": "no_reliable_news",
                "industry_sentiment": "background_only",
                "regulatory_sentiment": "unknown",
                "overall_confidence": "low",
            }

        lower = text.lower()
        pos = sum(lower.count(w) for w in ("beat", "upgrade", "growth", "record", "bullish"))
        neg = sum(lower.count(w) for w in ("downgrade", "lawsuit", "risk", "miss", "bearish"))
        score = pos - neg
        summary = "neutral"
        if score > 1:
            summary = "positive"
        elif score < -1:
            summary = "negative"
        lead = max(eligible, key=lambda x: x["relevance_score"])
        return {
            "top_positive_items": [],
            "top_negative_items": [],
            "sentiment_summary": summary,
            "confidence": "medium",
            "summary_flags": [f"score_{score}", f"eligible_items_{len(eligible)}"],
            "status": "ok",
            "relevance_type": lead["relevance_type"],
            "relevance_score": lead["relevance_score"],
            "classified_items": classified_items[:5],
            "news_published_at": lead.get("news_published_at"),
            "company_sentiment": summary if lead["relevance_type"] == "company_specific" else "neutral",
            "industry_sentiment": "background_only",
            "regulatory_sentiment": summary if lead["relevance_type"] == "regulatory" else "neutral",
            "overall_confidence": "medium",
            "failure_reason": None,
        }

    @staticmethod
    def _build_data_quality_block(
        technicals: Dict[str, Dict[str, Any]],
        fundamentals: Dict[str, Any],
        earnings_analysis: Dict[str, Any],
        sentiment_analysis: Dict[str, Any],
        alpha_errors: List[str],
        context: Dict[str, Any],
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        missing_fields: List[str] = []
        for name, node in technicals.items():
            if not isinstance(node, dict):
                continue
            if node.get("status") != "ok":
                missing_fields.append(f"technicals.{name}")
        missing_fields.extend([f"fundamentals.{x}" for x in fundamentals.get("missing_fields", [])])

        warnings = []
        warnings.extend([f"alpha_vantage: {err}" for err in alpha_errors])
        if context.get("realtime", {}).get("volume_ratio") in (None, "数据缺失"):
            warnings.append("volume_ratio_unavailable")
        if context.get("realtime", {}).get("turnover_rate") in (None, "数据缺失"):
            warnings.append("turnover_rate_unavailable")
        for reason in (diagnostics or {}).get("failure_reasons", []):
            warnings.append(f"provider_failure: {reason}")
        return {
            "price_history_status": "ok" if "technicals.ma20" not in missing_fields else "partial",
            "technicals_status": "ok" if all(v.get("status") == "ok" for v in technicals.values()) else "partial",
            "fundamentals_status": fundamentals.get("status", "partial"),
            "earnings_status": earnings_analysis.get("status", "partial"),
            "sentiment_status": sentiment_analysis.get("status", "weak"),
            "missing_fields": missing_fields,
            "warnings": warnings,
            "provider_notes": {
                "market_data": getattr(context.get("realtime", {}).get("source", "unknown"), "value", context.get("realtime", {}).get("source", "unknown")),
                "technicals": "local_from_ohlcv",
                "fundamentals": fundamentals.get("source", "fundamental_pipeline"),
                "fundamental_field_sources": fundamentals.get("field_sources", {}),
                "earnings_field_sources": earnings_analysis.get("field_sources", {}),
                "sentiment": "tavily_filtered",
                "diagnostics": diagnostics or {},
                "time_contract": {
                    "market_timestamp": context.get("market_timestamp"),
                    "market_session_date": context.get("market_session_date"),
                    "news_published_at": context.get("news_published_at"),
                    "report_generated_at": context.get("report_generated_at"),
                    "session_type": context.get("session_type"),
                    "market_timezone": context.get("market_timezone"),
                },
            },
        }

    def _analyze_with_agent(
        self, 
        code: str, 
        report_type: ReportType, 
        query_id: str,
        stock_name: str,
        realtime_quote: Any,
        chip_data: Optional[ChipDistribution],
        fundamental_context: Optional[Dict[str, Any]] = None,
        trend_result: Optional[TrendAnalysisResult] = None,
    ) -> Optional[AnalysisResult]:
        """
        使用 Agent 模式分析单只股票。
        """
        try:
            from src.agent.factory import build_agent_executor
            report_language = normalize_report_language(getattr(self.config, "report_language", "zh"))

            # Build executor from shared factory (ToolRegistry and SkillManager prototype are cached)
            executor = build_agent_executor(self.config, getattr(self.config, 'agent_skills', None) or None)

            # Build initial context to avoid redundant tool calls
            initial_context = {
                "stock_code": code,
                "stock_name": stock_name,
                "report_type": report_type.value,
                "report_language": report_language,
                "fundamental_context": fundamental_context,
            }
            
            if realtime_quote:
                initial_context["realtime_quote"] = self._safe_to_dict(realtime_quote)
            if chip_data:
                initial_context["chip_distribution"] = self._safe_to_dict(chip_data)
            if trend_result:
                initial_context["trend_result"] = self._safe_to_dict(trend_result)

            # Agent path: inject social sentiment as news_context so both
            # executor (_build_user_message) and orchestrator (ctx.set_data)
            # can consume it through the existing news_context channel
            social_context = None
            if self.social_sentiment_service.is_available and is_us_stock_code(code):
                try:
                    social_context = self.social_sentiment_service.get_social_context(code)
                    if social_context:
                        existing = initial_context.get("news_context")
                        if existing:
                            initial_context["news_context"] = existing + "\n\n" + social_context
                        else:
                            initial_context["news_context"] = social_context
                        initial_context["social_context"] = social_context
                        logger.info(f"[{code}] Agent mode: social sentiment data injected into news_context")
                except Exception as e:
                    logger.warning(f"[{code}] Agent mode: social sentiment fetch failed: {e}")

            # 运行 Agent
            if report_language == "en":
                message = f"Analyze stock {code} ({stock_name}) and return the full decision dashboard JSON in English."
            else:
                message = f"请分析股票 {code} ({stock_name})，并生成决策仪表盘报告。"
            agent_result = executor.run(message, context=initial_context)

            # 转换为 AnalysisResult
            result = self._agent_result_to_analysis_result(agent_result, code, stock_name, report_type, query_id)
            if result:
                result.query_id = query_id
                if social_context:
                    dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}
                    intel = dashboard.get("intelligence") if isinstance(dashboard.get("intelligence"), dict) else {}
                    intel.setdefault("social_context", social_context)
                    dashboard["intelligence"] = intel
                    dashboard.setdefault("structured_analysis", {})
                    structured = dashboard["structured_analysis"] if isinstance(dashboard.get("structured_analysis"), dict) else {}
                    sentiment = structured.get("sentiment_analysis") if isinstance(structured.get("sentiment_analysis"), dict) else {}
                    sentiment.setdefault("social_context", social_context)
                    structured["sentiment_analysis"] = sentiment
                    dashboard["structured_analysis"] = structured
                    result.dashboard = dashboard
            # Agent weak integrity: placeholder fill only, no LLM retry
            if result and getattr(self.config, "report_integrity_enabled", False):
                from src.analyzer import check_content_integrity, apply_placeholder_fill

                pass_integrity, missing = check_content_integrity(result)
                if not pass_integrity:
                    apply_placeholder_fill(result, missing)
                    logger.info(
                        "[LLM完整性] integrity_mode=agent_weak 必填字段缺失 %s，已占位补全",
                        missing,
                    )
            # chip_structure fallback (Issue #589), before save_analysis_history
            if result and chip_data:
                fill_chip_structure_if_needed(result, chip_data)

            # price_position fallback (same as non-agent path Step 7.7)
            if result:
                fill_price_position_if_needed(result, trend_result, realtime_quote)

            resolved_stock_name = result.name if result and result.name else stock_name

            # 保存新闻情报到数据库（Agent 工具结果仅用于 LLM 上下文，未持久化，Fixes #396）
            # 使用 search_stock_news（与 Agent 工具调用逻辑一致），仅 1 次 API 调用，无额外延迟
            if self.search_service.is_available:
                try:
                    news_response = self.search_service.search_stock_news(
                        stock_code=code,
                        stock_name=resolved_stock_name,
                        max_results=5
                    )
                    if news_response.success and news_response.results:
                        query_context = self._build_query_context(query_id=query_id)
                        self.db.save_news_intel(
                            code=code,
                            name=resolved_stock_name,
                            dimension="latest_news",
                            query=news_response.query,
                            response=news_response,
                            query_context=query_context
                        )
                        logger.info(f"[{code}] Agent 模式: 新闻情报已保存 {len(news_response.results)} 条")
                except Exception as e:
                    logger.warning(f"[{code}] Agent 模式保存新闻情报失败: {e}")

            # 保存分析历史记录
            if result:
                try:
                    initial_context["stock_name"] = resolved_stock_name
                    self.db.save_analysis_history(
                        result=result,
                        query_id=query_id,
                        report_type=report_type.value,
                        news_content=None,
                        context_snapshot=initial_context,
                        save_snapshot=self.save_context_snapshot
                    )
                except Exception as e:
                    logger.warning(f"[{code}] 保存 Agent 分析历史失败: {e}")

            return result

        except Exception as e:
            logger.error(f"[{code}] Agent 分析失败: {e}")
            logger.exception(f"[{code}] Agent 详细错误信息:")
            return None

    def _agent_result_to_analysis_result(
        self, agent_result, code: str, stock_name: str, report_type: ReportType, query_id: str
    ) -> AnalysisResult:
        """
        将 AgentResult 转换为 AnalysisResult。
        """
        report_language = normalize_report_language(getattr(self.config, "report_language", "zh"))
        result = AnalysisResult(
            code=code,
            name=stock_name,
            sentiment_score=50,
            trend_prediction="Unknown" if report_language == "en" else "未知",
            operation_advice="Watch" if report_language == "en" else "观望",
            confidence_level=localize_confidence_level("medium", report_language),
            report_language=report_language,
            success=agent_result.success,
            error_message=agent_result.error or None,
            data_sources=f"agent:{agent_result.provider}",
            model_used=agent_result.model or None,
        )

        if agent_result.success and agent_result.dashboard:
            dash = agent_result.dashboard
            ai_stock_name = str(dash.get("stock_name", "")).strip()
            if ai_stock_name and self._is_placeholder_stock_name(stock_name, code):
                result.name = ai_stock_name
            result.sentiment_score = self._safe_int(dash.get("sentiment_score"), 50)
            result.trend_prediction = dash.get("trend_prediction", "Unknown" if report_language == "en" else "未知")
            raw_advice = dash.get("operation_advice", "Watch" if report_language == "en" else "观望")
            if isinstance(raw_advice, dict):
                # LLM may return {"no_position": "...", "has_position": "..."}
                # Derive a short string from decision_type for the scalar field
                _signal_to_advice = {
                    "buy": "Buy" if report_language == "en" else "买入",
                    "sell": "Sell" if report_language == "en" else "卖出",
                    "hold": "Hold" if report_language == "en" else "持有",
                    "strong_buy": "Strong Buy" if report_language == "en" else "强烈买入",
                    "strong_sell": "Strong Sell" if report_language == "en" else "强烈卖出",
                }
                # Normalize decision_type (strip/lower) before lookup so
                # variants like "BUY" or " Buy " map correctly.
                raw_dt = str(dash.get("decision_type") or "hold").strip().lower()
                result.operation_advice = _signal_to_advice.get(raw_dt, "Watch" if report_language == "en" else "观望")
            else:
                result.operation_advice = str(raw_advice) if raw_advice else ("Watch" if report_language == "en" else "观望")
            from src.agent.protocols import normalize_decision_signal

            result.decision_type = normalize_decision_signal(
                dash.get("decision_type", "hold")
            )
            result.confidence_level = localize_confidence_level(
                dash.get("confidence_level", result.confidence_level),
                report_language,
            )
            result.analysis_summary = dash.get("analysis_summary", "")
            # The AI returns a top-level dict that contains a nested 'dashboard' sub-key
            # with core_conclusion / battle_plan / intelligence.  AnalysisResult's helper
            # methods (get_sniper_points, get_core_conclusion, etc.) expect that inner
            # structure, so we unwrap it here.
            result.dashboard = dash.get("dashboard") or dash
        else:
            result.sentiment_score = 50
            result.operation_advice = "Watch" if report_language == "en" else "观望"
            if not result.error_message:
                result.error_message = "Agent failed to generate a valid decision dashboard" if report_language == "en" else "Agent 未能生成有效的决策仪表盘"

        return result

    @staticmethod
    def _is_placeholder_stock_name(name: str, code: str) -> bool:
        """Return True when the stock name is missing or placeholder-like."""
        if not name:
            return True
        normalized = str(name).strip()
        if not normalized:
            return True
        if normalized == code:
            return True
        if normalized.startswith("股票"):
            return True
        if "Unknown" in normalized:
            return True
        return False

    @staticmethod
    def _safe_int(value: Any, default: int = 50) -> int:
        """安全地将值转换为整数。"""
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            import re
            match = re.search(r'-?\d+', value)
            if match:
                return int(match.group())
        return default
    
    def _describe_volume_ratio(self, volume_ratio: float) -> str:
        """
        量比描述
        
        量比 = 当前成交量 / 过去5日平均成交量
        """
        if volume_ratio < 0.5:
            return "极度萎缩"
        elif volume_ratio < 0.8:
            return "明显萎缩"
        elif volume_ratio < 1.2:
            return "正常"
        elif volume_ratio < 2.0:
            return "温和放量"
        elif volume_ratio < 3.0:
            return "明显放量"
        else:
            return "巨量"

    @staticmethod
    def _compute_ma_status(close: float, ma5: float, ma10: float, ma20: float) -> str:
        """
        Compute MA alignment status from price and MA values.
        Logic mirrors storage._analyze_ma_status (Issue #234).
        """
        close = close or 0
        ma5 = ma5 or 0
        ma10 = ma10 or 0
        ma20 = ma20 or 0
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

    def _augment_historical_with_realtime(
        self, df: pd.DataFrame, realtime_quote: Any, code: str
    ) -> pd.DataFrame:
        """
        Augment historical OHLCV with today's realtime quote for intraday MA calculation.
        Issue #234: Use realtime price instead of yesterday's close for technical indicators.
        """
        if df is None or df.empty or 'close' not in df.columns:
            return df
        if realtime_quote is None:
            return df
        price = getattr(realtime_quote, 'price', None)
        if price is None or not (isinstance(price, (int, float)) and price > 0):
            return df

        # Optional: skip augmentation on non-trading days (fail-open)
        enable_realtime_tech = getattr(
            self.config, 'enable_realtime_technical_indicators', True
        )
        if not enable_realtime_tech:
            return df
        market = get_market_for_stock(code)
        if market and not is_market_open(market, date.today()):
            return df

        last_val = df['date'].max()
        last_date = (
            last_val.date() if hasattr(last_val, 'date') else
            (last_val if isinstance(last_val, date) else pd.Timestamp(last_val).date())
        )
        yesterday_close = float(df.iloc[-1]['close']) if len(df) > 0 else price
        open_p = getattr(realtime_quote, 'open_price', None) or getattr(
            realtime_quote, 'pre_close', None
        ) or yesterday_close
        high_p = getattr(realtime_quote, 'high', None) or price
        low_p = getattr(realtime_quote, 'low', None) or price
        vol = getattr(realtime_quote, 'volume', None) or 0
        amt = getattr(realtime_quote, 'amount', None)
        pct = getattr(realtime_quote, 'change_pct', None)

        if last_date >= date.today():
            # Update last row with realtime close (copy to avoid mutating caller's df)
            df = df.copy()
            idx = df.index[-1]
            df.loc[idx, 'close'] = price
            if open_p is not None:
                df.loc[idx, 'open'] = open_p
            if high_p is not None:
                df.loc[idx, 'high'] = high_p
            if low_p is not None:
                df.loc[idx, 'low'] = low_p
            if vol:
                df.loc[idx, 'volume'] = vol
            if amt is not None:
                df.loc[idx, 'amount'] = amt
            if pct is not None:
                df.loc[idx, 'pct_chg'] = pct
        else:
            # Append virtual today row
            new_row = {
                'code': code,
                'date': date.today(),
                'open': open_p,
                'high': high_p,
                'low': low_p,
                'close': price,
                'volume': vol,
                'amount': amt if amt is not None else 0,
                'pct_chg': pct if pct is not None else 0,
            }
            new_df = pd.DataFrame([new_row])
            df = pd.concat([df, new_df], ignore_index=True)
        return df

    def _build_context_snapshot(
        self,
        enhanced_context: Dict[str, Any],
        news_content: Optional[str],
        realtime_quote: Any,
        chip_data: Optional[ChipDistribution]
    ) -> Dict[str, Any]:
        """
        构建分析上下文快照
        """
        return {
            "enhanced_context": enhanced_context,
            "news_content": news_content,
            "realtime_quote_raw": self._safe_to_dict(realtime_quote),
            "chip_distribution_raw": self._safe_to_dict(chip_data),
        }

    @staticmethod
    def _safe_to_dict(value: Any) -> Optional[Dict[str, Any]]:
        """
        安全转换为字典
        """
        if value is None:
            return None
        if hasattr(value, "to_dict"):
            try:
                return value.to_dict()
            except Exception:
                return None
        if hasattr(value, "__dict__"):
            try:
                return dict(value.__dict__)
            except Exception:
                return None
        return None

    def _resolve_query_source(self, query_source: Optional[str]) -> str:
        """
        解析请求来源。

        优先级（从高到低）：
        1. 显式传入的 query_source：调用方明确指定时优先使用，便于覆盖推断结果或兼容未来 source_message 来自非 bot 的场景
        2. 存在 source_message 时推断为 "bot"：当前约定为机器人会话上下文
        3. 存在 query_id 时推断为 "web"：Web 触发的请求会带上 query_id
        4. 默认 "system"：定时任务或 CLI 等无上述上下文时

        Args:
            query_source: 调用方显式指定的来源，如 "bot" / "web" / "cli" / "system"

        Returns:
            归一化后的来源标识字符串，如 "bot" / "web" / "cli" / "system"
        """
        if query_source:
            return query_source
        if self.source_message:
            return "bot"
        if self.query_id:
            return "web"
        return "system"

    def _build_query_context(self, query_id: Optional[str] = None) -> Dict[str, str]:
        """
        生成用户查询关联信息
        """
        effective_query_id = query_id or self.query_id or ""

        context: Dict[str, str] = {
            "query_id": effective_query_id,
            "query_source": self.query_source or "",
        }

        if self.source_message:
            context.update({
                "requester_platform": self.source_message.platform or "",
                "requester_user_id": self.source_message.user_id or "",
                "requester_user_name": self.source_message.user_name or "",
                "requester_chat_id": self.source_message.chat_id or "",
                "requester_message_id": self.source_message.message_id or "",
                "requester_query": self.source_message.content or "",
            })

        return context
    
    def process_single_stock(
        self,
        code: str,
        skip_analysis: bool = False,
        single_stock_notify: bool = False,
        report_type: ReportType = ReportType.SIMPLE,
        analysis_query_id: Optional[str] = None,
    ) -> Optional[AnalysisResult]:
        """
        处理单只股票的完整流程

        包括：
        1. 获取数据
        2. 保存数据
        3. AI 分析
        4. 单股推送（可选，#55）

        此方法会被线程池调用，需要处理好异常

        Args:
            analysis_query_id: 查询链路关联 id
            code: 股票代码
            skip_analysis: 是否跳过 AI 分析
            single_stock_notify: 是否启用单股推送模式（每分析完一只立即推送）
            report_type: 报告类型枚举（从配置读取，Issue #119）

        Returns:
            AnalysisResult 或 None
        """
        logger.info(f"========== 开始处理 {code} ==========")
        
        try:
            # Step 1: 获取并保存数据
            success, error = self.fetch_and_save_stock_data(code)
            
            if not success:
                logger.warning(f"[{code}] 数据获取失败: {error}")
                # 即使获取失败，也尝试用已有数据分析
            
            # Step 2: AI 分析
            if skip_analysis:
                logger.info(f"[{code}] 跳过 AI 分析（dry-run 模式）")
                return None
            
            effective_query_id = analysis_query_id or self.query_id or uuid.uuid4().hex
            result = self.analyze_stock(code, report_type, query_id=effective_query_id)
            
            if result:
                if not result.success:
                    logger.warning(
                        f"[{code}] 分析未成功: {result.error_message or '未知错误'}"
                    )
                else:
                    logger.info(
                        f"[{code}] 分析完成: {result.operation_advice}, "
                        f"评分 {result.sentiment_score}"
                    )
                
                # 单股推送模式（#55）：每分析完一只股票立即推送
                if single_stock_notify:
                    available_channels = []
                    try:
                        available_channels = [
                            channel.value for channel in (self.notifier.get_available_channels() or [])
                        ] if self.notifier.is_available() else []
                    except Exception:
                        available_channels = []

                    notification_result: Dict[str, Any] = {
                        "attempted": False,
                        "status": "not_configured" if not self.notifier.is_available() else "unknown",
                        "success": None,
                        "channels": available_channels,
                        "truth": "actual",
                        "attempts": [],
                    }

                    if self.notifier.is_available():
                        try:
                            # 根据报告类型选择生成方法
                            if report_type == ReportType.FULL:
                                report_content = self.notifier.generate_dashboard_report([result])
                                logger.info(f"[{code}] 使用完整报告格式")
                            elif report_type == ReportType.BRIEF:
                                report_content = self.notifier.generate_brief_report([result])
                                logger.info(f"[{code}] 使用简洁报告格式")
                            else:
                                report_content = self.notifier.generate_single_stock_report(result)
                                logger.info(f"[{code}] 使用精简报告格式")

                            push_ok = self.notifier.send(report_content, email_stock_codes=[code])
                            notification_result.update(
                                {
                                    "attempted": True,
                                    "status": "ok" if push_ok else "failed",
                                    "success": bool(push_ok),
                                    "attempts": [
                                        {
                                            "sequence": 1,
                                            "channel": (available_channels[0] if available_channels else "notification"),
                                            "action": "succeeded" if push_ok else "failed",
                                            "result": "succeeded" if push_ok else "failed",
                                            "message": (
                                                f"Notification sent via {(available_channels[0] if available_channels else 'notification')}."
                                                if push_ok
                                                else f"Notification failed via {(available_channels[0] if available_channels else 'notification')}."
                                            ),
                                        }
                                    ],
                                }
                            )
                            if push_ok:
                                logger.info(f"[{code}] 单股推送成功")
                            else:
                                logger.warning(f"[{code}] 单股推送失败")
                        except Exception as e:
                            notification_result.update(
                                {
                                    "attempted": True,
                                    "status": "failed",
                                    "success": False,
                                    "error": str(e),
                                    "attempts": [
                                        {
                                            "sequence": 1,
                                            "channel": (available_channels[0] if available_channels else "notification"),
                                            "action": "failed",
                                            "result": "timeout" if "timeout" in str(e).lower() else "failed",
                                            "reason": str(e),
                                            "message": f"Notification exception via {(available_channels[0] if available_channels else 'notification')}: {e}",
                                        }
                                    ],
                                }
                            )
                            logger.error(f"[{code}] 单股推送异常: {e}")
                    result.notification_result = notification_result
                else:
                    result.notification_result = {
                        "attempted": False,
                        "status": "skipped",
                        "success": None,
                        "channels": [],
                        "truth": "actual",
                        "attempts": [],
                    }

                try:
                    from src.services.execution_log_service import classify_notification_state
                    if isinstance(result.notification_result, dict):
                        result.notification_result["delivery_classification"] = classify_notification_state(result.notification_result)
                except Exception:
                    pass

                if isinstance(getattr(result, "runtime_execution", None), dict):
                    result.runtime_execution["notification"] = result.notification_result
                    steps = result.runtime_execution.get("steps")
                    if isinstance(steps, list):
                        for step in steps:
                            if isinstance(step, dict) and step.get("key") == "notification":
                                step["status"] = str((result.notification_result or {}).get("status") or "unknown")
                                break
            
            return result
            
        except Exception as e:
            # 捕获所有异常，确保单股失败不影响整体
            logger.exception(f"[{code}] 处理过程发生未知异常: {e}")
            return None
    
    def run(
        self,
        stock_codes: Optional[List[str]] = None,
        dry_run: bool = False,
        send_notification: bool = True,
        merge_notification: bool = False
    ) -> List[AnalysisResult]:
        """
        运行完整的分析流程

        流程：
        1. 获取待分析的股票列表
        2. 使用线程池并发处理
        3. 收集分析结果
        4. 发送通知

        Args:
            stock_codes: 股票代码列表（可选，默认使用配置中的自选股）
            dry_run: 是否仅获取数据不分析
            send_notification: 是否发送推送通知
            merge_notification: 是否合并推送（跳过本次推送，由 main 层合并个股+大盘后统一发送，Issue #190）

        Returns:
            分析结果列表
        """
        start_time = time.time()
        
        # 使用配置中的股票列表
        if stock_codes is None:
            self.config.refresh_stock_list()
            stock_codes = self.config.stock_list
        
        if not stock_codes:
            logger.error("未配置自选股列表，请在 .env 文件中设置 STOCK_LIST")
            return []
        
        logger.info(f"===== 开始分析 {len(stock_codes)} 只股票 =====")
        logger.info(f"股票列表: {', '.join(stock_codes)}")
        logger.info(f"并发数: {self.max_workers}, 模式: {'仅获取数据' if dry_run else '完整分析'}")
        
        # === 批量预取实时行情（优化：避免每只股票都触发全量拉取）===
        # 只有股票数量 >= 5 时才进行预取，少量股票直接逐个查询更高效
        if len(stock_codes) >= 5:
            prefetch_count = self.fetcher_manager.prefetch_realtime_quotes(stock_codes)
            if prefetch_count > 0:
                logger.info(f"已启用批量预取架构：一次拉取全市场数据，{len(stock_codes)} 只股票共享缓存")

        # Issue #455: 预取股票名称，避免并发分析时显示「股票xxxxx」
        # dry_run 仅做数据拉取，不需要名称预取，避免额外网络开销
        if not dry_run:
            self.fetcher_manager.prefetch_stock_names(stock_codes, use_bulk=False)

        # 单股推送模式（#55）：从配置读取
        single_stock_notify = getattr(self.config, 'single_stock_notify', False)
        # Issue #119: 从配置读取报告类型
        report_type_str = getattr(self.config, 'report_type', 'simple').lower()
        if report_type_str == 'brief':
            report_type = ReportType.BRIEF
        elif report_type_str == 'full':
            report_type = ReportType.FULL
        else:
            report_type = ReportType.SIMPLE
        # Issue #128: 从配置读取分析间隔
        analysis_delay = getattr(self.config, 'analysis_delay', 0)

        if single_stock_notify:
            logger.info(f"已启用单股推送模式：每分析完一只股票立即推送（报告类型: {report_type_str}）")
        
        results: List[AnalysisResult] = []
        
        # 使用线程池并发处理
        # 注意：max_workers 设置较低（默认3）以避免触发反爬
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交任务
            future_to_code = {
                executor.submit(
                    self.process_single_stock,
                    code,
                    skip_analysis=dry_run,
                    single_stock_notify=single_stock_notify and send_notification,
                    report_type=report_type,  # Issue #119: 传递报告类型
                    analysis_query_id=uuid.uuid4().hex,
                ): code
                for code in stock_codes
            }
            
            # 收集结果
            for idx, future in enumerate(as_completed(future_to_code)):
                code = future_to_code[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)

                    # Issue #128: 分析间隔 - 在个股分析和大盘分析之间添加延迟
                    if idx < len(stock_codes) - 1 and analysis_delay > 0:
                        # 注意：此 sleep 发生在“主线程收集 future 的循环”中，
                        # 并不会阻止线程池中的任务同时发起网络请求。
                        # 因此它对降低并发请求峰值的效果有限；真正的峰值主要由 max_workers 决定。
                        # 该行为目前保留（按需求不改逻辑）。
                        logger.debug(f"等待 {analysis_delay} 秒后继续下一只股票...")
                        time.sleep(analysis_delay)

                except Exception as e:
                    logger.error(f"[{code}] 任务执行失败: {e}")
        
        # 统计
        elapsed_time = time.time() - start_time
        
        # dry-run 模式下，数据获取成功即视为成功
        if dry_run:
            # 检查哪些股票的数据今天已存在
            success_count = sum(1 for code in stock_codes if self.db.has_today_data(code))
            fail_count = len(stock_codes) - success_count
        else:
            success_count = len(results)
            fail_count = len(stock_codes) - success_count
        
        logger.info("===== 分析完成 =====")
        logger.info(f"成功: {success_count}, 失败: {fail_count}, 耗时: {elapsed_time:.2f} 秒")
        
        # 保存报告到本地文件（无论是否推送通知都保存）
        if results and not dry_run:
            self._save_local_report(results, report_type)

        # 发送通知（单股推送模式下跳过汇总推送，避免重复）
        if results and send_notification and not dry_run:
            if single_stock_notify:
                # 单股推送模式：只保存汇总报告，不再重复推送
                logger.info("单股推送模式：跳过汇总推送，仅保存报告到本地")
                self._send_notifications(results, report_type, skip_push=True)
            elif merge_notification:
                # 合并模式（Issue #190）：仅保存，不推送，由 main 层合并个股+大盘后统一发送
                logger.info("合并推送模式：跳过本次推送，将在个股+大盘复盘后统一发送")
                self._send_notifications(results, report_type, skip_push=True)
            else:
                self._send_notifications(results, report_type)
        
        return results
    
    def _save_local_report(
        self,
        results: List[AnalysisResult],
        report_type: ReportType = ReportType.SIMPLE,
    ) -> None:
        """保存分析报告到本地文件（与通知推送解耦）"""
        try:
            report = self._generate_aggregate_report(results, report_type)
            filepath = self.notifier.save_report_to_file(report)
            logger.info(f"决策仪表盘日报已保存: {filepath}")
        except Exception as e:
            logger.error(f"保存本地报告失败: {e}")

    def _send_notifications(
        self,
        results: List[AnalysisResult],
        report_type: ReportType = ReportType.SIMPLE,
        skip_push: bool = False,
    ) -> None:
        """
        发送分析结果通知
        
        生成决策仪表盘格式的报告
        
        Args:
            results: 分析结果列表
            skip_push: 是否跳过推送（仅保存到本地，用于单股推送模式）
        """
        try:
            logger.info("生成决策仪表盘日报...")
            report = self._generate_aggregate_report(results, report_type)
            
            # 跳过推送（单股推送模式 / 合并模式：报告已由 _save_local_report 保存）
            if skip_push:
                return
            
            # 推送通知
            if self.notifier.is_available():
                channels = self.notifier.get_available_channels()
                context_success = self.notifier.send_to_context(report)

                # Issue #455: Markdown 转图片（与 notification.send 逻辑一致）
                from src.md2img import markdown_to_image

                channels_needing_image = {
                    ch for ch in channels
                    if ch.value in self.notifier._markdown_to_image_channels
                }
                non_wechat_channels_needing_image = {
                    ch for ch in channels_needing_image if ch != NotificationChannel.WECHAT
                }

                def _get_md2img_hint() -> str:
                    try:
                        engine = getattr(get_config(), "md2img_engine", "wkhtmltoimage")
                    except Exception:
                        engine = "wkhtmltoimage"
                    return (
                        "npm i -g markdown-to-file" if engine == "markdown-to-file"
                        else "wkhtmltopdf (apt install wkhtmltopdf / brew install wkhtmltopdf)"
                    )

                image_bytes = None
                if non_wechat_channels_needing_image:
                    image_bytes = markdown_to_image(
                        report, max_chars=self.notifier._markdown_to_image_max_chars
                    )
                    if image_bytes:
                        logger.info(
                            "Markdown 已转换为图片，将向 %s 发送图片",
                            [ch.value for ch in non_wechat_channels_needing_image],
                        )
                    else:
                        logger.warning(
                            "Markdown 转图片失败，将回退为文本发送。请检查 MARKDOWN_TO_IMAGE_CHANNELS 配置并安装 %s",
                            _get_md2img_hint(),
                        )

                # 企业微信：只发精简版（平台限制）
                wechat_success = False
                if NotificationChannel.WECHAT in channels:
                    if report_type == ReportType.BRIEF:
                        dashboard_content = self.notifier.generate_brief_report(results)
                    else:
                        dashboard_content = self.notifier.generate_wechat_dashboard(results)
                    logger.info(f"企业微信仪表盘长度: {len(dashboard_content)} 字符")
                    logger.debug(f"企业微信推送内容:\n{dashboard_content}")
                    wechat_image_bytes = None
                    if NotificationChannel.WECHAT in channels_needing_image:
                        wechat_image_bytes = markdown_to_image(
                            dashboard_content,
                            max_chars=self.notifier._markdown_to_image_max_chars,
                        )
                        if wechat_image_bytes is None:
                            logger.warning(
                                "企业微信 Markdown 转图片失败，将回退为文本发送。请检查 MARKDOWN_TO_IMAGE_CHANNELS 配置并安装 %s",
                                _get_md2img_hint(),
                            )
                    use_image = self.notifier._should_use_image_for_channel(
                        NotificationChannel.WECHAT, wechat_image_bytes
                    )
                    if use_image:
                        wechat_success = self.notifier._send_wechat_image(wechat_image_bytes)
                    else:
                        wechat_success = self.notifier.send_to_wechat(dashboard_content)

                # 其他渠道：发完整报告（避免自定义 Webhook 被 wechat 截断逻辑污染）
                non_wechat_success = False
                stock_email_groups = getattr(self.config, 'stock_email_groups', []) or []
                for channel in channels:
                    if channel == NotificationChannel.WECHAT:
                        continue
                    if channel == NotificationChannel.FEISHU:
                        non_wechat_success = self.notifier.send_to_feishu(report) or non_wechat_success
                    elif channel == NotificationChannel.TELEGRAM:
                        use_image = self.notifier._should_use_image_for_channel(
                            channel, image_bytes
                        )
                        if use_image:
                            result = self.notifier._send_telegram_photo(image_bytes)
                        else:
                            result = self.notifier.send_to_telegram(report)
                        non_wechat_success = result or non_wechat_success
                    elif channel == NotificationChannel.EMAIL:
                        if stock_email_groups:
                            code_to_emails: Dict[str, Optional[List[str]]] = {}
                            for r in results:
                                if r.code not in code_to_emails:
                                    emails = []
                                    for stocks, emails_list in stock_email_groups:
                                        if r.code in stocks:
                                            emails.extend(emails_list)
                                    code_to_emails[r.code] = list(dict.fromkeys(emails)) if emails else None
                            emails_to_results: Dict[Optional[Tuple], List] = defaultdict(list)
                            for r in results:
                                recs = code_to_emails.get(r.code)
                                key = tuple(recs) if recs else None
                                emails_to_results[key].append(r)
                            for key, group_results in emails_to_results.items():
                                grp_report = self._generate_aggregate_report(group_results, report_type)
                                grp_image_bytes = None
                                if channel.value in self.notifier._markdown_to_image_channels:
                                    grp_image_bytes = markdown_to_image(
                                        grp_report,
                                        max_chars=self.notifier._markdown_to_image_max_chars,
                                    )
                                use_image = self.notifier._should_use_image_for_channel(
                                    channel, grp_image_bytes
                                )
                                receivers = list(key) if key is not None else None
                                if use_image:
                                    result = self.notifier._send_email_with_inline_image(
                                        grp_image_bytes, receivers=receivers
                                    )
                                else:
                                    result = self.notifier.send_to_email(
                                        grp_report, receivers=receivers
                                    )
                                non_wechat_success = result or non_wechat_success
                        else:
                            use_image = self.notifier._should_use_image_for_channel(
                                channel, image_bytes
                            )
                            if use_image:
                                result = self.notifier._send_email_with_inline_image(image_bytes)
                            else:
                                result = self.notifier.send_to_email(report)
                            non_wechat_success = result or non_wechat_success
                    elif channel == NotificationChannel.CUSTOM:
                        use_image = self.notifier._should_use_image_for_channel(
                            channel, image_bytes
                        )
                        if use_image:
                            result = self.notifier._send_custom_webhook_image(
                                image_bytes, fallback_content=report
                            )
                        else:
                            result = self.notifier.send_to_custom(report)
                        non_wechat_success = result or non_wechat_success
                    elif channel == NotificationChannel.PUSHPLUS:
                        non_wechat_success = self.notifier.send_to_pushplus(report) or non_wechat_success
                    elif channel == NotificationChannel.SERVERCHAN3:
                        non_wechat_success = self.notifier.send_to_serverchan3(report) or non_wechat_success
                    elif channel == NotificationChannel.DISCORD:
                        non_wechat_success = self.notifier.send_to_discord(report) or non_wechat_success
                    elif channel == NotificationChannel.PUSHOVER:
                        non_wechat_success = self.notifier.send_to_pushover(report) or non_wechat_success
                    elif channel == NotificationChannel.ASTRBOT:
                        non_wechat_success = self.notifier.send_to_astrbot(report) or non_wechat_success
                    elif channel == NotificationChannel.SLACK:
                        use_image = self.notifier._should_use_image_for_channel(
                            channel, image_bytes
                        )
                        if use_image and self.notifier._slack_bot_token and self.notifier._slack_channel_id:
                            result = self.notifier._send_slack_image(
                                image_bytes, fallback_content=report
                            )
                        else:
                            result = self.notifier.send_to_slack(report)
                        non_wechat_success = result or non_wechat_success
                    else:
                        logger.warning(f"未知通知渠道: {channel}")

                success = wechat_success or non_wechat_success or context_success
                if success:
                    logger.info("决策仪表盘推送成功")
                else:
                    logger.warning("决策仪表盘推送失败")
            else:
                logger.info("通知渠道未配置，跳过推送")
                
        except Exception as e:
            import traceback
            logger.error(f"发送通知失败: {e}\n{traceback.format_exc()}")

    def _generate_aggregate_report(
        self,
        results: List[AnalysisResult],
        report_type: ReportType,
    ) -> str:
        """Generate aggregate report with backward-compatible notifier fallback."""
        generator = getattr(self.notifier, "generate_aggregate_report", None)
        if callable(generator):
            return generator(results, report_type)
        if report_type == ReportType.BRIEF and hasattr(self.notifier, "generate_brief_report"):
            return self.notifier.generate_brief_report(results)
        return self.notifier.generate_dashboard_report(results)
