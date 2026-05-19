import logging
import sys
from types import SimpleNamespace

import pandas as pd
import pytest
import requests

from data_provider.akshare_fetcher import (
    AkshareFetcher,
    SINA_REALTIME_ENDPOINT,
    TENCENT_REALTIME_ENDPOINT,
)


class _DummyCircuitBreaker:
    def __init__(self):
        self.failures = []
        self.successes = []

    def is_available(self, source: str) -> bool:
        return True

    def record_success(self, source: str) -> None:
        self.successes.append(source)

    def record_failure(self, source: str, error=None) -> None:
        self.failures.append((source, error))


class _DummyResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        self.encoding = None


def _make_sina_payload() -> str:
    fields = [
        "daqintielu", "5.100", "5.000", "5.190", "5.200", "5.050", "5.180", "5.190",
        "123456", "789012"
    ]
    fields.extend(["0"] * 20)
    fields.extend(["2026-03-08", "15:00:00"])
    return f'var hq_str_sh601006="{",".join(fields)}";'


def _make_tencent_payload() -> str:
    fields = ["0"] * 50
    fields[1] = "daqintielu"
    fields[2] = "601006"
    fields[3] = "5.19"
    fields[4] = "5.00"
    fields[5] = "5.10"
    fields[6] = "1234"
    fields[31] = "0.19"
    fields[32] = "3.80"
    fields[34] = "5.20"
    fields[35] = "5.05"
    fields[38] = "0.69"
    fields[39] = "12.3"
    fields[43] = "2.00"
    fields[44] = "1000"
    fields[45] = "1200"
    fields[46] = "1.20"
    fields[49] = "0.63"
    return f'v_sh601006="{"~".join(fields)}";'


@pytest.fixture
def akshare_fetcher(monkeypatch):
    fetcher = AkshareFetcher()
    monkeypatch.setattr(fetcher, "_enforce_rate_limit", lambda: None)
    return fetcher


def test_sina_realtime_success_logs_endpoint(caplog, monkeypatch, akshare_fetcher):
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)
    monkeypatch.setattr(
        "data_provider.akshare_fetcher.requests.get",
        lambda *args, **kwargs: _DummyResponse(200, _make_sina_payload()),
    )

    with caplog.at_level(logging.INFO):
        quote = akshare_fetcher._get_stock_realtime_quote_sina("601006")

    assert quote is not None
    assert quote.name == "daqintielu"
    assert quote.price == 5.19
    assert breaker.successes == ["akshare_sina"]
    assert f"endpoint={SINA_REALTIME_ENDPOINT}" in caplog.text
    assert "[shishixingqing-xinlang] 601006 daqintielu:" in caplog.text


def test_sina_realtime_remote_disconnect_logs_category(caplog, monkeypatch, akshare_fetcher):
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)

    def _raise_disconnect(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Remote end closed connection without response")

    monkeypatch.setattr("data_provider.akshare_fetcher.requests.get", _raise_disconnect)

    with caplog.at_level(logging.INFO):
        quote = akshare_fetcher._get_stock_realtime_quote_sina("601006")

    assert quote is None
    assert breaker.failures
    source_key, message = breaker.failures[0]
    assert source_key == "akshare_sina"
    assert "category=remote_disconnect" in message
    assert f"endpoint={SINA_REALTIME_ENDPOINT}" in caplog.text
    assert "xinlang shishixingqing接口shibai:" in caplog.text


def test_tencent_realtime_http_status_logs_endpoint(caplog, monkeypatch, akshare_fetcher):
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)
    monkeypatch.setattr(
        "data_provider.akshare_fetcher.requests.get",
        lambda *args, **kwargs: _DummyResponse(503, "service unavailable"),
    )

    with caplog.at_level(logging.INFO):
        quote = akshare_fetcher._get_stock_realtime_quote_tencent("601006")

    assert quote is None
    assert breaker.failures
    source_key, message = breaker.failures[0]
    assert source_key == "akshare_tencent"
    assert "category=http_status" in message
    assert "detail=HTTP 503" in message
    assert f"endpoint={TENCENT_REALTIME_ENDPOINT}" in caplog.text


