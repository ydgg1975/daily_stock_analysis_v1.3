# 전체 설정과 운영 가이드

이 문서는 Daily Stock Analysis를 처음 실행하고 운영하는 데 필요한 전체 흐름을 한곳에서 안내합니다. 자세한 주제별 설명은 개별 문서로 분리되어 있으므로, 이 문서는 “어떤 순서로 무엇을 보면 되는지”를 알려주는 운영 허브 역할을 합니다.

빠른 소개와 핵심 기능은 [README](../README.md)를 먼저 확인하세요.

## 프로젝트 구조

```text
daily_stock_analysis/
├── main.py                # CLI와 주요 실행 진입점
├── server.py              # FastAPI 서비스 진입점
├── src/                   # 분석, 설정, 알림, 서비스 로직
├── data_provider/         # 데이터 소스 어댑터와 fallback
├── api/                   # FastAPI API 라우터와 스키마
├── bot/                   # Bot 연동
├── apps/dsa-web/          # React WebUI
├── apps/dsa-desktop/      # Electron 데스크톱 앱
├── docker/                # Docker Compose와 배포 설정
├── scripts/               # 로컬/CI 보조 스크립트
├── docs/                  # 문서
└── .github/workflows/     # GitHub Actions
```

## 기본 실행 순서

1. `.env.example`을 `.env`로 복사합니다.
2. LLM provider를 하나 이상 설정합니다.
3. 분석할 종목 목록을 `STOCK_LIST`에 입력합니다.
4. 알림 채널을 하나 이상 설정합니다.
5. 로컬, Docker, GitHub Actions, 데스크톱 중 원하는 방식으로 실행합니다.
6. 분석 결과와 알림 전송 상태를 확인합니다.

```bash
cp .env.example .env
python main.py --dry-run
python main.py --serve-only
```

## LLM 설정

분석에는 LLM 설정이 필요합니다. 가장 단순한 방식은 provider API Key 하나와 주 모델명을 설정하는 것입니다.

```env
LITELLM_MODEL=openai/gpt-5.5
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
```

여러 provider와 fallback을 쓰려면 채널 모드를 사용합니다.

```env
LLM_CHANNELS=openai,gemini

LLM_OPENAI_PROTOCOL=openai
LLM_OPENAI_BASE_URL=https://api.openai.com/v1
LLM_OPENAI_API_KEY=sk-xxx
LLM_OPENAI_MODELS=gpt-5.5,gpt-5.4-mini

LLM_GEMINI_PROTOCOL=gemini
LLM_GEMINI_API_KEY=xxx
LLM_GEMINI_MODELS=gemini-3.1-pro-preview

LITELLM_MODEL=openai/gpt-5.5
LITELLM_FALLBACK_MODELS=gemini/gemini-3.1-pro-preview
```

설정 우선순위는 다음과 같습니다.

```text
LITELLM_CONFIG > LLM_CHANNELS > legacy provider keys
```

자세한 provider별 설정, YAML 고급 라우팅, Agent 모델, Vision 모델, strict temperature 대응은 [LLM 설정 가이드](LLM_CONFIG_GUIDE.md)와 [LLM provider 운영 가이드](llm-providers.md)를 참고하세요.

## 종목 목록

`STOCK_LIST`에 분석할 종목을 쉼표로 구분해 입력합니다.

```env
STOCK_LIST=600519,hk00700,AAPL
```

지원 예시:

| 시장 | 예시 |
| --- | --- |
| A주 | `600519`, `300750`, `000001` |
| 북경거래소 | `920748`, `BJ920493`, `920493.BJ` |
| 홍콩 주식 | `hk00700`, `hk09988` |
| 미국 주식 | `AAPL`, `TSLA`, `BRK.B` |
| 미국 지수 | `SPX`, `DJI`, `NASDAQ`, `VIX` |

Tushare 기반 종목 목록 수집은 [Tushare 종목 목록 가져오기 가이드](TUSHARE_STOCK_LIST_GUIDE.md)를 참고하세요.

## 뉴스와 데이터 소스

뉴스 소스는 필수는 아니지만 분석 품질에 큰 영향을 줍니다. 최근 뉴스, 공시, 이벤트, 섹터 이슈, 리스크 경고에 사용됩니다.

권장 설정:

```env
SERPAPI_API_KEYS=xxx
TAVILY_API_KEYS=xxx
TUSHARE_TOKEN=xxx
```

Anspire Open을 사용하는 경우 LLM과 검색을 같은 Key로 구성할 수 있습니다.

```env
ANSPIRE_API_KEYS=xxx
```

외부 데이터 소스는 네트워크, 원천 사이트 변경, rate limit의 영향을 받을 수 있습니다. 시스템은 가능한 경우 fallback을 사용하며, 단일 데이터 소스 실패가 전체 분석을 중단하지 않도록 설계하는 것을 목표로 합니다.

