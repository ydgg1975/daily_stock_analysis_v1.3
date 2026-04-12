from __future__ import annotations
import numpy as np  # ✅ 新增
"""WolfyStock P2 local-parquet backtest runner.

This module executes deterministic backtests and sensitivity analysis against
local US stock parquet files only. It is designed for server-side batch runs
and writes all artifacts under ``backtest_outputs/p2`` by default.
"""
# src/services/wolfystock_p2_runner.py



import argparse
import inspect
import json
import logging
import math
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import mean
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Optional, Sequence

import pandas as pd

from src.core.rule_backtest_engine import ParsedStrategy, RuleBacktestEngine, RuleBacktestParser

LOGGER = logging.getLogger(__name__)

DEFAULT_OUTPUT_ROOT = Path("backtest_outputs") / "p2"
DEFAULT_INITIAL_CAPITAL = 100000.0
REQUIRED_COMPARE_KPI_FIELDS = {
    "volatility_pct",
    "sortino_ratio",
    "calmar_ratio",
    "alpha_pct",
    "beta",
    "sharpe_ratio",
    "max_drawdown_pct",
    "win_rate_pct",
    "avg_holding_period_days",
    "profit_loss_ratio",
}

def standardize_ohlcv_columns(df):
    renamed = df.copy()  # 保留原始 df
    for col in ["open","high","low","close","volume"]:
        if col in renamed.columns:
            # 如果不是 Series，先转换
            if not isinstance(renamed[col], pd.Series):
                renamed[col] = pd.Series(renamed[col])
            # 强制 flatten，防止有嵌套 list/tuple/ndarray
            renamed[col] = renamed[col].apply(
                lambda x: x[0] if isinstance(x, (list, tuple, np.ndarray)) else x
            )
            # 转换为 numeric
            renamed[col] = pd.to_numeric(renamed[col], errors="coerce")
    return renamed

@dataclass(frozen=True)
class StrategyDefinition:
    """Concrete strategy configuration used for one deterministic run."""

    family: str
    label: str
    strategy_text: str
    parameters: dict[str, Any]
    is_baseline: bool = False


@dataclass(frozen=True)
class RunnerConfig:
    """Normalized runtime configuration for the P2 execution flow."""

    parquet_dir: Optional[Path]
    output_root: Path
    symbols: list[str]
    benchmark_symbol: str
    initial_capital: float
    start_date: Optional[date]
    end_date: Optional[date]
    max_workers: int
    dry_run: bool
    run_tag: str


@dataclass
class RunArtifact:
    """Serialized payload for one deterministic baseline or sensitivity run."""

    symbol: str
    strategy_family: str
    strategy_label: str
    strategy_text: str
    parameters: dict[str, Any]
    run_id: str
    output_dir: Path
    metadata: dict[str, Any]
    summary: dict[str, Any]
    execution_trace: dict[str, Any]
    metrics: dict[str, Any]
    ai_summary: dict[str, Any]
    status: str = "completed"
    error: Optional[str] = None


@dataclass
class SymbolExecutionResult:
    """Aggregated output for one symbol across deterministic and sensitivity runs."""

    symbol: str
    success_count: int = 0
    failure_count: int = 0
    skipped: bool = False
    skip_reason: Optional[str] = None
    baseline_runs: list[RunArtifact] = field(default_factory=list)
    sensitivity_payloads: list[dict[str, Any]] = field(default_factory=list)
    compare_payload: Optional[dict[str, Any]] = None
    errors: list[str] = field(default_factory=list)


def configure_logging() -> None:
    """Configure a plain console logger suitable for batch execution."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def resolve_local_parquet_dir(explicit_dir: Optional[str]) -> Optional[Path]:
    """Resolve the local US parquet root from CLI or environment variables."""

    if explicit_dir:
        return Path(explicit_dir).expanduser().resolve()

    for key in ("LOCAL_US_PARQUET_DIR", "US_STOCK_PARQUET_DIR"):
        value = (os.getenv(key) or "").strip()
        if value:
            return Path(value).expanduser().resolve()
    return None


def parse_date_or_none(raw_value: Optional[str]) -> Optional[date]:
    """Parse an ISO-8601 date string into ``date``."""

    if not raw_value:
        return None
    return date.fromisoformat(raw_value)


def ensure_directory(path: Path) -> None:
    """Create a directory if it does not exist."""

    path.mkdir(parents=True, exist_ok=True)


def json_default(value: Any) -> Any:
    """JSON serializer for dates, dataclasses, and Paths."""

    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return value.__dict__
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    """Write a JSON file with deterministic UTF-8 output."""

    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=json_default)


def list_available_symbols(parquet_dir: Path) -> list[str]:
    """List upper-cased symbols that have parquet files in the local directory."""

    if not parquet_dir.exists() or not parquet_dir.is_dir():
        return []
    return sorted(
        file_path.stem.upper()
        for file_path in parquet_dir.glob("*.parquet")
        if file_path.is_file()
    )


def resolve_symbols(parquet_dir: Optional[Path], requested_symbols: Sequence[str], dry_run: bool) -> tuple[list[str], list[str]]:
    """Resolve the symbol universe and return ``(selected, missing)``."""

    normalized_requested = [symbol.strip().upper() for symbol in requested_symbols if symbol.strip()]
    if dry_run:
        selected = normalized_requested or ["ORCL", "NVDA", "TSLA"]
        return selected, []

    if parquet_dir is None:
        raise ValueError("LOCAL_US_PARQUET_DIR/US_STOCK_PARQUET_DIR is required when not in dry-run mode.")

    available_symbols = set(list_available_symbols(parquet_dir))
    if normalized_requested:
        selected = [symbol for symbol in normalized_requested if symbol in available_symbols]
        missing = [symbol for symbol in normalized_requested if symbol not in available_symbols]
        return selected, missing

    selected = sorted(available_symbols)
    return selected, []


def resolve_benchmark_symbol(configured_benchmark: Optional[str], symbols: Sequence[str]) -> str:
    """Resolve the benchmark symbol using the user-provided value or first symbol."""

    if configured_benchmark:
        benchmark_symbol = configured_benchmark.strip().upper()
        if benchmark_symbol in symbols:
            return benchmark_symbol
    if not symbols:
        raise ValueError("At least one symbol is required.")
    return str(symbols[0]).upper()


def standardize_ohlcv_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize parquet column names to the engine's expected OHLCV schema."""

    renamed = frame.copy()
    renamed.columns = [str(column).strip() for column in renamed.columns]
    canonical_map = {
        "trade_date": "date",
        "datetime": "date",
        "timestamp": "date",
        "symbol": "code",
        "ticker": "code",
        "open_price": "open",
        "high_price": "high",
        "low_price": "low",
        "close_price": "close",
        "adj_close": "close",
        "标的收盘价": "close",
        "收盘价": "close",
        "开盘价": "open",
        "最高价": "high",
        "最低价": "low",
        "日期": "date",
    }
    renamed = renamed.rename(columns={column: canonical_map.get(column, column) for column in renamed.columns})

    if "date" not in renamed.columns:
        raise ValueError("Parquet file does not contain a date column.")
    if "close" not in renamed.columns:
        raise ValueError("Parquet file does not contain a close column.")

    renamed["date"] = pd.to_datetime(renamed["date"]).dt.date
    for price_column in ("open", "high", "low", "close"):
        if price_column not in renamed.columns:
            renamed[price_column] = renamed["close"]
        col = renamed[price_column]
        if not isinstance(col, pd.Series):
            col = pd.Series(col)
        col = col.apply(lambda x: x[0] if isinstance(x,(list, tuple, np.ndarray)) else x)
        renamed[price_column] = pd.to_numeric(col, errors="coerce")

    renamed = renamed.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates(subset=["date"], keep="last")
    renamed["open"] = renamed["open"].fillna(renamed["close"])
    renamed["high"] = renamed["high"].fillna(renamed[["open", "close"]].max(axis=1))
    renamed["low"] = renamed["low"].fillna(renamed[["open", "close"]].min(axis=1))
    return renamed.reset_index(drop=True)


