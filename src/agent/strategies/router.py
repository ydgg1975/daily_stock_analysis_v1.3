"""Deprecated compatibility wrapper for the legacy strategy router import path.

Use `src.agent.skills.router` for canonical imports.
"""

from src.agent.skills.router import SkillRouter, StrategyRouter, _DEFAULT_STRATEGIES, _DEFAULT_SKILLS

__all__ = ["SkillRouter", "StrategyRouter", "_DEFAULT_SKILLS", "_DEFAULT_STRATEGIES"]
