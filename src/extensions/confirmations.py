# -*- coding: utf-8 -*-
"""Process-local confirmation token store for Extension actions."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

from src.extensions.run_envelope import input_hash


@dataclass
class ConfirmationToken:
    confirmation_id: str
    action_id: str
    scope: str
    bound_to_input_hash: str
    expires_at: datetime
    one_shot: bool = True
    created_by: str = ""
    consumed_at: Optional[datetime] = None


class ConfirmationStore:
    """In-memory confirmation token store.

    MVP tokens are process-local and lost on restart, matching the P0 contract.
    """

    def __init__(self, max_tokens: int = 1000):
        self._lock = threading.RLock()
        self._tokens: Dict[str, ConfirmationToken] = {}
        self._max_tokens = max(1, int(max_tokens))

    def issue(
        self,
        *,
        action_id: str,
        scope: str,
        input_payload: Dict[str, object],
        ttl_seconds: int = 600,
        created_by: str = "",
    ) -> ConfirmationToken:
        token = ConfirmationToken(
            confirmation_id=f"cnf_{uuid.uuid4().hex}",
            action_id=action_id,
            scope=scope,
            bound_to_input_hash=input_hash(input_payload),
            expires_at=datetime.now() + timedelta(seconds=max(60, ttl_seconds)),
            created_by=created_by,
        )
        with self._lock:
            self._sweep_expired_locked(datetime.now())
            self._trim_if_needed_locked()
            self._tokens[token.confirmation_id] = token
        return token

    def consume(self, confirmation_id: str, *, action_id: str, input_payload: Dict[str, object]) -> bool:
        if not confirmation_id:
            return False
        with self._lock:
            now = datetime.now()
            self._sweep_expired_locked(now)
            token = self._tokens.get(confirmation_id)
            if token is None:
                return False
            if token.expires_at < now:
                self._tokens.pop(confirmation_id, None)
                return False
            if token.action_id != action_id:
                return False
            if token.bound_to_input_hash != input_hash(input_payload):
                return False
            token.consumed_at = now
            if token.one_shot:
                self._tokens.pop(confirmation_id, None)
            return True

    def _sweep_expired_locked(self, now: datetime) -> None:
        expired = [
            confirmation_id
            for confirmation_id, token in self._tokens.items()
            if token.expires_at < now
        ]
        for confirmation_id in expired:
            self._tokens.pop(confirmation_id, None)

    def _trim_if_needed_locked(self) -> None:
        if len(self._tokens) < self._max_tokens:
            return
        overflow = len(self._tokens) - self._max_tokens + 1
        oldest = sorted(self._tokens.items(), key=lambda item: item[1].expires_at)[:overflow]
        for confirmation_id, _token in oldest:
            self._tokens.pop(confirmation_id, None)


_STORE = ConfirmationStore()


def get_confirmation_store() -> ConfirmationStore:
    return _STORE
