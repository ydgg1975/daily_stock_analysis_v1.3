"""
Property-Based Tests for Report Generation

Task 10.4: Write property tests for report generation
- Property 46: JSON Output Structure Completeness
  Validates: Requirements 18.1-18.10
- Property 47: Markdown Report Structure Completeness
  Validates: Requirements 19.1-19.11
- Property 48: Strategy Mapping Correctness
  Validates: Requirements 20.1-20.7
"""

import json
import math
import sys
import os

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.market_diagnostic.reports.schema import DiagnosticReport
from src.market_diagnostic.reports.markdown_renderer import DiagnosticMarkdownRenderer
from src.market_diagnostic.reports.strategy_mapper import map_regime_to_strategies, get_all_regimes


# ---------------------------------------------------------------------------
# Shared renderer instance
# ---------------------------------------------------------------------------

_renderer = DiagnosticMarkdownRenderer()


# ---------------------------------------------------------------------------
# Strategy generators
# ---------------------------------------------------------------------------

_VALID_TREND_STATES = ["强趋势上行", "趋势上行中的回调", "震荡", "趋势转弱", "破位下行"]
_VALID_BREADTH_STATES = ["极弱", "偏弱", "中性", "偏强", "过热"]
_VALID_SENTIMENT_STATES = ["冰点", "回暖", "中性", "活跃", "狂热"]
_VALID_STYLE_STATES = ["大盘防守", "小盘进攻", "成长主导", "红利防守", "风格冲突"]
_VALID_SECTOR_STATES = ["无主线", "单主线", "双主线并行", "高速轮动", "退潮分化"]
_VALID_RISK_STATES = ["低风险", "中性风险", "高风险", "极端风险"]
_VALID_REGIMES = [
    "trend_risk_on_growth",
    "trend_risk_on_smallcap",
    "balanced_rotation",
    "defensive_dividend",
    "high_volatility_warning",
    "panic_bottoming",
    "broad_weakness_hold",
]

_REQUIRED_JSON_FIELDS = {
    "date",
    "trend_state",
    "breadth_state",
    "sentiment_state",
    "style_state",
    "sector_state",
    "risk_state",
    "composite_regime",
    "trend_score",
    "breadth_score",
    "sentiment_score",
    "risk_score",
    "regime_score",
    "indices",
    "breadth_metrics",
    "sentiment_metrics",
    "style_metrics",
    "sector_table",
    "capital_metrics",
    "risk_flags",
    "key_evidence",
    "counter_evidence",
    "confidence",
    "missing_data",
}

_REQUIRED_MARKDOWN_SECTIONS = [
    "一句话结论",
    "状态仪表盘",
    "指数与价格结构",
    "市场广度",
    "情绪与赚钱效应",
    "风格轮动",
    "板块主线诊断",
    "资金流向",
    "风险警报",
    "策略映射建议",
    "证据与置信度",
]


