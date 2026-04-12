# one_click_run_upgrade.py
import pandas as pd
from pathlib import Path
import subprocess
import sys

# 自动导入 _coerce_to_date
try:
    from src.core.rule_backtest_engine import _coerce_to_date
except ImportError:
    print("⚠️ Cannot import _coerce_to_date from rule_backtest_engine.py. Please check path.")
    _coerce_to_date = None

# 1️⃣ 修复 Parquet 文件
parquet_dir = Path("/Users/yehengli/us_test_data/normalized/us")
for file in parquet_dir.glob("*.parquet"):
    df = pd.read_parquet(file)
    if 'date' not in df.columns:
        possible = [c for c in df.columns if c.lower() in ['trade_date','timestamp','datetime']]
        if possible:
            df.rename(columns={possible[0]: 'date'}, inplace=True)
            print(f"Renamed '{possible[0]}' → 'date' in {file.name}")
        else:
            print(f"⚠️ No date column in {file.name}, skipping")
            continue
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df.to_parquet(file, index=False)
    print(f"✅ Fixed {file.name}")

# 2️⃣ 可选：检查前几行
for file in parquet_dir.glob("*.parquet"):
    df = pd.read_parquet(file)
    print(f"\n{file.name} head:")
    print(df.head(3))

# 3️⃣ 检查 __future__ 导入
engine_file = Path("src/core/rule_backtest_engine.py")
if engine_file.exists():
    with open(engine_file, "r", encoding="utf-8") as f:
        first_line = f.readline()
    if "from __future__ import annotations" not in first_line:
        print("⚠️ Warning: from __future__ import annotations must be first line in rule_backtest_engine.py")
else:
    print("⚠️ rule_backtest_engine.py not found. Check src/core path.")

# 4️⃣ 调用回测
backtest_file = Path("run_all_fixed.py")  # 如果在根目录
if not backtest_file.exists():
    print(f"⚠️ {backtest_file} not found. Please check path.")
    sys.exit(1)

print("\n▶️ Running backtest...")
subprocess.run(["python3", str(backtest_file)], check=True)
print("🏁 Backtest finished")