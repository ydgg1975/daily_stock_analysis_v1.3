"""
Unit Tests for Report Formatting

Task 10.5: Write unit tests for report formatting
- Test JSON serialization with missing data (Req 18.10)
- Test Markdown rendering with various state combinations (Req 19.12)
- Test strategy mapping for all regime types (Req 20.7)
"""

import json
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.market_diagnostic.reports.schema import DiagnosticReport
from src.market_diagnostic.reports.markdown_renderer import DiagnosticMarkdownRenderer
from src.market_diagnostic.reports.strategy_mapper import map_regime_to_strategies


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_report(**overrides) -> DiagnosticReport:
    """Return a minimal but fully-populated DiagnosticReport."""
    defaults = dict(
        date="2024-06-01",
        trend_state="强趋势上行",
        breadth_state="偏强",
        sentiment_state="活跃",
        style_state="成长主导",
        sector_state="单主线",
        risk_state="低风险",
        composite_regime="trend_risk_on_growth",
        trend_score=80.0,
        breadth_score=65.0,
        sentiment_score=70.0,
        risk_score=20.0,
        regime_score=72.0,
        style_score=68.0,
        sector_score=75.0,
        one_sentence_summary="市场强势上行。",
        key_evidence=["沪深300多头排列"],
        counter_evidence=["成交额偏低"],
        confidence=0.85,
        missing_data=[],
        risk_flags=[],
        strategy_mapping=[
            {"strategy_group": "趋势ETF组", "allocation_weight": 0.50},
            {"strategy_group": "行业轮动组", "allocation_weight": 0.30},
            {"strategy_group": "小市值进攻组", "allocation_weight": 0.20},
        ],
        indices=[
            {
                "code": "sh000300",
                "name": "沪深300",
                "close": 3850.5,
                "change_pct": 1.25,
                "ma_alignment": "多头排列",
                "macd_signal": "金叉",
                "atr_20": 45.2,
                "rsrs_score": 0.75,
                "bias_ma20": 0.032,
            }
        ],
        breadth_metrics={
            "up_down_ratio": 2.5,
            "limit_up_rate": 0.028,
            "seal_rate": 0.82,
            "above_ma20_ratio": 0.62,
            "above_ma60_ratio": 0.55,
            "new_high_ratio": 0.045,
            "amount_deviation_5d": 0.08,
            "amount_deviation_20d": 0.05,
            "breadth_score": 65.0,
        },
        sentiment_metrics={
            "limit_up_down_ratio": 3.5,
            "continuous_limit_up": 18,
            "seal_rate": 0.82,
            "next_day_premium": 0.015,
            "turnover_zscore": 0.8,
            "sentiment_score": 70.0,
        },
        style_metrics={
            "rs_large_vs_small": 0.95,
            "rs_300_vs_1000": 0.92,
            "rs_500_vs_1000": 0.98,
            "ret_1d": {},
            "ret_5d": {},
            "ret_20d": {},
            "amount_share": {},
            "dominant_style": "成长主导",
        },
        sector_table=[
            {
                "industry_code": "BK0447",
                "industry_name": "电子",
                "strength_score": 2.5,
                "persistence_score": 0.8,
                "crowding_score": 0.3,
                "leadership_score": 0.9,
                "state": "主升趋势",
            }
        ],
        capital_metrics={
            "total_amount": 9500.0,
            "amount_deviation_5d": 0.08,
            "amount_deviation_20d": 0.05,
            "amount_deviation_60d": 0.12,
            "north_net_flow": 15.3,
            "north_5d_avg": 8.2,
            "north_flow_trend": "inflow",
            "margin_balance": 15800.0,
            "margin_delta": 120.0,
            "main_net_flow": 45.0,
            "etf_net_flow": 30.0,
            "data_freshness": {},
            "has_delayed_data": False,
        },
    )
    defaults.update(overrides)
    return DiagnosticReport(**defaults)


_renderer = DiagnosticMarkdownRenderer()


# ===========================================================================
# 1. JSON Serialization with Missing Data (Req 18.10)
# ===========================================================================

