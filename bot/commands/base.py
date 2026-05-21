# -*- coding: utf-8 -*-
"""
Base class for bot commands.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional

from bot.models import BotMessage, BotResponse


class BotCommand(ABC):
    """
    Abstract base class for bot command handlers.

    Subclasses define command metadata and implement ``execute``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Primary command name, without the slash prefix."""
        pass

    @property
    @abstractmethod
    def aliases(self) -> List[str]:
        """Alternative command names."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Short user-facing command description."""
        pass

    @property
    @abstractmethod
    def usage(self) -> str:
        """User-facing usage string."""
        pass

    @property
    def hidden(self) -> bool:
        """Whether this command should be hidden from help output."""
        return False

    @property
    def admin_only(self) -> bool:
        """Whether this command requires admin privileges."""
        return False

    @abstractmethod
    def execute(self, message: BotMessage, args: List[str]) -> BotResponse:
        """Execute the command."""
        pass

    async def execute_async(self, message: BotMessage, args: List[str]) -> BotResponse:
        """Run the sync command implementation in a worker thread."""
        return await asyncio.to_thread(self.execute, message, args)

    def validate_args(self, args: List[str]) -> Optional[str]:
        """Validate command arguments; return an error message when invalid."""
        return None

    def get_help_text(self) -> str:
        """Return a compact help text for this command."""
        return f"**{self.name}** - {self.description}\n사용법: `{self.usage}`"
