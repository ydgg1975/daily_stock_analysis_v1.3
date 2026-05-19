# -*- coding: utf-8 -*-
"""
===================================
BaostockFetcher - beiyongshujuyuan 2 (Priority 3)
===================================

shujulaiyuan：zhengquanbao（Baostock）
tedian：mianfei、wuxu Token、xuyaodengluguanli
youdian：wending、wupeiexianzhi

guanjiancelve：
1. guanli bs.login() he bs.logout() shengmingzhouqi
2. shiyongshangxiawenguanliqifangzhilianjiexielou
3. shibaihouzhishutuibizhongshi
"""

import logging
import re
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Generator

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS, is_bse_code, _is_hk_market
import os

logger = logging.getLogger(__name__)


def _is_us_code(stock_code: str) -> bool:
    """
    panduandaimashifouweimeigu
    
    meigudaimaguize：
    - 1-5gedaxiezimu，ru 'AAPL', 'TSLA'
    - kenengbaohan '.'，ru 'BRK.B'
    """
    code = stock_code.strip().upper()
    return bool(re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', code))


class BaostockFetcher(BaseFetcher):
    """
    Baostock shujuyuanshixian
    
    youxianji：3
    shujulaiyuan：zhengquanbao Baostock API
    
    guanjiancelve：
    - shiyongshangxiawenguanliqiguanlilianjieshengmingzhouqi
    - meiciqingqiudouchongxindenglu/dengchu，fangzhilianjiexielou
    - shibaihouzhishutuibizhongshi
    
    Baostock tedian：
    - mianfei、wuxuzhuce
    - xuyaoxianshidenglu/dengchu
    - shujugengxinlveyouyanchi（T+1）
    """
    
    name = "BaostockFetcher"
    priority = int(os.getenv("BAOSTOCK_PRIORITY", "3"))
    
    def __init__(self):
        """chushihua BaostockFetcher"""
        self._bs_module = None
    
    def _get_baostock(self):
        """
        yanchijiazai baostock mokuai
        
        zhizaishoucishiyongshidaoru，bimianweianzhuangshibaocuo
        """
        if self._bs_module is None:
            import baostock as bs
            self._bs_module = bs
        return self._bs_module
    
    @contextmanager
    def _baostock_session(self) -> Generator:
        """
        Baostock lianjieshangxiawenguanliqi
        
        quebao：
        1. jinrushangxiawenshizidongdenglu
        2. tuichushangxiawenshizidongdengchu
        3. yichangshiyenengzhengquedengchu
        
        shiyongshili：
            with self._baostock_session():
                # zaizhelizhixingshujuchaxun
        """
        bs = self._get_baostock()
        login_result = None
        
        try:
            # denglu Baostock
            login_result = bs.login()
            
            if login_result.error_code != '0':
                raise DataFetchError(f"Baostock denglushibai: {login_result.error_msg}")
            
            logger.debug("Baostock dengluchenggong")
            
            yield bs
            
        finally:
            # quebaodengchu，fangzhilianjiexielou
            try:
                logout_result = bs.logout()
                if logout_result.error_code == '0':
                    logger.debug("Baostock dengchuchenggong")
                else:
                    logger.warning(f"Baostock dengchuyichang: {logout_result.error_msg}")
            except Exception as e:
                logger.warning(f"Baostock dengchushifashengcuowu: {e}")
    
    def _convert_stock_code(self, stock_code: str) -> str:
        """
        zhuanhuangupiaodaimawei Baostock geshi
        
        Baostock yaoqiudegeshi：
        - hushi：sh.600519
        - shenshi：sz.000001
        
        Args:
            stock_code: yuanshidaima，ru '600519', '000001'
            
        Returns:
            Baostock geshidaima，ru 'sh.600519', 'sz.000001'
        """
        code = stock_code.strip()

        # HK stocks are not supported by Baostock
        if _is_hk_market(code):
            raise DataFetchError(f"BaostockFetcher buzhichiganggu {code}，qingshiyong AkshareFetcher")

        # yijingbaohanqianzhuideqingkuang
        if code.startswith(('sh.', 'sz.')):
            return code.lower()
        
        # quchukenengdehouzhui
        code = code.replace('.SH', '').replace('.SZ', '').replace('.sh', '').replace('.sz', '')
        
        # ETF: Shanghai ETF (51xx, 52xx, 56xx, 58xx) -> sh; Shenzhen ETF (15xx, 16xx, 18xx) -> sz
        if len(code) == 6:
            if code.startswith(('51', '52', '56', '58')):
                return f"sh.{code}"
            if code.startswith(('15', '16', '18')):
                return f"sz.{code}"

        # genjudaimaqianzhuipanduanshichang
        if code.startswith(('600', '601', '603', '688')):
            return f"sh.{code}"
        elif code.startswith(('000', '002', '300')):
            return f"sz.{code}"
        else:
            logger.warning(f"wufaquedinggupiao {code} deshichang，morenshiyongshenshi")
            return f"sz.{code}"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        cong Baostock huoquyuanshishuju
        
        shiyong query_history_k_data_plus() huoqurixianshuju
        
        liucheng：
        1. jianchashifouweimeigu（buzhichi）
        2. shiyongshangxiawenguanliqiguanlilianjie
        3. zhuanhuangupiaodaimageshi
        4. diaoyong API chaxunshuju
        5. jiangjieguozhuanhuanwei DataFrame
        """
        # meigubuzhichi，paochuyichangrang DataFetcherManager qiehuandaoqitashujuyuan
        if _is_us_code(stock_code):
            raise DataFetchError(f"BaostockFetcher buzhichimeigu {stock_code}，qingshiyong AkshareFetcher huo YfinanceFetcher")

        # ganggubuzhichi，paochuyichangrang DataFetcherManager qiehuandaoqitashujuyuan
        if _is_hk_market(stock_code):
            raise DataFetchError(f"BaostockFetcher buzhichiganggu {stock_code}，qingshiyong AkshareFetcher")

        # beijiaosuobuzhichi，paochuyichangrang DataFetcherManager qiehuandaoqitashujuyuan
        if is_bse_code(stock_code):
            raise DataFetchError(
                f"BaostockFetcher buzhichibeijiaosuo {stock_code}，jiangzidongqiehuanqitashujuyuan"
            )
        
        # zhuanhuandaimageshi
        bs_code = self._convert_stock_code(stock_code)
        
        logger.debug(f"diaoyong Baostock query_history_k_data_plus({bs_code}, {start_date}, {end_date})")
        
        with self._baostock_session() as bs:
            try:
                # chaxunrixianshuju
                # adjustflag: 1-houfuquan，2-qianfuquan，3-bufuquan
                rs = bs.query_history_k_data_plus(
                    code=bs_code,
                    fields="date,open,high,low,close,volume,amount,pctChg",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",  # rixian
                    adjustflag="2"  # qianfuquan
                )
                
                if rs.error_code != '0':
                    raise DataFetchError(f"Baostock chaxunshibai: {rs.error_msg}")
                
                # zhuanhuanwei DataFrame
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                
                if not data_list:
                    raise DataFetchError(f"Baostock weichaxundao {stock_code} deshuju")
                
                df = pd.DataFrame(data_list, columns=rs.fields)
                
                return df
                
            except Exception as e:
                if isinstance(e, DataFetchError):
                    raise
                raise DataFetchError(f"Baostock huoqushujushibai: {e}") from e
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        biaozhunhua Baostock shuju
        
        Baostock fanhuidelieming：
        date, open, high, low, close, volume, amount, pctChg
        
        xuyaoyingshedaobiaozhunlieming：
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()
        
        # liemingyingshe（zhixuyaochuli pctChg）
        column_mapping = {
            'pctChg': 'pct_chg',
        }
        
        df = df.rename(columns=column_mapping)
        
        # shuzhileixingzhuanhuan（Baostock fanhuidedoushizifuchuan）
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
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
        
        shiyong Baostock de query_stock_basic jiekouhuoqugupiaojibenxinxi
        
        Args:
            stock_code: gupiaodaima
            
        Returns:
            gupiaomingcheng，shibaifanhui None
        """
        # jianchahuancun
        if hasattr(self, '_stock_name_cache') and stock_code in self._stock_name_cache:
            return self._stock_name_cache[stock_code]
        
        # chushihuahuancun
        if not hasattr(self, '_stock_name_cache'):
            self._stock_name_cache = {}
        
        try:
            bs_code = self._convert_stock_code(stock_code)
            
            with self._baostock_session() as bs:
                # chaxungupiaojibenxinxi
                rs = bs.query_stock_basic(code=bs_code)
                
                if rs.error_code == '0':
                    data_list = []
                    while rs.next():
                        data_list.append(rs.get_row_data())
                    
                    if data_list:
                        # Baostock fanhuideziduan：code, code_name, ipoDate, outDate, type, status
                        fields = rs.fields
                        name_idx = fields.index('code_name') if 'code_name' in fields else None
                        if name_idx is not None and len(data_list[0]) > name_idx:
                            name = data_list[0][name_idx]
                            self._stock_name_cache[stock_code] = name
                            logger.debug(f"Baostock huoqugupiaomingchengchenggong: {stock_code} -> {name}")
                            return name
                
        except Exception as e:
            logger.warning(f"Baostock huoqugupiaomingchengshibai {stock_code}: {e}")
        
        return None
    
    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """
        huoqugupiaoliebiao
        
        shiyong Baostock de query_stock_basic jiekouhuoququanbugupiaoliebiao
        
        Returns:
            baohan code, name liede DataFrame，shibaifanhui None
        """
        try:
            with self._baostock_session() as bs:
                # chaxunsuoyougupiaojibenxinxi
                rs = bs.query_stock_basic()
                
                if rs.error_code == '0':
                    data_list = []
                    while rs.next():
                        data_list.append(rs.get_row_data())
                    
                    if data_list:
                        df = pd.DataFrame(data_list, columns=rs.fields)
                        
                        # zhuanhuandaimageshi（quchu sh. huo sz. qianzhui）
                        df['code'] = df['code'].apply(lambda x: x.split('.')[1] if '.' in x else x)
                        df = df.rename(columns={'code_name': 'name'})
                        
                        # gengxinhuancun
                        if not hasattr(self, '_stock_name_cache'):
                            self._stock_name_cache = {}
                        for _, row in df.iterrows():
                            self._stock_name_cache[row['code']] = row['name']
                        
                        logger.info(f"Baostock huoqugupiaoliebiaochenggong: {len(df)} tiao")
                        return df[['code', 'name']]
                
        except Exception as e:
            logger.warning(f"Baostock huoqugupiaoliebiaoshibai: {e}")
        
        return None


if __name__ == "__main__":
    # ceshidaima
    logging.basicConfig(level=logging.DEBUG)
    
    fetcher = BaostockFetcher()
    
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