## 알림 설정

분석 결과는 여러 채널로 전송할 수 있습니다.

대표 예시:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_hook_token
FEISHU_WEBHOOK_SECRET=your_sign_secret
FEISHU_WEBHOOK_KEYWORD=주식일보
```

보고서, 이벤트 알림, 시스템 오류 채널을 분리할 수도 있습니다.

```env
NOTIFICATION_REPORT_CHANNELS=telegram,discord
NOTIFICATION_ALERT_CHANNELS=telegram
NOTIFICATION_SYSTEM_ERROR_CHANNELS=email
```

자세한 내용은 [알림 설정](notifications.md)을 참고하세요.

Bot별 문서:

- [Discord Bot 설정](bot/discord-bot-config.md)
- [Feishu 알림 설정](bot/feishu-bot-config.md)
- [DingTalk Bot 설정](bot/dingding-bot-config.md)
- [Bot 명령과 접속](bot-command.md)

## 로컬 실행

Python 의존성을 설치한 뒤 CLI로 실행합니다.

```bash
pip install -r requirements.txt

python main.py
python main.py --dry-run
python main.py --market-review
python main.py --schedule
```

WebUI만 실행하려면:

```bash
python main.py --serve-only
```

WebUI와 분석 흐름을 함께 실행하려면:

```bash
python main.py --serve
```

클라우드 서버에서 WebUI를 외부에 열려면 `.env`에서 `WEBUI_HOST=0.0.0.0`을 설정하고 서버 방화벽/보안 그룹 포트를 열어야 합니다.

## WebUI

WebUI는 FastAPI가 정적 파일과 API를 함께 제공하는 구조입니다. 프런트엔드 변경 후에는 WebUI를 빌드해야 합니다.

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
cd ../..
python main.py --serve-only
```

접속 주소:

```text
http://127.0.0.1:8000
```

서버 배포와 WebUI 접속 문제는 [배포 가이드](DEPLOY.md)와 [클라우드 서버 WebUI 접속 가이드](deploy-webui-cloud.md)를 참고하세요.

## Docker 배포

Docker Compose는 일반 서버 운영에서 권장하는 방식입니다.

```bash
cp .env.example .env
vim .env

docker-compose -f ./docker/docker-compose.yml up -d
docker-compose -f ./docker/docker-compose.yml logs -f
```

재배포:

```bash
git pull
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d
```

자세한 내용은 [배포 가이드](DEPLOY.md)를 참고하세요.

## GitHub Actions 실행

서버 없이 정기 분석과 알림만 실행하려면 GitHub Actions를 사용할 수 있습니다.

1. 저장소의 `Settings -> Secrets and variables -> Actions`로 이동합니다.
2. LLM API Key, `STOCK_LIST`, 알림 채널 값을 설정합니다.
3. Actions 탭에서 일일 분석 workflow를 수동 실행해 검증합니다.

주요 Secret/Variable 예시:

| 이름 | 설명 |
| --- | --- |
| `STOCK_LIST` | 분석할 종목 목록 |
| `LITELLM_MODEL` | 주 모델 |
| `ANSPIRE_API_KEYS` / `AIHUBMIX_KEY` | LLM/검색 provider |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` | LLM provider key |
| `SERPAPI_API_KEYS` / `TAVILY_API_KEYS` | 뉴스 검색 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram 알림 |
| `DISCORD_WEBHOOK_URL` | Discord Webhook |
| `FEISHU_WEBHOOK_URL` | Feishu Webhook |

GitHub Actions cron은 UTC 기준입니다. 한국 시간은 UTC보다 9시간 빠릅니다.

## 데스크톱 앱

데스크톱 앱은 Electron이 로컬 backend를 실행하고 React WebUI를 표시하는 구조입니다.

개발 실행:

```powershell
.\scripts\run-desktop.ps1
```

수동 빌드 흐름:

```bash
cd apps/dsa-web
npm ci
npm run build

