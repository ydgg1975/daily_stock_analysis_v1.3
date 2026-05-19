# -*- coding: utf-8 -*-

"""

===================================

Aguwatchlistguzhinenganalysisxitong - hexinanalysisliushuixian

===================================



역할(chinese removed)?
1. guanlizhenggeanalysis흐름

2. xietiaoshujuhuoqu?갷unchu?걌ousuo?갽enxi?걎ongzhidengmokuai

3. shixianbingfakongzhiheyichangchuli

4. tigongstockanalysisdehexingongneng

"""






















import logging

import threading

import time

import uuid

from collections import defaultdict

from concurrent.futures import ThreadPoolExecutor, as_completed

from datetime import date, datetime, timedelta, timezone

from typing import List, Dict, Any, Optional, Tuple, Callable



import pandas as pd



from src.config import FUNDAMENTAL_STAGE_TIMEOUT_SECONDS_DEFAULT, get_config, Config

from src.storage import get_db

from data_provider import DataFetcherManager

from data_provider.base import normalize_stock_code

from data_provider.realtime_types import ChipDistribution

from src.analyzer import (

    GeminiAnalyzer,

    AnalysisResult,

    fill_chip_structure_if_needed,

    fill_price_position_if_needed,

    stabilize_decision_with_structure,

)

from src.data.stock_mapping import STOCK_NAME_MAP

from src.notification import NotificationService, NotificationChannel

from src.report_language import (

    get_unknown_text,

    infer_decision_type_from_advice,

    localize_confidence_level,

    localize_operation_advice,

    localize_trend_prediction,

    normalize_report_language,

)

from src.search_service import SearchService

from src.services.social_sentiment_service import SocialSentimentService

from src.enums import ReportType

from src.stock_analyzer import StockTrendAnalyzer, TrendAnalysisResult

from src.core.trading_calendar import (

    get_effective_trading_date,

    get_market_for_stock,

    get_market_now,

    is_market_open,

)

from data_provider.us_index_mapping import is_us_stock_code

from bot.models import BotMessage





logger = logging.getLogger(__name__)



# fangyuxing guard(chinese removed)쉊angshiliraoguo __init__(chinese removed)늭utestzhong __new__(chinese removed)뎖ouzaoshi(chinese removed)?
# double-check chushihua _single_stock_notify_lock rengranxianchenganquan??
_SINGLE_STOCK_NOTIFY_LOCK_INIT_GUARD = threading.Lock()





