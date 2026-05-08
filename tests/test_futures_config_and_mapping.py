from unittest.mock import patch


def test_futures_config_loads_enabled_and_list():
    from src.config import Config

    with patch("src.config.setup_env"), patch.dict(
        "os.environ",
        {
            "FUTURES_ENABLED": "true",
            "FUTURES_LIST": "rb, I, 螺纹钢",
        },
        clear=False,
    ):
        config = Config._load_from_env()

    assert config.futures_enabled is True
    assert config.futures_list == ["RB", "I"]


def test_futures_symbol_aliases_normalize_to_main_contract():
    from src.data.futures_mapping import normalize_futures_symbol, to_main_contract_symbol

    assert normalize_futures_symbol("rb") == "RB"
    assert normalize_futures_symbol("rb0") == "RB"
    assert normalize_futures_symbol("螺纹钢") == "RB"
    assert to_main_contract_symbol("RB") == "RB0"


def test_futures_symbol_aliases_preserve_specific_contract_month():
    from src.data.futures_mapping import get_futures_name, normalize_futures_symbol, to_main_contract_symbol

    assert normalize_futures_symbol("焦煤2609") == "JM2609"
    assert normalize_futures_symbol("jm2609") == "JM2609"
    assert to_main_contract_symbol("焦煤2609") == "JM2609"
    assert get_futures_name("JM2609") == "焦煤2609"
