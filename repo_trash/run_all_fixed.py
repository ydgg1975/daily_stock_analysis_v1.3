# run_all_fixed.py
import os
from pathlib import Path

# 指定本地 parquet 目录
os.environ["LOCAL_US_PARQUET_DIR"] = str(Path("~/us_test_data/normalized/us").expanduser())
import pandas as pd
import numpy as np
from pathlib import Path
import subprocess
from src.services import wolfystock_p2_runner as p2
import scripts.run_wolfystock_p2 as run_p2


# -----------------------------
# 1. 修复 parquet 数据
# -----------------------------
parquet_dir = Path("~/us_test_data/normalized/us").expanduser()
ohlcv_cols = ["open","high","low","close","volume"]

def flatten_value(x):
    if isinstance(x, (int, float, np.number)) or x is None:
        return x
    if isinstance(x, (list, tuple, np.ndarray)):
        return flatten_value(x[0])
    return np.nan

for file in parquet_dir.glob("*.parquet"):
    df = pd.read_parquet(file)
    df.columns = [str(c).lower() for c in df.columns]
    for col in ohlcv_cols:
        if col in df.columns:
            df[col] = df[col].apply(flatten_value)
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df.to_parquet(file, index=False)
    print(f"Fixed {file}")

# -----------------------------
# 2. monkey patch P2
# -----------------------------
_orig_func = p2.standardize_ohlcv_columns

def patched_standardize_ohlcv_columns(df):
    renamed = df.copy()
    for price_column in ["open","high","low","close","volume"]:
        if price_column in renamed.columns:
            col = renamed[price_column]
            if not isinstance(col, pd.Series):
                col = pd.Series(col)
            col = col.apply(lambda x: x[0] if isinstance(x,(list,tuple,np.ndarray)) else x)
            renamed[price_column] = pd.to_numeric(col, errors="coerce")
    return renamed

p2.standardize_ohlcv_columns = patched_standardize_ohlcv_columns
print("Monkey patch applied for standardize_ohlcv_columns")

# -----------------------------
# 3. 执行 P2
# -----------------------------
print("Running WolfyStock P2...")
run_p2.main()

# -----------------------------
# 4. 执行 P3
# -----------------------------
print("Running WolfyStock P3...")
subprocess.run([
    "python3",
    "run_wolfystock_p3.py",
    "--p2-output", "backtest_outputs/p2_fullrun",
    "--output-root", "backtest_outputs/p3_fullrun",
    "--run-tag", "final-p3"
])