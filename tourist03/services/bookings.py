import uuid
from datetime import date
from typing import Any, Dict, List

from fastapi import Depends, HTTPException

from tourist03.bootstrap import ensure_crm_bookings_schema
from tourist03.db import _db_conn
from tourist03.schemas import BookingCreateRequest, BookingEditRequest, BookingOrderCreateRequest, OrderEditRequest
from tourist03.security import get_current_user, log_user_event


def _booking_public(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "camp_id": row.get("camp_id"),
        "camp_name": row.get("camp_name") or "",
        "room_id": row.get("room_id"),
        "room_name": row.get("room_name") or "",
        "check_in": row.get("check_in"),
        "check_out": row.get("check_out"),
        "guests_count": row.get("guests_count"),
        "status": row.get("status") or "",
        "payment_required": bool(row.get("payment_required")),
        "payment_status": row.get("payment_status") or "unpaid",
        "comment": row.get("comment") or "",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _order_status_rollup(statuses: List[str]) -> str:
    sts = [(status or "").strip().lower() for status in (statuses or [])]
    sts = [status for status in sts if status]
    if not sts:
        return "pending"

    terminal = {"cancelled_by_user", "rejected", "completed", "cancelled"}
    if all(status in terminal for status in sts):
        if any(status == "completed" for status in sts):
            return "completed"
        if any(status == "rejected" for status in sts):
            return "rejected"
        if any(status == "cancelled_by_user" for status in sts):
            return "cancelled_by_user"
        return "cancelled"

    if any(status in ("pending", "new", "") for status in sts):
        return "pending"
    if any(status == "awaiting_payment" for status in sts):
        return "awaiting_payment"
    if any(status == "confirmed" for status in sts):
        return "confirmed"
    return sts[0] or "pending"


def _order_payment_status_rollup(statuses: List[str]) -> str:
    sts = [(status or "").strip().lower() for status in (statuses or [])]
    sts = [status for status in sts if status]
    if not sts:
        return "unpaid"
    if any(status == "unpaid" for status in sts):
        return "unpaid"
    if any(status == "cash" for status in sts):
        return "cash"
    if all(status == "paid" for status in sts):
        return "paid"
    return sts[0] or "unpaid"


def _order_public(order_id: str, rows: List[dict]) -> Dict[str, Any]:
    first = rows[0] if rows else {}
    guests_total = 0
    items = []
    for row in rows:
        try:
            guests_total += int(row.get("guests_count") or 0)
        except Exception:
            pass
        items.append(
            {
                "booking_id": row.get("id"),
                "room_id": row.get("room_id"),
                "room_name": row.get("room_name") or "",
                "check_in": row.get("check_in"),
                "check_out": row.get("check_out"),
                "guests_count": row.get("guests_count"),
                "status": row.get("status") or "",
                "payment_required": bool(row.get("payment_required")),
                "payment_status": row.get("payment_status") or "unpaid",
                "comment": row.get("comment") or "",
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            }
        )

    created_at = None
    updated_at = None
    for row in rows:
        created = row.get("created_at")
        updated = row.get("updated_at")
        if created and (created_at is None or created < created_at):
            created_at = created
        if updated and (updated_at is None or updated > updated_at):
            updated_at = updated

    return {
        "order_id": order_id,
        "camp_id": first.get("camp_id"),
        "camp_name": first.get("camp_name") or "",
        "check_in": first.get("check_in"),
        "check_out": first.get("check_out"),
        "guests_count": guests_total,
        "status": _order_status_rollup([row.get("status") for row in rows]),
        "payment_required": any(bool(row.get("payment_required")) for row in rows),
        "payment_status": _order_payment_status_rollup([row.get("payment_status") for row in rows]),
        "comment": next((comment for comment in (str(row.get("comment") or "").strip() for row in rows) if comment), ""),
        "created_at": created_at,
        "updated_at": updated_at,
        "items": items,
    }


def auth_my_bookings(mode: str = "active", user: dict = Depends(get_current_user)):
    mode = (mode or "active").strip().lower()
    today = date.today()
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
            (user["id"],),
        )
        rows = [dict(row) for row in cur.fetchall()]

    active_statuses = {"pending", "confirmed", "awaiting_payment"}
    terminal_statuses = {"cancelled_by_user", "rejected", "completed", "cancelled"}

    active = []
    history = []
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        is_terminal = status in terminal_statuses
        is_past = row.get("check_out") is not None and row["check_out"] < today
        if is_past and not is_terminal:
            row["status"] = "completed"
        if is_terminal or is_past:
            history.append(_booking_public(row))
        else:
            if not status or status in active_statuses:
                active.append(_booking_public(row))
            else:
                active.append(_booking_public(row))

    return {"ok": True, "items": (history if mode == "history" else active)}


