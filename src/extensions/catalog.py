# -*- coding: utf-8 -*-
"""In-memory catalog for built-in extension action specs."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from src.extensions.action_spec import ActionSpec


class ExtensionCatalog:
    """Stores ActionSpec objects without becoming a second source of truth."""

    def __init__(self, actions: Optional[Iterable[ActionSpec]] = None):
        self._actions: Dict[str, ActionSpec] = {}
        for action in actions or []:
            self.register(action)

    def register(self, action: ActionSpec) -> None:
        """Register one validated action spec."""
        action.validate()
        if action.id in self._actions:
            raise ValueError(f"Action already registered: {action.id}")
        self._actions[action.id] = action

    def get(self, action_id: str) -> Optional[ActionSpec]:
        """Return an action by id."""
        return self._actions.get(action_id)

    def list_actions(self, *, plugin_id: Optional[str] = None) -> List[ActionSpec]:
        """List all actions, optionally filtered by plugin id."""
        actions = list(self._actions.values())
        if plugin_id:
            actions = [action for action in actions if action.plugin_id == plugin_id]
        return sorted(actions, key=lambda action: action.id)

    def __contains__(self, action_id: str) -> bool:
        return action_id in self._actions

    def __len__(self) -> int:
        return len(self._actions)
