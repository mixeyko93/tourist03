"""PostgreSQL persistence for public placement submissions."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from psycopg2 import errors

from tourist03.db import _db_conn, _pg_connect
from tourist03.domain.catalog_entities import (
    CatalogEntityValidationError,
    sanitize_entity_attributes_for_schema,
)
from tourist03.domain.submissions import ensure_status_transition, hash_token, new_public_number


DRAFT_MUTABLE_COLUMNS = frozenset(
    {
        "applicant_role",
        "applicant_name",
        "applicant_organization",
        "applicant_position",
        "applicant_phone",
        "applicant_email",
        "applicant_telegram",
        "applicant_whatsapp",
        "applicant_max",
        "preferred_contact_type",
        "place_name",
        "place_type_id",
        "region",
        "district",
        "city",
        "locality",
        "address",
        "lat",
        "lng",
        "short_description",
        "description",
        "seasonality",
        "working_hours",
        "min_price",
        "public_contacts",
        "amenities",
        "rooms_payload",
        "video_urls",
        "extra_data",
        "consents",
    }
)
JSON_COLUMNS = frozenset(
    {
        "working_hours",
        "public_contacts",
        "amenities",
        "rooms_payload",
        "video_urls",
        "extra_data",
        "consents",
    }
)
FINALIZABLE_COLUMNS = DRAFT_MUTABLE_COLUMNS | {"schema_key", "schema_version"}


def _row_dict(row) -> dict | None:
    return dict(row) if row else None


def create_draft(
    *,
    draft_token_hash: str,
    ip_hash: str | None,
    user_agent_hash: str | None,
    locale: str,
    source: str,
    ttl_hours: int,
) -> dict:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=max(int(ttl_hours), 1))
    for _ in range(8):
        public_number = new_public_number()
        try:
            with _db_conn("moderation") as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO moderation.placement_submissions (
                        public_number,
                        draft_token_hash,
                        ip_hash,
                        user_agent_hash,
                        locale,
                        source,
                        draft_expires_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        public_number,
                        draft_token_hash,
                        ip_hash,
                        user_agent_hash,
                        (locale or "ru")[:16],
                        (source or "web")[:32],
                        expires_at,
                    ),
                )
                row = dict(cur.fetchone())
                cur.execute(
                    """
                    INSERT INTO moderation.submission_status_history (
                        submission_id, previous_status, new_status, actor_type
                    )
                    VALUES (%s, NULL, 'draft', 'applicant')
                    """,
                    (row["id"],),
                )
                conn.commit()
                return row
        except errors.UniqueViolation:
            continue
    raise RuntimeError("Не удалось создать уникальный номер заявки")


def get_draft_by_token_hash(draft_token_hash: str, *, for_update: bool = False, conn=None) -> dict | None:
    owns_connection = conn is None
    if owns_connection:
        context = _db_conn("moderation")
        conn = context.__enter__()
    try:
        cur = conn.cursor()
        suffix = " FOR UPDATE" if for_update else ""
        cur.execute(
            f"""
            SELECT *
            FROM moderation.placement_submissions
            WHERE draft_token_hash = %s
            LIMIT 1{suffix}
            """,
            (draft_token_hash,),
        )
        return _row_dict(cur.fetchone())
    finally:
        if owns_connection:
            context.__exit__(None, None, None)


def patch_draft(draft_token_hash: str, changes: dict, *, expected_version: int | None = None) -> dict | None:
    normalized = {key: value for key, value in changes.items() if key in DRAFT_MUTABLE_COLUMNS}
    if not normalized:
        return get_draft_by_token_hash(draft_token_hash)

    assignments: list[str] = []
    params: list[Any] = []
    for key, value in normalized.items():
        if key in JSON_COLUMNS:
            assignments.append(f"{key} = %s::jsonb")
            params.append(json.dumps(value, ensure_ascii=False))
        else:
            assignments.append(f"{key} = %s")
            params.append(value)

    where = [
        "draft_token_hash = %s",
        "status = 'draft'",
        "draft_expires_at > NOW()",
    ]
    params.append(draft_token_hash)
    if expected_version is not None:
        where.append("content_version = %s")
        params.append(int(expected_version))

    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            UPDATE moderation.placement_submissions
            SET {', '.join(assignments)}
            WHERE {' AND '.join(where)}
            RETURNING *
            """,
            tuple(params),
        )
        row = cur.fetchone()
        conn.commit()
        return _row_dict(row)


