import secrets
from typing import Optional

from tourist03.db import _db_conn


def get_staff_account_by_chat_id(chat_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                email,
                display_name,
                phone,
                default_role_key,
                telegram_chat_id,
                telegram_username
            FROM auth.camp_admin_accounts
            WHERE telegram_chat_id = %s
              AND archived_at IS NULL
              AND is_active = TRUE
            LIMIT 1
            """,
            (int(chat_id),),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_superadmin_account_by_chat_id(chat_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                login,
                display_name,
                phone,
                is_root,
                telegram_chat_id,
                telegram_username
            FROM auth.superadmin_accounts
            WHERE telegram_chat_id = %s
              AND archived_at IS NULL
              AND is_active = TRUE
            LIMIT 1
            """,
            (int(chat_id),),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def list_staff_camp_ids(admin_id: int) -> list[int]:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT camp_id
            FROM crm.camp_admin_links
            WHERE admin_id = %s
            ORDER BY camp_id ASC
            """,
            (int(admin_id),),
        )
        return [int(row["camp_id"]) for row in cur.fetchall()]


def list_recent_open_events_for_admin(admin_id: int, camp_ids: list[int], *, limit: int = 5):
    safe_limit = max(1, min(int(limit or 5), 20))
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                e.id,
                e.camp_id,
                c.name AS camp_name,
                e.recipient_scope,
                e.event_type,
                e.title,
                e.body,
                e.action_url,
                e.metadata,
                e.severity,
                e.status,
                e.created_at
            FROM crm.notification_events e
            LEFT JOIN catalog.camps c ON c.id = e.camp_id
            WHERE e.recipient_scope = 'crm'
              AND e.channel = 'in_app'
              AND e.status <> 'closed'
              AND (
                    e.recipient_admin_id = %s
                    OR (
                        e.recipient_admin_id IS NULL
                        AND (
                            e.camp_id IS NULL
                            OR e.camp_id = ANY(%s)
                        )
                    )
              )
            ORDER BY
                CASE e.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                e.created_at DESC,
                e.id DESC
            LIMIT %s
            """,
            (int(admin_id), camp_ids, safe_limit),
        )
        return [dict(row) for row in cur.fetchall()]