def load_data(symbol: str, parquet_dir: Optional[Path], dry_run: bool = False) -> pd.DataFrame:
    """Load one symbol's daily parquet file and standardize its schema."""

    if dry_run:
        return build_mock_price_frame(symbol)

    if parquet_dir is None:
        raise ValueError("parquet_dir is required for real execution.")

    parquet_path = parquet_dir / f"{symbol.upper()}.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"Missing parquet file: {parquet_path}")

    frame = pd.read_parquet(parquet_path)
    standardized = standardize_ohlcv_columns(frame)
    standardized["code"] = symbol.upper()
    return standardized


def build_mock_price_frame(symbol: str, periods: int = 180) -> pd.DataFrame:
    """Build a deterministic synthetic OHLC frame for dry-run validation."""

    start = date(2024, 1, 2)
    rows: list[dict[str, Any]] = []
    for index in range(periods):
        base = 100.0 + index * 0.22 + math.sin(index / 5.0) * 4.5 + math.cos(index / 11.0) * 2.0
        close = round(base, 4)
        open_price = round(close * (1.0 + math.sin(index / 7.0) * 0.002), 4)
        high = round(max(open_price, close) * 1.008, 4)
        low = round(min(open_price, close) * 0.992, 4)
        rows.append(
            {
                "date": start.fromordinal(start.toordinal() + index),
                "code": symbol.upper(),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
            }
        )
    return pd.DataFrame(rows)


def dataframe_to_bars(symbol: str, frame: pd.DataFrame) -> list[SimpleNamespace]:
    """Convert a pandas DataFrame into the bar objects expected by the engine."""

    bars: list[SimpleNamespace] = []
    for row in frame.itertuples(index=False):
        bars.append(
            SimpleNamespace(
                code=symbol.upper(),
                date=row.date,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
            )
        )
    return bars


def build_strategy_definitions() -> dict[str, list[StrategyDefinition]]:
    """Return baseline strategies and sensitivity grids for supported families."""

    return {
        "moving_average_crossover": [
            StrategyDefinition(
                family="moving_average_crossover",
                label="ma-baseline",
                strategy_text="5日均线上穿20日均线买入，下穿卖出",
                parameters={"fast_period": 5, "slow_period": 20, "fast_type": "simple", "slow_type": "simple"},
                is_baseline=True,
            ),
            StrategyDefinition(
                family="moving_average_crossover",
                label="ma-3-15",
                strategy_text="3日均线上穿15日均线买入，下穿卖出",
                parameters={"fast_period": 3, "slow_period": 15, "fast_type": "simple", "slow_type": "simple"},
            ),
            StrategyDefinition(
                family="moving_average_crossover",
                label="ma-8-21",
                strategy_text="8日均线上穿21日均线买入，下穿卖出",
                parameters={"fast_period": 8, "slow_period": 21, "fast_type": "simple", "slow_type": "simple"},
            ),
            StrategyDefinition(
                family="moving_average_crossover",
                label="ma-10-30",
                strategy_text="10日均线上穿30日均线买入，下穿卖出",
                parameters={"fast_period": 10, "slow_period": 30, "fast_type": "simple", "slow_type": "simple"},
            ),
        ],
        "rsi_threshold": [
            StrategyDefinition(
                family="rsi_threshold",
                label="rsi-baseline",
                strategy_text="RSI14 小于 30 买入，RSI14 大于 70 卖出",
                parameters={"period": 14, "lower_threshold": 30.0, "upper_threshold": 70.0},
                is_baseline=True,
            ),
            StrategyDefinition(
                family="rsi_threshold",
                label="rsi-6-25-75",
                strategy_text="RSI6 小于 25 买入，RSI6 大于 75 卖出",
                parameters={"period": 6, "lower_threshold": 25.0, "upper_threshold": 75.0},
            ),
            StrategyDefinition(
                family="rsi_threshold",
                label="rsi-14-35-65",
                strategy_text="RSI14 小于 35 买入，RSI14 大于 65 卖出",
                parameters={"period": 14, "lower_threshold": 35.0, "upper_threshold": 65.0},
            ),
            StrategyDefinition(
                family="rsi_threshold",
                label="rsi-21-30-70",
                strategy_text="RSI21 小于 30 买入，RSI21 大于 70 卖出",
                parameters={"period": 21, "lower_threshold": 30.0, "upper_threshold": 70.0},
            ),
        ],
        "macd_crossover": [
            StrategyDefinition(
                family="macd_crossover",
                label="macd-baseline",
                strategy_text="MACD(12,26,9) 金叉买入，死叉卖出",
                parameters={"fast_period": 12, "slow_period": 26, "signal_period": 9},
                is_baseline=True,
            ),
            StrategyDefinition(
                family="macd_crossover",
                label="macd-8-21-5",
                strategy_text="MACD(8,21,5) 金叉买入，死叉卖出",
                parameters={"fast_period": 8, "slow_period": 21, "signal_period": 5},
            ),
            StrategyDefinition(
                family="macd_crossover",
                label="macd-10-30-9",
                strategy_text="MACD(10,30,9) 金叉买入，死叉卖出",
                parameters={"fast_period": 10, "slow_period": 30, "signal_period": 9},
            ),
            StrategyDefinition(
                family="macd_crossover",
                label="macd-5-35-5",
                strategy_text="MACD(5,35,5) 金叉买入，死叉卖出",
                parameters={"fast_period": 5, "slow_period": 35, "signal_period": 5},
            ),
        ],
    }


