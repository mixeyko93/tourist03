import json
from typing import Optional

from tourist03.db import _db_conn


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


def list_camps():
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, address, lake_name, status
            FROM catalog.camps
            ORDER BY id
            """
        )
        return [dict(row) for row in cur.fetchall()]


def find_admin_account_by_email(email: str):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM auth.camp_admin_accounts WHERE email = %s", (email,))
        row = cur.fetchone()
        return dict(row) if row else None


def create_admin_account(email: str, password_hash: str, display_name: str, camp_ids: list[int]):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO auth.camp_admin_accounts (email, password_hash, display_name)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (email, password_hash, display_name),
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
            """,
            (account_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def admin_email_exists(email: str, account_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM auth.camp_admin_accounts
            WHERE lower(email) = lower(%s) AND id <> %s
            """,
            (email, account_id),
        )
        return bool(cur.fetchone())


def update_admin_account(
    account_id: int,
    *,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    password_hash: Optional[str] = None,
    is_active: Optional[bool] = None,
    camp_ids: Optional[list[int]] = None,
):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        updates = []
        params = []
        if email is not None:
            updates.append("email=%s")
            params.append(email)
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
            cur.execute("DELETE FROM crm.camp_admin_links WHERE admin_id=%s", (account_id,))
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
                    """,
                    (account_id, cid),
                )
        conn.commit()


def list_accounts():
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                a.id,
                a.email,
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
            GROUP BY a.id
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
                "email": row["email"],
                "display_name": row["display_name"],
                "is_active": row["is_active"],
                "created_at": row["created_at"],
                "camps": camps_data,
            }
        )
    return accounts
