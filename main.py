# -*- coding: utf-8 -*-

"""
===================================
A주 지능형 분석 시스템 - 메인 진입점
===================================

역할：
1. 각 모듈을 조율하여 주식 분석 흐름 완성
2. 다중 스레드/프로세스 스케줄링
3. 전역 예외 처리 - 실패필 경우 전체에 영향 없음
4. 명령줄 인터페이스 제공



사용fangshi：

    python main.py              # zhengchangyunxing

    python main.py --debug      # tiaoshimoshi

    python main.py --dry-run    # jinhuoqushujubufenxi



jiaoyilinian（yirongrufenxi）：

- yanjincelve：buzhuigao，guaililv > 5% bumairu

- qushijiaoyi：zhizuo MA5>MA10>MA20 duotoupailie

- xiaolvyouxian：guanzhuchoumajizhongduhaodegupiao

- maidianpianhao：suolianghuicai MA5/MA10 zhicheng

"""











































from __future__ import annotations



import os

from pathlib import Path

from typing import Any, Callable, Dict, List, Optional, Tuple



from dotenv import dotenv_values

from src.config import setup_env



_INITIAL_PROCESS_ENV = dict(os.environ)

setup_env()



# dailipeizhi - tongguo USE_PROXY huanjingbianliangkongzhi，morenguanbi

# GitHub Actions huanjingzidongtiaoguodailipeizhi

if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("USE_PROXY", "false").lower() == "true":

    # bendikaifahuanjing，qiyongdaili（kezai .env zhongpeizhi PROXY_HOST he PROXY_PORT）

    proxy_host = os.getenv("PROXY_HOST", "127.0.0.1")

    proxy_port = os.getenv("PROXY_PORT", "10809")

    proxy_url = f"http://{proxy_host}:{proxy_port}"

    os.environ["http_proxy"] = proxy_url

    os.environ["https_proxy"] = proxy_url



import argparse

import logging

import sys

import time

import uuid

from datetime import datetime, timezone, timedelta



from data_provider.base import canonical_stock_code

from src.webui_frontend import prepare_webui_frontend_assets

from src.config import get_config, Config

from src.logging_config import setup_logging





logger = logging.getLogger(__name__)

_RUNTIME_ENV_FILE_KEYS = set()





def _get_active_env_path() -> Path:

    env_file = os.getenv("ENV_FILE")

    if env_file:

        return Path(env_file)

    return Path(__file__).resolve().parent / ".env"





def _read_active_env_values() -> Optional[Dict[str, str]]:

    env_path = _get_active_env_path()

    if not env_path.exists():

        return {}



    try:

        values = dotenv_values(env_path)

    except Exception as exc:  # pragma: no cover - defensive branch

        logger.warning("duqupeizhiwenjian %s shibai，jixuyanyongdangqianhuanjingbianliang: %s", env_path, exc)

        return None



    return {

        str(key): "" if value is None else str(value)

        for key, value in values.items()

        if key is not None

    }





_ACTIVE_ENV_FILE_VALUES = _read_active_env_values() or {}

_RUNTIME_ENV_FILE_KEYS = {

    key for key in _ACTIVE_ENV_FILE_VALUES

    if key not in _INITIAL_PROCESS_ENV

}



# setup_env() already ran at import time above.

_env_bootstrapped = True





def _bootstrap_environment() -> None:

    """Load .env and apply optional local proxy settings.



    Guarded to be idempotent so it can safely be called from lazy-import

    paths used by API / bot consumers.

    """

    global _env_bootstrapped

    if _env_bootstrapped:

        return



    from src.config import setup_env



    setup_env()



    if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("USE_PROXY", "false").lower() == "true":

        proxy_host = os.getenv("PROXY_HOST", "127.0.0.1")

        proxy_port = os.getenv("PROXY_PORT", "10809")

        proxy_url = f"http://{proxy_host}:{proxy_port}"

        os.environ["http_proxy"] = proxy_url

        os.environ["https_proxy"] = proxy_url



    _env_bootstrapped = True





