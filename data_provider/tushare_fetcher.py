# -*- coding: utf-8 -*-
"""
===================================
TushareFetcher - beiyongshujuyuan 1 (Priority 2)
===================================

shujulaiyuan：Tushare Pro API（waditu）
tedian：xuyao Token、youqingqiupeiexianzhi
youdian：shujuzhilianggao、jiekouwending

liukongcelve：
1. shixian"meifenzhongdiaoyongjishuqi"
2. chaoguomianfeipeie（80ci/fen）shi，qiangzhixiumiandaoxiayifenzhong
3. shiyong tenacity shixianzhishutuibizhongshi
"""

import json as _json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any

import pandas as pd
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, RateLimitError, STANDARD_COLUMNS,is_bse_code, is_st_stock, is_kc_cy_stock, normalize_stock_code, _is_hk_market
from .realtime_types import UnifiedRealtimeQuote, ChipDistribution
from src.config import get_config
import os
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


# ETF code prefixes by exchange
# Shanghai: 51xxxx, 52xxxx, 56xxxx, 58xxxx
# Shenzhen: 15xxxx, 16xxxx, 18xxxx
_ETF_SH_PREFIXES = ('51', '52', '56', '58')
_ETF_SZ_PREFIXES = ('15', '16', '18')
_ETF_ALL_PREFIXES = _ETF_SH_PREFIXES + _ETF_SZ_PREFIXES


def _is_etf_code(stock_code: str) -> bool:
    """
    Check if the code is an ETF fund code.

    ETF code ranges:
    - Shanghai ETF: 51xxxx, 52xxxx, 56xxxx, 58xxxx
    - Shenzhen ETF: 15xxxx, 16xxxx, 18xxxx
    """
    code = stock_code.strip().split('.')[0]
    return code.startswith(_ETF_ALL_PREFIXES) and len(code) == 6


