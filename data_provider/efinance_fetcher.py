# -*- coding: utf-8 -*-
"""
===================================
EfinanceFetcher - youxianshujuyuan (Priority 0)
===================================

shujulaiyuan：dongfangcaifupachong（tongguo efinance ku）
tedian：mianfei、wuxu Token、shujuquanmian、API jianjie
cangku：https://github.com/Micro-sheep/efinance

yu AkshareFetcher leisi，dan efinance ku：
1. API gengjianjieyiyong
2. zhichipilianghuoqushuju
3. gengwendingdejiekoufengzhuang

fangfengjincelve：
1. meiciqingqiuqiansuijixiumian 1.5-3.0 miao
2. suijilunhuan User-Agent
3. shiyong tenacity shixianzhishutuibizhongshi
4. rongduanqijizhi：lianxushibaihouzidonglengque
"""

import logging
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd
import requests  # yinru requests yibuhuoyichang
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

# Timeout (seconds) for efinance library calls that go through eastmoney APIs
# with no built-in timeout.  Prevents indefinite hangs when hosts are unreachable.
try:
    _EF_CALL_TIMEOUT = int(os.environ.get("EFINANCE_CALL_TIMEOUT", "30"))
except (ValueError, TypeError):
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "EFINANCE_CALL_TIMEOUT is not a valid integer, using default 30s"
    )
    _EF_CALL_TIMEOUT = 30

from src.patches.eastmoney_patch import eastmoney_patch
from src.config import get_config
from .base import BaseFetcher, DataFetchError, RateLimitError, STANDARD_COLUMNS,is_bse_code, is_st_stock, is_kc_cy_stock, normalize_stock_code, _is_hk_market
from .realtime_types import (
    UnifiedRealtimeQuote, RealtimeSource,
    get_realtime_circuit_breaker,
    safe_float, safe_int  # shiyongtongyideleixingzhuanhuanhanshu
)


# baoliujiudeleixingbieming，yongyuxianghoujianrong
@dataclass
class EfinanceRealtimeQuote:
    """
    shishixingqingshuju（laizi efinance）- xianghoujianrongbieming
    
    xindaimajianyishiyong UnifiedRealtimeQuote
    """
    code: str
    name: str = ""
    price: float = 0.0           # zuixinjia
    change_pct: float = 0.0      # zhangdiefu(%)
    change_amount: float = 0.0   # zhangdiee
    
    # liangjiazhibiao
    volume: int = 0              # chengjiaoliang
    amount: float = 0.0          # chengjiaoe
    turnover_rate: float = 0.0   # huanshoulv(%)
    amplitude: float = 0.0       # zhenfu(%)
    
    # jiagequjian
    high: float = 0.0            # zuigaojia
    low: float = 0.0             # zuidijia
    open_price: float = 0.0      # kaipanjia
    
    def to_dict(self) -> Dict[str, Any]:
        """zhuanhuanweizidian"""
        return {
            'code': self.code,
            'name': self.name,
            'price': self.price,
            'change_pct': self.change_pct,
            'change_amount': self.change_amount,
            'volume': self.volume,
            'amount': self.amount,
            'turnover_rate': self.turnover_rate,
            'amplitude': self.amplitude,
            'high': self.high,
            'low': self.low,
            'open': self.open_price,
        }


logger = logging.getLogger(__name__)

EASTMONEY_HISTORY_ENDPOINT = "push2his.eastmoney.com/api/qt/stock/kline/get"


# User-Agent chi，yongyusuijilunhuan
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


# huancunshishixingqingshuju（bimianchongfuqingqiu）
# TTL shewei 10 fenzhong (600miao)：piliangfenxichangjingxiabimianchongfulaqu
_realtime_cache: Dict[str, Any] = {
    'data': None,
    'timestamp': 0,
    'ttl': 600  # 10fenzhonghuancunyouxiaoqi
}

