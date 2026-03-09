from datetime import date
from typing import Optional

from tourist03.booking_db_errors import translate_booking_integrity_error
from tourist03.db import _db_conn


def find_admin_account_by_email(email: str):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email, password_hash, display_name, is_active
            FROM auth.camp_admin_accounts
            WHERE email = %s
            """,
            (email,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def list_admin_camps(camp_ids: list[int]):
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, address, description, status
            FROM catalog.camps
            WHERE id = ANY(%s)
            ORDER BY name
            """,
            (camp_ids,),
        )
        return [dict(row) for row in cur.fetchall()]


def list_admin_bookings(camp_ids: list[int], camp_id: Optional[int], date_from: Optional[date], date_to: Optional[date]):
    conditions = []
    params: list = []
    if camp_id:
        conditions.append("b.camp_id = %s")
        params.append(camp_id)
    else:
        conditions.append("b.camp_id = ANY(%s)")
        params.append(camp_ids)
    if date_from:
        conditions.append("b.check_in >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("b.check_out <= %s")
        params.append(date_to)
    where_clause = " AND ".join(conditions)
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
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
                b.payment_status,
                b.payment_required,
                b.user_id,
                u.name AS user_name,
                u.phone AS user_phone,
                CASE WHEN u.email_verified THEN u.email ELSE '' END AS user_email,
                b.guest_name,
                b.guest_phone,
                b.guest_email,
                b.comment
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            LEFT JOIN auth.users u ON u.id = b.user_id
            WHERE {where_clause}
            ORDER BY b.check_in DESC, b.id DESC
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def room_exists_for_camp(room_id: int, camp_id: int) -> bool:
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM catalog.rooms WHERE id=%s AND camp_id=%s", (room_id, camp_id))
        return bool(cur.fetchone())


def booking_has_conflict(
    room_id: int,
    camp_id: int,
    check_in,
    check_out,
    blocked_statuses: tuple[str, ...],
) -> bool:
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


def create_admin_booking(
    camp_id: int,
    room_id: Optional[int],
    check_in,
    check_out,
    guests_count: int,
    booking_status: str,
    comment: Optional[str],
    payment_status: str,
    payment_required: bool,
    guest_name: Optional[str],
    guest_phone: Optional[str],
    guest_email: Optional[str],
):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO crm.bookings (
                    user_id, camp_id, room_id,
                    check_in, check_out, guests_count,
                    status, source, comment,
                    payment_status, payment_required,
                    guest_name, guest_phone, guest_email
                )
                VALUES (NULL, %s, %s, %s, %s, %s, %s, 'crm', %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    camp_id,
                    room_id,
                    check_in,
                    check_out,
                    guests_count,
                    booking_status,
                    comment,
                    payment_status,
                    payment_required,
                    guest_name,
                    guest_phone,
                    guest_email,
                ),
            )
            booking_id = cur.fetchone()["id"]
            conn.commit()
        except Exception as exc:
            conn.rollback()
            translate_booking_integrity_error(
                exc,
                conflict_detail="Этот вариант уже забронирован на выбранные даты",
            )
            raise
        return booking_id


def get_booking_by_id(booking_id: int):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, camp_id, user_id, status, payment_status, payment_required FROM crm.bookings WHERE id=%s",
            (booking_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_admin_booking(
    booking_id: int,
    *,
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    payment_required: Optional[bool] = None,
):
    updates = []
    params = []
    if status is not None:
        updates.append("status=%s")
        params.append(status)
    if payment_status is not None:
        updates.append("payment_status=%s")
        params.append(payment_status)
    if payment_required is not None:
        updates.append("payment_required=%s")
        params.append(bool(payment_required))
    if not updates:
        return False

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        try:
            updates.append("updated_at=NOW()")
            params.append(booking_id)
            cur.execute(f"UPDATE crm.bookings SET {', '.join(updates)} WHERE id=%s", tuple(params))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            translate_booking_integrity_error(
                exc,
                conflict_detail="Этот вариант уже забронирован на выбранные даты",
            )
            raise
    return True


def list_admin_calendar(camp_ids: list[int], camp_id: Optional[int], date_from: Optional[date], date_to: Optional[date]):
    conditions = []
    params: list = []
    if camp_id:
        conditions.append("camp_id = %s")
        params.append(camp_id)
    else:
        conditions.append("camp_id = ANY(%s)")
        params.append(camp_ids)
    if date_from:
        conditions.append("check_in >= %s")
        params.append(date_from)
    if date_to:
        conditions.append("check_out <= %s")
        params.append(date_to)
    where_clause = " AND ".join(conditions)
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT camp_id, room_id, check_in, check_out, status
            FROM crm.bookings
            WHERE {where_clause}
            ORDER BY check_in
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]


def list_admin_bookings_calendar(camp_ids: list[int], camp_id: Optional[int], date_from: Optional[date], date_to: Optional[date]):
    conditions = []
    params: list = []
    if camp_id:
        conditions.append("b.camp_id = %s")
        params.append(camp_id)
    else:
        conditions.append("b.camp_id = ANY(%s)")
        params.append(camp_ids)
    if date_from:
        conditions.append("b.check_out > %s")
        params.append(date_from)
    if date_to:
        conditions.append("b.check_in < %s")
        params.append(date_to)
    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
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
                b.payment_status,
                b.payment_required,
                b.user_id,
                u.name AS user_name,
                u.phone AS user_phone,
                CASE WHEN u.email_verified THEN u.email ELSE '' END AS user_email,
                b.guest_name,
                b.guest_phone,
                b.guest_email,
                b.comment
            FROM crm.bookings b
            LEFT JOIN catalog.camps c ON c.id = b.camp_id
            LEFT JOIN catalog.rooms r ON r.id = b.room_id
            LEFT JOIN auth.users u ON u.id = b.user_id
            WHERE {where_clause}
            ORDER BY b.check_in ASC, b.id ASC
            """,
            tuple(params),
        )
        return [dict(row) for row in cur.fetchall()]
