# Zeabur 배포 가이드

이 문서는 daily stock analysis 프로젝트를 Zeabur에 배포해 FastAPI Web UI, 예약 분석, Discord 알림을 운영하는 방법을 설명합니다.

## 사전 준비

- Zeabur 계정
- GitHub 저장소 접근 권한
- 사용할 LLM provider API 키
- 선택 사항: Discord bot token 또는 webhook URL
- 선택 사항: 검색 provider API 키

배포 전 로컬에서 최소한 다음 명령이 통과하는지 확인하는 것을 권장합니다.

```bash
python -m pytest -m "not network"
cd apps/dsa-web && npm run build
```

## 저장소 연결

1. Zeabur 대시보드에서 새 프로젝트를 만듭니다.
2. GitHub 저장소를 연결합니다.
3. 배포할 branch를 선택합니다. 운영 배포는 보통 `main`을 사용합니다.
4. Dockerfile 경로가 필요하면 `docker/Dockerfile`을 지정합니다.
5. 빌드와 배포를 시작합니다.

GitHub Actions에서 이미 Docker 이미지를 만들고 있다면 Zeabur에서 해당 이미지를 사용하는 방식도 가능합니다. 단일 서비스로 단순하게 운영하려면 Zeabur가 저장소의 Dockerfile을 직접 빌드하도록 두는 편이 관리하기 쉽습니다.

## 실행 모드

Zeabur 서비스의 Start Command는 운영 목적에 맞게 선택합니다.

| 목적 | Start Command |
| --- | --- |
| Web UI와 API만 실행 | `python main.py --serve-only` |
| API와 스케줄러 함께 실행 | `python main.py --serve` |
| 예약 분석만 실행 | `python main.py --schedule` |
| 시장 리뷰 1회 실행 | `python main.py --market-review` |

웹 서비스로 공개하려면 `--serve-only` 또는 `--serve`를 우선 사용합니다. host와 port는 환경 변수에서 제어하는 방식을 권장합니다.

## 필수 환경 변수

| 변수 | 예시 | 설명 |
| --- | --- | --- |
| `PYTHONUNBUFFERED` | `1` | 컨테이너 로그를 즉시 출력합니다. |
| `LOG_DIR` | `/app/logs` | 로그 저장 경로입니다. |
| `DATABASE_PATH` | `/app/data/stock_analysis.db` | SQLite DB 경로입니다. |
| `WEBUI_HOST` | `0.0.0.0` | 외부 접속을 위한 bind 주소입니다. |
| `WEBUI_PORT` | `8000` | Zeabur가 노출할 애플리케이션 포트입니다. |

일부 기존 설정이나 스크립트가 `API_HOST`, `API_PORT`를 읽는 경우가 있으므로, 운영 환경에서는 필요에 따라 `WEBUI_*`와 `API_*` 값을 함께 맞춥니다.

## LLM과 검색 API 설정

LLM 설정은 `docs/LLM_CONFIG_GUIDE.md`와 `docs/llm-providers.md`를 기준으로 합니다.

자주 쓰는 변수는 다음과 같습니다.

| 변수 | 설명 |
| --- | --- |
| `LLM_CHANNELS` | 사용할 LLM channel 목록 |
| `LLM_<CHANNEL>_PROTOCOL` | provider protocol |
| `LLM_<CHANNEL>_BASE_URL` | provider endpoint |
| `LLM_<CHANNEL>_API_KEY` | channel 단일 API 키 |
| `LITELLM_MODEL` | 기본 분석 모델 |
| `AGENT_LITELLM_MODEL` | Agent 모델 |
| `GEMINI_API_KEY` | Gemini API 키 |
| `OPENAI_API_KEY` | OpenAI API 키 |
| `ANSPIRE_API_KEYS` | Anspire API 키 목록 |
| `AIHUBMIX_KEY` | AIHubMix API 키 |
| `SERPAPI_API_KEYS` | SerpAPI 키 목록 |
| `TAVILY_API_KEYS` | Tavily 키 목록 |
| `BRAVE_API_KEYS` | Brave Search 키 목록 |
| `SEARXNG_BASE_URLS` | SearXNG endpoint 목록 |

