#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.server.pid"
LOG_FILE="$SCRIPT_DIR/logs/server.log"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

echo "[daily-stock] pulling latest code..."
cd "$SCRIPT_DIR"
git pull

echo "[daily-stock] updating Python dependencies..."
"$VENV_PYTHON" -m pip install -q -r requirements.txt

echo "[daily-stock] building frontend..."
cd "$SCRIPT_DIR/apps/dsa-web"
npm ci --prefer-offline
VITE_BASE_PATH=/agents/daily-stock/ npm run build
cd "$SCRIPT_DIR"

echo "[daily-stock] stopping existing server..."
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    kill "$OLD_PID"
    sleep 2
  fi
  rm -f "$PID_FILE"
else
  # fallback: find by command
  pkill -f "python main.py --serve-only" 2>/dev/null || true
  sleep 1
fi

echo "[daily-stock] starting server..."
mkdir -p "$SCRIPT_DIR/logs"
nohup "$VENV_PYTHON" main.py --serve-only --port 3001 >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

sleep 2
if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "[daily-stock] server started (PID $(cat "$PID_FILE")), logging to $LOG_FILE"
else
  echo "[daily-stock] ERROR: server failed to start, check $LOG_FILE"
  exit 1
fi
