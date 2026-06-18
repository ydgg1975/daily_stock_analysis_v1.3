# -*- coding: utf-8 -*-
"""Verify the optional pre-trade review advisory threads through the real consumer paths.

The advisory is set on the in-memory AnalysisResult by the pipeline; this confirms it then
reaches the persisted history raw_result and the API response — both of which serialize via
AnalysisResult.to_dict() — and that it stays ABSENT (zero output change) when the feature is off.
"""
import unittest
from types import SimpleNamespace

from src.analyzer import AnalysisResult
from src.storage import DatabaseManager
from src.services.history_service import HistoryService


def _make_result() -> AnalysisResult:
    return AnalysisResult(
        code="600519",
        name="贵州茅台",
        trend_prediction="看多",
        sentiment_score=70,
        operation_advice="持有",
        analysis_summary="稳健",
        decision_type="hold",
    )


class TestPretradeReviewThreading(unittest.TestCase):
    def test_to_dict_omits_field_when_disabled(self):
        """Default (feature off) — to_dict must NOT contain pretrade_review (zero output change)."""
        data = _make_result().to_dict()
        self.assertNotIn("pretrade_review", data)

    def test_to_dict_includes_advisory_when_set(self):
        result = _make_result()
        result.pretrade_review = {"status": "ok", "verdict": "approve_with_concerns",
                                  "confidence": 0.75, "issues": [], "proof": {"sig": "..."}}
        data = result.to_dict()
        self.assertIn("pretrade_review", data)
        self.assertEqual(data["pretrade_review"]["verdict"], "approve_with_concerns")
        # the BUY/SELL conclusion fields are untouched
        self.assertEqual(data["operation_advice"], "持有")
        self.assertEqual(data["decision_type"], "hold")

    def test_storage_raw_result_preserves_advisory(self):
        """The persisted history raw_result is built from to_dict() — it must carry the advisory."""
        result = _make_result()
        result.pretrade_review = {"status": "review_unavailable", "reason": "network_error"}
        raw = DatabaseManager._build_raw_result(result)
        self.assertIn("pretrade_review", raw)
        self.assertEqual(raw["pretrade_review"]["status"], "review_unavailable")

    def test_storage_raw_result_omits_advisory_when_disabled(self):
        raw = DatabaseManager._build_raw_result(_make_result())
        self.assertNotIn("pretrade_review", raw)

    def test_history_restore_rebuilds_advisory(self):
        """The history-restore path (HistoryService._rebuild_analysis_result) reconstructs an
        AnalysisResult from a stored raw_result dict — it must carry pretrade_review back, or the
        regenerated history Markdown / restored object loses the advisory (the PR's history-restore
        contract). Round-trip: to_dict() -> raw_result -> rebuild -> field preserved."""
        result = _make_result()
        result.pretrade_review = {"status": "ok", "verdict": "approve_with_concerns",
                                  "confidence": 0.75, "issues": [], "proof": {"sig": "..."}}
        raw_result = result.to_dict()
        record = SimpleNamespace(code="600519", name="贵州茅台", sentiment_score=70,
                                 trend_prediction="看多", operation_advice="持有",
                                 news_content="", analysis_summary="稳健")
        rebuilt = HistoryService(db_manager=None)._rebuild_analysis_result(raw_result, record)
        self.assertIsNotNone(rebuilt)
        self.assertEqual(rebuilt.pretrade_review["verdict"], "approve_with_concerns")
        # and the BUY/SELL conclusion is preserved unchanged
        self.assertEqual(rebuilt.operation_advice, "持有")

    def test_history_restore_omits_advisory_when_absent(self):
        """Existing records (no pretrade_review in raw_result) rebuild with pretrade_review=None —
        a no-op for pre-feature history."""
        record = SimpleNamespace(code="600519", name="贵州茅台", sentiment_score=70,
                                 trend_prediction="看多", operation_advice="持有",
                                 news_content="", analysis_summary="稳健")
        rebuilt = HistoryService(db_manager=None)._rebuild_analysis_result(_make_result().to_dict(), record)
        self.assertIsNotNone(rebuilt)
        self.assertIsNone(rebuilt.pretrade_review)


if __name__ == "__main__":
    unittest.main()
