# -*- coding: utf-8 -*-
"""Tests for Scheduler background task support."""

from datetime import datetime
import sys
import unittest
from unittest.mock import MagicMock, patch


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


class SchedulerBackgroundTaskTestCase(unittest.TestCase):
    def test_background_task_runs_when_interval_elapsed(self):
        fake_schedule = _FakeScheduleModule()
        with patch.dict(sys.modules, {"schedule": fake_schedule}):
            from src.scheduler import Scheduler

            scheduler = Scheduler(schedule_time="18:00")
            calls = []
            fake_thread = MagicMock()
            fake_thread.is_alive.return_value = False

            def _make_thread(target=None, **kwargs):
                fake_thread.start.side_effect = target
                return fake_thread

            with patch("src.scheduler.threading.Thread", side_effect=_make_thread):
                scheduler.add_background_task(lambda: calls.append("ran"), interval_seconds=1, run_immediately=True, name="test")

        self.assertEqual(calls, ["ran"])

    def test_background_task_waits_for_interval(self):
        fake_schedule = _FakeScheduleModule()
        with patch.dict(sys.modules, {"schedule": fake_schedule}):
            from src.scheduler import Scheduler

            scheduler = Scheduler(schedule_time="18:00")
            calls = []
            scheduler.add_background_task(lambda: calls.append("ran"), interval_seconds=60, run_immediately=False, name="test")

            with patch("src.scheduler.time.time", return_value=scheduler._background_tasks[0]["last_run"] + 10):
                scheduler._run_background_tasks()

        self.assertEqual(calls, [])

    def test_run_with_schedule_registers_background_tasks_before_immediate_daily_task(self):
        fake_schedule = _FakeScheduleModule()
        with patch.dict(sys.modules, {"schedule": fake_schedule}):
            from src import scheduler as scheduler_module

            order = []

            class FakeScheduler:
                def __init__(
                    self,
                    schedule_time="18:00",
                    schedule_time_provider=None,
                    schedule_times=None,
                    schedule_times_provider=None,
                    install_signal_handlers=True,
                ):
                    order.append(("init", schedule_time))
                    order.append(("provider", callable(schedule_time_provider)))

                def add_background_task(self, **kwargs):
                    order.append(("background", kwargs["name"]))

                def set_daily_task(self, task, run_immediately=True):
                    order.append(("daily", run_immediately))

                def run(self):
                    order.append(("run", None))

            with patch.object(scheduler_module, "Scheduler", FakeScheduler):
                scheduler_module.run_with_schedule(
                    task=lambda: None,
                    run_immediately=True,
                    background_tasks=[{
                        "task": lambda: None,
                        "interval_seconds": 60,
                        "run_immediately": True,
                        "name": "event_monitor",
                    }],
                )

        self.assertEqual(order[:4], [("init", "18:00"), ("provider", False), ("background", "event_monitor"), ("daily", True)])

    def test_scheduler_reloads_daily_job_when_schedule_time_changes(self):
        fake_schedule = _FakeScheduleModule()
        with patch.dict(sys.modules, {"schedule": fake_schedule}):
            from src.scheduler import Scheduler

            scheduler = Scheduler(
                schedule_time="18:00",
                schedule_time_provider=lambda: "09:30",
            )
            scheduler.set_daily_task(lambda: None, run_immediately=False)

            self.assertEqual(len(fake_schedule.jobs), 1)
            self.assertEqual(fake_schedule.jobs[0].at_time, "18:00")

            scheduler._refresh_daily_schedule_if_needed()

        self.assertEqual(len(fake_schedule.jobs), 1)
        self.assertEqual(fake_schedule.jobs[0].at_time, "09:30")
        self.assertEqual(scheduler.schedule_time, "09:30")

    def test_scheduler_keeps_existing_daily_job_when_schedule_time_invalid(self):
        fake_schedule = _FakeScheduleModule()
        with patch.dict(sys.modules, {"schedule": fake_schedule}):
            from src.scheduler import Scheduler

            scheduler = Scheduler(
                schedule_time="18:00",
                schedule_time_provider=lambda: "25:99",
            )
            scheduler.set_daily_task(lambda: None, run_immediately=False)

            scheduler._refresh_daily_schedule_if_needed()

        self.assertEqual(len(fake_schedule.jobs), 1)
        self.assertEqual(fake_schedule.jobs[0].at_time, "18:00")
        self.assertEqual(scheduler.schedule_time, "18:00")

    def test_scheduler_keeps_current_daily_job_when_schedule_time_provider_fails(self):
        fake_schedule = _FakeScheduleModule()
        with patch.dict(sys.modules, {"schedule": fake_schedule}):
            from src.scheduler import Scheduler

            provider_calls = {"count": 0}

            def provider():
                provider_calls["count"] += 1
                if provider_calls["count"] == 1:
                    return "09:30"
                raise RuntimeError("boom")

            scheduler = Scheduler(
                schedule_time="18:00",
                schedule_time_provider=provider,
            )
            scheduler.set_daily_task(lambda: None, run_immediately=False)

            scheduler._refresh_daily_schedule_if_needed()
            scheduler._refresh_daily_schedule_if_needed()

        self.assertEqual(len(fake_schedule.jobs), 1)
        self.assertEqual(fake_schedule.jobs[0].at_time, "09:30")
        self.assertEqual(scheduler.schedule_time, "09:30")

    def test_scheduler_rejects_invalid_initial_schedule_time(self):
        fake_schedule = _FakeScheduleModule()
        with patch.dict(sys.modules, {"schedule": fake_schedule}):
            from src.scheduler import Scheduler

            scheduler = Scheduler(schedule_time="25:99")
            calls = []

            with self.assertRaisesRegex(ValueError, "25:99"):
                scheduler.set_daily_task(lambda: calls.append("ran"), run_immediately=True)

        self.assertEqual(calls, [])
        self.assertEqual(fake_schedule.jobs, [])

    def test_scheduler_registers_multiple_daily_jobs(self):
        fake_schedule = _FakeScheduleModule()
        with patch.dict(sys.modules, {"schedule": fake_schedule}):
            from src.scheduler import Scheduler

            scheduler = Scheduler(schedule_times=["15:10", "09:20", "09:20", "12:30"])
            scheduler.set_daily_task(lambda: None, run_immediately=False)

        self.assertEqual(scheduler.scheduled_times, ["09:20", "12:30", "15:10"])
        self.assertEqual(
            sorted(job.at_time for job in fake_schedule.jobs),
            ["09:20", "12:30", "15:10"],
        )
        self.assertEqual(scheduler.schedule_time, "09:20")

    def test_scheduler_reconfigures_multiple_times_via_provider(self):
        fake_schedule = _FakeScheduleModule()
        with patch.dict(sys.modules, {"schedule": fake_schedule}):
            from src.scheduler import Scheduler

            latest = {"times": ["09:20", "18:00"]}
            scheduler = Scheduler(
                schedule_times=["09:20", "18:00"],
                schedule_times_provider=lambda: latest["times"],
            )
            scheduler.set_daily_task(lambda: None, run_immediately=False)
            self.assertEqual(scheduler.scheduled_times, ["09:20", "18:00"])

            latest["times"] = ["09:20", "12:30"]
            scheduler._refresh_daily_schedule_if_needed()

        self.assertEqual(scheduler.scheduled_times, ["09:20", "12:30"])
        self.assertEqual(
            sorted(job.at_time for job in fake_schedule.jobs), ["09:20", "12:30"]
        )

    def test_scheduler_keeps_times_when_provider_returns_all_invalid(self):
        fake_schedule = _FakeScheduleModule()
        with patch.dict(sys.modules, {"schedule": fake_schedule}):
            from src.scheduler import Scheduler

            scheduler = Scheduler(
                schedule_times=["09:20", "12:30"],
                schedule_times_provider=lambda: ["99:99", "nope"],
            )
            scheduler.set_daily_task(lambda: None, run_immediately=False)

            scheduler._refresh_daily_schedule_if_needed()

        self.assertEqual(scheduler.scheduled_times, ["09:20", "12:30"])

    def test_scheduler_rejects_all_invalid_initial_times(self):
        fake_schedule = _FakeScheduleModule()
        with patch.dict(sys.modules, {"schedule": fake_schedule}):
            from src.scheduler import Scheduler

            scheduler = Scheduler(schedule_times=["25:00", "bogus"])
            with self.assertRaises(ValueError):
                scheduler.set_daily_task(lambda: None, run_immediately=False)

        self.assertEqual(scheduler.scheduled_times, [])
        self.assertEqual(fake_schedule.jobs, [])

    def test_scheduler_skips_signal_handlers_off_main_thread(self):
        fake_schedule = _FakeScheduleModule()
        results = {}

        def _worker():
            with patch.dict(sys.modules, {"schedule": fake_schedule}):
                from src.scheduler import Scheduler

                scheduler = Scheduler(schedule_time="18:00")
                results["installed"] = scheduler.shutdown_handler.signal_handlers_installed

        import threading as _threading

        thread = _threading.Thread(target=_worker)
        thread.start()
        thread.join()

        self.assertIn("installed", results)
        self.assertFalse(results["installed"])


if __name__ == "__main__":
    unittest.main()