def normalize_parsed_strategy(
    parsed: ParsedStrategy,
    *,
    symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    initial_capital: float,
) -> ParsedStrategy:
    """Convert parser output into the canonical strategy spec consumed by the engine."""

    assumptions = list(parsed.assumptions or [])
    assumption_groups = list(parsed.assumption_groups or [])
    strategy_kind = str(parsed.strategy_kind or "")
    setup = dict(parsed.setup or {})

    if strategy_kind == "moving_average_crossover":
        strategy_spec = {
            "strategy_type": "moving_average_crossover",
            "strategy_family": "moving_average_crossover",
            "signal": {
                "indicator_family": "moving_average",
                "fast_period": int(setup.get("fast_period") or 5),
                "slow_period": int(setup.get("slow_period") or 20),
                "fast_type": str(setup.get("fast_type") or "simple"),
                "slow_type": str(setup.get("slow_type") or "simple"),
                "entry_condition": "fast_crosses_above_slow",
                "exit_condition": "fast_crosses_below_slow",
            },
            "capital": {"initial_capital": float(initial_capital)},
            "date_range": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
            "execution": {
                "signal_timing": "bar_close",
                "fill_timing": "next_bar_open",
                "price_basis": "open",
            },
            "support": {"executable": True, "normalization_state": "assumed"},
            "symbol": symbol.upper(),
        }
        assumptions.extend(
            [
                {"key": "fast_type", "value": strategy_spec["signal"]["fast_type"], "source": "default_or_inferred"},
                {"key": "slow_type", "value": strategy_spec["signal"]["slow_type"], "source": "default_or_inferred"},
            ]
        )
    elif strategy_kind == "rsi_threshold":
        strategy_spec = {
            "strategy_type": "rsi_threshold",
            "strategy_family": "rsi_threshold",
            "signal": {
                "indicator_family": "rsi",
                "period": int(setup.get("period") or 14),
                "lower_threshold": float(setup.get("lower_threshold") or 30.0),
                "upper_threshold": float(setup.get("upper_threshold") or 70.0),
            },
            "capital": {"initial_capital": float(initial_capital)},
            "date_range": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
            "execution": {
                "signal_timing": "bar_close",
                "fill_timing": "next_bar_open",
                "price_basis": "open",
            },
            "support": {"executable": True, "normalization_state": "assumed"},
            "symbol": symbol.upper(),
        }
        assumptions.append(
            {"key": "rsi_period", "value": strategy_spec["signal"]["period"], "source": "default_or_inferred"}
        )
    elif strategy_kind == "macd_crossover":
        strategy_spec = {
            "strategy_type": "macd_crossover",
            "strategy_family": "macd_crossover",
            "signal": {
                "indicator_family": "macd",
                "fast_period": int(setup.get("fast_period") or 12),
                "slow_period": int(setup.get("slow_period") or 26),
                "signal_period": int(setup.get("signal_period") or 9),
                "entry_condition": "macd_crosses_above_signal",
                "exit_condition": "macd_crosses_below_signal",
            },
            "capital": {"initial_capital": float(initial_capital)},
            "date_range": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
            "execution": {
                "signal_timing": "bar_close",
                "fill_timing": "next_bar_open",
                "price_basis": "open",
            },
            "support": {"executable": True, "normalization_state": "assumed"},
            "symbol": symbol.upper(),
        }
        assumptions.append(
            {
                "key": "macd_periods",
                "value": [
                    strategy_spec["signal"]["fast_period"],
                    strategy_spec["signal"]["slow_period"],
                    strategy_spec["signal"]["signal_period"],
                ],
                "source": "default_or_inferred",
            }
        )
        assumption_groups.append(
            {
                "key": "indicator_defaults",
                "summary": "使用标准 MACD 参数族。",
            }
        )
    else:
        raise ValueError(f"Unsupported strategy kind for P2 execution: {strategy_kind}")

    parsed.strategy_spec = strategy_spec
    parsed.executable = True
    parsed.normalization_state = "assumed"
    parsed.assumptions = assumptions
    parsed.assumption_groups = assumption_groups
    parsed.detected_strategy_family = strategy_kind
    return parsed


def build_execution_trace(
    result_payload: dict[str, Any],
    *,
    fallback_note: str = "local_parquet_p2",
) -> dict[str, Any]:
    """Build an execution-trace-like payload from the engine result."""

    execution_trace_rows: list[dict[str, Any]] = []
    raw_rows = result_payload.get("audit_ledger") or []
    assumptions = result_payload.get("parsed_strategy", {}).get("assumptions") or []
    assumptions_summary = "；".join(
        f"{item.get('key')}={item.get('value')}" for item in assumptions if item.get("key")
    ) or "无额外默认值"

    for row in raw_rows:
        execution_trace_rows.append(
            {
                "date": row.get("date"),
                "symbol_close": row.get("symbol_close"),
                "benchmark_close": row.get("benchmark_close"),
                "event_type": row.get("action") or "hold",
                "action": row.get("action") or "hold",
                "position": row.get("position"),
                "shares": row.get("shares"),
                "cash": row.get("cash"),
                "holdings_value": row.get("holdings_value"),
                "total_portfolio_value": row.get("total_portfolio_value"),
                "daily_pnl": row.get("daily_pnl"),
                "daily_return": row.get("daily_return"),
                "cumulative_return": row.get("cumulative_return"),
                "drawdown_pct": row.get("drawdown_pct"),
                "signal_summary": row.get("signal_summary"),
                "fill_price": row.get("fill_price"),
                "assumptions_defaults": assumptions_summary,
                "fallback": fallback_note,
                "notes": row.get("notes"),
            }
        )

    return {
        "source": "engine_audit_ledger",
        "rows": execution_trace_rows,
        "execution_model": result_payload.get("execution_model") or {},
        "execution_assumptions": result_payload.get("execution_assumptions") or {},
        "assumptions_defaults": {
            "items": assumptions,
            "summary_text": assumptions_summary,
        },
        "fallback": {
            "run_fallback": False,
            "trace_rebuilt": False,
            "note": fallback_note,
        },
    }


def extract_daily_return_series(audit_rows: Sequence[dict[str, Any]]) -> pd.Series:
    """Extract daily return decimals from audit rows."""

    series = pd.Series(
        [
            float(row.get("daily_return") or 0.0) / 100.0
            for row in audit_rows
            if row.get("date")
        ],
        dtype="float64",
    )
    if series.empty:
        return pd.Series(dtype="float64")
    return series.fillna(0.0)


def build_external_benchmark_series(
    benchmark_frame: pd.DataFrame,
    *,
    start_date: Optional[str],
    end_date: Optional[str],
) -> pd.Series:
    """Build aligned benchmark daily returns in decimal form."""

    frame = benchmark_frame.copy()
    if start_date:
        frame = frame[frame["date"] >= date.fromisoformat(start_date)]
    if end_date:
        frame = frame[frame["date"] <= date.fromisoformat(end_date)]
    if frame.empty:
        return pd.Series(dtype="float64")
    frame = frame.sort_values("date").copy()
    frame["return"] = frame["close"].pct_change().fillna(0.0)
    return pd.Series(frame["return"].to_list(), index=pd.Index(frame["date"].astype(str), dtype="object"))


def compute_profit_loss_ratio(trades: Sequence[dict[str, Any]]) -> Optional[float]:
    """Compute average-win over average-loss from trade returns."""

    positive_returns = [float(trade.get("return_pct") or 0.0) for trade in trades if float(trade.get("return_pct") or 0.0) > 0]
    negative_returns = [abs(float(trade.get("return_pct") or 0.0)) for trade in trades if float(trade.get("return_pct") or 0.0) < 0]
    if not positive_returns or not negative_returns:
        return None
    return round(mean(positive_returns) / mean(negative_returns), 6)


