"""PostgreSQL persistence for Owner Portal identities and moderated changes."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from tourist03.db import _db_conn
from tourist03.domain.owner_changes import (
    OwnerChangeValidationError,
    build_owner_diff,
    ensure_owner_status_transition,
    merged_owner_snapshot,
    new_owner_change_number,
    owner_status_label,
    resolve_owner_room_media_target,
)
from tourist03.owner_security import hash_owner_token, owner_reset_token_for
from tourist03.repositories import catalog as catalog_repo


CAMP_COLUMNS = (
    "name",
    "short_description",
    "description",
    "region",
    "district",
    "city",
    "locality",
    "address",
    "lat",
    "lng",
    "min_price",
    "price_mode",
    "currency",
    "seasonality",
    "seasonality_key",
    "working_hours",
    "working_hours_mode",
    "attributes",
    "seo",
    "video_urls",
)
JSON_CAMP_COLUMNS = frozenset({"working_hours", "attributes", "seo", "video_urls"})
EDITABLE_REQUEST_STATUSES = frozenset({"draft", "needs_changes", "withdrawn"})


def _dict(row) -> dict | None:
    return dict(row) if row else None


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def get_owner_by_email(email: str) -> dict | None:
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM auth.owner_accounts WHERE lower(email) = lower(%s) LIMIT 1",
            (email,),
        )
        return _dict(cur.fetchone())


def get_owner_by_id(owner_id: int) -> dict | None:
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM auth.owner_accounts WHERE id = %s", (int(owner_id),))
        return _dict(cur.fetchone())


def log_owner_login(
    *,
    owner_id: int | None,
    email_hash: str | None,
    event_type: str,
    success: bool,
    ip_hash: str | None,
    user_agent_hash: str | None,
) -> None:
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO auth.owner_login_events (
                owner_account_id, email_hash, event_type, success, ip_hash, user_agent_hash
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (owner_id, email_hash, event_type, bool(success), ip_hash, user_agent_hash),
        )
        if success and owner_id:
            cur.execute(
                "UPDATE auth.owner_accounts SET last_login = NOW() WHERE id = %s",
                (int(owner_id),),
            )
        conn.commit()


def rehash_owner_password(owner_id: int, password_hash: str) -> None:
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE auth.owner_accounts SET password_hash = %s WHERE id = %s",
            (password_hash, int(owner_id)),
        )
        conn.commit()


def update_owner_profile(owner_id: int, changes: dict[str, Any]) -> dict | None:
    allowed = {
        "display_name",
        "company",
        "phone",
        "telegram",
        "whatsapp",
        "max",
        "preferred_contact_type",
    }
    normalized = {key: value for key, value in changes.items() if key in allowed}
    if not normalized:
        return get_owner_by_id(owner_id)
    assignments, params = [], []
    for key, value in normalized.items():
        assignments.append(f"{key} = %s")
        params.append(value)
    params.append(int(owner_id))
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE auth.owner_accounts SET {', '.join(assignments)} WHERE id = %s RETURNING *",
            tuple(params),
        )
        row = cur.fetchone()
        conn.commit()
        return _dict(row)


def update_owner_password(owner_id: int, password_hash: str) -> None:
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE auth.owner_accounts SET password_hash = %s WHERE id = %s",
            (password_hash, int(owner_id)),
        )
        conn.commit()


def create_owner_reset(
    *,
    owner_id: int,
    requested_ip_hash: str | None,
    ttl_minutes: int,
    secret: str,
    public_base_url: str,
) -> tuple[dict, str]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=max(int(ttl_minutes), 5))
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.owner_password_reset_tokens
            SET used_at = COALESCE(used_at, NOW())
            WHERE owner_account_id = %s AND used_at IS NULL
            """,
            (int(owner_id),),
        )
        cur.execute(
            """
            INSERT INTO auth.owner_password_reset_tokens (
                owner_account_id, token_hash, requested_ip_hash, expires_at
            )
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (int(owner_id), f"pending:{owner_id}:{expires_at.timestamp()}", requested_ip_hash, expires_at),
        )
        reset = dict(cur.fetchone())
        token = owner_reset_token_for(reset["id"], int(owner_id), expires_at, secret)
        token_hash = hash_owner_token(token, secret)
        cur.execute(
            "UPDATE auth.owner_password_reset_tokens SET token_hash = %s WHERE id = %s",
            (token_hash, reset["id"]),
        )
        cur.execute(
            """
            INSERT INTO crm.notification_events (
                owner_account_id, recipient_scope, channel, event_type,
                title, body, action_url, action_payload, severity, status,
                recipient_address, dedupe_key
            )
            SELECT
                accounts.id, 'owner', 'email', 'owner_password_reset_requested',
                'Восстановление доступа',
                'Откройте ссылку, чтобы задать новый пароль. Ссылка действует ограниченное время.',
                %s,
                %s::jsonb,
                'info',
                'new',
                accounts.email,
                %s
            FROM auth.owner_accounts accounts
            WHERE accounts.id = %s
            """,
            (
                f"{public_base_url.rstrip('/')}/owner/reset-password",
                _json(
                    {
                        "reset_id": reset["id"],
                        "owner_id": owner_id,
                        "expires_at": expires_at.isoformat(),
                    }
                ),
                f"owner-reset:{reset['id']}",
                int(owner_id),
            ),
        )
        conn.commit()
        reset["token_hash"] = token_hash
        return reset, token


def consume_owner_reset(*, token_hash: str, password_hash: str) -> int | None:
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM auth.owner_password_reset_tokens
            WHERE token_hash = %s
              AND used_at IS NULL
              AND expires_at > NOW()
            LIMIT 1
            FOR UPDATE
            """,
            (token_hash,),
        )
        reset = cur.fetchone()
        if not reset:
            return None
        owner_id = int(reset["owner_account_id"])
        cur.execute(
            """
            UPDATE auth.owner_accounts
            SET password_hash = %s
            WHERE id = %s AND is_active = TRUE
            """,
            (password_hash, owner_id),
        )
        if cur.rowcount != 1:
            return None
        cur.execute(
            """
            UPDATE auth.owner_password_reset_tokens
            SET used_at = NOW()
            WHERE owner_account_id = %s AND used_at IS NULL
            """,
            (owner_id,),
        )
        conn.commit()
        return owner_id


def _snapshot_with_cursor(cur, camp_id: int, *, lock: bool = False) -> dict | None:
    lock_sql = " FOR UPDATE OF camps" if lock else ""
    cur.execute(
        f"""
        SELECT
            camps.id, camps.name, camps.slug, camps.place_type_id,
            types.slug AS subtype, kinds.slug AS entity_kind,
            camps.schema_key, camps.schema_version,
            camps.short_description, camps.description,
            camps.region, camps.district, camps.city, camps.locality,
            camps.address, camps.lat, camps.lng, camps.min_price,
            camps.price_mode, camps.currency, camps.seasonality,
            camps.seasonality_key, camps.working_hours, camps.working_hours_mode,
            camps.attributes, camps.seo, camps.video_urls,
            camps.publication_status, camps.visibility,
            camps.status, camps.confirmed_at, camps.updated_at, camps.content_version,
            COALESCE(camps.metadata, '{{}}'::jsonb) AS metadata
        FROM catalog.camps camps
        JOIN catalog.place_types types ON types.id = camps.place_type_id
        JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
        WHERE camps.id = %s{lock_sql}
        """,
        (int(camp_id),),
    )
    row = cur.fetchone()
    if not row:
        return None
    snapshot = dict(row)
    metadata = snapshot.pop("metadata") or {}
    snapshot["surroundings"] = metadata.get("surroundings")
    cur.execute(
        """
        SELECT contact_type, label, value, public_url AS url, is_public, sort_order
        FROM catalog.place_contacts
        WHERE camp_id = %s ORDER BY sort_order, id
        """,
        (int(camp_id),),
    )
    snapshot["contacts"] = [dict(item) for item in cur.fetchall()]
    cur.execute(
        """
        SELECT amenity_id, value
        FROM catalog.camp_amenities
        WHERE camp_id = %s ORDER BY amenity_id
        """,
        (int(camp_id),),
    )
    snapshot["amenities"] = [dict(item) for item in cur.fetchall()]
    cur.execute(
        """
        SELECT
            id, name, room_type, floors, floor, beds_single, beds_double,
            wc_count, bath_type, has_ac, has_bbq, has_kitchen, capacity,
            price, description, price_adult, price_child, discount_pct,
            discount_from_nights, wc_type, bbq_type, kitchen_type, gazebo_type,
            terrace_type, balcony_type, pool_type
        FROM catalog.rooms
        WHERE camp_id = %s ORDER BY id
        """,
        (int(camp_id),),
    )
    snapshot["rooms"] = [dict(item) for item in cur.fetchall()]
    cur.execute(
        """
        SELECT id, media_type, url, poster_url, alt_text, caption, cover, sort
        FROM catalog.camp_media
        WHERE camp_id = %s
        ORDER BY cover DESC, sort, id
        """,
        (int(camp_id),),
    )
    snapshot["media"] = [dict(item) for item in cur.fetchall()]
    return snapshot