class StockAnalysisPipeline:

    """

    stockanalysiszhu흐름diaoduqi

    

    역할(chinese removed)?
    1. guanlizhenggeanalysis흐름

    2. xietiaoshujuhuoqu?갷unchu?걌ousuo?갽enxi?걎ongzhidengmokuai

    3. shixianbingfakongzhiheyichangchuli

    """














    

    def __init__(

        self,

        config: Optional[Config] = None,

        max_workers: Optional[int] = None,

        source_message: Optional[BotMessage] = None,

        query_id: Optional[str] = None,

        query_source: Optional[str] = None,

        save_context_snapshot: Optional[bool] = None,

        progress_callback: Optional[Callable[[int, str], None]] = None,

        analysis_skills: Optional[List[str]] = None,

    ):

        """

        초기화diaoduqi

        

        Args:

            config: configduixiang(chinese removed)늟exuan(chinese removed)똫oren사용quanjuconfig(chinese removed)?
            max_workers: zuidabingfaxianchengshu(chinese removed)늟exuan(chinese removed)똫orencongconfigduqu(chinese removed)?
        """











        self.config = config or get_config()

        self.max_workers = max_workers or self.config.max_workers

        self.source_message = source_message

        self.query_id = query_id

        self.query_source = self._resolve_query_source(query_source)

        self.save_context_snapshot = (

            self.config.save_context_snapshot if save_context_snapshot is None else save_context_snapshot

        )

        self.progress_callback = progress_callback

        self.analysis_skills = list(analysis_skills) if analysis_skills is not None else None

        

        # chushihuagemokuai

        self.db = get_db()

        self.fetcher_manager = DataFetcherManager()

        # buzaidanduchuangjian akshare_fetcher(chinese removed)똳ongyishiyong fetcher_manager huoquzengqiangshuju

        self.trend_analyzer = StockTrendAnalyzer()  # jishuanalysisqi

        self.analyzer = GeminiAnalyzer(config=self.config, skills=self.analysis_skills)

        self.notifier = NotificationService(source_message=source_message)

        self._single_stock_notify_lock = threading.Lock()

        

        # chushihuasousuofuwu(chinese removed)늟exuan(chinese removed)똠hushihuashibaibuyingzuduanzhuanalysisliucheng(chinese removed)?
        try:

            self.search_service = SearchService(

                bocha_keys=self.config.bocha_api_keys,

                tavily_keys=self.config.tavily_api_keys,

                anspire_keys=self.config.anspire_api_keys,

                brave_keys=self.config.brave_api_keys,

                serpapi_keys=self.config.serpapi_keys,

                minimax_keys=self.config.minimax_api_keys,

                searxng_base_urls=self.config.searxng_base_urls,

                searxng_public_instances_enabled=self.config.searxng_public_instances_enabled,

                news_max_age_days=self.config.news_max_age_days,

                news_strategy_profile=getattr(self.config, "news_strategy_profile", "short"),

            )

        except Exception as exc:

            logger.warning("sousuofuwuchushihuashibai(chinese removed)똨iangyiwusousuomoshiyunxing: %s", exc, exc_info=True)

            self.search_service = None

        

        logger.info(f"diaoduqichushihuawancheng(chinese removed)똺uidabingfashu: {self.max_workers}")

        logger.info("Technical analysis engine enabled (moving averages / trend / volume-price indicators)")
        # dayinshishixingqing/choumaconfigzhuangtai

        if self.config.enable_realtime_quote:

            logger.info(f"shishixingqingyiqiyong (youxianji: {self.config.realtime_source_priority})")

        else:

            logger.info("shishixingqingyijinyong(chinese removed)똨iangshiyonglishishoupanjia")

        if self.config.enable_chip_distribution:

            logger.info("choumafenbuanalysisyiqiyong")

        else:

            logger.info("choumafenbuanalysisyijinyong")

        if self.search_service is None:

            logger.warning("Search service is disabled because initialization failed or dependencies are missing")
        elif self.search_service.is_available:

            logger.info("sousuofuwuyiqiyong")

        else:

            logger.warning("Search service is disabled because no search provider is configured")


        # chushihuashejiaoyuqingfuwu(chinese removed)늞inmeigu(chinese removed)똩exuan(chinese removed)?
        try:

            self.social_sentiment_service = SocialSentimentService(

                api_key=self.config.social_sentiment_api_key,

                api_url=self.config.social_sentiment_api_url,

            )

            if self.social_sentiment_service.is_available:

                logger.info("Social sentiment service enabled (Reddit/X/Polymarket, US stocks only)")

        except Exception as exc:

            logger.warning(

                "shejiaoyuqingfuwuchushihuashibai(chinese removed)똨iangtiaoguoyuqinganalysis: %s",

                exc,

                exc_info=True,

            )

            self.social_sentiment_service = None



    def _emit_progress(self, progress: int, message: str) -> None:

        """Best-effort bridge from pipeline stages to task SSE progress."""

        callback = getattr(self, "progress_callback", None)

        if callback is None:

            return

        try:

            callback(progress, message)

        except Exception as exc:

            query_id = getattr(self, "query_id", None)

            logger.warning(

                "[pipeline] progress callback failed: %s (progress=%s, message=%r, query_id=%s)",

                exc,

                progress,

                message,

                query_id,

                extra={

                    "progress": progress,

                    "progress_message": message,

                    "query_id": query_id,

                },

            )



    def fetch_and_save_stock_data(

        self, 

        code: str,

        force_refresh: bool = False,

        current_time: Optional[datetime] = None,

    ) -> Tuple[bool, Optional[str]]:

        """

        huoqubingsavedanzhistockshuju

        

        duandianxuchuanluoji(chinese removed)?
        1. jianchashujukushifouyiyouzuixinkefuyongjiaoyirishuju

        2. ruguoyouqiebuqiangzhirefresh(chinese removed)똺etiaoguowangluoqingqiu

        3. fouzecongshujuyuanhuoqubingsave

        

        Args:

            code: stockdaima

            force_refresh: shifouqiangzhirefresh(chinese removed)늜ulvebendihuancun(chinese removed)?
            current_time: benlunyunxingdongjiedecankaoshijian(chinese removed)똹ongyutongyiduandianxuchuanmubiaojiaoyiripanduan

            

        Returns:

            Tuple[shifouchenggong, cuowuxinxi]

        """

        stock_name = code

        try:

            # shouxianhuoqustockmingcheng

            stock_name = self.fetcher_manager.get_stock_name(code, allow_realtime=False)



            target_date = self._resolve_resume_target_date(

                code, current_time=current_time

            )



            # duandianxuchuanjiancha(chinese removed)쉜uguozuixinkefuyongjiaoyirideshujuyicunzai(chinese removed)똺etiaoguo

            if not force_refresh and self.db.has_today_data(code, target_date):

                logger.info(

                    f"{stock_name}({code}) {target_date} data already exists; skipping fetch for resume"
                )

                return True, None



            # congshujuyuanhuoqushuju

            logger.info(f"{stock_name}({code}) kaishicongshujuyuanhuoqushuju...")

            df, source_name = self.fetcher_manager.get_daily_data(code, days=30)



            if df is None or df.empty:

                return False, "huoqushujuweikong"



            # savedaoshujuku

            saved_count = self.db.save_daily_data(df, code, source_name)

            logger.info(f"{stock_name}({code}) data saved successfully (source: {source_name}, added: {saved_count})")


            return True, None



        except Exception as e:

            error_msg = f"huoqu/saveshujushibai: {str(e)}"

            logger.error(f"{stock_name}({code}) {error_msg}")

            return False, error_msg

    

    def analyze_stock(self, code: str, report_type: ReportType, query_id: str) -> Optional[AnalysisResult]:

        """

        analysisdanzhistock(chinese removed)늷engqiangban(chinese removed)쉎anliangbi?갿uanshoulv?갷houmaanalysis?갺uoweiduqingbao(chinese removed)?
        

        흐름(chinese removed)?
        1. huoqushishixingqing(chinese removed)늢iangbi?갿uanshoulv(chinese removed)? tongguo DataFetcherManager zidongguzhang전환

        2. huoquchoumafenbu - tongguo DataFetcherManager dairongduanbaohu

        3. jinxingqushianalysis(chinese removed)늞iyujiaoyilinian(chinese removed)?
        4. duoweiduqingbaosousuo(chinese removed)늷uixinxiaoxi+fengxianpaicha+yejiyuqi(chinese removed)?
        5. congshujukuhuoquanalysisshangxiawen

        6. 호출 AI jinxingzongheanalysis

        

        Args:

            query_id: chaxunlianluguanlian id

            code: stockdaima

            report_type: baogaoleixing

            

        Returns:

            AnalysisResult huo None(chinese removed)늭uguoanalysisshibai(chinese removed)?
        """
































        stock_name = code

        try:

            self._emit_progress(18, f"{code}(chinese removed)쉦hengzaihuoququoteyuchoumashuju")

            # huoqustockmingcheng(chinese removed)늵ianzouqingliangmingchenglujing(chinese removed)똦ouxuruo realtime_quote you name zaifugai(chinese removed)?
            stock_name = self.fetcher_manager.get_stock_name(code, allow_realtime=False)



            # Step 1: huoqushishixingqing(chinese removed)늢iangbi?갿uanshoulvdeng(chinese removed)? shiyongtongyirukou(chinese removed)똺idongguzhangqiehuan

            realtime_quote = None

            try:

                if self.config.enable_realtime_quote:

                    realtime_quote = self.fetcher_manager.get_realtime_quote(code, log_final_failure=False)

                    if realtime_quote:

                        # shiyongshishixingqingfanhuidezhenshistockmingcheng

                        if realtime_quote.name:

                            stock_name = realtime_quote.name

                        # jianrongbutongshujuyuandeziduan(chinese removed)늶ouxieshujuyuankenengmeiyou volume_ratio(chinese removed)?
                        volume_ratio = getattr(realtime_quote, 'volume_ratio', None)

                        turnover_rate = getattr(realtime_quote, 'turnover_rate', None)

                        logger.info(f"{stock_name}({code}) shishixingqing: jiage={realtime_quote.price}, "

                                  f"liangbi={volume_ratio}, huanshoulv={turnover_rate}% "

                                  f"(laiyuan: {realtime_quote.source.value if hasattr(realtime_quote, 'source') else 'unknown'})")

                    else:

                        logger.warning(f"{stock_name}({code}) suoyoushishixinginputjuyuanjunbukeyong(chinese removed)똹ijiangjiweilishishoupanjiajixuanalysis")

                else:

                    logger.info(f"{stock_name}({code}) shishixingqingyijinyong(chinese removed)똲hiyonglishishoupanjiajixuanalysis")

            except Exception as e:

                logger.warning(f"{stock_name}({code}) shishixingqinglianluyichang(chinese removed)똹ijiangjiweilishishoupanjiajixuanalysis: {e}")



            # ruguohaishimeiyoumingcheng(chinese removed)똲hiyongdaimazuoweimingcheng

            if not stock_name:

                stock_name = f'stock{code}'



            # Step 2: huoquchoumafenbu - shiyongtongyirukou(chinese removed)똡airongduanbaohu

            chip_data = None

            try:

                chip_data = self.fetcher_manager.get_chip_distribution(code)

                if chip_data:

                    logger.info(f"{stock_name}({code}) choumafenbu: huolibili={chip_data.profit_ratio:.1%}, "

                              f"90%jizhongdu={chip_data.concentration_90:.2%}")

                else:

                    logger.debug(f"{stock_name}({code}) choumafenbuhuoqushibaihuoyijinyong")

            except Exception as e:

                logger.warning(f"{stock_name}({code}) huoquchoumafenbushibai: {e}")



            # If agent mode is explicitly enabled, or specific agent skills are configured, use the Agent analysis pipeline.

            # NOTE: use config.agent_mode (explicit opt-in) instead of

            # config.is_agent_available() so that users who only configured an

            # API Key for the traditional analysis path are not silently

            # switched to Agent mode (which is slower and more expensive).

            use_agent = getattr(self.config, 'agent_mode', False)

            if not use_agent:

                if self.analysis_skills:

                    use_agent = True

                    logger.info(f"{stock_name}({code}) Auto-enabled agent mode due to request skills: {self.analysis_skills}")

            if not use_agent:

                # Auto-enable agent mode when specific skills are configured (e.g., scheduled task with strategy)

                configured_skills = getattr(self.config, 'agent_skills', [])

                if configured_skills and configured_skills != ['all']:

                    use_agent = True

                    logger.info(f"{stock_name}({code}) Auto-enabled agent mode due to configured skills: {configured_skills}")



            self._emit_progress(32, f"{stock_name}(chinese removed)쉦hengzaijuhejibenmianyuqushishuju")



            # Step 2.5: jibenmiannenglijuhe(chinese removed)늯ongyirukou(chinese removed)똹ichangjiangji(chinese removed)?
            # - shibaishifanhui partial/failed(chinese removed)똟uyingxiangjiyoujishumian/xinwenlianlu

            # - closekaiguanshirengfanhui not_supported jiegou

            fundamental_context = None

            try:

                fundamental_context = self.fetcher_manager.get_fundamental_context(

                    code,

                    budget_seconds=getattr(

                        self.config,

                        'fundamental_stage_timeout_seconds',

                        FUNDAMENTAL_STAGE_TIMEOUT_SECONDS_DEFAULT,

                    ),

                )

            except Exception as e:

                logger.warning(f"{stock_name}({code}) jibenmianjuheshibai: {e}")

                fundamental_context = self.fetcher_manager.build_failed_fundamental_context(code, str(e))



            fundamental_context = self._attach_belong_boards_to_fundamental_context(

                code,

                fundamental_context,

            )



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

                logger.debug(f"{stock_name}({code}) jibenmiankuaizhaoxierushibai: {e}")



            # Step 3: qushianalysis(chinese removed)늞iyujiaoyilinian(chinese removed)됤?zai Agent fenzhizhiqianzhixing(chinese removed)똤ongliangtiaolujinggongyong

            trend_result: Optional[TrendAnalysisResult] = None

            try:

                from src.services.history_loader import get_frozen_target_date

                _mkt = get_market_for_stock(normalize_stock_code(code))

                frozen = get_frozen_target_date()

                end_date = frozen if frozen else get_market_now(_mkt).date()

                start_date = end_date - timedelta(days=89)  # ~60 trading days for MA60

                historical_bars = self.db.get_data_range(code, start_date, end_date)

                if historical_bars:

                    df = pd.DataFrame([bar.to_dict() for bar in historical_bars])

                    # Issue #234: Augment with realtime for intraday MA calculation

                    if self.config.enable_realtime_quote and realtime_quote:

                        df = self._augment_historical_with_realtime(df, realtime_quote, code)

                    trend_result = self.trend_analyzer.analyze(df, code)

                    logger.info(f"{stock_name}({code}) qushianalysis: {trend_result.trend_status.value}, "

                              f"mairuxinhao={trend_result.buy_signal.value}, pingfen={trend_result.signal_score}")

            except Exception as e:

                logger.warning(f"{stock_name}({code}) qushianalysisshibai: {e}", exc_info=True)



            if use_agent:

                logger.info(f"{stock_name}({code}) qiyong Agent moshijinxinganalysis")

                self._emit_progress(58, f"{stock_name}(chinese removed)쉦hengzaiqiehuan Agent analysislianlu")

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



            # Step 4: duoweiduqingbaosousuo(chinese removed)늷uixinxiaoxi+fengxianpaicha+yejiyuqi(chinese removed)?
            news_context = None

            self._emit_progress(46, f"{stock_name}(chinese removed)쉦hengzaijiansuoxinwenyuyuqing")

            if self.search_service is not None and self.search_service.is_available:

                logger.info(f"{stock_name}({code}) kaishiduoweiduqingbaosousuo...")



                # shiyongduoweidusousuo(chinese removed)늷uiduo5cisousuo(chinese removed)?
                intel_results = self.search_service.search_comprehensive_intel(

                    stock_code=code,

                    stock_name=stock_name,

                    max_searches=5

                )



                # geshihuaqingbaobaogao

                if intel_results:

                    news_context = self.search_service.format_intel_report(intel_results, stock_name)

                    total_results = sum(

                        len(r.results) for r in intel_results.values() if r.success

                    )

                    logger.info(f"{stock_name}({code}) qingbaosousuowancheng: gong {total_results} tiaojieguo")

                    logger.debug(f"{stock_name}({code}) qingbaosousuojieguo:\n{news_context}")



                    # savexinwenqingbaodaoshujuku(chinese removed)늶ongyuhouxufupanyuchaxun(chinese removed)?
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

                        logger.warning(f"{stock_name}({code}) savexinwenqingbaoshibai: {e}")

            else:

                logger.info(f"{stock_name}({code}) sousuofuwubukeyong(chinese removed)똳iaoguoqingbaosousuo")



            # Step 4.5: Social sentiment intelligence (US stocks only)

            if self.social_sentiment_service is not None and self.social_sentiment_service.is_available and is_us_stock_code(code):

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



            # Step 5: huoquanalysisshangxiawen(chinese removed)늞ishumianshuju(chinese removed)?
            self._emit_progress(58, f"{stock_name}(chinese removed)쉦hengzaizhenglianalysisshangxiawen")

            context = self.db.get_analysis_context(code)



            if context is None:

                logger.warning(f"{stock_name}({code}) wufahuoqulishiquoteshuju(chinese removed)똨iangjinjiyuxinwenheshishixingqinganalysis")

                _mkt_date = get_market_now(

                    get_market_for_stock(normalize_stock_code(code))

                ).date()

                context = {

                    'code': code,

                    'stock_name': stock_name,

                    'date': _mkt_date.isoformat(),

                    'data_missing': True,

                    'today': {},

                    'yesterday': {}

                }

            

            # Step 6: zengqiangshangxiawenshuju(chinese removed)늯ianjiashishixingqing?갷houma?걉ushianalysisjieguo?갾upiaomingcheng(chinese removed)?
            enhanced_context = self._enhance_context(

                context, 

                realtime_quote, 

                chip_data,

                trend_result,

                stock_name,  # chuanrustockmingcheng

                fundamental_context,

            )

            

            # Step 7: diaoyong AI analysis(chinese removed)늓huanruzengqiangdeshangxiawenhexinwen(chinese removed)?
            llm_progress_state = {"last_progress": 64}



            def _on_llm_stream(chars_received: int) -> None:

                dynamic_progress = min(92, 64 + min(chars_received // 80, 28))

                if dynamic_progress <= llm_progress_state["last_progress"]:

                    return

                llm_progress_state["last_progress"] = dynamic_progress

                self._emit_progress(

                    dynamic_progress,

                    f"{stock_name}: LLM is generating the analysis result ({chars_received} chars received)",
                )



            self._emit_progress(64, f"{stock_name}(chinese removed)쉦hengzaiqingqiu LLM shengchengbaogao")

            result = self.analyzer.analyze(

                enhanced_context,

                news_context=news_context,

                progress_callback=self._emit_progress,

                stream_progress_callback=_on_llm_stream,

            )



            # Step 7.5: tianchonganalysisshidejiagexinxidao result

            if result:

                self._emit_progress(94, f"{stock_name}(chinese removed)쉦hengzaijiaoyanbingzhenglianalysisjieguo")

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

                stabilize_decision_with_structure(result, trend_result, fundamental_context)



            # Step 8: saveanalysislishirecord

            if result and result.success:

                try:

                    self._emit_progress(97, f"{stock_name}(chinese removed)쉦hengzaisaveanalysisbaogao")

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

                    logger.warning(f"{stock_name}({code}) saveanalysislishishibai: {e}")



            return result



        except Exception as e:

            logger.error(f"{stock_name}({code}) analysisshibai: {e}")

            logger.exception(f"{stock_name}({code}) xiangxicuowuxinxi:")

            return None

    

    def _enhance_context(

        self,

        context: Dict[str, Any],

        realtime_quote,

        chip_data: Optional[ChipDistribution],

        trend_result: Optional[TrendAnalysisResult],

        stock_name: str = "",

        fundamental_context: Optional[Dict[str, Any]] = None

    ) -> Dict[str, Any]:

        """

        zengqianganalysisshangxiawen

        

        jiangshishixingqing?갷houmafenbu?걉ushianalysisjieguo?갾upiaomingchengadddaoshangxiawenzhong

        

        Args:

            context: yuanshishangxiawen

            realtime_quote: shishixinginputju(chinese removed)늈nifiedRealtimeQuote huo None(chinese removed)?
            chip_data: choumafenbushuju

            trend_result: qushianalysisjieguo

            stock_name: stockmingcheng

            

        Returns:

            zengqianghoudeshangxiawen

        """

        enhanced = context.copy()

        enhanced["report_language"] = normalize_report_language(getattr(self.config, "report_language", "zh"))

        

        # addstockmingcheng

        if stock_name:

            enhanced['stock_name'] = stock_name

        elif realtime_quote and getattr(realtime_quote, 'name', None):

            enhanced['stock_name'] = realtime_quote.name



        # jiangyunxingshisousuochuangkoutouchuangei analyzer(chinese removed)똟imianyuquanjuconfigchongxinduquchanshengchuangkoubuyizhi

        enhanced['news_window_days'] = getattr(self.search_service, "news_window_days", 3)

        

        # addshishixingqing(chinese removed)늞ianrongbutongshujuyuandeziduanchayi(chinese removed)?
        if realtime_quote:

            # shiyong getattr anquanhuoquziduan(chinese removed)똰ueshiziduanfanhui None huomorenzhi

            volume_ratio = getattr(realtime_quote, 'volume_ratio', None)

            enhanced['realtime'] = {

                'name': getattr(realtime_quote, 'name', ''),

                'price': getattr(realtime_quote, 'price', None),

                'change_pct': getattr(realtime_quote, 'change_pct', None),

                'volume_ratio': volume_ratio,

                'volume_ratio_desc': self._describe_volume_ratio(volume_ratio) if volume_ratio else 'wushuju',

                'turnover_rate': getattr(realtime_quote, 'turnover_rate', None),

                'pe_ratio': getattr(realtime_quote, 'pe_ratio', None),

                'pb_ratio': getattr(realtime_quote, 'pb_ratio', None),

                'total_mv': getattr(realtime_quote, 'total_mv', None),

                'circ_mv': getattr(realtime_quote, 'circ_mv', None),

                'change_60d': getattr(realtime_quote, 'change_60d', None),

                'source': getattr(realtime_quote, 'source', None),

            }

            # yichu None zhiyijianshaoshangxiawendaxiao

            enhanced['realtime'] = {k: v for k, v in enhanced['realtime'].items() if v is not None}

        

        # addchoumafenbu

        if chip_data:

            current_price = getattr(realtime_quote, 'price', 0) if realtime_quote else 0

            enhanced['chip'] = {

                'profit_ratio': chip_data.profit_ratio,

                'avg_cost': chip_data.avg_cost,

                'concentration_90': chip_data.concentration_90,

                'concentration_70': chip_data.concentration_70,

                'chip_status': chip_data.get_chip_status(current_price or 0),

            }

        

        # addqushianalysisjieguo

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

                enhanced['date'] = get_market_now(

                    get_market_for_stock(normalize_stock_code(enhanced.get('code', '')))

                ).date().isoformat()

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



    def _attach_belong_boards_to_fundamental_context(

        self,

        code: str,

        fundamental_context: Optional[Dict[str, Any]],

    ) -> Dict[str, Any]:

        """

        Attach A-share board membership as a top-level supplemental field.



        Keep this as a shallow copy so cached fundamental contexts are not

        mutated in place after retrieval.

        """

        if isinstance(fundamental_context, dict):

            enriched_context = dict(fundamental_context)

        else:

            enriched_context = self.fetcher_manager.build_failed_fundamental_context(

                code,

                "invalid fundamental context",

            )



        existing_boards = enriched_context.get("belong_boards")

        if isinstance(existing_boards, list):

            enriched_context["belong_boards"] = list(existing_boards)

            return enriched_context



        boards_block = enriched_context.get("boards")

        boards_status = boards_block.get("status") if isinstance(boards_block, dict) else None

        coverage = enriched_context.get("coverage")

        boards_coverage = coverage.get("boards") if isinstance(coverage, dict) else None

        market = enriched_context.get("market")

        if not isinstance(market, str) or not market.strip():

            market = get_market_for_stock(normalize_stock_code(code))



        if (

            market != "cn"

            or boards_status == "not_supported"

            or boards_coverage == "not_supported"

        ):

            enriched_context["belong_boards"] = []

            return enriched_context



        boards: List[Dict[str, Any]] = []

        try:

            raw_boards = self.fetcher_manager.get_belong_boards(code)

            if isinstance(raw_boards, list):

                boards = raw_boards

        except Exception as e:

            logger.debug("%s attach belong_boards failed (fail-open): %s", code, e)



        enriched_context["belong_boards"] = boards

        return enriched_context



    def _ensure_agent_history(self, code: str, min_days: int = 240) -> None:

        """Ensure at least *min_days* of K-line history is in DB for agent tools."""

        from src.services.history_loader import get_frozen_target_date



        target = get_frozen_target_date()

        if target is None:

            target = self._resolve_resume_target_date(code)

        start = target - timedelta(days=int(min_days * 1.8))

        bars = self.db.get_data_range(code, start, target)

        if bars and len(bars) >= min(min_days, 200):

            logger.debug("[%s] Agent history: %d bars in DB, sufficient", code, len(bars))

            return

        try:

            df, source = self.fetcher_manager.get_daily_data(code, days=min_days)

            if df is not None and not df.empty:

                self.db.save_daily_data(df, code, source)

                logger.info("[%s] Prefetched %d rows of history for agent (source: %s)", code, len(df), source)

        except Exception as e:

            logger.warning("[%s] Agent history prefetch failed: %s", code, e)



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

        사용 Agent moshianalysisdanzhistock??
        """




        try:

            from src.agent.factory import build_agent_executor

            report_language = normalize_report_language(getattr(self.config, "report_language", "zh"))



            requested_skills = (

                self.analysis_skills

                if self.analysis_skills is not None

                else (getattr(self.config, 'agent_skills', None) or None)

            )

            # Build executor from shared factory (ToolRegistry and SkillManager prototype are cached)

            executor = build_agent_executor(self.config, requested_skills)



            # Build initial context to avoid redundant tool calls

            initial_context = {

                "stock_code": code,

                "stock_name": stock_name,

                "report_type": report_type.value,

                "report_language": report_language,

                "fundamental_context": fundamental_context,

            }

            if self.analysis_skills is not None:

                initial_context["skills"] = self.analysis_skills

            

            if realtime_quote:

                initial_context["realtime_quote"] = self._safe_to_dict(realtime_quote)

            if chip_data:

                initial_context["chip_distribution"] = self._safe_to_dict(chip_data)

            if trend_result:

                initial_context["trend_result"] = self._safe_to_dict(trend_result)



            # Agent path: inject social sentiment as news_context so both

            # executor (_build_user_message) and orchestrator (ctx.set_data)

            # can consume it through the existing news_context channel

            if self.social_sentiment_service is not None and self.social_sentiment_service.is_available and is_us_stock_code(code):

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



            # Issue #1066: ensure deep history is in DB before agent tools run

            self._ensure_agent_history(code)



            # yunxing Agent

            if report_language == "en":

                message = f"Analyze stock {code} ({stock_name}) and return the full decision dashboard JSON in English."

            else:

                message = f"분석 종목 {code} ({stock_name})의 의사결정 대시보드 리포트를 생성해 주세요."
            agent_result = executor.run(message, context=initial_context)



            # zhuanhuanwei AnalysisResult

            result = self._agent_result_to_analysis_result(

                agent_result,

                code,

                stock_name,

                report_type,

                query_id,

                trend_result=trend_result,

            )

            if result:

                result.query_id = query_id

            # Agent weak integrity: placeholder fill only, no LLM retry

            if result and getattr(self.config, "report_integrity_enabled", False):

                from src.analyzer import check_content_integrity, apply_placeholder_fill



                pass_integrity, missing = check_content_integrity(result)

                if not pass_integrity:

                    apply_placeholder_fill(result, missing)

                    logger.info(

                        "[LLMwanzhengxing] integrity_mode=agent_weak bitianziduanqueshi %s(chinese removed)똹izhanweibuquan",

                        missing,

                    )

            # chip_structure fallback (Issue #589), before save_analysis_history

            if result and chip_data:

                fill_chip_structure_if_needed(result, chip_data)



            # price_position fallback (same as non-agent path Step 7.7)

            if result:

                fill_price_position_if_needed(result, trend_result, realtime_quote)

                realtime_data = initial_context.get("realtime_quote", {})

                if isinstance(realtime_data, dict):

                    result.current_price = realtime_data.get("price")

                    result.change_pct = realtime_data.get("change_pct")

                stabilize_decision_with_structure(result, trend_result, fundamental_context)



            resolved_stock_name = result.name if result and result.name else stock_name



            # savexinwenqingbaodaoshujuku(chinese removed)뉯gent gongjujieguojinyongyu LLM shangxiawen(chinese removed)똷eichijiuhua(chinese removed)똅ixes #396(chinese removed)?
            # shiyong search_stock_news(chinese removed)늶u Agent gongjudiaoyongluojiyizhi(chinese removed)됵펽jin 1 ci API diaoyong(chinese removed)똷uewaiyanchi

            if self.search_service is not None and self.search_service.is_available:

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

                        logger.info(f"[{code}] Agent moshi: xinwenqingbaoyisave {len(news_response.results)} tiao")

                except Exception as e:

                    logger.warning(f"[{code}] Agent moshisavexinwenqingbaoshibai: {e}")



            # saveanalysislishirecord

            if result and result.success:

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

                    logger.warning(f"[{code}] save Agent analysislishishibai: {e}")



            return result



        except Exception as e:

            logger.error(f"[{code}] Agent analysisshibai: {e}")

            logger.exception(f"[{code}] Agent xiangxicuowuxinxi:")

            return None



    def _agent_result_to_analysis_result(

        self,

        agent_result,

        code: str,

        stock_name: str,

        report_type: ReportType,

        query_id: str,

        trend_result: Optional[TrendAnalysisResult] = None,

    ) -> AnalysisResult:

        """

        ~으로 변환 AgentResult zhuanhuanwei AnalysisResult??
        """




        report_language = normalize_report_language(getattr(self.config, "report_language", "zh"))

        result = AnalysisResult(

            code=code,

            name=stock_name,

            sentiment_score=50,

            trend_prediction="Unknown" if report_language == "en" else "weizhi",

            operation_advice="Watch" if report_language == "en" else "guanwang",

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



            nested_dashboard = dash.get("dashboard") if isinstance(dash, dict) else None



            raw_score = self._agent_dashboard_value(

                dash,

                nested_dashboard,

                "sentiment_score",

                scalar=True,

            )

            if self._is_agent_field_missing(raw_score, scalar=True):

                fallback_score = self._trend_score_fallback(trend_result)

                if fallback_score is not None:

                    result.sentiment_score = fallback_score

                    self._mark_trend_fallback_source(result)

            else:

                result.sentiment_score = self._safe_int(raw_score, 50)



            raw_trend = self._agent_dashboard_value(

                dash,

                nested_dashboard,

                "trend_prediction",

                scalar=True,

                expect_text=True,

            )

            if self._is_agent_field_missing(raw_trend, scalar=True, expect_text=True):

                trend_label = self._trend_label_fallback(

                    trend_result,

                    report_language,

                )

                if trend_label:

                    result.trend_prediction = trend_label

                    self._mark_trend_fallback_source(result)

            else:

                result.trend_prediction = str(raw_trend)



            raw_advice = self._agent_dashboard_value(

                dash,

                nested_dashboard,

                "operation_advice",

                scalar=True,

                allow_dict=True,

                expect_text=True,

            )

            extracted_advice = ""

            if isinstance(raw_advice, dict):

                # LLM may return {"no_position": "...", "has_position": "..."}

                extracted_advice = self._extract_advice_text_from_dict(raw_advice)

                if extracted_advice:

                    result.operation_advice = localize_operation_advice(

                        extracted_advice,

                        report_language,

                    )

                else:

                    signal_label = self._trend_signal_fallback(

                        trend_result,

                        report_language,

                    )

                    if signal_label:

                        result.operation_advice = signal_label

                        self._mark_trend_fallback_source(result)

            elif not self._is_agent_field_missing(

                raw_advice,

                scalar=True,

                allow_dict=True,

                expect_text=True,

            ):

                result.operation_advice = str(raw_advice) if raw_advice else ("Watch" if report_language == "en" else "guanwang")

            else:

                signal_label = self._trend_signal_fallback(trend_result, report_language)

                if signal_label:

                    result.operation_advice = signal_label

                    self._mark_trend_fallback_source(result)

            from src.agent.protocols import normalize_decision_signal



            raw_decision = self._agent_dashboard_value(

                dash,

                nested_dashboard,

                "decision_type",

                scalar=True,

                expect_text=True,

            )

            if self._is_agent_field_missing(raw_decision, scalar=True, expect_text=True):

                trend_decision = self._trend_decision_fallback(trend_result)

                decision_from_advice = infer_decision_type_from_advice(

                    result.operation_advice,

                    default="",

                )

                if decision_from_advice:

                    result.decision_type = decision_from_advice

                    if (

                        self._is_agent_field_missing(

                            raw_advice,

                            scalar=True,

                            allow_dict=True,

                            expect_text=True,

                        )

                        and not extracted_advice

                        and trend_decision

                    ):

                        self._mark_trend_fallback_source(result)

                else:

                    result.decision_type = trend_decision or "hold"

                    if trend_decision:

                        self._mark_trend_fallback_source(result)

            else:

                result.decision_type = normalize_decision_signal(raw_decision)

            result.confidence_level = localize_confidence_level(

                self._agent_dashboard_value(dash, nested_dashboard, "confidence_level")

                or result.confidence_level,

                report_language,

            )

            raw_summary = self._agent_dashboard_value(

                dash,

                nested_dashboard,

                "analysis_summary",

                scalar=True,

                expect_text=True,

            )

            if not self._is_agent_field_missing(raw_summary, scalar=True, expect_text=True):

                result.analysis_summary = str(raw_summary)

            else:

                result.analysis_summary = self._summary_fallback_from_result(result, report_language)

            # The AI returns a top-level dict that contains a nested 'dashboard' sub-key

            # with core_conclusion / battle_plan / intelligence.  AnalysisResult's helper

            # methods (get_sniper_points, get_core_conclusion, etc.) expect that inner

            # structure, so we unwrap it here.

            result.dashboard = nested_dashboard or dash

            self._backfill_agent_dashboard_fields(result, trend_result, report_language)

        else:

            self._apply_trend_fallback(result, trend_result, report_language)

            if trend_result is not None:

                result.analysis_summary = (

                    result.analysis_summary

                    or self._summary_fallback_from_result(result, report_language)

                )

                self._backfill_agent_dashboard_fields(result, trend_result, report_language)

            if not result.error_message:

                result.error_message = "Agent failed to generate a valid decision dashboard" if report_language == "en" else "Agent weinengshengchengyouxiaodejueceyibiaopan"



        return result



    @staticmethod

    def _agent_dashboard_value(

        dash: Dict[str, Any],

        nested_dashboard: Any,

        key: str,

        *,

        scalar: bool = False,

        allow_dict: bool = False,

        expect_text: bool = False,

    ) -> Any:

        """Read a scalar from top-level agent payload, then nested dashboard fallback."""

        value = dash.get(key) if isinstance(dash, dict) else None

        if isinstance(nested_dashboard, dict) and StockAnalysisPipeline._is_agent_field_missing(

            value,

            scalar=scalar,

            allow_dict=allow_dict,

            expect_text=expect_text,

        ):

            nested_value = nested_dashboard.get(key)

            if not StockAnalysisPipeline._is_agent_field_missing(

                nested_value,

                scalar=scalar,

                allow_dict=allow_dict,

                expect_text=expect_text,

            ):

                value = nested_value

        return value



    @staticmethod

    def _extract_advice_text_from_dict(raw_advice: dict) -> str:

        for field in ("has_position", "no_position"):

            if isinstance(raw_advice.get(field), str):

                text = raw_advice[field].strip()

                if not StockAnalysisPipeline._is_agent_placeholder_text(text):

                    return text



        for value in raw_advice.values():

            if isinstance(value, str):

                text = value.strip()

                if not StockAnalysisPipeline._is_agent_placeholder_text(text):

                    return text



        return ""



    @staticmethod

    def _is_agent_placeholder_text(text: str) -> bool:

        if not text:

            return True

        return text.lower() in {"n/a", "na", "none", "null", "unknown", "tbd"} or text in {

            "weizhi",

            "daibuchong",

            "shujuqueshi",

            "wu",

        }



    @staticmethod

    def _is_agent_field_missing(

        value: Any,

        *,

        scalar: bool = False,

        allow_dict: bool = False,

        expect_text: bool = False,

    ) -> bool:

        if scalar and isinstance(value, dict):

            if not allow_dict or not value:

                return True

            return not StockAnalysisPipeline._extract_advice_text_from_dict(value)

        if value is None:

            return True

        if expect_text and scalar:

            if not isinstance(value, str):

                return True

        if isinstance(value, str):

            text = value.strip()

            return StockAnalysisPipeline._is_agent_placeholder_text(text)

        if isinstance(value, dict):

            if scalar:

                return not allow_dict

            return not value

        if scalar and isinstance(value, (list, tuple, set)):

            return True

        return False



    @staticmethod

    def _trend_score_fallback(trend_result: Optional[TrendAnalysisResult]) -> Optional[int]:

        if trend_result is None:

            return None

        try:

            score = int(getattr(trend_result, "signal_score", 0))

        except (TypeError, ValueError):

            return None

        return score if score > 0 else None



    @staticmethod

    def _trend_label_fallback(

        trend_result: Optional[TrendAnalysisResult],

        report_language: str = "zh",

    ) -> str:

        if trend_result is None:

            return ""

        trend_status = getattr(trend_result, "trend_status", None)

        value = getattr(trend_status, "value", None) or str(trend_status or "").strip()

        if report_language != "en":

            return value

        return localize_trend_prediction(value, report_language)



    @staticmethod

    def _trend_signal_fallback(

        trend_result: Optional[TrendAnalysisResult],

        report_language: str = "zh",

    ) -> str:

        if trend_result is None:

            return ""

        buy_signal = getattr(trend_result, "buy_signal", None)

        value = getattr(buy_signal, "value", None) or str(buy_signal or "").strip()

        return localize_operation_advice(value, report_language)



    @staticmethod

    def _trend_decision_fallback(trend_result: Optional[TrendAnalysisResult]) -> Optional[str]:

        if trend_result is None:

            return None

        signal_name = getattr(getattr(trend_result, "buy_signal", None), "name", "").lower()

        return {

            "strong_buy": "buy",

            "buy": "buy",

            "hold": "hold",

            "wait": "hold",

            "sell": "sell",

            "strong_sell": "sell",

        }.get(signal_name)



    @staticmethod

    def _mark_trend_fallback_source(result: AnalysisResult) -> None:

        if "trend:fallback" in (result.data_sources or ""):

            return

        result.data_sources = (

            f"{result.data_sources},trend:fallback"

            if result.data_sources

            else "trend:fallback"

        )



    @staticmethod

    def _summary_fallback_from_result(result: AnalysisResult, report_language: str) -> str:

        trend = (result.trend_prediction or "").strip()

        advice = (result.operation_advice or "").strip()

        if trend and advice:

            if report_language == "en":

                return f"Trend view: {trend}; action advice: {advice}."

            return f"추세 판단: {trend}; 매매 의견: {advice}."
        return ""



    def _backfill_agent_dashboard_fields(

        self,

        result: AnalysisResult,

        trend_result: Optional[TrendAnalysisResult],

        report_language: str,

    ) -> None:

        if not isinstance(result.dashboard, dict):

            result.dashboard = {}

        dashboard = result.dashboard



        for key in (

            "sentiment_score",

            "trend_prediction",

            "operation_advice",

            "decision_type",

            "confidence_level",

            "analysis_summary",

        ):

            current = dashboard.get(key)

            if key == "sentiment_score":

                if self._is_agent_field_missing(current, scalar=True):

                    dashboard[key] = getattr(result, key)

            elif self._is_agent_field_missing(current, scalar=True, expect_text=True):

                dashboard[key] = getattr(result, key)



        core = dashboard.get("core_conclusion")

        if not isinstance(core, dict):

            core = {}

            dashboard["core_conclusion"] = core

        if self._is_agent_field_missing(core.get("one_sentence"), scalar=True):

            core["one_sentence"] = result.analysis_summary or self._summary_fallback_from_result(

                result,

                report_language,

            ) or ("Analysis pending" if report_language == "en" else "analysisdaibuchong")



        intelligence = dashboard.get("intelligence")

        if not isinstance(intelligence, dict):

            intelligence = {}

            dashboard["intelligence"] = intelligence

        risk_alerts = intelligence.get("risk_alerts")

        if (

            "risk_alerts" not in intelligence

            or self._is_agent_field_missing(risk_alerts)

            or not isinstance(risk_alerts, list)

        ):

            risk_factors = getattr(trend_result, "risk_factors", None) or []

            intelligence["risk_alerts"] = list(risk_factors)



        if result.decision_type in ("buy", "hold"):

            battle = dashboard.get("battle_plan")

            if not isinstance(battle, dict):

                battle = {}

                dashboard["battle_plan"] = battle

            sniper_points = battle.get("sniper_points")

            if not isinstance(sniper_points, dict):

                sniper_points = {}

                battle["sniper_points"] = sniper_points

            if self._is_agent_field_missing(sniper_points.get("stop_loss"), scalar=True):

                sniper_points["stop_loss"] = self._stop_loss_fallback_from_trend(

                    trend_result,

                    report_language,

                )



    @staticmethod

    def _stop_loss_fallback_from_trend(

        trend_result: Optional[TrendAnalysisResult],

        report_language: str,

    ) -> Any:

        levels = getattr(trend_result, "support_levels", None) if trend_result else None

        if levels:

            return levels[0]

        return "To be completed" if report_language == "en" else "daibuchong"



    @staticmethod

    def _apply_trend_fallback(

        result: AnalysisResult,

        trend_result: Optional[TrendAnalysisResult],

        report_language: str,

    ) -> None:

        if trend_result is None:

            result.sentiment_score = 50

            result.operation_advice = "Watch" if report_language == "en" else "guanwang"

            return



        score = getattr(trend_result, "signal_score", None)

        try:

            numeric_score = int(score)

        except (TypeError, ValueError):

            numeric_score = 50

        result.sentiment_score = numeric_score if numeric_score > 0 else 50



        trend_label = StockAnalysisPipeline._trend_label_fallback(trend_result, report_language)

        if trend_label:

            result.trend_prediction = trend_label



        buy_signal = getattr(trend_result, "buy_signal", None)

        signal_label = StockAnalysisPipeline._trend_signal_fallback(

            trend_result,

            report_language,

        )

        if signal_label:

            result.operation_advice = signal_label

        else:

            result.operation_advice = "Watch" if report_language == "en" else "guanwang"



        from src.agent.protocols import normalize_decision_signal



        signal_name = getattr(buy_signal, "name", "").lower()

        signal_to_decision = {

            "strong_buy": "buy",

            "buy": "buy",

            "hold": "hold",

            "wait": "hold",

            "sell": "sell",

            "strong_sell": "sell",

        }

        result.decision_type = signal_to_decision.get(signal_name, result.decision_type or "hold")

        result.decision_type = normalize_decision_signal(result.decision_type)

        result.data_sources = f"{result.data_sources},trend:fallback" if result.data_sources else "trend:fallback"



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

        if normalized.startswith("stock"):

            return True

        if "Unknown" in normalized:

            return True

        return False



    @staticmethod

    def _safe_int(value: Any, default: int = 50) -> int:

        """Safely convert a value to an integer."""
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

        liangbimiaoshu

        

        거래량 비율 = ~인 경우전거래량 / guoqu5ripingjun거래량

        """









        if volume_ratio < 0.5:

            return "jiduweisuo"

        elif volume_ratio < 0.8:

            return "mingxianweisuo"

        elif volume_ratio < 1.2:

            return "zhengchang"

        elif volume_ratio < 2.0:

            return "wenhefangliang"

        elif volume_ratio < 3.0:

            return "mingxianfangliang"

        else:

            return "juliang"



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

            return "duotoupailie ?뱢"

        elif close < ma5 < ma10 < ma20 and ma20 > 0:

            return "kongtoupailie ?뱣"

        elif close > ma5 and ma5 > ma10:

            return "duanqixianghao ?뵾"

        elif close < ma5 and ma5 < ma10:

            return "duanqizouruo ?뵿"

        else:

            return "zhendangzhengli ?뷂툘"



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

        market_today = get_market_now(market).date()

        if market and not is_market_open(market, market_today):

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



        if last_date >= market_today:

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

                'date': market_today,

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

        goujiananalysisshangxiawenkuaizhao

        """

        snapshot = {

            "enhanced_context": enhanced_context,

            "news_content": news_content,

            "realtime_quote_raw": self._safe_to_dict(realtime_quote),

            "chip_distribution_raw": self._safe_to_dict(chip_data),

        }

        if self.analysis_skills is not None:

            snapshot["skills"] = list(self.analysis_skills)

        return snapshot



    @staticmethod

    def _resolve_resume_target_date(

        code: str, current_time: Optional[datetime] = None

    ) -> date:

        """

        Resolve the trading date used by checkpoint/resume checks.

        """

        market = get_market_for_stock(normalize_stock_code(code))

        return get_effective_trading_date(market, current_time=current_time)



    @staticmethod

    def _safe_to_dict(value: Any) -> Optional[Dict[str, Any]]:

        """

        anquanzhuanhuanweizidian

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

        jiexiqingqiulaiyuan??


        우선순위(chinese removed)늓onggaodaodi(chinese removed)됵폏

        1. xianshichuanrude query_source(chinese removed)쉊iaoyongfangmingquezhidingshiyouxian사용(chinese removed)똟ianyufugaituiduanjieguohuojianrongweilai source_message laizifei bot dechangjing

        2. cunzai source_message shituiduanwei "bot"(chinese removed)쉊angqianyuedingweijiqirenhuihuashangxiawen

        3. cunzai query_id shituiduanwei "web"(chinese removed)쉂eb chufadeqingqiuhuidaishang query_id

        4. 기본값 "system"(chinese removed)쉊ingshirenwuhuo CLI dengwushangshushangxiawenshi



        Args:

            query_source: diaoyongfangxianshizhidingdelaiyuan(chinese removed)똱u "bot" / "web" / "cli" / "system"



        Returns:

            guiyihuahoudelaiyuanbiaoshizifuchuan(chinese removed)똱u "bot" / "web" / "cli" / "system"

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

        shengchengyonghuchaxunguanlianxinxi

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

        current_time: Optional[datetime] = None,

    ) -> Optional[AnalysisResult]:

        """

        chulidanzhistockdewanzheng흐름



        baokuo(chinese removed)?
        1. huoqushuju

        2. saveshuju

        3. AI analysis

        4. ~인 경우utuisong(chinese removed)늟exuan(chinese removed)?55(chinese removed)?


        cifangfahuibeixianchengchidiaoyong(chinese removed)똸uyaochulihaoyichang



        Args:

            analysis_query_id: chaxunlianluguanlian id

            code: stockdaima

            skip_analysis: shifoutiaoguo AI analysis

            single_stock_notify: shifouqiyong~인 경우utuisongmoshi(chinese removed)늤eianalysiswanyizhilijituisong(chinese removed)?
            report_type: baogaoleixingmeiju(chinese removed)늓ongconfigduqu(chinese removed)똈ssue #119(chinese removed)?
            current_time: benlunyunxingdongjiedecankaoshijian(chinese removed)똹ongyutongyiduandianxuchuanmubiaojiaoyiripanduan



        Returns:

            AnalysisResult huo None

        """







































        logger.info(f"========== kaishichuli {code} ==========")



        from src.services.history_loader import set_frozen_target_date, reset_frozen_target_date

        frozen_td = self._resolve_resume_target_date(code, current_time=current_time)

        token = set_frozen_target_date(frozen_td)

        try:

            self._emit_progress(12, f"{code}(chinese removed)쉦hengzaizhunbeianalysisrenwu")

            # Step 1: huoqubingsaveshuju

            success, error = self.fetch_and_save_stock_data(

                code, current_time=current_time

            )

            

            if not success:

                logger.warning(f"[{code}] shujuhuoqushibai: {error}")

                # jishihuoqushibai(chinese removed)똹echangshiyongyiyoushujuanalysis

            else:

                self._emit_progress(16, f"{code}(chinese removed)쉎anginputjuzhunbeiwancheng")

            

            # Step 2: AI analysis

            if skip_analysis:

                logger.info(f"[{code}] skipping AI analysis in dry-run mode")
                return None

            

            effective_query_id = analysis_query_id or self.query_id or uuid.uuid4().hex

            result = self.analyze_stock(code, report_type, query_id=effective_query_id)

            

            if result and result.success:

                logger.info(

                    f"[{code}] analysiswancheng: {result.operation_advice}, "

                    f"pingfen {result.sentiment_score}"

                )

                

                # dangutuisongmoshi(chinese removed)?55(chinese removed)됵폏meianalysiswanyizhistocklijituisong

                if single_stock_notify:

                    self._send_single_stock_notification(

                        result,

                        report_type=report_type,

                        fallback_code=code,

                    )

            elif result:

                logger.warning(

                    f"[{code}] analysisweichenggong: {result.error_message or 'weizhicuowu'}"

                )

            

            return result

            

        except Exception as e:

            # buhuosuoyouyichang(chinese removed)똰uebaodangushibaibuyingxiangzhengti

            logger.exception(f"[{code}] chuliguochengfashengweizhiyichang: {e}")

            return None

        finally:

            reset_frozen_target_date(token)

    

    def run(

        self,

        stock_codes: Optional[List[str]] = None,

        dry_run: bool = False,

        send_notification: bool = True,

        merge_notification: bool = False

    ) -> List[AnalysisResult]:

        """

        yunxingwanzhengdeanalysis흐름



        흐름(chinese removed)?
        1. huoqudaianalysisdestockliebiao

        2. 사용xianchengchibingfachuli

        3. shoujianalysisjieguo

        4. sendnotification



        Args:

            stock_codes: stockdaimaliebiao(chinese removed)늟exuan(chinese removed)똫oren사용configzhongdewatchlistgu(chinese removed)?
            dry_run: shifoujinhuoqushujubuanalysis

            send_notification: shifousendtuisongnotification

            merge_notification: shifouhebingtuisong(chinese removed)늯iaoguobencituisong(chinese removed)똹ou main cenghebinggegu+dapanhoutongyisend(chinese removed)똈ssue #190(chinese removed)?


        Returns:

            analysisjieguoliebiao

        """
































        start_time = time.time()

        

        # shiyongconfigzhongdestockliebiao

        if stock_codes is None:

            self.config.refresh_stock_list()

            stock_codes = self.config.stock_list

        

        if not stock_codes:

            logger.error("weiconfigwatchlistguliebiao(chinese removed)똰ingzai .env wenjianzhongshezhi STOCK_LIST")

            return []

        

        logger.info(f"===== kaishianalysis {len(stock_codes)} zhistock =====")

        logger.info(f"stockliebiao: {', '.join(stock_codes)}")

        logger.info(f"bingfashu: {self.max_workers}, moshi: {'jinhuoqushuju' if dry_run else 'wanzhenganalysis'}")



        # dongjiebenlunyunxingdetongyicankaoshijian(chinese removed)똟imiankuamarketshoupanbianjieshitongpistockshiyongbutongmubiaojiaoyiri??
        resume_reference_time = datetime.now(timezone.utc)

        

        # === piliangyuqushishixingqing(chinese removed)늶ouhua(chinese removed)쉇imianmeizhistockdouchufaquanlianglaqu(chinese removed)?==

        # zhiyoustockshuliang >= 5 shicaijinxingyuqu(chinese removed)똲haoliangstockzhijiezhugechaxungenggaoxiao

        if len(stock_codes) >= 5:

            prefetch_count = self.fetcher_manager.prefetch_realtime_quotes(stock_codes)

            if prefetch_count > 0:

                logger.info(f"Realtime quote prefetch enabled: fetched shared market data for {len(stock_codes)} stocks")


        # Issue #455: yuqustockmingcheng(chinese removed)똟imianbingfaanalysisshixianshi?똤upiaoxxxxx??
        # dry_run jinzuoshujulaqu(chinese removed)똟uxuyaomingchengyuqu(chinese removed)똟imianewaiwangluokaixiao

        if not dry_run:

            self.fetcher_manager.prefetch_stock_names(stock_codes, use_bulk=False)



        # dangutuisongmoshi(chinese removed)?55(chinese removed)됵폏congconfigduqu

        single_stock_notify = getattr(self.config, 'single_stock_notify', False)

        # Issue #119: congconfigduqubaogaoleixing

        report_type_str = getattr(self.config, 'report_type', 'simple').lower()

        if report_type_str == 'brief':

            report_type = ReportType.BRIEF

        elif report_type_str == 'full':

            report_type = ReportType.FULL

        else:

            report_type = ReportType.SIMPLE

        # Issue #128: congconfigduquanalysisjiange

        analysis_delay = getattr(self.config, 'analysis_delay', 0)



        if single_stock_notify:

            logger.info(

                "Single-stock notification mode enabled; analysis remains concurrent and notifications are sent serially after result collection (report type: %s).",
                report_type_str,

            )

        

        results: List[AnalysisResult] = []

        

        # shiyongxianchengchibingfachuli

        # zhuyi(chinese removed)쉖ax_workers shezhijiaodi(chinese removed)늤oren3(chinese removed)뎫ibimianchufafanpa

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:

            # tijiaorenwu

            future_to_code = {

                executor.submit(

                    self.process_single_stock,

                    code,

                    skip_analysis=dry_run,

                    single_stock_notify=False,

                    report_type=report_type,  # Issue #119: chuandibaogaoleixing

                    analysis_query_id=uuid.uuid4().hex,

                    current_time=resume_reference_time,

                ): code

                for code in stock_codes

            }

            

            # shoujijieguo

            for idx, future in enumerate(as_completed(future_to_code)):

                code = future_to_code[future]

                try:

                    result = future.result()

                    if result and result.success:

                        results.append(result)

                        if single_stock_notify and send_notification and not dry_run:

                            self._send_single_stock_notification(

                                result,

                                report_type=report_type,

                                fallback_code=code,

                            )

                    elif result and not result.success:

                        logger.warning(

                            f"[{code}] analysisjieguobiaojiweishibai(chinese removed)똟ujiruhuizong: "

                            f"{result.error_message or 'weizhiyuanyin'}"

                        )



                    # Issue #128: analysisjiange - zaigeguanalysishedapananalysiszhijianaddyanchi

                    if idx < len(stock_codes) - 1 and analysis_delay > 0:

                        # zhuyi(chinese removed)쉉i sleep fashengzai?쐚huxianchengshouji future dexunhuan?쓟hong(chinese removed)?
                        # bingbuhuizuzhixianchengchizhongderenwutongshifaqiwangluoqingqiu??
                        # yincitaduijiangdibingfaqingqiufengzhidexiaoguoyouxian(chinese removed)썍henzhengdefengzhizhuyaoyou max_workers jueding??
                        # gaixingweimuqianbaoliu(chinese removed)늏nxuqiubugailuoji(chinese removed)됥?
                        logger.debug(f"dengdai {analysis_delay} miaohoujixuxiayizhistock...")

                        time.sleep(analysis_delay)



                except Exception as e:

                    logger.error(f"[{code}] renwuzhixingshibai: {e}")

        

        # tongji

        elapsed_time = time.time() - start_time

        

        # dry-run moshixia(chinese removed)똲hujuhuoquchenggongjishiweichenggong

        if dry_run:

            # jianchanaxiestockdezuixinkefuyongjiaoyirishujuyicunzai

            success_count = sum(

                1

                for code in stock_codes

                if self.db.has_today_data(

                    code,

                    self._resolve_resume_target_date(

                        code, current_time=resume_reference_time

                    ),

                )

            )

            fail_count = len(stock_codes) - success_count

        else:

            success_count = len(results)

            fail_count = len(stock_codes) - success_count

        

        logger.info("===== analysiswancheng =====")

        logger.info(f"chenggong: {success_count}, shibai: {fail_count}, haoshi: {elapsed_time:.2f} miao")

        

        # savebaogaodaobendiwenjian(chinese removed)늳ulunshifoutuisongnotificationdousave(chinese removed)?
        if results and not dry_run:

            self._save_local_report(results, report_type)



        # sendnotification(chinese removed)늕angutuisongmoshixiatiaoguohuizongtuisong(chinese removed)똟imianchongfu(chinese removed)?
        if results and send_notification and not dry_run:

            if single_stock_notify:

                # dangutuisongmoshi(chinese removed)쉦hisavehuizongbaogao(chinese removed)똟uzaichongfutuisong

                logger.info("dangutuisongmoshi(chinese removed)쉞iaoguohuizongtuisong(chinese removed)똨insavebaogaodaobendi")

                self._send_notifications(results, report_type, skip_push=True)

            elif merge_notification:

                # hebingmoshi(chinese removed)뉹ssue #190(chinese removed)됵폏jinsave(chinese removed)똟utuisong(chinese removed)똹ou main cenghebinggegu+dapanhoutongyisend

                logger.info("hebingtuisongmoshi(chinese removed)쉞iaoguobencituisong(chinese removed)똨iangzaigegu+dapanfupanhoutongyisend")

                self._send_notifications(results, report_type, skip_push=True)

            else:

                self._send_notifications(results, report_type)

        

        return results



    def _send_single_stock_notification(

        self,

        result: AnalysisResult,

        report_type: ReportType = ReportType.SIMPLE,

        fallback_code: Optional[str] = None,

    ) -> None:

        """Send a single-stock notification through the shared notification path."""
        if not self.notifier.is_available():

            return



        stock_code = getattr(result, "code", None) or fallback_code or "unknown"

        notify_lock = getattr(self, "_single_stock_notify_lock", None)

        if notify_lock is None:

            with _SINGLE_STOCK_NOTIFY_LOCK_INIT_GUARD:

                notify_lock = getattr(self, "_single_stock_notify_lock", None)

                if notify_lock is None:

                    notify_lock = threading.Lock()

                    setattr(self, "_single_stock_notify_lock", notify_lock)



        with notify_lock:

            try:

                if report_type == ReportType.FULL:

                    report_content = self.notifier.generate_dashboard_report([result])

                    logger.info(f"[{stock_code}] shiyongwanzhengbaogaogeshi")

                elif report_type == ReportType.BRIEF:

                    report_content = self.notifier.generate_brief_report([result])

                    logger.info(f"[{stock_code}] shiyongjianjiebaogaogeshi")

                else:

                    report_content = self.notifier.generate_single_stock_report(result)

                    logger.info(f"[{stock_code}] shiyongjingjianbaogaogeshi")



                if self.notifier.send(

                    report_content,

                    email_stock_codes=[stock_code],

                    route_type="report",

                    severity="info",

                    dedup_key=f"report:single:{stock_code}:{report_type.value}",

                    cooldown_key=f"report:single:{stock_code}:{report_type.value}",

                ):

                    logger.info(f"[{stock_code}] dangutuisongchenggong")

                else:

                    logger.warning(f"[{stock_code}] dangutuisongshibai")

            except Exception as e:

                logger.error(f"[{stock_code}] dangutuisongyichang: {e}")



    def _save_local_report(

        self,

        results: List[AnalysisResult],

        report_type: ReportType = ReportType.SIMPLE,

    ) -> None:

        """Save the analysis report locally and return the notification payload."""
        try:

            report = self._generate_aggregate_report(results, report_type)

            filepath = self.notifier.save_report_to_file(report)

            logger.info(f"jueceyibiaopanribaoyisave: {filepath}")

        except Exception as e:

            logger.error(f"savebendibaogaoshibai: {e}")



    def _send_notifications(

        self,

        results: List[AnalysisResult],

        report_type: ReportType = ReportType.SIMPLE,

        skip_push: bool = False,

    ) -> None:

        """

        sendanalysisjieguonotification

        

        shengchengjueceyibiaopan포맷debaogao

        

        Args:

            results: analysisjieguoliebiao

            skip_push: shifoutiaoguotuisong(chinese removed)늞insavedaobendi(chinese removed)똹ongyu~인 경우utuisongmoshi(chinese removed)?
        """
















        noise_decision = None

        noise_finalized = False

        try:

            logger.info("shengchengjueceyibiaopanribao...")

            report = self._generate_aggregate_report(results, report_type)

            

            # tiaoguotuisong(chinese removed)늕angutuisongmoshi / hebingmoshi(chinese removed)쉇aogaoyiyou _save_local_report save(chinese removed)?
            if skip_push:

                return

            

            # tuisongnotification

            if self.notifier.is_available():

                channels = self.notifier.get_available_channels()

                channels = self.notifier.get_channels_for_route("report", channels=channels)

                context_success = self.notifier.send_to_context(report)

                if channels and hasattr(self.notifier, "evaluate_noise_control"):

                    report_type_key = report_type.value if isinstance(report_type, ReportType) else str(report_type)

                    codes_key = ",".join(

                        sorted(str(getattr(result, "code", "") or "") for result in results)

                    )

                    noise_key = f"report:aggregate:{report_type_key}:{codes_key}"

                    noise_decision = self.notifier.evaluate_noise_control(

                        report,

                        route_type="report",

                        severity="info",

                        dedup_key=noise_key,

                        cooldown_key=noise_key,

                    )

                    if not noise_decision.should_send:

                        logger.info(noise_decision.message)

                        return



                # Issue #455: Markdown zhuantupian(chinese removed)늶u notification.send luojiyizhi(chinese removed)?
                from src.md2img import markdown_to_image



                channels_needing_image = {

                    ch for ch in channels

                    if ch.value in self.notifier._markdown_to_image_channels

                    and ch not in {NotificationChannel.NTFY, NotificationChannel.GOTIFY}

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



                def _send_channel_safely(channel_label: str, send_func: Callable[[], bool]) -> bool:

                    try:

                        return bool(send_func())

                    except Exception as e:

                        logger.exception(

                            "notificationqudao %s tuisongyichang(chinese removed)똨ixuchangshiqitaqudao: %s",

                            channel_label,

                            e,

                        )

                        return False



                image_bytes = None

                if non_wechat_channels_needing_image:

                    image_bytes = markdown_to_image(

                        report, max_chars=self.notifier._markdown_to_image_max_chars

                    )

                    if image_bytes:

                        logger.info(

                            "Markdown yizhuanhuanweitupian(chinese removed)똨iangxiang %s sendtupian",

                            [ch.value for ch in non_wechat_channels_needing_image],

                        )

                    else:

                        logger.warning(

                            "Markdown zhuantupianshibai(chinese removed)똨ianghuituiweiwenbensend?굌ingjiancha MARKDOWN_TO_IMAGE_CHANNELS configbinganzhuang %s",

                            _get_md2img_hint(),

                        )



                # qiyeweixin(chinese removed)쉦hifajingjianban(chinese removed)늩ingtaixianzhi(chinese removed)?
                wechat_success = False

                if NotificationChannel.WECHAT in channels:

                    def _send_wechat_report() -> bool:

                        if report_type == ReportType.BRIEF:

                            dashboard_content = self.notifier.generate_brief_report(results)

                        else:

                            dashboard_content = self.notifier.generate_wechat_dashboard(results)

                        logger.info(f"qiyeweixinyibiaopanchangdu: {len(dashboard_content)} zifu")

                        logger.debug(f"qiyeweixintuisongneirong:\n{dashboard_content}")

                        wechat_image_bytes = None

                        if NotificationChannel.WECHAT in channels_needing_image:

                            wechat_image_bytes = markdown_to_image(

                                dashboard_content,

                                max_chars=self.notifier._markdown_to_image_max_chars,

                            )

                            if wechat_image_bytes is None:

                                logger.warning(

                                    "qiyeweixin Markdown zhuantupianshibai(chinese removed)똨ianghuituiweiwenbensend?굌ingjiancha MARKDOWN_TO_IMAGE_CHANNELS configbinganzhuang %s",

                                    _get_md2img_hint(),

                                )

                        use_image = self.notifier._should_use_image_for_channel(

                            NotificationChannel.WECHAT, wechat_image_bytes

                        )

                        if use_image:

                            return self.notifier._send_wechat_image(wechat_image_bytes)

                        return self.notifier.send_to_wechat(dashboard_content)



                    wechat_success = _send_channel_safely(

                        NotificationChannel.WECHAT.value,

                        _send_wechat_report,

                    )



                # qitaqudao(chinese removed)쉌awanzhengbaogao(chinese removed)늒imianzidingyi Webhook bei wechat jieduanluojiwuran(chinese removed)?
                non_wechat_success = False

                stock_email_groups = getattr(self.config, 'stock_email_groups', []) or []

                for channel in channels:

                    if channel == NotificationChannel.WECHAT:

                        continue

                    if channel == NotificationChannel.FEISHU:

                        non_wechat_success = _send_channel_safely(

                            channel.value,

                            lambda: self.notifier.send_to_feishu(report),

                        ) or non_wechat_success

                    elif channel == NotificationChannel.TELEGRAM:

                        def _send_telegram_report() -> bool:

                            use_image = self.notifier._should_use_image_for_channel(

                                channel, image_bytes

                            )

                            if use_image:

                                return self.notifier._send_telegram_photo(image_bytes)

                            return self.notifier.send_to_telegram(report)



                        non_wechat_success = _send_channel_safely(

                            channel.value,

                            _send_telegram_report,

                        ) or non_wechat_success

                    elif channel == NotificationChannel.EMAIL:

                        if stock_email_groups:

                            code_to_emails: Dict[str, Optional[List[str]]] = {}

                            for r in results:

                                if r.code not in code_to_emails:

                                    canonical = normalize_stock_code(r.code)

                                    emails = []

                                    for stocks, emails_list in stock_email_groups:

                                        if canonical in stocks:

                                            emails.extend(emails_list)

                                    code_to_emails[r.code] = list(dict.fromkeys(emails)) if emails else None

                            emails_to_results: Dict[Optional[Tuple], List] = defaultdict(list)

                            for r in results:

                                recs = code_to_emails.get(r.code)

                                key = tuple(recs) if recs else None

                                emails_to_results[key].append(r)

                            for key, group_results in emails_to_results.items():

                                receivers = list(key) if key is not None else None



                                def _send_email_group(

                                    group_results=group_results,

                                    receivers=receivers,

                                ) -> bool:

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

                                    if use_image:

                                        return self.notifier._send_email_with_inline_image(

                                            grp_image_bytes, receivers=receivers

                                        )

                                    return self.notifier.send_to_email(

                                        grp_report, receivers=receivers

                                    )



                                email_label = (

                                    f"{channel.value}:{','.join(receivers)}"

                                    if receivers else f"{channel.value}:default"

                                )

                                non_wechat_success = _send_channel_safely(

                                    email_label,

                                    _send_email_group,

                                ) or non_wechat_success

                        else:

                            def _send_email_report() -> bool:

                                use_image = self.notifier._should_use_image_for_channel(

                                    channel, image_bytes

                                )

                                if use_image:

                                    return self.notifier._send_email_with_inline_image(image_bytes)

                                return self.notifier.send_to_email(report)



                            non_wechat_success = _send_channel_safely(

                                channel.value,

                                _send_email_report,

                            ) or non_wechat_success

                    elif channel == NotificationChannel.CUSTOM:

                        def _send_custom_report() -> bool:

                            use_image = self.notifier._should_use_image_for_channel(

                                channel, image_bytes

                            )

                            if use_image:

                                return self.notifier._send_custom_webhook_image(

                                    image_bytes, fallback_content=report

                                )

                            return self.notifier.send_to_custom(report)



                        non_wechat_success = _send_channel_safely(

                            channel.value,

                            _send_custom_report,

                        ) or non_wechat_success

                    elif channel == NotificationChannel.PUSHPLUS:

                        non_wechat_success = _send_channel_safely(

                            channel.value,

                            lambda: self.notifier.send_to_pushplus(report),

                        ) or non_wechat_success

                    elif channel == NotificationChannel.SERVERCHAN3:

                        non_wechat_success = _send_channel_safely(

                            channel.value,

                            lambda: self.notifier.send_to_serverchan3(report),

                        ) or non_wechat_success

                    elif channel == NotificationChannel.DISCORD:

                        non_wechat_success = _send_channel_safely(

                            channel.value,

                            lambda: self.notifier.send_to_discord(report),

                        ) or non_wechat_success

                    elif channel == NotificationChannel.PUSHOVER:

                        non_wechat_success = _send_channel_safely(

                            channel.value,

                            lambda: self.notifier.send_to_pushover(report),

                        ) or non_wechat_success

                    elif channel == NotificationChannel.NTFY:

                        non_wechat_success = _send_channel_safely(

                            channel.value,

                            lambda: self.notifier.send_to_ntfy(report),

                        ) or non_wechat_success

                    elif channel == NotificationChannel.GOTIFY:

                        non_wechat_success = _send_channel_safely(

                            channel.value,

                            lambda: self.notifier.send_to_gotify(report),

                        ) or non_wechat_success

                    elif channel == NotificationChannel.ASTRBOT:

                        non_wechat_success = _send_channel_safely(

                            channel.value,

                            lambda: self.notifier.send_to_astrbot(report),

                        ) or non_wechat_success

                    elif channel == NotificationChannel.SLACK:

                        def _send_slack_report() -> bool:

                            use_image = self.notifier._should_use_image_for_channel(

                                channel, image_bytes

                            )

                            if use_image and self.notifier._slack_bot_token and self.notifier._slack_channel_id:

                                return self.notifier._send_slack_image(

                                    image_bytes, fallback_content=report

                                )

                            return self.notifier.send_to_slack(report)



                        non_wechat_success = _send_channel_safely(

                            channel.value,

                            _send_slack_report,

                        ) or non_wechat_success

                    else:

                        logger.warning(f"weizhinotificationqudao: {channel}")



                success = wechat_success or non_wechat_success or context_success

                if (

                    (wechat_success or non_wechat_success)

                    and noise_decision is not None

                    and hasattr(self.notifier, "record_noise_control")

                ):

                    self.notifier.record_noise_control(noise_decision)

                    noise_finalized = True

                elif (

                    noise_decision is not None

                    and hasattr(self.notifier, "release_noise_control")

                ):

                    self.notifier.release_noise_control(noise_decision)

                    noise_finalized = True

                if success:

                    logger.info("jueceyibiaopantuisongchenggong")

                else:

                    logger.warning("jueceyibiaopantuisongshibai")

            else:

                logger.info("notificationqudaoweiconfig(chinese removed)똳iaoguotuisong")

                

        except Exception as e:

            if (

                noise_decision is not None

                and not noise_finalized

                and hasattr(self.notifier, "release_noise_control")

            ):

                self.notifier.release_noise_control(noise_decision)

            import traceback

            logger.error(f"sendnotificationshibai: {e}\n{traceback.format_exc()}")



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


