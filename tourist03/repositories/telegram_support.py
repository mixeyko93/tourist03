"""PostgreSQL persistence for Telegram contact support."""

from __future__ import annotations

import json
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator, Mapping, Optional

from tourist03.db import _db_conn


@contextmanager
def transaction() -> Iterator[Any]:
    with _db_conn("support") as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def register_update(
    conn,
    *,
    update_id: int,
    update_type: str,
    payload_sha256: str,
    telegram_user_id: Optional[int] = None,
    source_chat_id: Optional[int] = None,
) -> str:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO support.telegram_updates (
            update_id,
            update_type,
            payload_sha256,
            telegram_user_id,
            source_chat_id
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (update_id) DO NOTHING
        RETURNING update_id
        """,
        (
            int(update_id),
            str(update_type or "unsupported")[:100],
            payload_sha256,
            int(telegram_user_id) if telegram_user_id is not None else None,
            int(source_chat_id) if source_chat_id is not None else None,
        ),
    )
    if cur.fetchone() is not None:
        return "inserted"
    cur.execute(
        """
        SELECT payload_sha256
        FROM support.telegram_updates
        WHERE update_id = %s
        LIMIT 1
        """,
        (int(update_id),),
    )
    existing = cur.fetchone()
    if existing and secrets.compare_digest(
        str(existing.get("payload_sha256") or ""),
        str(payload_sha256 or ""),
    ):
        return "duplicate"
    return "mismatch"


def mark_update(
    conn,
    update_id: int,
    status: str,
    *,
    error: Optional[str] = None,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE support.telegram_updates
        SET status = %s,
            last_error = CASE WHEN %s IS NULL THEN NULL ELSE left(%s, 1000) END,
            processed_at = CASE
                WHEN %s IN ('processed', 'ignored', 'failed') THEN NOW()
                ELSE processed_at
            END
        WHERE update_id = %s
        """,
        (status, error, error, status, int(update_id)),
    )


def is_user_blocked(conn, telegram_user_id: int) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM support.telegram_blocklist
        WHERE telegram_user_id = %s
          AND unblocked_at IS NULL
          AND (expires_at IS NULL OR expires_at > NOW())
        LIMIT 1
        """,
        (int(telegram_user_id),),
    )
    return cur.fetchone() is not None


def block_user(
    telegram_user_id: int,
    *,
    reason: str,
    expires_at: Optional[datetime] = None,
) -> dict:
    user_id = int(telegram_user_id)
    if user_id <= 0:
        raise ValueError("Telegram user id must be positive")
    normalized_reason = str(reason or "").strip()
    if not normalized_reason:
        raise ValueError("A block reason is required")
    with transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO support.telegram_blocklist (
                telegram_user_id, reason, blocked_at, expires_at, unblocked_at
            )
            VALUES (%s, left(%s, 1000), NOW(), %s, NULL)
            ON CONFLICT (telegram_user_id) DO UPDATE
            SET reason = EXCLUDED.reason,
                blocked_at = NOW(),
                expires_at = EXCLUDED.expires_at,
                unblocked_at = NULL
            RETURNING telegram_user_id, reason, blocked_at, expires_at, unblocked_at
            """,
            (user_id, normalized_reason, expires_at),
        )
        row = dict(cur.fetchone())
        append_audit(
            conn,
            action_type="telegram_user_blocked",
            action_label="Пользователь Telegram заблокирован",
            target_type="telegram_user",
            target_id=user_id,
            metadata={"expires_at": expires_at.isoformat() if expires_at else None},
        )
        return row


def unblock_user(telegram_user_id: int) -> bool:
    user_id = int(telegram_user_id)
    if user_id <= 0:
        raise ValueError("Telegram user id must be positive")
    with transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE support.telegram_blocklist
            SET unblocked_at = NOW()
            WHERE telegram_user_id = %s
              AND unblocked_at IS NULL
            """,
            (user_id,),
        )
        changed = cur.rowcount == 1
        if changed:
            append_audit(
                conn,
                action_type="telegram_user_unblocked",
                action_label="Блокировка пользователя Telegram снята",
                target_type="telegram_user",
                target_id=user_id,
            )
        return changed


def get_operator(conn, telegram_user_id: int) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            id,
            telegram_user_id,
            display_name,
            can_reply,
            can_manage_topics,
            is_active,
            validated_at
        FROM support.telegram_operators
        WHERE telegram_user_id = %s
          AND is_active = TRUE
          AND validated_at IS NOT NULL
        LIMIT 1
        """,
        (int(telegram_user_id),),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def sync_operators(
    operator_ids: Iterable[int],
    *,
    validated_ids: Iterable[int] = (),
) -> int:
    normalized_values: set[int] = set()
    for value in operator_ids:
        try:
            normalized_value = int(value)
        except (TypeError, ValueError):
            continue
        if normalized_value > 0:
            normalized_values.add(normalized_value)
    normalized = sorted(normalized_values)
    validated: set[int] = set()
    for value in validated_ids:
        try:
            normalized_value = int(value)
        except (TypeError, ValueError):
            continue
        if normalized_value > 0:
            validated.add(normalized_value)
    with transaction() as conn:
        cur = conn.cursor()
        changed = 0
        for user_id in normalized:
            cur.execute(
                """
                INSERT INTO support.telegram_operators (
                    telegram_user_id, validated_at
                )
                VALUES (%s, CASE WHEN %s THEN NOW() ELSE NULL END)
                ON CONFLICT (telegram_user_id) DO UPDATE
                SET is_active = TRUE,
                    validated_at = CASE
                        WHEN %s THEN NOW()
                        ELSE NULL
                    END
                """,
                (user_id, user_id in validated, user_id in validated),
            )
            changed += cur.rowcount
        if normalized:
            cur.execute(
                """
                UPDATE support.telegram_operators
                SET is_active = FALSE
                WHERE NOT (telegram_user_id = ANY(%s))
                  AND is_active = TRUE
                """,
                (normalized,),
            )
        else:
            cur.execute(
                """
                UPDATE support.telegram_operators
                SET is_active = FALSE
                WHERE is_active = TRUE
                """
            )
        changed += cur.rowcount
        return changed


