from fastapi.testclient import TestClient


def test_build_futures_index_collects_realtime_contracts():
    import pandas as pd

    from src.services.futures_index_service import build_futures_index

    marks = pd.DataFrame(
        [
            {"exchange": "大连商品交易所", "symbol": "焦煤", "mark": "jm_qh"},
            {"exchange": "郑州商品交易所", "symbol": "PTA", "mark": "pta_qh"},
        ]
    )

    def fake_realtime(symbol):
        if symbol == "焦煤":
            return pd.DataFrame(
                [
                    {"symbol": "JM0", "name": "焦煤连续", "exchange": "dce"},
                    {"symbol": "JM2609", "name": "焦煤2609", "exchange": "dce"},
                ]
            )
        if symbol == "PTA":
            return pd.DataFrame(
                [
                    {"symbol": "TA0", "name": "PTA连续", "exchange": "czce"},
                    {"symbol": "TA2609", "name": "PTA2609", "exchange": "czce"},
                ]
            )
        raise AssertionError(symbol)

    items = build_futures_index(
        symbol_mark_loader=lambda: marks,
        realtime_loader=fake_realtime,
    )

    assert {item["canonical_code"] for item in items} >= {"JM0", "JM2609", "TA0", "TA2609"}
    assert next(item for item in items if item["canonical_code"] == "JM2609")["aliases"] == [
        "焦煤",
        "焦煤2609",
    ]


def test_futures_index_endpoint_returns_cached_items():
    from api.app import create_app

    client = TestClient(create_app(static_dir=None))
    app = client.app
    app.dependency_overrides = {}

    from api.v1.endpoints import stocks

    def fake_index():
        return [
            {
                "canonical_code": "JM2609",
                "display_code": "JM2609",
                "name_zh": "焦煤2609",
                "aliases": ["焦煤", "焦煤2609"],
                "market": "FUTURES",
                "asset_type": "futures",
                "active": True,
                "popularity": 100,
            }
        ]

    original = stocks.get_futures_index_items
    stocks.get_futures_index_items = fake_index
    try:
        response = client.get("/api/v1/stocks/futures-index")
    finally:
        stocks.get_futures_index_items = original

    assert response.status_code == 200
    assert response.json()["items"][0]["canonical_code"] == "JM2609"
