#!/usr/bin/env python3
"""
AkShare Interface Validation Script
====================================
Phase 0 validation for Market Diagnostic System.

Tests all required AkShare interfaces, documents return formats,
measures response times, and verifies data quality.

Requirements: 1.6, 22.1
Usage:
    python scripts/validate_akshare_interfaces.py
    python scripts/validate_akshare_interfaces.py --section breadth
    python scripts/validate_akshare_interfaces.py --section sector
    python scripts/validate_akshare_interfaces.py --section valuation
"""

import argparse
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recent_trading_date() -> str:
    """Return a recent weekday date string in YYYYMMDD format."""
    d = datetime.today()
    # Walk back to last weekday
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    # Use 2 days ago to avoid same-day data gaps
    d -= timedelta(days=2)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def _timed_call(func, *args, **kwargs) -> Tuple[Any, float]:
    """Call func(*args, **kwargs) and return (result, elapsed_seconds)."""
    t0 = time.time()
    result = func(*args, **kwargs)
    return result, round(time.time() - t0, 3)


def _check_columns(df, required_cols: List[str], api_name: str) -> bool:
    """Verify required columns exist in DataFrame."""
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        logger.warning(f"[{api_name}] Missing columns: {missing}")
        return False
    return True


# ---------------------------------------------------------------------------
# Section 1: Breadth Data Interfaces (Task 0.2)
# ---------------------------------------------------------------------------

def validate_breadth_interfaces(date: str) -> Dict[str, Any]:
    """
    Validate breadth data interfaces:
      - ak.stock_zt_pool_em        (limit-up pool)
      - ak.stock_zt_pool_dtgc_em   (limit-down pool, corrected name)
      - ak.stock_zh_a_spot_em      (market-wide realtime quotes)

    Requirements: 1.3, 3.1, 3.2, 3.3
    """
    try:
        import akshare as ak
    except ImportError:
        logger.error("akshare not installed. Run: pip install akshare")
        return {"status": "error", "message": "akshare not installed"}

    results: Dict[str, Any] = {}

    # --- 1. Limit-up pool ---
    logger.info(f"Testing ak.stock_zt_pool_em(date='{date}') ...")
    try:
        df_zt, elapsed = _timed_call(ak.stock_zt_pool_em, date=date)
        required = ["代码", "名称", "涨跌幅", "最新价", "成交额", "换手率", "炸板次数", "封板资金"]
        ok = _check_columns(df_zt, required, "stock_zt_pool_em")
        results["stock_zt_pool_em"] = {
            "status": "ok" if ok else "partial",
            "rows": len(df_zt),
            "columns": list(df_zt.columns),
            "elapsed_s": elapsed,
            "sample": df_zt.head(2).to_dict("records") if len(df_zt) > 0 else [],
        }
        logger.info(f"  → {len(df_zt)} rows in {elapsed}s")
    except Exception as e:
        logger.error(f"  → FAILED: {e}")
        results["stock_zt_pool_em"] = {"status": "error", "message": str(e)}

    time.sleep(2)

    # --- 2. Limit-down pool (corrected API name) ---
    logger.info(f"Testing ak.stock_zt_pool_dtgc_em(date='{date}') ...")
    try:
        df_dt, elapsed = _timed_call(ak.stock_zt_pool_dtgc_em, date=date)
        required = ["代码", "名称", "涨跌幅", "最新价", "成交额", "换手率"]
        ok = _check_columns(df_dt, required, "stock_zt_pool_dtgc_em")
        results["stock_zt_pool_dtgc_em"] = {
            "status": "ok" if ok else "partial",
            "rows": len(df_dt),
            "columns": list(df_dt.columns),
            "elapsed_s": elapsed,
            "note": "Correct name; design doc erroneously references stock_dt_pool_em",
        }
        logger.info(f"  → {len(df_dt)} rows in {elapsed}s")
    except Exception as e:
        logger.error(f"  → FAILED: {e}")
        results["stock_zt_pool_dtgc_em"] = {"status": "error", "message": str(e)}

    time.sleep(2)

    # --- 3. Market-wide realtime quotes ---
    logger.info("Testing ak.stock_zh_a_spot_em() ...")
    try:
        df_spot, elapsed = _timed_call(ak.stock_zh_a_spot_em)
        required = ["代码", "名称", "最新价", "涨跌幅", "成交量", "成交额", "量比", "换手率"]
        ok = _check_columns(df_spot, required, "stock_zh_a_spot_em")
        results["stock_zh_a_spot_em"] = {
            "status": "ok" if ok else "partial",
            "rows": len(df_spot),
            "columns": list(df_spot.columns),
            "elapsed_s": elapsed,
        }
        logger.info(f"  → {len(df_spot)} rows in {elapsed}s")
    except Exception as e:
        logger.error(f"  → FAILED: {e}")
        results["stock_zh_a_spot_em"] = {"status": "error", "message": str(e)}

    return results


