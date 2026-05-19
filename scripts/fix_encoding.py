#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
주식 분석 프로젝트 Python 파일 인코딩 보정 스크립트

수정 내역:
1. UTF-8 BOM 제거
2. \\r\\r\\n / \\r\\n / \\r → \\n 정규화
3. 자주 깨진 한글 주석 복원 (안전 매핑)

사용법:
    python scripts/fix_encoding.py --dry-run   # 미리보기만
    python scripts/fix_encoding.py             # 실제 적용
"""

import argparse
import os
import sys
from pathlib import Path

# --- 안전 매핑 표: 로마자/깨진 문자 → 정상 한글 ---
# 주의: 순서가 중요합니다. 길 문장이 짧은 문장을 덮어야 하면 먼저 두세요.
COMMENT_MAP = [
    # 종료 배의적 매핑 (기술박)
    ("zhize\u7aca?", "\u804c\u8d23\uff1a"),
    ("管理整个分析流程", "\u7ba1\u7406\u6574\u4e2a\u5206\u6790\u6d41\u7a0b"),
    ("xietiaoshujuhuoqu?\uac37unchu?\uac4cousuo?\uac4eenxi?\uac3dongzhidengmokuai",
     "\u534f\u8c03\u6570\u636e\u83b7\u53d6\u3001\u7f13\u5b58\u3001\u641c\u7d22\u3001\u5206\u6790\u3001\u901a\u77e5\u7b49\u6a21\u5757"),
    ("实现并发控制和异常处理", "\u5b9e\u73b0\u5e76\u53d1\u63a7\u5236\u548c\u5f02\u5e38\u5904\u7406"),
    ("提供股票分析的核心功能", "\u63d0\u4f9b\u80a1\u7968\u5206\u6790\u7684\u6838\u5fc3\u529f\u80fd"),
    ("初始化调度器", "\u521d\u59cb\u5316\u8c03\u5ea6\u5668"),
    ("数据源基类与管理器", "\u6570\u636e\u6e90\u57fa\u7c7b\u4e0e\u7ba1\u7406\u5668"),
    ("shejimoshi\uff1acelvemoshi (Strategy Pattern)", "\u8bbe\u8ba1\u6a21\u5f0f\uff1a\u7b56\u7565\u6a21\u5f0f (Strategy Pattern)"),
    ("BaseFetcher: chouxiangjilei\uff0cdingyitongyi接口", "BaseFetcher: \u62bd\u8c61\u57fa\u7c7b\uff0c\u5b9a\u4e49\u7edf\u4e00\u63a5\u53e3"),
    ("DataFetcherManager: celveguanliqi\uff0cshixianzidongqiehuan", "DataFetcherManager: \u7b56\u7565\u7ba1\u7406\u5668\uff0c\u5b9e\u73b0\u81ea\u52a8\u5207\u6362"),
    ("fangfengjincelve\uff1a", "\u9632\u5c01\u7981\u7b56\u7565\uff1a"),
    ("每个 Fetcher 内置流控逻辑", "\u6bcf\u4e2a Fetcher \u5185\u7f6e\u6d41\u63a7\u903b\u8f91"),
    ("失败自动切换到下一个数据源", "\u5931\u8d25\u81ea\u52a8\u5207\u6362\u5230\u4e0b\u4e00\u4e2a\u6570\u636e\u6e90"),
    ("指数退避重试机制", "\u6307\u6570\u9000\u907f\u91cd\u8bd5\u673a\u5236"),
    ("配置日志", "\u914d\u7f6e\u65e5\u5fd7"),
    ("标准化列名定义", "\u6807\u51c6\u5316\u5217\u540d\u5b9a\u4e49"),
    ("数据处理", "\u6570\u636e\u5904\u7406"),
    ("AI 分析", "AI \u5206\u6790"),
    ("sousuoyinqing\uff08yongyuhuoqugupiaoxinwen\uff09", "\u641c\u7d22\u5f15\u64ce\uff08\u7528\u4e8e\u83b7\u53d6\u80a1\u7968\u65b0\u95fb\uff09"),
    ("网络请求", "\u7f51\u7edc\u8bf7\u6c42"),
    ("数据库", "\u6570\u636e\u5e93"),
    ("baogaomubanyinqing\uff08Report Engine P0\uff09", "\u62a5\u544a\u6a21\u677f\u5f15\u64ce\uff08Report Engine P0\uff09"),
    ("Web 框架", "Web \u6846\u67b6"),
    ("核心依赖", "\u6838\u5fc3\u4f9d\u8d56"),
    ("shujuyuanyilai\uff08duoyuancelve\uff0canyouxianjipaixu\uff09", "\u6570\u636e\u6e90\u4f9d\u8d56\uff08\u591a\u6e90\u7b56\u7565\uff0c\u6309\u4f18\u5148\u7ea7\u6392\u5e8f\uff09"),
    ("Discord 机器人", "Discord \u673a\u5668\u4eba"),
    ("接口", "\u63a5\u53e3"),
    ("texing\uff1a", "\u7279\u6027\uff1a"),
    ("异步任务队列", "\u5f02\u6b65\u4efb\u52a1\u961f\u5217"),
    ("防重复提交", "\u9632\u91cd\u590d\u63d0\u4ea4"),
    ("实时推送", "\u5b9e\u65f6\u63a8\u9001"),
    ("jilu\u7aca?", "\u8bb0\u5f55\uff1a"),
    ("ceshi\u7aca?", "\u6d4b\u8bd5\uff1a"),
    ("shili\u7aca?", "\u793a\u4f8b\uff1a"),
    ("shuoming\u7aca?", "\u8bf4\u660e\uff1a"),
    ("canshu\u7aca?", "\u53c2\u6570\uff1a"),
    ("fanhui\u7aca?", "\u8fd4\u56de\uff1a"),
    ("yichang\u7aca?", "\u5f02\u5e38\uff1a"),
    ("zhuyi\u7aca?", "\u6ce8\u610f\uff1a"),
    ("tishi\u7aca?", "\u63d0\u793a\uff1a"),
    # 공통 데이터 소스 이름
    ("东方财富数据源", "\u4e1c\u65b9\u8d22\u5bcc\u6570\u636e\u6e90"),
    ("东方财富爬虫数据源", "\u4e1c\u65b9\u8d22\u5bcc\u722c\u866b\u6570\u636e\u6e90"),
    ("万得图 Pro API", "\u4e07\u5f97\u56fe Pro API"),
    ("通达信行情服务器", "\u901a\u8fbe\u4fe1\u884c\u60c5\u670d\u52a1\u5668"),
    ("证券宝数据", "\u8bc1\u5238\u5b9d\u6570\u636e"),
    ("长桥 OpenAPI", "\u957f\u6865 OpenAPI"),
    ("TickFlow official SDK", "TickFlow official SDK"),
    # 아래는 짧은 단어 매핑 (나중에 실행)
    ("\u7aca?", "\uff1a"),
]


def fix_file(path: Path, dry_run: bool = True) -> dict:
    """Fix a single Python file and return change stats."""
    with open(path, "rb") as f:
        raw = f.read()

    original = raw
    changes = {"bom": False, "crlf": False, "comments": 0}

    # 1. BOM 제거
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
        changes["bom"] = True

    # 2. \\r\\r\\n → \\n, \\r\\n → \\n, \\r → \\n
    if b"\r\r\n" in raw:
        raw = raw.replace(b"\r\r\n", b"\n")
        changes["crlf"] = True
    if b"\r\n" in raw:
        raw = raw.replace(b"\r\n", b"\n")
        changes["crlf"] = True
    if b"\r" in raw:
        raw = raw.replace(b"\r", b"\n")
        changes["crlf"] = True

    # 3. 주석 복원
    text = raw.decode("utf-8", errors="replace")
    for old, new in COMMENT_MAP:
        count = text.count(old)
        if count:
            text = text.replace(old, new)
            changes["comments"] += count

    new_raw = text.encode("utf-8")

    if not dry_run and new_raw != original:
        with open(path, "wb") as f:
            f.write(new_raw)

    return changes, new_raw != original


def main():
    parser = argparse.ArgumentParser(description="Fix encoding issues in Python files")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--path", default=".", help="Root directory to scan")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    py_files = list(root.rglob("*.py"))

    total_files = len(py_files)
    changed_files = 0
    total_bom = total_crlf = total_comments = 0

    print(f"Scanning {total_files} Python files in {root}\n")

    for path in py_files:
        changes, modified = fix_file(path, dry_run=args.dry_run)
        if modified:
            changed_files += 1
            total_bom += 1 if changes["bom"] else 0
            total_crlf += 1 if changes["crlf"] else 0
            total_comments += changes["comments"]
            action = "[DRY-RUN] Would fix" if args.dry_run else "[FIXED]"
            parts = []
            if changes["bom"]:
                parts.append("BOM")
            if changes["crlf"]:
                parts.append("CRLF")
            if changes["comments"]:
                parts.append(f"{changes['comments']} comments")
            print(f"  {action} {path.relative_to(root)} ({', '.join(parts)})")

    print(f"\n{'='*50}")
    print(f"Total files scanned : {total_files}")
    print(f"Files with issues   : {changed_files}")
    print(f"  - BOM removed     : {total_bom}")
    print(f"  - CRLF fixed      : {total_crlf}")
    print(f"  - Comments fixed  : {total_comments}")
    if args.dry_run:
        print(f"\n=> Run without --dry-run to apply changes.")
    else:
        print(f"\n[OK] All fixes applied.")
    print(f"{'='*50}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
