from types import SimpleNamespace
from unittest.mock import patch


def test_futures_prompt_uses_futures_specific_constraints():
    from src.analyzer import GeminiAnalyzer

    context = {
        "asset_type": "futures",
        "code": "RB",
        "stock_name": "螺纹钢主力",
        "date": "2026-05-07",
        "today": {"close": 3500, "open": 3480, "high": 3520, "low": 3460, "volume": 10000},
        "yesterday": {"close": 3470, "volume": 9000},
        "trend_analysis": {"trend_status": "多头排列", "buy_signal": "买入", "signal_score": 70},
    }

    analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
    with (
        patch.object(GeminiAnalyzer, "_get_runtime_config", return_value=SimpleNamespace(news_max_age_days=3)),
        patch.object(GeminiAnalyzer, "_get_skill_prompt_sections", return_value=("", "", False)),
    ):
        prompt = analyzer._format_prompt(context, "螺纹钢主力", report_language="zh")

    assert "国内商品期货主力连续合约" in prompt
    assert "多空趋势" in prompt
    assert "保证金" in prompt
    assert "不要使用股票专属概念" in prompt
    assert "PE/PB" in prompt


def test_futures_prompt_maps_trade_decision_to_long_short_semantics():
    from src.analyzer import GeminiAnalyzer

    context = {
        "asset_type": "futures",
        "code": "JM2609",
        "stock_name": "焦煤2609",
        "date": "2026-05-08",
        "today": {"close": 1200, "open": 1180, "high": 1215, "low": 1170, "volume": 8000},
        "trend_analysis": {"trend_status": "空头排列", "buy_signal": "卖出", "signal_score": 30},
    }

    analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
    with (
        patch.object(GeminiAnalyzer, "_get_runtime_config", return_value=SimpleNamespace(news_max_age_days=3)),
        patch.object(GeminiAnalyzer, "_get_skill_prompt_sections", return_value=("", "", False)),
    ):
        system_prompt = analyzer._get_analysis_system_prompt("zh", "JM2609", asset_type="futures")
        prompt = analyzer._format_prompt(context, "焦煤2609", report_language="zh")

    combined_prompt = system_prompt + prompt
    assert "buy 表示做多" in combined_prompt
    assert "sell 表示做空" in combined_prompt
    assert "做多信号" in combined_prompt
    assert "做空信号" in combined_prompt
    assert "不是卖出现货或股票减仓" in combined_prompt
    assert "空仓者" not in prompt
    assert "无仓位者" in prompt
    assert "买入价、止损价、目标价" not in prompt
    assert "多/空入场价、止损价、目标价" in prompt
