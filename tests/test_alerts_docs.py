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
        "`rule_id + target + data_source + data_timestamp`",
        "同一数据点去重",
        "`data_timestamp` 缺失时不做去重",
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


def test_alerts_doc_defines_p6_portfolio_and_watchlist_scope() -> None:
    doc = _read_doc()

    for token in (
        "## P6 持仓与自选股联动",
        "P6 scope/type 矩阵",
        "`watchlist`",
        "`portfolio_holdings`",
        "`portfolio_account`",
        "`portfolio_stop_loss`",
        "`portfolio_concentration`",
        "`portfolio_drawdown`",
        "`portfolio_price_stale`",
        "Target Identity Contract",
        "`effective_target`",
        "`RuntimeAlertRule.key`",
        "`{parent_key}|{effective_target}`",
        "dry-run",
        "`degraded_count`",
        "soft cap",
        "cooldown_active",
        "父规则摘要",
        "legacy `AGENT_EVENT_ALERT_RULES_JSON` 不支持 watchlist、portfolio",
        "sector 级集中度",
        "P6 PR",
    ):
        assert token in doc


def test_alerts_doc_defines_p7_market_light_scope() -> None:
    doc = _read_doc()

    for token in (
        "## P7 大盘红绿灯结构化告警",
        "MarketLightSnapshot",
        "`target_scope=market`",
        "`market_light_status`",
        "`market_light_score_drop`",
        "`statuses=[\"red\",\"yellow\"]`",
        "`min_drop > 0`",
        "`cn` / `hk` / `us`",
        "双向约束",
        "`context_snapshot.market_light_snapshots`",
        "`data_quality=unavailable`",
        "`partial_comparison=true`",
        "`missing_dimensions`",
        "canonical scorer",
        "thin wrapper",
        "`load_previous_snapshot(region, before_trade_date)`",
        "最大 `snapshot.trade_date`",
        "旧交易日 backfill",
        "`TRADING_DAY_CHECK_ENABLED`",
        "`data_source=market_light`",
        "legacy `AGENT_EVENT_ALERT_RULES_JSON` 不支持 market 规则",
        "revert P7 PR",
    ):
        assert token in doc


def test_alerts_doc_defines_p8_user_and_deployment_boundaries() -> None:
    doc = _read_doc()

    for token in (
        "## P8 用户配置与部署边界",
        "`AGENT_EVENT_MONITOR_ENABLED`",
        "`AGENT_EVENT_MONITOR_INTERVAL_MINUTES`",
        "`NOTIFICATION_ALERT_CHANNELS`",
        "`route_type=alert`",
        "Alert API / Web 告警中心持久化规则",
        "legacy `AGENT_EVENT_ALERT_RULES_JSON`",
        "只兼容 `single_symbol`",
        "P5 技术指标、P6 watchlist/portfolio 或 P7 market light",
        "docker/Dockerfile",
        "`python main.py --schedule`",
        "保留 `data/` 数据库卷",
        ".github/workflows/00-daily-analysis.yml",
        "一次性分析 workflow",
        "不运行 `--schedule` 后台 alert worker",
        "没有映射 `AGENT_EVENT_*`",
        "`/alerts`",
        "Desktop 不新增原生告警管理界面",
        "`triggered`、`skipped`、`degraded`、`failed`",
        "`rule_id + target + data_source + data_timestamp`",
        "回滚 P8 只需 revert 文档、配置说明和 Web 文案改动",
    ):
        assert token in doc


def test_changelog_mentions_alert_p6_release_note() -> None:
    changelog = (PROJECT_ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "P6" in changelog
    assert "관심 종목" in changelog
    assert "보유 종목" in changelog
    assert "계좌 연동 규칙" in changelog


def test_changelog_mentions_alert_p8_docs_closeout() -> None:
    changelog = (PROJECT_ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "[文档] 补齐告警中心 P8 文档与配置收口说明" in changelog
    assert "GitHub Actions 与 Desktop 边界" in changelog


def test_changelog_unreleased_keeps_flat_entries() -> None:
    changelog = (PROJECT_ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]

    assert "\n### " not in unreleased
