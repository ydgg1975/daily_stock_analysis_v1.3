# 자주 묻는 질문

이 문서는 Daily Stock Analysis를 설치, 실행, 배포하면서 자주 만나는 문제와 해결 방법을 정리합니다.

## 데이터와 종목

### Q1. 미국 주식 코드가 A주처럼 처리됩니다.

증상: `AMD`, `AAPL` 같은 미국 주식 코드가 잘못된 시장으로 인식되거나 가격이 이상하게 표시됩니다.

해결:

1. 최신 버전으로 업데이트합니다.
2. Yahoo Finance 우선순위를 낮추거나 데이터 소스 우선순위를 조정합니다.

```env
YFINANCE_PRIORITY=0
REALTIME_SOURCE_PRIORITY=tencent,akshare_sina,efinance,akshare_em
```

### Q2. 보고서에 가격이 `N/A`로 표시됩니다.

가능한 원인:

- 실시간 데이터 소스가 일시적으로 실패했습니다.
- 해당 시장이 휴장 중입니다.
- 종목 코드 형식이 잘못되었습니다.

해결:

1. 종목 코드 형식을 확인합니다.
2. 잠시 후 다시 실행합니다.
3. 여러 데이터 소스 fallback이 켜져 있는지 확인합니다.

### Q3. Tushare Token 오류가 납니다.

Tushare를 사용하지 않는다면 `TUSHARE_TOKEN`은 필수가 아닙니다. 시스템은 다른 데이터 소스로 fallback할 수 있습니다.

Tushare를 사용하려면 `.env`에 Token을 넣습니다.

```env
TUSHARE_TOKEN=your_tushare_token
```

Token 발급과 종목 목록 수집은 [Tushare 종목 목록 가져오기 가이드](TUSHARE_STOCK_LIST_GUIDE.md)를 참고하세요.

### Q4. Eastmoney 또는 외부 데이터 소스가 끊깁니다.

외부 데이터 소스는 네트워크, rate limit, 원천 사이트 변경의 영향을 받을 수 있습니다.

대응:

1. 잠시 후 재시도합니다.
2. 병렬 분석 수를 낮춥니다.
3. 다른 데이터 소스 fallback을 사용합니다.
4. 필요하면 `MAX_WORKERS=1`로 줄여 단일 작업부터 확인합니다.

```env
MAX_WORKERS=1
```

## 설정과 실행

### Q5. GitHub Actions에서 환경 변수를 못 읽습니다.

민감한 값은 GitHub `Secrets`, 일반 설정은 `Variables`에 넣습니다.

권장:

- Secrets: API Key, Token, Webhook URL, 이메일 비밀번호
- Variables: `STOCK_LIST`, 모델명, 실행 모드 같은 비밀이 아닌 값

경로:

```text
Settings -> Secrets and variables -> Actions
```

### Q6. `.env`를 수정했는데 반영되지 않습니다.

직접 실행 또는 Docker 환경에서는 프로세스를 재시작해야 합니다.

```bash
docker-compose -f ./docker/docker-compose.yml down
docker-compose -f ./docker/docker-compose.yml up -d
```

Docker Compose의 `environment:` 또는 `docker run -e`로 값을 넘기고 있다면, 컨테이너 환경 변수가 `.env`보다 우선할 수 있습니다.

WebUI 설정 화면에서 저장한 값도 실제 저장 후 재로드되어야 적용됩니다. 저장 성공 메시지를 확인하세요.

### Q7. 프록시는 어떻게 설정하나요?

서버 네트워크에서 특정 provider API에 접근할 수 없다면 프록시를 설정합니다.

```env
USE_PROXY=true
PROXY_HOST=127.0.0.1
PROXY_PORT=10809
```

Docker나 systemd 환경에서는 배포 설정에서 `http_proxy`, `https_proxy` 환경 변수를 지정하는 방식도 사용할 수 있습니다. 비밀값이나 환경별 값을 코드에 하드코딩하지 마세요.

## LLM 설정

자세한 내용은 [LLM 설정 가이드](LLM_CONFIG_GUIDE.md)를 참고하세요.

### Q8. `GEMINI_API_KEY`와 `LLM_CHANNELS`를 같이 쓰면 어떻게 되나요?

설정 우선순위는 다음과 같습니다.

```text
LITELLM_CONFIG > LLM_CHANNELS > legacy provider keys
```

`LLM_CHANNELS`가 유효하면 `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` 같은 legacy provider key는 이번 요청에서 사용되지 않을 수 있습니다. 혼란을 줄이려면 한 가지 방식으로 정리하는 것을 권장합니다.

### Q9. 설정은 했는데 “주 모델 미설정”이라고 나옵니다.

다음을 확인합니다.

1. `LITELLM_MODEL`에 `provider/model` 형식이 들어 있는지 확인합니다.
2. 채널 모드라면 `LLM_CHANNELS`와 `LLM_<NAME>_MODELS`가 함께 설정되어 있는지 확인합니다.
3. `python scripts/check_env.py --config`로 로컬 설정을 검사합니다.
4. 실제 연결은 `python scripts/check_env.py --llm`으로 확인합니다.

