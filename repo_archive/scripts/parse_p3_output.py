#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
from pathlib import Path
import plotly.express as px
import plotly.io as pio

# --- 路径设置 ---
BASE_DIR = Path(__file__).resolve().parent.parent
P3_DIR = BASE_DIR / "backtest_outputs/p3"
PLOTS_DIR = P3_DIR / "plots"

# 确保 plots 目录存在
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
print(f"✅ 目录准备就绪: {PLOTS_DIR}")

# --- CSV 文件 ---
RUNS_CSV = P3_DIR / "summary_runs.csv"
SYMBOLS_CSV = P3_DIR / "summary_symbols.csv"

def read_summary_csv():
    runs_df = pd.read_csv(RUNS_CSV)
    symbols_df = pd.read_csv(SYMBOLS_CSV)
    print("✅ CSV 已成功读取")
    print("\n--- summary_runs.csv 前 5 行 ---")
    print(runs_df.head())
    print("\n--- summary_symbols.csv 前 5 行 ---")
    print(symbols_df.head())
    return runs_df, symbols_df

# --- 绘图函数 ---
def plot_runs_histogram(runs_df):
    if 'annualized_return_pct' in runs_df.columns:
        fig = px.histogram(runs_df, x='annualized_return_pct', color='strategy_family',
                           nbins=50, title="策略年化收益分布")
        fig.write_html(PLOTS_DIR / "runs_annualized_return.html")
        print(f"✅ runs histogram 已保存: {PLOTS_DIR / 'runs_annualized_return.html'}")
    else:
        print("⚠️ runs_df 不包含 'annualized_return_pct'，跳过绘图")

def plot_symbols_bar(symbols_df):
    if 'avg_total_return_pct' in symbols_df.columns:
        top_symbols = symbols_df.sort_values('avg_total_return_pct', ascending=False).head(20)
        fig = px.bar(top_symbols, x='symbol', y='avg_total_return_pct', color='symbol',
                     title="前20股票平均总收益")
        fig.write_html(PLOTS_DIR / "symbols_avg_total_return.html")
        print(f"✅ symbols bar chart 已保存: {PLOTS_DIR / 'symbols_avg_total_return.html'}")
    else:
        print("⚠️ symbols_df 不包含 'avg_total_return_pct'，跳过绘图")

def plot_equity_curve(runs_df):
    # 检查 timestamp 和 equity 列
    if 'timestamp' in runs_df.columns and 'equity' in runs_df.columns:
        fig = px.line(runs_df, x='timestamp', y='equity', color='run_id', title="净值曲线")
        fig.write_html(PLOTS_DIR / "equity_curve.html")
        print(f"✅ equity curve 已保存: {PLOTS_DIR / 'equity_curve.html'}")
    else:
        print("⚠️ CSV 不包含 'timestamp' 或 'equity' 列，跳过绘图")

def main():
    runs_df, symbols_df = read_summary_csv()
    plot_runs_histogram(runs_df)
    plot_symbols_bar(symbols_df)
    plot_equity_curve(runs_df)

if __name__ == "__main__":
    main()