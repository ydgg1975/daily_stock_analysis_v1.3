import akshare as ak
import pandas as pd

codes = ["600519", "sh600519", "SH600519"]

for code in codes:
    print(f"Testing ak.stock_financial_analysis_indicator for {code}...")
    try:
        df = ak.stock_financial_analysis_indicator(symbol=code)
        if df is not None and not df.empty:
            print(f"Success with {code}!")
            print(df.head())
            break
        else:
            print(f"Returned empty or None for {code}")
    except Exception as e:
        print(f"Error for {code}: {e}")

print("Trying ak.stock_financial_abstract...")
try:
    df = ak.stock_financial_abstract(symbol="600519")
    if df is not None and not df.empty:
        print("Success abstract!")
        print(df.head())
except Exception as e:
    print(f"Error abstract: {e}")