def _setup_bootstrap_logging(debug: bool = False) -> None:

    """Initialize stderr-only logging before config is loaded.



    File handlers are deferred until ``config.log_dir`` is known (via the

    subsequent ``setup_logging()`` call) so that healthy runs never create

    log files in a hard-coded directory.

    """

    level = logging.DEBUG if debug else logging.INFO

    root = logging.getLogger()

    root.setLevel(level)

    if not any(

        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr

        for h in root.handlers

    ):

        handler = logging.StreamHandler(sys.stderr)

        handler.setLevel(level)

        handler.setFormatter(

            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

        )

        root.addHandler(handler)





def _setup_runtime_logging(log_dir: str, debug: bool = False) -> bool:

    """Switch to configured logging, falling back to console on file I/O errors."""

    try:

        setup_logging(log_prefix="stock_analysis", debug=debug, log_dir=log_dir)

        return True

    except OSError as exc:

        logger.warning(

            "wenjianrizhichushihuashibai，yijiangjiweikongzhitairizhishuchu；rizhimulu %r dangqianbukexiehuobukechuangjian: %s。"

            "guanfang Docker jingxiangqidongrukouhuizidongxiufumorenguazaimuluquanxian；ruorengshibai，"

            "qingjianchashifoushiyongle --user、zhiduguazai、rootless Docker huo NFS dengxianzhixierudehuanjing。",

            log_dir,

            exc,

        )

        return False





def _get_stock_analysis_pipeline():

    """Lazily import StockAnalysisPipeline for external consumers.



    Also ensures env/proxy bootstrap has run so that API / bot consumers

    that never call ``main()`` still get ``USE_PROXY`` applied.

    """

    _bootstrap_environment()

    from src.core.pipeline import StockAnalysisPipeline as _Pipeline



    return _Pipeline





class _LazyPipelineDescriptor:

    """Descriptor that resolves StockAnalysisPipeline on first attribute access."""



    _resolved = None



    def __set_name__(self, owner, name):

        self._name = name



    def __get__(self, obj, objtype=None):

        if self._resolved is None:

            self._resolved = _get_stock_analysis_pipeline()

        return self._resolved





class _ModuleExports:

    StockAnalysisPipeline = _LazyPipelineDescriptor()





_exports = _ModuleExports()





def __getattr__(name: str):

    if name == "StockAnalysisPipeline":

        return _exports.StockAnalysisPipeline

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")





def _reload_env_file_values_preserving_overrides() -> None:

    """Refresh `.env`-managed env vars without clobbering process env overrides."""

    global _RUNTIME_ENV_FILE_KEYS



    latest_values = _read_active_env_values()

    if latest_values is None:

        return



    managed_keys = {

        key for key in latest_values

        if key not in _INITIAL_PROCESS_ENV

    }



    for key in _RUNTIME_ENV_FILE_KEYS - managed_keys:

        os.environ.pop(key, None)



    for key in managed_keys:

        os.environ[key] = latest_values[key]



    _RUNTIME_ENV_FILE_KEYS = managed_keys