@st.composite
def diagnostic_report_strategy(draw):
    """
    Generate a valid DiagnosticReport with arbitrary but well-formed data.

    Produces reports with all required fields populated, covering the full
    range of valid state combinations.
    """
    score = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    confidence = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    small_float = st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    non_neg_float = st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False)
    date_str = draw(st.dates()).strftime("%Y-%m-%d")

    # Optional list fields
    risk_flags = draw(st.lists(
        st.sampled_from([
            "vol_spike", "breadth_collapse", "sector_overcrowding",
            "northbound_outflow", "leadership_breakdown", "index_break_support",
        ]),
        max_size=6,
        unique=True,
    ))
    key_evidence = draw(st.lists(st.text(min_size=1, max_size=30), max_size=5))
    counter_evidence = draw(st.lists(st.text(min_size=1, max_size=30), max_size=3))
    missing_data = draw(st.lists(st.text(min_size=1, max_size=20), max_size=5))

    return DiagnosticReport(
        date=date_str,
        trend_state=draw(st.sampled_from(_VALID_TREND_STATES)),
        breadth_state=draw(st.sampled_from(_VALID_BREADTH_STATES)),
        sentiment_state=draw(st.sampled_from(_VALID_SENTIMENT_STATES)),
        style_state=draw(st.sampled_from(_VALID_STYLE_STATES)),
        sector_state=draw(st.sampled_from(_VALID_SECTOR_STATES)),
        risk_state=draw(st.sampled_from(_VALID_RISK_STATES)),
        composite_regime=draw(st.sampled_from(_VALID_REGIMES)),
        trend_score=draw(score),
        breadth_score=draw(score),
        sentiment_score=draw(score),
        risk_score=draw(score),
        regime_score=draw(score),
        style_score=draw(score),
        sector_score=draw(score),
        indices=draw(st.lists(
            st.fixed_dictionaries({
                "code": st.sampled_from(["sh000001", "sz399001", "sh000300"]),
                "name": st.sampled_from(["上证指数", "深证成指", "沪深300"]),
                "close": st.floats(min_value=100.0, max_value=10000.0, allow_nan=False),
                "change_pct": st.floats(min_value=-10.0, max_value=10.0, allow_nan=False),
                "ma_alignment": st.sampled_from(["多头排列", "空头排列", "缠绕"]),
                "macd_signal": st.sampled_from(["金叉", "死叉", "中性"]),
                "atr_20": st.floats(min_value=0.0, max_value=200.0, allow_nan=False),
                "rsrs_score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
                "bias_ma20": st.floats(min_value=-0.2, max_value=0.2, allow_nan=False),
            }),
            max_size=9,
        )),
        breadth_metrics=draw(st.fixed_dictionaries({
            "up_down_ratio": st.floats(min_value=0.0, max_value=10.0, allow_nan=False),
            "limit_up_rate": st.floats(min_value=0.0, max_value=0.1, allow_nan=False),
            "seal_rate": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            "above_ma20_ratio": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            "above_ma60_ratio": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            "new_high_ratio": st.floats(min_value=0.0, max_value=0.1, allow_nan=False),
            "amount_deviation_5d": st.floats(min_value=-0.5, max_value=1.0, allow_nan=False),
            "amount_deviation_20d": st.floats(min_value=-0.5, max_value=1.0, allow_nan=False),
            "breadth_score": st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        })),
        sentiment_metrics=draw(st.fixed_dictionaries({
            "limit_up_down_ratio": st.floats(min_value=0.0, max_value=20.0, allow_nan=False),
            "continuous_limit_up": st.integers(min_value=0, max_value=200),
            "seal_rate": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            "next_day_premium": st.floats(min_value=-0.1, max_value=0.1, allow_nan=False),
            "turnover_zscore": st.floats(min_value=-3.0, max_value=3.0, allow_nan=False),
            "sentiment_score": st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        })),
        style_metrics=draw(st.fixed_dictionaries({
            "rs_large_vs_small": st.floats(min_value=0.5, max_value=2.0, allow_nan=False),
            "rs_300_vs_1000": st.floats(min_value=0.5, max_value=2.0, allow_nan=False),
            "rs_500_vs_1000": st.floats(min_value=0.5, max_value=2.0, allow_nan=False),
            "ret_1d": st.just({}),
            "ret_5d": st.just({}),
            "ret_20d": st.just({}),
            "amount_share": st.just({}),
            "dominant_style": st.sampled_from(_VALID_STYLE_STATES),
        })),
        sector_table=draw(st.lists(
            st.fixed_dictionaries({
                "industry_code": st.text(min_size=6, max_size=6, alphabet="BK0123456789"),
                "industry_name": st.sampled_from(["电子", "计算机", "医药生物", "钢铁", "食品饮料"]),
                "strength_score": st.floats(min_value=-3.0, max_value=3.0, allow_nan=False),
                "persistence_score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
                "crowding_score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
                "leadership_score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
                "state": st.sampled_from(["主升趋势", "趋势强化", "震荡整理", "超跌反弹", "弱势退潮"]),
            }),
            max_size=10,
        )),
        capital_metrics=draw(st.fixed_dictionaries({
            "total_amount": st.floats(min_value=0.0, max_value=20000.0, allow_nan=False),
            "amount_deviation_5d": st.floats(min_value=-0.5, max_value=1.0, allow_nan=False),
            "amount_deviation_20d": st.floats(min_value=-0.5, max_value=1.0, allow_nan=False),
            "amount_deviation_60d": st.floats(min_value=-0.5, max_value=1.0, allow_nan=False),
            "north_net_flow": st.floats(min_value=-500.0, max_value=500.0, allow_nan=False),
            "north_5d_avg": st.floats(min_value=-200.0, max_value=200.0, allow_nan=False),
            "north_flow_trend": st.sampled_from(["inflow", "outflow", "neutral"]),
            "margin_balance": st.floats(min_value=10000.0, max_value=30000.0, allow_nan=False),
            "margin_delta": st.floats(min_value=-500.0, max_value=500.0, allow_nan=False),
            "main_net_flow": st.floats(min_value=-500.0, max_value=500.0, allow_nan=False),
            "etf_net_flow": st.floats(min_value=-200.0, max_value=200.0, allow_nan=False),
            "data_freshness": st.just({}),
            "has_delayed_data": st.booleans(),
        })),
        risk_flags=risk_flags,
        one_sentence_summary=draw(st.text(min_size=0, max_size=50)),
        key_evidence=key_evidence,
        counter_evidence=counter_evidence,
        strategy_mapping=draw(st.lists(
            st.fixed_dictionaries({
                "strategy_group": st.text(min_size=1, max_size=20),
                "allocation_weight": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            }),
            max_size=5,
        )),
        confidence=draw(confidence),
        missing_data=missing_data,
    )


