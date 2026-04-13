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


def _make_candidate(symbol: str, rank: int, *, benchmark_code: str = "000300") -> dict:
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
        "ai_interpretation": {
            "available": True,
            "status": "generated",
            "summary": "AI 认为这更像趋势延续中的临界突破观察名单。",
            "opportunity_type": "临界突破",
            "risk_interpretation": "若竞价高开过多，承接不足时容易转成冲高回落。",
            "watch_plan": "盘前先看竞价承接，开盘后再看量能是否继续放大。",
            "review_commentary": "后续走势跑赢基准，说明强势题材与量能配合有效。",
            "provider": "gemini",
            "model": "gemini/gemini-2.5-flash",
            "generated_at": "2026-04-13T08:30:10",
            "message": None,
        },
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
            "benchmark_code": benchmark_code,
            "benchmark_return_pct": 1.8,
            "outperformed_benchmark": True,
        },
        "diagnostics": {"history_source": "local_db"},
    }


def _make_run_payload(
    run_id: int = 12,
    *,
    market: str = "cn",
    profile: str = "cn_preopen_v1",
    profile_label: str = "A股盘前扫描 v1",
    benchmark_code: str = "000300",
) -> dict:
    is_us = market == "us"
    universe_name = "us_preopen_watchlist_v1" if is_us else "cn_a_liquid_watchlist_v1"
    headline = "今日美股盘前优先观察：NVDA / AAPL" if is_us else "今日 A 股盘前优先观察：600001 / 600002"
    primary_symbol = "NVDA" if is_us else "600001"
    secondary_symbol = "AAPL" if is_us else "600002"
    return {
        "id": run_id,
        "market": market,
        "profile": profile,
        "profile_label": profile_label,
        "status": "completed",
        "run_at": "2026-04-13T08:30:00",
        "completed_at": "2026-04-13T08:31:00",
        "watchlist_date": "2026-04-13",
        "trigger_mode": "manual",
        "universe_name": universe_name,
        "shortlist_size": 2,
        "universe_size": 180 if is_us else 300,
        "preselected_size": 40 if is_us else 60,
        "evaluated_size": 32 if is_us else 48,
        "source_summary": "universe=local_us_history; snapshot=optional_us_realtime_quote; history=local_us_first" if is_us else "stock_list=FakeList; snapshot=FakeSnapshot; history=local_first; sector=enabled",
        "headline": headline,
        "universe_notes": ["使用本地 US history universe。"] if is_us else ["剔除 ST 与停牌近似状态。"],
        "scoring_notes": ["流动性、趋势延续、相对强度与 gap context 共同决定排序。"] if is_us else ["趋势、量能、活跃度加权。"],
        "diagnostics": {
            "history_stats": {"local_hits": 10},
            "ai_interpretation": {
                "enabled": True,
                "status": "completed",
                "top_n": 2,
                "attempted_candidates": 2,
                "generated_candidates": 2,
                "failed_candidates": 0,
                "skipped_candidates": 0,
                "models_used": ["gemini/gemini-2.5-flash"],
                "fallback_used": False,
                "message": "已为前 2 名候选生成 AI 解读。",
            },
        },
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
            "new_symbols": [{"symbol": primary_symbol, "name": f"股票{primary_symbol}", "current_rank": 1, "previous_rank": None, "rank_delta": None}],
            "retained_symbols": [{"symbol": secondary_symbol, "name": f"股票{secondary_symbol}", "current_rank": 2, "previous_rank": 1, "rank_delta": -1}],
            "dropped_symbols": [{"symbol": "MSFT" if is_us else "600003", "name": f"股票{'MSFT' if is_us else '600003'}", "current_rank": None, "previous_rank": 2, "rank_delta": None}],
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
        "shortlist": [
            _make_candidate(primary_symbol, 1, benchmark_code=benchmark_code),
            _make_candidate(secondary_symbol, 2, benchmark_code=benchmark_code),
        ],
    }