def count_recent_submissions_by_ip(ip_hash: str | None, *, hours: int = 1) -> int:
    if not ip_hash:
        return 0
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM moderation.placement_submissions
            WHERE ip_hash = %s
              AND submitted_at >= NOW() - (%s * INTERVAL '1 hour')
            """,
            (ip_hash, max(int(hours), 1)),
        )
        return int(cur.fetchone()["count"] or 0)


def finalize_submission(
    *,
    draft_token_hash: str,
    tracking_token_hash: str,
    idempotency_key_hash: str,
    spam_score: int,
    cleaned_payload: dict,
) -> tuple[dict, bool]:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM moderation.placement_submissions
            WHERE draft_token_hash = %s
            LIMIT 1
            FOR UPDATE
            """,
            (draft_token_hash,),
        )
        existing = cur.fetchone()
        if not existing:
            return {}, False
        row = dict(existing)
        if row["status"] != "draft":
            if row.get("submit_idempotency_key_hash") == idempotency_key_hash:
                return row, False
            raise ValueError("Заявка уже отправлена")
        if row["draft_expires_at"] <= datetime.now(timezone.utc):
            raise ValueError("Срок действия черновика истёк")

        assignments: list[str] = []
        params: list[Any] = []
        for key, value in cleaned_payload.items():
            if key not in FINALIZABLE_COLUMNS:
                continue
            if key in JSON_COLUMNS:
                assignments.append(f"{key} = %s::jsonb")
                params.append(json.dumps(value, ensure_ascii=False))
            else:
                assignments.append(f"{key} = %s")
                params.append(value)
        assignments.extend(
            [
                "tracking_token_hash = %s",
                "submit_idempotency_key_hash = %s",
                "spam_score = %s",
                "status = 'submitted'",
                "submitted_at = NOW()",
                "consented_at = NOW()",
            ]
        )
        params.extend([tracking_token_hash, idempotency_key_hash, int(spam_score), row["id"]])
        cur.execute(
            f"""
            UPDATE moderation.placement_submissions
            SET {', '.join(assignments)}
            WHERE id = %s
            RETURNING *
            """,
            tuple(params),
        )
        submitted = dict(cur.fetchone())
        cur.execute(
            """
            INSERT INTO moderation.submission_status_history (
                submission_id, previous_status, new_status, actor_type
            )
            VALUES (%s, 'draft', 'submitted', 'applicant')
            """,
            (row["id"],),
        )
        cur.execute(
            """
            UPDATE moderation.placement_submissions
            SET status = 'new'
            WHERE id = %s
            RETURNING *
            """,
            (row["id"],),
        )
        finalized = dict(cur.fetchone())
        cur.execute(
            """
            INSERT INTO moderation.submission_status_history (
                submission_id, previous_status, new_status, actor_type
            )
            VALUES (%s, 'submitted', 'new', 'system')
            """,
            (row["id"],),
        )
        cur.execute(
            """
            UPDATE moderation.submission_media
            SET status = 'attached',
                attached_at = NOW()
            WHERE submission_id = %s
              AND status = 'staged'
              AND deleted_at IS NULL
            """,
            (row["id"],),
        )
        conn.commit()
        return finalized, True


def get_submission_status(public_number: str, tracking_token_hash: str) -> dict | None:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                submissions.public_number,
                submissions.status,
                submissions.status_public_comment,
                submissions.updated_at,
                submissions.published_camp_id,
                camps.slug AS published_slug,
                camps.publication_status
            FROM moderation.placement_submissions submissions
            LEFT JOIN catalog.camps camps
              ON camps.id = submissions.published_camp_id
            WHERE lower(submissions.public_number) = lower(%s)
              AND submissions.tracking_token_hash = %s
            LIMIT 1
            """,
            (public_number, tracking_token_hash),
        )
        return _row_dict(cur.fetchone())


def count_media(submission_id: int, *, scope: str, room_client_id: str | None = None) -> int:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM moderation.submission_media
            WHERE submission_id = %s
              AND scope = %s
              AND room_client_id IS NOT DISTINCT FROM %s
              AND deleted_at IS NULL
              AND status IN ('staged', 'attached')
            """,
            (int(submission_id), scope, room_client_id),
        )
        return int(cur.fetchone()["count"] or 0)


def create_media(
    *,
    submission_id: int,
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
        cur.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            (73_031_000_000 + int(submission_id),),
        )
        cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM moderation.submission_media
            WHERE submission_id = %s
              AND scope = %s
              AND room_client_id IS NOT DISTINCT FROM %s
              AND deleted_at IS NULL
              AND status IN ('staged', 'attached')
            """,
            (int(submission_id), scope, room_client_id),
        )
        if int(cur.fetchone()["count"] or 0) >= max(1, int(max_count)):
            raise ValueError("Достигнут лимит фотографий")
        if is_cover:
            cur.execute(
                """
                UPDATE moderation.submission_media
                SET is_cover = FALSE
                WHERE submission_id = %s
                  AND scope = %s
                  AND room_client_id IS NOT DISTINCT FROM %s
                  AND deleted_at IS NULL
                """,
                (int(submission_id), scope, room_client_id),
            )
        cur.execute(
            """
            INSERT INTO moderation.submission_media (
                submission_id,
                scope,
                room_client_id,
                storage_key,
                thumbnail_storage_key,
                preview_token,
                public_preview_url,
                original_filename,
                safe_filename,
                mime_type,
                size_bytes,
                width,
                height,
                sort_order,
                is_cover,
                expires_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING *
            """,
            (
                int(submission_id),
                scope,
                room_client_id,
                storage_key,
                thumbnail_storage_key,
                preview_token,
                public_preview_url,
                original_filename,
                safe_filename,
                mime_type,
                int(size_bytes),
                int(width),
                int(height),
                int(sort_order),
                bool(is_cover),
                expires_at,
            ),
        )
        row = dict(cur.fetchone())
        conn.commit()
        return row


def get_media_for_draft(
    media_id: int,
    draft_token_hash: str,
    *,
    include_deleted: bool = False,
) -> dict | None:
    deleted_clause = "" if include_deleted else "AND media.deleted_at IS NULL"
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT media.*
            FROM moderation.submission_media media
            JOIN moderation.placement_submissions submissions
              ON submissions.id = media.submission_id
            WHERE media.id = %s
              AND submissions.draft_token_hash = %s
              AND submissions.status = 'draft'
              AND submissions.draft_expires_at > NOW()
              {deleted_clause}
            LIMIT 1
            """,
            (int(media_id), draft_token_hash),
        )
        return _row_dict(cur.fetchone())


