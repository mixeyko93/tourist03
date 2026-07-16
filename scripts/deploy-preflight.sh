#!/bin/sh
# Local preflight only. It does not push, deploy or change a database.
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
cd "$PROJECT_DIR"

git diff --check
PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" -m compileall -q app.py tourist03 tests
PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" -m unittest discover -s tests -v
(cd frontend && npm run build)

echo "Preflight passed. Run backup, migration upgrade and remote health checks only in the approved deploy window."
