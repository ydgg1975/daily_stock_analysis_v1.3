# 기여 가이드

Daily Stock Analysis에 기여할 때는 저장소 루트의 `AGENTS.md`를 우선 따릅니다.

## Issue 제안

새 Issue를 만들기 전에 기존 Issue를 먼저 검색하세요.

버그 신고에는 다음 정보를 포함하면 좋습니다.

- 사용 버전 또는 commit hash
- 실행 환경
- 재현 절차
- 기대 결과와 실제 결과
- 로그 또는 오류 메시지

## 기능 제안

기능 제안에는 사용 시나리오와 기대 효과를 적어 주세요.

## 개발 환경

```bash
pip install -r requirements.txt
pip install flake8 pytest
```

Web 변경 시:

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

## 커밋 메시지

영어 커밋 메시지를 사용합니다.

권장 type:

- `feat`: new feature
- `fix`: bug fix
- `docs`: documentation
- `refactor`: refactoring
- `test`: tests
- `chore`: maintenance
- `ci`: CI changes

예시:

```text
fix: restore missing dashboard history
```

## Pull Request

PR에는 다음을 포함하세요.

- 변경 배경
- 변경 범위
- 검증 명령과 결과
- 호환성 영향
- 위험과 롤백 방법

사용자에게 보이는 동작, API, CLI, 배포, 알림, 리포트 구조가 바뀌면 관련 문서와 `docs/CHANGELOG.md`를 함께 갱신합니다.