def get_camp_snapshot(camp_id: int) -> dict | None:
    with _db_conn("catalog") as conn:
        return _snapshot_with_cursor(conn.cursor(), camp_id)


def get_camp_snapshots(camp_ids: Iterable[int]) -> dict[int, dict]:
    normalized = sorted({int(camp_id) for camp_id in camp_ids})
    if not normalized:
        return {}
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                camps.id, camps.name, camps.slug, camps.place_type_id,
                types.slug AS subtype, kinds.slug AS entity_kind,
                camps.schema_key, camps.schema_version,
                camps.short_description, camps.description,
                camps.region, camps.district, camps.city, camps.locality,
                camps.address, camps.lat, camps.lng, camps.min_price,
                camps.price_mode, camps.currency, camps.seasonality,
                camps.seasonality_key, camps.working_hours, camps.working_hours_mode,
                camps.attributes, camps.seo, camps.video_urls,
                camps.publication_status, camps.visibility,
                camps.status, camps.confirmed_at, camps.updated_at, camps.content_version,
                COALESCE(camps.metadata, '{}'::jsonb) AS metadata
            FROM catalog.camps camps
            JOIN catalog.place_types types ON types.id = camps.place_type_id
            JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            WHERE camps.id = ANY(%s)
            """,
            (normalized,),
        )
        result: dict[int, dict] = {}
        for raw in cur.fetchall():
            row = dict(raw)
            camp_id = int(row["id"])
            metadata = row.pop("metadata") or {}
            row["surroundings"] = metadata.get("surroundings")
            row.update({"contacts": [], "amenities": [], "rooms": [], "media": []})
            result[camp_id] = row
        if not result:
            return {}

        for target, query in (
            (
                "contacts",
                """
                SELECT camp_id, contact_type, label, value, public_url AS url, is_public, sort_order
                FROM catalog.place_contacts WHERE camp_id = ANY(%s)
                ORDER BY camp_id, sort_order, id
                """,
            ),
            (
                "amenities",
                """
                SELECT camp_id, amenity_id, value
                FROM catalog.camp_amenities WHERE camp_id = ANY(%s)
                ORDER BY camp_id, amenity_id
                """,
            ),
            (
                "rooms",
                """
                SELECT
                    id, camp_id, name, room_type, floors, floor, beds_single, beds_double,
                    wc_count, bath_type, has_ac, has_bbq, has_kitchen, capacity,
                    price, description, price_adult, price_child, discount_pct,
                    discount_from_nights, wc_type, bbq_type, kitchen_type, gazebo_type,
                    terrace_type, balcony_type, pool_type
                FROM catalog.rooms WHERE camp_id = ANY(%s)
                ORDER BY camp_id, id
                """,
            ),
            (
                "media",
                """
                SELECT camp_id, id, media_type, url, poster_url, alt_text, caption, cover, sort
                FROM catalog.camp_media WHERE camp_id = ANY(%s)
                ORDER BY camp_id, cover DESC, sort, id
                """,
            ),
        ):
            cur.execute(query, (normalized,))
            for raw in cur.fetchall():
                item = dict(raw)
                camp_id = int(item.pop("camp_id"))
                if camp_id in result:
                    result[camp_id][target].append(item)
        return result


def get_camp_quality_snapshots(camp_ids: Iterable[int]) -> dict[int, dict]:
    """Load only the fields required by dashboard quality calculations.

    The query is independent of the number of camps and deliberately excludes
    media URLs, captions, room photos and other editor/detail payloads.
    """

    normalized = sorted({int(camp_id) for camp_id in camp_ids})
    if not normalized:
        return {}
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            WITH contact_summary AS (
                SELECT
                    camp_id,
                    jsonb_agg(
                        jsonb_build_object(
                            'contact_type', contact_type,
                            'value', value
                        )
                        ORDER BY sort_order, id
                    ) AS contacts
                FROM catalog.place_contacts
                WHERE camp_id = ANY(%s)
                GROUP BY camp_id
            ),
            amenity_summary AS (
                SELECT
                    camp_id,
                    jsonb_agg(jsonb_build_object('amenity_id', amenity_id)) AS amenities
                FROM catalog.camp_amenities
                WHERE camp_id = ANY(%s)
                GROUP BY camp_id
            ),
            room_summary AS (
                SELECT
                    camp_id,
                    jsonb_agg(
                        jsonb_build_object(
                            'description', description,
                            'price', price
                        )
                        ORDER BY id
                    ) AS rooms
                FROM catalog.rooms
                WHERE camp_id = ANY(%s)
                GROUP BY camp_id
            ),
            media_summary AS (
                SELECT
                    camp_id,
                    jsonb_agg(
                        jsonb_build_object(
                            'media_type', media_type,
                            'cover', cover
                        )
                        ORDER BY cover DESC, sort, id
                    ) AS media
                FROM catalog.camp_media
                WHERE camp_id = ANY(%s)
                GROUP BY camp_id
            )
            SELECT
                camps.id, camps.name, camps.short_description, camps.description,
                camps.lat, camps.lng, camps.min_price, camps.seasonality,
                camps.price_mode, camps.attributes,
                kinds.slug AS entity_kind,
                camps.schema_key, camps.schema_version,
                camps.working_hours, camps.video_urls, camps.confirmed_at,
                camps.updated_at,
                COALESCE(camps.metadata, '{}'::jsonb)->>'surroundings' AS surroundings,
                COALESCE(contact_summary.contacts, '[]'::jsonb) AS contacts,
                COALESCE(amenity_summary.amenities, '[]'::jsonb) AS amenities,
                COALESCE(room_summary.rooms, '[]'::jsonb) AS rooms,
                COALESCE(media_summary.media, '[]'::jsonb) AS media
            FROM catalog.camps camps
            JOIN catalog.place_types types ON types.id = camps.place_type_id
            JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            LEFT JOIN contact_summary ON contact_summary.camp_id = camps.id
            LEFT JOIN amenity_summary ON amenity_summary.camp_id = camps.id
            LEFT JOIN room_summary ON room_summary.camp_id = camps.id
            LEFT JOIN media_summary ON media_summary.camp_id = camps.id
            WHERE camps.id = ANY(%s)
            """,
            (normalized, normalized, normalized, normalized, normalized),
        )
        return {int(row["id"]): dict(row) for row in cur.fetchall()}


def owner_can_access_camp(owner_id: int, camp_id: int, *, write: bool = False, conn=None) -> bool:
    owns = conn is None
    if owns:
        context = _db_conn("catalog")
        conn = context.__enter__()
    try:
        cur = conn.cursor()
        roles = ("primary_owner", "owner", "representative", "manager", "editor")
        cur.execute(
            """
            SELECT role_key
            FROM catalog.camp_owner_links
            WHERE owner_account_id = %s AND camp_id = %s
            """,
            (int(owner_id), int(camp_id)),
        )
        row = cur.fetchone()
        return bool(row and (not write or row["role_key"] in roles))
    finally:
        if owns:
            context.__exit__(None, None, None)