def parse_arguments() -> argparse.Namespace:

    """jieximinglingxingcanshu"""

    parser = argparse.ArgumentParser(

        description='Aguzixuanguzhinengfenxixitong',

        formatter_class=argparse.RawDescriptionHelpFormatter,

        epilog='''

shili:

  python main.py                    # zhengchangyunxing

  python main.py --debug            # tiaoshimoshi

  python main.py --dry-run          # jinhuoqushuju，bujinxing AI fenxi

  python main.py --stocks 600519,000001  # zhidingfenxitedinggupiao

  python main.py --no-notify        # bufasongtuisongtongzhi

  python main.py --check-notify     # jianchatongzhipeizhi，bufasongtongzhi

  python main.py --single-notify    # qiyongdangutuisongmoshi（meifenxiwanyizhilijituisong）

  python main.py --schedule         # qiyongdingshirenwumoshi

  python main.py --market-review    # jinyunxingdapanfupan

        '''

    )



    parser.add_argument(

        '--debug',

        action='store_true',

        help='qiyongtiaoshimoshi，shuchuxiangxirizhi'

    )



    parser.add_argument(

        '--dry-run',

        action='store_true',

        help='jinhuoqushuju，bujinxing AI fenxi'

    )



    parser.add_argument(

        '--stocks',

        type=str,

        help='zhidingyaofenxidegupiaodaima，douhaofenge（fugaipeizhiwenjian）'

    )



    parser.add_argument(

        '--no-notify',

        action='store_true',

        help='bufasongtuisongtongzhi'

    )



    parser.add_argument(

        '--check-notify',

        action='store_true',

        help='zhidujianchatongzhiqudaopeizhi，bufasongtongzhi'

    )



    parser.add_argument(

        '--single-notify',

        action='store_true',

        help='qiyongdangutuisongmoshi：meifenxiwanyizhigupiaolijituisong，erbushihuizongtuisong'

    )



    parser.add_argument(

        '--workers',

        type=int,

        default=None,

        help='bingfaxianchengshu（morenshiyongpeizhizhi）'

    )



    parser.add_argument(

        '--schedule',

        action='store_true',

        help='qiyongdingshirenwumoshi，meiridingshizhixing'

    )



    parser.add_argument(

        '--no-run-immediately',

        action='store_true',

        help='dingshirenwuqidongshibulijizhixingyici'

    )



    parser.add_argument(

        '--market-review',

        action='store_true',

        help='jinyunxingdapanfupanfenxi'

    )



    parser.add_argument(

        '--no-market-review',

        action='store_true',

        help='tiaoguodapanfupanfenxi'

    )



    parser.add_argument(

        '--force-run',

        action='store_true',

        help='tiaoguojiaoyirijiancha，qiangzhizhixingquanliangfenxi（Issue #373）'

    )



    parser.add_argument(

        '--webui',

        action='store_true',

        help='qidong Web guanlijiemian'

    )



    parser.add_argument(

        '--webui-only',

        action='store_true',

        help='jinqidong Web fuwu，buzhixingzidongfenxi'

    )



    parser.add_argument(

        '--serve',

        action='store_true',

        help='qidong FastAPI houduanfuwu（tongshizhixingfenxirenwu）'

    )



    parser.add_argument(

        '--serve-only',

        action='store_true',

        help='jinqidong FastAPI houduanfuwu，buzidongzhixingfenxi'

    )



    parser.add_argument(

        '--port',

        type=int,

        default=8000,

        help='FastAPI fuwuduankou（moren 8000）'

    )



    parser.add_argument(

        '--host',

        type=str,

        default='0.0.0.0',

        help='FastAPI fuwujiantingdizhi（moren 0.0.0.0）'

    )



    parser.add_argument(

        '--no-context-snapshot',

        action='store_true',

        help='bubaocunfenxishangxiawenkuaizhao'

    )



    # === Backtest ===

    parser.add_argument(

        '--backtest',

        action='store_true',

        help='yunxinghuice（duilishifenxijieguojinxingpinggu）'

    )



    parser.add_argument(

        '--backtest-code',

        type=str,

        default=None,

        help='jinhuicezhidinggupiaodaima'

    )



    parser.add_argument(

        '--backtest-days',

        type=int,

        default=None,

        help='huicepingguchuangkou（jiaoyirishu，morenshiyongpeizhi）'

    )



    parser.add_argument(

        '--backtest-force',

        action='store_true',

        help='qiangzhihuice（jishiyiyouhuicejieguoyechongxinjisuan）'

    )



    return parser.parse_args()





def _compute_trading_day_filter(

    config: Config,

    args: argparse.Namespace,

    stock_codes: List[str],

) -> Tuple[List[str], Optional[str], bool]:

    """

    Compute filtered stock list and effective market review region (Issue #373).



    Returns:

        (filtered_codes, effective_region, should_skip_all)

        - effective_region None = use config default (check disabled)

        - effective_region '' = all relevant markets closed, skip market review

        - should_skip_all: skip entire run when no stocks and no market review to run

    """

    force_run = getattr(args, 'force_run', False)

    if force_run or not getattr(config, 'trading_day_check_enabled', True):

        return (stock_codes, None, False)



    from src.core.trading_calendar import (

        get_market_for_stock,

        get_open_markets_today,

        compute_effective_region,

    )



    open_markets = get_open_markets_today()

    filtered_codes = []

    for code in stock_codes:

        mkt = get_market_for_stock(code)

        if mkt in open_markets or mkt is None:

            filtered_codes.append(code)



    if config.market_review_enabled and not getattr(args, 'no_market_review', False):

        effective_region = compute_effective_region(

            getattr(config, 'market_review_region', 'cn') or 'cn', open_markets

        )

    else:

        effective_region = None



    should_skip_all = (not filtered_codes) and (effective_region or '') == ''

    return (filtered_codes, effective_region, should_skip_all)





