# -*- coding: utf-8 -*-
"""Permission and confirmation guards for extension actions."""

from __future__ import annotations

from typing import Optional

from src.extensions.action_spec import ActionContext, ActionSpec, ExtensionErrorCode


class PermissionGuard:
    """Small MVP guard for caller and confirmation checks."""

    def check(self, action: ActionSpec, context: ActionContext) -> Optional[str]:
        """Return an error code when execution should be denied."""
        if context.caller not in action.supported_callers:
            return ExtensionErrorCode.CALLER_NOT_ALLOWED.value
        if action.requires_confirmation and not context.confirmation_id:
            return ExtensionErrorCode.CONFIRMATION_REQUIRED.value
        return None
