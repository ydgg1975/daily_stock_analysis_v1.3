# -*- coding: utf-8 -*-
"""
===================================
API v1 Endpoints 模块初始化
===================================

职责：
1. 声明所有 endpoint 路由模块
"""

from api.v1.endpoints import (
    analysis,
    admin_logs,
    history,
    stocks,
    backtest,
    scanner,
    system_config,
    auth,
    agent,
    usage,
    portfolio,
)
__all__ = [
    "analysis",
    "admin_logs",
    "history",
    "stocks",
    "backtest",
    "scanner",
    "system_config",
    "auth",
    "agent",
    "usage",
    "portfolio",
]
