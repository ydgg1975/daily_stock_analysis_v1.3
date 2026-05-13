# -*- coding: utf-8 -*-
"""Unit tests for Iwencai market query fetcher mapping (no network)."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from data_provider.iwencai_market_query_fetcher import parse_iwencai_cli_payload
from data_provider.realtime_types import RealtimeSource

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _live_iwencai_enabled() -> bool:
    """Opt-in live API test: RUN_IWENCAI_LIVE=1 plus IWENCAI_API_KEY (from env or .env)."""
    flag = os.environ.get("RUN_IWENCAI_LIVE", "").strip().lower() in ("1", "true", "yes")
    if not flag:
        return False
    if os.environ.get("IWENCAI_API_KEY", "").strip():
        return True
    try:
        from dotenv import load_dotenv

        load_dotenv(_REPO_ROOT / ".env")
    except ImportError:
        return False
    return bool(os.environ.get("IWENCAI_API_KEY", "").strip())


FIXTURE_PAYLOAD = {
    "success": True,
    "query": "600519最新价涨跌幅成交量",
    "code_count": 1,
    "returned_count": 1,
    "page": "1",
    "limit": "2",
    "has_more": False,
    "chunks_info": '["600519最新价涨跌幅成交量 (1)"]',
    "trace_id": "deadbeef" * 8,
    "datas": [
        {
            "股票代码": "600519.SH",
            "股票简称": "贵州茅台",
            "最新价": "1361.33",
            "最新涨跌幅": -0.849241,
            "收盘价[20260511]": 1361.33,
            "涨跌幅[20260511]": -0.849241,
            "成交量[20260511]": 5713510.0,
            "开盘价_前复权[20260511]": 1372.89,
            "最高价_前复权[20260511]": 1372.89,
            "最低价_前复权[20260511]": 1361.0,
            "涨跌_前复权[20260511]": -11.66,
            "成交额[20260511]": 7790721390.0,
            "振幅[20260511]": 0.865993,
            "换手率[20260511]": 0.456252,
        }
    ],
}


class TestParseIwencaiCliPayload(unittest.TestCase):
    def test_maps_to_unified_quote(self):
        q = parse_iwencai_cli_payload(FIXTURE_PAYLOAD, "600519")
        self.assertIsNotNone(q)
        assert q is not None
        self.assertEqual(q.code, "600519")
        self.assertEqual(q.name, "贵州茅台")
        self.assertAlmostEqual(q.price or 0, 1361.33, places=2)
        self.assertEqual(q.source, RealtimeSource.IWENCAI_MARKET_QUERY)
        self.assertTrue(q.has_basic_data())
        self.assertEqual(q.volume, 5713510)
        self.assertAlmostEqual(q.amount or 0, 7790721390.0, delta=1.0)
        self.assertIsNotNone(q.pre_close)

    def test_picks_matching_row(self):
        payload = {
            "success": True,
            "datas": [
                {"股票代码": "000001.SZ", "股票简称": "平安银行", "最新价": "10"},
                {"股票代码": "600519.SH", "股票简称": "贵州茅台", "最新价": "100"},
            ],
        }
        q = parse_iwencai_cli_payload(payload, "600519")
        self.assertIsNotNone(q)
        assert q is not None
        self.assertEqual(q.name, "贵州茅台")

    def test_invalid_payload_returns_none(self):
        self.assertIsNone(parse_iwencai_cli_payload({"success": False}, "600519"))
        self.assertIsNone(parse_iwencai_cli_payload({"success": True, "datas": []}, "600519"))

    def test_numeric_stock_code_cell(self):
        payload = {
            "success": True,
            "datas": [{"股票代码": 600519, "股票简称": "贵州茅台", "最新价": "99.5"}],
        }
        q = parse_iwencai_cli_payload(payload, "600519")
        self.assertIsNotNone(q)
        assert q is not None
        self.assertEqual(q.code, "600519")
        self.assertAlmostEqual(q.price or 0, 99.5, places=2)


@patch("data_provider.iwencai_market_query_fetcher.subprocess.run")
class TestIwencaiFetcherSubprocess(unittest.TestCase):
    def test_get_realtime_quote_parses_stdout(self, mock_run: MagicMock):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(FIXTURE_PAYLOAD, ensure_ascii=False)
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        fd, cli_path = tempfile.mkstemp(suffix="_cli.py", text=True)
        os.write(fd, b"# placeholder\n")
        os.close(fd)
        try:
            cfg = MagicMock()
            cfg.iwencai_market_query_enabled = True
            cfg.iwencai_cli_path = cli_path
            cfg.iwencai_market_query_template = "{code}最新价"
            cfg.iwencai_subprocess_timeout_sec = 30

            with patch.dict(os.environ, {"IWENCAI_API_KEY": "test-key"}, clear=False):
                with patch("src.config.get_config", return_value=cfg):
                    from data_provider.iwencai_market_query_fetcher import IwencaiMarketQueryFetcher

                    f = IwencaiMarketQueryFetcher()
                    q = f.get_realtime_quote("600519")
            self.assertIsNotNone(q)
            assert q is not None
            self.assertEqual(q.code, "600519")
            mock_run.assert_called_once()
        finally:
            os.unlink(cli_path)

    def test_get_realtime_quote_accepts_indented_cli_json(self, mock_run: MagicMock):
        """cli.py prints json.dumps(..., indent=2); loads must accept newlines."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(FIXTURE_PAYLOAD, ensure_ascii=False, indent=2)
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        fd, cli_path = tempfile.mkstemp(suffix="_cli.py", text=True)
        os.write(fd, b"# placeholder\n")
        os.close(fd)
        try:
            cfg = MagicMock()
            cfg.iwencai_market_query_enabled = True
            cfg.iwencai_cli_path = cli_path
            cfg.iwencai_market_query_template = "{code}最新价"
            cfg.iwencai_subprocess_timeout_sec = 30

            with patch.dict(os.environ, {"IWENCAI_API_KEY": "test-key"}, clear=False):
                with patch("src.config.get_config", return_value=cfg):
                    from data_provider.iwencai_market_query_fetcher import IwencaiMarketQueryFetcher

                    f = IwencaiMarketQueryFetcher()
                    q = f.get_realtime_quote("600519")
            self.assertIsNotNone(q)
            assert q is not None
            self.assertTrue(q.has_basic_data())
        finally:
            os.unlink(cli_path)