def get_media_by_preview_token(preview_token: str) -> dict | None:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT media.*
            FROM moderation.submission_media media
            JOIN moderation.placement_submissions submissions
              ON submissions.id = media.submission_id
            WHERE media.preview_token = %s
              AND media.deleted_at IS NULL
              AND (
                  media.status IN ('attached', 'copied')
                  OR (
                      media.status = 'staged'
                      AND media.expires_at > NOW()
                      AND submissions.status = 'draft'
                      AND submissions.draft_expires_at > NOW()
                  )
              )
            LIMIT 1
            """,
            (preview_token,),
        )
        return _row_dict(cur.fetchone())


def delete_media_for_draft(media_id: int, draft_token_hash: str) -> dict | None:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE moderation.submission_media media
            SET deleted_at = NOW(),
                status = 'rejected',
                is_cover = FALSE
            FROM moderation.placement_submissions submissions
            WHERE media.id = %s
              AND submissions.id = media.submission_id
              AND submissions.draft_token_hash = %s
              AND submissions.status = 'draft'
              AND submissions.draft_expires_at > NOW()
              AND media.deleted_at IS NULL
            RETURNING media.*
            """,
            (int(media_id), draft_token_hash),
        )
        row = cur.fetchone()
        conn.commit()
        return _row_dict(row)


