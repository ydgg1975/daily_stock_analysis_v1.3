# -*- coding: utf-8 -*-
"""Tests for evidence graph construction."""

import sys
import unittest
from unittest.mock import MagicMock

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

from src.analyzer import AnalysisResult
from src.services.evidence_graph_service import build_evidence_graph


class EvidenceGraphServiceTest(unittest.TestCase):
    def test_builds_nodes_and_edges_from_result_metadata(self) -> None:
        result = AnalysisResult(
            code="AAPL",
            name="Apple",
            sentiment_score=68,
            trend_prediction="Bullish",
            operation_advice="Hold",
            analysis_summary="Momentum remains constructive.",
            risk_warning="Valuation remains elevated.",
            evidence_points=["MA5 remains above MA20."],
            counter_evidence=["Volume confirmation is weak."],
            data_limitations=["News data was not refreshed."],
            data_sources="technical,news",
        )

        graph = build_evidence_graph(result)

        self.assertEqual(graph["version"], 1)
        self.assertGreaterEqual(graph["summary"]["total_nodes"], 6)
        self.assertEqual(graph["summary"]["supporting_evidence"], 1)
        self.assertEqual(graph["summary"]["counter_evidence"], 1)
        self.assertEqual(graph["summary"]["risks"], 1)
        self.assertEqual(graph["summary"]["stale_nodes"], 1)
        self.assertIn("supports", {edge["relation"] for edge in graph["edges"]})
        self.assertIn("weakens", {edge["relation"] for edge in graph["edges"]})


if __name__ == "__main__":
    unittest.main()
