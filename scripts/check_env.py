# -*- coding: utf-8 -*-
"""로컬 실행 환경을 점검하는 보조 스크립트.

주요 확인 항목:
1. 설정 로드와 핵심 값 확인
2. 데이터베이스 연결과 저장 데이터 요약
3. 데이터 소스 조회
4. LLM 호출 준비 상태
5. 알림 전송 준비 상태
"""

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional


# 프록시는 명시적으로 켠 경우에만 적용합니다. GitHub Actions에서는 항상 건너뜁니다.
if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("USE_PROXY", "false").lower() == "true":
    proxy_host = os.getenv("PROXY_HOST", "127.0.0.1")
    proxy_port = os.getenv("PROXY_PORT", "10809")
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    os.environ["http_proxy"] = proxy_url
    os.environ["https_proxy"] = proxy_url


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def print_header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_section(title: str) -> None:
    print(f"\n--- {title} ---")


def _configured(value: Optional[str]) -> str:
    return "설정됨" if value else "미설정"


def _masked(value: Optional[str], visible: int = 8) -> str:
    if not value:
        return "-"
    return f"{value[:visible]}..."


def check_config() -> bool:
    print_header("1. 설정 로드 확인")

    from src.config import get_config

    config = get_config()

    print_section("기본 설정")
    print(f"  종목 목록: {config.stock_list}")
    print(f"  데이터베이스 경로: {config.database_path}")
    print(f"  최대 병렬 수: {config.max_workers}")
    print(f"  디버그 모드: {config.debug}")

    print_section("API 설정")
    print(f"  Tushare Token: {_configured(config.tushare_token)}")
    print(f"    Token 앞자리: {_masked(config.tushare_token)}")
    print(f"  Gemini API Key: {_configured(config.gemini_api_key)}")
    print(f"    Key 앞자리: {_masked(config.gemini_api_key)}")
    print(f"  Gemini 주 모델: {config.gemini_model}")
    print(f"  Gemini 보조 모델: {config.gemini_model_fallback}")
    print(f"  WeChat Webhook: {_configured(config.wechat_webhook_url)}")

    print_section("설정 검증")
    issues = config.validate_structured()
    prefixes = {"error": "오류", "warning": "경고", "info": "정보"}
    for issue in issues:
        prefix = prefixes.get(issue.severity, issue.severity)
        print(f"  [{prefix}] {issue.message}")

    if not any(issue.severity in ("error", "warning") for issue in issues):
        print("  핵심 설정 검증을 통과했습니다.")

    return True


def view_database() -> bool:
    print_header("2. 데이터베이스 내용 확인")

    from sqlalchemy import text
    from src.storage import get_db

    db = get_db()
    print_section("데이터베이스 연결")
    print("  연결 성공")

    session = db.get_session()
    try:
        result = session.execute(
            text(
                """
                SELECT
                    code,
                    COUNT(*) AS count,
                    MIN(date) AS min_date,
                    MAX(date) AS max_date,
                    data_source
                FROM stock_daily
                GROUP BY code, data_source
                ORDER BY code
                """
            )
        )
        stocks = result.fetchall()

        print_section(f"저장된 종목 데이터: {len(stocks)}건")
        for stock in stocks:
            print(
                "  "
                f"{stock.code}: {stock.count}개, "
                f"{stock.min_date} ~ {stock.max_date}, "
                f"출처: {stock.data_source}"
            )

        today = date.today()
        today_result = session.execute(
            text("SELECT COUNT(*) FROM stock_daily WHERE date = :today"),
            {"today": today},
        )
        today_count = today_result.scalar() or 0
        print_section("오늘 데이터")
        print(f"  {today} 기준 {today_count}건")

        recent_date = today - timedelta(days=7)
        recent_result = session.execute(
            text("SELECT COUNT(*) FROM stock_daily WHERE date >= :recent_date"),
            {"recent_date": recent_date},
        )
        recent_count = recent_result.scalar() or 0
        print(f"  최근 7일 데이터: {recent_count}건")

        return True
    finally:
        session.close()


def check_data_fetch(stock_code: str = "600519") -> bool:
    print_header("3. 데이터 소스 조회 확인")

    from data_provider.fetcher import DataFetcherManager

    manager = DataFetcherManager()
    print_section("사용 가능한 데이터 소스")
    for fetcher_name in manager.available_fetchers:
        print(f"  - {fetcher_name}")

    print_section(f"{stock_code} 최근 데이터 조회")
    try:
        data = manager.get_daily_data(stock_code, days=5)
    except Exception as exc:
        logger.exception("데이터 조회 실패")
        print(f"  조회 실패: {exc}")
        return False

    if data is None or data.empty:
        print("  조회 결과가 없습니다.")
        return False

    print(f"  조회 성공: {len(data)}행")
    print(f"  컬럼: {', '.join(map(str, data.columns))}")
    print(data.head().to_string(index=False))
    return True


