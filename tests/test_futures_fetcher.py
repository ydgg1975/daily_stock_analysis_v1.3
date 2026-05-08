from unittest.mock import patch

import pandas as pd


def test_futures_fetcher_uses_main_contract_symbol_and_standard_columns():
    from data_provider.futures_fetcher import FuturesFetcher

    raw = pd.DataFrame(
        {
            "日期": ["2026-05-01", "2026-05-02"],
            "开盘价": [3500, 3510],
            "最高价": [3560, 3570],
            "最低价": [3480, 3490],
            "收盘价": [3520, 3550],
            "成交量": [10000, 12000],
            "成交额": [350000000, 425000000],
        }
    )

    with patch("data_provider.futures_fetcher.ak.futures_main_sina", return_value=raw) as mocked:
        df = FuturesFetcher().get_daily_data("rb", days=2)

    mocked.assert_called_once()
    assert mocked.call_args.kwargs["symbol"] == "RB0"
    assert list(df[["date", "open", "high", "low", "close", "volume", "amount", "pct_chg"]].columns) == [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "pct_chg",
    ]
    assert df.iloc[-1]["close"] == 3550
    assert round(float(df.iloc[-1]["pct_chg"]), 2) == 0.85


def test_futures_fetcher_get_stock_name_uses_alias_mapping():
    from data_provider.futures_fetcher import FuturesFetcher

    assert FuturesFetcher().get_stock_name("rb") == "螺纹钢主力"
    assert FuturesFetcher().get_stock_name("AU0") == "沪金主力"


def test_futures_fetcher_uses_specific_contract_daily_endpoint():
    from data_provider.futures_fetcher import FuturesFetcher

    raw = pd.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-02", "2026-05-03"],
            "open": [1200, 1210, 1220],
            "high": [1230, 1240, 1250],
            "low": [1190, 1200, 1210],
            "close": [1220, 1230, 1240],
            "volume": [1000, 1100, 1200],
            "hold": [500, 520, 540],
            "settle": [1215, 1225, 1235],
        }
    )

    with patch("data_provider.futures_fetcher.ak.futures_zh_daily_sina", return_value=raw) as mocked:
        df = FuturesFetcher().get_daily_data("焦煤2609", start_date="2026-05-02", end_date="2026-05-03")

    mocked.assert_called_once_with(symbol="JM2609")
    assert [value.strftime("%Y-%m-%d") for value in df["date"]] == ["2026-05-02", "2026-05-03"]
    assert FuturesFetcher().get_stock_name("焦煤2609") == "焦煤2609"
