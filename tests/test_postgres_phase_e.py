# -*- coding: utf-8 -*-
"""Focused coverage for the PostgreSQL Phase E backtest baseline."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from src.config import Config
from src.postgres_phase_e import (
    PhaseEBacktestArtifact,
    PhaseEBacktestRun,
    phase_e_shadow_run_id,
)
from src.services.backtest_service import BacktestService
from src.services.rule_backtest_service import RuleBacktestService
from src.services.us_history_helper import LOCAL_US_PARQUET_SOURCE
from src.storage import AnalysisHistory, BacktestResult, BacktestRun, BacktestSummary, DatabaseManager, RuleBacktestRun, RuleBacktestTrade, StockDaily


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class PostgresPhaseEStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.phase_db_path = self.data_dir / "phase-baseline.sqlite"
        self._configure_environment(enable_phase_e=True)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        os.environ.pop("LOCAL_US_PARQUET_DIR", None)
        self.temp_dir.cleanup()

    def _configure_environment(self, *, enable_phase_e: bool) -> None:
        lines = [
            "STOCK_LIST=600519",
            "GEMINI_API_KEY=test",
            "ADMIN_AUTH_ENABLED=true",
            f"DATABASE_PATH={self.sqlite_db_path}",
        ]
        if enable_phase_e:
            lines.extend(
                [
                    f"POSTGRES_PHASE_A_URL=sqlite:///{self.phase_db_path}",
                    "POSTGRES_PHASE_A_APPLY_SCHEMA=true",
                ]
            )

        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        if enable_phase_e:
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

    def _create_user(self, user_id: str = "phase-e-user") -> None:
        self._db().create_or_update_app_user(
            user_id=user_id,
            username=user_id,
            display_name="Phase E User",
            role="user",
            password_hash="hash",
            is_active=True,
        )

    def _seed_historical_eval_fixture(
        self,
        *,
        owner_id: str,
        code: str = "600519",
        include_stock_rows: bool = True,
        analysis_date: date = date(2024, 1, 1),
    ) -> None:
        created_at = datetime.combine(analysis_date, datetime.min.time()) - timedelta(days=30)
        with self._db().get_session() as session:
            session.add(
                AnalysisHistory(
                    owner_id=owner_id,
                    query_id=f"phase-e-analysis:{code}",
                    code=code,
                    name=code,
                    report_type="simple",
                    sentiment_score=80,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="phase-e historical eval fixture",
                    stop_loss=95.0,
                    take_profit=110.0,
                    created_at=created_at,
                    context_snapshot=json_dumps({"enhanced_context": {"date": analysis_date.isoformat()}}),
                )
            )
            if include_stock_rows:
                session.add(
                    StockDaily(
                        code=code,
                        date=analysis_date,
                        open=100.0,
                        high=101.0,
                        low=99.0,
                        close=100.0,
                        data_source="DatabaseCache",
                    )
                )
                session.add_all(
                    [
                        StockDaily(code=code, date=analysis_date + timedelta(days=1), high=111.0, low=100.0, close=105.0, data_source="DatabaseCache"),
                        StockDaily(code=code, date=analysis_date + timedelta(days=2), high=108.0, low=103.0, close=106.0, data_source="DatabaseCache"),
                        StockDaily(code=code, date=analysis_date + timedelta(days=3), high=109.0, low=104.0, close=107.0, data_source="DatabaseCache"),
                    ]
                )
            session.commit()

    def _seed_rule_backtest_prices(self, *, code: str = "600519") -> None:
        with self._db().get_session() as session:
            closes = [
                10.0, 10.2, 10.1, 10.5, 11.0, 11.6, 11.8, 11.2,
                10.8, 10.2, 9.9, 10.3, 10.9, 11.4, 11.9, 12.1,
                11.7, 11.1, 10.7, 10.4, 10.8, 11.3, 11.8, 12.2,
            ]
            for index, close in enumerate(closes):
                current_date = date(2024, 1, 1) + timedelta(days=index)
                session.add(
                    StockDaily(
                        code=code,
                        date=current_date,
                        open=close - 0.1,
                        high=close + 0.2,
                        low=close - 0.3,
                        close=float(close),
                        data_source="DatabaseCache",
                    )
                )
            session.commit()

    def test_phase_e_shadows_historical_eval_runs_results_and_summaries(self) -> None:
        db = self._db()
        self._create_user()
        self._seed_historical_eval_fixture(owner_id="phase-e-user")

        service = BacktestService(db, owner_id="phase-e-user")
        stats = service.run_backtest(code="600519", force=False, eval_window_days=3, min_age_days=0, limit=10)

        self.assertEqual(stats["saved"], 1)
        with db.get_session() as session:
            sqlite_run = session.query(BacktestRun).one()
            self.assertEqual(session.query(BacktestResult).count(), 1)
            self.assertEqual(session.query(BacktestSummary).count(), 2)

        with db._phase_e_store.session_scope() as session:
            pg_run = (
                session.query(PhaseEBacktestRun)
                .filter(PhaseEBacktestRun.id == phase_e_shadow_run_id("analysis_eval", int(sqlite_run.id)))
                .one()
            )
            pg_artifacts = (
                session.query(PhaseEBacktestArtifact)
                .filter(PhaseEBacktestArtifact.backtest_run_id == pg_run.id)
                .order_by(PhaseEBacktestArtifact.artifact_kind.asc())
                .all()
            )

        self.assertEqual(pg_run.run_type, "analysis_eval")
        self.assertEqual(pg_run.owner_user_id, "phase-e-user")
        self.assertEqual(pg_run.canonical_symbol, "600519")
        self.assertEqual(pg_run.status, "completed")
        self.assertEqual(pg_run.request_payload["legacy_run_id"], int(sqlite_run.id))
        self.assertEqual(pg_run.request_payload["eval_window_days"], 3)
        self.assertEqual(pg_run.request_payload["min_age_days"], 0)
        self.assertEqual(pg_run.metrics_json["saved"], 1)
        self.assertEqual(
            [artifact.artifact_kind for artifact in pg_artifacts],
            ["evaluation_rows", "summary"],
        )
        evaluation_artifact = next(item for item in pg_artifacts if item.artifact_kind == "evaluation_rows")
        summary_artifact = next(item for item in pg_artifacts if item.artifact_kind == "summary")
        self.assertEqual(len(evaluation_artifact.payload_json["rows"]), 1)
        self.assertEqual(evaluation_artifact.payload_json["rows"][0]["code"], "600519")
        self.assertEqual(summary_artifact.payload_json["stock_summary"]["code"], "600519")
        self.assertEqual(summary_artifact.payload_json["overall_summary"]["scope"], "overall")

    def test_phase_e_records_local_parquet_usage_refs_only_when_runtime_source_is_concrete(self) -> None:
        db = self._db()
        self._create_user()
        self._seed_historical_eval_fixture(owner_id="phase-e-user", code="AAPL", include_stock_rows=False)

        parquet_root = self.data_dir / "local-us"
        parquet_root.mkdir(parents=True, exist_ok=True)
        (parquet_root / "AAPL.parquet").write_bytes(b"phase-e-local-parquet")
        os.environ["LOCAL_US_PARQUET_DIR"] = str(parquet_root)

        service = BacktestService(db, owner_id="phase-e-user")
        fixture_df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]),
                "open": [100.0, 101.0, 102.0, 103.0],
                "high": [101.0, 111.0, 108.0, 109.0],
                "low": [99.0, 100.0, 103.0, 104.0],
                "close": [100.0, 105.0, 106.0, 107.0],
                "volume": [1000, 1000, 1000, 1000],
            }
        )

        with patch.object(
            service,
            "_load_history_with_local_us_fallback",
            return_value=(fixture_df, LOCAL_US_PARQUET_SOURCE),
        ):
            stats = service.run_backtest(code="AAPL", force=False, eval_window_days=3, min_age_days=0, limit=10)

        self.assertEqual(stats["saved"], 1)
        with db._phase_e_store.session_scope() as session:
            pg_run = session.query(PhaseEBacktestRun).filter(PhaseEBacktestRun.run_type == "analysis_eval").one()

        usage_rows = db.get_market_data_usage_refs(entity_type="backtest_run", entity_id=int(pg_run.id))
        self.assertEqual(len(usage_rows), 1)
        self.assertEqual(usage_rows[0].usage_role, "primary_bars")
        self.assertEqual(usage_rows[0].detail_json["symbol"], "AAPL")
        self.assertEqual(usage_rows[0].detail_json["resolved_source"], LOCAL_US_PARQUET_SOURCE)
        self.assertIsNotNone(db.get_market_data_manifest("us.local_parquet.daily"))

    def test_phase_e_shadows_rule_backtest_lifecycle_and_persists_comparison_as_artifact(self) -> None:
        db = self._db()
        self._create_user()
        self._seed_rule_backtest_prices()

        service = RuleBacktestService(db, owner_id="phase-e-user")
        strategy_text = "Buy when Close > MA3. Sell when Close < MA3."

        with patch.object(service, "_get_llm_adapter", return_value=None):
            submitted = service.submit_backtest(
                code="600519",
                strategy_text=strategy_text,
                start_date="2024-01-08",
                end_date="2024-01-18",
                lookback_bars=20,
                confirmed=True,
            )
            with db._phase_e_store.session_scope() as session:
                queued_row = (
                    session.query(PhaseEBacktestRun)
                    .filter(
                        PhaseEBacktestRun.id
                        == phase_e_shadow_run_id("rule_deterministic", int(submitted["id"]))
                    )
                    .one()
                )
                queued_artifacts = (
                    session.query(PhaseEBacktestArtifact)
                    .filter(PhaseEBacktestArtifact.backtest_run_id == queued_row.id)
                    .order_by(PhaseEBacktestArtifact.artifact_kind.asc())
                    .all()
                )
            self.assertIn(queued_row.status, {"parsing", "queued"})
            self.assertEqual([item.artifact_kind for item in queued_artifacts], ["summary"])

            service.process_submitted_run(submitted["id"])

        detail = service.get_run(submitted["id"])
        assert detail is not None

        with db.get_session() as session:
            sqlite_run = session.query(RuleBacktestRun).filter(RuleBacktestRun.id == int(submitted["id"])).one()
            sqlite_trade_count = session.query(RuleBacktestTrade).filter(RuleBacktestTrade.run_id == sqlite_run.id).count()
        self.assertGreater(sqlite_trade_count, 0)

        with db._phase_e_store.session_scope() as session:
            pg_run = (
                session.query(PhaseEBacktestRun)
                .filter(
                    PhaseEBacktestRun.id
                    == phase_e_shadow_run_id("rule_deterministic", int(submitted["id"]))
                )
                .one()
            )
            pg_artifacts = (
                session.query(PhaseEBacktestArtifact)
                .filter(PhaseEBacktestArtifact.backtest_run_id == pg_run.id)
                .order_by(PhaseEBacktestArtifact.artifact_kind.asc())
                .all()
            )

        self.assertEqual(pg_run.run_type, "rule_deterministic")
        self.assertEqual(pg_run.owner_user_id, "phase-e-user")
        self.assertEqual(pg_run.status, "completed")
        self.assertEqual(pg_run.request_payload["legacy_run_id"], int(submitted["id"]))
        self.assertEqual(
            [item.artifact_kind for item in pg_artifacts],
            ["audit_rows", "comparison", "equity_curve", "execution_trace", "summary", "trade_events"],
        )
        comparison_artifact = next(item for item in pg_artifacts if item.artifact_kind == "comparison")
        trade_events_artifact = next(item for item in pg_artifacts if item.artifact_kind == "trade_events")
        self.assertEqual(comparison_artifact.payload_json["benchmark_summary"], detail["benchmark_summary"])
        self.assertEqual(comparison_artifact.payload_json["buy_and_hold_summary"], detail["buy_and_hold_summary"])
        self.assertEqual(
            comparison_artifact.payload_json["metrics"]["benchmark_return_pct"],
            detail["benchmark_return_pct"],
        )
        self.assertEqual(len(trade_events_artifact.payload_json["trades"]), sqlite_trade_count)

    def test_phase_e_factory_reset_clears_backtest_shadow_rows(self) -> None:
        db = self._db()
        self._create_user()
        self._seed_historical_eval_fixture(owner_id="phase-e-user")
        self._seed_rule_backtest_prices(code="000001")

        BacktestService(db, owner_id="phase-e-user").run_backtest(
            code="600519",
            force=False,
            eval_window_days=3,
            min_age_days=0,
            limit=10,
        )
        rule_service = RuleBacktestService(db, owner_id="phase-e-user")
        with patch.object(rule_service, "_get_llm_adapter", return_value=None):
            rule_service.parse_and_run(
                code="000001",
                strategy_text="Buy when Close > MA3. Sell when Close < MA3.",
                lookback_bars=20,
                confirmed=True,
            )

        result = db.factory_reset_non_bootstrap_state()

        self.assertIn("backtest_runs", result["cleared"])
        with db._phase_e_store.session_scope() as session:
            self.assertEqual(session.query(PhaseEBacktestArtifact).count(), 0)
            self.assertEqual(session.query(PhaseEBacktestRun).count(), 0)


def json_dumps(payload) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
