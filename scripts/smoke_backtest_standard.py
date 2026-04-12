# -*- coding: utf-8 -*-
"""Compatibility wrapper for the standard backtest smoke suite."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from test_backtest_basic import main


if __name__ == "__main__":
    raise SystemExit(main())
