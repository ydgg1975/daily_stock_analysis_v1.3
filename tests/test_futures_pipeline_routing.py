from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd


def test_pipeline_futures_daily_data_uses_futures_fetcher():
    from src.core.pipeline import StockAnalysisPipeline

    pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
    pipeline.asset_type = "futures"
    pipeline.futures_fetcher = Mock()
    pipeline.futures_fetcher.name = "FuturesFetcher"
    expected = pd.DataFrame({"close": [1]})
    pipeline.futures_fetcher.get_daily_data.return_value = expected

    df, source = pipeline._get_daily_data_for_asset("RB", days=30)

    pipeline.futures_fetcher.get_daily_data.assert_called_once_with("RB", days=30)
    assert df is expected
    assert source == "FuturesFetcher"


def test_pipeline_stock_daily_data_keeps_fetcher_manager_path():
    from src.core.pipeline import StockAnalysisPipeline

    pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
    pipeline.asset_type = "stock"
    pipeline.fetcher_manager = Mock()
    expected = pd.DataFrame({"close": [1]})
    pipeline.fetcher_manager.get_daily_data.return_value = (expected, "AkshareFetcher")

    df, source = pipeline._get_daily_data_for_asset("600519", days=30)

    pipeline.fetcher_manager.get_daily_data.assert_called_once_with("600519", days=30)
    assert df is expected
    assert source == "AkshareFetcher"


def test_analysis_service_passes_asset_type_to_pipeline():
    from src.services.analysis_service import AnalysisService

    fake_result = SimpleNamespace(
        success=True,
        code="RB",
        name="螺纹钢主力",
        sentiment_score=50,
        trend_prediction="震荡",
        operation_advice="观望",
        current_price=3500,
        change_pct=0.1,
        analysis_summary="期货分析摘要",
        get_sniper_points=lambda: {},
        news_summary="",
        technical_analysis="",
        fundamental_analysis="",
        risk_warning="",
    )

    with (
        patch("src.config.get_config", return_value=SimpleNamespace()),
        patch("src.core.pipeline.StockAnalysisPipeline") as pipeline_cls,
    ):
        pipeline = pipeline_cls.return_value
        pipeline.process_single_stock.return_value = fake_result
        result = AnalysisService().analyze_stock("RB", asset_type="futures", send_notification=False)

    assert result["stock_code"] == "RB"
    assert result["report"]["meta"]["asset_type"] == "futures"
    pipeline_cls.assert_called_once()
    assert pipeline_cls.call_args.kwargs["asset_type"] == "futures"
