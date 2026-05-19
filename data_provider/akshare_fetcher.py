# -*- coding: utf-8 -*-
"""
===================================
AkshareFetcher - zhushujuyuan (Priority 1)
===================================

shujulaiyuan：
1. dongfangcaifupachong（tongguo akshare ku） - morenshujuyuan
2. xinlangcaijingjiekou - beixuanshujuyuan
3. tengxuncaijingjiekou - beixuanshujuyuan

tedian：mianfei、wuxu Token、shujuquanmian
fengxian：pachongjizhiyibeifanpafengjin

fangfengjincelve：
1. meiciqingqiuqiansuijixiumian 2-5 miao
2. suijilunhuan User-Agent
3. shiyong tenacity shixianzhishutuibizhongshi
4. rongduanqijizhi：lianxushibaihouzidonglengque

zengqiangshuju：
- shishixingqing：liangbi、huanshoulv、shiyinglv、shijinglv、zongshizhi、liutongshizhi
- choumafenbu：huolibili、pingjunchengben、choumajizhongdu
"""

import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from src.patches.eastmoney_patch import eastmoney_patch
from src.config import get_config
from .base import BaseFetcher, DataFetchError, RateLimitError, STANDARD_COLUMNS, is_bse_code, is_st_stock, is_kc_cy_stock, normalize_stock_code
from .realtime_types import (
    UnifiedRealtimeQuote, ChipDistribution, RealtimeSource,
    get_realtime_circuit_breaker, get_chip_circuit_breaker,
    safe_float, safe_int  # shiyongtongyideleixingzhuanhuanhanshu
)
from .us_index_mapping import is_us_index_code, is_us_stock_code


# baoliujiude RealtimeQuote bieming，yongyuxianghoujianrong
RealtimeQuote = UnifiedRealtimeQuote


logger = logging.getLogger(__name__)

SINA_REALTIME_ENDPOINT = "hq.sinajs.cn/list"
TENCENT_REALTIME_ENDPOINT = "qt.gtimg.cn/q"


# User-Agent chi，yongyusuijilunhuan
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


# huancunshishixingqingshuju（bimianchongfuqingqiu）
# TTL shewei 20 fenzhong (1200miao)：
# - piliangfenxichangjing：tongchang 30 zhigupiaozai 5 fenzhongneifenxiwan，20 fenzhongzugoufugai
# - shishixingyaoqiu：gupiaofenxibuxuyaomiaojishishishuju，20 fenzhongyanchikejieshou
# - fangfengjin：jianshao API diaoyongpinlv
_realtime_cache: Dict[str, Any] = {
    'data': None,
    'timestamp': 0,
    'ttl': 1200  # 20fenzhonghuancunyouxiaoqi
}

# ETF shishixingqinghuancun
_etf_realtime_cache: Dict[str, Any] = {
    'data': None,
    'timestamp': 0,
    'ttl': 1200  # 20fenzhonghuancunyouxiaoqi
}


def _is_etf_code(stock_code: str) -> bool:
    """
    panduandaimashifouwei ETF jijin
    
    ETF daimaguize：
    - shangjiaosuo ETF: 51xxxx, 52xxxx, 56xxxx, 58xxxx
    - shenjiaosuo ETF: 15xxxx, 16xxxx, 18xxxx
    
    Args:
        stock_code: gupiao/jijindaima
        
    Returns:
        True biaoshishi ETF daima，False biaoshishiputonggupiaodaima
    """
    etf_prefixes = ('51', '52', '56', '58', '15', '16', '18')
    code = stock_code.strip().split('.')[0]
    return code.startswith(etf_prefixes) and len(code) == 6


def _is_hk_code(stock_code: str) -> bool:
    """
    panduandaimashifouweiganggu

    ganggudaimaguize：
    - 5weishuzidaima，ru '00700' (tengxunkonggu)
    - bufenganggudaimakenengdaiyouqianzhui，ru 'hk00700', 'hk1810'

    Args:
        stock_code: gupiaodaima

    Returns:
        True biaoshishiganggudaima，False biaoshibushiganggudaima
    """
    # quchukenengde 'hk' qianzhuibingjianchashifouweichunshuzi
    code = stock_code.strip().lower()
    if code.endswith('.hk'):
        numeric_part = code[:-3]
        return numeric_part.isdigit() and 1 <= len(numeric_part) <= 5
    if code.startswith('hk'):
        # dai hk qianzhuideyidingshiganggu，qudiaoqianzhuihouyingweichunshuzi（1-5wei）
        numeric_part = code[2:]
        return numeric_part.isdigit() and 1 <= len(numeric_part) <= 5
    # wuqianzhuishi，5weichunshuzicaishiweiganggu（bimianwupan A gudaima）
    return code.isdigit() and len(code) == 5


def is_hk_stock_code(stock_code: str) -> bool:
    """
    Public API: determine if a stock code is a Hong Kong stock.

    Delegates to _is_hk_code for internal compatibility.

    Args:
        stock_code: Stock code (e.g. '00700', 'hk00700')

    Returns:
        True if HK stock, False otherwise
    """
    return _is_hk_code(stock_code)


def _is_us_code(stock_code: str) -> bool:
    """
    panduandaimashifouweimeigugupiao（bubaokuomeiguzhishu）。

    weituogei us_index_mapping mokuaide is_us_stock_code()。

    Args:
        stock_code: gupiaodaima

    Returns:
        True biaoshishimeigudaima，False biaoshibushimeigudaima

    Examples:
        >>> _is_us_code('AAPL')
        True
        >>> _is_us_code('TSLA')
        True
        >>> _is_us_code('SPX')
        False
        >>> _is_us_code('600519')
        False
    """
    return is_us_stock_code(stock_code)


def _to_sina_tx_symbol(stock_code: str) -> str:
    """Convert 6-digit A-share code to sh/sz/bj prefixed symbol for Sina/Tencent APIs."""
    base = (stock_code.strip().split(".")[0] if "." in stock_code else stock_code).strip()
    if is_bse_code(base):
        return f"bj{base}"
    # Shanghai: 60xxxx, 5xxxx (ETF), 90xxxx (B-shares)
    if base.startswith(("6", "5", "90")):
        return f"sh{base}"
    return f"sz{base}"


def _classify_realtime_http_error(exc: Exception) -> Tuple[str, str]:
    """
    Classify Sina/Tencent realtime quote failures into stable categories.
    """
    detail = str(exc).strip() or type(exc).__name__
    lowered = detail.lower()

    remote_disconnect_keywords = (
        "remotedisconnected",
        "remote end closed connection without response",
        "connection aborted",
        "connection broken",
        "protocolerror",
        "chunkedencodingerror",
    )
    timeout_keywords = (
        "timeout",
        "timed out",
        "readtimeout",
        "connecttimeout",
    )
    rate_limit_keywords = (
        "banned",
        "blocked",
        "pinlv",
        "rate limit",
        "too many requests",
        "429",
        "xianzhi",
        "forbidden",
        "403",
    )

    if any(keyword in lowered for keyword in remote_disconnect_keywords):
        return "remote_disconnect", detail
    if isinstance(exc, (TimeoutError, requests.exceptions.Timeout)) or any(
        keyword in lowered for keyword in timeout_keywords
    ):
        return "timeout", detail
    if any(keyword in lowered for keyword in rate_limit_keywords):
        return "rate_limit_or_anti_bot", detail
    if isinstance(exc, requests.exceptions.RequestException):
        return "request_error", detail
    return "unknown_request_error", detail


def _build_realtime_failure_message(
    source_name: str,
    endpoint: str,
    stock_code: str,
    symbol: str,
    category: str,
    detail: str,
    elapsed: float,
    error_type: str,
) -> str:
    return (
        f"{source_name} shishixingqingjiekoushibai: endpoint={endpoint}, stock_code={stock_code}, "
        f"symbol={symbol}, category={category}, error_type={error_type}, "
        f"elapsed={elapsed:.2f}s, detail={detail}"
    )