def lock_user(conn, telegram_user_id: int) -> None:
    cur = conn.cursor()
    cur.execute("SELECT pg_advisory_xact_lock(%s)", (int(telegram_user_id),))


def get_open_ticket_for_user(
    conn,
    telegram_user_id: int,
    *,
    for_update: bool = False,
) -> Optional[dict]:
    cur = conn.cursor()
    suffix = " FOR UPDATE" if for_update else ""
    cur.execute(
        f"""
        SELECT *
        FROM support.telegram_tickets
        WHERE telegram_user_id = %s
          AND status IN ('opening', 'open')
        ORDER BY id DESC
        LIMIT 1
        {suffix}
        """,
        (int(telegram_user_id),),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_latest_closed_ticket_for_user(
    conn,
    telegram_user_id: int,
    *,
    for_update: bool = False,
) -> Optional[dict]:
    cur = conn.cursor()
    suffix = " FOR UPDATE" if for_update else ""
    cur.execute(
        f"""
        SELECT *
        FROM support.telegram_tickets
        WHERE telegram_user_id = %s
          AND status = 'closed'
        ORDER BY closed_at DESC NULLS LAST, id DESC
        LIMIT 1
        {suffix}
        """,
        (int(telegram_user_id),),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_ticket_by_topic(
    conn,
    *,
    support_chat_id: int,
    message_thread_id: int,
    for_update: bool = False,
) -> Optional[dict]:
    cur = conn.cursor()
    suffix = " FOR UPDATE" if for_update else ""
    cur.execute(
        f"""
        SELECT *
        FROM support.telegram_tickets
        WHERE support_chat_id = %s
          AND message_thread_id = %s
        LIMIT 1
        {suffix}
        """,
        (int(support_chat_id), int(message_thread_id)),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_ticket_by_relay_destination(
    conn,
    *,
    support_chat_id: int,
    message_thread_id: int,
    destination_message_id: int,
    for_update: bool = False,
) -> Optional[dict]:
    """Resolve a shared-topic reply to the exact ticket message it answers."""

    cur = conn.cursor()
    suffix = " FOR UPDATE OF tickets" if for_update else ""
    cur.execute(
        f"""
        SELECT tickets.*
        FROM support.telegram_messages messages
        JOIN support.telegram_tickets tickets ON tickets.id = messages.ticket_id
        WHERE messages.destination_chat_id = %s
          AND messages.destination_thread_id = %s
          AND messages.destination_message_id = %s
        ORDER BY messages.id DESC
        LIMIT 1
        {suffix}
        """,
        (
            int(support_chat_id),
            int(message_thread_id),
            int(destination_message_id),
        ),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def get_ticket(conn, ticket_id: int, *, for_update: bool = False) -> Optional[dict]:
    cur = conn.cursor()
    suffix = " FOR UPDATE" if for_update else ""
    cur.execute(
        f"""
        SELECT *
        FROM support.telegram_tickets
        WHERE id = %s
        LIMIT 1
        {suffix}
        """,
        (int(ticket_id),),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def ensure_open_ticket(
    conn,
    *,
    telegram_user_id: int,
    private_chat_id: int,
    support_chat_id: int,
    source_type: str = "general",
    source_id: Optional[str] = None,
    source_snapshot: Optional[Mapping[str, Any]] = None,
    message_thread_id: Optional[int] = None,
) -> tuple[dict, bool]:
    lock_user(conn, telegram_user_id)
    existing = get_open_ticket_for_user(conn, telegram_user_id, for_update=True)
    if existing:
        incoming_snapshot = dict(source_snapshot or {})
        if source_type != "general" or incoming_snapshot.get("topic_key"):
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE support.telegram_tickets
                SET source_type = %s,
                    source_id = %s,
                    source_snapshot = %s::jsonb,
                    message_thread_id = COALESCE(%s, message_thread_id),
                    status = CASE WHEN %s IS NULL THEN status ELSE 'open' END
                WHERE id = %s
                RETURNING *
                """,
                (
                    source_type,
                    source_id,
                    json.dumps(incoming_snapshot, ensure_ascii=False),
                    int(message_thread_id) if message_thread_id is not None else None,
                    int(message_thread_id) if message_thread_id is not None else None,
                    int(existing["id"]),
                ),
            )
            return dict(cur.fetchone()), False
        return existing, False

    public_number = (
        f"TG-{datetime.now(timezone.utc):%Y%m%d}-"
        f"{secrets.token_hex(5).upper()}"
    )
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO support.telegram_tickets (
            public_number,
            telegram_user_id,
            private_chat_id,
            support_chat_id,
            message_thread_id,
            status,
            source_type,
            source_id,
            source_snapshot
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING *
        """,
        (
            public_number,
            int(telegram_user_id),
            int(private_chat_id),
            int(support_chat_id),
            int(message_thread_id) if message_thread_id is not None else None,
            "open" if message_thread_id is not None else "opening",
            source_type,
            source_id,
            json.dumps(dict(source_snapshot or {}), ensure_ascii=False),
        ),
    )
    return dict(cur.fetchone()), True


def close_ticket(conn, ticket_id: int) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE support.telegram_tickets
        SET status = 'closed',
            closed_at = COALESCE(closed_at, NOW())
        WHERE id = %s
          AND status IN ('opening', 'open')
        RETURNING *
        """,
        (int(ticket_id),),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def reopen_ticket(conn, ticket_id: int) -> Optional[dict]:
    ticket = get_ticket(conn, ticket_id, for_update=True)
    if not ticket or ticket.get("status") != "closed":
        return None
    lock_user(conn, int(ticket["telegram_user_id"]))
    if get_open_ticket_for_user(conn, int(ticket["telegram_user_id"]), for_update=True):
        return None
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE support.telegram_tickets
        SET status = CASE WHEN message_thread_id IS NULL THEN 'opening' ELSE 'open' END,
            reopened_at = NOW(),
            closed_at = NULL
        WHERE id = %s
          AND status = 'closed'
        RETURNING *
        """,
        (int(ticket_id),),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def set_ticket_topic(conn, ticket_id: int, message_thread_id: int) -> dict:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE support.telegram_tickets
        SET message_thread_id = %s,
            status = CASE WHEN status = 'opening' THEN 'open' ELSE status END
        WHERE id = %s
          AND message_thread_id IS NULL
        RETURNING *
        """,
        (int(message_thread_id), int(ticket_id)),
    )
    row = cur.fetchone()
    if row:
        return dict(row)
    existing = get_ticket(conn, ticket_id)
    if not existing or int(existing.get("message_thread_id") or 0) != int(message_thread_id):
        raise RuntimeError("Telegram topic was not attached to the ticket")
    return existing


def touch_ticket_message_time(
    conn,
    ticket_id: int,
    *,
    direction: str,
) -> None:
    field = (
        "last_user_message_at"
        if direction == "user_to_support"
        else "last_operator_message_at"
    )
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE support.telegram_tickets
        SET {field} = NOW()
        WHERE id = %s
        """,
        (int(ticket_id),),
    )


def count_recent_user_messages(
    conn,
    telegram_user_id: int,
    *,
    window_seconds: int = 60,
) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) AS count
        FROM support.telegram_messages
        WHERE sender_user_id = %s
          AND direction = 'user_to_support'
          AND created_at >= NOW() - (%s * INTERVAL '1 second')
        """,
        (int(telegram_user_id), max(int(window_seconds), 1)),
    )
    row = cur.fetchone()
    return int(row["count"] if row else 0)


def count_recent_user_updates(
    conn,
    telegram_user_id: int,
    *,
    window_seconds: int = 60,
) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) AS count
        FROM support.telegram_updates
        WHERE telegram_user_id = %s
          AND received_at >= NOW() - (%s * INTERVAL '1 second')
        """,
        (int(telegram_user_id), max(int(window_seconds), 1)),
    )
    row = cur.fetchone()
    return int(row["count"] if row else 0)


def create_message(
    conn,
    *,
    ticket_id: int,
    direction: str,
    telegram_update_id: Optional[int],
    source_chat_id: Optional[int],
    source_message_id: Optional[int],
    sender_user_id: Optional[int],
    reply_to_source_message_id: Optional[int],
    message_kind: str,
    text: Optional[str] = None,
    caption: Optional[str] = None,
    file_id: Optional[str] = None,
    file_unique_id: Optional[str] = None,
    file_name: Optional[str] = None,
    mime_type: Optional[str] = None,
    file_size: Optional[int] = None,
) -> dict:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO support.telegram_messages (
            ticket_id,
            direction,
            telegram_update_id,
            source_chat_id,
            source_message_id,
            sender_user_id,
            reply_to_source_message_id,
            message_kind,
            text,
            caption,
            file_id,
            file_unique_id,
            file_name,
            mime_type,
            file_size
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING *
        """,
        (
            int(ticket_id),
            direction,
            int(telegram_update_id) if telegram_update_id is not None else None,
            int(source_chat_id) if source_chat_id is not None else None,
            int(source_message_id) if source_message_id is not None else None,
            int(sender_user_id) if sender_user_id is not None else None,
            int(reply_to_source_message_id)
            if reply_to_source_message_id is not None
            else None,
            message_kind,
            text,
            caption,
            file_id,
            file_unique_id,
            file_name,
            mime_type,
            int(file_size) if file_size is not None else None,
        ),
    )
    message = dict(cur.fetchone())
    touch_ticket_message_time(conn, ticket_id, direction=direction)
    return message


def enqueue_outbox(
    conn,
    *,
    action: str,
    dedupe_key: str,
    ticket_id: Optional[int] = None,
    message_id: Optional[int] = None,
    payload: Optional[Mapping[str, Any]] = None,
) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO support.telegram_outbox (
            ticket_id, message_id, action, dedupe_key, payload
        )
        VALUES (%s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (dedupe_key) DO NOTHING
        RETURNING *
        """,
        (
            int(ticket_id) if ticket_id is not None else None,
            int(message_id) if message_id is not None else None,
            action,
            dedupe_key,
            json.dumps(dict(payload or {}), ensure_ascii=False),
        ),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def append_audit(
    conn,
    *,
    action_type: str,
    action_label: str,
    target_type: str,
    target_id: Optional[Any] = None,
    actor_type: str = "telegram_support",
    actor_id: Optional[int] = None,
    actor_display: Optional[str] = None,
    comment: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO crm.audit_log (
            actor_type,
            actor_id,
            actor_display,
            target_type,
            target_id,
            action_type,
            action_label,
            comment,
            was_auto_applied,
            metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s::jsonb)
        """,
        (
            actor_type,
            int(actor_id) if actor_id is not None else None,
            actor_display,
            target_type,
            str(target_id) if target_id is not None else None,
            action_type,
            action_label,
            comment,
            json.dumps(dict(metadata or {}), ensure_ascii=False),
        ),
    )


def resolve_source_context(
    conn,
    *,
    source_type: str,
    source_id: Optional[int],
    public_base_url: str,
) -> dict:
    base_url = str(public_base_url or "").rstrip("/")
    if source_type == "general" or source_id is None:
        return {
            "source_type": "general",
            "title": "Общий вопрос",
            "canonical_url": f"{base_url}/" if base_url else None,
        }

    cur = conn.cursor()
    if source_type == "entity":
        cur.execute(
            """
            SELECT
                camps.id,
                camps.name AS title,
                camps.slug,
                kinds.name AS kind_name
            FROM catalog.camps camps
            JOIN catalog.place_types types ON types.id = camps.place_type_id
            JOIN catalog.entity_kinds kinds ON kinds.id = types.entity_kind_id
            WHERE camps.id = %s
              AND camps.publication_status = 'published'
              AND lower(COALESCE(camps.status, '')) IN ('active', 'published')
              AND camps.visibility = 'public'
              AND types.is_active = TRUE
              AND kinds.is_active = TRUE
            LIMIT 1
            """,
            (int(source_id),),
        )
        row = cur.fetchone()
        if row:
            return {
                "source_type": "entity",
                "title": str(row["title"]),
                "id": int(row["id"]),
                "kind": str(row.get("kind_name") or "Объект"),
                "canonical_url": f"{base_url}/places/{row['slug']}",
            }
    elif source_type == "route":
        cur.execute(
            """
            SELECT id, title, slug
            FROM content.routes
            WHERE id = %s AND status = 'published'
            LIMIT 1
            """,
            (int(source_id),),
        )
        row = cur.fetchone()
        if row:
            return {
                "source_type": "route",
                "title": str(row["title"]),
                "id": int(row["id"]),
                "canonical_url": f"{base_url}/routes/{row['slug']}",
            }
    elif source_type == "collection":
        cur.execute(
            """
            SELECT id, title, slug
            FROM content.collections
            WHERE id = %s AND status = 'published'
            LIMIT 1
            """,
            (int(source_id),),
        )
        row = cur.fetchone()
        if row:
            return {
                "source_type": "collection",
                "title": str(row["title"]),
                "id": int(row["id"]),
                "canonical_url": f"{base_url}/collections/{row['slug']}",
            }
    elif source_type == "submission":
        cur.execute(
            """
            SELECT id, public_number, place_name
            FROM moderation.placement_submissions
            WHERE id = %s
            LIMIT 1
            """,
            (int(source_id),),
        )
        row = cur.fetchone()
        if row:
            return {
                "source_type": "submission",
                "title": str(row.get("place_name") or "Заявка на размещение"),
                "id": int(row["id"]),
                "public_number": str(row["public_number"]),
                "canonical_url": None,
            }

    # A signed but no longer public/deleted source must not leak its former data.
    return {
        "source_type": "general",
        "title": "Общий вопрос",
        "canonical_url": f"{base_url}/" if base_url else None,
    }


def claim_outbox_batch(
    *,
    limit: int = 50,
    lease_seconds: int = 60,
) -> list[dict]:
    safe_limit = max(1, min(int(limit), 200))
    safe_lease = max(10, min(int(lease_seconds), 600))
    batch_token = secrets.token_urlsafe(32)
    with transaction() as conn:
        cur = conn.cursor()
        # Creating a forum topic is not idempotent in Telegram Bot API.  If a
        # worker disappears after the remote call, an expired lease is an
        # ambiguous outcome and must never be blindly retried.  Quarantine it
        # for operator reconciliation before claiming ordinary retryable work.
        cur.execute(
            """
            UPDATE support.telegram_outbox
            SET status = 'dead_letter',
                claim_token = NULL,
                lease_until = NULL,
                last_error = left(
                    COALESCE(last_error || '; ', '')
                    || 'create_topic lease expired; manual reconciliation required',
                    1000
                ),
                telegram_result = jsonb_build_object(
                    'manual_reconciliation_required', TRUE,
                    'reason', 'expired_create_topic_lease'
                ),
                updated_at = NOW()
            WHERE action = 'create_topic'
              AND status = 'processing'
              AND lease_until < NOW()
            RETURNING id, ticket_id, attempts
            """
        )
        for stale in cur.fetchall():
            append_audit(
                conn,
                action_type="telegram_topic_creation_ambiguous",
                action_label="Создание темы требует ручной сверки",
                target_type="telegram_ticket",
                target_id=stale.get("ticket_id"),
                metadata={
                    "outbox_id": int(stale["id"]),
                    "attempts": int(stale.get("attempts") or 0),
                    "reason": "expired_create_topic_lease",
                },
            )
        # None of the Bot API delivery operations below accepts an
        # application-level idempotency key.  An expired processing lease can
        # therefore mean that Telegram accepted the request while the worker
        # died before committing the local ACK.  Reclaiming such a row would
        # risk sending/copying the same message twice (or repeating a topic
        # state change), so fail closed and require operator reconciliation.
        cur.execute(
            """
            UPDATE support.telegram_outbox
            SET status = 'dead_letter',
                claim_token = NULL,
                lease_until = NULL,
                last_error = left(
                    COALESCE(last_error || '; ', '')
                    || 'delivery lease expired; manual reconciliation required',
                    1000
                ),
                telegram_result = jsonb_build_object(
                    'manual_reconciliation_required', TRUE,
                    'reason', 'expired_delivery_lease',
                    'action', action
                ),
                updated_at = NOW()
            WHERE action <> 'create_topic'
              AND status = 'processing'
              AND lease_until < NOW()
            RETURNING id, ticket_id, message_id, action, attempts
            """
        )
        for stale in cur.fetchall():
            if stale.get("message_id"):
                cur.execute(
                    """
                    UPDATE support.telegram_messages
                    SET delivery_status = 'dead_letter'
                    WHERE id = %s
                    """,
                    (int(stale["message_id"]),),
                )
            append_audit(
                conn,
                action_type="telegram_delivery_ambiguous",
                action_label="Доставка Telegram требует ручной сверки",
                target_type="telegram_ticket",
                target_id=stale.get("ticket_id"),
                metadata={
                    "outbox_id": int(stale["id"]),
                    "action": str(stale["action"]),
                    "attempts": int(stale.get("attempts") or 0),
                    "reason": "expired_delivery_lease",
                },
            )
        cur.execute(
            """
            WITH candidates AS (
                SELECT outbox.id
                FROM support.telegram_outbox outbox
                LEFT JOIN support.telegram_tickets tickets
                  ON tickets.id = outbox.ticket_id
                WHERE (
                        outbox.status IN ('pending', 'retry')
                        AND outbox.next_attempt_at <= NOW()
                    )
                  AND (
                        outbox.action IN ('send_text_user', 'copy_operator_to_user')
                        OR (
                            outbox.action = 'create_topic'
                            AND tickets.message_thread_id IS NULL
                        )
                        OR (
                            outbox.action IN (
                                'copy_user_to_topic', 'send_text_topic',
                                'close_topic', 'reopen_topic'
                            )
                            AND tickets.message_thread_id IS NOT NULL
                        )
                    )
                ORDER BY outbox.next_attempt_at, outbox.id
                FOR UPDATE OF outbox SKIP LOCKED
                LIMIT %s
            )
            UPDATE support.telegram_outbox outbox
            SET status = 'processing',
                attempts = attempts + 1,
                claim_token = %s || ':' || outbox.id::text,
                lease_until = NOW() + (%s * INTERVAL '1 second'),
                updated_at = NOW()
            FROM candidates
            WHERE outbox.id = candidates.id
            RETURNING outbox.*
            """,
            (safe_limit, batch_token, safe_lease),
        )
        return [dict(row) for row in cur.fetchall()]


def load_delivery_context(outbox_id: int, claim_token: str) -> Optional[dict]:
    with _db_conn("support") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                outbox.*,
                tickets.public_number,
                tickets.telegram_user_id,
                tickets.private_chat_id,
                tickets.support_chat_id,
                tickets.message_thread_id,
                tickets.status AS ticket_status,
                tickets.source_snapshot,
                messages.source_chat_id,
                messages.source_message_id,
                messages.reply_to_source_message_id,
                messages.direction,
                messages.message_kind,
                messages.text,
                messages.caption
            FROM support.telegram_outbox outbox
            LEFT JOIN support.telegram_tickets tickets
              ON tickets.id = outbox.ticket_id
            LEFT JOIN support.telegram_messages messages
              ON messages.id = outbox.message_id
            WHERE outbox.id = %s
              AND outbox.status = 'processing'
              AND outbox.claim_token = %s
              AND outbox.lease_until > NOW()
            LIMIT 1
            """,
            (int(outbox_id), claim_token),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def find_relay_reply_message_id(
    *,
    source_chat_id: int,
    destination_message_id: int,
) -> Optional[int]:
    with _db_conn("support") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT source_message_id
            FROM support.telegram_messages
            WHERE destination_chat_id = %s
              AND destination_message_id = %s
              AND source_message_id IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (int(source_chat_id), int(destination_message_id)),
        )
        row = cur.fetchone()
        return int(row["source_message_id"]) if row else None


def mark_outbox_sent(
    outbox_id: int,
    claim_token: str,
    *,
    telegram_result: Optional[Mapping[str, Any]] = None,
    destination_chat_id: Optional[int] = None,
    destination_thread_id: Optional[int] = None,
    destination_message_id: Optional[int] = None,
) -> bool:
    with transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE support.telegram_outbox
            SET status = 'sent',
                telegram_result = %s::jsonb,
                sent_at = NOW(),
                claim_token = NULL,
                lease_until = NULL,
                last_error = NULL,
                updated_at = NOW()
            WHERE id = %s
              AND status = 'processing'
              AND claim_token = %s
            RETURNING message_id
            """,
            (
                json.dumps(dict(telegram_result or {}), ensure_ascii=False),
                int(outbox_id),
                claim_token,
            ),
        )
        row = cur.fetchone()
        if row and row.get("message_id"):
            cur.execute(
                """
                UPDATE support.telegram_messages
                SET delivery_status = 'sent',
                    destination_chat_id = %s,
                    destination_thread_id = %s,
                    destination_message_id = %s,
                    delivered_at = NOW()
                WHERE id = %s
                """,
                (
                    int(destination_chat_id)
                    if destination_chat_id is not None
                    else None,
                    int(destination_thread_id)
                    if destination_thread_id is not None
                    else None,
                    int(destination_message_id)
                    if destination_message_id is not None
                    else None,
                    int(row["message_id"]),
                ),
            )
        return row is not None


def mark_delivery_ambiguous(
    outbox_id: int,
    claim_token: str,
    *,
    error: str,
    telegram_result: Optional[Mapping[str, Any]] = None,
    destination_chat_id: Optional[int] = None,
    destination_thread_id: Optional[int] = None,
    destination_message_id: Optional[int] = None,
) -> str:
    """Quarantine a remotely delivered action whose local ACK failed.

    Telegram has no caller-supplied idempotency key for message delivery and
    topic state changes.  Once the remote call has returned successfully, a
    local persistence error must therefore never put the row back on the retry
    queue.  This method records all non-sensitive identifiers available for
    manual reconciliation and remains claim-token fenced.
    """

    result = dict(telegram_result or {})
    result.update(
        {
            "manual_reconciliation_required": True,
            "remote_delivery_confirmed": True,
            "reason": "remote_success_ack_failed",
        }
    )
    if destination_chat_id is not None:
        result["destination_chat_id"] = int(destination_chat_id)
    if destination_thread_id is not None:
        result["destination_thread_id"] = int(destination_thread_id)
    if destination_message_id is not None:
        result["destination_message_id"] = int(destination_message_id)

    with transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id, ticket_id, message_id, action, attempts, status, claim_token
            FROM support.telegram_outbox
            WHERE id = %s
              AND action <> 'create_topic'
              AND (
                    (status = 'processing' AND claim_token = %s)
                    OR status IN ('sent', 'dead_letter')
              )
            FOR UPDATE
            """,
            (int(outbox_id), claim_token),
        )
        row = cur.fetchone()
        if not row:
            return "missing"
        if row["status"] == "sent":
            # The database may have committed the ACK even if the client
            # observed a connection error while receiving the response.
            return "sent"
        result["action"] = str(row["action"])
        cur.execute(
            """
            UPDATE support.telegram_outbox
            SET status = 'dead_letter',
                claim_token = NULL,
                lease_until = NULL,
                last_error = left(%s, 1000),
                telegram_result = %s::jsonb,
                updated_at = NOW()
            WHERE id = %s
              AND action <> 'create_topic'
              AND status IN ('processing', 'dead_letter')
            """,
            (
                error or "Remote Telegram delivery succeeded but local ACK failed",
                json.dumps(result, ensure_ascii=False),
                int(outbox_id),
            ),
        )
        if row.get("message_id"):
            cur.execute(
                """
                UPDATE support.telegram_messages
                SET delivery_status = 'dead_letter',
                    destination_chat_id = %s,
                    destination_thread_id = %s,
                    destination_message_id = %s,
                    delivered_at = COALESCE(delivered_at, NOW())
                WHERE id = %s
                """,
                (
                    int(destination_chat_id)
                    if destination_chat_id is not None
                    else None,
                    int(destination_thread_id)
                    if destination_thread_id is not None
                    else None,
                    int(destination_message_id)
                    if destination_message_id is not None
                    else None,
                    int(row["message_id"]),
                ),
            )
        append_audit(
            conn,
            action_type="telegram_delivery_ambiguous",
            action_label="Доставка Telegram требует ручной сверки",
            target_type="telegram_ticket",
            target_id=row.get("ticket_id"),
            metadata={
                "outbox_id": int(outbox_id),
                "action": str(row["action"]),
                "attempts": int(row.get("attempts") or 0),
                "destination_chat_id": destination_chat_id,
                "destination_thread_id": destination_thread_id,
                "destination_message_id": destination_message_id,
                "reason": "remote_success_ack_failed",
            },
        )
        return "dead_letter"


def complete_topic_creation(
    outbox_id: int,
    claim_token: str,
    *,
    ticket_id: int,
    support_chat_id: int,
    message_thread_id: int,
) -> None:
    """Atomically attach a remotely created topic and complete its outbox row."""

    with transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id
            FROM support.telegram_outbox
            WHERE id = %s
              AND action = 'create_topic'
              AND status = 'processing'
              AND claim_token = %s
            FOR UPDATE
            """,
            (int(outbox_id), claim_token),
        )
        if cur.fetchone() is None:
            raise RuntimeError("Telegram topic outbox claim is no longer current")
        set_ticket_topic(conn, int(ticket_id), int(message_thread_id))
        cur.execute(
            """
            UPDATE support.telegram_outbox
            SET status = 'sent',
                telegram_result = %s::jsonb,
                sent_at = NOW(),
                claim_token = NULL,
                lease_until = NULL,
                last_error = NULL,
                updated_at = NOW()
            WHERE id = %s
              AND action = 'create_topic'
              AND status = 'processing'
              AND claim_token = %s
            """,
            (
                json.dumps(
                    {
                        "support_chat_id": int(support_chat_id),
                        "message_thread_id": int(message_thread_id),
                    },
                    ensure_ascii=False,
                ),
                int(outbox_id),
                claim_token,
            ),
        )
        if cur.rowcount != 1:
            raise RuntimeError("Telegram topic outbox row was not completed")


def mark_topic_creation_ambiguous(
    outbox_id: int,
    claim_token: str,
    *,
    error: str,
    support_chat_id: Optional[int] = None,
    message_thread_id: Optional[int] = None,
) -> str:
    """Dead-letter a non-idempotent topic creation without blind retries.

    A known remote thread id is retained even when a competing worker already
    quarantined an expired lease.  This gives an operator enough information to
    reconcile the ticket without creating another Telegram topic.
    """

    result = {
        "manual_reconciliation_required": True,
        "reason": "ambiguous_create_topic_result",
    }
    if support_chat_id is not None:
        result["support_chat_id"] = int(support_chat_id)
    if message_thread_id is not None:
        result["message_thread_id"] = int(message_thread_id)
    with transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, ticket_id, attempts, status, claim_token
            FROM support.telegram_outbox
            WHERE id = %s
              AND action = 'create_topic'
              AND (
                    (status = 'processing' AND claim_token = %s)
                    OR status = 'dead_letter'
              )
            FOR UPDATE
            """,
            (int(outbox_id), claim_token),
        )
        row = cur.fetchone()
        if not row:
            return "missing"
        if row["status"] == "dead_letter" and message_thread_id is None:
            return "dead_letter"
        cur.execute(
            """
            UPDATE support.telegram_outbox
            SET status = 'dead_letter',
                claim_token = NULL,
                lease_until = NULL,
                last_error = left(%s, 1000),
                telegram_result = %s::jsonb,
                updated_at = NOW()
            WHERE id = %s
              AND action = 'create_topic'
            """,
            (
                error or "Ambiguous Telegram create_topic result",
                json.dumps(result, ensure_ascii=False),
                int(outbox_id),
            ),
        )
        append_audit(
            conn,
            action_type="telegram_topic_creation_ambiguous",
            action_label="Создание темы требует ручной сверки",
            target_type="telegram_ticket",
            target_id=row.get("ticket_id"),
            metadata={
                "outbox_id": int(outbox_id),
                "attempts": int(row.get("attempts") or 0),
                "support_chat_id": support_chat_id,
                "message_thread_id": message_thread_id,
            },
        )
        return "dead_letter"


