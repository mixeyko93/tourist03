from typing import Optional

from tourist03.bootstrap import ensure_crm_bookings_schema
from tourist03.db import _db_conn


def _order_filter(order_id: str, *, id_expr: str, group_expr: str):
    order_id = (order_id or "").strip()
    if order_id.isdigit():
        return id_expr, int(order_id)
    return group_expr, order_id


def list_user_bookings(user_id: int):
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
                b.payment_required,
                b.payment_status,
                b.comment,
                b.created_at,
                b.updated_at
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC, b.id DESC
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def list_user_order_rows(user_id: int):
    with _db_conn("crm") as conn:
        ensure_crm_bookings_schema(conn)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                b.id,
                b.group_id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                b.check_in,
                b.check_out,
                b.guests_count,
                b.status,
                b.payment_required,
                b.payment_status,
                b.comment,
                b.created_at,
                b.updated_at
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            WHERE b.user_id = %s
            ORDER BY b.created_at DESC, b.id DESC
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_user_order_rows(order_id: str, user_id: int):
    condition, value = _order_filter(order_id, id_expr="b.id = %s", group_expr="b.group_id = %s")
    with _db_conn("crm") as conn:
        ensure_crm_bookings_schema(conn)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                b.id,
                b.group_id,
                b.camp_id,
                c.name AS camp_name,
                b.room_id,
                r.name AS room_name,
                b.check_in,
                b.check_out,
                b.guests_count,
                b.status,
                b.payment_required,
                b.payment_status,
                b.comment,
                b.created_at,
                b.updated_at
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            WHERE {condition} AND b.user_id = %s
            ORDER BY b.id DESC
            """,
            (value, user_id),
        )
        return [dict(row) for row in cur.fetchall()]


def get_rooms_by_ids(room_ids: list[int]):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, camp_id FROM catalog.rooms WHERE id = ANY(%s)", (room_ids,))
        return [dict(row) for row in cur.fetchall()]


def create_order(
    user_id: int,
    camp_id: int,
    order_id: str,
    check_in,
    check_out,
    items: list[dict],
    comment: Optional[str],
    blocked_statuses: tuple[str, ...],
):
    booking_ids = []
    with _db_conn("crm") as conn:
        ensure_crm_bookings_schema(conn)
        cur = conn.cursor()
        for item in items:
            cur.execute(
                """
                SELECT 1
                FROM crm.bookings
                WHERE room_id=%s
                  AND camp_id=%s
                  AND (status IS NULL OR lower(status) NOT IN %s)
                  AND check_in < %s
                  AND check_out > %s
                LIMIT 1
                """,
                (item["room_id"], camp_id, blocked_statuses, check_out, check_in),
            )
            if cur.fetchone():
                return None

        for item in items:
            cur.execute(
                """
                INSERT INTO crm.bookings(user_id, camp_id, room_id, group_id, check_in, check_out, guests_count, status, source, comment)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'pending','webapp',%s)
                RETURNING id
                """,
                (
                    user_id,
                    camp_id,
                    item["room_id"],
                    order_id,
                    check_in,
                    check_out,
                    item["guests_count"],
                    comment,
                ),
            )
            booking_ids.append(int(cur.fetchone()["id"]))
        conn.commit()
    return booking_ids


def get_order_status_rows(order_id: str, user_id: int):
    condition, value = _order_filter(order_id, id_expr="id=%s", group_expr="group_id=%s")
    with _db_conn("crm") as conn:
        ensure_crm_bookings_schema(conn)
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, status FROM crm.bookings WHERE {condition} AND user_id=%s",
            (value, user_id),
        )
        return [dict(row) for row in cur.fetchall()]


def cancel_order(order_id: str, user_id: int):
    condition, value = _order_filter(order_id, id_expr="id=%s", group_expr="group_id=%s")
    with _db_conn("crm") as conn:
        ensure_crm_bookings_schema(conn)
        cur = conn.cursor()
        cur.execute(
            f"UPDATE crm.bookings SET status='cancelled_by_user', updated_at=NOW() WHERE {condition} AND user_id=%s",
            (value, user_id),
        )
        conn.commit()


def get_order_payment_rows(order_id: str, user_id: int):
    condition, value = _order_filter(order_id, id_expr="id=%s", group_expr="group_id=%s")
    with _db_conn("crm") as conn:
        ensure_crm_bookings_schema(conn)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT id, status, payment_required, payment_status
            FROM crm.bookings
            WHERE {condition} AND user_id=%s
            """,
            (value, user_id),
        )
        return [dict(row) for row in cur.fetchall()]


