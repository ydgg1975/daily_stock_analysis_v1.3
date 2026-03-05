"""
BOZI V7.5 集成示例

展示如何在 stock_analyzer 中集成 BOZI V7.5 核心技术指标

版本：1.0.0
"""

from typing import Optional
import pandas as pd

try:
    from core.bozi_v75_indicators import BoziV75Indicators, calculate_all_indicators
    from core import __bozi_indicators  # noqa: F401
except ImportError:
    # 如果在非包模式下运行
    import sys
    import os
    
    # 添加 src 到 Python 路径
    src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    from bozi_v75_indicators import BoziV75Indicators, calculate_all_indicators
    from bozi_indicators import __all__ as __bozi_indicators


def enhance_stock_analyzer_with_bozi(df: pd.DataFrame) -> pd.DataFrame:
    """
    在现有股票数据上添加 BOZI V7.5 技术指标
    
    Args:
        df: 包含 OHLCV 数据的 DataFrame
    
    Returns:
        添加 BOZI V7.5 指标的 DataFrame
    """
    # 使用 BOZI V7.5 指标计算
    df_enhanced = calculate_all_indicators(df)
    
    return df_enhanced


def generate_bozi_signal_summary(df: pd.DataFrame) -> dict:
    """
    生成 BOZI V7.5 信号摘要
    
    Args:
        df: 包含所有指标的 DataFrame
    
    Returns:
        信号摘要字典
    """
    if 'MA多头排列' not in df.columns:
        return {'error': '数据不包含必需的指标，请先运行 enhance_stock_analyzer_with_bozi()'}
    
    latest = df.iloc[-1]
    
    # 生成操作建议
    operation = '观望'
    reasons = []
    
    if latest['共振选股']:
        operation = '买入'
        reasons.append('5维共振选股条件满足')
    elif latest['MA多头排列'] and latest['BBI趋势向上'] and not latest['V5风险']:
        operation = '加仓'
        reasons.append('均线多头排列 + BBI 趋势向上 + 乖离率安全')
    elif latest['V7风险'] or (latest['V5风险'] and latest['超跌分界线']):
        operation = '减仓/清仓'
        reasons.append(f"触及 V7 风险线 ({latest['BIAS20']:.2f}%)")
    elif latest['多头回踩支撑']:
        operation = '观望/加仓'
        reasons.append('多头回踩支撑位，可能是低点')
    
    summary = {
        '操作建议': operation,
        '理由': ' | '.join(reasons),
        '技术面评分': {
            '均线系统': 85 if latest['MA多头排列'] else 60,
            'BBI趋势': 80 if latest['BBI趋势向上'] else 50,
            '量能状态': 75 if latest['机构起航'] else 50,
            '乖离率': 80 if not latest['V5风险'] else 40,
        },
        '风控提示': {
            '乖离率': latest['BIAS20'] if 'BIAS20' in df.columns else None,
            'V5风险': latest['V5风险'] if 'V5风险' in df.columns else False,
            'V7风险': latest['V7风险'] if 'V7风险' in df.columns else False,
            '建议仓位': '全仓' if latest['共振选股'] else '半仓' if operation == '加仓' else '轻仓',
        },
        '选股信号': {
            '共振选股': latest['共振选股'] if '共振选股' in df.columns else False,
            '共振强度': latest['共振强度'] if '共振强度' in df.columns else 0,
            'MA收敛度': latest['MA收敛度'] if 'MA收敛度' in df.columns else 0,
        },
    }
    
    return summary


def format_bozi_signal_message(summary: dict) -> str:
    """
    格式化 BOZI V7.5 信号消息
    
    Args:
        summary: 信号摘要字典
    
    Returns:
        格式化的消息字符串
    """
    lines = []
    
    # 标题
    lines.append("=" * 60)
    lines.append("📊 BOZI V7.5 技术信号")
    lines.append("=" * 60)
    
    # 操作建议
    lines.append(f"\n【操作建议】{summary['操作建议']}")
    for reason in summary['理由'].split(' | '):
        lines.append(f"  • {reason}")
    
    # 技术面评分
    scores = summary['技术面评分']
    lines.append(f"\n【技术面评分】")
    lines.append(f"  均线系统: {scores['均线系统']} (多头排列: {bool(scores['均线系统'] == 85)})")
    lines.append(f"  BBI 趋势: {scores['BBI趋势']} (趋势向上: {bool(scores['BBI趋势'] == 80)})")
    lines.append(f"  量能状态: {scores['量能状态']} (机构起航: {bool(scores['量能状态'] == 75)})")
    lines.append(f"  乖离率: {scores['乖离率']} (V5 安全: {bool(scores['乖离率'] == 80)})")
    
    # 风控提示
    risk = summary['风控提示']
    lines.append(f"\n【风控提示】")
    if risk['乖离率']:
        lines.append(f"  BIAS20: {risk['乖离率']:.2f}%")
    lines.append(f"  V5 风险: {'🔴 极致' if risk['V5风险'] else '🟢 安全'}")
    lines.append(f"  V7 风险: {'🔴 极高' if risk['V7风险'] else '🟢 安全'}")
    lines.append(f"  建议仓位: {risk['建议仓位']}")
    
    # 选股信号
    selection = summary['选股信号']
    lines.append(f"\n【选股信号】")
    lines.append(f"  共振选股: {'✅ 高确定性' if selection['共振选股'] else '⚠️ 不满足'}")
    if selection['共振选股']:
        lines.append(f"  共振强度: {selection['共振强度']:.0f}")
        lines.append(f"  MA 收敛度: {selection['MA收敛度']:.2f}%")
    
    # 风险区间
    lines.append(f"\n【风险区间】")
    if risk['多头回踩支撑']:
        lines.append(f"  • 回踩支撑: {risk['多头回踩支撑']}")
    if risk['超跌分界线']:
        lines.append(f"  • 超跌分界: {risk['超跌分界线']}")
    
    lines.append("\n" + "=" * 60)
    
    return "\n".join(lines)


def test_bozi_integration():
    """测试 BOZI V7.5 集成"""
    import numpy as np
    
    print("测试 BOZI V7.5 集成...")
    print("=" * 60)
    
    # 生成示例数据
    np.random.seed(42)
    dates = pd.date_range(start='2025-01-01', periods=250)
    
    # 价格数据（上升趋势）
    trend = np.linspace(10, 15, 250)
    noise = np.random.normal(0, 0.3, 250)
    close = trend + noise
    
    # OHLCV
    opens = close + np.random.normal(0, 0.2, 250)
    highs = np.maximum(opens, close)
    lows = np.minimum(opens, close)
    volumes = np.random.randint(1000000, 5000000, 250)
    
    df = pd.DataFrame({
        'date': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': close,
        'volume': volumes,
    })
    
    # 增强数据
    print("\n增强股票数据...")
    df_enhanced = enhance_stock_analyzer_with_bozi(df)
    
    # 生成信号摘要
    print("生成 BOZI V7.5 信号摘要...")
    summary = generate_bozi_signal_summary(df_enhanced)
    
    # 格式化消息
    print("\n格式化信号消息...")
    message = format_bozi_signal_message(summary)
    
    print(message)
    
    print("\n✅ 测试完成！")
    print("=" * 60)


if __name__ == '__main__':
    test_bozi_integration()