def list_submission_media(submission_id: int) -> list[dict]:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM moderation.submission_media
            WHERE submission_id = %s
              AND deleted_at IS NULL
            ORDER BY scope, room_client_id NULLS FIRST, sort_order, id
            """,
            (int(submission_id),),
        )
        return [dict(row) for row in cur.fetchall()]


def list_submissions(
    *,
    status: str | None = None,
    place_type_id: int | None = None,
    region: str | None = None,
    applicant_role: str | None = None,
    assigned_admin_id: int | None = None,
    has_photos: bool | None = None,
    spam_risk: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    clauses = ["TRUE"]
    params: list[Any] = []
    if status:
        clauses.append("submissions.status = %s")
        params.append(status)
    if place_type_id:
        clauses.append("submissions.place_type_id = %s")
        params.append(int(place_type_id))
    if region:
        clauses.append("lower(submissions.region) = lower(%s)")
        params.append(region)
    if applicant_role:
        clauses.append("submissions.applicant_role = %s")
        params.append(applicant_role)
    if assigned_admin_id:
        clauses.append("submissions.assigned_admin_id = %s")
        params.append(int(assigned_admin_id))
    if has_photos is not None:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM moderation.submission_media media_filter
                WHERE media_filter.submission_id = submissions.id
                  AND media_filter.deleted_at IS NULL
            ) = %s
            """
        )
        params.append(bool(has_photos))
    if spam_risk == "high":
        clauses.append("submissions.spam_score >= 60")
    elif spam_risk == "normal":
        clauses.append("submissions.spam_score < 60")
    if date_from:
        clauses.append("submissions.created_at >= %s")
        params.append(date_from)
    if date_to:
        clauses.append("submissions.created_at < %s")
        params.append(date_to + timedelta(days=1))
    if query:
        clauses.append(
            """
            (
                submissions.public_number ILIKE %s
                OR submissions.place_name ILIKE %s
                OR submissions.applicant_name ILIKE %s
                OR submissions.region ILIKE %s
            )
            """
        )
        pattern = f"%{query}%"
        params.extend([pattern, pattern, pattern, pattern])

    where_sql = " AND ".join(clauses)
    safe_limit = max(1, min(int(limit), 100))
    safe_offset = max(0, int(offset))
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM moderation.placement_submissions submissions
            WHERE {where_sql}
            """,
            tuple(params),
        )
        total = int(cur.fetchone()["count"] or 0)
        cur.execute(
            f"""
            SELECT
                submissions.id,
                submissions.public_number,
                submissions.status,
                submissions.place_name,
                submissions.place_type_id,
                place_types.name AS place_type_name,
                entity_kinds.slug AS entity_kind,
                submissions.schema_key,
                submissions.schema_version,
                submissions.region,
                submissions.applicant_role,
                submissions.applicant_name,
                submissions.assigned_admin_id,
                admins.display_name AS assigned_admin_name,
                submissions.spam_score,
                submissions.created_at,
                submissions.submitted_at,
                submissions.updated_at,
                submissions.content_version,
                submissions.published_camp_id,
                (
                    SELECT COUNT(*)
                    FROM moderation.submission_media media
                    WHERE media.submission_id = submissions.id
                      AND media.deleted_at IS NULL
                ) AS media_count
            FROM moderation.placement_submissions submissions
            LEFT JOIN catalog.place_types place_types
              ON place_types.id = submissions.place_type_id
            LEFT JOIN catalog.entity_kinds entity_kinds
              ON entity_kinds.id = place_types.entity_kind_id
            LEFT JOIN auth.superadmin_accounts admins
              ON admins.id = submissions.assigned_admin_id
            WHERE {where_sql}
            ORDER BY
                CASE submissions.status
                    WHEN 'new' THEN 0
                    WHEN 'in_review' THEN 1
                    WHEN 'needs_clarification' THEN 2
                    ELSE 3
                END,
                submissions.created_at DESC,
                submissions.id DESC
            LIMIT %s OFFSET %s
            """,
            tuple([*params, safe_limit, safe_offset]),
        )
        return {
            "ok": True,
            "items": [dict(row) for row in cur.fetchall()],
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
        }


def get_submission_detail(submission_id: int) -> dict | None:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                submissions.*,
                place_types.name AS place_type_name,
                place_types.slug AS place_type_slug,
                entity_kinds.slug AS entity_kind,
                place_types.default_schema_key AS place_type_schema_key,
                place_types.default_schema_version AS place_type_schema_version,
                admins.display_name AS assigned_admin_name,
                camps.slug AS published_camp_slug
            FROM moderation.placement_submissions submissions
            LEFT JOIN catalog.place_types place_types
              ON place_types.id = submissions.place_type_id
            LEFT JOIN catalog.entity_kinds entity_kinds
              ON entity_kinds.id = place_types.entity_kind_id
            LEFT JOIN auth.superadmin_accounts admins
              ON admins.id = submissions.assigned_admin_id
            LEFT JOIN catalog.camps camps
              ON camps.id = submissions.published_camp_id
            WHERE submissions.id = %s
            LIMIT 1
            """,
            (int(submission_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        result = dict(row)
        cur.execute(
            """
            SELECT *
            FROM moderation.submission_media
            WHERE submission_id = %s AND deleted_at IS NULL
            ORDER BY scope, room_client_id NULLS FIRST, sort_order, id
            """,
            (int(submission_id),),
        )
        result["media"] = [dict(item) for item in cur.fetchall()]
        cur.execute(
            """
            SELECT *
            FROM moderation.submission_status_history
            WHERE submission_id = %s
            ORDER BY created_at, id
            """,
            (int(submission_id),),
        )
        result["history"] = [dict(item) for item in cur.fetchall()]
        cur.execute(
            """
            SELECT
                notes.*,
                admins.display_name AS author_name
            FROM moderation.submission_notes notes
            LEFT JOIN auth.superadmin_accounts admins
              ON admins.id = notes.author_id
            WHERE notes.submission_id = %s
            ORDER BY notes.created_at, notes.id
            """,
            (int(submission_id),),
        )
        result["notes"] = [dict(item) for item in cur.fetchall()]
        cur.execute(
            """
            SELECT
                id,
                actor_type,
                actor_id,
                actor_display,
                action_type,
                action_label,
                comment,
                metadata,
                created_at
            FROM crm.audit_log
            WHERE target_type = 'placement_submission'
              AND target_id IN (%s, %s)
            ORDER BY created_at DESC, id DESC
            LIMIT 100
            """,
            (str(result["id"]), result["public_number"]),
        )
        result["audit"] = [dict(item) for item in cur.fetchall()]
        return result


def patch_submission_by_admin(
    submission_id: int,
    changes: dict,
    *,
    expected_version: int,
) -> dict | None:
    allowed = DRAFT_MUTABLE_COLUMNS | {"assigned_admin_id", "status_public_comment"}
    normalized = {key: value for key, value in changes.items() if key in allowed}
    if not normalized:
        return get_submission_detail(submission_id)
    assignments: list[str] = []
    params: list[Any] = []
    for key, value in normalized.items():
        if key in JSON_COLUMNS:
            assignments.append(f"{key} = %s::jsonb")
            params.append(json.dumps(value, ensure_ascii=False))
        else:
            assignments.append(f"{key} = %s")
            params.append(value)
    params.extend([int(submission_id), int(expected_version)])
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            UPDATE moderation.placement_submissions
            SET {', '.join(assignments)}
            WHERE id = %s AND content_version = %s
            RETURNING *
            """,
            tuple(params),
        )
        row = cur.fetchone()
        conn.commit()
        return _row_dict(row)


def transition_submission(
    submission_id: int,
    new_status: str,
    *,
    actor_id: int | None,
    public_comment: str | None = None,
    internal_comment: str | None = None,
    expected_version: int | None = None,
    assign_to_actor: bool = False,
) -> dict | None:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM moderation.placement_submissions
            WHERE id = %s
            FOR UPDATE
            """,
            (int(submission_id),),
        )
        current_row = cur.fetchone()
        if not current_row:
            return None
        current = dict(current_row)
        if expected_version is not None and int(current["content_version"]) != int(expected_version):
            raise RuntimeError("Данные заявки изменились. Обновите страницу")
        comment = public_comment or internal_comment
        ensure_status_transition(current["status"], new_status, comment=comment)
        timestamp_column = {
            "in_review": "reviewed_at",
            "approved": "approved_at",
            "rejected": "rejected_at",
        }.get(new_status)
        assignments = [
            "status = %s",
            "status_public_comment = %s",
        ]
        params: list[Any] = [new_status, (public_comment or "").strip() or None]
        if timestamp_column:
            assignments.append(f"{timestamp_column} = NOW()")
        if assign_to_actor and actor_id:
            assignments.append("assigned_admin_id = %s")
            params.append(int(actor_id))
        params.append(int(submission_id))
        cur.execute(
            f"""
            UPDATE moderation.placement_submissions
            SET {', '.join(assignments)}
            WHERE id = %s
            RETURNING *
            """,
            tuple(params),
        )
        updated = dict(cur.fetchone())
        cur.execute(
            """
            INSERT INTO moderation.submission_status_history (
                submission_id,
                previous_status,
                new_status,
                actor_type,
                actor_id,
                public_comment,
                internal_comment
            )
            VALUES (%s, %s, %s, 'superadmin', %s, %s, %s)
            """,
            (
                int(submission_id),
                current["status"],
                new_status,
                actor_id,
                (public_comment or "").strip() or None,
                (internal_comment or "").strip() or None,
            ),
        )
        conn.commit()
        return updated


def add_submission_note(
    submission_id: int,
    *,
    author_id: int | None,
    text: str,
    visible_to_applicant: bool,
) -> dict | None:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM moderation.placement_submissions WHERE id = %s",
            (int(submission_id),),
        )
        if not cur.fetchone():
            return None
        cur.execute(
            """
            INSERT INTO moderation.submission_notes (
                submission_id,
                author_id,
                note_type,
                text,
                is_visible_to_applicant
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                int(submission_id),
                author_id,
                "public" if visible_to_applicant else "internal",
                text,
                bool(visible_to_applicant),
            ),
        )
        row = dict(cur.fetchone())
        conn.commit()
        return row


def create_catalog_draft_from_submission(
    submission_id: int,
    *,
    actor_id: int | None,
    idempotency_key: str,
) -> tuple[dict, bool]:
    conn = _pg_connect("moderation")
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM moderation.placement_submissions
            WHERE id = %s
            FOR UPDATE
            """,
            (int(submission_id),),
        )
        source_row = cur.fetchone()
        if not source_row:
            return {}, False
        source = dict(source_row)
        if source.get("published_camp_id"):
            conn.commit()
            return {"camp_id": int(source["published_camp_id"]), "status": source["status"]}, False
        if source["status"] != "approved":
            raise ValueError("Черновик объекта можно создать только из одобренной заявки")
        if not (idempotency_key or "").strip():
            raise ValueError("Idempotency key обязателен")

        cur.execute(
            """
            SELECT
                types.id,
                types.default_schema_key,
                types.default_schema_version,
                kinds.slug AS entity_kind
            FROM catalog.place_types types
            JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            WHERE types.id = %s
            LIMIT 1
            """,
            (source["place_type_id"],),
        )
        type_row = cur.fetchone()
        if not type_row:
            raise ValueError("Тип объекта заявки больше недоступен")
        entity_type = dict(type_row)
        schema_key = str(
            source.get("schema_key") or entity_type["default_schema_key"] or ""
        ).strip().lower()
        schema_version = int(
            source.get("schema_version")
            or entity_type["default_schema_version"]
            or 1
        )
        cur.execute(
            """
            SELECT
                schemas.schema_key,
                schemas.version,
                schemas.name AS title,
                schemas.applicable_kinds,
                schemas.fields,
                schemas.sections,
                schemas.validation,
                schemas.display,
                schemas.schema_org_type,
                schemas.quality_keys
            FROM catalog.entity_schemas schemas
            WHERE schemas.schema_key = %s
              AND schemas.version = %s
              AND schemas.applicable_kinds ? %s
            LIMIT 1
            """,
            (schema_key, schema_version, entity_type["entity_kind"]),
        )
        schema_row = cur.fetchone()
        if not schema_row:
            raise ValueError("Замороженная схема заявки больше недоступна")
        schema_definition = dict(schema_row)
        try:
            attributes = sanitize_entity_attributes_for_schema(
                source.get("extra_data"),
                schema_definition,
            )
        except CatalogEntityValidationError as exc:
            raise ValueError(str(exc)) from exc
        is_accommodation = entity_type["entity_kind"] == "accommodation"
        if not is_accommodation and (source.get("rooms_payload") or []):
            raise ValueError(
                "Варианты размещения доступны только для объектов проживания"
            )
        price_mode = "from" if source.get("min_price") is not None else "request"

        cur.execute(
            "SELECT catalog.slugify_place_name(%s) AS slug",
            (source["place_name"],),
        )
        base_slug = str(cur.fetchone()["slug"] or "place")
        candidate = base_slug
        suffix = 1
        while True:
            cur.execute(
                "SELECT 1 FROM catalog.camps WHERE lower(slug) = lower(%s)",
                (candidate,),
            )
            if not cur.fetchone():
                break
            suffix += 1
            candidate = f"{base_slug}-{suffix}"

        metadata = {
            "source": "placement_submission",
            "submission_public_number": source["public_number"],
            "submission_idempotency_hash": hash_token(idempotency_key),
        }
        cur.execute(
            """
            INSERT INTO catalog.camps (
                name,
                slug,
                place_type_id,
                publication_status,
                status,
                address,
                lat,
                lng,
                short_description,
                description,
                region,
                district,
                city,
                locality,
                seasonality,
                working_hours,
                min_price,
                video_urls,
                metadata,
                schema_key,
                schema_version,
                attributes,
                visibility,
                price_mode,
                currency,
                is_visible_on_map,
                accepts_bookings
            )
            VALUES (
                %s, %s, %s, 'draft', 'disabled', %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb,
                %s, %s, %s::jsonb, 'hidden', %s, 'RUB', FALSE, FALSE
            )
            RETURNING id, slug, publication_status
            """,
            (
                source["place_name"],
                candidate,
                source["place_type_id"],
                source["address"],
                source["lat"],
                source["lng"],
                source["short_description"],
                source["description"],
                source["region"],
                source["district"],
                source["city"],
                source["locality"],
                source["seasonality"],
                json.dumps(source["working_hours"] or {}, ensure_ascii=False),
                source["min_price"],
                json.dumps(source["video_urls"] or [], ensure_ascii=False),
                json.dumps(metadata, ensure_ascii=False),
                schema_key,
                schema_version,
                json.dumps(attributes, ensure_ascii=False),
                price_mode,
            ),
        )
        camp = dict(cur.fetchone())
        camp_id = int(camp["id"])

        for contact in source["public_contacts"] or []:
            if not isinstance(contact, dict):
                continue
            cur.execute(
                """
                INSERT INTO catalog.place_contacts (
                    camp_id,
                    contact_type,
                    label,
                    value,
                    normalized_value,
                    public_url,
                    is_public,
                    sort_order
                )
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s)
                """,
                (
                    camp_id,
                    contact.get("contact_type"),
                    contact.get("label"),
                    contact.get("value"),
                    contact.get("normalized_value") or contact.get("value"),
                    contact.get("public_url"),
                    int(contact.get("sort_order") or 0),
                ),
            )
        for amenity in source["amenities"] or []:
            if not isinstance(amenity, dict) or not amenity.get("amenity_id"):
                continue
            cur.execute(
                """
                INSERT INTO catalog.camp_amenities (camp_id, amenity_id, value)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (camp_id, amenity_id)
                DO UPDATE SET value = EXCLUDED.value
                """,
                (
                    camp_id,
                    int(amenity["amenity_id"]),
                    json.dumps(amenity.get("value"), ensure_ascii=False),
                ),
            )

        room_id_by_client: dict[str, int] = {}
        for room in source["rooms_payload"] or [] if is_accommodation else []:
            if not isinstance(room, dict):
                continue
            beds_single = int(room.get("beds_single") or 0)
            beds_double = int(room.get("beds_double") or 0)
            capacity = int(room.get("capacity") or beds_single + beds_double * 2)
            cur.execute(
                """
                INSERT INTO catalog.rooms (
                    camp_id,
                    name,
                    room_type,
                    floors,
                    floor,
                    beds_single,
                    beds_double,
                    bath_type,
                    wc_type,
                    bbq_type,
                    kitchen_type,
                    gazebo_type,
                    terrace_type,
                    pool_type,
                    balcony_type,
                    has_ac,
                    capacity,
                    price_adult,
                    price_child,
                    price,
                    description,
                    photos_json
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '[]'
                )
                RETURNING id
                """,
                (
                    camp_id,
                    str(room.get("name") or "").strip(),
                    str(room.get("room_type") or "").strip(),
                    int(room.get("floors") or 1),
                    int(room.get("floor") or 1),
                    beds_single,
                    beds_double,
                    str(room.get("bath_type") or "").strip(),
                    str(room.get("wc_type") or "").strip(),
                    str(room.get("bbq_type") or "").strip(),
                    str(room.get("kitchen_type") or "").strip(),
                    str(room.get("gazebo_type") or "").strip(),
                    str(room.get("terrace_type") or "").strip(),
                    str(room.get("pool_type") or "").strip(),
                    str(room.get("balcony_type") or "").strip(),
                    int(bool(room.get("has_ac"))),
                    capacity,
                    int(room.get("price_adult") or 0),
                    int(room.get("price_child") or 0),
                    int(room.get("price") or 0),
                    str(room.get("description") or "").strip(),
                ),
            )
            client_id = str(room.get("client_id") or "").strip()
            if client_id:
                room_id_by_client[client_id] = int(cur.fetchone()["id"])
            else:
                cur.fetchone()

        cur.execute(
            """
            SELECT *
            FROM moderation.submission_media
            WHERE submission_id = %s
              AND deleted_at IS NULL
              AND status = 'attached'
            ORDER BY scope, room_client_id NULLS FIRST, sort_order, id
            """,
            (int(submission_id),),
        )
        for media in cur.fetchall():
            url = f"/static/uploads/{media['storage_key']}"
            if media["scope"] == "place":
                cur.execute(
                    """
                    INSERT INTO catalog.camp_media (
                        camp_id,
                        media_type,
                        url,
                        source_kind,
                        moderation_status,
                        sort,
                        cover
                    )
                    VALUES (%s, 'image', %s, 'upload', 'pending', %s, %s)
                    """,
                    (camp_id, url, int(media["sort_order"]), bool(media["is_cover"])),
                )
            else:
                if not is_accommodation:
                    raise ValueError(
                        "Фотографии вариантов размещения доступны только для проживания"
                    )
                room_id = room_id_by_client.get(str(media["room_client_id"] or ""))
                if not room_id:
                    continue
                cur.execute(
                    """
                    INSERT INTO catalog.room_media (
                        camp_id,
                        room_id,
                        media_type,
                        url,
                        source_kind,
                        moderation_status,
                        sort,
                        cover
                    )
                    VALUES (%s, %s, 'image', %s, 'upload', 'pending', %s, %s)
                    """,
                    (
                        camp_id,
                        room_id,
                        url,
                        int(media["sort_order"]),
                        bool(media["is_cover"]),
                    ),
                )
            cur.execute(
                """
                UPDATE moderation.submission_media
                SET status = 'copied'
                WHERE id = %s
                """,
                (int(media["id"]),),
            )

        cur.execute(
            """
            UPDATE moderation.placement_submissions
            SET published_camp_id = %s,
                status = 'object_draft_created'
            WHERE id = %s
            RETURNING content_version
            """,
            (camp_id, int(submission_id)),
        )
        cur.execute(
            """
            INSERT INTO moderation.submission_status_history (
                submission_id,
                previous_status,
                new_status,
                actor_type,
                actor_id,
                internal_comment
            )
            VALUES (
                %s, 'approved', 'object_draft_created',
                'superadmin', %s, 'Создан черновик объекта каталога'
            )
            """,
            (int(submission_id), actor_id),
        )
        conn.commit()
        return {
            "camp_id": camp_id,
            "slug": camp["slug"],
            "publication_status": camp["publication_status"],
            "status": "object_draft_created",
        }, True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def enqueue_submission_notifications(
    submission_id: int,
    *,
    event_type: str,
    title: str,
    body: str,
    admin_action_url: str,
    applicant_email: str | None = None,
    applicant_title: str | None = None,
    applicant_body: str | None = None,
    applicant_action_url: str | None = None,
    support_email: str | None = None,
    severity: str = "info",
) -> int:
    created = 0
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id
            FROM auth.superadmin_accounts
            WHERE archived_at IS NULL
              AND is_active = TRUE
              AND telegram_chat_id IS NOT NULL
            ORDER BY is_root DESC, id
            """
        )
        for recipient in cur.fetchall():
            dedupe_key = f"submission:{submission_id}:{event_type}:telegram:{recipient['id']}"
            cur.execute(
                """
                INSERT INTO crm.notification_events (
                    submission_id,
                    recipient_scope,
                    recipient_admin_id,
                    channel,
                    event_type,
                    title,
                    body,
                    action_url,
                    severity,
                    dedupe_key,
                    metadata
                )
                VALUES (
                    %s, 'superadmin', %s, 'telegram', %s, %s, %s, %s, %s, %s,
                    jsonb_build_object('submission_id', %s)
                )
                ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
                """,
                (
                    int(submission_id),
                    int(recipient["id"]),
                    event_type,
                    title,
                    body,
                    admin_action_url,
                    severity,
                    dedupe_key,
                    int(submission_id),
                ),
            )
            created += cur.rowcount
        if support_email:
            dedupe_key = f"submission:{submission_id}:{event_type}:email:support"
            cur.execute(
                """
                INSERT INTO crm.notification_events (
                    submission_id,
                    recipient_scope,
                    recipient_address,
                    channel,
                    event_type,
                    title,
                    body,
                    action_url,
                    severity,
                    dedupe_key,
                    metadata
                )
                VALUES (
                    %s, 'support', %s, 'email', %s, %s, %s, %s, %s, %s,
                    jsonb_build_object('submission_id', %s)
                )
                ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
                """,
                (
                    int(submission_id),
                    support_email,
                    event_type,
                    title,
                    body,
                    admin_action_url,
                    severity,
                    dedupe_key,
                    int(submission_id),
                ),
            )
            created += cur.rowcount
        if applicant_email and applicant_title and applicant_body:
            dedupe_key = f"submission:{submission_id}:{event_type}:email"
            cur.execute(
                """
                INSERT INTO crm.notification_events (
                    submission_id,
                    recipient_scope,
                    recipient_address,
                    channel,
                    event_type,
                    title,
                    body,
                    action_url,
                    severity,
                    dedupe_key,
                    metadata
                )
                VALUES (
                    %s, 'applicant', %s, 'email', %s, %s, %s, %s, %s, %s,
                    jsonb_build_object('submission_id', %s)
                )
                ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
                """,
                (
                    int(submission_id),
                    applicant_email,
                    event_type,
                    applicant_title,
                    applicant_body,
                    applicant_action_url,
                    severity,
                    dedupe_key,
                    int(submission_id),
                ),
            )
            created += cur.rowcount
        conn.commit()
    return created


def respond_to_clarification(
    public_number: str,
    tracking_token_hash: str,
    message: str,
) -> dict | None:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM moderation.placement_submissions
            WHERE lower(public_number) = lower(%s)
              AND tracking_token_hash = %s
            FOR UPDATE
            """,
            (public_number, tracking_token_hash),
        )
        current_row = cur.fetchone()
        if not current_row:
            return None
        current = dict(current_row)
        if current["status"] != "needs_clarification":
            raise ValueError("Ответ сейчас не требуется")
        cur.execute(
            """
            INSERT INTO moderation.submission_notes (
                submission_id,
                note_type,
                text,
                is_visible_to_applicant
            )
            VALUES (%s, 'applicant_reply', %s, TRUE)
            """,
            (current["id"], message),
        )
        cur.execute(
            """
            UPDATE moderation.placement_submissions
            SET status = 'in_review',
                status_public_comment = 'Ответ получен и передан модератору'
            WHERE id = %s
            RETURNING *
            """,
            (current["id"],),
        )
        updated = dict(cur.fetchone())
        cur.execute(
            """
            INSERT INTO moderation.submission_status_history (
                submission_id,
                previous_status,
                new_status,
                actor_type,
                public_comment
            )
            VALUES (
                %s, 'needs_clarification', 'in_review',
                'applicant', 'Получен ответ заявителя'
            )
            """,
            (current["id"],),
        )
        conn.commit()
        return updated


