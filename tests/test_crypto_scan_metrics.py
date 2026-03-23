# -*- coding: utf-8 -*-
"""Tests for CryptoScanMetric model and repository methods."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import pytest
from datetime import datetime, timedelta
from src.storage import DatabaseManager, CryptoScanMetric


@pytest.mark.not_network
class TestCryptoScanMetric:

    def setup_method(self):
        self.db = DatabaseManager(db_url="sqlite:///:memory:")
        self.db._initialized = False
        self.db.__init__(db_url="sqlite:///:memory:")

    def test_save_and_retrieve_metric(self):
        now = datetime.now()
        self.db.save_scan_metric(
            scan_id="abc12345",
            started_at=now,
            finished_at=now,
            duration_ms=1200,
            chains_total=3,
            chains_failed=1,
            launches_new=5,
            launches_updated=2,
            per_chain_json=json.dumps({"bsc": {"duration_ms": 400}}),
            success=True,
        )
        metrics = self.db.get_scan_metrics(limit=10)
        assert len(metrics) == 1
        m = metrics[0]
        assert m["scan_id"] == "abc12345"
        assert m["duration_ms"] == 1200
        assert m["chains_total"] == 3
        assert m["chains_failed"] == 1
        assert m["launches_new"] == 5
        assert m["launches_updated"] == 2
        assert m["success"] is True

    def test_get_scan_metrics_since_filter(self):
        old = datetime.now() - timedelta(hours=2)
        recent = datetime.now()
        self.db.save_scan_metric(
            scan_id="old00001", started_at=old, finished_at=old,
            duration_ms=500, chains_total=1, chains_failed=0,
            launches_new=1, launches_updated=0, success=True,
        )
        self.db.save_scan_metric(
            scan_id="new00001", started_at=recent, finished_at=recent,
            duration_ms=600, chains_total=2, chains_failed=0,
            launches_new=3, launches_updated=1, success=True,
        )
        since = datetime.now() - timedelta(hours=1)
        metrics = self.db.get_scan_metrics(since=since)
        assert len(metrics) == 1
        assert metrics[0]["scan_id"] == "new00001"

    def test_metrics_ordered_newest_first(self):
        for i in range(3):
            t = datetime.now() - timedelta(minutes=30 - i * 10)
            self.db.save_scan_metric(
                scan_id=f"scan{i:04d}", started_at=t, finished_at=t,
                duration_ms=100 * (i + 1), chains_total=1, chains_failed=0,
                launches_new=1, launches_updated=0, success=True,
            )
        metrics = self.db.get_scan_metrics()
        assert len(metrics) == 3
        assert metrics[0]["scan_id"] == "scan0002"

    def test_failed_scan_metric(self):
        now = datetime.now()
        self.db.save_scan_metric(
            scan_id="fail0001", started_at=now, finished_at=now,
            duration_ms=100, chains_total=2, chains_failed=2,
            launches_new=0, launches_updated=0, success=False,
        )
        metrics = self.db.get_scan_metrics()
        assert metrics[0]["success"] is False
        assert metrics[0]["chains_failed"] == 2
