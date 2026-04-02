#!/bin/sh
set -eu

build_server() {
  if [ -n "${DEPLOY_SERVER:-}" ]; then
    printf '%s' "$DEPLOY_SERVER"
    return
  fi

  if [ -n "${DEPLOY_HOST:-}" ] && [ -n "${DEPLOY_USER:-}" ]; then
    printf '%s@%s' "$DEPLOY_USER" "$DEPLOY_HOST"
    return
  fi

  printf '%s' "root@45.153.71.21"
}

run_remote() {
  if [ -n "${DEPLOY_PASSWORD:-}" ] && command -v expect >/dev/null 2>&1; then
    EXPECT_SCRIPT="$(mktemp)"
    cat >"$EXPECT_SCRIPT" <<'EOF'
set timeout -1
log_user 1
set password $env(DEPLOY_PASSWORD)
eval spawn $argv
expect {
  -re "(?i)are you sure you want to continue connecting.*" {
    send -- "yes\r"
    exp_continue
  }
  -re "(?i)password:" {
    send -- "$password\r"
    exp_continue
  }
  eof
}
catch wait result
set code [lindex $result 3]
if {$code eq ""} {
  set code 0
}
exit $code
EOF
    env DEPLOY_PASSWORD="$DEPLOY_PASSWORD" expect "$EXPECT_SCRIPT" "$@"
    status=$?
    rm -f "$EXPECT_SCRIPT"
    return $status
  fi

  "$@"
}

resolve_deploy_password() {
  if [ -n "${DEPLOY_PASSWORD:-}" ]; then
    return
  fi

  if [ -n "${KEYCHAIN_SERVICE:-}" ] && [ -n "${KEYCHAIN_ACCOUNT:-}" ] && command -v security >/dev/null 2>&1; then
    DEPLOY_PASSWORD="$(security find-generic-password -s "$KEYCHAIN_SERVICE" -a "$KEYCHAIN_ACCOUNT" -w 2>/dev/null || true)"
    export DEPLOY_PASSWORD
  fi
}

SERVER="$(build_server)"
PROJECT_PATH="${DEPLOY_PATH:-/opt/tourist03}"
RSYNC_RSH="${RSYNC_RSH:-ssh -o StrictHostKeyChecking=accept-new}"
DEPLOY_CMD="${DEPLOY_CMD:-./.venv/bin/pip install -r requirements.txt && systemctl restart tourist03-app tourist03-bot caddy}"

resolve_deploy_password

run_remote rsync -az --delete \
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

run_remote ssh -o StrictHostKeyChecking=accept-new "$SERVER" "chown -R tourist03:tourist03 \"$PROJECT_PATH\" && cd \"$PROJECT_PATH\" && $DEPLOY_CMD"
