import json
import tempfile
import unittest
from pathlib import Path

from src.services.shared_runtime_service import SharedRuntimeService


class SharedRuntimeServiceTestCase(unittest.TestCase):
    def test_export_object_writes_stable_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = SharedRuntimeService(output_dir=Path(temp_dir))

            output_path = service.export_object(
                object_name="portfolio_state",
                schema_version="1.0",
                data={"portfolio_id": "default", "cash": 1000.0},
            )

            self.assertTrue(output_path.exists())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["object_name"], "portfolio_state")
            self.assertEqual(payload["schema_version"], "1.0")
            self.assertIn("generated_at", payload)
            self.assertEqual(payload["data"]["portfolio_id"], "default")
            self.assertEqual(payload["data"]["cash"], 1000.0)


if __name__ == "__main__":
    unittest.main()
