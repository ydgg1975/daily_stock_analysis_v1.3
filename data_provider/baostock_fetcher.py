# -*- coding: utf-8 -*-
"""
===================================
BaostockFetcher - 备用数据源 2 (Priority 3)
===================================

数据来源：证券宝（Baostock）
特点：免费、无需 Token、需要登录管理
优点：稳定、无配额限制

关键策略：
1. 管理 bs.login() 和 bs.logout() 生命周期
2. 使用上下文管理器防止连接泄露
3. 失败后指数退避重试
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

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS
import os

logger = logging.getLogger(__name__)


def _is_us_code(stock_code: str) -> bool:
    """
    判断代码是否为美股
    
    美股代码规则：
    - 1-5个大写字母，如 'AAPL', 'TSLA'
    - 可能包含 '.'，如 'BRK.B'
    """
    code = stock_code.strip().upper()
    return bool(re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', code))


class BaostockFetcher(BaseFetcher):
    """
    Baostock 数据源实现
    
    优先级：3
    数据来源：证券宝 Baostock API
    
    关键策略：
    - 使用上下文管理器管理连接生命周期
    - 每次请求都重新登录/登出，防止连接泄露
    - 失败后指数退避重试
    
    Baostock 特点：
    - 免费、无需注册
    - 需要显式登录/登出
    - 数据更新略有延迟（T+1）
    """
    
    name = "BaostockFetcher"
    priority = int(os.getenv("BAOSTOCK_PRIORITY", "3"))
    
    def __init__(self):
        """初始化 BaostockFetcher"""
        self._bs_module = None
    
    def _get_baostock(self):
        """
        延迟加载 baostock 模块
        
        只在首次使用时导入，避免未安装时报错
        """
        if self._bs_module is None:
            import baostock as bs
            self._bs_module = bs
        return self._bs_module
    
    @contextmanager
    def _baostock_session(self) -> Generator:
        """
        Baostock 连接上下文管理器
        
        确保：
        1. 进入上下文时自动登录
        2. 退出上下文时自动登出
        3. 异常时也能正确登出
        
        使用示例：
            with self._baostock_session():
                # 在这里执行数据查询
        """
        bs = self._get_baostock()
        login_result = None
        
        try:
            # 登录 Baostock
            login_result = bs.login()
            
            if login_result.error_code != '0':
                raise DataFetchError(f"Baostock 登录失败: {login_result.error_msg}")
            
            logger.debug("Baostock 登录成功")
            
            yield bs
            
        finally:
            # 确保登出，防止连接泄露
            try:
                logout_result = bs.logout()
                if logout_result.error_code == '0':
                    logger.debug("Baostock 登出成功")
                else:
                    logger.warning(f"Baostock 登出异常: {logout_result.error_msg}")
            except Exception as e:
                logger.warning(f"Baostock 登出时发生错误: {e}")
    
    def _convert_stock_code(self, stock_code: str) -> str:
        """
        转换股票代码为 Baostock 格式
        
        Baostock 要求的格式：
        - 沪市：sh.600519
        - 深市：sz.000001
        
        Args:
            stock_code: 原始代码，如 '600519', '000001'
            
        Returns:
            Baostock 格式代码，如 'sh.600519', 'sz.000001'
        """
        code = stock_code.strip()
        
        # 已经包含前缀的情况
        if code.startswith(('sh.', 'sz.')):
            return code.lower()
        
        # 去除可能的后缀
        code = code.replace('.SH', '').replace('.SZ', '').replace('.sh', '').replace('.sz', '')
        
        # ETF: Shanghai ETF (51xx, 52xx, 56xx, 58xx) -> sh; Shenzhen ETF (15xx, 16xx, 18xx) -> sz
        if len(code) == 6:
            if code.startswith(('51', '52', '56', '58')):
                return f"sh.{code}"
            if code.startswith(('15', '16', '18')):
                return f"sz.{code}"

        # 根据代码前缀判断市场
        if code.startswith(('600', '601', '603', '688')):
            return f"sh.{code}"
        elif code.startswith(('000', '002', '300')):
            return f"sz.{code}"
        else:
            logger.warning(f"无法确定股票 {code} 的市场，默认使用深市")
            return f"sz.{code}"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        从 Baostock 获取原始数据
        
        使用 query_history_k_data_plus() 获取日线数据
        
        流程：
        1. 检查是否为美股（不支持）
        2. 使用上下文管理器管理连接
        3. 转换股票代码格式
        4. 调用 API 查询数据
        5. 将结果转换为 DataFrame
        """
        # 美股不支持，抛出异常让 DataFetcherManager 切换到其他数据源
        if _is_us_code(stock_code):
            raise DataFetchError(f"BaostockFetcher 不支持美股 {stock_code}，请使用 AkshareFetcher 或 YfinanceFetcher")
        
        # 转换代码格式
        bs_code = self._convert_stock_code(stock_code)
        
        logger.debug(f"调用 Baostock query_history_k_data_plus({bs_code}, {start_date}, {end_date})")
        
        with self._baostock_session() as bs:
            try:
                # 查询日线数据
                # adjustflag: 1-后复权，2-前复权，3-不复权
                rs = bs.query_history_k_data_plus(
                    code=bs_code,
                    fields="date,open,high,low,close,volume,amount,pctChg",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",  # 日线
                    adjustflag="2"  # 前复权
                )
                
                if rs.error_code != '0':
                    raise DataFetchError(f"Baostock 查询失败: {rs.error_msg}")
                
                # 转换为 DataFrame
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                
                if not data_list:
                    raise DataFetchError(f"Baostock 未查询到 {stock_code} 的数据")
                
                df = pd.DataFrame(data_list, columns=rs.fields)
                
                return df
                
            except Exception as e:
                if isinstance(e, DataFetchError):
                    raise
                raise DataFetchError(f"Baostock 获取数据失败: {e}") from e
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化 Baostock 数据
        
        Baostock 返回的列名：
        date, open, high, low, close, volume, amount, pctChg
        
        需要映射到标准列名：
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()
        
        # 列名映射（只需要处理 pctChg）
        column_mapping = {
            'pctChg': 'pct_chg',
        }
        
        df = df.rename(columns=column_mapping)
        
        # 数值类型转换（Baostock 返回的都是字符串）
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 添加股票代码列
        df['code'] = stock_code
        
        # 只保留需要的列
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]
        
        return df

    def get_financial_indicators(self, stock_code: str) -> Optional[pd.DataFrame]:
        """
        获取股票历史财务指标
        
        Args:
            stock_code: 股票代码
            
        Returns:
            包含历史财务指标的 DataFrame，失败返回 None
        """
        # 美股不支持
        if _is_us_code(stock_code):
            return None
            
        try:
            bs_code = self._convert_stock_code(stock_code)
            
            with self._baostock_session() as bs:
                # Baostock 提供了 query_profit_data (盈利能力), query_operation_data (营运能力), 
                # query_growth_data (成长能力), query_balance_data (偿债能力)
                
                # 我们需要获取最近一期的数据
                # 获取年份和季度
                now = datetime.now()
                year = now.year
                quarter = (now.month - 1) // 3 + 1
                
                # 如果是第一季度，可能数据还没出，往前推一季度
                if quarter == 1:
                    year -= 1
                    quarter = 4
                else:
                    quarter -= 1
                
                # 获取盈利能力 (ROE, 毛利率, 净利率)
                profit_rs = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
                
                # 获取成长能力 (净利润增长率)
                growth_rs = bs.query_growth_data(code=bs_code, year=year, quarter=quarter)
                
                # 获取偿债能力 (资产负债率)
                balance_rs = bs.query_balance_data(code=bs_code, year=year, quarter=quarter)
                
                # 合并数据
                data = {}
                
                if profit_rs.error_code == '0':
                    while profit_rs.next():
                        # get_row_data() 返回列表，需要根据 fields 映射
                        row = profit_rs.get_row_data()
                        # fields: code, pubDate, statDate, roeAvg, npMargin, gpMargin...
                        # roeAvg: 净资产收益率(平均)
                        # gpMargin: 销售毛利率
                        fields = profit_rs.fields
                        data['净资产收益率'] = float(row[fields.index('roeAvg')]) * 100 if row[fields.index('roeAvg')] else 0
                        data['销售毛利率'] = float(row[fields.index('gpMargin')]) * 100 if row[fields.index('gpMargin')] else 0
                
                if growth_rs.error_code == '0':
                    while growth_rs.next():
                        row = growth_rs.get_row_data()
                        # YOYNI: 净利润同比增长率
                        fields = growth_rs.fields
                        data['净利润增长率'] = float(row[fields.index('YOYNI')]) * 100 if row[fields.index('YOYNI')] else 0

                if balance_rs.error_code == '0':
                    while balance_rs.next():
                        row = balance_rs.get_row_data()
                        # assetLiabilityRatio: 资产负债率
                        fields = balance_rs.fields
                        data['资产负债率'] = float(row[fields.index('assetLiabilityRatio')]) * 100 if row[fields.index('assetLiabilityRatio')] else 0
                
                if not data:
                    return None
                    
                # 构造 DataFrame
                df = pd.DataFrame([data])
                df['end_date'] = f"{year}-Q{quarter}"
                
                logger.info(f"[Baostock] 成功获取 {stock_code} 财务指标")
                return df
                
        except Exception as e:
            logger.warning(f"Baostock 获取财务指标失败 {stock_code}: {e}")
            return None

    def get_chip_distribution(self, stock_code: str):
        """
        获取筹码分布数据（Baostock 不支持）
        """
        return None

    def get_stock_name(self, stock_code: str) -> Optional[str]:
        """
        获取股票名称
        
        使用 Baostock 的 query_stock_basic 接口获取股票基本信息
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票名称，失败返回 None
        """
        # 检查缓存
        if hasattr(self, '_stock_name_cache') and stock_code in self._stock_name_cache:
            return self._stock_name_cache[stock_code]
        
        # 初始化缓存
        if not hasattr(self, '_stock_name_cache'):
            self._stock_name_cache = {}
        
        try:
            bs_code = self._convert_stock_code(stock_code)
            
            with self._baostock_session() as bs:
                # 查询股票基本信息
                rs = bs.query_stock_basic(code=bs_code)
                
                if rs.error_code == '0':
                    data_list = []
                    while rs.next():
                        data_list.append(rs.get_row_data())
                    
                    if data_list:
                        # Baostock 返回的字段：code, code_name, ipoDate, outDate, type, status
                        fields = rs.fields
                        name_idx = fields.index('code_name') if 'code_name' in fields else None
                        if name_idx is not None and len(data_list[0]) > name_idx:
                            name = data_list[0][name_idx]
                            self._stock_name_cache[stock_code] = name
                            logger.debug(f"Baostock 获取股票名称成功: {stock_code} -> {name}")
                            return name
                
        except Exception as e:
            logger.warning(f"Baostock 获取股票名称失败 {stock_code}: {e}")
        
        return None
    
    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """
        获取股票列表
        
        使用 Baostock 的 query_stock_basic 接口获取全部股票列表
        
        Returns:
            包含 code, name 列的 DataFrame，失败返回 None
        """
        try:
            with self._baostock_session() as bs:
                # 查询所有股票基本信息
                rs = bs.query_stock_basic()
                
                if rs.error_code == '0':
                    data_list = []
                    while rs.next():
                        data_list.append(rs.get_row_data())
                    
                    if data_list:
                        df = pd.DataFrame(data_list, columns=rs.fields)
                        
                        # 转换代码格式（去除 sh. 或 sz. 前缀）
                        df['code'] = df['code'].apply(lambda x: x.split('.')[1] if '.' in x else x)
                        df = df.rename(columns={'code_name': 'name'})
                        
                        # 更新缓存
                        if not hasattr(self, '_stock_name_cache'):
                            self._stock_name_cache = {}
                        for _, row in df.iterrows():
                            self._stock_name_cache[row['code']] = row['name']
                        
                        logger.info(f"Baostock 获取股票列表成功: {len(df)} 条")
                        return df[['code', 'name']]
                
        except Exception as e:
            logger.warning(f"Baostock 获取股票列表失败: {e}")
        
        return None


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    fetcher = BaostockFetcher()
    
    try:
        # 测试历史数据
        df = fetcher.get_daily_data('600519')  # 茅台
        print(f"获取成功，共 {len(df)} 条数据")
        print(df.tail())
        
        # 测试股票名称
        name = fetcher.get_stock_name('600519')
        print(f"股票名称: {name}")
        
    except Exception as e:
        print(f"获取失败: {e}")
