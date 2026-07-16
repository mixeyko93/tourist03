from contextlib import contextmanager
from typing import Optional

import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor

from tourist03.settings import get_settings


def _pg_connect(
    schema: str,
    *,
    connect_timeout: Optional[int] = None,
    statement_timeout_ms: Optional[int] = None,
):
    # Ensure values passed to psycopg2 are proper Python strings.
    def _safe_str(val):
        if isinstance(val, bytes):
            try:
                return val.decode("utf-8")
            except Exception:
                return val.decode("utf-8", errors="replace")
        if val is None:
            return None
        return str(val)

    settings = get_settings()
    options = ["-c client_encoding=UTF8"]
    if statement_timeout_ms is not None:
        options.append(f"-c statement_timeout={max(int(statement_timeout_ms), 1)}")

    kwargs = dict(
        host=_safe_str(settings.pg_host),
        port=settings.pg_port,
        dbname=_safe_str(settings.pg_db),
        user=_safe_str(settings.pg_user),
        password=_safe_str(settings.pg_password),
        options=" ".join(options),
        cursor_factory=RealDictCursor,
    )
    if connect_timeout is not None:
        kwargs["connect_timeout"] = max(int(connect_timeout), 1)

    try:
        conn = psycopg2.connect(**kwargs)
    except UnicodeDecodeError as exc:
        msg = (
            "UnicodeDecodeError while connecting to Postgres. "
            "Sanitized connection parameters (repr):\n"
            f"host={repr(kwargs.get('host'))}, dbname={repr(kwargs.get('dbname'))}, "
            f"user={repr(kwargs.get('user'))}, password=[redacted]\n"
            f"Original error: {exc!r}"
        )
        raise RuntimeError(msg) from exc

    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO %s", (schema,))
    except errors.InvalidSchemaName:
        conn.rollback()
    return conn


@contextmanager
def _db_conn(schema: str):
    conn = _pg_connect(schema)
    try:
        yield conn
    finally:
        conn.close()
