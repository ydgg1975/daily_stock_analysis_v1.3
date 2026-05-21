# -*- coding: utf-8 -*-
"""Contract checks for the alert-center documentation."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PROJECT_ROOT / "docs" / "alerts.md"


def _read_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_alerts_doc_exists_and_links_p0_scope() -> None:
    doc = _read_doc()

    assert "Issue #1202" in doc
    assert "AGENT_EVENT_ALERT_RULES_JSON" in doc
    assert "EventMonitor" in doc
    assert "P1 Alert API MVP" in doc
    assert "P0 문서와 계약" in doc


def test_alerts_doc_covers_legacy_runtime_rules() -> None:
    doc = _read_doc()

    for token in ("price_cross", "price_change_percent", "volume_spike"):
        assert token in doc
    for token in ("sentiment_shift", "risk_flag", "custom"):
        assert token in doc


def test_alerts_doc_defines_required_contract_entities() -> None:
    doc = _read_doc()

    required_sections = (
        "### `alert_rule`",
        "### `alert_trigger`",
        "### `alert_notification`",
        "### `alert_cooldown`",
    )
    for section in required_sections:
        assert section in doc

    required_fields = (
        "target_scope",
        "parameters",
        "cooldown_policy",
        "notification_policy",
        "observed_value",
        "data_timestamp",
        "trigger_id",
        "latency_ms",
        "cooldown_until",
    )
    for field_name in required_fields:
        assert field_name in doc


def test_alerts_doc_covers_storage_evaluation_and_rollback() -> None:
    doc = _read_doc()

    assert (PROJECT_ROOT / "src" / "storage.py").is_file()

    for token in (
        "## 저장소 설계 기준",
        "src/storage.py",
        "src/repositories/",
        "src/services/",
        "data/stock_analysis.db",
        "중복 초기화",
        "되돌리기",
    ):
        assert token in doc


def test_alerts_doc_keeps_p0_non_goals_explicit() -> None:
    doc = _read_doc()

    for token in (
        "`api/v1/schemas/alerts.py` 추가",
        "Web 알림 센터 페이지 추가",
        "DB 테이블 추가",
        "트리거 이력 구현",
        "`AGENT_EVENT_ALERT_RULES_JSON` 자동 마이그레이션",
        "`NotificationService` 재작성",
    ):
        assert token in doc


def test_alerts_doc_defines_p1_api_mvp_scope() -> None:
    doc = _read_doc()

    for token in (
        "api/v1/endpoints/alerts.py",
        "api/v1/schemas/alerts.py",
        "GET /api/v1/alerts/rules",
        "POST /api/v1/alerts/rules",
        "GET /api/v1/alerts/rules/{rule_id}",
        "PATCH /api/v1/alerts/rules/{rule_id}",
        "DELETE /api/v1/alerts/rules/{rule_id}",
        "POST /api/v1/alerts/rules/{rule_id}/enable",
        "POST /api/v1/alerts/rules/{rule_id}/disable",
        "POST /api/v1/alerts/rules/{rule_id}/test",
        "GET /api/v1/alerts/triggers",
        "GET /api/v1/alerts/notifications",
        "price_cross",
        "price_change_percent",
        "volume_spike",
        "dry-run",
        "민감",
        "실제 알림 전송",
    ):
        assert token in doc


def test_alerts_doc_keeps_p1_non_goals_explicit() -> None:
    doc = _read_doc()

    for token in (
        "Web 알림 센터 페이지 추가",
        "schedule worker가 새 active rules를 자동 실행",
        "`alert_trigger` / `alert_notification` 행 생성",
        "`alert_cooldown` 영속 상태 생성",
        "MACD, KDJ, CCI, RSI",
        "legacy 설정 자동 마이그레이션",
    ):
        assert token in doc


def test_alerts_doc_defines_p2_worker_scope() -> None:
    doc = _read_doc()

    for token in (
        "### P2 알림 평가 Worker",
        "src/services/alert_worker.py",
        "agent_event_monitor",
        "DB active rule",
        "legacy JSON",
        "`triggered`, `skipped`, `degraded`, `failed`",
        "per-channel attempt",
        "cooldown_policy",
    ):
        assert token in doc


def test_alerts_doc_describes_p1_rollback_for_created_tables() -> None:
    doc = _read_doc()

    for token in (
        "P1에서 추가한",
        "`alert_rules` / `alert_triggers` / `alert_notifications` SQLite 테이블",
        "Base.metadata.create_all()",
        "SQLite 테이블과 데이터를 자동 삭제하지 않으며",
        "P1 신규 Alert API 코드를 되돌리는 PR",
    ):
        assert token in doc


def test_alerts_doc_defines_p4_notification_and_cooldown_scope() -> None:
    doc = _read_doc()

    for token in (
        "### P4 알림 결과와 영속 쿨다운",
        "`alert_cooldowns`",
        "`alert_notifications`",
        "`__cooldown__`",
        "`__noise_suppressed__`",
        "`__no_channel__`",
        "`__dispatch__`",
        "DB active rule만 `alert_cooldowns`",
        "legacy fingerprint",
        "P4 revert",
    ):
        assert token in doc


def test_alerts_doc_defines_p5_indicator_scope() -> None:
    doc = _read_doc()

    for token in (
        "### P5 기술 지표 규칙",
        "ma_price_cross",
        "rsi_threshold",
        "macd_cross",
        "kdj_cross",
        "cci_threshold",
        "compute_required_bars",
        "requested_days",
        "required_bars > 365",
        "prev <= threshold < current",
        "Wilder",
        "SMMA",
        "alpha=1/period",
        "EMA(fast_period)",
        "alpha=1/k_period",
        "0.015 * mean_deviation",
        "HTTP 400 + `validation_error`",
        "HTTP 400 + `unsupported_alert_type`",
        "unsupported type",
        "legacy 세 규칙 실행",
    ):
        assert token in doc
