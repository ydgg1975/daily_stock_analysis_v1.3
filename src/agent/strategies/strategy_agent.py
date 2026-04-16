"""Deprecated compatibility wrapper for the legacy strategy agent import path.

Use `src.agent.skills.skill_agent` for canonical imports.
"""

from src.agent.skills.skill_agent import SkillAgent, StrategyAgent

__all__ = ["SkillAgent", "StrategyAgent"]