def list_recent_open_events_for_superadmin(account_id: int, *, limit: int = 5):
    safe_limit = max(1, min(int(limit or 5), 20))
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                e.id,
                e.camp_id,
                c.name AS camp_name,
                e.recipient_scope,
                e.event_type,
                e.title,
                e.body,
                e.action_url,
                e.severity,
                e.status,
                e.metadata,
                e.created_at
            FROM crm.notification_events e
            LEFT JOIN catalog.camps c ON c.id = e.camp_id
            WHERE e.recipient_scope = 'superadmin'
              AND e.channel = 'in_app'
              AND e.status <> 'closed'
              AND (
                    e.recipient_admin_id = %s
                    OR e.recipient_admin_id IS NULL
              )
            ORDER BY
                CASE e.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                e.created_at DESC,
                e.id DESC
            LIMIT %s
            """,
            (int(account_id), safe_limit),
        )
        return [dict(row) for row in cur.fetchall()]


def list_active_staff_telegram_recipients(
    camp_id: int,
    *,
    admin_ids: Optional[list[int]] = None,
    exclude_admin_ids: Optional[list[int]] = None,
):
    conditions = [
        "l.camp_id = %s",
        "a.archived_at IS NULL",
        "a.is_active = TRUE",
        "a.notifications_enabled = TRUE",
        "a.telegram_chat_id IS NOT NULL",
    ]
    params: list = [int(camp_id)]

    if admin_ids is not None:
        normalized_admin_ids = [int(value) for value in admin_ids if value is not None]
        if not normalized_admin_ids:
            return []
        conditions.append("a.id = ANY(%s)")
        params.append(normalized_admin_ids)

    if exclude_admin_ids:
        normalized_excluded = [int(value) for value in exclude_admin_ids if value is not None]
        if normalized_excluded:
            conditions.append("NOT (a.id = ANY(%s))")
            params.append(normalized_excluded)

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT DISTINCT
                a.id,
                a.display_name,
                a.email,
                a.telegram_chat_id,
                a.telegram_username,
                l.role_key,
                l.is_primary,
                l.can_manage_staff
            FROM crm.camp_admin_links l
            JOIN auth.camp_admin_accounts a ON a.id = l.admin_id
            WHERE {' AND '.join(conditions)}
            ORDER BY l.is_primary DESC, a.display_name ASC, a.id ASC
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def list_manager_telegram_recipients(camp_id: int, *, exclude_admin_ids: Optional[list[int]] = None):
    conditions = [
        "l.camp_id = %s",
        "a.archived_at IS NULL",
        "a.is_active = TRUE",
        "a.notifications_enabled = TRUE",
        "a.telegram_chat_id IS NOT NULL",
        "(l.is_primary = TRUE OR l.can_manage_staff = TRUE OR l.role_key IN ('chief_manager', 'administrator'))",
    ]
    params: list = [int(camp_id)]
    if exclude_admin_ids:
        normalized_excluded = [int(value) for value in exclude_admin_ids if value is not None]
        if normalized_excluded:
            conditions.append("NOT (a.id = ANY(%s))")
            params.append(normalized_excluded)

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT DISTINCT
                a.id,
                a.display_name,
                a.email,
                a.telegram_chat_id,
                a.telegram_username,
                l.role_key,
                l.is_primary,
                l.can_manage_staff
            FROM crm.camp_admin_links l
            JOIN auth.camp_admin_accounts a ON a.id = l.admin_id
            WHERE {' AND '.join(conditions)}
            ORDER BY l.is_primary DESC, a.display_name ASC, a.id ASC
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def list_active_superadmin_telegram_recipients(*, exclude_account_ids: Optional[list[int]] = None, root_only: bool = False):
    conditions = [
        "archived_at IS NULL",
        "is_active = TRUE",
        "telegram_chat_id IS NOT NULL",
    ]
    params: list = []
    if root_only:
        conditions.append("is_root = TRUE")
    if exclude_account_ids:
        normalized = [int(value) for value in exclude_account_ids if value is not None]
        if normalized:
            conditions.append("NOT (id = ANY(%s))")
            params.append(normalized)
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                id,
                login,
                display_name,
                is_root,
                telegram_chat_id,
                telegram_username
            FROM auth.superadmin_accounts
            WHERE {' AND '.join(conditions)}
            ORDER BY is_root DESC, display_name ASC, id ASC
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def list_pending_telegram_notifications(*, limit: int = 100):
    safe_limit = max(1, min(int(limit or 100), 500))
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM (
                SELECT
                    e.id,
                    e.camp_id,
                    c.name AS camp_name,
                    e.recipient_scope,
                    e.recipient_admin_id,
                    a.display_name AS recipient_name,
                    a.telegram_chat_id,
                    a.telegram_username,
                    e.event_type,
                    e.title,
                    e.body,
                    e.action_url,
                    e.action_payload,
                    e.severity,
                    e.status,
                    e.metadata,
                    e.attempts,
                    e.next_attempt_at,
                    e.created_at
                FROM crm.notification_events e
                JOIN auth.camp_admin_accounts a ON a.id = e.recipient_admin_id
                LEFT JOIN catalog.camps c ON c.id = e.camp_id
                WHERE e.recipient_scope = 'crm'
                  AND e.channel = 'telegram'
                  AND e.status = 'new'
                  AND e.next_attempt_at <= NOW()
                  AND a.archived_at IS NULL
                  AND a.is_active = TRUE
                  AND a.notifications_enabled = TRUE
                  AND a.telegram_chat_id IS NOT NULL

                UNION ALL

                SELECT
                    e.id,
                    e.camp_id,
                    c.name AS camp_name,
                    e.recipient_scope,
                    e.recipient_admin_id,
                    COALESCE(sa.display_name, sa.login) AS recipient_name,
                    sa.telegram_chat_id,
                    sa.telegram_username,
                    e.event_type,
                    e.title,
                    e.body,
                    e.action_url,
                    e.action_payload,
                    e.severity,
                    e.status,
                    e.metadata,
                    e.attempts,
                    e.next_attempt_at,
                    e.created_at
                FROM crm.notification_events e
                JOIN auth.superadmin_accounts sa ON sa.id = e.recipient_admin_id
                LEFT JOIN catalog.camps c ON c.id = e.camp_id
                WHERE e.recipient_scope = 'superadmin'
                  AND e.channel = 'telegram'
                  AND e.status = 'new'
                  AND e.next_attempt_at <= NOW()
                  AND sa.archived_at IS NULL
                  AND sa.is_active = TRUE
                  AND sa.telegram_chat_id IS NOT NULL

                UNION ALL

                SELECT
                    e.id,
                    e.camp_id,
                    c.name AS camp_name,
                    e.recipient_scope,
                    e.owner_account_id AS recipient_admin_id,
                    o.display_name AS recipient_name,
                    o.telegram_chat_id,
                    NULL::text AS telegram_username,
                    e.event_type,
                    e.title,
                    e.body,
                    e.action_url,
                    e.action_payload,
                    e.severity,
                    e.status,
                    e.metadata,
                    e.attempts,
                    e.next_attempt_at,
                    e.created_at
                FROM crm.notification_events e
                JOIN auth.owner_accounts o ON o.id = e.owner_account_id
                LEFT JOIN catalog.camps c ON c.id = e.camp_id
                WHERE e.recipient_scope = 'owner'
                  AND e.channel = 'telegram'
                  AND e.status = 'new'
                  AND e.next_attempt_at <= NOW()
                  AND o.account_status = 'active'
                  AND o.is_active = TRUE
                  AND o.telegram_chat_id IS NOT NULL
            ) AS q
            ORDER BY q.created_at ASC, q.id ASC
            LIMIT %s
            """,
            (safe_limit,),
        )
        return [dict(row) for row in cur.fetchall()]


