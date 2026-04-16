# -*- coding: utf-8 -*-
"""Smoke tests for the dedicated portfolio snapshot benchmark script."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "benchmark_portfolio_snapshot.py"


class PortfolioSnapshotBenchmarkScriptTestCase(unittest.TestCase):
    def test_script_writes_json_results_for_requested_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "portfolio_snapshot_benchmark.json"
            cmd = [
                "python3",
                str(SCRIPT_PATH),
                "--account-counts",
                "1,2",
                "--symbol-counts",
                "2",
                "--trades-per-symbol",
                "1",
                "--warm-runs",
                "1",
                "--output",
                str(output_path),
            ]
            completed = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr or completed.stdout)
            self.assertTrue(output_path.exists())

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["scenario_count"], 2)
            self.assertEqual(len(payload["results"]), 2)
            first = payload["results"][0]
            self.assertIn("scenario", first)
            self.assertIn("cold_read", first)
            self.assertIn("warm_read", first)
            self.assertIn("lookup_counts", first["cold_read"])
            self.assertIn("lookup_counts", first["warm_read"])


if __name__ == "__main__":
    unittest.main()
