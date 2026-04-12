# -*- coding: utf-8 -*-
"""Shared helpers for deterministic backtest API smoke scripts."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Tuple

from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import get_database_manager
from src.config import Config
from src.storage import DatabaseManager, StockDaily

REPO_ROOT = Path(__file__).resolve().parents[1]
FAKE_PARQUET_ENV = "BACKTEST_SMOKE_FAKE_PARQUET"
ASYNC_DELAY_ENV = "BACKTEST_SMOKE_ASYNC_DELAY_MS"
DISABLE_LLM_ENV = "BACKTEST_SMOKE_DISABLE_LLM"
TERMINAL_RULE_RUN_STATUSES = {"completed", "failed", "cancelled"}


@dataclass
class BacktestSmokeRuntime:
    temp_dir: tempfile.TemporaryDirectory[str]
    root: Path
    database_path: Path
    env_file: Path
    local_parquet_dir: Path
    patch_dir: Path
    output_dir: Path
    env: Dict[str, str]
    db: DatabaseManager


@dataclass
class BacktestSmokeServer:
    process: subprocess.Popen[str]
    host: str
    port: int
    base_url: str
    health_url: str

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 90,
    ) -> Tuple[int, Any]:
        query = ""
        if params:
            query = "?" + urllib.parse.urlencode(
                {key: value for key, value in params.items() if value is not None}
            )
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self.base_url}{path}{query}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
                return response.status, json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                parsed = json.loads(body) if body else None
            except json.JSONDecodeError:
                parsed = body
            return exc.code, parsed

    def wait_for_rule_status(
        self,
        run_id: int,
        *,
        target_statuses: set[str],
        timeout_seconds: int = 60,
    ) -> Dict[str, Any]:
        deadline = time.time() + timeout_seconds
        last_payload: Dict[str, Any] = {}
        while time.time() < deadline:
            status_code, payload = self.request("GET", f"/api/v1/backtest/rule/runs/{run_id}/status", timeout_seconds=15)
            if status_code != 200 or not isinstance(payload, dict):
                time.sleep(0.25)
                continue
            last_payload = payload
            status = str(payload.get("status") or "")
            if status in target_statuses:
                return payload
            if status in TERMINAL_RULE_RUN_STATUSES and status not in target_statuses:
                raise RuntimeError(f"run {run_id} reached unexpected terminal status: {status}")
            time.sleep(0.25)
        raise RuntimeError(f"timed out waiting for run {run_id} status; last payload={last_payload}")


def _reset_runtime_singletons() -> None:
    DatabaseManager.reset_instance()
    Config._instance = None


def _set_env_var(key: str, value: Optional[str], originals: Dict[str, Optional[str]]) -> None:
    if key not in originals:
        originals[key] = os.environ.get(key)
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


def _build_pythonpath_entries(*entries: str) -> str:
    normalized: list[str] = []
    for entry in entries:
        if entry and entry not in normalized:
            normalized.append(entry)
    return os.pathsep.join(normalized)


def _write_smoke_sitecustomize(patch_dir: Path) -> None:
    patch_dir.mkdir(parents=True, exist_ok=True)
    (patch_dir / "sitecustomize.py").write_text(
        """
import os
import time
from pathlib import Path

try:
    import pandas as pd
except Exception:
    pd = None
else:
    _orig_read_parquet = getattr(pd, "read_parquet", None)

    def _smoke_read_parquet(path, *args, **kwargs):
        fake_mode = os.getenv("BACKTEST_SMOKE_FAKE_PARQUET", "").strip().lower()
        path_obj = Path(path)
        if fake_mode == "json" and path_obj.suffix == ".parquet" and path_obj.exists():
            return pd.read_json(path_obj)
        if _orig_read_parquet is None:
            raise ImportError("pandas parquet engine is unavailable")
        return _orig_read_parquet(path, *args, **kwargs)

    pd.read_parquet = _smoke_read_parquet

