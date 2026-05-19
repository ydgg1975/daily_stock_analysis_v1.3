# -*- coding: utf-8 -*-
"""
===================================
PytdxFetcher - tongdaxinshujuyuan (Priority 2)
===================================

shujulaiyuan：tongdaxinhangqingfuwuqi（pytdx ku）
tedian：mianfei、wuxu Token、zhilianhangqingfuwuqi
youdian：shishishuju、wending、wupeiexianzhi

guanjiancelve：
1. duofuwuqizidongqiehuan
2. lianjiechaoshizidongzhonglian
3. shibaihouzhishutuibizhongshi
"""

import logging
import re
import time
from contextlib import contextmanager
from typing import Optional, Generator, List, Tuple

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import (
    BaseFetcher,
    DataFetchError,
    DataSourceUnavailableError,
    STANDARD_COLUMNS,
    is_bse_code,
    _is_hk_market,
)
import os

logger = logging.getLogger(__name__)

_PYTDX_CONNECTION_COOLDOWN_SECONDS = 15.0


def _parse_hosts_from_env() -> Optional[List[Tuple[str, int]]]:
    """
    conghuanjingbianlianggoujiantongdaxinfuwuqiliebiao。

    youxianji：
    1. PYTDX_SERVERS：douhaofenge "ip:port,ip:port"（ru "192.168.1.1:7709,10.0.0.1:7709"）
    2. PYTDX_HOST + PYTDX_PORT：dangefuwuqi
    3. junweipeizhishifanhui None（diaoyongfangshiyong DEFAULT_HOSTS）
    """
    servers = os.getenv("PYTDX_SERVERS", "").strip()
    if servers:
        result = []
        for part in servers.split(","):
            part = part.strip()
            if ":" in part:
                host, port_str = part.rsplit(":", 1)
                host, port_str = host.strip(), port_str.strip()
                if host and port_str:
                    try:
                        result.append((host, int(port_str)))
                    except ValueError:
                        logger.warning(f"Invalid PYTDX_SERVERS entry: {part}")
            else:
                logger.warning(f"Invalid PYTDX_SERVERS entry (missing port): {part}")
        if result:
            return result

    host = os.getenv("PYTDX_HOST", "").strip()
    port_str = os.getenv("PYTDX_PORT", "").strip()
    if host and port_str:
        try:
            return [(host, int(port_str))]
        except ValueError:
            logger.warning(f"Invalid PYTDX_HOST/PYTDX_PORT: {host}:{port_str}")

    return None


