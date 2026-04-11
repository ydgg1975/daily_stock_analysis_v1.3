# File: src/services/rule_backtest_service.py
import os
import pandas as pd
from pathlib import Path

OUTPUT_DIR = Path('./backtest_outputs')
OUTPUT_DIR.mkdir(exist_ok=True)

# ---- Load US Parquet ----
def load_us_parquet(symbol: str) -> pd.DataFrame:
    file_path = Path(os.getenv("LOCAL_US_PARQUET_DIR")) / f"{symbol}.parquet"
    df = pd.read_parquet(file_path)
    # Standardize columns
    if 'trade_date' in df.columns:
        df = df.rename(columns={'trade_date': 'date'})
    if 'close' not in df.columns and '标的收盘价' in df.columns:
        df = df.rename(columns={'标的收盘价': 'close'})
    return df

# ---- Serialize trace ----
def serialize_trace(trace: list) -> list:
    for e in trace:
        if 'date' in e and isinstance(e['date'], pd.Timestamp):
            e['date'] = e['date'].strftime('%Y-%m-%d')
    return trace

# ---- P0 Automated Backtest ----
def run_backtest_automated(symbol: str, initial_capital: float):
    df = load_us_parquet(symbol)
    trace = []

    position = 0
    cash = initial_capital
    for idx, row in df.iterrows():
        action = 'hold'
        if pd.notna(row.get('MA5')) and row['close'] > row['MA5']:
            if cash >= row['close']:
                position += 1
                cash -= row['close']
                action = 'buy'
        elif pd.notna(row.get('MA5')) and row['close'] < row['MA5'] and position > 0:
            cash += row['close'] * position
            position = 0
            action = 'sell'
        trace.append({
            'date': row['date'],
            'close': row['close'],
            'action': action,
            'position': position,
            'cash': cash
        })

    trace = serialize_trace(trace)
    return {'trace': trace}

# ---- Export helpers ----
def export_execution_trace_csv(trace: list, filename: str):
    df = pd.DataFrame(trace)
    df.to_csv(filename, index=False, encoding='utf-8-sig')

def export_execution_trace_json(trace: list, filename: str):
    df = pd.DataFrame(trace)
    df.to_json(filename, orient='records', force_ascii=False)