#!/usr/bin/env python3
"""GitHub Actions PR 리뷰 워크플로에서 사용하는 AI 코드 리뷰 스크립트."""

from __future__ import annotations

import json
import os
import subprocess
import traceback


MAX_DIFF_LENGTH = 18000
REVIEW_PATHS = [
    "*.py",
    "*.md",
    "README.md",
    "AGENTS.md",
    "docs/**",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "requirements.txt",
    ".github/requirements-ci.txt",
    "pyproject.toml",
    "setup.cfg",
    ".github/workflows/*.yml",
    ".github/scripts/*.py",
    "apps/dsa-web/**",
]


def run_git(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Git 명령 실행 실패: {' '.join(args)}")
        print(result.stderr.strip())
        return ""
    return result.stdout.strip()


def get_diff() -> tuple[str, bool]:
    """리뷰 대상 파일의 PR diff를 가져옵니다."""
    base_ref = os.environ.get("GITHUB_BASE_REF", "main")
    diff = run_git(["git", "diff", f"origin/{base_ref}...HEAD", "--", *REVIEW_PATHS])
    truncated = len(diff) > MAX_DIFF_LENGTH
    return diff[:MAX_DIFF_LENGTH], truncated


def get_changed_files() -> list[str]:
    """리뷰 대상 변경 파일 목록을 가져옵니다."""
    base_ref = os.environ.get("GITHUB_BASE_REF", "main")
    output = run_git(["git", "diff", "--name-only", f"origin/{base_ref}...HEAD", "--", *REVIEW_PATHS])
    return output.splitlines() if output else []


def get_pr_context() -> tuple[str, str]:
    """GitHub 이벤트 payload에서 PR 제목과 본문을 읽습니다."""
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        return "", ""
    try:
        with open(event_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        pr = payload.get("pull_request", {})
        return (pr.get("title") or "").strip(), (pr.get("body") or "").strip()
    except Exception:
        return "", ""


def classify_files(files: list[str]) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    py_files = [f for f in files if f.endswith(".py")]
    doc_files = [f for f in files if f.endswith(".md") or f.startswith("docs/") or f in ("README.md", "AGENTS.md")]
    frontend_files = [f for f in files if f.startswith("apps/dsa-web/") or f.endswith((".tsx", ".ts"))]
    ci_files = [f for f in files if f.startswith(".github/workflows/")]
    config_files = [
        f
        for f in files
        if f
        in (
            "requirements.txt",
            ".github/requirements-ci.txt",
            "pyproject.toml",
            "setup.cfg",
            ".github/PULL_REQUEST_TEMPLATE.md",
        )
    ]
    return py_files, doc_files, frontend_files, ci_files, config_files


def _build_ci_context() -> str:
    """워크플로에서 전달한 환경 변수를 바탕으로 CI 상태 문단을 만듭니다."""
    auto_check_result = os.environ.get("CI_AUTO_CHECK_RESULT", "")
    syntax_ok = os.environ.get("CI_SYNTAX_OK", "")
    has_py = os.environ.get("CI_HAS_PY_CHANGES", "false")

    if not auto_check_result:
        return """
## CI 확인 상태

- PR 워크플로의 CI 상태 정보를 찾지 못했습니다.
"""

    lines = ["\n## CI 확인 상태"]
    lines.append(f"- 정적 검사 결과: **{'통과' if auto_check_result == 'success' else '실패'}**")
    if has_py == "true":
        syntax_status = "통과" if syntax_ok == "true" else "실패" if syntax_ok == "false" else "미실행"
        lines.append(f"- Python 문법 검사(py_compile): **{syntax_status}**")
        lines.append("- Flake8 치명 오류 검사(E9/F63/F7/F82): 정적 검사 결과가 통과이면 함께 통과한 것으로 봅니다.")
    else:
        lines.append("- Python 파일: 변경 없음, 문법 검사는 건너뜀.")
    lines.append("")
    lines.append(
        "> 이 CI는 Python 문법과 치명 lint 오류를 확인합니다. 백엔드 변경이 있으면 "
        "`./scripts/ci_gate.sh` 실행 여부나 생략 사유를 검토 의견에 포함하세요."
    )
    lines.append("")
    return "\n".join(lines)


def build_prompt(diff_content: str, files: list[str], truncated: bool, pr_title: str, pr_body: str) -> str:
    """AGENTS.md 기준에 맞춘 AI 리뷰 프롬프트를 만듭니다."""
    truncate_notice = ""
    if truncated:
        truncate_notice = "\n\n> 참고: diff가 길어 일부만 포함되었습니다. 보이는 변경을 검토하고 불확실한 영역은 명확히 표시하세요.\n"

    py_files, doc_files, frontend_files, ci_files, config_files = classify_files(files)
    ci_context = _build_ci_context()
    file_list = "\n".join(f"- {path}" for path in files) or "- 없음"

    return f"""
당신은 Daily Stock Analysis 저장소의 PR 리뷰어입니다.

AGENTS.md 기준에 맞춰 정확성, 보안, 회귀 위험, 누락된 검증을 우선 검토하세요.
단순한 취향이나 스타일 지적은 피하고, 병합을 막아야 하는 문제와 실제 수정 가치가 있는 문제만 남기세요.
응답은 한국어로 작성하세요.

## PR 정보

- 제목: {pr_title or "(제목 없음)"}
- 본문:
{pr_body or "(본문 없음)"}

{ci_context}
## 변경 파일 요약

- 전체 검토 대상 파일 수: {len(files)}
- Python 파일: {len(py_files)}
- 문서 파일: {len(doc_files)}
- Web 프런트엔드 파일: {len(frontend_files)}
- CI/워크플로 파일: {len(ci_files)}
- 설정 파일: {len(config_files)}

### 파일 목록

{file_list}

## 리뷰 기준

1. 필요성: 변경이 PR 목적과 직접 관련되는지 판단하세요.
2. 정확성: 런타임 오류, ImportError, 깨진 문자열, API/Schema 호환성, 데이터 흐름 회귀를 우선 확인하세요.
3. 설정과 외부 의존성: 모델명, Base URL, 환경 변수, provider 의미가 바뀌면 근거와 이전 경로가 충분한지 확인하세요.
4. 테스트: 변경 범위에 맞는 로컬/CI 검증이 있는지 확인하세요.
5. 병합 판단: 차단 이슈가 있으면 명확히 표시하고, 없으면 남은 위험만 간결히 적으세요.

## 출력 형식

**리뷰 결론**
- 필요성:
- 관련 issue:
- PR 유형:
- 설명 완성도:
- 병합 가능 여부:

**주요 문제**
- 문제가 없으면 `차단 이슈 없음`이라고 쓰세요.
- 문제가 있으면 `[심각도] 파일:라인 - 설명` 형식으로 작성하세요.

**검증 의견**
- CI와 로컬 검증이 충분한지, 추가로 필요한 검증이 있는지 적으세요.

**되돌림/위험**
- 되돌릴 때 주의할 점이나 남은 위험을 적으세요.

{truncate_notice}
## Diff

```diff
{diff_content}
```
"""


def review_with_gemini(prompt: str) -> str | None:
    """Gemini API로 리뷰를 실행합니다."""
    api_key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_MODEL") or os.environ.get("GEMINI_MODEL_FALLBACK") or "gemini-2.5-flash"

    if not api_key:
        print("Gemini API 키가 설정되지 않았습니다. GitHub Secrets의 GEMINI_API_KEY를 확인하세요.")
        return None

    print(f"사용 모델: {model}")

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
        print(f"Gemini 리뷰가 성공했습니다: {model}")
        return response.text
    except ImportError as e:
        print(f"Gemini 의존성이 설치되지 않았습니다: {e}")
        print("   설치 명령: pip install google-genai")
        return None
    except Exception as e:
        print(f"Gemini 리뷰가 실패했습니다: {e}")
        traceback.print_exc()
        return None


def review_with_openai(prompt: str) -> str | None:
    """OpenAI 호환 API를 fallback으로 사용해 리뷰를 실행합니다."""
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        print("OpenAI API 키가 설정되지 않았습니다. GitHub Secrets의 OPENAI_API_KEY를 확인하세요.")
        return None

    print(f"Base URL: {base_url}")
    print(f"사용 모델: {model}")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3,
        )
        print(f"OpenAI 호환 리뷰가 성공했습니다: {model}")
        return response.choices[0].message.content
    except ImportError as e:
        print(f"OpenAI 의존성이 설치되지 않았습니다: {e}")
        print("   설치 명령: pip install openai")
        return None
    except Exception as e:
        print(f"OpenAI 호환 리뷰가 실패했습니다: {e}")
        traceback.print_exc()
        return None


def ai_review(diff_content: str, files: list[str], truncated: bool) -> str | None:
    """Gemini를 먼저 사용하고 실패하면 OpenAI 호환 API를 fallback으로 사용합니다."""
    pr_title, pr_body = get_pr_context()
    prompt = build_prompt(diff_content, files, truncated, pr_title, pr_body)

    result = review_with_gemini(prompt)
    if result:
        return result

    print("OpenAI 호환 fallback을 시도합니다...")
    result = review_with_openai(prompt)
    if result:
        return result

    return None


def main() -> None:
    diff, truncated = get_diff()
    files = get_changed_files()

    if not diff or not files:
        print("검토할 코드, 문서, 설정 변경이 없어 AI 리뷰를 건너뜁니다.")
        summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_file:
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write("## AI 코드 리뷰\n\n검토할 변경이 없습니다.\n")
        return

    print(f"리뷰 대상 파일: {files}")
    if truncated:
        print(f"Diff 내용이 {MAX_DIFF_LENGTH}자로 잘렸습니다.")

    review = ai_review(diff, files, truncated)
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    strict_mode = os.environ.get("AI_REVIEW_STRICT", "false").lower() == "true"

    if review:
        if summary_file:
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write(f"## AI 코드 리뷰\n\n{review}\n")

        with open("ai_review_result.txt", "w", encoding="utf-8") as f:
            f.write(review)

        print("AI 리뷰가 완료되었습니다.")
    else:
        print("사용 가능한 AI 리뷰 provider가 없습니다.")
        if summary_file:
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write("## AI 코드 리뷰\n\nAI 리뷰를 사용할 수 없습니다. provider 설정을 확인하세요.\n")
        if strict_mode:
            raise SystemExit("AI_REVIEW_STRICT=true and no AI review result is available")


if __name__ == "__main__":
    main()
