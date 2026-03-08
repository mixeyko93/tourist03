from contextlib import contextmanager

import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor

from tourist03.config import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER


def _pg_connect(schema: str):
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

    kwargs = dict(
        host=_safe_str(PG_HOST),
        port=PG_PORT,
        dbname=_safe_str(PG_DB),
        user=_safe_str(PG_USER),
        password=_safe_str(PG_PASSWORD),
        options="-c client_encoding=UTF8",
        cursor_factory=RealDictCursor,
    )

    try:
        conn = psycopg2.connect(**kwargs)
    except UnicodeDecodeError as exc:
        msg = (
            "UnicodeDecodeError while connecting to Postgres. "
            "Sanitized connection parameters (repr):\n"
            f"host={repr(kwargs.get('host'))}, dbname={repr(kwargs.get('dbname'))}, "
            f"user={repr(kwargs.get('user'))}, password={repr(kwargs.get('password'))}\n"
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
