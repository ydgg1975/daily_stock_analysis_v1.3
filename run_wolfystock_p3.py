"""CLI wrapper for the WolfyStock P3 report generator."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.wolfystock_p3_report import main


if __name__ == "__main__":
    raise SystemExit(main())