class TestJsonSerializationMissingData:
    """Tests for to_json() behaviour when data is missing or incomplete."""

    def test_to_json_includes_missing_data_field_when_populated(self):
        """Req 18.10: missing_data field must appear in JSON when data is missing."""
        report = _make_report(missing_data=["north_bound_capital", "margin_balance"])
        parsed = json.loads(report.to_json())

        assert "missing_data" in parsed
        assert "north_bound_capital" in parsed["missing_data"]
        assert "margin_balance" in parsed["missing_data"]

    def test_to_json_missing_data_field_present_when_empty(self):
        """Req 18.10: missing_data field must be present even when empty."""
        report = _make_report(missing_data=[])
        parsed = json.loads(report.to_json())

        assert "missing_data" in parsed
        assert parsed["missing_data"] == []

    def test_to_json_handles_none_values_in_breadth_metrics(self):
        """Req 18.10: None values in breadth_metrics must serialise to JSON null."""
        report = _make_report(
            breadth_metrics={
                "up_down_ratio": None,
                "limit_up_rate": None,
                "seal_rate": None,
                "above_ma20_ratio": None,
                "above_ma60_ratio": None,
                "new_high_ratio": None,
                "amount_deviation_5d": None,
                "amount_deviation_20d": None,
                "breadth_score": None,
            }
        )
        json_str = report.to_json()
        parsed = json.loads(json_str)

        assert parsed["breadth_metrics"]["up_down_ratio"] is None
        assert parsed["breadth_metrics"]["breadth_score"] is None

    def test_to_json_handles_none_values_in_sentiment_metrics(self):
        """Req 18.10: None values in sentiment_metrics must serialise to JSON null."""
        report = _make_report(
            sentiment_metrics={
                "limit_up_down_ratio": None,
                "continuous_limit_up": None,
                "seal_rate": None,
                "next_day_premium": None,
                "turnover_zscore": None,
                "sentiment_score": None,
            }
        )
        parsed = json.loads(report.to_json())
        assert parsed["sentiment_metrics"]["sentiment_score"] is None

    def test_to_json_handles_none_values_in_capital_metrics(self):
        """Req 18.10: None values in capital_metrics must serialise to JSON null."""
        report = _make_report(
            capital_metrics={
                "total_amount": None,
                "amount_deviation_5d": None,
                "amount_deviation_20d": None,
                "amount_deviation_60d": None,
                "north_net_flow": None,
                "north_5d_avg": None,
                "north_flow_trend": None,
                "margin_balance": None,
                "margin_delta": None,
                "main_net_flow": None,
                "etf_net_flow": None,
                "data_freshness": {},
                "has_delayed_data": False,
            }
        )
        parsed = json.loads(report.to_json())
        assert parsed["capital_metrics"]["total_amount"] is None
        assert parsed["capital_metrics"]["north_net_flow"] is None

    def test_to_json_handles_empty_indices(self):
        """Req 18.10: Empty indices list must serialise to an empty JSON array."""
        report = _make_report(indices=[])
        parsed = json.loads(report.to_json())

        assert "indices" in parsed
        assert parsed["indices"] == []

    def test_to_json_handles_empty_sector_table(self):
        """Req 18.10: Empty sector_table must serialise to an empty JSON array."""
        report = _make_report(sector_table=[])
        parsed = json.loads(report.to_json())

        assert "sector_table" in parsed
        assert parsed["sector_table"] == []

    def test_to_json_handles_empty_breadth_metrics(self):
        """Req 18.10: Empty breadth_metrics dict must serialise to an empty JSON object."""
        report = _make_report(breadth_metrics={})
        parsed = json.loads(report.to_json())

        assert "breadth_metrics" in parsed
        assert parsed["breadth_metrics"] == {}

    def test_to_json_handles_empty_capital_metrics(self):
        """Req 18.10: Empty capital_metrics dict must serialise to an empty JSON object."""
        report = _make_report(capital_metrics={})
        parsed = json.loads(report.to_json())

        assert "capital_metrics" in parsed
        assert parsed["capital_metrics"] == {}

    def test_to_json_handles_empty_style_metrics(self):
        """Req 18.10: Empty style_metrics dict must serialise to an empty JSON object."""
        report = _make_report(style_metrics={})
        parsed = json.loads(report.to_json())

        assert "style_metrics" in parsed
        assert parsed["style_metrics"] == {}

    def test_from_dict_roundtrip_preserves_missing_data(self):
        """Req 18.10: from_dict() round-trip must preserve missing_data list."""
        original = _make_report(missing_data=["north_bound_capital", "sector_breadth"])
        data = json.loads(original.to_json())
        restored = DiagnosticReport.from_dict(data)

        assert restored.missing_data == original.missing_data

    def test_from_dict_roundtrip_preserves_all_states(self):
        """from_dict() round-trip must preserve all state fields."""
        original = _make_report(
            trend_state="破位下行",
            breadth_state="极弱",
            sentiment_state="冰点",
            risk_state="极端风险",
            composite_regime="panic_bottoming",
        )
        data = json.loads(original.to_json())
        restored = DiagnosticReport.from_dict(data)

        assert restored.trend_state == "破位下行"
        assert restored.breadth_state == "极弱"
        assert restored.sentiment_state == "冰点"
        assert restored.risk_state == "极端风险"
        assert restored.composite_regime == "panic_bottoming"

    def test_from_dict_roundtrip_preserves_scores(self):
        """from_dict() round-trip must preserve numeric score fields."""
        original = _make_report(
            trend_score=42.5,
            breadth_score=33.0,
            sentiment_score=55.5,
            risk_score=78.0,
            regime_score=38.2,
            confidence=0.72,
        )
        data = json.loads(original.to_json())
        restored = DiagnosticReport.from_dict(data)

        assert restored.trend_score == pytest.approx(42.5)
        assert restored.breadth_score == pytest.approx(33.0)
        assert restored.confidence == pytest.approx(0.72)

    def test_from_dict_roundtrip_preserves_empty_missing_data(self):
        """from_dict() round-trip must preserve empty missing_data list."""
        original = _make_report(missing_data=[])
        data = json.loads(original.to_json())
        restored = DiagnosticReport.from_dict(data)

        assert restored.missing_data == []

    def test_to_json_chinese_characters_preserved(self):
        """to_json() must preserve Chinese characters (ensure_ascii=False)."""
        report = _make_report(one_sentence_summary="市场处于强趋势上行阶段。")
        json_str = report.to_json()

        # Chinese characters should appear literally, not as \\uXXXX escapes
        assert "市场处于强趋势上行阶段" in json_str