def list_owner_camps(
    owner_id: int,
    *,
    limit: int = 20,
    offset: int = 0,
    entity_kind: str | None = None,
) -> list[dict]:
    clauses = ["links.owner_account_id = %s"]
    params: list[Any] = [int(owner_id)]
    if entity_kind:
        clauses.append("kinds.slug = %s")
        params.append(str(entity_kind).strip().lower())
    params.extend(
        (
            min(max(int(limit), 1), 100),
            max(int(offset), 0),
        )
    )
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                camps.id, camps.name, camps.slug, camps.publication_status,
                camps.status, camps.updated_at, camps.confirmed_at,
                types.name AS place_type_name, types.slug AS subtype,
                kinds.slug AS entity_kind, kinds.name AS entity_kind_name,
                camps.schema_key, camps.schema_version,
                links.role_key, links.is_primary,
                COUNT(changes.id) FILTER (
                    WHERE changes.status IN ('submitted', 'in_review', 'needs_changes', 'approved')
                )::int AS pending_changes
            FROM catalog.camp_owner_links links
            JOIN catalog.camps camps ON camps.id = links.camp_id
            LEFT JOIN catalog.place_types types ON types.id = camps.place_type_id
            LEFT JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            LEFT JOIN moderation.owner_change_requests changes
              ON changes.camp_id = camps.id
             AND changes.owner_account_id = links.owner_account_id
            WHERE {' AND '.join(clauses)}
            GROUP BY camps.id, types.name, types.slug, kinds.slug, kinds.name,
                     links.role_key, links.is_primary
            ORDER BY links.is_primary DESC, lower(camps.name), camps.id
            LIMIT %s OFFSET %s
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def owner_profile_statistics(owner_id: int, *, entity_kind: str | None = None) -> dict:
    kind_clause = "AND kinds.slug = %s" if entity_kind else ""
    params: tuple[Any, ...] = (
        (int(owner_id), str(entity_kind).strip().lower())
        if entity_kind
        else (int(owner_id),)
    )
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                COUNT(DISTINCT links.camp_id)::int AS objects_count,
                COUNT(DISTINCT changes.id) FILTER (WHERE changes.status IN ('approved', 'applied'))::int AS approved_changes,
                COUNT(DISTINCT changes.id) FILTER (WHERE changes.status IN ('submitted', 'in_review', 'needs_changes'))::int AS pending_changes,
                COUNT(DISTINCT changes.id) FILTER (WHERE changes.status = 'rejected')::int AS rejected_changes
            FROM auth.owner_accounts accounts
            LEFT JOIN catalog.camp_owner_links links ON links.owner_account_id = accounts.id
            LEFT JOIN catalog.camps camps ON camps.id = links.camp_id
            LEFT JOIN catalog.place_types types ON types.id = camps.place_type_id
            LEFT JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            LEFT JOIN moderation.owner_change_requests changes
              ON changes.owner_account_id = accounts.id
             AND changes.camp_id = links.camp_id
            WHERE accounts.id = %s
              {kind_clause}
            """,
            params,
        )
        return dict(cur.fetchone())


def list_owner_activity(
    owner_id: int,
    *,
    limit: int = 30,
    entity_kind: str | None = None,
) -> list[dict]:
    kind_clause = (
        "AND (audit.camp_id IS NULL OR kinds.slug = %s)"
        if entity_kind
        else ""
    )
    params: list[Any] = [int(owner_id), int(owner_id)]
    if entity_kind:
        params.append(str(entity_kind).strip().lower())
    params.append(min(max(int(limit), 1), 100))
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                audit.id, audit.created_at, audit.action_type AS type,
                audit.action_label AS description, audit.camp_id,
                audit.target_id, audit.metadata,
                CASE
                    WHEN audit.target_type = 'owner_change_request'
                    THEN '/owner/changes/' || audit.target_id
                    ELSE NULL
                END AS action_url
            FROM crm.audit_log audit
            LEFT JOIN catalog.camps camps ON camps.id = audit.camp_id
            LEFT JOIN catalog.place_types types ON types.id = camps.place_type_id
            LEFT JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            WHERE (
                (audit.actor_type = 'owner' AND audit.actor_id = %s)
                OR (
                    audit.camp_id IN (
                        SELECT camp_id
                        FROM catalog.camp_owner_links
                        WHERE owner_account_id = %s
                    )
                    AND (
                        audit.target_type = 'owner_change_request'
                        OR audit.action_type IN ('owner_camp_unpublished', 'owner_change_applied')
                    )
                )
            )
            {kind_clause}
            ORDER BY audit.created_at DESC, audit.id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def list_owner_changes(owner_id: int, *, camp_id: int | None = None) -> list[dict]:
    clauses, params = ["changes.owner_account_id = %s"], [int(owner_id)]
    if camp_id is not None:
        clauses.append("changes.camp_id = %s")
        params.append(int(camp_id))
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT changes.*, camps.name AS camp_name, camps.slug AS camp_slug
            FROM moderation.owner_change_requests changes
            JOIN catalog.camps camps ON camps.id = changes.camp_id
            WHERE {' AND '.join(clauses)}
            ORDER BY changes.updated_at DESC, changes.id DESC
            """,
            tuple(params),
        )
        rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row["status_label"] = owner_status_label(row["status"])
    return rows


def list_owner_change_summaries(
    owner_id: int,
    *,
    camp_id: int | None = None,
    statuses: Iterable[str] | None = None,
    entity_kind: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> list[dict]:
    """Return moderation-history rows without proposed/published JSON payloads."""

    clauses, params = ["changes.owner_account_id = %s"], [int(owner_id)]
    if camp_id is not None:
        clauses.append("changes.camp_id = %s")
        params.append(int(camp_id))
    if entity_kind:
        clauses.append("kinds.slug = %s")
        params.append(str(entity_kind).strip().lower())
    normalized_statuses = sorted({str(status) for status in statuses or [] if status})
    if normalized_statuses:
        clauses.append("changes.status = ANY(%s)")
        params.append(normalized_statuses)
    params.extend((min(max(int(limit), 1), 100), max(int(offset), 0)))
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                changes.id, changes.public_number, changes.camp_id,
                camps.name AS camp_name, camps.slug AS camp_slug,
                types.slug AS subtype, kinds.slug AS entity_kind,
                changes.schema_key, changes.schema_version,
                changes.status, changes.content_version,
                changes.moderator_comment, changes.submitted_at,
                changes.decided_at, changes.updated_at, changes.created_at,
                COALESCE(jsonb_array_length(changes.diff_payload), 0)::int AS diff_count
            FROM moderation.owner_change_requests changes
            JOIN catalog.camps camps ON camps.id = changes.camp_id
            JOIN catalog.place_types types ON types.id = camps.place_type_id
            JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            WHERE {' AND '.join(clauses)}
            ORDER BY changes.updated_at DESC, changes.id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params),
        )
        rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row["status_label"] = owner_status_label(row["status"])
    return rows


def count_owner_changes(
    owner_id: int,
    *,
    camp_id: int | None = None,
    entity_kind: str | None = None,
) -> int:
    clauses, params = ["changes.owner_account_id = %s"], [int(owner_id)]
    if camp_id is not None:
        clauses.append("changes.camp_id = %s")
        params.append(int(camp_id))
    if entity_kind:
        clauses.append("kinds.slug = %s")
        params.append(str(entity_kind).strip().lower())
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT COUNT(*)::int AS count
            FROM moderation.owner_change_requests changes
            JOIN catalog.camps camps ON camps.id = changes.camp_id
            JOIN catalog.place_types types ON types.id = camps.place_type_id
            JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            WHERE {' AND '.join(clauses)}
            """,
            tuple(params),
        )
        return int(cur.fetchone()["count"])


def get_owner_change(
    change_id: int,
    *,
    owner_id: int | None = None,
    lock: bool = False,
    conn=None,
) -> dict | None:
    owns = conn is None
    if owns:
        context = _db_conn("moderation")
        conn = context.__enter__()
    try:
        clauses, params = ["changes.id = %s"], [int(change_id)]
        if owner_id is not None:
            clauses.append("changes.owner_account_id = %s")
            params.append(int(owner_id))
        suffix = " FOR UPDATE OF changes" if lock else ""
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT changes.*, camps.name AS camp_name, camps.slug AS camp_slug,
                   types.slug AS subtype, kinds.slug AS entity_kind,
                   owners.display_name AS owner_name, owners.email AS owner_email,
                   COALESCE(reviewers.display_name, reviewers.login) AS moderator_name
            FROM moderation.owner_change_requests changes
            JOIN catalog.camps camps ON camps.id = changes.camp_id
            JOIN catalog.place_types types ON types.id = camps.place_type_id
            JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            JOIN auth.owner_accounts owners ON owners.id = changes.owner_account_id
            LEFT JOIN auth.superadmin_accounts reviewers ON reviewers.id = changes.moderator_account_id
            WHERE {' AND '.join(clauses)}
            LIMIT 1{suffix}
            """,
            tuple(params),
        )
        row = _dict(cur.fetchone())
        if not row:
            return None
        cur.execute(
            """
            SELECT *
            FROM moderation.owner_change_request_history
            WHERE change_request_id = %s ORDER BY created_at DESC, id DESC
            """,
            (int(change_id),),
        )
        row["history"] = [dict(item) for item in cur.fetchall()]
        cur.execute(
            """
            SELECT *
            FROM moderation.owner_change_request_media
            WHERE change_request_id = %s AND deleted_at IS NULL
            ORDER BY scope, room_client_id, sort_order, id
            """,
            (int(change_id),),
        )
        row["staged_media"] = [dict(item) for item in cur.fetchall()]
        row["status_label"] = owner_status_label(row["status"])
        return row
    finally:
        if owns:
            context.__exit__(None, None, None)


