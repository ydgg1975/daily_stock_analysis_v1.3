# -*- coding: utf-8 -*-
"""Core DSA actions shared by extension workflows."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from data_provider.base import canonical_stock_code

from src.extensions.action_spec import ActionContext, ActionResult, ActionSpec, ExtensionErrorCode, ExtensionStatus

logger = logging.getLogger("dsa.extensions.dsa.actions")

PLUGIN_ID = "dsa"
PLUGIN_VERSION = "core"

ANALYZE_STOCK_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "stock_code": {"type": "string", "description": "Single stock code to analyze."},
        "stock_codes": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 50,
            "description": "Batch stock codes to submit to the analysis queue.",
        },
        "stock_name": {"type": "string"},
        "report_type": {"type": "string", "default": "detailed"},
        "force_refresh": {"type": "boolean", "default": False},
        "notify": {"type": "boolean", "default": False},
        "original_query": {"type": "string"},
        "selection_source": {"type": "string", "default": "import"},
        "skills": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
    },
    "additionalProperties": False,
}

STOCK_POOL_IMPORT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "stock_codes": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 200,
        },
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["code"],
                "additionalProperties": True,
            },
            "minItems": 1,
            "maxItems": 200,
        },
        "merge": {"type": "boolean", "default": True},
    },
    "additionalProperties": False,
}

NOTIFICATION_SEND_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string", "minLength": 1, "maxLength": 20000},
        "dry_run": {"type": "boolean", "default": False},
    },
    "required": ["content"],
    "additionalProperties": False,
}


def build_dsa_core_actions(config=None) -> List[ActionSpec]:
    """Build internal DSA actions that extension actions can reuse."""

    metadata = {
        "plugin_version": PLUGIN_VERSION,
        "business_category": "dsa_core",
        "internal": True,
    }

    def _analyze_stock(context: ActionContext) -> ActionResult:
        payload = context.input or {}
        codes = _stock_codes_from_payload(payload)
        if not codes:
            return _result(
                context,
                ExtensionStatus.FAILED.value,
                {"tasks": [], "duplicates": []},
                error_code=ExtensionErrorCode.INPUT_INVALID.value,
                diagnostics={"reason": "stock_code or stock_codes is required."},
            )

        max_items = _max_items(context, default=len(codes))
        if len(codes) > max_items:
            return _result(
                context,
                ExtensionStatus.FAILED.value,
                {"tasks": [], "duplicates": []},
                error_code=ExtensionErrorCode.BUDGET_EXCEEDED.value,
                diagnostics={"reason": f"Requested {len(codes)} items exceeds max_items={max_items}."},
            )

        from src.services.task_queue import get_task_queue

        accepted, duplicates = get_task_queue().submit_tasks_batch(
            codes,
            stock_name=_optional_text(payload.get("stock_name")),
            original_query=_optional_text(payload.get("original_query")) or f"extension:{context.run_id}",
            selection_source=_optional_text(payload.get("selection_source")) or "import",
            report_type=str(payload.get("report_type") or "detailed"),
            force_refresh=bool(payload.get("force_refresh", False)),
            notify=bool(payload.get("notify", False)),
            skills=_string_list(payload.get("skills")),
        )
        status = ExtensionStatus.COMPLETED.value if accepted and not duplicates else ExtensionStatus.PARTIAL.value
        if not accepted and duplicates:
            status = ExtensionStatus.FAILED.value
        return _result(
            context,
            status,
            {
                "tasks": [task.to_dict() for task in accepted],
                "duplicates": [
                    {
                        "stock_code": duplicate.stock_code,
                        "existing_task_id": duplicate.existing_task_id,
                    }
                    for duplicate in duplicates
                ],
            },
        )

    def _stock_pool_import(context: ActionContext) -> ActionResult:
        payload = context.input or {}
        codes = _stock_codes_from_payload(payload)
        if not codes:
            return _result(
                context,
                ExtensionStatus.FAILED.value,
                {"imported": [], "stock_list": []},
                error_code=ExtensionErrorCode.INPUT_INVALID.value,
                diagnostics={"reason": "stock_codes or candidates is required."},
            )

        max_items = _max_items(context, default=len(codes))
        if len(codes) > max_items:
            return _result(
                context,
                ExtensionStatus.FAILED.value,
                {"imported": [], "stock_list": []},
                error_code=ExtensionErrorCode.BUDGET_EXCEEDED.value,
                diagnostics={"reason": f"Requested {len(codes)} items exceeds max_items={max_items}."},
            )

        from src.config import Config, get_config
        from src.core.config_manager import ConfigManager

        manager = ConfigManager()
        current_map = manager.read_config_map()
        existing_raw = current_map.get("STOCK_LIST", "")
        existing = [
            canonical_stock_code(item)
            for item in existing_raw.split(",")
            if canonical_stock_code(item)
        ] or list(getattr(get_config(), "stock_list", []) or [])
        merge = bool(payload.get("merge", True))
        next_codes = _ordered_unique((existing if merge else []) + codes)
        manager.apply_updates(
            [("STOCK_LIST", ",".join(next_codes))],
            sensitive_keys=set(),
            mask_token="***",
        )
        Config.reset_instance()
        return _result(
            context,
            ExtensionStatus.COMPLETED.value,
            {"imported": codes, "stock_list": next_codes},
        )

    def _notification_send(context: ActionContext) -> ActionResult:
        payload = context.input or {}
        content = str(payload.get("content") or "").strip()
        if not content:
            return _result(
                context,
                ExtensionStatus.FAILED.value,
                {"sent": False},
                error_code=ExtensionErrorCode.INPUT_INVALID.value,
                diagnostics={"reason": "content is required."},
            )
        if context.dry_run or bool(payload.get("dry_run", False)):
            return _result(context, ExtensionStatus.COMPLETED.value, {"sent": False, "dry_run": True})

        from src.notification import NotificationService

        sent = bool(NotificationService().send(content))
        return _result(
            context,
            ExtensionStatus.COMPLETED.value if sent else ExtensionStatus.FAILED.value,
            {"sent": sent},
            error_code=None if sent else ExtensionErrorCode.DEPENDENCY_FAILED.value,
        )

    return [
        ActionSpec(
            id="dsa.analyze_stock",
            plugin_id=PLUGIN_ID,
            name="Submit DSA Stock Analysis",
            description="Submit one or more stock analysis tasks through the existing task queue.",
            category="stock_analysis",
            mode="sync",
            input_schema=ANALYZE_STOCK_INPUT_SCHEMA,
            handler=_analyze_stock,
            permissions=["analysis.submit"],
            supported_callers=["system", "cli", "bot", "scheduler", "mcp"],
            concurrency_limit=2,
            budget_hints={"max_items": 20},
            metadata=metadata,
        ),
        ActionSpec(
            id="stock_pool.import",
            plugin_id="stock_pool",
            name="Import Stock Pool Candidates",
            description="Merge candidate stock codes into STOCK_LIST.",
            category="watchlist",
            mode="sync",
            input_schema=STOCK_POOL_IMPORT_INPUT_SCHEMA,
            handler=_stock_pool_import,
            permissions=["watchlist.write"],
            supported_callers=["system"],
            concurrency_limit=1,
            budget_hints={"max_items": 200},
            metadata={**metadata, "plugin_id_alias": "stock_pool"},
        ),
        ActionSpec(
            id="notification.send",
            plugin_id="notification",
            name="Send Notification",
            description="Send a notification through the existing notification service.",
            category="notification",
            mode="sync",
            input_schema=NOTIFICATION_SEND_INPUT_SCHEMA,
            handler=_notification_send,
            permissions=["notify"],
            supported_callers=["system"],
            requires_confirmation=True,
            confirmation_scope="notify.send",
            concurrency_limit=1,
            metadata={**metadata, "plugin_id_alias": "notification"},
        ),
    ]


def _result(
    context: ActionContext,
    status: str,
    result: Dict[str, Any],
    *,
    error_code: Optional[str] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> ActionResult:
    now = datetime.now()
    return ActionResult(
        run_id=context.run_id,
        action_id=context.action_id,
        status=status,
        result=result,
        error_code=error_code,
        diagnostics=diagnostics or {},
        created_at=now,
        updated_at=now,
    )


def _stock_codes_from_payload(payload: Dict[str, Any]) -> List[str]:
    raw_codes = payload.get("stock_codes")
    if not isinstance(raw_codes, list):
        raw_codes = []
    if payload.get("stock_code"):
        raw_codes = [payload.get("stock_code")] + raw_codes
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        raw_codes.extend(
            item.get("code") or item.get("symbol")
            for item in candidates
            if isinstance(item, dict)
        )
    return _ordered_unique([str(code) for code in raw_codes if code])


def _ordered_unique(values: List[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        code = canonical_stock_code(value)
        if not code or code in seen:
            continue
        seen.add(code)
        result.append(code)
    return result


def _optional_text(value: Any) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text or None


def _string_list(value: Any) -> Optional[List[str]]:
    if not isinstance(value, list):
        return None
    return [str(item) for item in value if str(item).strip()]


def _max_items(context: ActionContext, *, default: int) -> int:
    for source in (context.budget, context.budget_hints):
        value = source.get("max_items") if isinstance(source, dict) else None
        if value is None:
            continue
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            continue
    return max(1, int(default))
