# -*- coding: utf-8 -*-
"""
===================================
ZhituFetcher - 智图数据源 (Priority 5)
===================================

数据来源：智图数据 API (api.zhituapi.com)
特点：
1. 股票和指数数据覆盖全面
2. 提供技术指标数据 (MACD/KDJ/BOLL/MA)
3. 有 Token 配额限制

API 文档：
- 股票接口: https://www.zhituapi.com/hsstockapi.html
- 指数接口: https://www.zhituapi.com/hsindexapi.html

认证方式：URL 参数传递 token
"""

import logging
import os
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd
import requests

from .base import BaseFetcher, DataFetchError
from .realtime_types import UnifiedRealtimeQuote, RealtimeSource, safe_float, safe_int

logger = logging.getLogger(__name__)

# 智图 API 基础 URL
ZHITU_HS_BASE_URL = "https://api.zhituapi.com/hs"   # 股票接口
ZHITU_HZ_BASE_URL = "https://api.zhituapi.com/hz"   # 指数接口

# 指数代码映射 (智图格式 -> 标准格式)
ZHITU_INDEX_MAP = {
    "000001.SH": "上证指数",
    "000300.SH": "沪深300",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
    "000016.SH": "上证50",
    "000905.SH": "中证500",
    "399005.SZ": "中小100",
}

# 主要指数列表 (智图格式)
ZHITU_MAJOR_INDICES = [
    "000001.SH",  # 上证指数
    "000300.SH",  # 沪深300
    "399001.SZ",  # 深证成指
    "399006.SZ",  # 创业板指
    "000016.SH",  # 上证50
]