def _run_market_review_with_shared_lock(

    config: Config,

    run_market_review_func: Callable[..., Optional[str]],

    **kwargs: Any,

) -> Optional[str]:

    from src.core.market_review_lock import (

        release_market_review_lock,

        try_acquire_market_review_lock,

    )



    lock_token = try_acquire_market_review_lock(config)

    if lock_token is None:

        logger.warning("dapanfupanzhengzaizhixingzhong，tiaoguobencidapanfupan")

        return None



    try:

        return run_market_review_func(**kwargs)

    finally:

        release_market_review_lock(lock_token)





def run_full_analysis(

    config: Config,

    args: argparse.Namespace,

    stock_codes: Optional[List[str]] = None

):

    """

    zhixingwanzhengdefenxi흐름（gegu + dapanfupan）



    zheshidingshirenwudiaoyongdezhuhanshu

    """









    # Import pipeline modules outside the broad try/except so that import-time

    # failures propagate to the caller instead of being silently swallowed.

    from src.core.market_review import run_market_review

    from src.core.pipeline import StockAnalysisPipeline



    try:

        # Issue #529: Hot-reload STOCK_LIST from .env on each scheduled run

        if stock_codes is None:

            config.refresh_stock_list()



        # Issue #373: Trading day filter (per-stock, per-market)

        effective_codes = stock_codes if stock_codes is not None else config.stock_list

        filtered_codes, effective_region, should_skip = _compute_trading_day_filter(

            config, args, effective_codes

        )

        if should_skip:

            logger.info(

                "jinrisuoyouxiangguanshichangjunweifeijiaoyiri，tiaoguozhixing。keshiyong --force-run qiangzhizhixing。"

            )

            return

        if set(filtered_codes) != set(effective_codes):

            skipped = set(effective_codes) - set(filtered_codes)

            logger.info("jinrixiushigupiaoyitiaoguo: %s", skipped)

        stock_codes = filtered_codes



        # minglingxingcanshu --single-notify fugaipeizhi（#55）

        if getattr(args, 'single_notify', False):

            config.single_stock_notify = True



        # Issue #190: geguyudapanfupanhebingtuisong

        merge_notification = (

            getattr(config, 'merge_email_notification', False)

            and config.market_review_enabled

            and not getattr(args, 'no_market_review', False)

            and not config.single_stock_notify

        )



        # chuangjiandiaoduqi

        save_context_snapshot = None

        if getattr(args, 'no_context_snapshot', False):

            save_context_snapshot = False

        query_id = uuid.uuid4().hex

        pipeline = StockAnalysisPipeline(

            config=config,

            max_workers=args.workers,

            query_id=query_id,

            query_source="cli",

            save_context_snapshot=save_context_snapshot

        )



        # 1. yunxinggegufenxi

        results = pipeline.run(

            stock_codes=stock_codes,

            dry_run=args.dry_run,

            send_notification=not args.no_notify,

            merge_notification=merge_notification

        )



        # Issue #128: fenxijiange - zaigegufenxihedapanfenxizhijiantianjiayanchi

        analysis_delay = getattr(config, 'analysis_delay', 0)

        if (

            analysis_delay > 0

            and config.market_review_enabled

            and not args.no_market_review

            and effective_region != ''

        ):

            logger.info(f"dengdai {analysis_delay} miaohouzhixingdapanfupan（bimianAPIxianliu）...")

            time.sleep(analysis_delay)



        # 2. yunxingdapanfupan（ruguoqiyongqiebushijingegumoshi）

        market_report = ""

        if (

            config.market_review_enabled

            and not args.no_market_review

            and effective_region != ''

        ):

            review_result = _run_market_review_with_shared_lock(

                config,

                run_market_review,

                notifier=pipeline.notifier,

                analyzer=pipeline.analyzer,

                search_service=pipeline.search_service,

                send_notification=not args.no_notify,

                merge_notification=merge_notification,

                override_region=effective_region,

            )

            # ruguoyoujieguo，fuzhigei market_report yongyuhouxufeishuwendangshengcheng

            if review_result:

                market_report = review_result



        # Issue #190: hebingtuisong（gegu+dapanfupan）

        if merge_notification and (results or market_report) and not args.no_notify:

            parts = []

            if market_report:

                parts.append(f"# 📈 dapanfupan\n\n{market_report}")

            if results:

                dashboard_content = pipeline.notifier.generate_aggregate_report(

                    results,

                    getattr(config, 'report_type', 'simple'),

                )

                parts.append(f"# 🚀 gegujueceyibiaopan\n\n{dashboard_content}")

            if parts:

                combined_content = "\n\n---\n\n".join(parts)

                if pipeline.notifier.is_available():

                    if pipeline.notifier.send(combined_content, email_send_to_all=True, route_type="report"):

                        logger.info("yihebingtuisong（gegu+dapanfupan）")

                    else:

                        logger.warning("hebingtuisongshibai")



        # shuchuzhaiyao

        if results:

            logger.info("\n===== fenxijieguozhaiyao =====")

            for r in sorted(results, key=lambda x: x.sentiment_score, reverse=True):

                emoji = r.get_emoji()

                logger.info(

                    f"{emoji} {r.name}({r.code}): {r.operation_advice} | "

                    f"pingfen {r.sentiment_score} | {r.trend_prediction}"

                )



        logger.info("\nrenwuzhixingwancheng")



        # === xinzeng：shengchengfeishuyunwendang ===

        try:

            from src.feishu_doc import FeishuDocManager



            feishu_doc = FeishuDocManager()

            if feishu_doc.is_configured() and (results or market_report):

                logger.info("zhengzaichuangjianfeishuyunwendang...")



                # 1. zhunbeibiaoti "01-01 13:01dapanfupan"

                tz_cn = timezone(timedelta(hours=8))

                now = datetime.now(tz_cn)

                doc_title = f"{now.strftime('%Y-%m-%d %H:%M')} dapanfupan"



                # 2. zhunbeineirong (pinjiegegufenxihedapanfupan)

                full_content = ""



                # tianjiadapanfupanneirong（ruguoyou）

                if market_report:

                    full_content += f"# 📈 dapanfupan\n\n{market_report}\n\n---\n\n"



                # tianjiagegujueceyibiaopan（shiyong NotificationService shengcheng，an report_type fenzhi）

                if results:

                    dashboard_content = pipeline.notifier.generate_aggregate_report(

                        results,

                        getattr(config, 'report_type', 'simple'),

                    )

                    full_content += f"# 🚀 gegujueceyibiaopan\n\n{dashboard_content}"



                # 3. chuangjianwendang

                doc_url = feishu_doc.create_daily_doc(doc_title, full_content)

                if doc_url:

                    logger.info(f"feishuyunwendangchuangjianchenggong: {doc_url}")

                    # kexuan：jiangwendanglianjieyetuisongdaoqunli

                    if not args.no_notify:

                        pipeline.notifier.send(

                            f"[{now.strftime('%Y-%m-%d %H:%M')}] fupanwendangchuangjianchenggong: {doc_url}",

                            route_type="report",

                        )



        except Exception as e:

            logger.error(f"feishuwendangshengchengshibai: {e}")



        # === Auto backtest ===

        try:

            if getattr(config, 'backtest_enabled', False):

                from src.services.backtest_service import BacktestService



                logger.info("kaishizidonghuice...")

                service = BacktestService()

                stats = service.run_backtest(

                    force=False,

                    eval_window_days=getattr(config, 'backtest_eval_window_days', 10),

                    min_age_days=getattr(config, 'backtest_min_age_days', 14),

                    limit=200,

                )

                logger.info(

                    f"zidonghuicewancheng: processed={stats.get('processed')} saved={stats.get('saved')} "

                    f"completed={stats.get('completed')} insufficient={stats.get('insufficient')} errors={stats.get('errors')}"

                )

        except Exception as e:

            logger.warning(f"zidonghuiceshibai（yihulve）: {e}")



    except Exception as e:

        logger.exception(f"fenxiliuchengzhixingshibai: {e}")





