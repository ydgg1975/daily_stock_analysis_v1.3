# -*- coding: utf-8 -*-
"""Service tests for DecisionSignal P1."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.config import Config
from src.services.decision_signal_service import DecisionSignalService
from src.storage import DatabaseManager, DecisionSignalRecord


def test_service_imports_without_api_bootstrap() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from src.services.decision_signal_service import DecisionSignalService; "
            "print(DecisionSignalService.__name__)",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "DecisionSignalService" in result.stdout


@pytest.fixture()
def isolated_db(tmp_path):
    old_database_path = os.environ.get("DATABASE_PATH")
    db_path = tmp_path / "decision_signal_service.db"
    os.environ["DATABASE_PATH"] = str(db_path)
    Config.reset_instance()
    DatabaseManager.reset_instance()
    db = DatabaseManager.get_instance()
    try:
        yield db
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        if old_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = old_database_path


def _payload(**overrides):
    payload = {
        "stock_code": "SH600519",
        "stock_name": "贵州茅台",
        "market": "cn",
        "source_type": "analysis",
        "source_report_id": 101,
        "trace_id": "trace-101",
        "market_phase": "intraday",
        "trigger_source": "api",
        "action": "buy",
        "confidence": 0.72,
        "score": 83,
        "horizon": "3d",
        "reason": "放量突破",
    }
    payload.update(overrides)
    return payload


def test_service_normalizes_fields_and_partial_plan_quality(isolated_db) -> None:
    service = DecisionSignalService(db_manager=isolated_db)

    result = service.create_signal(
        _payload(
            entry_low="1680.5",
            stop_loss="1600",
        )
    )

    item = result["item"]
    assert result["created"] is True
    assert item["stock_code"] == "600519"
    assert item["market"] == "cn"
    assert item["action"] == "buy"
    assert item["action_label"] == "买入"
    assert item["confidence"] == 0.72
    assert item["score"] == 83
    assert item["entry_low"] == 1680.5
    assert item["stop_loss"] == 1600.0
    assert item["plan_quality"] == "partial"


def test_service_plan_quality_slots_and_explicit_override(isolated_db) -> None:
    service = DecisionSignalService(db_manager=isolated_db)

    minimal = service.create_signal(_payload(source_report_id=201, trace_id="trace-201", entry_low=1680))
    assert minimal["item"]["plan_quality"] == "minimal"

    complete = service.create_signal(
        _payload(
            source_report_id=202,
            trace_id="trace-202",
            entry_low=1680,
            entry_high=1700,
            stop_loss=1600,
            target_price=1850,
            invalidation="跌破 1600",
        )
    )
    assert complete["item"]["plan_quality"] == "complete"

    explicit = service.create_signal(
        _payload(
            source_report_id=203,
            trace_id="trace-203",
            plan_quality="unknown",
            entry_low=1680,
            stop_loss=1600,
            target_price=1850,
            invalidation="跌破 1600",
        )
    )
    assert explicit["item"]["plan_quality"] == "unknown"


def test_service_rejects_invalid_enums_and_ranges(isolated_db) -> None:
    service = DecisionSignalService(db_manager=isolated_db)

    with pytest.raises(ValueError, match="market"):
        service.create_signal(_payload(market="jp"))
    with pytest.raises(ValueError, match="action"):
        service.create_signal(_payload(action="strong buy"))
    with pytest.raises(ValueError, match="confidence"):
        service.create_signal(_payload(confidence=1.1))
    with pytest.raises(ValueError, match="score"):
        service.create_signal(_payload(score=101))
    with pytest.raises(ValueError, match="trigger_source"):
        service.create_signal(_payload(trigger_source="x" * 65))


def test_service_sanitizes_text_and_json_before_persisting(isolated_db) -> None:
    service = DecisionSignalService(db_manager=isolated_db)
    long_text = "x" * 450

    result = service.create_signal(
        _payload(
            reason=f"{long_text} Bearer abc.def.ghi https://hooks.example.com/send",
            risk_summary="api_key=sk-1234567890abcdef123456",
            invalidation={"token": "plain-secret", "note": "secret=keepout"},
            watch_conditions=["watch https://example.com/path"],
            evidence={
                "webhook_url": "https://secret.example.com/hook",
                "note": "Bearer abcdef0123456789",
            },
            metadata={"access_token": "abc", "callback": "https://example.com/cb"},
        )
    )

    item = result["item"]
    assert len(item["reason"]) > 300
    response_blob = str(item)
    assert "hooks.example.com" not in response_blob
    assert "secret.example.com" not in response_blob
    assert "example.com/cb" not in response_blob
    assert "plain-secret" not in response_blob
    assert "abcdef0123456789" not in response_blob
    assert "sk-1234567890abcdef123456" not in response_blob
    assert "[REDACTED" in response_blob

    with isolated_db.get_session() as session:
        row = session.query(DecisionSignalRecord).filter_by(id=item["id"]).one()
        stored_blob = " ".join(
            str(value or "")
            for value in (
                row.reason,
                row.risk_summary,
                row.invalidation,
                row.watch_conditions,
                row.evidence_json,
                row.metadata_json,
            )
        )
    assert "hooks.example.com" not in stored_blob
    assert "plain-secret" not in stored_blob
    assert "sk-1234567890abcdef123456" not in stored_blob