# ---------------------------------------------------------------------------
# Section 2: Sector Data Interfaces (Task 0.3)
# ---------------------------------------------------------------------------

def validate_sector_interfaces(date: str) -> Dict[str, Any]:
    """
    Validate sector data interfaces:
      - ak.stock_board_industry_hist_em   (industry historical data)
      - ak.stock_board_industry_cons_em   (industry constituents)
      - ak.stock_sector_fund_flow_rank    (industry capital flow)

    Requirements: 1.4, 6.1, 6.2
    """
    try:
        import akshare as ak
    except ImportError:
        logger.error("akshare not installed.")
        return {"status": "error", "message": "akshare not installed"}

    results: Dict[str, Any] = {}
    sample_industry = "BK0447"  # 银行 (Banking) as representative sample

    # --- 1. Industry historical data ---
    logger.info(f"Testing ak.stock_board_industry_hist_em(symbol='{sample_industry}', period='日k') ...")
    try:
        df_hist, elapsed = _timed_call(
            ak.stock_board_industry_hist_em,
            symbol=sample_industry,
            period="日k",
            start_date="20250101",
            end_date=date,
            adjust="",
        )
        required = ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]
        ok = _check_columns(df_hist, required, "stock_board_industry_hist_em")
        results["stock_board_industry_hist_em"] = {
            "status": "ok" if ok else "partial",
            "rows": len(df_hist),
            "columns": list(df_hist.columns),
            "elapsed_s": elapsed,
            "sample_symbol": sample_industry,
        }
        logger.info(f"  → {len(df_hist)} rows in {elapsed}s")
    except Exception as e:
        logger.error(f"  → FAILED: {e}")
        results["stock_board_industry_hist_em"] = {"status": "error", "message": str(e)}

    time.sleep(3)

    # --- 2. Industry constituents ---
    logger.info(f"Testing ak.stock_board_industry_cons_em(symbol='{sample_industry}') ...")
    try:
        df_cons, elapsed = _timed_call(ak.stock_board_industry_cons_em, symbol=sample_industry)
        required = ["代码", "名称"]
        ok = _check_columns(df_cons, required, "stock_board_industry_cons_em")
        results["stock_board_industry_cons_em"] = {
            "status": "ok" if ok else "partial",
            "rows": len(df_cons),
            "columns": list(df_cons.columns),
            "elapsed_s": elapsed,
            "sample_symbol": sample_industry,
        }
        logger.info(f"  → {len(df_cons)} rows in {elapsed}s")
    except Exception as e:
        logger.error(f"  → FAILED: {e}")
        results["stock_board_industry_cons_em"] = {"status": "error", "message": str(e)}

    time.sleep(3)

    # --- 3. Industry capital flow ---
    logger.info("Testing ak.stock_sector_fund_flow_rank(indicator='今日') ...")
    try:
        df_flow, elapsed = _timed_call(ak.stock_sector_fund_flow_rank, indicator="今日")
        required = ["名称", "今日涨跌幅"]
        ok = _check_columns(df_flow, required, "stock_sector_fund_flow_rank")
        results["stock_sector_fund_flow_rank"] = {
            "status": "ok" if ok else "partial",
            "rows": len(df_flow),
            "columns": list(df_flow.columns),
            "elapsed_s": elapsed,
        }
        logger.info(f"  → {len(df_flow)} rows in {elapsed}s")
    except Exception as e:
        logger.error(f"  → FAILED: {e}")
        results["stock_sector_fund_flow_rank"] = {"status": "error", "message": str(e)}

    return results


# ---------------------------------------------------------------------------
# Section 3: Valuation and Macro Data Interfaces (Task 0.4)
# ---------------------------------------------------------------------------

