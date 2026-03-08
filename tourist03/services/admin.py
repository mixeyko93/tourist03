from datetime import date
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from tourist03.db import _db_conn
from tourist03.schemas import AdminCreateBookingRequest, AdminLoginRequest, BookingAdminUpdateRequest
from tourist03.security import _get_admin_camp_ids, get_current_admin, log_user_event, verify_password


def admin_login(req: AdminLoginRequest, request: Request):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email, password_hash, display_name, is_active
            FROM auth.camp_admin_accounts
            WHERE email = %s
            """,
            (req.email.lower().strip(),),
        )
        row = cur.fetchone()
    if not row or not row["is_active"] or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный логин или пароль")
    request.session["admin_id"] = row["id"]
    return {"status": "ok"}


def admin_logout(request: Request):
    request.session.clear()
    return {"status": "ok"}


def admin_me(admin: dict = Depends(get_current_admin)):
    return admin


def api_admin_my_camps(admin: dict = Depends(get_current_admin)):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        return []
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
        rows = cur.fetchall()
    response = []
    for row in rows:
        status_value = (row.get("status") or "").strip().lower()
        response.append(
            {
                "id": row.get("id"),
                "name": row.get("name") or "",
                "region": row.get("address") or "Не указано",
                "description": row.get("description") or "",
                "is_active": status_value in ("", "active", "активна", "активный"),
            }
        )
    return response


def api_admin_bookings(
    camp_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        return []
    conditions = []
    params: list = []
    if camp_id:
        if camp_id not in camp_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
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
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def api_admin_create_booking(payload: AdminCreateBookingRequest, admin: dict = Depends(get_current_admin)):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    if payload.camp_id not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    if payload.check_out <= payload.check_in:
        raise HTTPException(status_code=400, detail="Дата выезда должна быть позже даты заезда")
    if payload.guests_count <= 0:
        raise HTTPException(status_code=400, detail="Некорректное количество гостей")

    allowed_status = {"pending", "confirmed", "rejected", "completed", "cancelled_by_user", "cancelled"}
    allowed_payment = {"unpaid", "paid", "cash"}
    booking_status = (payload.status or "pending").strip().lower()
    payment_status = (payload.payment_status or "unpaid").strip().lower()
    if booking_status not in allowed_status:
        raise HTTPException(status_code=400, detail="Некорректный статус брони")
    if payment_status not in allowed_payment:
        raise HTTPException(status_code=400, detail="Некорректный статус оплаты")

    payment_required = bool(payload.payment_required)
    if payment_status in ("paid", "cash"):
        payment_required = False

    room_id = payload.room_id
    if room_id is not None:
        with _db_conn("catalog") as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM catalog.rooms WHERE id=%s AND camp_id=%s", (room_id, payload.camp_id))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Некорректный номер (апартамент) для выбранной базы")

    guest_name = (payload.guest_name or "").strip() or None
    guest_phone = (payload.guest_phone or "").strip() or None
    guest_email = (str(payload.guest_email).strip().lower() if payload.guest_email is not None else None) if payload.guest_email is not None else None
    comment = (payload.comment or "").strip() or None

    with _db_conn("crm") as conn:
        cur = conn.cursor()
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
                payload.camp_id,
                room_id,
                payload.check_in,
                payload.check_out,
                payload.guests_count,
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

    return {"ok": True, "id": booking_id}


def api_admin_update_booking(
    booking_id: int,
    payload: BookingAdminUpdateRequest,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")

    allowed_payment = {"unpaid", "paid", "cash"}
    payment_status = payload.payment_status
    if payment_status is not None:
        payment_status = (payment_status or "").strip().lower()
        if payment_status not in allowed_payment:
            raise HTTPException(status_code=400, detail="Некорректный статус оплаты")

    new_status = payload.status.strip() if payload.status is not None else None
    payment_required = payload.payment_required if payload.payment_required is not None else None

    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, camp_id, user_id, status, payment_status, payment_required FROM crm.bookings WHERE id=%s",
            (booking_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        booking = dict(row)
        if booking["camp_id"] not in camp_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")

        updates = []
        params = []
        if new_status is not None and new_status != booking.get("status"):
            updates.append("status=%s")
            params.append(new_status)
        if payment_status is not None and payment_status != booking.get("payment_status"):
            updates.append("payment_status=%s")
            params.append(payment_status)
        if payment_required is not None and payment_required != booking.get("payment_required"):
            updates.append("payment_required=%s")
            params.append(bool(payment_required))

        if payment_status in ("paid", "cash") and booking.get("payment_required"):
            updates.append("payment_required=FALSE")

        if not updates:
            return {"ok": True}

        updates.append("updated_at=NOW()")
        params.append(booking_id)
        cur.execute(f"UPDATE crm.bookings SET {', '.join(updates)} WHERE id=%s", tuple(params))
        conn.commit()

    if booking.get("user_id"):
        log_user_event(
            int(booking["user_id"]),
            "booking_admin_update",
            {
                "booking_id": booking_id,
                "status": new_status,
                "payment_status": payment_status,
                "payment_required": payment_required,
                "admin_id": admin.get("id"),
            },
        )
    return {"ok": True}


def api_admin_calendar(
    camp_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        return []
    conditions = []
    params: list = []
    if camp_id:
        if camp_id not in camp_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
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
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def api_admin_bookings_calendar(
    camp_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        return []

    conditions = []
    params: list = []
    if camp_id:
        if camp_id not in camp_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
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
        rows = cur.fetchall()
    return [dict(row) for row in rows]
