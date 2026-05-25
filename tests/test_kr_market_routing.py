from data_provider.base import normalize_stock_code
from data_provider.yfinance_fetcher import YfinanceFetcher
from src.core.trading_calendar import get_market_for_stock
from src.market_context import detect_market


def test_krx_market_detection_and_normalization():
    assert normalize_stock_code("005930.KS") == "005930.KS"
    assert normalize_stock_code("KQ091990") == "091990.KQ"

    assert detect_market("005930") == "kr"
    assert detect_market("005930.KS") == "kr"
    assert detect_market("091990.KQ") == "kr"
    assert get_market_for_stock("005930") == "kr"
    assert get_market_for_stock("005930.KS") == "kr"


def test_yfinance_routes_krx_symbols_to_yahoo_suffixes():
    fetcher = YfinanceFetcher()

    assert fetcher._convert_stock_code("005930") == "005930.KS"
    assert fetcher._convert_stock_code("005930.KS") == "005930.KS"
    assert fetcher._convert_stock_code("KR005930") == "005930.KS"
    assert fetcher._convert_stock_code("091990.KQ") == "091990.KQ"