def create_owner_entity(
    *,
    owner_id: int,
    entity_kind: str,
    subtype: str,
    name: str,
    proposed_payload: dict,
) -> tuple[dict, dict]:
    """Create an invisible storage row and its first moderated change atomically."""

    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                types.id AS place_type_id,
                types.default_schema_key AS schema_key,
                types.default_schema_version AS schema_version,
                kinds.slug AS entity_kind
            FROM catalog.place_types types
            JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            WHERE types.slug = %s
              AND kinds.slug = %s
              AND types.is_active = TRUE
              AND kinds.is_active = TRUE
            LIMIT 1
            """,
            (subtype, entity_kind),
        )
        catalog_type = cur.fetchone()
        if not catalog_type:
            raise ValueError("Выбранный тип сущности недоступен")

        cur.execute(
            """
            SELECT
                nextval(pg_get_serial_sequence('catalog.camps', 'id'))::int AS id,
                catalog.slugify_place_name(%s) AS base_slug
            """,
            (name,),
        )
        identity = cur.fetchone()
        entity_id = int(identity["id"])
        base_slug = str(identity["base_slug"])
        cur.execute("SELECT 1 FROM catalog.camps WHERE lower(slug) = lower(%s)", (base_slug,))
        slug = base_slug if not cur.fetchone() else f"{base_slug}-{entity_id}"
        is_accommodation = entity_kind == "accommodation"
        cur.execute(
            """
            INSERT INTO catalog.camps (
                id, name, slug, place_type_id, schema_key, schema_version,
                status, publication_status, visibility, is_visible_on_map,
                accepts_bookings, accepts_standalone_services,
                attributes, seo, price_mode, currency
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                'disabled', 'draft', 'hidden', FALSE,
                %s, %s,
                '{}'::jsonb, '{}'::jsonb, 'none', 'RUB'
            )
            RETURNING id, name, slug, publication_status, status, visibility,
                      schema_key, schema_version, content_version
            """,
            (
                entity_id,
                name,
                slug,
                int(catalog_type["place_type_id"]),
                catalog_type["schema_key"],
                int(catalog_type["schema_version"]),
                is_accommodation,
                not is_accommodation,
            ),
        )
        entity = dict(cur.fetchone())
        entity.update({"entity_kind": entity_kind, "subtype": subtype, "entity_id": entity_id})
        cur.execute(
            """
            INSERT INTO catalog.camp_owner_links (
                owner_account_id, camp_id, role_key, is_primary
            )
            VALUES (%s, %s, 'primary_owner', TRUE)
            RETURNING id
            """,
            (int(owner_id), entity_id),
        )
        number = new_owner_change_number()
        diff = build_owner_diff({}, proposed_payload)
        cur.execute(
            """
            INSERT INTO moderation.owner_change_requests (
                public_number, camp_id, owner_account_id, status,
                proposed_payload, published_snapshot, diff_payload,
                base_content_version, schema_key, schema_version
            )
            VALUES (%s, %s, %s, 'draft', %s::jsonb, '{}'::jsonb, %s::jsonb, %s, %s, %s)
            RETURNING *
            """,
            (
                number,
                entity_id,
                int(owner_id),
                _json(proposed_payload),
                _json(diff),
                int(entity["content_version"]),
                catalog_type["schema_key"],
                int(catalog_type["schema_version"]),
            ),
        )
        change = dict(cur.fetchone())
        _insert_history(
            cur,
            change["id"],
            None,
            "draft",
            "owner",
            owner_id,
            "Создана новая карточка",
            snapshot={"entity_kind": entity_kind, "subtype": subtype},
        )
        _insert_audit(
            cur,
            actor_type="owner",
            actor_id=owner_id,
            actor_display=None,
            camp_id=entity_id,
            target_type="owner_change_request",
            target_id=change["id"],
            action_type="owner_entity_created",
            action_label="Создана новая карточка",
            metadata={"public_number": number, "entity_kind": entity_kind, "subtype": subtype},
        )
        conn.commit()
    return entity, get_owner_change(change["id"], owner_id=owner_id)


def create_owner_change(owner_id: int, camp_id: int) -> tuple[dict, bool]:
    with _db_conn("moderation") as conn:
        if not owner_can_access_camp(owner_id, camp_id, write=True, conn=conn):
            return {}, False
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id
            FROM moderation.owner_change_requests
            WHERE owner_account_id = %s AND camp_id = %s
              AND status IN ('draft', 'needs_changes', 'withdrawn')
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (int(owner_id), int(camp_id)),
        )
        existing = cur.fetchone()
        if existing:
            return get_owner_change(existing["id"], owner_id=owner_id, conn=conn), False
        snapshot = _snapshot_with_cursor(cur, camp_id)
        if not snapshot:
            return {}, False
        for _ in range(8):
            number = new_owner_change_number()
            try:
                cur.execute(
                    """
                    INSERT INTO moderation.owner_change_requests (
                        public_number, camp_id, owner_account_id, status,
                        proposed_payload, published_snapshot, diff_payload,
                        base_content_version
                    )
                    VALUES (%s, %s, %s, 'draft', '{}'::jsonb, %s::jsonb, '[]'::jsonb, %s)
                    RETURNING *
                    """,
                    (number, int(camp_id), int(owner_id), _json(snapshot), int(snapshot["content_version"])),
                )
                row = dict(cur.fetchone())
                _insert_history(
                    cur,
                    row["id"],
                    None,
                    "draft",
                    "owner",
                    owner_id,
                    "Создан черновик изменений",
                    snapshot={},
                )
                _insert_audit(
                    cur,
                    actor_type="owner",
                    actor_id=owner_id,
                    actor_display=None,
                    camp_id=camp_id,
                    target_type="owner_change_request",
                    target_id=row["id"],
                    action_type="owner_change_created",
                    action_label="Создан черновик изменений",
                    metadata={"public_number": number},
                )
                conn.commit()
                return get_owner_change(row["id"], owner_id=owner_id), True
            except Exception as exc:
                if getattr(exc, "pgcode", None) == "23505":
                    conn.rollback()
                    continue
                raise
    raise RuntimeError("Не удалось создать номер изменений")


def save_owner_change(
    change_id: int,
    owner_id: int,
    proposed_payload: dict,
    *,
    expected_version: int,
) -> dict | None:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM moderation.owner_change_requests
            WHERE id = %s AND owner_account_id = %s
            FOR UPDATE
            """,
            (int(change_id), int(owner_id)),
        )
        row = cur.fetchone()
        if not row or row["status"] not in EDITABLE_REQUEST_STATUSES:
            return None
        if int(row["content_version"]) != int(expected_version):
            raise RuntimeError("Черновик изменился. Обновите страницу")
        diff = build_owner_diff(row["published_snapshot"] or {}, proposed_payload)
        cur.execute(
            """
            UPDATE moderation.owner_change_requests
            SET proposed_payload = %s::jsonb,
                diff_payload = %s::jsonb,
                status = 'draft'
            WHERE id = %s
            RETURNING *
            """,
            (_json(proposed_payload), _json(diff), int(change_id)),
        )
        _insert_audit(
            cur,
            actor_type="owner",
            actor_id=owner_id,
            actor_display=None,
            camp_id=row["camp_id"],
            target_type="owner_change_request",
            target_id=change_id,
            action_type="owner_change_saved",
            action_label="Сохранены изменения",
            metadata={"fields": [item["field"] for item in diff]},
        )
        conn.commit()
    return get_owner_change(change_id, owner_id=owner_id)


