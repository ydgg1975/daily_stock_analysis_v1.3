# 전체 운영 가이드

Daily Stock Analysis를 설치하고, 설정하고, 운영하는 데 필요한 핵심 절차를 한국어로 정리한 문서입니다.

## 1. 실행 방식

### 로컬 실행

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py --serve
```

### 단일 분석 실행

```bash
python main.py --stocks KR005930,AAPL,hk00700
```

### 예약 실행

```bash
python main.py --schedule
```

### API 서버 실행

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

## 2. 종목 코드 규칙

한국, 중국, 홍콩, 미국 코드가 서로 충돌하지 않도록 시장 접두사를 사용하는 방식을 권장합니다.

| 시장 | 예시 | 설명 |
| --- | --- | --- |
| 한국 | `KR005930` | 삼성전자 |
| 중국 | `CN600519` | 중국 A주 |
| 홍콩 | `hk00700` | 홍콩 종목 |
| 미국 | `AAPL` | 미국 티커 |

숫자만 입력하는 기존 방식은 일부 시장에서 충돌할 수 있으므로 새 설정에는 접두사 방식을 우선 사용하세요.

## 3. 필수 환경 변수

`.env` 또는 GitHub Actions Secrets에 필요한 값을 설정합니다.

| 변수 | 설명 |
| --- | --- |
| `STOCK_LIST` | 분석 대상 종목 목록 |
| `OPENAI_API_KEY` | OpenAI 호환 모델 API 키 |
| `OPENAI_BASE_URL` | OpenAI 호환 API 주소 |
| `OPENAI_MODEL` | 사용할 모델명 |
| `TELEGRAM_BOT_TOKEN` | Telegram 알림 사용 시 필요 |
| `TELEGRAM_CHAT_ID` | Telegram 수신 채팅 ID |
| `DISCORD_WEBHOOK_URL` | Discord 알림 Webhook |
| `SLACK_BOT_TOKEN` | Slack Bot 토큰 |
| `SLACK_CHANNEL_ID` | Slack 채널 ID |
| `EMAIL_SENDER` | 이메일 발신 계정 |
| `EMAIL_PASSWORD` | 이메일 발신 비밀번호 또는 앱 비밀번호 |

새 환경 변수를 추가할 때는 `.env.example`과 관련 문서를 함께 갱신해야 합니다.

## 4. AI 모델 설정

이 프로젝트는 OpenAI 호환 API를 우선 기준으로 사용합니다. 다른 공급자도 OpenAI 호환 엔드포인트를 제공한다면 같은 설정 구조로 연결할 수 있습니다.

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

로컬 모델을 사용할 경우에는 Ollama 같은 로컬 서버를 먼저 실행한 뒤 `OPENAI_BASE_URL`을 로컬 주소로 지정합니다.

## 5. 뉴스와 검색 공급자

뉴스 품질은 검색 공급자 설정에 크게 영향을 받습니다. 한국 경제 뉴스와 증권사 리포트를 강화하려면 한국어 검색 결과를 안정적으로 반환하는 공급자를 우선 연결하세요.

권장 확인 항목:

- 종목명과 종목코드 검색이 모두 가능한지
- 한국어 뉴스 결과가 충분히 나오는지
- 검색 실패 시 분석 전체가 중단되지 않는지
- API 제한량과 timeout 정책이 적절한지

## 6. Web UI

프런트엔드 개발과 빌드는 `apps/dsa-web`에서 실행합니다.

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

API 서버와 함께 사용할 때는 백엔드 주소, 인증 설정, 리포트 렌더링 상태를 같이 확인합니다.

## 7. 데스크톱 앱

데스크톱 앱은 `apps/dsa-desktop`에서 관리합니다. 데스크톱 빌드 전에 Web 빌드가 정상인지 먼저 확인하는 것이 좋습니다.

```bash
cd apps/dsa-web
npm run build

cd ../dsa-desktop
npm install
npm run build
```

## 8. 알림 채널

알림 채널은 하나 이상 설정하면 됩니다. 여러 채널을 동시에 설정할 수 있으며, 한 채널이 실패하더라도 전체 분석 흐름이 중단되지 않도록 유지하는 것이 원칙입니다.

지원 채널:

- 이메일
- Telegram
- Discord
- Slack
- Webhook 계열 채널

채널별 세부 설정은 `docs/notifications.md`를 참고하세요.

## 9. 데이터와 장애 대응

데이터 공급자는 실패할 수 있으므로 fallback이 중요합니다.

운영 시 확인할 항목:

- 시장별 데이터 공급자 우선순위
- timeout과 retry 설정
- 실패한 종목이 전체 작업을 중단시키는지 여부
- 뉴스 검색 실패 시 리포트가 어떻게 표시되는지
- 캐시가 오래된 결과를 반환하지 않는지

## 10. 검증 명령

백엔드 변경 후:

```bash
python -m pytest -m "not network"
python -m py_compile main.py server.py
```

전체 게이트:

```bash
./scripts/ci_gate.sh
```

AI 협업 문서나 지침 파일 변경 후:

```bash
python scripts/check_ai_assets.py
python scripts/check_language_artifacts.py --pinyin-scope surface
```

## 11. 운영 원칙

- 사용자에게 보이는 문구는 한국어를 기본으로 유지합니다.
- 중국어 원문, 깨진 문자, 병음 표기는 새 문서와 UI에 추가하지 않습니다.
- 시장 코드 충돌을 피하기 위해 `KR`, `CN`, `hk`, 미국 티커 규칙을 명확히 구분합니다.
- 설정 없이도 기본 실행이 가능하고, 설정하면 기능이 강화되는 구조를 유지합니다.
- 문서, API, Web, Desktop이 같은 용어를 사용하도록 맞춥니다.
