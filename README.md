<div align="center">

# Daily Stock Analysis

[![CI](https://github.com/robot0971-art/daily_stock_analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/robot0971-art/daily_stock_analysis/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

AI 기반 주식 분석, 리포트 생성, 뉴스 검색, 포트폴리오 관리, 알림 발송을 한곳에서 다루는 분석 도구입니다.

[문서 센터](docs/INDEX.md) · [전체 가이드](docs/full-guide.md) · [FAQ](docs/FAQ.md)

한국어 | [English](docs/README_EN.md)

</div>

## 주요 기능

| 영역 | 내용 |
| --- | --- |
| AI 분석 | 종목 분석, 대시보드형 의사결정 리포트, 전략 기반 분석 |
| 시장 지원 | 한국, 미국, 홍콩, 중국 시장 코드 인식 및 데이터 조회 |
| 한국 시장 | `KR005930` 같은 한국 종목 코드 인식, 한국 증시 검색 기반 준비 |
| 뉴스/검색 | 경제 뉴스, 종목 뉴스, 리포트성 최신 정보 검색, 외부 검색 공급자 연동 |
| Web UI | 분석 실행, 히스토리, 리포트, 설정, 포트폴리오, 알림 관리 |
| 데스크톱 | Electron 기반 데스크톱 실행 및 패키징 |
| 자동화 | 스케줄 실행, GitHub Actions, Docker 실행 |
| 알림 | 이메일, Telegram, Discord, Slack, Webhook 등 다중 채널 |

## 빠른 시작

```bash
pip install -r requirements.txt
python main.py --serve
```

브라우저에서 FastAPI/Web UI 진입점을 확인합니다.

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Web 프런트엔드만 빌드하려면:

```bash
cd apps/dsa-web
npm ci
npm run build
```

## 기본 사용 예시

```bash
python main.py --stocks KR005930,AAPL,HK00700
python main.py --stocks CN600519,KR005930
python main.py --market-review
python main.py --schedule
python main.py --dry-run
```

종목 코드는 시장 충돌을 줄이기 위해 접두어 사용을 권장합니다.

| 시장 | 예시 |
| --- | --- |
| 한국 | `KR005930` |
| 중국 | `CN600519` |
| 홍콩 | `HK00700` |
| 미국 | `AAPL` |

## 주요 디렉터리

| 경로 | 설명 |
| --- | --- |
| `src/` | 분석 흐름, 서비스, 리포트, 설정 |
| `api/` | FastAPI API |
| `data_provider/` | 시장 데이터 공급자 |
| `apps/dsa-web/` | React Web UI |
| `apps/dsa-desktop/` | Electron 데스크톱 |
| `bot/` | 메신저/봇 명령 처리 |
| `docs/` | 사용자 문서 |
| `tests/` | 테스트 |

## 설정

환경 변수는 `.env` 또는 실행 환경에 설정합니다. 새 설정을 추가할 때는 `.env.example`과 관련 문서를 함께 갱신해야 합니다.

AI 모델, 뉴스 공급자, 알림 채널, 데이터 공급자 설정은 [문서 센터](docs/INDEX.md)에서 항목별 가이드를 확인하세요.

## 검증

```bash
python scripts/check_ai_assets.py
python scripts/check_language_artifacts.py
python -m py_compile main.py server.py
cd apps/dsa-web && npm run build
```

최근 안정화 기준:

```bash
python -m pytest tests/test_search_performance.py tests/test_search_service_concurrency.py tests/test_fetcher_source_optimization.py tests/test_data_fetcher_prefetch_stock_names.py -q
```

## 라이선스

MIT License
