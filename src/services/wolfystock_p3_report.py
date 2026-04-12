"""WolfyStock P3 report generator for local P2 outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import mean
from typing import Any, Optional

import pandas as pd

LOGGER = logging.getLogger(__name__)

DEFAULT_OUTPUT_ROOT = Path("backtest_outputs") / "p3"
PIPELINE_VERSION = "p3.1"
NUMERIC_FINGERPRINT_FIELDS = [
    "total_return_pct",
    "daily_return_pct",
    "volatility_pct",
    "max_drawdown_pct",
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "alpha_pct",
    "beta",
    "win_rate_pct",
    "avg_position_duration_days",
    "profit_loss_ratio",
    "trade_count",
    "annualized_return_pct",
]


@dataclass(frozen=True)
class P2RunRecord:
    """One parsed run from the P2 output directory."""

    symbol: str
    strategy_family: str
    strategy_label: str
    run_id: str
    run_dir: Path
    metadata: dict[str, Any]
    run_json: dict[str, Any]
    summary_json: dict[str, Any]
    execution_trace: dict[str, Any]
    ai_summary_json: dict[str, Any]


@dataclass
class P2Dataset:
    """Complete parsed P2 dataset required by the P3 generator."""

    p2_output_root: Path
    run_summary: dict[str, Any]
    runs: list[P2RunRecord] = field(default_factory=list)
    sensitivity_payloads: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    compare_payloads: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class ReportContext:
    """Normalized runtime context for the P3 report workflow."""

    p2_output_root: Path
    output_root: Path
    run_tag: str
    dry_run: bool
    generated_at: str
    compatibility_root: Path


@dataclass(frozen=True)
class DedupeConflict:
    """Conflicting duplicate record group detected during deduplication."""

    dedupe_key: str
    symbol: str
    strategy_family: str
    strategy_label: str
    parameter_hash: str
    run_ids: list[str]
    fingerprints: list[dict[str, Any]]


def configure_logging() -> None:
    """Configure console logging for report generation."""

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON file into a dictionary."""

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    """Write a JSON file with stable formatting."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_markdown(path: Path, content: str) -> None:
    """Write a markdown report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_html(path: Path, content: str) -> None:
    """Write an HTML report or visualization."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def export_csv(path: Path, frame: pd.DataFrame) -> None:
    """Export a DataFrame as CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def ensure_directory(path: Path) -> None:
    """Create a directory if it does not exist."""

    path.mkdir(parents=True, exist_ok=True)


def stable_json_dumps(payload: Any) -> str:
    """Serialize a JSON payload using a stable key order."""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(payload: Any) -> str:
    """Compute a stable SHA1 hash for JSON-like payloads."""

    text = stable_json_dumps(payload)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def parse_run_summary(p2_output_root: Path) -> dict[str, Any]:
    """Load the required P2 run summary."""

    summary_path = p2_output_root / "run_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing P2 run summary: {summary_path}")
    return read_json(summary_path)


def parse_p2_runs(p2_output_root: Path) -> list[P2RunRecord]:
    """Parse all P2 run folders under ``runs/``."""

    runs_dir = p2_output_root / "runs"
    if not runs_dir.exists():
        raise FileNotFoundError(f"Missing P2 runs directory: {runs_dir}")

    parsed_runs: list[P2RunRecord] = []
    for run_dir in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
        run_json_path = run_dir / "run.json"
        summary_json_path = run_dir / "summary.json"
        execution_trace_path = run_dir / "execution_trace.json"
        ai_summary_path = run_dir / "ai_summary.json"
        if not run_json_path.exists() or not summary_json_path.exists() or not execution_trace_path.exists():
            LOGGER.warning("Skipping incomplete run directory: %s", run_dir)
            continue

        parsed_runs.append(
            P2RunRecord(
                symbol="",
                strategy_family="",
                strategy_label="",
                run_id=run_dir.name,
                run_dir=run_dir,
                metadata={},
                run_json=read_json(run_json_path),
                summary_json=read_json(summary_json_path),
                execution_trace=read_json(execution_trace_path),
                ai_summary_json=read_json(ai_summary_path) if ai_summary_path.exists() else {},
            )
        )

    normalized_runs: list[P2RunRecord] = []
    for run in parsed_runs:
        symbol = str(run.run_json.get("symbol") or run.summary_json.get("symbol") or "").upper()
        strategy_family = str(run.run_json.get("strategy_family") or run.summary_json.get("strategy_family") or "")
        strategy_label = str(run.run_json.get("strategy_label") or run.summary_json.get("strategy_label") or "")
        metadata = dict(run.run_json.get("metadata") or run.summary_json.get("metadata") or {})
        normalized_runs.append(
            P2RunRecord(
                symbol=symbol,
                strategy_family=strategy_family,
                strategy_label=strategy_label,
                run_id=run.run_id,
                run_dir=run.run_dir,
                metadata=metadata,
                run_json=run.run_json,
                summary_json=run.summary_json,
                execution_trace=run.execution_trace,
                ai_summary_json=run.ai_summary_json,
            )
        )
    return normalized_runs