class ZhituFetcher(BaseFetcher):
    """
    智图数据源实现

    优先级：5（在 Baostock/Yfinance 之前）
    数据来源：智图数据 API

    主要 API：
    - GET /hs/real/ssjy/{code} - 实时行情
    - GET /hs/history/{code}.{market}/d/n - 日线历史
    - GET /hz/real/ssjy/{index_code} - 指数实时行情
    - GET /hz/history/ma/{index_code}/d - 指数均线数据
    """

    name = "ZhituFetcher"
    priority = int(os.getenv("ZHITU_PRIORITY", "5"))

    def __init__(self, token: str = None):
        """
        初始化 ZhituFetcher

        Args:
            token: 智图 API Token，若未提供则尝试从环境变量读取
        """
        self._token = token or os.getenv("ZHITU_API_TOKEN", "")
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self._stock_name_cache: Dict[str, str] = {}

    def _get(self, url: str, params: Dict = None, timeout: int = 30) -> Dict:
        """
        发送 GET 请求

        Args:
            url: 请求 URL
            params: 请求参数
            timeout: 超时时间（秒）

        Returns:
            JSON 响应

        Raises:
            DataFetchError: 请求失败时抛出
        """
        try:
            # 添加 token 参数
            query_params = {"token": self._token}
            if params:
                query_params.update(params)

            response = self._session.get(url, params=query_params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise DataFetchError(f"请求超时: {url}")
        except requests.exceptions.RequestException as e:
            raise DataFetchError(f"请求失败: {e}")

    def _convert_stock_code(self, stock_code: str) -> Tuple[str, str]:
        """
        将标准股票代码转换为智图格式

        Args:
            stock_code: 标准股票代码，如 '600519', '000001.SZ'

        Returns:
            (代码, 市场) - 如 ('600519', 'sh')
        """
        code = stock_code.strip().upper()

        # 处理带后缀的代码
        if '.' in code:
            code_part, suffix = code.rsplit('.', 1)
            suffix_map = {'SH': 'sh', 'SZ': 'sz', 'SHANGHAI': 'sh', 'SHENZHEN': 'sz'}
            market = suffix_map.get(suffix.upper(), suffix.lower())
            return code_part, market

        # 根据代码前缀判断市场
        if code.startswith(('6', '5', '9')):
            return code, 'sh'  # 上证
        elif code.startswith(('0', '1', '2', '3', '4')):
            return code, 'sz'  # 深证
        else:
            return code, 'sz'  # 默认深证

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取日线原始数据

        Args:
            stock_code: 股票代码，如 '600519'
            start_date: 开始日期 'YYYY-MM-DD'
            end_date: 结束日期 'YYYY-MM-DD'

        Returns:
            原始 DataFrame
        """
        code, market = self._convert_stock_code(stock_code)

        # 转换日期格式 (YYYY-MM-DD -> YYYYMMDD)
        start = start_date.replace('-', '')
        end = end_date.replace('-', '')

        url = f"{ZHITU_HS_BASE_URL}/history/{code}.{market}/d/n"

        try:
            data = self._get(url, timeout=30)

            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                return df
            else:
                raise DataFetchError(f"无数据返回: {stock_code}")

        except Exception as e:
            raise DataFetchError(f"获取日线数据失败: {e}")

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化数据列名

        智图返回字段: t, o, h, l, c, v, a
        标准字段: date, open, high, low, close, volume, amount
        """
        if df.empty:
            return df

        # 列名映射
        column_map = {
            't': 'date',
            'o': 'open',
            'h': 'high',
            'l': 'low',
            'c': 'close',
            'v': 'volume',
            'a': 'amount',
        }

        # 重命名列
        df = df.rename(columns=column_map)

        # 确保日期格式正确
        if 'date' in df.columns:
            # 尝试转换为日期格式
            df['date'] = pd.to_datetime(df['date'], format='mixed', errors='coerce')

        # 确保数值类型正确
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 按日期排序
        if 'date' in df.columns:
            df = df.sort_values('date')

        return df

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        获取实时行情

        Args:
            stock_code: 股票代码

        Returns:
            UnifiedRealtimeQuote 对象
        """
        code, market = self._convert_stock_code(stock_code)

        url = f"{ZHITU_HS_BASE_URL}/real/ssjy/{code}"

        try:
            data = self._get(url, timeout=15)

            if not data:
                return None

            # 智图返回的是 dict，不是 list
            item = data[0] if isinstance(data, list) else data

            # 检查是否有有效数据
            if not item or 'p' not in item:
                return None

            return UnifiedRealtimeQuote(
                code=stock_code,
                name=item.get('mc', '') or '',  # 名称（可能在某些接口返回）
                price=safe_float(item.get('p', 0)),
                change_pct=safe_float(item.get('pc', 0)),
                change_amount=safe_float(item.get('ud', 0)),
                volume=safe_int(item.get('v', 0)),
                amount=safe_float(item.get('cje', 0)),
                high=safe_float(item.get('h', 0)),
                low=safe_float(item.get('l', 0)),
                open_price=safe_float(item.get('o', 0)),
                pe_ratio=safe_float(item.get('pe', 0)),
                pb_ratio=safe_float(item.get('sjl', 0)),
                change_60d=safe_float(item.get('zdf60', 0)),  # 60日涨跌幅
                source=RealtimeSource.ZHITU,
            )

        except Exception as e:
            logger.debug(f"[Zhitu] 获取实时行情失败 {stock_code}: {e}")
            return None

    def get_stock_name(self, stock_code: str, allow_realtime: bool = True) -> Optional[str]:
        """
        获取股票名称

        Args:
            stock_code: 股票代码
            allow_realtime: 是否允许实时获取

        Returns:
            股票名称
        """
        # 先检查缓存
        if stock_code in self._stock_name_cache:
            return self._stock_name_cache[stock_code]

        # 尝试从实时行情获取
        if allow_realtime:
            quote = self.get_realtime_quote(stock_code)
            if quote and quote.name:
                self._stock_name_cache[stock_code] = quote.name
                return quote.name

        return None

    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """
        获取主要指数实时行情

        Args:
            region: 市场区域，cn=A股

        Returns:
            指数列表
        """
        if region != "cn":
            return None

        results = []

        for index_code in ZHITU_MAJOR_INDICES:
            try:
                code, market = self._convert_stock_code(index_code)
                url = f"{ZHITU_HZ_BASE_URL}/real/ssjy/{code}"

                data = self._get(url, timeout=15)

                if data and len(data) > 0:
                    item = data[0] if isinstance(data, list) else data

                    results.append({
                        "code": index_code,
                        "name": ZHITU_INDEX_MAP.get(index_code, item.get('mc', '')),
                        "current": safe_float(item.get('p', 0)),
                        "change": safe_float(item.get('ud', 0)),
                        "change_pct": safe_float(item.get('pc', 0)),
                        "volume": safe_int(item.get('v', 0)),
                        "amount": safe_float(item.get('cje', 0)),
                    })

            except Exception as e:
                logger.debug(f"[Zhitu] 获取指数失败 {index_code}: {e}")
                continue

        return results if results else None

    def get_daily_data_with_indicators(self, stock_code: str, days: int = 30) -> Optional[pd.DataFrame]:
        """
        获取指数带技术指标的历史数据（MA/MACD/KDJ/BOLL）

        这是智图的特色接口，通过 /hz/history/ma 等端点获取指数技术指标。

        URL 格式（已修复）：/hz/history/ma/{index_code}/d
        - 注意：此接口仅适用于标准指数代码（如 000300.SH），不适用于股票代码

        Args:
            stock_code: 标准指数代码（如 "000300.SH"），不接受股票代码
            days: 天数

        Returns:
            带技术指标的 DataFrame
        """
        from datetime import timedelta

        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')

        # 不再经过 _convert_stock_code，直接使用传入的代码
        # 因为 /hz/history/ma/{code}/d 接口只接受标准指数代码（如 000300.SH）
        index_code = stock_code.strip().upper()

        url = f"{ZHITU_HZ_BASE_URL}/history/ma/{index_code}/d"

        try:
            data = self._get(url, params={'st': start_date, 'et': end_date}, timeout=30)

            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)

                # 重命名列
                df = df.rename(columns={
                    't': 'date',
                })

                # 转换日期
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'], format='mixed', errors='coerce')

                # 数值转换（MA 指标列）
                ma_cols = ['ma3', 'ma5', 'ma10', 'ma15', 'ma20', 'ma30',
                           'ma60', 'ma120', 'ma200', 'ma250']
                for col in df.columns:
                    if col != 'date':
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                # 按日期排序
                df = df.sort_values('date')

                return df

        except Exception as e:
            logger.debug(f"[Zhitu] get_daily_data_with_indicators({stock_code}) 失败: {e}")

        return None

    # =========================================================================
    # 市场统计与板块排行
    # =========================================================================

    def get_market_stats(self) -> Optional[Dict[str, Any]]:
        """
        获取市场涨跌统计

        数据来源：
        - 涨停股池 (/hs/pool/ztgc/{date})
        - 跌停股池 (/hs/pool/dtgc/{date})

        注意：智图 API 不提供直接的涨跌家数和成交额数据，
        故 up_count/down_count/flat_count/total_amount 返回 None。

        Returns:
            Dict: 包含:
                - up_count: 上涨家数 (None，不可得)
                - down_count: 下跌家数 (None，不可得)
                - flat_count: 平盘家数 (None，不可得)
                - limit_up_count: 涨停家数
                - limit_down_count: 跌停家数
                - total_amount: 两市成交额 (None，不可得)
        """
        today = datetime.now().strftime('%Y-%m-%d')

        limit_up_count = 0
        limit_down_count = 0

        # 获取涨停股池
        try:
            url = f"{ZHITU_HS_BASE_URL}/pool/ztgc/{today}"
            data = self._get(url, timeout=15)
            if isinstance(data, list):
                limit_up_count = len(data)
            elif isinstance(data, dict) and 'data' in data:
                limit_up_count = len(data['data'])
        except Exception as e:
            logger.debug(f"[Zhitu] get_market_stats: 涨停股池失败: {e}")

        # 获取跌停股池
        try:
            url = f"{ZHITU_HS_BASE_URL}/pool/dtgc/{today}"
            data = self._get(url, timeout=15)
            if isinstance(data, list):
                limit_down_count = len(data)
            elif isinstance(data, dict) and 'data' in data:
                limit_down_count = len(data['data'])
        except Exception as e:
            logger.debug(f"[Zhitu] get_market_stats: 跌停股池失败: {e}")

        return {
            "up_count": None,
            "down_count": None,
            "flat_count": None,
            "limit_up_count": limit_up_count,
            "limit_down_count": limit_down_count,
            "total_amount": None,
        }

    def get_sector_rankings(self, n: int = 5) -> Optional[Tuple[List[Dict], List[Dict]]]:
        """
        获取板块涨跌榜

        智图 API 不提供板块指数的实时行情数据（/hz/real/ssjy/{code} 对板块代码返回 404），
        因此无法通过智图实现板块排行，返回 None 触发 fallback 到其他数据源。

        Args:
            n: 返回前n个

        Returns:
            None - 智图不支持此接口
        """
        logger.debug("[Zhitu] get_sector_rankings: 智图 API 不支持板块指数实时行情，返回 None")
        return None