def compute_kpis(
    *,
    summary_metrics: dict[str, Any],
    trades: Sequence[dict[str, Any]],
    audit_rows: Sequence[dict[str, Any]],
    benchmark_returns: pd.Series,
) -> dict[str, Any]:
    """Compute the compare payload KPI set required by P2."""

    strategy_returns = extract_daily_return_series(audit_rows)
    if strategy_returns.empty:
        return {
            "volatility_pct": None,
            "sortino_ratio": None,
            "calmar_ratio": None,
            "alpha_pct": None,
            "beta": None,
            "sharpe_ratio": None,
            "max_drawdown_pct": summary_metrics.get("max_drawdown_pct"),
            "win_rate_pct": summary_metrics.get("win_rate_pct"),
            "avg_holding_period_days": summary_metrics.get("avg_holding_calendar_days"),
            "profit_loss_ratio": compute_profit_loss_ratio(trades),
        }

    volatility = strategy_returns.std(ddof=0) * math.sqrt(252) * 100.0 if len(strategy_returns) > 1 else 0.0
    downside_returns = strategy_returns[strategy_returns < 0]
    downside_std = downside_returns.std(ddof=0) if not downside_returns.empty else 0.0
    mean_return = strategy_returns.mean()
    sharpe_ratio = None if strategy_returns.std(ddof=0) == 0 else (mean_return / strategy_returns.std(ddof=0)) * math.sqrt(252)
    sortino_ratio = None if downside_std == 0 else (mean_return / downside_std) * math.sqrt(252)

    annualized_return_pct = summary_metrics.get("annualized_return_pct")
    max_drawdown_pct = summary_metrics.get("max_drawdown_pct")
    calmar_ratio = None
    if annualized_return_pct is not None and max_drawdown_pct not in (None, 0):
        calmar_ratio = round(float(annualized_return_pct) / float(max_drawdown_pct), 6)

    alpha_pct: Optional[float] = None
    beta: Optional[float] = None
    if not benchmark_returns.empty:
        strategy_index = pd.Index([str(row.get("date")) for row in audit_rows if row.get("date")], dtype="object")
        strategy_series = pd.Series(strategy_returns.to_list(), index=strategy_index)
        aligned = pd.concat(
            [strategy_series.rename("strategy"), benchmark_returns.rename("benchmark")],
            axis=1,
            join="inner",
        ).dropna()
        if not aligned.empty and aligned["benchmark"].var(ddof=0) != 0:
            covariance = aligned["strategy"].cov(aligned["benchmark"])
            variance = aligned["benchmark"].var(ddof=0)
            beta = round(float(covariance / variance), 6)
            alpha_daily = float(aligned["strategy"].mean()) - float(beta) * float(aligned["benchmark"].mean())
            alpha_pct = round(alpha_daily * 252 * 100.0, 6)

    return {
        "volatility_pct": round(volatility, 6),
        "sortino_ratio": round(sortino_ratio, 6) if sortino_ratio is not None else None,
        "calmar_ratio": calmar_ratio,
        "alpha_pct": alpha_pct,
        "beta": beta,
        "sharpe_ratio": round(sharpe_ratio, 6) if sharpe_ratio is not None else None,
        "max_drawdown_pct": summary_metrics.get("max_drawdown_pct"),
        "win_rate_pct": summary_metrics.get("win_rate_pct"),
        "avg_holding_period_days": summary_metrics.get("avg_holding_calendar_days"),
        "profit_loss_ratio": compute_profit_loss_ratio(trades),
    }


def build_summary_payload(
    *,
    symbol: str,
    strategy: StrategyDefinition,
    result_payload: dict[str, Any],
    metadata: dict[str, Any],
    compare_kpis: dict[str, Any],
) -> dict[str, Any]:
    """Build a compact, parseable summary JSON for one run."""

    return {
        "symbol": symbol.upper(),
        "strategy_family": strategy.family,
        "strategy_label": strategy.label,
        "strategy_text": strategy.strategy_text,
        "parameters": strategy.parameters,
        "metadata": metadata,
        "metrics": result_payload.get("metrics") or {},
        "compare_kpis": compare_kpis,
        "benchmark_summary": result_payload.get("benchmark_summary") or {},
        "buy_and_hold_summary": result_payload.get("buy_and_hold_summary") or {},
        "warnings": result_payload.get("warnings") or [],
        "no_result_reason": result_payload.get("no_result_reason"),
        "no_result_message": result_payload.get("no_result_message"),
    }


def validate_run_payload(execution_trace: dict[str, Any], summary_payload: dict[str, Any]) -> None:
    """Validate the required run payload invariants before persisting artifacts."""

    trace_rows = execution_trace.get("rows") or []
    if len(trace_rows) <= 0:
        raise ValueError("execution_trace length must be greater than zero.")

    serialized_summary = json.dumps(summary_payload, ensure_ascii=False, default=json_default)
    parsed_summary = json.loads(serialized_summary)
    if not isinstance(parsed_summary, dict) or not parsed_summary:
        raise ValueError("summary_json must be present and parseable.")


def validate_compare_payload(compare_payload: dict[str, Any]) -> None:
    """Validate that compare payloads expose the expected KPI fields."""

    missing_fields = REQUIRED_COMPARE_KPI_FIELDS - set(compare_payload.get("expected_kpi_fields") or [])
    if missing_fields:
        raise ValueError(f"compare JSON missing expected KPI metadata fields: {sorted(missing_fields)}")

    run_rows = compare_payload.get("runs") or []
    for row in run_rows:
        kpis = row.get("kpis") or {}
        for field_name in REQUIRED_COMPARE_KPI_FIELDS:
            if field_name not in kpis:
                raise ValueError(f"compare JSON missing KPI field '{field_name}' in run row.")


