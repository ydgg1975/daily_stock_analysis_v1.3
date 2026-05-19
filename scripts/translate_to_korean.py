#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Translate all Chinese/pinyin comments and docstrings in Python files to Korean.

Usage:
    python scripts/translate_to_korean.py
    python scripts/translate_to_korean.py --dry-run   # Preview only

Requires: OPENCODE_GO_API_KEY or OPENAI_API_KEY in .env
"""

import argparse
import io
import json
import os
import pickle
import re
import sys
import time
import tokenize
from pathlib import Path

import requests


def load_api_key():
    """Load API key from .env or environment."""
    for env_path in [Path(".env"), Path.home() / ".hermes" / ".env"]:
        if env_path.exists():
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("OPENCODE_GO_API_KEY="):
                        return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    for key in ["OPENCODE_GO_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
        if os.getenv(key):
            return os.getenv(key)
    return None


API_KEY = load_api_key()
BASE_URL = os.getenv("LLM_BASE_URL", "https://opencode.ai/zen/go/v1")
MODEL = os.getenv("LLM_MODEL", "kimi-k2.6")


def clean_garbled(text):
    text = re.sub(r'\u7aca[\uac00-\ud7af]', '', text)
    text = re.sub(r'[\uac00-\ud7af]{1,2}(?=[a-zA-Z])', '', text)
    return text


def has_pinyin_chinese(text):
    pinyin_words = [
        'zhize', 'guanli', 'fenxi', 'shuju', 'huoqu', 'tongzhi', 'qudao', 'baogao',
        'chushihua', 'shejimoshi', 'celve', 'shixian', 'tigong', 'shiyong', 'fangshi',
        'jieshao', 'canshu', 'fanhui', 'yichang', 'zhuyi', 'tishi', 'sousuo',
        'chenggong', 'shibai', 'chuliqingqiu', 'jiekou', 'texing', 'yibu',
        'fangchongfu', 'shishituisong', 'jilu', 'ceshi', 'shili', 'shuoming',
        'huanjing', 'rizhi', 'daoru', 'daochu', 'yingyong', 'shili', 'fuwu',
        'peizhi', 'chushihua', 'gupiao', 'fenxi', 'tongzhi', 'shichang',
    ]
    lower = text.lower()
    return bool(re.search(r'[\u4e00-\u9fff]', text)) or any(w in lower for w in pinyin_words)


def translate_batch(texts, batch_num):
    if not API_KEY:
        raise RuntimeError("No API key found. Set OPENCODE_GO_API_KEY in .env")
    
    prompt = (
        "You are a professional translator. Translate the following Chinese pinyin phrases "
        "into natural Korean suitable for code comments.\n\n"
        "Rules:\n"
        "- These are Chinese words written in pinyin (romanized Chinese)\n"
        "- Translate to natural, professional Korean for code comments\n"
        "- Keep any %s, %d, {placeholder} format placeholders as-is\n"
        "- Keep English technical terms as-is\n"
        "- Return ONLY in this format:\n\n"
        "[1] KOREAN: <translation>\n"
        "[2] KOREAN: <translation>\n"
        "...\n\n"
        "Phrases to translate:\n"
    )
    for i, text in enumerate(texts, 1):
        prompt += f"\n[{i}] {text}"

    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 16000,
            },
            timeout=180,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        translations = {}
        pattern = r'\[(\d+)\]\s*KOREAN:\s*(.*?)(?=\n\[\d+\]\s*KOREAN:|\Z)'
        for m in re.finditer(pattern, content, re.DOTALL):
            idx = int(m.group(1)) - 1
            trans = m.group(2).strip()
            if 0 <= idx < len(texts):
                translations[texts[idx]] = trans
        return translations
    except Exception as e:
        print(f"  Batch {batch_num} failed: {e}")
        return {}


def extract_occurrences(root):
    occurrences = []
    unique = {}
    for filepath in root.rglob("*.py"):
        if filepath.name in ("fix_encoding.py", "translate_to_korean.py"):
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception:
            continue
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except tokenize.TokenError:
            continue

        for i, tok in enumerate(tokens):
            if tok.type == tokenize.STRING:
                is_docstring = (i == 0) or (i > 0 and tokens[i - 1].type in (
                    tokenize.NEWLINE, tokenize.NL, tokenize.INDENT, tokenize.DEDENT
                ))
                if is_docstring:
                    text = tok.string
                    for q in ('"""', "'''", '"', "'"):
                        if text.startswith(q) and text.endswith(q):
                            text = text[len(q):-len(q)]
                            break
                    cleaned = clean_garbled(text)
                    if has_pinyin_chinese(cleaned):
                        if cleaned not in unique:
                            unique[cleaned] = text
                        occurrences.append((str(filepath), "docstring", tok.string, cleaned, tok.start, tok.end))
            elif tok.type == tokenize.COMMENT:
                cleaned = clean_garbled(tok.string)
                if has_pinyin_chinese(cleaned):
                    text = tok.string.lstrip("#").strip()
                    if text not in unique:
                        unique[text] = text
                    occurrences.append((str(filepath), "comment", tok.string, text, tok.start, tok.end))
    return unique, occurrences