def transition_owner_change(
    change_id: int,
    *,
    target: str,
    actor_type: str,
    actor_id: int,
    owner_id: int | None = None,
    comment: str | None = None,
    proposed_payload: dict | None = None,
    expected_version: int | None = None,
) -> dict | None:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        clauses, params = ["id = %s"], [int(change_id)]
        if owner_id is not None:
            clauses.append("owner_account_id = %s")
            params.append(int(owner_id))
        cur.execute(
            f"SELECT * FROM moderation.owner_change_requests WHERE {' AND '.join(clauses)} FOR UPDATE",
            tuple(params),
        )
        raw_row = cur.fetchone()
        row = dict(raw_row) if raw_row else None
        if not row:
            return None
        next_diff = row["diff_payload"] or []
        if proposed_payload is not None:
            if target != "submitted" or actor_type != "owner":
                raise ValueError("Сохранение доступно только при отправке владельцем")
            if row["status"] not in EDITABLE_REQUEST_STATUSES:
                raise ValueError("Черновик уже недоступен для отправки")
            if expected_version is None or int(row["content_version"]) != int(expected_version):
                raise RuntimeError("Черновик изменился. Обновите страницу")
            next_diff = build_owner_diff(
                row["published_snapshot"] or {},
                proposed_payload,
            )
        ensure_owner_status_transition(row["status"], target, comment=comment)
        if target == "submitted" and not next_diff:
            cur.execute(
                """
                SELECT 1
                FROM moderation.owner_change_request_media
                WHERE change_request_id = %s
                  AND deleted_at IS NULL
                  AND status = 'staged'
                LIMIT 1
                """,
                (int(change_id),),
            )
            if not cur.fetchone():
                raise ValueError("Нет изменений для отправки")
        timestamp_columns = {
            "submitted": "submitted_at = NOW()",
            "approved": "decided_at = NOW()",
            "rejected": "decided_at = NOW()",
            "archived": "archived_at = NOW()",
        }
        extra = f", {timestamp_columns[target]}" if target in timestamp_columns else ""
        if proposed_payload is not None:
            cur.execute(
                f"""
                UPDATE moderation.owner_change_requests
                SET proposed_payload = %s::jsonb,
                    diff_payload = %s::jsonb,
                    status = %s,
                    moderator_account_id = CASE WHEN %s = 'superadmin' THEN %s ELSE moderator_account_id END,
                    moderator_comment = CASE WHEN %s = 'superadmin' THEN %s ELSE moderator_comment END
                    {extra}
                WHERE id = %s
                RETURNING *
                """,
                (
                    _json(proposed_payload),
                    _json(next_diff),
                    target,
                    actor_type,
                    actor_id,
                    actor_type,
                    comment,
                    int(change_id),
                ),
            )
        else:
            cur.execute(
                f"""
                UPDATE moderation.owner_change_requests
                SET status = %s,
                    moderator_account_id = CASE WHEN %s = 'superadmin' THEN %s ELSE moderator_account_id END,
                    moderator_comment = CASE WHEN %s = 'superadmin' THEN %s ELSE moderator_comment END
                    {extra}
                WHERE id = %s
                RETURNING *
                """,
                (target, actor_type, actor_id, actor_type, comment, int(change_id)),
            )
        updated = dict(cur.fetchone())
        if proposed_payload is not None:
            _insert_audit(
                cur,
                actor_type="owner",
                actor_id=actor_id,
                actor_display=None,
                camp_id=row["camp_id"],
                target_type="owner_change_request",
                target_id=change_id,
                action_type="owner_change_saved",
                action_label="Сохранены изменения",
                metadata={"fields": [item["field"] for item in next_diff]},
            )
        summary = {
            "submitted": "Изменения отправлены на проверку",
            "in_review": "Изменения взяты на проверку",
            "needs_changes": "Запрошены уточнения",
            "approved": "Изменения одобрены",
            "rejected": "Изменения отклонены",
            "withdrawn": "Изменения отозваны",
            "draft": "Изменения возвращены в черновик",
            "archived": "Изменения перенесены в архив",
        }.get(target, f"Статус: {owner_status_label(target)}")
        _insert_history(
            cur,
            change_id,
            row["status"],
            target,
            actor_type,
            actor_id,
            summary,
            comment=comment,
            snapshot={"diff": updated["diff_payload"] or []},
        )
        _insert_audit(
            cur,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_display=None,
            camp_id=row["camp_id"],
            target_type="owner_change_request",
            target_id=change_id,
            action_type=f"owner_change_{target}",
            action_label=summary,
            comment=comment,
            metadata={"status": target, "public_number": row["public_number"]},
        )
        _insert_owner_notification(
            cur,
            owner_id=row["owner_account_id"],
            change_id=change_id,
            camp_id=row["camp_id"],
            event_type=f"owner_change_{target}",
            title=summary,
            body=f"{row['public_number']} · {owner_status_label(target)}",
            action_url=f"/owner/changes/{change_id}",
            severity="warning" if target in {"needs_changes", "rejected"} else "info",
        )
        conn.commit()
    return get_owner_change(change_id)


