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
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

from src.config import get_config, Config
from src.storage import get_db
from data_provider import DataFetcherManager
from data_provider.realtime_types import ChipDistribution
from src.analyzer import GeminiAnalyzer, AnalysisResult, fill_chip_structure_if_needed, fill_price_position_if_needed
from src.data.stock_mapping import STOCK_NAME_MAP
from src.notification import NotificationService, NotificationChannel
from src.report_language import (
    get_unknown_text,
    localize_confidence_level,
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
            # 注意：这里用自然日 date.today() 做“断点续传”判断。
            # 若在周末/节假日/非交易日运行，或机器时区不在中国，可能出现：
            # - 数据库已有最新交易日数据但仍会重复拉取（has_today_data 返回 False）
            # - 或在跨日/时区偏移时误判“今日已有数据”
            # 该行为目前保留（按需求不改逻辑），但如需更严谨可改为“最新交易日/数据源最新日期”判断。
            
            # 断点续传检查：如果今日数据已存在，跳过
            if not force_refresh and self.db.has_today_data(code, today):
                logger.info(f"{stock_name}({code}) 今日数据已存在，跳过获取（断点续传）")
                return True, None

            # 从数据源获取数据
            logger.info(f"{stock_name}({code}) 开始从数据源获取数据...")
            df = None
            source_name = ""
            history_fetch_error = None
            if is_us_stock_code(code):
                us_snapshot_df, us_snapshot_source = self._build_us_realtime_snapshot_df(code)
                if us_snapshot_df is not None and not us_snapshot_df.empty:
                    df = us_snapshot_df
                    source_name = us_snapshot_source
                    logger.info(
                        f"{stock_name}({code}) 使用美股实时快照入库，跳过 Yahoo 历史拉取 "
                        f"(来源: {source_name})"
                    )
            try:
                if df is None:
                    df, source_name = self.fetcher_manager.get_daily_data(code, days=30)
            except Exception as e:
                history_fetch_error = e
                logger.warning(f"{stock_name}({code}) 历史日线获取失败: {e}")
                # 美股容错：若历史拉取失败，尝试用已成功的实时行情快照兜底写入
                if is_us_stock_code(code) and df is None:
                    df, source_name = self._build_us_realtime_snapshot_df(code)
                    if df is not None and not df.empty:
                        logger.warning(
                            f"{stock_name}({code}) 历史失败但实时成功，使用实时快照入库继续流程 "
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

    def _build_us_realtime_snapshot_df(self, code: str) -> Tuple[Optional[pd.DataFrame], str]:
        quote = self.fetcher_manager.get_realtime_quote(code)
        if not quote or not getattr(quote, "has_basic_data", lambda: False)():
            return None, ""

        today = date.today().isoformat()
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
            "date": today,
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
                "failure_reasons": [],
            }

            # Step 1: 获取实时行情（量比、换手率等）- 使用统一入口，自动故障切换
            realtime_quote = None
            try:
                realtime_quote = self.fetcher_manager.get_realtime_quote(code)
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
                logger.info(f"{stock_name}({code}) 搜索服务不可用，跳过情报搜索")

            # Step 4.5: Social sentiment intelligence (US stocks only)
            if self.social_sentiment_service.is_available and is_us_stock_code(code):
                try:
                    social_context = self.social_sentiment_service.get_social_context(code)
                    if social_context:
                        logger.info(f"{stock_name}({code}) Social sentiment data retrieved")
                        if news_context:
                            news_context = news_context + "\n\n" + social_context
                        else:
                            news_context = social_context
                except Exception as e:
                    logger.warning(f"{stock_name}({code}) Social sentiment fetch failed: {e}")

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
            
            # Step 6: 增强上下文数据（添加实时行情、筹码、趋势分析结果、股票名称）
            enhanced_context = self._enhance_context(
                context, 
                realtime_quote, 
                chip_data,
                trend_result,
                stock_name,  # 传入股票名称
                fundamental_context,
                shares_outstanding=shares_outstanding,
            )
            multidim_blocks = self._build_multidim_blocks(
                code=code,
                context=enhanced_context,
                fundamental_context=fundamental_context,
                news_context=news_context,
                news_items=news_items,
                diagnostics=diagnostics,
                alpha_indicators={"rsi14": rsi, "sma20": sma20, "sma60": sma60},
                alpha_overview=alpha_overview,
                yfinance_fundamentals=yfinance_fundamentals,
                yfinance_quarterly_income=yfinance_quarterly_income,
                alpha_quarterly_income=alpha_quarterly_income,
                alpha_errors=alpha_errors + yfinance_errors,
            )
            enhanced_context.update(multidim_blocks)
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
        structured["fundamentals"] = enhanced_context.get("fundamentals", {})
        structured["earnings_analysis"] = enhanced_context.get("earnings_analysis", {})
        structured["sentiment_analysis"] = enhanced_context.get("sentiment_analysis", {})
        structured["data_quality"] = enhanced_context.get("data_quality", {})
        dashboard["structured_analysis"] = structured

        intel = dashboard.get("intelligence") if isinstance(dashboard.get("intelligence"), dict) else {}
        sentiment = enhanced_context.get("sentiment_analysis", {})
        if isinstance(sentiment, dict):
            intel.setdefault("sentiment_summary", sentiment.get("sentiment_summary"))
            intel.setdefault("company_sentiment", sentiment.get("company_sentiment"))
            intel.setdefault("industry_sentiment", sentiment.get("industry_sentiment"))
            intel.setdefault("regulatory_sentiment", sentiment.get("regulatory_sentiment"))
            intel.setdefault("overall_confidence", sentiment.get("overall_confidence"))
        dashboard["intelligence"] = intel
        result.dashboard = dashboard
    
    def _enhance_context(
        self,
        context: Dict[str, Any],
        realtime_quote,
        chip_data: Optional[ChipDistribution],
        trend_result: Optional[TrendAnalysisResult],
        stock_name: str = "",
        fundamental_context: Optional[Dict[str, Any]] = None,
        shares_outstanding: Optional[int] = None,
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
                computed_volume_ratio = self._compute_volume_ratio(context, realtime_quote)
                if computed_volume_ratio is not None:
                    volume_ratio = computed_volume_ratio
                elif volume_ratio is None:
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
            if isinstance(volume_ratio, (int, float)):
                volume_ratio_desc = self._describe_volume_ratio(float(volume_ratio))
            enhanced['realtime'] = {
                'name': getattr(realtime_quote, 'name', ''),
                'price': getattr(realtime_quote, 'price', None),
                'change_pct': getattr(realtime_quote, 'change_pct', None),
                'volume_ratio': volume_ratio,
                'volume_ratio_desc': volume_ratio_desc,
                'turnover_rate': turnover_rate,
                'pe_ratio': getattr(realtime_quote, 'pe_ratio', None),
                'pb_ratio': getattr(realtime_quote, 'pb_ratio', None),
                'total_mv': getattr(realtime_quote, 'total_mv', None),
                'circ_mv': getattr(realtime_quote, 'circ_mv', None),
                'change_60d': getattr(realtime_quote, 'change_60d', None),
                'source': getattr(getattr(realtime_quote, 'source', None), 'value', getattr(realtime_quote, 'source', None)),
                'snapshot_type': enhanced.get("session_type"),
                'market_timestamp': enhanced.get("market_timestamp"),
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

        # Issue #234: Override today with realtime OHLC + trend MA for intraday analysis
        # Guard: trend_result.ma5 > 0 ensures MA calculation succeeded (data sufficient)
        if realtime_quote and trend_result and trend_result.ma5 > 0:
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
        report_generated_at = datetime.now(timezone.utc).isoformat()
        market_session_date = context.get("date") or market_now.date().isoformat()
        has_realtime_price = (
            realtime_quote is not None
            and getattr(realtime_quote, "price", None) is not None
        )
        market = get_market_for_stock(code)
        is_open = is_market_open(market, market_now.date()) if market else False
        session_type = "intraday_snapshot" if (has_realtime_price and is_open) else "last_completed_session"
        return {
            "market_timezone": market_tz_name,
            "market_timestamp": market_now.isoformat(),
            "market_session_date": market_session_date,
            "news_published_at": None,
            "report_generated_at": report_generated_at,
            "session_type": session_type,
        }

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

    def _compute_volume_ratio(self, context: Dict[str, Any], realtime_quote: Any) -> Optional[float]:
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
        yfinance_quarterly_income: Optional[List[Dict[str, Any]]],
        alpha_quarterly_income: Optional[List[Dict[str, Any]]],
        alpha_errors: List[str],
    ) -> Dict[str, Any]:
        technicals = self._build_technicals_block(code, alpha_indicators)
        fundamentals = self._build_fundamentals_block(
            fundamental_context,
            alpha_overview=alpha_overview,
            yfinance_fundamentals=yfinance_fundamentals,
        )
        earnings_analysis = self._build_earnings_analysis_block(
            fundamental_context,
            yfinance_quarterly_income=yfinance_quarterly_income,
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
            alpha_errors=alpha_errors,
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

    def _build_technicals_block(
        self,
        code: str,
        alpha_indicators: Dict[str, Optional[float]],
    ) -> Dict[str, Dict[str, Any]]:
        bars = self.db.get_latest_data(code, days=300) or []
        if not bars:
            return {
                k: {"value": None, "status": "data_unavailable", "source": "local_from_ohlcv"}
                for k in ("ma5", "ma10", "ma20", "ma60", "rsi14", "macd", "macd_signal", "macd_hist")
            }

        rows: List[Dict[str, Any]] = []
        for bar in reversed(bars):
            rows.append(
                {
                    "date": getattr(bar, "date", None),
                    "close": getattr(bar, "close", None),
                    "volume": getattr(bar, "volume", None),
                }
            )
        df = pd.DataFrame(rows)
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"]).copy()
        if df.empty:
            return {
                k: {"value": None, "status": "data_unavailable", "source": "local_from_ohlcv"}
                for k in ("ma5", "ma10", "ma20", "ma60", "rsi14", "macd", "macd_signal", "macd_hist")
            }

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

        technicals: Dict[str, Dict[str, Any]] = {}
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
                "source": "local_from_ohlcv",
            }

        if technicals["ma20"]["status"] != "ok" and alpha_indicators.get("sma20") is not None:
            technicals["ma20"] = {
                "value": round(float(alpha_indicators["sma20"]), 4),
                "status": "ok",
                "source": "alpha_vantage_fallback",
            }
        if technicals["ma60"]["status"] != "ok" and alpha_indicators.get("sma60") is not None:
            technicals["ma60"] = {
                "value": round(float(alpha_indicators["sma60"]), 4),
                "status": "ok",
                "source": "alpha_vantage_fallback",
            }
        if technicals["rsi14"]["status"] != "ok" and alpha_indicators.get("rsi14") is not None:
            technicals["rsi14"] = {
                "value": round(float(alpha_indicators["rsi14"]), 4),
                "status": "ok",
                "source": "alpha_vantage_fallback",
            }
        return technicals

    @staticmethod
    def _build_fundamentals_block(
        fundamental_context: Optional[Dict[str, Any]],
        alpha_overview: Optional[Dict[str, Any]] = None,
        yfinance_fundamentals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = ((fundamental_context or {}).get("valuation") or {}).get("data", {})
        raw = payload if isinstance(payload, dict) else {}
        alpha = alpha_overview if isinstance(alpha_overview, dict) else {}
        yf_data = yfinance_fundamentals if isinstance(yfinance_fundamentals, dict) else {}
        field_sources: Dict[str, str] = {}

        def pick(field_name: str, *keys: str) -> Any:
            for key in keys:
                val = yf_data.get(key)
                if val not in (None, "", "N/A", 0):
                    field_sources[field_name] = "yfinance"
                    return val
            for key in keys:
                val = raw.get(key)
                if val not in (None, "", "N/A", 0):
                    field_sources[field_name] = "fundamental_context"
                    return val
            for key in keys:
                val = alpha.get(key)
                if val not in (None, "", "N/A", 0):
                    field_sources[field_name] = "alpha_vantage_overview"
                    return val
            return None

        normalized = {
            "marketCap": pick("marketCap", "marketCap", "total_market_cap", "market_cap", "MarketCapitalization"),
            "trailingPE": pick("trailingPE", "trailingPE", "pe_ttm", "pe", "PERatio"),
            "forwardPE": pick("forwardPE", "forwardPE", "forward_pe", "ForwardPE"),
            "totalRevenue": pick("totalRevenue", "totalRevenue", "total_revenue", "revenue", "RevenueTTM"),
            "revenueGrowth": pick("revenueGrowth", "revenueGrowth", "revenue_growth", "QuarterlyRevenueGrowthYOY"),
            "grossMargins": pick("grossMargins", "grossMargins", "gross_margin", "GrossMargin", "GrossProfitTTM"),
            "operatingMargins": pick("operatingMargins", "operatingMargins", "operating_margin", "OperatingMarginTTM"),
            "freeCashflow": pick("freeCashflow", "freeCashflow", "free_cashflow"),
            "operatingCashflow": pick("operatingCashflow", "operatingCashflow", "operating_cashflow"),
            "debtToEquity": pick("debtToEquity", "debtToEquity", "debt_to_equity"),
            "currentRatio": pick("currentRatio", "currentRatio", "current_ratio"),
            "returnOnEquity": pick("returnOnEquity", "returnOnEquity", "roe", "ReturnOnEquityTTM"),
            "returnOnAssets": pick("returnOnAssets", "returnOnAssets", "roa", "ReturnOnAssetsTTM"),
        }
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
            "source": "yfinance_overview_fallback_chain" if field_sources else "fundamental_pipeline",
        }

    @staticmethod
    def _build_earnings_analysis_block(
        fundamental_context: Optional[Dict[str, Any]],
        yfinance_quarterly_income: Optional[List[Dict[str, Any]]] = None,
        alpha_quarterly_income: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        earnings_data = ((fundamental_context or {}).get("earnings") or {}).get("data", {})
        yfinance_income = yfinance_quarterly_income if isinstance(yfinance_quarterly_income, list) else []
        alpha_income = alpha_quarterly_income if isinstance(alpha_quarterly_income, list) else []
        if not isinstance(earnings_data, dict) and not yfinance_income and not alpha_income:
            return {
                "quarterly_series": [],
                "derived_metrics": {},
                "summary_flags": ["earnings_data_unavailable"],
                "narrative_insights": ["财报数据不足，无法形成完整趋势判断"],
                "field_sources": {},
                "status": "partial",
            }
        field_sources: Dict[str, str] = {}
        quarterly = (earnings_data.get("quarterly_series", []) if isinstance(earnings_data, dict) else [])
        if quarterly:
            field_sources["quarterly_series"] = "fundamental_context"
        elif yfinance_income:
            quarterly = yfinance_income
            field_sources["quarterly_series"] = "yfinance"
        elif alpha_income:
            quarterly = alpha_income
            field_sources["quarterly_series"] = "alpha_vantage_income_statement"
        if not isinstance(quarterly, list):
            quarterly = []
        quarterly = quarterly[:4]
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
        if len(quarterly) >= 4:
            q0, q3 = quarterly[0], quarterly[3]
            trend["yoy_revenue_growth"] = _delta(q0.get("revenue"), q3.get("revenue"))
            trend["yoy_net_income_change"] = _delta(q0.get("net_income"), q3.get("net_income"))

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
            if self.social_sentiment_service.is_available and is_us_stock_code(code):
                try:
                    social_context = self.social_sentiment_service.get_social_context(code)
                    if social_context:
                        existing = initial_context.get("news_context")
                        if existing:
                            initial_context["news_context"] = existing + "\n\n" + social_context
                        else:
                            initial_context["news_context"] = social_context
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
                if single_stock_notify and self.notifier.is_available():
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
                        
                        if self.notifier.send(report_content, email_stock_codes=[code]):
                            logger.info(f"[{code}] 单股推送成功")
                        else:
                            logger.warning(f"[{code}] 单股推送失败")
                    except Exception as e:
                        logger.error(f"[{code}] 单股推送异常: {e}")
            
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