def validate_valuation_interfaces() -> Dict[str, Any]:
    """
    Validate valuation and macro data interfaces:
      - ak.stock_zh_index_value_csindex   (CSI index PE/PB)
      - ak.bond_zh_us_rate                (China/US bond yields)
      - ak.currency_boc_sina              (BOC exchange rates)

    Requirements: 24.1, 24.2
    """
    try:
        import akshare as ak
    except ImportError:
        logger.error("akshare not installed.")
        return {"status": "error", "message": "akshare not installed"}

    results: Dict[str, Any] = {}

    # --- 1. CSI300 PE/PB ---
    logger.info("Testing ak.stock_zh_index_value_csindex(symbol='000300') ...")
    try:
        df_val, elapsed = _timed_call(ak.stock_zh_index_value_csindex, symbol="000300")
        results["stock_zh_index_value_csindex"] = {
            "status": "ok",
            "rows": len(df_val),
            "columns": list(df_val.columns),
            "elapsed_s": elapsed,
            "note": "CSI300 PE/PB valuation data",
        }
        logger.info(f"  → {len(df_val)} rows in {elapsed}s")
    except Exception as e:
        logger.error(f"  → FAILED: {e}")
        results["stock_zh_index_value_csindex"] = {"status": "error", "message": str(e)}

    time.sleep(2)

    # --- 2. Bond yields ---
    logger.info("Testing ak.bond_zh_us_rate() ...")
    try:
        df_bond, elapsed = _timed_call(ak.bond_zh_us_rate)
        results["bond_zh_us_rate"] = {
            "status": "ok",
            "rows": len(df_bond),
            "columns": list(df_bond.columns),
            "elapsed_s": elapsed,
            "note": "China/US bond yield data",
        }
        logger.info(f"  → {len(df_bond)} rows in {elapsed}s")
    except Exception as e:
        logger.error(f"  → FAILED: {e}")
        results["bond_zh_us_rate"] = {"status": "error", "message": str(e)}

    time.sleep(2)

    # --- 3. BOC exchange rates ---
    logger.info("Testing ak.currency_boc_sina() ...")
    try:
        df_fx, elapsed = _timed_call(ak.currency_boc_sina)
        results["currency_boc_sina"] = {
            "status": "ok",
            "rows": len(df_fx),
            "columns": list(df_fx.columns),
            "elapsed_s": elapsed,
            "note": "Bank of China exchange rate data",
        }
        logger.info(f"  → {len(df_fx)} rows in {elapsed}s")
    except Exception as e:
        logger.error(f"  → FAILED: {e}")
        results["currency_boc_sina"] = {"status": "error", "message": str(e)}

    return results


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def print_summary(all_results: Dict[str, Dict[str, Any]]) -> None:
    """Print a human-readable validation summary."""
    print("\n" + "=" * 60)
    print("AkShare Interface Validation Summary")
    print("=" * 60)
    for section, results in all_results.items():
        print(f"\n[{section}]")
        if isinstance(results, dict) and "status" in results and results["status"] == "error":
            print(f"  ERROR: {results.get('message')}")
            continue
        for api, info in results.items():
            status = info.get("status", "unknown")
            rows = info.get("rows", "N/A")
            elapsed = info.get("elapsed_s", "N/A")
            icon = "✓" if status == "ok" else ("⚠" if status == "partial" else "✗")
            print(f"  {icon} {api}: {rows} rows, {elapsed}s [{status}]")
            if "note" in info:
                print(f"      Note: {info['note']}")
            if status == "error":
                print(f"      Error: {info.get('message')}")
    print("\n" + "=" * 60)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate AkShare interfaces for Market Diagnostic System")
    parser.add_argument(
        "--section",
        choices=["breadth", "sector", "valuation", "all"],
        default="all",
        help="Which section to validate (default: all)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Trading date in YYYYMMDD format (default: auto-detect recent trading day)",
    )
    args = parser.parse_args()

    date = args.date or _recent_trading_date()
    logger.info(f"Using trading date: {date}")

    all_results: Dict[str, Dict[str, Any]] = {}

    if args.section in ("breadth", "all"):
        logger.info("\n--- Validating Breadth Data Interfaces ---")
        all_results["breadth"] = validate_breadth_interfaces(date)

    if args.section in ("sector", "all"):
        logger.info("\n--- Validating Sector Data Interfaces ---")
        all_results["sector"] = validate_sector_interfaces(date)

    if args.section in ("valuation", "all"):
        logger.info("\n--- Validating Valuation & Macro Interfaces ---")
        all_results["valuation"] = validate_valuation_interfaces()

    print_summary(all_results)


if __name__ == "__main__":
    main()