def _is_us_code(stock_code: str) -> bool:
    """
    panduandaimashifouweimeigu
    
    meigudaimaguize：
    - 1-5gedaxiezimu，ru 'AAPL', 'TSLA'
    - kenengbaohan '.'，ru 'BRK.B'
    """
    code = stock_code.strip().upper()
    return bool(re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', code))


class PytdxFetcher(BaseFetcher):
    """
    tongdaxinshujuyuanshixian
    
    youxianji：2（yu Tushare tongji）
    shujulaiyuan：tongdaxinhangqingfuwuqi
    
    guanjiancelve：
    - zidongxuanzezuiyoufuwuqi
    - lianjieshibaizidongqiehuanfuwuqi
    - shibaihouzhishutuibizhongshi
    
    Pytdx tedian：
    - mianfei、wuxuzhuce
    - zhilianhangqingfuwuqi
    - zhichishishixingqinghelishishuju
    - zhichigupiaomingchengchaxun
    """
    
    name = "PytdxFetcher"
    priority = int(os.getenv("PYTDX_PRIORITY", "2"))
    
    # morentongdaxinhangqingfuwuqiliebiao
    DEFAULT_HOSTS = [
        ("119.147.212.81", 7709),  # shenzhen
        ("112.74.214.43", 7727),   # shenzhen
        ("221.231.141.60", 7709),  # shanghai
        ("101.227.73.20", 7709),   # shanghai
        ("101.227.77.254", 7709),  # shanghai
        ("14.215.128.18", 7709),   # guangzhou
        ("59.173.18.140", 7709),   # wuhan
        ("180.153.39.51", 7709),   # hangzhou
    ]
    # Pytdx get_security_list returns at most 1000 items per page
    SECURITY_LIST_PAGE_SIZE = 1000
    
    def __init__(self, hosts: Optional[List[Tuple[str, int]]] = None):
        """
        chushihua PytdxFetcher

        Args:
            hosts: fuwuqiliebiao [(host, port), ...]。ruoweichuanru，youxianshiyonghuanjingbianliang
                   PYTDX_SERVERS（ip:port,ip:port）huo PYTDX_HOST+PYTDX_PORT，
                   fouzeshiyongneizhi DEFAULT_HOSTS。
        """
        if hosts is not None:
            self._hosts = hosts
        else:
            env_hosts = _parse_hosts_from_env()
            self._hosts = env_hosts if env_hosts else self.DEFAULT_HOSTS
        self._api = None
        self._connected = False
        self._current_host_idx = 0
        self._stock_list_cache = None  # gupiaoliebiaohuancun
        self._stock_name_cache = {}    # gupiaomingchenghuancun {code: name}
        self._unavailable_until = 0.0
        self._last_unavailable_reason = ""

    def _is_in_connection_cooldown(self) -> bool:
        return time.time() < self._unavailable_until

    def _mark_connection_cooldown(self, reason: str) -> None:
        self._unavailable_until = time.time() + _PYTDX_CONNECTION_COOLDOWN_SECONDS
        self._last_unavailable_reason = str(reason or "").strip()
        logger.info(
            "Pytdx lianjieshibai，jinrulengque %.0fs: %s",
            _PYTDX_CONNECTION_COOLDOWN_SECONDS,
            self._last_unavailable_reason or "unknown",
        )

    def is_available_for_request(self, capability: str = "") -> bool:
        return not self._is_in_connection_cooldown()
    
    def _get_pytdx(self):
        """
        yanchijiazai pytdx mokuai
        
        zhizaishoucishiyongshidaoru，bimianweianzhuangshibaocuo
        """
        try:
            from pytdx.hq import TdxHq_API
            return TdxHq_API
        except ImportError:
            logger.warning("pytdx weianzhuang，qingyunxing: pip install pytdx")
            return None
    
    @contextmanager
    def _pytdx_session(self) -> Generator:
        """
        Pytdx lianjieshangxiawenguanliqi
        
        quebao：
        1. jinrushangxiawenshizidonglianjie
        2. tuichushangxiawenshizidongduankai
        3. yichangshiyenengzhengqueduankai
        
        shiyongshili：
            with self._pytdx_session() as api:
                # zaizhelizhixingshujuchaxun
        """
        if self._is_in_connection_cooldown():
            raise DataSourceUnavailableError(
                f"Pytdx temporarily unavailable: {self._last_unavailable_reason or 'connection cooldown'}"
            )

        TdxHq_API = self._get_pytdx()
        if TdxHq_API is None:
            raise DataFetchError("pytdx kuweianzhuang")
        
        api = TdxHq_API()
        connected = False
        
        try:
            # changshilianjiefuwuqi（zidongxuanzezuiyou）
            for i in range(len(self._hosts)):
                host_idx = (self._current_host_idx + i) % len(self._hosts)
                host, port = self._hosts[host_idx]
                
                try:
                    if api.connect(host, port, time_out=5):
                        connected = True
                        self._current_host_idx = host_idx
                        logger.debug(f"Pytdx lianjiechenggong: {host}:{port}")
                        break
                except Exception as e:
                    logger.debug(f"Pytdx lianjie {host}:{port} shibai: {e}")
                    continue
            
            if not connected:
                self._mark_connection_cooldown("Pytdx wufalianjierenhefuwuqi")
                raise DataFetchError("Pytdx wufalianjierenhefuwuqi")
            
            yield api
            
        finally:
            # quebaoduankailianjie
            try:
                api.disconnect()
                logger.debug("Pytdx lianjieyiduankai")
            except Exception as e:
                logger.warning(f"Pytdx duankailianjieshichucuo: {e}")
    
    def _get_market_code(self, stock_code: str) -> Tuple[int, str]:
        """
        genjugupiaodaimapanduanshichang
        
        Pytdx shichangdaima：
        - 0: shenzhen
        - 1: shanghai
        
        Args:
            stock_code: gupiaodaima
            
        Returns:
            (market, code) yuanzu
        """
        code = stock_code.strip()
        
        # quchukenengdeqianzhuihouzhui
        code = code.replace('.SH', '').replace('.SZ', '')
        code = code.replace('.sh', '').replace('.sz', '')
        code = code.replace('sh', '').replace('sz', '')
        
        # genjudaimaqianzhuipanduanshichang
        # shanghai：60xxxx, 68xxxx（kechuangban）
        # shenzhen：00xxxx, 30xxxx（chuangyeban）, 002xxx（zhongxiaoban）
        if code.startswith(('60', '68')):
            return 1, code  # shanghai
        else:
            return 0, code  # shenzhen

    def _build_stock_list_cache(self, api) -> None:
        """
        Build a full stock code -> name cache from paginated security lists.
        """
        self._stock_list_cache = {}

        for market in (0, 1):
            start = 0
            while True:
                stocks = api.get_security_list(market, start) or []
                for stock in stocks:
                    code = stock.get('code')
                    name = stock.get('name')
                    if code and name:
                        self._stock_list_cache[code] = name

                if len(stocks) < self.SECURITY_LIST_PAGE_SIZE:
                    break

                start += self.SECURITY_LIST_PAGE_SIZE
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        congtongdaxinhuoquyuanshishuju
        
        shiyong get_security_bars() huoqurixianshuju
        
        liucheng：
        1. jianchashifouweimeigu（buzhichi）
        2. shiyongshangxiawenguanliqiguanlilianjie
        3. panduanshichangdaima
        4. diaoyong API huoqu K xianshuju
        """
        # meigubuzhichi，paochuyichangrang DataFetcherManager qiehuandaoqitashujuyuan
        if _is_us_code(stock_code):
            raise DataFetchError(f"PytdxFetcher buzhichimeigu {stock_code}，qingshiyong AkshareFetcher huo YfinanceFetcher")

        # ganggubuzhichi，paochuyichangrang DataFetcherManager qiehuandaoqitashujuyuan
        if _is_hk_market(stock_code):
            raise DataFetchError(f"PytdxFetcher buzhichiganggu {stock_code}，qingshiyong AkshareFetcher")

        # beijiaosuobuzhichi，paochuyichangrang DataFetcherManager qiehuandaoqitashujuyuan
        if is_bse_code(stock_code):
            raise DataFetchError(
                f"PytdxFetcher buzhichibeijiaosuo {stock_code}，jiangzidongqiehuanqitashujuyuan"
            )
        
        market, code = self._get_market_code(stock_code)
        
        # jisuanxuyaohuoqudejiaoyirishuliang（gusuan）
        from datetime import datetime as dt
        start_dt = dt.strptime(start_date, '%Y-%m-%d')
        end_dt = dt.strptime(end_date, '%Y-%m-%d')
        days = (end_dt - start_dt).days
        count = min(max(days * 5 // 7 + 10, 30), 800)  # gusuanjiaoyiri，zuida 800 tiao
        
        logger.debug(f"diaoyong Pytdx get_security_bars(market={market}, code={code}, count={count})")
        
        with self._pytdx_session() as api:
            try:
                # huoquri K xianshuju
                # category: 9-rixian, 0-5fenzhong, 1-15fenzhong, 2-30fenzhong, 3-1xiaoshi
                data = api.get_security_bars(
                    category=9,  # rixian
                    market=market,
                    code=code,
                    start=0,  # congzuixinkaishi
                    count=count
                )
                
                if data is None or len(data) == 0:
                    raise DataFetchError(f"Pytdx weichaxundao {stock_code} deshuju")
                
                # zhuanhuanwei DataFrame
                df = api.to_df(data)
                
                # guolvriqifanwei
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df[(df['datetime'] >= start_date) & (df['datetime'] <= end_date)]
                
                return df
                
            except Exception as e:
                if isinstance(e, DataFetchError):
                    raise
                raise DataFetchError(f"Pytdx huoqushujushibai: {e}") from e
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        biaozhunhua Pytdx shuju
        
        Pytdx fanhuidelieming：
        datetime, open, high, low, close, vol, amount
        
        xuyaoyingshedaobiaozhunlieming：
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()
        
        # liemingyingshe
        column_mapping = {
            'datetime': 'date',
            'vol': 'volume',
        }
        
        df = df.rename(columns=column_mapping)
        
        # jisuanzhangdiefu（pytdx bufanhuizhangdiefu，xuyaozijijisuan）
        if 'pct_chg' not in df.columns and 'close' in df.columns:
            df['pct_chg'] = df['close'].pct_change() * 100
            df['pct_chg'] = df['pct_chg'].fillna(0).round(2)
        
        # tianjiagupiaodaimalie
        df['code'] = stock_code
        
        # zhibaoliuxuyaodelie
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]
        
        return df
    
    def get_stock_name(self, stock_code: str) -> Optional[str]:
        """
        huoqugupiaomingcheng
        
        Args:
            stock_code: gupiaodaima
            
        Returns:
            gupiaomingcheng，shibaifanhui None
        """
        # ganggubuzhichi（pytdx buhanganggushuju）
        if _is_hk_market(stock_code):
            return None

        # xianjianchahuancun
        if stock_code in self._stock_name_cache:
            return self._stock_name_cache[stock_code]
        
        try:
            market, code = self._get_market_code(stock_code)
            
            with self._pytdx_session() as api:
                # huoqugupiaoliebiao（huancun）
                if self._stock_list_cache is None:
                    self._build_stock_list_cache(api)
                
                # chazhaogupiaomingcheng
                name = self._stock_list_cache.get(code)
                if name:
                    self._stock_name_cache[stock_code] = name
                    return name
                
                # changshishiyong get_finance_info
                finance_info = api.get_finance_info(market, code)
                if finance_info and 'name' in finance_info:
                    name = finance_info['name']
                    self._stock_name_cache[stock_code] = name
                    return name
                
        except Exception as e:
            logger.debug(f"Pytdx huoqugupiaomingchengshibai {stock_code}: {e}")
        
        return None
    
    def get_realtime_quote(self, stock_code: str) -> Optional[dict]:
        """
        huoqushishixingqing
        
        Args:
            stock_code: gupiaodaima
            
        Returns:
            shishixingqingshujuzidian，shibaifanhui None
        """
        if is_bse_code(stock_code):
            raise DataFetchError(
                f"PytdxFetcher buzhichibeijiaosuo {stock_code}，jiangzidongqiehuanqitashujuyuan"
            )
        try:
            market, code = self._get_market_code(stock_code)
            
            with self._pytdx_session() as api:
                data = api.get_security_quotes([(market, code)])
                
                if data and len(data) > 0:
                    quote = data[0]
                    return {
                        'code': stock_code,
                        'name': quote.get('name', ''),
                        'price': quote.get('price', 0),
                        'open': quote.get('open', 0),
                        'high': quote.get('high', 0),
                        'low': quote.get('low', 0),
                        'pre_close': quote.get('last_close', 0),
                        'volume': quote.get('vol', 0),
                        'amount': quote.get('amount', 0),
                        'bid_prices': [quote.get(f'bid{i}', 0) for i in range(1, 6)],
                        'ask_prices': [quote.get(f'ask{i}', 0) for i in range(1, 6)],
                    }
        except Exception as e:
            logger.warning(f"Pytdx huoqushishixingqingshibai {stock_code}: {e}")
        
        return None


if __name__ == "__main__":
    # ceshidaima
    logging.basicConfig(level=logging.DEBUG)
    
    fetcher = PytdxFetcher()
    
    try:
        # ceshilishishuju
        df = fetcher.get_daily_data('600519')  # maotai
        print(f"huoquchenggong，gong {len(df)} tiaoshuju")
        print(df.tail())
        
        # ceshigupiaomingcheng
        name = fetcher.get_stock_name('600519')
        print(f"gupiaomingcheng: {name}")
        
        # ceshishishixingqing
        quote = fetcher.get_realtime_quote('600519')
        print(f"shishixingqing: {quote}")
        
    except Exception as e:
        print(f"huoqushibai: {e}")
