import json
from typing import Optional

from tourist03.db import _db_conn
from tourist03.repositories import catalog as catalog_repo

_MISSING = object()


def _decode_json_value(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def get_user_history_user(user_id: int):
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, phone, email, role, phone_verified, email_verified, created_at
            FROM auth.users
            WHERE id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_user_events(user_id: int):
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, event_type, payload, created_at
            FROM auth.user_events
            WHERE user_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 500
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_user_bookings(user_id: int):
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
                b.guests_count,
                b.status,
                b.source,
                b.comment,
                b.created_at,
                b.updated_at
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC, b.id DESC
            LIMIT 500
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def list_camps(*, archived_only: bool = False, search: Optional[str] = None, status: Optional[str] = None):
    conditions = []
    params: list = []

    if archived_only:
        conditions.append("(COALESCE(c.status, 'active') = 'archived' OR c.archived_at IS NOT NULL)")
    else:
        conditions.append("COALESCE(c.status, 'active') <> 'archived'")

    normalized_status = (status or "").strip().lower()
    if normalized_status:
        conditions.append("COALESCE(c.status, 'active') = %s")
        params.append(normalized_status)

    normalized_search = (search or "").strip()
    if normalized_search:
        pattern = f"%{normalized_search}%"
        conditions.append(
            """
            (
                COALESCE(c.name, '') ILIKE %s OR
                COALESCE(c.lake_name, '') ILIKE %s OR
                COALESCE(c.address, '') ILIKE %s OR
                COALESCE(c.owner, '') ILIKE %s OR
                COALESCE(c.manager, '') ILIKE %s
            )
            """
        )
        params.extend([pattern, pattern, pattern, pattern, pattern])

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                c.id,
                c.name,
                c.address,
                c.lake_name,
                c.status,
                c.owner,
                c.manager,
                c.min_price,
                COALESCE(room_stats.rooms_count, c.rooms_count, 0) AS rooms_count,
                COALESCE(room_stats.beds_count, c.beds_count, 0) AS beds_count,
                c.lat,
                c.lng,
                c.archived_at,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'id', a.id,
                            'display_name', a.display_name,
                            'login', a.email,
                            'is_active', a.is_active
                        )
                        ORDER BY a.display_name, a.id
                    ) FILTER (WHERE a.id IS NOT NULL AND a.archived_at IS NULL),
                    '[]'::json
                ) AS linked_admins
            FROM catalog.camps c
            LEFT JOIN (
                SELECT
                    camp_id,
                    COUNT(*) AS rooms_count,
                    SUM(COALESCE(beds_single, 0) + COALESCE(beds_double, 0) * 2) AS beds_count
                FROM catalog.rooms
                GROUP BY camp_id
            ) room_stats ON room_stats.camp_id = c.id
            LEFT JOIN crm.camp_admin_links l ON l.camp_id = c.id
            LEFT JOIN auth.camp_admin_accounts a ON a.id = l.admin_id
            {where_sql}
            GROUP BY c.id, room_stats.rooms_count, room_stats.beds_count
            ORDER BY c.archived_at DESC NULLS LAST, c.id DESC
            """,
            tuple(params),
        )
        rows = [dict(row) for row in cur.fetchall()]

    items = []
    for row in rows:
        linked_admins = row.get("linked_admins") or []
        if isinstance(linked_admins, str):
            try:
                linked_admins = json.loads(linked_admins)
            except Exception:
                linked_admins = []
        row["linked_admins"] = linked_admins if isinstance(linked_admins, list) else []
        items.append(row)
    return items


def get_camp_editor_context(camp_id: int):
    camp = catalog_repo.get_camp(camp_id)
    if not camp:
        return None
    photos = catalog_repo.list_camp_photos(camp_id)
    media = catalog_repo.list_camp_media(camp_id)
    room_context = catalog_repo.get_camp_room_listing_context(camp_id)

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                a.id,
                a.email AS login,
                a.display_name,
                a.is_active
            FROM crm.camp_admin_links l
            JOIN auth.camp_admin_accounts a ON a.id = l.admin_id
            WHERE l.camp_id = %s
              AND a.archived_at IS NULL
            ORDER BY a.display_name, a.id
            """,
            (camp_id,),
        )
        linked_accounts = [dict(row) for row in cur.fetchall()]

    rooms = room_context.get("rooms") if room_context else []
    for room in rooms:
        room["media"] = catalog_repo.list_room_media(camp_id, int(room["id"]), room.get("photos") or [])
    return {
        "camp": camp,
        "photos": photos,
        "media": media,
        "rooms": rooms,
        "linked_accounts": linked_accounts,
    }