# ===========================================================================
# 2. Markdown Rendering with Various State Combinations (Req 19.12)
# ===========================================================================

class TestMarkdownRenderingStateCombinations:
    """Tests for Markdown rendering across all valid state values."""

    # ---- All 7 composite regimes ----

    @pytest.mark.parametrize("regime,expected_display", [
        ("trend_risk_on_growth",   "趋势进攻-成长主导"),
        ("trend_risk_on_smallcap", "趋势进攻-小盘主导"),
        ("balanced_rotation",      "均衡轮动"),
        ("defensive_dividend",     "防守-红利"),
        ("high_volatility_warning","高波动预警"),
        ("panic_bottoming",        "恐慌探底"),
        ("broad_weakness_hold",    "全面弱势-持币观望"),
    ])
    def test_all_composite_regimes_render_display_name(self, regime, expected_display):
        """Req 19.2: Each composite regime must render its human-readable display name."""
        report = _make_report(composite_regime=regime)
        output = _renderer.render(report)
        assert expected_display in output, (
            f"Regime '{regime}' should render as '{expected_display}'"
        )

    # ---- All 5 trend states ----

    @pytest.mark.parametrize("trend_state", [
        "强趋势上行",
        "趋势上行中的回调",
        "震荡",
        "趋势转弱",
        "破位下行",
    ])
    def test_all_trend_states_appear_in_dashboard(self, trend_state):
        """Req 19.2: All 5 trend states must appear in the state dashboard."""
        report = _make_report(trend_state=trend_state)
        output = _renderer.render(report)
        assert trend_state in output, (
            f"Trend state '{trend_state}' not found in rendered output"
        )

    # ---- All 4 risk states ----

    @pytest.mark.parametrize("risk_state", [
        "低风险",
        "中性风险",
        "高风险",
        "极端风险",
    ])
    def test_all_risk_states_appear_in_dashboard(self, risk_state):
        """Req 19.2: All 4 risk states must appear in the state dashboard."""
        report = _make_report(risk_state=risk_state)
        output = _renderer.render(report)
        assert risk_state in output, (
            f"Risk state '{risk_state}' not found in rendered output"
        )

    # ---- LLM narrative (Req 19.12) ----

    def test_llm_narrative_section_appended_when_provided(self):
        """Req 19.12: LLM narrative section must be appended when a non-empty string is given."""
        report = _make_report()
        narrative = "今日市场整体偏强，科技板块领涨，建议关注半导体机会。"
        output = _renderer.render(report, llm_narrative=narrative)

        assert "AI 叙述分析" in output
        assert narrative in output

    def test_llm_narrative_section_absent_when_not_provided(self):
        """Req 19.12: LLM narrative section must NOT appear when no narrative is given."""
        report = _make_report()
        output = _renderer.render(report)
        assert "AI 叙述分析" not in output

    def test_llm_narrative_section_absent_for_empty_string(self):
        """Req 19.12: Empty string narrative must not add the LLM section."""
        report = _make_report()
        output = _renderer.render(report, llm_narrative="")
        assert "AI 叙述分析" not in output

    def test_llm_narrative_section_absent_for_whitespace_only(self):
        """Req 19.12: Whitespace-only narrative must not add the LLM section."""
        report = _make_report()
        output = _renderer.render(report, llm_narrative="   \n\t  ")
        assert "AI 叙述分析" not in output

    def test_llm_narrative_content_is_trimmed(self):
        """Req 19.12: LLM narrative content must be stripped of leading/trailing whitespace."""
        report = _make_report()
        narrative = "  市场分析内容。  "
        output = _renderer.render(report, llm_narrative=narrative)
        assert "市场分析内容。" in output

    # ---- one_sentence_summary edge cases ----

    def test_empty_one_sentence_summary_shows_placeholder(self):
        """When one_sentence_summary is empty, a placeholder must be shown."""
        report = _make_report(one_sentence_summary="")
        output = _renderer.render(report)
        assert "一句话结论" in output
        assert "暂无摘要" in output

    def test_none_one_sentence_summary_shows_placeholder(self):
        """When one_sentence_summary is None, a placeholder must be shown."""
        report = _make_report(one_sentence_summary=None)
        output = _renderer.render(report)
        assert "一句话结论" in output
        assert "暂无摘要" in output

    def test_non_empty_one_sentence_summary_is_rendered(self):
        """When one_sentence_summary is non-empty, it must appear in the output."""
        summary = "市场处于震荡整理阶段，建议保持中性仓位。"
        report = _make_report(one_sentence_summary=summary)
        output = _renderer.render(report)
        assert summary in output

    # ---- Breadth state combinations ----

    @pytest.mark.parametrize("breadth_state", [
        "极弱", "偏弱", "中性", "偏强", "过热",
    ])
    def test_all_breadth_states_appear_in_dashboard(self, breadth_state):
        """Req 19.2: All 5 breadth states must appear in the state dashboard."""
        report = _make_report(breadth_state=breadth_state)
        output = _renderer.render(report)
        assert breadth_state in output

    # ---- Sentiment state combinations ----

    @pytest.mark.parametrize("sentiment_state", [
        "冰点", "回暖", "中性", "活跃", "狂热",
    ])
    def test_all_sentiment_states_appear_in_dashboard(self, sentiment_state):
        """Req 19.2: All 5 sentiment states must appear in the state dashboard."""
        report = _make_report(sentiment_state=sentiment_state)
        output = _renderer.render(report)
        assert sentiment_state in output

    # ---- Style state combinations ----

    @pytest.mark.parametrize("style_state", [
        "大盘防守", "小盘进攻", "成长主导", "红利防守", "风格冲突",
    ])
    def test_all_style_states_appear_in_dashboard(self, style_state):
        """Req 19.2: All 5 style states must appear in the state dashboard."""
        report = _make_report(style_state=style_state)
        output = _renderer.render(report)
        assert style_state in output

    # ---- Sector state combinations ----

    @pytest.mark.parametrize("sector_state", [
        "无主线", "单主线", "双主线并行", "高速轮动", "退潮分化",
    ])
    def test_all_sector_states_appear_in_dashboard(self, sector_state):
        """Req 19.2: All 5 sector states must appear in the state dashboard."""
        report = _make_report(sector_state=sector_state)
        output = _renderer.render(report)
        assert sector_state in output


