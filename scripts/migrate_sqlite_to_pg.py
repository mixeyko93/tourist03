#!/usr/bin/env python
"""
Copy data from legacy SQLite DBs located in ./db into the PostgreSQL
database described in .env (schemas: catalog, auth).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "tourist03")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")

CATALOG_TABLES = [
    (
        "camps",
        "catalog.camps",
        [
            "id",
            "name",
            "lat",
            "lng",
            "min_price",
            "emoji",
            "lake_name",
            "photo_main",
            "status",
            "owner",
            "manager",
            "admin_phones",
            "rooms_count",
            "beds_count",
            "address",
            "phone",
            "site_url",
            "emoji_size",
            "bbq_count",
            "bbq_shared_count",
            "bath_count",
            "sauna_count",
            "pools_private_count",
            "pools_shared_count",
            "description",
        ],
    ),
    (
        "rooms",
        "catalog.rooms",
        [
            "id",
            "camp_id",
            "name",
            "room_type",
            "floors",
            "floor",
            "beds_single",
            "beds_double",
            "wc_count",
            "bath_type",
            "has_ac",
            "has_bbq",
            "has_kitchen",
            "capacity",
            "price",
            "photo_main",
            "photos_json",
            "description",
            "price_adult",
            "price_child",
            "discount_pct",
            "discount_from_nights",
            "wc_type",
            "bbq_type",
            "kitchen_type",
            "gazebo_type",
            "terrace_type",
            "balcony_type",
            "pool_type",
        ],
    ),
    (
        "camp_photos",
        "catalog.camp_photos",
        ["id", "camp_id", "url", "sort", "cover"],
    ),
    (
        "room_photos",
        "catalog.room_photos",
        ["id", "camp_id", "room_id", "url", "cover", "sort"],
    ),
]

AUTH_TABLES = [
    (
        "users",
        "auth.users",
        ["id", "name", "phone", "role"],
    ),
]


def _sqlite_conn(name: str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(BASE_DIR / "db" / name))
    conn.row_factory = sqlite3.Row
    return conn


def _pg_conn(schema: str):
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )
    with conn.cursor() as cur:
        cur.execute("SET search_path TO %s", (schema,))
    return conn


def _fetch_rows(sql_conn: sqlite3.Connection, table: str) -> list[dict]:
    cur = sql_conn.execute(f"SELECT * FROM {table}")
    return [dict(row) for row in cur.fetchall()]


def _insert_rows(pg_conn, target: str, columns: list[str], rows: list[dict]):
    if not rows:
        print(f"[skip] {target}: no rows to migrate")
        return
    payload = [[row.get(col) for col in columns] for row in rows]
    placeholders = ",".join(["%s"] * len(columns))
    columns_sql = ",".join([f'"{col}"' for col in columns])
    sql = f"INSERT INTO {target} ({columns_sql}) VALUES ({placeholders})"
    with pg_conn.cursor() as cur:
        execute_batch(cur, sql, payload, page_size=500)
    pg_conn.commit()
    print(f"[ok] inserted {len(rows)} rows into {target}")


def _reset_sequences(pg_conn, tables: list[str]):
    with pg_conn.cursor() as cur:
        for tbl in tables:
            cur.execute(
                f"""
                SELECT setval(
                    pg_get_serial_sequence(%s, 'id'),
                    COALESCE((SELECT MAX(id) FROM {tbl}), 0),
                    COALESCE((SELECT MAX(id) FROM {tbl}), 0) <> 0
                )
                """,
                (tbl,),
            )
    pg_conn.commit()


def migrate_catalog():
    sqlite_conn = _sqlite_conn("camps.db")
    pg_conn = _pg_conn("catalog")
    try:
        with pg_conn.cursor() as cur:
            for _, target, _ in reversed(CATALOG_TABLES):
                cur.execute(f"DELETE FROM {target}")
        pg_conn.commit()
        print("[info] catalog tables cleared")
        for source, target, columns in CATALOG_TABLES:
            rows = _fetch_rows(sqlite_conn, source)
            _insert_rows(pg_conn, target, columns, rows)
        _reset_sequences(pg_conn, [target for _, target, _ in CATALOG_TABLES])
    finally:
        sqlite_conn.close()
        pg_conn.close()


def migrate_auth():
    sqlite_conn = _sqlite_conn("users.db")
    pg_conn = _pg_conn("auth")
    try:
        with pg_conn.cursor() as cur:
            for _, target, _ in reversed(AUTH_TABLES):
                cur.execute(f"DELETE FROM {target}")
        pg_conn.commit()
        print("[info] auth tables cleared")
        for source, target, columns in AUTH_TABLES:
            rows = _fetch_rows(sqlite_conn, source)
            _insert_rows(pg_conn, target, columns, rows)
        _reset_sequences(pg_conn, [target for _, target, _ in AUTH_TABLES])
    finally:
        sqlite_conn.close()
        pg_conn.close()


def main():
    migrate_catalog()
    migrate_auth()
    print("[done] Migration complete")


if __name__ == "__main__":
    main()