@pytest.mark.network
@unittest.skipUnless(
    _live_iwencai_enabled(),
    "Set RUN_IWENCAI_LIVE=1 and IWENCAI_API_KEY (e.g. in .env) for live iWencai E2E",
)
class TestIwencaiLiveCLI(unittest.TestCase):
    """Hits openapi.iwencai.com via skills/hithink-market-query/scripts/cli.py."""

    _saved_env: dict

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from dotenv import load_dotenv

            load_dotenv(_REPO_ROOT / ".env")
        except ImportError:
            pass
        cls._saved_env = {}
        for key in ("IWENCAI_MARKET_QUERY_ENABLED", "REALTIME_SOURCE_PRIORITY"):
            cls._saved_env[key] = os.environ.get(key)
        os.environ["IWENCAI_MARKET_QUERY_ENABLED"] = "true"
        os.environ["REALTIME_SOURCE_PRIORITY"] = "iwencai_market"

    @classmethod
    def tearDownClass(cls) -> None:
        for key, val in cls._saved_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        from src.config import Config

        Config.reset_instance()

    def setUp(self) -> None:
        from src.config import Config

        Config.reset_instance()

    def tearDown(self) -> None:
        from src.config import Config

        Config.reset_instance()

    def test_cli_stdout_parses_to_quote(self) -> None:
        import subprocess
        import sys

        cli = _REPO_ROOT / "skills" / "hithink-market-query" / "scripts" / "cli.py"
        self.assertTrue(cli.is_file(), "skills/hithink-market-query/scripts/cli.py missing")
        cwd = str(cli.parent.parent)
        query = "600519最新价涨跌幅成交量换手率"
        cmd = [
            sys.executable,
            str(cli),
            "--query",
            query,
            "--limit",
            "8",
            "--timeout",
            "45",
        ]
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=90,
            env=os.environ.copy(),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr[:500] if proc.stderr else proc.stdout[:500])
        payload = json.loads((proc.stdout or "").strip())
        q = parse_iwencai_cli_payload(payload, "600519")
        self.assertIsNotNone(q, msg=json.dumps(payload, ensure_ascii=False)[:800])
        assert q is not None
        self.assertEqual(q.code, "600519")
        self.assertTrue(q.has_basic_data())
        self.assertGreater(q.price or 0, 0)
        self.assertEqual(q.source, RealtimeSource.IWENCAI_MARKET_QUERY)

    def test_data_fetcher_manager_prefers_iwencai(self) -> None:
        from data_provider.base import DataFetcherManager

        mgr = DataFetcherManager()
        q = mgr.get_realtime_quote("600519")
        self.assertIsNotNone(q)
        assert q is not None
        self.assertEqual(q.source, RealtimeSource.IWENCAI_MARKET_QUERY)
        self.assertTrue(q.has_basic_data())