def _apply_contacts(cur, camp_id: int, contacts: Iterable[dict]) -> None:
    cur.execute("DELETE FROM catalog.place_contacts WHERE camp_id = %s", (int(camp_id),))
    for index, contact in enumerate(contacts):
        value = str(contact.get("value") or "").strip()
        if not value:
            continue
        cur.execute(
            """
            INSERT INTO catalog.place_contacts (
                camp_id, contact_type, label, value, normalized_value,
                public_url, is_public, sort_order
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                int(camp_id),
                contact["contact_type"],
                contact.get("label"),
                value,
                value.casefold(),
                contact.get("url"),
                bool(contact.get("is_public", True)),
                int(contact.get("sort_order", index * 10)),
            ),
        )


def _apply_amenities(cur, camp_id: int, amenities: Iterable[dict]) -> None:
    cur.execute("DELETE FROM catalog.camp_amenities WHERE camp_id = %s", (int(camp_id),))
    for item in amenities:
        cur.execute(
            """
            INSERT INTO catalog.camp_amenities (camp_id, amenity_id, value)
            VALUES (%s, %s, %s::jsonb)
            """,
            (int(camp_id), int(item["amenity_id"]), _json(item.get("value"))),
        )


def _apply_rooms(cur, camp_id: int, rooms: Iterable[dict]) -> dict[str, int]:
    cur.execute("DELETE FROM catalog.rooms WHERE camp_id = %s", (int(camp_id),))
    room_id_by_client: dict[str, int] = {}
    columns = (
        "name", "room_type", "floors", "floor", "beds_single", "beds_double",
        "wc_count", "bath_type", "has_ac", "has_bbq", "has_kitchen", "capacity",
        "price", "description", "price_adult", "price_child", "discount_pct",
        "discount_from_nights", "wc_type", "bbq_type", "kitchen_type", "gazebo_type",
        "terrace_type", "balcony_type", "pool_type",
    )
    for room in rooms:
        values = [room.get(column) for column in columns]
        cur.execute(
            f"""
            INSERT INTO catalog.rooms (camp_id, {', '.join(columns)})
            VALUES (%s, {', '.join(['%s'] * len(columns))})
            RETURNING id
            """,
            (int(camp_id), *values),
        )
        room_id = int(cur.fetchone()["id"])
        client_id = str(room.get("client_id") or room.get("id") or "").strip()
        if client_id:
            room_id_by_client[client_id] = room_id
    return room_id_by_client


def apply_owner_change(
    change_id: int,
    *,
    moderator_id: int,
    idempotency_key_hash: str,
) -> tuple[dict, bool]:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM moderation.owner_change_requests
            WHERE id = %s
            FOR UPDATE
            """,
            (int(change_id),),
        )
        request = cur.fetchone()
        if not request:
            return {}, False
        if request["status"] == "applied":
            if request.get("apply_idempotency_key_hash") == idempotency_key_hash:
                return get_owner_change(change_id), False
            raise RuntimeError("Изменения уже опубликованы")
        if request["status"] != "approved":
            raise RuntimeError("Сначала одобрите изменения")
        current = _snapshot_with_cursor(cur, request["camp_id"], lock=True)
        if not current:
            raise RuntimeError("Объект не найден")
        if int(current["content_version"]) != int(request["base_content_version"]):
            raise RuntimeError("Карточка изменилась после создания запроса. Нужна повторная проверка")
        if (
            request.get("schema_key")
            and (
                request["schema_key"] != current.get("schema_key")
                or int(request.get("schema_version") or 0) != int(current.get("schema_version") or 0)
            )
        ):
            raise RuntimeError("Схема карточки изменилась после создания запроса. Нужна повторная проверка")

        proposed = request["proposed_payload"] or {}
        if "rooms" in proposed and current.get("entity_kind") != "accommodation":
            raise RuntimeError("Варианты размещения доступны только объектам проживания")
        merged = merged_owner_snapshot(current, proposed)
        assignments, params = [], []
        for column in CAMP_COLUMNS:
            if column not in proposed:
                continue
            assignments.append(f"{column} = %s::jsonb" if column in JSON_CAMP_COLUMNS else f"{column} = %s")
            params.append(_json(merged[column]) if column in JSON_CAMP_COLUMNS else merged[column])
        if "surroundings" in proposed:
            assignments.append("metadata = jsonb_set(COALESCE(metadata, '{}'::jsonb), '{surroundings}', %s::jsonb, TRUE)")
            params.append(_json(merged.get("surroundings")))
        if assignments:
            params.append(int(request["camp_id"]))
            cur.execute(
                f"UPDATE catalog.camps SET {', '.join(assignments)} WHERE id = %s",
                tuple(params),
            )
        if proposed.get("request_publication") is True:
            cur.execute(
                """
                UPDATE catalog.camps
                SET publication_status = 'published',
                    status = 'active',
                    visibility = CASE WHEN visibility = 'hidden' THEN 'public' ELSE visibility END,
                    is_visible_on_map = (lat IS NOT NULL AND lng IS NOT NULL)
                WHERE id = %s
                """,
                (int(request["camp_id"]),),
            )
        if "contacts" in proposed:
            _apply_contacts(cur, request["camp_id"], merged.get("contacts") or [])
        if "amenities" in proposed:
            _apply_amenities(cur, request["camp_id"], merged.get("amenities") or [])
        room_id_by_client: dict[str, int] = {}
        if "rooms" in proposed:
            room_id_by_client = _apply_rooms(cur, request["camp_id"], merged.get("rooms") or [])

        cur.execute(
            """
            SELECT *
            FROM moderation.owner_change_request_media
            WHERE change_request_id = %s
              AND deleted_at IS NULL
              AND status = 'staged'
            ORDER BY scope, room_client_id NULLS FIRST, sort_order, id
            FOR UPDATE
            """,
            (int(change_id),),
        )
        for media in cur.fetchall():
            if media["scope"] == "room" and current.get("entity_kind") != "accommodation":
                raise RuntimeError("Фото вариантов размещения недоступны для этого типа карточки")
            applied_media_id = None
            if media["action"] == "remove" and media.get("target_media_id"):
                table = "catalog.camp_media" if media["scope"] == "place" else "catalog.room_media"
                cur.execute(
                    f"DELETE FROM {table} WHERE id = %s AND camp_id = %s",
                    (int(media["target_media_id"]), int(request["camp_id"])),
                )
            elif media["action"] == "add" and media.get("storage_key"):
                url = f"/static/uploads/{media['storage_key']}"
                if media["scope"] == "place":
                    cur.execute(
                        """
                        INSERT INTO catalog.camp_media (
                            camp_id, media_type, url, source_kind,
                            moderation_status, sort, cover
                        )
                        VALUES (%s, 'image', %s, 'owner_portal', 'approved', %s, %s)
                        RETURNING id
                        """,
                        (
                            int(request["camp_id"]),
                            url,
                            int(media["sort_order"]),
                            bool(media["is_cover"]),
                        ),
                    )
                    applied_media_id = int(cur.fetchone()["id"])
                else:
                    client_key = str(media.get("room_client_id") or "")
                    room_id = room_id_by_client.get(client_key)
                    if room_id is None and client_key.isdigit():
                        cur.execute(
                            "SELECT id FROM catalog.rooms WHERE id = %s AND camp_id = %s",
                            (int(client_key), int(request["camp_id"])),
                        )
                        existing_room = cur.fetchone()
                        room_id = int(existing_room["id"]) if existing_room else None
                    if room_id is not None:
                        cur.execute(
                            """
                            INSERT INTO catalog.room_media (
                                camp_id, room_id, media_type, url, source_kind,
                                moderation_status, sort, cover
                            )
                            VALUES (%s, %s, 'image', %s, 'owner_portal', 'approved', %s, %s)
                            RETURNING id
                            """,
                            (
                                int(request["camp_id"]),
                                room_id,
                                url,
                                int(media["sort_order"]),
                                bool(media["is_cover"]),
                            ),
                        )
                        applied_media_id = int(cur.fetchone()["id"])
            cur.execute(
                """
                UPDATE moderation.owner_change_request_media
                SET status = 'applied', applied_media_id = %s
                WHERE id = %s
                """,
                (applied_media_id, int(media["id"])),
            )

        if proposed.get("request_publication") is True:
            try:
                catalog_repo.ensure_entities_ready_for_publication(
                    cur,
                    [int(request["camp_id"])],
                    block_owner_storage_drafts=False,
                    skip_already_published=False,
                )
            except ValueError as exc:
                raise RuntimeError(str(exc)) from exc

        cur.execute(
            """
            UPDATE moderation.owner_change_requests
            SET status = 'applied',
                moderator_account_id = %s,
                apply_idempotency_key_hash = %s,
                applied_at = NOW(),
                decided_at = COALESCE(decided_at, NOW())
            WHERE id = %s
            RETURNING *
            """,
            (int(moderator_id), idempotency_key_hash, int(change_id)),
        )
        updated = dict(cur.fetchone())
        _insert_history(
            cur,
            change_id,
            "approved",
            "applied",
            "superadmin",
            moderator_id,
            "Одобренные изменения опубликованы",
            snapshot={"diff": updated["diff_payload"] or []},
        )
        _insert_audit(
            cur,
            actor_type="superadmin",
            actor_id=moderator_id,
            actor_display=None,
            camp_id=request["camp_id"],
            target_type="owner_change_request",
            target_id=change_id,
            action_type="owner_change_applied",
            action_label="Изменения опубликованы",
            old_value=request["published_snapshot"],
            new_value=merged,
            was_auto_applied=False,
            metadata={"idempotency": True},
        )
        _insert_owner_notification(
            cur,
            owner_id=request["owner_account_id"],
            change_id=change_id,
            camp_id=request["camp_id"],
            event_type="owner_change_applied",
            title="Изменения опубликованы",
            body=f"{request['public_number']} · карточка объекта обновлена",
            action_url=f"/owner/changes/{change_id}",
        )
        conn.commit()
    return get_owner_change(change_id), True


