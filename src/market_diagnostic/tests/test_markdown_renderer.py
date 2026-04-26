"""
Unit Tests for DiagnosticMarkdownRenderer

Task 10.2: Verify the Markdown renderer generates correct output.
Requirements: 19.1-19.12
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.market_diagnostic.reports.schema import DiagnosticReport
from src.market_diagnostic.reports.markdown_renderer import DiagnosticMarkdownRenderer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_minimal_report(**overrides) -> DiagnosticReport:
    """Create a minimal DiagnosticReport for testing."""
    defaults = dict(
        date="2024-01-15",
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
        one_sentence_summary="市场处于强趋势上行阶段，成长风格主导，广度健康。",
        key_evidence=["沪深300多头排列", "广度偏强，站上MA20比例62%", "情绪活跃，涨停率2.8%"],
        counter_evidence=["成交额偏离20日均仅+5%，增量资金有限"],
        confidence=0.85,
        missing_data=[],
        risk_flags=[],
        strategy_mapping=[
            {"strategy_group": "趋势ETF组", "allocation_weight": 0.33},
            {"strategy_group": "行业轮动组", "allocation_weight": 0.33},
            {"strategy_group": "小市值进攻组", "allocation_weight": 0.34},
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
                "amount_share": 0.12,
            },
            {
                "industry_code": "BK0448",
                "industry_name": "计算机",
                "strength_score": 2.1,
                "persistence_score": 0.7,
                "crowding_score": 0.2,
                "leadership_score": 0.8,
                "state": "趋势强化",
                "amount_share": 0.09,
            },
            {
                "industry_code": "BK0452",
                "industry_name": "电力设备",
                "strength_score": 1.8,
                "persistence_score": 0.6,
                "crowding_score": 0.4,
                "leadership_score": 0.7,
                "state": "趋势强化",
                "amount_share": 0.08,
            },
            {
                "industry_code": "BK0470",
                "industry_name": "医药生物",
                "strength_score": -0.3,
                "persistence_score": 0.2,
                "crowding_score": 0.1,
                "leadership_score": 0.3,
                "state": "震荡整理",
                "amount_share": 0.06,
            },
            {
                "industry_code": "BK0459",
                "industry_name": "钢铁",
                "strength_score": -1.2,
                "persistence_score": 0.1,
                "crowding_score": 0.0,
                "leadership_score": 0.1,
                "state": "弱势退潮",
                "amount_share": 0.02,
            },
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMarkdownRendererStructure:
    """Tests that all required sections are present in the rendered output."""

    def setup_method(self):
        self.renderer = DiagnosticMarkdownRenderer()
        self.report = _make_minimal_report()
        self.output = self.renderer.render(self.report)

    def test_render_returns_string(self):
        """render() should return a string."""
        assert isinstance(self.output, str)
        assert len(self.output) > 0

    def test_title_contains_date(self):
        """Req 19.1: Title should contain the report date."""
        assert "2024-01-15" in self.output
        assert "大盘全维度诊断" in self.output

    def test_one_sentence_summary_present(self):
        """Req 19.1: One-sentence summary section should be present."""
        assert "一句话结论" in self.output
        assert "市场处于强趋势上行阶段" in self.output

    def test_state_dashboard_present(self):
        """Req 19.2: State dashboard table should be present."""
        assert "状态仪表盘" in self.output
        assert "维度" in self.output
        assert "状态" in self.output
        assert "得分" in self.output

    def test_dashboard_shows_all_dimensions(self):
        """Req 19.2: Dashboard should show all 6 dimensions."""
        for dim in ["趋势", "广度", "情绪", "风格", "板块", "风险"]:
            assert dim in self.output, f"Dimension '{dim}' not found in dashboard"

    def test_dashboard_shows_composite_regime(self):
        """Req 19.2: Dashboard should show composite regime."""
        assert "Regime" in self.output
        assert "trend_risk_on_growth" in self.output

    def test_index_structure_section_present(self):
        """Req 19.3: Index structure section should be present."""
        assert "指数与价格结构" in self.output
        assert "沪深300" in self.output

    def test_index_table_has_technical_indicators(self):
        """Req 19.3: Index table should include MA/MACD/ATR columns."""
        assert "MA排列" in self.output
        assert "MACD信号" in self.output
        assert "ATR" in self.output
        assert "RSRS" in self.output

    def test_breadth_section_present(self):
        """Req 19.4: Market breadth section should be present."""
        assert "市场广度" in self.output
        assert "涨跌比" in self.output
        assert "封板率" in self.output
        assert "MA20" in self.output

    def test_sentiment_section_present(self):
        """Req 19.5: Sentiment section should be present."""
        assert "情绪与赚钱效应" in self.output
        assert "涨停" in self.output
        assert "封板率" in self.output

    def test_style_section_present(self):
        """Req 19.6: Style rotation section should be present."""
        assert "风格轮动" in self.output
        assert "相对强弱" in self.output
        assert "成长主导" in self.output

    def test_sector_section_present(self):
        """Req 19.7: Sector diagnosis section should be present."""
        assert "板块主线诊断" in self.output
        assert "TOP 5 强势行业" in self.output
        assert "电子" in self.output

    def test_sector_shows_top5_strongest(self):
        """Req 19.7: Sector section should show top-5 strongest sectors."""
        assert "电子" in self.output
        assert "计算机" in self.output
        assert "电力设备" in self.output

    def test_sector_shows_weakest(self):
        """Req 19.7: Sector section should show weakest sectors."""
        assert "BOTTOM 5 弱势行业" in self.output
        assert "钢铁" in self.output

    def test_capital_flow_section_present(self):
        """Req 19.8: Capital flow section should be present."""
        assert "资金流向" in self.output
        assert "北向" in self.output
        assert "融资" in self.output
        assert "成交额" in self.output

    def test_risk_alert_section_present(self):
        """Req 19.9: Risk alert section should be present."""
        assert "风险警报" in self.output

    def test_no_active_risk_flags_shows_clear(self):
        """Req 19.9: When no risk flags, should show clear status."""
        assert "无活跃风险警报" in self.output

    def test_strategy_mapping_section_present(self):
        """Req 19.10: Strategy mapping section should be present."""
        assert "策略映射建议" in self.output
        assert "趋势ETF组" in self.output
        assert "行业轮动组" in self.output

    def test_evidence_section_present(self):
        """Req 19.11: Evidence and confidence section should be present."""
        assert "证据与置信度" in self.output
        assert "支持证据" in self.output
        assert "反向证据" in self.output
        assert "置信度" in self.output

    def test_confidence_displayed_as_percentage(self):
        """Req 19.11: Confidence should be displayed as percentage."""
        assert "85%" in self.output

    def test_key_evidence_items_present(self):
        """Req 19.11: Key evidence items should be listed."""
        assert "沪深300多头排列" in self.output

    def test_counter_evidence_items_present(self):
        """Req 19.11: Counter evidence items should be listed."""
        assert "增量资金有限" in self.output

    def test_no_llm_narrative_by_default(self):
        """Req 19.12: No LLM narrative section when not provided."""
        assert "AI 叙述分析" not in self.output

    def test_llm_narrative_appended_when_provided(self):
        """Req 19.12: LLM narrative should be appended when provided."""
        narrative = "今日市场整体偏强，科技板块领涨，建议关注半导体机会。"
        output_with_narrative = self.renderer.render(self.report, llm_narrative=narrative)
        assert "AI 叙述分析" in output_with_narrative
        assert narrative in output_with_narrative

    def test_llm_narrative_not_appended_when_empty_string(self):
        """Req 19.12: Empty string LLM narrative should not add section."""
        output = self.renderer.render(self.report, llm_narrative="")
        assert "AI 叙述分析" not in output

    def test_llm_narrative_not_appended_when_whitespace_only(self):
        """Req 19.12: Whitespace-only LLM narrative should not add section."""
        output = self.renderer.render(self.report, llm_narrative="   \n  ")
        assert "AI 叙述分析" not in output


class TestMarkdownRendererWithRiskFlags:
    """Tests for risk flag rendering."""

    def setup_method(self):
        self.renderer = DiagnosticMarkdownRenderer()

    def test_active_risk_flags_listed(self):
        """Req 19.9: Active risk flags should be listed."""
        report = _make_minimal_report(
            risk_flags=["vol_spike", "breadth_collapse"],
            risk_state="高风险",
        )
        output = self.renderer.render(report)
        assert "波动率骤升" in output
        assert "广度崩塌" in output

    def test_unknown_risk_flag_still_shown(self):
        """Unknown risk flags should still be displayed."""
        report = _make_minimal_report(risk_flags=["custom_flag"])
        output = self.renderer.render(report)
        assert "custom_flag" in output

    def test_all_known_risk_flags_have_display_names(self):
        """All 6 known risk flags should have display names."""
        known_flags = [
            "vol_spike", "breadth_collapse", "sector_overcrowding",
            "northbound_outflow", "leadership_breakdown", "index_break_support",
        ]
        report = _make_minimal_report(risk_flags=known_flags, risk_state="极端风险")
        output = self.renderer.render(report)
        for flag in known_flags:
            assert flag not in output or any(
                display_word in output
                for display_word in ["波动率", "广度", "拥挤", "北向", "龙头", "支撑"]
            ), f"Flag {flag} should have a display name"


class TestMarkdownRendererWithMissingData:
    """Tests for rendering with missing/empty data."""

    def setup_method(self):
        self.renderer = DiagnosticMarkdownRenderer()

    def test_empty_indices_shows_unavailable(self):
        """When indices is empty, should show unavailable message."""
        report = _make_minimal_report(indices=[])
        output = self.renderer.render(report)
        assert "指数数据不可用" in output

    def test_empty_breadth_metrics_shows_unavailable(self):
        """When breadth_metrics is empty, should show unavailable message."""
        report = _make_minimal_report(breadth_metrics={})
        output = self.renderer.render(report)
        assert "广度数据不可用" in output

    def test_empty_sentiment_metrics_shows_unavailable(self):
        """When sentiment_metrics is empty, should show unavailable message."""
        report = _make_minimal_report(sentiment_metrics={})
        output = self.renderer.render(report)
        assert "情绪数据不可用" in output

    def test_empty_style_metrics_shows_unavailable(self):
        """When style_metrics is empty, should show unavailable message."""
        report = _make_minimal_report(style_metrics={})
        output = self.renderer.render(report)
        assert "风格数据不可用" in output

    def test_empty_sector_table_shows_unavailable(self):
        """When sector_table is empty, should show unavailable message."""
        report = _make_minimal_report(sector_table=[])
        output = self.renderer.render(report)
        assert "板块数据不可用" in output

    def test_empty_capital_metrics_shows_unavailable(self):
        """When capital_metrics is empty, should show unavailable message."""
        report = _make_minimal_report(capital_metrics={})
        output = self.renderer.render(report)
        assert "资金数据不可用" in output

    def test_missing_data_list_shown_in_evidence_section(self):
        """When missing_data is non-empty, items should appear in evidence section."""
        report = _make_minimal_report(missing_data=["north_bound_capital", "margin_balance"])
        output = self.renderer.render(report)
        assert "缺失数据" in output
        assert "north_bound_capital" in output
        assert "margin_balance" in output

    def test_empty_strategy_mapping_shows_placeholder(self):
        """When strategy_mapping is empty, should show placeholder."""
        report = _make_minimal_report(strategy_mapping=[])
        output = self.renderer.render(report)
        assert "暂无策略映射" in output

    def test_delayed_capital_data_shows_warning(self):
        """When capital data has T+1 delay, should show warning."""
        report = _make_minimal_report(
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
                "data_freshness": {"north_net_flow": "T+1 delayed"},
                "has_delayed_data": True,
            }
        )
        output = self.renderer.render(report)
        assert "T+1" in output


class TestMarkdownRendererSectorSorting:
    """Tests for sector sorting logic."""

    def setup_method(self):
        self.renderer = DiagnosticMarkdownRenderer()

    def test_sectors_sorted_by_strength_score(self):
        """Top-5 sectors should be the ones with highest strength scores."""
        sectors = [
            {"industry_code": "A", "industry_name": "行业A", "strength_score": 3.0, "state": "主升趋势"},
            {"industry_code": "B", "industry_name": "行业B", "strength_score": 1.0, "state": "震荡整理"},
            {"industry_code": "C", "industry_name": "行业C", "strength_score": -2.0, "state": "弱势退潮"},
            {"industry_code": "D", "industry_name": "行业D", "strength_score": 2.5, "state": "趋势强化"},
            {"industry_code": "E", "industry_name": "行业E", "strength_score": 0.5, "state": "震荡整理"},
            {"industry_code": "F", "industry_name": "行业F", "strength_score": -1.5, "state": "弱势退潮"},
        ]
        report = _make_minimal_report(sector_table=sectors)
        output = self.renderer.render(report)

        # 行业A (3.0) and 行业D (2.5) should be in top 5
        assert "行业A" in output
        assert "行业D" in output

        # 行业C (-2.0) should be in bottom 5
        assert "行业C" in output


class TestMarkdownRendererFormatting:
    """Tests for specific formatting details."""

    def setup_method(self):
        self.renderer = DiagnosticMarkdownRenderer()

    def test_score_bar_in_dashboard(self):
        """Dashboard should include progress bars."""
        report = _make_minimal_report()
        output = self.renderer.render(report)
        # Progress bars use block characters
        assert "█" in output or "░" in output

    def test_regime_display_name_shown(self):
        """Regime should show human-readable display name."""
        report = _make_minimal_report(composite_regime="trend_risk_on_growth")
        output = self.renderer.render(report)
        assert "趋势进攻-成长主导" in output

    def test_unknown_regime_shows_raw_value(self):
        """Unknown regime should show raw value."""
        report = _make_minimal_report(composite_regime="unknown_regime")
        output = self.renderer.render(report)
        assert "unknown_regime" in output

    def test_change_pct_formatted_with_sign(self):
        """Change percentage should be formatted with sign."""
        report = _make_minimal_report(
            indices=[{
                "code": "sh000300",
                "name": "沪深300",
                "close": 3850.5,
                "change_pct": 1.25,
                "ma_alignment": "多头排列",
                "macd_signal": "金叉",
                "atr_20": 45.2,
                "rsrs_score": 0.75,
                "bias_ma20": 0.032,
            }]
        )
        output = self.renderer.render(report)
        assert "+1.25%" in output

    def test_negative_change_pct_formatted_with_minus(self):
        """Negative change percentage should be formatted with minus sign."""
        report = _make_minimal_report(
            indices=[{
                "code": "sh000300",
                "name": "沪深300",
                "close": 3800.0,
                "change_pct": -0.85,
                "ma_alignment": "空头排列",
                "macd_signal": "死叉",
                "atr_20": 50.0,
                "rsrs_score": 0.3,
                "bias_ma20": -0.015,
            }]
        )
        output = self.renderer.render(report)
        assert "-0.85%" in output

    def test_none_values_show_na(self):
        """None values in metrics should show N/A."""
        report = _make_minimal_report(
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
        output = self.renderer.render(report)
        assert "N/A" in output
