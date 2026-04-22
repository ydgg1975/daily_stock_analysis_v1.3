import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.storage import Base
from src.services.watchlist_service import WatchlistService
from fastapi.testclient import TestClient


@pytest.fixture
def svc():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return WatchlistService(sessionmaker(bind=engine))


def test_add_and_list(svc):
    svc.add("user1", "600519", "贵州茅台")
    svc.add("user1", "AAPL", "Apple")
    items = svc.list("user1")
    assert len(items) == 2
    codes = [i["stock_code"] for i in items]
    assert "600519" in codes
    assert "AAPL" in codes


def test_add_duplicate_is_idempotent(svc):
    svc.add("user1", "600519", "贵州茅台")
    svc.add("user1", "600519", "贵州茅台")
    assert len(svc.list("user1")) == 1


def test_remove(svc):
    svc.add("user1", "600519")
    svc.remove("user1", "600519")
    assert len(svc.list("user1")) == 0


def test_isolation_between_users(svc):
    svc.add("user1", "600519")
    svc.add("user2", "AAPL")
    assert len(svc.list("user1")) == 1
    assert svc.list("user1")[0]["stock_code"] == "600519"


def test_is_watched(svc):
    svc.add("user1", "600519")
    assert svc.is_watched("user1", "600519") is True
    assert svc.is_watched("user1", "AAPL") is False


# ------------------------------------------------------------------
# HTTP endpoint tests
# ------------------------------------------------------------------

@pytest.fixture
def http_client(tmp_path, monkeypatch):
    """Fresh TestClient with isolated DB; registers a user so auth middleware is active."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)

    from src.config import Config
    Config.reset_instance()

    from src.storage import DatabaseManager
    DatabaseManager._instance = None

    import src.auth as _auth_mod
    _auth_mod._session_secret = None
    _auth_mod._auth_enabled = None

    from api.app import create_app
    app = create_app()
    client = TestClient(app)

    # Register a user so auth is enforced and session cookie is set.
    client.post("/api/v1/auth/register", json={
        "email": "test@test.com",
        "password": "pass1234",
        "passwordConfirm": "pass1234",
    })
    return client


def test_add_watchlist_normalizes_name_ignoring_request_name(http_client):
    """Regardless of what name user submits, DB stores canonical name from code."""
    resp = http_client.post(
        "/api/v1/watchlist",
        json={"stockCode": "600519", "stockName": "WRONG_NAME_XYZ"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stock_code"] == "600519"
    assert body["stock_name"] == "贵州茅台"  # canonical, not WRONG_NAME_XYZ


def test_add_watchlist_rejects_unknown_code(http_client, monkeypatch):
    from src.services import stock_identity_service as mod
    monkeypatch.setattr(mod, "_lookup_name_from_akshare", lambda code: None)
    resp = http_client.post(
        "/api/v1/watchlist",
        json={"stockCode": "ZZ999999", "stockName": "anything"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "stock.identity_not_found"
