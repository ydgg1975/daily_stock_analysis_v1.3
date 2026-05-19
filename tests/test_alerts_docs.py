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
    assert "P0 buzuo" in doc


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
        "## cunchufanganpinggu",
        "src/storage.py",
        "src/repositories/",
        "src/services/",
        "data/stock_analysis.db",
        "midengchushihua",
        "huigunshuoming",
    ):
        assert token in doc


def test_alerts_doc_keeps_p0_non_goals_explicit() -> None:
    doc = _read_doc()

    for token in (
        "P0 jieduanbuxinzeng `api/v1/schemas/alerts.py`",
        "P0 jieduanbuxinzeng Web gaojingzhongxinyemian",
        "P0 jieduanbuxinzeng(chinese removed)biao",
        "P0 jieduanbushixianchufalishi",
        "P0 jieduanbuzidongqianyi,shanchuhuofugai `AGENT_EVENT_ALERT_RULES_JSON`",
        "P0 jieduanbuzhongxie `NotificationService`",
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
        "unsupported",
        "tuomin",
        "baoliuziduan",
        "buzhixinglengquehuozidingyitongzhiyuyi",
    ):
        assert token in doc


def test_alerts_doc_keeps_p1_non_goals_explicit() -> None:
    doc = _read_doc()

    for token in (
        "buxinzeng Web gaojingzhongxinyemian",
        "burang schedule worker jiazaichijiuhua active rules",
        "bushixianzhenshi `alert_trigger` / `alert_notification` xieru",
        "bushixian `alert_cooldown` zhixingyuyi",
        "bushixian MACD,KDJ,CCI,RSI",
        "buzidongqianyi,shanchu,fugaihuogaixie legacy peizhi",
    ):
        assert token in doc


def test_alerts_doc_defines_p2_worker_scope() -> None:
    doc = _read_doc()

    for token in (
        "## P2 gaojingpinggu Worker",
        "src/services/alert_worker.py",
        "agent_event_monitor",
        "chijiuhua active rules",
        "legacy JSON",
        "`triggered`,`skipped`,`degraded`,`failed`",
        "buxie `alert_notifications`",
        "buzhixing `cooldown_policy`",
    ):
        assert token in doc


def test_alerts_doc_describes_p1_rollback_for_created_tables() -> None:
    doc = _read_doc()

    for token in (
        "P1 xinzeng Alert API daima",
        "`alert_rules` / `alert_triggers` / `alert_notifications` SQLite biao",
        "Base.metadata.create_all()",
        "SQLite biaoyushujubuhuizidongshanchu",
        "shoudongshanchuxiangguanbiao",
    ):
        assert token in doc


def test_alerts_doc_defines_p4_notification_and_cooldown_scope() -> None:
    doc = _read_doc()

    for token in (
        "## P4 tongzhijieguoyuchijiuhualengque",
        "`alert_cooldowns`",
        "`alert_notifications`",
        "`__cooldown__`",
        "`__cooldown_read_failed__`",
        "`__noise_suppressed__`",
        "notification_noise.py",
        "DB chijiuhuaguizezhengchanglujingshiyong `alert_cooldowns`",
        "duquchijiuhualengquezhuangtaishibai",
        "legacy `AGENT_EVENT_ALERT_RULES_JSON` guizejixushiyong worker jinchengnei fingerprint",
        "buhuixieruhuoyanchang `alert_cooldowns`",
        "zuixiaohuigunfangshishi revert P4 PR",
    ):
        assert token in doc
