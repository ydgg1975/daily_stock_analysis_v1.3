#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "static",
    "dist",
    "build",
    "htmlcov",
}

SKIP_SUFFIXES = {
    ".db",
    ".ico",
    ".jpg",
    ".jpeg",
    ".png",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".webp",
}

SURFACE_PATHS = (
    Path("AGENTS.md"),
    Path(".github/copilot-instructions.md"),
    Path(".github/instructions"),
    Path(".github/workflows/ci.yml"),
    Path("apps/dsa-web/src"),
)

SURFACE_EXCLUDE_PARTS = {"__tests__", "tests", "e2e"}

HAN_OR_MOJIBAKE = re.compile(r"[\u3400-\u9fff]|\u7aca|\u951b|\ufffd|\?\?\?|[\ue000-\uf8ff]")

PINYIN_TERMS = (
    "baocun",
    "beixuan",
    "ceshi",
    "chakan",
    "dakai",
    "fasong",
    "fenxi",
    "fuzhi",
    "guanbi",
    "guizhoumaotai",
    "gupiao",
    "hangqing",
    "jilu",
    "maotai",
    "mima",
    "moxing",
    "peizhi",
    "qingqiushibai",
    "qingshu",
    "queren",
    "renzheng",
    "shanchu",
    "shaohou",
    "shichang",
    "shuaxin",
    "tianjia",
    "tongzhi",
    "touming",
    "weidenglu",
    "xiangguan",
    "yinxing",
    "zanwu",
    "zhengzai",
    "zhongguo",
    "zhongshi",
    "zhongxin",
    "zhongxing",
    "zixuan",
)

PINYIN_RE = re.compile(r"\b(" + "|".join(re.escape(term) for term in PINYIN_TERMS) + r")\b", re.IGNORECASE)


def iter_files(base: Path) -> list[Path]:
    if base.is_file():
        return [base]
    files: list[Path] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(ROOT).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        files.append(path)
    return files


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def line_excerpt(text: str, index: int) -> tuple[int, str]:
    line_no = text.count("\n", 0, index) + 1
    line_start = text.rfind("\n", 0, index) + 1
    line_end = text.find("\n", index)
    if line_end == -1:
        line_end = len(text)
    return line_no, text[line_start:line_end].strip()


def collect_matches(files: list[Path], pattern: re.Pattern[str]) -> list[str]:
    findings: list[str] = []
    for path in files:
        text = read_text(path)
        if text is None:
            continue
        rel = path.relative_to(ROOT)
        for match in pattern.finditer(text):
            line_no, excerpt = line_excerpt(text, match.start())
            findings.append(f"{rel}:{line_no}: {match.group(0)!r} in {excerpt[:180]}")
            break
    return findings


def surface_files() -> list[Path]:
    files: list[Path] = []
    for rel in SURFACE_PATHS:
        path = ROOT / rel
        if not path.exists():
            continue
        for file_path in iter_files(path):
            parts = set(file_path.relative_to(ROOT).parts)
            if parts & SURFACE_EXCLUDE_PARTS:
                continue
            files.append(file_path)
    return files


def all_repo_files() -> list[Path]:
    return iter_files(ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Block disallowed language artifacts from user-facing project files.")
    parser.add_argument(
        "--han-scope",
        choices=("surface", "all"),
        default="surface",
        help="Where to block Han/mojibake artifacts. Default: surface.",
    )
    parser.add_argument(
        "--pinyin-scope",
        choices=("surface", "all", "none"),
        default="none",
        help="Where to block romanized legacy terms. Default: none.",
    )
    args = parser.parse_args()

    failures: list[str] = []

    han_targets = surface_files() if args.han_scope == "surface" else all_repo_files()
    han_findings = collect_matches(han_targets, HAN_OR_MOJIBAKE)
    if han_findings:
        failures.append(f"Disallowed Han/mojibake characters found in {args.han_scope} scope:")
        failures.extend(f"  {item}" for item in han_findings[:80])

    if args.pinyin_scope != "none":
        pinyin_targets = surface_files() if args.pinyin_scope == "surface" else all_repo_files()
        pinyin_findings = collect_matches(pinyin_targets, PINYIN_RE)
        if pinyin_findings:
            failures.append(f"Disallowed romanized legacy terms found in {args.pinyin_scope} scope:")
            failures.extend(f"  {item}" for item in pinyin_findings[:80])

    if failures:
        print("[language-artifacts] ERROR", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1

    print("[language-artifacts] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