def auth_my_orders(mode: str = "active", user: dict = Depends(get_current_user)):
    mode = (mode or "active").strip().lower()
    today = date.today()
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
            (user["id"],),
        )
        rows = [dict(row) for row in cur.fetchall()]

    terminal_statuses = {"cancelled_by_user", "rejected", "completed", "cancelled"}
    for row in rows:
        status = (row.get("status") or "").strip().lower()
        is_terminal = status in terminal_statuses
        is_past = row.get("check_out") is not None and row["check_out"] < today
        if is_past and not is_terminal:
            row["status"] = "completed"

    groups: Dict[str, List[dict]] = {}
    order_keys: List[str] = []
    for row in rows:
        key = (row.get("group_id") or "").strip() or str(row.get("id"))
        if key not in groups:
            groups[key] = []
            order_keys.append(key)
        groups[key].append(row)

    active = []
    history = []
    for key in order_keys:
        group_rows = groups.get(key) or []
        if not group_rows:
            continue
        order = _order_public(key, group_rows)
        all_history = True
        for row in group_rows:
            status = (row.get("status") or "").strip().lower()
            is_terminal = status in terminal_statuses
            is_past = row.get("check_out") is not None and row["check_out"] < today
            if not (is_terminal or is_past):
                all_history = False
                break
        (history if all_history else active).append(order)

    return {"ok": True, "items": (history if mode == "history" else active)}


def auth_order_one(order_id: str, user: dict = Depends(get_current_user)):
    order_id = (order_id or "").strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="invalid id")

    with _db_conn("crm") as conn:
        ensure_crm_bookings_schema(conn)
        cur = conn.cursor()
        if order_id.isdigit():
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
                WHERE b.id = %s AND b.user_id = %s
                ORDER BY b.id DESC
                """,
                (int(order_id), user["id"]),
            )
        else:
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
                WHERE b.group_id = %s AND b.user_id = %s
                ORDER BY b.id DESC
                """,
                (order_id, user["id"]),
            )
        rows = [dict(row) for row in cur.fetchall()]
        if not rows:
            raise HTTPException(status_code=404, detail="not found")
    return {"ok": True, "item": _order_public(order_id, rows)}


def auth_order_create(payload: BookingOrderCreateRequest, user: dict = Depends(get_current_user)):
    if payload.check_out <= payload.check_in:
        raise HTTPException(status_code=400, detail="Дата выезда должна быть позже даты заезда")

    raw_items = payload.items or []
    if not raw_items:
        raise HTTPException(status_code=400, detail="Добавьте апартаменты")

    items = []
    seen_room_ids = set()
    for item in raw_items:
        room_id = int(item.room_id)
        if room_id in seen_room_ids:
            raise HTTPException(status_code=400, detail="Дублирование апартаментов в заявке")
        seen_room_ids.add(room_id)
        guests_count = item.guests_count
        if guests_count is None:
            guests_count = int(item.adults or 0) + int(item.kids or 0)
        try:
            guests_count = int(guests_count)
        except Exception:
            guests_count = 0
        if guests_count <= 0:
            raise HTTPException(status_code=400, detail="Укажите количество гостей")
        items.append({"room_id": room_id, "guests_count": guests_count})

    room_ids = [item["room_id"] for item in items]
    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, camp_id FROM catalog.rooms WHERE id = ANY(%s)", (room_ids,))
        rows = cur.fetchall()
    rooms_by_id = {int(row["id"]): int(row.get("camp_id") or 0) for row in rows}
    if len(rooms_by_id) != len(room_ids):
        raise HTTPException(status_code=400, detail="Неверный номер апартамента")
    for room_id in room_ids:
        if int(rooms_by_id.get(int(room_id)) or 0) != int(payload.camp_id):
            raise HTTPException(status_code=400, detail="Неверный номер/база")

    order_id = uuid.uuid4().hex
    comment = (payload.comment or "").strip() or None

    blocked_statuses = ("rejected", "cancelled_by_user", "cancelled")
    booking_ids: List[int] = []
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
                (item["room_id"], payload.camp_id, blocked_statuses, payload.check_out, payload.check_in),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Один из вариантов уже забронирован на выбранные даты")

        for item in items:
            cur.execute(
                """
                INSERT INTO crm.bookings(user_id, camp_id, room_id, group_id, check_in, check_out, guests_count, status, source, comment)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'pending','webapp',%s)
                RETURNING id
                """,
                (
                    user["id"],
                    payload.camp_id,
                    item["room_id"],
                    order_id,
                    payload.check_in,
                    payload.check_out,
                    item["guests_count"],
                    comment,
                ),
            )
            row = cur.fetchone()
            booking_ids.append(int(row["id"]))
        conn.commit()

    log_user_event(
        user["id"],
        "order_create",
        {
            "order_id": order_id,
            "camp_id": payload.camp_id,
            "check_in": str(payload.check_in),
            "check_out": str(payload.check_out),
            "booking_ids": booking_ids,
        },
    )
    return {"ok": True, "order_id": order_id, "booking_ids": booking_ids}