def reconcile_topic_creation(
    *,
    ticket_id: int,
    support_chat_id: int,
    message_thread_id: int,
) -> dict:
    """Attach an operator-verified topic after an ambiguous remote result."""

    if int(support_chat_id) >= 0 or int(message_thread_id) <= 0:
        raise ValueError("A supergroup and positive message thread id are required")
    with transaction() as conn:
        ticket = get_ticket(conn, int(ticket_id), for_update=True)
        if not ticket:
            raise ValueError("Telegram ticket does not exist")
        if int(ticket.get("support_chat_id") or 0) != int(support_chat_id):
            raise ValueError("Telegram support chat does not match the ticket")
        if ticket.get("message_thread_id") is not None:
            if int(ticket["message_thread_id"]) != int(message_thread_id):
                raise ValueError("Telegram ticket is already attached to another topic")
            return ticket
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, telegram_result
            FROM support.telegram_outbox
            WHERE ticket_id = %s
              AND action = 'create_topic'
              AND status = 'dead_letter'
              AND COALESCE(
                    (telegram_result ->> 'manual_reconciliation_required')::boolean,
                    FALSE
              ) = TRUE
            ORDER BY id DESC
            LIMIT 1
            FOR UPDATE
            """,
            (int(ticket_id),),
        )
        outbox = cur.fetchone()
        if not outbox:
            raise ValueError("Ticket has no ambiguous topic creation to reconcile")
        attached = set_ticket_topic(conn, int(ticket_id), int(message_thread_id))
        result = dict(outbox.get("telegram_result") or {})
        result.update(
            {
                "manual_reconciliation_required": False,
                "reconciled": True,
                "support_chat_id": int(support_chat_id),
                "message_thread_id": int(message_thread_id),
            }
        )
        cur.execute(
            """
            UPDATE support.telegram_outbox
            SET status = 'sent',
                telegram_result = %s::jsonb,
                sent_at = NOW(),
                last_error = NULL,
                claim_token = NULL,
                lease_until = NULL,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                json.dumps(result, ensure_ascii=False),
                int(outbox["id"]),
            ),
        )
        append_audit(
            conn,
            action_type="telegram_topic_creation_reconciled",
            action_label="Тема Telegram сверена вручную",
            target_type="telegram_ticket",
            target_id=ticket_id,
            metadata={
                "outbox_id": int(outbox["id"]),
                "support_chat_id": int(support_chat_id),
                "message_thread_id": int(message_thread_id),
            },
        )
        return attached