def list_users(search: Optional[str] = None):
    conditions = ["u.archived_at IS NULL"]
    params: list = []

    normalized_search = (search or "").strip()
    if normalized_search:
        pattern = f"%{normalized_search}%"
        conditions.append(
            """
            (
                COALESCE(u.name, '') ILIKE %s OR
                COALESCE(u.phone, '') ILIKE %s OR
                COALESCE(u.email, '') ILIKE %s
            )
            """
        )
        params.extend([pattern, pattern, pattern])

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                u.id,
                u.name,
                u.phone,
                CASE
                    WHEN COALESCE(u.email_verified, FALSE) THEN COALESCE(u.email, '')
                    ELSE ''
                END AS email,
                COALESCE(u.phone_verified, FALSE) AS phone_verified,
                COALESCE(u.email_verified, FALSE) AS email_verified,
                u.created_at,
                COUNT(b.id) AS bookings_count,
                MAX(b.created_at) AS last_booking_at
            FROM auth.users u
            LEFT JOIN crm.bookings b ON b.user_id = u.id
            WHERE {' AND '.join(conditions)}
            GROUP BY u.id
            ORDER BY u.created_at DESC, u.id DESC
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def list_recent_events(*, search: Optional[str] = None, camp_id: Optional[int] = None, limit: int = 20):
    conditions = ["e.channel = 'in_app'"]
    params: list = []

    if camp_id is not None:
        conditions.append("e.camp_id = %s")
        params.append(int(camp_id))

    normalized_search = (search or "").strip()
    if normalized_search:
        pattern = f"%{normalized_search}%"
        conditions.append(
            """
            (
                COALESCE(c.name, '') ILIKE %s OR
                COALESCE(e.title, '') ILIKE %s OR
                COALESCE(e.body, '') ILIKE %s OR
                COALESCE(e.event_type, '') ILIKE %s
            )
            """
        )
        params.extend([pattern, pattern, pattern, pattern])

    safe_limit = max(1, min(int(limit or 20), 100))
    params.append(safe_limit)

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                e.id,
                e.camp_id,
                c.name AS camp_name,
                e.recipient_scope,
                e.event_type,
                e.title,
                e.body,
                e.action_url,
                e.action_payload,
                e.severity,
                e.status,
                e.metadata,
                e.created_at,
                e.read_at,
                e.closed_at
            FROM crm.notification_events e
            LEFT JOIN catalog.camps c ON c.id = e.camp_id
            WHERE {' AND '.join(conditions)}
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def find_admin_account_by_login(login: str):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id
            FROM auth.camp_admin_accounts
            WHERE archived_at IS NULL
              AND (
                lower(email) = lower(%s)
                OR (
                    position('@' in email) > 0
                    AND split_part(lower(email), '@', 1) = lower(%s)
                )
              )
            ORDER BY CASE WHEN lower(email) = lower(%s) THEN 0 ELSE 1 END, id
            LIMIT 1
            """,
            (login, login, login),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def create_admin_account(login: str, password_hash: str, display_name: str, camp_ids: list[int], default_role_key: Optional[str] = None):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO auth.camp_admin_accounts (email, password_hash, display_name)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (login, password_hash, display_name),
        )
        admin_id = cur.fetchone()["id"]
        linked: set[int] = set()
        for camp_id in camp_ids:
            try:
                cid = int(camp_id)
            except (TypeError, ValueError):
                continue
            if cid in linked:
                continue
            linked.add(cid)
            cur.execute(
                """
                INSERT INTO crm.camp_admin_links (admin_id, camp_id)
                VALUES (%s, %s)
                ON CONFLICT (admin_id, camp_id) DO NOTHING
                """,
                (admin_id, cid),
            )
        conn.commit()
        return admin_id


def get_admin_account(account_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email, display_name, is_active
            FROM auth.camp_admin_accounts
            WHERE id=%s
              AND archived_at IS NULL
            """,
            (account_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def admin_login_exists(login: str, account_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM auth.camp_admin_accounts
            WHERE (
                lower(email) = lower(%s)
                OR (
                    position('@' in email) > 0
                    AND split_part(lower(email), '@', 1) = lower(%s)
                )
            )
              AND id <> %s
              AND archived_at IS NULL
            """,
            (login, login, account_id),
        )
        return bool(cur.fetchone())


def update_admin_account(
    account_id: int,
    *,
    login: Optional[str] = None,
    display_name: Optional[str] = None,
    password_hash: Optional[str] = None,
    is_active: Optional[bool] = None,
    camp_ids: Optional[list[int]] = None,
    default_role_key: Optional[str] = None,
):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        updates = []
        params = []
        if login is not None:
            updates.append("email=%s")
            params.append(login)
        if display_name is not None:
            updates.append("display_name=%s")
            params.append(display_name)
        if password_hash is not None:
            updates.append("password_hash=%s")
            params.append(password_hash)
        if is_active is not None:
            updates.append("is_active=%s")
            params.append(bool(is_active))
        if updates:
            cur.execute(f"UPDATE auth.camp_admin_accounts SET {', '.join(updates)} WHERE id=%s", tuple([*params, account_id]))

        if camp_ids is not None:
            cur.execute("SELECT camp_id FROM crm.camp_admin_links WHERE admin_id=%s", (account_id,))
            existing_camps = {int(row["camp_id"]) for row in cur.fetchall()}
            target_camps: set[int] = set()
            for camp_id in camp_ids:
                try:
                    target_camps.add(int(camp_id))
                except (TypeError, ValueError):
                    continue
            to_remove = existing_camps - target_camps
            if to_remove:
                cur.execute(
                    "DELETE FROM crm.camp_admin_links WHERE admin_id=%s AND camp_id = ANY(%s)",
                    (account_id, list(to_remove)),
                )
            for cid in target_camps:
                cur.execute(
                    """
                    INSERT INTO crm.camp_admin_links (admin_id, camp_id)
                    VALUES (%s, %s)
                    ON CONFLICT (admin_id, camp_id) DO NOTHING
                    """,
                    (account_id, cid),
                )
        conn.commit()


def delete_admin_account(account_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM crm.camp_admin_links WHERE admin_id=%s", (account_id,))
        cur.execute("DELETE FROM auth.camp_admin_accounts WHERE id=%s", (account_id,))
        conn.commit()


def list_accounts():
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                a.id,
                a.email AS login,
                a.display_name,
                a.is_active,
                a.created_at,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'camp_id', l.camp_id,
                            'camp_name', c.name
                        )
                        ORDER BY c.name
                    ) FILTER (WHERE l.camp_id IS NOT NULL),
                    '[]'::json
                ) AS camps
            FROM auth.camp_admin_accounts AS a
            LEFT JOIN crm.camp_admin_links AS l ON l.admin_id = a.id
            LEFT JOIN catalog.camps AS c ON c.id = l.camp_id
            WHERE a.archived_at IS NULL
            GROUP BY a.id, a.email, a.display_name, a.is_active, a.created_at
            ORDER BY a.created_at DESC, a.id DESC
            """
        )
        rows = cur.fetchall()
    accounts = []
    for row in rows:
        raw_camps = row.get("camps")
        camps_data = []
        if isinstance(raw_camps, str):
            try:
                camps_data = json.loads(raw_camps)
            except Exception:
                camps_data = []
        elif isinstance(raw_camps, list):
            camps_data = raw_camps
        accounts.append(
            {
                "id": row["id"],
                "login": row["login"],
                "display_name": row["display_name"],
                "is_active": row["is_active"],
                "default_role_key": "administrator",
                "created_at": row["created_at"],
                "camps": camps_data,
            }
        )
    return accounts


def count_active_root_superadmins() -> int:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM auth.superadmin_accounts
            WHERE archived_at IS NULL
              AND is_active = TRUE
              AND is_root = TRUE
            """
        )
        row = cur.fetchone()
        return int(row["count"] if row else 0)


def get_superadmin_account_by_id(account_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                login,
                password_hash,
                display_name,
                phone,
                is_active,
                is_root,
                telegram_user_id,
                telegram_chat_id,
                telegram_username,
                telegram_link_code,
                telegram_link_code_expires_at,
                created_by_id,
                archived_at,
                created_at,
                updated_at
            FROM auth.superadmin_accounts
            WHERE id = %s
            """,
            (account_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_superadmin_account_by_login(login: str):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                login,
                password_hash,
                display_name,
                phone,
                is_active,
                is_root,
                telegram_user_id,
                telegram_chat_id,
                telegram_username,
                telegram_link_code,
                telegram_link_code_expires_at,
                created_by_id,
                archived_at,
                created_at,
                updated_at
            FROM auth.superadmin_accounts
            WHERE lower(login) = lower(%s)
            ORDER BY archived_at NULLS FIRST, id DESC
            LIMIT 1
            """,
            (login,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def upsert_bootstrap_superadmin(*, login: str, password_hash: str, display_name: str):
    existing = get_superadmin_account_by_login(login)
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        if existing:
            cur.execute(
                """
                UPDATE auth.superadmin_accounts
                SET
                    password_hash = %s,
                    display_name = %s,
                    is_active = TRUE,
                    is_root = TRUE,
                    archived_at = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (password_hash, display_name, existing["id"]),
            )
            account_id = existing["id"]
        else:
            cur.execute(
                """
                INSERT INTO auth.superadmin_accounts (
                    login,
                    password_hash,
                    display_name,
                    is_active,
                    is_root
                )
                VALUES (%s, %s, %s, TRUE, TRUE)
                RETURNING id
                """,
                (login, password_hash, display_name),
            )
            account_id = cur.fetchone()["id"]
        conn.commit()
    return get_superadmin_account_by_id(account_id)


def list_superadmin_accounts(*, include_archived: bool = False):
    where_sql = "" if include_archived else "WHERE a.archived_at IS NULL"
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                a.id,
                a.login,
                a.display_name,
                a.phone,
                a.is_active,
                a.is_root,
                a.telegram_chat_id,
                a.telegram_username,
                a.created_by_id,
                a.archived_at,
                a.created_at,
                a.updated_at,
                creator.display_name AS created_by_display
            FROM auth.superadmin_accounts AS a
            LEFT JOIN auth.superadmin_accounts AS creator ON creator.id = a.created_by_id
            {where_sql}
            ORDER BY a.is_root DESC, a.created_at DESC, a.id DESC
            """
        )
        return [dict(row) for row in cur.fetchall()]


def create_superadmin_account(
    *,
    login: str,
    password_hash: str,
    display_name: str,
    phone: Optional[str],
    is_active: bool,
    is_root: bool,
    created_by_id: Optional[int],
):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO auth.superadmin_accounts (
                login,
                password_hash,
                display_name,
                phone,
                is_active,
                is_root,
                created_by_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (login, password_hash, display_name, phone, bool(is_active), bool(is_root), created_by_id),
        )
        account_id = cur.fetchone()["id"]
        conn.commit()
    return account_id


def superadmin_login_exists(login: str, account_id: Optional[int] = None) -> bool:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        if account_id is None:
            cur.execute(
                """
                SELECT 1
                FROM auth.superadmin_accounts
                WHERE lower(login) = lower(%s)
                  AND archived_at IS NULL
                """,
                (login,),
            )
        else:
            cur.execute(
                """
                SELECT 1
                FROM auth.superadmin_accounts
                WHERE lower(login) = lower(%s)
                  AND id <> %s
                  AND archived_at IS NULL
                """,
                (login, account_id),
            )
        return bool(cur.fetchone())


def update_superadmin_account(
    account_id: int,
    *,
    login=_MISSING,
    display_name=_MISSING,
    phone=_MISSING,
    password_hash=_MISSING,
    is_active: Optional[bool] = None,
    is_root: Optional[bool] = None,
    archived_at=_MISSING,
):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        updates = []
        params = []
        if login is not _MISSING:
            updates.append("login = %s")
            params.append(login)
        if display_name is not _MISSING:
            updates.append("display_name = %s")
            params.append(display_name)
        if phone is not _MISSING:
            updates.append("phone = %s")
            params.append(phone)
        if password_hash is not _MISSING:
            updates.append("password_hash = %s")
            params.append(password_hash)
        if is_active is not None:
            updates.append("is_active = %s")
            params.append(bool(is_active))
        if is_root is not None:
            updates.append("is_root = %s")
            params.append(bool(is_root))
        if archived_at is not _MISSING:
            updates.append("archived_at = %s")
            params.append(archived_at)
        updates.append("updated_at = NOW()")
        cur.execute(
            f"""
            UPDATE auth.superadmin_accounts
            SET {', '.join(updates)}
            WHERE id = %s
            """,
            tuple([*params, account_id]),
        )
        conn.commit()


def list_system_audit(
    *,
    search: Optional[str] = None,
    actor_type: Optional[str] = None,
    target_type: Optional[str] = None,
    camp_id: Optional[int] = None,
    limit: int = 100,
):
    conditions = ["1 = 1"]
    params: list = []

    normalized_search = (search or "").strip()
    if normalized_search:
        pattern = f"%{normalized_search}%"
        conditions.append(
            """
            (
                COALESCE(a.actor_display, '') ILIKE %s OR
                COALESCE(a.action_label, '') ILIKE %s OR
                COALESCE(a.comment, '') ILIKE %s OR
                COALESCE(a.target_type, '') ILIKE %s OR
                COALESCE(c.name, '') ILIKE %s
            )
            """
        )
        params.extend([pattern, pattern, pattern, pattern, pattern])

    if actor_type:
        conditions.append("a.actor_type = %s")
        params.append(actor_type)

    if target_type:
        conditions.append("a.target_type = %s")
        params.append(target_type)

    if camp_id is not None:
        conditions.append("a.camp_id = %s")
        params.append(int(camp_id))

    safe_limit = max(1, min(int(limit or 100), 500))
    params.append(safe_limit)

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                a.id,
                a.actor_type,
                a.actor_id,
                a.actor_display,
                a.camp_id,
                c.name AS camp_name,
                a.target_type,
                a.target_id,
                a.action_type,
                a.action_label,
                a.changed_field,
                a.old_value,
                a.new_value,
                a.comment,
                a.is_sensitive,
                a.was_auto_applied,
                a.metadata,
                a.created_at
            FROM crm.audit_log AS a
            LEFT JOIN catalog.camps AS c ON c.id = a.camp_id
            WHERE {' AND '.join(conditions)}
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT %s
            """,
            tuple(params),
        )
        rows = [dict(row) for row in cur.fetchall()]

    items = []
    for row in rows:
        row["old_value"] = _decode_json_value(row.get("old_value"))
        row["new_value"] = _decode_json_value(row.get("new_value"))
        row["metadata"] = _decode_json_value(row.get("metadata"))
        items.append(row)
    return items
