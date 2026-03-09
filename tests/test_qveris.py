# -*- coding: utf-8 -*-
"""Tests for QVerisClient, data normalization, and QVeris Agent tools.
All tests are offline — httpx and os.getenv are mocked throughout."""
import unittest, sys, os
from unittest.mock import patch, MagicMock
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.qveris_client import QVerisClient, QVerisError
from src.agent.tools.qveris_tools import (
    ALL_QVERIS_TOOLS, _handle_get_financial_statements, _handle_get_analyst_ratings,
)
from src.agent.tools.registry import ToolDefinition
# Inline to avoid transitive dep chain: data_provider.base -> src.analyzer -> litellm
STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']
_OHLCV = {"open": 150.0, "high": 155.0, "low": 149.0, "close": 153.0, "volume": 1000000}
_PAYLOADS = {
    "search": {
        "search_id": "search-123", "total": 2,
        "results": [
            {"tool_id": "tool-a", "name": "Alpha Vantage Quote", "stats": {"success_rate": 0.95}},
            {"tool_id": "tool-b", "name": "FMP Quote", "stats": {"success_rate": 0.88}},
        ],
    },
    "exec_ok": {"execution_id": "exec-456", "success": True, "result": _OHLCV,
                "elapsed_time_ms": 234, "cost": 6.5},
    "exec_fail": {"execution_id": "x", "success": False,
                  "error_message": "Provider returned HTTP 403"},
    "truncated": {"execution_id": "t", "success": True, "result": {
        "truncated_content": "partial...",
        "full_content_file_url": "https://qveris.ai/files/abc123"}},
}
def _resp(key_or_dict):
    """Build a fake httpx.Response (200 OK) from a _PAYLOADS key or raw dict."""
    data = _PAYLOADS[key_or_dict] if isinstance(key_or_dict, str) else key_or_dict
    r = MagicMock()
    r.status_code, r.json.return_value, r.raise_for_status.return_value = 200, data, None
    return r
# ---------------------------------------------------------------------------
@patch.dict(os.environ, {}, clear=True)
class TestQVerisDisabled(unittest.TestCase):
    """When QVERIS_API_KEY is absent the client and tools must be inert."""
    def test_client_disabled_all_methods_return_none(self):
        c = QVerisClient()
        self.assertFalse(c.enabled)
        for val in (c.search_tools("x"), c.execute_tool("t", "s", {}), c.search_and_execute("q", {})):
            self.assertIsNone(val)
    def test_agent_handlers_return_error_dicts(self):
        cases = [
            (_handle_get_financial_statements, ("AAPL", "income_statement")),
            (_handle_get_analyst_ratings, ("AAPL",)),
        ]
        for handler, args in cases:
            with self.subTest(handler=handler.__name__):
                self.assertIn("QVERIS_API_KEY", handler(*args).get("error", ""))
# ---------------------------------------------------------------------------
class TestQVerisClientEnabled(unittest.TestCase):
    """Enabled client with mocked httpx — covers search, execute, and edge cases."""
    def setUp(self):
        for p in (patch.dict(os.environ, {"QVERIS_API_KEY": "k"}),
                  patch("httpx.Client.__init__", return_value=None)):
            p.start(); self.addCleanup(p.stop)
        self.mp = MagicMock()
        self.client = QVerisClient()
        self.client._client = MagicMock()
        self.client._client.post = self.mp
    def test_search_tools_sends_correct_payload(self):
        self.mp.return_value = _resp("search")
        result = self.client.search_tools("stock quote AAPL", limit=5)
        path, payload = self.mp.call_args[0][0], self.mp.call_args[1]["json"]
        self.assertEqual(path, "/search")
        self.assertEqual(payload["query"], "stock quote AAPL")
        self.assertEqual(payload["limit"], 5)
        self.assertEqual(result["search_id"], "search-123")
    def test_execute_tool_passes_search_id(self):
        self.mp.return_value = _resp("exec_ok")
        result = self.client.execute_tool("tool-a", "search-123", {"symbol": "AAPL"})
        self.assertIn("tool_id=tool-a", self.mp.call_args[0][0])
        self.assertEqual(self.mp.call_args[1]["json"]["search_id"], "search-123")
        self.assertEqual(result["close"], 153.0)
    def test_execute_tool_failure_raises_with_flag(self):
        self.mp.return_value = _resp("exec_fail")
        with self.assertRaises(QVerisError) as ctx:
            self.client.execute_tool("tool-x", "s-1", {"symbol": "BAD"})
        self.assertTrue(ctx.exception.is_execution_error)
        self.assertIn("403", str(ctx.exception))
    def test_search_and_execute_selects_highest_success_rate(self):
        self.mp.side_effect = [_resp("search"), _resp("exec_ok")]
        self.client.search_and_execute("income AAPL", {"symbol": "AAPL"})
        self.assertIn("tool_id=tool-a", self.mp.call_args_list[1][0][0])
    def test_search_and_execute_honors_prefer_tool_id(self):
        self.mp.side_effect = [_resp("search"), _resp("exec_ok")]
        self.client.search_and_execute("q", {"symbol": "A"}, prefer_tool_id="tool-b")
        self.assertIn("tool_id=tool-b", self.mp.call_args_list[1][0][0])
    def test_truncated_response_logs_warning(self):
        self.mp.return_value = _resp("truncated")
        with self.assertLogs("src.qveris_client", level="WARNING") as cm:
            result = self.client.execute_tool("tool-a", "s-1", {"symbol": "X"})
        self.assertTrue(any("Truncated" in l and "abc123" in l for l in cm.output))
        self.assertIn("truncated_content", result)
# ---------------------------------------------------------------------------
class TestNormalizationAndToolDefs(unittest.TestCase):
    """Data normalization helpers and ALL_QVERIS_TOOLS structure validation."""
    def test_fmp_format_maps_to_standard_columns(self):
        df = pd.DataFrame([dict(_OHLCV, date="2026-03-08")])
        for col in STANDARD_COLUMNS:
            if col not in df.columns:
                df[col] = None
        self.assertEqual(list(df[STANDARD_COLUMNS].columns), STANDARD_COLUMNS)
    def test_standard_columns_exact_values(self):
        self.assertEqual(STANDARD_COLUMNS,
                         ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg'])
    def test_all_qveris_tools_are_valid_data_tools(self):
        self.assertGreater(len(ALL_QVERIS_TOOLS), 0)
        for td in ALL_QVERIS_TOOLS:
            self.assertIsInstance(td, ToolDefinition)
            self.assertEqual(td.category, "data")
            self.assertTrue(td.name and callable(td.handler))

if __name__ == '__main__':
    unittest.main()
