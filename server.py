# -*- coding: utf-8 -*-
"""
===================================
Daily Stock Analysis - FastAPI houduanfuwurukou
===================================

zhize：
1. tigong RESTful API fuwu
2. peizhi CORS kuayuzhichi
3. jiankangjianchajiekou
4. tuoguanqianduanjingtaiwenjian（shengchanmoshi）

qidongfangshi：
    uvicorn server:app --reload --host 0.0.0.0 --port 8000
    
    huoshiyong main.py:
    python main.py --serve-only      # jinqidong API fuwu
    python main.py --serve           # API fuwu + zhixingfenxi
"""

import logging

from src.config import setup_env, get_config
from src.logging_config import setup_logging

# chushihuahuanjingbianliangyurizhi
setup_env()

config = get_config()
level_name = (config.log_level or "INFO").upper()
level = getattr(logging, level_name, logging.INFO)

setup_logging(
    log_prefix="api_server",
    console_level=level,
    extra_quiet_loggers=['uvicorn', 'fastapi'],
)

# cong api.app daoruyingyongshili
from api.app import app  # noqa: E402

# daochu app gong uvicorn shiyong
__all__ = ['app']


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
