# 실시간 알림 센터

이 문서는 알림 센터의 현재 실행 기준, 데이터 계약, 단계별 구현 범위, 호환 경계를 정리합니다.

## 현재 기준

런타임 알림은 `src/services/alert_worker.py`의 백그라운드 worker가 담당합니다. 규칙 평가는 `src/services/alert_service.py`와 `src/agent/events.py`의 기존 EventMonitor 규칙 모델을 재사용합니다.

- 설정 진입점: `AGENT_EVENT_MONITOR_ENABLED`, `AGENT_EVENT_MONITOR_INTERVAL_MINUTES`, `AGENT_EVENT_ALERT_RULES_JSON`
- 실행 진입점: `main.py`가 schedule 모드에서 `agent_event_monitor` 백그라운드 작업을 등록합니다.
- 규칙 소스: worker는 DB에 저장된 active rule을 읽고, legacy `AGENT_EVENT_ALERT_RULES_JSON`도 계속 지원합니다.
- 알림 전송: 트리거 후 `NotificationService.send(..., route_type="alert")`를 사용하며 기존 alert 라우팅 설정을 따릅니다.
- 설정 검증: `src/services/system_config_service.py`가 legacy JSON 형식과 규칙 의미를 검증합니다.

현재 런타임에서 실행 가능한 기본 규칙은 세 가지입니다.

| `alert_type` | 방향 필드 | 임계값 필드 | 의미 |
| --- | --- | --- | --- |
| `price_cross` | `direction`: `above` / `below` | `price` | 실시간 가격이 지정 가격을 상향 또는 하향 돌파 |
| `price_change_percent` | `direction`: `up` / `down` | `change_pct` | 실시간 등락률이 지정 비율에 도달 |
| `volume_spike` | 없음 | `multiplier` | 최신 거래량이 최근 평균 거래량의 지정 배수 이상 |

`sentiment_shift`, `risk_flag`, `custom` 같은 값은 향후 확장 자리이며 현재 실행 가능한 규칙으로 받지 않습니다.

## Legacy 설정 호환

`AGENT_EVENT_ALERT_RULES_JSON`은 legacy 규칙 입력으로 계속 유지합니다. 자동 마이그레이션, 삭제, 덮어쓰기, 재작성은 하지 않습니다.

- 빈 문자열이나 빈 배열은 legacy 규칙 없음으로 봅니다.
- schedule 모드는 legacy 규칙이 없어도 worker를 등록해, API에서 새로 만든 active rule이 재시작 없이 평가될 수 있게 합니다.
- Web/System 설정 저장은 JSON 형식, 필수 필드, 방향, 임계값, 지원 규칙 타입을 엄격히 검증해야 합니다.
- 런타임 로딩 중 단일 규칙이 잘못되면 그 규칙만 건너뛰고 나머지 규칙은 계속 평가합니다.
- worker의 프로세스 내부 fingerprint는 반복 푸시를 줄이기 위한 안전장치입니다. 영속 냉각 모델이나 재시작 후 유지되는 상태가 아닙니다.

## 데이터 계약

아래 계약은 API, worker, Web, 저장소 구현을 맞추기 위한 기준입니다.

### `alert_rule`

관리 가능한 알림 규칙입니다.

| 필드 | 설명 |
| --- | --- |
| `id` | 규칙 ID |
| `name` | 사용자 표시 이름 |
| `target_scope` | 대상 범위. 예: `single_symbol`, `watchlist`, `portfolio`, `market` |
| `target` | 대상 코드 또는 참조 ID |
| `alert_type` | 규칙 타입 |
| `parameters` | 규칙 파라미터 |
| `severity` | 알림 등급. 예: `info`, `warning`, `critical` |
| `enabled` | 활성 여부 |
| `cooldown_policy` | 냉각 정책 |
| `notification_policy` | 알림 정책 |
| `source` | 생성 출처. 예: `legacy_env`, `web`, `api`, `import` |
| `created_at` / `updated_at` | 생성 및 수정 시간 |

### `alert_trigger`

기록 가능한 규칙 평가 또는 실제 트리거입니다.

