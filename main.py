# -*- coding: utf-8 -*-
"""
===================================
Daily Stock Analysis - main scheduler
===================================

Responsibilities:
1. 종목 데이터를 수집하고 분석합니다.
2. 시장 리뷰를 실행하고 리포트를 생성합니다.
3. 알림 채널로 분석 결과를 전송합니다.
4. 예약 실행을 관리합니다.

Usage:
    python main.py              # 일반 실행
    python main.py --debug      # 디버그 실행
    python main.py --dry-run    # 데이터를 수집하되 AI 분석은 건너뜀

Trading rules embedded in analysis:
- 추세 확인: 가격 흐름과 이동평균을 함께 확인합니다.
- 배열 확인: MA5 > MA10 > MA20 정배열을 선호합니다.
- 거래량 확인: 거래량 변화와 돌파 여부를 확인합니다.
- 매수 신호: 현재가가 MA5/MA10 위에 있는지 확인합니다.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from dotenv import dotenv_values
from src.config import setup_env

_INITIAL_PROCESS_ENV = dict(os.environ)
setup_env()

# Proxy configuration controlled by USE_PROXY. Disabled by default.
# GitHub Actions skips local proxy configuration automatically.
if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("USE_PROXY", "false").lower() == "true":
    # Local development proxy. Configure PROXY_HOST and PROXY_PORT in .env.
    proxy_host = os.getenv("PROXY_HOST", "127.0.0.1")
    proxy_port = os.getenv("PROXY_PORT", "10809")
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    os.environ["http_proxy"] = proxy_url
    os.environ["https_proxy"] = proxy_url

import argparse
import logging
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta

from data_provider.base import canonical_stock_code
from src.webui_frontend import prepare_webui_frontend_assets
from src.config import get_config, Config
from src.logging_config import setup_logging


logger = logging.getLogger(__name__)
_RUNTIME_ENV_FILE_KEYS = set()


def _get_active_env_path() -> Path:
    env_file = os.getenv("ENV_FILE")
    if env_file:
        return Path(env_file)
    return Path(__file__).resolve().parent / ".env"


def _read_active_env_values() -> Optional[Dict[str, str]]:
    env_path = _get_active_env_path()
    if not env_path.exists():
        return {}

    try:
        values = dotenv_values(env_path)
    except Exception as exc:  # pragma: no cover - defensive branch
        logger.warning("환경 파일 %s을 읽는 중 오류가 발생했습니다: %s", env_path, exc)
        return None

    return {
        str(key): "" if value is None else str(value)
        for key, value in values.items()
        if key is not None
    }


_ACTIVE_ENV_FILE_VALUES = _read_active_env_values() or {}
_RUNTIME_ENV_FILE_KEYS = {
    key for key in _ACTIVE_ENV_FILE_VALUES
    if key not in _INITIAL_PROCESS_ENV
}

# setup_env() already ran at import time above.
_env_bootstrapped = True


def _bootstrap_environment() -> None:
    """Load .env and apply optional local proxy settings.

    Guarded to be idempotent so it can safely be called from lazy-import
    paths used by API / bot consumers.
    """
    global _env_bootstrapped
    if _env_bootstrapped:
        return

    from src.config import setup_env

    setup_env()

    if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("USE_PROXY", "false").lower() == "true":
        proxy_host = os.getenv("PROXY_HOST", "127.0.0.1")
        proxy_port = os.getenv("PROXY_PORT", "10809")
        proxy_url = f"http://{proxy_host}:{proxy_port}"
        os.environ["http_proxy"] = proxy_url
        os.environ["https_proxy"] = proxy_url

    _env_bootstrapped = True


def _setup_bootstrap_logging(debug: bool = False) -> None:
    """Initialize stderr-only logging before config is loaded.

    File handlers are deferred until ``config.log_dir`` is known (via the
    subsequent ``setup_logging()`` call) so that healthy runs never create
    log files in a hard-coded directory.
    """
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    if not any(
        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr
        for h in root.handlers
    ):
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(handler)


def _setup_runtime_logging(log_dir: str, debug: bool = False) -> bool:
    """Switch to configured logging, falling back to console on file I/O errors."""
    try:
        setup_logging(log_prefix="stock_analysis", debug=debug, log_dir=log_dir)
        return True
    except OSError as exc:
        logger.warning(
            "파일 로그 초기화에 실패해 콘솔 로그 출력으로 전환했습니다. "
            "로그 디렉터리 %r을 사용할 수 없거나 파일을 만들 수 없습니다: %s. "
            "공식 Docker 이미지 시작 진입점은 기본 마운트 디렉터리 권한을 자동으로 보정합니다. "
            "직접 실행하는 경우 --user, 볼륨 소유자, rootless Docker, NFS 같은 권한 조건을 확인하세요.",
            log_dir,
            exc,
        )
        return False


def _get_stock_analysis_pipeline():
    """Lazily import StockAnalysisPipeline for external consumers.

    Also ensures env/proxy bootstrap has run so that API / bot consumers
    that never call ``main()`` still get ``USE_PROXY`` applied.
    """
    _bootstrap_environment()
    from src.core.pipeline import StockAnalysisPipeline as _Pipeline

    return _Pipeline


class _LazyPipelineDescriptor:
    """Descriptor that resolves StockAnalysisPipeline on first attribute access."""

    _resolved = None

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if self._resolved is None:
            self._resolved = _get_stock_analysis_pipeline()
        return self._resolved


class _ModuleExports:
    StockAnalysisPipeline = _LazyPipelineDescriptor()


_exports = _ModuleExports()


def __getattr__(name: str):
    if name == "StockAnalysisPipeline":
        return _exports.StockAnalysisPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _reload_env_file_values_preserving_overrides() -> None:
    """Refresh `.env`-managed env vars without clobbering process env overrides."""
    global _RUNTIME_ENV_FILE_KEYS

    latest_values = _read_active_env_values()
    if latest_values is None:
        return

    managed_keys = {
        key for key in latest_values
        if key not in _INITIAL_PROCESS_ENV
    }

    for key in _RUNTIME_ENV_FILE_KEYS - managed_keys:
        os.environ.pop(key, None)

    for key in managed_keys:
        os.environ[key] = latest_values[key]

    _RUNTIME_ENV_FILE_KEYS = managed_keys


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Daily Stock Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python main.py                    # normal run
  python main.py --debug            # debug mode
  python main.py --dry-run          # fetch data without AI analysis
  python main.py --stocks 600519,000001  # analyze specific stocks
  python main.py --no-notify        # do not send notifications
  python main.py --check-notify     # check notification config only
  python main.py --single-notify    # send each stock result immediately
  python main.py --schedule         # enable scheduled mode
  python main.py --market-review    # run market review only
        '''
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='자세한 디버그 로그를 출력합니다'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='데이터만 수집하고 AI 분석은 실행하지 않습니다'
    )

    parser.add_argument(
        '--stocks',
        type=str,
        help='분석할 종목 코드를 쉼표로 구분해 지정합니다'
    )

    parser.add_argument(
        '--no-notify',
        action='store_true',
        help='알림 전송을 비활성화합니다'
    )

    parser.add_argument(
        '--check-notify',
        action='store_true',
        help='알림 설정만 점검하고 분석은 실행하지 않습니다'
    )

    parser.add_argument(
        '--single-notify',
        action='store_true',
        help='종목별 분석 결과를 각각 즉시 전송합니다'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='병렬 작업자 수를 지정합니다'
    )

    parser.add_argument(
        '--schedule',
        action='store_true',
        help='예약 모드로 실행합니다'
    )

    parser.add_argument(
        '--no-run-immediately',
        action='store_true',
        help='예약 모드 시작 직후 즉시 실행하지 않습니다'
    )

    parser.add_argument(
        '--market-review',
        action='store_true',
        help='시장 리뷰만 실행합니다'
    )

    parser.add_argument(
        '--no-market-review',
        action='store_true',
        help='시장 리뷰 실행을 비활성화합니다'
    )

    parser.add_argument(
        '--force-run',
        action='store_true',
        help='휴장일이어도 강제로 실행합니다'
    )

    parser.add_argument(
        '--webui',
        action='store_true',
        help='Web UI와 API 서버를 시작합니다'
    )

    parser.add_argument(
        '--webui-only',
        action='store_true',
        help='Web UI와 API 서버만 시작하고 분석은 실행하지 않습니다'
    )

    parser.add_argument(
        '--serve',
        action='store_true',
        help='FastAPI 서버를 함께 시작합니다'
    )

    parser.add_argument(
        '--serve-only',
        action='store_true',
        help='FastAPI 서버만 시작하고 분석은 실행하지 않습니다'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='FastAPI 서버 포트입니다(기본값 8000)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='FastAPI 서버 바인딩 호스트입니다(기본값 0.0.0.0)'
    )

    parser.add_argument(
        '--no-context-snapshot',
        action='store_true',
        help='분석 컨텍스트 스냅샷 저장을 비활성화합니다'
    )

    parser.add_argument(
        '--backtest',
        action='store_true',
        help='추천 이력 백테스트를 실행합니다'
    )

    parser.add_argument(
        '--backtest-code',
        type=str,
        default=None,
        help='백테스트할 종목 코드를 지정합니다'
    )

    parser.add_argument(
        '--backtest-days',
        type=int,
        default=None,
        help='백테스트 평가 기간을 일 단위로 지정합니다'
    )

    parser.add_argument(
        '--backtest-force',
        action='store_true',
        help='기존 백테스트 결과를 무시하고 다시 계산합니다'
    )

    return parser.parse_args()

def _compute_trading_day_filter(
    config: Config,
    args: argparse.Namespace,
    stock_codes: List[str],
) -> Tuple[List[str], Optional[str], bool]:
    """
    Compute filtered stock list and effective market review region (Issue #373).

    Returns:
        (filtered_codes, effective_region, should_skip_all)
        - effective_region None = use config default (check disabled)
        - effective_region '' = all relevant markets closed, skip market review
        - should_skip_all: skip entire run when no stocks and no market review to run
    """
    force_run = getattr(args, 'force_run', False)
    if force_run or not getattr(config, 'trading_day_check_enabled', True):
        return (stock_codes, None, False)

    from src.core.trading_calendar import (
        get_market_for_stock,
        get_open_markets_today,
        compute_effective_region,
    )

    open_markets = get_open_markets_today()
    filtered_codes = []
    for code in stock_codes:
        mkt = get_market_for_stock(code)
        if mkt in open_markets or mkt is None:
            filtered_codes.append(code)

    if config.market_review_enabled and not getattr(args, 'no_market_review', False):
        effective_region = compute_effective_region(
            getattr(config, 'market_review_region', 'cn') or 'cn', open_markets
        )
    else:
        effective_region = None

    should_skip_all = (not filtered_codes) and (effective_region or '') == ''
    return (filtered_codes, effective_region, should_skip_all)


def _run_market_review_with_shared_lock(
    config: Config,
    run_market_review_func: Callable[..., Optional[str]],
    **kwargs: Any,
) -> Optional[str]:
    from src.core.market_review_lock import (
        release_market_review_lock,
        try_acquire_market_review_lock,
    )

    lock_token = try_acquire_market_review_lock(config)
    if lock_token is None:
        logger.warning("시장 리뷰가 이미 실행 중이므로 이번 시장 리뷰를 건너뜁니다")
        return None

    try:
        return run_market_review_func(**kwargs)
    finally:
        release_market_review_lock(lock_token)


def run_full_analysis(
    config: Config,
    args: argparse.Namespace,
    stock_codes: Optional[List[str]] = None
):
    """
    전체 분석을 실행합니다(종목 분석 + 시장 리뷰).

    예약 실행에서도 재사용할 수 있는 진입점입니다.
    """
    # Import pipeline modules outside the broad try/except so that import-time
    # failures propagate to the caller instead of being silently swallowed.
    from src.core.market_review import run_market_review
    from src.core.pipeline import StockAnalysisPipeline

    try:
        # Issue #529: Hot-reload STOCK_LIST from .env on each scheduled run
        if stock_codes is None:
            config.refresh_stock_list()

        # Issue #373: Trading day filter (per-stock, per-market)
        effective_codes = stock_codes if stock_codes is not None else config.stock_list
        filtered_codes, effective_region, should_skip = _compute_trading_day_filter(
            config, args, effective_codes
        )
        if should_skip:
            logger.info(
                "오늘은 관련 시장이 모두 비거래일이므로 실행을 건너뜁니다. --force-run으로 강제 실행할 수 있습니다."
            )
            return
        if set(filtered_codes) != set(effective_codes):
            skipped = set(effective_codes) - set(filtered_codes)
            logger.info("오늘 휴장인 종목을 건너뜁습니다: %s", skipped)
        stock_codes = filtered_codes

        # Command-line --single-notify overrides config (#55).
        if getattr(args, 'single_notify', False):
            config.single_stock_notify = True

        # Issue #190: merge stock analysis and market review notifications.
        merge_notification = (
            getattr(config, 'merge_email_notification', False)
            and config.market_review_enabled
            and not getattr(args, 'no_market_review', False)
            and not config.single_stock_notify
        )

        # Create pipeline.
        save_context_snapshot = None
        if getattr(args, 'no_context_snapshot', False):
            save_context_snapshot = False
        query_id = uuid.uuid4().hex
        pipeline = StockAnalysisPipeline(
            config=config,
            max_workers=args.workers,
            query_id=query_id,
            query_source="cli",
            save_context_snapshot=save_context_snapshot
        )

        # 1. Run individual stock analysis.
        results = pipeline.run(
            stock_codes=stock_codes,
            dry_run=args.dry_run,
            send_notification=not args.no_notify,
            merge_notification=merge_notification
        )

        # Issue #128: add a delay between stock analysis and market review.
        analysis_delay = getattr(config, 'analysis_delay', 0)
        if (
            analysis_delay > 0
            and config.market_review_enabled
            and not args.no_market_review
            and effective_region != ''
        ):
            logger.info("%s초 후 시장 리뷰를 시작합니다(API rate limit 보호)...", analysis_delay)
            time.sleep(analysis_delay)

        # 2. Run market review when enabled and not in stock-only mode.
        market_report = ""
        if (
            config.market_review_enabled
            and not args.no_market_review
            and effective_region != ''
        ):
            review_result = _run_market_review_with_shared_lock(
                config,
                run_market_review,
                notifier=pipeline.notifier,
                analyzer=pipeline.analyzer,
                search_service=pipeline.search_service,
                send_notification=not args.no_notify,
                merge_notification=merge_notification,
                override_region=effective_region,
            )
            # Store market_report for later Feishu document generation.
            if review_result:
                market_report = review_result

        # Issue #190: merged notification (stocks + market review).
        if merge_notification and (results or market_report) and not args.no_notify:
            parts = []
            if market_report:
                parts.append(f"# 시장 리뷰\n\n{market_report}")
            if results:
                dashboard_content = pipeline.notifier.generate_aggregate_report(
                    results,
                    getattr(config, 'report_type', 'simple'),
                )
                parts.append(f"# 종목 분석 의사결정 대시보드\n\n{dashboard_content}")
            if parts:
                combined_content = "\n\n---\n\n".join(parts)
                if pipeline.notifier.is_available():
                    if pipeline.notifier.send(combined_content, email_send_to_all=True, route_type="report"):
                        logger.info("통합 알림 전송 완료(시장 리뷰 + 종목 분석)")
                    else:
                        logger.warning("통합 알림 전송 실패")

        # Output summary.
        if results:
            logger.info("\n===== 분석 결과 요약 =====")
            for r in sorted(results, key=lambda x: x.sentiment_score, reverse=True):
                emoji = r.get_emoji()
                logger.info(
                    f"{emoji} {r.name}({r.code}): {r.operation_advice} | "
                    f"점수 {r.sentiment_score} | {r.trend_prediction}"
                )

        logger.info("\n분석 작업이 완료되었습니다")

        # === Generate Feishu cloud document ===
        try:
            from src.feishu_doc import FeishuDocManager

            feishu_doc = FeishuDocManager()
            if feishu_doc.is_configured() and (results or market_report):
                logger.info("Feishu cloud document creation started...")

                # 1. Prepare title, e.g. "2026-01-01 13:01 주식 분석".
                tz_cn = timezone(timedelta(hours=8))
                now = datetime.now(tz_cn)
                doc_title = f"{now.strftime('%Y-%m-%d %H:%M')} 주식 분석"

                # 2. Prepare content by combining stock analysis and market review.
                full_content = ""

                # Add market review content when present.
                if market_report:
                    full_content += f"# 시장 리뷰\n\n{market_report}\n\n---\n\n"

                # Add stock decision dashboard generated by NotificationService.
                if results:
                    dashboard_content = pipeline.notifier.generate_aggregate_report(
                        results,
                        getattr(config, 'report_type', 'simple'),
                    )
                    full_content += f"# 종목 분석 의사결정 대시보드\n\n{dashboard_content}"

                # 3. Create document.
                doc_url = feishu_doc.create_daily_doc(doc_title, full_content)
                if doc_url:
                    logger.info(f"Feishu cloud document created: {doc_url}")
                    # Optionally send the document link to the group.
                    if not args.no_notify:
                        pipeline.notifier.send(
                            f"[{now.strftime('%Y-%m-%d %H:%M')}] 주식 분석 문서 링크: {doc_url}",
                            route_type="report",
                        )

        except Exception as e:
            logger.error(f"Feishu document generation failed: {e}")

        # === Auto backtest ===
        try:
            if getattr(config, 'backtest_enabled', False):
                from src.services.backtest_service import BacktestService

                logger.info("자동 백테스트를 시작합니다...")
                service = BacktestService()
                stats = service.run_backtest(
                    force=False,
                    eval_window_days=getattr(config, 'backtest_eval_window_days', 10),
                    min_age_days=getattr(config, 'backtest_min_age_days', 14),
                    limit=200,
                )
                logger.info(
                    f"자동 백테스트 완료: processed={stats.get('processed')} saved={stats.get('saved')} "
                    f"completed={stats.get('completed')} insufficient={stats.get('insufficient')} errors={stats.get('errors')}"
                )
        except Exception as e:
            logger.warning("자동 백테스트 오류(무시): %s", e)

    except Exception as e:
        logger.exception("전체 분석 실행 오류: %s", e)


def start_api_server(host: str, port: int, config: Config) -> None:
    """
    백그라운드 스레드에서 FastAPI 서버를 시작합니다.

    Args:
        host: 바인딩 호스트
        port: 바인딩 포트
        config: 애플리케이션 설정
    """
    import threading
    import uvicorn

    def run_server():
        level_name = (config.log_level or "INFO").lower()
        uvicorn.run(
            "api.app:app",
            host=host,
            port=port,
            log_level=level_name,
            log_config=None,
        )

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    logger.info("FastAPI 서버를 시작했습니다: http://%s:%s", host, port)


def _is_truthy_env(var_name: str, default: str = "true") -> bool:
    """Parse common truthy / falsy environment values."""
    value = os.getenv(var_name, default).strip().lower()
    return value not in {"0", "false", "no", "off"}


def start_bot_stream_clients(config: Config) -> None:
    """Start bot stream clients when enabled in config."""
    # Start Dingtalk Stream client.
    if config.dingtalk_stream_enabled:
        try:
            from bot.platforms import start_dingtalk_stream_background, DINGTALK_STREAM_AVAILABLE
            if DINGTALK_STREAM_AVAILABLE:
                if start_dingtalk_stream_background():
                    logger.info("[Main] Dingtalk Stream client started in background.")
                else:
                    logger.warning("[Main] Dingtalk Stream client failed to start.")
            else:
                logger.warning("[Main] Dingtalk Stream enabled but SDK is missing.")
                logger.warning("[Main] Run: pip install dingtalk-stream")
        except Exception as exc:
            logger.error(f"[Main] Failed to start Dingtalk Stream client: {exc}")

    # Start Feishu Stream client.
    if getattr(config, 'feishu_stream_enabled', False):
        try:
            from bot.platforms import start_feishu_stream_background, FEISHU_SDK_AVAILABLE
            if FEISHU_SDK_AVAILABLE:
                if start_feishu_stream_background():
                    logger.info("[Main] Feishu Stream client started in background.")
                else:
                    logger.warning("[Main] Feishu Stream client failed to start.")
            else:
                logger.warning("[Main] Feishu Stream enabled but SDK is missing.")
                logger.warning("[Main] Run: pip install lark-oapi")
        except Exception as exc:
            logger.error(f"[Main] Failed to start Feishu Stream client: {exc}")


def _resolve_scheduled_stock_codes(stock_codes: Optional[List[str]]) -> Optional[List[str]]:
    """Scheduled runs should always read the latest persisted watchlist."""
    if stock_codes is not None:
        logger.warning(
            "예약 모드에서 --stocks 인자가 감지되었습니다. 예약 실행은 시작 시점의 종목 스냅샷을 무시하고 매 실행 전 최신 STOCK_LIST를 다시 읽습니다."
        )
    return None


def _reload_runtime_config() -> Config:
    """Reload config from the latest persisted `.env` values for scheduled runs."""
    _reload_env_file_values_preserving_overrides()
    Config.reset_instance()
    return get_config()


def _build_schedule_time_provider(default_schedule_time: str):
    """Read the latest schedule time directly from the active config file.

    Fallback order:
    1. Process-level env override (set before launch) → honour it.
    2. Persisted config file value (written by WebUI) → use it.
    3. Documented system default ``"18:00"`` → always fall back here so
       that clearing SCHEDULE_TIME in WebUI correctly resets the schedule.
    """
    from src.core.config_manager import ConfigManager

    _SYSTEM_DEFAULT_SCHEDULE_TIME = "18:00"
    manager = ConfigManager()

    def _provider() -> str:
        if "SCHEDULE_TIME" in _INITIAL_PROCESS_ENV:
            return os.getenv("SCHEDULE_TIME", default_schedule_time)

        config_map = manager.read_config_map()
        schedule_time = (config_map.get("SCHEDULE_TIME", "") or "").strip()
        if schedule_time:
            return schedule_time
        return _SYSTEM_DEFAULT_SCHEDULE_TIME

    return _provider


def main() -> int:
    """
    메인 진입점입니다.

    Returns:
        프로세스 종료 코드입니다(0은 성공).
    """
    # 명령행 인자를 해석합니다
    args = parse_arguments()

    # Initialize bootstrap logging before config load so early failures are written.
    try:
        _setup_bootstrap_logging(debug=args.debug)
    except Exception as exc:
        logging.basicConfig(
            level=logging.DEBUG if getattr(args, "debug", False) else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stderr,
        )
        logger.warning("Bootstrap 로그 초기화에 실패해 stderr 기본 로그로 전환했습니다: %s", exc)

    # Load config after bootstrap logging so exceptions are captured.
    try:
        config = get_config()
    except Exception as exc:
        logger.exception("설정 로드 실패: %s", exc)
        return 1

    # Configure console and file logging.
    try:
        _setup_runtime_logging(config.log_dir, debug=args.debug)
    except Exception as exc:
        logger.exception("런타임 로그 설정에 실패했습니다: %s", exc)
        return 1

    logger.info("=" * 60)
    logger.info("Daily Stock Analysis 시작")
    logger.info("실행 시각: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("=" * 60)

    # Validate config.
    warnings = config.validate()
    for warning in warnings:
        logger.warning(warning)

    if getattr(args, "check_notify", False):
        from src.services.notification_diagnostics import (
            format_notification_diagnostics,
            run_notification_diagnostics,
        )

        result = run_notification_diagnostics(config)
        print(format_notification_diagnostics(result))
        return 0 if result.ok else 1

    # Parse stock list and normalize to uppercase (Issue #355).
    stock_codes = None
    if args.stocks:
        stock_codes = [canonical_stock_code(c) for c in args.stocks.split(',') if (c or "").strip()]
        logger.info("명령줄 인자로 받은 종목 목록: %s", stock_codes)

    # Map --webui / --webui-only to --serve / --serve-only.
    if args.webui:
        args.serve = True
    if args.webui_only:
        args.serve_only = True

    # Backward compatibility for old WEBUI_ENABLED environment variable.
    if config.webui_enabled and not (args.serve or args.serve_only):
        args.serve = True

    # Start Web service when enabled.
    start_serve = (args.serve or args.serve_only) and os.getenv("GITHUB_ACTIONS") != "true"

    # Backward compatibility for WEBUI_HOST/WEBUI_PORT when host/port are not explicitly set.
    if start_serve:
        if args.host == '0.0.0.0' and os.getenv('WEBUI_HOST'):
            args.host = os.getenv('WEBUI_HOST')
        if args.port == 8000 and os.getenv('WEBUI_PORT'):
            args.port = int(os.getenv('WEBUI_PORT'))

    bot_clients_started = False
    if start_serve:
        if not prepare_webui_frontend_assets():
            logger.warning("프런트엔드 자산 준비에 실패했지만 FastAPI 서버는 계속 시작합니다(Web 화면이 제한될 수 있습니다)")
        try:
            start_api_server(host=args.host, port=args.port, config=config)
            bot_clients_started = True
        except Exception as e:
            logger.error("FastAPI 서버 시작 오류: %s", e)

    if bot_clients_started:
        start_bot_stream_clients(config)

    # Web service only mode: do not run analysis automatically.
    if args.serve_only:
        logger.info("모드: Web 서비스 전용")
        logger.info("Web 접속 주소: http://%s:%s", args.host, args.port)
        logger.info("/api/v1/analysis/analyze API로 분석을 요청할 수 있습니다")
        logger.info("API 문서: http://%s:%s/docs", args.host, args.port)
        logger.info("종료하려면 Ctrl+C를 누르세요...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n사용자 요청으로 서비스를 종료합니다")
        return 0

    try:
        # Mode 0: backtest.
        if getattr(args, 'backtest', False):
            logger.info("모드: 백테스트")
            from src.services.backtest_service import BacktestService

            service = BacktestService()
            stats = service.run_backtest(
                code=getattr(args, 'backtest_code', None),
                force=getattr(args, 'backtest_force', False),
                eval_window_days=getattr(args, 'backtest_days', None),
            )
            logger.info(
                f"백테스트 완료: processed={stats.get('processed')} saved={stats.get('saved')} "
                f"completed={stats.get('completed')} insufficient={stats.get('insufficient')} errors={stats.get('errors')}"
            )
            return 0

        # Mode 1: market review only.
        if args.market_review:
            from src.core.market_review import run_market_review
            from src.core.market_review_runtime import build_market_review_runtime

            # Issue #373: Trading day check for market-review-only mode.
            # Do NOT use _compute_trading_day_filter here: that helper checks
            # config.market_review_enabled, which would wrongly block an
            # explicit --market-review invocation when the flag is disabled.
            effective_region = None
            if not getattr(args, 'force_run', False) and getattr(config, 'trading_day_check_enabled', True):
                from src.core.trading_calendar import get_open_markets_today, compute_effective_region as _compute_region
                open_markets = get_open_markets_today()
                effective_region = _compute_region(
                    getattr(config, 'market_review_region', 'cn') or 'cn', open_markets
                )
                if effective_region == '':
                    logger.info("오늘은 관련 시장이 모두 휴장일이므로 시장 리뷰를 건너뜁니다. --force-run으로 강제 실행할 수 있습니다.")
                    return 0

            logger.info("모드: 시장 리뷰 전용")
            notifier, analyzer, search_service = build_market_review_runtime(config)

            _run_market_review_with_shared_lock(
                config,
                run_market_review,
                notifier=notifier,
                analyzer=analyzer,
                search_service=search_service,
                send_notification=not args.no_notify,
                override_region=effective_region,
            )
            return 0

        # Mode 2: scheduled tasks.
        if args.schedule or config.schedule_enabled:
            logger.info("모드: 예약 실행")
            logger.info("예약 실행 시각: %s", config.schedule_time)

            # Determine whether to run immediately:
            # Command line arg --no-run-immediately overrides config if present.
            # Otherwise use config (defaults to True).
            should_run_immediately = config.schedule_run_immediately
            if getattr(args, 'no_run_immediately', False):
                should_run_immediately = False

            logger.info("시작 직후 실행 여부: %s", should_run_immediately)

            from src.scheduler import run_with_schedule
            scheduled_stock_codes = _resolve_scheduled_stock_codes(stock_codes)
            schedule_time_provider = _build_schedule_time_provider(config.schedule_time)

            def scheduled_task():
                runtime_config = _reload_runtime_config()
                run_full_analysis(runtime_config, args, scheduled_stock_codes)

            background_tasks = []
            if getattr(config, 'agent_event_monitor_enabled', False):
                from src.services.alert_worker import AlertWorker

                interval_minutes = max(1, getattr(config, 'agent_event_monitor_interval_minutes', 5))
                alert_worker = AlertWorker(config_provider=_reload_runtime_config)

                def event_monitor_task():
                    stats = alert_worker.run_once()
                    triggered_count = stats.get("triggered", 0)
                    if triggered_count:
                        logger.info("[EventMonitor] 이번 실행에서 %d건의 알림을 트리거했습니다", triggered_count)

                background_tasks.append({
                    "task": event_monitor_task,
                    "interval_seconds": interval_minutes * 60,
                    "run_immediately": True,
                    "name": "agent_event_monitor",
                })

            run_with_schedule(
                task=scheduled_task,
                schedule_time=config.schedule_time,
                run_immediately=should_run_immediately,
                background_tasks=background_tasks,
                schedule_time_provider=schedule_time_provider,
            )
            return 0

        # Mode 3: normal one-shot run.
        if config.run_immediately:
            run_full_analysis(config, args, stock_codes)
        else:
            logger.info("RUN_IMMEDIATELY=false 설정으로 즉시 분석을 건너뜁니다")

        logger.info("\n프로그램 실행이 완료되었습니다")

        # Keep the program alive when service mode is enabled and not scheduled.
        keep_running = start_serve and not (args.schedule or config.schedule_enabled)
        if keep_running:
            logger.info("API 서버 실행 중입니다(종료하려면 Ctrl+C)...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

        return 0

    except KeyboardInterrupt:
        logger.info("\n사용자 요청으로 프로그램을 종료합니다")
        return 130

    except Exception as e:
        logger.exception("프로그램 실행 오류: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