cd ../dsa-desktop
npm install
npm run build
```

패키징, 업데이트, Windows NSIS 설치 흐름은 [데스크톱 패키징 가이드](desktop-package.md)를 참고하세요.

## 설정 백업과 복구

WebUI와 데스크톱 설정 화면에서 `.env` 백업을 내보내고 가져올 수 있습니다.

- 내보내기는 현재 저장된 `.env`를 기준으로 합니다.
- 가져오기는 키 단위 병합 방식입니다.
- WebUI에서 가져오기를 쓰려면 관리자 인증이 필요할 수 있습니다.
- 데스크톱 앱은 로컬 앱이므로 해당 제한을 별도로 적용하지 않습니다.

macOS 데스크톱 앱을 DMG로 교체하기 전에는 설정 백업을 내보내는 것을 권장합니다.

## 분석 결과와 보고서

분석 결과는 CLI 출력, WebUI 분석 기록, 알림 채널, 보고서 파일로 확인할 수 있습니다.

보고서 관련 주요 설정:

```env
REPORT_TYPE=full
REPORT_LANGUAGE=en
REPORT_SHOW_LLM_MODEL=true
REPORT_SUMMARY_ONLY=false
SINGLE_STOCK_NOTIFY=false
```

긴 알림이 실패한다면 `REPORT_TYPE=simple` 또는 `SINGLE_STOCK_NOTIFY=true`를 검토하세요.

## Agent와 AI 종목 상담

Agent 기능은 도구 호출을 통해 실시간 데이터, 뉴스, 기술 지표, 과거 분석 결과를 조회한 뒤 응답을 구성합니다.

관련 설정:

```env
AGENT_LITELLM_MODEL=
AGENT_EVENT_MONITOR_ENABLED=false
AGENT_EVENT_MONITOR_INTERVAL_MINUTES=5
```

Agent 모델을 비워두면 일반 분석의 LLM 설정을 상속합니다. Agent만 별도 모델을 쓰려면 `AGENT_LITELLM_MODEL`을 설정하세요.

## 이벤트 알림 센터

EventMonitor는 가격, 등락률, 거래량, 이동평균, RSI, MACD, KDJ, CCI 같은 조건을 평가해 알림을 보낼 수 있습니다.

기본 설정:

```env
AGENT_EVENT_MONITOR_ENABLED=true
AGENT_EVENT_MONITOR_INTERVAL_MINUTES=5
```

WebUI의 알림 페이지에서 규칙 관리, dry-run, 트리거 이력, 알림 시도 결과, cooldown 상태를 확인할 수 있습니다. 상세 계약과 경계 조건은 [실시간 알림 센터](alerts.md)를 참고하세요.

## 포트폴리오

포트폴리오 기능은 계좌, 거래, 현금 흐름, 회사 행동, CSV 가져오기, 위험 요약을 다룹니다.

주요 API:

| API | 설명 |
| --- | --- |
| `/api/v1/portfolio/snapshot` | 보유 현황 조회 |
| `/api/v1/portfolio/risk` | 위험 요약 |
| `/api/v1/portfolio/trades` | 거래 기록 |
| `/api/v1/portfolio/cash-ledger` | 현금 흐름 |
| `/api/v1/portfolio/corporate-actions` | 회사 행동 |
| `/api/v1/portfolio/imports/csv/brokers` | CSV broker parser 목록 |
| `/api/v1/portfolio/fx/refresh` | 환율 캐시 갱신 |

CSV 가져오기는 먼저 dry-run으로 확인한 뒤 실제 반영하는 흐름을 권장합니다.

## 검증 명령

백엔드:

```bash
pip install -r requirements.txt
pip install flake8 pytest
./scripts/ci_gate.sh
python -m pytest -m "not network"
```

Web:

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

데스크톱:

```bash
cd apps/dsa-desktop
npm install
npm run build
```

문서와 언어 정리:

```bash
python scripts/check_language_artifacts.py
python scripts/check_ai_assets.py
git diff --check
```

## 문제 해결

자주 보는 문제는 [FAQ](FAQ.md)에 정리되어 있습니다.

대표 확인 순서:

1. `.env` 저장 여부와 실제 실행 환경 변수를 확인합니다.
2. LLM provider 연결 테스트를 실행합니다.
3. 데이터 소스 오류가 단일 provider 문제인지 확인합니다.
4. 알림 채널을 개별 테스트합니다.
5. Docker 또는 systemd 로그를 확인합니다.
6. WebUI 정적 파일이 빌드되어 있는지 확인합니다.

## 관련 문서

- [README](../README.md)
- [문서 인덱스](INDEX.md)
- [배포 가이드](DEPLOY.md)
- [클라우드 서버 WebUI 접속 가이드](deploy-webui-cloud.md)
- [LLM 설정 가이드](LLM_CONFIG_GUIDE.md)
- [LLM provider 운영 가이드](llm-providers.md)
- [알림 설정](notifications.md)
- [FAQ](FAQ.md)
- [데스크톱 패키징 가이드](desktop-package.md)
- [실시간 알림 센터](alerts.md)
- [변경 로그](CHANGELOG.md)

마지막 정리일: 2026-05-21

### Docker env file contract

Docker 실행 예시는 컨테이너 안의 `/app/.env` 단일 파일 bind mount 대신 시작 시점 환경 주입을 사용합니다.

```bash
docker run --env-file .env daily-stock-analysis
```

Compose 구성은 다음처럼 `env_file:`을 사용합니다.

```yaml
env_file:
  - ../.env
```
