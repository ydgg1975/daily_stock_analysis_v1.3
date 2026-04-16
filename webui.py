# -*- coding: utf-8 -*-
"""
===================================
WebUI 兼容启动脚本
===================================

兼容旧版 Web 服务入口。
直接运行 `python webui.py` 仍会启动 Web 后端服务，但该入口已弃用。

当前推荐命令：
    python3 main.py --serve-only

Usage:
  python webui.py
  WEBUI_HOST=0.0.0.0 WEBUI_PORT=8000 python webui.py
"""

from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)


def main() -> int:
    """
    启动 Web 服务
    """
    # 兼容旧版环境变量名
    host = os.getenv("WEBUI_HOST", os.getenv("API_HOST", "127.0.0.1"))
    port = int(os.getenv("WEBUI_PORT", os.getenv("API_PORT", "8000")))

    print("注意：`python webui.py` 已弃用，当前仅保留兼容入口。")
    print(f"请改用：python3 main.py --serve-only --host {host} --port {port}")
    print(f"正在启动 Web 服务: http://{host}:{port}")
    print(f"API 文档: http://{host}:{port}/docs")
    print()

    try:
        import uvicorn
        from src.config import setup_env
        from src.logging_config import setup_logging

        setup_env()
        setup_logging(log_prefix="web_server")

        uvicorn.run(
            "api.app:app",
            host=host,
            port=port,
            log_level="info",
        )
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
