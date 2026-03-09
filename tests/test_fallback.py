import logging
import sys
import os
import pandas as pd
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from data_provider.base import DataFetcherManager
from data_provider.akshare_fetcher import AkshareFetcher
from data_provider.efinance_fetcher import EfinanceFetcher
from data_provider.tushare_fetcher import TushareFetcher
from data_provider.baostock_fetcher import BaostockFetcher

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_fallback_mechanism():
    """测试数据源回退机制"""
    print("="*50)
    print("测试数据源回退机制 (Fallback Mechanism)")
    print("="*50)
    
    # 1. 初始化 Manager
    manager = DataFetcherManager()
    
    # 2. 模拟各个 Fetcher 的 get_financial_indicators 方法
    # 我们希望模拟：
    # Akshare (Priority 1) -> 失败
    # Efinance (Priority 0) -> 失败
    # Tushare (Priority 2) -> 失败
    # Baostock (Priority 3) -> 成功
    
    stock_code = "600519"
    
    # Mock AkshareFetcher
    with patch.object(AkshareFetcher, 'get_financial_indicators', side_effect=Exception("Akshare API Error")):
        # Mock EfinanceFetcher
        with patch.object(EfinanceFetcher, 'get_financial_indicators', side_effect=Exception("Efinance API Error")):
             # Mock TushareFetcher
            with patch.object(TushareFetcher, 'get_financial_indicators', side_effect=Exception("Tushare API Error")):
                # Mock BaostockFetcher - 让它成功
                expected_df = pd.DataFrame([{
                    '净资产收益率': 20.5,
                    '销售毛利率': 92.1,
                    '净利润增长率': 15.6,
                    '资产负债率': 18.2,
                    'end_date': '2023-Q4'
                }])
                with patch.object(BaostockFetcher, 'get_financial_indicators', return_value=expected_df):
                    
                    print(f"尝试获取 {stock_code} 的财务指标...")
                    print("预期行为: Efinance(失败) -> Akshare(失败) -> Tushare(失败) -> Baostock(成功)")
                    
                    # 调用 Manager 的 get_financial_indicators
                    # 注意：Manager 内部会遍历所有注册的 fetchers
                    # 我们需要确保 manager 使用的是我们 patch 过的 fetcher 实例
                    # 由于 manager 在 __init__ 中实例化了 fetchers，我们上面的 patch.object 可能对已经实例化的对象无效
                    # 除非我们 patch 类方法本身，或者重新实例化 manager
                    
                    # 重新实例化 manager 以使用 patched classes (如果 patch 是在类级别)
                    # 但 patch.object 是针对类的，会影响新实例
                    
                    # 强制重新加载 fetchers
                    manager = DataFetcherManager()
                    
                    result = manager.get_financial_indicators(stock_code)
                    
                    if result is not None and not result.empty:
                        print("✅ 测试成功: 成功通过回退机制获取到数据")
                        print("返回数据:")
                        print(result)
                        
                        # 验证数据来源 (通过日志或返回值的特征)
                        if result.iloc[0]['end_date'] == '2023-Q4':
                            print("确认数据来自 Mock 的 Baostock")
                    else:
                        print("❌ 测试失败: 未获取到数据")

def test_real_fallback_chain():
    """
    测试真实环境下的回退链 (非 Mock)
    警告: 这会产生真实的 API 请求
    """
    print("\n" + "="*50)
    print("测试真实环境回退链 (Real Environment)")
    print("="*50)
    
    manager = DataFetcherManager()
    code = "600519"
    
    # 尝试获取财务指标
    # 由于 Efinance, Akshare, Tushare, Baostock 都实现了 get_financial_indicators
    # Manager 会按照优先级顺序尝试
    
    print(f"正在尝试从真实数据源获取 {code} 财务指标...")
    df = manager.get_financial_indicators(code)
    
    if df is not None:
        print(f"✅ 获取成功! 数据来源取决于优先级配置和网络状况")
        print(df.head())
    else:
        print("❌ 所有数据源均失败")

if __name__ == "__main__":
    test_fallback_mechanism()
    # test_real_fallback_chain() # 取消注释以运行真实测试
