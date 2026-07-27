#!/usr/bin/env python3
"""Measure the first Owner Portal dashboard response against PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx

import app as app_module
from tourist03 import owner_security
from tourist03.db import _db_conn
from tourist03.migrations import run_migrations
from tourist03.owner_security import hash_owner_password
from tourist03.repositories import owners as owner_repo
from tourist03.security import hash_password
from tourist03.settings import Settings, configure_settings
from tests.postgres_harness import TemporaryPostgres


def settings_for_profile():
    if os.getenv("PG_INTEGRATION_USE_EXISTING", "").lower() in {"1", "true", "yes", "on"}:
        return Settings(
            environment="test",
            pg_host=os.environ["PG_HOST"],
            pg_port=int(os.environ["PG_PORT"]),
            pg_db=os.environ["PG_DB"],
            pg_user=os.environ["PG_USER"],
            pg_password=os.environ.get("PG_PASSWORD", ""),
            feature_owner_portal=True,
            feature_owner_change_requests=True,
        ), None
    postgres = TemporaryPostgres()
    postgres.start()
    return Settings(
        environment="test",
        pg_host="127.0.0.1",
        pg_port=postgres.port,
        pg_db="postgres",
        pg_user="postgres",
        pg_password="",
        feature_owner_portal=True,
        feature_owner_change_requests=True,
    ), postgres


def seed_profile_data():
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO catalog.camps (
                name, slug, place_type_id, publication_status, status,
                short_description, description, lat, lng, min_price,
                seasonality, working_hours, content_version
            )
            VALUES (
                'Профиль производительности', 'owner-performance-profile', 1,
                'published', 'active', 'Краткое описание',
                %s, 53.1, 107.2, 6500, 'Круглый год', %s::jsonb, 1
            )
            RETURNING id
            """,
            ("Подробное описание объекта. " * 8, json.dumps("Ежедневно", ensure_ascii=False)),
        )
        camp_id = int(cur.fetchone()["id"])
        cur.execute(
            """
            INSERT INTO auth.superadmin_accounts (
                login, password_hash, display_name, is_active, is_root
            )
            VALUES ('owner-performance-reviewer', %s, 'Профиль', TRUE, TRUE)
            RETURNING id
            """,
            (hash_password("ReviewerPassword123"),),
        )
        superadmin_id = int(cur.fetchone()["id"])
        cur.execute(
            """
            INSERT INTO catalog.place_contacts (
                camp_id, contact_type, label, value, normalized_value,
                public_url, is_public, sort_order
            )
            VALUES (
                %s, 'phone', 'Телефон', '+79990001122', '+79990001122',
                'tel:+79990001122', TRUE, 10
            )
            """,
            (camp_id,),
        )
        cur.execute(
            """
            INSERT INTO catalog.rooms (camp_id, name, price, description)
            VALUES (%s, 'Дом', 6500, 'Дом с террасой')
            """,
            (camp_id,),
        )
        cur.execute(
            """
            INSERT INTO catalog.camp_media (
                camp_id, media_type, url, source_kind, moderation_status, cover, sort
            )
            VALUES (%s, 'image', '/static/uploads/performance.jpg', 'admin', 'approved', TRUE, 0)
            """,
            (camp_id,),
        )
        conn.commit()
    owner = owner_repo.create_owner_account(
        email="owner-performance@example.com",
        password_hash=hash_owner_password("OwnerPassword123"),
        display_name="Владелец профиля",
    )
    owner_repo.link_owner_camp(
        owner_id=owner["id"],
        camp_id=camp_id,
        role_key="primary_owner",
        is_primary=True,
        superadmin_id=superadmin_id,
    )
    change, _ = owner_repo.create_owner_change(owner["id"], camp_id)
    saved = owner_repo.save_owner_change(
        change["id"],
        owner["id"],
        {"short_description": "Обновлённое краткое описание"},
        expected_version=change["content_version"],
    )
    owner_repo.transition_owner_change(
        saved["id"],
        target="submitted",
        actor_type="owner",
        actor_id=owner["id"],
        owner_id=owner["id"],
    )
    return owner, camp_id


def explain_indexes(owner_id: int) -> list[str]:
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            EXPLAIN (FORMAT JSON)
            SELECT camp_id
            FROM catalog.camp_owner_links
            WHERE owner_account_id = %s
            ORDER BY camp_id
            """,
            (owner_id,),
        )
        plan = cur.fetchone()["QUERY PLAN"][0]["Plan"]

    names: list[str] = []

    def walk(node):
        if node.get("Index Name"):
            names.append(node["Index Name"])
        for child in node.get("Plans", []):
            walk(child)

    walk(plan)
    return sorted(set(names))


async def profile(settings: Settings, owner: dict, camp_id: int) -> dict:
    application = app_module.create_app(settings)
    connection_count = 0
    original_owner_conn = owner_repo._db_conn
    original_security_conn = owner_security._db_conn

    @contextmanager
    def counted_owner_conn(schema):
        nonlocal connection_count
        connection_count += 1
        with original_owner_conn(schema) as conn:
            yield conn

    @contextmanager
    def counted_security_conn(schema):
        nonlocal connection_count
        connection_count += 1
        with original_security_conn(schema) as conn:
            yield conn

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        login = await client.post(
            "/api/owner/auth/login",
            json={"email": owner["email"], "password": "OwnerPassword123"},
        )
        if login.status_code != 200:
            raise RuntimeError(login.text)
        with (
            patch.object(owner_repo, "_db_conn", counted_owner_conn),
            patch.object(owner_security, "_db_conn", counted_security_conn),
        ):
            started = time.perf_counter()
            response = await client.get("/api/owner/dashboard")
            elapsed_ms = (time.perf_counter() - started) * 1000
    if response.status_code != 200:
        raise RuntimeError(response.text)
    payload = response.json()
    return {
        "endpoint": "/api/owner/dashboard",
        "elapsed_ms": round(elapsed_ms, 2),
        "sql_query_count": connection_count,
        "response_bytes": len(response.content),
        "objects_returned": len(payload["camps"]),
        "activity_limit": 7,
        "contains_full_history": "changes" in payload,
        "contains_notifications": "notifications" in payload,
        "contains_proposed_payload": any("proposed_payload" in item for item in payload["pending_changes"]),
        "contains_full_diff": any("diff_payload" in item for item in payload["pending_changes"]),
        "contains_media_urls": "performance.jpg" in response.text,
        "owner_isolation": all(item["id"] == camp_id for item in payload["camps"]),
        "cache_control": response.headers.get("cache-control"),
        "indexes": explain_indexes(owner["id"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    settings, postgres = settings_for_profile()
    try:
        configure_settings(settings)
        run_migrations()
        owner, camp_id = seed_profile_data()
        result = asyncio.run(profile(settings, owner, camp_id))
    finally:
        configure_settings(None)
        if postgres:
            postgres.stop()
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
