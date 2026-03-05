"""
BOZI V7.5 核心技术指标模块

基于 BOZI V7.5 专业技术手册的指标实现
包含：4周期均线系统、BBI 复合趋势线、换手率机构量、乖离率双重监测

作者：OpenClaw 集成
版本：1.0.0
集成到：clover4495/daily_stock_analysis
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional


class BoziV75Indicators:
    """BOZI V7.5 技术指标计算器"""
    
    @staticmethod
    def calculate_ma_system(df: pd.DataFrame, prices: str = 'close') -> pd.DataFrame:
        """
        计算4周期均线系统
        
        Args:
            df: 包含 OHLCV 数据的 DataFrame
            prices: 价格列名，默认 'close'
        
        Returns:
            添加均线列的 DataFrame
        """
        if prices not in df.columns:
            return df
        
        close = df[prices]
        
        result = df.copy()
        result['MA7'] = close.rolling(window=7).mean()
        result['MA20'] = close.rolling(window=20).mean()
        result['MA60'] = close.rolling(window=60).mean()
        result['MA120'] = close.rolling(window=120).mean()
        
        # 均线多头排列状态
        ma_up = (
            (result['MA7'] > result['MA20']) & 
            (result['MA20'] > result['MA60']) & 
            (result['MA60'] > result['MA120'])
        )
        result['MA多头排列'] = ma_up
        
        # 均线收敛度（用于选股）
        max_ma = result[['MA7', 'MA20', 'MA60', 'MA120']].max(axis=1)
        min_ma = result[['MA7', 'MA20', 'MA60', 'MA120']].min(axis=1)
        result['MA收敛度'] = (max_ma - min_ma) / min_ma * 100
        
        return result
    
    @staticmethod
    def calculate_bbi_trend(df: pd.DataFrame, prices: str = 'close') -> pd.DataFrame:
        """
        计算 BBI 复合趋势线
        
        BBI = (MA7 + MA20 + MA60 + MA120) / 4
        """
        if prices not in df.columns:
            return df
        
        if 'MA7' not in df.columns:
            df = BoziV75Indicators.calculate_ma_system(df, prices)
        
        result = df.copy()
        
        # BBI 计算
        result['BBI'] = (
            result['MA7'] + result['MA20'] + 
            result['MA60'] + result['MA120']
        ) / 4
        
        # BBI 趋势状态
        result['BBI多头排列'] = (
            (result['MA7'] > result['MA20']) &
            (result['MA20'] > result['MA60']) &
            (result['MA60'] > result['MA120'])
        )
        
        # BBI 趋势向上
        result['BBI趋势向上'] = result['BBI'] > result['BBI'].shift(1)
        
        return result
    
    @staticmethod
    def calculate_turnover_signals(df: pd.DataFrame, volume: str = 'volume', capital: str = 'capital') -> pd.DataFrame:
        """
        计算基于换手率的机构量能识别
        
        Args:
            df: 包含 OHLCV 的 DataFrame
            volume: 成交量列名
            capital: 市值列名
        
        Returns:
            添加量能信号的 DataFrame
        """
        if volume not in df.columns:
            return df
        
        # 估算 capital 如果不存在
        if capital not in df.columns:
            df['capital'] = df['close'] * df['volume'] * 0.1  # 估算流通市值
        
        result = df.copy()
        
        # 换手率计算
        result['换手率'] = df[volume] / df['capital'] * 100
        
        # 机构倍量（放量：> 1.5 倍前量）
        result['机构倍数'] = df[volume] / df[volume].shift(1)
        
        # 机构起航信号（放量 + 换手率 > 2.5%）
        result['机构起航'] = (
            (result['机构倍数'] > 1.5) &
            (result['换手率'] > 2.5) &
            (result['close'] > result['close'].shift(1))
        )
        
        # 冰点地量（缩量：< 0.5 倍前量）
        result['冰点地量'] = result['机构倍数'] < 0.5
        
        return result
    
    @staticmethod
    def calculate_bias_monitor(df: pd.DataFrame, prices: str = 'close') -> pd.DataFrame:
        """
        计算乖离率双重监测（V5 + V7 双阈值）
        
        Args:
            df: 包含 OHLCV 的 DataFrame
            prices: 价格列名
        
        Returns:
            添加乖离率信号的 DataFrame
        """
        if prices not in df.columns:
            return df
        
        if 'MA20' not in df.columns:
            df = BoziV75Indicators.calculate_ma_system(df, prices)
        
        result = df.copy()
        
        # 乖离率计算
        result['BIAS20'] = (result['close'] - result['MA20']) / result['MA20'] * 100
        
        # BIAS 平滑均线（10日）
        result['BIAS平滑'] = result['BIAS20'].rolling(window=10).mean()
        
        # 乖离率动能
        result['BIAS动能'] = result['BIAS20'] > result['BIAS平滑'].shift(1)
        
        # 风险阈值定义
        V5_乖离阈值 = 10  # 极致风险区间
        V7_乖离阈值 = 12  # 风控线
        V5_压力阈值 = 10  # 核心压力红线
        SUPPORT_V7 = -2  # 多头回踩支撑
        EXTREME_LOW = -10  # 超跌分界线
        
        result['V5乖离阈值'] = V5_乖离阈值
        result['V7乖离阈值'] = V7_乖离阈值
        result['V5压力阈值'] = V5_压力阈值
        result['SUPPORT_V7'] = SUPPORT_V7
        result['EXTREME_LOW'] = EXTREME_LOW
        
        # 风险状态
        result['V5风险'] = abs(result['BIAS20']) >= V5_乖离阈值
        result['V7风险'] = abs(result['BIAS20']) >= V7_乖离阈值
        
        # 多头回踩支撑
        result['多头回踩支撑'] = result['BIAS20'] < SUPPORT_V7
        
        # 超跌分界线
        result['超跌分界线'] = result['BIAS20'] < EXTREME_LOW
        
        return result
    
    @staticmethod
    def calculate_resonance_selection(df: pd.DataFrame, prices: str = 'close', volume: str = 'volume', capital: str = 'capital') -> pd.DataFrame:
        """
        5维共振选股器
        
        Args:
            df: 包含 OHLCV 的 DataFrame
            prices: 价格列名
            volume: 成交量列名
            capital: 市值列名
        
        Returns:
            添加选股信号的 DataFrame
        """
        if prices not in df.columns or volume not in df.columns:
            return df
        
        # 先计算基础指标
        if 'MA7' not in df.columns:
            df = BoziV75Indicators.calculate_ma_system(df, prices)
        df = BoziV75Indicators.calculate_bbi_trend(df, prices)
        df = BoziV75Indicators.calculate_turnover_signals(df, volume, capital)
        df = BoziV75Indicators.calculate_bias_monitor(df, prices)
        
        result = df.copy()
        
        # 条件1：均线收敛度 < 3.5%
        cond_收敛 = result['MA收敛度'] < 3.5
        
        # 条件2：BBI 趋势抬头
        cond_bbi = result['BBI趋势向上']
        
        # 条件3：机构倍量 + 换手率过滤
        cond_量能 = (
            result['机构倍数'] > 1.6 &
            (2.5 < result['换手率']) & 
            (result['换手率'] < 12)
        )
        
        # 条件4：洗盘记忆（6日内缩量）
        cond_洗盘 = False
        for i in range(6, len(result)):
            if all(result['冰点地量'].iloc[i-6:i]):
                cond_洗盘 = True
                break
        
        # 条件5：乖离率动能回升
        cond_动能 = result['BIAS动能']
        
        # 综合选股条件
        result['共振选股'] = (
            cond_收敛 & cond_bbi & cond_量能 & cond_洗盘 & cond_动能 & 
            result['close'] > result['close'].shift(1)
        )
        
        # 满足条件数量统计（近20日）
        result['共振强度'] = result['共振选股'].rolling(window=20).sum()
        
        return result
    
    @staticmethod
    def generate_decision_summary(df: pd.DataFrame) -> Dict:
        """
        生成技术决策摘要
        
        Returns:
            包含各项技术状态的字典
        """
        if 'MA7' not in df.columns:
            return {}
        
        summary = {
            '均线系统': {
                'MA7': df['MA7'].iloc[-1],
                'MA20': df['MA20'].iloc[-1],
                'MA60': df['MA60'].iloc[-1],
                'MA120': df['MA120'].iloc[-1],
                '多头排列': df['MA多头排列'].iloc[-1],
            },
            'BBI趋势': {
                'BBI值': df['BBI'].iloc[-1],
                '趋势向上': df['BBI趋势向上'].iloc[-1],
            },
            '乖离率状态': {
                'BIAS20': df['BIAS20'].iloc[-1],
                'V5风险': df['V5风险'].iloc[-1],
                'V7风险': df['V7风险'].iloc[-1],
                '多头回踩': df['多头回踩支撑'].iloc[-1],
                '超跌分界': df['超跌分界线'].iloc[-1],
            },
            '量能状态': {
                '换手率': df['换手率'].iloc[-1],
                '机构倍数': df['机构倍数'].iloc[-1],
                '机构起航': df['机构起航'].iloc[-1],
                '冰点地量': df['冰点地量'].iloc[-1],
            },
            '选股信号': {
                '共振选股': df['共振选股'].iloc[-1],
                '共振强度': df['共振强度'].iloc[-1] if '共振强度' in df.columns else 0,
                'MA收敛度': df['MA收敛度'].iloc[-1],
            },
        }
        
        return summary


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    一键计算所有 BOZI V7.5 指标
    
    Args:
        df: 包含 OHLCV 数据的 DataFrame
    
    Returns:
        添加所有指标的 DataFrame
    """
    result = df.copy()
    
    # 1. 4周期均线系统
    result = BoziV75Indicators.calculate_ma_system(result)
    
    # 2. BBI 复合趋势线
    result = BoziV75Indicators.calculate_bbi_trend(result)
    
    # 3. 换手率机构量
    result = BoziV75Indicators.calculate_turnover_signals(result)
    
    # 4. 乖离率双重监测
    result = BoziV75Indicators.calculate_bias_monitor(result)
    
    # 5. 5维共振选股
    result = BoziV75Indicators.calculate_resonance_selection(result)
    
    return result


if __name__ == '__main__':
    # 测试代码
    import sys
    
    print("BOZI V7.5 核心技术指标模块已加载")
    print(f"Python 版本: {sys.version}")
    print(f"支持指标: MA7/20/60/120, BBI, 换手率, 乖离率双重监测, 5维共振选股")
    print(f"集成到: clover4495/daily_stock_analysis")
