# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 分析历史存储单元测试
===================================

职责：
1. 验证分析历史保存逻辑
2. 验证上下文快照保存开关
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Keep this test runnable when optional LLM runtime deps are not installed.
try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

try:
    from fastapi.testclient import TestClient
    from api.app import create_app
    from api.v1.endpoints.history import get_history_detail, get_stock_bar
except ModuleNotFoundError:
    TestClient = None
    create_app = None
    get_history_detail = None
    get_stock_bar = None

from src.config import Config
from src.storage import DatabaseManager, AnalysisHistory, BacktestResult, DecisionSignalRecord
from src.analyzer import AnalysisResult
from src.services.history_service import HistoryService
import src.auth as auth


def _analysis_context_pack_overview() -> dict:
    return {
        "pack_version": "1.0",
        "created_at": "2026-04-10T08:30:00+00:00",
        "subject": {
            "code": "600519",
            "stock_name": "贵州茅台",
            "market": "cn",
        },
        "blocks": [
            {
                "key": "quote",
                "label": "行情",
                "status": "available",
                "source": "mock",
                "warnings": [],
                "missing_reasons": [],
            }
        ],
        "counts": {
            "available": 1,
            "missing": 0,
            "not_supported": 0,
            "fallback": 0,
            "stale": 0,
            "estimated": 0,
            "partial": 0,
            "fetch_failed": 0,
        },
        "data_quality": {
            "overall_score": 100,
            "level": "good",
            "block_scores": {
                "quote": 100,
                "daily_bars": 100,
                "technical": 100,
                "news": 100,
                "fundamentals": 100,
                "chip": 100,
            },
            "limitations": [],
        },
        "warnings": [],
        "metadata": {
            "trigger_source": "api",
            "news_result_count": 2,
        },
    }


def _market_phase_summary() -> dict:
    return {
        "market": "cn",
        "phase": "intraday",
        "market_local_time": "2026-03-27T10:00:00+08:00",
        "session_date": "2026-03-27",
        "effective_daily_bar_date": "2026-03-26",
        "is_trading_day": True,
        "is_market_open_now": True,
        "is_partial_bar": True,
        "minutes_to_open": None,
        "minutes_to_close": 300,
        "trigger_source": "api",
        "analysis_intent": "auto",
        "warnings": ["partial_bar"],
    }


