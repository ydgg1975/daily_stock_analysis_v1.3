# -*- coding: utf-8 -*-
"""
===================================
rizhiconfigmokuai - tongyiderizhixitongchushihua
===================================

zhize竊?
1. tigongtongyiderizhigeshiheconfigchangliang
2. zhichikongzhitai + wenjian竊늓hanggui/tiaoshi竊뎤ancengrizhishuchu
3. zidongjiangdidisanfangkurizhijibie
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional, Tuple


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(pathname)s:%(lineno)d | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_ALLOWED_LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}
_DEFAULT_LITELLM_LOG_LEVEL = 'WARNING'


class RelativePathFormatter(logging.Formatter):
    """zidingyi Formatter竊똲huchuxiangduilujingerfeijueduilujing"""

    def __init__(self, fmt=None, datefmt=None, relative_to=None):
        super().__init__(fmt, datefmt)
        self.relative_to = Path(relative_to) if relative_to else Path.cwd()

    def format(self, record):
        # jiangjueduilujingzhuanweixiangduilujing
        try:
            record.pathname = str(Path(record.pathname).relative_to(self.relative_to))
        except ValueError:
            # ruguowufazhuanhuanweixiangduilujing竊똟aochiyuanyang
            pass
        return super().format(record)



# morenxuyaojiangdirizhijibiededisanfangku
DEFAULT_QUIET_LOGGERS = [
    'urllib3',
    'sqlalchemy',
    'google',
    'httpx',
]

LITELLM_LOGGERS = [
    'LiteLLM',
    'LiteLLM Router',
    'LiteLLM Proxy',
    'litellm',
]


def _resolve_litellm_log_level(raw_level: Optional[str] = None) -> Tuple[int, Optional[str]]:
    """Resolve LiteLLM logger level from env, returning invalid raw value if any."""
    if raw_level is None:
        raw_level = os.getenv('LITELLM_LOG_LEVEL', '')

    normalized = (raw_level or '').strip().upper()
    if not normalized:
        normalized = _DEFAULT_LITELLM_LOG_LEVEL

    level = _ALLOWED_LOG_LEVELS.get(normalized)
    if level is None:
        return _ALLOWED_LOG_LEVELS[_DEFAULT_LITELLM_LOG_LEVEL], raw_level
    return level, None


def setup_logging(
    log_prefix: str = "app",
    log_dir: str = "./logs",
    console_level: Optional[int] = None,
    debug: bool = False,
    extra_quiet_loggers: Optional[List[str]] = None,
) -> None:
    """
    tongyiderizhixitongchushihua

    configsancengrizhishuchu竊?
    1. kongzhitai竊쉍enju debug canshuhuo console_level shezhijibie
    2. changguirizhiwenjian竊숳NFO jibie竊?0MB lunzhuan竊똟aoliu 5 gebeifen
    3. tiaoshirizhiwenjian竊숧EBUG jibie竊?0MB lunzhuan竊똟aoliu 3 gebeifen

    Args:
        log_prefix: rizhiwenjianmingqianzhui竊늭u "api_server" -> api_server_20240101.log竊?
        log_dir: rizhiwenjianmulu竊똫oren ./logs
        console_level: kongzhitairizhijibie竊늟exuan竊똹ouxianyu debug canshu竊?
        debug: shifouqiyongtiaoshimoshi竊늟ongzhitaishuchu DEBUG jibie竊?
        extra_quiet_loggers: ewaixuyaojiangdirizhijibiededisanfangkuliebiao
    """
    # quedingkongzhitairizhijibie
    if console_level is not None:
        level = console_level
    else:
        level = logging.DEBUG if debug else logging.INFO

    # chuangjianrizhimulu
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # rizhiwenjianlujing竊늏nriqifenwenjian竊?
    today_str = datetime.now().strftime('%Y%m%d')
    log_file = log_path / f"{log_prefix}_{today_str}.log"
    debug_log_file = log_path / f"{log_prefix}_debug_{today_str}.log"

    # configgen logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # gen logger shewei DEBUG竊똹ou handler kongzhishuchujibie

    # qingchuyiyou handler竊똟imianchongfuadd
    if root_logger.handlers:
        root_logger.handlers.clear()
    # chuangjianxiangduilujing Formatter竊늵iangduiyuxiangmugenmulu竊?
    project_root = Path.cwd()
    rel_formatter = RelativePathFormatter(
        LOG_FORMAT, LOG_DATE_FORMAT, relative_to=project_root
    )
    # Handler 1: kongzhitaishuchu
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(rel_formatter)
    root_logger.addHandler(console_handler)

    # Handler 2: changguirizhiwenjian竊뉹NFO jibie竊?0MB lunzhuan竊?
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(rel_formatter)
    root_logger.addHandler(file_handler)

    # Handler 3: tiaoshirizhiwenjian竊뉲EBUG jibie竊똟aohansuoyouxiangxixinxi竊?
    debug_handler = RotatingFileHandler(
        debug_log_file,
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=3,
        encoding='utf-8'
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(rel_formatter)
    root_logger.addHandler(debug_handler)

    # jiangdidisanfangkuderizhijibie
    quiet_loggers = DEFAULT_QUIET_LOGGERS.copy()
    if extra_quiet_loggers:
        quiet_loggers.extend(extra_quiet_loggers)

    for logger_name in quiet_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    litellm_level, invalid_litellm_level = _resolve_litellm_log_level()
    for logger_name in LITELLM_LOGGERS:
        logging.getLogger(logger_name).setLevel(litellm_level)

    # shuchuchushihuawanchengxinxi竊늮hiyongxiangduilujing竊?
    try:
        rel_log_path = log_path.resolve().relative_to(project_root)
    except ValueError:
        rel_log_path = log_path

    try:
        rel_log_file = log_file.resolve().relative_to(project_root)
    except ValueError:
        rel_log_file = log_file

    try:
        rel_debug_log_file = debug_log_file.resolve().relative_to(project_root)
    except ValueError:
        rel_debug_log_file = debug_log_file

    logging.info(f"rizhixitongchushihuawancheng竊똱izhimulu: {rel_log_path}")
    logging.info(f"changguirizhi: {rel_log_file}")
    logging.info(f"tiaoshirizhi: {rel_debug_log_file}")
    if invalid_litellm_level is not None:
        logging.warning(
            "LITELLM_LOG_LEVEL=%r wuxiao竊똹ihuituiwei %s竊쌽exuanzhi竊?s",
            invalid_litellm_level,
            _DEFAULT_LITELLM_LOG_LEVEL,
            ", ".join(_ALLOWED_LOG_LEVELS),
        )

