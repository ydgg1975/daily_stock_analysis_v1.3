# -*- coding: utf-8 -*-
"""Tests for app liveness/readiness and task queue lifecycle wiring."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app


class _SessionStub:
    def __init__(self) -> None:
        self.executed = []

    def execute(self, statement):
        self.executed.append(str(statement))
        return 1

    def close(self) -> None:
        return None


class _DatabaseStub:
    def __init__(self) -> None:
        self.session = _SessionStub()

    def get_session(self):
        return self.session


class _QueueStub:
    def __init__(self, runtime_status: dict | None = None) -> None:
        self.runtime_status = runtime_status or {
            "mode": "process_local",
            "single_process_required": True,
            "configured_worker_count": 1,
            "topology_ok": True,
            "shutdown": False,
            "accepting_new_tasks": True,
            "worker_hints": {},
        }
        self.shutdown_calls = []

    def get_runtime_status(self) -> dict:
        return dict(self.runtime_status)

    def shutdown(self, *, wait: bool = False, cancel_futures: bool = True) -> None:
        self.shutdown_calls.append((wait, cancel_futures))


class ApiAppHealthTestCase(unittest.TestCase):
    def _make_app(self, *, queue_stub: _QueueStub | None = None, db_stub: _DatabaseStub | None = None):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        static_dir = Path(temp_dir.name)
        queue = queue_stub or _QueueStub()
        db = db_stub or _DatabaseStub()
        service = object()
        patches = [
            patch("api.app.SystemConfigService", return_value=service),
            patch("api.app.get_task_queue", return_value=queue),
            patch("api.app.get_db", return_value=db),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        app = create_app(static_dir=static_dir)
        return app, queue, db

    def test_live_health_endpoint_reports_process_alive(self) -> None:
        app, _, _ = self._make_app()

        with TestClient(app) as client:
            response = client.get("/api/health/live")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "live")
        self.assertIs(payload["ready"], True)

    def test_ready_health_endpoint_checks_storage_and_queue_topology(self) -> None:
        app, _, db = self._make_app()

        with TestClient(app) as client:
            response = client.get("/api/health/ready")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "ready")
        self.assertIs(payload["ready"], True)
        self.assertEqual(payload["checks"]["storage"]["status"], "ok")
        self.assertEqual(payload["checks"]["task_queue"]["status"], "ok")
        self.assertTrue(db.session.executed)

    def test_default_health_alias_uses_readiness_contract(self) -> None:
        app, _, _ = self._make_app()

        with TestClient(app) as client:
            response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "ready")
        self.assertIs(payload["ready"], True)

    def test_ready_health_returns_503_when_task_queue_topology_is_unsafe(self) -> None:
        queue = _QueueStub(
            runtime_status={
                "mode": "process_local",
                "single_process_required": True,
                "configured_worker_count": 2,
                "topology_ok": False,
                "shutdown": False,
                "accepting_new_tasks": True,
                "worker_hints": {"WEB_CONCURRENCY": 2},
            }
        )
        app, _, _ = self._make_app(queue_stub=queue)

        with TestClient(app) as client:
            response = client.get("/api/health/ready")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "not_ready")
        self.assertIs(payload["ready"], False)
        self.assertEqual(payload["checks"]["task_queue"]["status"], "not_ready")

    def test_app_lifespan_shuts_down_task_queue_explicitly(self) -> None:
        queue = _QueueStub()
        app, _, _ = self._make_app(queue_stub=queue)

        with TestClient(app) as client:
            response = client.get("/api/health/live")
            self.assertEqual(response.status_code, 200)

        self.assertEqual(queue.shutdown_calls, [(False, True)])


if __name__ == "__main__":
    unittest.main()
