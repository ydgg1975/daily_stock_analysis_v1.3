# 설정 페이지 도움말 유지보수 안내

설정 페이지 도움말은 사용자가 WebUI 설정 화면 안에서 핵심 설명을 바로 확인하도록 돕는 문서와 코드 자산입니다. 화면에는 짧은 설명만 유지하고, 자세한 내용은 설정 항목 제목 옆 도움말 아이콘에서 확인하도록 구성합니다.

이 문서는 도움말 시스템의 유지보수 규칙을 설명합니다. 설정의 실제 의미, 기본값, 런타임 우선순위, 문제 해결 세부 내용은 `.env.example`, `docs/full-guide.md`, `docs/LLM_CONFIG_GUIDE.md`, `docs/llm-providers.md` 같은 주제 문서를 사실 기준으로 삼습니다.

## 데이터 구조

후면 설정 등록부는 `src/core/config_registry.py`에서 각 필드에 도움말 메타데이터를 붙입니다.

- `help_key`: 프런트엔드 도움말 문구를 찾는 안정적인 key입니다.
- `examples`: UI에 보여줄 설정 예시입니다. 민감 값은 `sk-xxxx`, `your_token` 같은 placeholder만 사용합니다.
- `docs`: 관련 문서 링크입니다. 가능하면 저장소 안의 주제 문서나 전체 가이드를 가리킵니다.
- `warning_codes`: 프런트엔드 표시나 향후 검증 확장에 사용할 안정적인 경고 code입니다.

프런트엔드의 긴 도움말 문구는 `apps/dsa-web/src/locales/settingsHelp.ts`에서 관리합니다.

- 기본 문구는 한국어 기준으로 유지합니다.
- 다른 언어 문구가 있다면 같은 의미 범위를 유지합니다.
- 문구는 용도, 값 형식, 영향 범위, 주의 사항, 관련 문서를 설명해야 하며 주제 문서 전체를 복사하지 않습니다.

## 현재 범위

기초 설정과 자주 틀리는 설정을 우선 다룹니다.

- 기본 분석 대상: `STOCK_LIST`
- LLM 런타임: `LITELLM_MODEL`, `LLM_CHANNELS`, Agent 모델, fallback 모델, YAML 라우팅, temperature
- LLM 채널 편집기: 채널명, 프로토콜, Base URL, API Key, 모델 목록, 런타임 능력 검사, 주 모델, Agent 주 모델, Vision, fallback
- 데이터와 검색: Tushare, 실시간 시세 우선순위, 실시간 기술 지표, 검색 API Key, SearXNG, 칩 분포, 뉴스 창
- 알림: Webhook, Telegram, 이메일, Discord, Slack, 보고서 출력, Webhook SSL 검증
- WebUI와 실행: host, port, 로그인 보호, 신뢰 프록시, 스케줄, 거래일 확인, 네트워크 프록시

향후 Agent, 백테스트, 보고서 고급 필드, 로그, 데이터베이스, 데스크톱, 세부 배포 설정을 이어서 추가할 수 있습니다.

## 범위 경계

- `settingsHelp.ts`의 `settings.llm_channel.*` 문구는 LLM 채널 편집기 내부 필드 설명입니다. 개별 `.env` 키와 1:1로 대응하지 않을 수 있습니다.
- 그 외 도움말 문구는 `src/core/config_registry.py`의 어떤 필드에서든 `help_key`로 추적 가능해야 합니다.
- 도움말 문구는 설정 저장, 검증, 런타임 우선순위, `.env` 쓰기, 환경 변수 override 의미를 바꾸지 않습니다.
- 실제 secret, 계정, token, 전체 Webhook URL, 로컬 절대 경로를 예시로 쓰지 않습니다.
- LLM provider, 모델명, Base URL 예시는 저장소 문서나 공식 출처로 추적 가능해야 합니다.
- 외부 provider의 전역 가용성, LiteLLM 호환 범위, fallback 정책은 도움말에서 단독으로 새 약속을 만들지 않습니다. 의미가 바뀌면 주제 문서와 PR 설명도 함께 수정합니다.

## 사실 기준 우선순위

도움말을 새로 추가하거나 고칠 때는 아래 순서로 확인합니다.

1. `.env.example`: 설정 키, 기본값, 예시 형식, 민감 값 placeholder
2. `docs/full-guide.md`: 주요 설정 설명, 실행 진입점, 배포 맥락
3. `docs/LLM_CONFIG_GUIDE.md`, `docs/llm-providers.md`: LLM 우선순위, Channels, provider/model, 호환 경계, 문제 해결
4. 주제 문서: `docs/bot/feishu-bot-config.md`, `docs/deploy-webui-cloud.md`, `docs/desktop-package.md` 등
5. 코드와 테스트: 문서와 코드가 다르면 실행 가능한 구현을 우선하고 문서를 함께 바로잡습니다.

## 재시작 의미

설정 페이지 저장은 보통 `.env`를 갱신하고 가능한 범위에서 런타임 설정을 새로 읽습니다. 도움말과 `warning_codes`는 다음 차이를 명확히 알려야 합니다.

- `WEBUI_HOST`, `WEBUI_PORT`: 프로세스 시작 시 바인딩되는 값이므로 저장 후 현재 프로세스, Docker 컨테이너, 서비스 관리자를 재시작해야 합니다.
- `RUN_IMMEDIATELY`: 비 schedule 모드 시작 시 한 번 실행할지를 정하는 값입니다. 실행 중인 WebUI/API 프로세스가 즉시 분석을 시작하게 만들지는 않습니다.
- `SCHEDULE_ENABLED`, `SCHEDULE_RUN_IMMEDIATELY`: schedule 모드의 시작 동작입니다. 저장만으로 scheduler가 새로 시작되지는 않습니다.
- `SCHEDULE_TIME`: 이미 실행 중인 scheduler가 즉시 새 시간을 반영하지 않을 수 있으므로, 안정적으로 적용하려면 schedule 프로세스를 재시작합니다.

## 검증

도움말 관련 변경 후에는 가능한 범위에서 다음을 확인합니다.

- 설정 등록부와 `settingsHelp.ts`의 `help_key` 불일치 여부
- 새 문구에 secret, 실제 계정, 전체 Webhook URL이 포함되지 않았는지
- 관련 문서 링크가 존재하는지
- `python scripts/check_language_artifacts.py`
- Web 설정 페이지를 바꿨다면 `cd apps/dsa-web && npm run lint && npm run build`