# ===========================================================================
# 3. Strategy Mapping for All Regime Types (Req 20.7)
# ===========================================================================

class TestStrategyMappingAllRegimes:
    """Tests for map_regime_to_strategies() covering all 7 regimes."""

    ALL_REGIMES = [
        "trend_risk_on_growth",
        "trend_risk_on_smallcap",
        "balanced_rotation",
        "defensive_dividend",
        "high_volatility_warning",
        "panic_bottoming",
        "broad_weakness_hold",
    ]

    @pytest.mark.parametrize("regime", ALL_REGIMES)
    def test_all_regimes_return_non_empty_list(self, regime):
        """Req 20.7: Every valid regime must return a non-empty strategy list."""
        result = map_regime_to_strategies(regime)
        assert isinstance(result, list)
        assert len(result) > 0, f"Regime '{regime}' returned empty strategy list"

    @pytest.mark.parametrize("regime", ALL_REGIMES)
    def test_all_regimes_have_strategy_group_and_weight(self, regime):
        """Req 20.7: Each strategy entry must have strategy_group (str) and allocation_weight (float)."""
        result = map_regime_to_strategies(regime)
        for item in result:
            assert "strategy_group" in item
            assert "allocation_weight" in item
            assert isinstance(item["strategy_group"], str)
            assert isinstance(item["allocation_weight"], float)

    # ---- Req 20.1: trend_risk_on_growth includes 趋势ETF组 ----

    def test_trend_risk_on_growth_includes_trend_etf(self):
        """Req 20.1: trend_risk_on_growth must include '趋势ETF组'."""
        result = map_regime_to_strategies("trend_risk_on_growth")
        groups = [item["strategy_group"] for item in result]
        assert "趋势ETF组" in groups

    def test_trend_risk_on_growth_includes_sector_rotation(self):
        """Req 20.1: trend_risk_on_growth must include '行业轮动组'."""
        result = map_regime_to_strategies("trend_risk_on_growth")
        groups = [item["strategy_group"] for item in result]
        assert "行业轮动组" in groups

    def test_trend_risk_on_smallcap_includes_trend_etf(self):
        """Req 20.1: trend_risk_on_smallcap must include '趋势ETF组'."""
        result = map_regime_to_strategies("trend_risk_on_smallcap")
        groups = [item["strategy_group"] for item in result]
        assert "趋势ETF组" in groups

    # ---- Req 20.2: balanced_rotation includes 行业轮动组 ----

    def test_balanced_rotation_includes_sector_rotation(self):
        """Req 20.2: balanced_rotation must include '行业轮动组'."""
        result = map_regime_to_strategies("balanced_rotation")
        groups = [item["strategy_group"] for item in result]
        assert "行业轮动组" in groups

    def test_balanced_rotation_includes_dividend_value(self):
        """Req 20.2: balanced_rotation must include '红利价值组'."""
        result = map_regime_to_strategies("balanced_rotation")
        groups = [item["strategy_group"] for item in result]
        assert "红利价值组" in groups

    def test_balanced_rotation_includes_stock_bond_balance(self):
        """Req 20.2: balanced_rotation must include '股债平衡组'."""
        result = map_regime_to_strategies("balanced_rotation")
        groups = [item["strategy_group"] for item in result]
        assert "股债平衡组" in groups

    # ---- Req 20.3: defensive_dividend includes 红利价值组 ----

    def test_defensive_dividend_includes_dividend_value(self):
        """Req 20.3: defensive_dividend must include '红利价值组'."""
        result = map_regime_to_strategies("defensive_dividend")
        groups = [item["strategy_group"] for item in result]
        assert "红利价值组" in groups

    def test_defensive_dividend_includes_stock_bond_balance(self):
        """Req 20.3: defensive_dividend must include '股债平衡组'."""
        result = map_regime_to_strategies("defensive_dividend")
        groups = [item["strategy_group"] for item in result]
        assert "股债平衡组" in groups

    # ---- Req 20.4: high_volatility_warning includes 高现金配置 ----

    def test_high_volatility_warning_includes_high_cash(self):
        """Req 20.4: high_volatility_warning must include '高现金配置'."""
        result = map_regime_to_strategies("high_volatility_warning")
        groups = [item["strategy_group"] for item in result]
        assert "高现金配置" in groups

    def test_high_volatility_warning_includes_all_weather(self):
        """Req 20.4: high_volatility_warning must include '全天候组'."""
        result = map_regime_to_strategies("high_volatility_warning")
        groups = [item["strategy_group"] for item in result]
        assert "全天候组" in groups

    # ---- Req 20.5: panic_bottoming includes 趋势ETF组小仓试探 ----

    def test_panic_bottoming_includes_small_position_probe(self):
        """Req 20.5: panic_bottoming must include '趋势ETF组小仓试探'."""
        result = map_regime_to_strategies("panic_bottoming")
        groups = [item["strategy_group"] for item in result]
        assert "趋势ETF组小仓试探" in groups

    def test_panic_bottoming_includes_smallcap_observation(self):
        """Req 20.5: panic_bottoming must include '小市值观察'."""
        result = map_regime_to_strategies("panic_bottoming")
        groups = [item["strategy_group"] for item in result]
        assert "小市值观察" in groups

    # ---- Req 20.6: broad_weakness_hold includes 股债平衡组 ----

    def test_broad_weakness_hold_includes_stock_bond_balance(self):
        """Req 20.6: broad_weakness_hold must include '股债平衡组'."""
        result = map_regime_to_strategies("broad_weakness_hold")
        groups = [item["strategy_group"] for item in result]
        assert "股债平衡组" in groups

    def test_broad_weakness_hold_includes_all_weather(self):
        """Req 20.6: broad_weakness_hold must include '全天候组'."""
        result = map_regime_to_strategies("broad_weakness_hold")
        groups = [item["strategy_group"] for item in result]
        assert "全天候组" in groups

    def test_broad_weakness_hold_includes_high_cash(self):
        """Req 20.6: broad_weakness_hold must include '高现金配置'."""
        result = map_regime_to_strategies("broad_weakness_hold")
        groups = [item["strategy_group"] for item in result]
        assert "高现金配置" in groups

    # ---- Req 20.7: unknown regime returns empty list ----

    def test_unknown_regime_returns_empty_list(self):
        """Req 20.7: An unknown regime identifier must return an empty list."""
        result = map_regime_to_strategies("nonexistent_regime")
        assert result == []

    # ---- Allocation weight sanity checks ----

    @pytest.mark.parametrize("regime", ALL_REGIMES)
    def test_all_weights_are_positive(self, regime):
        """Req 20.7: All allocation weights must be strictly positive."""
        result = map_regime_to_strategies(regime)
        for item in result:
            assert item["allocation_weight"] > 0, (
                f"Weight for '{item['strategy_group']}' in '{regime}' must be > 0"
            )

    @pytest.mark.parametrize("regime", ALL_REGIMES)
    def test_all_weights_are_at_most_one(self, regime):
        """Req 20.7: No single allocation weight should exceed 1.0."""
        result = map_regime_to_strategies(regime)
        for item in result:
            assert item["allocation_weight"] <= 1.0, (
                f"Weight for '{item['strategy_group']}' in '{regime}' exceeds 1.0"
            )

    # ---- Strategy groups are non-empty strings ----

    @pytest.mark.parametrize("regime", ALL_REGIMES)
    def test_strategy_group_names_are_non_empty(self, regime):
        """Req 20.7: Strategy group names must be non-empty strings."""
        result = map_regime_to_strategies(regime)
        for item in result:
            assert len(item["strategy_group"]) > 0, (
                f"Empty strategy_group name found in regime '{regime}'"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
