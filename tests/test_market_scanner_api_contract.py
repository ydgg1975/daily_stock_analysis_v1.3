# -*- coding: utf-8 -*-
"""Contract tests for market scanner endpoints."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from api.v1.endpoints.scanner import (
    get_recent_watchlists,
    get_market_scan_run,
    get_market_scan_runs,
    get_scanner_operational_status,
    get_today_watchlist,
    run_market_scan,
)
from api.v1.schemas.scanner import ScannerRunRequest


def _make_candidate(symbol: str, rank: int) -> dict:
    return {
        "symbol": symbol,
        "name": f"股票{symbol}",
        "rank": rank,
        "score": 80.0 - rank,
        "quality_hint": "高优先级",
        "reason_summary": "趋势与量能共振。",
        "reasons": ["趋势结构完整。"],
        "key_metrics": [{"label": "最新价", "value": "18.20"}],
        "feature_signals": [{"label": "趋势结构", "value": "18.0 / 20"}],
        "risk_notes": ["需要确认竞价承接。"],
        "watch_context": [{"label": "观察触发", "value": "上破近 20 日高点。"}],
        "boards": ["AI算力"],
        "appeared_in_recent_runs": 0,
        "last_trade_date": "2026-04-10",
        "scan_timestamp": "2026-04-13T08:30:00",
        "realized_outcome": {
            "review_status": "ready",
            "outcome_label": "strong",
            "thesis_match": "validated",
            "review_window_days": 3,
            "anchor_date": "2026-04-10",
            "window_end_date": "2026-04-15",
            "same_day_close_return_pct": 2.3,
            "next_day_return_pct": 1.2,
            "review_window_return_pct": 5.6,
            "max_favorable_move_pct": 7.4,
            "max_adverse_move_pct": -1.5,
            "benchmark_code": "000300",
            "benchmark_return_pct": 1.8,
            "outperformed_benchmark": True,
        },
        "diagnostics": {"history_source": "local_db"},
    }


def _make_run_payload(run_id: int = 12) -> dict:
    return {
        "id": run_id,
        "market": "cn",
        "profile": "cn_preopen_v1",
        "profile_label": "A股盘前扫描 v1",
        "status": "completed",
        "run_at": "2026-04-13T08:30:00",
        "completed_at": "2026-04-13T08:31:00",
        "watchlist_date": "2026-04-13",
        "trigger_mode": "manual",
        "universe_name": "cn_a_liquid_watchlist_v1",
        "shortlist_size": 2,
        "universe_size": 300,
        "preselected_size": 60,
        "evaluated_size": 48,
        "source_summary": "stock_list=FakeList; snapshot=FakeSnapshot; history=local_first; sector=enabled",
        "headline": "今日 A 股盘前优先观察：600001 / 600002",
        "universe_notes": ["剔除 ST 与停牌近似状态。"],
        "scoring_notes": ["趋势、量能、活跃度加权。"],
        "diagnostics": {"history_stats": {"local_hits": 10}},
        "notification": {
            "attempted": False,
            "status": "not_attempted",
            "success": None,
            "channels": [],
            "message": None,
            "report_path": None,
            "sent_at": None,
        },
        "failure_reason": None,
        "comparison_to_previous": {
            "available": True,
            "previous_run_id": 11,
            "previous_watchlist_date": "2026-04-10",
            "new_count": 1,
            "retained_count": 1,
            "dropped_count": 1,
            "new_symbols": [{"symbol": "600001", "name": "股票600001", "current_rank": 1, "previous_rank": None, "rank_delta": None}],
            "retained_symbols": [{"symbol": "600002", "name": "股票600002", "current_rank": 2, "previous_rank": 1, "rank_delta": -1}],
            "dropped_symbols": [{"symbol": "600003", "name": "股票600003", "current_rank": None, "previous_rank": 2, "rank_delta": None}],
        },
        "review_summary": {
            "available": True,
            "review_window_days": 3,
            "review_status": "ready",
            "candidate_count": 2,
            "reviewed_count": 2,
            "pending_count": 0,
            "hit_rate_pct": 50.0,
            "outperform_rate_pct": 50.0,
            "avg_same_day_close_return_pct": 1.5,
            "avg_review_window_return_pct": 2.2,
            "avg_max_favorable_move_pct": 4.0,
            "avg_max_adverse_move_pct": -1.8,
            "strong_count": 1,
            "mixed_count": 0,
            "weak_count": 1,
            "best_symbol": "600001",
            "best_return_pct": 5.6,
            "weakest_symbol": "600002",
            "weakest_return_pct": -1.2,
        },
        "shortlist": [_make_candidate("600001", 1), _make_candidate("600002", 2)],
    }


def _make_operational_status_payload() -> dict:
    return {
        "market": "cn",
        "profile": "cn_preopen_v1",
        "profile_label": "A股盘前扫描 v1",
        "watchlist_date": "2026-04-13",
        "today_trading_day": True,
        "schedule_enabled": True,
        "schedule_time": "08:40",
        "schedule_run_immediately": False,
        "notification_enabled": True,
        "today_watchlist": {
            "id": 12,
            "watchlist_date": "2026-04-13",
            "trigger_mode": "scheduled",
            "status": "completed",
            "run_at": "2026-04-13T08:40:00",
            "headline": "今日 A 股盘前优先观察：600001 / 600002",
            "shortlist_size": 2,
            "notification_status": "success",
            "failure_reason": None,
        },
        "last_run": {
            "id": 12,
            "watchlist_date": "2026-04-13",
            "trigger_mode": "scheduled",
            "status": "completed",
            "run_at": "2026-04-13T08:40:00",
            "headline": "今日 A 股盘前优先观察：600001 / 600002",
            "shortlist_size": 2,
            "notification_status": "success",
            "failure_reason": None,
        },
        "last_scheduled_run": {
            "id": 12,
            "watchlist_date": "2026-04-13",
            "trigger_mode": "scheduled",
            "status": "completed",
            "run_at": "2026-04-13T08:40:00",
            "headline": "今日 A 股盘前优先观察：600001 / 600002",
            "shortlist_size": 2,
            "notification_status": "success",
            "failure_reason": None,
        },
        "last_manual_run": {
            "id": 11,
            "watchlist_date": "2026-04-13",
            "trigger_mode": "manual",
            "status": "completed",
            "run_at": "2026-04-13T08:32:00",
            "headline": "今日 A 股盘前优先观察：600001 / 600002",
            "shortlist_size": 2,
            "notification_status": "not_attempted",
            "failure_reason": None,
        },
        "latest_failure": None,
        "quality_summary": {
            "available": True,
            "review_window_days": 3,
            "benchmark_code": "000300",
            "run_count": 5,
            "reviewed_run_count": 4,
            "reviewed_candidate_count": 18,
            "review_coverage_pct": 90.0,
            "avg_candidates_per_run": 4.2,
            "avg_shortlist_return_pct": 1.8,
            "positive_run_rate_pct": 75.0,
            "hit_rate_pct": 61.1,
            "outperform_rate_pct": 55.6,
            "positive_candidate_avg_score": 82.4,
            "negative_candidate_avg_score": 74.2,
        },
    }


class MarketScannerApiContractTestCase(unittest.TestCase):
    def test_run_market_scan_passes_request_to_service(self) -> None:
        service = MagicMock()
        service.run_manual_scan.return_value = _make_run_payload()

        request = ScannerRunRequest(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=5,
            universe_limit=300,
            detail_limit=60,
        )

        with patch("api.v1.endpoints.scanner.MarketScannerOperationsService", return_value=service):
            response = run_market_scan(request, db_manager=MagicMock())

        self.assertEqual(response.id, 12)
        self.assertEqual(response.shortlist[0].symbol, "600001")
        self.assertEqual(response.shortlist[0].realized_outcome.review_status, "ready")
        self.assertEqual(response.watchlist_date, "2026-04-13")
        self.assertEqual(response.trigger_mode, "manual")
        self.assertEqual(response.comparison_to_previous.new_count, 1)
        self.assertEqual(response.review_summary.best_symbol, "600001")
        service.run_manual_scan.assert_called_once_with(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=5,
            universe_limit=300,
            detail_limit=60,
            request_source="api",
            notify=False,
        )

    def test_get_market_scan_runs_serializes_history(self) -> None:
        service = MagicMock()
        service.list_runs.return_value = {
            "total": 1,
            "page": 1,
            "limit": 10,
            "items": [
                {
                    "id": 12,
                    "market": "cn",
                    "profile": "cn_preopen_v1",
                    "profile_label": "A股盘前扫描 v1",
                    "status": "completed",
                    "run_at": "2026-04-13T08:30:00",
                    "completed_at": "2026-04-13T08:31:00",
                    "watchlist_date": "2026-04-13",
                    "trigger_mode": "scheduled",
                    "universe_name": "cn_a_liquid_watchlist_v1",
                    "shortlist_size": 2,
                    "universe_size": 300,
                    "preselected_size": 60,
                    "evaluated_size": 48,
                    "source_summary": "test",
                    "headline": "headline",
                    "top_symbols": ["600001", "600002"],
                    "notification_status": "success",
                    "failure_reason": None,
                    "change_summary": {
                        "available": True,
                        "previous_run_id": 11,
                        "previous_watchlist_date": "2026-04-10",
                        "new_count": 1,
                        "retained_count": 1,
                        "dropped_count": 1,
                        "new_symbols": [{"symbol": "600001", "name": "股票600001", "current_rank": 1, "previous_rank": None, "rank_delta": None}],
                        "retained_symbols": [{"symbol": "600002", "name": "股票600002", "current_rank": 2, "previous_rank": 1, "rank_delta": -1}],
                        "dropped_symbols": [{"symbol": "600003", "name": "股票600003", "current_rank": None, "previous_rank": 2, "rank_delta": None}],
                    },
                    "review_summary": {
                        "available": True,
                        "review_window_days": 3,
                        "review_status": "ready",
                        "candidate_count": 2,
                        "reviewed_count": 2,
                        "pending_count": 0,
                        "hit_rate_pct": 50.0,
                        "outperform_rate_pct": 50.0,
                        "avg_same_day_close_return_pct": 1.5,
                        "avg_review_window_return_pct": 2.2,
                        "avg_max_favorable_move_pct": 4.0,
                        "avg_max_adverse_move_pct": -1.8,
                        "strong_count": 1,
                        "mixed_count": 0,
                        "weak_count": 1,
                        "best_symbol": "600001",
                        "best_return_pct": 5.6,
                        "weakest_symbol": "600002",
                        "weakest_return_pct": -1.2,
                    },
                }
            ],
        }

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            response = get_market_scan_runs(db_manager=MagicMock())

        self.assertEqual(response.total, 1)
        self.assertEqual(response.items[0].top_symbols, ["600001", "600002"])
        self.assertEqual(response.items[0].notification_status, "success")
        self.assertEqual(response.items[0].change_summary.new_count, 1)
        service.list_runs.assert_called_once()

    def test_get_market_scan_run_returns_404_when_missing(self) -> None:
        service = MagicMock()
        service.get_run_detail.return_value = None

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_market_scan_run(999, db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")

    def test_get_today_watchlist_returns_404_when_missing(self) -> None:
        service = MagicMock()
        service.get_today_watchlist.return_value = None

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            with self.assertRaises(HTTPException) as ctx:
                get_today_watchlist(db_manager=MagicMock())

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "not_found")

    def test_get_recent_watchlists_serializes_daily_history(self) -> None:
        service = MagicMock()
        service.list_recent_watchlists.return_value = {
            "total": 1,
            "page": 1,
            "limit": 7,
            "items": [
                {
                    "id": 12,
                    "market": "cn",
                    "profile": "cn_preopen_v1",
                    "profile_label": "A股盘前扫描 v1",
                    "status": "completed",
                    "run_at": "2026-04-13T08:40:00",
                    "completed_at": "2026-04-13T08:41:00",
                    "watchlist_date": "2026-04-13",
                    "trigger_mode": "scheduled",
                    "universe_name": "cn_a_liquid_watchlist_v1",
                    "shortlist_size": 2,
                    "universe_size": 300,
                    "preselected_size": 60,
                    "evaluated_size": 48,
                    "source_summary": "scanner=daily",
                    "headline": "今日 A 股盘前优先观察：600001 / 600002",
                    "top_symbols": ["600001", "600002"],
                    "notification_status": "success",
                    "failure_reason": None,
                    "change_summary": {
                        "available": True,
                        "previous_run_id": 11,
                        "previous_watchlist_date": "2026-04-10",
                        "new_count": 1,
                        "retained_count": 1,
                        "dropped_count": 1,
                        "new_symbols": [{"symbol": "600001", "name": "股票600001", "current_rank": 1, "previous_rank": None, "rank_delta": None}],
                        "retained_symbols": [{"symbol": "600002", "name": "股票600002", "current_rank": 2, "previous_rank": 1, "rank_delta": -1}],
                        "dropped_symbols": [{"symbol": "600003", "name": "股票600003", "current_rank": None, "previous_rank": 2, "rank_delta": None}],
                    },
                    "review_summary": {
                        "available": True,
                        "review_window_days": 3,
                        "review_status": "ready",
                        "candidate_count": 2,
                        "reviewed_count": 2,
                        "pending_count": 0,
                        "hit_rate_pct": 50.0,
                        "outperform_rate_pct": 50.0,
                        "avg_same_day_close_return_pct": 1.5,
                        "avg_review_window_return_pct": 2.2,
                        "avg_max_favorable_move_pct": 4.0,
                        "avg_max_adverse_move_pct": -1.8,
                        "strong_count": 1,
                        "mixed_count": 0,
                        "weak_count": 1,
                        "best_symbol": "600001",
                        "best_return_pct": 5.6,
                        "weakest_symbol": "600002",
                        "weakest_return_pct": -1.2,
                    },
                }
            ],
        }

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            response = get_recent_watchlists(db_manager=MagicMock())

        self.assertEqual(response.total, 1)
        self.assertEqual(response.items[0].watchlist_date, "2026-04-13")
        self.assertEqual(response.items[0].trigger_mode, "scheduled")
        self.assertEqual(response.items[0].notification_status, "success")
        self.assertEqual(response.items[0].review_summary.review_status, "ready")
        service.list_recent_watchlists.assert_called_once()

    def test_get_scanner_operational_status_serializes_status_summary(self) -> None:
        service = MagicMock()
        service.get_operational_status.return_value = _make_operational_status_payload()

        with patch("api.v1.endpoints.scanner.MarketScannerOperationsService", return_value=service):
            response = get_scanner_operational_status(db_manager=MagicMock())

        self.assertTrue(response.schedule_enabled)
        self.assertEqual(response.schedule_time, "08:40")
        self.assertEqual(response.today_watchlist.id, 12)
        self.assertEqual(response.last_manual_run.trigger_mode, "manual")
        self.assertTrue(response.quality_summary.available)
        self.assertEqual(response.quality_summary.run_count, 5)
        service.get_operational_status.assert_called_once()


if __name__ == "__main__":
    unittest.main()
