# -*- coding: utf-8 -*-
"""In-memory concurrency and dedupe guard for extension actions."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Dict, Optional

from src.extensions.action_spec import ActionContext, ActionSpec


@dataclass
class ConcurrencyDecision:
    """Result of trying to enter an action execution slot."""

    allowed: bool
    reason: str = ""
    existing_run_id: str = ""
    dedupe_key: str = ""


class InMemoryConcurrencyGuard:
    """Process-local per-action concurrency and dedupe guard."""

    def __init__(self):
        self._lock = threading.RLock()
        self._running_counts: Dict[str, int] = {}
        self._dedupe_runs: Dict[str, str] = {}

    def acquire(self, action: ActionSpec, context: ActionContext) -> ConcurrencyDecision:
        """Try to reserve an execution slot for an action."""
        dedupe_key = self._build_dedupe_key(action, context)
        with self._lock:
            if dedupe_key and dedupe_key in self._dedupe_runs:
                return ConcurrencyDecision(
                    allowed=False,
                    reason="duplicate",
                    existing_run_id=self._dedupe_runs[dedupe_key],
                    dedupe_key=dedupe_key,
                )

            current = self._running_counts.get(action.id, 0)
            if current >= action.concurrency_limit:
                return ConcurrencyDecision(
                    allowed=False,
                    reason="concurrency_limit",
                    dedupe_key=dedupe_key,
                )

            self._running_counts[action.id] = current + 1
            if dedupe_key:
                self._dedupe_runs[dedupe_key] = context.run_id
            return ConcurrencyDecision(allowed=True, dedupe_key=dedupe_key)

    def release(self, action: ActionSpec, dedupe_key: str = "") -> None:
        """Release a previously acquired execution slot."""
        with self._lock:
            current = self._running_counts.get(action.id, 0)
            if current <= 1:
                self._running_counts.pop(action.id, None)
            else:
                self._running_counts[action.id] = current - 1
            if dedupe_key:
                self._dedupe_runs.pop(dedupe_key, None)

    def _build_dedupe_key(self, action: ActionSpec, context: ActionContext) -> str:
        if context.idempotency_key:
            return f"{context.caller}:{action.id}:idempotency:{context.idempotency_key}"
        if action.dedupe_strategy == "input_hash":
            return f"{context.caller}:{action.id}:input:{context.input_hash}"
        return ""
