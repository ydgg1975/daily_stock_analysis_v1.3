# -*- coding: utf-8 -*-
"""Focused coverage for the PostgreSQL Phase D scanner/watchlist baseline."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from src.config import Config
from src.multi_user import OWNERSHIP_SCOPE_SYSTEM, OWNERSHIP_SCOPE_USER
from src.services.market_scanner_service import MarketScannerService
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _candidate_payload(
    symbol: str,
    *,
    name: str,
    rank: int,
    score: float,
    reason: str,
) -> dict:
    return {
        "symbol": symbol,
        "name": name,
        "rank": rank,
        "score": score,
        "quality_hint": "高优先级" if score >= 80 else "优先观察",
        "reason_summary": reason,
        "reasons": [f"{name} 趋势与量能结构完整。"],
        "key_metrics": [{"label": "最新价", "value": "10.20"}],
        "feature_signals": [{"label": "趋势结构", "value": "18.0 / 20"}],
        "risk_notes": ["注意弱开回落。"],
        "watch_context": [{"label": "观察触发", "value": "上破前高。"}],
        "boards": ["AI算力"],
        "_diagnostics": {
            "history": {
                "latest_trade_date": "2026-04-15",
            }
        },
    }


class PostgresPhaseDStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.phase_db_path = self.data_dir / "phase-baseline.sqlite"
        self._configure_environment(enable_phase_d=True)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self.temp_dir.cleanup()

    def _configure_environment(self, *, enable_phase_d: bool) -> None:
        lines = [
            "STOCK_LIST=600519",
            "GEMINI_API_KEY=test",
            "ADMIN_AUTH_ENABLED=true",
            f"DATABASE_PATH={self.sqlite_db_path}",
        ]
        if enable_phase_d:
            lines.extend(
                [
                    f"POSTGRES_PHASE_A_URL=sqlite:///{self.phase_db_path}",
                    "POSTGRES_PHASE_A_APPLY_SCHEMA=true",
                ]
            )

        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        if enable_phase_d:
            os.environ["POSTGRES_PHASE_A_URL"] = f"sqlite:///{self.phase_db_path}"
            os.environ["POSTGRES_PHASE_A_APPLY_SCHEMA"] = "true"
        else:
            os.environ.pop("POSTGRES_PHASE_A_URL", None)
            os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)

        Config.reset_instance()
        DatabaseManager.reset_instance()
        auth.refresh_auth_state()

    def _db(self) -> DatabaseManager:
        return DatabaseManager.get_instance()

    def test_phase_d_dual_writes_scanner_runs_candidates_and_watchlists(self) -> None:
        from src.postgres_phase_d import (
            PhaseDScannerCandidate,
            PhaseDScannerRun,
            PhaseDWatchlist,
            PhaseDWatchlistItem,
        )

        db = self._db()
        db.create_or_update_app_user(user_id="scanner-user", username="scanner-user")
        service = MarketScannerService(db, owner_id="scanner-user")

        saved = service.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="A股盘前扫描 v1",
            universe_name="cn_a_liquid_watchlist_v1",
            status="completed",
            headline="2026-04-16 手动观察名单",
            trigger_mode="manual",
            request_source="api",
            watchlist_date="2026-04-16",
            source_summary="scanner=daily",
            shortlist=[
                _candidate_payload("600001", name="算力龙头", rank=1, score=88.2, reason="趋势共振最强。"),
                _candidate_payload("600002", name="机器人核心", rank=2, score=81.4, reason="量价结构改善。"),
            ],
            universe_size=320,
            preselected_size=64,
            evaluated_size=42,
            scope=OWNERSHIP_SCOPE_USER,
            owner_id="scanner-user",
        )

        detail = service.get_run_detail(saved["id"], scope=OWNERSHIP_SCOPE_USER, owner_id="scanner-user")
        assert detail is not None
        self.assertEqual([item["symbol"] for item in detail["shortlist"]], ["600001", "600002"])

        with db._phase_d_store.session_scope() as session:
            pg_run = session.query(PhaseDScannerRun).filter(PhaseDScannerRun.id == saved["id"]).one()
            pg_candidates = (
                session.query(PhaseDScannerCandidate)
                .filter(PhaseDScannerCandidate.scanner_run_id == saved["id"])
                .order_by(PhaseDScannerCandidate.rank.asc())
                .all()
            )
            pg_watchlist = (
                session.query(PhaseDWatchlist)
                .filter(PhaseDWatchlist.source_scanner_run_id == saved["id"])
                .one()
            )
            pg_watchlist_items = (
                session.query(PhaseDWatchlistItem)
                .filter(PhaseDWatchlistItem.watchlist_id == pg_watchlist.id)
                .order_by(PhaseDWatchlistItem.rank.asc())
                .all()
            )

        self.assertEqual(pg_run.scope, OWNERSHIP_SCOPE_USER)
        self.assertEqual(pg_run.owner_user_id, "scanner-user")
        self.assertEqual(pg_run.trigger_mode, "manual")
        self.assertEqual(pg_run.request_source, "api")
        self.assertEqual(pg_run.shortlist_size, 2)
        self.assertEqual(pg_run.headline, "2026-04-16 手动观察名单")
        self.assertEqual([row.canonical_symbol for row in pg_candidates], ["600001", "600002"])
        self.assertEqual(pg_candidates[0].candidate_payload["watch_context"][0]["label"], "观察触发")
        self.assertEqual(pg_watchlist.scope, OWNERSHIP_SCOPE_USER)
        self.assertEqual(pg_watchlist.owner_user_id, "scanner-user")
        self.assertEqual(pg_watchlist.watchlist_date.isoformat(), "2026-04-16")
        self.assertEqual(pg_watchlist.status, "active")
        self.assertEqual(pg_watchlist.notification_summary, {})
        self.assertEqual([row.canonical_symbol for row in pg_watchlist_items], ["600001", "600002"])
        self.assertEqual(pg_watchlist_items[0].selection_reason, "趋势共振最强。")

    def test_phase_d_updates_shadow_watchlist_metadata_when_run_operation_state_changes(self) -> None:
        from src.postgres_phase_d import PhaseDScannerRun, PhaseDWatchlist, PhaseDWatchlistItem

        db = self._db()
        db.create_or_update_app_user(user_id="ops-user", username="ops-user")
        service = MarketScannerService(db, owner_id="ops-user")

        saved = service.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="A股盘前扫描 v1",
            universe_name="cn_a_liquid_watchlist_v1",
            status="completed",
            headline="待更新 run",
            trigger_mode="manual",
            request_source="cli",
            watchlist_date="2026-04-15",
            source_summary="scanner=terminal",
            shortlist=[_candidate_payload("600001", name="算力龙头", rank=1, score=85.0, reason="首选。")],
            scope=OWNERSHIP_SCOPE_USER,
            owner_id="ops-user",
        )

        updated = service.update_run_operation_metadata(
            saved["id"],
            trigger_mode="scheduled",
            watchlist_date="2026-04-16",
            request_source="scheduler",
            notification_result={
                "attempted": True,
                "status": "success",
                "success": True,
                "channels": ["feishu"],
                "message": "sent",
            },
            failure_reason="同步通知已记录",
            scope=OWNERSHIP_SCOPE_USER,
            owner_id="ops-user",
        )

        assert updated is not None
        self.assertEqual(updated["watchlist_date"], "2026-04-16")
        self.assertEqual(updated["notification"]["status"], "success")
        self.assertEqual(updated["failure_reason"], "同步通知已记录")

        with db._phase_d_store.session_scope() as session:
            pg_run = session.query(PhaseDScannerRun).filter(PhaseDScannerRun.id == saved["id"]).one()
            pg_watchlist = (
                session.query(PhaseDWatchlist)
                .filter(PhaseDWatchlist.source_scanner_run_id == saved["id"])
                .one()
            )
            first_watchlist_item = (
                session.query(PhaseDWatchlistItem)
                .filter(PhaseDWatchlistItem.watchlist_id == pg_watchlist.id)
                .order_by(PhaseDWatchlistItem.rank.asc())
                .first()
            )
        assert first_watchlist_item is not None
        first_candidate_ref = int(first_watchlist_item.source_scanner_candidate_id)

        self.assertEqual(pg_run.trigger_mode, "scheduled")
        self.assertEqual(pg_run.request_source, "scheduler")
        self.assertEqual(pg_run.status, "completed")
        self.assertEqual(pg_run.diagnostics_json["notification"]["status"], "success")
        self.assertEqual(pg_watchlist.watchlist_date.isoformat(), "2026-04-16")
        self.assertEqual(pg_watchlist.notification_status, "success")
        self.assertEqual(pg_watchlist.notification_summary["channels"], ["feishu"])

        updated_failed = service.update_run_operation_metadata(
            saved["id"],
            trigger_mode="scheduler",
            watchlist_date="2026-04-17",
            request_source="scheduler",
            notification_result={
                "attempted": True,
                "status": "failed",
                "success": False,
                "channels": ["feishu"],
                "message": "retry later",
            },
            scope=OWNERSHIP_SCOPE_USER,
            owner_id="ops-user",
        )

        assert updated_failed is not None
        self.assertEqual(updated_failed["watchlist_date"], "2026-04-17")
        self.assertEqual(updated_failed["notification"]["status"], "failed")

        with db._phase_d_store.session_scope() as session:
            pg_run = session.query(PhaseDScannerRun).filter(PhaseDScannerRun.id == saved["id"]).one()
            pg_watchlist = (
                session.query(PhaseDWatchlist)
                .filter(PhaseDWatchlist.source_scanner_run_id == saved["id"])
                .one()
            )
            ref_count = (
                session.query(PhaseDWatchlistItem)
                .filter(PhaseDWatchlistItem.source_scanner_candidate_id == first_candidate_ref)
                .count()
            )

        self.assertEqual(pg_run.status, "completed")
        self.assertEqual(pg_run.diagnostics_json["notification"]["status"], "failed")
        self.assertEqual(pg_watchlist.watchlist_date.isoformat(), "2026-04-17")
        self.assertEqual(pg_watchlist.notification_status, "failed")
        self.assertEqual(pg_watchlist.notification_summary["message"], "retry later")
        self.assertEqual(ref_count, 1)

    def test_phase_d_preserves_owner_partitioning_and_system_watchlist_visibility_contract(self) -> None:
        from src.postgres_phase_d import PhaseDScannerRun, PhaseDWatchlist

        db = self._db()
        db.create_or_update_app_user(user_id="user-a", username="user-a")
        db.create_or_update_app_user(user_id="user-b", username="user-b")
        service_a = MarketScannerService(db, owner_id="user-a")
        service_b = MarketScannerService(db, owner_id="user-b")

        run_a = service_a.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="Scanner",
            universe_name="fixture",
            status="completed",
            headline="user a run",
            trigger_mode="manual",
            request_source="api",
            watchlist_date="2026-04-16",
            source_summary="fixture",
            shortlist=[],
            scope=OWNERSHIP_SCOPE_USER,
            owner_id="user-a",
        )
        system_run = service_a.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="Scanner",
            universe_name="fixture",
            status="completed",
            headline="system run",
            trigger_mode="scheduled",
            request_source="scheduler",
            watchlist_date="2026-04-16",
            source_summary="fixture",
            shortlist=[],
            scope=OWNERSHIP_SCOPE_SYSTEM,
            owner_id=None,
        )
        run_b = service_b.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="Scanner",
            universe_name="fixture",
            status="completed",
            headline="user b run",
            trigger_mode="manual",
            request_source="api",
            watchlist_date="2026-04-16",
            source_summary="fixture",
            shortlist=[],
            scope=OWNERSHIP_SCOPE_USER,
            owner_id="user-b",
        )

        history_a = service_a.list_runs(market="cn", profile="cn_preopen_v1", page=1, limit=10)
        history_b = service_b.list_runs(market="cn", profile="cn_preopen_v1", page=1, limit=10)
        recent_watchlists = service_b.list_recent_watchlists(market="cn", profile="cn_preopen_v1", limit_days=5)

        self.assertEqual({item["id"] for item in history_a["items"]}, {run_a["id"], system_run["id"]})
        self.assertEqual({item["id"] for item in history_b["items"]}, {run_b["id"], system_run["id"]})
        self.assertEqual(recent_watchlists["total"], 1)
        self.assertEqual(recent_watchlists["items"][0]["id"], system_run["id"])

        with db._phase_d_store.session_scope() as session:
            run_rows = {
                (row.id, row.scope, row.owner_user_id)
                for row in session.query(PhaseDScannerRun).all()
            }
            watchlist_rows = {
                (row.source_scanner_run_id, row.scope, row.owner_user_id)
                for row in session.query(PhaseDWatchlist).all()
            }

        self.assertEqual(
            run_rows,
            {
                (run_a["id"], OWNERSHIP_SCOPE_USER, "user-a"),
                (run_b["id"], OWNERSHIP_SCOPE_USER, "user-b"),
                (system_run["id"], OWNERSHIP_SCOPE_SYSTEM, None),
            },
        )
        self.assertEqual(
            watchlist_rows,
            {
                (run_a["id"], OWNERSHIP_SCOPE_USER, "user-a"),
                (run_b["id"], OWNERSHIP_SCOPE_USER, "user-b"),
                (system_run["id"], OWNERSHIP_SCOPE_SYSTEM, None),
            },
        )

    def test_phase_d_factory_reset_clears_user_shadow_state_but_keeps_system_watchlists(self) -> None:
        from src.postgres_phase_d import PhaseDScannerRun, PhaseDWatchlist

        db = self._db()
        db.create_or_update_app_user(user_id="cleanup-user", username="cleanup-user")
        service = MarketScannerService(db, owner_id="cleanup-user")

        user_run = service.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="Scanner",
            universe_name="fixture",
            status="completed",
            headline="cleanup manual",
            trigger_mode="manual",
            request_source="api",
            watchlist_date="2026-04-16",
            source_summary="fixture",
            shortlist=[_candidate_payload("600001", name="算力龙头", rank=1, score=80.0, reason="保留观察。")],
            scope=OWNERSHIP_SCOPE_USER,
            owner_id="cleanup-user",
        )
        system_run = service.record_terminal_run(
            market="cn",
            profile="cn_preopen_v1",
            profile_label="Scanner",
            universe_name="fixture",
            status="completed",
            headline="cleanup scheduled",
            trigger_mode="scheduled",
            request_source="scheduler",
            watchlist_date="2026-04-16",
            source_summary="fixture",
            shortlist=[],
            scope=OWNERSHIP_SCOPE_SYSTEM,
            owner_id=None,
        )

        result = db.factory_reset_non_bootstrap_state()

        self.assertIn("scanner_runs", result["cleared"])
        with db.get_session() as session:
            from src.storage import MarketScannerRun

            self.assertIsNone(session.get(MarketScannerRun, user_run["id"]))
            self.assertIsNotNone(session.get(MarketScannerRun, system_run["id"]))

        with db._phase_d_store.session_scope() as session:
            remaining_runs = {
                (row.id, row.scope, row.owner_user_id)
                for row in session.query(PhaseDScannerRun).all()
            }
            remaining_watchlists = {
                (row.source_scanner_run_id, row.scope, row.owner_user_id)
                for row in session.query(PhaseDWatchlist).all()
            }

        self.assertEqual(remaining_runs, {(system_run["id"], OWNERSHIP_SCOPE_SYSTEM, None)})
        self.assertEqual(remaining_watchlists, {(system_run["id"], OWNERSHIP_SCOPE_SYSTEM, None)})

    def test_factory_reset_runs_phase_d_cleanup_before_phase_a_user_deletion(self) -> None:
        db = self._db()
        db._sqlite_create_or_update_app_user(
            user_id="reset-order-user",
            username="reset-order-user",
        )

        call_order: list[str] = []

        class _FakePhaseAStore:
            def dispose(self):
                return None

            def list_non_bootstrap_user_ids(self):
                return []

            def clear_non_bootstrap_state(self, user_ids):
                call_order.append(f"phase_a:{','.join(sorted(user_ids))}")
                return {
                    "user_preferences": 0,
                    "app_user_sessions": 0,
                    "app_users": 0,
                    "notification_targets": 0,
                }

        class _FakePhaseBStore:
            def dispose(self):
                return None

            def clear_non_bootstrap_state(self, user_ids):
                call_order.append(f"phase_b:{','.join(sorted(user_ids))}")
                return {
                    "chat_messages": 0,
                    "chat_sessions": 0,
                    "analysis_records": 0,
                    "analysis_sessions": 0,
                }

        class _FakePhaseDStore:
            def dispose(self):
                return None

            def clear_non_bootstrap_state(self, user_ids):
                call_order.append(f"phase_d:{','.join(sorted(user_ids))}")
                return {
                    "scanner_candidates": 0,
                    "scanner_runs": 0,
                    "watchlist_items": 0,
                    "watchlists": 0,
                }

        db._phase_a_enabled = True
        db._phase_b_enabled = True
        db._phase_d_enabled = True
        db._phase_a_store = _FakePhaseAStore()
        db._phase_b_store = _FakePhaseBStore()
        db._phase_d_store = _FakePhaseDStore()

        result = db.factory_reset_non_bootstrap_state()

        self.assertEqual(
            call_order,
            [
                "phase_b:reset-order-user",
                "phase_d:reset-order-user",
                "phase_a:reset-order-user",
            ],
        )
        self.assertEqual(result["cleared"], ["app_users"])
        self.assertEqual(result["counts"]["app_users"], 1)


if __name__ == "__main__":
    unittest.main()
