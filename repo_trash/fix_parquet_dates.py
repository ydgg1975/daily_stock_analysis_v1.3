import pandas as pd
from pathlib import Path

parquet_dir = Path("/Users/yehengli/us_test_data/normalized/us")

for file in parquet_dir.glob("*.parquet"):
    df = pd.read_parquet(file)
    print(f"\nFile: {file}")
    print("Columns:", df.columns.tolist())

    # 如果没有 date 列，但有 trade_date 列
    if 'date' not in df.columns and 'trade_date' in df.columns:
        df.rename(columns={'trade_date': 'date'}, inplace=True)
        print("Renamed 'trade_date' → 'date'")

    # 强制转换为 datetime
    df['date'] = pd.to_datetime(df['date'], errors='coerce')

    # 保存覆盖原文件
    df.to_parquet(file, index=False)
    print(f"✅ Fixed {file}")