# 배포 가이드

Daily Stock Analysis는 로컬 실행, Docker, GitHub Actions, 클라우드 서버 배포를 지원합니다.

## 1. 로컬 배포

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py --serve
```

API 서버만 실행하려면:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

## 2. Docker 배포

```bash
docker build -t daily-stock-analysis .
docker run --env-file .env -p 8000:8000 daily-stock-analysis
```

운영 환경에서는 `.env` 파일 권한과 API 키 노출 여부를 반드시 확인하세요.

## 3. GitHub Actions 배포

GitHub Actions로 매일 분석을 실행하려면 저장소 Secrets에 필요한 값을 등록합니다.

필수 또는 권장 Secrets:

| Secret | 설명 |
| --- | --- |
| `STOCK_LIST` | 분석 대상 종목 목록 |
| `OPENAI_API_KEY` | AI 모델 API 키 |
| `OPENAI_BASE_URL` | OpenAI 호환 API 주소 |
| `OPENAI_MODEL` | 모델명 |
| `TELEGRAM_BOT_TOKEN` | Telegram 알림 |
| `TELEGRAM_CHAT_ID` | Telegram 수신 ID |
| `DISCORD_WEBHOOK_URL` | Discord 알림 |
| `SLACK_BOT_TOKEN` | Slack 알림 |
| `SLACK_CHANNEL_ID` | Slack 채널 |

Actions 탭에서 워크플로를 활성화한 뒤 수동 실행으로 먼저 검증하세요.

## 4. 클라우드 서버 배포

클라우드 서버에서는 다음 순서로 진행합니다.

1. Python과 Node.js 런타임을 설치합니다.
2. 저장소를 클론합니다.
3. `.env`를 설정합니다.
4. 백엔드 의존성을 설치합니다.
5. Web UI를 빌드합니다.
6. API 서버를 systemd, Docker, 또는 프로세스 매니저로 실행합니다.
7. 리버스 프록시와 HTTPS를 설정합니다.

## 5. Web UI 빌드

```bash
cd apps/dsa-web
npm ci
npm run build
```

빌드 결과가 백엔드에서 정상 제공되는지 확인합니다.

## 6. 운영 확인

배포 후 최소 확인 항목:

- `/health` 또는 기본 API 응답
- Web UI 로딩
- 종목 검색
- 단일 종목 분석
- 뉴스 검색 결과 포함 여부
- 알림 채널 발송
- 로그에 깨진 문자나 중국어 문구가 남지 않는지

## 7. 롤백

문제가 발생하면 직전 정상 커밋 또는 직전 Docker 이미지로 되돌립니다.

설정 문제일 가능성이 높다면 먼저 `.env`, Secrets, 모델 API 주소, 알림 Webhook을 확인하세요.