def mark_submission_published_by_camp(camp_id: int, *, actor_id: int | None) -> dict | None:
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM moderation.placement_submissions
            WHERE published_camp_id = %s
            FOR UPDATE
            """,
            (int(camp_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        current = dict(row)
        if current["status"] == "published":
            return current
        if current["status"] != "object_draft_created":
            raise ValueError("Статус связанной заявки не допускает публикацию")
        cur.execute(
            """
            UPDATE moderation.placement_submissions
            SET status = 'published',
                status_public_comment = 'Объект опубликован на карте'
            WHERE id = %s
            RETURNING *
            """,
            (current["id"],),
        )
        updated = dict(cur.fetchone())
        cur.execute(
            """
            INSERT INTO moderation.submission_status_history (
                submission_id,
                previous_status,
                new_status,
                actor_type,
                actor_id,
                public_comment
            )
            VALUES (
                %s, 'object_draft_created', 'published',
                'superadmin', %s, 'Объект опубликован на карте'
            )
            """,
            (current["id"], actor_id),
        )
        conn.commit()
        return updated


def expire_staged_media(*, limit: int = 200) -> list[dict]:
    safe_limit = max(1, min(int(limit), 1000))
    with _db_conn("moderation") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            WITH expired AS (
                SELECT id
                FROM moderation.submission_media
                WHERE status = 'staged'
                  AND deleted_at IS NULL
                  AND expires_at <= NOW()
                ORDER BY expires_at, id
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE moderation.submission_media media
            SET status = 'rejected',
                deleted_at = NOW(),
                is_cover = FALSE
            FROM expired
            WHERE media.id = expired.id
            RETURNING media.id, media.storage_key, media.thumbnail_storage_key
            """,
            (safe_limit,),
        )
        rows = [dict(row) for row in cur.fetchall()]
        conn.commit()
        return rows
