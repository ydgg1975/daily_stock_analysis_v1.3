# AGENTS.md

이 문서는 이 저장소의 기본 개발 흐름을 정합니다. 목표는 반복 확인과 재작업을 줄이고, 변경 사항이 현재 프로젝트 구조와 일관되게 유지되도록 하는 것입니다.

이 문서가 저장소의 스크립트, 워크플로, 실제 코드 상태와 맞지 않으면 실행 가능한 실제 내용을 우선합니다. 관련 변경을 할 때 문서도 함께 바로잡아 규칙이 계속 어긋나지 않게 합니다.

## 1. 필수 규칙

- 기존 디렉터리 경계를 따릅니다.
  - 백엔드 로직은 우선 `src/`, `data_provider/`, `api/`, `bot/`에 둡니다.
  - Web 프런트엔드 변경은 `apps/dsa-web/`에서 합니다.
  - 데스크톱 변경은 `apps/dsa-desktop/`에서 합니다.
  - 배포와 파이프라인 변경은 `scripts/`, `.github/workflows/`, `docker/`에서 합니다.
- 명확한 확인 없이 `git commit`, `git tag`, `git push`를 실행하지 않습니다.
- commit message는 영어로 작성하고 `Co-Authored-By`를 추가하지 않습니다.
- 키, 계정, 경로, 모델명, 포트, 환경별 분기 로직을 하드코딩하지 않습니다.
- 기존 모듈, 설정 진입점, 스크립트, 테스트를 우선 재사용하고 병렬 구현을 새로 만들지 않습니다.
- 기본값은 안정성입니다. 현재 작업에 직접 필요하지 않은 리팩터링, 추상화, 인프라 이전은 자제합니다.
- 새 설정 항목을 추가하면 `.env.example`과 관련 문서를 함께 업데이트합니다.
- 사용자에게 보이는 기능, CLI/API 동작, 배포 방식, 알림 방식, 보고서 구조가 바뀌면 관련 문서와 `docs/CHANGELOG.md`를 함께 업데이트합니다.
- `docs/CHANGELOG.md`의 `[Unreleased]` 구간은 평평한 형식을 사용합니다. 각 항목은 독립된 한 줄이며 형식은 `- [유형] 설명`입니다. 유형은 `신기능`/`개선`/`수정`/`문서`/`테스트`/`chore` 중 하나를 사용합니다. `[Unreleased]` 안에 `###` 분류 제목을 추가하지 않습니다.
- `README.md`는 프로젝트 소개, 핵심 기능 요약, 빠른 시작, 주요 진입점, 후원/협업 같은 첫 화면 수준 정보에만 사용합니다. 꼭 필요하지 않으면 README를 키우지 않습니다.
- 세부 동작, 페이지 상호작용, 주제별 설정, 문제 해결, 필드 계약, 구현 의미와 경계 조건은 대응하는 `docs/*.md`나 주제 문서에 우선 작성합니다.
- 한 언어 문서를 바꾸면 대응 문서 동기화 필요 여부를 검토합니다. 동기화하지 않았다면 전달 설명에 이유를 적습니다.
- 주석, docstring, 로그 문구는 명확성과 정확성을 우선합니다. 영어를 강제하지 않지만 파일 문맥과 일관되게 작성합니다.

## 1.1 PR 제목 규칙

- PR 제목은 `<type>: <change>` 형식을 권장합니다. 예: `fix: restore market analysis history`.
- 우선 type은 `fix`/`feat`/`refactor`/`docs`/`chore`/`test`/`ci`입니다.
- 제목은 실제 변경 내용을 설명해야 하며 `[codex]`, `codex`, `autocode`, `copilot` 같은 도구나 에이전트 출처 접두사는 붙이지 않는 것을 권장합니다.
- 이 규칙은 협업 가독성과 일관성을 위한 권장 사항이며 단독으로 리뷰 차단 사유가 되어서는 안 됩니다.

## 2. AI 협업 자산 관리

