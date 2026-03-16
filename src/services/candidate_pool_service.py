# -*- coding: utf-8 -*-
"""Candidate pool service for screening outputs."""

from __future__ import annotations

from datetime import date
from typing import Dict, Optional

from src.storage import DatabaseManager


class CandidatePoolService:
    """Build a stable candidate pool payload from the latest screening run."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def build_pool(self, *, as_of_date: Optional[date] = None) -> Dict:
        run = self._latest_screening_run(as_of_date=as_of_date)
        if run is None:
            return {"run_id": None, "trade_date": None, "market": None, "items": []}
        return {
            "run_id": run["run_id"],
            "trade_date": run["trade_date"],
            "market": run["market"],
            "items": self.db.list_screening_candidates(run["run_id"], as_of_date=as_of_date),
        }

    def _latest_screening_run(self, *, as_of_date: Optional[date]) -> Optional[Dict]:
        runs = self.db.list_screening_runs(limit=20)
        for run in runs:
            if run["status"] not in {"completed", "completed_with_ai_degraded"}:
                continue
            if as_of_date is not None and run["trade_date"] and run["trade_date"] > as_of_date.isoformat():
                continue
            return run
        return None
