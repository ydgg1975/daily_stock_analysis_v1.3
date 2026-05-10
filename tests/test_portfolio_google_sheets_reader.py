# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.portfolio.google_sheets_reader import _derive_position_metrics


def test_derive_position_metrics_prefers_derived_pnl_over_sheet_value():
    total_value, pnl, pnl_pct = _derive_position_metrics(
        shares=100,
        avg_buy_price=10.0,
        current_price=15.0,
        total_value=1500.0,
        pnl=123.0,
    )

    assert total_value == 1500.0
    assert pnl == 500.0
    assert pnl_pct == 50.0


def test_derive_position_metrics_backfills_missing_total_value():
    total_value, pnl, pnl_pct = _derive_position_metrics(
        shares=20,
        avg_buy_price=50.0,
        current_price=60.0,
        total_value=None,
        pnl=None,
    )

    assert total_value == 1200.0
    assert pnl == 200.0
    assert pnl_pct == 20.0
