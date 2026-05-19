# Fix Issue

Issue 분석 결과를 바탕으로 저장소 규칙에 맞게 최소 수정, 검증, 위험과 롤백 설명을 수행합니다.

**Repository**: https://github.com/ZhuLinsen/daily_stock_analysis
**Rule source**: `AGENTS.md`

## Usage

```text
/fix-issue <issue_number>
```

## Prerequisites

가능하면 먼저 `/analyze-issue <issue_number>`를 완료해 문제가 타당하고 범위가 명확한지 확인합니다.

## Instructions

### 1. 분석 기준 확인

`.claude/reviews/issues/issue-<number>.md`가 있으면 먼저 읽습니다. 없으면 이번 수정 안에서 최소 분석을 보충합니다.

### 2. 안전한 작업 방식

- 현재 작업 트리 기준으로 최소 관련 변경만 수행합니다.
- 기본적으로 `git pull`을 실행하지 않습니다.
- 사용자의 명시 요청 없이 브랜치를 바꾸거나 사용자 변경을 되돌리지 않습니다.
- 브랜치 생성, commit, push, PR 생성은 사용자 확인 후 진행합니다.

### 3. 수정 구현

- 기존 모듈, 설정 진입점, 스크립트, 테스트를 우선 재사용합니다.
- 기본 동작은 가능한 한 하위 호환을 유지합니다.
- fallback, 알림, 보고서 구조, 배포 흐름을 깨지 않도록 확인합니다.
- 사용자 표시 동작, 설정 의미, CLI/API, 배포, 알림, 리포트 구조가 바뀌면 관련 문서와 `docs/CHANGELOG.md`를 갱신합니다.

`docs/CHANGELOG.md`의 `[Unreleased]`에는 한 줄 형식으로 추가합니다.

```markdown
- [수정] 변경 내용을 간결히 설명합니다.
```

### 4. 검증

변경 범위에 맞는 가장 가까운 검증을 실행합니다.

- 백엔드: `./scripts/ci_gate.sh` 또는 `python -m py_compile <changed_python_files>`
- Web: `cd apps/dsa-web && npm ci && npm run lint && npm run build`
- Desktop: Web 빌드 후 Electron 빌드
- AI 협업 자산: `python scripts/check_ai_assets.py`

검증하지 못한 항목은 이유와 위험을 기록합니다.

### 5. 분석 문서 갱신

수정 후 `.claude/reviews/issues/issue-<number>.md`에 구현 내용, 검증, 위험, 롤백을 보충합니다.

## Allowed Auto-Actions

- 코드와 문서 분석
- 현재 작업과 직접 관련된 최소 수정
- 비파괴 로컬 검증 실행
- 로컬 분석 문서 갱신

## Actions Requiring Confirmation

- 브랜치 생성 또는 전환
- `git commit`
- `git push`
- PR 생성
- Issue 댓글 작성 또는 닫기
