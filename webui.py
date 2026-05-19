# -*- coding: utf-8 -*-
"""
===================================
WebUI qidongjiaoben
===================================

yongyuqidong Web fuwujiemian。
zhijieyunxing `python webui.py` jiangqidong Web houduanfuwu。

dengxiaomingling：
    python main.py --webui-only

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
    qidong Web fuwu
    """
    # jianrongjiubanhuanjingbianliangming
    host = os.getenv("WEBUI_HOST", os.getenv("API_HOST", "127.0.0.1"))
    port = int(os.getenv("WEBUI_PORT", os.getenv("API_PORT", "8000")))

    print(f"zhengzaiqidong Web fuwu: http://{host}:{port}")
    print(f"API wendang: http://{host}:{port}/docs")
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
