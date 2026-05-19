#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Remove garbled Chinese/pinyin comments and normalize to English.
Excludes core files that will be manually translated.

Usage:
    python scripts/cleanup_comments.py
    python scripts/cleanup_comments.py --dry-run
"""

import argparse
import os
import re
import sys
from pathlib import Path

CORE_FILES = {
    "main.py",
    "src/core/pipeline.py",
    "src/agent/orchestrator.py",
    "data_provider/base.py",
    "src/config.py",
}


def has_garbage(text):
    if re.search(r'[\u4e00-\u9fff]', text):
        return True
    if re.search(r'\u7aca[\uac00-\ud7af]', text):
        return True
    pinyin_frags = [
        'zhize', 'guanli', 'fenxi', 'shuju', 'huoqu', 'tongzhi',
        'qudao', 'baogao', 'chushihua', 'shejimoshi', 'celve',
        'shixian', 'tigong', 'shiyong', 'fangshi', 'jieshao',
        'canshu', 'fanhui', 'yichang', 'zhuyi', 'tishi', 'sousuo',
        'chenggong', 'shibai', 'chuliqingqiu', 'jiekou', 'texing',
        'yibu', 'fangchongfu', 'shishituisong', 'jilu', 'ceshi',
        'shili', 'shuoming', 'huanjing', 'rizhi', 'daoru', 'daochu',
        'yingyong', 'fuwu', 'peizhi', 'gupiao', 'shichang',
        'bendikaifa', 'morenguanbi', 'zidongtiaoguo',
    ]
    lower = text.lower()
    return any(frag in lower for frag in pinyin_frags)


def process_file(filepath, root, dry_run):
    rel = str(filepath.relative_to(root))
    if rel in CORE_FILES:
        return 0

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception:
        return 0

    original = source
    module_name = filepath.stem.replace("_", " ").title()

    # Replace top-level docstrings (""" or ''' at start or after # -*- coding -*-")
    # Pattern 1: coding header followed by docstring
    pattern1 = re.compile(
        r'(^(?:#[^\n]*\n)*)\s*"""[\s\S]*?"""\s*',
        re.MULTILINE
    )
    match = pattern1.match(source)
    if match and has_garbage(match.group(0)):
        coding_lines = match.group(1) or ""
        source = coding_lines + f'"""\nDaily Stock Analysis - {module_name}\n"""\n\n'

    # Replace single-line comments with garbage
    lines = source.splitlines(keepends=True)
    new_lines = []
    modified = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#") and has_garbage(stripped):
            # Remove the comment line entirely (keep indentation if line has code before #)
            comment_pos = line.find("#")
            before = line[:comment_pos].rstrip()
            if before:
                new_lines.append(before + "\n")
            else:
                modified = True
                continue  # skip pure comment line
            modified = True
        else:
            new_lines.append(line)

    source = "".join(new_lines)

    # Also handle multi-line docstrings that aren't at the very top
    # but still contain garbage - replace with simple English
    def replace_docstring(m):
        content = m.group(0)
        if has_garbage(content):
            return f'"""\nDaily Stock Analysis - {module_name}\n"""'
        return content

    # Only replace docstrings that contain garbage
    source = re.sub(
        r'"""[\s\S]*?"""',
        replace_docstring,
        source
    )
    source = re.sub(
        r"'''[\s\S]*?'''",
        replace_docstring,
        source
    )

    if source != original:
        if not dry_run:
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                f.write(source)
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(".").resolve()
    py_files = sorted(root.rglob("*.py"))
    total = len(py_files)
    changed = 0

    print(f"Scanning {total} Python files...")
    print(f"Core files excluded: {', '.join(CORE_FILES)}")
    print()

    for filepath in py_files:
        result = process_file(filepath, root, args.dry_run)
        if result:
            changed += 1
            rel = filepath.relative_to(root)
            print(f"  {'[DRY-RUN]' if args.dry_run else '[FIXED]'} {rel}")

    print()
    print(f"{'='*50}")
    print(f"Total files: {total}")
    print(f"Files cleaned: {changed}")
    if args.dry_run:
        print("Run without --dry-run to apply.")
    else:
        print("Done! All garbled comments removed.")
    print(f"{'='*50}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
