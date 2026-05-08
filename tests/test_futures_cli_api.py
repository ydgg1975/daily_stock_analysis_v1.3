from unittest.mock import patch


def test_parse_arguments_accepts_futures_list():
    from main import parse_arguments

    with patch("sys.argv", ["main.py", "--futures", "RB,I,AU"]):
        args = parse_arguments()

    assert args.futures == "RB,I,AU"


def test_analyze_request_accepts_futures_asset_type():
    from api.v1.schemas.analysis import AnalyzeRequest

    request = AnalyzeRequest(asset_type="futures", stock_codes=["RB", "I"])

    assert request.asset_type == "futures"


def test_futures_input_bypasses_stock_name_resolver():
    from api.v1.endpoints.analysis import _resolve_and_normalize_input

    with patch("api.v1.endpoints.analysis.resolve_name_to_code") as resolver:
        assert _resolve_and_normalize_input("螺纹钢", asset_type="futures") == "RB"
        assert _resolve_and_normalize_input("焦煤2609", asset_type="futures") == "JM2609"

    resolver.assert_not_called()


def test_task_queue_dedupe_key_includes_asset_type():
    from src.services.task_queue import _dedupe_stock_code_key

    assert _dedupe_stock_code_key("RB", asset_type="stock") == "RB"
    assert _dedupe_stock_code_key("RB", asset_type="futures") == "futures:RB"