def test_tencent_realtime_success_logs_endpoint(caplog, monkeypatch, akshare_fetcher):
    breaker = _DummyCircuitBreaker()
    monkeypatch.setattr("data_provider.akshare_fetcher.get_realtime_circuit_breaker", lambda: breaker)
    monkeypatch.setattr(
        "data_provider.akshare_fetcher.requests.get",
        lambda *args, **kwargs: _DummyResponse(200, _make_tencent_payload()),
    )

    with caplog.at_level(logging.INFO):
        quote = akshare_fetcher._get_stock_realtime_quote_tencent("601006")

    assert quote is not None
    assert quote.name == "daqintielu"
    assert quote.price == 5.19
    assert breaker.successes == ["akshare_tencent"]
    assert f"endpoint={TENCENT_REALTIME_ENDPOINT}" in caplog.text
    assert "[shishixingqing-tengxun] 601006 daqintielu:" in caplog.text


def test_hot_stocks_uses_eastmoney_hot_ranking_when_available(monkeypatch, akshare_fetcher):
    fake_akshare = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)
    monkeypatch.setattr(
        akshare_fetcher,
        "_get_eastmoney_hot_stocks",
        lambda _ak, n: [
            {
                "rank": 1,
                "code": "SZ000066",
                "name": "zhongguochangcheng",
                "price": 21.8,
                "change_pct": 9.99,
                "source": "dongfangcaifurenqibang",
            }
        ],
    )

    result = akshare_fetcher.get_hot_stocks(5)

    assert result[0]["source"] == "dongfangcaifurenqibang"
    assert result[0]["name"] == "zhongguochangcheng"


def test_hot_stocks_falls_back_to_xueqiu_when_primary_sources_empty(monkeypatch, akshare_fetcher):
    call_order = []

    def _eastmoney(_ak, _n):
        call_order.append("eastmoney_hot")
        return None

    def _up(_ak, _n):
        call_order.append("eastmoney_hot_up")
        return []

    def _xueqiu(_ak, _n):
        call_order.append("xueqiu")
        return [
            {
                "rank": 1,
                "code": "SH600004",
                "name": "huaxiayinhang",
                "price": 7.21,
                "change_pct": None,
                "source": "xueqiuguanzhubang",
            }
        ]

    monkeypatch.setattr(akshare_fetcher, "_get_eastmoney_hot_stocks", _eastmoney)
    monkeypatch.setattr(akshare_fetcher, "_get_eastmoney_hot_up_stocks", _up)
    monkeypatch.setattr(akshare_fetcher, "_get_xueqiu_hot_stocks", _xueqiu)

    result = akshare_fetcher.get_hot_stocks(5)

    assert call_order == ["eastmoney_hot", "eastmoney_hot_up", "xueqiu"]
    assert result == [
        {
            "rank": 1,
            "code": "SH600004",
            "name": "huaxiayinhang",
            "price": 7.21,
            "change_pct": None,
            "source": "xueqiuguanzhubang",
        }
    ]


def test_limit_up_pool_zero_pads_first_seal_times_before_sorting(monkeypatch, akshare_fetcher):
    df = pd.DataFrame(
        [
            {
                "daima": "000002",
                "mingcheng": "wuhougu",
                "zhangdiefu": 10.0,
                "zuixinjia": 12.3,
                "chengjiaoe": 1,
                "huanshoulv": 2,
                "fengbanzijin": 3,
                "shoucifengbanshijian": 141354,
                "zuihoufengbanshijian": 141500,
                "zhabancishu": 0,
                "zhangtingtongji": "1/1",
                "lianbanshu": 1,
                "suoshuhangye": "dichan",
            },
            {
                "daima": "000001",
                "mingcheng": "jingjiagu",
                "zhangdiefu": 10.0,
                "zuixinjia": 10.0,
                "chengjiaoe": 1,
                "huanshoulv": 2,
                "fengbanzijin": 3,
                "shoucifengbanshijian": 92500,
                "zuihoufengbanshijian": 93000,
                "zhabancishu": 0,
                "zhangtingtongji": "1/1",
                "lianbanshu": 1,
                "suoshuhangye": "jisuanji",
            },
            {
                "daima": "000003",
                "mingcheng": "zaopangu",
                "zhangdiefu": 10.0,
                "zuixinjia": 11.0,
                "chengjiaoe": 1,
                "huanshoulv": 2,
                "fengbanzijin": 3,
                "shoucifengbanshijian": 101500,
                "zuihoufengbanshijian": 102000,
                "zhabancishu": 0,
                "zhangtingtongji": "1/1",
                "lianbanshu": 1,
                "suoshuhangye": "dianzi",
            },
        ]
    )
    fake_akshare = SimpleNamespace(stock_zt_pool_em=lambda date: df)
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)

    result = akshare_fetcher.get_limit_up_pool(date="20260511", n=3)

    assert [row["code"] for row in result] == ["000001", "000003", "000002"]
    assert result[0]["first_limit_time"] == "092500"
    assert result[0]["last_limit_time"] == "093000"
