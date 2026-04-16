#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WS1 reproducible baseline capture harness (no optimization logic)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "ws1_baseline"


@dataclass
class StepResult:
    name: str
    kind: str
    ok: bool
    status_code: Optional[int]
    duration_ms: int
    error: Optional[str]
    request: Dict[str, Any]
    response_excerpt: Optional[Any]


class BaselineCaptureError(RuntimeError):
    """Raised when strict mode requires an immediate stop."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_json(
    *,
    base_url: str,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]],
    timeout_seconds: int,
) -> tuple[Optional[int], Optional[Any], Optional[str]]:
    url = f"{base_url.rstrip('/')}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
            body = json.loads(raw) if raw else None
            return resp.status, body, None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            body = raw
        return exc.code, body, None
    except Exception as exc:  # pylint: disable=broad-except
        return None, None, str(exc)


def _run_api_step(
    *,
    name: str,
    base_url: str,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]],
    timeout_seconds: int,
) -> StepResult:
    started = time.perf_counter()
    status_code, body, error = _request_json(
        base_url=base_url,
        method=method,
        path=path,
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    elapsed = int((time.perf_counter() - started) * 1000)
    ok = error is None and status_code is not None and 200 <= int(status_code) < 300

    excerpt: Any = body
    if isinstance(body, dict) and len(body) > 12:
        excerpt = {"keys": sorted(body.keys()), "sample": {k: body[k] for k in list(body.keys())[:6]}}

    return StepResult(
        name=name,
        kind="api",
        ok=ok,
        status_code=status_code,
        duration_ms=elapsed,
        error=error,
        request={"method": method, "path": path, "payload": payload},
        response_excerpt=excerpt,
    )


def _run_cmd_step(*, name: str, command: list[str], timeout_seconds: int) -> StepResult:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        output_excerpt = {
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
        }
        return StepResult(
            name=name,
            kind="command",
            ok=completed.returncode == 0,
            status_code=completed.returncode,
            duration_ms=elapsed,
            error=None,
            request={"command": command},
            response_excerpt=output_excerpt,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        return StepResult(
            name=name,
            kind="command",
            ok=False,
            status_code=None,
            duration_ms=elapsed,
            error=f"timeout after {timeout_seconds}s: {exc}",
            request={"command": command},
            response_excerpt=None,
        )


def _assert_or_continue(result: StepResult, strict: bool) -> None:
    if strict and not result.ok:
        raise BaselineCaptureError(f"Step failed in strict mode: {result.name}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture WS1 baseline timings for scanner/portfolio/analysis/backtest.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Running API base URL.")
    parser.add_argument("--stock-code", default="AAPL", help="Stock code used for analysis baseline call.")
    parser.add_argument("--scanner-market", default="cn", choices=["cn", "us", "hk"], help="Scanner market.")
    parser.add_argument("--scanner-profile", default="cn_preopen_v1", help="Scanner profile key.")
    parser.add_argument("--timeout-seconds", type=int, default=180, help="Per-step timeout seconds.")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output json path. Default: reports/ws1_baseline/baseline_<UTC timestamp>.json",
    )
    parser.add_argument(
        "--skip-backtest-smoke",
        action="store_true",
        help="Skip backtest smoke command steps.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Stop immediately when any step fails.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    started_at = _now_iso()

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = (DEFAULT_OUTPUT_DIR / f"baseline_{stamp}.json").resolve()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    steps: list[StepResult] = []

    auth_status = _run_api_step(
        name="auth_status",
        base_url=args.base_url,
        method="GET",
        path="/api/v1/auth/status",
        payload=None,
        timeout_seconds=args.timeout_seconds,
    )
    steps.append(auth_status)
    _assert_or_continue(auth_status, args.strict)

    scanner = _run_api_step(
        name="scanner_run",
        base_url=args.base_url,
        method="POST",
        path="/api/v1/scanner/run",
        payload={
            "market": args.scanner_market,
            "profile": args.scanner_profile,
            "shortlist_size": 5,
            "detail_limit": 50,
        },
        timeout_seconds=args.timeout_seconds,
    )
    steps.append(scanner)
    _assert_or_continue(scanner, args.strict)

    portfolio_snapshot = _run_api_step(
        name="portfolio_snapshot",
        base_url=args.base_url,
        method="GET",
        path="/api/v1/portfolio/snapshot",
        payload=None,
        timeout_seconds=args.timeout_seconds,
    )
    steps.append(portfolio_snapshot)
    _assert_or_continue(portfolio_snapshot, args.strict)

    analysis = _run_api_step(
        name="analysis_search_sync",
        base_url=args.base_url,
        method="POST",
        path="/api/v1/analysis/analyze",
        payload={
            "stock_code": args.stock_code,
            "report_type": "brief",
            "force_refresh": False,
            "async_mode": False,
        },
        timeout_seconds=args.timeout_seconds,
    )
    steps.append(analysis)
    _assert_or_continue(analysis, args.strict)

    if not args.skip_backtest_smoke:
        backtest_standard = _run_cmd_step(
            name="backtest_standard_smoke",
            command=[sys.executable, "scripts/smoke_backtest_standard.py"],
            timeout_seconds=args.timeout_seconds,
        )
        steps.append(backtest_standard)
        _assert_or_continue(backtest_standard, args.strict)

        backtest_rule = _run_cmd_step(
            name="backtest_rule_smoke",
            command=[sys.executable, "scripts/smoke_backtest_rule.py"],
            timeout_seconds=args.timeout_seconds,
        )
        steps.append(backtest_rule)
        _assert_or_continue(backtest_rule, args.strict)

    finished_at = _now_iso()
    payload = {
        "ws": "WS1",
        "generated_at": finished_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "base_url": args.base_url,
        "cwd": str(REPO_ROOT),
        "python": sys.executable,
        "strict": args.strict,
        "skip_backtest_smoke": args.skip_backtest_smoke,
        "env_hints": {
            "ADMIN_AUTH_ENABLED": os.getenv("ADMIN_AUTH_ENABLED"),
            "ENV_FILE": os.getenv("ENV_FILE"),
        },
        "steps": [asdict(item) for item in steps],
        "summary": {
            "total_steps": len(steps),
            "passed_steps": sum(1 for step in steps if step.ok),
            "failed_steps": [step.name for step in steps if not step.ok],
        },
    }

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"output": str(output_path), **payload["summary"]}, ensure_ascii=False))
    return 0 if not payload["summary"]["failed_steps"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