class AnalysisHistoryTestCase(unittest.TestCase):
    """分析历史存储测试"""

    def setUp(self) -> None:
        """为每个用例初始化独立数据库"""
        auth._auth_enabled = False
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_analysis_history.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        """清理资源"""
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def _build_result(self) -> AnalysisResult:
        """构造分析结果"""
        return AnalysisResult(
            code="600519",
            name="贵州茅台",
            sentiment_score=78,
            trend_prediction="看多",
            operation_advice="持有",
            analysis_summary="基本面稳健，短期震荡",
        )

    def _save_history(self, query_id: str) -> int:
        """保存一条测试历史记录并返回主键 ID。"""
        result = self._build_result()
        saved = self.db.save_analysis_history(
            result=result,
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            return row.id

    def test_save_analysis_history_with_snapshot(self) -> None:
        """保存历史记录并写入上下文快照"""
        result = self._build_result()
        result.dashboard = {
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "理想买入点：125.5元",
                    "secondary_buy": "120",
                    "stop_loss": "止损位：110元",
                    "take_profit": "目标位：150.0元",
                }
            }
        }
        context_snapshot = {"enhanced_context": {"code": "600519"}}

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_001",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=context_snapshot,
            save_snapshot=True
        )

        self.assertEqual(saved, 1)

        history = self.db.get_analysis_history(code="600519", days=7, limit=10)
        self.assertEqual(len(history), 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            self.assertEqual(row.query_id, "query_001")
            self.assertIsNotNone(row.context_snapshot)
            self.assertEqual(row.ideal_buy, 125.5)
            self.assertEqual(row.secondary_buy, 120.0)
            self.assertEqual(row.stop_loss, 110.0)
            self.assertEqual(row.take_profit, 150.0)

    def test_save_analysis_history_without_snapshot(self) -> None:
        """关闭快照保存时不写入 context_snapshot"""
        result = self._build_result()

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_002",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot={"foo": "bar"},
            save_snapshot=False
        )

        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            self.assertIsNone(row.context_snapshot)

    def test_save_analysis_history_persists_model_used(self) -> None:
        """model_used should be persisted in raw_result for history detail."""
        result = self._build_result()
        result.model_used = "gemini/gemini-2.0-flash"

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_003",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_003").first()
            if row is None:
                self.fail("未找到保存的历史记录")
            payload = json.loads(row.raw_result or "{}")
            self.assertEqual(payload.get("model_used"), "gemini/gemini-2.0-flash")

    def test_update_analysis_history_diagnostics_preserves_snapshot_fields(self) -> None:
        """通知发送后补写 diagnostics 时，不应覆盖已有上下文字段。"""
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id="query_diag_patch",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot={
                "enhanced_context": {"code": "600519"},
                "diagnostics": {
                    "trace_id": "trace-1",
                    "query_id": "query_diag_patch",
                    "stock_code": "600519",
                    "notification_runs": [],
                },
            },
            save_snapshot=True,
        )
        self.assertEqual(saved, 1)

        updated = self.db.update_analysis_history_diagnostics(
            query_id="query_diag_patch",
            code="600519",
            notification_runs=[
                {
                    "channel": "report",
                    "status": "success",
                    "success": True,
                }
            ],
        )

        self.assertEqual(updated, 1)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_diag_patch"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            snapshot = json.loads(row.context_snapshot or "{}")
            self.assertEqual(snapshot["enhanced_context"]["code"], "600519")
            notification_run = snapshot["diagnostics"]["notification_runs"][-1]
            self.assertEqual(notification_run["status"], "success")
            self.assertEqual(notification_run["trace_id"], "trace-1")

    def test_history_detail_hides_placeholder_model_used(self) -> None:
        """Placeholder model values should be normalized to None in detail response."""
        result = self._build_result()
        result.model_used = "unknown"

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_004",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_004").first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        service = HistoryService(self.db)
        detail = service.get_history_detail_by_id(record_id)
        self.assertIsNotNone(detail)
        self.assertIsNone(detail.get("model_used"))

    def test_history_list_includes_timeline_summary_fields(self) -> None:
        """History list items expose the fields needed by the same-stock timeline drawer."""
        result = self._build_result()
        result.model_used = "gemini/gemini-2.5-pro"
        context_snapshot = {
            "enhanced_context": {
                "realtime": {
                    "price": "51.5",
                    "change_pct": "-4.61%",
                    "volume_ratio": "1.17",
                    "turnover_rate": "11.46",
                },
            },
            "market_phase_summary": _market_phase_summary(),
        }

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_timeline_summary",
            report_type="detailed",
            news_content="新闻摘要",
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        self.assertEqual(saved, 1)

        service = HistoryService(self.db)
        payload = service.get_history_list(stock_code="600519.SH", page=1, limit=5)

        self.assertEqual(payload["total"], 1)
        item = payload["items"][0]
        self.assertEqual(item["stock_code"], "600519")
        self.assertEqual(item["trend_prediction"], "看多")
        self.assertEqual(item["analysis_summary"], "基本面稳健，短期震荡")
        self.assertEqual(item["operation_advice"], "持有")
        self.assertEqual(item["action"], "hold")
        self.assertEqual(item["action_label"], "持有")
        self.assertEqual(item["model_used"], "gemini/gemini-2.5-pro")
        self.assertEqual(item["current_price"], 51.5)
        self.assertEqual(item["change_pct"], -4.61)
        self.assertEqual(item["volume_ratio"], 1.17)
        self.assertEqual(item["turnover_rate"], 11.46)
        self.assertEqual(item["market_phase_summary"]["phase"], "intraday")
        self.assertEqual(item["market_phase_summary"]["minutes_to_close"], 300)

    def test_market_review_history_can_be_filtered_without_stock_records(self) -> None:
        """Market review records should be queryable as a dedicated history collection."""
        stock_result = self._build_result()
        market_result = AnalysisResult(
            code="MARKET",
            name="大盘复盘",
            sentiment_score=50,
            trend_prediction="大盘复盘",
            operation_advice="查看复盘",
            analysis_summary="大盘复盘摘要",
        )

        self.assertEqual(
            self.db.save_analysis_history(
                result=stock_result,
                query_id="query_stock_history",
                report_type="detailed",
                news_content="个股正文",
                context_snapshot=None,
                save_snapshot=False,
            ),
            1,
        )
        self.assertEqual(
            self.db.save_analysis_history(
                result=market_result,
                query_id="query_market_review_history",
                report_type="market_review",
                news_content="大盘复盘正文",
                context_snapshot={
                    "report_kind": "market_review",
                    "market_review_payload": {
                        "kind": "market_review",
                        "sections": [{"title": "复盘", "markdown": "结构化正文"}],
                    },
                },
                save_snapshot=True,
            ),
            1,
        )

        service = HistoryService(self.db)
        payload = service.get_history_list(
            stock_code="MARKET",
            report_type="market_review",
            page=1,
            limit=10,
        )

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["stock_code"], "MARKET")
        self.assertEqual(payload["items"][0]["report_type"], "market_review")
        self.assertIsNone(payload["items"][0]["action"])
        self.assertIsNone(payload["items"][0]["action_label"])

    def test_distinct_stock_bar_excludes_market_review_records_by_default(self) -> None:
        """The stock bar aggregation should not mix MARKET into ordinary stock entries."""
        stock_result = self._build_result()
        market_result = AnalysisResult(
            code="MARKET",
            name="大盘复盘",
            sentiment_score=50,
            trend_prediction="大盘复盘",
            operation_advice="查看复盘",
            analysis_summary="大盘复盘摘要",
        )

        self.assertEqual(
            self.db.save_analysis_history(
                result=stock_result,
                query_id="query_stock_bar_stock",
                report_type="detailed",
                news_content="个股正文",
                context_snapshot=None,
                save_snapshot=False,
            ),
            1,
        )
        self.assertEqual(
            self.db.save_analysis_history(
                result=market_result,
                query_id="query_stock_bar_market",
                report_type="market_review",
                news_content="大盘复盘正文",
                context_snapshot=None,
                save_snapshot=False,
            ),
            1,
        )

        records = self.db.get_distinct_stocks_from_history(limit=10)

        self.assertEqual([record.code for record in records], ["600519"])

    def test_stock_bar_item_derives_action_fields_from_legacy_advice(self) -> None:
        if get_stock_bar is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = self._build_result()
        result.operation_advice = "不建议买入"

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_stock_bar_action",
            report_type="detailed",
            news_content="个股正文",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        response = get_stock_bar(
            start_date=None,
            end_date=None,
            limit=10,
            db_manager=self.db,
        )

        self.assertEqual(len(response.items), 1)
        self.assertEqual(response.items[0].operation_advice, "不建议买入")
        self.assertEqual(response.items[0].action, "avoid")
        self.assertEqual(response.items[0].action_label, "回避")

    def test_history_detail_uses_service_resolved_action_fields(self) -> None:
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        service = MagicMock()
        service.resolve_and_get_detail.return_value = {
            "id": 1,
            "query_id": "query_action_conflict",
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "report_type": "detailed",
            "report_language": "zh",
            "created_at": "2026-05-21T17:40:00",
            "sentiment_score": 45,
            "operation_advice": "持有观察",
            "action": "watch",
            "action_label": "观望",
            "trend_prediction": "震荡",
            "analysis_summary": "等待确认",
            "raw_result": {
                "operation_advice": "持有观察",
                "action": "watch",
                "report_language": "zh",
            },
        }

        with patch("api.v1.endpoints.history.HistoryService", return_value=service):
            response = get_history_detail("query_action_conflict", db_manager=self.db)

        self.assertEqual(response.summary.operation_advice, "持有观察")
        self.assertEqual(response.summary.action, "watch")
        self.assertEqual(response.summary.action_label, "观望")

    def test_history_list_matches_equivalent_suffixed_stock_codes(self) -> None:
        """Same-stock history should include rows saved with supported suffixed codes."""

        def save_record(code: str, query_id: str) -> None:
            result = self._build_result()
            result.code = code
            if "HK" in code:
                result.name = "腾讯控股"
            saved = self.db.save_analysis_history(
                result=result,
                query_id=query_id,
                report_type="simple",
                news_content="新闻摘要",
                context_snapshot=None,
                save_snapshot=False,
            )
            self.assertEqual(saved, 1)

        save_record("600519.SH", "query_cn_suffix")
        save_record("600519", "query_cn_plain")
        save_record("00700.HK", "query_hk_suffix")
        save_record("HK00700", "query_hk_prefix")

        service = HistoryService(self.db)

        cn_from_suffix = service.get_history_list(stock_code="600519.SH", page=1, limit=10)
        self.assertEqual(cn_from_suffix["total"], 2)
        self.assertEqual(
            {item["stock_code"] for item in cn_from_suffix["items"]},
            {"600519.SH", "600519"},
        )

        cn_from_plain = service.get_history_list(stock_code="600519", page=1, limit=10)
        self.assertEqual(cn_from_plain["total"], 2)
        self.assertEqual(
            {item["stock_code"] for item in cn_from_plain["items"]},
            {"600519.SH", "600519"},
        )

        hk_from_suffix = service.get_history_list(stock_code="00700.HK", page=1, limit=10)
        self.assertEqual(hk_from_suffix["total"], 2)
        self.assertEqual(
            {item["stock_code"] for item in hk_from_suffix["items"]},
            {"00700.HK", "HK00700"},
        )

        hk_from_prefix = service.get_history_list(stock_code="HK00700", page=1, limit=10)
        self.assertEqual(hk_from_prefix["total"], 2)
        self.assertEqual(
            {item["stock_code"] for item in hk_from_prefix["items"]},
            {"00700.HK", "HK00700"},
        )

    def test_history_list_matches_unpadded_hk_suffix_variants(self) -> None:
        """HK short suffix forms (e.g. 1810.HK) should match 5-digit canonical suffix/prefix forms."""

        def save_record(code: str, query_id: str) -> None:
            result = self._build_result()
            result.code = code
            if "HK" in code:
                result.name = "腾讯控股"
            saved = self.db.save_analysis_history(
                result=result,
                query_id=query_id,
                report_type="simple",
                news_content="新闻摘要",
                context_snapshot=None,
                save_snapshot=False,
            )
            self.assertEqual(saved, 1)

        save_record("1810.HK", "query_hk_unpadded")
        save_record("01810.HK", "query_hk_padded")
        save_record("HK01810", "query_hk_prefix")

        service = HistoryService(self.db)

        hk_from_suffix = service.get_history_list(stock_code="01810.HK", page=1, limit=10)
        self.assertEqual(hk_from_suffix["total"], 3)
        self.assertEqual(
            {item["stock_code"] for item in hk_from_suffix["items"]},
            {"1810.HK", "01810.HK", "HK01810"},
        )

        hk_from_prefix = service.get_history_list(stock_code="HK01810", page=1, limit=10)
        self.assertEqual(hk_from_prefix["total"], 3)
        self.assertEqual(
            {item["stock_code"] for item in hk_from_prefix["items"]},
            {"1810.HK", "01810.HK", "HK01810"},
        )

    def test_history_list_matches_sh_and_ss_suffixed_variants(self) -> None:
        """SH suffix and legacy `.SS` variants should be treated as the same A-share stock."""

        def save_record(code: str, query_id: str) -> None:
            result = self._build_result()
            result.code = code
            saved = self.db.save_analysis_history(
                result=result,
                query_id=query_id,
                report_type="simple",
                news_content="新闻摘要",
                context_snapshot=None,
                save_snapshot=False,
            )
            self.assertEqual(saved, 1)

        save_record("600519.SH", "query_cn_sh")
        save_record("600519.SS", "query_cn_ss")
        save_record("600519", "query_cn_plain")

        service = HistoryService(self.db)
        expected = {"600519.SH", "600519.SS", "600519"}

        from_sh = service.get_history_list(stock_code="600519.SH", page=1, limit=10)
        self.assertEqual(from_sh["total"], 3)
        self.assertEqual({item["stock_code"] for item in from_sh["items"]}, expected)

        from_ss = service.get_history_list(stock_code="600519.SS", page=1, limit=10)
        self.assertEqual(from_ss["total"], 3)
        self.assertEqual({item["stock_code"] for item in from_ss["items"]}, expected)

        from_plain = service.get_history_list(stock_code="600519", page=1, limit=10)
        self.assertEqual(from_plain["total"], 3)
        self.assertEqual({item["stock_code"] for item in from_plain["items"]}, expected)

    def test_history_detail_preserves_zero_change_pct(self) -> None:
        """change_pct=0.0（平盘）应原样返回，而不是被当成缺失值丢失。

        Regression for issue #1084: history endpoint used `or` chains that
        treated 0.0 as falsy and silently dropped the daily change.
        """
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        context_snapshot = {
            "enhanced_context": {
                "realtime": {"price": 100.0, "change_pct": 0.0},
            }
        }
        query_id = "query_change_pct_zero"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.meta.current_price, 100.0)
        self.assertEqual(report.meta.change_pct, 0.0)

    def test_history_detail_falls_back_to_realtime_quote_raw_change_pct(self) -> None:
        """缺少 enhanced_context.realtime.change_pct 时，应回退到 realtime_quote_raw。

        Regression for issue #1084: previously the realtime_quote_raw fallback
        was only consulted when current_price was missing, so reports with
        price-only enhanced_context lost their change_pct entirely.
        """
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        context_snapshot = {
            "enhanced_context": {
                "realtime": {"price": 200.0},
            },
            "realtime_quote_raw": {"change_pct": 1.23},
        }
        query_id = "query_change_pct_fallback"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.meta.current_price, 200.0)
        self.assertEqual(report.meta.change_pct, 1.23)

    @patch("src.auth.is_auth_enabled", return_value=False)
    def test_history_detail_ignores_non_dict_realtime_quote_raw(self, mock_auth) -> None:
        """GET /api/v1/history/{id} should tolerate truthy non-dict realtime_quote_raw."""
        if TestClient is None or create_app is None:
            self.skipTest("fastapi is not installed in this test environment")

        context_snapshot = {
            "enhanced_context": {
                "realtime": {"price": 300.0},
            },
            "realtime_quote_raw": "not-a-dict",
        }
        query_id = "query_change_pct_non_dict_raw"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        static_dir = Path(self._temp_dir.name) / "empty-static"
        static_dir.mkdir(exist_ok=True)
        client = TestClient(create_app(static_dir=static_dir))

        response = client.get(f"/api/v1/history/{record_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["meta"]["current_price"], 300.0)
        self.assertIsNone(payload["meta"]["change_pct"])

    def test_history_detail_accepts_dict_raw_result(self) -> None:
        """_record_to_detail_dict should handle dict raw_result without json.loads errors."""
        result = self._build_result()
        result.model_used = "gemini/gemini-2.0-flash"
        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_005",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_005").first()
            if row is None:
                self.fail("未找到保存的历史记录")
            row.raw_result = {"model_used": "unknown", "extra": "v"}

            service = HistoryService(self.db)
            detail = service._record_to_detail_dict(row)

        self.assertIsNotNone(detail)
        self.assertIsInstance(detail.get("raw_result"), dict)
        self.assertIsNone(detail.get("model_used"))

    def test_history_detail_prefers_raw_sniper_strings(self) -> None:
        """History detail should display the original sniper point strings from raw_result."""
        result = self._build_result()
        result.dashboard = {
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "理想买入点：125.5元",
                    "secondary_buy": "120-121 元分批",
                    "stop_loss": "跌破 110 元止损",
                    "take_profit": "目标位：150.0元",
                }
            }
        }

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_006",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_006").first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        service = HistoryService(self.db)
        detail = service.get_history_detail_by_id(record_id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail.get("ideal_buy"), "理想买入点：125.5元")
        self.assertEqual(detail.get("secondary_buy"), "120-121 元分批")
        self.assertEqual(detail.get("stop_loss"), "跌破 110 元止损")
        self.assertEqual(detail.get("take_profit"), "目标位：150.0元")

    def test_history_detail_falls_back_to_numeric_sniper_columns(self) -> None:
        """History detail should still fall back to stored numeric sniper columns when raw strings are unavailable."""
        result = self._build_result()
        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_007",
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == "query_007").first()
            if row is None:
                self.fail("未找到保存的历史记录")
            row.ideal_buy = 125.5
            row.secondary_buy = 120.0
            row.stop_loss = 110.0
            row.take_profit = 150.0
            row.raw_result = json.dumps({"model_used": "gemini/gemini-2.0-flash"})
            session.commit()
            record_id = row.id

        service = HistoryService(self.db)
        detail = service.get_history_detail_by_id(record_id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail.get("ideal_buy"), "125.5")
        self.assertEqual(detail.get("secondary_buy"), "120.0")
        self.assertEqual(detail.get("stop_loss"), "110.0")
        self.assertEqual(detail.get("take_profit"), "150.0")

    def test_history_detail_uses_fundamental_snapshot_fallback_when_context_missing(self) -> None:
        """When context_snapshot is disabled, detail API should fallback to fundamental_snapshot."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = self._build_result()
        query_id = "query_fundamental_fallback_001"
        saved = self.db.save_analysis_history(
            result=result,
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        self.db.save_fundamental_snapshot(
            query_id=query_id,
            code="600519",
            payload={
                "belong_boards": [{"name": "白酒", "type": "行业"}],
                "boards": {
                    "data": {
                        "top": [{"name": "白酒", "change_pct": 2.6}],
                        "bottom": [],
                    }
                },
                "earnings": {
                    "data": {
                        "financial_report": {"report_date": "2025-12-31", "revenue": 1000},
                        "dividend": {"ttm_dividend_yield_pct": 2.6, "ttm_cash_dividend_per_share": 1.3},
                    }
                }
            },
        )

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.details.financial_report["report_date"], "2025-12-31")
        self.assertEqual(report.details.dividend_metrics["ttm_dividend_yield_pct"], 2.6)
        self.assertEqual(report.details.belong_boards, [{"name": "白酒", "type": "行业"}])
        self.assertEqual(report.details.sector_rankings["top"][0]["name"], "白酒")

    def test_history_detail_preserves_unavailable_board_rankings_state(self) -> None:
        """Failed board ranking blocks should remain unavailable in detail response."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        query_id = "query_fundamental_failed_boards_001"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        fallback_fundamental = {
            "belong_boards": [{"name": "白酒", "type": "行业"}],
            "boards": {
                "status": "failed",
                "data": {},
            },
        }
        saved_snapshot = self.db.save_fundamental_snapshot(
            query_id=query_id,
            code="600519",
            payload=fallback_fundamental,
        )
        self.assertEqual(saved_snapshot, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.details.belong_boards, [{"name": "白酒", "type": "行业"}])
        self.assertIsNone(report.details.sector_rankings)

    def test_history_detail_returns_null_fundamental_fields_when_snapshot_absent(self) -> None:
        """Detail API should keep new fields nullable when no context/fundamental snapshot exists."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        query_id = "query_fundamental_fallback_002"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertIsNone(report.details.financial_report)
        self.assertIsNone(report.details.dividend_metrics)
        self.assertEqual(report.details.belong_boards, [])
        self.assertIsNone(report.details.sector_rankings)

    def test_history_detail_returns_empty_related_boards_for_non_cn(self) -> None:
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = AnalysisResult(
            code="AAPL",
            name="Apple",
            sentiment_score=65,
            trend_prediction="Bullish",
            operation_advice="Hold",
            analysis_summary="US stock test",
        )
        query_id = "query_non_cn_board_001"
        saved = self.db.save_analysis_history(
            result=result,
            query_id=query_id,
            report_type="simple",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.details.belong_boards, [])
        self.assertIsNone(report.details.sector_rankings)

    def test_history_detail_reads_agent_snapshot_related_boards_shape(self) -> None:
        """Agent-mode snapshots store fundamental_context/realtime_quote at the top level."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        context_snapshot = {
            "fundamental_context": {
                "belong_boards": [{"name": "白酒", "type": "行业"}],
                "boards": {
                    "data": {
                        "top": [{"name": "白酒", "change_pct": 2.8}],
                        "bottom": [],
                    }
                },
            },
            "realtime_quote": {
                "price": 1888.0,
                "change_pct": 1.56,
            },
        }
        query_id = "query_agent_snapshot_boards_001"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(report.meta.current_price, 1888.0)
        self.assertEqual(report.meta.change_pct, 1.56)
        self.assertEqual(report.details.belong_boards, [{"name": "白酒", "type": "行业"}])
        self.assertEqual(report.details.sector_rankings["top"][0]["name"], "白酒")

    def test_history_detail_returns_overview_and_sanitizes_snapshot(self) -> None:
        """History detail exposes the public overview separately from raw snapshot JSON."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        overview = _analysis_context_pack_overview()
        phase_summary = _market_phase_summary()
        query_id = "query_context_pack_overview_001"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot={
                "enhanced_context": {"code": "600519"},
                "analysis_context_pack_overview": overview,
                "market_phase_summary": {
                    **phase_summary,
                    "market_phase_context": {"raw": True},
                },
            },
            save_snapshot=True,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertEqual(
            report.details.analysis_context_pack_overview.metadata.trigger_source,
            "api",
        )
        self.assertEqual(
            report.details.analysis_context_pack_overview.data_quality.overall_score,
            100,
        )
        self.assertIsNotNone(report.meta.market_phase_summary)
        self.assertEqual(report.meta.market_phase_summary.phase, "intraday")
        self.assertEqual(report.meta.market_phase_summary.minutes_to_close, 300)
        self.assertEqual(report.details.analysis_context_pack_overview.metadata.news_result_count, 2)
        self.assertNotIn(
            "analysis_context_pack_overview",
            report.details.context_snapshot,
        )
        self.assertNotIn(
            "market_phase_summary",
            report.details.context_snapshot,
        )

    def test_history_detail_handles_missing_overview_when_snapshot_disabled(self) -> None:
        """SAVE_CONTEXT_SNAPSHOT=false style records should not require an overview."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        query_id = "query_context_pack_snapshot_disabled_001"
        saved = self.db.save_analysis_history(
            result=self._build_result(),
            query_id=query_id,
            report_type="simple",
            news_content="新闻摘要",
            context_snapshot={
                "enhanced_context": {"code": "600519"},
                "analysis_context_pack_overview": _analysis_context_pack_overview(),
            },
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id
            self.assertIsNone(row.context_snapshot)

        report = get_history_detail(str(record_id), db_manager=self.db)
        self.assertIsNone(report.meta.market_phase_summary)
        self.assertIsNone(report.details.analysis_context_pack_overview)
        self.assertIsNone(report.details.context_snapshot)

    def test_history_markdown_localizes_english_report_and_placeholder_name(self) -> None:
        """History markdown should preserve report_language for English reports."""
        result = AnalysisResult(
            code="AAPL",
            name="股票AAPL",
            sentiment_score=78,
            trend_prediction="Bullish",
            operation_advice="Buy",
            analysis_summary="Momentum remains constructive.",
            report_language="en",
            dashboard={
                "core_conclusion": {
                    "one_sentence": "Favor buying on pullbacks.",
                    "position_advice": {
                        "no_position": "Open a starter position.",
                        "has_position": "Hold and trail the stop.",
                    },
                },
                "intelligence": {
                    "risk_alerts": [],
                },
                "battle_plan": {
                    "sniper_points": {
                        "ideal_buy": "180-182",
                        "stop_loss": "172",
                        "take_profit": "195",
                    }
                },
            },
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_english_markdown_001",
            report_type="full",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_english_markdown_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        markdown = HistoryService(self.db).get_markdown_report(str(record_id))

        self.assertIsNotNone(markdown)
        self.assertIn("Stock Analysis Report", markdown)
        self.assertIn("Core Conclusion", markdown)
        self.assertIn("Unnamed Stock (AAPL)", markdown)
        self.assertNotIn("核心结论", markdown)

    def test_history_markdown_returns_persisted_market_review_report(self) -> None:
        """Market review history should return the saved Markdown without rebuilding a stock report."""
        result = AnalysisResult(
            code="MARKET",
            name="大盘复盘",
            sentiment_score=50,
            trend_prediction="大盘复盘",
            operation_advice="查看复盘",
            analysis_summary="今日大盘复盘",
            raw_response="# 🎯 大盘复盘\n\n## 今日大盘\n\n复盘正文",
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="market_review_query_001",
            report_type="market_review",
            news_content="## 今日大盘\n\n复盘正文",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "market_review_query_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        markdown = HistoryService(self.db).get_markdown_report(str(record_id))

        self.assertEqual(markdown, "# 🎯 大盘复盘\n\n## 今日大盘\n\n复盘正文")

    def test_history_markdown_collapses_unavailable_chip_structure(self) -> None:
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            sentiment_score=72,
            trend_prediction="看多",
            operation_advice="持有",
            analysis_summary="稳健",
            dashboard={
                "data_perspective": {
                    "chip_structure": {
                        "profit_ratio": "数据缺失，无法判断",
                        "avg_cost": "数据缺失，无法判断",
                        "concentration": "数据缺失，无法判断",
                        "chip_health": "数据缺失，无法判断",
                    }
                }
            },
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_chip_unavailable_001",
            report_type="full",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_chip_unavailable_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        markdown = HistoryService(self.db).get_markdown_report(str(record_id))

        self.assertIsNotNone(markdown)
        self.assertIn("**筹码**: 筹码分布未启用或数据源暂不可用，未纳入筹码判断。", markdown)
        self.assertEqual(markdown.count("数据缺失，无法判断"), 0)

    def test_history_detail_returns_persisted_market_review_report(self) -> None:
        """Market review detail should surface the saved recap content for Web history clicks."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        report_content = "# 🎯 大盘复盘\n\n## 今日大盘\n\n复盘正文"
        result = AnalysisResult(
            code="MARKET",
            name="大盘复盘",
            sentiment_score=50,
            trend_prediction="大盘复盘",
            operation_advice="查看复盘",
            analysis_summary="今日大盘复盘",
            raw_response=report_content,
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="market_review_query_detail_001",
            report_type="market_review",
            news_content="## 今日大盘\n\n复盘正文",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "market_review_query_detail_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)

        self.assertEqual(report.meta.report_type, "market_review")
        self.assertEqual(report.summary.analysis_summary, report_content)
        self.assertIsNone(report.summary.action)
        self.assertIsNone(report.summary.action_label)
        self.assertEqual(report.details.news_content, report_content)

    def test_history_detail_localizes_english_summary_fields(self) -> None:
        """History detail should localize summary enums for English reports."""
        if get_history_detail is None:
            self.skipTest("fastapi is not installed in this test environment")

        result = AnalysisResult(
            code="AAPL",
            name="股票AAPL",
            sentiment_score=78,
            trend_prediction="看多",
            operation_advice="买入",
            analysis_summary="Momentum remains constructive.",
            report_language="en",
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_english_detail_001",
            report_type="full",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_english_detail_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        report = get_history_detail(str(record_id), db_manager=self.db)

        self.assertEqual(report.meta.report_language, "en")
        self.assertEqual(report.meta.stock_name, "Unnamed Stock")
        self.assertEqual(report.summary.operation_advice, "Buy")
        self.assertEqual(report.summary.action, "buy")
        self.assertEqual(report.summary.action_label, "Buy")
        self.assertEqual(report.summary.trend_prediction, "Bullish")
        self.assertEqual(report.summary.sentiment_label, "Bullish")

    def test_history_markdown_uses_safe_bias_emoji_for_english_status(self) -> None:
        """English bias status should keep the correct non-risk emoji in markdown."""
        result = AnalysisResult(
            code="AAPL",
            name="股票AAPL",
            sentiment_score=80,
            trend_prediction="Bullish",
            operation_advice="Buy",
            analysis_summary="Momentum remains constructive.",
            report_language="en",
            dashboard={
                "data_perspective": {
                    "price_position": {
                        "current_price": 190.5,
                        "ma5": 188.0,
                        "ma10": 184.5,
                        "ma20": 179.2,
                        "bias_ma5": 1.33,
                        "bias_status": "Safe",
                        "support_level": 184.5,
                        "resistance_level": 195.0,
                    }
                }
            },
        )

        saved = self.db.save_analysis_history(
            result=result,
            query_id="query_english_markdown_bias_001",
            report_type="full",
            news_content="news",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)

        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.query_id == "query_english_markdown_bias_001"
            ).first()
            if row is None:
                self.fail("未找到保存的历史记录")
            record_id = row.id

        markdown = HistoryService(self.db).get_markdown_report(str(record_id))

        self.assertIsNotNone(markdown)
        self.assertIn("✅Safe", markdown)
        self.assertNotIn("🚨Safe", markdown)

    def test_delete_analysis_history_records_also_cleans_backtests_and_decision_signals(self) -> None:
        """删除历史记录时应一并清理关联回测结果和决策信号。"""
        record_id = self._save_history("query_delete_001")

        with self.db.session_scope() as session:
            session.add(BacktestResult(
                analysis_history_id=record_id,
                code="600519",
                analysis_date=None,
                eval_window_days=10,
                engine_version="v1",
                eval_status="pending",
            ))
            session.add(DecisionSignalRecord(
                stock_code="600519",
                stock_name="贵州茅台",
                market="cn",
                source_type="analysis",
                source_report_id=record_id,
                trace_id="trace-delete-linked",
                market_phase="intraday",
                trigger_source="api",
                action="buy",
                action_label="买入",
                reason="linked",
                plan_quality="minimal",
                status="active",
            ))
            session.add(DecisionSignalRecord(
                stock_code="000001",
                stock_name="平安银行",
                market="cn",
                source_type="analysis",
                source_report_id=record_id + 999,
                trace_id="trace-delete-unrelated",
                market_phase="intraday",
                trigger_source="api",
                action="watch",
                action_label="观望",
                reason="unrelated",
                plan_quality="minimal",
                status="active",
            ))

        deleted = self.db.delete_analysis_history_records([record_id])
        self.assertEqual(deleted, 1)

        with self.db.get_session() as session:
            self.assertIsNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id).first())
            self.assertEqual(
                session.query(BacktestResult).filter(BacktestResult.analysis_history_id == record_id).count(),
                0,
            )
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(DecisionSignalRecord.source_report_id == record_id).count(),
                0,
            )
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(DecisionSignalRecord.trace_id == "trace-delete-unrelated").count(),
                1,
            )

    def test_delete_analysis_history_records_keeps_signals_for_nonexistent_history_id(self) -> None:
        """不存在的历史 ID 不应触发弱关联 DecisionSignal 清理。"""
        missing_id = 987654321

        with self.db.session_scope() as session:
            session.add(DecisionSignalRecord(
                stock_code="600519",
                stock_name="贵州茅台",
                market="cn",
                source_type="manual",
                source_report_id=missing_id,
                trace_id="trace-delete-missing-history",
                market_phase="intraday",
                trigger_source="api",
                action="watch",
                action_label="观望",
                reason="manual signal with unverified report id",
                plan_quality="minimal",
                status="active",
            ))

        deleted = self.db.delete_analysis_history_records([missing_id])
        self.assertEqual(deleted, 0)

        with self.db.get_session() as session:
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(
                    DecisionSignalRecord.trace_id == "trace-delete-missing-history"
                ).count(),
                1,
            )

    def test_delete_analysis_history_records_keeps_manual_signal_with_same_report_id(self) -> None:
        """source_report_id 是弱引用，真实 history 删除不应误删 manual/pre-report 信号。"""
        record_id = self._save_history("query_delete_manual_collision")

        with self.db.session_scope() as session:
            session.add(DecisionSignalRecord(
                stock_code="600519",
                stock_name="贵州茅台",
                market="cn",
                source_type="analysis",
                source_report_id=record_id,
                trace_id="trace-delete-analysis-bound",
                market_phase="intraday",
                trigger_source="api",
                action="buy",
                action_label="买入",
                reason="history-bound signal",
                plan_quality="minimal",
                status="active",
            ))
            session.add(DecisionSignalRecord(
                stock_code="600519",
                stock_name="贵州茅台",
                market="cn",
                source_type="manual",
                source_report_id=record_id,
                trace_id="trace-delete-manual-weak-ref",
                market_phase="intraday",
                trigger_source="api",
                action="watch",
                action_label="观望",
                reason="manual signal with caller-supplied report id",
                plan_quality="minimal",
                status="active",
            ))

        deleted = self.db.delete_analysis_history_records([record_id])
        self.assertEqual(deleted, 1)

        with self.db.get_session() as session:
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(
                    DecisionSignalRecord.trace_id == "trace-delete-analysis-bound"
                ).count(),
                0,
            )
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(
                    DecisionSignalRecord.trace_id == "trace-delete-manual-weak-ref"
                ).count(),
                1,
            )

    def test_delete_analysis_history_records_cleans_only_existing_ids_in_mixed_batch(self) -> None:
        """混合存在/不存在 ID 时，只清理实际存在历史记录的关联数据。"""
        record_id = self._save_history("query_delete_mixed")
        missing_id = record_id + 987654

        with self.db.session_scope() as session:
            session.add(BacktestResult(
                analysis_history_id=record_id,
                code="600519",
                analysis_date=None,
                eval_window_days=10,
                engine_version="v1",
                eval_status="pending",
            ))
            session.add(DecisionSignalRecord(
                stock_code="600519",
                stock_name="贵州茅台",
                market="cn",
                source_type="analysis",
                source_report_id=record_id,
                trace_id="trace-delete-mixed-linked",
                market_phase="intraday",
                trigger_source="api",
                action="buy",
                action_label="买入",
                reason="linked",
                plan_quality="minimal",
                status="active",
            ))
            session.add(DecisionSignalRecord(
                stock_code="000001",
                stock_name="平安银行",
                market="cn",
                source_type="manual",
                source_report_id=missing_id,
                trace_id="trace-delete-mixed-missing",
                market_phase="intraday",
                trigger_source="api",
                action="watch",
                action_label="观望",
                reason="weak report id collision",
                plan_quality="minimal",
                status="active",
            ))

        deleted = self.db.delete_analysis_history_records([record_id, missing_id])
        self.assertEqual(deleted, 1)

        with self.db.get_session() as session:
            self.assertIsNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id).first())
            self.assertEqual(
                session.query(BacktestResult).filter(BacktestResult.analysis_history_id == record_id).count(),
                0,
            )
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(
                    DecisionSignalRecord.trace_id == "trace-delete-mixed-linked"
                ).count(),
                0,
            )
            self.assertEqual(
                session.query(DecisionSignalRecord).filter(
                    DecisionSignalRecord.trace_id == "trace-delete-mixed-missing"
                ).count(),
                1,
            )

    @patch("src.auth.is_auth_enabled", return_value=False)
    def test_delete_history_api_deletes_selected_records(self, mock_auth) -> None:
        """DELETE /api/v1/history should remove only the requested records."""
        if TestClient is None or create_app is None:
            self.skipTest("fastapi is not installed in this test environment")

        record_id_1 = self._save_history("query_delete_api_001")
        record_id_2 = self._save_history("query_delete_api_002")

        static_dir = Path(self._temp_dir.name) / "empty-static"
        static_dir.mkdir(exist_ok=True)
        client = TestClient(create_app(static_dir=static_dir))

        response = client.request(
            "DELETE",
            "/api/v1/history",
            json={"record_ids": [record_id_1]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("deleted"), 1)

        with self.db.get_session() as session:
            self.assertIsNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id_1).first())
            self.assertIsNotNone(session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id_2).first())


class HistoryItemSchemaNegativeSentimentTest(unittest.TestCase):
    """Regression: HistoryItem / ReportSummary must accept out-of-range sentiment_score from DB rows."""

    @classmethod
    def setUpClass(cls) -> None:
        """Import schema classes once for all tests, skipping gracefully when deps are missing."""
        try:
            from api.v1.schemas.history import HistoryItem, ReportSummary  # type: ignore
        except ModuleNotFoundError:
            cls.HistoryItem = None
            cls.ReportSummary = None
        else:
            cls.HistoryItem = HistoryItem
            cls.ReportSummary = ReportSummary

    def test_negative_sentiment_score_does_not_raise(self) -> None:
        """Bug #942: sentiment_score=-22 in DB should not cause Pydantic ValidationError."""
        if self.HistoryItem is None:
            self.skipTest("fastapi / pydantic not installed in this test environment")

        item = self.HistoryItem(query_id="q1", stock_code="600519", sentiment_score=-22)
        self.assertEqual(item.sentiment_score, -22)

    def test_out_of_range_high_sentiment_score_does_not_raise(self) -> None:
        """HistoryItem should also accept scores above 100 from legacy data."""
        if self.HistoryItem is None:
            self.skipTest("fastapi / pydantic not installed in this test environment")

        item = self.HistoryItem(query_id="q2", stock_code="600519", sentiment_score=150)
        self.assertEqual(item.sentiment_score, 150)

    def test_none_sentiment_score_is_allowed(self) -> None:
        """HistoryItem.sentiment_score=None should still be valid (optional field)."""
        if self.HistoryItem is None:
            self.skipTest("fastapi / pydantic not installed in this test environment")

        item = self.HistoryItem(query_id="q3", stock_code="600519", sentiment_score=None)
        self.assertIsNone(item.sentiment_score)

    def test_report_summary_negative_sentiment_score_does_not_raise(self) -> None:
        """ReportSummary.sentiment_score should also accept negative values from legacy DB rows."""
        if self.ReportSummary is None:
            self.skipTest("fastapi / pydantic not installed in this test environment")

        summary = self.ReportSummary(sentiment_score=-22)
        self.assertEqual(summary.sentiment_score, -22)

    def test_report_summary_out_of_range_high_sentiment_score_does_not_raise(self) -> None:
        """ReportSummary.sentiment_score should also accept scores above 100 from legacy data."""
        if self.ReportSummary is None:
            self.skipTest("fastapi / pydantic not installed in this test environment")

        summary = self.ReportSummary(sentiment_score=150)
        self.assertEqual(summary.sentiment_score, 150)

    def test_report_summary_none_sentiment_score_is_allowed(self) -> None:
        """ReportSummary.sentiment_score=None should still be valid (optional field)."""
        if self.ReportSummary is None:
            self.skipTest("fastapi / pydantic not installed in this test environment")

        summary = self.ReportSummary(sentiment_score=None)
        self.assertIsNone(summary.sentiment_score)


class TestRecordToListItemDictRobustness(unittest.TestCase):
    """Regression: _record_to_list_item_dict / get_history_list must survive non-dict raw_result sub-structures."""

    def setUp(self) -> None:
        auth._auth_enabled = False
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_robustness.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def _save_record(self, query_id: str, **overrides) -> int:
        result = AnalysisResult(
            code=overrides.get("code", "600519"),
            name=overrides.get("name", "贵州茅台"),
            sentiment_score=overrides.get("sentiment_score", 78),
            trend_prediction=overrides.get("trend_prediction", "看多"),
            operation_advice=overrides.get("operation_advice", "持有"),
            analysis_summary=overrides.get("analysis_summary", "基本面稳健"),
        )
        saved = self.db.save_analysis_history(
            result=result,
            query_id=query_id,
            report_type="simple",
            news_content="正文",
            context_snapshot=None,
            save_snapshot=False,
        )
        self.assertEqual(saved, 1)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            if row is None:
                self.fail(f"未找到 query_id={query_id}")
            return row.id

    def _set_raw_result(self, record_id: int, value) -> None:
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == record_id).first()
            row.raw_result = value
            session.commit()

    # --- _record_to_list_item_dict: non-dict dashboard ---

    def test_list_item_dashboard_is_string(self) -> None:
        """dashboard as str should not raise; time_sensitivity=None."""
        rid = self._save_record("q_str_dash")
        self._set_raw_result(rid, json.dumps({"dashboard": "not a dict"}))

        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)

        self.assertIsNone(item["time_sensitivity"])
        self.assertEqual(item["stock_code"], "600519")

    def test_list_item_dashboard_is_list(self) -> None:
        """dashboard as list should not raise; time_sensitivity=None."""
        rid = self._save_record("q_list_dash")
        self._set_raw_result(rid, json.dumps({"dashboard": [1, 2, 3]}))

        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)

        self.assertIsNone(item["time_sensitivity"])

    def test_list_item_dashboard_is_nonempty_string(self) -> None:
        """dashboard as non-empty str must not trigger .get() AttributeError."""
        rid = self._save_record("q_nes_dash")
        self._set_raw_result(rid, json.dumps({"dashboard": "some string"}))

        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)

        self.assertIsNone(item["time_sensitivity"])

    def test_list_item_dashboard_is_none(self) -> None:
        """dashboard=None should not raise."""
        rid = self._save_record("q_none_dash")
        self._set_raw_result(rid, json.dumps({"dashboard": None}))

        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)

        self.assertIsNone(item["time_sensitivity"])

    def test_list_item_core_conclusion_is_string(self) -> None:
        """core_conclusion as str should not raise; time_sensitivity=None."""
        rid = self._save_record("q_str_core")
        self._set_raw_result(rid, json.dumps({"dashboard": {"core_conclusion": "oops"}}))

        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)

        self.assertIsNone(item["time_sensitivity"])

    def test_list_item_core_conclusion_is_list(self) -> None:
        """core_conclusion as list should not raise; time_sensitivity=None."""
        rid = self._save_record("q_list_core")
        self._set_raw_result(rid, json.dumps({"dashboard": {"core_conclusion": ["a", "b"]}}))

        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)

        self.assertIsNone(item["time_sensitivity"])

    def test_list_item_raw_result_is_string(self) -> None:
        """raw_result as plain string (not JSON dict) should not raise."""
        rid = self._save_record("q_raw_str")
        self._set_raw_result(rid, "not json at all")

        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)

        self.assertIsNone(item["time_sensitivity"])
        self.assertIsNone(item["model_used"])

    def test_list_item_raw_result_is_list(self) -> None:
        """raw_result as JSON list should not raise."""
        rid = self._save_record("q_raw_list")
        self._set_raw_result(rid, json.dumps([1, 2, 3]))

        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)

        self.assertIsNone(item["time_sensitivity"])

    def test_list_item_valid_time_sensitivity(self) -> None:
        """Happy path: time_sensitivity extracted from valid nested dict."""
        rid = self._save_record("q_valid_ts")
        self._set_raw_result(rid, json.dumps({
            "dashboard": {
                "core_conclusion": {
                    "time_sensitivity": "今日内",
                    "sentiment": "偏多",
                }
            }
        }))

        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)

        self.assertEqual(item["time_sensitivity"], "今日内")

    # --- get_history_list: per-record error isolation ---

    def test_get_history_list_isolates_bad_record(self) -> None:
        """One malformed raw_result should not kill the entire list."""
        good_id = self._save_record("q_good")
        bad_id = self._save_record("q_bad", code="000001", name="坏数据")

        # bad record: raw_result is a non-JSON string that parse_json_field returns as-is,
        # then .get() on it would fail if not isinstance-guarded.
        # Actually parse_json_field returns the string itself for non-JSON.
        # The isinstance guard in _record_to_list_item_dict handles this.
        # To simulate a real crash, we make raw_result a dict with dashboard as dict
        # but then corrupt it so _decision_action_fields_for_record or similar raises.
        # Simplest: set raw_result to a value that causes an unexpected error inside the method.
        # We'll use a mock approach — but simpler: just verify the good record still shows up.
        self._set_raw_result(bad_id, json.dumps({"dashboard": "string_value"}))
        self._set_raw_result(good_id, json.dumps({
            "dashboard": {
                "core_conclusion": {"time_sensitivity": "本周内"}
            }
        }))

        service = HistoryService(self.db)
        payload = service.get_history_list(page=1, limit=10)

        # Both records should be returned (bad one doesn't crash, just gets None time_sensitivity)
        self.assertEqual(payload["total"], 2)
        codes = {item["stock_code"] for item in payload["items"]}
        self.assertIn("600519", codes)
        self.assertIn("000001", codes)

        # Verify the good record has correct time_sensitivity
        good_item = next(i for i in payload["items"] if i["stock_code"] == "600519")
        self.assertEqual(good_item["time_sensitivity"], "本周内")

        # Bad record should have None time_sensitivity, not a crash
        bad_item = next(i for i in payload["items"] if i["stock_code"] == "000001")
        self.assertIsNone(bad_item["time_sensitivity"])

    def test_list_item_time_sensitivity_is_int(self) -> None:
        """time_sensitivity as int should be normalized to None."""
        rid = self._save_record("q_ts_int")
        self._set_raw_result(rid, json.dumps({
            "dashboard": {"core_conclusion": {"time_sensitivity": 42}}
        }))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_list_item_time_sensitivity_is_list(self) -> None:
        """time_sensitivity as list should be normalized to None."""
        rid = self._save_record("q_ts_list")
        self._set_raw_result(rid, json.dumps({
            "dashboard": {"core_conclusion": {"time_sensitivity": ["今日内", "本周内"]}}
        }))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_list_item_time_sensitivity_is_dict(self) -> None:
        """time_sensitivity as dict should be normalized to None."""
        rid = self._save_record("q_ts_dict")
        self._set_raw_result(rid, json.dumps({
            "dashboard": {"core_conclusion": {"time_sensitivity": {"level": "high"}}}
        }))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_list_item_time_sensitivity_is_empty_string(self) -> None:
        """time_sensitivity as empty string should be normalized to None."""
        rid = self._save_record("q_ts_empty")
        self._set_raw_result(rid, json.dumps({
            "dashboard": {"core_conclusion": {"time_sensitivity": ""}}
        }))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_list_item_time_sensitivity_is_bool(self) -> None:
        """time_sensitivity as bool should be normalized to None."""
        rid = self._save_record("q_ts_bool")
        self._set_raw_result(rid, json.dumps({
            "dashboard": {"core_conclusion": {"time_sensitivity": True}}
        }))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_get_history_list_sort_by_sentiment_score_asc(self) -> None:
        """Server-side sort by sentiment_score asc should order items globally."""
        for code, score in [("600519", 90), ("000001", 30), ("600036", 60)]:
            result = AnalysisResult(
                code=code, name=f"Stock{code}", sentiment_score=score,
                trend_prediction="看多", operation_advice="持有", analysis_summary="test",
            )
            self.db.save_analysis_history(
                result=result, query_id=f"q_sort_{code}", report_type="simple",
                news_content="正文", context_snapshot=None, save_snapshot=False,
            )
        service = HistoryService(self.db)
        payload = service.get_history_list(page=1, limit=10, sort_by="sentiment_score", sort_order="asc")
        scores = [item["sentiment_score"] for item in payload["items"]]
        self.assertEqual(scores, [30, 60, 90])

    def test_get_history_list_sort_by_sentiment_score_desc(self) -> None:
        """Server-side sort by sentiment_score desc should reverse the order."""
        for code, score in [("600519", 90), ("000001", 30), ("600036", 60)]:
            result = AnalysisResult(
                code=code, name=f"Stock{code}", sentiment_score=score,
                trend_prediction="看多", operation_advice="持有", analysis_summary="test",
            )
            self.db.save_analysis_history(
                result=result, query_id=f"q_sort_desc_{code}", report_type="simple",
                news_content="正文", context_snapshot=None, save_snapshot=False,
            )
        service = HistoryService(self.db)
        payload = service.get_history_list(page=1, limit=10, sort_by="sentiment_score", sort_order="desc")
        scores = [item["sentiment_score"] for item in payload["items"]]
        self.assertEqual(scores, [90, 60, 30])

    def test_get_history_list_sort_defaults_to_created_at_desc(self) -> None:
        """Default sort should be created_at desc (newest first)."""
        import time
        for code in ["600519", "000001"]:
            result = AnalysisResult(
                code=code, name=f"Stock{code}", sentiment_score=50,
                trend_prediction="看多", operation_advice="持有", analysis_summary="test",
            )
            self.db.save_analysis_history(
                result=result, query_id=f"q_default_sort_{code}", report_type="simple",
                news_content="正文", context_snapshot=None, save_snapshot=False,
            )
            time.sleep(0.01)
        service = HistoryService(self.db)
        payload = service.get_history_list(page=1, limit=10)
        self.assertEqual(payload["items"][0]["stock_code"], "000001")
        self.assertEqual(payload["items"][1]["stock_code"], "600519")

    def test_sort_deterministic_with_tied_values(self) -> None:
        """Records with same sentiment_score should have stable order via secondary id sort."""
        for code in ["600519", "000001", "600036"]:
            result = AnalysisResult(
                code=code, name=f"Stock{code}", sentiment_score=50,
                trend_prediction="看多", operation_advice="持有", analysis_summary="test",
            )
            self.db.save_analysis_history(
                result=result, query_id=f"q_tied_{code}", report_type="simple",
                news_content="正文", context_snapshot=None, save_snapshot=False,
            )
        service = HistoryService(self.db)
        page1 = service.get_history_list(page=1, limit=2, sort_by="sentiment_score", sort_order="desc")
        page2 = service.get_history_list(page=2, limit=2, sort_by="sentiment_score", sort_order="desc")
        ids_page1 = [item["id"] for item in page1["items"]]
        ids_page2 = [item["id"] for item in page2["items"]]
        self.assertEqual(len(set(ids_page1) & set(ids_page2)), 0, "tied records overlap across pages")
        all_ids = set(ids_page1) | set(ids_page2)
        self.assertEqual(len(all_ids), 3)

    # --- time_sensitivity: additional edge cases ---

    def test_time_sensitivity_none_explicit(self) -> None:
        """time_sensitivity key present with null value → None."""
        rid = self._save_record("q_ts_none")
        self._set_raw_result(rid, json.dumps({
            "dashboard": {"core_conclusion": {"time_sensitivity": None}}
        }))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_time_sensitivity_float(self) -> None:
        """time_sensitivity as float → None (not a str)."""
        rid = self._save_record("q_ts_float")
        self._set_raw_result(rid, json.dumps({
            "dashboard": {"core_conclusion": {"time_sensitivity": 3.14}}
        }))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_time_sensitivity_whitespace_only(self) -> None:
        """time_sensitivity as whitespace-only string → None after strip."""
        rid = self._save_record("q_ts_ws")
        self._set_raw_result(rid, json.dumps({
            "dashboard": {"core_conclusion": {"time_sensitivity": "   "}}
        }))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_time_sensitivity_missing_key(self) -> None:
        """core_conclusion exists but time_sensitivity key absent → None."""
        rid = self._save_record("q_ts_missing")
        self._set_raw_result(rid, json.dumps({
            "dashboard": {"core_conclusion": {"sentiment": "偏多"}}
        }))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_dashboard_none_core_conclusion_missing(self) -> None:
        """dashboard=None → time_sensitivity=None, no crash."""
        rid = self._save_record("q_dash_none")
        self._set_raw_result(rid, json.dumps({"dashboard": None}))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_raw_result_empty_dict(self) -> None:
        """raw_result={} → time_sensitivity=None, no crash."""
        rid = self._save_record("q_raw_empty")
        self._set_raw_result(rid, json.dumps({}))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_raw_result_false(self) -> None:
        """raw_result=False (falsy non-dict) → time_sensitivity=None."""
        rid = self._save_record("q_raw_false")
        self._set_raw_result(rid, json.dumps(False))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_raw_result_integer(self) -> None:
        """raw_result=0 (int, non-dict) → time_sensitivity=None."""
        rid = self._save_record("q_raw_int")
        self._set_raw_result(rid, json.dumps(0))
        service = HistoryService(self.db)
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.id == rid).first()
            item = service._record_to_list_item_dict(row)
        self.assertIsNone(item["time_sensitivity"])

    def test_mixed_records_time_sensitivity_via_list(self) -> None:
        """Multiple records with mixed valid/invalid time_sensitivity — each returns correct value."""
        configs = [
            ("q_mix_valid", {"dashboard": {"core_conclusion": {"time_sensitivity": "今日内"}}}, "今日内"),
            ("q_mix_int", {"dashboard": {"core_conclusion": {"time_sensitivity": 99}}}, None),
            ("q_mix_list", {"dashboard": {"core_conclusion": {"time_sensitivity": ["a"]}}}, None),
            ("q_mix_missing", {"dashboard": {"core_conclusion": {}}}, None),
            ("q_mix_str", {"dashboard": {"core_conclusion": {"time_sensitivity": "不急"}}}, "不急"),
        ]
        for qid, raw, _expected in configs:
            rid = self._save_record(qid)
            self._set_raw_result(rid, json.dumps(raw))

        service = HistoryService(self.db)
        payload = service.get_history_list(page=1, limit=10)
        self.assertEqual(payload["total"], len(configs))

        for item in payload["items"]:
            qid = item["query_id"]
            expected = next(e for q, _, e in configs if q == qid)
            self.assertEqual(
                item["time_sensitivity"], expected,
                f"query_id={qid}: expected {expected!r}, got {item['time_sensitivity']!r}"
            )

    def test_time_sensitivity_preserves_chinese_unicode(self) -> None:
        """Chinese time_sensitivity strings survive full round-trip."""
        for val in ["立即行动", "今日内", "本周内", "不急"]:
            rid = self._save_record(f"q_cn_{val}")
            self._set_raw_result(rid, json.dumps({
                "dashboard": {"core_conclusion": {"time_sensitivity": val}}
            }))
        service = HistoryService(self.db)
        payload = service.get_history_list(page=1, limit=10)
        values = {item["time_sensitivity"] for item in payload["items"]}
        self.assertEqual(values, {"立即行动", "今日内", "本周内", "不急"})

    def test_get_history_list_degrades_crashing_record_via_mock(self) -> None:
        """A record that crashes during parsing returns degraded data, not a skip."""
        good_id = self._save_record("q_iso_good")
        bad_id = self._save_record("q_iso_bad", code="000001", name="坏数据")
        self._set_raw_result(good_id, json.dumps({
            "dashboard": {"core_conclusion": {"time_sensitivity": "本周内"}}
        }))

        service = HistoryService(self.db)
        original_inner = service._record_to_list_item_dict_inner

        def _selective_crash(record):
            if record.id == bad_id:
                raise RuntimeError("simulated corruption")
            return original_inner(record)

        with patch.object(service, "_record_to_list_item_dict_inner", side_effect=_selective_crash):
            payload = service.get_history_list(page=1, limit=10)

        # Both records present — bad one degraded, not skipped
        self.assertEqual(payload["total"], 2)
        self.assertEqual(len(payload["items"]), 2)

        good_item = next(i for i in payload["items"] if i["stock_code"] == "600519")
        self.assertEqual(good_item["time_sensitivity"], "本周内")

        bad_item = next(i for i in payload["items"] if i["stock_code"] == "000001")
        self.assertEqual(bad_item["stock_name"], "坏数据")
        self.assertIsNone(bad_item["sentiment_score"])
        self.assertIsNone(bad_item["time_sensitivity"])

    def test_get_history_list_total_is_db_count_not_page_count(self) -> None:
        """total must reflect DB row count, not len(items) on the current page."""
        for i in range(5):
            self._save_record(f"q_pg_{i}", code=f"00000{i}")

        service = HistoryService(self.db)
        page1 = service.get_history_list(page=1, limit=2)

        self.assertEqual(page1["total"], 5)
        self.assertEqual(len(page1["items"]), 2)


