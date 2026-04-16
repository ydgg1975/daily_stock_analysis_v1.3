"""Deprecated compatibility wrapper for the legacy strategy aggregator import path.

Use `src.agent.skills.aggregator` for canonical imports.
"""

from src.agent.skills.aggregator import SkillAggregator, StrategyAggregator

__all__ = ["SkillAggregator", "StrategyAggregator"]
