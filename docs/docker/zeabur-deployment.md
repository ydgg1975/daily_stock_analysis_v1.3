# Zeabur 배포 가이드

Zeabur에서 Daily Stock Analysis를 실행하는 기본 절차입니다.

## 1. 프로젝트 생성

Zeabur에서 GitHub 저장소를 연결하고 새 서비스를 생성합니다.

## 2. 빌드 설정

자동 감지가 실패하면 Docker 기반 배포를 선택합니다.

## 3. 시작 명령

| 모드 | 명령 |
| --- | --- |
| 예약 분석 | `python main.py --schedule` |
| Web/API | `python main.py --serve-only` |
| Web/API + 1회 분석 | `python main.py --serve` |
| 시장 요약 | `python main.py --market-review` |

## 4. 환경 변수

필수 또는 권장 변수:

- `STOCK_LIST`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- 알림 채널별 Webhook 또는 Token

## 5. 영구 저장소

데이터 유지를 위해 다음 경로를 볼륨으로 연결하는 것을 권장합니다.

- `/app/data`
- `/app/logs`
- `/app/reports`

## 6. 확인 항목

- 서비스 로그
- `/api/health`
- Web UI 접속
- 종목 분석 실행
- 알림 전송

## 7. 문제 해결

- 포트가 Zeabur 설정과 맞는지 확인합니다.
- 환경 변수가 누락되지 않았는지 확인합니다.
- 볼륨 경로가 올바른지 확인합니다.
- 모델 API 호출이 실패하면 키, 모델명, quota를 확인합니다.
