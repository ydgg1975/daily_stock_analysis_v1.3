#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker/docker-compose.yml"

echo "[daily-stock] pulling latest code..."
cd "$SCRIPT_DIR"
git pull

echo "[daily-stock] rebuilding and restarting server container..."
docker-compose -f "$COMPOSE_FILE" up -d --build server

echo "[daily-stock] container status:"
docker-compose -f "$COMPOSE_FILE" ps server

echo "[daily-stock] done."
