# -*- coding: utf-8 -*-
"""Operational layer for scheduled scanner runs and watchlist delivery."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from zoneinfo import ZoneInfo

from src.config import Config, get_config
from src.core.scanner_profile import get_scanner_profile
from src.core.trading_calendar import MARKET_TIMEZONE, is_market_open
from src.notification import NotificationService
from src.services.market_scanner_service import MarketScannerService, ScannerRuntimeError
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)


class MarketScannerOperationsService:
    """Thin orchestration layer for scanner schedule + notification workflows."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        scanner_service: Optional[MarketScannerService] = None,
        config: Optional[Config] = None,
        notifier_factory: Optional[Callable[[], NotificationService]] = None,
    ) -> None:
        self.config = config or get_config()
        self.scanner_service = scanner_service or MarketScannerService(db_manager=db_manager)
        self.notifier_factory = notifier_factory or NotificationService

    def run_manual_scan(
        self,
        *,
        market: str = "cn",
        profile: Optional[str] = None,
        shortlist_size: Optional[int] = None,
        universe_limit: Optional[int] = None,
        detail_limit: Optional[int] = None,
        request_source: str = "api",
        notify: bool = False,
    ) -> Dict[str, Any]:
        return self._run_scan_workflow(
            market=market,
            profile=profile,
            shortlist_size=shortlist_size,
            universe_limit=universe_limit,
            detail_limit=detail_limit,
            trigger_mode="manual",
            request_source=request_source,
            notify=notify,
            raise_on_failure=True,
        )

    def run_cli_scan(
        self,
        *,
        market: str = "cn",
        profile: Optional[str] = None,
        notify: bool = True,
    ) -> Dict[str, Any]:
        return self.run_manual_scan(
            market=market,
            profile=profile,
            request_source="cli",
            notify=notify,
        )

    def run_scheduled_scan(
        self,
        *,
        force_run: bool = False,
    ) -> Dict[str, Any]:
        profile = getattr(self.config, "scanner_profile", "cn_preopen_v1") or "cn_preopen_v1"
        resolved_profile = get_scanner_profile(market="cn", profile=profile)
        watchlist_date = self._resolve_watchlist_date(resolved_profile.market)

        if (
            not force_run
            and getattr(self.config, "trading_day_check_enabled", True)
            and not self._is_trading_day(resolved_profile.market)
        ):
            return {
                "status": "skipped",
                "market": resolved_profile.market,
                "profile": resolved_profile.key,
                "profile_label": resolved_profile.label,
                "watchlist_date": watchlist_date,
                "message": "今日为非交易日，已跳过盘前扫描。",
            }

        return self._run_scan_workflow(
            market=resolved_profile.market,
            profile=resolved_profile.key,
            trigger_mode="scheduled",
            request_source="scheduler",
            notify=getattr(self.config, "scanner_notification_enabled", True),
            raise_on_failure=False,
        )

    def get_operational_status(
        self,
        *,
        market: str = "cn",
        profile: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_profile = get_scanner_profile(market=market, profile=profile)
        return self.scanner_service.get_operational_status(
            market=resolved_profile.market,
            profile=resolved_profile.key,
            schedule_enabled=getattr(self.config, "scanner_schedule_enabled", False),
            schedule_time=getattr(self.config, "scanner_schedule_time", None),
            schedule_run_immediately=getattr(self.config, "scanner_schedule_run_immediately", False),
            notification_enabled=getattr(self.config, "scanner_notification_enabled", True),
        )

    def _run_scan_workflow(
        self,
        *,
        market: str,
        profile: Optional[str],
        shortlist_size: Optional[int] = None,
        universe_limit: Optional[int] = None,
        detail_limit: Optional[int] = None,
        trigger_mode: str,
        request_source: str,
        notify: bool,
        raise_on_failure: bool,
    ) -> Dict[str, Any]:
        resolved_profile = get_scanner_profile(market=market, profile=profile)
        watchlist_date = self._resolve_watchlist_date(resolved_profile.market)

        try:
            detail = self.scanner_service.run_scan(
                market=resolved_profile.market,
                profile=resolved_profile.key,
                shortlist_size=shortlist_size,
                universe_limit=universe_limit,
                detail_limit=detail_limit,
            )
        except ValueError as exc:
            message = str(exc)
            if self._is_empty_watchlist_message(message):
                detail = self.scanner_service.record_terminal_run(
                    market=resolved_profile.market,
                    profile=resolved_profile.key,
                    profile_label=resolved_profile.label,
                    universe_name=resolved_profile.universe_name,
                    status="empty",
                    headline="今日 A 股盘前未筛出满足条件的观察名单",
                    trigger_mode=trigger_mode,
                    request_source=request_source,
                    watchlist_date=watchlist_date,
                    source_summary="scanner=empty",
                    diagnostics={
                        "empty_reason": message,
                    },
                    universe_notes=[
                        "本次运行未筛出满足条件的候选。可复核当日市场活跃度、流动性过滤条件与历史样本完备性。",
                    ],
                    scoring_notes=self.scanner_service._build_scoring_notes(),
                    shortlist=[],
                )
            else:
                failure_diagnostics = dict(exc.diagnostics) if isinstance(exc, ScannerRuntimeError) else None
                detail = self.scanner_service.record_failed_run(
                    market=resolved_profile.market,
                    profile=resolved_profile.key,
                    profile_label=resolved_profile.label,
                    universe_name=resolved_profile.universe_name,
                    trigger_mode=trigger_mode,
                    request_source=request_source,
                    watchlist_date=watchlist_date,
                    error_message=message,
                    diagnostics=failure_diagnostics,
                    source_summary=exc.source_summary if isinstance(exc, ScannerRuntimeError) else None,
                )
                if raise_on_failure:
                    raise
        except Exception as exc:
            detail = self.scanner_service.record_failed_run(
                market=resolved_profile.market,
                profile=resolved_profile.key,
                profile_label=resolved_profile.label,
                universe_name=resolved_profile.universe_name,
                trigger_mode=trigger_mode,
                request_source=request_source,
                watchlist_date=watchlist_date,
                error_message=str(exc),
                diagnostics=dict(exc.diagnostics) if isinstance(exc, ScannerRuntimeError) else None,
                source_summary=exc.source_summary if isinstance(exc, ScannerRuntimeError) else None,
            )
            if raise_on_failure:
                raise

        updated_detail = self.scanner_service.update_run_operation_metadata(
            detail["id"],
            trigger_mode=trigger_mode,
            watchlist_date=watchlist_date,
            request_source=request_source,
        ) or detail

        if notify and updated_detail.get("status") in {"completed", "empty"}:
            notification_result = self._deliver_watchlist_notification(updated_detail)
            updated_detail = self.scanner_service.update_run_operation_metadata(
                updated_detail["id"],
                trigger_mode=trigger_mode,
                watchlist_date=watchlist_date,
                request_source=request_source,
                notification_result=notification_result,
            ) or updated_detail

        return updated_detail

    @staticmethod
    def _is_empty_watchlist_message(message: str) -> bool:
        return any(
            token in (message or "")
            for token in (
                "扫描宇宙为空",
                "详细评估阶段未留下有效候选",
            )
        )

    def _resolve_watchlist_date(self, market: str) -> str:
        tz_name = MARKET_TIMEZONE.get((market or "").strip().lower(), "Asia/Shanghai")
        return datetime.now(ZoneInfo(tz_name)).date().isoformat()

    def _is_trading_day(self, market: str) -> bool:
        tz_name = MARKET_TIMEZONE.get((market or "").strip().lower(), "Asia/Shanghai")
        market_now = datetime.now(ZoneInfo(tz_name))
        return is_market_open(market, market_now.date())

    def _deliver_watchlist_notification(self, detail: Dict[str, Any]) -> Dict[str, Any]:
        if not getattr(self.config, "scanner_notification_enabled", True):
            return {
                "attempted": False,
                "status": "skipped",
                "success": None,
                "channels": [],
                "message": "scanner notification disabled",
            }

        notifier = self.notifier_factory()
        content = self.build_watchlist_notification(detail)
        report_path = None
        try:
            filename = f"scanner_watchlist_{str(detail.get('watchlist_date') or '').replace('-', '')}.md"
            report_path = notifier.save_report_to_file(content, filename)
        except Exception as exc:
            logger.warning("保存 scanner watchlist 文件失败: %s", exc)

        channels = []
        try:
            channels = [channel.value for channel in notifier.get_available_channels()]
        except Exception:
            channels = []

        if not notifier.is_available():
            return {
                "attempted": False,
                "status": "not_configured",
                "success": None,
                "channels": channels,
                "message": "no configured notification channel",
                "report_path": report_path,
            }

        try:
            success = bool(notifier.send(content, email_send_to_all=True))
            return {
                "attempted": True,
                "status": "success" if success else "failed",
                "success": success,
                "channels": channels,
                "message": None if success else "notification service returned false",
                "report_path": report_path,
                "sent_at": datetime.now().isoformat(),
            }
        except Exception as exc:
            logger.exception("Scanner notification failed: %s", exc)
            return {
                "attempted": True,
                "status": "failed",
                "success": False,
                "channels": channels,
                "message": str(exc),
                "report_path": report_path,
                "sent_at": datetime.now().isoformat(),
            }

    @staticmethod
    def build_watchlist_notification(detail: Dict[str, Any]) -> str:
        watchlist_date = detail.get("watchlist_date") or detail.get("run_at", "")[:10]
        profile_label = detail.get("profile_label") or detail.get("profile") or "Scanner"
        headline = detail.get("headline") or "A 股盘前观察名单"
        status = str(detail.get("status") or "completed")
        shortlist = detail.get("shortlist") or []
        diagnostics = detail.get("diagnostics") if isinstance(detail.get("diagnostics"), dict) else {}
        history_stats = diagnostics.get("history_stats") if isinstance(diagnostics.get("history_stats"), dict) else {}

        lines = [
            f"# 🔎 {headline}",
            "",
            f"- 日期: {watchlist_date}",
            f"- 配置: {profile_label}",
            f"- 触发: {detail.get('trigger_mode') or 'manual'}",
            f"- 运行时间: {detail.get('run_at') or '--'}",
            f"- 候选池: {detail.get('universe_size') or 0} | 详细评估: {detail.get('evaluated_size') or 0} | Shortlist: {detail.get('shortlist_size') or 0}",
            f"- 历史补数: 本地 {history_stats.get('local_hits', 0)} / 在线 {history_stats.get('network_fetches', 0)}",
            "",
        ]

        if status == "empty" or not shortlist:
            lines.extend(
                [
                    "## 今日结论",
                    "",
                    "今日未筛出满足当前规则阈值的盘前观察名单。",
                    "建议继续观察竞价强度、板块轮动和盘中量能确认，不要把“无 shortlist”误读为系统静默失败。",
                ]
            )
            return "\n".join(lines)

        lines.append("## 今日观察名单")
        lines.append("")
        for candidate in shortlist:
            reasons = candidate.get("reasons") or []
            risk_notes = candidate.get("risk_notes") or []
            watch_context = candidate.get("watch_context") or []
            primary_reason = candidate.get("reason_summary") or (reasons[0] if reasons else "满足规则筛选条件。")
            primary_risk = risk_notes[0] if risk_notes else "仍需结合竞价与板块确认。"
            primary_watch = watch_context[0].get("value") if watch_context and isinstance(watch_context[0], dict) else "观察强弱确认。"
            lines.extend(
                [
                    f"### #{candidate.get('rank')} {candidate.get('symbol')} {candidate.get('name')} | Score {float(candidate.get('score') or 0.0):.1f}",
                    f"- 原因: {primary_reason}",
                    f"- 风险: {primary_risk}",
                    f"- 观察: {primary_watch}",
                    "",
                ]
            )

        return "\n".join(lines)