# ---------------------------------------------------------------------------
# Property 46: JSON Output Structure Completeness
# Validates: Requirements 18.1-18.10
# ---------------------------------------------------------------------------

@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_46_json_output_is_valid_json(report):
    """
    **Property 46: JSON Output Structure Completeness**
    **Validates: Requirements 18.1-18.10**

    For any valid DiagnosticReport, to_json() must return a valid JSON string.
    """
    json_str = report.to_json()

    # Must return a non-empty string
    assert isinstance(json_str, str)
    assert len(json_str) > 0

    # Must be parseable as JSON
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_46_json_contains_all_required_fields(report):
    """
    **Property 46: JSON Output Structure Completeness**
    **Validates: Requirements 18.1-18.10**

    For any valid DiagnosticReport, to_json() must contain all required fields:
    date, trend_state, breadth_state, sentiment_state, style_state, sector_state,
    risk_state, composite_regime, trend_score, breadth_score, sentiment_score,
    risk_score, regime_score, indices, breadth_metrics, sentiment_metrics,
    style_metrics, sector_table, capital_metrics, risk_flags, key_evidence,
    counter_evidence, confidence, missing_data.
    """
    json_str = report.to_json()
    parsed = json.loads(json_str)

    missing = _REQUIRED_JSON_FIELDS - set(parsed.keys())
    assert not missing, f"JSON output missing required fields: {missing}"


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_46_json_state_fields_are_strings(report):
    """
    **Property 46: JSON Output Structure Completeness**
    **Validates: Requirement 18.1**

    All state classification fields in JSON output must be strings.
    """
    parsed = json.loads(report.to_json())

    state_fields = [
        "trend_state", "breadth_state", "sentiment_state",
        "style_state", "sector_state", "risk_state", "composite_regime",
    ]
    for field in state_fields:
        assert isinstance(parsed[field], str), \
            f"Field '{field}' should be a string, got {type(parsed[field])}"


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_46_json_score_fields_are_numeric(report):
    """
    **Property 46: JSON Output Structure Completeness**
    **Validates: Requirement 18.1**

    All score fields in JSON output must be numeric (int or float).
    """
    parsed = json.loads(report.to_json())

    score_fields = [
        "trend_score", "breadth_score", "sentiment_score",
        "risk_score", "regime_score",
    ]
    for field in score_fields:
        assert isinstance(parsed[field], (int, float)), \
            f"Field '{field}' should be numeric, got {type(parsed[field])}"


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_46_json_list_fields_are_lists(report):
    """
    **Property 46: JSON Output Structure Completeness**
    **Validates: Requirements 18.2, 18.6, 18.8, 18.9, 18.10**

    List fields in JSON output must be arrays.
    """
    parsed = json.loads(report.to_json())

    list_fields = ["indices", "sector_table", "risk_flags", "key_evidence",
                   "counter_evidence", "missing_data"]
    for field in list_fields:
        assert isinstance(parsed[field], list), \
            f"Field '{field}' should be a list, got {type(parsed[field])}"


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_46_json_dict_fields_are_objects(report):
    """
    **Property 46: JSON Output Structure Completeness**
    **Validates: Requirements 18.3, 18.4, 18.5, 18.7**

    Dict fields in JSON output must be JSON objects.
    """
    parsed = json.loads(report.to_json())

    dict_fields = ["breadth_metrics", "sentiment_metrics", "style_metrics", "capital_metrics"]
    for field in dict_fields:
        assert isinstance(parsed[field], dict), \
            f"Field '{field}' should be a dict, got {type(parsed[field])}"


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_46_json_confidence_is_float(report):
    """
    **Property 46: JSON Output Structure Completeness**
    **Validates: Requirement 18.9**

    The confidence field in JSON output must be a float.
    """
    parsed = json.loads(report.to_json())
    assert isinstance(parsed["confidence"], (int, float)), \
        f"confidence should be numeric, got {type(parsed['confidence'])}"


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_46_json_roundtrip_preserves_date(report):
    """
    **Property 46: JSON Output Structure Completeness**
    **Validates: Requirement 18.1**

    The date field must survive JSON serialization unchanged.
    """
    parsed = json.loads(report.to_json())
    assert parsed["date"] == report.date


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_46_json_roundtrip_preserves_regime(report):
    """
    **Property 46: JSON Output Structure Completeness**
    **Validates: Requirement 18.1**

    The composite_regime field must survive JSON serialization unchanged.
    """
    parsed = json.loads(report.to_json())
    assert parsed["composite_regime"] == report.composite_regime


