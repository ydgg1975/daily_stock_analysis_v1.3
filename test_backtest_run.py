#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the standard and/or rule backtest smoke suites."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from test_backtest_basic import main as run_standard_smoke
from test_backtest_rule import main as run_rule_smoke


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
        run_standard_smoke()
    if args.mode in {"both", "rule"}:
        run_rule_smoke()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
