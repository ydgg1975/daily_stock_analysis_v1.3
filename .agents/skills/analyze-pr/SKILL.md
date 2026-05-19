# Analyze PR

GitHub Pull Request를 검토해 필요성, 설명 완성도, 검증 근거, 주요 위험, 병합 가능성을 판단합니다.

**Repository**: https://github.com/ZhuLinsen/daily_stock_analysis/pulls

## Usage

```text
/analyze-pr <pr_number>
```

## Instructions

분석은 간결한 한국어로 작성하고, `AGENTS.md`와 `.github/PULL_REQUEST_TEMPLATE.md`를 우선 따릅니다.

### 1. PR 정보 확인

```bash
gh pr view <pr_number> --repo ZhuLinsen/daily_stock_analysis
gh pr view <pr_number> --repo ZhuLinsen/daily_stock_analysis --comments
gh pr checks <pr_number> --repo ZhuLinsen/daily_stock_analysis
gh pr diff <pr_number> --repo ZhuLinsen/daily_stock_analysis
```

실패한 CI가 있으면 먼저 실패 로그를 확인합니다.

```bash
gh run view <run_id> --log-failed
```

### 2. 제목과 설명 확인

PR 제목은 `<type>: <change summary>` 형식을 권장합니다. 예: `fix: 대시보드 분석 이력 누락 수정`

권장 type:

- `fix`
- `feat`
- `refactor`
- `docs`
- `chore`
- `test`
- `ci`

`[codex]`, `codex`, `autocode`, `copilot` 같은 도구 출처 접두사는 권장하지 않습니다.

### 3. 검증 근거 우선 확인

CI 결과, PR diff, 기존 테스트와 워크플로 로그를 우선 사용합니다. CI가 변경 범위를 충분히 덮지 못하거나 회귀 위험이 있으면 최소한의 로컬 검증을 보충합니다.

### 4. 리뷰 관점

중점 확인 항목:

- 실제 문제를 해결하는가
- 무관한 변경이 섞이지 않았는가
- API, Schema, Web, Desktop 호환성을 깨지 않는가
- fallback, 알림, 배포 흐름에 회귀가 없는가
- 설정 의미가 바뀌었다면 문서와 `.env.example`이 갱신되었는가

### 5. 분석 문서 작성

분석 결과는 `.claude/reviews/prs/pr-<number>.md`에 저장합니다.

권장 섹션:

- Findings
- Summary
- Validation Evidence
- Compatibility And Risk
- Draft Review Comment

## Allowed Auto-Actions

- PR 메타데이터, diff, 댓글, CI 상태 확인
- 관련 코드와 문서 읽기
- 필요한 최소 로컬 검증
- 로컬 분석 문서 생성

## Actions Requiring Confirmation

- PR 댓글 게시
- Approve
- Request changes
- Merge
- PR 닫기