def auth_order_cancel(order_id: str, user: dict = Depends(get_current_user)):
    order_id = (order_id or "").strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="invalid id")

    with _db_conn("crm") as conn:
        ensure_crm_bookings_schema(conn)
        cur = conn.cursor()
        if order_id.isdigit():
            cur.execute("SELECT id, status FROM crm.bookings WHERE id=%s AND user_id=%s", (int(order_id), user["id"]))
            rows = [dict(row) for row in cur.fetchall()]
        else:
            cur.execute("SELECT id, status FROM crm.bookings WHERE group_id=%s AND user_id=%s", (order_id, user["id"]))
            rows = [dict(row) for row in cur.fetchall()]
        if not rows:
            raise HTTPException(status_code=404, detail="not found")

        for row in rows:
            status = (row.get("status") or "").strip().lower()
            if status in ("completed", "rejected", "cancelled_by_user", "cancelled"):
                raise HTTPException(status_code=400, detail="Бронь уже завершена")

        if order_id.isdigit():
            cur.execute(
                "UPDATE crm.bookings SET status='cancelled_by_user', updated_at=NOW() WHERE id=%s AND user_id=%s",
                (int(order_id), user["id"]),
            )
        else:
            cur.execute(
                "UPDATE crm.bookings SET status='cancelled_by_user', updated_at=NOW() WHERE group_id=%s AND user_id=%s",
                (order_id, user["id"]),
            )
        conn.commit()

    log_user_event(user["id"], "order_cancel", {"order_id": order_id})
    return {"ok": True}


def auth_order_pay(order_id: str, user: dict = Depends(get_current_user)):
    order_id = (order_id or "").strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="invalid id")

    with _db_conn("crm") as conn:
        ensure_crm_bookings_schema(conn)
        cur = conn.cursor()
        if order_id.isdigit():
            cur.execute(
                """
                SELECT id, status, payment_required, payment_status
                FROM crm.bookings
                WHERE id=%s AND user_id=%s
                """,
                (int(order_id), user["id"]),
            )
        else:
            cur.execute(
                """
                SELECT id, status, payment_required, payment_status
                FROM crm.bookings
                WHERE group_id=%s AND user_id=%s
                """,
                (order_id, user["id"]),
            )
        rows = [dict(row) for row in cur.fetchall()]
        if not rows:
            raise HTTPException(status_code=404, detail="not found")

        for row in rows:
            status = (row.get("status") or "").strip().lower()
            pay_required = bool(row.get("payment_required"))
            pay_status = (row.get("payment_status") or "").strip().lower()
            if status != "confirmed":
                raise HTTPException(status_code=400, detail="Оплата доступна после подтверждения брони")
            if not pay_required:
                raise HTTPException(status_code=400, detail="Оплата пока не запрошена администратором")
            if pay_status != "unpaid":
                raise HTTPException(status_code=400, detail="Бронь уже оплачена или отмечена как наличная")

    log_user_event(user["id"], "order_pay_click", {"order_id": order_id})
    return {"ok": True, "payment_url": None}