def mark_telegram_notification_sent(event_id: int) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE crm.notification_events
            SET status = 'closed',
                read_at = COALESCE(read_at, NOW()),
                closed_at = COALESCE(closed_at, NOW()),
                sent_at = COALESCE(sent_at, NOW()),
                attempts = attempts + 1,
                last_error = NULL
            WHERE id = %s
            """,
            (int(event_id),),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed


def mark_notification_failed(event_id: int, error_message: str) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE crm.notification_events
            SET attempts = attempts + 1,
                last_error = left(%s, 1000),
                next_attempt_at = NOW() + (
                    LEAST(3600, GREATEST(30, power(2, LEAST(attempts, 7))::integer * 30))
                    * INTERVAL '1 second'
                ),
                status = CASE WHEN attempts >= 9 THEN 'failed' ELSE 'new' END
            WHERE id = %s
            """,
            ((error_message or "delivery failed")[:1000], int(event_id)),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed


def list_pending_email_notifications(*, limit: int = 100) -> list[dict]:
    safe_limit = max(1, min(int(limit or 100), 500))
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                submission_id,
                owner_account_id,
                owner_change_request_id,
                recipient_address,
                event_type,
                title,
                body,
                action_url,
                action_payload,
                severity,
                attempts,
                metadata,
                created_at
            FROM crm.notification_events
            WHERE channel = 'email'
              AND status = 'new'
              AND next_attempt_at <= NOW()
              AND NULLIF(trim(recipient_address), '') IS NOT NULL
            ORDER BY created_at, id
            LIMIT %s
            """,
            (safe_limit,),
        )
        return [dict(row) for row in cur.fetchall()]


def claim_pending_email_notifications(
    *,
    limit: int = 100,
    lease_seconds: int = 120,
) -> list[dict]:
    """Atomically lease due email events across concurrent/restarted workers."""

    safe_limit = max(1, min(int(limit or 100), 500))
    safe_lease = max(30, min(int(lease_seconds or 120), 900))
    batch_token = secrets.token_urlsafe(32)
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            WITH eligible AS (
                SELECT id
                FROM crm.notification_events
                WHERE channel = 'email'
                  AND status = 'new'
                  AND next_attempt_at <= NOW()
                  AND NULLIF(trim(recipient_address), '') IS NOT NULL
                  AND (
                        claim_token IS NULL
                        OR lease_until IS NULL
                        OR lease_until < NOW()
                  )
                ORDER BY created_at, id
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            UPDATE crm.notification_events events
            SET claim_token = %s || ':' || events.id::text,
                claimed_at = NOW(),
                lease_until = NOW() + (%s * INTERVAL '1 second')
            FROM eligible
            WHERE events.id = eligible.id
            RETURNING events.*
            """,
            (safe_limit, batch_token, safe_lease),
        )
        rows = [dict(row) for row in cur.fetchall()]
        conn.commit()
    return sorted(rows, key=lambda row: (row.get("created_at"), int(row["id"])))