# ETF shishixingqinghuancun（yugupiaofenkaihuancun）
_etf_realtime_cache: Dict[str, Any] = {
    'data': None,
    'timestamp': 0,
    'ttl': 600  # 10fenzhonghuancunyouxiaoqi
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
    return stock_code.startswith(etf_prefixes) and len(stock_code) == 6


def _is_us_code(stock_code: str) -> bool:
    """
    panduandaimashifouweimeigu
    
    meigudaimaguize：
    - 1-5gedaxiezimu，ru 'AAPL', 'TSLA'
    - kenengbaohan '.'，ru 'BRK.B'
    """
    code = stock_code.strip().upper()
    return bool(re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', code))


def _ef_call_with_timeout(func, *args, timeout=None, **kwargs):
    """Run an efinance library call in a thread with a timeout.

    efinance internally uses requests/urllib3 with no timeout, so when
    eastmoney hosts are unreachable the call can hang for many minutes.
    This helper caps the *calling thread's* wait time.  Note: Python threads
    cannot be forcibly killed, so the worker thread may continue running in
    the background until the OS-level TCP timeout fires or the process exits.
    This is acceptable — the calling thread returns promptly on timeout.
    """
    if timeout is None:
        timeout = _EF_CALL_TIMEOUT
    # Do NOT use 'with ThreadPoolExecutor(...)' here: the context manager calls
    # shutdown(wait=True) on __exit__, which would re-block on the hung thread.
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(func, *args, **kwargs)
        return future.result(timeout=timeout)
    finally:
        # wait=False: calling thread returns immediately; worker cleans up later
        executor.shutdown(wait=False)


def _classify_eastmoney_error(exc: Exception) -> Tuple[str, str]:
    """
    Classify Eastmoney request failures into stable log categories.
    """
    message = str(exc).strip()
    lowered = message.lower()

    remote_disconnect_keywords = (
        'remotedisconnected',
        'remote end closed connection without response',
        'connection aborted',
        'connection broken',
        'protocolerror',
    )
    timeout_keywords = (
        'timeout',
        'timed out',
        'readtimeout',
        'connecttimeout',
    )
    rate_limit_keywords = (
        'banned',
        'blocked',
        'pinlv',
        'rate limit',
        'too many requests',
        '429',
        'xianzhi',
        'forbidden',
        '403',
    )

    if any(keyword in lowered for keyword in remote_disconnect_keywords):
        return "remote_disconnect", message
    if isinstance(exc, (TimeoutError, requests.exceptions.Timeout)) or any(
        keyword in lowered for keyword in timeout_keywords
    ):
        return "timeout", message
    if any(keyword in lowered for keyword in rate_limit_keywords):
        return "rate_limit_or_anti_bot", message
    if isinstance(exc, requests.exceptions.RequestException):
        return "request_error", message
    return "unknown_request_error", message


class EfinanceFetcher(BaseFetcher):
    """
    Efinance shujuyuanshixian
    
    youxianji：0（zuigao，youxianyu AkshareFetcher）
    shujulaiyuan：dongfangcaifuwang（tongguo efinance kufengzhuang）
    cangku：https://github.com/Micro-sheep/efinance
    
    zhuyao API：
    - ef.stock.get_quote_history(): huoqulishi K xianshuju
    - ef.stock.get_base_info(): huoqugupiaojibenxinxi
    - ef.stock.get_realtime_quotes(): huoqushishixingqing
    
    guanjiancelve：
    - meiciqingqiuqiansuijixiumian 1.5-3.0 miao
    - suiji User-Agent lunhuan
    - shibaihouzhishutuibizhongshi（zuiduo3ci）
    """
    
    name = "EfinanceFetcher"
    priority = int(os.getenv("EFINANCE_PRIORITY", "0"))  # zuigaoyouxianji，paizai AkshareFetcher zhiqian
    
    def __init__(self, sleep_min: float = 1.5, sleep_max: float = 3.0):
        """
        chushihua EfinanceFetcher
        
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

    @staticmethod
    def _build_history_failure_message(
        stock_code: str,
        beg_date: str,
        end_date: str,
        exc: Exception,
        elapsed: float,
        is_etf: bool = False,
    ) -> Tuple[str, str]:
        category, detail = _classify_eastmoney_error(exc)
        instrument_type = "ETF" if is_etf else "stock"
        message = (
            "Eastmoney lishiKxianjiekoushibai: "
            f"endpoint={EASTMONEY_HISTORY_ENDPOINT}, stock_code={stock_code}, "
            f"market_type={instrument_type}, range={beg_date}~{end_date}, "
            f"category={category}, error_type={type(exc).__name__}, elapsed={elapsed:.2f}s, detail={detail}"
        )
        return category, message

    def _set_random_user_agent(self) -> None:
        """
        shezhisuiji User-Agent
        
        tongguoxiugai requests Session de headers shixian
        zheshiguanjiandefanpacelvezhiyi
        """
        try:
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
        stop=stop_after_attempt(1),  # jianshaodao1ci，bimianchufaxianliu
        wait=wait_exponential(multiplier=1, min=4, max=60),  # baochidengdaishijianshezhi
        retry=retry_if_exception_type((
            ConnectionError,
            TimeoutError,
            requests.exceptions.RequestException,
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        cong efinance huoquyuanshishuju
        
        genjudaimaleixingzidongxuanze API：
        - meigu：buzhichi，paochuyichangrang DataFetcherManager qiehuandaoqitashujuyuan
        - putonggupiao：shiyong ef.stock.get_quote_history()
        - ETF jijin：shiyong ef.stock.get_quote_history()（ETF shijiaoyisuozhengquan，shiyonggupiao K xianjiekou）
        
        liucheng：
        1. panduandaimaleixing（meigu/gupiao/ETF）
        2. shezhisuiji User-Agent
        3. zhixingsulvxianzhi（suijixiumian）
        4. diaoyongduiyingde efinance API
        5. chulifanhuishuju
        """
        # meigubuzhichi，paochuyichangrang DataFetcherManager qiehuandao AkshareFetcher/YfinanceFetcher
        if _is_us_code(stock_code):
            raise DataFetchError(f"EfinanceFetcher buzhichimeigu {stock_code}，qingshiyong AkshareFetcher huo YfinanceFetcher")

        # efinance delishi K xianjiekouzaiganggudaimashangkenengfanhuifeiyuqishichangshuju，
        # mingquetiaoguobingjiaogei AkShare/Tushare/YFinance/Longbridge dengganggulujingdoudi。
        if _is_hk_market(stock_code):
            raise DataFetchError(f"EfinanceFetcher buzhichiganggurixian {stock_code}，qingshiyong AkshareFetcher huoqitaganggushujuyuan")
        
        # genjudaimaleixingxuanzebutongdehuoqufangfa
        if _is_etf_code(stock_code):
            return self._fetch_etf_data(stock_code, start_date, end_date)
        else:
            return self._fetch_stock_data(stock_code, start_date, end_date)
    
    def _fetch_stock_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        huoquputong A gulishishuju
        
        shujulaiyuan：ef.stock.get_quote_history()
        
        API canshushuoming：
        - stock_codes: gupiaodaima
        - beg: kaishiriqi，geshi 'YYYYMMDD'
        - end: jieshuriqi，geshi 'YYYYMMDD'
        - klt: zhouqi，101=rixian
        - fqt: fuquanfangshi，1=qianfuquan
        """
        import efinance as ef
        
        # fangfengjincelve 1: suiji User-Agent
        self._set_random_user_agent()
        
        # fangfengjincelve 2: qiangzhixiumian
        self._enforce_rate_limit()
        
        # geshihuariqi（efinance shiyong YYYYMMDD geshi）
        beg_date = start_date.replace('-', '')
        end_date_fmt = end_date.replace('-', '')
        
        logger.info(f"[APIdiaoyong] ef.stock.get_quote_history(stock_codes={stock_code}, "
                   f"beg={beg_date}, end={end_date_fmt}, klt=101, fqt=1)")
        
        api_start = time.time()
        try:
            # diaoyong efinance huoqu A gurixianshuju
            # klt=101 huoqurixianshuju
            # fqt=1 huoquqianfuquanshuju
            df = _ef_call_with_timeout(
                ef.stock.get_quote_history,
                stock_codes=stock_code,
                beg=beg_date,
                end=end_date_fmt,
                klt=101,  # rixian
                fqt=1,    # qianfuquan
                timeout=60,
            )
            
            api_elapsed = time.time() - api_start
            
            # jilufanhuishujuzhaiyao
            if df is not None and not df.empty:
                logger.info(
                    "[APIfanhui] Eastmoney lishiKxianchenggong: "
                    f"endpoint={EASTMONEY_HISTORY_ENDPOINT}, stock_code={stock_code}, "
                    f"range={beg_date}~{end_date_fmt}, rows={len(df)}, elapsed={api_elapsed:.2f}s"
                )
                logger.info(f"[APIfanhui] lieming: {list(df.columns)}")
                if 'riqi' in df.columns:
                    logger.info(f"[APIfanhui] riqifanwei: {df['riqi'].iloc[0]} ~ {df['riqi'].iloc[-1]}")
                logger.debug(f"[APIfanhui] zuixin3tiaoshuju:\n{df.tail(3).to_string()}")
            else:
                logger.warning(
                    "[APIfanhui] Eastmoney lishiKxianweikong: "
                    f"endpoint={EASTMONEY_HISTORY_ENDPOINT}, stock_code={stock_code}, "
                    f"range={beg_date}~{end_date_fmt}, elapsed={api_elapsed:.2f}s"
                )
            
            return df
            
        except Exception as e:
            api_elapsed = time.time() - api_start
            category, failure_message = self._build_history_failure_message(
                stock_code=stock_code,
                beg_date=beg_date,
                end_date=end_date_fmt,
                exc=e,
                elapsed=api_elapsed,
            )

            if category == "rate_limit_or_anti_bot":
                logger.warning(failure_message)
                raise RateLimitError(f"efinance kenengbeixianliu: {failure_message}") from e

            logger.error(failure_message)
            raise DataFetchError(f"efinance huoqushujushibai: {failure_message}") from e
    
    def _fetch_etf_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        huoqu ETF jijinlishishuju

        Exchange-traded ETFs have OHLCV data just like regular stocks, so we use
        ef.stock.get_quote_history (the stock K-line API) which returns full
        open/high/low/close/volume data.

        Previously this method used ef.fund.get_quote_history which only returns
        NAV data (danweijingzhi/leijijingzhi) without volume or OHLC, causing:
        - Issue #541: 'got an unexpected keyword argument beg'
        - Issue #527: ETF volume/turnover always showing 0

        Args:
            stock_code: ETF code, e.g. '512400', '159883', '515120'
            start_date: Start date, format 'YYYY-MM-DD'
            end_date: End date, format 'YYYY-MM-DD'

        Returns:
            ETF historical OHLCV DataFrame
        """
        import efinance as ef

        # Anti-ban strategy 1: random User-Agent
        self._set_random_user_agent()

        # Anti-ban strategy 2: enforce rate limit
        self._enforce_rate_limit()

        # Format dates (efinance uses YYYYMMDD)
        beg_date = start_date.replace('-', '')
        end_date_fmt = end_date.replace('-', '')

        logger.info(f"[APIdiaoyong] ef.stock.get_quote_history(stock_codes={stock_code}, "
                     f"beg={beg_date}, end={end_date_fmt}, klt=101, fqt=1)  [ETF]")

        api_start = time.time()
        try:
            # ETFs are exchange-traded securities; use the stock API to get full OHLCV data
            df = _ef_call_with_timeout(
                ef.stock.get_quote_history,
                stock_codes=stock_code,
                beg=beg_date,
                end=end_date_fmt,
                klt=101,  # daily
                fqt=1,    # forward-adjusted
                timeout=60,
            )

            api_elapsed = time.time() - api_start

            if df is not None and not df.empty:
                logger.info(
                    "[APIfanhui] Eastmoney lishiKxianchenggong [ETF]: "
                    f"endpoint={EASTMONEY_HISTORY_ENDPOINT}, stock_code={stock_code}, "
                    f"range={beg_date}~{end_date_fmt}, rows={len(df)}, elapsed={api_elapsed:.2f}s"
                )
                logger.info(f"[APIfanhui] lieming: {list(df.columns)}")
                if 'riqi' in df.columns:
                    logger.info(f"[APIfanhui] riqifanwei: {df['riqi'].iloc[0]} ~ {df['riqi'].iloc[-1]}")
                logger.debug(f"[APIfanhui] zuixin3tiaoshuju:\n{df.tail(3).to_string()}")
            else:
                logger.warning(
                    "[APIfanhui] Eastmoney lishiKxianweikong [ETF]: "
                    f"endpoint={EASTMONEY_HISTORY_ENDPOINT}, stock_code={stock_code}, "
                    f"range={beg_date}~{end_date_fmt}, elapsed={api_elapsed:.2f}s"
                )

            return df

        except Exception as e:
            api_elapsed = time.time() - api_start
            category, failure_message = self._build_history_failure_message(
                stock_code=stock_code,
                beg_date=beg_date,
                end_date=end_date_fmt,
                exc=e,
                elapsed=api_elapsed,
                is_etf=True,
            )

            if category == "rate_limit_or_anti_bot":
                logger.warning(failure_message)
                raise RateLimitError(f"efinance kenengbeixianliu: {failure_message}") from e

            logger.error(failure_message)
            raise DataFetchError(f"efinance huoqu ETF shujushibai: {failure_message}") from e
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        biaozhunhua efinance shuju
        
        efinance fanhuidelieming（zhongwen）：
        gupiaomingcheng, gupiaodaima, riqi, kaipan, shoupan, zuigao, zuidi, chengjiaoliang, chengjiaoe, zhenfu, zhangdiefu, zhangdiee, huanshoulv
        
        xuyaoyingshedaobiaozhunlieming：
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()
        
        # Column mapping (efinance Chinese column names -> standard English column names)
        column_mapping = {
            'riqi': 'date',
            'kaipan': 'open',
            'shoupan': 'close',
            'zuigao': 'high',
            'zuidi': 'low',
            'chengjiaoliang': 'volume',
            'chengjiaoe': 'amount',
            'zhangdiefu': 'pct_chg',
            'gupiaodaima': 'code',
            'gupiaomingcheng': 'name',
        }
        
        # zhongmingminglie
        df = df.rename(columns=column_mapping)
        
        # Fallback: if OHLC columns are missing (e.g. very old data path), fill from close
        if 'close' in df.columns and 'open' not in df.columns:
            df['open'] = df['close']
            df['high'] = df['close']
            df['low'] = df['close']
            
        # Fill volume and amount if missing
        if 'volume' not in df.columns:
            df['volume'] = 0
        if 'amount' not in df.columns:
            df['amount'] = 0

        
        # ruguomeiyou code lie，shoudongtianjia
        if 'code' not in df.columns:
            df['code'] = stock_code
        
        # zhibaoliuxuyaodelie
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]
        
        return df
    
    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        huoqushishixingqingshuju
        
        shujulaiyuan：ef.stock.get_realtime_quotes()
        ETF shujuyuan：ef.stock.get_realtime_quotes(['ETF'])
        
        Args:
            stock_code: gupiaodaima
            
        Returns:
            UnifiedRealtimeQuote duixiang，huoqushibaifanhui None
        """
        # ETF xuyaodanduqingqiu ETF shishixingqingjiekou
        if _is_etf_code(stock_code):
            return self._get_etf_realtime_quote(stock_code)

        import efinance as ef
        circuit_breaker = get_realtime_circuit_breaker()
        source_key = "efinance"
        
        # jiancharongduanqizhuangtai
        if not circuit_breaker.is_available(source_key):
            logger.info(f"[rongduan] shujuyuan {source_key} chuyurongduanzhuangtai，tiaoguo")
            return None
        
        try:
            # jianchahuancun
            current_time = time.time()
            if (_realtime_cache['data'] is not None and 
                current_time - _realtime_cache['timestamp'] < _realtime_cache['ttl']):
                df = _realtime_cache['data']
                cache_age = int(current_time - _realtime_cache['timestamp'])
                logger.debug(f"[huancunmingzhong] shishixingqing(efinance) - huancunnianling {cache_age}s/{_realtime_cache['ttl']}s")
            else:
                # chufaquanliangshuaxin
                logger.info(f"[huancunweimingzhong] chufaquanliangshuaxin shishixingqing(efinance)")
                # fangfengjincelve
                self._set_random_user_agent()
                self._enforce_rate_limit()
                
                logger.info(f"[APIdiaoyong] ef.stock.get_realtime_quotes() huoqushishixingqing...")
                import time as _time
                api_start = _time.time()
                
                # efinance deshishixingqing API (with timeout to avoid indefinite hangs)
                df = _ef_call_with_timeout(ef.stock.get_realtime_quotes)
                
                api_elapsed = _time.time() - api_start
                logger.info(f"[APIfanhui] ef.stock.get_realtime_quotes chenggong: fanhui {len(df)} zhigupiao, haoshi {api_elapsed:.2f}s")
                circuit_breaker.record_success(source_key)
                
                # gengxinhuancun
                _realtime_cache['data'] = df
                _realtime_cache['timestamp'] = current_time
                logger.info(f"[huancungengxin] shishixingqing(efinance) huancunyishuaxin，TTL={_realtime_cache['ttl']}s")
            
            # chazhaozhidinggupiao
            # efinance fanhuideliemingkenengshi 'gupiaodaima' huo 'code'
            code_col = 'gupiaodaima' if 'gupiaodaima' in df.columns else 'code'
            row = df[df[code_col] == stock_code]
            if row.empty:
                logger.info(f"[APIfanhui] weizhaodaogupiao {stock_code} deshishixingqing")
                return None
            
            row = row.iloc[0]
            
            # shiyong realtime_types.py zhongdetongyizhuanhuanhanshu
            # huoqulieming（kenengshizhongwenhuoyingwen）
            name_col = 'gupiaomingcheng' if 'gupiaomingcheng' in df.columns else 'name'
            price_col = 'zuixinjia' if 'zuixinjia' in df.columns else 'price'
            pct_col = 'zhangdiefu' if 'zhangdiefu' in df.columns else 'pct_chg'
            chg_col = 'zhangdiee' if 'zhangdiee' in df.columns else 'change'
            vol_col = 'chengjiaoliang' if 'chengjiaoliang' in df.columns else 'volume'
            amt_col = 'chengjiaoe' if 'chengjiaoe' in df.columns else 'amount'
            turn_col = 'huanshoulv' if 'huanshoulv' in df.columns else 'turnover_rate'
            amp_col = 'zhenfu' if 'zhenfu' in df.columns else 'amplitude'
            high_col = 'zuigao' if 'zuigao' in df.columns else 'high'
            low_col = 'zuidi' if 'zuidi' in df.columns else 'low'
            open_col = 'kaipan' if 'kaipan' in df.columns else 'open'
            # efinance yefanhuiliangbi、shiyinglv、shizhidengziduan
            vol_ratio_col = 'liangbi' if 'liangbi' in df.columns else 'volume_ratio'
            pe_col = 'shiyinglv' if 'shiyinglv' in df.columns else 'pe_ratio'
            total_mv_col = 'zongshizhi' if 'zongshizhi' in df.columns else 'total_mv'
            circ_mv_col = 'liutongshizhi' if 'liutongshizhi' in df.columns else 'circ_mv'
            
            quote = UnifiedRealtimeQuote(
                code=stock_code,
                name=str(row.get(name_col, '')),
                source=RealtimeSource.EFINANCE,
                price=safe_float(row.get(price_col)),
                change_pct=safe_float(row.get(pct_col)),
                change_amount=safe_float(row.get(chg_col)),
                volume=safe_int(row.get(vol_col)),
                amount=safe_float(row.get(amt_col)),
                turnover_rate=safe_float(row.get(turn_col)),
                amplitude=safe_float(row.get(amp_col)),
                high=safe_float(row.get(high_col)),
                low=safe_float(row.get(low_col)),
                open_price=safe_float(row.get(open_col)),
                volume_ratio=safe_float(row.get(vol_ratio_col)),  # liangbi
                pe_ratio=safe_float(row.get(pe_col)),  # shiyinglv
                total_mv=safe_float(row.get(total_mv_col)),  # zongshizhi
                circ_mv=safe_float(row.get(circ_mv_col)),  # liutongshizhi
            )
            
            logger.info(f"[shishixingqing-efinance] {stock_code} {quote.name}: jiage={quote.price}, zhangdie={quote.change_pct}%, "
                       f"liangbi={quote.volume_ratio}, huanshoulv={quote.turnover_rate}%")
            return quote
            
        except FuturesTimeoutError:
            logger.info(f"[chaoshi] ef.stock.get_realtime_quotes() chaoguo {_EF_CALL_TIMEOUT}s，tiaoguo {stock_code}")
            circuit_breaker.record_failure(source_key, "timeout")
            return None
        except Exception as e:
            logger.info(f"[APIcuowu] huoqu {stock_code} shishixingqing(efinance)shibai: {e}")
            circuit_breaker.record_failure(source_key, str(e))
            return None

    def _get_etf_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        huoqu ETF shishixingqing

        efinance morenshishijiekoujinfanhuigupiaoshuju，ETF xuyaoxianshichuanru ['ETF']。
        """
        import efinance as ef
        circuit_breaker = get_realtime_circuit_breaker()
        source_key = "efinance_etf"

        if not circuit_breaker.is_available(source_key):
            logger.info(f"[rongduan] shujuyuan {source_key} chuyurongduanzhuangtai，tiaoguo")
            return None

        try:
            current_time = time.time()
            if (
                _etf_realtime_cache['data'] is not None and
                current_time - _etf_realtime_cache['timestamp'] < _etf_realtime_cache['ttl']
            ):
                df = _etf_realtime_cache['data']
                cache_age = int(current_time - _etf_realtime_cache['timestamp'])
                logger.debug(f"[huancunmingzhong] ETFshishixingqing(efinance) - huancunnianling {cache_age}s/{_etf_realtime_cache['ttl']}s")
            else:
                self._set_random_user_agent()
                self._enforce_rate_limit()

                logger.info("[APIdiaoyong] ef.stock.get_realtime_quotes(['ETF']) huoquETFshishixingqing...")
                import time as _time
                api_start = _time.time()
                df = _ef_call_with_timeout(ef.stock.get_realtime_quotes, ['ETF'])
                api_elapsed = _time.time() - api_start

                if df is not None and not df.empty:
                    logger.info(f"[APIfanhui] ETF shishixingqingchenggong: {len(df)} tiao, haoshi {api_elapsed:.2f}s")
                    circuit_breaker.record_success(source_key)
                else:
                    logger.info(f"[APIfanhui] ETF shishixingqingweikong, haoshi {api_elapsed:.2f}s")
                    df = pd.DataFrame()

                _etf_realtime_cache['data'] = df
                _etf_realtime_cache['timestamp'] = current_time

            if df is None or df.empty:
                logger.info(f"[shishixingqing] ETFshishixingqingshujuweikong(efinance)，tiaoguo {stock_code}")
                return None

            code_col = 'gupiaodaima' if 'gupiaodaima' in df.columns else 'code'
            code_series = df[code_col].astype(str).str.zfill(6)
            target_code = str(stock_code).strip().zfill(6)
            row = df[code_series == target_code]
            if row.empty:
                logger.info(f"[APIfanhui] weizhaodao ETF {stock_code} deshishixingqing(efinance)")
                return None

            row = row.iloc[0]
            name_col = 'gupiaomingcheng' if 'gupiaomingcheng' in df.columns else 'name'
            price_col = 'zuixinjia' if 'zuixinjia' in df.columns else 'price'
            pct_col = 'zhangdiefu' if 'zhangdiefu' in df.columns else 'pct_chg'
            chg_col = 'zhangdiee' if 'zhangdiee' in df.columns else 'change'
            vol_col = 'chengjiaoliang' if 'chengjiaoliang' in df.columns else 'volume'
            amt_col = 'chengjiaoe' if 'chengjiaoe' in df.columns else 'amount'
            turn_col = 'huanshoulv' if 'huanshoulv' in df.columns else 'turnover_rate'
            amp_col = 'zhenfu' if 'zhenfu' in df.columns else 'amplitude'
            high_col = 'zuigao' if 'zuigao' in df.columns else 'high'
            low_col = 'zuidi' if 'zuidi' in df.columns else 'low'
            open_col = 'kaipan' if 'kaipan' in df.columns else 'open'

            quote = UnifiedRealtimeQuote(
                code=target_code,
                name=str(row.get(name_col, '')),
                source=RealtimeSource.EFINANCE,
                price=safe_float(row.get(price_col)),
                change_pct=safe_float(row.get(pct_col)),
                change_amount=safe_float(row.get(chg_col)),
                volume=safe_int(row.get(vol_col)),
                amount=safe_float(row.get(amt_col)),
                turnover_rate=safe_float(row.get(turn_col)),
                amplitude=safe_float(row.get(amp_col)),
                high=safe_float(row.get(high_col)),
                low=safe_float(row.get(low_col)),
                open_price=safe_float(row.get(open_col)),
            )

            logger.info(
                f"[ETFshishixingqing-efinance] {target_code} {quote.name}: "
                f"jiage={quote.price}, zhangdie={quote.change_pct}%, huanshoulv={quote.turnover_rate}%"
            )
            return quote
        except Exception as e:
            logger.info(f"[APIcuowu] huoqu ETF {stock_code} shishixingqing(efinance)shibai: {e}")
            circuit_breaker.record_failure(source_key, str(e))
            return None

    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """
        huoquzhuyaozhishushishixingqing (efinance)，jinzhichi A gu
        """
        if region != "cn":
            return None
        import efinance as ef

        indices_map = {
            '000001': ('shangzhengzhishu', 'sh000001'),
            '399001': ('shenzhengchengzhi', 'sz399001'),
            '399006': ('chuangyebanzhi', 'sz399006'),
            '000688': ('kechuang50', 'sh000688'),
            '000016': ('shangzheng50', 'sh000016'),
            '000300': ('hushen300', 'sh000300'),
        }

        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[APIdiaoyong] ef.stock.get_realtime_quotes(['hushenxiliezhishu']) huoquzhishuhangqing...")
            import time as _time
            api_start = _time.time()
            df = _ef_call_with_timeout(ef.stock.get_realtime_quotes, ['hushenxiliezhishu'])
            api_elapsed = _time.time() - api_start

            if df is None or df.empty:
                logger.warning(f"[APIfanhui] zhishuhangqingweikong, haoshi {api_elapsed:.2f}s")
                return None

            logger.info(f"[APIfanhui] zhishuhangqingchenggong: {len(df)} tiao, haoshi {api_elapsed:.2f}s")
            code_col = 'gupiaodaima' if 'gupiaodaima' in df.columns else 'code'
            code_series = df[code_col].astype(str).str.zfill(6)

            results: List[Dict[str, Any]] = []
            for code, (name, full_code) in indices_map.items():
                row = df[code_series == code]
                if row.empty:
                    continue
                item = row.iloc[0]

                price_col = 'zuixinjia' if 'zuixinjia' in df.columns else 'price'
                pct_col = 'zhangdiefu' if 'zhangdiefu' in df.columns else 'pct_chg'
                chg_col = 'zhangdiee' if 'zhangdiee' in df.columns else 'change'
                open_cols = [column for column in ('jinkai', 'kaipan', 'open') if column in df.columns]
                high_col = 'zuigao' if 'zuigao' in df.columns else 'high'
                low_col = 'zuidi' if 'zuidi' in df.columns else 'low'
                vol_col = 'chengjiaoliang' if 'chengjiaoliang' in df.columns else 'volume'
                amt_col = 'chengjiaoe' if 'chengjiaoe' in df.columns else 'amount'
                amp_col = 'zhenfu' if 'zhenfu' in df.columns else 'amplitude'

                current = safe_float(item.get(price_col, 0))
                change_amount = safe_float(item.get(chg_col, 0))
                open_price = 0.0
                for column in open_cols:
                    candidate = safe_float(item.get(column), default=None)
                    if candidate not in (None, 0.0):
                        open_price = candidate
                        break
                if open_price == 0.0 and open_cols:
                    open_price = safe_float(item.get(open_cols[0], 0), 0)

                results.append({
                    'code': full_code,
                    'name': name,
                    'current': current,
                    'change': change_amount,
                    'change_pct': safe_float(item.get(pct_col, 0)),
                    'open': open_price,
                    'high': safe_float(item.get(high_col, 0)),
                    'low': safe_float(item.get(low_col, 0)),
                    'prev_close': current - change_amount if current or change_amount else 0,
                    'volume': safe_float(item.get(vol_col, 0)),
                    'amount': safe_float(item.get(amt_col, 0)),
                    'amplitude': safe_float(item.get(amp_col, 0)),
                })

            if results:
                logger.info(f"[efinance] huoqudao {len(results)} gezhishuhangqing")
            return results if results else None
        except Exception as e:
            logger.error(f"[efinance] huoquzhishuhangqingshibai: {e}")
            return None

    def get_market_stats(self) -> Optional[Dict[str, Any]]:
        """
        huoqushichangzhangdietongji (efinance)
        """
        import efinance as ef

        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            current_time = time.time()
            if (
                _realtime_cache['data'] is not None and
                current_time - _realtime_cache['timestamp'] < _realtime_cache['ttl']
            ):
                df = _realtime_cache['data']
            else:
                logger.info("[APIdiaoyong] ef.stock.get_realtime_quotes() huoqushichangtongji...")
                df = _ef_call_with_timeout(ef.stock.get_realtime_quotes)
                _realtime_cache['data'] = df
                _realtime_cache['timestamp'] = current_time

            if df is None or df.empty:
                logger.warning("[APIfanhui] shichangtongjishujuweikong")
                return None

            return self._calc_market_stats(df)
        except Exception as e:
            logger.error(f"[efinance] huoqushichangtongjishibai: {e}")
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
        huoqubankuaizhangdiebang (efinance)
        """
        import efinance as ef

        try:
            self._set_random_user_agent()
            self._enforce_rate_limit()

            logger.info("[APIdiaoyong] ef.stock.get_realtime_quotes(['hangyebankuai']) huoqubankuaihangqing...")
            df = _ef_call_with_timeout(ef.stock.get_realtime_quotes, ['hangyebankuai'])
            if df is None or df.empty:
                logger.warning("[efinance] bankuaihangqingshujuweikong")
                return None

            change_col = 'zhangdiefu' if 'zhangdiefu' in df.columns else 'pct_chg'
            name_col = 'gupiaomingcheng' if 'gupiaomingcheng' in df.columns else 'name'
            if change_col not in df.columns or name_col not in df.columns:
                return None

            df[change_col] = pd.to_numeric(df[change_col], errors='coerce')
            df = df.dropna(subset=[change_col])
            top = df.nlargest(n, change_col)
            bottom = df.nsmallest(n, change_col)

            top_sectors = [
                {'name': str(row[name_col]), 'change_pct': float(row[change_col])}
                for _, row in top.iterrows()
            ]
            bottom_sectors = [
                {'name': str(row[name_col]), 'change_pct': float(row[change_col])}
                for _, row in bottom.iterrows()
            ]
            return top_sectors, bottom_sectors
        except Exception as e:
            logger.error(f"[efinance] huoqubankuaipaihangshibai: {e}")
            return None
    
    def get_base_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        huoqugupiaojibenxinxi
        
        shujulaiyuan：ef.stock.get_base_info()
        baohan：shiyinglv、shijinglv、suochuhangye、zongshizhi、liutongshizhi、ROE、jinglilvdeng
        
        Args:
            stock_code: gupiaodaima
            
        Returns:
            baohanjibenxinxidezidian，huoqushibaifanhui None
        """
        import efinance as ef
        
        try:
            # fangfengjincelve
            self._set_random_user_agent()
            self._enforce_rate_limit()
            
            logger.info(f"[APIdiaoyong] ef.stock.get_base_info(stock_codes={stock_code}) huoqujibenxinxi...")
            import time as _time
            api_start = _time.time()
            
            info = _ef_call_with_timeout(ef.stock.get_base_info, stock_code)
            
            api_elapsed = _time.time() - api_start
            logger.info(f"[APIfanhui] ef.stock.get_base_info chenggong, haoshi {api_elapsed:.2f}s")
            
            if info is None:
                logger.warning(f"[APIfanhui] weihuoqudao {stock_code} dejibenxinxi")
                return None
            
            # zhuanhuanweizidian
            if isinstance(info, pd.Series):
                return info.to_dict()
            elif isinstance(info, pd.DataFrame):
                if not info.empty:
                    return info.iloc[0].to_dict()
            
            return None
            
        except Exception as e:
            logger.error(f"[APIcuowu] huoqu {stock_code} jibenxinxishibai: {e}")
            return None
    
    def get_belong_board(self, stock_code: str) -> Optional[pd.DataFrame]:
        """
        huoqugupiaosuoshubankuai
        
        shujulaiyuan：ef.stock.get_belong_board()
        
        Args:
            stock_code: gupiaodaima
            
        Returns:
            suoshubankuai DataFrame，huoqushibaifanhui None
        """
        import efinance as ef
        
        try:
            # fangfengjincelve
            self._set_random_user_agent()
            self._enforce_rate_limit()
            
            logger.info(f"[APIdiaoyong] ef.stock.get_belong_board(stock_code={stock_code}) huoqusuoshubankuai...")
            import time as _time
            api_start = _time.time()
            
            df = _ef_call_with_timeout(ef.stock.get_belong_board, stock_code)
            
            api_elapsed = _time.time() - api_start
            
            if df is not None and not df.empty:
                logger.info(f"[APIfanhui] ef.stock.get_belong_board chenggong: fanhui {len(df)} gebankuai, haoshi {api_elapsed:.2f}s")
                return df
            else:
                logger.warning(f"[APIfanhui] weihuoqudao {stock_code} debankuaixinxi")
                return None
            
        except FuturesTimeoutError:
            logger.warning(f"[chaoshi] ef.stock.get_belong_board({stock_code}) chaoguo {_EF_CALL_TIMEOUT}s，tiaoguo")
            return None
        except Exception as e:
            logger.error(f"[APIcuowu] huoqu {stock_code} suoshubankuaishibai: {e}")
            return None
    
    def get_enhanced_data(self, stock_code: str, days: int = 60) -> Dict[str, Any]:
        """
        huoquzengqiangshuju（lishiKxian + shishixingqing + jibenxinxi）
        
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
            'base_info': None,
            'belong_board': None,
        }
        
        # huoqurixianshuju
        try:
            df = self.get_daily_data(stock_code, days=days)
            result['daily_data'] = df
        except Exception as e:
            logger.error(f"huoqu {stock_code} rixianshujushibai: {e}")
        
        # huoqushishixingqing
        result['realtime_quote'] = self.get_realtime_quote(stock_code)
        
        # huoqujibenxinxi
        result['base_info'] = self.get_base_info(stock_code)
        
        # huoqusuoshubankuai
        result['belong_board'] = self.get_belong_board(stock_code)
        
        return result


if __name__ == "__main__":
    # ceshidaima
    logging.basicConfig(level=logging.DEBUG)
    
    fetcher = EfinanceFetcher()
    
    # ceshiputonggupiao
    print("=" * 50)
    print("ceshiputonggupiaoshujuhuoqu (efinance)")
    print("=" * 50)
    try:
        df = fetcher.get_daily_data('600519')  # maotai
        print(f"[gupiao] huoquchenggong，gong {len(df)} tiaoshuju")
        print(df.tail())
    except Exception as e:
        print(f"[gupiao] huoqushibai: {e}")
    
    # ceshi ETF jijin
    print("\n" + "=" * 50)
    print("ceshi ETF jijinshujuhuoqu (efinance)")
    print("=" * 50)
    try:
        df = fetcher.get_daily_data('512400')  # youselongtouETF
        print(f"[ETF] huoquchenggong，gong {len(df)} tiaoshuju")
        print(df.tail())
    except Exception as e:
        print(f"[ETF] huoqushibai: {e}")
    
    # ceshishishixingqing
    print("\n" + "=" * 50)
    print("ceshishishixingqinghuoqu (efinance)")
    print("=" * 50)
    try:
        quote = fetcher.get_realtime_quote('600519')
        if quote:
            print(f"[shishixingqing] {quote.name}: jiage={quote.price}, zhangdiefu={quote.change_pct}%")
        else:
            print("[shishixingqing] weihuoqudaoshuju")
    except Exception as e:
        print(f"[shishixingqing] huoqushibai: {e}")
    
    # ceshijibenxinxi
    print("\n" + "=" * 50)
    print("ceshijibenxinxihuoqu (efinance)")
    print("=" * 50)
    try:
        info = fetcher.get_base_info('600519')
        if info:
            print(f"[jibenxinxi] shiyinglv={info.get('shiyinglv(dong)', 'N/A')}, shijinglv={info.get('shijinglv', 'N/A')}")
        else:
            print("[jibenxinxi] weihuoqudaoshuju")
    except Exception as e:
        print(f"[jibenxinxi] huoqushibai: {e}")

    # ceshishichangtongji 
    print("\n" + "=" * 50)
    print("Testing get_market_stats (efinance)")
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
