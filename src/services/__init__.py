# -*- coding: utf-8 -*-
"""
===================================
fuwucengmokuaichushihua
===================================

zhize：
1. shengmingkedaochudefuwulei（yanchidaoru，bimianqidongshilaru LLM dengzhongyilai）

shiyongfangshi：
    zhijiecongzimokuaidaoru，liru:
    from src.services.history_service import HistoryService
"""


def __getattr__(name: str):
    """yanchidaoru：jinzaitongguo src.services.X fangwenshicaijiazaiduiyingzimokuai。"""
    _lazy_map = {
        "AnalysisService": "src.services.analysis_service",
        "BacktestService": "src.services.backtest_service",
        "HistoryService": "src.services.history_service",
        "StockService": "src.services.stock_service",
        "TaskService": "src.services.task_service",
        "get_task_service": "src.services.task_service",
    }
    if name in _lazy_map:
        import importlib
        module = importlib.import_module(_lazy_map[name])
        return getattr(module, name)
    raise AttributeError(f"module 'src.services' has no attribute {name!r}")


__all__ = [
    "AnalysisService",
    "BacktestService",
    "HistoryService",
    "StockService",
    "TaskService",
    "get_task_service",
]