- `AGENTS.md`는 저장소 내 AI 협업 규칙의 단일 기준입니다.
- `CLAUDE.md`는 Claude 생태계 호환을 위해 `AGENTS.md`를 가리키는 심볼릭 링크여야 합니다.
- `.github/copilot-instructions.md`와 `.github/instructions/*.instructions.md`는 GitHub Copilot / Coding Agent용 미러 또는 계층 보충 문서입니다. 충돌하면 `AGENTS.md`를 우선합니다.
- 저장소 협업 skill은 `.claude/skills/`에 둡니다. 분석 산출물은 `.claude/reviews/`에 두며 기본적으로 로컬 산출물로 봅니다.
- 루트 `SKILL.md`와 `docs/openclaw-skill-integration.md`는 제품 또는 외부 통합 설명이며 저장소 협업 규칙의 기준이 아닙니다.
- 나중에 `.agents/skills/`나 다른 agent 전용 디렉터리를 추가하려면 먼저 단일 기준을 명확히 하고 스크립트나 미러링으로 동기화합니다. 같은 의미의 여러 문서를 손으로 오래 유지하지 않습니다.
- AI 협업 관리 자산을 수정하면 다음을 실행합니다.

```bash
python scripts/check_ai_assets.py
```

## 3. 저장소 개요

- 프로젝트 성격: 주식 지능형 분석 시스템으로 A주, 홍콩 주식, 미국 주식을 다룹니다.
- 주요 흐름: 데이터 수집 -> 기술 분석/뉴스 검색 -> LLM 분석 -> 보고서 생성 -> 알림 발송.
- 주요 진입점:
  - `main.py`: 분석 작업 메인 진입점
  - `server.py`: FastAPI 서비스 진입점
  - `apps/dsa-web/`: Web 프런트엔드
  - `apps/dsa-desktop/`: Electron 데스크톱
  - `.github/workflows/`: CI, 릴리스, 일일 작업
- 핵심 책임:
  - `src/core/`: 주요 흐름 오케스트레이션
  - `src/services/`: 비즈니스 서비스 계층
  - `src/repositories/`: 데이터 접근 계층
  - `src/reports/`: 보고서 생성
  - `src/schemas/`: Schema와 데이터 구조
  - `data_provider/`: 다중 데이터 소스 어댑터와 fallback
  - `api/`: FastAPI API
  - `bot/`: 봇 연동
  - `scripts/`: 로컬 스크립트
  - `.github/scripts/`: GitHub 자동화 스크립트
  - `tests/`: pytest 테스트
  - `docs/`: 문서와 설명

## 4. 자주 쓰는 명령

### 애플리케이션 실행

```bash
python main.py
python main.py --debug
python main.py --dry-run
python main.py --stocks 600519,hk00700,AAPL
python main.py --market-review
python main.py --schedule
python main.py --serve
python main.py --serve-only
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### 백엔드 검증

```bash
pip install -r requirements.txt
pip install flake8 pytest
./scripts/ci_gate.sh
python -m pytest -m "not network"
python -m py_compile <changed_python_files>
```

### Web / Desktop

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build

cd ../dsa-desktop
npm install
npm run build
```

### PR / CI 증거 확인

```bash
gh pr view <pr_number>
gh pr checks <pr_number>
gh run view <run_id> --log-failed
```

## 5. 기본 작업 흐름

1. 작업 유형을 먼저 판단합니다: `fix / feat / refactor / docs / chore / test / review`.
2. 기존 구현, 설정, 테스트, 스크립트, 워크플로, 문서를 먼저 읽은 뒤 수정합니다.
3. 변경 경계를 식별합니다: 백엔드 / API / Web / Desktop / Workflow / Docs / AI 협업 자산.
4. 고위험 영역인지 먼저 판단합니다: 설정 의미, API / Schema, 데이터 소스 fallback, 보고서 구조, 인증, 스케줄링, 릴리스 흐름, 데스크톱 시작 흐름.
5. 현재 작업과 직접 관련된 최소 변경만 수행합니다.
6. 문서, 스크립트, 워크플로 설명이 실제와 다르면 실제 코드와 워크플로를 우선 신뢰한 뒤 문서 수정 여부를 결정합니다.
7. 수정 후 아래 검증 매트릭스에 따라 확인합니다.
8. 최종 전달에는 기본적으로 다음을 포함합니다: 변경 내용, 변경 이유, 검증 상황, 미검증 항목, 위험점, 되돌리는 방법.

## 6. 검증 매트릭스

### CI 범위

현재 저장소 CI의 주요 항목은 다음과 같습니다.