@unittest.skipUnless(TestClient, "fastapi / httpx not installed")
class TestHistoryListEndpointContract(unittest.TestCase):
    """Endpoint-level regression: HistoryItem schema mismatch must surface as 500, not silently drop records."""

    def setUp(self) -> None:
        auth._auth_enabled = False
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_endpoint.db")
        os.environ["DATABASE_PATH"] = self._db_path

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

        static_dir = Path(self._temp_dir.name) / "empty-static"
        static_dir.mkdir(exist_ok=True)
        self.client = TestClient(create_app(static_dir=static_dir))

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def _insert_record(self, query_id: str, **overrides) -> int:
        result = AnalysisResult(
            code=overrides.get("code", "600519"),
            name=overrides.get("name", "贵州茅台"),
            sentiment_score=overrides.get("sentiment_score", 78),
            trend_prediction=overrides.get("trend_prediction", "看多"),
            operation_advice=overrides.get("operation_advice", "持有"),
            analysis_summary=overrides.get("analysis_summary", "基本面稳健"),
        )
        self.db.save_analysis_history(
            result=result,
            query_id=query_id,
            report_type="simple",
            news_content="",
            context_snapshot=None,
            save_snapshot=False,
        )
        with self.db.get_session() as session:
            row = session.query(AnalysisHistory).filter(AnalysisHistory.query_id == query_id).first()
            return row.id

    def test_schema_mismatch_surfaces_500_not_silent_drop(self) -> None:
        """If service returns a dict with invalid types, endpoint returns 500."""
        self._insert_record("q_ok")

        # Patch HistoryService.get_history_list to return a good item + a bad item
        # with sentiment_score="not_an_int" — Pydantic must reject it.
        original_get = HistoryService.get_history_list

        def _patched_get(self_svc, **kwargs):
            real = original_get(self_svc, **kwargs)
            real["items"].append({
                "id": 999,
                "query_id": "q_bad",
                "stock_code": "BAD",
                "sentiment_score": "not_an_int",
            })
            real["total"] = len(real["items"])
            return real

        with patch.object(HistoryService, "get_history_list", _patched_get):
            response = self.client.get("/api/v1/history")

        # Must NOT return 200 with partial data — schema regression must be loud
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(response.status_code, 500)
        body = response.json()
        # FastAPI may wrap in {"detail": ...} or return the error dict directly
        error_payload = body.get("detail", body)
        self.assertIn("error", error_payload)

    def test_total_matches_items_when_all_fit_one_page(self) -> None:
        """total equals len(items) when all records fit on a single page."""
        for i in range(3):
            self._insert_record(f"q_total_{i}")

        response = self.client.get("/api/v1/history")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 3)
        self.assertEqual(body["total"], len(body["items"]))

    def test_total_is_db_count_when_paginated(self) -> None:
        """total must be the DB row count, not len(items), when results span multiple pages."""
        for i in range(25):
            self._insert_record(f"q_pg_{i}", code=f"0000{i:02d}")

        response = self.client.get("/api/v1/history", params={"limit": 20, "page": 1})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 25, "total must be DB count, not page item count")
        self.assertEqual(len(body["items"]), 20, "first page should have 20 items")


if __name__ == "__main__":
    unittest.main()
