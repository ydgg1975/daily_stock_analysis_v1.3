# -*- coding: utf-8 -*-
"""Tests for the scanner AI interpretation layer."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.core.scanner_profile import CN_A_PREOPEN_V1
from src.services.scanner_ai_service import ScannerAiInterpretationService


class FakeAnalyzer:
    def __init__(self, responses: list[dict | None], *, available: bool = True) -> None:
        self._responses = list(responses)
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def generate_text_with_meta(self, *args, **kwargs):  # noqa: ANN002, ANN003
        _ = args, kwargs
        if not self._responses:
            return None
        return self._responses.pop(0)


def _candidate(symbol: str, rank: int) -> dict:
    return {
        "symbol": symbol,
        "name": f"股票{symbol}",
        "rank": rank,
        "score": 85.0 - rank,
        "quality_hint": "高优先级",
        "reason_summary": "趋势和量能结构较好。",
        "reasons": ["趋势结构完整。", "量能活跃。"],
        "risk_notes": ["需要确认竞价承接。"],
        "watch_context": [{"label": "观察触发", "value": "关注前高突破。"}],
        "boards": ["AI算力"],
        "key_metrics": [{"label": "最新价", "value": "18.20"}],
        "feature_signals": [{"label": "趋势结构", "value": "18.0 / 20"}],
        "_diagnostics": {},
    }


class ScannerAiInterpretationServiceTestCase(unittest.TestCase):
    def test_interpret_shortlist_generates_top_n_and_skips_tail(self) -> None:
        analyzer = FakeAnalyzer(
            [
                {
                    "text": (
                        '{"summary":"更像趋势延续里的临界突破观察。","opportunity_type":"临界突破",'
                        '"risk_interpretation":"高开过多时要防冲高回落。","watch_plan":"先看竞价承接，再看开盘量能是否继续放大。",'
                        '"review_commentary":null}'
                    ),
                    "model": "gemini/gemini-2.5-flash",
                    "provider": "gemini",
                    "usage": {},
                    "attempt_trace": [],
                },
                {
                    "text": (
                        '{"summary":"板块联动还在，但更适合等确认。","opportunity_type":"板块联动",'
                        '"risk_interpretation":"若板块强度转弱，个股延续性会下降。","watch_plan":"先看板块同步性，再看个股量比是否维持强势。",'
                        '"review_commentary":null}'
                    ),
                    "model": "gemini/gemini-2.5-flash",
                    "provider": "gemini",
                    "usage": {},
                    "attempt_trace": [],
                },
            ]
        )
        service = ScannerAiInterpretationService(
            config=SimpleNamespace(
                scanner_ai_enabled=True,
                scanner_ai_top_n=2,
                litellm_model="gemini/gemini-2.5-flash",
            ),
            analyzer_factory=lambda: analyzer,
        )

        candidates, diagnostics = service.interpret_shortlist(
            profile=CN_A_PREOPEN_V1,
            candidates=[_candidate("600001", 1), _candidate("600002", 2), _candidate("600003", 3)],
        )

        self.assertEqual(diagnostics["status"], "completed")
        self.assertEqual(diagnostics["generated_candidates"], 2)
        self.assertTrue(candidates[0]["ai_interpretation"]["available"])
        self.assertEqual(candidates[0]["ai_interpretation"]["opportunity_type"], "临界突破")
        self.assertEqual(candidates[1]["ai_interpretation"]["status"], "generated")
        self.assertEqual(candidates[2]["ai_interpretation"]["status"], "skipped")

    def test_interpret_shortlist_returns_unavailable_when_analyzer_is_not_ready(self) -> None:
        service = ScannerAiInterpretationService(
            config=SimpleNamespace(
                scanner_ai_enabled=True,
                scanner_ai_top_n=2,
                litellm_model="gemini/gemini-2.5-flash",
            ),
            analyzer_factory=lambda: FakeAnalyzer([], available=False),
        )

        candidates, diagnostics = service.interpret_shortlist(
            profile=CN_A_PREOPEN_V1,
            candidates=[_candidate("600001", 1), _candidate("600002", 2)],
        )

        self.assertEqual(diagnostics["status"], "unavailable")
        self.assertTrue(all(item["ai_interpretation"]["status"] == "unavailable" for item in candidates))

    def test_enrich_review_commentary_updates_existing_generated_payload(self) -> None:
        analyzer = FakeAnalyzer(
            [
                {
                    "text": '{"review_commentary":"后续表现跑赢基准，说明趋势与量能配合有效。"}',
                    "model": "gemini/gemini-2.5-flash",
                    "provider": "gemini",
                    "usage": {},
                    "attempt_trace": [],
                }
            ]
        )
        service = ScannerAiInterpretationService(
            config=SimpleNamespace(
                scanner_ai_enabled=True,
                scanner_ai_top_n=2,
                litellm_model="gemini/gemini-2.5-flash",
            ),
            analyzer_factory=lambda: analyzer,
        )
        candidate = _candidate("600001", 1)
        candidate["diagnostics"] = {
            "ai_interpretation": {
                "status": "generated",
                "summary": "更像趋势延续里的临界突破观察。",
                "opportunity_type": "临界突破",
                "risk_interpretation": "高开过多时要防冲高回落。",
                "watch_plan": "先看竞价承接，再看开盘量能是否继续放大。",
                "review_commentary": None,
                "review_commentary_status": "pending_review_data",
            }
        }

        updated = service.enrich_review_commentary(
            profile=CN_A_PREOPEN_V1,
            candidate=candidate,
            realized_outcome={
                "review_status": "ready",
                "review_window_return_pct": 5.6,
                "max_favorable_move_pct": 7.4,
                "max_adverse_move_pct": -1.5,
                "outperformed_benchmark": True,
                "thesis_match": "validated",
            },
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated["review_commentary_status"], "generated")
        self.assertIn("跑赢基准", updated["review_commentary"])


if __name__ == "__main__":
    unittest.main()
