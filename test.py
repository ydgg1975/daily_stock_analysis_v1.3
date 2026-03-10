from data_provider.akshare_fetcher import AkshareFetcher
from data_provider.baostock_fetcher import BaostockFetcher
from data_provider.efinance_fetcher import EfinanceFetcher
from data_provider.tushare_fetcher import TushareFetcher
from data_provider.pytdx_fetcher import PytdxFetcher
from data_provider.yfinance_fetcher import YfinanceFetcher
import logging

logging.basicConfig(level=logging.DEBUG)

# 优先级
# 0. EfinanceFetcher
# 1. AkshareFetcher
# 2. TushareFetcher
# 3. PytdxFetcher
# 4. BaostockFetcher
# 5. YfinanceFetcher
fetcher = YfinanceFetcher()
df = fetcher.get_company_info('600519')  # 茅台
print(df)