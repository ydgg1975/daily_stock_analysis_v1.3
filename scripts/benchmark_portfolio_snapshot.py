#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dedicated WS2 benchmark harness for portfolio snapshot cold vs warm reads."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Callable, Dict, Iterable, Iterator, List, Optional
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from src.config import Config
from src.storage import DatabaseManager
from src.services.portfolio_service import PortfolioService

DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "benchmarks"


@dataclass
class Scenario:
    account_count: int
    symbols_per_account: int
    trades_per_symbol: int
    warm_runs: int
    mix_currencies: bool


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_int_csv(raw: str) -> List[int]:
    values = [int(part.strip()) for part in str(raw or "").split(",") if str(part).strip()]
    if not values:
        raise ValueError("At least one integer value is required")
    return values


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark portfolio snapshot cold vs warm reads on synthetic scenarios.",
    )
    parser.add_argument("--account-counts", default="1,5", help="Comma-separated account counts.")
    parser.add_argument("--symbol-counts", default="25,100", help="Comma-separated symbol counts per account.")
    parser.add_argument("--trades-per-symbol", type=int, default=3, help="Buy trades per symbol.")
    parser.add_argument("--warm-runs", type=int, default=3, help="Warm repeat reads per scenario.")
    parser.add_argument(
        "--mix-currencies",
        action="store_true",
        help="Alternate USD/HKD symbols inside each account to exercise FX paths.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output JSON path. Default: reports/benchmarks/portfolio_snapshot_<UTC timestamp>.json",
    )
    return parser


@contextmanager
def _temporary_portfolio_env() -> Iterator[None]:
    previous_env_file = os.environ.get("ENV_FILE")
    previous_db_path = os.environ.get("DATABASE_PATH")
    temp_dir = tempfile.TemporaryDirectory()
    try:
        env_path = Path(temp_dir.name) / ".env"
        db_path = Path(temp_dir.name) / "portfolio_snapshot_benchmark.db"
        env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519",
                    "GEMINI_API_KEY=test",
                    "ADMIN_AUTH_ENABLED=false",
                    f"DATABASE_PATH={db_path}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(env_path)
        os.environ["DATABASE_PATH"] = str(db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()
        yield
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        if previous_env_file is None:
            os.environ.pop("ENV_FILE", None)
        else:
            os.environ["ENV_FILE"] = previous_env_file
        if previous_db_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = previous_db_path
        temp_dir.cleanup()


def _save_close(db: DatabaseManager, *, symbol: str, on_date: date, close: float) -> None:
    df = pd.DataFrame(
        [
            {
                "date": on_date,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 1.0,
                "amount": close,
                "pct_chg": 0.0,
            }
        ]
    )
    db.save_daily_data(df, code=symbol, data_source="portfolio-snapshot-benchmark")


def _make_symbol(symbol_index: int, *, mix_currencies: bool) -> tuple[str, str, str, float]:
    if mix_currencies and symbol_index % 2 == 1:
        code = f"HK{700 + symbol_index:05d}"
        return code, "hk", "HKD", 320.0 + float(symbol_index % 17)
    code = f"US{symbol_index:04d}"
    return code, "us", "USD", 100.0 + float(symbol_index % 31)


def _seed_account(
    service: PortfolioService,
    db: DatabaseManager,
    *,
    account_index: int,
    scenario: Scenario,
    as_of_date: date,
) -> int:
    account = service.create_account(
        name=f"Bench {account_index + 1}",
        broker="Benchmark",
        market="global" if scenario.mix_currencies else "us",
        base_currency="USD",
    )
    account_id = int(account["id"])
    service.record_cash_ledger(
        account_id=account_id,
        event_date=as_of_date,
        direction="in",
        amount=2_000_000.0,
        currency="USD",
    )
    if scenario.mix_currencies:
        service.record_cash_ledger(
            account_id=account_id,
            event_date=as_of_date,
            direction="in",
            amount=10_000_000.0,
            currency="HKD",
        )
        db_repo = service.repo
        db_repo.save_fx_rate(
            from_currency="HKD",
            to_currency="USD",
            rate_date=as_of_date,
            rate=0.128,
            source="benchmark",
            is_stale=False,
        )

    for symbol_index in range(scenario.symbols_per_account):
        symbol, market, currency, base_price = _make_symbol(symbol_index=symbol_index, mix_currencies=scenario.mix_currencies)
        for trade_index in range(scenario.trades_per_symbol):
            service.record_trade(
                account_id=account_id,
                symbol=symbol,
                trade_date=as_of_date,
                side="buy",
                quantity=10 + trade_index,
                price=base_price + trade_index,
                fee=1.0,
                tax=0.2,
                market=market,
                currency=currency,
                trade_uid=f"bench-{account_index}-{symbol}-{trade_index}",
                dedup_hash=f"bench-{account_index}-{symbol}-{trade_index}",
            )
        _save_close(db, symbol=symbol, on_date=as_of_date, close=base_price + 5.0)
    return account_id


def _seed_scenario(service: PortfolioService, db: DatabaseManager, *, scenario: Scenario, as_of_date: date) -> List[int]:
    return [
        _seed_account(
            service,
            db,
            account_index=account_index,
            scenario=scenario,
            as_of_date=as_of_date,
        )
        for account_index in range(scenario.account_count)
    ]


def _instrumented_call(service: PortfolioService, *, as_of_date: date, cost_method: str) -> Dict[str, object]:
    targets: List[tuple[object, str]] = [
        (service, "_load_cached_account_snapshot"),
        (service, "_build_account_snapshot"),
        (service.repo, "get_cached_snapshot_bundle"),
        (service.repo, "replace_positions_lots_and_snapshot"),
        (service.repo, "get_latest_closes"),
        (service.repo, "get_latest_close"),
        (service.repo, "get_latest_market_data_update"),
        (service.repo, "get_latest_fx_rate"),
        (service.repo, "get_latest_fx_rate_update"),
        (service.repo, "list_trades"),
        (service.repo, "list_cash_ledger"),
        (service.repo, "list_corporate_actions"),
    ]
    counts: Dict[str, int] = {}

    def _wrap(method_name: str, bound_method: Callable[..., object]) -> Callable[..., object]:
        def _wrapped(*args, **kwargs):
            counts[method_name] = counts.get(method_name, 0) + 1
            return bound_method(*args, **kwargs)

        return _wrapped

    with ExitStack() as stack:
        for target, name in targets:
            original = getattr(target, name)
            stack.enter_context(patch.object(target, name, new=_wrap(name, original)))
        started = time.perf_counter()
        snapshot = service.get_portfolio_snapshot(as_of=as_of_date, cost_method=cost_method)
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)

    account_positions = sum(len(account.get("positions", [])) for account in snapshot.get("accounts", []))
    return {
        "duration_ms": elapsed_ms,
        "lookup_counts": counts,
        "account_count": int(snapshot.get("account_count", 0) or 0),
        "position_count": int(account_positions),
    }


