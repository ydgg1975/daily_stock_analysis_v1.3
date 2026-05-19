# Analyze Issue

GitHub Issue를 분석해 실제 문제인지, 저장소 책임 범위인지, 우선순위가 어느 정도인지 판단합니다.

**Repository**: https://github.com/ZhuLinsen/daily_stock_analysis/issues

## Usage

```text
/analyze-issue <issue_number>
```

## Instructions

분석은 간결한 한국어로 작성하고, 저장소 루트의 `AGENTS.md`를 우선 따릅니다.

### 1. Issue 정보 확인

```bash
gh issue view <issue_number> --repo ZhuLinsen/daily_stock_analysis
gh issue view <issue_number> --repo ZhuLinsen/daily_stock_analysis --comments
```

버그라면 다음 정보가 있는지 확인합니다.

- 최신 버전에서 재현되는지
- commit hash 또는 기준 버전
- 실행 환경과 재현 절차
- 로그 또는 오류 메시지

### 2. 핵심 판단

다음 질문에 답합니다.

- 버전 기준이 명확한가
- 문제가 실제로 재현 가능하거나 충분히 타당한가
- 저장소 책임 범위 안에 있는가
- 즉시 처리할 가치가 있는가

### 3. 저장소 근거 확인

관련 코드, 설정, 테스트, 스크립트, 워크플로, 문서를 읽고 판단합니다.

API, 데이터 공급자 fallback, 리포트 생성, 알림, 인증, 데스크톱, 배포 흐름에 영향이 있으면 영향 범위를 명확히 적습니다.

### 4. 분석 문서 작성

분석 결과는 `.claude/reviews/issues/issue-<number>.md`에 저장합니다.

권장 필드:

- 버전 기준
- 타당성
- 저장소 Issue 여부
- 해결 난이도
- 결론
- 분류
- 우선순위
- 권장 조치
- 근거
- 영향 범위
- 위험과 롤백
- 초안 답변

## Allowed Auto-Actions

- Issue 상세와 댓글 확인
- 관련 코드와 문서 읽기
- 로컬 분석 문서 생성

## Actions Requiring Confirmation

- 라벨 추가 또는 수정
- Issue 댓글 작성
- Issue 닫기
- 실제 수정 작업 시작