class AkshareFetcher(BaseFetcher):
    """
    Akshare shujuyuanshixian
    
    youxianji：1（zuigao）
    shujulaiyuan：dongfangcaifuwangpachong
    
    guanjiancelve：
    - meiciqingqiuqiansuijixiumian 2.0-5.0 miao
    - suiji User-Agent lunhuan
    - shibaihouzhishutuibizhongshi（zuiduo3ci）
    """
    
    name = "AkshareFetcher"
    priority = int(os.getenv("AKSHARE_PRIORITY", "1"))
    
    def __init__(self, sleep_min: float = 2.0, sleep_max: float = 5.0):
        """
        chushihua AkshareFetcher
        
        Args:
            sleep_min: zuixiaoxiumianshijian（miao）
            sleep_max: zuidaxiumianshijian（miao）
        """
        self.sleep_min = sleep_min
        self.sleep_max = sleep_max
        self._last_request_time: Optional[float] = None
        # dongcaibudingkaiqicaizhixingdabudingcaozuo
        if get_config().enable_eastmoney_patch:
            eastmoney_patch()
    
    def _set_random_user_agent(self) -> None:
        """
        shezhisuiji User-Agent
        
        tongguoxiugai requests Session de headers shixian
        zheshiguanjiandefanpacelvezhiyi
        """
        try:
            import akshare as ak
            # akshare neibushiyong requests，womentongguohuanjingbianlianghuozhijieshezhilaiyingxiang
            # shijishang akshare kenengbuzhijiebaolu session，zhelitongguo fake_useragent zuoweibuchong
            random_ua = random.choice(USER_AGENTS)
            logger.debug(f"shezhi User-Agent: {random_ua[:50]}...")
        except Exception as e:
            logger.debug(f"shezhi User-Agent shibai: {e}")
    
    def _enforce_rate_limit(self) -> None:
        """
        qiangzhizhixingsulvxianzhi
        
        celve：
        1. jianchajulishangciqingqiudeshijianjiange
        2. ruguojiangebuzu，buchongxiumianshijian
        3. ranhouzaizhixingsuiji jitter xiumian
        """
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            min_interval = self.sleep_min
            if elapsed < min_interval:
                additional_sleep = min_interval - elapsed
                logger.debug(f"buchongxiumian {additional_sleep:.2f} miao")
                time.sleep(additional_sleep)
        
        # zhixingsuiji jitter xiumian
        self.random_sleep(self.sleep_min, self.sleep_max)
        self._last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(3),  # zuiduozhongshi3ci
        wait=wait_exponential(multiplier=1, min=2, max=30),  # zhishutuibi：2, 4, 8... zuida30miao
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        cong Akshare huoquyuanshishuju
        
        genjudaimaleixingzidongxuanze API：
        - meigu：buzhichi，paochuyichangyou YfinanceFetcher chuli（Issue #311）
        - ganggu：shiyong ak.stock_hk_hist()
        - ETF jijin：shiyong ak.fund_etf_hist_em()
        - putong A gu：shiyong ak.stock_zh_a_hist()
        
        liucheng：
        1. panduandaimaleixing（meigu/ganggu/ETF/Agu）
        2. shezhisuiji User-Agent
        3. zhixingsulvxianzhi（suijixiumian）
        4. diaoyongduiyingde akshare API
        5. chulifanhuishuju
        """
        # genjudaimaleixingxuanzebutongdehuoqufangfa
        if _is_us_code(stock_code):
            # meigu：akshare de stock_us_daily jiekoufuquancunzaiyizhiwenti（canjian Issue #311）
            # jiaoyou YfinanceFetcher chuli，quebaofuquanjiageyizhi
            raise DataFetchError(
                f"AkshareFetcher buzhichimeigu {stock_code}，qingshiyong YfinanceFetcher huoquzhengquedefuquanjiage"
            )
        elif _is_hk_code(stock_code):
            return self._fetch_hk_data(stock_code, start_date, end_date)
        elif _is_etf_code(stock_code):
            return self._fetch_etf_data(stock_code, start_date, end_date)
        else:
            return self._fetch_stock_data(stock_code, start_date, end_date)
    
    def _fetch_stock_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        huoquputong A gulishishuju

        celve：
        1. youxianchangshidongfangcaifujiekou (ak.stock_zh_a_hist)
        2. shibaihouchangshixinlangcaijingjiekou (ak.stock_zh_a_daily)
        3. zuihouchangshitengxuncaijingjiekou (ak.stock_zh_a_hist_tx)
        """
        # changshiliebiao
        methods = [
            (self._fetch_stock_data_em, "dongfangcaifu"),
            (self._fetch_stock_data_sina, "xinlangcaijing"),
            (self._fetch_stock_data_tx, "tengxuncaijing"),
        ]

        last_error = None

        for fetch_method, source_name in methods:
            try:
                logger.info(f"[shujuyuan] changshishiyong {source_name} huoqu {stock_code}...")
                df = fetch_method(stock_code, start_date, end_date)

                if df is not None and not df.empty:
                    logger.info(f"[shujuyuan] {source_name} huoquchenggong")
                    return df
            except Exception as e:
                last_error = e
                logger.warning(f"[shujuyuan] {source_name} huoqushibai: {e}")
                # jixuchangshixiayige

        # suoyoudoushibai
        raise DataFetchError(f"Akshare suoyouqudaohuoqushibai: {last_error}")

    def _fetch_stock_data_em(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        huoquputong A gulishishuju (dongfangcaifu)
        shujulaiyuan：ak.stock_zh_a_hist()
        """
        import akshare as ak

        # fangfengjincelve 1: suiji User-Agent
        self._set_random_user_agent()

        # fangfengjincelve 2: qiangzhixiumian
        self._enforce_rate_limit()

        logger.info(f"[APIdiaoyong] ak.stock_zh_a_hist(symbol={stock_code}, ...)")

        try:
            import time as _time
            api_start = _time.time()

            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq"
            )

            api_elapsed = _time.time() - api_start

            if df is not None and not df.empty:
                logger.info(f"[APIfanhui] ak.stock_zh_a_hist chenggong: {len(df)} xing, haoshi {api_elapsed:.2f}s")
                return df
            else:
                logger.warning(f"[APIfanhui] ak.stock_zh_a_hist fanhuikongshuju")
                return pd.DataFrame()

        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['banned', 'blocked', 'pinlv', 'rate', 'xianzhi']):
                raise RateLimitError(f"Akshare(EM) kenengbeixianliu: {e}") from e
            raise e

    def _fetch_stock_data_sina(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        huoquputong A gulishishuju (xinlangcaijing)
        shujulaiyuan：ak.stock_zh_a_daily()
        """
        import akshare as ak

        # zhuanhuandaimageshi：sh600000, sz000001, bj920748
        symbol = _to_sina_tx_symbol(stock_code)

        self._enforce_rate_limit()

        try:
            df = ak.stock_zh_a_daily(
                symbol=symbol,
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq"
            )

            # biaozhunhuaxinlangshujulieming
            # xinlangfanhui：date, open, high, low, close, volume, amount, outstanding_share, turnover
            if df is not None and not df.empty:
                # quebaoriqiliecunzai
                if 'date' in df.columns:
                    df = df.rename(columns={'date': 'riqi'})

                # yingsheqitalieyipipei _normalize_data deqiwang
                # _normalize_data qiwang：riqi, kaipan, shoupan, zuigao, zuidi, chengjiaoliang, chengjiaoe
                rename_map = {
                    'open': 'kaipan', 'high': 'zuigao', 'low': 'zuidi',
                    'close': 'shoupan', 'volume': 'chengjiaoliang', 'amount': 'chengjiaoe'
                }
                df = df.rename(columns=rename_map)

                # jisuanzhangdiefu（xinlangjiekoukenengbufanhui）
                if 'shoupan' in df.columns:
                    df['zhangdiefu'] = df['shoupan'].pct_change() * 100
                    df['zhangdiefu'] = df['zhangdiefu'].fillna(0)

                return df
            return pd.DataFrame()

        except Exception as e:
            raise e

    def _fetch_stock_data_tx(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        huoquputong A gulishishuju (tengxuncaijing)
        shujulaiyuan：ak.stock_zh_a_hist_tx()
        """
        import akshare as ak

        # zhuanhuandaimageshi：sh600000, sz000001, bj920748
        symbol = _to_sina_tx_symbol(stock_code)

        self._enforce_rate_limit()

        try:
            df = ak.stock_zh_a_hist_tx(
                symbol=symbol,
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq"
            )

            # biaozhunhuatengxunshujulieming
            # tengxunfanhui：date, open, close, high, low, volume, amount
            if df is not None and not df.empty:
                rename_map = {
                    'date': 'riqi', 'open': 'kaipan', 'high': 'zuigao',
                    'low': 'zuidi', 'close': 'shoupan', 'volume': 'chengjiaoliang',
                    'amount': 'chengjiaoe'
                }
                df = df.rename(columns=rename_map)

                # tengxunshujutongchangbaohan 'zhangdiefu'，ruguomeiyouzejisuan
                if 'pct_chg' in df.columns:
                    df = df.rename(columns={'pct_chg': 'zhangdiefu'})
                elif 'shoupan' in df.columns:
                    df['zhangdiefu'] = df['shoupan'].pct_change() * 100
                    df['zhangdiefu'] = df['zhangdiefu'].fillna(0)

                return df
            return pd.DataFrame()

        except Exception as e:
            raise e
    
    def _fetch_etf_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        huoqu ETF jijinlishishuju
        
        shujulaiyuan：ak.fund_etf_hist_em()
        
        Args:
            stock_code: ETF daima，ru '512400', '159883'
            start_date: kaishiriqi，geshi 'YYYY-MM-DD'
            end_date: jieshuriqi，geshi 'YYYY-MM-DD'
            
        Returns:
            ETF lishishuju DataFrame
        """
        import akshare as ak
        
        # fangfengjincelve 1: suiji User-Agent
        self._set_random_user_agent()
        
        # fangfengjincelve 2: qiangzhixiumian
        self._enforce_rate_limit()
        
        logger.info(f"[APIdiaoyong] ak.fund_etf_hist_em(symbol={stock_code}, period=daily, "
                   f"start_date={start_date.replace('-', '')}, end_date={end_date.replace('-', '')}, adjust=qfq)")
        
        try:
            import time as _time
            api_start = _time.time()
            
            # diaoyong akshare huoqu ETF rixianshuju
            df = ak.fund_etf_hist_em(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq"  # qianfuquan
            )
            
            api_elapsed = _time.time() - api_start
            
            # jilufanhuishujuzhaiyao
            if df is not None and not df.empty:
                logger.info(f"[APIfanhui] ak.fund_etf_hist_em chenggong: fanhui {len(df)} xingshuju, haoshi {api_elapsed:.2f}s")
                logger.info(f"[APIfanhui] lieming: {list(df.columns)}")
                logger.info(f"[APIfanhui] riqifanwei: {df['riqi'].iloc[0]} ~ {df['riqi'].iloc[-1]}")
                logger.debug(f"[APIfanhui] zuixin3tiaoshuju:\n{df.tail(3).to_string()}")
            else:
                logger.warning(f"[APIfanhui] ak.fund_etf_hist_em fanhuikongshuju, haoshi {api_elapsed:.2f}s")
            
            return df
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # jiancefanpafengjin
            if any(keyword in error_msg for keyword in ['banned', 'blocked', 'pinlv', 'rate', 'xianzhi']):
                logger.warning(f"jiancedaokenengbeifengjin: {e}")
                raise RateLimitError(f"Akshare kenengbeixianliu: {e}") from e
            
            raise DataFetchError(f"Akshare huoqu ETF shujushibai: {e}") from e
    
    def _fetch_us_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        huoqumeigulishishuju
        
        shujulaiyuan：ak.stock_us_daily()（xinlangcaijingjiekou）
        
        Args:
            stock_code: meigudaima，ru 'AMD', 'AAPL', 'TSLA'
            start_date: kaishiriqi，geshi 'YYYY-MM-DD'
            end_date: jieshuriqi，geshi 'YYYY-MM-DD'
            
        Returns:
            meigulishishuju DataFrame
        """
        import akshare as ak
        
        # fangfengjincelve 1: suiji User-Agent
        self._set_random_user_agent()
        
        # fangfengjincelve 2: qiangzhixiumian
        self._enforce_rate_limit()
        
        # meigudaimazhijieshiyongdaxie
        symbol = stock_code.strip().upper()
        
        logger.info(f"[APIdiaoyong] ak.stock_us_daily(symbol={symbol}, adjust=qfq)")
        
        try:
            import time as _time
            api_start = _time.time()
            
            # diaoyong akshare huoqumeigurixianshuju
            # stock_us_daily fanhuiquanbulishishuju，houxuxuyaoanriqiguolv
            df = ak.stock_us_daily(
                symbol=symbol,
                adjust="qfq"  # qianfuquan
            )
            
            api_elapsed = _time.time() - api_start
            
            # jilufanhuishujuzhaiyao
            if df is not None and not df.empty:
                logger.info(f"[APIfanhui] ak.stock_us_daily chenggong: fanhui {len(df)} xingshuju, haoshi {api_elapsed:.2f}s")
                logger.info(f"[APIfanhui] lieming: {list(df.columns)}")
                
                # anriqiguolv
                df['date'] = pd.to_datetime(df['date'])
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
                
                if not df.empty:
                    logger.info(f"[APIfanhui] guolvhouriqifanwei: {df['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['date'].iloc[-1].strftime('%Y-%m-%d')}")
                    logger.debug(f"[APIfanhui] zuixin3tiaoshuju:\n{df.tail(3).to_string()}")
                else:
                    logger.warning(f"[APIfanhui] guolvhoushujuweikong，riqifanwei {start_date} ~ {end_date} wushuju")
                
                # zhuanhuanliemingweizhongwengeshiyipipei _normalize_data
                # stock_us_daily fanhui: date, open, high, low, close, volume
                rename_map = {
                    'date': 'riqi',
                    'open': 'kaipan',
                    'high': 'zuigao',
                    'low': 'zuidi',
                    'close': 'shoupan',
                    'volume': 'chengjiaoliang',
                }
                df = df.rename(columns=rename_map)
                
                # jisuanzhangdiefu（meigujiekoubuzhijiefanhui）
                if 'shoupan' in df.columns:
                    df['zhangdiefu'] = df['shoupan'].pct_change() * 100
                    df['zhangdiefu'] = df['zhangdiefu'].fillna(0)
                
                # gusuanchengjiaoe（meigujiekoubufanhui）
                if 'chengjiaoliang' in df.columns and 'shoupan' in df.columns:
                    df['chengjiaoe'] = df['chengjiaoliang'] * df['shoupan']
                else:
                    df['chengjiaoe'] = 0
                
                return df
            else:
                logger.warning(f"[APIfanhui] ak.stock_us_daily fanhuikongshuju, haoshi {api_elapsed:.2f}s")
                return pd.DataFrame()
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # jiancefanpafengjin
            if any(keyword in error_msg for keyword in ['banned', 'blocked', 'pinlv', 'rate', 'xianzhi']):
                logger.warning(f"jiancedaokenengbeifengjin: {e}")
                raise RateLimitError(f"Akshare kenengbeixianliu: {e}") from e
            
            raise DataFetchError(f"Akshare huoqumeigushujushibai: {e}") from e

    def _fetch_hk_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        huoquganggulishishuju
        
        shujulaiyuan：ak.stock_hk_hist()
        
        Args:
            stock_code: ganggudaima，ru '00700', '01810'
            start_date: kaishiriqi，geshi 'YYYY-MM-DD'
            end_date: jieshuriqi，geshi 'YYYY-MM-DD'
            
        Returns:
            ganggulishishuju DataFrame
        """
        import akshare as ak
        
        # fangfengjincelve 1: suiji User-Agent
        self._set_random_user_agent()
        
        # fangfengjincelve 2: qiangzhixiumian
        self._enforce_rate_limit()
        
        # quebaodaimageshizhengque（5weishuzi）
        code = stock_code.lower().replace('hk', '').zfill(5)
        
        logger.info(f"[APIdiaoyong] ak.stock_hk_hist(symbol={code}, period=daily, "
                   f"start_date={start_date.replace('-', '')}, end_date={end_date.replace('-', '')}, adjust=qfq)")
        
        try:
            import time as _time
            api_start = _time.time()
            
            # diaoyong akshare huoquganggurixianshuju
            df = ak.stock_hk_hist(
                symbol=code,
                period="daily",
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq"  # qianfuquan
            )
            
            api_elapsed = _time.time() - api_start
            
            # jilufanhuishujuzhaiyao
            if df is not None and not df.empty:
                logger.info(f"[APIfanhui] ak.stock_hk_hist chenggong: fanhui {len(df)} xingshuju, haoshi {api_elapsed:.2f}s")
                logger.info(f"[APIfanhui] lieming: {list(df.columns)}")
                logger.info(f"[APIfanhui] riqifanwei: {df['riqi'].iloc[0]} ~ {df['riqi'].iloc[-1]}")
                logger.debug(f"[APIfanhui] zuixin3tiaoshuju:\n{df.tail(3).to_string()}")
            else:
                logger.warning(f"[APIfanhui] ak.stock_hk_hist fanhuikongshuju, haoshi {api_elapsed:.2f}s")
            
            return df
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # jiancefanpafengjin
            if any(keyword in error_msg for keyword in ['banned', 'blocked', 'pinlv', 'rate', 'xianzhi']):
                logger.warning(f"jiancedaokenengbeifengjin: {e}")
                raise RateLimitError(f"Akshare kenengbeixianliu: {e}") from e
            
            raise DataFetchError(f"Akshare huoquganggushujushibai: {e}") from e
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        biaozhunhua Akshare shuju
        
        Akshare fanhuidelieming（zhongwen）：
        riqi, kaipan, shoupan, zuigao, zuidi, chengjiaoliang, chengjiaoe, zhenfu, zhangdiefu, zhangdiee, huanshoulv
        
        xuyaoyingshedaobiaozhunlieming：
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()
        
        # liemingyingshe（Akshare zhongwenlieming -> biaozhunyingwenlieming）
        column_mapping = {
            'riqi': 'date',
            'kaipan': 'open',
            'shoupan': 'close',
            'zuigao': 'high',
            'zuidi': 'low',
            'chengjiaoliang': 'volume',
            'chengjiaoe': 'amount',
            'zhangdiefu': 'pct_chg',
        }
        
        # zhongmingminglie
        df = df.rename(columns=column_mapping)
        
        # tianjiagupiaodaimalie
        df['code'] = stock_code
        
        # zhibaoliuxuyaodelie
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]
        
        return df
    
    def get_realtime_quote(self, stock_code: str, source: str = "em") -> Optional[UnifiedRealtimeQuote]:
        """
        huoqushishixingqingshuju（zhichiduoshujuyuan）

        shujuyuanyouxianji（kepeizhi）：
        1. em: dongfangcaifu（akshare ak.stock_zh_a_spot_em）- shujuzuiquan，hanliangbi/PE/PB/shizhideng
        2. sina: xinlangcaijing（akshare ak.stock_zh_a_spot）- qingliangji，jibenhangqing
        3. tencent: tengxunzhilianjiekou - dangupiaochaxun，fuzaixiao

        Args:
            stock_code: gupiao/ETFdaima
            source: shujuyuanleixing，kexuan "em", "sina", "tencent"

        Returns:
            UnifiedRealtimeQuote duixiang，huoqushibaifanhui None
        """
        circuit_breaker = get_realtime_circuit_breaker()

        # genjudaimaleixingxuanzebutongdehuoqufangfa
        if _is_us_code(stock_code):
            # meigubushiyong Akshare，you YfinanceFetcher chuli
            logger.debug(f"[APItiaoguo] {stock_code} shimeigu，Akshare buzhichimeigushishixingqing")
            return None
        elif _is_hk_code(stock_code):
            return self._get_hk_realtime_quote(stock_code)
        elif _is_etf_code(stock_code):
            source_key = "akshare_etf"
            if not circuit_breaker.is_available(source_key):
                logger.info(f"[rongduan] shujuyuan {source_key} chuyurongduanzhuangtai，tiaoguo")
                return None
            return self._get_etf_realtime_quote(stock_code)
        else:
            source_key = f"akshare_{source}"
            if not circuit_breaker.is_available(source_key):
                logger.info(f"[rongduan] shujuyuan {source_key} chuyurongduanzhuangtai，tiaoguo")
                return None
            # putong A gu：genju source xuanzeshujuyuan
            if source == "sina":
                return self._get_stock_realtime_quote_sina(stock_code)
            elif source == "tencent":
                return self._get_stock_realtime_quote_tencent(stock_code)
            else:
                return self._get_stock_realtime_quote_em(stock_code)
    
    def _get_stock_realtime_quote_em(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        huoquputong A gushishixingqingshuju（dongfangcaifushujuyuan）
        
        shujulaiyuan：ak.stock_zh_a_spot_em()
        youdian：shujuzuiquan，hanliangbi、huanshoulv、shiyinglv、shijinglv、zongshizhi、liutongshizhideng
        quedian：quanlianglaqu，shujuliangda，rongyichaoshi/xianliu
        """
        import akshare as ak
        circuit_breaker = get_realtime_circuit_breaker()
        source_key = "akshare_em"
        
        try:
            # jianchahuancun
            current_time = time.time()
            if (_realtime_cache['data'] is not None and 
                current_time - _realtime_cache['timestamp'] < _realtime_cache['ttl']):
                df = _realtime_cache['data']
                cache_age = int(current_time - _realtime_cache['timestamp'])
                logger.debug(f"[huancunmingzhong] Agushishixingqing(dongcai) - huancunnianling {cache_age}s/{_realtime_cache['ttl']}s")
            else:
                # chufaquanliangshuaxin
                logger.info(f"[huancunweimingzhong] chufaquanliangshuaxin Agushishixingqing(dongcai)")
                last_error: Optional[Exception] = None
                df = None
                for attempt in range(1, 3):
                    try:
                        # fangfengjincelve
                        self._set_random_user_agent()
                        self._enforce_rate_limit()

                        logger.info(f"[APIdiaoyong] ak.stock_zh_a_spot_em() huoquAgushishixingqing... (attempt {attempt}/2)")
                        import time as _time
                        api_start = _time.time()

                        df = ak.stock_zh_a_spot_em()

                        api_elapsed = _time.time() - api_start
                        logger.info(f"[APIfanhui] ak.stock_zh_a_spot_em chenggong: fanhui {len(df)} zhigupiao, haoshi {api_elapsed:.2f}s")
                        circuit_breaker.record_success(source_key)
                        break
                    except Exception as e:
                        last_error = e
                        logger.info(f"[APIcuowu] ak.stock_zh_a_spot_em huoqushibai (attempt {attempt}/2): {e}")
                        time.sleep(min(2 ** attempt, 5))

                # gengxinhuancun：chenggonghuancunshuju；shibaiyehuancunkongshuju，bimiantongyilunrenwuduitongyijiekoufanfuqingqiu
                if df is None:
                    logger.info(f"[APIcuowu] ak.stock_zh_a_spot_em zuizhongshibai: {last_error}")
                    circuit_breaker.record_failure(source_key, str(last_error))
                    df = pd.DataFrame()
                _realtime_cache['data'] = df
                _realtime_cache['timestamp'] = current_time
                logger.info(f"[huancungengxin] Agushishixingqing(dongcai) huancunyishuaxin，TTL={_realtime_cache['ttl']}s")

            if df is None or df.empty:
                logger.info(f"[shishixingqing] Agushishixingqingshujuweikong，tiaoguo {stock_code}")
                return None
            
            # chazhaozhidinggupiao
            row = df[df['daima'] == stock_code]
            if row.empty:
                logger.info(f"[APIfanhui] weizhaodaogupiao {stock_code} deshishixingqing")
                return None
            
            row = row.iloc[0]
            
            # shiyong realtime_types.py zhongdetongyizhuanhuanhanshu
            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=str(row.get('mingcheng', '')),
                source=RealtimeSource.AKSHARE_EM,
                price=safe_float(row.get('zuixinjia')),
                change_pct=safe_float(row.get('zhangdiefu')),
                change_amount=safe_float(row.get('zhangdiee')),
                volume=safe_int(row.get('chengjiaoliang')),
                amount=safe_float(row.get('chengjiaoe')),
                volume_ratio=safe_float(row.get('liangbi')),
                turnover_rate=safe_float(row.get('huanshoulv')),
                amplitude=safe_float(row.get('zhenfu')),
                open_price=safe_float(row.get('jinkai')),
                high=safe_float(row.get('zuigao')),
                low=safe_float(row.get('zuidi')),
                pe_ratio=safe_float(row.get('shiyinglv-dongtai')),
                pb_ratio=safe_float(row.get('shijinglv')),
                total_mv=safe_float(row.get('zongshizhi')),
                circ_mv=safe_float(row.get('liutongshizhi')),
                change_60d=safe_float(row.get('60rizhangdiefu')),
                high_52w=safe_float(row.get('52zhouzuigao')),
                low_52w=safe_float(row.get('52zhouzuidi')),
            )
            
            logger.info(f"[shishixingqing-dongcai] {stock_code} {quote.name}: jiage={quote.price}, zhangdie={quote.change_pct}%, "
                       f"liangbi={quote.volume_ratio}, huanshoulv={quote.turnover_rate}%")
            return quote
            
        except Exception as e:
            logger.info(f"[APIcuowu] huoqu {stock_code} shishixingqing(dongcai)shibai: {e}")
            circuit_breaker.record_failure(source_key, str(e))
            return None
    
    def _get_stock_realtime_quote_sina(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        huoquputong A gushishixingqingshuju（xinlangcaijingshujuyuan）
        
        shujulaiyuan：xinlangcaijingjiekou（zhilian，dangupiaochaxun）
        youdian：dangupiaochaxun，fuzaixiao，sudukuai
        quedian：shujuziduanjiaoshao，wuliangbi/PE/PBdeng
        
        jiekougeshi：http://hq.sinajs.cn/list=sh600519,sz000001
        """
        circuit_breaker = get_realtime_circuit_breaker()
        source_key = "akshare_sina"
        symbol = _to_sina_tx_symbol(stock_code)
        url = f"http://{SINA_REALTIME_ENDPOINT}={symbol}"
        api_start = time.time()
        
        try:
            headers = {
                'Referer': 'http://finance.sina.com.cn',
                'User-Agent': random.choice(USER_AGENTS)
            }
            
            logger.info(
                f"[APIdiaoyong] xinlangcaijingjiekouhuoqu {stock_code} shishixingqing: endpoint={SINA_REALTIME_ENDPOINT}, symbol={symbol}"
            )
            
            self._enforce_rate_limit()
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'gbk'
            api_elapsed = time.time() - api_start
            
            if response.status_code != 200:
                failure_message = _build_realtime_failure_message(
                    source_name="xinlang",
                    endpoint=SINA_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="http_status",
                    detail=f"HTTP {response.status_code}",
                    elapsed=api_elapsed,
                    error_type="HTTPStatus",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None
            
            # jiexishuju：var hq_str_sh600519="guizhoumaotai,1866.000,1870.000,..."
            content = response.text.strip()
            if '=""' in content or not content:
                failure_message = _build_realtime_failure_message(
                    source_name="xinlang",
                    endpoint=SINA_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="empty_response",
                    detail="empty quote payload",
                    elapsed=api_elapsed,
                    error_type="EmptyResponse",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None
            
            # tiquyinhaoneideshuju
            data_start = content.find('"')
            data_end = content.rfind('"')
            if data_start == -1 or data_end == -1:
                failure_message = _build_realtime_failure_message(
                    source_name="xinlang",
                    endpoint=SINA_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="malformed_payload",
                    detail="quote payload missing quotes",
                    elapsed=api_elapsed,
                    error_type="MalformedPayload",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None
            
            data_str = content[data_start+1:data_end]
            fields = data_str.split(',')
            
            if len(fields) < 32:
                failure_message = _build_realtime_failure_message(
                    source_name="xinlang",
                    endpoint=SINA_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="insufficient_fields",
                    detail=f"field_count={len(fields)}",
                    elapsed=api_elapsed,
                    error_type="InsufficientFields",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None
            
            circuit_breaker.record_success(source_key)
            
            # xinlangshujuziduanshunxu：
            # 0:mingcheng 1:jinkai 2:zuoshou 3:zuixinjia 4:zuigao 5:zuidi 6:maiyijia 7:maiyijia
            # 8:chengjiaoliang(gu) 9:chengjiaoe(yuan) ... 30:riqi 31:shijian
            # shiyong realtime_types.py zhongdetongyizhuanhuanhanshu
            price = safe_float(fields[3])
            pre_close = safe_float(fields[2])
            change_pct = None
            change_amount = None
            if price and pre_close and pre_close > 0:
                change_amount = price - pre_close
                change_pct = (change_amount / pre_close) * 100
            
            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=fields[0],
                source=RealtimeSource.AKSHARE_SINA,
                price=price,
                change_pct=change_pct,
                change_amount=change_amount,
                volume=safe_int(fields[8]),  # chengjiaoliang（gu）
                amount=safe_float(fields[9]),  # chengjiaoe（yuan）
                open_price=safe_float(fields[1]),
                high=safe_float(fields[4]),
                low=safe_float(fields[5]),
                pre_close=pre_close,
            )
            
            logger.info(
                f"[shishixingqing-xinlang] {stock_code} {quote.name}: endpoint={SINA_REALTIME_ENDPOINT}, "
                f"jiage={quote.price}, zhangdie={quote.change_pct}, chengjiaoliang={quote.volume}, elapsed={api_elapsed:.2f}s"
            )
            return quote
            
        except Exception as e:
            api_elapsed = time.time() - api_start
            category, detail = _classify_realtime_http_error(e)
            failure_message = _build_realtime_failure_message(
                source_name="xinlang",
                endpoint=SINA_REALTIME_ENDPOINT,
                stock_code=stock_code,
                symbol=symbol,
                category=category,
                detail=detail,
                elapsed=api_elapsed,
                error_type=type(e).__name__,
            )
            logger.info(failure_message)
            circuit_breaker.record_failure(source_key, failure_message)
            return None
    
    def _get_stock_realtime_quote_tencent(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        huoquputong A gushishixingqingshuju（tengxuncaijingshujuyuan）
        
        shujulaiyuan：tengxuncaijingjiekou（zhilian，dangupiaochaxun）
        youdian：dangupiaochaxun，fuzaixiao，baohanhuanshoulv
        quedian：wuliangbi/PE/PBdengguzhishuju
        
        jiekougeshi：http://qt.gtimg.cn/q=sh600519,sz000001
        """
        circuit_breaker = get_realtime_circuit_breaker()
        source_key = "akshare_tencent"
        symbol = _to_sina_tx_symbol(stock_code)
        url = f"http://{TENCENT_REALTIME_ENDPOINT}={symbol}"
        api_start = time.time()
        
        try:
            headers = {
                'Referer': 'http://finance.qq.com',
                'User-Agent': random.choice(USER_AGENTS)
            }
            
            logger.info(
                f"[APIdiaoyong] tengxuncaijingjiekouhuoqu {stock_code} shishixingqing: endpoint={TENCENT_REALTIME_ENDPOINT}, symbol={symbol}"
            )
            
            self._enforce_rate_limit()
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'gbk'
            api_elapsed = time.time() - api_start
            
            if response.status_code != 200:
                failure_message = _build_realtime_failure_message(
                    source_name="tengxun",
                    endpoint=TENCENT_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="http_status",
                    detail=f"HTTP {response.status_code}",
                    elapsed=api_elapsed,
                    error_type="HTTPStatus",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None
            
            content = response.text.strip()
            if '=""' in content or not content:
                failure_message = _build_realtime_failure_message(
                    source_name="tengxun",
                    endpoint=TENCENT_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="empty_response",
                    detail="empty quote payload",
                    elapsed=api_elapsed,
                    error_type="EmptyResponse",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None
            
            # tiqushuju
            data_start = content.find('"')
            data_end = content.rfind('"')
            if data_start == -1 or data_end == -1:
                failure_message = _build_realtime_failure_message(
                    source_name="tengxun",
                    endpoint=TENCENT_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="malformed_payload",
                    detail="quote payload missing quotes",
                    elapsed=api_elapsed,
                    error_type="MalformedPayload",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None
            
            data_str = content[data_start+1:data_end]
            fields = data_str.split('~')

            if len(fields) < 45:
                failure_message = _build_realtime_failure_message(
                    source_name="tengxun",
                    endpoint=TENCENT_REALTIME_ENDPOINT,
                    stock_code=stock_code,
                    symbol=symbol,
                    category="insufficient_fields",
                    detail=f"field_count={len(fields)}",
                    elapsed=api_elapsed,
                    error_type="InsufficientFields",
                )
                logger.info(failure_message)
                circuit_breaker.record_failure(source_key, failure_message)
                return None
            
            circuit_breaker.record_success(source_key)
            
            # tengxunshujuziduanshunxu（wanzheng）：
            # 1:mingcheng 2:daima 3:zuixinjia 4:zuoshou 5:jinkai 6:chengjiaoliang(shou) 7:waipan 8:neipan
            # 9-28:maimaiwudang 30:shijianchuo 31:zhangdiee 32:zhangdiefu(%) 33:zuigao 34:zuidi 35:shoupan/chengjiaoliang/chengjiaoe
            # 36:chengjiaoliang(shou) 37:chengjiaoe(wan) 38:huanshoulv(%) 39:shiyinglv 43:zhenfu(%)
            # 44:liutongshizhi(yi) 45:zongshizhi(yi) 46:shijinglv 47:zhangtingjia 48:dietingjia 49:liangbi
            # shiyong realtime_types.py zhongdetongyizhuanhuanhanshu
            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=fields[1] if len(fields) > 1 else "",
                source=RealtimeSource.TENCENT,
                price=safe_float(fields[3]),
                change_pct=safe_float(fields[32]),
                change_amount=safe_float(fields[31]) if len(fields) > 31 else None,
                volume=safe_int(fields[6]) * 100 if fields[6] else None,  # tengxunfanhuideshishou，zhuanweigu
                open_price=safe_float(fields[5]),
                high=safe_float(fields[33]) if len(fields) > 33 else None,  # xiuzheng：ziduan 33 shizuigaojia
                low=safe_float(fields[34]) if len(fields) > 34 else None,  # xiuzheng：ziduan 34 shizuidijia
                pre_close=safe_float(fields[4]),
                turnover_rate=safe_float(fields[38]) if len(fields) > 38 else None,
                amplitude=safe_float(fields[43]) if len(fields) > 43 else None,
                volume_ratio=safe_float(fields[49]) if len(fields) > 49 else None,  # liangbi
                pe_ratio=safe_float(fields[39]) if len(fields) > 39 else None,  # shiyinglv
                pb_ratio=safe_float(fields[46]) if len(fields) > 46 else None,  # shijinglv
                circ_mv=safe_float(fields[44]) * 100000000 if len(fields) > 44 and fields[44] else None,  # liutongshizhi(yi->yuan)
                total_mv=safe_float(fields[45]) * 100000000 if len(fields) > 45 and fields[45] else None,  # zongshizhi(yi->yuan)
            )
            
            logger.info(
                f"[shishixingqing-tengxun] {stock_code} {quote.name}: endpoint={TENCENT_REALTIME_ENDPOINT}, "
                f"jiage={quote.price}, zhangdie={quote.change_pct}%, liangbi={quote.volume_ratio}, "
                f"huanshoulv={quote.turnover_rate}%, elapsed={api_elapsed:.2f}s"
            )
            return quote
            
        except Exception as e:
            api_elapsed = time.time() - api_start
            category, detail = _classify_realtime_http_error(e)
            failure_message = _build_realtime_failure_message(
                source_name="tengxun",
                endpoint=TENCENT_REALTIME_ENDPOINT,
                stock_code=stock_code,
                symbol=symbol,
                category=category,
                detail=detail,
                elapsed=api_elapsed,
                error_type=type(e).__name__,
            )
            logger.info(failure_message)
            circuit_breaker.record_failure(source_key, failure_message)
            return None
    
    def _get_etf_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        huoqu ETF jijinshishixingqingshuju
        
        shujulaiyuan：ak.fund_etf_spot_em()
        baohan：zuixinjia、zhangdiefu、chengjiaoliang、chengjiaoe、huanshoulvdeng
        
        Args:
            stock_code: ETF daima
            
        Returns:
            UnifiedRealtimeQuote duixiang，huoqushibaifanhui None
        """
        import akshare as ak
        circuit_breaker = get_realtime_circuit_breaker()
        source_key = "akshare_etf"
        
        try:
            # jianchahuancun
            current_time = time.time()
            if (_etf_realtime_cache['data'] is not None and 
                current_time - _etf_realtime_cache['timestamp'] < _etf_realtime_cache['ttl']):
                df = _etf_realtime_cache['data']
                logger.debug(f"[huancunmingzhong] shiyonghuancundeETFshishixingqingshuju")
            else:
                last_error: Optional[Exception] = None
                df = None
                for attempt in range(1, 3):
                    try:
                        # fangfengjincelve
                        self._set_random_user_agent()
                        self._enforce_rate_limit()

                        logger.info(f"[APIdiaoyong] ak.fund_etf_spot_em() huoquETFshishixingqing... (attempt {attempt}/2)")
                        import time as _time
                        api_start = _time.time()

                        df = ak.fund_etf_spot_em()

                        api_elapsed = _time.time() - api_start
                        logger.info(f"[APIfanhui] ak.fund_etf_spot_em chenggong: fanhui {len(df)} zhiETF, haoshi {api_elapsed:.2f}s")
                        circuit_breaker.record_success(source_key)
                        break
                    except Exception as e:
                        last_error = e
                        logger.info(f"[APIcuowu] ak.fund_etf_spot_em huoqushibai (attempt {attempt}/2): {e}")
                        time.sleep(min(2 ** attempt, 5))

                if df is None:
                    logger.info(f"[APIcuowu] ak.fund_etf_spot_em zuizhongshibai: {last_error}")
                    circuit_breaker.record_failure(source_key, str(last_error))
                    df = pd.DataFrame()
                _etf_realtime_cache['data'] = df
                _etf_realtime_cache['timestamp'] = current_time

            if df is None or df.empty:
                logger.info(f"[shishixingqing] ETFshishixingqingshujuweikong，tiaoguo {stock_code}")
                return None
            
            # chazhaozhiding ETF
            row = df[df['daima'] == stock_code]
            if row.empty:
                logger.info(f"[APIfanhui] weizhaodao ETF {stock_code} deshishixingqing")
                return None
            
            row = row.iloc[0]
            
            # shiyong realtime_types.py zhongdetongyizhuanhuanhanshu
            # ETF hangqingshujugoujian
            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=str(row.get('mingcheng', '')),
                source=RealtimeSource.AKSHARE_EM,
                price=safe_float(row.get('zuixinjia')),
                change_pct=safe_float(row.get('zhangdiefu')),
                change_amount=safe_float(row.get('zhangdiee')),
                volume=safe_int(row.get('chengjiaoliang')),
                amount=safe_float(row.get('chengjiaoe')),
                volume_ratio=safe_float(row.get('liangbi')),
                turnover_rate=safe_float(row.get('huanshoulv')),
                amplitude=safe_float(row.get('zhenfu')),
                open_price=safe_float(row.get('kaipanjia')),
                high=safe_float(row.get('zuigaojia')),
                low=safe_float(row.get('zuidijia')),
                total_mv=safe_float(row.get('zongshizhi')),
                circ_mv=safe_float(row.get('liutongshizhi')),
                high_52w=safe_float(row.get('52zhouzuigao')),
                low_52w=safe_float(row.get('52zhouzuidi')),
            )
            
            logger.info(f"[ETFshishixingqing] {stock_code} {quote.name}: jiage={quote.price}, zhangdie={quote.change_pct}%, "
                       f"huanshoulv={quote.turnover_rate}%")
            return quote
            
        except Exception as e:
            logger.info(f"[APIcuowu] huoqu ETF {stock_code} shishixingqingshibai: {e}")
            circuit_breaker.record_failure(source_key, str(e))
            return None
    
    def _get_hk_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        huoquganggushishixingqingshuju

        zhushujuyuan：ak.stock_hk_spot_em()（dongfangcaifu）
        beiyongshujuyuan：ak.stock_hk_spot()（xinlang）
        baohan：zuixinjia、zhangdiefu、chengjiaoliang、chengjiaoedeng

        Args:
            stock_code: ganggudaima

        Returns:
            UnifiedRealtimeQuote duixiang，huoqushibaifanhui None
        """
        import akshare as ak
        circuit_breaker = get_realtime_circuit_breaker()
        em_key = "akshare_hk_em"
        sina_key = "akshare_hk_sina"

        # fangfengjincelve
        self._set_random_user_agent()
        self._enforce_rate_limit()

        # quebaodaimageshizhengque（5weishuzi）
        raw_code = stock_code.strip().lower()
        if raw_code.endswith('.hk'):
            raw_code = raw_code[:-3]
        if raw_code.startswith('hk'):
            raw_code = raw_code[2:]
        code = raw_code.zfill(5)

        # --- zhushujuyuan：dongfangcaifu ---
        if circuit_breaker.is_available(em_key):
            try:
                logger.info(f"[APIdiaoyong] ak.stock_hk_spot_em() huoquganggushishixingqing...")
                import time as _time
                api_start = _time.time()

                df = ak.stock_hk_spot_em()

                api_elapsed = _time.time() - api_start
                logger.info(f"[APIfanhui] ak.stock_hk_spot_em chenggong: fanhui {len(df)} zhiganggu, haoshi {api_elapsed:.2f}s")
                circuit_breaker.record_success(em_key)

                # chazhaozhidingganggu
                row = df[df['daima'] == code]
                if row.empty:
                    logger.info(f"[APIfanhui] weizhaodaoganggu {code} deshishixingqing (stock_hk_spot_em)")
                else:
                    row = row.iloc[0]
                    quote = UnifiedRealtimeQuote(
                        code=stock_code,
                        name=str(row.get('mingcheng', '')),
                        source=RealtimeSource.AKSHARE_EM,
                        price=safe_float(row.get('zuixinjia')),
                        change_pct=safe_float(row.get('zhangdiefu')),
                        change_amount=safe_float(row.get('zhangdiee')),
                        volume=safe_int(row.get('chengjiaoliang')),
                        amount=safe_float(row.get('chengjiaoe')),
                        volume_ratio=safe_float(row.get('liangbi')),
                        turnover_rate=safe_float(row.get('huanshoulv')),
                        amplitude=safe_float(row.get('zhenfu')),
                        pe_ratio=safe_float(row.get('shiyinglv')),
                        pb_ratio=safe_float(row.get('shijinglv')),
                        total_mv=safe_float(row.get('zongshizhi')),
                        circ_mv=safe_float(row.get('liutongshizhi')),
                        high_52w=safe_float(row.get('52zhouzuigao')),
                        low_52w=safe_float(row.get('52zhouzuidi')),
                    )
                    logger.info(f"[ganggushishixingqing] {stock_code} {quote.name}: jiage={quote.price}, zhangdie={quote.change_pct}%, "
                                f"huanshoulv={quote.turnover_rate}%")
                    return quote

            except Exception as e:
                logger.warning(f"[APIcuowu] ak.stock_hk_spot_em huoquganggu {stock_code} shibai: {e}，changshi stock_hk_spot beiyongjiekou")
                circuit_breaker.record_failure(em_key, str(e))
        else:
            logger.info(f"[rongduan] shujuyuan {em_key} chuyurongduanzhuangtai，changshishiyongbeiyonglianlu")

        # --- beiyongshujuyuan：xinlang ---
        if not circuit_breaker.is_available(sina_key):
            logger.info(f"[rongduan] shujuyuan {sina_key} chuyurongduanzhuangtai，tiaoguobeiyonglianlu")
            return None

        try:
            logger.info(f"[APIdiaoyong] ak.stock_hk_spot() huoquganggushishixingqing（beiyong）...")
            import time as _time
            api_start = _time.time()

            df_spot = ak.stock_hk_spot()

            api_elapsed = _time.time() - api_start
            logger.info(f"[APIfanhui] ak.stock_hk_spot chenggong: fanhui {len(df_spot)} zhiganggu, haoshi {api_elapsed:.2f}s")

            row = df_spot[df_spot['daima'] == code]
            if row.empty:
                logger.info(f"[APIfanhui] weizhaodaoganggu {code} deshishixingqing (stock_hk_spot)")
                return None

            row = row.iloc[0]
            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=str(row.get('mingcheng', '')),
                source=RealtimeSource.AKSHARE_EM,
                price=safe_float(row.get('zuixinjia')),
                change_pct=safe_float(row.get('zhangdiefu')),
                change_amount=safe_float(row.get('zhangdiee')),
                volume=safe_int(row.get('chengjiaoliang')),
                amount=safe_float(row.get('chengjiaoe')),
            )
            circuit_breaker.record_success(sina_key)
            logger.info(f"[ganggushishixingqing-beiyong] {stock_code} {quote.name}: jiage={quote.price}, zhangdie={quote.change_pct}%")
            return quote

        except Exception as e:
            logger.info(f"[APIcuowu] ak.stock_hk_spot beiyongjiekouyeshibai: {e}")
            circuit_breaker.record_failure(sina_key, str(e))
            return None
    
    def get_chip_distribution(self, stock_code: str) -> Optional[ChipDistribution]:
        """
        huoquchoumafenbushuju
        
        shujulaiyuan：ak.stock_cyq_em()
        baohan：huolibili、pingjunchengben、choumajizhongdu
        
        zhuyi：ETF/zhishumeiyouchoumafenbushuju，huizhijiefanhui None
        
        Args:
            stock_code: gupiaodaima
            
        Returns:
            ChipDistribution duixiang（zuixinyitiandeshuju），huoqushibaifanhui None
        """
        import akshare as ak

        # meigumeiyouchoumafenbushuju（Akshare buzhichi）
        if _is_us_code(stock_code):
            logger.debug(f"[APItiaoguo] {stock_code} shimeigu，wuchoumafenbushuju")
            return None

        # ganggumeiyouchoumafenbushuju（stock_cyq_em shi A guzhuanshujiekou）
        if _is_hk_code(stock_code):
            logger.debug(f"[APItiaoguo] {stock_code} shiganggu，wuchoumafenbushuju")
            return None

        # ETF/zhishumeiyouchoumafenbushuju
        if _is_etf_code(stock_code):
            logger.debug(f"[APItiaoguo] {stock_code} shi ETF/zhishu，wuchoumafenbushuju")
            return None
        
        try:
            # fangfengjincelve
            self._set_random_user_agent()
            self._enforce_rate_limit()
            
            logger.info(f"[APIdiaoyong] ak.stock_cyq_em(symbol={stock_code}) huoquchoumafenbu...")
            import time as _time
            api_start = _time.time()
            
            df = ak.stock_cyq_em(symbol=stock_code)
            
            api_elapsed = _time.time() - api_start
            
            if df.empty:
                logger.warning(f"[APIfanhui] ak.stock_cyq_em fanhuikongshuju, haoshi {api_elapsed:.2f}s")
                return None
            
            logger.info(f"[APIfanhui] ak.stock_cyq_em chenggong: fanhui {len(df)} tianshuju, haoshi {api_elapsed:.2f}s")
            logger.debug(f"[APIfanhui] choumashujulieming: {list(df.columns)}")
            
            # quzuixinyitiandeshuju
            latest = df.iloc[-1]
            
            # shiyong realtime_types.py zhongdetongyizhuanhuanhanshu
            chip = ChipDistribution(
                code=stock_code,
                date=str(latest.get('riqi', '')),
                profit_ratio=safe_float(latest.get('huolibili')),
                avg_cost=safe_float(latest.get('pingjunchengben')),
                cost_90_low=safe_float(latest.get('90chengben-di')),
                cost_90_high=safe_float(latest.get('90chengben-gao')),
                concentration_90=safe_float(latest.get('90jizhongdu')),
                cost_70_low=safe_float(latest.get('70chengben-di')),
                cost_70_high=safe_float(latest.get('70chengben-gao')),
                concentration_70=safe_float(latest.get('70jizhongdu')),
            )
            
            logger.info(f"[choumafenbu] {stock_code} riqi={chip.date}: huolibili={chip.profit_ratio:.1%}, "
                       f"pingjunchengben={chip.avg_cost}, 90%jizhongdu={chip.concentration_90:.2%}, "
                       f"70%jizhongdu={chip.concentration_70:.2%}")
            return chip
            
        except Exception as e:
            logger.error(f"[APIcuowu] huoqu {stock_code} choumafenbushibai: {e}")
            return None
    
    def get_enhanced_data(self, stock_code: str, days: int = 60) -> Dict[str, Any]:
        """
        huoquzengqiangshuju（lishiKxian + shishixingqing + choumafenbu）
        
        Args:
            stock_code: gupiaodaima
            days: lishishujutianshu
            
        Returns:
            baohansuoyoushujudezidian
        """
        result = {
            'code': stock_code,
            'daily_data': None,
            'realtime_quote': None,
            'chip_distribution': None,
        }
        
        # huoqurixianshuju
        try:
            df = self.get_daily_data(stock_code, days=days)
            result['daily_data'] = df
        except Exception as e:
            logger.error(f"huoqu {stock_code} rixianshujushibai: {e}")
        
        # huoqushishixingqing
        result['realtime_quote'] = self.get_realtime_quote(stock_code)
        
        # huoquchoumafenbu
        result['chip_distribution'] = self.get_chip_distribution(stock_code)
        
        return result

    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """
        huoquzhuyaozhishushishixingqing (xinlangjiekou)，jinzhichi A gu
        """
        if region != "cn":
            return None
        import akshare as ak

        # zhuyaozhishudaimayingshe
        indices_map = {
            'sh000001': 'shangzhengzhishu',
            'sz399001': 'shenzhengchengzhi',
            'sz399006': 'chuangyebanzhi',
            'sh000688': 'kechuang50',
            'sh000016': 'shangzheng50',
            'sh000300': 'hushen300',
        }

        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            # shiyong akshare huoquzhishuhangqing（xinlangcaijingjiekou）
            df = ak.stock_zh_index_spot_sina()

            results = []
            if df is not None and not df.empty:
                for code, name in indices_map.items():
                    # chazhaoduiyingzhishu
                    row = df[df['daima'] == code]
                    if row.empty:
                        # changshidaiqianzhuichazhao
                        row = df[df['daima'].str.contains(code)]

                    if not row.empty:
                        row = row.iloc[0]
                        current = safe_float(row.get('zuixinjia', 0))
                        prev_close = safe_float(row.get('zuoshou', 0))
                        high = safe_float(row.get('zuigao', 0))
                        low = safe_float(row.get('zuidi', 0))

                        # jisuanzhenfu
                        amplitude = 0.0
                        if prev_close > 0:
                            amplitude = (high - low) / prev_close * 100

                        results.append({
                            'code': code,
                            'name': name,
                            'current': current,
                            'change': safe_float(row.get('zhangdiee', 0)),
                            'change_pct': safe_float(row.get('zhangdiefu', 0)),
                            'open': safe_float(row.get('jinkai', 0)),
                            'high': high,
                            'low': low,
                            'prev_close': prev_close,
                            'volume': safe_float(row.get('chengjiaoliang', 0)),
                            'amount': safe_float(row.get('chengjiaoe', 0)),
                            'amplitude': amplitude,
                        })
            return results

        except Exception as e:
            logger.error(f"[Akshare] huoquzhishuhangqingshibai: {e}")
            return None

    def get_market_stats(self) -> Optional[Dict[str, Any]]:
        """
        huoqushichangzhangdietongji

        shujuyuanyouxianji：
        1. dongcaijiekou (ak.stock_zh_a_spot_em)
        2. xinlangjiekou (ak.stock_zh_a_spot)
        """
        import akshare as ak

        # youxiandongcaijiekou
        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[APIdiaoyong] ak.stock_zh_a_spot_em() huoqushichangtongji...")
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                return self._calc_market_stats(df)
        except Exception as e:
            logger.warning(f"[Akshare] dongcaijiekouhuoqushichangtongjishibai: {e}，changshixinlangjiekou")

        # dongcaishibaihou，changshixinlangjiekou
        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[APIdiaoyong] ak.stock_zh_a_spot() huoqushichangtongji(xinlang)...")
            df = ak.stock_zh_a_spot()
            if df is not None and not df.empty:
                return self._calc_market_stats(df)
        except Exception as e:
            logger.error(f"[Akshare] xinlangjiekouhuoqushichangtongjiyeshibai: {e}")

        return None

    def _calc_market_stats(
        self,
        df: pd.DataFrame,
        ) -> Optional[Dict[str, Any]]:
        """conghangqing DataFrame jisuanzhangdietongji。"""
        import numpy as np

        df = df.copy()
        
        # 1. tiqujichubiduishuju：zuixinjia、zuoshou
        # jianrongbutongjiekoufanhuidelieming sina/em efinance tushare xtdata
        code_col = next((c for c in ['daima', 'gupiaodaima', 'ts_code','stock_code'] if c in df.columns), None)
        name_col = next((c for c in ['mingcheng', 'gupiaomingcheng','name','name'] if c in df.columns), None)
        close_col = next((c for c in ['zuixinjia', 'zuixinjia', 'close','lastPrice'] if c in df.columns), None)
        pre_close_col = next((c for c in ['zuoshou', 'zuorishoupan', 'pre_close','lastClose'] if c in df.columns), None)
        amount_col = next((c for c in ['chengjiaoe', 'chengjiaoe', 'amount','amount'] if c in df.columns), None) 
        
        limit_up_count = 0
        limit_down_count = 0
        up_count = 0
        down_count = 0
        flat_count = 0

        for code, name, current_price, pre_close, amount in zip(
            df[code_col], df[name_col], df[close_col], df[pre_close_col], df[amount_col]
        ):
            
            # tingpaiguolv efinance detingpaishujuyoushihouhuiqueshijiagexianshiwei '-'，em xianshiweinone
            if pd.isna(current_price) or pd.isna(pre_close) or current_price in ['-'] or pre_close in ['-'] or amount == 0:
                continue
            
            # em、efinance weistr xuyaozhuanhuanweifloat
            current_price = float(current_price)
            pre_close = float(pre_close)
            
            # huoququchuqianzhuidechunshuzidaima
            pure_code = normalize_stock_code(str(code)) 

            # A. quedingmeizhigupiaodezhangdiefubili (shiyongchunshuzidaimapanduan)
            if is_bse_code(pure_code): 
                ratio = 0.30
            elif is_kc_cy_stock(pure_code): #pure_code.startswith(('688', '30')):
                ratio = 0.20
            elif is_st_stock(name): #'ST' in str_name:
                ratio = 0.05
            else:
                ratio = 0.10

            # B. yangeanzhao A guguizejisuanzhangdietingjia：zuoshou * (1 ± bili) -> sishewurubaoliu2weixiaoshu
            limit_up_price = np.floor(pre_close * (1 + ratio) * 100 + 0.5) / 100.0
            limit_down_price = np.floor(pre_close * (1 - ratio) * 100 + 0.5) / 100.0

            limit_up_price_Tolerance = round(abs(pre_close * (1 + ratio) - limit_up_price), 10)
            limit_down_price_Tolerance = round(abs(pre_close * (1 - ratio) - limit_down_price), 10)

            # C. jingquebidui
            if current_price > 0 :
                is_limit_up = (current_price > 0) and (abs(current_price - limit_up_price) <= limit_up_price_Tolerance)
                is_limit_down = (current_price > 0) and (abs(current_price - limit_down_price) <= limit_down_price_Tolerance)

                if is_limit_up:
                    limit_up_count += 1
                if is_limit_down:
                    limit_down_count += 1

                if current_price > pre_close:
                    up_count += 1
                elif current_price < pre_close:
                    down_count += 1
                else:
                    flat_count += 1
                
        # tongjishuliang
        stats = {
            'up_count': up_count,
            'down_count': down_count,
            'flat_count': flat_count,
            'limit_up_count': limit_up_count,
            'limit_down_count': limit_down_count,
            'total_amount': 0.0,
        }
        
        # chengjiaoetongji
        if amount_col and amount_col in df.columns:
            df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce')
            stats['total_amount'] = (df[amount_col].sum() / 1e8)
            
        return stats

    def get_sector_rankings(self, n: int = 5) -> Optional[Tuple[List[Dict], List[Dict]]]:
        """
        huoquhangyebankuaizhangdiebang

        shujuyuanyouxianji：
        1. dongcaijiekou (ak.stock_board_industry_name_em)
        2. xinlangjiekou (ak.stock_sector_spot)
        """
        import akshare as ak

        def _get_rank_top_n(df: pd.DataFrame, change_col: str, industry_name: str, n: int) -> Tuple[list, list]:
            df[change_col] = pd.to_numeric(df[change_col], errors='coerce')
            df = df.dropna(subset=[change_col])

            # zhangfuqiann
            top = df.nlargest(n, change_col)
            top_sectors = [
                {'name': row[industry_name], 'change_pct': row[change_col]}
                for _, row in top.iterrows()
            ]

            bottom = df.nsmallest(n, change_col)
            bottom_sectors = [
                {'name': row[industry_name], 'change_pct': row[change_col]}
                for _, row in bottom.iterrows()
            ]
            return top_sectors, bottom_sectors
        
        # youxiandongcaijiekou
        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[APIdiaoyong] ak.stock_board_industry_name_em() huoqubankuaipaihang...")
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                change_col = 'zhangdiefu'
                name = 'bankuaimingcheng'
                return _get_rank_top_n(df, change_col, name, n)
            
        except Exception as e:
            logger.warning(f"[Akshare] dongcaijiekouhuoquhangyebankuaipaihangshibai: {e}，changshixinlangjiekou")

        # dongcaishibaihou，changshixinlangjiekou
        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[APIdiaoyong] ak.stock_sector_spot() huoquhangyebankuaipaihang(xinlang)...")
            df = ak.stock_sector_spot(indicator='hangye')
            if df is None or df.empty:
                return None
            change_col = 'zhangdiefu'
            name = 'bankuai'
            return _get_rank_top_n(df, change_col, name, n)
        
        except Exception as e:
            logger.error(f"[Akshare] xinlangjiekouhuoqubankuaipaihangyeshibai: {e}")
            return None

    def get_concept_rankings(self, n: int = 5) -> Optional[Tuple[List[Dict], List[Dict]]]:
        """huoqugainian/ticaizhangdiebang。"""
        import akshare as ak

        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[APIdiaoyong] ak.stock_board_concept_name_em() huoqugainianpaihang...")
            df = ak.stock_board_concept_name_em()
            if df is None or df.empty:
                return None

            change_col = 'zhangdiefu'
            name_col = 'bankuaimingcheng'
            if change_col not in df.columns or name_col not in df.columns:
                return None

            df = df.copy()
            df[change_col] = pd.to_numeric(df[change_col], errors='coerce')
            df = df.dropna(subset=[change_col])
            top = df.nlargest(n, change_col)
            bottom = df.nsmallest(n, change_col)
            return (
                [
                    {'name': str(row[name_col]), 'change_pct': float(row[change_col])}
                    for _, row in top.iterrows()
                ],
                [
                    {'name': str(row[name_col]), 'change_pct': float(row[change_col])}
                    for _, row in bottom.iterrows()
                ],
            )
        except Exception as e:
            logger.warning(f"[Akshare] huoqugainianpaihangshibai: {e}")
            return None

    def get_hot_stocks(self, n: int = 10) -> Optional[List[Dict[str, Any]]]:
        """huoqurenqigubang，anmianpeizhirebangshujuyuanjiangji。"""
        import akshare as ak

        fetch_attempts = (
            ("dongfangcaifurenqibang", lambda top_n: self._get_eastmoney_hot_stocks(ak, top_n)),
            ("dongfangcaifubiaoshengbang", lambda top_n: self._get_eastmoney_hot_up_stocks(ak, top_n)),
            ("xueqiuguanzhubang", lambda top_n: self._get_xueqiu_hot_stocks(ak, top_n)),
        )
        last_error = ""
        for source, fetch in fetch_attempts:
            try:
                rows = fetch(n)
                if rows:
                    return rows[:n]
            except Exception as e:
                last_error = f"{source}: {e}"
                logger.debug("[Akshare] renqiguhouxuanyuanshibai source=%s: %s", source, e)
        if last_error:
            logger.warning("[Akshare] huoqurenqiguquanbuhouxuanyuanshibai: %s", last_error)
        return None

    def _get_eastmoney_hot_stocks(self, ak: Any, n: int = 10) -> Optional[List[Dict[str, Any]]]:
        """huoqudongfangcaifurenqigubang。"""
        self._set_random_user_agent()
        self._enforce_rate_limit()

        logger.info("[APIdiaoyong] ak.stock_hot_rank_em() huoqudongfangcaifurenqigu...")
        df = ak.stock_hot_rank_em()
        if df is None or df.empty:
            return None

        rows: List[Dict[str, Any]] = []
        for _, row in df.head(n).iterrows():
            rows.append({
                'rank': self._safe_int(row.get('dangqianpaiming')),
                'code': str(row.get('daima', '')).strip(),
                'name': str(row.get('gupiaomingcheng', '')).strip(),
                'price': self._safe_float(row.get('zuixinjia')),
                'change_pct': self._safe_float(row.get('zhangdiefu')),
                'source': 'dongfangcaifurenqibang',
            })
        return rows

    def _get_eastmoney_hot_up_stocks(self, ak: Any, n: int = 10) -> Optional[List[Dict[str, Any]]]:
        """huoqudongfangcaifubiaoshengbang。"""
        self._set_random_user_agent()
        self._enforce_rate_limit()

        logger.info("[APIdiaoyong] ak.stock_hot_up_em() huoqudongfangcaifubiaoshengbang...")
        df = ak.stock_hot_up_em()
        if df is None or df.empty:
            return None

        code_col = self._find_first_column(df, ("daima", "gupiaodaima"))
        name_col = self._find_first_column(df, ("gupiaomingcheng", "mingcheng", "gupiaojiancheng"))
        rank_col = self._find_first_column(df, ("dangqianpaiming", "paiming", "xuhao"))
        price_col = self._find_first_column(df, ("zuixinjia", "xianjia"))
        change_col = self._find_column_containing(df, ("zhangdiefu",))
        if not code_col or not name_col:
            return None

        rows: List[Dict[str, Any]] = []
        for _, row in df.head(n).iterrows():
            rows.append({
                'rank': self._safe_int(row.get(rank_col)) if rank_col else len(rows) + 1,
                'code': str(row.get(code_col, '')).strip(),
                'name': str(row.get(name_col, '')).strip(),
                'price': self._safe_float(row.get(price_col)) if price_col else None,
                'change_pct': self._safe_float(row.get(change_col)) if change_col else None,
                'source': 'dongfangcaifubiaoshengbang',
            })
        return rows

    def _get_xueqiu_hot_stocks(self, ak: Any, n: int = 10) -> Optional[List[Dict[str, Any]]]:
        """huoquxueqiuguanzhubangdoudi。gaijiekoujiaoman，jinzairenqibangshibaihouchangshi。"""
        self._set_random_user_agent()
        self._enforce_rate_limit()

        logger.info("[APIdiaoyong] ak.stock_hot_follow_xq() huoquxueqiuguanzhubang...")
        df = ak.stock_hot_follow_xq(symbol='zuiremen')
        if df is None or df.empty:
            return None

        rows: List[Dict[str, Any]] = []
        for idx, (_, row) in enumerate(df.head(n).iterrows(), 1):
            rows.append({
                'rank': idx,
                'code': str(row.get('gupiaodaima', '')).strip(),
                'name': str(row.get('gupiaojiancheng', '')).strip(),
                'price': self._safe_float(row.get('zuixinjia')),
                'change_pct': None,
                'source': 'xueqiuguanzhubang',
            })
        return rows

    def get_limit_up_pool(
        self,
        date: Optional[str] = None,
        n: int = 20,
    ) -> Optional[List[Dict[str, Any]]]:
        """huoquzhangtingchi，youxiananlianbanshuhefengbanshijianzhanshi。"""
        import akshare as ak

        query_date = date or datetime.now().strftime('%Y%m%d')
        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[APIdiaoyong] ak.stock_zt_pool_em(date=%s) huoquzhangtingchi...", query_date)
            df = ak.stock_zt_pool_em(date=query_date)
            if df is None or df.empty:
                return None

            df = df.copy()
            for col in ('lianbanshu', 'fengbanzijin', 'chengjiaoe', 'huanshoulv', 'zhangdiefu'):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            if 'shoucifengbanshijian' in df.columns:
                df['shoucifengbanshijian'] = df['shoucifengbanshijian'].map(self._normalize_limit_time_value)
                df['_shoucifengbanshijianpaixu'] = df['shoucifengbanshijian'].where(df['shoucifengbanshijian'] != '', '999999')
            sort_cols = [col for col in ('lianbanshu', '_shoucifengbanshijianpaixu') if col in df.columns]
            if sort_cols:
                ascending = [False if col == 'lianbanshu' else True for col in sort_cols]
                df = df.sort_values(sort_cols, ascending=ascending)

            rows: List[Dict[str, Any]] = []
            for _, row in df.head(n).iterrows():
                rows.append({
                    'code': str(row.get('daima', '')).strip(),
                    'name': str(row.get('mingcheng', '')).strip(),
                    'change_pct': self._safe_float(row.get('zhangdiefu')),
                    'price': self._safe_float(row.get('zuixinjia')),
                    'amount': self._safe_float(row.get('chengjiaoe')),
                    'turnover_rate': self._safe_float(row.get('huanshoulv')),
                    'seal_amount': self._safe_float(row.get('fengbanzijin')),
                    'first_limit_time': str(row.get('shoucifengbanshijian', '')).strip(),
                    'last_limit_time': self._normalize_limit_time_value(row.get('zuihoufengbanshijian')),
                    'break_count': self._safe_int(row.get('zhabancishu')),
                    'limit_stat': str(row.get('zhangtingtongji', '')).strip(),
                    'consecutive_boards': self._safe_int(row.get('lianbanshu')),
                    'industry': str(row.get('suoshuhangye', '')).strip(),
                })
            return rows
        except Exception as e:
            logger.warning(f"[Akshare] huoquzhangtingchishibai: {e}")
            return None

    @staticmethod
    def _normalize_limit_time_value(value: Any) -> str:
        """Normalize AkShare HHMMSS-like seal time values to zero-padded HHMMSS."""
        try:
            if pd.isna(value):
                return ""
        except TypeError:
            pass

        text = str(value).strip()
        if not text or text.lower() in {"nan", "nat", "none", "null", "-", "--"}:
            return ""

        if ":" in text:
            parts = text.split(":")
            try:
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                second = int(parts[2]) if len(parts) > 2 else 0
                return f"{hour:02d}{minute:02d}{second:02d}"
            except (TypeError, ValueError):
                return text

        try:
            return f"{int(float(text)):06d}"
        except (TypeError, ValueError):
            digits = "".join(ch for ch in text if ch.isdigit())
            return digits.zfill(6) if digits else text

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            if pd.isna(value):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            if pd.isna(value):
                return 0
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _find_first_column(df: pd.DataFrame, candidates: Tuple[str, ...]) -> Optional[str]:
        columns = [str(col) for col in df.columns]
        for candidate in candidates:
            if candidate in columns:
                return candidate
        return None

    @staticmethod
    def _find_column_containing(df: pd.DataFrame, keywords: Tuple[str, ...]) -> Optional[str]:
        for col in df.columns:
            col_text = str(col)
            if all(keyword in col_text for keyword in keywords):
                return col
        return None


if __name__ == "__main__":
    # ceshidaima
    logging.basicConfig(level=logging.DEBUG)
    
    fetcher = AkshareFetcher()
    
    # ceshiputonggupiao
    print("=" * 50)
    print("ceshiputonggupiaoshujuhuoqu")
    print("=" * 50)
    try:
        df = fetcher.get_daily_data('600519')  # maotai
        print(f"[gupiao] huoquchenggong，gong {len(df)} tiaoshuju")
        print(df.tail())
    except Exception as e:
        print(f"[gupiao] huoqushibai: {e}")
    
    # ceshi ETF jijin
    print("\n" + "=" * 50)
    print("ceshi ETF jijinshujuhuoqu")
    print("=" * 50)
    try:
        df = fetcher.get_daily_data('512400')  # youselongtouETF
        print(f"[ETF] huoquchenggong，gong {len(df)} tiaoshuju")
        print(df.tail())
    except Exception as e:
        print(f"[ETF] huoqushibai: {e}")
    
    # ceshi ETF shishixingqing
    print("\n" + "=" * 50)
    print("ceshi ETF shishixingqinghuoqu")
    print("=" * 50)
    try:
        quote = fetcher.get_realtime_quote('512880')  # zhengquanETF
        if quote:
            print(f"[ETFshishi] {quote.name}: jiage={quote.price}, zhangdiefu={quote.change_pct}%")
        else:
            print("[ETFshishi] weihuoqudaoshuju")
    except Exception as e:
        print(f"[ETFshishi] huoqushibai: {e}")
    
    # ceshiganggulishishuju
    print("\n" + "=" * 50)
    print("ceshiganggulishishujuhuoqu")
    print("=" * 50)
    try:
        df = fetcher.get_daily_data('00700')  # tengxunkonggu
        print(f"[ganggu] huoquchenggong，gong {len(df)} tiaoshuju")
        print(df.tail())
    except Exception as e:
        print(f"[ganggu] huoqushibai: {e}")
    
    # ceshiganggushishixingqing
    print("\n" + "=" * 50)
    print("ceshiganggushishixingqinghuoqu")
    print("=" * 50)
    try:
        quote = fetcher.get_realtime_quote('00700')  # tengxunkonggu
        if quote:
            print(f"[ganggushishi] {quote.name}: jiage={quote.price}, zhangdiefu={quote.change_pct}%")
        else:
            print("[ganggushishi] weihuoqudaoshuju")
    except Exception as e:
        print(f"[ganggushishi] huoqushibai: {e}")

    # ceshishichangtongji
    print("\n" + "=" * 50)
    print("Testing get_market_stats (akshare)")
    print("=" * 50)
    try:
        stats = fetcher.get_market_stats()
        if stats:
            print(f"Market Stats successfully computed:")
            print(f"Up: {stats['up_count']} (Limit Up: {stats['limit_up_count']})")
            print(f"Down: {stats['down_count']} (Limit Down: {stats['limit_down_count']})")
            print(f"Flat: {stats['flat_count']}")
            print(f"Total Amount: {stats['total_amount']:.2f} yi (Yi)")
        else:
            print("Failed to compute market stats.")
    except Exception as e:
        print(f"Failed to compute market stats: {e}")

    # ceshichoumafenbushuju
    print("\n" + "=" * 50)
    print("ceshichoumafenbushujuhuoqu")
    print("=" * 50)
    try:
        chip = fetcher.get_chip_distribution('600519')  # maotai
    except Exception as e:
        print(f"[choumafenbu] huoqushibai: {e}")

    # ceshixingyebankuaipaiming
    print("\n" + "=" * 50)
    print("ceshixingyebankuaipaiminghuoqu")
    print("=" * 50)
    try:
        rankings = fetcher.get_sector_rankings(n=5)
        if rankings:
            top, bottom = rankings
            print("zhangfubang Top 5:")
            for sector in top:
                print(f"{sector['name']}: {sector['change_pct']}%")
            print("\ndiefubang Top 5:")
            for sector in bottom:
                print(f"{sector['name']}: {sector['change_pct']}%")
        else:
            print("weihuoqudaohangyebankuaipaimingshuju")
    except Exception as e:
        print(f"[hangyebankuaipaiming] huoqushibai: {e}")
