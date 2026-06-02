# -*- coding: utf-8 -*-
"""Tests for health check endpoints: /api/health and /api/v1/health."""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app


class HealthEndpointTestCase(unittest.TestCase):
    """Both /api/health and /api/v1/health should return 200 with valid payload."""

    @classmethod
    def setUpClass(cls):
        temp_dir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp_dir.cleanup)
        cls.client = TestClient(create_app(static_dir=Path(temp_dir.name)))

    def test_api_health_returns_200(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("timestamp", body)

    def test_api_v1_health_returns_200(self):
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("timestamp", body)


if __name__ == "__main__":
    unittest.main()
