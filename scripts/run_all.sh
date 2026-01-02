#!/usr/bin/env bash
set -euo pipefail

# Запуск API (uvicorn) и бота параллельно.
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
PORT=${PORT:-8080}

cleanup() {
  echo "Stopping services..."
  pkill -P $$ || true
}
trap cleanup INT TERM

$PY -m uvicorn app:app --reload --host 127.0.0.1 --port "${PORT}" &
uvicorn_pid=$!

$PY bot.py &
bot_pid=$!

echo "API pid=${uvicorn_pid}, bot pid=${bot_pid}"
wait $uvicorn_pid $bot_pid