def _run_scenario(scenario: Scenario) -> Dict[str, object]:
    as_of_date = date(2026, 1, 31)
    with _temporary_portfolio_env():
        db = DatabaseManager.get_instance()
        service = PortfolioService()
        _seed_scenario(service, db, scenario=scenario, as_of_date=as_of_date)

        cold_read = _instrumented_call(service, as_of_date=as_of_date, cost_method="fifo")
        warm_runs = [
            _instrumented_call(service, as_of_date=as_of_date, cost_method="fifo")
            for _ in range(scenario.warm_runs)
        ]
        warm_durations = [float(item["duration_ms"]) for item in warm_runs]

    return {
        "scenario": {
            **asdict(scenario),
            "total_symbols": scenario.account_count * scenario.symbols_per_account,
            "total_trade_events": scenario.account_count * scenario.symbols_per_account * scenario.trades_per_symbol,
        },
        "cold_read": cold_read,
        "warm_read": {
            "run_count": scenario.warm_runs,
            "durations_ms": warm_durations,
            "avg_duration_ms": round(mean(warm_durations), 3),
            "min_duration_ms": round(min(warm_durations), 3),
            "max_duration_ms": round(max(warm_durations), 3),
            "lookup_counts": warm_runs[0]["lookup_counts"] if warm_runs else {},
            "account_count": warm_runs[0]["account_count"] if warm_runs else 0,
            "position_count": warm_runs[0]["position_count"] if warm_runs else 0,
        },
    }


def _default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (DEFAULT_OUTPUT_DIR / f"portfolio_snapshot_{stamp}.json").resolve()


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    scenarios = [
        Scenario(
            account_count=account_count,
            symbols_per_account=symbol_count,
            trades_per_symbol=int(args.trades_per_symbol),
            warm_runs=int(args.warm_runs),
            mix_currencies=bool(args.mix_currencies),
        )
        for account_count in _parse_int_csv(args.account_counts)
        for symbol_count in _parse_int_csv(args.symbol_counts)
    ]

    output_path = Path(args.output).expanduser().resolve() if args.output else _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = [_run_scenario(scenario) for scenario in scenarios]
    payload = {
        "generated_at": _utc_now_iso(),
        "scenario_count": len(results),
        "results": results,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