# ---------------------------------------------------------------------------
# Property 47: Markdown Report Structure Completeness
# Validates: Requirements 19.1-19.11
# ---------------------------------------------------------------------------

@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_47_markdown_returns_non_empty_string(report):
    """
    **Property 47: Markdown Report Structure Completeness**
    **Validates: Requirements 19.1-19.11**

    For any valid DiagnosticReport, render() must return a non-empty string.
    """
    output = _renderer.render(report)

    assert isinstance(output, str)
    assert len(output) > 0


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_47_markdown_contains_all_required_sections(report):
    """
    **Property 47: Markdown Report Structure Completeness**
    **Validates: Requirements 19.1-19.11**

    For any valid DiagnosticReport, render() must contain all required section headers:
    一句话结论, 状态仪表盘, 指数与价格结构, 市场广度, 情绪与赚钱效应, 风格轮动,
    板块主线诊断, 资金流向, 风险警报, 策略映射建议, 证据与置信度.
    """
    output = _renderer.render(report)

    for section in _REQUIRED_MARKDOWN_SECTIONS:
        assert section in output, \
            f"Required section '{section}' not found in Markdown output"


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_47_markdown_contains_date(report):
    """
    **Property 47: Markdown Report Structure Completeness**
    **Validates: Requirement 19.1**

    The rendered Markdown must contain the report date.
    """
    output = _renderer.render(report)
    assert report.date in output, \
        f"Date '{report.date}' not found in Markdown output"


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_47_markdown_contains_composite_regime(report):
    """
    **Property 47: Markdown Report Structure Completeness**
    **Validates: Requirement 19.2**

    The rendered Markdown must contain the composite regime identifier.
    """
    output = _renderer.render(report)
    assert report.composite_regime in output, \
        f"Composite regime '{report.composite_regime}' not found in Markdown output"


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_47_markdown_contains_all_state_values(report):
    """
    **Property 47: Markdown Report Structure Completeness**
    **Validates: Requirement 19.2**

    The rendered Markdown dashboard must contain all six dimension state values.
    """
    output = _renderer.render(report)

    for state_value in [
        report.trend_state,
        report.breadth_state,
        report.sentiment_state,
        report.style_state,
        report.sector_state,
        report.risk_state,
    ]:
        assert state_value in output, \
            f"State value '{state_value}' not found in Markdown output"


@given(report=diagnostic_report_strategy())
@settings(max_examples=50)
def test_property_47_markdown_section_order_is_correct(report):
    """
    **Property 47: Markdown Report Structure Completeness**
    **Validates: Requirements 19.1-19.11**

    Required sections must appear in the correct order in the Markdown output.
    """
    output = _renderer.render(report)

    positions = [output.find(section) for section in _REQUIRED_MARKDOWN_SECTIONS]

    # All sections must be present
    for i, (section, pos) in enumerate(zip(_REQUIRED_MARKDOWN_SECTIONS, positions)):
        assert pos >= 0, f"Section '{section}' not found in output"

    # Sections must appear in order
    for i in range(len(positions) - 1):
        assert positions[i] < positions[i + 1], (
            f"Section '{_REQUIRED_MARKDOWN_SECTIONS[i]}' (pos {positions[i]}) "
            f"must appear before '{_REQUIRED_MARKDOWN_SECTIONS[i+1]}' (pos {positions[i+1]})"
        )