def auth_order_edit(order_id: str, payload: OrderEditRequest, user: dict = Depends(get_current_user)):
    order_id = (order_id or "").strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="invalid id")

    if payload.check_in is None and payload.check_out is None and payload.comment is None:
        return {"ok": True}

    blocked_statuses = ("rejected", "cancelled_by_user", "cancelled")
    terminal_statuses = ("completed", "rejected", "cancelled_by_user", "cancelled")

    with _db_conn("crm") as conn:
        ensure_crm_bookings_schema(conn)
        cur = conn.cursor()

        if order_id.isdigit():
            cur.execute(
                """
                SELECT id, room_id, camp_id, check_in, check_out, status, payment_status
                FROM crm.bookings
                WHERE id=%s AND user_id=%s
                """,
                (int(order_id), user["id"]),
            )
        else:
            cur.execute(
                """
                SELECT id, room_id, camp_id, check_in, check_out, status, payment_status
                FROM crm.bookings
                WHERE group_id=%s AND user_id=%s
                ORDER BY id
                """,
                (order_id, user["id"]),
            )
        rows = [dict(row) for row in cur.fetchall()]
        if not rows:
            raise HTTPException(status_code=404, detail="not found")

        for row in rows:
            status = (row.get("status") or "").strip().lower()
            if status in terminal_statuses:
                raise HTTPException(status_code=400, detail="Нельзя редактировать завершённую бронь")
            if (row.get("payment_status") or "").strip().lower() == "paid":
                raise HTTPException(status_code=400, detail="Нельзя редактировать оплаченную бронь")

        current_check_in = rows[0].get("check_in")
        current_check_out = rows[0].get("check_out")
        new_check_in = payload.check_in if payload.check_in is not None else current_check_in
        new_check_out = payload.check_out if payload.check_out is not None else current_check_out
        if payload.check_in is not None or payload.check_out is not None:
            if not new_check_in or not new_check_out or new_check_out <= new_check_in:
                raise HTTPException(status_code=400, detail="Дата выезда должна быть позже даты заезда")

            booking_ids = [int(row["id"]) for row in rows]
            for row in rows:
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
                    (
                        int(row.get("room_id") or 0),
                        int(row.get("camp_id") or 0),
                        booking_ids,
                        blocked_statuses,
                        new_check_out,
                        new_check_in,
                    ),
                )
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="Один из апартаментов уже забронирован на выбранные даты")

        updates = []
        params: List[Any] = []
        if payload.check_in is not None:
            updates.append("check_in=%s")
            params.append(payload.check_in)
        if payload.check_out is not None:
            updates.append("check_out=%s")
            params.append(payload.check_out)
        if payload.comment is not None:
            updates.append("comment=%s")
            params.append((payload.comment or "").strip())
        if not updates:
            return {"ok": True}

        updates.append("updated_at=NOW()")
        if order_id.isdigit():
            params.extend([int(order_id), user["id"]])
            cur.execute(f"UPDATE crm.bookings SET {', '.join(updates)} WHERE id=%s AND user_id=%s", tuple(params))
        else:
            params.extend([order_id, user["id"]])
            cur.execute(f"UPDATE crm.bookings SET {', '.join(updates)} WHERE group_id=%s AND user_id=%s", tuple(params))
        conn.commit()

    log_user_event(user["id"], "order_edit", {"order_id": order_id})
    return {"ok": True}