| 필드 | 설명 |
| --- | --- |
| `id` | 트리거 기록 ID |
| `rule_id` | 규칙 ID |
| `target` | 실제 평가 대상 |
| `observed_value` | 관측값 |
| `threshold` | 임계값 |
| `reason` | 트리거 또는 평가 사유 |
| `data_source` | 사용한 데이터 소스 또는 provider |
| `data_timestamp` | 데이터 기준 시간. 없으면 현재 시간으로 위조하지 않습니다. |
| `triggered_at` | 평가 또는 트리거 시간 |
| `status` | `triggered`, `skipped`, `degraded`, `failed` 등 |
| `diagnostics` | 민감 정보를 제거한 진단 정보 |

### `alert_notification`

트리거와 연결된 알림 전송 시도입니다.

| 필드 | 설명 |
| --- | --- |
| `id` | 전송 시도 ID |
| `trigger_id` | 연결된 트리거 ID |
| `channel` | 알림 채널 |
| `attempt` | 시도 순번 |
| `success` | 성공 여부 |
| `error_code` | 구조화된 오류 코드 |
| `retryable` | 재시도 권장 여부 |
| `latency_ms` | 소요 시간 |
| `diagnostics` | 민감 정보를 제거한 전송 진단 |
| `created_at` | 시도 시간 |

### `alert_cooldown`

규칙 또는 대상 기준의 냉각 상태입니다.

| 필드 | 설명 |
| --- | --- |
| `rule_id` | 규칙 ID |
| `target` | 냉각 대상 |
| `severity` | 선택 등급 차원 |
| `last_triggered_at` | 최근 트리거 시간 |
| `cooldown_until` | 냉각 종료 시간 |
| `reason` | 냉각 사유 |
| `state` | `active`, `expired` 등 |
| `updated_at` | 수정 시간 |

## 저장소 설계 기준

저장소에는 이미 SQLite 기반 저장 계층과 repository/service 분리가 있습니다.

- `src/storage.py`: SQLite 연결, SQLAlchemy ORM 모델, `DatabaseManager`
- `src/repositories/`: 데이터 접근 계층
- `src/services/`: 비즈니스 서비스 계층
- 기본 DB 경로: 보통 `data/stock_analysis.db`

알림 지속화를 구현할 때는 같은 구조를 재사용합니다. storage에는 ORM 모델, repository에는 CRUD와 조회, service에는 규칙 검증과 평가 상태, 알림 결과, 냉각 의미를 둡니다.

schema 변경 PR은 다음을 함께 설명해야 합니다.

- 중복 초기화가 기존 데이터를 깨지 않는지
- 알림 센터가 꺼져 있을 때 일일 분석, 문의, 알림, 시장 복기, 포트폴리오 기능에 영향이 없는지
- revert 외에 DB 테이블 또는 데이터 정리가 필요한지
- legacy `AGENT_EVENT_ALERT_RULES_JSON`을 자동으로 마이그레이션하거나 삭제하지 않는지

## 단계별 범위

### P0 문서와 계약

- 문서, 계약, 저장소 설계, 호환 테스트를 정리합니다.
- API, Web 화면, DB 테이블, worker 동작은 새로 추가하지 않습니다.

### P1 Alert API MVP

- `api/v1/endpoints/alerts.py`와 `api/v1/schemas/alerts.py`를 추가합니다.
- 규칙 CRUD, 활성화/비활성화, dry-run 테스트, 트리거/알림 조회 API를 제공합니다.
- 첫 버전은 `price_cross`, `price_change_percent`, `volume_spike`만 지원합니다.
- `test` API는 dry-run만 수행하며 실제 알림 전송이나 트리거 기록을 만들지 않습니다.
- API 응답은 token, 전체 Webhook URL, 이메일 비밀번호, cookie, Bot secret을 노출하지 않습니다.

### P2 알림 평가 Worker

- schedule 런타임을 매 라운드 DB active rule과 legacy JSON 규칙을 함께 평가하는 worker로 정리합니다.
- DB 규칙과 legacy 규칙은 `target_scope + target + alert_type + canonical(parameters)` 기준으로 중복 제거하며 DB 규칙을 우선합니다.
- 단일 규칙 실패는 `failed` 상태로 기록하고 같은 라운드의 다른 규칙이나 메인 분석 흐름을 막지 않습니다.
- `alert_triggers`에는 `triggered`, `skipped`, `degraded`, `failed` 같은 최소 평가 기록만 남깁니다.
- 정상 `not_triggered`는 표를 불필요하게 키우지 않기 위해 기록하지 않습니다.