try:
    from src.services.rule_backtest_service import RuleBacktestService
except Exception:
    RuleBacktestService = None
else:
    _orig_process_submitted_run = RuleBacktestService.process_submitted_run
    _orig_build_ai_summary = RuleBacktestService._build_ai_summary

    def _smoke_process_submitted_run(self, run_id):
        delay_ms = int(os.getenv("BACKTEST_SMOKE_ASYNC_DELAY_MS", "0") or 0)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
        return _orig_process_submitted_run(self, run_id)

    def _smoke_build_ai_summary(self, parsed, result):
        if os.getenv("BACKTEST_SMOKE_DISABLE_LLM", "1").strip().lower() not in {"", "0", "false", "no"}:
            return "Smoke summary"
        return _orig_build_ai_summary(self, parsed, result)

    RuleBacktestService.process_submitted_run = _smoke_process_submitted_run
    RuleBacktestService._build_ai_summary = _smoke_build_ai_summary
""".strip()
        + "\n",
        encoding="utf-8",
    )


@contextmanager
def temporary_backtest_runtime(
    *,
    eval_window_days: int = 5,
    min_age_days: int = 14,
    async_delay_ms: int = 0,
) -> Generator[BacktestSmokeRuntime, None, None]:
    temp_dir = tempfile.TemporaryDirectory()
    root = Path(temp_dir.name)
    database_path = root / "smoke_backtest.db"
    env_file = root / "smoke.env"
    local_parquet_dir = root / "local_us_parquet"
    patch_dir = root / "python_shims"
    output_dir = root / "outputs"
    local_parquet_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    env_file.write_text("ADMIN_AUTH_ENABLED=false\n", encoding="utf-8")
    _write_smoke_sitecustomize(patch_dir)

    originals: Dict[str, Optional[str]] = {}
    env_overrides = {
        "DATABASE_PATH": str(database_path),
        "BACKTEST_EVAL_WINDOW_DAYS": str(eval_window_days),
        "BACKTEST_MIN_AGE_DAYS": str(min_age_days),
        "ADMIN_AUTH_ENABLED": "false",
        "ENV_FILE": str(env_file),
        "LOCAL_US_PARQUET_DIR": str(local_parquet_dir),
        FAKE_PARQUET_ENV: "json",
        ASYNC_DELAY_ENV: str(async_delay_ms),
        DISABLE_LLM_ENV: "1",
    }
    for key, value in env_overrides.items():
        _set_env_var(key, value, originals)

    pythonpath = _build_pythonpath_entries(
        str(patch_dir),
        str(REPO_ROOT),
        os.environ.get("PYTHONPATH", ""),
    )
    _set_env_var("PYTHONPATH", pythonpath, originals)

    _reset_runtime_singletons()
    db = DatabaseManager.get_instance()
    runtime = BacktestSmokeRuntime(
        temp_dir=temp_dir,
        root=root,
        database_path=database_path,
        env_file=env_file,
        local_parquet_dir=local_parquet_dir,
        patch_dir=patch_dir,
        output_dir=output_dir,
        env=dict(os.environ),
        db=db,
    )

    try:
        yield runtime
    finally:
        _reset_runtime_singletons()
        for key, value in originals.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        temp_dir.cleanup()


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _tail_process_output(process: subprocess.Popen[str]) -> str:
    if process.stdout is None:
        return ""
    if process.poll() is None:
        return ""
    try:
        remaining = process.stdout.read()
    except Exception:
        remaining = ""
    return remaining[-4000:]


def _wait_for_server(server: BacktestSmokeServer, *, timeout_seconds: int = 45) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if server.process.poll() is not None:
            break
        try:
            with urllib.request.urlopen(server.health_url, timeout=5) as response:
                body = response.read().decode("utf-8")
                payload = json.loads(body) if body else None
                if response.status == 200 and isinstance(payload, dict) and payload.get("status") == "ok":
                    return
        except Exception:
            time.sleep(0.25)
            continue
    if server.process.poll() is None:
        _stop_server(server.process)
    output = _tail_process_output(server.process)
    raise RuntimeError(f"uvicorn did not become ready in time.\n{output}")


def _stop_server(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@contextmanager
def temporary_backtest_server(
    runtime: BacktestSmokeRuntime,
    *,
    port: Optional[int] = None,
) -> Generator[BacktestSmokeServer, None, None]:
    resolved_port = port or _find_free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.app:app", "--host", "127.0.0.1", "--port", str(resolved_port)],
        cwd=str(REPO_ROOT),
        env=dict(runtime.env),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    server = BacktestSmokeServer(
        process=process,
        host="127.0.0.1",
        port=resolved_port,
        base_url=f"http://127.0.0.1:{resolved_port}",
        health_url=f"http://127.0.0.1:{resolved_port}/api/health",
    )
    try:
        _wait_for_server(server)
        yield server
    finally:
        _stop_server(process)


def build_us_price_rows(
    *,
    days: int = 320,
    end_date: Optional[date] = None,
    start_price: float = 120.0,
) -> list[dict[str, Any]]:
    resolved_end = end_date or (datetime.now().date() - timedelta(days=1))
    resolved_start = resolved_end - timedelta(days=days - 1)
    rows: list[dict[str, Any]] = []
    for index in range(days):
        point_date = resolved_start + timedelta(days=index)
        wave = ((index % 19) - 9) * 0.55
        drift = index * 0.18
        close = round(start_price + drift + wave, 4)
        open_price = round(close - 0.45 + ((index % 3) - 1) * 0.12, 4)
        high = round(max(open_price, close) + 0.9, 4)
        low = round(min(open_price, close) - 0.9, 4)
        rows.append(
            {
                "date": point_date.isoformat(),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1_000_000 + index * 500,
                "amount": round(close * (1_000_000 + index * 500), 4),
                "pct_chg": 0.0,
            }
        )
    return rows


def write_fake_local_us_parquet(
    runtime: BacktestSmokeRuntime,
    *,
    symbol: str,
    rows: list[dict[str, Any]],
) -> Path:
    destination = runtime.local_parquet_dir / f"{symbol.upper()}.parquet"
    destination.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return destination


def seed_local_us_history_fixture(
    runtime: BacktestSmokeRuntime,
    *,
    code: str = "AAPL",
    days: int = 320,
) -> tuple[str, str]:
    rows = build_us_price_rows(days=days)
    write_fake_local_us_parquet(runtime, symbol=code, rows=rows)
    start_index = min(150, max(10, days // 2))
    end_index = max(start_index + 60, days - 2)
    end_index = min(end_index, days - 2)
    return rows[start_index]["date"], rows[end_index]["date"]


def get_stock_daily_sources(db: DatabaseManager, *, code: str) -> list[str]:
    with db.get_session() as session:
        rows = session.query(StockDaily.data_source).filter(StockDaily.code == code).all()
    unique_sources: list[str] = []
    for (source,) in rows:
        normalized = str(source or "").strip()
        if normalized and normalized not in unique_sources:
            unique_sources.append(normalized)
    return unique_sources


def assert_json_keys(label: str, payload: Any, keys: list[str]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} expected JSON object, got {type(payload).__name__}")
    missing = [key for key in keys if key not in payload]
    if missing:
        raise RuntimeError(f"{label} missing keys: {missing}")
    return payload


@contextmanager
def temporary_backtest_client(
    *,
    eval_window_days: int = 3,
    min_age_days: int = 14,
) -> Generator[Tuple[TestClient, DatabaseManager], None, None]:
    with temporary_backtest_runtime(
        eval_window_days=eval_window_days,
        min_age_days=min_age_days,
    ) as runtime:
        app = create_app()
        app.dependency_overrides[get_database_manager] = lambda: runtime.db
        with TestClient(app) as client:
            yield client, runtime.db
