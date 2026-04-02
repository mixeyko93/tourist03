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
                e.event_type,
                e.title,
                e.body,
                e.action_url,
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


def list_pending_telegram_notifications(*, limit: int = 100):
    safe_limit = max(1, min(int(limit or 100), 500))
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                e.id,
                e.camp_id,
                c.name AS camp_name,
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
                e.created_at
            FROM crm.notification_events e
            JOIN auth.camp_admin_accounts a ON a.id = e.recipient_admin_id
            LEFT JOIN catalog.camps c ON c.id = e.camp_id
            WHERE e.recipient_scope = 'crm'
              AND e.channel = 'telegram'
              AND e.status = 'new'
              AND a.archived_at IS NULL
              AND a.is_active = TRUE
              AND a.notifications_enabled = TRUE
              AND a.telegram_chat_id IS NOT NULL
            ORDER BY e.created_at ASC, e.id ASC
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
                closed_at = COALESCE(closed_at, NOW())
            WHERE id = %s
            """,
            (int(event_id),),
        )
        changed = cur.rowcount > 0
        conn.commit()
        return changed


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
