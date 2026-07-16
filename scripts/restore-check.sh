#!/bin/sh
# Restore one backup into an explicit test database and compare row counts.
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
BACKUP_DIR=${1:?Usage: scripts/restore-check.sh /path/to/backup}
: "${RESTORE_TEST_DB:?RESTORE_TEST_DB must name an existing test database}"
: "${RESTORE_CONFIRM:?Set RESTORE_CONFIRM=RESTORE_TEST_DATABASE to continue}"
: "${PG_HOST:?PG_HOST is required}"
: "${PG_PORT:?PG_PORT is required}"
: "${PG_USER:?PG_USER is required}"
: "${PG_PASSWORD:?PG_PASSWORD is required}"

if [ "$RESTORE_CONFIRM" != "RESTORE_TEST_DATABASE" ]; then
  echo "Refusing restore: confirmation phrase does not match." >&2
  exit 1
fi
case "$RESTORE_TEST_DB" in
  *test*|*restore*) ;;
  *)
    echo "Refusing restore: RESTORE_TEST_DB must visibly be a test/restore database." >&2
    exit 1
    ;;
esac
for command in pg_restore psql tar; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Required command is unavailable: $command" >&2
    exit 1
  }
done
for artifact in database.dump uploads.tar.gz migrations.json row_counts.tsv sha256sums.txt; do
  [ -f "$BACKUP_DIR/$artifact" ] || {
    echo "Backup artifact is missing: $artifact" >&2
    exit 1
  }
done

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$BACKUP_DIR" && sha256sum -c sha256sums.txt)
else
  (cd "$BACKUP_DIR" && shasum -a 256 -c sha256sums.txt)
fi

export PGPASSWORD=$PG_PASSWORD
export PGHOST=$PG_HOST PGPORT=$PG_PORT PGDATABASE=$RESTORE_TEST_DB PGUSER=$PG_USER

# The target database must already exist and have an unmistakably test-only name.
pg_restore --clean --if-exists --no-owner --no-acl --dbname="$RESTORE_TEST_DB" "$BACKUP_DIR/database.dump"

while IFS='	' read -r table_name expected_count; do
  [ -n "$table_name" ] || continue
  actual_count=$(psql --no-psqlrc -At -c "SELECT count(*) FROM $table_name")
  if [ "$actual_count" != "$expected_count" ]; then
    echo "Row count mismatch for $table_name: expected $expected_count, got $actual_count" >&2
    exit 1
  fi
done < "$BACKUP_DIR/row_counts.tsv"

(
  cd "$PROJECT_DIR"
  PG_DB="$RESTORE_TEST_DB" "$PYTHON_BIN" -m tourist03.migrations check
)

if [ -n "${RESTORE_UPLOAD_DIR:-}" ]; then
  case "$RESTORE_UPLOAD_DIR" in
    "$PROJECT_DIR/static/uploads"|"$PROJECT_DIR/static/uploads"/*)
      echo "Refusing to extract uploads into the live uploads directory." >&2
      exit 1
      ;;
  esac
  mkdir -p "$RESTORE_UPLOAD_DIR"
  tar -xzf "$BACKUP_DIR/uploads.tar.gz" -C "$RESTORE_UPLOAD_DIR"
fi

echo "Restore check passed for test database: $RESTORE_TEST_DB"
