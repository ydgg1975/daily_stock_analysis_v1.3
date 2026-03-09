import sys
import os
import logging
from datetime import date, timedelta
import pandas as pd
from dataclasses import dataclass

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core.backtest_engine import BacktestEngine, EvaluationConfig, DailyBarLike, BacktestResultLike

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class MockBar:
    date: date
    open: float
    high: float
    low: float
    close: float

@dataclass
class MockResult:
    eval_status: str
    position_recommendation: str = None
    outcome: str = None
    direction_correct: bool = None
    stock_return_pct: float = None
    simulated_return_pct: float = None
    hit_stop_loss: bool = None
    hit_take_profit: bool = None
    first_hit: str = None
    first_hit_trading_days: int = None
    operation_advice: str = None

def test_backtest_engine():
    """测试回测引擎核心逻辑"""
    print("="*50)
    print("测试回测引擎 (Backtest Engine)")
    print("="*50)
    
    # 1. 准备测试数据
    start_price = 100.0
    analysis_date = date(2023, 1, 1)
    
    # 构造未来 5 天的行情
    # 情况 1: 上涨，未触发止盈止损
    forward_bars_up = [
        MockBar(date(2023, 1, 2), 100, 102, 99, 101),
        MockBar(date(2023, 1, 3), 101, 103, 100, 102),
        MockBar(date(2023, 1, 4), 102, 104, 101, 103),
        MockBar(date(2023, 1, 5), 103, 105, 102, 104),
        MockBar(date(2023, 1, 6), 104, 106, 103, 105), # Close 105 (+5%)
    ]
    
    # 情况 2: 下跌，触发止损
    forward_bars_down = [
        MockBar(date(2023, 1, 2), 100, 101, 98, 99),
        MockBar(date(2023, 1, 3), 99, 100, 95, 96), # Low 95, 触发止损 95
        MockBar(date(2023, 1, 4), 96, 97, 94, 95),
    ]
    
    config = EvaluationConfig(eval_window_days=5)
    
    # 2. 测试 "买入" 建议 + 上涨行情
    print("\n测试用例 1: 建议买入 + 实际上涨")
    res1 = BacktestEngine.evaluate_single(
        operation_advice="建议买入",
        analysis_date=analysis_date,
        start_price=start_price,
        forward_bars=forward_bars_up,
        stop_loss=95.0,
        take_profit=110.0,
        config=config
    )
    print(f"方向预测: {res1['direction_expected']} (预期 up)")
    print(f"实际结果: {res1['outcome']} (预期 win)")
    print(f"模拟收益: {res1['simulated_return_pct']}% (预期 5.0%)")
    
    if res1['outcome'] == 'win' and res1['simulated_return_pct'] == 5.0:
        print("✅ 通过")
    else:
        print("❌ 失败")
        
    # 3. 测试 "买入" 建议 + 下跌行情 (触发止损)
    print("\n测试用例 2: 建议买入 + 实际下跌 (触发止损)")
    res2 = BacktestEngine.evaluate_single(
        operation_advice="建议买入",
        analysis_date=analysis_date,
        start_price=start_price,
        forward_bars=forward_bars_down,
        stop_loss=95.0,
        take_profit=110.0,
        config=config
    )
    print(f"方向预测: {res2['direction_expected']} (预期 up)")
    print(f"实际结果: {res2['outcome']} (预期 loss)")
    print(f"止损触发: {res2['hit_stop_loss']} (预期 True)")
    print(f"模拟收益: {res2['simulated_return_pct']}% (预期 -5.0%)")
    
    if res2['outcome'] == 'loss' and res2['hit_stop_loss'] and res2['simulated_return_pct'] == -5.0:
        print("✅ 通过")
    else:
        print("❌ 失败")

    # 4. 测试汇总统计
    print("\n测试用例 3: 汇总统计计算")
    # 构造一组结果
    results = [
        MockResult(eval_status="completed", position_recommendation="long", outcome="win", direction_correct=True, stock_return_pct=5.0, simulated_return_pct=5.0, operation_advice="买入"),
        MockResult(eval_status="completed", position_recommendation="long", outcome="loss", direction_correct=False, stock_return_pct=-5.0, simulated_return_pct=-5.0, operation_advice="买入"), # 假设止损
        MockResult(eval_status="completed", position_recommendation="cash", outcome="win", direction_correct=True, stock_return_pct=-2.0, simulated_return_pct=0.0, operation_advice="卖出"), # 卖出正确
        MockResult(eval_status="completed", position_recommendation="long", outcome="win", direction_correct=True, stock_return_pct=10.0, simulated_return_pct=10.0, operation_advice="买入"),
    ]
    
    summary = BacktestEngine.compute_summary(
        results=results,
        scope="test",
        code="TEST",
        eval_window_days=5,
        engine_version="v1"
    )
    
    print(f"总数: {summary['total_evaluations']}")
    print(f"方向准确率: {summary['direction_accuracy_pct']}% (预期 75.0%)") # 3/4
    print(f"胜率: {summary['win_rate_pct']}% (预期 75.0%)") # 3/4 (win/total)
    
    if summary['direction_accuracy_pct'] == 75.0 and summary['win_rate_pct'] == 75.0:
        print("✅ 通过")
    else:
        print("❌ 失败")

if __name__ == "__main__":
    test_backtest_engine()
