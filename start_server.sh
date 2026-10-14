#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8001}"

echo "Iniciando API de EyeInsights..."

exec python -m uvicorn app.main:app \
    --host "$API_HOST" \
    --port "$API_PORT"
