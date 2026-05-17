# -*- coding: utf-8 -*-
"""Tests for rules engine evaluation and display."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestRuleEngineEvaluate(unittest.TestCase):

    def setUp(self):
        from src.rules.engine import RuleEngine
        self.engine = RuleEngine()

    def test_evaluate_empty_data_no_crash(self):
        results = self.engine.evaluate({})
        self.assertEqual(len(results), 22)
        self.assertTrue(all(not r.matched for r in results))

    def test_evaluate_returns_22_results(self):
        results = self.engine.evaluate({"rsi": 50, "ma5": 100, "ma10": 99})
        self.assertEqual(len(results), 22)

    def test_rsi_overbought_matches(self):
        results = self.engine.evaluate({"rsi": 75})
        rsi_rules = [r for r in results if r.rule_id == "T07"]
        self.assertEqual(len(rsi_rules), 1)
        self.assertTrue(rsi_rules[0].matched)

    def test_rsi_oversold_matches(self):
        results = self.engine.evaluate({"rsi": 25})
        rsi_rules = [r for r in results if r.rule_id == "T08"]
        self.assertTrue(rsi_rules[0].matched)

    def test_rsi_normal_not_matched(self):
        results = self.engine.evaluate({"rsi": 50})
        rsi_over = [r for r in results if r.rule_id == "T07"]
        rsi_under = [r for r in results if r.rule_id == "T08"]
        self.assertFalse(rsi_over[0].matched)
        self.assertFalse(rsi_under[0].matched)

    def test_ma_bullish_alignment(self):
        results = self.engine.evaluate({"ma_alignment": "bullish"})
        rule = [r for r in results if r.rule_id == "T03"][0]
        self.assertTrue(rule.matched)

    def test_new_high_20d(self):
        results = self.engine.evaluate({"new_high_20d": True})
        rule = [r for r in results if r.rule_id == "TR03"][0]
        self.assertTrue(rule.matched)

    def test_valuation_rules_not_matched_without_data(self):
        results = self.engine.evaluate({})
        val_rules = [r for r in results if r.dimension == "valuation"]
        self.assertTrue(all(not r.matched for r in val_rules))

    def test_pe_percentile_low(self):
        results = self.engine.evaluate({"pe_percentile": 15.0})
        rule = [r for r in results if r.rule_id == "V01"][0]
        self.assertTrue(rule.matched)

    def test_pe_percentile_high(self):
        results = self.engine.evaluate({"pe_percentile": 85.0})
        rule = [r for r in results if r.rule_id == "V02"][0]
        self.assertTrue(rule.matched)

    def test_pe_percentile_moderate(self):
        results = self.engine.evaluate({"pe_percentile": 50.0})
        v03 = [r for r in results if r.rule_id == "V03"][0]
        self.assertTrue(v03.matched)
        self.assertFalse([r for r in results if r.rule_id == "V01"][0].matched)
        self.assertFalse([r for r in results if r.rule_id == "V02"][0].matched)


class TestDimensionSummary(unittest.TestCase):

    def test_summary_counts_signals(self):
        from src.rules.engine import dimension_summary
        from src.schemas.rules import RuleResult
        results = [
            RuleResult("T01", "technical", "test", "", "bullish", True, 0.8),
            RuleResult("T02", "technical", "test", "", "bearish", True, 0.8),
            RuleResult("T03", "technical", "test", "", "bullish", False, 1.0),
        ]
        summary = dimension_summary(results)
        self.assertIn("technical", summary)
        self.assertEqual(summary["technical"]["bullish"], 1)
        self.assertEqual(summary["technical"]["bearish"], 1)

    def test_unmatched_dimension_excluded(self):
        from src.rules.engine import dimension_summary
        from src.schemas.rules import RuleResult
        results = [
            RuleResult("T01", "technical", "test", "", "bullish", False, 0.8),
        ]
        summary = dimension_summary(results)
        self.assertNotIn("technical", summary)


class TestComputeTotalScore(unittest.TestCase):

    def test_bullish_positive(self):
        from src.rules.engine import compute_total_score
        from src.schemas.rules import RuleResult
        results = [
            RuleResult("T01", "technical", "test", "", "bullish", True, 1.0),
        ]
        score = compute_total_score(results)
        self.assertGreater(score, 0)

    def test_bearish_negative(self):
        from src.rules.engine import compute_total_score
        from src.schemas.rules import RuleResult
        results = [
            RuleResult("T02", "technical", "test", "", "bearish", True, 1.0),
        ]
        score = compute_total_score(results)
        self.assertLess(score, 0)

    def test_empty_results_zero(self):
        from src.rules.engine import compute_total_score
        score = compute_total_score([])
        self.assertEqual(score, 0.0)


class TestDisplayFormatter(unittest.TestCase):

    def test_empty_rules_returns_empty_string(self):
        from src.rules.display import format_rules_tags
        result = format_rules_tags([], {}, 0.0)
        self.assertEqual(result, "")

    def test_format_tags_contains_emoji(self):
        from src.rules.display import format_rules_tags
        from src.schemas.rules import RuleResult
        results = [
            RuleResult("T01", "technical", "均线金叉", "MA5上穿MA10", "bullish", True, 0.8),
        ]
        summary = {"technical": {"bullish": 1}}
        tags = format_rules_tags(results, summary, 0.8)
        self.assertIn("🟢", tags)
        self.assertIn("技术面", tags)

    def test_html_format_contains_span(self):
        from src.rules.display import format_rules_tags_html
        from src.schemas.rules import RuleResult
        results = [
            RuleResult("T01", "technical", "均线金叉", "MA5上穿MA10", "bullish", True, 0.8),
        ]
        summary = {"technical": {"bullish": 1}}
        html = format_rules_tags_html(results, summary, 0.8)
        self.assertIn("<span", html)
        self.assertIn("#52c41a", html)


if __name__ == "__main__":
    unittest.main()
