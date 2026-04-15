# -*- coding: utf-8 -*-
"""Tests for the scanner operational workflow layer."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.notification import NotificationChannel
from src.repositories.stock_repo import StockRepository
from src.services.execution_log_service import ExecutionLogService
from src.services.market_scanner_ops_service import MarketScannerOperationsService
from src.services.market_scanner_service import MarketScannerService, ScannerRuntimeError
from src.storage import DatabaseManager
from tests.test_market_scanner_service import FakeScannerDataManager, FakeUsScannerDataManager, seed_us_local_history


class FakeNotifier:
    def __init__(
        self,
        *,
        available: bool = True,
        send_result: bool = True,
        send_error: Exception | None = None,
    ) -> None:
        self.available = available
        self.send_result = send_result
        self.send_error = send_error
        self.saved_reports: list[tuple[str, str]] = []
        self.sent_messages: list[str] = []

    def save_report_to_file(self, content: str, filename: str) -> str:
        self.saved_reports.append((filename, content))
        return f"/tmp/{filename}"

    def get_available_channels(self):
        if not self.available:
            return []
        return [NotificationChannel.FEISHU]

    def is_available(self) -> bool:
        return self.available

    def send(self, content: str, email_send_to_all: bool = False) -> bool:
        _ = email_send_to_all
        self.sent_messages.append(content)
        if self.send_error is not None:
            raise self.send_error
        return self.send_result


def _make_config(**overrides):
    base = {
        "scanner_profile": "cn_preopen_v1",
        "scanner_schedule_enabled": True,
        "scanner_schedule_time": "08:40",
        "scanner_schedule_run_immediately": False,
        "scanner_notification_enabled": False,
        "trading_day_check_enabled": True,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class MarketScannerOperationsServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")
        self.data_manager = FakeScannerDataManager()
        self.scanner_service = MarketScannerService(self.db, data_manager=self.data_manager)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def test_manual_and_scheduled_runs_record_trigger_mode_and_watchlist_views(self) -> None:
        ops_service = MarketScannerOperationsService(
            scanner_service=self.scanner_service,
            config=_make_config(scanner_notification_enabled=False),
            notifier_factory=lambda: FakeNotifier(available=False),
        )

        manual = ops_service.run_manual_scan(
            market="cn",
            profile="cn_preopen_v1",
            notify=False,
        )
        scheduled = ops_service.run_scheduled_scan(force_run=True)

        self.assertEqual(manual["trigger_mode"], "manual")
        self.assertEqual(scheduled["trigger_mode"], "scheduled")
        self.assertEqual(manual["watchlist_date"], scheduled["watchlist_date"])

        today_watchlist = self.scanner_service.get_today_watchlist(
            market="cn",
            profile="cn_preopen_v1",
        )
        self.assertIsNotNone(today_watchlist)
        self.assertEqual(today_watchlist["id"], scheduled["id"])

        recent = self.scanner_service.list_recent_watchlists(
            market="cn",
            profile="cn_preopen_v1",
            limit_days=3,
        )
        self.assertEqual(recent["items"][0]["id"], scheduled["id"])
        self.assertEqual(recent["items"][0]["watchlist_date"], scheduled["watchlist_date"])

        status = ops_service.get_operational_status(market="cn", profile="cn_preopen_v1")
        self.assertEqual(status["last_manual_run"]["id"], manual["id"])
        self.assertEqual(status["last_scheduled_run"]["id"], scheduled["id"])
        self.assertEqual(status["today_watchlist"]["id"], scheduled["id"])

    def test_notification_success_is_recorded_on_scheduled_run(self) -> None:
        notifier = FakeNotifier(available=True, send_result=True)
        ops_service = MarketScannerOperationsService(
            scanner_service=self.scanner_service,
            config=_make_config(scanner_notification_enabled=True),
            notifier_factory=lambda: notifier,
        )

        detail = ops_service.run_scheduled_scan(force_run=True)

        self.assertEqual(detail["notification"]["status"], "success")
        self.assertTrue(detail["notification"]["attempted"])
        self.assertEqual(detail["notification"]["channels"], ["feishu"])
        self.assertTrue(notifier.saved_reports)
        self.assertTrue(notifier.sent_messages)

        persisted = self.scanner_service.get_run_detail(detail["id"])
        self.assertEqual(persisted["notification"]["status"], "success")
        self.assertEqual(persisted["trigger_mode"], "scheduled")

    def test_notification_failure_is_recorded_on_scheduled_run(self) -> None:
        notifier = FakeNotifier(available=True, send_error=RuntimeError("push failed"))
        ops_service = MarketScannerOperationsService(
            scanner_service=self.scanner_service,
            config=_make_config(scanner_notification_enabled=True),
            notifier_factory=lambda: notifier,
        )

        detail = ops_service.run_scheduled_scan(force_run=True)

        self.assertEqual(detail["notification"]["status"], "failed")
        self.assertFalse(detail["notification"]["success"])
        self.assertIn("push failed", detail["notification"]["message"])

        persisted = self.scanner_service.get_run_detail(detail["id"])
        self.assertEqual(persisted["notification"]["status"], "failed")
        self.assertIn("push failed", persisted["notification"]["message"])

    def test_notification_markdown_contains_rank_reasons_risk_and_watch_context(self) -> None:
        detail = self.scanner_service.run_scan(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=2,
            universe_limit=50,
            detail_limit=10,
        )
        detail = self.scanner_service.update_run_operation_metadata(
            detail["id"],
            trigger_mode="scheduled",
            watchlist_date="2026-04-13",
            request_source="scheduler",
            notification_result={
                "attempted": False,
                "status": "not_attempted",
                "success": None,
                "channels": [],
            },
        )

        payload = MarketScannerOperationsService.build_watchlist_notification(detail)

        self.assertIn("今日观察名单", payload)
        self.assertIn("#1", payload)
        self.assertIn("600001", payload)
        self.assertIn("原因:", payload)
        self.assertIn("风险:", payload)
        self.assertIn("观察:", payload)

    def test_runtime_failure_persists_structured_diagnostics(self) -> None:
        ops_service = MarketScannerOperationsService(
            scanner_service=self.scanner_service,
            config=_make_config(scanner_notification_enabled=False),
            notifier_factory=lambda: FakeNotifier(available=False),
        )

        with patch.object(
            self.scanner_service,
            "run_scan",
            side_effect=ScannerRuntimeError(
                "no_realtime_snapshot_available",
                "A 股全市场快照不可用。",
                diagnostics={
                    "reason_code": "no_realtime_snapshot_available",
                    "universe_resolution": {
                        "source": "local_universe_cache",
                    },
                    "snapshot_resolution": {
                        "attempts": [
                            {
                                "fetcher": "AkshareFetcher",
                                "reason_code": "akshare_snapshot_fetch_failed",
                            },
                            {
                                "fetcher": "EfinanceFetcher",
                                "reason_code": "efinance_snapshot_fetch_failed",
                            },
                        ],
                    },
                },
                source_summary="universe=local_universe_cache; snapshot=unknown; degraded=no; snapshot_attempts=AkshareFetcher:failed(akshare_snapshot_fetch_failed),EfinanceFetcher:failed(efinance_snapshot_fetch_failed)",
            ),
        ):
            detail = ops_service.run_scheduled_scan(force_run=True)

        self.assertEqual(detail["status"], "failed")
        self.assertEqual(detail["failure_reason"], "A 股全市场快照不可用。")
        self.assertEqual(detail["diagnostics"]["reason_code"], "no_realtime_snapshot_available")
        self.assertEqual(detail["diagnostics"]["universe_resolution"]["source"], "local_universe_cache")
        self.assertEqual(
            [item["reason_code"] for item in detail["diagnostics"]["snapshot_resolution"]["attempts"]],
            ["akshare_snapshot_fetch_failed", "efinance_snapshot_fetch_failed"],
        )
        self.assertIn("snapshot_attempts=", detail["source_summary"])

    def test_scheduled_run_resolves_us_profile_from_config(self) -> None:
        stock_repo = StockRepository(self.db)
        seed_us_local_history(stock_repo)
        us_scanner_service = MarketScannerService(self.db, data_manager=FakeUsScannerDataManager())
        ops_service = MarketScannerOperationsService(
            scanner_service=us_scanner_service,
            config=_make_config(
                scanner_profile="us_preopen_v1",
                scanner_schedule_enabled=True,
                scanner_notification_enabled=False,
            ),
            notifier_factory=lambda: FakeNotifier(available=False),
        )

        detail = ops_service.run_scheduled_scan(force_run=True)

        self.assertEqual(detail["market"], "us")
        self.assertEqual(detail["profile"], "us_preopen_v1")
        self.assertEqual(detail["trigger_mode"], "scheduled")
        self.assertTrue(detail["headline"].startswith("今日美股盘前优先观察："))
        self.assertEqual(detail["diagnostics"]["benchmark_context"]["benchmark_code"], "SPY")

        status = ops_service.get_operational_status(market="us", profile="us_preopen_v1")
        self.assertEqual(status["market"], "us")
        self.assertEqual(status["profile"], "us_preopen_v1")
        self.assertEqual(status["today_watchlist"]["id"], detail["id"])

    def test_manual_scan_records_scanner_run_observability_for_admin_logs(self) -> None:
        ops_service = MarketScannerOperationsService(
            scanner_service=self.scanner_service,
            config=_make_config(scanner_notification_enabled=False),
            notifier_factory=lambda: FakeNotifier(available=False),
        )

        detail = ops_service.run_manual_scan(
            market="cn",
            profile="cn_preopen_v1",
            notify=False,
        )

        logs = ExecutionLogService()
        sessions, total = logs.list_sessions(limit=20)

        self.assertGreaterEqual(total, 1)
        scanner_session = next(
            item for item in sessions
            if item["readable_summary"]["subsystem"] == "scanner"
        )
        readable = scanner_session["readable_summary"]
        self.assertEqual(readable["action_name"], "scanner_run")
        self.assertEqual(readable["scanner_run_id"], detail["id"])
        self.assertEqual(readable["scanner_market"], "cn")
        self.assertEqual(readable["scanner_shortlist_count"], detail["shortlist_size"])
        self.assertEqual(readable["scanner_fallback_count"], 0)

        detail_payload = logs.get_session_detail(scanner_session["session_id"])
        self.assertIsNotNone(detail_payload)
        assert detail_payload is not None
        self.assertEqual(detail_payload["events"][0]["category"], "scanner")
        self.assertEqual(detail_payload["events"][0]["detail"]["scanner_run_id"], detail["id"])


if __name__ == "__main__":
    unittest.main()
