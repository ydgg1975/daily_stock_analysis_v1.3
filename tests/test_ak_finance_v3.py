import akshare as ak
import pandas as pd

try:
    df = ak.stock_financial_abstract(symbol="600519")
    if df is not None and not df.empty:
        print("Success abstract!")
        print(df['指标'].unique())
        print(df.head(20))
except Exception as e:
    print(f"Error abstract: {e}")
