import os
import tempfile
import unittest
from pathlib import Path

from src.utils.dotenv_loader import load_dotenv_file, read_dotenv_values


class DotenvLoaderTestCase(unittest.TestCase):
    def test_read_dotenv_values_ignores_shell_source_prelude(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "source /Users/example/project/.env.shared\n"
                "ADMIN_AUTH_ENABLED=true\n"
                "OPENAI_API_KEY=test-key\n",
                encoding="utf-8",
            )

            values = read_dotenv_values(env_path)

            self.assertEqual(values.get("ADMIN_AUTH_ENABLED"), "true")
            self.assertEqual(values.get("OPENAI_API_KEY"), "test-key")

    def test_load_dotenv_file_sets_values_without_parse_warning_directive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "source /Users/example/project/.env.shared\n"
                "BACKTEST_ENABLED=true\n",
                encoding="utf-8",
            )

            previous = os.environ.get("BACKTEST_ENABLED")
            try:
                os.environ.pop("BACKTEST_ENABLED", None)
                load_dotenv_file(env_path, override=True)
                self.assertEqual(os.environ.get("BACKTEST_ENABLED"), "true")
            finally:
                if previous is None:
                    os.environ.pop("BACKTEST_ENABLED", None)
                else:
                    os.environ["BACKTEST_ENABLED"] = previous


if __name__ == "__main__":
    unittest.main()
