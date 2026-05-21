# 기여 가이드

daily_stock_analysis에 관심을 가져주셔서 감사합니다. 버그 제보, 기능 제안, 문서 개선, 코드 기여를 모두 환영합니다.

## 버그 제보

1. 먼저 [Issues](https://github.com/robot0971-art/daily_stock_analysis/issues)에서 같은 문제가 이미 등록되어 있는지 확인합니다.
2. Bug Report 템플릿을 사용해 새 Issue를 작성합니다.
3. 재현 절차, 실행 환경, 로그, 기대 결과와 실제 결과를 함께 적습니다.

## 기능 제안

1. 기존 Issues와 Discussions에서 같은 제안이 있는지 확인합니다.
2. Feature Request 템플릿을 사용해 새 Issue를 작성합니다.
3. 사용 시나리오, 기대 동작, 우선순위, 대안이 있으면 함께 설명합니다.

## 개발 환경

```bash
git clone https://github.com/robot0971-art/daily_stock_analysis.git
cd daily_stock_analysis

python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
cp .env.example .env
```

## 작업 흐름

1. 저장소를 fork합니다.
2. 작업 브랜치를 만듭니다: `git checkout -b feature/your-feature`
3. 변경 사항을 커밋합니다: `git commit -m "feat: add some feature"`
4. 브랜치를 push합니다: `git push origin feature/your-feature`
5. Pull Request를 생성합니다.

## 커밋 규칙

[Conventional Commits](https://www.conventionalcommits.org/) 형식을 권장합니다.

```text
feat: 새 기능
fix: 버그 수정
docs: 문서 변경
style: 동작에 영향이 없는 코드 스타일 변경
refactor: 리팩터링
perf: 성능 개선
test: 테스트 변경
chore: 빌드, 도구, 관리 작업
```

예시:

```text
feat: add Telegram notification channel
fix: handle 429 retry backoff
docs: update WebUI deployment guide
```

## 코드 기준

- Python 코드는 PEP 8을 따릅니다.
- 새 기능은 가능한 범위에서 테스트와 문서를 함께 갱신합니다.
- 설정, API, 보고서 구조, 알림 동작을 바꾸면 호환성 영향을 PR 설명에 적습니다.
- 비밀키, 계정, 로컬 경로, 환경별 값은 하드코딩하지 않습니다.

## CI 확인

PR에는 주요 검사가 자동으로 실행됩니다.

| 검사 | 설명 | 차단 여부 |
| --- | --- | --- |
| backend-gate | `scripts/ci_gate.sh` 실행 | 예 |
| docker-build | Docker 이미지 빌드와 핵심 모듈 import smoke | 예 |
| web-gate | 프런트엔드 변경 시 `npm run lint`와 `npm run build` 실행 | 예 |
| network-smoke | 네트워크 의존 smoke 테스트 | 아니오 |

로컬에서 가능한 기본 검증:

```bash
pip install -r requirements.txt
pip install flake8 pytest
./scripts/ci_gate.sh

cd apps/dsa-web
npm ci
npm run lint
npm run build
```

## 우선 기여 영역

- 알림 채널과 전송 안정성 개선
- LLM provider 설정과 fallback 품질 개선
- 데이터 소스 fallback과 필드 표준화 개선
- WebUI와 데스크톱 UX 개선
- 문서 현지화와 문제 해결 가이드 보강

## 질문

궁금한 점은 Issue 또는 Discussion으로 남겨주세요. 작은 문서 수정부터 큰 기능 제안까지 모두 도움이 됩니다.
