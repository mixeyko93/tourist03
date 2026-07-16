#!/bin/sh
# Create a self-contained, untracked PostgreSQL + uploads backup.
set -eu
umask 077

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
BACKUP_ROOT=${BACKUP_ROOT:-"$PROJECT_DIR/backups"}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR="$BACKUP_ROOT/$STAMP"

: "${PG_HOST:?PG_HOST is required}"
: "${PG_PORT:?PG_PORT is required}"
: "${PG_DB:?PG_DB is required}"
: "${PG_USER:?PG_USER is required}"
: "${PG_PASSWORD:?PG_PASSWORD is required}"

for command in pg_dump psql tar; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Required command is unavailable: $command" >&2
    exit 1
  }
done

if [ -e "$BACKUP_DIR" ]; then
  echo "Backup destination already exists: $BACKUP_DIR" >&2
  exit 1
fi
if [ ! -d "$PROJECT_DIR/static/uploads" ]; then
  echo "Uploads directory is missing: $PROJECT_DIR/static/uploads" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
export PGPASSWORD=$PG_PASSWORD
export PGHOST=$PG_HOST PGPORT=$PG_PORT PGDATABASE=$PG_DB PGUSER=$PG_USER

pg_dump -Fc --no-owner --no-acl --file="$BACKUP_DIR/database.dump"
tar -czf "$BACKUP_DIR/uploads.tar.gz" -C "$PROJECT_DIR/static" uploads
printf '%s\n' "$STAMP" > "$BACKUP_DIR/timestamp.txt"

(
  cd "$PROJECT_DIR"
  "$PYTHON_BIN" -m tourist03.migrations status
) > "$BACKUP_DIR/migrations.json"

psql --no-psqlrc -At -c "
  SELECT quote_ident(schemaname) || '.' || quote_ident(tablename)
  FROM pg_tables
  WHERE schemaname IN ('auth', 'catalog', 'crm')
  ORDER BY schemaname, tablename
" | while IFS= read -r table_name; do
  [ -n "$table_name" ] || continue
  count=$(psql --no-psqlrc -At -c "SELECT count(*) FROM $table_name")
  printf '%s\t%s\n' "$table_name" "$count"
done > "$BACKUP_DIR/row_counts.tsv"

sha_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1"
  else
    shasum -a 256 "$1"
  fi
}

(
  cd "$BACKUP_DIR"
  sha_file database.dump
  sha_file uploads.tar.gz
  sha_file migrations.json
  sha_file row_counts.tsv
  sha_file timestamp.txt
) > "$BACKUP_DIR/sha256sums.txt"

echo "Backup created: $BACKUP_DIR"