### P3 Web 알림 센터 MVP

- WebUI에 `/alerts` 알림 센터를 추가합니다.
- 규칙 목록, 페이지네이션, 활성화 필터, 규칙 타입 필터를 제공합니다.
- 생성 폼은 현재 실행 가능한 기본 세 가지 규칙과 `single_symbol` 대상을 우선 지원합니다.
- dry-run 테스트는 API schema에 선언된 값만 표시합니다.
- 알림 시도 영역은 `GET /api/v1/alerts/notifications`를 조회하지만, P2에서 per-channel attempt를 쓰지 않으면 빈 상태를 정상으로 봅니다.
- Web은 legacy JSON 직접 편집, 자동 마이그레이션, 자동 삭제를 제공하지 않습니다.

### P4 알림 결과와 영속 냉각

- 실제 트리거별 알림 전송 결과를 `alert_notifications`에 기록합니다.
- 비채널 상태도 synthetic channel로 기록할 수 있습니다. 예: `__cooldown__`, `__noise_suppressed__`, `__no_channel__`, `__dispatch__`
- DB 규칙은 `alert_cooldowns`로 영속 업무 냉각을 관리합니다.
- legacy JSON 규칙은 기존 worker 프로세스 내부 fingerprint를 계속 사용합니다.
- Web은 냉각 상태와 알림 결과를 읽기 전용으로 보여주며 냉각 정책 편집 UI는 제공하지 않습니다.

### P5 기술 지표 규칙

P5는 Alert API, Web 알림 센터, `src/services/alert_worker.py` 평가 체인에 일봉 기술 지표 규칙을 추가합니다.

| `alert_type` | 주요 파라미터 | 의미 |
| --- | --- | --- |
| `ma_price_cross` | `direction`, `window` | 종가가 MA를 상향/하향 돌파 |
| `rsi_threshold` | `direction`, `period`, `threshold` | RSI가 임계값을 상향/하향 돌파 |
| `macd_cross` | `direction`, `fast_period`, `slow_period`, `signal_period` | DIF/DEA 교차 |
| `kdj_cross` | `direction`, `period`, `k_period`, `d_period` | K/D 교차 |
| `cci_threshold` | `direction`, `period`, `threshold` | CCI가 임계값을 상향/하향 돌파 |

평가 기준은 다음과 같습니다.

- 첫 버전은 일봉 종가만 사용하고 분봉은 지원하지 않습니다.
- 최근 두 개의 완료된 일봉만 비교해 edge trigger를 판단합니다.
- 현재 level이 이미 조건을 만족하더라도 새로 돌파하지 않았으면 `not_triggered`로 봅니다.
- 장중 partial bar는 보수적으로 제외합니다.
- MA, RSI, MACD, KDJ, CCI는 `src/services/alert_indicators.py`에서 OHLCV를 정규화해 직접 계산합니다.
- 샘플 부족, 필수 컬럼 누락, 데이터 소스 오류는 `degraded` 또는 `failed`로 기록하고 알림을 보내지 않습니다.

P5 기술 지표는 Alert API/Web에서만 생성합니다. legacy `AGENT_EVENT_ALERT_RULES_JSON`에는 기술 지표 규칙을 추가하지 않습니다.

## 하지 않는 일

- legacy `AGENT_EVENT_ALERT_RULES_JSON`의 자동 마이그레이션
- 사용자의 알림 secret 또는 Webhook URL 노출
- 알림 센터가 꺼져 있을 때 기존 분석 흐름 변경
- 새 DSL 또는 별도 규칙 엔진 도입
- Market Light, 포트폴리오, watchlist 연동 규칙의 조기 구현

## 되돌림

- 문서만 바꾼 단계는 해당 PR을 revert하면 됩니다.
- API나 worker를 추가한 단계는 revert 후에도 SQLite에 이미 생성된 테이블과 데이터가 남을 수 있습니다.
- DB 데이터를 삭제해야 하는 경우 유지보수자가 보존 필요성을 확인한 뒤 수동으로 정리해야 합니다.
- P5 이후 생성된 기술 지표 규칙은 이전 코드에서 unsupported type으로 건너뛰어야 하며, legacy 세 규칙 실행을 막아서는 안 됩니다.
