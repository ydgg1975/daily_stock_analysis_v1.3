# -*- coding: utf-8 -*-
"""Focused coverage for the PostgreSQL Phase G control-plane baseline."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from api.v1.endpoints import auth as auth_endpoint
from src.config import Config
from src.core.config_manager import ConfigManager
from src.multi_user import BOOTSTRAP_ADMIN_USER_ID
from src.postgres_phase_g import (
    PhaseGAdminLog,
    PhaseGProviderConfig,
    PhaseGSystemAction,
    PhaseGSystemConfig,
)
from src.services.execution_log_service import ExecutionLogService
from src.services.system_config_service import SystemConfigService
from src.storage import DatabaseManager


class PostgresPhaseGStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.sqlite_db_path = self.data_dir / "legacy.sqlite"
        self.phase_db_path = self.data_dir / "phase-baseline.sqlite"
        self._configure_environment()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        os.environ.pop("POSTGRES_PHASE_A_URL", None)
        os.environ.pop("POSTGRES_PHASE_A_APPLY_SCHEMA", None)
        self.temp_dir.cleanup()

    def _configure_environment(self) -> None:
        lines = [
            "STOCK_LIST=600519,000001",
            "GEMINI_API_KEY=secret-key-value",
            "GEMINI_MODEL=gemini-2.5-pro",
            "SCHEDULE_TIME=18:00",
            "LOG_LEVEL=INFO",
            f"DATABASE_PATH={self.sqlite_db_path}",
            f"POSTGRES_PHASE_A_URL=sqlite:///{self.phase_db_path}",
            "POSTGRES_PHASE_A_APPLY_SCHEMA=true",
        ]
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.sqlite_db_path)
        os.environ["POSTGRES_PHASE_A_URL"] = f"sqlite:///{self.phase_db_path}"
        os.environ["POSTGRES_PHASE_A_APPLY_SCHEMA"] = "true"
        Config.reset_instance()
        DatabaseManager.reset_instance()

    def _db(self) -> DatabaseManager:
        return DatabaseManager.get_instance()

    def _service(self) -> SystemConfigService:
        return SystemConfigService(manager=ConfigManager(env_path=self.env_path))

    @staticmethod
    def _request_with_service(service: SystemConfigService) -> SimpleNamespace:
        return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(system_config_service=service)))

    def test_phase_g_shadows_provider_and_system_config_without_changing_env_reads(self) -> None:
        db = self._db()
        db.ensure_bootstrap_admin_user()
        service = self._service()

        payload = service.get_config(include_schema=False)

        with db._phase_g_store.session_scope() as session:
            gemini = (
                session.query(PhaseGProviderConfig)
                .filter(PhaseGProviderConfig.provider_key == "gemini")
                .one()
            )
            stock_list = (
                session.query(PhaseGSystemConfig)
                .filter(PhaseGSystemConfig.config_key == "STOCK_LIST")
                .one()
            )
            schedule_time = (
                session.query(PhaseGSystemConfig)
                .filter(PhaseGSystemConfig.config_key == "SCHEDULE_TIME")
                .one()
            )

        self.assertEqual(gemini.config_scope, "system")
        self.assertEqual(gemini.auth_mode, "api_key")
        self.assertEqual(gemini.config_json["GEMINI_MODEL"], "gemini-2.5-pro")
        self.assertEqual(gemini.secret_json["GEMINI_API_KEY"], "secret-key-value")
        self.assertEqual(stock_list.value_type, "array")
        self.assertEqual(stock_list.value_json, ["600519", "000001"])
        self.assertEqual(schedule_time.value_json, "18:00")

        items = {item["key"]: item["value"] for item in payload["items"]}
        self.assertEqual(items["GEMINI_API_KEY"], "secret-key-value")
        self.assertEqual(items["SCHEDULE_TIME"], "18:00")

    def test_phase_g_update_refreshes_shadow_rows_and_preserves_actor_attribution(self) -> None:
        db = self._db()
        db.ensure_bootstrap_admin_user()
        service = self._service()
        service.get_config(include_schema=False)

        response = service.update(
            config_version=service._manager.get_config_version(),
            items=[
                {"key": "GEMINI_API_KEY", "value": "new-secret"},
                {"key": "SCHEDULE_TIME", "value": "19:30"},
            ],
            reload_now=False,
            actor_user_id=BOOTSTRAP_ADMIN_USER_ID,
        )

        self.assertTrue(response["success"])
        with db._phase_g_store.session_scope() as session:
            gemini = (
                session.query(PhaseGProviderConfig)
                .filter(PhaseGProviderConfig.provider_key == "gemini")
                .one()
            )
            schedule_time = (
                session.query(PhaseGSystemConfig)
                .filter(PhaseGSystemConfig.config_key == "SCHEDULE_TIME")
                .one()
            )

        self.assertEqual(gemini.secret_json["GEMINI_API_KEY"], "new-secret")
        self.assertEqual(gemini.rotation_version, 2)
        self.assertEqual(gemini.updated_by_user_id, BOOTSTRAP_ADMIN_USER_ID)
        self.assertEqual(schedule_time.value_json, "19:30")
        self.assertEqual(schedule_time.updated_by_user_id, BOOTSTRAP_ADMIN_USER_ID)

    def test_phase_g_admin_logs_remain_global_across_admin_actors(self) -> None:
        db = self._db()
        db.create_or_update_app_user(user_id=BOOTSTRAP_ADMIN_USER_ID, username="admin", role="admin")
        db.create_or_update_app_user(user_id="admin-2", username="admin-2", role="admin")

        service = ExecutionLogService()
        first_session_id = service.record_admin_action(
            action="reset_runtime_caches",
            message="Runtime caches reset",
            actor={"user_id": BOOTSTRAP_ADMIN_USER_ID, "username": "admin", "role": "admin"},
            subsystem="system_control",
            destructive=False,
            detail={"cleared": ["search_service"]},
        )
        second_session_id = service.record_admin_action(
            action="rotate_provider_key",
            message="Provider key rotated",
            actor={"user_id": "admin-2", "username": "admin-2", "role": "admin"},
            subsystem="system_control",
            destructive=True,
            detail={"provider": "gemini"},
        )

        logs = db.list_phase_g_admin_logs(limit=10)
        actions = db.list_phase_g_system_actions(limit=10)

        self.assertEqual({row["related_session_key"] for row in logs}, {first_session_id, second_session_id})
        self.assertEqual({row["actor_user_id"] for row in logs}, {BOOTSTRAP_ADMIN_USER_ID, "admin-2"})
        self.assertEqual({row["scope"] for row in logs}, {"system"})
        self.assertEqual(len(actions), 2)
        self.assertEqual({row["actor_user_id"] for row in actions}, {BOOTSTRAP_ADMIN_USER_ID, "admin-2"})

    def test_phase_g_factory_reset_records_destructive_system_action_auditability(self) -> None:
        db = self._db()
        db.ensure_bootstrap_admin_user()
        service = self._service()

        response = service.factory_reset_system(
            confirmation_phrase="FACTORY RESET",
            actor_user_id=BOOTSTRAP_ADMIN_USER_ID,
            actor_display_name="Bootstrap Admin",
        )

        self.assertTrue(response["success"])
        with db._phase_g_store.session_scope() as session:
            admin_log = session.query(PhaseGAdminLog).order_by(PhaseGAdminLog.id.desc()).first()
            system_action = session.query(PhaseGSystemAction).order_by(PhaseGSystemAction.id.desc()).first()

        self.assertIsNotNone(admin_log)
        self.assertIsNotNone(system_action)
        self.assertEqual(admin_log.event_type, "factory_reset_system")
        self.assertEqual(admin_log.actor_user_id, BOOTSTRAP_ADMIN_USER_ID)
        self.assertEqual(system_action.action_key, "factory_reset_system")
        self.assertTrue(system_action.destructive)
        self.assertEqual(system_action.status, "completed")
        self.assertEqual(system_action.request_json["confirmation_phrase"], "FACTORY RESET")
        self.assertIn("cleared", system_action.result_json)

    def test_phase_g_factory_reset_preserves_system_rows_while_nulling_deleted_user_refs(self) -> None:
        db = self._db()
        db.ensure_bootstrap_admin_user()
        db.create_or_update_app_user(user_id="admin-2", username="admin-2", role="admin")
        service = self._service()

        service.get_config(include_schema=False)
        service.update(
            config_version=service._manager.get_config_version(),
            items=[{"key": "SCHEDULE_TIME", "value": "19:15"}],
            reload_now=False,
            actor_user_id="admin-2",
        )
        ExecutionLogService().record_admin_action(
            action="rotate_provider_key",
            message="Provider key rotated",
            actor={"user_id": "admin-2", "username": "admin-2", "role": "admin"},
            subsystem="system_control",
            destructive=True,
            detail={"provider": "gemini"},
        )

        result = db.factory_reset_non_bootstrap_state()

        self.assertIn("app_users", result["cleared"])
        self.assertIsNone(db.get_app_user("admin-2"))
        with db._phase_g_store.session_scope() as session:
            schedule_time = (
                session.query(PhaseGSystemConfig)
                .filter(PhaseGSystemConfig.config_key == "SCHEDULE_TIME")
                .one()
            )
            admin_log = session.query(PhaseGAdminLog).order_by(PhaseGAdminLog.id.desc()).first()
            system_action = session.query(PhaseGSystemAction).order_by(PhaseGSystemAction.id.desc()).first()

        self.assertEqual(schedule_time.value_json, "19:15")
        self.assertIsNone(schedule_time.updated_by_user_id)
        self.assertIsNone(admin_log.actor_user_id)
        self.assertEqual(admin_log.detail_json["actor_user_id"], "admin-2")
        self.assertIsNone(system_action.actor_user_id)
        self.assertEqual(system_action.request_json["actor_user_id"], "admin-2")

    def test_phase_g_auth_toggle_via_shared_service_keeps_pg_shadow_in_sync(self) -> None:
        db = self._db()
        db.ensure_bootstrap_admin_user()
        service = self._service()
        service.get_config(include_schema=False)

        applied = auth_endpoint._apply_auth_enabled(
            True,
            request=self._request_with_service(service),
        )

        self.assertTrue(applied)
        with db._phase_g_store.session_scope() as session:
            row = (
                session.query(PhaseGSystemConfig)
                .filter(PhaseGSystemConfig.config_key == "ADMIN_AUTH_ENABLED")
                .one()
            )
        self.assertEqual(row.value_type, "boolean")
        self.assertEqual(row.value_json, True)

    def test_phase_g_auth_toggle_fallback_keeps_pg_shadow_in_sync(self) -> None:
        db = self._db()
        db.ensure_bootstrap_admin_user()
        service = self._service()
        service.get_config(include_schema=False)

        applied = auth_endpoint._apply_auth_enabled(False, request=None)

        self.assertTrue(applied)
        with db._phase_g_store.session_scope() as session:
            row = (
                session.query(PhaseGSystemConfig)
                .filter(PhaseGSystemConfig.config_key == "ADMIN_AUTH_ENABLED")
                .one()
            )
        self.assertEqual(row.value_type, "boolean")
        self.assertEqual(row.value_json, False)


if __name__ == "__main__":
    unittest.main()
