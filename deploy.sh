#!/bin/sh
set -eu

SERVER="${DEPLOY_SERVER:-root@45.153.71.21}"
PROJECT_PATH="${DEPLOY_PATH:-/opt/tourist03}"
DEPLOY_CMD="${DEPLOY_CMD:-git pull && ./.venv/bin/pip install -r requirements.txt && systemctl restart tourist03-app tourist03-bot caddy}"

ssh "$SERVER" "cd \"$PROJECT_PATH\" && $DEPLOY_CMD"