# ---------------------------------------------------------------------------
# Property 48: Strategy Mapping Correctness
# Validates: Requirements 20.1-20.7
# ---------------------------------------------------------------------------

@given(regime=st.sampled_from(_VALID_REGIMES))
def test_property_48_strategy_mapping_returns_list_of_dicts(regime):
    """
    **Property 48: Strategy Mapping Correctness**
    **Validates: Requirements 20.1-20.7**

    map_regime_to_strategies() must return a list of dicts for any valid regime.
    """
    result = map_regime_to_strategies(regime)

    assert isinstance(result, list), \
        f"map_regime_to_strategies('{regime}') should return a list"
    assert len(result) > 0, \
        f"map_regime_to_strategies('{regime}') should return a non-empty list"

    for item in result:
        assert isinstance(item, dict), \
            f"Each item in strategy mapping should be a dict, got {type(item)}"


@given(regime=st.sampled_from(_VALID_REGIMES))
def test_property_48_strategy_mapping_dicts_have_required_keys(regime):
    """
    **Property 48: Strategy Mapping Correctness**
    **Validates: Requirements 20.1-20.7**

    Each dict in the strategy mapping must have 'strategy_group' (str)
    and 'allocation_weight' (float) keys.
    """
    result = map_regime_to_strategies(regime)

    for item in result:
        assert "strategy_group" in item, \
            f"Strategy mapping item missing 'strategy_group' key: {item}"
        assert "allocation_weight" in item, \
            f"Strategy mapping item missing 'allocation_weight' key: {item}"

        assert isinstance(item["strategy_group"], str), \
            f"'strategy_group' should be str, got {type(item['strategy_group'])}"
        assert isinstance(item["allocation_weight"], float), \
            f"'allocation_weight' should be float, got {type(item['allocation_weight'])}"


@given(regime=st.sampled_from(_VALID_REGIMES))
def test_property_48_allocation_weights_sum_to_one(regime):
    """
    **Property 48: Strategy Mapping Correctness**
    **Validates: Requirement 20.7**

    Allocation weights for any valid regime must sum to 1.0 within floating
    point tolerance.
    """
    result = map_regime_to_strategies(regime)

    total = sum(item["allocation_weight"] for item in result)
    assert math.isclose(total, 1.0, abs_tol=1e-9), \
        f"Allocation weights for '{regime}' sum to {total}, expected 1.0"


@given(regime=st.sampled_from(_VALID_REGIMES))
def test_property_48_all_regimes_return_non_empty_lists(regime):
    """
    **Property 48: Strategy Mapping Correctness**
    **Validates: Requirements 20.1-20.7**

    All 7 valid composite regimes must return non-empty strategy lists.
    """
    result = map_regime_to_strategies(regime)
    assert len(result) > 0, \
        f"Regime '{regime}' returned empty strategy list"


def test_property_48_all_seven_regimes_covered():
    """
    **Property 48: Strategy Mapping Correctness**
    **Validates: Requirements 20.1-20.7**

    All 7 composite regimes must be supported by the strategy mapper.
    """
    all_regimes = get_all_regimes()
    assert len(all_regimes) == 7, \
        f"Expected 7 regimes, got {len(all_regimes)}: {all_regimes}"

    for regime in _VALID_REGIMES:
        assert regime in all_regimes, \
            f"Regime '{regime}' not found in get_all_regimes()"


@given(regime=st.sampled_from(_VALID_REGIMES))
def test_property_48_allocation_weights_are_positive(regime):
    """
    **Property 48: Strategy Mapping Correctness**
    **Validates: Requirement 20.7**

    Each allocation weight must be strictly positive (> 0).
    """
    result = map_regime_to_strategies(regime)

    for item in result:
        assert item["allocation_weight"] > 0, \
            f"Allocation weight for '{item['strategy_group']}' in regime '{regime}' " \
            f"should be positive, got {item['allocation_weight']}"


def test_property_48_unknown_regime_returns_empty_list():
    """
    **Property 48: Strategy Mapping Correctness**
    **Validates: Requirement 20.7**

    An unknown regime identifier must return an empty list (graceful handling).
    """
    result = map_regime_to_strategies("unknown_regime_xyz")
    assert result == [], \
        f"Unknown regime should return empty list, got {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
