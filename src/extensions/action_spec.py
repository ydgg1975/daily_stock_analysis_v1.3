# -*- coding: utf-8 -*-
"""Core contracts for Extension Runtime actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ExtensionStatus(str, Enum):
    """Action execution status values."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"


class ExtensionErrorCode(str, Enum):
    """Structured error codes shared by extension entrypoints."""

    PLUGIN_DISABLED = "E_PLUGIN_DISABLED"
    PLUGIN_UNAVAILABLE = "E_PLUGIN_UNAVAILABLE"
    ACTION_NOT_FOUND = "E_ACTION_NOT_FOUND"
    CALLER_NOT_ALLOWED = "E_CALLER_NOT_ALLOWED"
    PERMISSION_DENIED = "E_PERMISSION_DENIED"
    CONFIRMATION_REQUIRED = "E_CONFIRMATION_REQUIRED"
    CONFIRMATION_INVALID = "E_CONFIRMATION_INVALID"
    INPUT_INVALID = "E_INPUT_INVALID"
    IDEMPOTENCY_CONFLICT = "E_IDEMPOTENCY_CONFLICT"
    CONCURRENCY_LIMIT = "E_CONCURRENCY_LIMIT"
    BUDGET_EXCEEDED = "E_BUDGET_EXCEEDED"
    TIMEOUT = "E_TIMEOUT"
    CALL_DEPTH_EXCEEDED = "E_CALL_DEPTH_EXCEEDED"
    DEPENDENCY_FAILED = "E_DEPENDENCY_FAILED"
    UPSTREAM_DEGRADED = "E_UPSTREAM_DEGRADED"
    OUTPUT_TOO_LARGE = "E_OUTPUT_TOO_LARGE"
    CANCELLED = "E_CANCELLED"
    INTERNAL = "E_INTERNAL"


SUPPORTED_CALLERS = {"web", "agent", "bot", "cli", "scheduler", "mcp", "system"}
SUPPORTED_MODES = {"sync", "async"}
SUPPORTED_DEDUPE = {"none", "input_hash", "idempotency_key"}
SUPPORTED_CANCEL = {"none", "pending_only", "subprocess", "cooperative"}


@dataclass
class ActionContext:
    """Runtime context passed to an Action handler."""

    action_id: str
    input: Dict[str, Any]
    caller: str = "system"
    trace_id: str = ""
    traceparent: str = ""
    session_id: str = ""
    request_id: str = ""
    idempotency_key: str = ""
    confirmation_id: str = ""
    dry_run: bool = False
    call_depth: int = 0
    budget: Dict[str, Any] = field(default_factory=dict)
    budget_hints: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    input_hash: str = ""
    run_id: str = ""


@dataclass
class ActionSpec:
    """Definition of one extension action."""

    id: str
    plugin_id: str
    name: str
    description: str
    category: str
    mode: str
    input_schema: Dict[str, Any]
    handler: Callable[[ActionContext], Any]
    output_schema: Optional[Dict[str, Any]] = None
    permissions: List[str] = field(default_factory=list)
    supported_callers: List[str] = field(default_factory=lambda: sorted(SUPPORTED_CALLERS))
    requires_confirmation: bool = False
    confirmation_scope: str = ""
    timeout_seconds: Optional[float] = None
    budget_hints: Dict[str, Any] = field(default_factory=dict)
    concurrency_limit: int = 1
    dedupe_strategy: str = "none"
    cancel_capability: str = "none"
    sensitive_output_paths: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate fields that are shared across runtime entrypoints."""
        if not self.id or "." not in self.id:
            raise ValueError("ActionSpec.id must be a dotted id such as 'plugin.action'")
        if not self.plugin_id:
            raise ValueError("ActionSpec.plugin_id is required")
        if not self.id.startswith(f"{self.plugin_id}."):
            raise ValueError("ActionSpec.id must be prefixed by plugin_id")
        if self.mode not in SUPPORTED_MODES:
            raise ValueError(f"Unsupported action mode: {self.mode}")
        if self.dedupe_strategy not in SUPPORTED_DEDUPE:
            raise ValueError(f"Unsupported dedupe strategy: {self.dedupe_strategy}")
        if self.cancel_capability not in SUPPORTED_CANCEL:
            raise ValueError(f"Unsupported cancel capability: {self.cancel_capability}")
        if self.concurrency_limit < 1:
            raise ValueError("ActionSpec.concurrency_limit must be >= 1")
        invalid_callers = sorted(set(self.supported_callers) - SUPPORTED_CALLERS)
        if invalid_callers:
            raise ValueError(f"Unsupported callers: {', '.join(invalid_callers)}")
        if not isinstance(self.input_schema, dict) or self.input_schema.get("type") != "object":
            raise ValueError("ActionSpec.input_schema must be an object JSON schema")


@dataclass
class ActionResult:
    """Serializable result envelope returned by ExtensionRuntime."""

    run_id: str
    action_id: str
    status: str
    result: Optional[Any] = None
    warnings: List[str] = field(default_factory=list)
    degradation: List[str] = field(default_factory=list)
    source_chain: List[Dict[str, Any]] = field(default_factory=list)
    source_errors: List[Dict[str, Any]] = field(default_factory=list)
    error_code: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to an API/tool friendly dictionary."""
        return {
            "run_id": self.run_id,
            "action_id": self.action_id,
            "status": self.status,
            "result": self.result,
            "warnings": self.warnings,
            "degradation": self.degradation,
            "source_chain": self.source_chain,
            "source_errors": self.source_errors,
            "error_code": self.error_code,
            "diagnostics": self.diagnostics,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
