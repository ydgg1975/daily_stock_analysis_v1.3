import akshare as ak
import pandas as pd

code = "600519"
print(f"Testing ak.stock_financial_analysis_indicator for {code}...")
try:
    df = ak.stock_financial_analysis_indicator(symbol=code)
    if df is not None and not df.empty:
        print("Success!")
        print(df.head())
    else:
        print("Returned empty or None")
except Exception as e:
    print(f"Error: {e}")
