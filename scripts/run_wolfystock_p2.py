"""CLI wrapper for the WolfyStock P2 local-parquet runner."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.wolfystock_p2_runner import main


if __name__ == "__main__":
    raise SystemExit(main())