def parse_sensitivity_payloads(p2_output_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Parse all P2 sensitivity payloads."""

    sensitivity_dir = p2_output_root / "sensitivity"
    payloads: dict[tuple[str, str], dict[str, Any]] = {}
    if not sensitivity_dir.exists():
        return payloads

    for family_dir in sorted(path for path in sensitivity_dir.iterdir() if path.is_dir()):
        payload_path = family_dir / "sensitivity.json"
        if not payload_path.exists():
            continue
        payload = read_json(payload_path)
        key = (str(payload.get("symbol") or "").upper(), str(payload.get("strategy_family") or ""))
        payloads[key] = payload
    return payloads


def parse_compare_payloads(p2_output_root: Path) -> dict[str, dict[str, Any]]:
    """Parse all P2 compare payloads by symbol."""

    compare_dir = p2_output_root / "compare"
    payloads: dict[str, dict[str, Any]] = {}
    if not compare_dir.exists():
        return payloads

    for symbol_dir in sorted(path for path in compare_dir.iterdir() if path.is_dir()):
        compare_path = symbol_dir / "compare.json"
        if not compare_path.exists():
            continue
        payload = read_json(compare_path)
        payloads[str(payload.get("symbol") or symbol_dir.name).upper()] = payload
    return payloads


def load_p2_dataset(p2_output_root: Path) -> P2Dataset:
    """Parse the entire P2 output tree."""

    return P2Dataset(
        p2_output_root=p2_output_root,
        run_summary=parse_run_summary(p2_output_root),
        runs=parse_p2_runs(p2_output_root),
        sensitivity_payloads=parse_sensitivity_payloads(p2_output_root),
        compare_payloads=parse_compare_payloads(p2_output_root),
    )


def extract_execution_trace_rows(run: P2RunRecord) -> list[dict[str, Any]]:
    """Return normalized execution trace rows for a run."""

    return [dict(row) for row in (run.execution_trace.get("rows") or []) if row.get("date")]


def safe_float(value: Any) -> Optional[float]:
    """Convert a value into a float when possible."""

    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result):
        return None
    return result


def parse_run_timestamp(run: P2RunRecord) -> datetime:
    """Resolve the run timestamp from metadata or run id."""

    generated_at = str(run.metadata.get("generated_at") or "").strip()
    if generated_at:
        try:
            return datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    match = re.search(r"(\d{8}T\d{6})", run.run_id)
    if match:
        return datetime.strptime(match.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    return datetime.fromtimestamp(run.run_dir.stat().st_mtime, tz=UTC)


def build_parameter_hash(run: P2RunRecord) -> str:
    """Build a stable parameter hash from the structured parameter payload."""

    parameters = run.summary_json.get("parameters")
    if parameters is None:
        parameters = run.run_json.get("parameters")
    if parameters is None:
        parameters = {}
    return stable_hash(parameters)


def build_dedupe_key(run: P2RunRecord) -> str:
    """Build the business dedupe key for a run."""

    parameter_hash = build_parameter_hash(run)
    return "::".join([run.symbol, run.strategy_family, run.strategy_label, parameter_hash])


def compute_metric_fingerprint(run: P2RunRecord) -> dict[str, Any]:
    """Build a rounded fingerprint of metrics used to compare duplicates."""

    raw_summary_metrics = dict(run.summary_json.get("metrics") or run.run_json.get("metrics") or {})
    raw_compare_kpis = dict(run.summary_json.get("compare_kpis") or {})
    fingerprint = {
        "total_return_pct": round(safe_float(raw_summary_metrics.get("total_return_pct")) or 0.0, 6),
        "daily_return_pct": round(
            mean([safe_float(item.get("daily_return")) or 0.0 for item in extract_execution_trace_rows(run)]) if extract_execution_trace_rows(run) else 0.0,
            6,
        ),
        "volatility_pct": round(safe_float(raw_compare_kpis.get("volatility_pct")) or 0.0, 6),
        "max_drawdown_pct": round(
            safe_float(raw_compare_kpis.get("max_drawdown_pct") or raw_summary_metrics.get("max_drawdown_pct")) or 0.0,
            6,
        ),
        "sharpe_ratio": round(safe_float(raw_compare_kpis.get("sharpe_ratio")) or 0.0, 6),
        "sortino_ratio": round(safe_float(raw_compare_kpis.get("sortino_ratio")) or 0.0, 6),
        "alpha_pct": round(safe_float(raw_compare_kpis.get("alpha_pct")) or 0.0, 6),
        "beta": round(safe_float(raw_compare_kpis.get("beta")) or 0.0, 6),
        "win_rate_pct": round(
            safe_float(raw_compare_kpis.get("win_rate_pct") or raw_summary_metrics.get("win_rate_pct")) or 0.0,
            6,
        ),
        "avg_position_duration_days": round(
            safe_float(raw_compare_kpis.get("avg_holding_period_days") or raw_summary_metrics.get("avg_holding_calendar_days")) or 0.0,
            6,
        ),
        "profit_loss_ratio": round(safe_float(raw_compare_kpis.get("profit_loss_ratio")) or 0.0, 6),
        "trade_count": int(safe_float(raw_summary_metrics.get("trade_count")) or 0),
        "annualized_return_pct": round(safe_float(raw_summary_metrics.get("annualized_return_pct")) or 0.0, 6),
        "parameter_hash": build_parameter_hash(run),
    }
    return fingerprint


def deduplicate_runs(runs: list[P2RunRecord]) -> tuple[list[P2RunRecord], list[DedupeConflict], pd.DataFrame]:
    """Deduplicate runs by business key and keep the latest run id."""

    groups: dict[str, list[P2RunRecord]] = {}
    for run in runs:
        groups.setdefault(build_dedupe_key(run), []).append(run)

    kept_runs: list[P2RunRecord] = []
    conflicts: list[DedupeConflict] = []
    audit_rows: list[dict[str, Any]] = []

    for dedupe_key, group_runs in sorted(groups.items()):
        ordered = sorted(group_runs, key=parse_run_timestamp)
        latest = ordered[-1]
        fingerprints = [compute_metric_fingerprint(item) for item in ordered]
        unique_fingerprints = {stable_json_dumps(item) for item in fingerprints}
        has_conflict = len(unique_fingerprints) > 1
        if has_conflict:
            conflicts.append(
                DedupeConflict(
                    dedupe_key=dedupe_key,
                    symbol=latest.symbol,
                    strategy_family=latest.strategy_family,
                    strategy_label=latest.strategy_label,
                    parameter_hash=build_parameter_hash(latest),
                    run_ids=[item.run_id for item in ordered],
                    fingerprints=fingerprints,
                )
            )
            LOGGER.warning("Conflicting duplicates detected for %s", dedupe_key)

        kept_runs.append(latest)
        audit_rows.append(
            {
                "dedupe_key": dedupe_key,
                "symbol": latest.symbol,
                "strategy_family": latest.strategy_family,
                "strategy_label": latest.strategy_label,
                "parameter_hash": build_parameter_hash(latest),
                "run_count_before_dedupe": len(group_runs),
                "kept_run_id": latest.run_id,
                "dropped_run_ids": [item.run_id for item in ordered[:-1]],
                "has_conflict_duplicates": has_conflict,
            }
        )

    return kept_runs, conflicts, pd.DataFrame(audit_rows).sort_values(
        ["symbol", "strategy_family", "strategy_label"]
    )


def extract_period_bounds(trace_rows: list[dict[str, Any]]) -> tuple[Optional[date], Optional[date]]:
    """Extract the first and last dates from execution trace rows."""

    if not trace_rows:
        return None, None
    dates = [date.fromisoformat(str(item["date"])) for item in trace_rows if item.get("date")]
    if not dates:
        return None, None
    return min(dates), max(dates)


def compute_annualized_return_pct(total_return_pct: Optional[float], trace_rows: list[dict[str, Any]]) -> tuple[Optional[float], str, Optional[int], Optional[int]]:
    """Compute annualized return using total return and trace period length."""

    total_return_pct = safe_float(total_return_pct)
    start_date, end_date = extract_period_bounds(trace_rows)
    if total_return_pct is None:
        return None, "missing_total_return_pct", None, None
    if start_date is None or end_date is None:
        return None, "missing_period_bounds", None, None

    calendar_days = max(1, (end_date - start_date).days)
    trading_days = max(1, len(trace_rows))
    total_multiple = 1.0 + (float(total_return_pct) / 100.0)
    if total_multiple <= 0:
        return None, "invalid_total_return_multiple", trading_days, calendar_days

    annualized = (math.pow(total_multiple, 365.0 / calendar_days) - 1.0) * 100.0
    return round(annualized, 6), "computed_from_total_return_and_period", trading_days, calendar_days


def compute_volatility_pct(trace_rows: list[dict[str, Any]]) -> tuple[Optional[float], str]:
    """Compute annualized volatility from daily returns when absent."""

    returns = [safe_float(item.get("daily_return")) for item in trace_rows]
    returns = [float(item) / 100.0 for item in returns if item is not None]
    if len(returns) < 2:
        return None, "missing_daily_return_series"
    series = pd.Series(returns, dtype="float64")
    return round(float(series.std(ddof=0) * math.sqrt(252) * 100.0), 6), "computed_from_trace_daily_returns"


def compute_drawdown_pct(trace_rows: list[dict[str, Any]]) -> tuple[Optional[float], str]:
    """Compute maximum drawdown from equity series when absent."""

    equity = [safe_float(item.get("total_portfolio_value")) for item in trace_rows]
    equity = [item for item in equity if item is not None]
    if len(equity) < 2:
        return None, "missing_equity_series"
    series = pd.Series(equity, dtype="float64")
    rolling_max = series.cummax()
    drawdown = ((series - rolling_max) / rolling_max.replace(0, pd.NA)).fillna(0.0) * 100.0
    return round(abs(float(drawdown.min())), 6), "computed_from_trace_equity_series"


def compute_sharpe_ratio(trace_rows: list[dict[str, Any]]) -> tuple[Optional[float], str]:
    """Compute Sharpe ratio from daily return series when absent."""

    returns = [safe_float(item.get("daily_return")) for item in trace_rows]
    returns = [float(item) / 100.0 for item in returns if item is not None]
    if len(returns) < 2:
        return None, "missing_daily_return_series"
    series = pd.Series(returns, dtype="float64")
    std = float(series.std(ddof=0))
    if std == 0:
        return None, "zero_return_std"
    return round(float((series.mean() / std) * math.sqrt(252)), 6), "computed_from_trace_daily_returns"


def compute_sortino_ratio(trace_rows: list[dict[str, Any]]) -> tuple[Optional[float], str]:
    """Compute Sortino ratio from daily return series when absent."""

    returns = [safe_float(item.get("daily_return")) for item in trace_rows]
    returns = [float(item) / 100.0 for item in returns if item is not None]
    if len(returns) < 2:
        return None, "missing_daily_return_series"
    series = pd.Series(returns, dtype="float64")
    downside = series[series < 0]
    if downside.empty:
        return None, "no_downside_returns"
    downside_std = float(downside.std(ddof=0))
    if downside_std == 0:
        return None, "zero_downside_std"
    return round(float((series.mean() / downside_std) * math.sqrt(252)), 6), "computed_from_trace_daily_returns"


def build_metric_with_status(primary_value: Any, primary_status: str, fallback_factory: Any) -> tuple[Optional[float], str]:
    """Return a metric using the provided value or fallback computation."""

    value = safe_float(primary_value)
    if value is not None:
        return round(float(value), 6), primary_status
    return fallback_factory()


def build_run_record(run: P2RunRecord, run_tag: str, generated_at: str, conflict_keys: set[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build the exported run row and time-series rows for one deduplicated run."""

    trace_rows = extract_execution_trace_rows(run)
    summary_metrics = dict(run.summary_json.get("metrics") or run.run_json.get("metrics") or {})
    compare_kpis = dict(run.summary_json.get("compare_kpis") or {})
    parameter_hash = build_parameter_hash(run)
    dedupe_key = build_dedupe_key(run)

    total_return_pct = safe_float(summary_metrics.get("total_return_pct"))
    daily_return_pct = safe_float(mean([safe_float(row.get("daily_return")) or 0.0 for row in trace_rows])) if trace_rows else None

    annualized_return_pct, annualized_status, trading_days, calendar_days = build_metric_with_status(
        summary_metrics.get("annualized_return_pct"),
        "provided_by_p2",
        lambda: compute_annualized_return_pct(total_return_pct, trace_rows),
    )

    volatility_pct, volatility_status = build_metric_with_status(
        compare_kpis.get("volatility_pct"),
        "provided_by_p2",
        lambda: compute_volatility_pct(trace_rows),
    )

    max_drawdown_pct, max_drawdown_status = build_metric_with_status(
        compare_kpis.get("max_drawdown_pct") or summary_metrics.get("max_drawdown_pct"),
        "provided_by_p2",
        lambda: compute_drawdown_pct(trace_rows),
    )

    sharpe_ratio, sharpe_status = build_metric_with_status(
        compare_kpis.get("sharpe_ratio"),
        "provided_by_p2",
        lambda: compute_sharpe_ratio(trace_rows),
    )

    sortino_ratio, sortino_status = build_metric_with_status(
        compare_kpis.get("sortino_ratio"),
        "provided_by_p2",
        lambda: compute_sortino_ratio(trace_rows),
    )

    calmar_value = safe_float(compare_kpis.get("calmar_ratio"))
    if calmar_value is not None:
        calmar_ratio = round(float(calmar_value), 6)
        calmar_status = "provided_by_p2"
    elif annualized_return_pct is not None and max_drawdown_pct not in (None, 0):
        calmar_ratio = round(float(annualized_return_pct) / float(max_drawdown_pct), 6)
        calmar_status = "computed_from_annualized_and_drawdown"
    else:
        calmar_ratio = None
        calmar_status = "missing_input_metrics"

    profit_loss_value = safe_float(compare_kpis.get("profit_loss_ratio"))
    if profit_loss_value is not None:
        profit_loss_ratio = round(float(profit_loss_value), 6)
        profit_loss_status = "provided_by_p2"
    else:
        profit_loss_ratio = None
        profit_loss_status = "null_no_trade_level_data"

    completeness_flags = {
        "annualized_return_pct": annualized_status,
        "volatility_pct": volatility_status,
        "max_drawdown_pct": max_drawdown_status,
        "sharpe_ratio": sharpe_status,
        "sortino_ratio": sortino_status,
        "calmar_ratio": calmar_status,
        "profit_loss_ratio": profit_loss_status,
    }

    record = {
        "run_tag": run_tag,
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": generated_at,
        "symbol": run.symbol,
        "strategy_family": run.strategy_family,
        "strategy_label": run.strategy_label,
        "run_id": run.run_id,
        "parameter_hash": parameter_hash,
        "dedupe_key": dedupe_key,
        "has_conflict_duplicates": dedupe_key in conflict_keys,
        "total_return_pct": total_return_pct,
        "daily_return_pct": round(float(daily_return_pct), 6) if daily_return_pct is not None else None,
        "volatility_pct": volatility_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "calmar_ratio": calmar_ratio,
        "alpha_pct": safe_float(compare_kpis.get("alpha_pct")),
        "beta": safe_float(compare_kpis.get("beta")),
        "win_rate_pct": safe_float(compare_kpis.get("win_rate_pct") or summary_metrics.get("win_rate_pct")),
        "avg_position_duration_days": safe_float(compare_kpis.get("avg_holding_period_days") or summary_metrics.get("avg_holding_calendar_days")),
        "profit_loss_ratio": profit_loss_ratio,
        "trade_count": int(safe_float(summary_metrics.get("trade_count")) or 0),
        "annualized_return_pct": annualized_return_pct,
        "trading_days": trading_days,
        "calendar_days": calendar_days,
        "period_start": trace_rows[0]["date"] if trace_rows else None,
        "period_end": trace_rows[-1]["date"] if trace_rows else None,
        "completeness_flags": stable_json_dumps(completeness_flags),
    }

    timeseries_rows: list[dict[str, Any]] = []
    for row in trace_rows:
        timeseries_rows.append(
            {
                "run_tag": run_tag,
                "pipeline_version": PIPELINE_VERSION,
                "generated_at": generated_at,
                "run_id": run.run_id,
                "dedupe_key": dedupe_key,
                "symbol": run.symbol,
                "strategy_family": run.strategy_family,
                "strategy_label": run.strategy_label,
                "parameter_hash": parameter_hash,
                "timestamp": row.get("date"),
                "equity": safe_float(row.get("total_portfolio_value")),
                "cumulative_return_pct": safe_float(row.get("cumulative_return")),
                "drawdown_pct": safe_float(row.get("drawdown_pct")),
                "daily_return_pct": safe_float(row.get("daily_return")),
                "symbol_close": safe_float(row.get("symbol_close")),
                "position": safe_float(row.get("position")),
                "action": row.get("action"),
            }
        )

    return record, timeseries_rows


def build_run_and_timeseries_frames(
    runs: list[P2RunRecord],
    *,
    run_tag: str,
    generated_at: str,
    conflicts: list[DedupeConflict],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the deduplicated summary_runs and timeseries export frames."""

    conflict_keys = {item.dedupe_key for item in conflicts}
    run_rows: list[dict[str, Any]] = []
    timeseries_rows: list[dict[str, Any]] = []
    for run in runs:
        record, series_rows = build_run_record(run, run_tag, generated_at, conflict_keys)
        run_rows.append(record)
        timeseries_rows.extend(series_rows)

    run_df = pd.DataFrame(run_rows).sort_values(["symbol", "strategy_family", "strategy_label"])
    timeseries_df = pd.DataFrame(timeseries_rows).sort_values(["symbol", "strategy_family", "strategy_label", "timestamp"])
    return run_df, timeseries_df


def aggregate_symbol_metrics(run_df: pd.DataFrame, generated_at: str, run_tag: str) -> pd.DataFrame:
    """Aggregate symbol-level metrics from deduplicated runs."""

    if run_df.empty:
        return pd.DataFrame(columns=["symbol"])

    group = run_df.groupby("symbol", as_index=False)
    symbol_df = group.agg(
        strategy_count=("strategy_label", "nunique"),
        avg_total_return_pct=("total_return_pct", "mean"),
        best_total_return_pct=("total_return_pct", "max"),
        worst_total_return_pct=("total_return_pct", "min"),
        avg_sharpe_ratio=("sharpe_ratio", "mean"),
        avg_sortino_ratio=("sortino_ratio", "mean"),
        avg_calmar_ratio=("calmar_ratio", "mean"),
        avg_alpha_pct=("alpha_pct", "mean"),
        avg_beta=("beta", "mean"),
        avg_win_rate_pct=("win_rate_pct", "mean"),
        avg_position_duration_days=("avg_position_duration_days", "mean"),
        avg_profit_loss_ratio=("profit_loss_ratio", "mean"),
        avg_volatility_pct=("volatility_pct", "mean"),
        worst_max_drawdown_pct=("max_drawdown_pct", "max"),
    ).sort_values("symbol")

    best_strategy = (
        run_df.sort_values(["symbol", "total_return_pct"], ascending=[True, False])
        .groupby("symbol", as_index=False)
        .first()[["symbol", "strategy_label"]]
        .rename(columns={"strategy_label": "best_strategy_label"})
    )
    worst_strategy = (
        run_df.sort_values(["symbol", "total_return_pct"], ascending=[True, True])
        .groupby("symbol", as_index=False)
        .first()[["symbol", "strategy_label"]]
        .rename(columns={"strategy_label": "worst_strategy_label"})
    )
    symbol_df = symbol_df.merge(best_strategy, on="symbol", how="left").merge(worst_strategy, on="symbol", how="left")
    symbol_df["run_tag"] = run_tag
    symbol_df["pipeline_version"] = PIPELINE_VERSION
    symbol_df["generated_at"] = generated_at
    symbol_df["completeness_flags"] = symbol_df.apply(
        lambda row: stable_json_dumps(
            {
                "avg_calmar_ratio": "missing_in_some_runs" if pd.isna(row["avg_calmar_ratio"]) else "complete",
                "avg_profit_loss_ratio": "missing_in_some_runs" if pd.isna(row["avg_profit_loss_ratio"]) else "complete",
            }
        ),
        axis=1,
    )
    return symbol_df


def dataframe_to_markdown(frame: pd.DataFrame) -> str:
    """Convert a DataFrame to a markdown table without extra dependencies."""

    if frame.empty:
        return "_No data available._"
    columns = [str(column) for column in frame.columns]
    rows = frame.astype(object).where(pd.notnull(frame), "").values.tolist()
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def build_symbol_executive_summary(symbol: str, symbol_runs: pd.DataFrame) -> str:
    """Generate one executive summary per symbol."""

    best_row = symbol_runs.sort_values("total_return_pct", ascending=False).iloc[0]
    worst_row = symbol_runs.sort_values("total_return_pct", ascending=True).iloc[0]
    sharpe_row = symbol_runs.sort_values("sharpe_ratio", ascending=False).iloc[0]
    return (
        f"## {symbol}\n\n"
        f"- Best total return strategy: `{best_row['strategy_label']}` at `{best_row['total_return_pct']}`%.\n"
        f"- Best Sharpe strategy: `{sharpe_row['strategy_label']}` at `{sharpe_row['sharpe_ratio']}`.\n"
        f"- Weakest total return strategy: `{worst_row['strategy_label']}` at `{worst_row['total_return_pct']}`%.\n"
        f"- Average volatility across strategies: `{symbol_runs['volatility_pct'].mean():.4f}`%.\n"
        f"- Largest observed drawdown: `{symbol_runs['max_drawdown_pct'].max():.4f}`%.\n"
    )


def build_strategy_appendix(run_row: dict[str, Any], sensitivity_payload: Optional[dict[str, Any]], compare_payload: Optional[dict[str, Any]]) -> str:
    """Generate one appendix summary per unique strategy."""

    sensitivity_headline = (sensitivity_payload or {}).get("highlights", {}).get("headline") or "No sensitivity headline available."
    best_total = (compare_payload or {}).get("best_runs", {}).get("best_total_return") or {}
    compare_note = (
        "This strategy is the top total-return configuration for the symbol."
        if str(best_total.get("strategy_label") or "") == str(run_row.get("strategy_label") or "")
        else f"Top total-return configuration is `{best_total.get('strategy_label') or 'N/A'}`."
    )
    return (
        f"### {run_row['symbol']} / {run_row['strategy_label']}\n\n"
        f"- Total return: `{run_row['total_return_pct']}`%\n"
        f"- Annualized return: `{run_row['annualized_return_pct']}`%\n"
        f"- Sharpe / Sortino / Calmar: `{run_row['sharpe_ratio']}` / `{run_row['sortino_ratio']}` / `{run_row['calmar_ratio']}`\n"
        f"- Max drawdown: `{run_row['max_drawdown_pct']}`%\n"
        f"- Win rate: `{run_row['win_rate_pct']}`%\n"
        f"- Average holding duration: `{run_row['avg_position_duration_days']}` days\n"
        f"- Parameter sensitivity: {sensitivity_headline}\n"
        f"- Compare note: {compare_note}\n"
        f"- Completeness: `{run_row['completeness_flags']}`\n"
    )


def generate_ai_summaries(
    run_df: pd.DataFrame,
    dataset: P2Dataset,
) -> tuple[dict[str, str], dict[str, str]]:
    """Generate symbol-level executive summaries and strategy appendices."""

    strategy_summaries: dict[str, str] = {}
    symbol_summaries: dict[str, str] = {}

    for symbol, symbol_runs in run_df.groupby("symbol"):
        symbol_summaries[symbol] = build_symbol_executive_summary(symbol, symbol_runs)
        for row in symbol_runs.to_dict(orient="records"):
            sensitivity_payload = dataset.sensitivity_payloads.get((symbol, row["strategy_family"]))
            compare_payload = dataset.compare_payloads.get(symbol)
            strategy_summaries[str(row["run_id"])] = build_strategy_appendix(row, sensitivity_payload, compare_payload)
    return strategy_summaries, symbol_summaries


def sanitize_filename(value: str) -> str:
    """Make a value safe for filenames."""

    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value).strip("-_") or "item"


def html_template(title: str, body: str) -> str:
    """Build a standalone HTML page."""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{
      margin: 24px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0b1020;
      color: #e8edf7;
    }}
    .card {{
      background: #121933;
      border: 1px solid #273159;
      border-radius: 14px;
      padding: 16px;
      box-shadow: 0 12px 30px rgba(0,0,0,0.2);
      margin-bottom: 20px;
    }}
    h1, h2, h3 {{ margin: 0 0 12px 0; }}
    p, li {{ color: #b7c1de; }}
    svg {{ width: 100%; height: auto; display: block; }}
    .axis {{ stroke: #7081b9; stroke-width: 1; }}
    .grid {{ stroke: #253052; stroke-width: 1; opacity: 0.8; }}
    .label {{ fill: #b7c1de; font-size: 12px; }}
    .series-label {{ fill: #e8edf7; font-size: 12px; }}
    .bar {{ fill: #2a9d8f; }}
    .line-a {{ stroke: #4cc9f0; fill: none; stroke-width: 2; }}
    .line-b {{ stroke: #f72585; fill: none; stroke-width: 2; }}
    .line-c {{ stroke: #f4a261; fill: none; stroke-width: 2; }}
    .line-d {{ stroke: #90be6d; fill: none; stroke-width: 2; }}
    .dot {{ fill: #f4a261; opacity: 0.85; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 18px;
      font-size: 13px;
    }}
    th, td {{
      border: 1px solid #273159;
      padding: 8px;
      text-align: left;
    }}
    th {{ background: #192445; }}
  </style>
</head>
<body>
  {body}
</body>
</html>"""


def normalize_series(values: list[float], *, min_out: float, max_out: float) -> list[float]:
    """Map numeric values into a target screen range."""

    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi == lo:
        mid = (min_out + max_out) / 2.0
        return [mid for _ in values]
    return [min_out + ((value - lo) / (hi - lo)) * (max_out - min_out) for value in values]


def polyline_points(values: list[float], width: int = 900, height: int = 360, padding: int = 48) -> str:
    """Convert a series into SVG polyline points."""

    if not values:
        return ""
    x_step = (width - padding * 2) / max(1, len(values) - 1)
    y_values = normalize_series(values, min_out=height - padding, max_out=padding)
    return " ".join(f"{padding + index * x_step:.2f},{y_values[index]:.2f}" for index in range(len(values)))


def render_line_chart_html(title: str, series_map: dict[str, list[float]], labels: list[str], *, subtitle: Optional[str] = None) -> str:
    """Render a multi-series SVG line chart as HTML."""

    colors = ["line-a", "line-b", "line-c", "line-d"]
    width = 960
    height = 420
    padding = 56
    grid_lines = []
    for index in range(5):
        y = padding + index * ((height - padding * 2) / 4.0)
        grid_lines.append(f'<line class="grid" x1="{padding}" y1="{y:.2f}" x2="{width-padding}" y2="{y:.2f}" />')
    x_axis = f'<line class="axis" x1="{padding}" y1="{height-padding}" x2="{width-padding}" y2="{height-padding}" />'
    y_axis = f'<line class="axis" x1="{padding}" y1="{padding}" x2="{padding}" y2="{height-padding}" />'
    x_labels = []
    if labels:
        step = max(1, len(labels) // 6)
        for index in range(0, len(labels), step):
            x = padding + index * ((width - padding * 2) / max(1, len(labels) - 1))
            x_labels.append(f'<text class="label" x="{x:.2f}" y="{height-padding+22}">{labels[index]}</text>')
    polylines = []
    legends = []
    for index, (name, values) in enumerate(series_map.items()):
        if not values:
            continue
        css_class = colors[index % len(colors)]
        polylines.append(f'<polyline class="{css_class}" points="{polyline_points(values, width, height, padding)}" />')
        legends.append(f'<text class="series-label" x="{padding + (index % 4) * 220}" y="{26 + (index // 4) * 18}">{name}</text>')
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    return html_template(
        title,
        f"""
        <div class="card">
          <h1>{title}</h1>
          {subtitle_html}
          <svg viewBox="0 0 {width} {height}">
            {''.join(grid_lines)}
            {x_axis}
            {y_axis}
            {''.join(polylines)}
            {''.join(x_labels)}
            {''.join(legends)}
          </svg>
        </div>
        """,
    )


def render_bar_chart_html(title: str, categories: list[str], values: list[float], *, subtitle: Optional[str] = None) -> str:
    """Render an SVG bar chart as HTML."""

    width = 960
    height = 420
    padding = 56
    bar_width = (width - padding * 2) / max(1, len(values))
    scaled_heights = normalize_series(values, min_out=24.0, max_out=height - padding * 2)
    bars = []
    labels = []
    for index, value in enumerate(values):
        x = padding + index * bar_width + 6
        bar_height = scaled_heights[index]
        y = height - padding - bar_height
        bars.append(f'<rect class="bar" x="{x:.2f}" y="{y:.2f}" width="{max(18, bar_width - 12):.2f}" height="{bar_height:.2f}" />')
        labels.append(f'<text class="label" x="{x:.2f}" y="{height-padding+22}">{categories[index]}</text>')
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    return html_template(
        title,
        f"""
        <div class="card">
          <h1>{title}</h1>
          {subtitle_html}
          <svg viewBox="0 0 {width} {height}">
            <line class="axis" x1="{padding}" y1="{height-padding}" x2="{width-padding}" y2="{height-padding}" />
            <line class="axis" x1="{padding}" y1="{padding}" x2="{padding}" y2="{height-padding}" />
            {''.join(bars)}
            {''.join(labels)}
          </svg>
        </div>
        """,
    )


def render_heatmap_html(title: str, frame: pd.DataFrame, *, subtitle: Optional[str] = None) -> str:
    """Render a heatmap-like HTML table."""

    if frame.empty:
        return html_template(title, f"<div class='card'><h1>{title}</h1><p>No data available.</p></div>")
    minimum = float(frame.min().min())
    maximum = float(frame.max().max())

    def bg_color(value: float) -> str:
        ratio = 0.5 if maximum == minimum else (float(value) - minimum) / (maximum - minimum)
        blue = int(70 + 120 * ratio)
        green = int(60 + 110 * ratio)
        red = int(20 + 90 * (1.0 - ratio))
        return f"rgb({red},{green},{blue})"

    header = "<tr><th>Strategy</th>" + "".join(f"<th>{column}</th>" for column in frame.columns) + "</tr>"
    rows = []
    for label, row in frame.iterrows():
        cells = [f"<td>{label}</td>"]
        for column in frame.columns:
            value = row[column]
            if pd.isna(value):
                cells.append("<td>NA</td>")
            else:
                cells.append(f"<td style='background:{bg_color(float(value))}'>{float(value):.2f}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    return html_template(
        title,
        f"""
        <div class="card">
          <h1>{title}</h1>
          {subtitle_html}
          <table>
            <thead>{header}</thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
        </div>
        """,
    )


def render_scatter_html(title: str, points: list[dict[str, Any]], *, x_label: str, y_label: str, subtitle: Optional[str] = None) -> str:
    """Render a simple scatter chart as HTML."""

    width = 960
    height = 420
    padding = 56
    x_values = [float(item["x"]) for item in points]
    y_values = [float(item["y"]) for item in points]
    x_coords = normalize_series(x_values, min_out=padding, max_out=width - padding)
    y_coords = normalize_series(y_values, min_out=height - padding, max_out=padding)
    circles = []
    labels = []
    for index, point in enumerate(points):
        circles.append(f'<circle class="dot" cx="{x_coords[index]:.2f}" cy="{y_coords[index]:.2f}" r="5" />')
        labels.append(f'<text class="label" x="{x_coords[index] + 8:.2f}" y="{y_coords[index] - 6:.2f}">{point["label"]}</text>')
    subtitle_html = f"<p>{subtitle}</p>" if subtitle else ""
    return html_template(
        title,
        f"""
        <div class="card">
          <h1>{title}</h1>
          {subtitle_html}
          <svg viewBox="0 0 {width} {height}">
            <line class="axis" x1="{padding}" y1="{height-padding}" x2="{width-padding}" y2="{height-padding}" />
            <line class="axis" x1="{padding}" y1="{padding}" x2="{padding}" y2="{height-padding}" />
            {''.join(circles)}
            {''.join(labels)}
            <text class="series-label" x="{width/2:.2f}" y="{height-12}">{x_label}</text>
            <text class="series-label" x="8" y="{height/2:.2f}" transform="rotate(-90 8,{height/2:.2f})">{y_label}</text>
          </svg>
        </div>
        """,
    )


def build_plot_reference(path: Path, *, plot_type: str, title: str, symbol: Optional[str] = None, strategy_family: Optional[str] = None) -> dict[str, Any]:
    """Build a plot reference payload."""

    payload = {
        "plot_type": plot_type,
        "title": title,
        "path": str(path),
    }
    if symbol:
        payload["symbol"] = symbol
    if strategy_family:
        payload["strategy_family"] = strategy_family
    return payload


def plot_summary_charts(run_df: pd.DataFrame, symbol_df: pd.DataFrame, output_root: Path) -> list[dict[str, Any]]:
    """Generate top-level summary charts."""

    refs: list[dict[str, Any]] = []
    if not run_df.empty:
        annualized_counts = (
            run_df["annualized_return_pct"]
            .fillna(0.0)
            .round(-1)
            .value_counts()
            .sort_index()
        )
        annualized_path = output_root / "plots" / "summary" / "runs_annualized_return.html"
        write_html(
            annualized_path,
            render_bar_chart_html(
                "Runs Annualized Return Distribution",
                [str(index) for index in annualized_counts.index.tolist()],
                [float(value) for value in annualized_counts.values.tolist()],
                subtitle="Deduplicated run counts by annualized return bucket.",
            ),
        )
        refs.append(build_plot_reference(annualized_path, plot_type="runs_annualized_return", title="Runs Annualized Return Distribution"))

    if not symbol_df.empty:
        ordered = symbol_df.sort_values("avg_total_return_pct", ascending=False)
        symbols_path = output_root / "plots" / "summary" / "symbols_avg_total_return.html"
        write_html(
            symbols_path,
            render_bar_chart_html(
                "Average Total Return by Symbol",
                ordered["symbol"].tolist(),
                [float(value) for value in ordered["avg_total_return_pct"].fillna(0.0).tolist()],
                subtitle="Recomputed from deduplicated unique strategy runs.",
            ),
        )
        refs.append(build_plot_reference(symbols_path, plot_type="symbols_avg_total_return", title="Average Total Return by Symbol"))
    return refs


def plot_equity_curves(timeseries_df: pd.DataFrame, run_df: pd.DataFrame, output_root: Path) -> list[dict[str, Any]]:
    """Plot equity curves for best-performing strategies per symbol."""

    refs: list[dict[str, Any]] = []
    if timeseries_df.empty or run_df.empty:
        return refs

    for symbol, symbol_runs in run_df.groupby("symbol"):
        top_labels = []
        for column in ("total_return_pct", "sharpe_ratio", "sortino_ratio"):
            best_row = symbol_runs.sort_values(column, ascending=False).iloc[0]
            label = str(best_row["strategy_label"])
            if label not in top_labels:
                top_labels.append(label)

        symbol_series = timeseries_df[
            (timeseries_df["symbol"] == symbol)
            & (timeseries_df["strategy_label"].isin(top_labels))
        ]
        if symbol_series.empty:
            continue
        series_map: dict[str, list[float]] = {}
        labels: list[str] = []
        for strategy_label, label_rows in symbol_series.groupby("strategy_label"):
            ordered = label_rows.sort_values("timestamp")
            labels = ordered["timestamp"].astype(str).tolist()
            series_map[str(strategy_label)] = [float(item) for item in ordered["cumulative_return_pct"].fillna(0.0).tolist()]
        plot_path = output_root / "plots" / "equity_curves" / f"{sanitize_filename(symbol)}-equity-curves.html"
        write_html(
            plot_path,
            render_line_chart_html(
                f"{symbol} Equity Curves",
                series_map,
                labels,
                subtitle="Top total-return / Sharpe / Sortino strategies after deduplication.",
            ),
        )
        refs.append(build_plot_reference(plot_path, plot_type="equity_curves", title=f"{symbol} Equity Curves", symbol=symbol))
    return refs


def plot_strategy_overlay(timeseries_df: pd.DataFrame, run_df: pd.DataFrame, output_root: Path) -> list[dict[str, Any]]:
    """Plot overlay charts for all strategies per symbol."""

    refs: list[dict[str, Any]] = []
    if timeseries_df.empty or run_df.empty:
        return refs

    for symbol, symbol_series in timeseries_df.groupby("symbol"):
        series_map: dict[str, list[float]] = {}
        labels: list[str] = []
        for strategy_label, label_rows in symbol_series.groupby("strategy_label"):
            ordered = label_rows.sort_values("timestamp")
            labels = ordered["timestamp"].astype(str).tolist()
            series_map[str(strategy_label)] = [float(item) for item in ordered["cumulative_return_pct"].fillna(0.0).tolist()]
        symbol_runs = run_df[run_df["symbol"] == symbol]
        best_row = symbol_runs.sort_values("total_return_pct", ascending=False).iloc[0]
        worst_row = symbol_runs.sort_values("total_return_pct", ascending=True).iloc[0]
        avg_return = float(symbol_runs["total_return_pct"].mean())
        plot_path = output_root / "plots" / "strategy_overlays" / f"{sanitize_filename(symbol)}-strategy-overlay.html"
        write_html(
            plot_path,
            render_line_chart_html(
                f"{symbol} Strategy Overlay",
                series_map,
                labels,
                subtitle=(
                    f"Average total return {avg_return:.4f}%. "
                    f"Best {best_row['strategy_label']} / Worst {worst_row['strategy_label']}."
                ),
            ),
        )
        refs.append(build_plot_reference(plot_path, plot_type="strategy_overlay", title=f"{symbol} Strategy Overlay", symbol=symbol))
    return refs


def plot_sensitivity_heatmaps(dataset: P2Dataset, output_root: Path) -> list[dict[str, Any]]:
    """Plot heatmaps from sensitivity payloads."""

    refs: list[dict[str, Any]] = []
    for (symbol, family), payload in sorted(dataset.sensitivity_payloads.items()):
        rows = payload.get("runs") or []
        if not rows:
            continue
        frame = pd.DataFrame(
            [
                {
                    "strategy_label": item.get("strategy_label"),
                    "total_return_pct": safe_float((item.get("metrics") or {}).get("total_return_pct")),
                    "sharpe_ratio": safe_float((item.get("metrics") or {}).get("sharpe_ratio")),
                    "max_drawdown_pct": safe_float((item.get("metrics") or {}).get("max_drawdown_pct")),
                }
                for item in rows
            ]
        ).set_index("strategy_label")
        if frame.empty:
            continue
        plot_path = output_root / "plots" / "sensitivity_heatmaps" / f"{sanitize_filename(symbol)}-{sanitize_filename(family)}-heatmap.html"
        write_html(
            plot_path,
            render_heatmap_html(
                f"{symbol} {family} Sensitivity Heatmap",
                frame,
                subtitle="Sensitivity payloads are displayed after deduplicated strategy selection.",
            ),
        )
        refs.append(build_plot_reference(plot_path, plot_type="sensitivity_heatmap", title=f"{symbol} {family} Sensitivity Heatmap", symbol=symbol, strategy_family=family))
    return refs


def plot_compare_kpis(run_df: pd.DataFrame, output_root: Path) -> list[dict[str, Any]]:
    """Plot KPI comparison charts from the deduplicated run table."""

    refs: list[dict[str, Any]] = []
    if run_df.empty:
        return refs
    for symbol, symbol_runs in run_df.groupby("symbol"):
        frame = symbol_runs[["strategy_label", "total_return_pct", "sharpe_ratio", "sortino_ratio", "max_drawdown_pct"]].copy()
        plot_path = output_root / "plots" / "compare_kpis" / f"{sanitize_filename(symbol)}-compare-kpis.html"
        write_html(
            plot_path,
            render_heatmap_html(
                f"{symbol} Compare KPIs",
                frame.set_index("strategy_label"),
                subtitle="Risk and return KPI matrix for deduplicated strategy runs.",
            ),
        )
        refs.append(build_plot_reference(plot_path, plot_type="compare_kpis", title=f"{symbol} Compare KPIs", symbol=symbol))
    return refs


def plot_null_rate_by_metric(run_df: pd.DataFrame, output_root: Path) -> Optional[dict[str, Any]]:
    """Plot null-rate diagnostics for key metrics."""

    if run_df.empty:
        return None
    null_rates = []
    for column in NUMERIC_FINGERPRINT_FIELDS:
        if column not in run_df.columns:
            continue
        null_rates.append((column, float(run_df[column].isna().mean() * 100.0)))
    plot_path = output_root / "plots" / "diagnostics" / "null-rate-by-metric.html"
    write_html(
        plot_path,
        render_bar_chart_html(
            "Null Rate by Metric",
            [item[0] for item in null_rates],
            [item[1] for item in null_rates],
            subtitle="Percentage of deduplicated runs with null values per metric.",
        ),
    )
    return build_plot_reference(plot_path, plot_type="null_rate_by_metric", title="Null Rate by Metric")


def plot_deduplication_audit(audit_df: pd.DataFrame, output_root: Path) -> Optional[dict[str, Any]]:
    """Plot dedupe audit results."""

    if audit_df.empty:
        return None
    counts = (
        audit_df["run_count_before_dedupe"]
        .value_counts()
        .sort_index()
    )
    plot_path = output_root / "plots" / "diagnostics" / "deduplication-audit.html"
    write_html(
        plot_path,
        render_bar_chart_html(
            "Deduplication Audit",
            [str(item) for item in counts.index.tolist()],
            [float(item) for item in counts.values.tolist()],
            subtitle="How many runs existed per business key before deduplication.",
        ),
    )
    return build_plot_reference(plot_path, plot_type="deduplication_audit", title="Deduplication Audit")


def plot_risk_return_scatter(run_df: pd.DataFrame, output_root: Path) -> Optional[dict[str, Any]]:
    """Plot risk-return scatter diagnostics."""

    frame = run_df.dropna(subset=["volatility_pct", "total_return_pct"])
    if frame.empty:
        return None
    points = [
        {
            "x": float(row["volatility_pct"]),
            "y": float(row["total_return_pct"]),
            "label": f"{row['symbol']}:{row['strategy_label']}",
        }
        for row in frame.to_dict(orient="records")
    ]
    plot_path = output_root / "plots" / "diagnostics" / "risk-return-scatter.html"
    write_html(
        plot_path,
        render_scatter_html(
            "Risk vs Return Scatter",
            points,
            x_label="Volatility %",
            y_label="Total Return %",
            subtitle="Deduplicated strategy runs plotted by volatility and total return.",
        ),
    )
    return build_plot_reference(plot_path, plot_type="risk_return_scatter", title="Risk vs Return Scatter")


def plot_drawdown_vs_sharpe(run_df: pd.DataFrame, output_root: Path) -> Optional[dict[str, Any]]:
    """Plot drawdown vs Sharpe quadrant."""

    frame = run_df.dropna(subset=["max_drawdown_pct", "sharpe_ratio"])
    if frame.empty:
        return None
    points = [
        {
            "x": float(row["max_drawdown_pct"]),
            "y": float(row["sharpe_ratio"]),
            "label": f"{row['symbol']}:{row['strategy_label']}",
        }
        for row in frame.to_dict(orient="records")
    ]
    plot_path = output_root / "plots" / "diagnostics" / "drawdown-vs-sharpe.html"
    write_html(
        plot_path,
        render_scatter_html(
            "Drawdown vs Sharpe",
            points,
            x_label="Max Drawdown %",
            y_label="Sharpe Ratio",
            subtitle="Strategies closer to the upper-left are usually more attractive risk-adjusted candidates.",
        ),
    )
    return build_plot_reference(plot_path, plot_type="drawdown_vs_sharpe", title="Drawdown vs Sharpe")


def plot_cross_symbol_leaderboards(symbol_df: pd.DataFrame, output_root: Path) -> Optional[dict[str, Any]]:
    """Plot cross-symbol leaderboard chart."""

    if symbol_df.empty:
        return None
    ordered = symbol_df.sort_values("best_total_return_pct", ascending=False).head(12)
    plot_path = output_root / "plots" / "diagnostics" / "cross-symbol-leaderboards.html"
    write_html(
        plot_path,
        render_bar_chart_html(
            "Cross-Symbol Leaderboard",
            ordered["symbol"].tolist(),
            [float(item) for item in ordered["best_total_return_pct"].fillna(0.0).tolist()],
            subtitle="Top symbols ranked by best unique strategy total return.",
        ),
    )
    return build_plot_reference(plot_path, plot_type="cross_symbol_leaderboard", title="Cross-Symbol Leaderboard")


def generate_visualizations(
    dataset: P2Dataset,
    run_df: pd.DataFrame,
    symbol_df: pd.DataFrame,
    timeseries_df: pd.DataFrame,
    audit_df: pd.DataFrame,
    output_root: Path,
) -> list[dict[str, Any]]:
    """Generate all required visualization artifacts."""

    refs: list[dict[str, Any]] = []
    refs.extend(plot_summary_charts(run_df, symbol_df, output_root))
    refs.extend(plot_equity_curves(timeseries_df, run_df, output_root))
    refs.extend(plot_strategy_overlay(timeseries_df, run_df, output_root))
    refs.extend(plot_sensitivity_heatmaps(dataset, output_root))
    refs.extend(plot_compare_kpis(run_df, output_root))
    for diagnostic in (
        plot_null_rate_by_metric(run_df, output_root),
        plot_deduplication_audit(audit_df, output_root),
        plot_risk_return_scatter(run_df, output_root),
        plot_drawdown_vs_sharpe(run_df, output_root),
        plot_cross_symbol_leaderboards(symbol_df, output_root),
    ):
        if diagnostic is not None:
            refs.append(diagnostic)
    return refs


def build_markdown_report(
    context: ReportContext,
    run_df: pd.DataFrame,
    symbol_df: pd.DataFrame,
    symbol_summaries: dict[str, str],
    strategy_summaries: dict[str, str],
    plot_refs: list[dict[str, Any]],
    conflicts: list[DedupeConflict],
) -> str:
    """Build the top-level markdown report."""

    lines = [
        "# WolfyStock P3 Report",
        "",
        f"- P2 output: `{context.p2_output_root}`",
        f"- Run tag: `{context.run_tag}`",
        f"- Pipeline version: `{PIPELINE_VERSION}`",
        f"- Generated at: `{context.generated_at}`",
        f"- Deduplicated runs: `{len(run_df)}`",
        f"- Symbols: `{len(symbol_df)}`",
        f"- Conflicting duplicate groups: `{len(conflicts)}`",
        "",
        "## Symbol Overview",
        "",
        dataframe_to_markdown(symbol_df),
        "",
        "## Executive Summaries",
        "",
    ]

    for symbol in sorted(symbol_summaries):
        lines.append(symbol_summaries[symbol])
        lines.append("")

    lines.extend(["## Strategy Appendices", ""])
    for _, row in run_df.sort_values(["symbol", "strategy_family", "strategy_label"]).iterrows():
        lines.append(strategy_summaries[str(row["run_id"])])
        lines.append("")

    lines.extend(["## Plot Inventory", ""])
    for plot in plot_refs:
        lines.append(f"- `{plot['plot_type']}`: `{plot['path']}`")
    lines.append("")

    if conflicts:
        lines.extend(["## Conflict Audit", ""])
        for conflict in conflicts:
            lines.append(f"- `{conflict.dedupe_key}`: conflicting run_ids = `{', '.join(conflict.run_ids)}`")

    return "\n".join(lines)


def export_reports(
    context: ReportContext,
    run_df: pd.DataFrame,
    symbol_df: pd.DataFrame,
    timeseries_df: pd.DataFrame,
    strategy_summaries: dict[str, str],
    symbol_summaries: dict[str, str],
    plot_refs: list[dict[str, Any]],
    conflicts: list[DedupeConflict],
    audit_df: pd.DataFrame,
) -> dict[str, Any]:
    """Export JSON, CSV, markdown, timeseries, and AI summaries."""

    reports_dir = context.output_root / "reports"
    ai_root = context.output_root / "ai_summaries"
    executive_dir = ai_root / "executive"
    appendix_dir = ai_root / "appendix"
    artifacts_dir = context.output_root / "artifacts"
    timeseries_dir = artifacts_dir / "timeseries"

    ensure_directory(reports_dir)
    ensure_directory(executive_dir)
    ensure_directory(appendix_dir)
    ensure_directory(timeseries_dir)

    export_csv(reports_dir / "summary_runs.csv", run_df)
    export_csv(reports_dir / "summary_symbols.csv", symbol_df)
    export_csv(artifacts_dir / "dedupe_audit.csv", audit_df)
    export_csv(timeseries_dir / "timeseries_runs.csv", timeseries_df)

    conflicts_payload = {
        "run_tag": context.run_tag,
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": context.generated_at,
        "conflict_count": len(conflicts),
        "conflicts": [
            {
                "dedupe_key": item.dedupe_key,
                "symbol": item.symbol,
                "strategy_family": item.strategy_family,
                "strategy_label": item.strategy_label,
                "parameter_hash": item.parameter_hash,
                "run_ids": item.run_ids,
                "fingerprints": item.fingerprints,
            }
            for item in conflicts
        ],
    }
    write_json(artifacts_dir / "conflicts.json", conflicts_payload)

    for symbol, content in symbol_summaries.items():
        write_markdown(executive_dir / f"{sanitize_filename(symbol)}.md", content)
    for run_id, content in strategy_summaries.items():
        write_markdown(appendix_dir / f"{sanitize_filename(run_id)}.md", content)

    write_markdown(executive_dir / "symbol_executive_summaries.md", "\n\n".join(symbol_summaries[symbol] for symbol in sorted(symbol_summaries)))

    markdown = build_markdown_report(
        context=context,
        run_df=run_df,
        symbol_df=symbol_df,
        symbol_summaries=symbol_summaries,
        strategy_summaries=strategy_summaries,
        plot_refs=plot_refs,
        conflicts=conflicts,
    )
    write_markdown(reports_dir / "report.md", markdown)

    report_payload = {
        "run_tag": context.run_tag,
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": context.generated_at,
        "p2_output_root": str(context.p2_output_root),
        "run_metrics": run_df.to_dict(orient="records"),
        "symbol_metrics": symbol_df.to_dict(orient="records"),
        "plot_inventory": plot_refs,
        "conflicts": conflicts_payload,
        "dedupe_audit": audit_df.to_dict(orient="records"),
        "ai_summaries": strategy_summaries,
        "ai_symbol_summaries": symbol_summaries,
        "timeseries_runs_path": str(timeseries_dir / "timeseries_runs.csv"),
    }
    write_json(reports_dir / "report.json", report_payload)
    return report_payload


def create_archive(context: ReportContext) -> Path:
    """Archive the canonical report directory into a zip file."""

    archive_base = context.output_root.parent / f"{sanitize_filename(context.run_tag)}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=str(context.output_root))
    return Path(archive_path)


def remove_path(path: Path) -> None:
    """Remove a file, directory, or symlink when it exists."""

    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def sync_compatibility_root(context: ReportContext, archive_path: Optional[Path]) -> None:
    """Expose the latest report through the base p3 directory for backward compatibility."""

    compatibility_root = context.compatibility_root
    ensure_directory(compatibility_root)

    for name in [
        "summary_runs.csv",
        "summary_symbols.csv",
        "report.json",
        "report.md",
        "timeseries_runs.csv",
        "conflicts.json",
        "plots",
        "ai_summaries",
        "latest",
    ]:
        remove_path(compatibility_root / name)

    targets = {
        "summary_runs.csv": context.output_root / "reports" / "summary_runs.csv",
        "summary_symbols.csv": context.output_root / "reports" / "summary_symbols.csv",
        "report.json": context.output_root / "reports" / "report.json",
        "report.md": context.output_root / "reports" / "report.md",
        "timeseries_runs.csv": context.output_root / "artifacts" / "timeseries" / "timeseries_runs.csv",
        "conflicts.json": context.output_root / "artifacts" / "conflicts.json",
        "plots": context.output_root / "plots",
        "ai_summaries": context.output_root / "ai_summaries",
        "latest": context.output_root,
    }
    for name, target in targets.items():
        os.symlink(target, compatibility_root / name, target_is_directory=target.is_dir())

    if archive_path is not None:
        for old_zip in compatibility_root.glob("*.zip"):
            if old_zip.name != archive_path.name:
                old_zip.unlink()


def clean_legacy_outputs(compatibility_root: Path, canonical_dir: Path) -> None:
    """Remove unnecessary files and duplicate legacy folders once the canonical run exists."""

    for ds_store in compatibility_root.rglob(".DS_Store"):
        ds_store.unlink()
    parent_root = compatibility_root.parent
    for ds_store in parent_root.rglob(".DS_Store"):
        ds_store.unlink()

    incomplete_root = parent_root / "p3_fullrun"
    if incomplete_root.exists() and not (incomplete_root / "summary_runs.csv").exists():
        shutil.rmtree(incomplete_root)

    for child in compatibility_root.iterdir():
        if child == canonical_dir:
            continue
        if child.is_dir() and not child.is_symlink() and child.name not in {canonical_dir.name}:
            shutil.rmtree(child)


def validate_symbol_coverage(dataset: P2Dataset, run_df: pd.DataFrame) -> None:
    """Ensure all symbols from the P2 run summary are represented in the deduplicated output."""

    expected_symbols = {str(item.get("symbol") or "").upper() for item in dataset.run_summary.get("symbols") or []}
    actual_symbols = set(run_df["symbol"].unique().tolist()) if not run_df.empty else set()
    missing_symbols = sorted(expected_symbols - actual_symbols)
    if missing_symbols:
        raise ValueError(f"P3 parse missing symbols declared in run_summary.json: {missing_symbols}")


def validate_output_consistency(dataset: P2Dataset, run_df: pd.DataFrame, symbol_df: pd.DataFrame, strategy_summaries: dict[str, str], symbol_summaries: dict[str, str]) -> None:
    """Validate deduplicated output before publishing it."""

    expected_run_count = sum(int(item.get("success_count") or 0) for item in dataset.run_summary.get("symbols") or [])
    if len(run_df.index) != expected_run_count:
        raise ValueError(f"Deduplicated run count mismatch: expected {expected_run_count}, got {len(run_df.index)}")
    if len(symbol_df.index) != len(dataset.run_summary.get("symbols") or []):
        raise ValueError("Symbol-level summary count does not match run_summary.json.")
    if len(strategy_summaries) != len(run_df.index):
        raise ValueError("Strategy appendix summary count does not match deduplicated runs.")
    if len(symbol_summaries) != len(symbol_df.index):
        raise ValueError("Symbol executive summary count does not match symbol-level summary count.")


def build_context(args: argparse.Namespace) -> ReportContext:
    """Construct runtime context and canonical output directories."""

    p2_output_root = Path(args.p2_output).expanduser().resolve()
    if not p2_output_root.exists():
        raise FileNotFoundError(f"P2 output directory does not exist: {p2_output_root}")

    run_tag = args.run_tag or datetime.now(UTC).strftime("p3-%Y%m%dT%H%M%SZ")
    if args.dry_run:
        temp_root = Path(tempfile.mkdtemp(prefix="wolfystock-p3-dryrun-"))
        compatibility_root = temp_root / "p3"
        output_root = compatibility_root / sanitize_filename(run_tag)
        LOGGER.info("Dry-run mode enabled. Temporary output root: %s", output_root)
    else:
        compatibility_root = Path(args.output_root or DEFAULT_OUTPUT_ROOT).expanduser().resolve()
        output_root = compatibility_root / sanitize_filename(run_tag)

    ensure_directory(output_root)
    return ReportContext(
        p2_output_root=p2_output_root,
        output_root=output_root,
        run_tag=run_tag,
        dry_run=bool(args.dry_run),
        generated_at=datetime.now(UTC).isoformat(),
        compatibility_root=compatibility_root,
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for the P3 workflow."""

    parser = argparse.ArgumentParser(description="Generate WolfyStock P3 reports from P2 outputs.")
    parser.add_argument("--p2-output", required=True, help="Path to the P2 output directory.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Base output directory for P3 artifacts.")
    parser.add_argument("--run-tag", default="", help="Optional run tag.")
    parser.add_argument("--dry-run", action="store_true", help="Use temporary output only and do not write permanent files.")
    return parser.parse_args(argv)


def run(argv: Optional[list[str]] = None) -> int:
    """Execute the complete P3 workflow."""

    configure_logging()
    args = parse_args(argv)
    context = build_context(args)
    LOGGER.info("WolfyStock P3 start: p2_output=%s dry_run=%s run_tag=%s", context.p2_output_root, context.dry_run, context.run_tag)

    dataset = load_p2_dataset(context.p2_output_root)
    deduped_runs, conflicts, audit_df = deduplicate_runs(dataset.runs)
    run_df, timeseries_df = build_run_and_timeseries_frames(
        deduped_runs,
        run_tag=context.run_tag,
        generated_at=context.generated_at,
        conflicts=conflicts,
    )
    symbol_df = aggregate_symbol_metrics(run_df, context.generated_at, context.run_tag)
    strategy_summaries, symbol_summaries = generate_ai_summaries(run_df, dataset)
    plot_refs = generate_visualizations(dataset, run_df, symbol_df, timeseries_df, audit_df, context.output_root)

    validate_symbol_coverage(dataset, run_df)
    validate_output_consistency(dataset, run_df, symbol_df, strategy_summaries, symbol_summaries)

    export_reports(
        context=context,
        run_df=run_df,
        symbol_df=symbol_df,
        timeseries_df=timeseries_df,
        strategy_summaries=strategy_summaries,
        symbol_summaries=symbol_summaries,
        plot_refs=plot_refs,
        conflicts=conflicts,
        audit_df=audit_df,
    )

    archive_path = None if context.dry_run else create_archive(context)
    if not context.dry_run:
        sync_compatibility_root(context, archive_path)
        clean_legacy_outputs(context.compatibility_root, context.output_root)

    LOGGER.info(
        "WolfyStock P3 finished: deduped_runs=%s symbols=%s plots=%s conflicts=%s archive=%s",
        len(run_df.index),
        len(symbol_df.index),
        len(plot_refs),
        len(conflicts),
        archive_path or "dry-run-temp-only",
    )
    return 0


def main() -> int:
    """CLI entry point."""

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