def mark_claimed_email_notification_sent(
    event_id: int,
    claim_token: str,
    *,
    delivered_message_id: str | None = None,
) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE crm.notification_events
            SET status = 'closed',
                read_at = COALESCE(read_at, NOW()),
                closed_at = COALESCE(closed_at, NOW()),
                sent_at = COALESCE(sent_at, NOW()),
                attempts = attempts + 1,
                last_error = NULL,
                delivered_message_id = COALESCE(%s, delivered_message_id),
                claim_token = NULL,
                claimed_at = NULL,
                lease_until = NULL
            WHERE id = %s
              AND channel = 'email'
              AND status = 'new'
              AND claim_token = %s
            """,
            (delivered_message_id, int(event_id), claim_token),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed


def mark_claimed_email_notification_failed(
    event_id: int,
    claim_token: str,
    error_message: str,
) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE crm.notification_events
            SET attempts = attempts + 1,
                last_error = left(%s, 1000),
                next_attempt_at = NOW() + (
                    LEAST(3600, GREATEST(30, power(2, LEAST(attempts, 7))::integer * 30))
                    * INTERVAL '1 second'
                ),
                status = CASE WHEN attempts >= 9 THEN 'failed' ELSE 'new' END,
                claim_token = NULL,
                claimed_at = NULL,
                lease_until = NULL
            WHERE id = %s
              AND channel = 'email'
              AND status = 'new'
              AND claim_token = %s
            """,
            ((error_message or "delivery failed")[:1000], int(event_id), claim_token),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed


def mark_email_notification_sent(event_id: int) -> bool:
    return mark_telegram_notification_sent(event_id)


def list_pending_webapp_bookings(*, limit: int = 200):
    safe_limit = max(1, min(int(limit or 200), 1000))
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                b.id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                b.check_in,
                b.check_out,
                b.status,
                b.source,
                b.guests_count,
                b.guest_name,
                b.guest_phone,
                b.guest_email,
                u.name AS user_name,
                u.phone AS user_phone,
                CASE WHEN u.email_verified THEN u.email ELSE '' END AS user_email,
                b.comment,
                b.created_at,
                b.updated_at
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            LEFT JOIN auth.users u ON u.id = b.user_id
            WHERE b.source = 'webapp'
              AND b.status = 'pending'
            ORDER BY b.created_at ASC, b.id ASC
            LIMIT %s
            """,
            (safe_limit,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_booking_escalation_attempt_map(booking_ids: list[int]) -> dict[int, int]:
    normalized_ids = [int(value) for value in booking_ids if value is not None]
    if not normalized_ids:
        return {}
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                ((COALESCE(metadata, '{}'::jsonb)->>'booking_id'))::BIGINT AS booking_id,
                MAX(COALESCE(((COALESCE(metadata, '{}'::jsonb)->>'attempt_no'))::INTEGER, 0)) AS max_attempt
            FROM crm.notification_events
            WHERE event_type = 'booking_escalation'
              AND COALESCE(metadata, '{}'::jsonb)->>'booking_id' IS NOT NULL
              AND ((COALESCE(metadata, '{}'::jsonb)->>'booking_id'))::BIGINT = ANY(%s)
            GROUP BY ((COALESCE(metadata, '{}'::jsonb)->>'booking_id'))::BIGINT
            """,
            (normalized_ids,),
        )
        return {
            int(row["booking_id"]): int(row["max_attempt"] or 0)
            for row in cur.fetchall()
            if row.get("booking_id") is not None
        }
