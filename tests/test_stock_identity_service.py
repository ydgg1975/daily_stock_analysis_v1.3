# -*- coding: utf-8 -*-
"""Unit tests for stock_identity_service."""
from __future__ import annotations

import pytest

from src.services.stock_identity_service import (
    StockIdentityNotFound,
    normalize_stock_identity,
)


def test_normalize_returns_canonical_pair_for_known_a_share():
    code, name = normalize_stock_identity("600519")
    assert code == "600519"
    assert name == "贵州茅台"


def test_normalize_trims_whitespace_and_lowercases_prefix():
    code, name = normalize_stock_identity("  600519  ")
    assert code == "600519"
    assert name == "贵州茅台"


def test_normalize_raises_when_code_is_empty():
    with pytest.raises(StockIdentityNotFound):
        normalize_stock_identity("")


def test_normalize_raises_when_code_unknown_and_no_fallback(monkeypatch):
    # Force the akshare fallback to return empty to simulate offline
    from src.services import stock_identity_service as mod
    monkeypatch.setattr(mod, "_lookup_name_from_akshare", lambda code: None)
    with pytest.raises(StockIdentityNotFound):
        normalize_stock_identity("ZZ999999")


def test_normalize_hk_stock_common_prefixes():
    # Codebase canonical form: HK codes stored without the .HK suffix
    code, name = normalize_stock_identity("hk00700")
    assert code == "00700"
    assert name == "腾讯控股"


def test_normalize_us_stock_uppercase():
    # Codebase canonical form: US tickers uppercase, names stored in Chinese
    code, name = normalize_stock_identity("aapl")
    assert code == "AAPL"
    assert name == "苹果"


def test_normalize_rejects_pure_symbols():
    with pytest.raises(StockIdentityNotFound):
        normalize_stock_identity("@@@")


def test_normalize_uses_akshare_fallback_when_local_miss(monkeypatch):
    from src.services import stock_identity_service as mod
    monkeypatch.setattr(mod, "_lookup_name_from_akshare", lambda code: "某公司")
    code, name = normalize_stock_identity("999999")
    assert code == "999999"
    assert name == "某公司"
