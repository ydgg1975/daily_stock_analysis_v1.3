#!/usr/bin/env bash
# End-to-end smoke: one-stock analysis with iWencai realtime first.
# Requires: IWENCAI_API_KEY, configured LLM keys in .env, and skills/hithink-market-query installed.
# Usage: ./scripts/verify_iwencai_pipeline.sh
# Optional: VERIFY_STOCK=600519 REALTIME_SOURCE_PRIORITY=iwencai_market,tencent

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -z "${IWENCAI_API_KEY:-}" ]]; then
  echo "verify_iwencai_pipeline: IWENCAI_API_KEY not set — skipping (exit 0)."
  exit 0
fi

export IWENCAI_MARKET_QUERY_ENABLED="${IWENCAI_MARKET_QUERY_ENABLED:-true}"
export REALTIME_SOURCE_PRIORITY="${REALTIME_SOURCE_PRIORITY:-iwencai_market,tencent,akshare_sina,efinance,akshare_em}"
export TRADING_DAY_CHECK_ENABLED="${TRADING_DAY_CHECK_ENABLED:-false}"

STOCK="${VERIFY_STOCK:-600519}"
echo "Running main.py for stock=${STOCK} (no notify, force-run)..."
python main.py --stocks "${STOCK}" --no-notify --force-run

echo "Done. Grep logs for Iwencai / iwencai_market to confirm source."
echo "Optional: RUN_IWENCAI_LIVE=1 pytest tests/test_iwencai_market_query_fetcher.py::TestIwencaiLiveCLI -v"
