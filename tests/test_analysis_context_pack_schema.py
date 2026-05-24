# -*- coding: utf-8 -*-
"""Tests for the Issue #1389 P1 AnalysisContextPack schema."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.core.trading_calendar import build_market_phase_context
from src.schemas.analysis_context_pack import (
    PACK_VERSION,
    AnalysisContextBlock,
    AnalysisContextItem,
    AnalysisContextPack,
    AnalysisSubject,
    ContextFieldStatus,
    DataQuality,
)
from src.utils.sanitize import redact_sensitive_mapping


def _subject() -> AnalysisSubject:
    return AnalysisSubject(code="600519", stock_name="贵州茅台", market="cn")


def test_pack_defaults_and_json_serialization_are_stable() -> None:
    pack = AnalysisContextPack(
        subject=_subject(),
        created_at=datetime(2026, 5, 24, 9, 30, tzinfo=timezone.utc),
    )

    dumped = pack.model_dump(mode="json")
    json.dumps(dumped, ensure_ascii=False)

    assert dumped["pack_version"] == PACK_VERSION
    assert dumped["subject"] == {
        "code": "600519",
        "stock_name": "贵州茅台",
        "market": "cn",
    }
    assert dumped["blocks"] == {}
    assert dumped["data_quality"] == {"warnings": [], "metadata": {}}
    assert dumped["metadata"] == {}
    assert dumped["created_at"] == "2026-05-24T09:30:00Z"


def test_item_and_block_timestamp_use_iso_strings() -> None:
    item = AnalysisContextItem(
        status=ContextFieldStatus.AVAILABLE,
        value=1880.0,
        timestamp="2026-05-24T09:30:00+08:00",
    )
    block = AnalysisContextBlock(
        status=ContextFieldStatus.AVAILABLE,
        items={"price": item},
        timestamp="2026-05-24T09:30:01+08:00",
    )

    dumped = block.model_dump(mode="json")

    assert dumped["timestamp"] == "2026-05-24T09:30:01+08:00"
    assert dumped["items"]["price"]["timestamp"] == "2026-05-24T09:30:00+08:00"


def test_context_field_status_allows_only_p0_quality_states() -> None:
    for state in (
        "available",
        "missing",
        "not_supported",
        "fallback",
        "stale",
        "estimated",
        "partial",
    ):
        assert ContextFieldStatus(state).value == state

    with pytest.raises(ValueError):
        ContextFieldStatus("fetch_failed")

    with pytest.raises(ValidationError):
        AnalysisContextItem(status="fetch_failed")


def test_market_phase_context_dict_can_be_used_as_phase_slot() -> None:
    phase = build_market_phase_context(
        market="cn",
        current_time=datetime(2026, 5, 24, 9, 0, tzinfo=timezone.utc),
        trigger_source="system",
        analysis_intent="auto",
    ).to_dict()
    pack = AnalysisContextPack(subject=_subject(), phase=phase)

    assert pack.phase == phase
    assert isinstance(pack.model_dump(mode="json")["phase"], dict)


def test_block_and_item_status_are_independent_contract_fields() -> None:
    block = AnalysisContextBlock(
        status=ContextFieldStatus.PARTIAL,
        items={
            "price": AnalysisContextItem(
                status=ContextFieldStatus.AVAILABLE,
                value=1880.0,
            ),
            "turnover_rate": AnalysisContextItem(
                status=ContextFieldStatus.MISSING,
                missing_reason="provider_empty",
            ),
        },
    )

    dumped = block.model_dump(mode="json")

    assert dumped["status"] == "partial"
    assert dumped["items"]["price"]["status"] == "available"
    assert dumped["items"]["turnover_rate"]["status"] == "missing"


def test_data_quality_is_container_only() -> None:
    data_quality = DataQuality(
        warnings=["quote_stale"],
        metadata={"note": "P1 does not define scoring"},
    )

    assert data_quality.model_dump(mode="json") == {
        "warnings": ["quote_stale"],
        "metadata": {"note": "P1 does not define scoring"},
    }


def test_redact_sensitive_mapping_recurses_dicts_and_lists_by_key() -> None:
    payload = {
        "API_KEY": "ak-secret",
        "OPENAI_API_KEY": "openai-secret",
        "GEMINI_API_KEY": "gemini-secret",
        "data_api": "akshare",
        "api_url": "https://example.test/data",
        "nested": [
            {
                "authorization_header": "Bearer token",
                "license_key": "license-secret",
                "vendor_license_key": "vendor-license-secret",
                "source": "provider",
            },
            {
                "webhook_url": "https://hooks.example.test/abc",
                "send_key": "send-key-secret",
                "normal": "kept",
            },
        ],
        "metadata": {"Cookie": "session=abc", "count": 1},
    }

    redacted = redact_sensitive_mapping(payload)

    assert redacted["API_KEY"] == "[REDACTED]"
    assert redacted["OPENAI_API_KEY"] == "[REDACTED]"
    assert redacted["GEMINI_API_KEY"] == "[REDACTED]"
    assert redacted["data_api"] == "akshare"
    assert redacted["api_url"] == "https://example.test/data"
    assert redacted["nested"][0]["authorization_header"] == "[REDACTED]"
    assert redacted["nested"][0]["license_key"] == "[REDACTED]"
    assert redacted["nested"][0]["vendor_license_key"] == "[REDACTED]"
    assert redacted["nested"][0]["source"] == "provider"
    assert redacted["nested"][1]["webhook_url"] == "[REDACTED]"
    assert redacted["nested"][1]["send_key"] == "[REDACTED]"
    assert redacted["nested"][1]["normal"] == "kept"
    assert redacted["metadata"]["Cookie"] == "[REDACTED]"
    assert redacted["metadata"]["count"] == 1


def test_pack_safe_dict_redacts_sensitive_metadata_but_keeps_business_fields() -> None:
    pack = AnalysisContextPack(
        subject=_subject(),
        blocks={
            "quote": AnalysisContextBlock(
                status=ContextFieldStatus.AVAILABLE,
                items={
                    "price": AnalysisContextItem(
                        status=ContextFieldStatus.AVAILABLE,
                        value=1880.0,
                        source="akshare",
                        metadata={"access_token": "secret", "data_api": "kept"},
                    )
                },
            )
        },
        metadata={"webhook_url": "https://hooks.example.test/abc", "trace_id": "q-1"},
    )

    safe = pack.to_safe_dict()

    assert safe["metadata"]["webhook_url"] == "[REDACTED]"
    assert safe["metadata"]["trace_id"] == "q-1"
    price_metadata = safe["blocks"]["quote"]["items"]["price"]["metadata"]
    assert price_metadata["access_token"] == "[REDACTED]"
    assert price_metadata["data_api"] == "kept"
