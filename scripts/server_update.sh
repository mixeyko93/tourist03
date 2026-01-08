#!/usr/bin/env bash
set -euo pipefail

REPO_DIR=${REPO_DIR:-/opt/tourist03-repo}
APP_DIR=${APP_DIR:-/opt/tourist03}

if [[ ! -d "$REPO_DIR/.git" ]]; then
  echo "ERROR: repo not found at $REPO_DIR (expected .git)" >&2
  exit 1
fi
if [[ ! -d "$APP_DIR" ]]; then
  echo "ERROR: app dir not found at $APP_DIR" >&2
  exit 1
fi

echo "== Pulling repo =="
cd "$REPO_DIR"
git pull --ff-only

echo "== Syncing to app dir (keeping secrets) =="
rsync -a --delete --no-owner --no-group \
  --exclude '.env' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude 'static/uploads' \
  "$REPO_DIR"/ "$APP_DIR"/

echo "== Installing deps (if needed) =="
if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
  "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
else
  echo "WARN: venv not found at $APP_DIR/.venv (skipping pip install)" >&2
fi

echo "== Restarting services =="
systemctl restart tourist03-app || true
systemctl restart tourist03-bot || true

echo "== Status =="
systemctl --no-pager --full status tourist03-app || true
systemctl --no-pager --full status tourist03-bot || true