def auth_booking_create(payload: BookingCreateRequest, user: dict = Depends(get_current_user)):
    guests_count = payload.guests_count
    if guests_count is None:
        guests_count = int(payload.adults or 0) + int(payload.kids or 0)
    try:
        guests_count = int(guests_count)
    except Exception:
        guests_count = 0
    if guests_count <= 0:
        raise HTTPException(status_code=400, detail="Укажите количество гостей")
    if payload.check_out <= payload.check_in:
        raise HTTPException(status_code=400, detail="Дата выезда должна быть позже даты заезда")

    with _db_conn("catalog") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, camp_id, name FROM catalog.rooms WHERE id=%s", (payload.room_id,))
        room = cur.fetchone()
    if not room or int(room.get("camp_id") or 0) != int(payload.camp_id):
        raise HTTPException(status_code=400, detail="Неверный номер/база")

    blocked_statuses = ("rejected", "cancelled_by_user", "cancelled")
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
            (payload.room_id, payload.camp_id, blocked_statuses, payload.check_out, payload.check_in),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Этот вариант уже забронирован на выбранные даты")

        cur.execute(
            """
            INSERT INTO crm.bookings(user_id, camp_id, room_id, check_in, check_out, guests_count, status, source, comment)
            VALUES (%s,%s,%s,%s,%s,%s,'pending','webapp',%s)
            RETURNING id
            """,
            (user["id"], payload.camp_id, payload.room_id, payload.check_in, payload.check_out, guests_count, payload.comment),
        )
        row = cur.fetchone()
        conn.commit()

    booking_id = int(row["id"])
    log_user_event(
        user["id"],
        "booking_create",
        {
            "booking_id": booking_id,
            "camp_id": payload.camp_id,
            "room_id": payload.room_id,
            "check_in": str(payload.check_in),
            "check_out": str(payload.check_out),
            "guests_count": guests_count,
        },
    )
    return {"ok": True, "booking_id": booking_id}


def auth_booking_one(booking_id: int, user: dict = Depends(get_current_user)):
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
            (booking_id, user["id"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        return {"ok": True, "item": _booking_public(dict(row))}


def auth_booking_edit(booking_id: int, payload: BookingEditRequest, user: dict = Depends(get_current_user)):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, status, payment_status FROM crm.bookings WHERE id=%s AND user_id=%s", (booking_id, user["id"]))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        booking = dict(row)
        status = (booking.get("status") or "").strip().lower()
        if status in ("completed", "rejected", "cancelled_by_user", "cancelled"):
            raise HTTPException(status_code=400, detail="Нельзя редактировать завершённую бронь")
        if (booking.get("payment_status") or "").strip().lower() == "paid":
            raise HTTPException(status_code=400, detail="Нельзя редактировать оплаченную бронь")

        updates = []
        params = []
        if payload.check_in is not None:
            updates.append("check_in=%s")
            params.append(payload.check_in)
        if payload.check_out is not None:
            updates.append("check_out=%s")
            params.append(payload.check_out)
        if payload.guests_count is not None:
            updates.append("guests_count=%s")
            params.append(int(payload.guests_count))
        if payload.comment is not None:
            updates.append("comment=%s")
            params.append((payload.comment or "").strip())
        if not updates:
            return {"ok": True}
        updates.append("updated_at=NOW()")
        params.extend([booking_id, user["id"]])
        cur.execute(f"UPDATE crm.bookings SET {', '.join(updates)} WHERE id=%s AND user_id=%s", tuple(params))
        conn.commit()
    log_user_event(user["id"], "booking_edit", {"booking_id": booking_id})
    return {"ok": True}


def auth_booking_cancel(booking_id: int, user: dict = Depends(get_current_user)):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, status FROM crm.bookings WHERE id=%s AND user_id=%s", (booking_id, user["id"]))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        status = (row.get("status") or "").strip().lower()
        if status in ("completed", "rejected", "cancelled_by_user", "cancelled"):
            raise HTTPException(status_code=400, detail="Бронь уже завершена")
        cur.execute(
            "UPDATE crm.bookings SET status='cancelled_by_user', updated_at=NOW() WHERE id=%s AND user_id=%s",
            (booking_id, user["id"]),
        )
        conn.commit()
    log_user_event(user["id"], "booking_cancel", {"booking_id": booking_id})
    return {"ok": True}


def auth_booking_pay(booking_id: int, user: dict = Depends(get_current_user)):
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, status, payment_required, payment_status
            FROM crm.bookings
            WHERE id=%s AND user_id=%s
            """,
            (booking_id, user["id"]),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        status = (row.get("status") or "").strip().lower()
        pay_required = bool(row.get("payment_required"))
        pay_status = (row.get("payment_status") or "").strip().lower()
        if status != "confirmed":
            raise HTTPException(status_code=400, detail="Оплата доступна после подтверждения брони")
        if not pay_required:
            raise HTTPException(status_code=400, detail="Оплата пока не запрошена администратором")
        if pay_status != "unpaid":
            raise HTTPException(status_code=400, detail="Бронь уже оплачена или отмечена как наличная")
    log_user_event(user["id"], "booking_pay_click", {"booking_id": booking_id})
    return {"ok": True, "payment_url": None}
