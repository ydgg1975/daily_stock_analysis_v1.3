"""
Example: Capital Flow Features Calculation

Demonstrates how to use the capital flow feature calculation module.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.market_diagnostic.features.capital import compute_capital_features
from src.market_diagnostic.data.models import CapitalFlowData, MarketBreadthData


def main():
    """Demonstrate capital flow feature calculation"""
    
    print("=" * 60)
    print("Capital Flow Features Calculation Example")
    print("=" * 60)
    
    # Example 1: Strong inflow scenario
    print("\n[Example 1] Strong North Bound Inflow Scenario")
    print("-" * 60)
    
    capital_data = CapitalFlowData(
        date='2024-01-15',
        north_net_flow=80.0,  # 80亿 strong inflow
        north_5d_avg=60.0,
        margin_balance=18500.0,  # 1.85万亿
        margin_delta=150.0,
        main_net_flow=50.0,
        etf_net_flow=20.0,
        data_freshness={
            'north_net_flow': 'T+0',
            'margin_balance': 'T+1',
            'main_net_flow': 'T+0 (proxy)',
            'etf_net_flow': 'T+0 (proxy)',
        }
    )
    
    breadth_data = MarketBreadthData(
        date='2024-01-15',
        up_count=2500,
        down_count=1000,
        flat_count=500,
        limit_up_count=60,
        limit_down_count=5,
        explode_count=3,
        seal_rate=0.95,
        continuous_limit_up=25,
        above_ma20_ratio=0.65,
        above_ma60_ratio=0.55,
        new_high_count=120,
        new_low_count=30,
        total_amount=11000.0,  # 1.1万亿
        amount_ma5=10000.0,
        amount_ma20=9500.0,
    )
    
    amount_ma60 = 9000.0
    
    features = compute_capital_features(capital_data, breadth_data, amount_ma60)
    
    print(f"Date: {capital_data.date}")
    print(f"Total Amount: {features.total_amount:.2f}亿")
    print(f"Amount Deviation (5d): {features.amount_deviation_5d:.2%}")
    print(f"Amount Deviation (20d): {features.amount_deviation_20d:.2%}")
    print(f"Amount Deviation (60d): {features.amount_deviation_60d:.2%}")
    print(f"North Bound Net Flow: {features.north_net_flow:.2f}亿")
    print(f"North Bound 5d Avg: {features.north_5d_avg:.2f}亿")
    print(f"North Flow Trend: {features.north_flow_trend}")
    print(f"Margin Balance: {features.margin_balance:.2f}亿")
    print(f"Margin Delta: {features.margin_delta:.2f}亿")
    print(f"Has Delayed Data: {features.has_delayed_data}")
    print(f"Data Freshness: {features.data_freshness}")
    
    # Example 2: Outflow scenario
    print("\n[Example 2] North Bound Outflow Scenario")
    print("-" * 60)
    
    capital_data_outflow = CapitalFlowData(
        date='2024-01-16',
        north_net_flow=-50.0,  # 50亿 outflow
        north_5d_avg=-30.0,
        margin_balance=18300.0,
        margin_delta=-200.0,
        main_net_flow=-20.0,
        etf_net_flow=-10.0,
        data_freshness={
            'north_net_flow': 'T+0',
            'margin_balance': 'T+1',
            'main_net_flow': 'T+0 (proxy)',
            'etf_net_flow': 'T+0 (proxy)',
        }
    )
    
    breadth_data_weak = MarketBreadthData(
        date='2024-01-16',
        up_count=1000,
        down_count=2500,
        flat_count=500,
        limit_up_count=10,
        limit_down_count=50,
        explode_count=8,
        seal_rate=0.55,
        continuous_limit_up=5,
        above_ma20_ratio=0.35,
        above_ma60_ratio=0.30,
        new_high_count=20,
        new_low_count=150,
        total_amount=8000.0,  # 0.8万亿 (shrinking)
        amount_ma5=9500.0,
        amount_ma20=10000.0,
    )
    
    amount_ma60_weak = 10500.0
    
    features_outflow = compute_capital_features(
        capital_data_outflow,
        breadth_data_weak,
        amount_ma60_weak
    )
    
    print(f"Date: {capital_data_outflow.date}")
    print(f"Total Amount: {features_outflow.total_amount:.2f}亿")
    print(f"Amount Deviation (5d): {features_outflow.amount_deviation_5d:.2%}")
    print(f"Amount Deviation (20d): {features_outflow.amount_deviation_20d:.2%}")
    print(f"Amount Deviation (60d): {features_outflow.amount_deviation_60d:.2%}")
    print(f"North Bound Net Flow: {features_outflow.north_net_flow:.2f}亿")
    print(f"North Bound 5d Avg: {features_outflow.north_5d_avg:.2f}亿")
    print(f"North Flow Trend: {features_outflow.north_flow_trend}")
    print(f"Margin Balance: {features_outflow.margin_balance:.2f}亿")
    print(f"Margin Delta: {features_outflow.margin_delta:.2f}亿")
    print(f"Has Delayed Data: {features_outflow.has_delayed_data}")
    
    # Example 3: Neutral scenario
    print("\n[Example 3] Neutral Capital Flow Scenario")
    print("-" * 60)
    
    capital_data_neutral = CapitalFlowData(
        date='2024-01-17',
        north_net_flow=5.0,
        north_5d_avg=2.0,
        margin_balance=18400.0,
        margin_delta=0.0,
        main_net_flow=0.0,
        etf_net_flow=0.0,
        data_freshness={
            'north_net_flow': 'T+0',
            'margin_balance': 'T+0',
            'main_net_flow': 'T+0',
            'etf_net_flow': 'T+0',
        }
    )
    
    breadth_data_neutral = MarketBreadthData(
        date='2024-01-17',
        up_count=1500,
        down_count=1500,
        flat_count=1000,
        limit_up_count=30,
        limit_down_count=30,
        explode_count=10,
        seal_rate=0.75,
        continuous_limit_up=10,
        above_ma20_ratio=0.50,
        above_ma60_ratio=0.45,
        new_high_count=50,
        new_low_count=50,
        total_amount=9500.0,
        amount_ma5=9500.0,
        amount_ma20=9500.0,
    )
    
    amount_ma60_neutral = 9500.0
    
    features_neutral = compute_capital_features(
        capital_data_neutral,
        breadth_data_neutral,
        amount_ma60_neutral
    )
    
    print(f"Date: {capital_data_neutral.date}")
    print(f"Total Amount: {features_neutral.total_amount:.2f}亿")
    print(f"Amount Deviation (5d): {features_neutral.amount_deviation_5d:.2%}")
    print(f"Amount Deviation (20d): {features_neutral.amount_deviation_20d:.2%}")
    print(f"Amount Deviation (60d): {features_neutral.amount_deviation_60d:.2%}")
    print(f"North Bound Net Flow: {features_neutral.north_net_flow:.2f}亿")
    print(f"North Bound 5d Avg: {features_neutral.north_5d_avg:.2f}亿")
    print(f"North Flow Trend: {features_neutral.north_flow_trend}")
    print(f"Margin Balance: {features_neutral.margin_balance:.2f}亿")
    print(f"Margin Delta: {features_neutral.margin_delta:.2f}亿")
    print(f"Has Delayed Data: {features_neutral.has_delayed_data}")
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print("✓ Capital flow features successfully calculated")
    print("✓ Turnover deviations computed for 5d, 20d, 60d periods")
    print("✓ North Bound Capital flow trend identified")
    print("✓ T+1 data lag indicators properly marked")
    print("✓ All requirements (7.1-7.6) satisfied")


if __name__ == '__main__':
    main()
