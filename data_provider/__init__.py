# -*- coding: utf-8 -*-
"""
===================================
shujuyuancelveceng - baochushihua
===================================

benbaoshixiancelvemoshiguanliduogeshujuyuan，shixian：
1. tongyideshujuhuoqujiekou
2. zidongguzhangqiehuan
3. fangfengjinliukongcelve

shujuyuanyouxianji（dongtaitiaozheng）：
【peizhile TUSHARE_TOKEN shi】
1. TushareFetcher (Priority 0) - 🔥 zuigaoyouxianji（dongtaitisheng）
2. EfinanceFetcher (Priority 0) - tongyouxianji
3. AkshareFetcher (Priority 1) - laizi akshare ku
4. PytdxFetcher (Priority 2) - laizi pytdx ku（tongdaxin）
5. BaostockFetcher (Priority 3) - laizi baostock ku
6. YfinanceFetcher (Priority 4) - laizi yfinance ku

【weipeizhi TUSHARE_TOKEN shi】
1. EfinanceFetcher (Priority 0) - zuigaoyouxianji，laizi efinance ku
2. AkshareFetcher (Priority 1) - laizi akshare ku
3. PytdxFetcher (Priority 2) - laizi pytdx ku（tongdaxin）
4. TushareFetcher (Priority 2) - laizi tushare ku（bukeyong）
5. BaostockFetcher (Priority 3) - laizi baostock ku
6. YfinanceFetcher (Priority 4) - laizi yfinance ku
7. LongbridgeFetcher (Priority 5) - zhangqiao OpenAPI（meigu/ganggudoudi）

tishi：youxianjishuziyuexiaoyueyouxian，tongyouxianjianchushihuashunxupailie
"""

from .base import BaseFetcher, DataFetcherManager
from .efinance_fetcher import EfinanceFetcher
from .akshare_fetcher import AkshareFetcher, is_hk_stock_code
from .tushare_fetcher import TushareFetcher
from .pytdx_fetcher import PytdxFetcher
from .baostock_fetcher import BaostockFetcher
from .yfinance_fetcher import YfinanceFetcher
from .longbridge_fetcher import LongbridgeFetcher
from .finnhub_fetcher import FinnhubFetcher
from .alphavantage_fetcher import AlphaVantageFetcher
from .us_index_mapping import is_us_index_code, is_us_stock_code, get_us_index_yf_symbol, US_INDEX_MAPPING

__all__ = [
    'BaseFetcher',
    'DataFetcherManager',
    'EfinanceFetcher',
    'AkshareFetcher',
    'TushareFetcher',
    'PytdxFetcher',
    'BaostockFetcher',
    'YfinanceFetcher',
    'LongbridgeFetcher',
    'FinnhubFetcher',
    'AlphaVantageFetcher',
    'is_us_index_code',
    'is_us_stock_code',
    'is_hk_stock_code',
    'get_us_index_yf_symbol',
    'US_INDEX_MAPPING',
]
