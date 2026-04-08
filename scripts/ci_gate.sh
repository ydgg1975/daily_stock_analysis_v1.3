#!/usr/bin/env bash

set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "[backend-gate] Python interpreter not found (tried python, python3)" >&2
    exit 127
  fi
fi

run_flake8_critical() {
  if command -v flake8 >/dev/null 2>&1; then
    flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
    return 0
  fi
  if "${PYTHON_BIN}" -c "import flake8" >/dev/null 2>&1; then
    "${PYTHON_BIN}" -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
    return 0
  fi
  if [[ -n "${CI:-}" ]]; then
    echo "[backend-gate] flake8 is required in CI but is not available" >&2
    exit 127
  fi
  echo "==> backend-gate: flake8 critical checks"
  echo "WARN: flake8 not installed; install dev tools with: ${PYTHON_BIN} -m pip install -r requirements-dev.txt"
}

echo "==> backend-gate: Python syntax check"
"${PYTHON_BIN}" -m py_compile main.py src/config.py src/auth.py src/analyzer.py src/notification.py
"${PYTHON_BIN}" -m py_compile src/storage.py src/scheduler.py src/search_service.py
"${PYTHON_BIN}" -m py_compile src/market_analyzer.py src/stock_analyzer.py
"${PYTHON_BIN}" -m py_compile data_provider/*.py

run_flake8_critical

echo "==> backend-gate: local deterministic checks"
./test.sh code
./test.sh yfinance

echo "==> backend-gate: offline test suite"
"${PYTHON_BIN}" -m pytest -m "not network"

echo "==> backend-gate: all checks passed"
