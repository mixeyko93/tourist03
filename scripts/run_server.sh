#!/usr/bin/env bash
set -euo pipefail

# Simple helper to run the API locally.
cd "$(dirname "$0")/.."

PORT=${PORT:-8080}
python3 -m uvicorn app:app --reload --host 127.0.0.1 --port "${PORT}"