API 키는 Zeabur의 Secret 또는 환경 변수 관리 화면에서 등록합니다. 공개 로그에 출력되지 않도록 값 자체를 문서나 workflow에 직접 쓰지 않습니다.

## Discord 알림

Discord 알림을 사용하려면 다음 중 필요한 값을 설정합니다.

| 변수 | 설명 |
| --- | --- |
| `DISCORD_BOT_TOKEN` | Discord bot token |
| `DISCORD_MAIN_CHANNEL_ID` | 기본 알림 채널 ID |
| `DISCORD_WEBHOOK_URL` | webhook 방식 알림 URL |

Bot 방식은 Discord Developer Portal에서 애플리케이션을 만들고, bot 권한과 Message Content Intent를 확인해야 합니다. Webhook 방식은 채널별 webhook URL만 있으면 단순하게 운영할 수 있습니다.

## 볼륨 설정

컨테이너가 재배포되어도 데이터가 유지되도록 다음 경로를 persistent volume에 연결합니다.

| 경로 | 용도 |
| --- | --- |
| `/app/data` | SQLite DB와 상태 파일 |
| `/app/logs` | 실행 로그 |
| `/app/reports` | 분석 보고서 |

볼륨을 설정하지 않으면 재배포나 컨테이너 재생성 시 DB와 보고서가 사라질 수 있습니다.

## Healthcheck

Zeabur의 healthcheck는 다음 endpoint 중 하나를 사용합니다.

- `GET /api/health`
- `GET /health`

Dockerfile healthcheck 예시는 다음과 같습니다.

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || curl -f http://localhost:8000/health || exit 1
```

서비스가 예약 분석만 실행하는 모드라면 HTTP healthcheck가 맞지 않을 수 있습니다. 이 경우 Zeabur 서비스 유형을 분리하거나 healthcheck 정책을 조정합니다.

## 도메인과 HTTPS

Zeabur 대시보드에서 커스텀 도메인을 연결할 수 있습니다.

1. 서비스의 Domains 메뉴를 엽니다.
2. 사용할 도메인을 추가합니다.
3. 안내된 DNS 레코드를 도메인 관리 화면에 등록합니다.
4. HTTPS 인증서 발급이 완료될 때까지 기다립니다.

관리자 설정 화면을 외부에 공개하는 경우 인증 설정과 접근 제어를 반드시 확인합니다.

## 운영 점검

배포 후 다음을 확인합니다.

- `/api/health` 또는 `/health` 응답
- Web UI 접속
- 설정 화면에서 LLM 연결 테스트
- 간단한 종목 분석 실행
- Discord 알림 전송 여부
- `/app/data` 볼륨에 DB가 생성되는지
- 재배포 후 DB와 설정이 유지되는지

로그 확인은 Zeabur 대시보드의 Logs 화면을 우선 사용합니다. 컨테이너 내부 경로를 확인할 수 있으면 `/app/logs`도 함께 확인합니다.

## 문제 해결

| 증상 | 확인할 항목 |
| --- | --- |
| Web UI에 접속되지 않음 | Start Command, `WEBUI_HOST=0.0.0.0`, port 노출 설정을 확인합니다. |
| Healthcheck 실패 | 실행 모드가 HTTP 서버를 띄우는지, `/api/health`가 응답하는지 확인합니다. |
| 분석이 실행되지 않음 | LLM API 키, 분석 대상 종목, 스케줄 설정, 로그의 예외 메시지를 확인합니다. |
| Discord 알림이 오지 않음 | token 또는 webhook URL, 채널 ID, bot 권한을 확인합니다. |
| 재배포 후 데이터가 사라짐 | `/app/data` volume 연결 여부를 확인합니다. |
| 외부 API 요청 실패 | provider 키, 네트워크 정책, timeout, rate limit을 확인합니다. |

## 권장 운영 방식

- Web UI/API 서비스와 예약 분석 worker를 분리하면 장애 범위를 줄일 수 있습니다.
- LLM provider는 최소 두 개 channel을 준비해 fallback을 구성합니다.
- API 키와 webhook URL은 Secret으로 관리합니다.
- 운영 전에는 작은 종목 목록으로 dry run을 수행합니다.
- 변경 배포 후에는 healthcheck, LLM 연결 테스트, 실제 분석 1회를 확인합니다.
