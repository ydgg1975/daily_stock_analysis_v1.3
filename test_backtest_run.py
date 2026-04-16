#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the standard and/or rule backtest smoke suites via canonical scripts/ entrypoints."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _run_script(script_path: str) -> int:
    completed = subprocess.run(
        [sys.executable, script_path],
        cwd=str(REPO_ROOT),
        check=False,
    )
    return int(completed.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run backtest smoke suites.")
    parser.add_argument(
        "--mode",
        choices=["both", "standard", "rule"],
        default="both",
        help="Select which smoke flow to run.",
    )
    args = parser.parse_args(argv)

    if args.mode in {"both", "standard"}:
        code = _run_script("scripts/smoke_backtest_standard.py")
        if code != 0:
            return code
    if args.mode in {"both", "rule"}:
        code = _run_script("scripts/smoke_backtest_rule.py")
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
