"""
Test Task 1: Project Structure and Core Data Models

Validates Requirements 1.1, 24.1, 24.2, 24.3, 25.1
"""

import pytest
import sys
import os
from dataclasses import fields

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))


def test_directory_structure_exists():
    """Verify all required directories exist"""
    import os
    base_path = os.path.dirname(os.path.dirname(__file__))
    
    required_dirs = [
        "data",
        "features",
        "diagnostics",
        "states",
        "reports",
    ]
    
    for dir_name in required_dirs:
        dir_path = os.path.join(base_path, dir_name)
        assert os.path.isdir(dir_path), f"Directory {dir_name} should exist"
        
        # Verify __init__.py exists
        init_file = os.path.join(dir_path, "__init__.py")
        assert os.path.isfile(init_file), f"__init__.py should exist in {dir_name}"


def test_config_file_exists():
    """Verify config.py exists and contains required configurations"""
    from src.market_diagnostic import config
    
    # Verify INDEX_POOL exists and has 9 indices
    assert hasattr(config, "INDEX_POOL"), "INDEX_POOL should be defined"
    assert len(config.INDEX_POOL) == 9, "INDEX_POOL should contain 9 indices"
    
    # Verify required indices
    required_indices = [
        "sh000001",  # 上证指数
        "sz399001",  # 深证成指
        "sz399006",  # 创业板指
        "sh000688",  # 科创50
        "sh000016",  # 上证50
        "sh000300",  # 沪深300
        "sh000905",  # 中证500
        "sh000852",  # 中证1000
        "sh000015",  # 微盘股指数
    ]
    
    for index_code in required_indices:
        assert index_code in config.INDEX_POOL, f"{index_code} should be in INDEX_POOL"


def test_style_pairs_configuration():
    """Verify STYLE_PAIRS configuration"""
    from src.market_diagnostic import config
    
    assert hasattr(config, "STYLE_PAIRS"), "STYLE_PAIRS should be defined"
    assert len(config.STYLE_PAIRS) >= 3, "STYLE_PAIRS should contain at least 3 pairs"
    
    # Verify structure: each pair should be (code1, code2, description)
    for pair in config.STYLE_PAIRS:
        assert len(pair) == 3, "Each style pair should have 3 elements"
        assert isinstance(pair[0], str), "First element should be index code"
        assert isinstance(pair[1], str), "Second element should be index code"
        assert isinstance(pair[2], str), "Third element should be description"


def test_industry_codes_configuration():
    """Verify SHENWAN_INDUSTRIES configuration"""
    from src.market_diagnostic import config
    
    assert hasattr(config, "SHENWAN_INDUSTRIES"), "SHENWAN_INDUSTRIES should be defined"
    assert len(config.SHENWAN_INDUSTRIES) == 31, "SHENWAN_INDUSTRIES should contain 31 industries"


def test_index_daily_data_model():
    """Verify IndexDailyData model structure (Requirement 1.1)"""
    from src.market_diagnostic.data import IndexDailyData
    
    # Verify all required fields exist
    required_fields = {
        "code", "name", "date", "close", "open", "high", "low",
        "prev_close", "volume", "amount", "change_pct",
        "close_series", "volume_series"
    }
    
    model_fields = {f.name for f in fields(IndexDailyData)}
    assert required_fields.issubset(model_fields), \
        f"IndexDailyData missing fields: {required_fields - model_fields}"
    
    # Test instantiation
    data = IndexDailyData(
        code="sh000001",
        name="上证指数",
        date="2024-01-01",
        close=3000.0,
        open=2990.0,
        high=3010.0,
        low=2980.0,
        prev_close=2995.0,
        volume=1000000.0,
        amount=50000000000.0,
        change_pct=0.17,
        close_series=[2995.0, 2990.0, 3000.0],
        volume_series=[900000.0, 950000.0, 1000000.0]
    )
    
    assert data.code == "sh000001"
    assert data.close == 3000.0
    assert len(data.close_series) == 3


def test_market_breadth_data_model():
    """Verify MarketBreadthData model structure (Requirement 1.3)"""
    from src.market_diagnostic.data import MarketBreadthData
    
    required_fields = {
        "date", "up_count", "down_count", "flat_count",
        "limit_up_count", "limit_down_count", "explode_count",
        "seal_rate", "continuous_limit_up", "above_ma20_ratio",
        "above_ma60_ratio", "new_high_count", "new_low_count",
        "total_amount", "amount_ma5", "amount_ma20"
    }
    
    model_fields = {f.name for f in fields(MarketBreadthData)}
    assert required_fields.issubset(model_fields), \
        f"MarketBreadthData missing fields: {required_fields - model_fields}"
    
    # Test instantiation
    data = MarketBreadthData(
        date="2024-01-01",
        up_count=2000,
        down_count=1500,
        flat_count=100,
        limit_up_count=50,
        limit_down_count=10,
        explode_count=5,
        seal_rate=0.91,
        continuous_limit_up=20,
        above_ma20_ratio=0.55,
        above_ma60_ratio=0.48,
        new_high_count=100,
        new_low_count=50,
        total_amount=8000.0,
        amount_ma5=7500.0,
        amount_ma20=7000.0
    )
    
    assert data.seal_rate == 0.91
    assert data.above_ma20_ratio == 0.55