def _make_operational_status_payload(
    *,
    market: str = "cn",
    profile: str = "cn_preopen_v1",
    profile_label: str = "A股盘前扫描 v1",
    benchmark_code: str = "000300",
) -> dict:
    is_us = market == "us"
    headline = "今日美股盘前优先观察：NVDA / AAPL" if is_us else "今日 A 股盘前优先观察：600001 / 600002"
    return {
        "market": market,
        "profile": profile,
        "profile_label": profile_label,
        "watchlist_date": "2026-04-13",
        "today_trading_day": True,
        "schedule_enabled": True,
        "schedule_time": "21:20" if is_us else "08:40",
        "schedule_run_immediately": False,
        "notification_enabled": True,
        "today_watchlist": {
            "id": 12,
            "watchlist_date": "2026-04-13",
            "trigger_mode": "scheduled",
            "status": "completed",
            "run_at": "2026-04-13T08:40:00",
            "headline": headline,
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
            "headline": headline,
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
            "headline": headline,
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
            "headline": headline,
            "shortlist_size": 2,
            "notification_status": "not_attempted",
            "failure_reason": None,
        },
        "latest_failure": None,
        "quality_summary": {
            "available": True,
            "review_window_days": 3,
            "benchmark_code": benchmark_code,
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
        self.assertTrue(response.shortlist[0].ai_interpretation.available)
        self.assertEqual(response.shortlist[0].ai_interpretation.opportunity_type, "临界突破")
        self.assertEqual(response.watchlist_date, "2026-04-13")
        self.assertEqual(response.trigger_mode, "manual")
        self.assertEqual(response.comparison_to_previous.new_count, 1)
        self.assertEqual(response.review_summary.best_symbol, "600001")
        self.assertEqual(response.diagnostics["ai_interpretation"]["status"], "completed")
        service.run_manual_scan.assert_called_once_with(
            market="cn",
            profile="cn_preopen_v1",
            shortlist_size=5,
            universe_limit=300,
            detail_limit=60,
            request_source="api",
            notify=False,
        )

    def test_run_market_scan_supports_us_profile_request(self) -> None:
        service = MagicMock()
        service.run_manual_scan.return_value = _make_run_payload(
            run_id=24,
            market="us",
            profile="us_preopen_v1",
            profile_label="US Pre-open Scanner v1",
            benchmark_code="SPY",
        )

        request = ScannerRunRequest(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=5,
            universe_limit=180,
            detail_limit=40,
        )

        with patch("api.v1.endpoints.scanner.MarketScannerOperationsService", return_value=service):
            response = run_market_scan(request, db_manager=MagicMock())

        self.assertEqual(response.id, 24)
        self.assertEqual(response.market, "us")
        self.assertEqual(response.profile, "us_preopen_v1")
        self.assertEqual(response.profile_label, "US Pre-open Scanner v1")
        self.assertEqual(response.shortlist[0].symbol, "NVDA")
        self.assertEqual(response.shortlist[0].realized_outcome.benchmark_code, "SPY")
        service.run_manual_scan.assert_called_once_with(
            market="us",
            profile="us_preopen_v1",
            shortlist_size=5,
            universe_limit=180,
            detail_limit=40,
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

    def test_get_recent_watchlists_supports_us_profile_filters(self) -> None:
        service = MagicMock()
        service.list_recent_watchlists.return_value = {
            "total": 1,
            "page": 1,
            "limit": 5,
            "items": [
                {
                    "id": 22,
                    "market": "us",
                    "profile": "us_preopen_v1",
                    "profile_label": "US Pre-open Scanner v1",
                    "status": "completed",
                    "run_at": "2026-04-13T21:20:00",
                    "completed_at": "2026-04-13T21:21:00",
                    "watchlist_date": "2026-04-13",
                    "trigger_mode": "scheduled",
                    "universe_name": "us_preopen_watchlist_v1",
                    "shortlist_size": 2,
                    "universe_size": 180,
                    "preselected_size": 40,
                    "evaluated_size": 32,
                    "source_summary": "us_history=local",
                    "headline": "今日美股盘前优先观察：NVDA / AAPL",
                    "top_symbols": ["NVDA", "AAPL"],
                    "notification_status": "success",
                    "failure_reason": None,
                    "change_summary": {
                        "available": False,
                        "previous_run_id": None,
                        "previous_watchlist_date": None,
                        "new_count": 0,
                        "retained_count": 0,
                        "dropped_count": 0,
                        "new_symbols": [],
                        "retained_symbols": [],
                        "dropped_symbols": [],
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
                        "avg_same_day_close_return_pct": 1.1,
                        "avg_review_window_return_pct": 2.8,
                        "avg_max_favorable_move_pct": 4.7,
                        "avg_max_adverse_move_pct": -2.0,
                        "strong_count": 1,
                        "mixed_count": 1,
                        "weak_count": 0,
                        "best_symbol": "NVDA",
                        "best_return_pct": 4.9,
                        "weakest_symbol": "AAPL",
                        "weakest_return_pct": 0.7,
                    },
                }
            ],
        }

        with patch("api.v1.endpoints.scanner.MarketScannerService", return_value=service):
            response = get_recent_watchlists(
                market="us",
                profile="us_preopen_v1",
                limit_days=5,
                db_manager=MagicMock(),
            )

        self.assertEqual(response.items[0].market, "us")
        self.assertEqual(response.items[0].profile, "us_preopen_v1")
        service.list_recent_watchlists.assert_called_once_with(
            market="us",
            profile="us_preopen_v1",
            limit_days=5,
        )

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
