# -*- coding: utf-8 -*-
"""Tests for the market scanner service."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from data_provider.base import BaseFetcher, DataFetchError, DataFetcherManager
from src.repositories.stock_repo import StockRepository
from src.services.market_scanner_service import MarketScannerService, ScannerRuntimeError
from src.storage import DatabaseManager, MarketScannerRun


def _make_history(
    *,
    start_price: float,
    slope: float,
    amount_base: float,
    volume_base: float,
    bars: int = 100,
) -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=bars)
    closes = np.array([start_price + slope * idx + 0.12 * np.sin(idx / 5.0) for idx in range(bars)], dtype=float)
    opens = closes * 0.992
    highs = closes * 1.018
    lows = closes * 0.984
    volumes = np.array([volume_base * (1.0 + 0.08 * np.cos(idx / 6.0)) for idx in range(bars)], dtype=float)
    amounts = closes * volumes
    pct_chg = pd.Series(closes).pct_change().fillna(0.0) * 100.0
    return pd.DataFrame(
        {
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "amount": np.maximum(amounts, amount_base),
            "pct_chg": pct_chg,
        }
    )


class FakeScannerDataManager:
    def __init__(self):
        self.daily_history_calls: list[str] = []
        self.stock_list = pd.DataFrame(
            [
                {"code": "600001", "name": "算力龙头"},
                {"code": "600002", "name": "机器人核心"},
                {"code": "300123", "name": "高景气成长"},
                {"code": "600003", "name": "稳健白马"},
                {"code": "000005", "name": "ST风险股"},
                {"code": "830001", "name": "北交所样本"},
            ]
        )
        self.snapshot = pd.DataFrame(
            [
                {
                    "code": "600001",
                    "name": "算力龙头",
                    "price": 18.4,
                    "change_pct": 4.2,
                    "volume": 58_000_000,
                    "amount": 1.25e9,
                    "turnover_rate": 6.2,
                    "volume_ratio": 1.9,
                    "amplitude": 4.5,
                    "change_60d": 24.0,
                },
                {
                    "code": "600002",
                    "name": "机器人核心",
                    "price": 22.6,
                    "change_pct": 3.1,
                    "volume": 41_000_000,
                    "amount": 9.8e8,
                    "turnover_rate": 4.8,
                    "volume_ratio": 1.6,
                    "amplitude": 4.2,
                    "change_60d": 18.5,
                },
                {
                    "code": "300123",
                    "name": "高景气成长",
                    "price": 31.2,
                    "change_pct": 8.6,
                    "volume": 37_000_000,
                    "amount": 8.7e8,
                    "turnover_rate": 13.5,
                    "volume_ratio": 2.2,
                    "amplitude": 7.2,
                    "change_60d": 31.0,
                },
                {
                    "code": "600003",
                    "name": "稳健白马",
                    "price": 12.9,
                    "change_pct": 1.0,
                    "volume": 26_000_000,
                    "amount": 4.6e8,
                    "turnover_rate": 2.0,
                    "volume_ratio": 1.0,
                    "amplitude": 2.8,
                    "change_60d": 9.0,
                },
                {
                    "code": "000005",
                    "name": "ST风险股",
                    "price": 5.0,
                    "change_pct": 1.0,
                    "volume": 12_000_000,
                    "amount": 2.6e8,
                    "turnover_rate": 1.1,
                    "volume_ratio": 0.9,
                    "amplitude": 2.0,
                    "change_60d": 5.0,
                },
                {
                    "code": "830001",
                    "name": "北交所样本",
                    "price": 15.0,
                    "change_pct": 1.5,
                    "volume": 15_000_000,
                    "amount": 3.4e8,
                    "turnover_rate": 1.8,
                    "volume_ratio": 1.0,
                    "amplitude": 2.2,
                    "change_60d": 8.0,
                },
            ]
        )
        self.histories = {
            "600001": _make_history(start_price=11.0, slope=0.085, amount_base=9.0e8, volume_base=48_000_000),
            "600002": _make_history(start_price=15.0, slope=0.065, amount_base=7.2e8, volume_base=34_000_000),
            "300123": _make_history(start_price=18.0, slope=0.11, amount_base=6.5e8, volume_base=31_000_000),
            "600003": _make_history(start_price=10.5, slope=0.03, amount_base=3.2e8, volume_base=21_000_000),
        }
        self.boards = {
            "600001": [{"name": "AI算力"}, {"name": "服务器"}],
            "600002": [{"name": "机器人"}],
            "300123": [{"name": "AI算力"}],
            "600003": [{"name": "家电"}],
        }

    def get_cn_stock_list(self):
        return self.stock_list.copy(), "FakeListSource"

    def get_cn_realtime_snapshot(self):
        return self.snapshot.copy(), "FakeSnapshotSource"

    def get_daily_data(self, code: str, days: int = 140):
        normalized = str(code)
        self.daily_history_calls.append(normalized)
        return self.histories[normalized].copy().tail(days).reset_index(drop=True), "FakeDailySource"

    def get_sector_rankings(self, n: int = 5):
        return ([{"name": "AI算力"}, {"name": "机器人"}][:n], [])

    def get_belong_boards(self, stock_code: str):
        return list(self.boards.get(stock_code, []))


class StructuredScannerDataManager(FakeScannerDataManager):
    def __init__(
        self,
        *,
        stock_list_result: dict | None = None,
        snapshot_result: dict | None = None,
    ):
        super().__init__()
        self.stock_list_attempts = 0
        self.snapshot_attempts = 0
        self._stock_list_result = stock_list_result
        self._snapshot_result = snapshot_result

    def try_get_cn_stock_list(self, preferred_fetchers=None):
        self.stock_list_attempts += 1
        if self._stock_list_result is not None:
            return self._clone_result(self._stock_list_result)
        return {
            "success": True,
            "source": "FakeListSource",
            "data": self.stock_list.copy(),
            "attempts": [{"fetcher": "FakeListSource", "status": "success", "rows": int(len(self.stock_list))}],
            "error_code": None,
            "error_message": None,
        }

    def try_get_cn_realtime_snapshot(self, preferred_fetchers=None):
        self.snapshot_attempts += 1
        if self._snapshot_result is not None:
            return self._clone_result(self._snapshot_result)
        return {
            "success": True,
            "source": "FakeSnapshotSource",
            "data": self.snapshot.copy(),
            "attempts": [{"fetcher": "FakeSnapshotSource", "status": "success", "rows": int(len(self.snapshot))}],
            "error_code": None,
            "error_message": None,
        }

    @staticmethod
    def _clone_result(payload: dict) -> dict:
        cloned = dict(payload)
        data = cloned.get("data")
        if isinstance(data, pd.DataFrame):
            cloned["data"] = data.copy()
        attempts = cloned.get("attempts")
        if isinstance(attempts, list):
            cloned["attempts"] = [dict(item) for item in attempts]
        return cloned


class FetcherStub(BaseFetcher):
    def __init__(
        self,
        *,
        name: str,
        priority: int,
        stock_list: pd.DataFrame | None = None,
        snapshot: pd.DataFrame | None = None,
        stock_list_error: Exception | None = None,
        snapshot_error: Exception | None = None,
    ) -> None:
        self.name = name
        self.priority = priority
        self._stock_list = stock_list.copy() if isinstance(stock_list, pd.DataFrame) else stock_list
        self._snapshot = snapshot.copy() if isinstance(snapshot, pd.DataFrame) else snapshot
        self._stock_list_error = stock_list_error
        self._snapshot_error = snapshot_error

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (stock_code, start_date, end_date)
        return pd.DataFrame()

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        _ = stock_code
        return df

    def get_stock_list(self):
        if self._stock_list_error is not None:
            raise self._stock_list_error
        return self._stock_list.copy() if isinstance(self._stock_list, pd.DataFrame) else self._stock_list

    def get_a_share_spot_snapshot(self):
        if self._snapshot_error is not None:
            raise self._snapshot_error
        return self._snapshot.copy() if isinstance(self._snapshot, pd.DataFrame) else self._snapshot


class MarketScannerServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url="sqlite:///:memory:")
        self.stock_repo = StockRepository(self.db)
        self.data_manager = FakeScannerDataManager()
        self.service = MarketScannerService(self.db, data_manager=self.data_manager)

        local_history = self.data_manager.histories["600001"].copy()
        self.stock_repo.save_dataframe(local_history, "600001", data_source="LocalWarmCache")

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def _make_review_df(self, rows: list[tuple[str, float, float, float]]) -> pd.DataFrame:
        dates = pd.to_datetime([item[0] for item in rows])
        closes = [item[1] for item in rows]
        highs = [item[2] for item in rows]
        lows = [item[3] for item in rows]
        return pd.DataFrame(
            {
                "date": dates,
                "open": closes,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": [10_000_000] * len(rows),
                "amount": [3.0e8] * len(rows),
                "pct_chg": pd.Series(closes).pct_change().fillna(0.0) * 100.0,
            }
        )

    def _set_run_timestamps(self, run_id: int, run_at_iso: str, completed_at_iso: str) -> None:
        with self.db.get_session() as session:
            run = session.get(MarketScannerRun, run_id)
            assert run is not None
            run.run_at = datetime.fromisoformat(run_at_iso)
            run.completed_at = datetime.fromisoformat(completed_at_iso)
            session.add(run)
            session.commit()

    def _candidate_payload(self, symbol: str, name: str, rank: int, score: float, last_trade_date: str) -> dict:
        return {
            "symbol": symbol,
            "name": name,
            "rank": rank,
            "score": score,
            "quality_hint": "高优先级" if score >= 80 else "优先观察",
            "reason_summary": f"{name} 趋势与量能结构较好。",
            "reasons": [f"{name} 趋势结构完整。"],
            "key_metrics": [{"label": "最新价", "value": "10.00"}],
            "feature_signals": [{"label": "趋势结构", "value": "18.0 / 20"}],
            "risk_notes": ["注意弱开回落。"],
            "watch_context": [{"label": "观察触发", "value": "上破前高。"}],
            "boards": ["AI算力"],
            "_diagnostics": {
                "history": {
                    "latest_trade_date": last_trade_date,
                }
            },
        }

    def _seed_review_watchlists(self) -> tuple[int, int]:
        rows_600001 = [
            ("2026-04-09", 10.0, 10.2, 9.8),
            ("2026-04-10", 10.2, 10.4, 10.0),
            ("2026-04-13", 10.7, 10.9, 10.4),
            ("2026-04-14", 11.1, 11.3, 10.8),
            ("2026-04-15", 11.0, 11.2, 10.7),
        ]
        rows_600002 = [
            ("2026-04-09", 9.5, 9.7, 9.3),
            ("2026-04-10", 9.4, 9.6, 9.2),
            ("2026-04-13", 9.2, 9.3, 8.9),
            ("2026-04-14", 9.0, 9.1, 8.8),
            ("2026-04-15", 8.9, 9.0, 8.7),
        ]
        rows_300123 = [
            ("2026-04-09", 20.0, 20.2, 19.8),
            ("2026-04-10", 20.5, 20.8, 20.1),
            ("2026-04-13", 21.3, 21.8, 21.0),
            ("2026-04-14", 21.8, 22.2, 21.5),
            ("2026-04-15", 22.1, 22.5, 21.8),
        ]
        rows_benchmark = [
            ("2026-04-09", 4000.0, 4010.0, 3990.0),
            ("2026-04-10", 4020.0, 4035.0, 4010.0),
            ("2026-04-13", 4040.0, 4055.0, 4030.0),
            ("2026-04-14", 4050.0, 4065.0, 4040.0),
            ("2026-04-15", 4060.0, 4075.0, 4050.0),
        ]
        self.stock_repo.save_dataframe(self._make_review_df(rows_600001), "600001", data_source="ReviewFixture")
        self.stock_repo.save_dataframe(self._make_review_df(rows_600002), "600002", data_source="ReviewFixture")
        self.stock_repo.save_dataframe(self._make_review_df(rows_300123), "300123", data_source="ReviewFixture")
        self.stock_repo.save_dataframe(self._make_review_df(rows_benchmark), "000300", data_source="ReviewFixture")

        previous = self.service.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="A股盘前扫描 v1",
            universe_name="cn_a_liquid_watchlist_v1",
            status="completed",
            headline="2026-04-10 watchlist",
            trigger_mode="scheduled",
            request_source="scheduler",
            watchlist_date="2026-04-10",
            source_summary="scanner=daily",
            diagnostics={},
            universe_notes=[],
            scoring_notes=[],
            shortlist=[
                self._candidate_payload("600001", "算力龙头", 1, 84.0, "2026-04-09"),
                self._candidate_payload("600002", "机器人核心", 2, 78.0, "2026-04-09"),
            ],
            universe_size=300,
            preselected_size=60,
            evaluated_size=40,
        )
        current = self.service.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="A股盘前扫描 v1",
            universe_name="cn_a_liquid_watchlist_v1",
            status="completed",
            headline="2026-04-13 watchlist",
            trigger_mode="scheduled",
            request_source="scheduler",
            watchlist_date="2026-04-13",
            source_summary="scanner=daily",
            diagnostics={},
            universe_notes=[],
            scoring_notes=[],
            shortlist=[
                self._candidate_payload("300123", "高景气成长", 1, 88.0, "2026-04-10"),
                self._candidate_payload("600001", "算力龙头", 2, 82.0, "2026-04-10"),
            ],
            universe_size=320,
            preselected_size=62,
            evaluated_size=42,
        )
        self._set_run_timestamps(previous["id"], "2026-04-10T08:40:00", "2026-04-10T08:41:00")
        self._set_run_timestamps(current["id"], "2026-04-13T08:40:00", "2026-04-13T08:41:00")
        return previous["id"], current["id"]

    def test_run_scan_builds_ranked_shortlist_and_persists_history(self) -> None:
        result = self.service.run_scan(
            market="cn",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
        )

        self.assertEqual(result["market"], "cn")
        self.assertEqual(result["shortlist_size"], 3)
        self.assertEqual(result["headline"].startswith("今日 A 股盘前优先观察："), True)
        self.assertGreaterEqual(result["diagnostics"]["history_stats"]["local_hits"], 1)
        self.assertNotIn("600001", self.data_manager.daily_history_calls)

        shortlist = result["shortlist"]
        self.assertEqual(shortlist[0]["symbol"], "600001")
        self.assertEqual(shortlist[0]["rank"], 1)
        self.assertTrue(shortlist[0]["reason_summary"])
        self.assertGreaterEqual(len(shortlist[0]["key_metrics"]), 4)
        self.assertGreaterEqual(len(shortlist[0]["risk_notes"]), 1)
        self.assertGreaterEqual(len(shortlist[0]["watch_context"]), 3)
        self.assertIn("AI算力", shortlist[0]["boards"])

        history = self.service.list_runs(market="cn", page=1, limit=10)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["id"], result["id"])
        self.assertIn("600001", history["items"][0]["top_symbols"])

        detail = self.service.get_run_detail(result["id"])
        self.assertIsNotNone(detail)
        self.assertEqual(detail["shortlist"][0]["symbol"], "600001")
        self.assertEqual(detail["shortlist"][0]["appeared_in_recent_runs"], 0)

    def test_run_scan_rejects_unimplemented_market_profile(self) -> None:
        with self.assertRaises(ValueError):
            self.service.run_scan(market="us")

    def test_run_scan_prefers_local_universe_cache_and_skips_online_stock_list(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        cache_path = Path(temp_dir.name) / "scanner_cn_universe_cache.csv"
        self.data_manager.stock_list[["code", "name"]].to_csv(cache_path, index=False)

        manager = StructuredScannerDataManager()
        service = MarketScannerService(
            self.db,
            data_manager=manager,
            local_universe_cache_path=str(cache_path),
        )

        result = service.run_scan(
            market="cn",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(manager.stock_list_attempts, 0)
        self.assertEqual(result["diagnostics"]["scanner_data"]["universe_resolution"]["source"], "local_universe_cache")
        self.assertIn("universe=local_universe_cache", result["source_summary"])

    def test_resolve_cn_stock_universe_uses_builtin_mapping_after_tushare_permission_denied(self) -> None:
        DatabaseManager.reset_instance()
        empty_db = DatabaseManager(db_url="sqlite:///:memory:")
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        cache_path = Path(temp_dir.name) / "scanner_cn_universe_cache.csv"

        manager = DataFetcherManager(
            fetchers=[
                FetcherStub(
                    name="TushareFetcher",
                    priority=1,
                    stock_list_error=DataFetchError("permission denied for stock_basic"),
                )
            ]
        )
        service = MarketScannerService(
            empty_db,
            data_manager=manager,
            local_universe_cache_path=str(cache_path),
        )

        result = service._resolve_cn_stock_universe()

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "builtin_stock_mapping")
        self.assertTrue(cache_path.exists())
        self.assertIn("600519", result["data"]["code"].tolist())
        attempt_codes = [item.get("reason_code") for item in result["attempts"] if item.get("reason_code")]
        self.assertIn("tushare_permission_denied", attempt_codes)

    def test_snapshot_fetcher_manager_falls_back_from_akshare_to_efinance(self) -> None:
        snapshot = self.data_manager.snapshot.copy()
        manager = DataFetcherManager(
            fetchers=[
                FetcherStub(
                    name="AkshareFetcher",
                    priority=1,
                    snapshot_error=DataFetchError("stock_zh_a_spot_em unavailable"),
                ),
                FetcherStub(
                    name="EfinanceFetcher",
                    priority=2,
                    snapshot=snapshot,
                ),
            ]
        )

        result = manager.try_get_cn_realtime_snapshot(
            preferred_fetchers=["AkshareFetcher", "EfinanceFetcher"],
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "EfinanceFetcher")
        self.assertEqual(result["attempts"][0]["reason_code"], "akshare_snapshot_fetch_failed")
        self.assertEqual(result["attempts"][1]["status"], "success")

    def test_snapshot_fetcher_manager_returns_precise_failure_attempts(self) -> None:
        manager = DataFetcherManager(
            fetchers=[
                FetcherStub(
                    name="AkshareFetcher",
                    priority=1,
                    snapshot_error=DataFetchError("stock_zh_a_spot_em unavailable"),
                ),
                FetcherStub(
                    name="EfinanceFetcher",
                    priority=2,
                    snapshot_error=DataFetchError("ef.stock.get_realtime_quotes timeout"),
                ),
            ]
        )

        result = manager.try_get_cn_realtime_snapshot(
            preferred_fetchers=["AkshareFetcher", "EfinanceFetcher"],
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "no_realtime_snapshot_available")
        self.assertEqual(
            [item["reason_code"] for item in result["attempts"]],
            ["akshare_snapshot_fetch_failed", "efinance_snapshot_fetch_failed"],
        )

    def test_run_scan_uses_degraded_mode_when_realtime_snapshot_unavailable(self) -> None:
        for code, history in self.data_manager.histories.items():
            self.stock_repo.save_dataframe(history.copy(), code, data_source="LocalWarmCache")

        manager = StructuredScannerDataManager(
            snapshot_result={
                "success": False,
                "source": None,
                "data": None,
                "attempts": [
                    {
                        "fetcher": "AkshareFetcher",
                        "status": "failed",
                        "reason_code": "akshare_snapshot_fetch_failed",
                        "summary": "[AkshareFetcher] (DataFetchError) stock_zh_a_spot_em unavailable",
                    },
                    {
                        "fetcher": "EfinanceFetcher",
                        "status": "failed",
                        "reason_code": "efinance_snapshot_fetch_failed",
                        "summary": "[EfinanceFetcher] (DataFetchError) timeout",
                    },
                ],
                "error_code": "no_realtime_snapshot_available",
                "error_message": "snapshot unavailable",
            }
        )
        service = MarketScannerService(self.db, data_manager=manager)

        result = service.run_scan(
            market="cn",
            shortlist_size=3,
            universe_limit=50,
            detail_limit=10,
        )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["diagnostics"]["scanner_data"]["degraded_mode_used"])
        self.assertIn("snapshot=local_history_degraded", result["source_summary"])
        self.assertIn("degraded=yes", result["source_summary"])
        self.assertTrue(any("降级快照" in note for note in result["universe_notes"]))

    def test_run_scan_raises_structured_error_when_no_snapshot_and_no_degraded_mode(self) -> None:
        DatabaseManager.reset_instance()
        empty_db = DatabaseManager(db_url="sqlite:///:memory:")
        empty_service = MarketScannerService(
            empty_db,
            data_manager=StructuredScannerDataManager(
                snapshot_result={
                    "success": False,
                    "source": None,
                    "data": None,
                    "attempts": [
                        {
                            "fetcher": "AkshareFetcher",
                            "status": "failed",
                            "reason_code": "akshare_snapshot_fetch_failed",
                            "summary": "[AkshareFetcher] (DataFetchError) stock_zh_a_spot_em unavailable",
                        },
                        {
                            "fetcher": "EfinanceFetcher",
                            "status": "failed",
                            "reason_code": "efinance_snapshot_fetch_failed",
                            "summary": "[EfinanceFetcher] (DataFetchError) timeout",
                        },
                    ],
                    "error_code": "no_realtime_snapshot_available",
                    "error_message": "snapshot unavailable",
                }
            ),
        )

        with self.assertRaises(ScannerRuntimeError) as ctx:
            empty_service.run_scan(
                market="cn",
                shortlist_size=3,
                universe_limit=50,
                detail_limit=10,
            )

        self.assertEqual(ctx.exception.reason_code, "no_realtime_snapshot_available")
        self.assertIn("snapshot_resolution", ctx.exception.diagnostics)
        self.assertIn("snapshot_attempts", ctx.exception.source_summary or "")

    def test_get_run_detail_includes_comparison_and_realized_outcomes(self) -> None:
        _, current_run_id = self._seed_review_watchlists()

        detail = self.service.get_run_detail(current_run_id)

        assert detail is not None
        self.assertTrue(detail["comparison_to_previous"]["available"])
        self.assertEqual(detail["comparison_to_previous"]["new_count"], 1)
        self.assertEqual(detail["comparison_to_previous"]["retained_count"], 1)
        self.assertEqual(detail["comparison_to_previous"]["dropped_count"], 1)
        self.assertEqual(detail["comparison_to_previous"]["new_symbols"][0]["symbol"], "300123")
        self.assertEqual(detail["comparison_to_previous"]["retained_symbols"][0]["symbol"], "600001")
        self.assertEqual(detail["comparison_to_previous"]["retained_symbols"][0]["rank_delta"], -1)
        self.assertEqual(detail["comparison_to_previous"]["dropped_symbols"][0]["symbol"], "600002")
        self.assertTrue(detail["review_summary"]["available"])
        self.assertGreater(detail["review_summary"]["avg_review_window_return_pct"], 0.0)
        candidate_map = {item["symbol"]: item for item in detail["shortlist"]}
        self.assertEqual(candidate_map["300123"]["realized_outcome"]["review_status"], "ready")
        self.assertEqual(candidate_map["300123"]["realized_outcome"]["thesis_match"], "validated")
        self.assertTrue(candidate_map["300123"]["realized_outcome"]["outperformed_benchmark"])

    def test_list_recent_watchlists_includes_change_and_review_summaries(self) -> None:
        self._seed_review_watchlists()

        response = self.service.list_recent_watchlists(
            market="cn",
            profile="cn_preopen_v1",
            limit_days=5,
        )

        self.assertEqual(response["total"], 2)
        latest = response["items"][0]
        previous = response["items"][1]
        self.assertTrue(latest["change_summary"]["available"])
        self.assertEqual(latest["change_summary"]["new_count"], 1)
        self.assertTrue(latest["review_summary"]["available"])
        self.assertEqual(previous["change_summary"]["available"], False)
        self.assertTrue(previous["review_summary"]["available"])

    def test_operational_status_exposes_recent_quality_summary(self) -> None:
        self._seed_review_watchlists()

        status = self.service.get_operational_status(
            market="cn",
            profile="cn_preopen_v1",
        )

        quality = status["quality_summary"]
        self.assertTrue(quality["available"])
        self.assertEqual(quality["run_count"], 2)
        self.assertEqual(quality["reviewed_run_count"], 2)
        self.assertGreater(quality["avg_shortlist_return_pct"], 0.0)
        self.assertGreater(quality["hit_rate_pct"], 0.0)
        self.assertGreater(quality["positive_candidate_avg_score"], quality["negative_candidate_avg_score"])


if __name__ == "__main__":
    unittest.main()