def unpublish_owner_camp(owner_id: int, camp_id: int) -> dict | None:
    with _db_conn("catalog") as conn:
        if not owner_can_access_camp(owner_id, camp_id, write=True, conn=conn):
            return None
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, publication_status
            FROM catalog.camps WHERE id = %s FOR UPDATE
            """,
            (int(camp_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        if row["publication_status"] != "published":
            return dict(row)
        cur.execute(
            """
            UPDATE catalog.camps
            SET publication_status = 'disabled', status = 'disabled'
            WHERE id = %s
            RETURNING id, name, publication_status, updated_at
            """,
            (int(camp_id),),
        )
        updated = dict(cur.fetchone())
        _insert_audit(
            cur,
            actor_type="owner",
            actor_id=owner_id,
            actor_display=None,
            camp_id=camp_id,
            target_type="camp",
            target_id=camp_id,
            action_type="owner_camp_unpublished",
            action_label="Объект снят с публикации",
            old_value={"publication_status": "published"},
            new_value={"publication_status": "unpublished"},
            is_sensitive=True,
        )
        _insert_owner_notification(
            cur,
            owner_id=owner_id,
            change_id=None,
            camp_id=camp_id,
            event_type="owner_camp_unpublished",
            title="Объект снят с публикации",
            body=f"{row['name']} больше не показывается в публичном каталоге.",
            action_url=f"/owner",
            severity="warning",
        )
        conn.commit()
        return updated


def create_owner_change_media(
    *,
    change_id: int,
    owner_id: int,
    scope: str,
    room_client_id: str | None,
    storage_key: str,
    thumbnail_storage_key: str,
    preview_token: str,
    public_preview_url: str,
    original_filename: str,
    safe_filename: str,
    mime_type: str,
    size_bytes: int,
    width: int,
    height: int,
    sort_order: int,
    is_cover: bool,
    expires_at: datetime,
    max_count: int,
) -> dict:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (83_200_000_000 + int(change_id),))
        cur.execute(
            """
            SELECT
                changes.camp_id,
                changes.status,
                changes.proposed_payload,
                changes.published_snapshot,
                kinds.slug AS entity_kind
            FROM moderation.owner_change_requests changes
            JOIN catalog.camps camps ON camps.id = changes.camp_id
            JOIN catalog.place_types types ON types.id = camps.place_type_id
            JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            WHERE changes.id = %s
              AND changes.owner_account_id = %s
            FOR UPDATE OF changes
            """,
            (int(change_id), int(owner_id)),
        )
        change = cur.fetchone()
        if not change or change["status"] not in EDITABLE_REQUEST_STATUSES:
            raise ValueError("Черновик недоступен для загрузки")
        normalized_scope = str(scope or "").strip().lower()
        if normalized_scope not in {"place", "room"}:
            raise OwnerChangeValidationError(
                "Некорректный раздел фотографии"
            )
        normalized_room = None
        if normalized_scope == "room":
            normalized_room = resolve_owner_room_media_target(
                dict(change),
                room_client_id,
            )
        cur.execute(
            """
            SELECT COUNT(*)::int AS count
            FROM moderation.owner_change_request_media
            WHERE change_request_id = %s
              AND scope = %s
              AND room_client_id IS NOT DISTINCT FROM %s
              AND deleted_at IS NULL
              AND action = 'add'
              AND status = 'staged'
            """,
            (int(change_id), normalized_scope, normalized_room),
        )
        if int(cur.fetchone()["count"]) >= int(max_count):
            raise ValueError("Достигнут лимит фотографий")
        if is_cover:
            cur.execute(
                """
                UPDATE moderation.owner_change_request_media
                SET is_cover = FALSE
                WHERE change_request_id = %s
                  AND scope = %s
                  AND room_client_id IS NOT DISTINCT FROM %s
                  AND deleted_at IS NULL
                """,
                (int(change_id), normalized_scope, normalized_room),
            )
        cur.execute(
            """
            INSERT INTO moderation.owner_change_request_media (
                change_request_id, media_type, action, scope, room_client_id,
                storage_key, thumbnail_storage_key, preview_token, public_preview_url,
                original_filename, safe_filename, mime_type, size_bytes,
                width, height, sort_order, is_cover, status, expires_at
            )
            VALUES (
                %s, 'image', 'add', %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, 'staged', %s
            )
            RETURNING *
            """,
            (
                int(change_id), normalized_scope, normalized_room,
                storage_key, thumbnail_storage_key,
                preview_token, public_preview_url, original_filename, safe_filename,
                mime_type, int(size_bytes), int(width), int(height), int(sort_order),
                bool(is_cover), expires_at,
            ),
        )
        row = dict(cur.fetchone())
        _insert_audit(
            cur,
            actor_type="owner",
            actor_id=owner_id,
            actor_display=None,
            camp_id=change["camp_id"],
            target_type="owner_change_request",
            target_id=change_id,
            action_type="owner_media_added",
            action_label="Добавлена фотография",
            metadata={
                "media_id": row["id"],
                "scope": normalized_scope,
                "room_client_id": normalized_room,
            },
        )
        conn.commit()
        return row


def stage_owner_media_removal(
    *,
    change_id: int,
    owner_id: int,
    target_media_id: int,
) -> dict:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT changes.camp_id, changes.status, media.url, media.sort, media.cover
            FROM moderation.owner_change_requests changes
            JOIN catalog.camp_media media
              ON media.camp_id = changes.camp_id
             AND media.id = %s
            WHERE changes.id = %s
              AND changes.owner_account_id = %s
            FOR UPDATE OF changes
            """,
            (int(target_media_id), int(change_id), int(owner_id)),
        )
        target = cur.fetchone()
        if not target or target["status"] not in EDITABLE_REQUEST_STATUSES:
            raise ValueError("Фотография недоступна для изменения")
        cur.execute(
            """
            SELECT *
            FROM moderation.owner_change_request_media
            WHERE change_request_id = %s
              AND scope = 'place'
              AND action = 'remove'
              AND target_media_id = %s
              AND status = 'staged'
              AND deleted_at IS NULL
            LIMIT 1
            """,
            (int(change_id), int(target_media_id)),
        )
        existing = cur.fetchone()
        if existing:
            return dict(existing)
        cur.execute(
            """
            INSERT INTO moderation.owner_change_request_media (
                change_request_id, media_type, action, scope, target_media_id,
                public_preview_url, sort_order, is_cover, status
            )
            VALUES (%s, 'image', 'remove', 'place', %s, %s, %s, %s, 'staged')
            RETURNING *
            """,
            (
                int(change_id),
                int(target_media_id),
                target["url"],
                int(target["sort"] or 0),
                bool(target["cover"]),
            ),
        )
        row = dict(cur.fetchone())
        _insert_audit(
            cur,
            actor_type="owner",
            actor_id=owner_id,
            actor_display=None,
            camp_id=target["camp_id"],
            target_type="owner_change_request",
            target_id=change_id,
            action_type="owner_media_removal_staged",
            action_label="Фотография отмечена для удаления",
            metadata={"media_id": int(target_media_id)},
        )
        conn.commit()
        return row


def get_owner_change_media(preview_token: str, owner_id: int) -> dict | None:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT media.*
            FROM moderation.owner_change_request_media media
            JOIN moderation.owner_change_requests changes
              ON changes.id = media.change_request_id
            WHERE media.preview_token = %s
              AND changes.owner_account_id = %s
              AND media.deleted_at IS NULL
              AND (
                media.status = 'applied'
                OR (media.status = 'staged' AND media.expires_at > NOW())
              )
            LIMIT 1
            """,
            (preview_token, int(owner_id)),
        )
        return _dict(cur.fetchone())


def delete_owner_change_media(media_id: int, change_id: int, owner_id: int) -> dict | None:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE moderation.owner_change_request_media media
            SET deleted_at = NOW(), status = 'rejected', is_cover = FALSE
            FROM moderation.owner_change_requests changes
            WHERE media.id = %s
              AND media.change_request_id = %s
              AND changes.id = media.change_request_id
              AND changes.owner_account_id = %s
              AND changes.status IN ('draft', 'needs_changes', 'withdrawn')
              AND media.status = 'staged'
              AND media.deleted_at IS NULL
            RETURNING media.*
            """,
            (int(media_id), int(change_id), int(owner_id)),
        )
        row = cur.fetchone()
        conn.commit()
        return _dict(row)


def list_owner_notifications(owner_id: int, *, limit: int = 50) -> list[dict]:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id, owner_change_request_id, camp_id, event_type, title, body,
                action_url, severity, status, created_at, read_at
            FROM crm.notification_events
            WHERE owner_account_id = %s
              AND recipient_scope = 'owner'
              AND channel = 'in_app'
              AND status <> 'closed'
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (int(owner_id), min(max(int(limit), 1), 100)),
        )
        return [dict(row) for row in cur.fetchall()]


