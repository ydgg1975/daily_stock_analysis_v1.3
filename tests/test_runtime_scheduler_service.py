# -*- coding: utf-8 -*-
"""Tests for RuntimeSchedulerService lifecycle, manual run, and status."""

import sys
import threading
import unittest
from datetime import datetime
from unittest.mock import patch

from src.services.runtime_scheduler_service import RuntimeSchedulerService


class _FakeJob:
    def __init__(self, schedule_module):
        self._schedule_module = schedule_module
        self.next_run = datetime(2026, 1, 1, 18, 0, 0)
        self.at_time = None

    @property
    def day(self):
        return self

    def at(self, value):
        self.at_time = value
        hour, minute = [int(part) for part in value.split(":")]
        self.next_run = datetime(2026, 1, 1, hour, minute, 0)
        return self

    def do(self, fn):
        self.job_func = fn
        self._schedule_module.jobs.append(self)
        return self


class _FakeScheduleModule:
    def __init__(self):
        self.jobs = []

    def every(self):
        return _FakeJob(self)

    def get_jobs(self):
        return list(self.jobs)

    def run_pending(self):
        return None

    def cancel_job(self, job):
        self.jobs.remove(job)


class RuntimeSchedulerServiceTestCase(unittest.TestCase):
    def setUp(self):
        self._fake_schedule = _FakeScheduleModule()
        self._patch = patch.dict(sys.modules, {"schedule": self._fake_schedule})
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def _make_service(self, **overrides):
        params = dict(
            task=lambda: None,
            schedule_times_provider=lambda: ["09:20", "12:30"],
            enabled_provider=lambda: True,
        )
        params.update(overrides)
        return RuntimeSchedulerService(**params)

    def test_start_registers_jobs_and_stop_terminates(self):
        service = self._make_service()
        self.addCleanup(service.stop)

        self.assertTrue(service.start())
        self.assertTrue(service.is_running())
        self.assertEqual(
            sorted(job.at_time for job in self._fake_schedule.jobs),
            ["09:20", "12:30"],
        )

        self.assertFalse(service.start())

        service.stop()
        self.assertFalse(service.is_running())

    def test_start_skipped_when_disabled(self):
        service = self._make_service(enabled_provider=lambda: False)
        self.assertFalse(service.start())
        self.assertFalse(service.is_running())

    def test_start_skipped_when_no_valid_times(self):
        service = self._make_service(schedule_times_provider=lambda: [])
        self.assertFalse(service.start())
        self.assertFalse(service.is_running())

    def test_reconcile_starts_and_stops_with_enabled_flag(self):
        enabled = {"value": False}
        service = self._make_service(enabled_provider=lambda: enabled["value"])
        self.addCleanup(service.stop)

        self.assertFalse(service.reconcile_from_config())
        self.assertFalse(service.is_running())

        enabled["value"] = True
        self.assertTrue(service.reconcile_from_config())
        self.assertTrue(service.is_running())

        enabled["value"] = False
        self.assertFalse(service.reconcile_from_config())
        self.assertFalse(service.is_running())

    def test_reconcile_while_running_does_not_restart_thread(self):
        service = self._make_service()
        self.addCleanup(service.stop)
        self.assertTrue(service.start())
        running_thread = service._thread

        with patch.object(service._scheduler, "request_refresh") as refresh:
            self.assertTrue(service.reconcile_from_config())

        refresh.assert_called_once()
        self.assertIs(service._thread, running_thread)
        self.assertTrue(service.is_running())

    def test_run_now_executes_task_and_records_status(self):
        done = threading.Event()
        calls = []

        def _task():
            calls.append(1)
            done.set()

        service = self._make_service(task=_task)
        self.assertTrue(service.run_now())
        self.assertTrue(done.wait(timeout=5))

        for _ in range(50):
            if not service.status()["task_running"]:
                break
            threading.Event().wait(0.02)

        status = service.status()
        self.assertEqual(calls, [1])
        self.assertEqual(status["run_count"], 1)
        self.assertTrue(status["last_success"])
        self.assertIsNone(status["last_error"])

    def test_run_now_records_failure_without_crashing(self):
        done = threading.Event()

        def _task():
            try:
                raise RuntimeError("boom")
            finally:
                done.set()

        service = self._make_service(task=_task)
        self.assertTrue(service.run_now())
        self.assertTrue(done.wait(timeout=5))

        for _ in range(50):
            if not service.status()["task_running"]:
                break
            threading.Event().wait(0.02)

        status = service.status()
        self.assertEqual(status["run_count"], 1)
        self.assertFalse(status["last_success"])
        self.assertIn("boom", status["last_error"])

    def test_run_now_guards_against_overlap(self):
        release = threading.Event()
        started = threading.Event()

        def _task():
            started.set()
            release.wait(timeout=5)

        service = self._make_service(task=_task)
        self.assertTrue(service.run_now())
        self.assertTrue(started.wait(timeout=5))

        self.assertFalse(service.run_now())

        release.set()

    def test_status_reports_enabled_and_times_when_not_started(self):
        service = self._make_service()
        status = service.status()
        self.assertTrue(status["enabled"])
        self.assertFalse(status["scheduler_running"])
        self.assertEqual(status["schedule_times"], ["09:20", "12:30"])

    def test_scheduled_run_suppressed_when_a_task_is_already_running(self):
        ran = []
        service = self._make_service(task=lambda: ran.append(1))
        service._status["task_running"] = True

        service._wrapped_task()

        self.assertEqual(ran, [])
        status = service.status()
        self.assertEqual(status["run_count"], 0)
        self.assertEqual(status["skipped_count"], 1)
        self.assertIsNotNone(status["last_skipped_reason"])
        self.assertIn("抑制", status["last_skipped_reason"])

    def test_failure_records_status_and_continues(self):
        def _boom():
            raise RuntimeError("kaboom")

        service = self._make_service(task=_boom)
        service._wrapped_task()

        status = service.status()
        self.assertEqual(status["run_count"], 1)
        self.assertFalse(status["last_success"])
        self.assertIn("kaboom", status["last_error"])
        self.assertFalse(status["task_running"])


if __name__ == "__main__":
    unittest.main()
