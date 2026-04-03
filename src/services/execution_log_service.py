# -*- coding: utf-8 -*-
"""
Execution log service for admin observability (D2).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.storage import get_db

_SECRET_PATTERNS = [
    re.compile(r"(https?://)[^/\s]+/[^\s]+", re.IGNORECASE),
    re.compile(r"(token|secret|password|webhook)[=:]\s*([^\s,;]+)", re.IGNORECASE),
]

_NOTIFICATION_STATES = {"success", "partial_success", "timeout_unknown", "failed", "not_configured"}


def _masked_message(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    masked = str(text)
    for pattern in _SECRET_PATTERNS:
        masked = pattern.sub(r"\1***" if pattern.pattern.startswith("(https?://)") else r"\1=***", masked)
    return masked[:400] if masked else None


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _status_from_attempt_result(value: Any) -> str:
    status = _as_str(value).lower()
    if not status:
        return "unknown"
    if status in {"ok", "success"}:
        return "succeeded"
    if status in {"partial"}:
        return "partial_success"
    if status in {"failed", "error"}:
        return "failed"
    if status in {"timeout", "timed_out"}:
        return "timed_out"
    if status in {"succeeded", "failed", "empty_result", "invalid_response", "insufficient_fields", "skipped_because_previous_succeeded", "switched_to_fallback"}:
        return status
    return status


def _action_from_status(status: Any) -> str:
    normalized = _as_str(status).lower()
    if normalized in {"attempting", "waiting", "running"}:
        return "attempting"
    if normalized in {"succeeded", "success", "ok"}:
        return "succeeded"
    if normalized in {"failed", "error"}:
        return "failed"
    if normalized in {"timed_out", "timeout", "timeout_unknown"}:
        return "timeout"
    if normalized in {"switched_to_fallback", "switched"}:
        return "switched"
    if normalized in {"empty_result"}:
        return "empty_result"
    if normalized in {"invalid_response"}:
        return "invalid_response"
    if normalized in {"insufficient_fields"}:
        return "insufficient_fields"
    if normalized in {"skipped_because_previous_succeeded"}:
        return "skipped"
    if normalized in {"partial_success", "partial"}:
        return "completed"
    if normalized in {"not_configured"}:
        return "skipped"
    if normalized in {"selected", "configured"}:
        return "selected"
    if normalized in {"completed"}:
        return "completed"
    return "unknown"


def _outcome_from_status(status: Any) -> str:
    normalized = _as_str(status).lower()
    if normalized in {"succeeded", "success", "ok", "completed"}:
        return "ok"
    if normalized in {"partial", "partial_success"}:
        return "partial"
    if normalized in {"timeout", "timed_out", "timeout_unknown"}:
        return "timeout"
    if normalized in {"failed", "error", "empty_result", "invalid_response", "insufficient_fields"}:
        return "failed"
    if normalized in {"not_configured", "skipped", "skipped_because_previous_succeeded"}:
        return "ok"
    if normalized in {"switched_to_fallback", "switched"}:
        return "ok"
    return "unknown"


def _data_phase(key: str) -> str:
    mapping = {
        "market": "data_market",
        "fundamentals": "data_fundamentals",
        "news": "data_news",
        "sentiment": "data_sentiment",
    }
    return mapping.get(key, f"data_{key}")


def classify_notification_state(notification: Dict[str, Any]) -> str:
    attempted = bool(notification.get("attempted"))
    raw_status = _as_str(notification.get("status")).lower()
    success = notification.get("success")
    error = _as_str(notification.get("error")).lower()
    channels = notification.get("channels") or []

    if not attempted and raw_status in {"not_configured", "skipped"}:
        return "not_configured"
    if raw_status in {"partial", "partial_success"}:
        return "partial_success"
    if raw_status in {"ok", "success"} or success is True:
        return "success"
    if "timeout" in raw_status or "timeout" in error or "timed out" in error:
        return "timeout_unknown"
    if attempted and success is False and len(channels) > 1:
        return "partial_success"
    if attempted and (raw_status in {"failed", "error"} or success is False):
        return "failed"
    if not attempted and channels:
        return "not_configured"
    return "failed" if attempted else "not_configured"


class ExecutionLogService:
    """Write/read structured execution logs for admin-only observability."""

    def __init__(self):
        self.db = get_db()

    def start_session(
        self,
        *,
        task_id: str,
        stock_code: str,
        stock_name: Optional[str],
        configured_execution: Optional[Dict[str, Any]],
    ) -> str:
        session_id = uuid.uuid4().hex
        started_at = datetime.now()
        self.db.create_execution_log_session(
            session_id=session_id,
            task_id=task_id,
            code=stock_code,
            name=stock_name,
            overall_status="running",
            truth_level="mixed",
            summary={"configured_execution": configured_execution or {}},
            started_at=started_at,
        )
        self.db.append_execution_log_event(
            session_id=session_id,
            phase="system",
            step="task_started",
            target=stock_code,
            status="started",
            truth_level="actual",
            message=f"Task {task_id} started",
            detail={"configured_execution": configured_execution or {}},
            event_at=started_at,
        )
        self._append_configured_events(session_id, configured_execution or {})
        return session_id

    def _append_configured_events(self, session_id: str, configured: Dict[str, Any]) -> None:
        ai = configured.get("ai") if isinstance(configured, dict) else {}
        data = configured.get("data") if isinstance(configured, dict) else {}
        notification = configured.get("notification") if isinstance(configured, dict) else {}

        if isinstance(ai, dict):
            primary_gateway = _as_str(ai.get("configured_primary_gateway")) or _as_str(ai.get("gateway"))
            backup_gateway = _as_str(ai.get("configured_backup_gateway"))
            primary_model = _as_str(ai.get("configured_primary_model")) or _as_str(ai.get("model"))

            if primary_gateway:
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="ai_route",
                    step="primary_selected",
                    target=primary_gateway,
                    status="selected",
                    truth_level="inferred",
                    message=f"Primary AI gateway selected: {primary_gateway}",
                    detail={"category": "ai_route", "action": "selected"},
                )
            if backup_gateway:
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="ai_route",
                    step="backup_selected",
                    target=backup_gateway,
                    status="selected",
                    truth_level="inferred",
                    message=f"Backup AI gateway selected: {backup_gateway}",
                    detail={"category": "ai_route", "action": "selected"},
                )
            if primary_model:
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="ai_model",
                    step="primary_selected",
                    target=primary_model,
                    status="selected",
                    truth_level=str(ai.get("model_truth") or "inferred"),
                    message=f"Primary AI model selected: {primary_model}",
                    detail={
                        "category": "ai_model",
                        "action": "selected",
                        "configured_primary_model": ai.get("configured_primary_model"),
                    },
                )

            self.db.append_execution_log_event(
                session_id=session_id,
                phase="ai_model",
                step="configured",
                target=_as_str(ai.get("model")) or _as_str(ai.get("provider")) or "ai_route",
                status="attempting",
                truth_level=str(ai.get("model_truth") or "inferred"),
                detail={"category": "ai_model", "action": "attempting", "configured_primary_model": ai.get("configured_primary_model")},
            )

        for key in ("market", "fundamentals", "news", "sentiment"):
            phase = _data_phase(key)
            block = data.get(key) if isinstance(data, dict) else {}
            if not isinstance(block, dict):
                continue
            target = _as_str(block.get("source")) or phase
            source_chain = block.get("source_chain") or []
            status = _as_str(block.get("status")).lower() or ("attempting" if target else "not_configured")
            self.db.append_execution_log_event(
                session_id=session_id,
                phase=phase,
                step="configured",
                target=target,
                status=status,
                truth_level=str(block.get("truth") or "inferred"),
                message=f"{phase} route configured: {target}",
                detail={"category": phase, "action": "selected", "source_chain": source_chain},
            )

        if isinstance(notification, dict):
            channels = notification.get("channels") if isinstance(notification.get("channels"), list) else []
            status = "selected" if channels else "not_configured"
            self.db.append_execution_log_event(
                session_id=session_id,
                phase="notification",
                step="channel_selected",
                target=(channels[0] if channels else "notification"),
                status=status,
                truth_level=str(notification.get("truth") or "inferred"),
                message=f"Notification channels configured: {', '.join(channels) if channels else 'none'}",
                detail={"category": "notification", "action": "selected" if channels else "skipped", "channels": channels},
            )

    def append_runtime_result(
        self,
        *,
        session_id: str,
        runtime_execution: Optional[Dict[str, Any]],
        notification_result: Optional[Dict[str, Any]],
        query_id: Optional[str],
        overall_status: str,
    ) -> None:
        runtime = runtime_execution if isinstance(runtime_execution, dict) else {}
        ai = runtime.get("ai") if isinstance(runtime.get("ai"), dict) else {}
        data = runtime.get("data") if isinstance(runtime.get("data"), dict) else {}
        notification = notification_result if isinstance(notification_result, dict) else (
            runtime.get("notification") if isinstance(runtime.get("notification"), dict) else {}
        )

        if ai:
            primary_gateway = _as_str(ai.get("gateway")) or _as_str(ai.get("configured_primary_gateway"))
            backup_gateway = _as_str(ai.get("configured_backup_gateway"))
            final_model = _as_str(ai.get("model"))
            route_succeeded = bool(final_model)
            ai_attempt_chain = ai.get("attempt_chain") if isinstance(ai.get("attempt_chain"), list) else []

            if primary_gateway:
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="ai_route",
                    step="primary_invoked",
                    target=primary_gateway,
                    status="succeeded" if route_succeeded else "failed",
                    truth_level=str(ai.get("gateway_truth") or "actual"),
                    message=(
                        f"Primary AI gateway {primary_gateway} invoked successfully."
                        if route_succeeded
                        else f"Primary AI gateway {primary_gateway} invocation failed."
                    ),
                    detail={
                        "category": "ai_route",
                        "action": "succeeded" if route_succeeded else "failed",
                        "outcome": _outcome_from_status("succeeded" if route_succeeded else "failed"),
                    },
                )
            if bool(ai.get("fallback_occurred")) and backup_gateway:
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="ai_route",
                    step="fallback_switched",
                    target=backup_gateway,
                    status="switched_to_fallback",
                    truth_level="actual",
                    message=f"AI route switched to backup gateway {backup_gateway}",
                    detail={"category": "ai_route", "action": "switched", "outcome": "ok"},
                )
            if ai_attempt_chain:
                for idx, attempt in enumerate(ai_attempt_chain):
                    if not isinstance(attempt, dict):
                        continue
                    model_name = _as_str(attempt.get("model")) or final_model or "ai_model"
                    status = _status_from_attempt_result(
                        attempt.get("result") or attempt.get("status") or attempt.get("outcome")
                    )
                    message = _masked_message(
                        _as_str(attempt.get("message")) or _as_str(attempt.get("reason"))
                    )
                    reason = _masked_message(_as_str(attempt.get("reason")))
                    self.db.append_execution_log_event(
                        session_id=session_id,
                        phase="ai_model",
                        step=f"attempt_{idx + 1}",
                        target=model_name,
                        status=status,
                        truth_level=str(ai.get("model_truth") or "actual"),
                        message=message,
                        detail={
                            "category": "ai_model",
                            "action": _as_str(attempt.get("action")) or _action_from_status(status),
                            "outcome": _outcome_from_status(status),
                            "reason": reason,
                            "attempt": attempt,
                        },
                    )
                    if idx < len(ai_attempt_chain) - 1 and status in {
                        "failed",
                        "timed_out",
                        "timeout",
                        "empty_result",
                        "invalid_response",
                        "insufficient_fields",
                    }:
                        next_attempt = ai_attempt_chain[idx + 1] if isinstance(ai_attempt_chain[idx + 1], dict) else {}
                        next_model = _as_str(next_attempt.get("model")) or "fallback_model"
                        self.db.append_execution_log_event(
                            session_id=session_id,
                            phase="ai_model",
                            step="fallback",
                            target=next_model,
                            status="switched_to_fallback",
                            truth_level="actual",
                            message=f"Switched to fallback AI model: {next_model}",
                            detail={"category": "ai_model", "action": "switched", "outcome": "ok"},
                        )
            elif final_model:
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="ai_model",
                    step="attempt_1",
                    target=final_model,
                    status="attempting",
                    truth_level=str(ai.get("model_truth") or "actual"),
                    message=f"AI model attempt: {final_model}",
                    detail={"category": "ai_model", "action": "attempting", "outcome": "unknown"},
                )
            self.db.append_execution_log_event(
                session_id=session_id,
                phase="ai_model",
                step="final_success" if final_model else "final_failed",
                target=final_model or _as_str(ai.get("provider")) or "ai",
                status="succeeded" if final_model else "failed",
                truth_level=str(ai.get("model_truth") or "actual"),
                message=(
                    f"Final AI model succeeded: {final_model}"
                    if final_model
                    else "AI model failed to produce a final result."
                ),
                detail={
                    "category": "ai_model",
                    "action": "succeeded" if final_model else "failed",
                    "provider": ai.get("provider"),
                    "gateway": ai.get("gateway"),
                    "fallback_occurred": bool(ai.get("fallback_occurred")),
                    "outcome": _outcome_from_status("succeeded" if final_model else "failed"),
                },
            )

        self._append_data_events(session_id, data)
        self._append_notification_events(session_id, notification)

        self.db.finalize_execution_log_session(
            session_id=session_id,
            overall_status=overall_status,
            truth_level="mixed",
            query_id=query_id,
            summary={
                "runtime_execution": runtime,
                "notification_result": notification,
            },
            ended_at=datetime.now(),
        )
        self.db.attach_execution_session_to_query(session_id=session_id, query_id=query_id)

    def _append_data_events(self, session_id: str, data: Dict[str, Any]) -> None:
        for key in ("market", "fundamentals", "news", "sentiment"):
            phase = _data_phase(key)
            block = data.get(key) if isinstance(data, dict) else {}
            if not isinstance(block, dict):
                continue

            source_chain = block.get("source_chain")
            if isinstance(source_chain, list) and source_chain:
                for idx, attempt in enumerate(source_chain):
                    if not isinstance(attempt, dict):
                        continue
                    explicit_action = _as_str(attempt.get("action")).lower()
                    if explicit_action == "selected":
                        continue
                    target = (
                        _as_str(attempt.get("provider"))
                        or _as_str(attempt.get("source"))
                        or _as_str(attempt.get("target"))
                        or f"{phase}-attempt-{idx + 1}"
                    )
                    status = _status_from_attempt_result(
                        attempt.get("result") or attempt.get("status") or attempt.get("outcome")
                    )
                    reason = _masked_message(_as_str(attempt.get("reason")))
                    message = _masked_message(
                        _as_str(attempt.get("message"))
                        or reason
                        or _as_str(attempt.get("note"))
                    )
                    self.db.append_execution_log_event(
                        session_id=session_id,
                        phase=phase,
                        step=f"attempt_{idx + 1}",
                        target=target,
                        status=status,
                        truth_level="actual",
                        message=message,
                        detail={
                            "category": phase,
                            "action": _as_str(attempt.get("action")) or _action_from_status(status),
                            "outcome": _outcome_from_status(status),
                            "reason": reason,
                            "attempt": attempt,
                        },
                    )
                    if idx < len(source_chain) - 1 and status in {
                        "failed",
                        "timed_out",
                        "timeout",
                        "empty_result",
                        "invalid_response",
                        "insufficient_fields",
                    }:
                        next_attempt = source_chain[idx + 1] if isinstance(source_chain[idx + 1], dict) else {}
                        next_target = (
                            _as_str(next_attempt.get("provider"))
                            or _as_str(next_attempt.get("source"))
                            or _as_str(next_attempt.get("target"))
                            or "fallback"
                        )
                        self.db.append_execution_log_event(
                            session_id=session_id,
                            phase=phase,
                            step="fallback",
                            target=next_target,
                            status="switched_to_fallback",
                            truth_level="actual",
                            message=f"Fallback switched from {target} to {next_target}",
                            detail={"category": phase, "action": "switched", "outcome": "ok"},
                        )
                final_target = _as_str(block.get("source")) or (
                    _as_str(source_chain[-1].get("provider")) if isinstance(source_chain[-1], dict) else ""
                ) or phase
                final_status = _as_str(block.get("status")).lower() or "succeeded"
                final_reason = _masked_message(_as_str(block.get("final_reason")))
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase=phase,
                    step="final",
                    target=final_target,
                    status=final_status,
                    truth_level=str(block.get("truth") or "actual"),
                    message=(
                        f"Final source selected: {final_target}. {final_reason}"
                        if final_reason
                        else f"Final source selected: {final_target}"
                    ),
                    detail={
                        "category": phase,
                        "action": _action_from_status(final_status),
                        "fallback_occurred": bool(block.get("fallback_occurred")),
                        "outcome": _outcome_from_status(final_status),
                        "reason": final_reason,
                    },
                )
            else:
                target = _as_str(block.get("source")) or phase
                status = _as_str(block.get("status")).lower() or "unknown"
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase=phase,
                    step="final",
                    target=target,
                    status=status,
                    truth_level=str(block.get("truth") or "inferred"),
                    message=f"Source result: {target} ({status})",
                    detail={
                        "category": phase,
                        "action": _action_from_status(status),
                        "fallback_occurred": bool(block.get("fallback_occurred")),
                        "outcome": _outcome_from_status(status),
                    },
                )

    def _append_notification_events(self, session_id: str, notification: Dict[str, Any]) -> None:
        if not isinstance(notification, dict):
            notification = {}
        channels = notification.get("channels") if isinstance(notification.get("channels"), list) else []
        attempt_chain = notification.get("attempts") if isinstance(notification.get("attempts"), list) else []
        final_state = _as_str(notification.get("delivery_classification")).lower() or classify_notification_state(notification)
        if final_state not in _NOTIFICATION_STATES:
            final_state = "failed"

        if not channels:
            self.db.append_execution_log_event(
                session_id=session_id,
                phase="notification",
                step="final",
                target="notification",
                status=final_state,
                truth_level=str(notification.get("truth") or "actual"),
                message=_masked_message(notification.get("error")),
                detail={
                    "category": "notification",
                    "action": _action_from_status(final_state),
                    "channels": [],
                    "outcome": _outcome_from_status(final_state),
                },
            )
            return

        if attempt_chain:
            for idx, attempt in enumerate(attempt_chain):
                if not isinstance(attempt, dict):
                    continue
                channel = _as_str(attempt.get("channel")) or _as_str(attempt.get("target")) or str(channels[0])
                status = _status_from_attempt_result(
                    attempt.get("result") or attempt.get("status") or attempt.get("outcome")
                )
                reason = _masked_message(_as_str(attempt.get("reason")))
                message = _masked_message(
                    _as_str(attempt.get("message"))
                    or reason
                    or f"Notification attempt on channel {channel}"
                )
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="notification",
                    step=f"attempt_{idx + 1}",
                    target=channel,
                    status=status,
                    truth_level=str(notification.get("truth") or "actual"),
                    message=message,
                    detail={
                        "category": "notification",
                        "action": _as_str(attempt.get("action")) or _action_from_status(status),
                        "channels": channels,
                        "reason": reason,
                        "outcome": _outcome_from_status(status),
                        "attempt": attempt,
                    },
                )
                if idx < len(attempt_chain) - 1 and status in {"failed", "timed_out", "timeout", "empty_result", "invalid_response"}:
                    next_attempt = attempt_chain[idx + 1] if isinstance(attempt_chain[idx + 1], dict) else {}
                    next_channel = _as_str(next_attempt.get("channel")) or _as_str(next_attempt.get("target")) or "backup_channel"
                    self.db.append_execution_log_event(
                        session_id=session_id,
                        phase="notification",
                        step="fallback",
                        target=next_channel,
                        status="switched_to_fallback",
                        truth_level="actual",
                        message=f"Notification fallback switched to {next_channel}",
                        detail={"category": "notification", "action": "switched", "outcome": "ok"},
                    )
        else:
            for idx, channel in enumerate(channels):
                self.db.append_execution_log_event(
                    session_id=session_id,
                    phase="notification",
                    step=f"attempt_{idx + 1}",
                    target=str(channel),
                    status="attempting",
                    truth_level=str(notification.get("truth") or "actual"),
                    message=f"Attempt notification channel: {channel}",
                    detail={"category": "notification", "action": "attempting", "channels": channels, "outcome": "unknown"},
                )
        self.db.append_execution_log_event(
            session_id=session_id,
            phase="notification",
            step="final",
            target=str(channels[0]),
            status=final_state,
            truth_level=str(notification.get("truth") or "actual"),
            message=_masked_message(notification.get("error")),
            detail={
                "category": "notification",
                "action": _action_from_status(final_state),
                "raw_status": notification.get("status"),
                "success": notification.get("success"),
                "outcome": _outcome_from_status(final_state),
            },
        )

    def fail_session(self, *, session_id: str, error_message: str, query_id: Optional[str] = None) -> None:
        self.db.append_execution_log_event(
            session_id=session_id,
            phase="system",
            step="task_failed",
            target="analysis",
            status="failed",
            truth_level="actual",
            message=_masked_message(error_message),
        )
        self.db.finalize_execution_log_session(
            session_id=session_id,
            overall_status="failed",
            truth_level="actual",
            query_id=query_id,
            summary={"error": _masked_message(error_message)},
            ended_at=datetime.now(),
        )

    @staticmethod
    def _runtime_from_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(summary, dict):
            return {}
        runtime = summary.get("runtime_execution")
        if isinstance(runtime, dict):
            return runtime
        configured = summary.get("configured_execution")
        if isinstance(configured, dict):
            return configured
        return {}

    @staticmethod
    def _extract_final_sources(runtime: Dict[str, Any]) -> Dict[str, Optional[str]]:
        data = runtime.get("data") if isinstance(runtime.get("data"), dict) else {}
        def _source(key: str) -> Optional[str]:
            block = data.get(key) if isinstance(data, dict) else {}
            if not isinstance(block, dict):
                return None
            source = _as_str(block.get("source"))
            return source or None
        return {
            "market": _source("market"),
            "fundamentals": _source("fundamentals"),
            "news": _source("news"),
            "sentiment": _source("sentiment"),
        }

    @staticmethod
    def _event_attempt_count(events: List[Dict[str, Any]], phase: str) -> int:
        return sum(
            1
            for event in events
            if str(event.get("phase") or "").strip().lower() == phase
            and str(event.get("step") or "").strip().lower().startswith("attempt_")
        )

    @staticmethod
    def _event_has_fallback(events: List[Dict[str, Any]], phase_prefix: str) -> bool:
        for event in events:
            phase = str(event.get("phase") or "").strip().lower()
            step = str(event.get("step") or "").strip().lower()
            status = str(event.get("status") or "").strip().lower()
            if phase.startswith(phase_prefix) and (
                step == "fallback" or status == "switched_to_fallback"
            ):
                return True
        return False

    @staticmethod
    def _top_failure_reason(
        *,
        events: Optional[List[Dict[str, Any]]] = None,
        summary: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        for event in events or []:
            status = str(event.get("status") or "").strip().lower()
            if status in {"failed", "timed_out", "timeout_unknown"}:
                msg = _masked_message(_as_str(event.get("message")))
                if msg:
                    return msg
        if isinstance(summary, dict):
            msg = _masked_message(_as_str(summary.get("error")))
            if msg:
                return msg
        return None

    @staticmethod
    def _phase_attempt_events(events: List[Dict[str, Any]], phase: str) -> List[Dict[str, Any]]:
        phase_key = str(phase or "").strip().lower()
        attempts: List[Dict[str, Any]] = []
        for event in events or []:
            current_phase = str(event.get("phase") or "").strip().lower()
            if current_phase != phase_key:
                continue
            step = str(event.get("step") or "").strip().lower()
            if step.startswith("attempt_"):
                attempts.append(event)
        return attempts

    @staticmethod
    def _build_chain_narrative(label: str, attempts: List[Dict[str, Any]], final_target: Optional[str]) -> Optional[str]:
        if not attempts:
            if final_target:
                return f"{label} final source accepted: {final_target}."
            return None
        first = attempts[0]
        first_target = _as_str(first.get("target")) or "unknown"
        first_status = _as_str(first.get("status")).lower()
        final = None
        for item in attempts:
            status = _as_str(item.get("status")).lower()
            if status in {"succeeded", "success", "ok", "partial_success", "completed"}:
                final = item
                break
        if final:
            final_target_name = _as_str(final.get("target")) or final_target or "unknown"
            if final_target_name != first_target:
                reason = _masked_message(_as_str(first.get("message"))) or _masked_message(_as_str(first.get("detail", {}).get("reason")))
                return (
                    f"{label} first attempted {first_target} ({first_status or 'failed'}), then switched and accepted {final_target_name}."
                    + (f" Reason: {reason}" if reason else "")
                )
            return f"{label} attempted {first_target} and succeeded without fallback."
        reason = _masked_message(_as_str(attempts[-1].get("message"))) or _masked_message(_as_str(attempts[-1].get("detail", {}).get("reason")))
        return f"{label} attempts failed; final source unresolved." + (f" Reason: {reason}" if reason else "")

    def build_readable_summary(
        self,
        *,
        overall_status: str,
        summary: Dict[str, Any],
        events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        runtime = self._runtime_from_summary(summary)
        ai = runtime.get("ai") if isinstance(runtime.get("ai"), dict) else {}
        final_ai_model = _as_str(ai.get("model")) or None
        ai_fallback_used = bool(ai.get("fallback_occurred")) or self._event_has_fallback(events or [], "ai_")
        ai_attempts_count = self._event_attempt_count(events or [], "ai_model") + self._event_attempt_count(events or [], "ai")
        if ai_attempts_count <= 0 and final_ai_model:
            ai_attempts_count = 1

        final_sources = self._extract_final_sources(runtime)
        data_fallback_used = bool(
            self._event_has_fallback(events or [], "data_")
            or any(
                bool(
                    ((runtime.get("data") or {}).get(key) or {}).get("fallback_occurred")
                )
                for key in ("market", "fundamentals", "news", "sentiment")
            )
        )

        notification = summary.get("notification_result") if isinstance(summary.get("notification_result"), dict) else (
            runtime.get("notification") if isinstance(runtime.get("notification"), dict) else {}
        )
        notification_classification = (
            _as_str(notification.get("delivery_classification")).lower()
            or classify_notification_state(notification if isinstance(notification, dict) else {})
        )
        if notification_classification not in _NOTIFICATION_STATES:
            notification_classification = "failed"

        failure_reason = self._top_failure_reason(events=events, summary=summary)

        narrative_parts: List[str] = []
        ai_attempts = self._phase_attempt_events(events or [], "ai_model")
        ai_story = self._build_chain_narrative("AI", ai_attempts, final_ai_model)
        if ai_story:
            ai_gateway = _as_str(ai.get("gateway")) or _as_str(ai.get("configured_primary_gateway")) or None
            if ai_gateway:
                narrative_parts.append(f"{ai_story} Gateway: {ai_gateway}.")
            else:
                narrative_parts.append(ai_story)

        market_story = self._build_chain_narrative(
            "Market data",
            self._phase_attempt_events(events or [], "data_market"),
            final_sources.get("market"),
        )
        if market_story:
            narrative_parts.append(market_story)
        fundamental_story = self._build_chain_narrative(
            "Fundamentals",
            self._phase_attempt_events(events or [], "data_fundamentals"),
            final_sources.get("fundamentals"),
        )
        if fundamental_story:
            narrative_parts.append(fundamental_story)
        news_story = self._build_chain_narrative(
            "News",
            self._phase_attempt_events(events or [], "data_news"),
            final_sources.get("news"),
        )
        if news_story:
            narrative_parts.append(news_story)
        sentiment_story = self._build_chain_narrative(
            "Sentiment",
            self._phase_attempt_events(events or [], "data_sentiment"),
            final_sources.get("sentiment"),
        )
        if sentiment_story:
            narrative_parts.append(sentiment_story)

        if notification_classification == "timeout_unknown":
            narrative_parts.append("Notification timed out after send attempt; final delivery is unknown.")
        elif notification_classification == "partial_success":
            narrative_parts.append("Notification had partial success across channels.")
        elif notification_classification == "failed":
            narrative_parts.append("Notification failed.")
        elif notification_classification == "success":
            narrative_parts.append("Notification succeeded.")
        elif notification_classification == "not_configured":
            narrative_parts.append("Notification channel not configured for this run.")

        if failure_reason:
            narrative_parts.append(f"Top failure reason: {failure_reason}")

        summary_paragraph = " ".join(part for part in narrative_parts if part).strip()

        return {
            "final_ai_model": final_ai_model,
            "ai_attempts_count": ai_attempts_count,
            "ai_fallback_used": ai_fallback_used,
            "final_market_source": final_sources.get("market"),
            "final_fundamental_source": final_sources.get("fundamentals"),
            "final_news_source": final_sources.get("news"),
            "final_sentiment_source": final_sources.get("sentiment"),
            "data_fallback_used": data_fallback_used,
            "notification_classification": notification_classification,
            "top_failure_reason": failure_reason,
            "summary_paragraph": summary_paragraph or None,
            "status": _as_str(overall_status) or "unknown",
        }

    def list_sessions(
        self,
        *,
        stock_code: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        channel: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        rows, total = self.db.list_execution_log_sessions(
            stock_code=stock_code,
            status=status,
            category=category,
            provider=provider,
            model=model,
            channel=channel,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        items: List[Dict[str, Any]] = []
        for row in rows:
            summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
            row["readable_summary"] = self.build_readable_summary(
                overall_status=str(row.get("overall_status") or "unknown"),
                summary=summary,
                events=None,
            )
            items.append(row)
        return items, total

    def get_session_detail(self, session_id: str) -> Optional[Dict[str, Any]]:
        detail = self.db.get_execution_log_session_detail(session_id)
        if not detail:
            return None
        summary = detail.get("summary") if isinstance(detail.get("summary"), dict) else {}
        events = detail.get("events") if isinstance(detail.get("events"), list) else []
        enriched_events: List[Dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            detail_block = event.get("detail") if isinstance(event.get("detail"), dict) else {}
            category = _as_str(detail_block.get("category")) or _as_str(event.get("phase")) or "system"
            action = _as_str(detail_block.get("action")) or _action_from_status(event.get("status"))
            outcome = _as_str(detail_block.get("outcome")) or _outcome_from_status(event.get("status"))
            reason = _masked_message(_as_str(detail_block.get("reason")))
            next_event = dict(event)
            next_event["category"] = category
            next_event["action"] = action
            next_event["outcome"] = outcome
            next_event["reason"] = reason
            enriched_events.append(next_event)

        detail["readable_summary"] = self.build_readable_summary(
            overall_status=str(detail.get("overall_status") or "unknown"),
            summary=summary,
            events=enriched_events,
        )
        detail["events"] = enriched_events
        return detail