def list_moderation_changes(
    *,
    status: str | None = None,
    camp_id: int | None = None,
    owner_id: int | None = None,
    region: str | None = None,
    date_from=None,
    date_to=None,
    limit: int = 100,
) -> list[dict]:
    clauses, params = [], []
    if status:
        clauses.append("changes.status = %s")
        params.append(status)
    if camp_id:
        clauses.append("changes.camp_id = %s")
        params.append(int(camp_id))
    if owner_id:
        clauses.append("changes.owner_account_id = %s")
        params.append(int(owner_id))
    if region:
        clauses.append("lower(camps.region) = lower(%s)")
        params.append(region)
    if date_from:
        clauses.append("changes.created_at >= %s::date")
        params.append(date_from)
    if date_to:
        clauses.append("changes.created_at < (%s::date + INTERVAL '1 day')")
        params.append(date_to)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(min(max(int(limit), 1), 200))
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                changes.*, camps.name AS camp_name, owners.display_name AS owner_name,
                owners.email AS owner_email
            FROM moderation.owner_change_requests changes
            JOIN catalog.camps camps ON camps.id = changes.camp_id
            JOIN auth.owner_accounts owners ON owners.id = changes.owner_account_id
            {where}
            ORDER BY
                CASE changes.status
                    WHEN 'submitted' THEN 0 WHEN 'in_review' THEN 1
                    WHEN 'needs_changes' THEN 2 ELSE 3
                END,
                changes.submitted_at NULLS LAST, changes.updated_at DESC
            LIMIT %s
            """,
            tuple(params),
        )
        rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        row["status_label"] = owner_status_label(row["status"])
    return rows


def create_owner_account(
    *,
    email: str,
    password_hash: str,
    display_name: str,
    company: str | None = None,
) -> dict:
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO auth.owner_accounts (email, password_hash, display_name, company)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (email, password_hash, display_name, company),
        )
        row = dict(cur.fetchone())
        _insert_owner_notification(
            cur,
            owner_id=row["id"],
            change_id=None,
            camp_id=None,
            event_type="owner_account_created",
            title="Добро пожаловать в Туристику",
            body="Кабинет владельца готов. Проверьте профиль и состояние карточек.",
            action_url="/owner",
        )
        conn.commit()
        return row


def list_owner_accounts() -> list[dict]:
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                owners.id, owners.email, owners.display_name, owners.company,
                owners.phone, owners.preferred_contact_type, owners.is_active,
                owners.account_status, owners.last_login, owners.created_at,
                COALESCE(
                    jsonb_agg(
                        jsonb_build_object(
                            'camp_id', camps.id,
                            'camp_name', camps.name,
                            'role_key', links.role_key,
                            'is_primary', links.is_primary
                        )
                        ORDER BY links.is_primary DESC, camps.name
                    ) FILTER (WHERE camps.id IS NOT NULL),
                    '[]'::jsonb
                ) AS camps
            FROM auth.owner_accounts owners
            LEFT JOIN catalog.camp_owner_links links ON links.owner_account_id = owners.id
            LEFT JOIN catalog.camps camps ON camps.id = links.camp_id
            GROUP BY owners.id
            ORDER BY owners.created_at DESC, owners.id DESC
            """
        )
        return [dict(row) for row in cur.fetchall()]


def update_owner_account_admin(owner_id: int, changes: dict[str, Any]) -> dict | None:
    allowed = {"display_name", "company", "is_active", "account_status"}
    normalized = {key: value for key, value in changes.items() if key in allowed}
    if not normalized:
        return get_owner_by_id(owner_id)
    assignments, params = [], []
    for key, value in normalized.items():
        assignments.append(f"{key} = %s")
        params.append(value)
    params.append(int(owner_id))
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE auth.owner_accounts SET {', '.join(assignments)} WHERE id = %s RETURNING *",
            tuple(params),
        )
        row = cur.fetchone()
        conn.commit()
        return _dict(row)


def link_owner_camp(
    *,
    owner_id: int,
    camp_id: int,
    role_key: str,
    is_primary: bool,
    superadmin_id: int | None,
) -> dict:
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        if is_primary:
            cur.execute(
                "UPDATE catalog.camp_owner_links SET is_primary = FALSE WHERE camp_id = %s",
                (int(camp_id),),
            )
        cur.execute(
            """
            INSERT INTO catalog.camp_owner_links (
                owner_account_id, camp_id, role_key, is_primary, created_by_superadmin_id
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (camp_id, owner_account_id) DO UPDATE
            SET role_key = EXCLUDED.role_key,
                is_primary = EXCLUDED.is_primary,
                updated_at = NOW()
            RETURNING *
            """,
            (int(owner_id), int(camp_id), role_key, bool(is_primary), superadmin_id),
        )
        row = dict(cur.fetchone())
        conn.commit()
        return row


def _insert_history(
    cur,
    change_id: int,
    previous_status: str | None,
    new_status: str,
    actor_type: str,
    actor_id: int | None,
    summary: str,
    *,
    comment: str | None = None,
    snapshot: dict | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO moderation.owner_change_request_history (
            change_request_id, previous_status, new_status, actor_type,
            actor_id, summary, comment, snapshot
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (change_id, previous_status, new_status, actor_type, actor_id, summary, comment, _json(snapshot or {})),
    )


def _insert_audit(
    cur,
    *,
    actor_type: str,
    actor_id: int | None,
    actor_display: str | None,
    camp_id: int | None,
    target_type: str,
    target_id: Any,
    action_type: str,
    action_label: str,
    old_value: Any = None,
    new_value: Any = None,
    comment: str | None = None,
    is_sensitive: bool = False,
    was_auto_applied: bool = False,
    metadata: dict | None = None,
) -> None:
    cur.execute(
        """
        INSERT INTO crm.audit_log (
            actor_type, actor_id, actor_display, camp_id, target_type, target_id,
            action_type, action_label, old_value, new_value, comment,
            is_sensitive, was_auto_applied, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s::jsonb)
        """,
        (
            actor_type, actor_id, actor_display, camp_id, target_type, str(target_id),
            action_type, action_label,
            _json(old_value) if old_value is not None else None,
            _json(new_value) if new_value is not None else None,
            comment, bool(is_sensitive), bool(was_auto_applied), _json(metadata or {}),
        ),
    )


def _insert_owner_notification(
    cur,
    *,
    owner_id: int,
    change_id: int | None,
    camp_id: int | None,
    event_type: str,
    title: str,
    body: str,
    action_url: str | None,
    severity: str = "info",
) -> None:
    cur.execute(
        """
        INSERT INTO crm.notification_events (
            owner_account_id, owner_change_request_id, camp_id,
            recipient_scope, channel, event_type, title, body,
            action_url, severity, status
        )
        VALUES (%s, %s, %s, 'owner', 'in_app', %s, %s, %s, %s, %s, 'new')
        """,
        (owner_id, change_id, camp_id, event_type, title, body, action_url, severity),
    )
    cur.execute(
        """
        INSERT INTO crm.notification_events (
            owner_account_id, owner_change_request_id, camp_id,
            recipient_scope, channel, event_type, title, body,
            action_url, severity, status, recipient_address, dedupe_key
        )
        SELECT
            accounts.id, %s, %s, 'owner', 'email', %s, %s, %s,
            %s, %s, 'new', accounts.email, %s
        FROM auth.owner_accounts accounts
        WHERE accounts.id = %s
          AND NULLIF(trim(accounts.email), '') IS NOT NULL
        ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
        """,
        (
            change_id,
            camp_id,
            event_type,
            title,
            body,
            action_url,
            severity,
            f"owner-email:{event_type}:{change_id or 0}:{camp_id or 0}:{owner_id}",
            owner_id,
        ),
    )
    cur.execute(
        """
        INSERT INTO crm.notification_events (
            owner_account_id, owner_change_request_id, camp_id,
            recipient_scope, channel, event_type, title, body,
            action_url, severity, status, dedupe_key
        )
        SELECT
            accounts.id, %s, %s, 'owner', 'telegram', %s, %s, %s,
            %s, %s, 'new', %s
        FROM auth.owner_accounts accounts
        WHERE accounts.id = %s
          AND accounts.telegram_chat_id IS NOT NULL
        ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
        """,
        (
            change_id,
            camp_id,
            event_type,
            title,
            body,
            action_url,
            severity,
            f"owner-telegram:{event_type}:{change_id or 0}:{camp_id or 0}:{owner_id}",
            owner_id,
        ),
    )
