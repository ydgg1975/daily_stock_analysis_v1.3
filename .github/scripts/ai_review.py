#!/usr/bin/env python3
"""
AI code review script used by GitHub Actions PR Review workflow.
"""
import json
import os
import subprocess
import traceback


MAX_DIFF_LENGTH = 18000
REVIEW_PATHS = [
    '*.py',
    '*.md',
    'README.md',
    'AGENTS.md',
    'docs/**',
    '.github/PULL_REQUEST_TEMPLATE.md',
    'requirements.txt',
    '.github/requirements-ci.txt',
    'pyproject.toml',
    'setup.cfg',
    '.github/workflows/*.yml',
    '.github/scripts/*.py',
    'apps/dsa-web/**',
]


def run_git(args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"⚠️ git command failed: {' '.join(args)}")
        print(result.stderr.strip())
        return ''
    return result.stdout.strip()


def get_diff():
    """Get PR diff content for review-relevant files."""
    base_ref = os.environ.get('GITHUB_BASE_REF', 'main')
    diff = run_git(['git', 'diff', f'origin/{base_ref}...HEAD', '--', *REVIEW_PATHS])
    truncated = len(diff) > MAX_DIFF_LENGTH
    return diff[:MAX_DIFF_LENGTH], truncated


def get_changed_files():
    """Get changed file list for review-relevant files."""
    base_ref = os.environ.get('GITHUB_BASE_REF', 'main')
    output = run_git(['git', 'diff', '--name-only', f'origin/{base_ref}...HEAD', '--', *REVIEW_PATHS])
    return output.split('\n') if output else []


def get_pr_context():
    """Read PR title/body from GitHub event payload when available."""
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    if not event_path or not os.path.exists(event_path):
        return '', ''
    try:
        with open(event_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        pr = payload.get('pull_request', {})
        return (pr.get('title') or '').strip(), (pr.get('body') or '').strip()
    except Exception:
        return '', ''


def classify_files(files):
    py_files = [f for f in files if f.endswith('.py')]
    doc_files = [f for f in files if f.endswith('.md') or f.startswith('docs/') or f in ('README.md', 'AGENTS.md')]
    frontend_files = [f for f in files if f.startswith('apps/dsa-web/') or f.endswith(('.tsx', '.ts'))]
    ci_files = [f for f in files if f.startswith('.github/workflows/')]
    config_files = [
        f for f in files if f in ('requirements.txt', '.github/requirements-ci.txt', 'pyproject.toml', 'setup.cfg', '.github/PULL_REQUEST_TEMPLATE.md')
    ]
    return py_files, doc_files, frontend_files, ci_files, config_files


def _build_ci_context():
    """Build CI context section from environment variables set by the workflow."""
    auto_check_result = os.environ.get('CI_AUTO_CHECK_RESULT', '')
    syntax_ok = os.environ.get('CI_SYNTAX_OK', '')
    has_py = os.environ.get('CI_HAS_PY_CHANGES', 'false')

    if not auto_check_result:
        return """
Daily Stock Analysis - Ai Review
"""

    lines = ["\n## CI jianchazhuangtai（laizibenci PR dezidonghualiushuixian）"]
    lines.append(f"- jingtaijianchazongtijieguo: **{'✅ tongguo' if auto_check_result == 'success' else '❌ shibai'}**")
    if has_py == 'true':
        lines.append(f"- Python yufajiancha (py_compile): **{'✅ tongguo' if syntax_ok == 'true' else '❌ shibai' if syntax_ok == 'false' else '⏭️ weizhixing'}**")
        lines.append("- Flake8 yanzhongcuowujiancha (E9/F63/F7/F82): **✅ tongguo**（ruoweitongguozejingtaijianchazongtihuishibai）")
    else:
        lines.append("- Python wenjian: wubiangeng，yufajianchayitiaoguo")
    lines.append("")
    lines.append("> yishang CI jinfugaiyufazhengquexing（py_compile）hezhiming lint cuowu（flake8 E9/F63/F7/F82）。`./scripts/ci_gate.sh` **weibaohanzai CI zhong**：dui Python houduangaidong，ruo PR miaoshuweishuominggai gate shifouzhixing（huogeichutiaoguoyuanyin），yingzaijianyixiangzhongzhuming，danbugouchengzuduan。yufa/flake8 yitongguozewuxuchongfutieduiyingbendishuchu。")
    lines.append("")
    return '\n'.join(lines)


def build_prompt(diff_content, files, truncated, pr_title, pr_body):
    """Build AI review prompt aligned with AGENTS.md requirements."""
    truncate_notice = ''
    if truncated:
        truncate_notice = "\n\n> ⚠️ zhuyi：diff guochangyijieduan，qingjiyukejianneirongshenchabingbiaozhubuquedingdian。\n"

    py_files, doc_files, frontend_files, ci_files, config_files = classify_files(files)
    ci_context = _build_ci_context()
    return f"""
Daily Stock Analysis - Ai Review
"""


def review_with_gemini(prompt):
    """Run review with Gemini API."""
    api_key = os.environ.get('GEMINI_API_KEY')
    model = os.environ.get('GEMINI_MODEL') or os.environ.get('GEMINI_MODEL_FALLBACK') or 'gemini-2.5-flash'

    if not api_key:
        print("❌ Gemini API Key weipeizhi（jiancha GitHub Secrets: GEMINI_API_KEY）")
        return None

    print(f"🤖 shiyongmoxing: {model}")

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt
        )
        print(f"✅ Gemini ({model}) shenchachenggong")
        return response.text
    except ImportError as e:
        print(f"❌ Gemini yilaiweianzhuang: {e}")
        print("   qingquebaoanzhuangle google-genai: pip install google-genai")
        return None
    except Exception as e:
        print(f"❌ Gemini shenchashibai: {e}")
        traceback.print_exc()
        return None