def get_order_edit_rows(order_id: str, user_id: int):
    condition, value = _order_filter(order_id, id_expr="id=%s", group_expr="group_id=%s")
    with _db_conn("crm") as conn:
        ensure_crm_bookings_schema(conn)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT id, room_id, camp_id, check_in, check_out, status, payment_status
            FROM crm.bookings
            WHERE {condition} AND user_id=%s
            ORDER BY id
            """,
            (value, user_id),
        )
        return [dict(row) for row in cur.fetchall()]


def order_has_conflict(
    room_id: int,
    camp_id: int,
    excluded_ids: list[int],
    check_in,
    check_out,
    blocked_statuses: tuple[str, ...],
):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM crm.bookings
            WHERE room_id=%s
              AND camp_id=%s
              AND NOT (id = ANY(%s))
              AND (status IS NULL OR lower(status) NOT IN %s)
              AND check_in < %s
              AND check_out > %s
            LIMIT 1
            """,
            (room_id, camp_id, excluded_ids, blocked_statuses, check_out, check_in),
        )
        return bool(cur.fetchone())


def update_order(order_id: str, user_id: int, *, check_in=None, check_out=None, comment=None):
    updates = []
    params = []
    if check_in is not None:
        updates.append("check_in=%s")
        params.append(check_in)
    if check_out is not None:
        updates.append("check_out=%s")
        params.append(check_out)
    if comment is not None:
        updates.append("comment=%s")
        params.append(comment)
    if not updates:
        return False

    condition, value = _order_filter(order_id, id_expr="id=%s", group_expr="group_id=%s")
    with _db_conn("crm") as conn:
        ensure_crm_bookings_schema(conn)
        cur = conn.cursor()
        updates.append("updated_at=NOW()")
        cur.execute(
            f"UPDATE crm.bookings SET {', '.join(updates)} WHERE {condition} AND user_id=%s",
            tuple([*params, value, user_id]),
        )
        conn.commit()
    return True


def get_room(room_id: int):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, camp_id, name FROM catalog.rooms WHERE id=%s", (room_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def booking_has_conflict(
    room_id: int,
    camp_id: int,
    check_in,
    check_out,
    blocked_statuses: tuple[str, ...],
):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1
            FROM crm.bookings
            WHERE room_id=%s
              AND camp_id=%s
              AND (status IS NULL OR lower(status) NOT IN %s)
              AND check_in < %s
              AND check_out > %s
            LIMIT 1
            """,
            (room_id, camp_id, blocked_statuses, check_out, check_in),
        )
        return bool(cur.fetchone())


def create_booking(user_id: int, camp_id: int, room_id: int, check_in, check_out, guests_count: int, comment: Optional[str]):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO crm.bookings(user_id, camp_id, room_id, check_in, check_out, guests_count, status, source, comment)
            VALUES (%s,%s,%s,%s,%s,%s,'pending','webapp',%s)
            RETURNING id
            """,
            (user_id, camp_id, room_id, check_in, check_out, guests_count, comment),
        )
        booking_id = int(cur.fetchone()["id"])
        conn.commit()
    return booking_id


def get_user_booking_row(booking_id: int, user_id: int):
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
                b.payment_required,
                b.payment_status,
                b.comment,
                b.created_at,
                b.updated_at
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            WHERE b.id = %s AND b.user_id = %s
            """,
            (booking_id, user_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_booking_edit_state(booking_id: int, user_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, status, payment_status FROM crm.bookings WHERE id=%s AND user_id=%s",
            (booking_id, user_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_booking(booking_id: int, user_id: int, *, check_in=None, check_out=None, guests_count=None, comment=None):
    updates = []
    params = []
    if check_in is not None:
        updates.append("check_in=%s")
        params.append(check_in)
    if check_out is not None:
        updates.append("check_out=%s")
        params.append(check_out)
    if guests_count is not None:
        updates.append("guests_count=%s")
        params.append(int(guests_count))
    if comment is not None:
        updates.append("comment=%s")
        params.append(comment)
    if not updates:
        return False

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        updates.append("updated_at=NOW()")
        cur.execute(
            f"UPDATE crm.bookings SET {', '.join(updates)} WHERE id=%s AND user_id=%s",
            tuple([*params, booking_id, user_id]),
        )
        conn.commit()
    return True


def get_booking_status_row(booking_id: int, user_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, status FROM crm.bookings WHERE id=%s AND user_id=%s", (booking_id, user_id))
        row = cur.fetchone()
        return dict(row) if row else None


def cancel_booking(booking_id: int, user_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE crm.bookings SET status='cancelled_by_user', updated_at=NOW() WHERE id=%s AND user_id=%s",
            (booking_id, user_id),
        )
        conn.commit()


def get_booking_payment_row(booking_id: int, user_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, status, payment_required, payment_status
            FROM crm.bookings
            WHERE id=%s AND user_id=%s
            """,
            (booking_id, user_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None