### Q10. 여러 provider를 동시에 쓰고 싶습니다.

채널 모드를 사용합니다.

```env
LLM_CHANNELS=aihubmix,deepseek,gemini
LLM_AIHUBMIX_PROTOCOL=openai
LLM_AIHUBMIX_BASE_URL=https://aihubmix.com/v1
LLM_AIHUBMIX_API_KEY=sk-xxx
LLM_AIHUBMIX_MODELS=gpt-5.5,claude-sonnet-4-6

LLM_DEEPSEEK_PROTOCOL=deepseek
LLM_DEEPSEEK_API_KEY=sk-xxx
LLM_DEEPSEEK_MODELS=deepseek-v4-flash

LLM_GEMINI_PROTOCOL=gemini
LLM_GEMINI_API_KEY=xxx
LLM_GEMINI_MODELS=gemini-3.1-pro-preview

LITELLM_MODEL=openai/gpt-5.5
LITELLM_FALLBACK_MODELS=deepseek/deepseek-v4-flash,gemini/gemini-3.1-pro-preview
```

## 알림

### Q11. 알림 메시지가 너무 길어서 실패합니다.

일부 알림 플랫폼은 메시지 길이에 제한이 있습니다.

대응:

1. 간단 보고서 형식을 사용합니다.
2. 종목별 개별 알림을 사용합니다.
3. 긴 전문은 WebUI 또는 보고서 파일에서 확인합니다.

```env
REPORT_TYPE=simple
SINGLE_STOCK_NOTIFY=true
```

### Q12. Telegram 메시지가 오지 않습니다.

확인:

1. `TELEGRAM_BOT_TOKEN`이 정확한지 확인합니다.
2. `TELEGRAM_CHAT_ID`가 맞는지 확인합니다.
3. Bot이 대상 그룹에 추가되어 있는지 확인합니다.
4. 서버에서 Telegram API에 접근 가능한지 확인합니다.

Chat ID 확인 예시:

```text
https://api.telegram.org/bot<TOKEN>/getUpdates
```

### Q13. WeChat Work Markdown이 깨집니다.

텍스트 모드로 바꿔 테스트합니다.

```env
WECHAT_MSG_TYPE=text
```

자세한 알림 설정은 [알림 설정](notifications.md)을 참고하세요.

## Docker

### Q14. Docker 컨테이너가 시작 직후 종료됩니다.

확인:

```bash
docker-compose -f ./docker/docker-compose.yml logs -f --tail=100
```

자주 발생하는 원인:

- `.env` 형식 오류
- 필수 API Key 누락
- 포트 충돌
- 데이터 디렉터리 권한 문제

### Q15. Docker 내부에서 API 또는 외부 사이트 DNS 해석이 실패합니다.

`Temporary failure in name resolution` 또는 `NameResolutionError`가 보이면 DNS 문제일 수 있습니다.

Compose 설정에 DNS를 지정할 수 있습니다.

```yaml
dns:
  - 223.5.5.5
  - 119.29.29.29
  - 8.8.8.8
```

설정 후 컨테이너를 다시 만듭니다.

```bash
docker-compose -f ./docker/docker-compose.yml down
docker-compose -f ./docker/docker-compose.yml up -d --force-recreate
```

### Q16. Docker 버전과 WebUI 버전이 달라 보입니다.

Docker 이미지 버전은 GitHub Release 또는 이미지 tag를 기준으로 확인합니다. WebUI의 빌드 정보는 현재 브라우저가 받은 정적 파일의 빌드 시점을 보여주며, Docker 이미지 tag와 항상 같은 의미는 아닙니다.

정확한 배포 버전은 다음을 확인하세요.

- `docker-compose.yml` 또는 배포 스크립트의 이미지 tag
- GitHub Releases의 tag
- 실제 pull한 이미지 이름

## GitHub Actions

### Q17. 수동 실행이 휴장일 체크 때문에 건너뜁니다.

수동 실행에서 강제 실행 옵션을 사용하거나, 필요한 경우 휴장일 체크를 끕니다.

```env
TRADING_DAY_CHECK_ENABLED=false
```

권장 의미:

- `TRADING_DAY_CHECK_ENABLED=true`: 거래일이 아니면 기본적으로 건너뜁니다.
- `force_run=true`: 수동 실행에서 거래일 체크를 무시합니다.
- `TRADING_DAY_CHECK_ENABLED=false`: 거래일 체크를 사용하지 않습니다.

### Q18. 시장 리뷰만 실행하고 싶습니다.

로컬:

```bash
python main.py --market-review
```

GitHub Actions:

```text
Run workflow -> mode: market-only
```

## 더 보기

- [전체 가이드](full-guide.md)
- [배포 가이드](DEPLOY.md)
- [알림 설정](notifications.md)
- [LLM 설정 가이드](LLM_CONFIG_GUIDE.md)
- [변경 로그](CHANGELOG.md)

마지막 정리일: 2026-05-21