| 검사 | 출처 | 설명 | 차단 여부 |
| --- | --- | --- | --- |
| `ai-governance` | `.github/workflows/ci.yml` | `AGENTS.md` / `CLAUDE.md` / `.github` 지침 / `.claude/skills` 관계 확인 | 예 |
| `backend-gate` | `.github/workflows/ci.yml` | `./scripts/ci_gate.sh` 실행 | 예 |
| `docker-build` | `.github/workflows/ci.yml` | Docker 빌드와 핵심 모듈 import smoke | 예 |
| `web-gate` | `.github/workflows/ci.yml` | 프런트엔드 변경 시 `npm run lint` + `npm run build` 실행 | 예 |
| `network-smoke` | `.github/workflows/network-smoke.yml` | `pytest -m network` + `scripts/test.sh quick` | 아니오 |
| `pr-review` | `.github/workflows/pr-review.yml` | PR 정적 검사 + AI 리뷰 + 자동 라벨 | 아니오 |

PR에 해당 CI 결과가 있으면 그 결론을 인용할 수 있습니다. CI가 변경 범위를 덮지 못하거나 로컬과 CI 차이가 크면 로컬 검증과 부족한 부분을 함께 설명합니다.

### 변경 범위별 검증

- Python 백엔드 변경:
  - 대상: `main.py`, `src/`, `data_provider/`, `api/`, `bot/`, `tests/`
  - 우선 실행: `./scripts/ci_gate.sh`
  - 최소 요구: `python -m py_compile <changed_python_files>`
  - API, 작업 오케스트레이션, 보고서 생성, 알림 발송, 데이터 소스 fallback, 인증, 스케줄링에 영향이 있으면 해당 경로 검증 여부를 전달 설명에 적습니다.

- Web 프런트엔드 변경:
  - 대상: `apps/dsa-web/`
  - 기본 실행: `cd apps/dsa-web && npm ci && npm run lint && npm run build`
  - API 연동, 라우팅, 상태 관리, Markdown/차트 렌더링, 인증 상태에 영향이 있으면 연동 범위와 미검증 위험을 명확히 적습니다.

- 데스크톱 변경:
  - 대상: `apps/dsa-desktop/`, `scripts/run-desktop.ps1`, `scripts/build-desktop*.ps1`, `scripts/build-*.sh`, `docs/desktop-package.md`
  - 기본 실행: Web 빌드 후 데스크톱 빌드
  - 플랫폼 제약으로 완전 검증하지 못하면 Web 산출물, Electron 빌드, Release 워크플로 영향 검증 여부를 명확히 적습니다.

- API / Schema / 인증 연동 변경:
  - 대상: `api/**`, `src/schemas/**`, `src/services/**`, `apps/dsa-web/**`, `apps/dsa-desktop/**`
  - 대응 백엔드 검증과 영향을 받는 클라이언트 빌드 검증을 최소한 수행합니다.
  - 로그인, Cookie, 세션, 폴링 상태, 필드 증감, enum 변경이 있으면 호환성 영향을 명확히 적습니다.

- 문서와 관리 파일 변경:
  - 대상: `README.md`, `docs/**`, `AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/**`, `.claude/skills/**`
  - 코드 테스트는 필수가 아닙니다.
  - 명령, 설정 항목, 파일명, 워크플로 이름이 실제 저장소와 맞는지 확인합니다.
  - AI 협업 관리 자산을 바꾸면 `python scripts/check_ai_assets.py`를 실행합니다.

- 워크플로 / 스크립트 / Docker 변경:
  - 대상: `.github/**`, `scripts/**`, `docker/**`
  - 변경 범위에 가장 가까운 로컬 검증을 실행합니다.
  - 어떤 파이프라인, 릴리스 경로, 배포 경로에 영향이 있는지 전달합니다.
  - Docker / GitHub Actions 관련 검증을 실행하지 못했다면 이유와 잠재 위험을 적습니다.

- 네트워크나 외부 의존성 관련 변경:
  - 먼저 오프라인 또는 결정적 검사를 실행합니다.
  - timeout, retry, fallback, 예외 문구, degraded path가 유지되는지 확인합니다.
  - 온라인 검증을 하지 못하면 이유를 명확히 적습니다.

## 7. 안정성 보호선

