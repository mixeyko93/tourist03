#!/bin/sh
set -eu

SERVER="${DEPLOY_SERVER:-root@45.153.71.21}"
PROJECT_PATH="${DEPLOY_PATH:-/opt/tourist03}"
RSYNC_RSH="${RSYNC_RSH:-ssh}"
DEPLOY_CMD="${DEPLOY_CMD:-./.venv/bin/pip install -r requirements.txt && systemctl restart tourist03-app tourist03-bot caddy}"

rsync -az --delete \
  --exclude='.git' \
  --exclude='.deploy.local' \
  --exclude='.env' \
  --exclude='.venv' \
  --exclude='DerivedData' \
  --exclude='__pycache__' \
  --exclude='.DS_Store' \
  --exclude='._*' \
  --exclude='node_modules' \
  --exclude='frontend/node_modules' \
  --exclude='uploads' \
  --exclude='cache' \
  --exclude='__cache__' \
  -e "$RSYNC_RSH" \
  ./ "$SERVER:$PROJECT_PATH/"

ssh "$SERVER" "chown -R tourist03:tourist03 \"$PROJECT_PATH\" && cd \"$PROJECT_PATH\" && $DEPLOY_CMD"