def check_llm() -> bool:
    print_header("4. LLM 호출 준비 상태 확인")

    from src.analyzer import GeminiAnalyzer
    from src.config import get_config

    config = get_config()
    if not config.gemini_api_key:
        print("  Gemini API Key가 없어 LLM 호출을 건너뜁니다.")
        return False

    analyzer = GeminiAnalyzer()
    print_section("분석기 초기화")
    print(f"  주 모델: {config.gemini_model}")
    print(f"  보조 모델: {config.gemini_model_fallback}")

    prompt = "테스트 메시지입니다. '정상'이라고만 답하세요."
    try:
        response = analyzer._call_gemini_api(prompt)
    except Exception as exc:
        logger.exception("LLM 호출 실패")
        print(f"  호출 실패: {exc}")
        return False

    print(f"  응답: {str(response)[:200]}")
    return True


def check_notification() -> bool:
    print_header("5. 알림 전송 확인")

    from src.notification import NotificationService

    service = NotificationService()
    test_message = (
        f"DSA 환경 점검 알림\n\n"
        f"전송 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "이 메시지가 보이면 알림 설정이 정상입니다."
    )

    try:
        ok = service.send_text(test_message)
    except Exception as exc:
        logger.exception("알림 전송 실패")
        print(f"  전송 실패: {exc}")
        return False

    print("  전송 성공" if ok else "  전송 실패")
    return bool(ok)


def query_stock_data(stock_code: str) -> bool:
    print_header(f"{stock_code} 데이터 상세 조회")

    from sqlalchemy import text
    from src.storage import get_db

    db = get_db()
    session = db.get_session()
    try:
        result = session.execute(
            text(
                """
                SELECT date, open, high, low, close, volume, data_source
                FROM stock_daily
                WHERE code = :code
                ORDER BY date DESC
                LIMIT 10
                """
            ),
            {"code": stock_code},
        )
        rows = result.fetchall()

        if not rows:
            print("  저장된 데이터가 없습니다.")
            return False

        for row in rows:
            print(
                "  "
                f"{row.date}: O={row.open}, H={row.high}, "
                f"L={row.low}, C={row.close}, V={row.volume}, "
                f"출처={row.data_source}"
            )
        return True
    finally:
        session.close()


def run_all_tests(stock_code: str) -> bool:
    checks = [
        ("설정", check_config),
        ("데이터베이스", view_database),
        ("데이터 조회", lambda: check_data_fetch(stock_code)),
    ]

    results: list[tuple[str, bool]] = []
    for name, check in checks:
        try:
            results.append((name, check()))
        except Exception as exc:
            logger.exception("%s 확인 중 예외 발생", name)
            print(f"  {name} 확인 실패: {exc}")
            results.append((name, False))

    print_header("확인 결과 요약")
    for name, ok in results:
        print(f"  {name}: {'통과' if ok else '실패'}")

    return all(ok for _, ok in results)


def main() -> int:
    parser = argparse.ArgumentParser(description="DSA 로컬 환경 점검")
    parser.add_argument("--config", action="store_true", help="설정만 확인합니다.")
    parser.add_argument("--db", action="store_true", help="데이터베이스만 확인합니다.")
    parser.add_argument("--fetch", action="store_true", help="데이터 소스 조회를 확인합니다.")
    parser.add_argument("--llm", action="store_true", help="LLM 호출을 확인합니다.")
    parser.add_argument("--notify", action="store_true", help="알림 전송을 확인합니다.")
    parser.add_argument("--stock", default="600519", help="확인할 종목 코드")
    parser.add_argument("--query", metavar="CODE", help="저장된 특정 종목 데이터를 조회합니다.")
    parser.add_argument("--all", action="store_true", help="기본 확인 항목을 모두 실행합니다.")
    args = parser.parse_args()

    if args.query:
        return 0 if query_stock_data(args.query) else 1
    if args.config:
        return 0 if check_config() else 1
    if args.db:
        return 0 if view_database() else 1
    if args.fetch:
        return 0 if check_data_fetch(args.stock) else 1
    if args.llm:
        return 0 if check_llm() else 1
    if args.notify:
        return 0 if check_notification() else 1

    return 0 if run_all_tests(args.stock) else 1


if __name__ == "__main__":
    raise SystemExit(main())
