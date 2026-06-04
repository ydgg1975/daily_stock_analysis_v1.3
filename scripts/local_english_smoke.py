"""Run a small local English-mode smoke test.

Usage:
    python scripts/local_english_smoke.py AAPL
    python scripts/local_english_smoke.py AAPL MSFT
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime
from pathlib import Path

from src.config import get_config
from src.core.pipeline import StockAnalysisPipeline


HAN_RE = re.compile(r"[\u4e00-\u9fff]")


def main() -> int:
    logging.basicConfig(level=logging.ERROR)

    config = get_config()
    codes = [code.strip().upper() for code in sys.argv[1:] if code.strip()] or list(config.stock_list)
    if not codes:
        print("No stock codes supplied and STOCK_LIST is empty.")
        return 1

    print(f"Language: {config.report_language}")
    print(f"Model: {config.litellm_model}")
    print(f"Stocks: {', '.join(codes)}")

    pipeline = StockAnalysisPipeline(config=config, max_workers=1, save_context_snapshot=False)
    results = pipeline.run(codes, dry_run=False, send_notification=False)

    print(f"Result count: {len(results)}")
    for result in results:
        print(
            f"- {result.code}: success={result.success} "
            f"score={result.sentiment_score} advice={result.operation_advice!r} "
            f"trend={result.trend_prediction!r}"
        )

    report_path = Path(__file__).resolve().parents[1] / "reports" / f"report_{datetime.now():%Y%m%d}.md"
    if not report_path.exists():
        print(f"Report not found: {report_path}")
        return 1

    report_text = report_path.read_text(encoding="utf-8", errors="replace")
    has_chinese = bool(HAN_RE.search(report_text))
    print(f"Report: {report_path}")
    print(f"Report has Chinese: {has_chinese}")
    return 1 if has_chinese else 0


if __name__ == "__main__":
    raise SystemExit(main())