def mark_outbox_failed(
    outbox_id: int,
    claim_token: str,
    *,
    error: str,
    max_attempts: int,
    retry_after_seconds: Optional[int] = None,
    permanent: bool = False,
) -> str:
    safe_max = max(1, int(max_attempts))
    with transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT attempts, message_id, ticket_id
            FROM support.telegram_outbox
            WHERE id = %s
              AND status = 'processing'
              AND claim_token = %s
            FOR UPDATE
            """,
            (int(outbox_id), claim_token),
        )
        row = cur.fetchone()
        if not row:
            return "missing"
        attempts = int(row.get("attempts") or 0)
        dead_letter = bool(permanent or attempts >= safe_max)
        status = "dead_letter" if dead_letter else "retry"
        retry_seconds = (
            max(1, min(int(retry_after_seconds), 86_400))
            if retry_after_seconds is not None
            else min(3600, max(5, 5 * (2 ** max(0, min(attempts - 1, 9)))))
        )
        cur.execute(
            """
            UPDATE support.telegram_outbox
            SET status = %s,
                next_attempt_at = NOW() + (%s * INTERVAL '1 second'),
                claim_token = NULL,
                lease_until = NULL,
                last_error = left(%s, 1000),
                updated_at = NOW()
            WHERE id = %s
              AND status = 'processing'
              AND claim_token = %s
            """,
            (
                status,
                retry_seconds,
                error or "Telegram delivery failed",
                int(outbox_id),
                claim_token,
            ),
        )
        if row.get("message_id"):
            cur.execute(
                """
                UPDATE support.telegram_messages
                SET delivery_status = %s
                WHERE id = %s
                """,
                (status, int(row["message_id"])),
            )
        if dead_letter:
            append_audit(
                conn,
                action_type="telegram_delivery_dead_letter",
                action_label="Доставка Telegram исчерпала попытки",
                target_type="telegram_ticket",
                target_id=row.get("ticket_id"),
                metadata={"outbox_id": int(outbox_id), "attempts": attempts},
            )
        return status