def start_api_server(host: str, port: int, config: Config) -> None:

    """

    zaihoutaixianchengqidong FastAPI fuwu



    Args:

        host: jiantingdizhi

        port: jiantingduankou

        config: peizhiduixiang

    """

    import threading

    import uvicorn



    def run_server():

        level_name = (config.log_level or "INFO").lower()

        uvicorn.run(

            "api.app:app",

            host=host,

            port=port,

            log_level=level_name,

            log_config=None,

        )



    thread = threading.Thread(target=run_server, daemon=True)

    thread.start()

    logger.info(f"FastAPI fuwuyiqidong: http://{host}:{port}")





def _is_truthy_env(var_name: str, default: str = "true") -> bool:

    """Parse common truthy / falsy environment values."""

    value = os.getenv(var_name, default).strip().lower()

    return value not in {"0", "false", "no", "off"}





def start_bot_stream_clients(config: Config) -> None:

    """Start bot stream clients when enabled in config."""

    # qidongdingding Stream kehuduan

    if config.dingtalk_stream_enabled:

        try:

            from bot.platforms import start_dingtalk_stream_background, DINGTALK_STREAM_AVAILABLE

            if DINGTALK_STREAM_AVAILABLE:

                if start_dingtalk_stream_background():

                    logger.info("[Main] Dingtalk Stream client started in background.")

                else:

                    logger.warning("[Main] Dingtalk Stream client failed to start.")

            else:

                logger.warning("[Main] Dingtalk Stream enabled but SDK is missing.")

                logger.warning("[Main] Run: pip install dingtalk-stream")

        except Exception as exc:

            logger.error(f"[Main] Failed to start Dingtalk Stream client: {exc}")



    # qidongfeishu Stream kehuduan

    if getattr(config, 'feishu_stream_enabled', False):

        try:

            from bot.platforms import start_feishu_stream_background, FEISHU_SDK_AVAILABLE

            if FEISHU_SDK_AVAILABLE:

                if start_feishu_stream_background():

                    logger.info("[Main] Feishu Stream client started in background.")

                else:

                    logger.warning("[Main] Feishu Stream client failed to start.")

            else:

                logger.warning("[Main] Feishu Stream enabled but SDK is missing.")

                logger.warning("[Main] Run: pip install lark-oapi")

        except Exception as exc:

            logger.error(f"[Main] Failed to start Feishu Stream client: {exc}")