def build_metadata(
    *,
    benchmark_symbol: str,
    run_tag: str,
    strategy_label: str,
    parsed_strategy: ParsedStrategy,
    result_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build shared metadata for artifacts and summaries."""

    execution_model = result_payload.get("execution_model") or {}
    return {
        "symbol": result_payload.get("symbol"),
        "strategy_label": strategy_label,
        "strategy_version": parsed_strategy.version,
        "parse_version": parsed_strategy.version,
        "engine_version": execution_model.get("version") or "v1",
        "run_tag": run_tag,
        "benchmark_symbol": benchmark_symbol,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def load_p1_helper() -> Optional[Callable[..., Any]]:
    """Load an existing P1 automation helper if the repository exposes one."""

    try:
        from src.services import rule_backtest_service as p1_module
    except Exception:
        return None

    for helper_name in ("parse_and_run_automated", "run_backtest_automated"):
        helper = getattr(p1_module, helper_name, None)
        if callable(helper):
            return helper
    return None


def maybe_run_via_p1_helper(
    helper: Optional[Callable[..., Any]],
    *,
    symbol: str,
    strategy_text: str,
    initial_capital: float,
    start_date: Optional[date],
    end_date: Optional[date],
) -> Optional[dict[str, Any]]:
    """Attempt to reuse a P1 helper if the local repository exposes a compatible one."""

    if helper is None:
        return None

    try:
        signature = inspect.signature(helper)
        call_kwargs: dict[str, Any] = {}
        if "code" in signature.parameters:
            call_kwargs["code"] = symbol
        elif "symbol" in signature.parameters:
            call_kwargs["symbol"] = symbol
        else:
            return None

        if "strategy_text" in signature.parameters:
            call_kwargs["strategy_text"] = strategy_text
        if "initial_capital" in signature.parameters:
            call_kwargs["initial_capital"] = initial_capital
        if "start_date" in signature.parameters and start_date is not None:
            call_kwargs["start_date"] = start_date.isoformat()
        if "end_date" in signature.parameters and end_date is not None:
            call_kwargs["end_date"] = end_date.isoformat()
        if "confirmed" in signature.parameters:
            call_kwargs["confirmed"] = True

        response = helper(**call_kwargs)
        if isinstance(response, dict) and response:
            return response
    except Exception:
        LOGGER.warning("Existing P1 helper is present but incompatible for this run; falling back to engine execution.")
    return None


def execute_engine_run(
    *,
    symbol: str,
    strategy: StrategyDefinition,
    frame: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    config: RunnerConfig,
    p1_helper: Optional[Callable[..., Any]],
) -> tuple[dict[str, Any], ParsedStrategy]:
    """Run one deterministic strategy via P1 helper or direct parser+engine fallback."""

    p1_response = maybe_run_via_p1_helper(
        p1_helper,
        symbol=symbol,
        strategy_text=strategy.strategy_text,
        initial_capital=config.initial_capital,
        start_date=config.start_date,
        end_date=config.end_date,
    )
    if p1_response is not None and "metrics" in p1_response:
        parsed_strategy = RuleBacktestParser().parse(strategy.strategy_text)
        parsed_strategy = normalize_parsed_strategy(
            parsed_strategy,
            symbol=symbol,
            start_date=config.start_date,
            end_date=config.end_date,
            initial_capital=config.initial_capital,
        )
        return p1_response, parsed_strategy

    parser = RuleBacktestParser()
    parsed_strategy = parser.parse(strategy.strategy_text)
    parsed_strategy = normalize_parsed_strategy(
        parsed_strategy,
        symbol=symbol,
        start_date=config.start_date,
        end_date=config.end_date,
        initial_capital=config.initial_capital,
    )

    bars = dataframe_to_bars(symbol, frame)
    engine = RuleBacktestEngine()
    result = engine.run(
        code=symbol,
        parsed_strategy=parsed_strategy,
        bars=bars,
        initial_capital=config.initial_capital,
        lookback_bars=len(bars),
        start_date=config.start_date,
        end_date=config.end_date,
    )
    result_payload = result.to_dict()
    if not result_payload.get("audit_ledger"):
        result_payload["audit_ledger"] = [
            row.to_dict()
            for row in RuleBacktestEngine._build_audit_ledger(
                equity_curve=result_payload.get("equity_curve") or [],
                benchmark_curve=result_payload.get("benchmark_curve") or [],
                buy_and_hold_curve=result_payload.get("buy_and_hold_curve") or [],
                benchmark_summary=result_payload.get("benchmark_summary") or {},
            )
        ]
    result_payload["symbol"] = symbol
    result_payload["benchmark_symbol"] = config.benchmark_symbol
    result_payload["external_benchmark_available"] = bool(not benchmark_frame.empty)
    return result_payload, parsed_strategy


def build_mock_result_payload(
    *,
    symbol: str,
    strategy: StrategyDefinition,
    config: RunnerConfig,
) -> tuple[dict[str, Any], ParsedStrategy]:
    """Build a synthetic deterministic payload for dry-run mode."""

    frame = build_mock_price_frame(symbol, periods=90)
    parser = RuleBacktestParser()
    parsed_strategy = normalize_parsed_strategy(
        parser.parse(strategy.strategy_text),
        symbol=symbol,
        start_date=config.start_date,
        end_date=config.end_date,
        initial_capital=config.initial_capital,
    )
    audit_rows: list[dict[str, Any]] = []
    total_portfolio_value = config.initial_capital
    previous_value = total_portfolio_value
    for index, row in enumerate(frame.itertuples(index=False)):
        drift = (math.sin(index / 6.0) + 0.5) * 0.012
        total_portfolio_value = round(total_portfolio_value * (1.0 + drift), 6)
        action = "buy" if index in (5, 25, 55) else "sell" if index in (15, 40, 70) else "hold"
        daily_pnl = round(total_portfolio_value - previous_value, 6)
        daily_return = round((daily_pnl / previous_value) * 100.0 if previous_value else 0.0, 6)
        cumulative_return = round(((total_portfolio_value / config.initial_capital) - 1.0) * 100.0, 6)
        audit_rows.append(
            {
                "date": row.date.isoformat(),
                "symbol_close": row.close,
                "benchmark_close": row.close * 0.995,
                "position": 1.0 if index % 20 < 12 else 0.0,
                "shares": 100.0 if index % 20 < 12 else 0.0,
                "cash": round(total_portfolio_value * 0.3, 6),
                "holdings_value": round(total_portfolio_value * 0.7, 6),
                "total_portfolio_value": total_portfolio_value,
                "daily_pnl": daily_pnl,
                "daily_return": daily_return,
                "cumulative_return": cumulative_return,
                "benchmark_cumulative_return": round(cumulative_return * 0.82, 6),
                "buy_hold_cumulative_return": round(cumulative_return * 0.9, 6),
                "action": action,
                "fill_price": row.open,
                "signal_summary": strategy.strategy_text,
                "drawdown_pct": round(abs(min(0.0, -math.sin(index / 12.0) * 8.0)), 6),
                "notes": "dry_run_mock",
            }
        )
        previous_value = total_portfolio_value

    metrics = {
        "initial_capital": config.initial_capital,
        "final_equity": total_portfolio_value,
        "total_return_pct": round(((total_portfolio_value / config.initial_capital) - 1.0) * 100.0, 6),
        "annualized_return_pct": 18.5,
        "benchmark_return_pct": 13.2,
        "excess_return_vs_benchmark_pct": 5.3,
        "buy_and_hold_return_pct": 13.2,
        "excess_return_vs_buy_and_hold_pct": 5.3,
        "trade_count": 6,
        "entry_signal_count": 6,
        "win_count": 4,
        "loss_count": 2,
        "win_rate_pct": 66.6667,
        "avg_trade_return_pct": 4.2,
        "max_drawdown_pct": 9.1,
        "avg_holding_days": 7.5,
        "avg_holding_bars": 7.5,
        "avg_holding_calendar_days": 7.5,
        "bars_used": len(audit_rows),
        "lookback_bars": len(audit_rows),
        "period_start": audit_rows[0]["date"],
        "period_end": audit_rows[-1]["date"],
    }
    result_payload = {
        "symbol": symbol,
        "parsed_strategy": parsed_strategy.to_dict(),
        "execution_model": {
            "version": "v1",
            "timeframe": "daily",
            "signal_evaluation_timing": "bar_close",
            "entry_timing": "next_bar_open",
            "exit_timing": "next_bar_open",
            "entry_fill_price_basis": "open",
            "exit_fill_price_basis": "open",
        },
        "execution_assumptions": {
            "timeframe": "daily",
            "signal_evaluation_timing": "bar_close",
            "entry_fill_timing": "next_bar_open",
            "exit_fill_timing": "next_bar_open",
            "position_sizing": "single_position_full_notional",
        },
        "trades": [
            {
                "code": symbol,
                "entry_date": audit_rows[5]["date"],
                "exit_date": audit_rows[15]["date"],
                "return_pct": 5.8,
                "holding_bars": 10,
                "holding_calendar_days": 10,
            },
            {
                "code": symbol,
                "entry_date": audit_rows[25]["date"],
                "exit_date": audit_rows[40]["date"],
                "return_pct": -2.1,
                "holding_bars": 15,
                "holding_calendar_days": 15,
            },
            {
                "code": symbol,
                "entry_date": audit_rows[55]["date"],
                "exit_date": audit_rows[70]["date"],
                "return_pct": 8.9,
                "holding_bars": 15,
                "holding_calendar_days": 15,
            },
        ],
        "audit_ledger": audit_rows,
        "equity_curve": [],
        "benchmark_curve": [],
        "benchmark_summary": {
            "label": "External benchmark",
            "code": config.benchmark_symbol,
            "return_pct": 13.2,
        },
        "buy_and_hold_curve": [],
        "buy_and_hold_summary": {
            "label": "Buy and hold",
            "return_pct": 13.2,
        },
        "metrics": metrics,
        "warnings": [],
        "no_result_reason": None,
        "no_result_message": None,
    }
    return result_payload, parsed_strategy


def _build_ai_summary(
    *,
    symbol: str,
    strategy_label: str,
    summary_payload: dict[str, Any],
    sensitivity_payload: dict[str, Any],
    compare_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build a local AI-style summary payload from deterministic results."""

    metrics = summary_payload.get("metrics") or {}
    best_by_sharpe = compare_payload.get("best_runs", {}).get("best_sharpe") or {}
    family_highlights = sensitivity_payload.get("highlights") or {}
    summary_text = (
        f"{symbol} / {strategy_label} 回测显示总收益 {metrics.get('total_return_pct')}%，"
        f"年化 {metrics.get('annualized_return_pct')}%，最大回撤 {metrics.get('max_drawdown_pct')}%，"
        f"胜率 {metrics.get('win_rate_pct')}%。"
    )
    if best_by_sharpe:
        summary_text += (
            f" 对比结果中 Sharpe 最优配置为 {best_by_sharpe.get('strategy_label')} "
            f"({best_by_sharpe.get('kpis', {}).get('sharpe_ratio')})。"
        )
    if family_highlights:
        summary_text += (
            f" 敏感性分析提示 {family_highlights.get('headline')}。"
        )
    return {
        "provider": "local_rule_based_summary",
        "summary_text": summary_text,
        "key_metrics": {
            "total_return_pct": metrics.get("total_return_pct"),
            "annualized_return_pct": metrics.get("annualized_return_pct"),
            "max_drawdown_pct": metrics.get("max_drawdown_pct"),
            "win_rate_pct": metrics.get("win_rate_pct"),
            "sharpe_ratio": summary_payload.get("compare_kpis", {}).get("sharpe_ratio"),
            "sortino_ratio": summary_payload.get("compare_kpis", {}).get("sortino_ratio"),
        },
        "sensitivity_highlights": family_highlights,
        "compare_highlights": compare_payload.get("best_runs") or {},
    }


def generate_ai_summary(
    *,
    symbol: str,
    strategy_label: str,
    summary_payload: dict[str, Any],
    sensitivity_payload: dict[str, Any],
    compare_payload: dict[str, Any],
) -> dict[str, Any]:
    """Call the real summary builder for this module."""

    return _build_ai_summary(
        symbol=symbol,
        strategy_label=strategy_label,
        summary_payload=summary_payload,
        sensitivity_payload=sensitivity_payload,
        compare_payload=compare_payload,
    )


def persist_run_artifact(artifact: RunArtifact) -> None:
    """Persist run JSON artifacts to the configured output directory."""

    ensure_directory(artifact.output_dir)
    write_json(artifact.output_dir / "execution_trace.json", artifact.execution_trace)
    write_json(artifact.output_dir / "summary.json", artifact.summary)
    write_json(artifact.output_dir / "ai_summary.json", artifact.ai_summary)
    write_json(
        artifact.output_dir / "run.json",
        {
            "status": artifact.status,
            "symbol": artifact.symbol,
            "strategy_family": artifact.strategy_family,
            "strategy_label": artifact.strategy_label,
            "strategy_text": artifact.strategy_text,
            "parameters": artifact.parameters,
            "metadata": artifact.metadata,
            "metrics": artifact.metrics,
            "error": artifact.error,
        },
    )


def build_sensitivity_payload(symbol: str, family: str, runs: Sequence[RunArtifact]) -> dict[str, Any]:
    """Build sensitivity summary JSON for one symbol and one strategy family."""

    ordered_runs = sorted(runs, key=lambda item: item.metrics.get("total_return_pct") or float("-inf"), reverse=True)
    best_run = ordered_runs[0] if ordered_runs else None
    worst_run = ordered_runs[-1] if ordered_runs else None
    headline = "无可用结果"
    if best_run and worst_run:
        headline = (
            f"{family} 参数敏感性中最佳为 {best_run.strategy_label}"
            f"（总收益 {best_run.metrics.get('total_return_pct')}%），"
            f"最弱为 {worst_run.strategy_label}"
            f"（总收益 {worst_run.metrics.get('total_return_pct')}%）。"
        )
    return {
        "symbol": symbol,
        "strategy_family": family,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_count": len(runs),
        "highlights": {
            "headline": headline,
            "best_total_return": best_run.summary if best_run else None,
            "worst_total_return": worst_run.summary if worst_run else None,
        },
        "runs": [
            {
                "strategy_label": run.strategy_label,
                "parameters": run.parameters,
                "metrics": run.metrics,
                "metadata": run.metadata,
            }
            for run in ordered_runs
        ],
    }


def compare_runs(
    *,
    symbol: str,
    baseline_runs: Sequence[RunArtifact],
    sensitivity_payloads: Sequence[dict[str, Any]],
    benchmark_symbol: str,
    run_tag: str,
) -> dict[str, Any]:
    """Build compare JSON across all strategies and sensitivity runs for one symbol."""

    comparison_rows = []
    for run in baseline_runs:
        comparison_rows.append(
            {
                "symbol": symbol,
                "strategy_family": run.strategy_family,
                "strategy_label": run.strategy_label,
                "parameters": run.parameters,
                "metrics": run.metrics,
                "kpis": run.summary.get("compare_kpis") or {},
                "metadata": run.metadata,
            }
        )

    best_total_return = max(
        comparison_rows,
        key=lambda row: row.get("metrics", {}).get("total_return_pct") or float("-inf"),
        default=None,
    )
    best_sharpe = max(
        comparison_rows,
        key=lambda row: row.get("kpis", {}).get("sharpe_ratio") or float("-inf"),
        default=None,
    )
    best_sortino = max(
        comparison_rows,
        key=lambda row: row.get("kpis", {}).get("sortino_ratio") or float("-inf"),
        default=None,
    )

    compare_payload = {
        "symbol": symbol,
        "benchmark_symbol": benchmark_symbol,
        "run_tag": run_tag,
        "generated_at": datetime.now(UTC).isoformat(),
        "expected_kpi_fields": sorted(REQUIRED_COMPARE_KPI_FIELDS),
        "runs": comparison_rows,
        "best_runs": {
            "best_total_return": best_total_return,
            "best_sharpe": best_sharpe,
            "best_sortino": best_sortino,
        },
        "sensitivity": list(sensitivity_payloads),
    }
    validate_compare_payload(compare_payload)
    return compare_payload


def process_strategy_family(
    *,
    symbol: str,
    family: str,
    strategies: Sequence[StrategyDefinition],
    frame: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    config: RunnerConfig,
    p1_helper: Optional[Callable[..., Any]],
    compare_payload_stub: Optional[dict[str, Any]] = None,
) -> tuple[list[RunArtifact], dict[str, Any]]:
    """Run a strategy family across baseline and sensitivity parameters."""

    family_runs: list[RunArtifact] = []
    benchmark_returns = build_external_benchmark_series(
        benchmark_frame,
        start_date=config.start_date.isoformat() if config.start_date else None,
        end_date=config.end_date.isoformat() if config.end_date else None,
    )

    for strategy in strategies:
        LOGGER.info("Processing %s / %s", symbol, strategy.label)
        run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{strategy.label}"
        output_dir = config.output_root / "runs" / f"{symbol}-{strategy.label}-{run_id}"
        try:
            if config.dry_run:
                result_payload, parsed_strategy = build_mock_result_payload(
                    symbol=symbol,
                    strategy=strategy,
                    config=config,
                )
            else:
                result_payload, parsed_strategy = execute_engine_run(
                    symbol=symbol,
                    strategy=strategy,
                    frame=frame,
                    benchmark_frame=benchmark_frame,
                    config=config,
                    p1_helper=p1_helper,
                )

            compare_kpis = compute_kpis(
                summary_metrics=result_payload.get("metrics") or {},
                trades=result_payload.get("trades") or [],
                audit_rows=result_payload.get("audit_ledger") or [],
                benchmark_returns=benchmark_returns,
            )
            metadata = build_metadata(
                benchmark_symbol=config.benchmark_symbol,
                run_tag=config.run_tag,
                strategy_label=strategy.label,
                parsed_strategy=parsed_strategy,
                result_payload=result_payload,
            )
            execution_trace = build_execution_trace(result_payload)
            summary_payload = build_summary_payload(
                symbol=symbol,
                strategy=strategy,
                result_payload=result_payload,
                metadata=metadata,
                compare_kpis=compare_kpis,
            )
            validate_run_payload(execution_trace, summary_payload)
            ai_summary = generate_ai_summary(
                symbol=symbol,
                strategy_label=strategy.label,
                summary_payload=summary_payload,
                sensitivity_payload={"highlights": {"headline": "等待 family compare 完成"}},
                compare_payload=compare_payload_stub or {"best_runs": {}},
            )

            artifact = RunArtifact(
                symbol=symbol,
                strategy_family=family,
                strategy_label=strategy.label,
                strategy_text=strategy.strategy_text,
                parameters=strategy.parameters,
                run_id=run_id,
                output_dir=output_dir,
                metadata=metadata,
                summary=summary_payload,
                execution_trace=execution_trace,
                metrics=result_payload.get("metrics") or {},
                ai_summary=ai_summary,
            )
            persist_run_artifact(artifact)
            family_runs.append(artifact)
        except Exception as exc:
            LOGGER.exception("Strategy run failed: %s / %s", symbol, strategy.label)
            failed_artifact = RunArtifact(
                symbol=symbol,
                strategy_family=family,
                strategy_label=strategy.label,
                strategy_text=strategy.strategy_text,
                parameters=strategy.parameters,
                run_id=run_id,
                output_dir=output_dir,
                metadata={
                    "run_tag": config.run_tag,
                    "benchmark_symbol": config.benchmark_symbol,
                    "generated_at": datetime.now(UTC).isoformat(),
                },
                summary={},
                execution_trace={"rows": []},
                metrics={},
                ai_summary={},
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            ensure_directory(output_dir)
            write_json(
                output_dir / "run_error.json",
                {
                    "symbol": symbol,
                    "strategy_family": family,
                    "strategy_label": strategy.label,
                    "error": failed_artifact.error,
                    "traceback": traceback.format_exc(),
                },
            )

    sensitivity_payload = build_sensitivity_payload(symbol, family, family_runs)
    sensitivity_dir = config.output_root / "sensitivity" / f"{symbol}-{family}"
    ensure_directory(sensitivity_dir)
    write_json(sensitivity_dir / "sensitivity.json", sensitivity_payload)
    return family_runs, sensitivity_payload


def refresh_family_ai_summaries(
    *,
    symbol: str,
    family_runs: Sequence[RunArtifact],
    sensitivity_payload: dict[str, Any],
    compare_payload: dict[str, Any],
) -> None:
    """Regenerate and persist AI summaries once compare payloads are available."""

    for artifact in family_runs:
        artifact.ai_summary = generate_ai_summary(
            symbol=symbol,
            strategy_label=artifact.strategy_label,
            summary_payload=artifact.summary,
            sensitivity_payload=sensitivity_payload,
            compare_payload=compare_payload,
        )
        write_json(artifact.output_dir / "ai_summary.json", artifact.ai_summary)


def process_symbol(
    symbol: str,
    *,
    config: RunnerConfig,
    strategy_groups: dict[str, list[StrategyDefinition]],
    p1_helper: Optional[Callable[..., Any]],
) -> SymbolExecutionResult:
    """Process one symbol across baseline runs, sensitivity, compare, and AI summary."""

    LOGGER.info("Starting symbol %s", symbol)
    result = SymbolExecutionResult(symbol=symbol)

    try:
        frame = load_data(symbol, config.parquet_dir, dry_run=config.dry_run)
    except FileNotFoundError:
        LOGGER.warning("Skipping %s because the parquet file is missing.", symbol)
        result.skipped = True
        result.skip_reason = "missing_parquet"
        return result
    except Exception as exc:
        LOGGER.exception("Failed to load data for %s", symbol)
        result.failure_count += 1
        result.errors.append(f"load_data failed: {type(exc).__name__}: {exc}")
        return result

    benchmark_frame = frame if symbol == config.benchmark_symbol else load_data(
        config.benchmark_symbol,
        config.parquet_dir,
        dry_run=config.dry_run,
    )

    for family, strategies in strategy_groups.items():
        try:
            family_runs, sensitivity_payload = process_strategy_family(
                symbol=symbol,
                family=family,
                strategies=strategies,
                frame=frame,
                benchmark_frame=benchmark_frame,
                config=config,
                p1_helper=p1_helper,
            )
            result.baseline_runs.extend(family_runs)
            result.sensitivity_payloads.append(sensitivity_payload)
            result.success_count += len(family_runs)
            result.failure_count += max(0, len(strategies) - len(family_runs))
        except Exception as exc:
            LOGGER.exception("Family execution failed: %s / %s", symbol, family)
            result.failure_count += len(strategies)
            result.errors.append(f"{family} failed: {type(exc).__name__}: {exc}")

    if result.baseline_runs:
        compare_payload = compare_runs(
            symbol=symbol,
            baseline_runs=result.baseline_runs,
            sensitivity_payloads=result.sensitivity_payloads,
            benchmark_symbol=config.benchmark_symbol,
            run_tag=config.run_tag,
        )
        compare_dir = config.output_root / "compare" / symbol
        ensure_directory(compare_dir)
        write_json(compare_dir / "compare.json", compare_payload)
        result.compare_payload = compare_payload

        for sensitivity_payload in result.sensitivity_payloads:
            family = str(sensitivity_payload.get("strategy_family") or "")
            family_runs = [artifact for artifact in result.baseline_runs if artifact.strategy_family == family]
            refresh_family_ai_summaries(
                symbol=symbol,
                family_runs=family_runs,
                sensitivity_payload=sensitivity_payload,
                compare_payload=compare_payload,
            )

    return result


def build_runner_config(args: argparse.Namespace) -> RunnerConfig:
    """Build the validated runner config from parsed CLI arguments."""

    parquet_dir = resolve_local_parquet_dir(args.parquet_dir)
    symbols, missing_symbols = resolve_symbols(
        parquet_dir,
        requested_symbols=(args.symbols.split(",") if args.symbols else []),
        dry_run=args.dry_run,
    )
    for symbol in missing_symbols:
        LOGGER.warning("Requested symbol %s was skipped because its parquet file is missing.", symbol)
    if not symbols:
        raise ValueError("No executable symbols were resolved from the local parquet directory.")

    benchmark_symbol = resolve_benchmark_symbol(args.benchmark_symbol, symbols)
    if args.benchmark_symbol and args.benchmark_symbol.strip().upper() != benchmark_symbol:
        LOGGER.warning(
            "Benchmark symbol %s is unavailable. Falling back to %s.",
            args.benchmark_symbol.strip().upper(),
            benchmark_symbol,
        )

    output_root = Path(args.output_root or DEFAULT_OUTPUT_ROOT).expanduser().resolve()
    ensure_directory(output_root)
    ensure_directory(output_root / "runs")
    ensure_directory(output_root / "sensitivity")
    ensure_directory(output_root / "compare")

    max_workers = max(1, min(int(args.max_workers or 1), len(symbols)))
    run_tag = args.run_tag or datetime.now(UTC).strftime("p2-%Y%m%dT%H%M%SZ")

    return RunnerConfig(
        parquet_dir=parquet_dir,
        output_root=output_root,
        symbols=symbols,
        benchmark_symbol=benchmark_symbol,
        initial_capital=float(args.initial_capital or DEFAULT_INITIAL_CAPITAL),
        start_date=parse_date_or_none(args.start_date),
        end_date=parse_date_or_none(args.end_date),
        max_workers=max_workers,
        dry_run=bool(args.dry_run),
        run_tag=run_tag,
    )


def summarize_results(results: Sequence[SymbolExecutionResult]) -> dict[str, Any]:
    """Build an end-of-run summary for logs and artifact persistence."""

    summary = {
        "symbol_count": len(results),
        "success_symbols": sum(1 for item in results if not item.skipped and item.failure_count == 0),
        "partial_failure_symbols": sum(1 for item in results if not item.skipped and item.failure_count > 0),
        "skipped_symbols": sum(1 for item in results if item.skipped),
        "success_runs": sum(item.success_count for item in results),
        "failed_runs": sum(item.failure_count for item in results),
        "symbols": [
            {
                "symbol": item.symbol,
                "success_count": item.success_count,
                "failure_count": item.failure_count,
                "skipped": item.skipped,
                "skip_reason": item.skip_reason,
                "errors": item.errors,
            }
            for item in results
        ],
    }
    return summary


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for the P2 batch runner."""

    parser = argparse.ArgumentParser(description="Run WolfyStock P2 local-parquet backtests.")
    parser.add_argument("--symbols", default="", help="Comma-separated symbol list. Defaults to all parquet files.")
    parser.add_argument("--benchmark-symbol", default="", help="Optional benchmark symbol. Defaults to the first resolved symbol.")
    parser.add_argument("--parquet-dir", default="", help="Override LOCAL_US_PARQUET_DIR/US_STOCK_PARQUET_DIR.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Artifact root directory.")
    parser.add_argument("--initial-capital", type=float, default=DEFAULT_INITIAL_CAPITAL, help="Initial capital per run.")
    parser.add_argument("--start-date", default="", help="Optional ISO start date.")
    parser.add_argument("--end-date", default="", help="Optional ISO end date.")
    parser.add_argument("--max-workers", type=int, default=max(1, min(os.cpu_count() or 1, 4)), help="Parallel symbol workers.")
    parser.add_argument("--dry-run", action="store_true", help="Execute the full pipeline with mocked outputs.")
    parser.add_argument("--run-tag", default="", help="Optional run tag recorded in metadata.")
    return parser.parse_args(argv)


def run(argv: Optional[Sequence[str]] = None) -> int:
    """Run the full P2 execution pipeline."""

    configure_logging()
    args = parse_args(argv)
    config = build_runner_config(args)
    strategy_groups = build_strategy_definitions()
    p1_helper = load_p1_helper()

    LOGGER.info(
        "WolfyStock P2 start: symbols=%s benchmark=%s dry_run=%s output=%s",
        ",".join(config.symbols),
        config.benchmark_symbol,
        config.dry_run,
        config.output_root,
    )

    results: list[SymbolExecutionResult] = []
    if config.max_workers == 1:
        for symbol in config.symbols:
            results.append(
                process_symbol(
                    symbol,
                    config=config,
                    strategy_groups=strategy_groups,
                    p1_helper=p1_helper,
                )
            )
    else:
        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            futures = {
                executor.submit(
                    process_symbol,
                    symbol,
                    config=config,
                    strategy_groups=strategy_groups,
                    p1_helper=p1_helper,
                ): symbol
                for symbol in config.symbols
            }
            for future in as_completed(futures):
                results.append(future.result())

    summary = summarize_results(results)
    write_json(config.output_root / "run_summary.json", summary)
    LOGGER.info(
        "WolfyStock P2 finished: success_runs=%s failed_runs=%s skipped_symbols=%s",
        summary["success_runs"],
        summary["failed_runs"],
        summary["skipped_symbols"],
    )
    return 0 if summary["failed_runs"] == 0 else 1


def main() -> int:
    """CLI entry point."""

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
