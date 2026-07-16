#!/usr/bin/env bash
# Restore one backup into an explicit test database and compare row counts.
set -Eeuo pipefail

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
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
for command in pg_restore psql; do
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
trap 'unset PGPASSWORD' EXIT

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
  mkdir -p "$RESTORE_UPLOAD_DIR"
  RESTORE_UPLOAD_DIR=$(CDPATH= cd -- "$RESTORE_UPLOAD_DIR" && pwd -P)
  LIVE_UPLOAD_DIR=$(CDPATH= cd -- "$PROJECT_DIR/static/uploads" && pwd -P)
  case "$RESTORE_UPLOAD_DIR" in
    "$LIVE_UPLOAD_DIR"|"$LIVE_UPLOAD_DIR"/*)
      echo "Refusing to extract uploads into the live uploads directory." >&2
      exit 1
      ;;
  esac
  "$PYTHON_BIN" - "$BACKUP_DIR/uploads.tar.gz" "$RESTORE_UPLOAD_DIR" <<'PY'
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

archive_path = Path(sys.argv[1])
destination = Path(sys.argv[2]).resolve()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return False
    return True


with tarfile.open(archive_path, "r:gz") as archive:
    members = archive.getmembers()
    for member in members:
        name = PurePosixPath(member.name)
        target = destination.joinpath(*name.parts)
        if (
            name.is_absolute()
            or ".." in name.parts
            or not name.parts
            or name.parts[0] != "uploads"
            or member.issym()
            or member.islnk()
            or member.isdev()
            or not is_within(target, destination)
        ):
            raise SystemExit(f"Unsafe uploads archive member: {member.name!r}")

    for member in members:
        target = destination.joinpath(*PurePosixPath(member.name).parts)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not member.isfile():
            raise SystemExit(f"Unsupported uploads archive member: {member.name!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise SystemExit(f"Unable to read uploads archive member: {member.name!r}")
        with source, target.open("xb") as output:
            shutil.copyfileobj(source, output)
PY
fi

echo "Restore check passed for test database: $RESTORE_TEST_DB"