def _resolve_scheduled_stock_codes(stock_codes: Optional[List[str]]) -> Optional[List[str]]:

    """Scheduled runs should always read the latest persisted watchlist."""

    if stock_codes is not None:

        logger.warning(

            "dingshimoshixiajiancedao --stocks canshu；jihuazhixingjianghulveqidongshigupiaokuaizhao，bingzaimeiciyunxingqianchongxinduquzuixinde STOCK_LIST。"

        )

    return None





def _reload_runtime_config() -> Config:

    """Reload config from the latest persisted `.env` values for scheduled runs."""

    _reload_env_file_values_preserving_overrides()

    Config.reset_instance()

    return get_config()





def _build_schedule_time_provider(default_schedule_time: str):

    """Read the latest schedule time directly from the active config file.



    Fallback order:

    1. Process-level env override (set before launch) → honour it.

    2. Persisted config file value (written by WebUI) → use it.

    3. Documented system default ``"18:00"`` → always fall back here so

       that clearing SCHEDULE_TIME in WebUI correctly resets the schedule.

    """

    from src.core.config_manager import ConfigManager



    _SYSTEM_DEFAULT_SCHEDULE_TIME = "18:00"

    manager = ConfigManager()



    def _provider() -> str:

        if "SCHEDULE_TIME" in _INITIAL_PROCESS_ENV:

            return os.getenv("SCHEDULE_TIME", default_schedule_time)



        config_map = manager.read_config_map()

        schedule_time = (config_map.get("SCHEDULE_TIME", "") or "").strip()

        if schedule_time:

            return schedule_time

        return _SYSTEM_DEFAULT_SCHEDULE_TIME



    return _provider





