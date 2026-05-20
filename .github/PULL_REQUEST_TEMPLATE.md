<!--
Korean contributors: 한국어로 작성해도 됩니다.
English contributors: please fill in English.
-->

## PR Type

- [ ] fix
- [ ] feat
- [ ] refactor
- [ ] docs
- [ ] chore
- [ ] test

## Background And Problem

현재 문제, 영향 범위, 재현 또는 발생 조건을 설명하세요.
Describe the problem, its impact, and what triggers it.

## Scope Of Change

이 PR에서 변경한 모듈과 파일 범위를 적어 주세요.
List the modules and files changed in this PR.

## Issue Link

Fill in one of:
- `Fixes #<issue_number>`
- `Refs #<issue_number>`
- If there is no issue, explain the motivation and acceptance criteria.

## Verification Commands And Results

실제로 실행한 명령과 핵심 결과를 적어 주세요. 단순히 "tested"라고만 쓰지 마세요.
Paste the commands you actually ran and their key output.

```bash
# example
./scripts/ci_gate.sh
python -m pytest -m "not network"
```

Key output and conclusion:

## Compatibility And Risk

호환성 영향과 잠재 위험을 설명하세요. 해당 없음이면 `None`이라고 적어 주세요.
Describe compatibility impact and potential risks.

- If this PR changes third-party model/API compatibility, request parameters, routing prefixes, or provider fallback behavior, include an official source link or announcement and clarify whether the rule is permanent, runtime-specific, or a temporary compatibility workaround.
- If this PR depends on a specific runtime or pinned dependency window, state the compatibility window you verified and which code paths were covered.
- If this PR touches runtime config save, cleanup, migration, or backfill logic, explicitly describe whether existing config is rewritten, cleared, migrated, or left intact, and how users can restore the previous behavior.

## Rollback Plan

실행 가능한 되돌리기 방법을 최소 하나 적어 주세요.
Provide at least one actionable rollback step.

For compatibility fixes, include the minimal rollback path, for example `revert this PR`, and whether any additional config or data rollback is required.

## EXTRACT_PROMPT Change (if applicable)

If this PR changes `EXTRACT_PROMPT` in `src/services/image_stock_extractor.py`, paste the full updated prompt here:

<details>
<summary>Expand: Full EXTRACT_PROMPT</summary>

```
(paste full prompt here)
```

</details>

## Checklist

- [ ] This PR has a clear motivation and value.
- [ ] Reproducible verification commands and results are included.
- [ ] Compatibility and risk have been assessed.
- [ ] A rollback plan is provided.
- [ ] If user-visible changes are included, relevant docs and `docs/CHANGELOG.md` are updated.
- [ ] `README.md` is updated only for homepage-level changes, with details kept in `docs/*.md`.
