import contextlib
import io
import runpy
import subprocess
import sys
import unittest
from builtins import __import__ as builtin_import
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


class WS7CleanupTestCase(unittest.TestCase):
    @staticmethod
    def _guard_legacy_root_backtest_imports(name, globals=None, locals=None, fromlist=(), level=0):
        if name in {"test_backtest_basic", "test_backtest_rule"}:
            raise ModuleNotFoundError(f"legacy root smoke module blocked in WS7 test: {name}")
        return builtin_import(name, globals, locals, fromlist, level)

    def test_standard_smoke_script_loads_without_legacy_root_helpers(self) -> None:
        with patch("builtins.__import__", side_effect=self._guard_legacy_root_backtest_imports):
            namespace = runpy.run_path(
                str(REPO_ROOT / "scripts" / "smoke_backtest_standard.py"),
                run_name="ws7_standard_smoke_script",
            )

        self.assertTrue(callable(namespace.get("main")))

    def test_rule_smoke_script_loads_without_legacy_root_helpers(self) -> None:
        with patch("builtins.__import__", side_effect=self._guard_legacy_root_backtest_imports):
            namespace = runpy.run_path(
                str(REPO_ROOT / "scripts" / "smoke_backtest_rule.py"),
                run_name="ws7_rule_smoke_script",
            )

        self.assertTrue(callable(namespace.get("main")))

    def test_main_help_marks_webui_aliases_as_deprecated(self) -> None:
        completed = subprocess.run(
            [sys.executable, "main.py", "--help"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("--webui", completed.stdout)
        self.assertIn("--webui-only", completed.stdout)
        self.assertIn("已弃用", completed.stdout)
        self.assertIn("--serve", completed.stdout)
        self.assertIn("--serve-only", completed.stdout)

    def test_webui_wrapper_prints_canonical_replacement(self) -> None:
        import uvicorn
        import webui

        stdout_buffer = io.StringIO()
        with (
            patch.object(uvicorn, "run") as run_mock,
            patch("src.config.setup_env"),
            patch("src.logging_config.setup_logging"),
            contextlib.redirect_stdout(stdout_buffer),
        ):
            exit_code = webui.main()

        self.assertEqual(exit_code, 0)
        output = stdout_buffer.getvalue()
        self.assertIn("已弃用", output)
        self.assertIn("python3 main.py --serve-only", output)
        run_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
