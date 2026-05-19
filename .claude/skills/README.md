# Repository Claude Skills

이 디렉터리는 저장소 협업용 skill을 보관합니다.

- 단일 규칙 원본은 저장소 루트의 `AGENTS.md`입니다.
- `CLAUDE.md`는 `AGENTS.md`를 가리키는 호환용 심볼릭 링크입니다.
- 이 디렉터리의 skill은 `AGENTS.md`와 충돌하지 않아야 합니다.
- `.claude/reviews/`는 로컬 분석 산출물이며 기본적으로 규칙 원본이 아닙니다.

다른 agent용 skill 디렉터리를 추가할 때는 먼저 단일 규칙 원본을 정하고, 수동 중복 관리 대신 스크립트나 미러링 방식으로 동기화하세요.