def apply_translations(root, unique, occurrences, translation_map, dry_run):
    changed = 0
    for filepath, typ, original, cleaned, start, end in occurrences:
        fp = Path(filepath)
        if cleaned not in translation_map:
            continue
        trans = translation_map[cleaned]
        if trans == cleaned or not trans:
            continue

        try:
            with open(fp, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            continue

        s_line, s_col = start
        e_line, e_col = end

        if s_line == e_line:
            line = lines[s_line - 1]
            new_line = line[:s_col] + trans + line[e_col:]
            lines[s_line - 1] = new_line
        else:
            start_line = lines[s_line - 1]
            end_line = lines[e_line - 1]
            new_text = start_line[:s_col] + trans + end_line[e_col:]
            lines[s_line - 1] = new_text
            for _ in range(s_line, e_line):
                lines.pop(s_line)

        if not dry_run:
            with open(fp, "w", encoding="utf-8") as f:
                f.writelines(lines)
        changed += 1

    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--batch-size", type=int, default=50, help="Texts per API batch")
    parser.add_argument("--resume", action="store_true", help="Resume from cached translations")
    args = parser.parse_args()

    root = Path(".").resolve()
    cache_path = root / ".translation_cache.json"

    print("Step 1/4: Extracting Chinese/pinyin texts...")
    unique, occurrences = extract_occurrences(root)
    print(f"  Unique texts: {len(unique)}")
    print(f"  Total occurrences: {len(occurrences)}")

    translation_map = {}
    if args.resume and cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            translation_map = json.load(f)
        print(f"  Loaded {len(translation_map)} cached translations")

    texts_to_translate = [t for t in unique if t not in translation_map]
    if texts_to_translate:
        print(f"\nStep 2/4: Translating {len(texts_to_translate)} texts...")
        batch_size = args.batch_size
        total_batches = (len(texts_to_translate) + batch_size - 1) // batch_size
        for i in range(0, len(texts_to_translate), batch_size):
            batch = texts_to_translate[i:i + batch_size]
            batch_num = i // batch_size + 1
            print(f"  Batch {batch_num}/{total_batches} ({len(batch)} texts)...", end=" ", flush=True)
            result = translate_batch(batch, batch_num)
            translation_map.update(result)
            print(f"OK ({len(result)} translated)")
            if not args.dry_run:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(translation_map, f, ensure_ascii=False, indent=2)
            time.sleep(1)
    else:
        print("\nStep 2/4: All texts already translated (cached)")

    print(f"\nStep 3/4: Applying translations...")
    changed = apply_translations(root, unique, occurrences, translation_map, args.dry_run)
    print(f"  {changed} occurrences {'would be' if args.dry_run else ''} updated")

    if args.dry_run:
        print("\n[Dry run] No files modified. Run without --dry-run to apply.")
    else:
        print("\nDone! All Chinese/pinyin comments translated to Korean.")
        if cache_path.exists():
            print(f"Translation cache saved to: {cache_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