def main() -> int:

    """

    zhurukouhanshu



    Returns:

        tuichuma（0 biaoshichenggong）

    """

    # jieximinglingxingcanshu

    args = parse_arguments()



    # zaipeizhijiazaiqianxianchushihua bootstrap rizhi，quebaozaoqishibaiyenengluopan

    try:

        _setup_bootstrap_logging(debug=args.debug)

    except Exception as exc:

        logging.basicConfig(

            level=logging.DEBUG if getattr(args, "debug", False) else logging.INFO,

            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",

            stream=sys.stderr,

        )

        logger.warning("Bootstrap rizhichushihuashibai，yihuituidao stderr: %s", exc)



    # jiazaipeizhi（zai bootstrap logging zhihouzhixing，quebaoyichangyourizhi）

    try:

        config = get_config()

    except Exception as exc:

        logger.exception("jiazaipeizhishibai: %s", exc)

        return 1



    # peizhirizhi（shuchudaokongzhitaihewenjian）

    try:

        _setup_runtime_logging(config.log_dir, debug=args.debug)

    except Exception as exc:

        logger.exception("qiehuandaopeizhirizhimulushibai: %s", exc)

        return 1



    logger.info("=" * 60)

    logger.info("Aguzixuanguzhinengfenxixitong qidong")

    logger.info(f"yunxingshijian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    logger.info("=" * 60)



    # yanzhengpeizhi

    warnings = config.validate()

    for warning in warnings:

        logger.warning(warning)



    if getattr(args, "check_notify", False):

        from src.services.notification_diagnostics import (

            format_notification_diagnostics,

            run_notification_diagnostics,

        )



        result = run_notification_diagnostics(config)

        print(format_notification_diagnostics(result))

        return 0 if result.ok else 1



    # jiexigupiaoliebiao（tongyiweidaxie Issue #355）

    stock_codes = None

    if args.stocks:

        stock_codes = [canonical_stock_code(c) for c in args.stocks.split(',') if (c or "").strip()]

        logger.info(f"shiyongminglingxingzhidingdegupiaoliebiao: {stock_codes}")



    # === chuli --webui / --webui-only canshu，yingshedao --serve / --serve-only ===

    if args.webui:

        args.serve = True

    if args.webui_only:

        args.serve_only = True



    # jianrongjiuban WEBUI_ENABLED huanjingbianliang

    if config.webui_enabled and not (args.serve or args.serve_only):

        args.serve = True



    # === qidong Web fuwu (ruguoqiyong) ===

    start_serve = (args.serve or args.serve_only) and os.getenv("GITHUB_ACTIONS") != "true"



    # jianrongjiuban WEBUI_HOST/WEBUI_PORT：ruguoyonghuweitongguo --host/--port zhiding，zeshiyongjiubianliang

    if start_serve:

        if args.host == '0.0.0.0' and os.getenv('WEBUI_HOST'):

            args.host = os.getenv('WEBUI_HOST')

        if args.port == 8000 and os.getenv('WEBUI_PORT'):

            args.port = int(os.getenv('WEBUI_PORT'))



    bot_clients_started = False

    if start_serve:

        if not prepare_webui_frontend_assets():

            logger.warning("qianduanjingtaiziyuanweijiuxu，jixuqidong FastAPI fuwu（Web yemiankenengbukeyong）")

        try:

            start_api_server(host=args.host, port=args.port, config=config)

            bot_clients_started = True

        except Exception as e:

            logger.error(f"qidong FastAPI fuwushibai: {e}")



    if bot_clients_started:

        start_bot_stream_clients(config)



    # === jin Web fuwumoshi：buzidongzhixingfenxi ===

    if args.serve_only:

        logger.info("moshi: jin Web fuwu")

        logger.info(f"Web fuwuyunxingzhong: http://{args.host}:{args.port}")

        logger.info("tongguo /api/v1/analysis/analyze jiekouchufafenxi")

        logger.info(f"API wendang: http://{args.host}:{args.port}/docs")

        logger.info("an Ctrl+C tuichu...")

        try:

            while True:

                time.sleep(1)

        except KeyboardInterrupt:

            logger.info("\nyonghuzhongduan，chengxutuichu")

        return 0



    try:

        # moshi0: huice

        if getattr(args, 'backtest', False):

            logger.info("moshi: huice")

            from src.services.backtest_service import BacktestService



            service = BacktestService()

            stats = service.run_backtest(

                code=getattr(args, 'backtest_code', None),

                force=getattr(args, 'backtest_force', False),

                eval_window_days=getattr(args, 'backtest_days', None),

            )

            logger.info(

                f"huicewancheng: processed={stats.get('processed')} saved={stats.get('saved')} "

                f"completed={stats.get('completed')} insufficient={stats.get('insufficient')} errors={stats.get('errors')}"

            )

            return 0



        # moshi1: jindapanfupan

        if args.market_review:

            from src.core.market_review import run_market_review

            from src.core.market_review_runtime import build_market_review_runtime



            # Issue #373: Trading day check for market-review-only mode.

            # Do NOT use _compute_trading_day_filter here: that helper checks

            # config.market_review_enabled, which would wrongly block an

            # explicit --market-review invocation when the flag is disabled.

            effective_region = None

            if not getattr(args, 'force_run', False) and getattr(config, 'trading_day_check_enabled', True):

                from src.core.trading_calendar import get_open_markets_today, compute_effective_region as _compute_region

                open_markets = get_open_markets_today()

                effective_region = _compute_region(

                    getattr(config, 'market_review_region', 'cn') or 'cn', open_markets

                )

                if effective_region == '':

                    logger.info("jinridapanfupanxiangguanshichangjunweifeijiaoyiri，tiaoguozhixing。keshiyong --force-run qiangzhizhixing。")

                    return 0



            logger.info("moshi: jindapanfupan")

            notifier, analyzer, search_service = build_market_review_runtime(config)



            _run_market_review_with_shared_lock(

                config,

                run_market_review,

                notifier=notifier,

                analyzer=analyzer,

                search_service=search_service,

                send_notification=not args.no_notify,

                override_region=effective_region,

            )

            return 0



        # moshi2: dingshirenwumoshi

        if args.schedule or config.schedule_enabled:

            logger.info("moshi: dingshirenwu")

            logger.info(f"meirizhixingshijian: {config.schedule_time}")



            # Determine whether to run immediately:

            # Command line arg --no-run-immediately overrides config if present.

            # Otherwise use config (defaults to True).

            should_run_immediately = config.schedule_run_immediately

            if getattr(args, 'no_run_immediately', False):

                should_run_immediately = False



            logger.info(f"qidongshilijizhixing: {should_run_immediately}")



            from src.scheduler import run_with_schedule

            scheduled_stock_codes = _resolve_scheduled_stock_codes(stock_codes)

            schedule_time_provider = _build_schedule_time_provider(config.schedule_time)



            def scheduled_task():

                runtime_config = _reload_runtime_config()

                run_full_analysis(runtime_config, args, scheduled_stock_codes)



            background_tasks = []

            if getattr(config, 'agent_event_monitor_enabled', False):

                from src.services.alert_worker import AlertWorker



                interval_minutes = max(1, getattr(config, 'agent_event_monitor_interval_minutes', 5))

                alert_worker = AlertWorker(config_provider=_reload_runtime_config)



                def event_monitor_task():

                    stats = alert_worker.run_once()

                    triggered_count = stats.get("triggered", 0)

                    if triggered_count:

                        logger.info("[EventMonitor] benlunchufa %d tiaotixing", triggered_count)



                background_tasks.append({

                    "task": event_monitor_task,

                    "interval_seconds": interval_minutes * 60,

                    "run_immediately": True,

                    "name": "agent_event_monitor",

                })



            run_with_schedule(

                task=scheduled_task,

                schedule_time=config.schedule_time,

                run_immediately=should_run_immediately,

                background_tasks=background_tasks,

                schedule_time_provider=schedule_time_provider,

            )

            return 0



        # moshi3: zhengchangdanciyunxing

        if config.run_immediately:

            run_full_analysis(config, args, stock_codes)

        else:

            logger.info("peizhiweibulijiyunxingfenxi (RUN_IMMEDIATELY=false)")



        logger.info("\nchengxuzhixingwancheng")



        # ruguoqiyonglefuwuqieshifeidingshirenwumoshi，baochichengxuyunxing

        keep_running = start_serve and not (args.schedule or config.schedule_enabled)

        if keep_running:

            logger.info("API fuwuyunxingzhong (an Ctrl+C tuichu)...")

            try:

                while True:

                    time.sleep(1)

            except KeyboardInterrupt:

                pass



        return 0



    except KeyboardInterrupt:

        logger.info("\nyonghuzhongduan，chengxutuichu")

        return 130



    except Exception as e:

        logger.exception(f"chengxuzhixingshibai: {e}")

        return 1





if __name__ == "__main__":

    sys.exit(main())