- 설정과 실행 진입점:
  - `.env` 의미, 기본값, CLI 인자, 서비스 시작 방식, 스케줄링 의미를 바꾸면 로컬 실행, Docker, GitHub Actions, API, Web, Desktop 영향을 함께 검토합니다.
  - 새 설정은 가능하면 “설정하지 않아도 동작하고, 설정하면 기능이 강화되는” 방식으로 둡니다.

- 데이터 소스와 fallback:
  - `data_provider/`를 바꾸면 데이터 소스 우선순위, 실패 시 fallback, 필드 표준화, 캐시, timeout 전략을 확인합니다.
  - 요구가 명시되지 않았다면 단일 데이터 소스 실패가 전체 분석 흐름을 중단시키지 않아야 합니다.

- API / Web / Desktop 호환:
  - API, Schema, 인증, 보고서 payload를 바꾸면 백엔드, Web, Desktop 호환성을 함께 확인합니다.
  - 기본적으로 필드 추가, 기존 필드 유지, 호환 계층 제공을 우선합니다.

- 보고서 / Prompt / 알림:
  - 보고서 구조, Prompt, 추출기, 알림 템플릿, 봇 흐름을 바꾸면 상위 입력과 하위 소비자가 여전히 호환되는지 확인합니다.
  - 요구가 명시되지 않았다면 단일 알림 채널 실패가 전체 분석 흐름을 중단시키지 않아야 합니다.
  - `src/services/image_stock_extractor.py`의 `EXTRACT_PROMPT`를 바꾸면 PR 설명에 최신 prompt 전체를 첨부합니다.

- 워크플로 / 릴리스 / 패키징:
  - 자동 tag, Release, Docker 게시, 일일 분석, 데스크톱 패키징 흐름을 바꾸면 트리거 조건, 산출물 경로, 권한 경계, 되돌리는 방법을 검토합니다.
  - 자동 tag는 기본적으로 opt-in입니다. commit title에 `#patch`, `#minor`, `#major`가 있을 때만 버전 업데이트가 동작해야 합니다.

## 8. Issue / PR / Skill 작업 흐름

- 저장소에는 다음 skill이 있습니다.
  - `.claude/skills/analyze-issue/SKILL.md`
  - `.claude/skills/analyze-pr/SKILL.md`
  - `.claude/skills/fix-issue/SKILL.md`
- 작업이 명확히 issue 분석, PR 리뷰, issue 수정이라면 대응 skill을 우선 사용하고 산출물은 `.claude/reviews/`에 저장합니다.
- skill의 명령, 템플릿, 검증 순서, 전달 구조는 `AGENTS.md`와 일치해야 합니다.
- skill은 기본적으로 CI / 워크플로 증거를 먼저 읽고 로컬 검증 보강 여부를 결정합니다.
- skill은 기본적으로 `git pull`, `git push`, `git tag`, `gh pr create`처럼 원격이나 현재 브랜치 상태를 바꾸는 작업을 실행하지 않습니다. 이런 작업은 사용자 확인이 필요합니다.
- PR 리뷰 기본 순서:
  1. 필요성
  2. 관련성
  3. 제목 제안
  4. 설명 완성도
  5. 검증 증거
  6. 구현 정확성
  7. 병합 판단
- `fix` PR은 원문제, 원인, 수정점, 회귀 위험을 설명해야 합니다.
- 병합 차단 조건:
  - 정확성 또는 보안 문제
  - 차단형 CI 실패
  - PR 설명과 실제 변경 내용의 실질적 불일치
  - 되돌리는 방법 누락

## 9. 전달과 릴리스

- 기본 전달 구조:
  - 변경 내용
  - 변경 이유
  - 검증 상황
  - 미검증 항목
  - 위험점
  - 되돌리는 방법
- 문서 작업만 했다면 `Docs only, tests not run`이라고 쓸 수 있습니다. 그래도 명령과 파일명을 실제 저장소와 대조했는지 설명합니다.
- 자동 tag는 commit title에 `#patch`, `#minor`, `#major`가 있을 때만 트리거합니다.
- 수동 tag는 annotated tag를 사용해야 합니다.
- 사용자에게 보이는 변경은 PR로 병합하고 label과 검증 설명을 보강하는 것을 우선합니다.
