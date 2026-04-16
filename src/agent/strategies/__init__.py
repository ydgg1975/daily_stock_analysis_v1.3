# -*- coding: utf-8 -*-
"""
Deprecated compatibility re-exports for the legacy strategy namespace.

Use the canonical skills namespace instead:
- `src.agent.skills.skill_agent.SkillAgent`
- `src.agent.skills.router.SkillRouter`
- `src.agent.skills.aggregator.SkillAggregator`

Provides:
- :class:`StrategyAgent` — legacy alias of :class:`SkillAgent`
- :class:`StrategyRouter` — legacy alias of :class:`SkillRouter`
- :class:`StrategyAggregator` — legacy alias of :class:`SkillAggregator`
"""

from src.agent.strategies.strategy_agent import StrategyAgent
from src.agent.strategies.router import StrategyRouter
from src.agent.strategies.aggregator import StrategyAggregator

__all__ = [
    "StrategyAgent",
    "StrategyRouter",
    "StrategyAggregator",
]