def review_with_openai(prompt):
    """Run review with OpenAI-compatible API as fallback."""
    api_key = os.environ.get('OPENAI_API_KEY')
    base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

    if not api_key:
        print("❌ OpenAI API Key weipeizhi（jiancha GitHub Secrets: OPENAI_API_KEY）")
        return None

    print(f"🌐 Base URL: {base_url}")
    print(f"🤖 shiyongmoxing: {model}")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3
        )
        print(f"✅ OpenAI jianrong接口 ({model}) shenchachenggong")
        return response.choices[0].message.content
    except ImportError as e:
        print(f"❌ OpenAI yilaiweianzhuang: {e}")
        print("   qingquebaoanzhuangle openai: pip install openai")
        return None
    except Exception as e:
        print(f"❌ OpenAI jianrong接口shenchashibai: {e}")
        traceback.print_exc()
        return None


def ai_review(diff_content, files, truncated):
    """Run AI review: Gemini first, then OpenAI fallback."""
    pr_title, pr_body = get_pr_context()
    prompt = build_prompt(diff_content, files, truncated, pr_title, pr_body)

    result = review_with_gemini(prompt)
    if result:
        return result

    print("changshishiyong OpenAI jianrong接口...")
    result = review_with_openai(prompt)
    if result:
        return result

    return None


def main():
    diff, truncated = get_diff()
    files = get_changed_files()

    if not diff or not files:
        print("meiyoukeshenchadedaima/wendang/peizhibiangeng，tiaoguo AI shencha")
        summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary_file:
            with open(summary_file, 'a', encoding='utf-8') as f:
                f.write("## 🤖 AI daimashencha\n\n✅ meiyoukeshenchabiangeng\n")
        return

    print(f"shenchawenjian: {files}")
    if truncated:
        print(f"⚠️ Diff neirongyijieduanzhi {MAX_DIFF_LENGTH} zifu")

    review = ai_review(diff, files, truncated)

    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')

    strict_mode = os.environ.get('AI_REVIEW_STRICT', 'false').lower() == 'true'

    if review:
        if summary_file:
            with open(summary_file, 'a', encoding='utf-8') as f:
                f.write(f"## 🤖 AI daimashencha\n\n{review}\n")

        with open('ai_review_result.txt', 'w', encoding='utf-8') as f:
            f.write(review)

        print("AI shenchawancheng")
    else:
        print("⚠️ suoyou AI 接口doubukeyong")
        if summary_file:
            with open(summary_file, 'a', encoding='utf-8') as f:
                f.write("## 🤖 AI daimashencha\n\n⚠️ AI 接口bukeyong，qingjianchapeizhi\n")
        if strict_mode:
            raise SystemExit("AI_REVIEW_STRICT=true and no AI review result is available")


if __name__ == '__main__':
    main()