def test_sector_daily_data_model():
    """Verify SectorDailyData model structure (Requirement 1.4)"""
    from src.market_diagnostic.data import SectorDailyData
    
    required_fields = {
        "date", "industry_code", "industry_name",
        "ret_1d", "ret_5d", "ret_20d", "excess_ret_1d",
        "breadth_20", "new_high_ratio", "amount", "amount_share",
        "amount_share_delta", "limit_up_count", "turnover"
    }
    
    model_fields = {f.name for f in fields(SectorDailyData)}
    assert required_fields.issubset(model_fields), \
        f"SectorDailyData missing fields: {required_fields - model_fields}"
    
    # Test instantiation
    data = SectorDailyData(
        date="2024-01-01",
        industry_code="BK0447",
        industry_name="电子",
        ret_1d=0.02,
        ret_5d=0.05,
        ret_20d=0.10,
        excess_ret_1d=0.01,
        breadth_20=0.60,
        new_high_ratio=0.15,
        amount=500.0,
        amount_share=0.08,
        amount_share_delta=0.01,
        limit_up_count=5,
        turnover=0.05
    )
    
    assert data.industry_code == "BK0447"
    assert data.ret_1d == 0.02


def test_capital_flow_data_model():
    """Verify CapitalFlowData model structure (Requirement 1.5)"""
    from src.market_diagnostic.data import CapitalFlowData
    
    required_fields = {
        "date", "north_net_flow", "north_5d_avg",
        "margin_balance", "margin_delta", "main_net_flow",
        "etf_net_flow", "data_freshness"
    }
    
    model_fields = {f.name for f in fields(CapitalFlowData)}
    assert required_fields.issubset(model_fields), \
        f"CapitalFlowData missing fields: {required_fields - model_fields}"
    
    # Test instantiation
    data = CapitalFlowData(
        date="2024-01-01",
        north_net_flow=50.0,
        north_5d_avg=45.0,
        margin_balance=18000.0,
        margin_delta=100.0,
        main_net_flow=30.0,
        etf_net_flow=20.0,
        data_freshness={
            "north_net_flow": "T+1",
            "margin_balance": "T+1"
        }
    )
    
    assert data.north_net_flow == 50.0
    assert "north_net_flow" in data.data_freshness


def test_configuration_thresholds():
    """Verify threshold configurations (Requirement 24.1)"""
    from src.market_diagnostic import config
    
    # Verify BREADTH_THRESHOLDS
    assert hasattr(config, "BREADTH_THRESHOLDS")
    assert "extreme_weak" in config.BREADTH_THRESHOLDS
    assert config.BREADTH_THRESHOLDS["extreme_weak"] == 0.20
    assert config.BREADTH_THRESHOLDS["weak"] == 0.35
    assert config.BREADTH_THRESHOLDS["neutral"] == 0.55
    assert config.BREADTH_THRESHOLDS["strong"] == 0.70
    
    # Verify REGIME_SCORE_WEIGHTS
    assert hasattr(config, "REGIME_SCORE_WEIGHTS")
    assert config.REGIME_SCORE_WEIGHTS["trend"] == 0.20
    assert config.REGIME_SCORE_WEIGHTS["risk"] == -0.20


def test_regime_strategy_mapping():
    """Verify regime to strategy mapping (Requirement 20)"""
    from src.market_diagnostic import config
    
    assert hasattr(config, "REGIME_STRATEGY_MAPPING")
    
    required_regimes = [
        "trend_risk_on_growth",
        "trend_risk_on_smallcap",
        "balanced_rotation",
        "defensive_dividend",
        "high_volatility_warning",
        "panic_bottoming",
        "broad_weakness_hold",
    ]
    
    for regime in required_regimes:
        assert regime in config.REGIME_STRATEGY_MAPPING, \
            f"Regime {regime} should be in REGIME_STRATEGY_MAPPING"
        assert isinstance(config.REGIME_STRATEGY_MAPPING[regime], list), \
            f"Strategy mapping for {regime} should be a list"


def test_extensibility_layer_separation():
    """Verify layer separation for extensibility (Requirement 25.1)"""
    import os
    base_path = os.path.dirname(os.path.dirname(__file__))
    
    # Verify each layer is in a separate directory
    layers = ["data", "features", "diagnostics", "states", "reports"]
    
    for layer in layers:
        layer_path = os.path.join(base_path, layer)
        assert os.path.isdir(layer_path), f"Layer {layer} should be in separate directory"
        
        # Verify layer has __init__.py for proper module structure
        init_path = os.path.join(layer_path, "__init__.py")
        assert os.path.isfile(init_path), f"Layer {layer} should have __init__.py"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