def _is_us_code(stock_code: str) -> bool:
    """
    panduandaimashifouweimeigu
    
    meigudaimaguize：
    - 1-5gedaxiezimu，ru 'AAPL', 'TSLA'
    - kenengbaohan '.'，ru 'BRK.B'
    """
    code = stock_code.strip().upper()
    return bool(re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', code))


class _TushareHttpClient:
    """Lightweight Tushare Pro client that does not require the tushare SDK."""

    def __init__(self, token: str, timeout: int = 30, api_url: str = "http://api.tushare.pro") -> None:
        self._token = token
        self._timeout = timeout
        self._api_url = api_url

    def query(self, api_name: str, fields: str = "", **kwargs) -> pd.DataFrame:
        req_params = {
            "api_name": api_name,
            "token": self._token,
            "params": kwargs,
            "fields": fields,
        }
        res = requests.post(self._api_url, json=req_params, timeout=self._timeout)
        if res.status_code != 200:
            raise Exception(f"Tushare API HTTP {res.status_code}")

        result = _json.loads(res.text)
        if result.get("code") != 0:
            raise Exception(result.get("msg") or f"Tushare API error code {result.get('code')}")

        data = result.get("data") or {}
        columns = data.get("fields") or []
        items = data.get("items") or []
        return pd.DataFrame(items, columns=columns)

    def __getattr__(self, api_name: str):
        if api_name.startswith("_"):
            raise AttributeError(api_name)

        def caller(**kwargs) -> pd.DataFrame:
            return self.query(api_name, **kwargs)

        return caller


class TushareFetcher(BaseFetcher):
    """
    Tushare Pro shujuyuanshixian
    
    youxianji：2
    shujulaiyuan：Tushare Pro API
    
    guanjiancelve：
    - meifenzhongdiaoyongjishuqi，fangzhichaochupeie
    - chaoguo 80 ci/fenzhongshiqiangzhidengdai
    - shibaihouzhishutuibizhongshi
    
    peieshuoming（Tushare mianfeiyonghu）：
    - meifenzhongzuiduo 80 ciqingqiu
    - meitianzuiduo 500 ciqingqiu
    """
    
    name = "TushareFetcher"
    priority = int(os.getenv("TUSHARE_PRIORITY", "2"))  # morenyouxianji，huizai __init__ zhonggenjupeizhidongtaitiaozheng

    def __init__(self, rate_limit_per_minute: int = 80):
        """
        chushihua TushareFetcher

        Args:
            rate_limit_per_minute: meifenzhongzuidaqingqiushu（moren80，Tusharemianfeipeie）
        """
        self.rate_limit_per_minute = rate_limit_per_minute
        self._call_count = 0  # dangqianfenzhongneidediaoyongcishu
        self._minute_start: Optional[float] = None  # dangqianjishuzhouqikaishishijian
        self._api: Optional[object] = None  # Tushare API shili
        self.date_list: Optional[List[str]] = None  # jiaoyiriliebiaohuancun（daoxu，zuixinriqizaiqian）
        self._date_list_end: Optional[str] = None  # huancunduiyingdejiezhiriqi，yongyukuarishuaxin

        # changshichushihua API
        self._init_api()

        # genju API chushihuajieguodongtaitiaozhengyouxianji
        self.priority = self._determine_priority()
    
    def _init_api(self) -> None:
        """
        chushihua Tushare API

        ruguo Token weipeizhi，cishujuyuanjiangbukeyong。
        zhelizhijieshiyongneizhi HTTP client，bimianyunxingshiqiangyilai tushare SDK，
        congerjianshao Docker / PyInstaller / duoxunihuanjingchangjingxiayinquebaodaozhidechushihuashibai。
        """
        config = get_config()

        if not config.tushare_token:
            logger.warning("Tushare Token weipeizhi，cishujuyuanbukeyong")
            return

        try:
            self._api = self._build_api_client(config.tushare_token)
            logger.info("Tushare API chushihuachenggong")
        except Exception as e:
            logger.error(f"Tushare API chushihuashibai: {e}")
            self._api = None

    def _build_api_client(self, token: str) -> _TushareHttpClient:
        """
        Build a lightweight Tushare Pro client over direct HTTP requests.

        The project already normalizes all Pro calls through the same request
        contract, so we do not need the official tushare SDK during runtime.
        """
        client = _TushareHttpClient(token=token)
        logger.debug("Tushare API client configured for direct HTTP calls")
        return client

    def _determine_priority(self) -> int:
        """
        genju Token peizhihe API chushihuazhuangtaiquedingyouxianji

        celve：
        - Token peizhiqie API chushihuachenggong：youxianji -1（jueduizuigao，youyu efinance）
        - qitaqingkuang：youxianji 2（moren）

        Returns:
            youxianjishuzi（0=zuigao，shuziyuedayouxianjiyuedi）
        """
        config = get_config()

        if config.tushare_token and self._api is not None:
            # Token peizhiqie API chushihuachenggong，tishengweizuigaoyouxianji
            logger.info("✅ jiancedao TUSHARE_TOKEN qie API chushihuachenggong，Tushare shujuyuanyouxianjitishengweizuigao (Priority -1)")
            return -1

        # Token weipeizhihuo API chushihuashibai，baochimorenyouxianji
        return 2

    def is_available(self) -> bool:
        """
        jianchashujuyuanshifoukeyong

        Returns:
            True biaoshikeyong，False biaoshibukeyong
        """
        return self._api is not None

    def _check_rate_limit(self) -> None:
        """
        jianchabingzhixingsulvxianzhi
        
        liukongcelve：
        1. jianchashifoujinruxindeyifenzhong
        2. ruguoshi，zhongzhijishuqi
        3. ruguodangqianfenzhongdiaoyongcishuchaoguoxianzhi，qiangzhixiumian
        """
        current_time = time.time()
        
        # jianchashifouxuyaozhongzhijishuqi（xindeyifenzhong）
        if self._minute_start is None:
            self._minute_start = current_time
            self._call_count = 0
        elif current_time - self._minute_start >= 60:
            # yijingguoleyifenzhong，zhongzhijishuqi
            self._minute_start = current_time
            self._call_count = 0
            logger.debug("sulvxianzhijishuqiyizhongzhi")
        
        # jianchashifouchaoguopeie
        if self._call_count >= self.rate_limit_per_minute:
            # jisuanxuyaodengdaideshijian（daoxiayifenzhong）
            elapsed = current_time - self._minute_start
            sleep_time = max(0, 60 - elapsed) + 1  # +1 miaohuanchong
            
            logger.warning(
                f"Tushare dadaosulvxianzhi ({self._call_count}/{self.rate_limit_per_minute} ci/fenzhong)，"
                f"dengdai {sleep_time:.1f} miao..."
            )
            
            time.sleep(sleep_time)
            
            # zhongzhijishuqi
            self._minute_start = time.time()
            self._call_count = 0
        
        # zengjiadiaoyongjishu
        self._call_count += 1
        logger.debug(f"Tushare dangqianfenzhongdiaoyongcishu: {self._call_count}/{self.rate_limit_per_minute}")

    def _call_api_with_rate_limit(self, method_name: str, **kwargs) -> pd.DataFrame:
        """tongyitongguosulvxianzhibaozhuang Tushare API diaoyong。"""
        if self._api is None:
            raise DataFetchError("Tushare API weichushihua，qingjiancha Token peizhi")

        self._check_rate_limit()
        method = getattr(self._api, method_name)
        return method(**kwargs)

    def _get_china_now(self) -> datetime:
        """fanhuishanghaishiqudangqianshijian，fangbianceshifugaikuarishuaxinluoji。"""
        return datetime.now(ZoneInfo("Asia/Shanghai"))

    def _get_trade_dates(self, end_date: Optional[str] = None) -> List[str]:
        """anziranrishuaxinjiaoyirilihuancun，bimianfuwukuarihoujixufuyongjiurili。"""
        if self._api is None:
            return []

        china_now = self._get_china_now()
        requested_end_date = end_date or china_now.strftime("%Y%m%d")

        if self.date_list is not None and self._date_list_end == requested_end_date:
            return self.date_list

        start_date = (china_now - timedelta(days=20)).strftime("%Y%m%d")
        df_cal = self._call_api_with_rate_limit(
            "trade_cal",
            exchange="SSE",
            start_date=start_date,
            end_date=requested_end_date,
        )

        if df_cal is None or df_cal.empty or "cal_date" not in df_cal.columns:
            logger.warning("[Tushare] trade_cal fanhuiweikong，wufagengxinjiaoyirilihuancun")
            self.date_list = []
            self._date_list_end = requested_end_date
            return self.date_list

        trade_dates = sorted(
            df_cal[df_cal["is_open"] == 1]["cal_date"].astype(str).tolist(),
            reverse=True,
        )
        self.date_list = trade_dates
        self._date_list_end = requested_end_date
        return trade_dates

    @staticmethod
    def _pick_trade_date(trade_dates: List[str], use_today: bool) -> Optional[str]:
        """genjukeyongjiaoyiriliebiaoxuanzedangtianhuoqianyijiaoyiri。"""
        if not trade_dates:
            return None
        if use_today or len(trade_dates) == 1:
            return trade_dates[0]
        return trade_dates[1]

    @staticmethod
    def _detect_exchange_hint(stock_code: str) -> Optional[str]:
        """Return SH/SZ/BJ when the raw user input carries an explicit exchange hint."""
        upper = (stock_code or "").strip().upper()
        if upper.startswith(("SH", "SS")) or upper.endswith((".SH", ".SS")):
            return "SH"
        if upper.startswith("SZ") or upper.endswith(".SZ"):
            return "SZ"
        if upper.startswith("BJ") or upper.endswith(".BJ"):
            return "BJ"
        return None

    @classmethod
    def _get_legacy_realtime_symbol(cls, stock_code: str) -> str:
        """Build the legacy tushare symbol while preserving explicit SH/SZ hints."""
        code = normalize_stock_code(stock_code)
        exchange_hint = cls._detect_exchange_hint(stock_code)

        if code == '000001' and exchange_hint == 'SH':
            return 'sh000001'
        if code == '399001':
            return 'sz399001'
        if code == '399006':
            return 'sz399006'
        if code == '000300':
            return 'sh000300'
        if is_bse_code(code):
            return f"bj{code}"
        return code
    
    def _convert_stock_code(self, stock_code: str) -> str:
        """
        zhuanhuan A gu / ETF / beijiaosuodengwei Tushare ts_code（buhangangguluoji）。

        Tushare yaoqiudegeshishili：
        - hushigupiao：600519.SH
        - shenshigupiao：000001.SZ
        - hushi ETF：510050.SH
        - shenshi ETF：159919.SZ

        Args:
            stock_code: yuanshidaima，ru '600519', '000001', '563230'

        Returns:
            Tushare geshidaima，ru '600519.SH', '000001.SZ'
        """
        raw_code = stock_code.strip()
        
        # Already has suffix
        if '.' in raw_code:
            ts_code = raw_code.upper()
            if ts_code.endswith('.SS'):
                return f"{ts_code[:-3]}.SH"
            return ts_code

        if _is_us_code(raw_code):
            raise DataFetchError(f"TushareFetcher buzhichimeigu {raw_code}，qingshiyong AkshareFetcher huo YfinanceFetcher")

        if _is_hk_market(raw_code):
            #raise DataFetchError(f"TushareFetcher buzhichiganggu {raw_code}，qingshiyong AkshareFetcher")
            return normalize_stock_code(raw_code)

        code = normalize_stock_code(raw_code)
        exchange_hint = self._detect_exchange_hint(raw_code)

        if exchange_hint == "SH":
            return f"{code}.SH"
        if exchange_hint == "SZ":
            return f"{code}.SZ"
        if exchange_hint == "BJ":
            return f"{code}.BJ"

        # ETF: determine exchange by prefix
        if code.startswith(_ETF_SH_PREFIXES) and len(code) == 6:
            return f"{code}.SH"
        if code.startswith(_ETF_SZ_PREFIXES) and len(code) == 6:
            return f"{code}.SZ"
        
        # BSE (Beijing Stock Exchange): 8xxxxx, 4xxxxx, 920xxx
        if is_bse_code(code):
            return f"{code}.BJ"
        
        # Regular stocks
        # Shanghai: 600xxx, 601xxx, 603xxx, 688xxx (STAR Market)
        # Shenzhen: 000xxx, 002xxx, 300xxx (ChiNext)
        if code.startswith(('600', '601', '603', '688')):
            return f"{code}.SH"
        elif code.startswith(('000', '002', '300')):
            return f"{code}.SZ"
        else:
            logger.warning(f"wufaquedinggupiao {code} deshichang，morenshiyongshenshi")
            return f"{code}.SZ"

    def _convert_hk_stock_code_for_tushare(self, stock_code: str) -> str:
        """
        jiangyonghushuruzhuanwei Tushare Pro jiekousuoxude ts_code（hanganggu nnnnn.HK）。

        - feiganggu：weituo _convert_stock_code（A gu / ETF / beijiaosuodeng）。
        - ganggu：cong HK00700、00700、00700.HK dengxingshiguiyiwei 5 weishuzi + .HK。
        """
        raw_code = stock_code.strip()
        if _is_hk_market(raw_code):
            if "." in raw_code:
                ts_code = raw_code.upper()
                if ts_code.endswith(".SS"):
                    return f"{ts_code[:-3]}.SH"
                if ts_code.endswith(".HK"):
                    return ts_code
            digits = re.sub(r"\D", "", raw_code)
            if not digits:
                raise DataFetchError(f"wufashibieganggudaima {raw_code}")
            code = digits[-5:].rjust(5, "0")
            return f"{code}.HK"
        return self._convert_stock_code(stock_code)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        cong Tushare huoquyuanshishuju
        
        genjudaimaleixingxuanzebutongjiekou：
        - putonggupiao：daily()
        - ETF jijin：fund_daily()
        
        liucheng：
        1. jiancha API shifoukeyong
        2. jianchashifouweimeigu（buzhichi）
        3. zhixingsulvxianzhijiancha
        4. zhuanhuangupiaodaimageshi
        5. genjudaimaleixingxuanzejiekoubingdiaoyong
        """
        if self._api is None:
            raise DataFetchError("Tushare API weichushihua，qingjiancha Token peizhi")
        
        # US stocks not supported
        if _is_us_code(stock_code):
            raise DataFetchError(f"TushareFetcher buzhichimeigu {stock_code}，qingshiyong AkshareFetcher huo YfinanceFetcher")
        
        # Rate-limit check
        self._check_rate_limit()
        
        is_hk = _is_hk_market(stock_code)
         # panduanshifouwei ETF / ganggu，yixuanzebutongjiekou
        is_etf = _is_etf_code(stock_code)
        if is_hk:
            ts_code = self._convert_hk_stock_code_for_tushare(stock_code)
            api_name = "hk_daily"
        else:
            ts_code = self._convert_stock_code(stock_code)
            api_name = "fund_daily" if is_etf else "daily"
        
        # Convert date format (Tushare requires YYYYMMDD)
        ts_start = start_date.replace('-', '')
        ts_end = end_date.replace('-', '')
        
       

        logger.debug(f"diaoyong Tushare {api_name}({ts_code}, {ts_start}, {ts_end})")
        
        try:
            if is_hk:
                # ganggushiyong hk_daily jiekou
                df = self._api.hk_daily(
                    ts_code=ts_code,
                    start_date=ts_start,
                    end_date=ts_end,
                )
            elif is_etf:
                # ETF uses fund_daily interface
                df = self._api.fund_daily(
                    ts_code=ts_code,
                    start_date=ts_start,
                    end_date=ts_end,
                )
            else:
                # Regular A-share stocks use daily interface
                df = self._api.daily(
                    ts_code=ts_code,
                    start_date=ts_start,
                    end_date=ts_end,
                )
            
            return df
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # jiancepeiechaoxian
            if any(keyword in error_msg for keyword in ['quota', 'peie', 'limit', 'quanxian']):
                logger.warning(f"Tushare peiekenengchaoxian: {e}")
                raise RateLimitError(f"Tushare peiechaoxian: {e}") from e
            
            raise DataFetchError(f"Tushare huoqushujushibai: {e}") from e
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        biaozhunhua Tushare shuju
        
        Tushare daily / fund_daily fanhuidelieming：
        ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
        
        xuyaoyingshedaobiaozhunlieming：
        date, open, high, low, close, volume, amount, pct_chg

        danweisuofangjinshiyongyu A gu（ji ETF dengshiyongtongyitaodanweidejiekou）：
        - vol an「shou」ji，chengyi 100 zhuanwei「gu」
        - amount an「qianyuan」ji，chengyi 1000 zhuanwei「yuan」

        ganggu hk_daily fanhuide vol / amount yishikezhijieshiyongdeliangji，buzuoshangshusuofang。
        """
        df = df.copy()
        is_hk = _is_hk_market(stock_code)

        # liemingyingshe
        column_mapping = {
            'trade_date': 'date',
            'vol': 'volume',
            # open, high, low, close, amount, pct_chg liemingxiangtong
        }
        
        df = df.rename(columns=column_mapping)
        
        # zhuanhuanriqigeshi（YYYYMMDD -> YYYY-MM-DD）
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
        
        # chengjiaoliang / chengjiaoe：jin A guleijiekouzuodanweihuansuan（ganggu hk_daily buhuansuan）
        if 'volume' in df.columns and not is_hk:
            df['volume'] = df['volume'] * 100
        
        if 'amount' in df.columns and not is_hk:
            df['amount'] = df['amount'] * 1000
        
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
        
        shiyong Tushare de stock_basic jiekouhuoqugupiaojibenxinxi
        
        Args:
            stock_code: gupiaodaima
            
        Returns:
            gupiaomingcheng，shibaifanhui None
        """
        if self._api is None:
            logger.warning("Tushare API weichushihua，wufahuoqugupiaomingcheng")
            return None

        # jianchahuancun
        if hasattr(self, '_stock_name_cache') and stock_code in self._stock_name_cache:
            return self._stock_name_cache[stock_code]
        
        # chushihuahuancun
        if not hasattr(self, '_stock_name_cache'):
            self._stock_name_cache = {}
        
        try:
            # sulvxianzhijiancha
            self._check_rate_limit()
            

            # genjushichang/leixingxuanzejichuxinxijiekou
            if _is_hk_market(stock_code):
                ts_code = self._convert_hk_stock_code_for_tushare(stock_code)
                # ganggu：shiyong hk_basic
                df = self._api.hk_basic(
                    ts_code=ts_code,
                    fields='ts_code,name'
                )
            elif _is_etf_code(stock_code):
                ts_code = self._convert_stock_code(stock_code)
                # ETF：shiyong fund_basic
                df = self._api.fund_basic(
                    ts_code=ts_code,
                    fields='ts_code,name'
                )
            else:
                ts_code = self._convert_stock_code(stock_code)
                # A gugupiao：shiyong stock_basic
                df = self._api.stock_basic(
                    ts_code=ts_code,
                    fields='ts_code,name'
                )
            
            if df is not None and not df.empty:
                name = df.iloc[0]['name']
                self._stock_name_cache[stock_code] = name
                logger.debug(f"Tushare huoqugupiaomingchengchenggong: {stock_code} -> {name}")
                return name
            
        except Exception as e:
            logger.warning(f"Tushare huoqugupiaomingchengshibai {stock_code}: {e}")
        
        return None
    
    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """
        huoqugupiaoliebiao
        
        shiyong Tushare de stock_basic jiekouhuoqu A guliebiao（buhanganggu）。
        
        Returns:
            baohan code, name, industry, area, market liede DataFrame，shibaifanhui None
        """
        if self._api is None:
            logger.warning("Tushare API weichushihua，wufahuoqugupiaoliebiao")
            return None
        
        try:
            self._check_rate_limit()

            df = self._api.stock_basic(
                exchange='',
                list_status='L',
                fields='ts_code,name,industry,area,market'
            )

            if df is None or df.empty:
                return None

            df = df.copy()
            df['code'] = df['ts_code'].astype(str).str.split('.').str[0]

            if not hasattr(self, '_stock_name_cache'):
                self._stock_name_cache = {}
            for _, row in df.iterrows():
                self._stock_name_cache[row['code']] = row['name']

            logger.info(f"Tushare huoqugupiaoliebiaochenggong: {len(df)} tiao")
            return df[['code', 'name', 'industry', 'area', 'market']]

        except Exception as e:
            logger.warning(f"Tushare huoqugupiaoliebiaoshibai: {e}")

        return None
    
    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        huoqushishixingqing

        celve：
        1. youxianchangshi Pro jiekou（xuyao2000jifen）：shujuquan，wendingxinggao
        2. shibaijiangjidaojiubanjiekou：menkandi，shujujiaoshao

        Args:
            stock_code: gupiaodaima

        Returns:
            UnifiedRealtimeQuote duixiang，shibaifanhui None
        """
        if self._api is None:
            return None

        # HK stocks not supported by Tushare
        if _is_hk_market(stock_code):
            logger.debug(f"TushareFetcher tiaoguoganggushishixingqing {stock_code}")
            return None

        normalized_code = normalize_stock_code(stock_code)

        from .realtime_types import (
            RealtimeSource,
            safe_float, safe_int
        )

        # sulvxianzhijiancha
        self._check_rate_limit()

        # changshi Pro jiekou
        try:
            ts_code = self._convert_stock_code(stock_code)
            # changshidiaoyong Pro shishijiekou (xuyaojifen)
            df = self._api.quotation(ts_code=ts_code)

            if df is not None and not df.empty:
                row = df.iloc[0]
                logger.debug(f"Tushare Pro shishixingqinghuoquchenggong: {stock_code}")

                return UnifiedRealtimeQuote(
                    code=normalized_code,
                    name=str(row.get('name', '')),
                    source=RealtimeSource.TUSHARE,
                    price=safe_float(row.get('price')),
                    change_pct=safe_float(row.get('pct_chg')),  # Pro jiekoutongchangzhijiefanhuizhangdiefu
                    change_amount=safe_float(row.get('change')),
                    volume=safe_int(row.get('vol')),
                    amount=safe_float(row.get('amount')),
                    high=safe_float(row.get('high')),
                    low=safe_float(row.get('low')),
                    open_price=safe_float(row.get('open')),
                    pre_close=safe_float(row.get('pre_close')),
                    turnover_rate=safe_float(row.get('turnover_ratio')), # Pro jiekoukenengyouhuanshoulv
                    pe_ratio=safe_float(row.get('pe')),
                    pb_ratio=safe_float(row.get('pb')),
                    total_mv=safe_float(row.get('total_mv')),
                )
        except Exception as e:
            # jinjilutiaoshirizhi，bubaocuo，jixuchangshijiangji
            logger.debug(f"Tushare Pro shishixingqingbukeyong (kenengshijifenbuzu): {e}")

        # jiangji：changshijiubanjiekou
        try:
            import tushare as ts

            symbol = self._get_legacy_realtime_symbol(stock_code)

            # diaoyongjiubanshishijiekou (ts.get_realtime_quotes)
            df = ts.get_realtime_quotes(symbol)

            if df is None or df.empty:
                return None

            row = df.iloc[0]

            # jisuanzhangdiefu
            price = safe_float(row['price'])
            pre_close = safe_float(row['pre_close'])
            change_pct = 0.0
            change_amount = 0.0

            if price and pre_close and pre_close > 0:
                change_amount = price - pre_close
                change_pct = (change_amount / pre_close) * 100

            # goujiantongyiduixiang
            return UnifiedRealtimeQuote(
                code=normalized_code,
                name=str(row['name']),
                source=RealtimeSource.TUSHARE,
                price=price,
                change_pct=round(change_pct, 2),
                change_amount=round(change_amount, 2),
                volume=safe_int(row['volume']) // 100,  # zhuanhuanweishou
                amount=safe_float(row['amount']),
                high=safe_float(row['high']),
                low=safe_float(row['low']),
                open_price=safe_float(row['open']),
                pre_close=pre_close,
            )

        except Exception as e:
            logger.warning(f"Tushare (jiuban) huoqushishixingqingshibai {stock_code}: {e}")
            return None

    def get_main_indices(self, region: str = "cn") -> Optional[List[dict]]:
        """
        huoquzhuyaozhishushishixingqing (Tushare Pro)，jinzhichi A gu
        """
        if region != "cn":
            return None
        if self._api is None:
            return None

        from .realtime_types import safe_float

        # zhishuyingshe：Tusharedaima -> mingcheng
        indices_map = {
            '000001.SH': 'shangzhengzhishu',
            '399001.SZ': 'shenzhengchengzhi',
            '399006.SZ': 'chuangyebanzhi',
            '000688.SH': 'kechuang50',
            '000016.SH': 'shangzheng50',
            '000300.SH': 'hushen300',
        }

        try:
            self._check_rate_limit()

            # Tushare index_daily huoqulishishuju，shishishujuxuyongqitajiekouhuogusuan
            # youyu Tushare mianfeiyonghukenengwufahuoquzhishushishixingqing，zhelizuoweibeixuan
            # shiyong index_daily huoquzuijinjiaoyirishuju

            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - pd.Timedelta(days=5)).strftime('%Y%m%d')

            results = []

            # pilianghuoqusuoyouzhishushuju
            for ts_code, name in indices_map.items():
                try:
                    df = self._api.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                    if df is not None and not df.empty:
                        row = df.iloc[0] # zuixinyitian

                        current = safe_float(row['close'])
                        prev_close = safe_float(row['pre_close'])

                        results.append({
                            'code': ts_code.split('.')[0], # jianrong sh000001 geshixuzhuanhuan，zhelibaochichunshuzi
                            'name': name,
                            'current': current,
                            'change': safe_float(row['change']),
                            'change_pct': safe_float(row['pct_chg']),
                            'open': safe_float(row['open']),
                            'high': safe_float(row['high']),
                            'low': safe_float(row['low']),
                            'prev_close': prev_close,
                            'volume': safe_float(row['vol']),
                            'amount': safe_float(row['amount']) * 1000, # qianyuanzhuanyuan
                            'amplitude': 0.0 # Tushare index_daily buzhijiefanhuizhenfu
                        })
                except Exception as e:
                    logger.debug(f"Tushare huoquzhishu {name} shibai: {e}")
                    continue

            if results:
                return results
            else:
                logger.warning("[Tushare] weihuoqudaozhishuhangqingshuju")

        except Exception as e:
            logger.error(f"[Tushare] huoquzhishuhangqingshibai: {e}")

        return None

    def get_market_stats(self) -> Optional[dict]:
        """
        huoqushichangzhangdietongji (Tushare Pro)
        2000jifen meitianfangwengaijiekou ts.pro_api().rt_k liangci
        jiekouxianzhijian：https://tushare.pro/document/1?doc_id=108
        """
        if self._api is None:
            return None

        try:
            logger.info("[Tushare] ts.pro_api() huoqushichangtongji...")
            
            # huoqudangqianzhongguoshijian，panduanshifouzaijiaoyishijiannei
            china_now = self._get_china_now()
            current_clock = china_now.strftime("%H:%M")
            current_date = china_now.strftime("%Y%m%d")

            trade_dates = self._get_trade_dates(current_date)
            if not trade_dates:
                return None

            if current_date in trade_dates:
                if current_clock < '09:30' or current_clock > '16:30':
                    use_realtime = False
                else:
                    use_realtime = True
            else:
                use_realtime = False

            # ruoshipandeshihoushiyong zeshiyongqitakeyishipanhuoqudeshujuyuan akshare、efinance
            if use_realtime:
                try:
                    df = self._call_api_with_rate_limit("rt_k", ts_code='3*.SZ,6*.SH,0*.SZ,92*.BJ')
                    if df is not None and not df.empty:
                        return self._calc_market_stats(df)
                    
                except Exception as e:
                    logger.error(f"[Tushare] ts.pro_api().rt_k changshihuoqushishishujushibai: {e}")
                    return None
            else:

                if current_date not in trade_dates:
                    last_date = self._pick_trade_date(trade_dates, use_today=True)  # nazuijinderiqi
                else:
                    if current_clock < '09:30': 
                        last_date = self._pick_trade_date(trade_dates, use_today=False)  # naquqianyitiandeshuju
                    else:  # ji '> 16:30'                  
                        last_date = self._pick_trade_date(trade_dates, use_today=True)  # naqudangtiandeshuju

                if last_date is None:
                    return None

                try:
                    df = self._call_api_with_rate_limit(
                        "daily",
                        ts_code='3*.SZ,6*.SH,0*.SZ,92*.BJ',
                        start_date=last_date,
                        end_date=last_date,
                    )
                    # weifangzhibutongjiekoufanhuideliemingdaxiaoxiebuyizhi（liru rt_k fanhuixiaoxie，daily fanhuidaxie），tongyijiangliemingzhuanweixiaoxie
                    df.columns = [col.lower() for col in df.columns]

                    # huoqugupiaojichuxinxi（baohandaimahemingcheng）
                    df_basic = self._call_api_with_rate_limit("stock_basic", fields='ts_code,name')
                    df = pd.merge(df, df_basic, on='ts_code', how='left')
                    # jiang dailyde amount liedezhichengyi 1000 laiheqitashujuyuanbaochiyizhi
                    if 'amount' in df.columns:
                        df['amount'] = df['amount'] * 1000

                    if df is not None and not df.empty:
                        return self._calc_market_stats(df)
                except Exception as e:
                    logger.error(f"[Tushare] ts.pro_api().daily huoqushujushibai: {e}")
                    

            
        except Exception as e:
            logger.error(f"[Tushare] huoqushichangtongjishibai: {e}")

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

    def get_trade_time(self,early_time='09:30',late_time='16:30') -> Optional[str]:
        '''
        huoqudangqianshijiankeyihuodeshujudekaishishijianriqi

        Args:
                early_time: moren '09:30'
                late_time: moren '16:30'
                early_time-late_time zhijianweishiyongshangyigejiaoyirishujudeshijianduan，qitashijianweishiyongdangtianshujudeshijianduan
        Returns:
                start_date: keyihuodeshujudekaishiriqi
        '''
        china_now = self._get_china_now()
        china_date = china_now.strftime("%Y%m%d")
        china_clock = china_now.strftime("%H:%M")

        trade_dates = self._get_trade_dates(china_date)
        if not trade_dates:
            return None

        if china_date in trade_dates:
            if  early_time < china_clock < late_time: # shiyongshangyigejiaoyirishujudeshijianduan
                use_today = False
            else:
                use_today = True
        else:
            # feijiaoyiri： todaybuzaitrade_dateszhong，trade_dates[0]jiushizuijinjiaoyiri
            use_today = True

        start_date = self._pick_trade_date(trade_dates, use_today=use_today)
        if start_date is None:
            return None

        if not use_today:
            logger.info(f"[Tushare] dangqianshijian {china_clock} kenengwufahuoqudangtianchoumafenbu，changshihuoquqianyigejiaoyirideshuju {start_date}")

        return start_date
    
    def get_sector_rankings(self, n: int = 5) -> Optional[Tuple[list, list]]:
        """
        huoquhangyebankuaizhangdiebang (Tushare Pro)
        
        shujuyuanyouxianji：
        1. tonghuashunjiekou (ts.pro_api().moneyflow_ind_ths)
        2. dongcaijiekou (ts.pro_api().moneyflow_ind_dc)
        zhuyi：meigejiekoudehangyefenleihebankuaidingyibutong，huidaozhijieguoliangzhebuyizhi
        """
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

        # 15:30zhihoucaiyoudangtianshuju
        start_date = self.get_trade_time(early_time='00:00', late_time='15:30')
        if not start_date:
            return None

        # youxiantonghuashunjiekou
        logger.info("[Tushare] ts.pro_api().moneyflow_ind_ths huoqubankuaipaihang(tonghuashun)...")
        try:
            df = self._call_api_with_rate_limit("moneyflow_ind_ths", trade_date=start_date)
            if df is not None and not df.empty:
                change_col = 'pct_change'
                name = 'industry'
                if change_col in df.columns:
                    return _get_rank_top_n(df, change_col, name, n)
        except Exception as e:
            logger.warning(f"[Tushare] huoqutonghuashunhangyebankuaizhangdiebangshibai: {e} changshidongcaijiekou")

        # tonghuashunjiekoushibai，jiangjichangshidongcaijiekou
        logger.info("[Tushare] ts.pro_api().moneyflow_ind_dc huoqubankuaipaihang(dongcai)...")
        try:
            df = self._call_api_with_rate_limit("moneyflow_ind_dc", trade_date=start_date)
            if df is not None and not df.empty:
                df = df[df['content_type'] == 'hangye']  # guolvchuxingyebankuai
                change_col = 'pct_change'
                name = 'name'
                if change_col in df.columns:
                    return _get_rank_top_n(df, change_col, name, n)
        except Exception as e:
            logger.warning(f"[Tushare] huoqudongcaihangyebankuaizhangdiebangshibai: {e}")
            return None
        
        # huoquweikonghuozhejiekoudiaoyongshibai，fanhui None
        return None
    
    

    
    def get_chip_distribution(self, stock_code: str) -> Optional[ChipDistribution]:
        """
        huoquchoumafenbushuju
        
        shujulaiyuan：ts.pro_api().cyq_chips()
        baohan：huolibili、pingjunchengben、choumajizhongdu
        
        zhuyi：ETF/zhishumeiyouchoumafenbushuju，huizhijiefanhui None；ganggubuzhichi，zhijiefanhui None。
        5000jifenyixiameitianfangwen15ci,meixiaoshifangwen5ci
        
        Args:
            stock_code: gupiaodaima
            
        Returns:
            ChipDistribution duixiang（zuixinjiaoyirideshuju），huoqushibaifanhui None

        """
        if _is_us_code(stock_code):
            logger.warning(f"[Tushare] TushareFetcher buzhichimeigu {stock_code} dechoumafenbu")
            return None
        
        if _is_etf_code(stock_code):
            logger.warning(f"[Tushare] TushareFetcher buzhichi ETF {stock_code} dechoumafenbu")
            return None

        if _is_hk_market(stock_code):
            logger.warning(f"[Tushare] TushareFetcher buzhichiganggu {stock_code} dechoumafenbu")
            return None
        
        try:
            # 19dianzhihoucaiyoudangtianshuju
            start_date = self.get_trade_time(early_time='00:00', late_time='19:00') 
            if not start_date:
                return None

            ts_code = self._convert_stock_code(stock_code)

            df = self._call_api_with_rate_limit(
                "cyq_chips",
                ts_code=ts_code,
                start_date=start_date,
                end_date=start_date,
            )
            if df is not None and not df.empty:
                daily_df = self._call_api_with_rate_limit(
                    "daily",
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=start_date,
                )
                if daily_df is None or daily_df.empty:
                    return None
                current_price = daily_df.iloc[0]['close']
                metrics = self.compute_cyq_metrics(df, current_price)

                chip = ChipDistribution(
                    code=stock_code,
                    date=datetime.strptime(start_date, '%Y%m%d').strftime('%Y-%m-%d'),
                    profit_ratio=metrics['huolibili'],
                    avg_cost=metrics['pingjunchengben'],
                    cost_90_low=metrics['90chengben-di'],
                    cost_90_high=metrics['90chengben-gao'],
                    concentration_90=metrics['90jizhongdu'],
                    cost_70_low=metrics['70chengben-di'],
                    cost_70_high=metrics['70chengben-gao'],
                    concentration_70=metrics['70jizhongdu'],
                )
                
                logger.info(f"[choumafenbu] {stock_code} riqi={chip.date}: huolibili={chip.profit_ratio:.1%}, "
                        f"pingjunchengben={chip.avg_cost}, 90%jizhongdu={chip.concentration_90:.2%}, "
                        f"70%jizhongdu={chip.concentration_70:.2%}")
                return chip

        except Exception as e:
            logger.warning(f"[Tushare] huoquchoumafenbushibai {stock_code}: {e}")
            return None

    def compute_cyq_metrics(self, df: pd.DataFrame, current_price: float) -> dict:
        """
        jiyu Tushare dechoumafenbumingxibiao (cyq_chips) jisuanchangyongchoumazhibiao  
        :param df: baohan 'price' he 'percent' liede DataFrame  
        :param current_price: gupiaodangtiandidangqianjia/shoupanjia (yongyujisuanhuolibili)  
        :return: baohangexiangchoumazhibiaodizidian  
        """
        import numpy as np
        # 1. quebaoanjiagecongxiaodaodapaixu (Tushare fanhuideshujuwangwangshichundaoxude)
        df_sorted = df.sort_values(by='price', ascending=True).reset_index(drop=True)

        # 2. fangzhiyuanshishuju percent zonghechanshengfudianshuwucha，guiyihuadao 100%
        total_percent = df_sorted['percent'].sum()

        df_sorted['norm_percent'] = df_sorted['percent'] / total_percent * 100

        # 3. jisuanchoumadeleijifenbu
        df_sorted['cumsum'] = df_sorted['norm_percent'].cumsum()

        # --- huolibili ---
        # suoyoujiage <= dangqianjiadechoumazhihe
        winner_rate = df_sorted[df_sorted['price'] <= current_price]['norm_percent'].sum()

        # --- pingjunchengben ---
        # jiagedejiaquanpingjunzhi
        avg_cost = np.average(df_sorted['price'], weights=df_sorted['norm_percent'])

        # --- fuzhuhanshu：qiuzhidingleijibilichudejiage ---
        def get_percentile_price(target_pct):
            # xunzhaoleijiqiuhediyicidayudengyumubiaobaifenbidexingsuoyin
            idx = df_sorted['cumsum'].searchsorted(target_pct)
            idx = min(idx, len(df_sorted) - 1) # fangzhiyuejie
            return df_sorted.loc[idx, 'price']

        # --- 90% chengbenquyujizhongdu ---
        # qutouquweige 5%
        cost_90_low = get_percentile_price(5)
        cost_90_high = get_percentile_price(95)
        if (cost_90_high + cost_90_low) != 0:
            concentration_90 = (cost_90_high - cost_90_low) / (cost_90_high + cost_90_low) * 100
        else:
            concentration_90 = 0.0
            
        # --- 70% chengbenquyujizhongdu ---
        # qutouquweige 15%
        cost_70_low = get_percentile_price(15)
        cost_70_high = get_percentile_price(85)
        if (cost_70_high + cost_70_low) != 0:
            concentration_70 = (cost_70_high - cost_70_low) / (cost_70_high + cost_70_low) * 100
        else:
            concentration_70 = 0.0

        # fanhuigeshihuajieguo
        return {
            "huolibili": round(winner_rate/100, 4), # /100 yuaksharebaochiyizhi，fanhuixiaoshugeshi
            "pingjunchengben": round(avg_cost, 4),
            "90chengben-di": round(cost_90_low, 4),
            "90chengben-gao": round(cost_90_high, 4),
            "90jizhongdu": round(concentration_90/100, 4),
            "70chengben-di": round(cost_70_low, 4),
            "70chengben-gao": round(cost_70_high, 4),
            "70jizhongdu": round(concentration_70/100, 4)
        }



if __name__ == "__main__":
    # ceshidaima
    logging.basicConfig(level=logging.DEBUG)
    
    fetcher = TushareFetcher()
    
    try:
        # ceshilishishuju
        df = fetcher.get_daily_data('600519')  # maotai
        print(f"huoquchenggong，gong {len(df)} tiaoshuju")
        print(df.tail())
        
        # ceshigupiaomingcheng
        name = fetcher.get_stock_name('600519')
        print(f"gupiaomingcheng: {name}")
        
    except Exception as e:
        print(f"huoqushibai: {e}")

    # ceshishichangtongji
    print("\n" + "=" * 50)
    print("Testing get_market_stats (tushare)")
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
