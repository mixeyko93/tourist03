import uuid
from datetime import date
from typing import Dict, List

from fastapi import Depends, HTTPException

from tourist03.domain import bookings as booking_domain
from tourist03.repositories import bookings as bookings_repo
from tourist03.schemas import BookingCreateRequest, BookingEditRequest, BookingOrderCreateRequest, OrderEditRequest
from tourist03.serializers import bookings as booking_serializers
from tourist03.security import get_current_user, log_user_event


def auth_my_bookings(mode: str = "active", user: dict = Depends(get_current_user)):
    mode = (mode or "active").strip().lower()
    today = date.today()
    rows = bookings_repo.list_user_bookings(user["id"])

    active = []
    history = []
    for row in rows:
        row["status"] = booking_domain.status_for_history(row.get("status"), row.get("check_out"), today=today)
        if booking_domain.is_history_booking(row.get("status"), row.get("check_out"), today=today):
            history.append(booking_serializers.serialize_booking(row))
        else:
            active.append(booking_serializers.serialize_booking(row))

    return {"ok": True, "items": (history if mode == "history" else active)}


def auth_my_orders(mode: str = "active", user: dict = Depends(get_current_user)):
    mode = (mode or "active").strip().lower()
    today = date.today()
    rows = bookings_repo.list_user_order_rows(user["id"])
    for row in rows:
        row["status"] = booking_domain.status_for_history(row.get("status"), row.get("check_out"), today=today)

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
        order = booking_serializers.serialize_order(key, group_rows)
        all_history = all(
            booking_domain.is_history_booking(row.get("status"), row.get("check_out"), today=today)
            for row in group_rows
        )
        (history if all_history else active).append(order)

    return {"ok": True, "items": (history if mode == "history" else active)}


def auth_order_one(order_id: str, user: dict = Depends(get_current_user)):
    order_id = (order_id or "").strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="invalid id")

    rows = bookings_repo.get_user_order_rows(order_id, user["id"])
    if not rows:
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True, "item": booking_serializers.serialize_order(order_id, rows)}


def auth_order_create(payload: BookingOrderCreateRequest, user: dict = Depends(get_current_user)):
    booking_domain.ensure_valid_date_range(payload.check_in, payload.check_out)

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
        guests_count = booking_domain.resolve_guests_count(
            item.guests_count,
            adults=item.adults,
            kids=item.kids,
        )
        items.append({"room_id": room_id, "guests_count": guests_count})

    room_ids = [item["room_id"] for item in items]
    rows = bookings_repo.get_rooms_by_ids(room_ids)
    rooms_by_id = {int(row["id"]): int(row.get("camp_id") or 0) for row in rows}
    if len(rooms_by_id) != len(room_ids):
        raise HTTPException(status_code=400, detail="Неверный номер апартамента")
    for room_id in room_ids:
        if int(rooms_by_id.get(int(room_id)) or 0) != int(payload.camp_id):
            raise HTTPException(status_code=400, detail="Неверный номер/база")

    order_id = uuid.uuid4().hex
    comment = (payload.comment or "").strip() or None
    booking_ids = bookings_repo.create_order(
        user["id"],
        payload.camp_id,
        order_id,
        payload.check_in,
        payload.check_out,
        items,
        comment,
        booking_domain.CONFLICT_IGNORED_STATUSES,
    )
    if booking_ids is None:
        raise HTTPException(status_code=409, detail="Один из вариантов уже забронирован на выбранные даты")

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

    rows = bookings_repo.get_order_status_rows(order_id, user["id"])
    if not rows:
        raise HTTPException(status_code=404, detail="not found")

    for row in rows:
        booking_domain.ensure_cancellable(row.get("status"))

    bookings_repo.cancel_order(order_id, user["id"])
    log_user_event(user["id"], "order_cancel", {"order_id": order_id})
    return {"ok": True}


def auth_order_pay(order_id: str, user: dict = Depends(get_current_user)):
    order_id = (order_id or "").strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="invalid id")

    rows = bookings_repo.get_order_payment_rows(order_id, user["id"])
    if not rows:
        raise HTTPException(status_code=404, detail="not found")

    for row in rows:
        booking_domain.ensure_payable(row.get("status"), row.get("payment_required"), row.get("payment_status"))

    log_user_event(user["id"], "order_pay_click", {"order_id": order_id})
    return {"ok": True, "payment_url": None}


def auth_order_edit(order_id: str, payload: OrderEditRequest, user: dict = Depends(get_current_user)):
    order_id = (order_id or "").strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="invalid id")

    if payload.check_in is None and payload.check_out is None and payload.comment is None:
        return {"ok": True}

    rows = bookings_repo.get_order_edit_rows(order_id, user["id"])
    if not rows:
        raise HTTPException(status_code=404, detail="not found")

    for row in rows:
        booking_domain.ensure_editable(row.get("status"), row.get("payment_status"))

    current_check_in = rows[0].get("check_in")
    current_check_out = rows[0].get("check_out")
    new_check_in = payload.check_in if payload.check_in is not None else current_check_in
    new_check_out = payload.check_out if payload.check_out is not None else current_check_out
    if payload.check_in is not None or payload.check_out is not None:
        booking_domain.ensure_valid_date_range(new_check_in, new_check_out)

        booking_ids = [int(row["id"]) for row in rows]
        for row in rows:
            if bookings_repo.order_has_conflict(
                int(row.get("room_id") or 0),
                int(row.get("camp_id") or 0),
                booking_ids,
                new_check_in,
                new_check_out,
                booking_domain.CONFLICT_IGNORED_STATUSES,
            ):
                raise HTTPException(status_code=409, detail="Один из апартаментов уже забронирован на выбранные даты")

    changed = bookings_repo.update_order(
        order_id,
        user["id"],
        check_in=payload.check_in,
        check_out=payload.check_out,
        comment=(payload.comment or "").strip() if payload.comment is not None else None,
    )
    if not changed:
        return {"ok": True}

    log_user_event(user["id"], "order_edit", {"order_id": order_id})
    return {"ok": True}


def auth_booking_create(payload: BookingCreateRequest, user: dict = Depends(get_current_user)):
    guests_count = booking_domain.resolve_guests_count(
        payload.guests_count,
        adults=payload.adults,
        kids=payload.kids,
    )
    booking_domain.ensure_valid_date_range(payload.check_in, payload.check_out)

    room = bookings_repo.get_room(payload.room_id)
    if not room or int(room.get("camp_id") or 0) != int(payload.camp_id):
        raise HTTPException(status_code=400, detail="Неверный номер/база")

    if bookings_repo.booking_has_conflict(
        payload.room_id,
        payload.camp_id,
        payload.check_in,
        payload.check_out,
        booking_domain.CONFLICT_IGNORED_STATUSES,
    ):
        raise HTTPException(status_code=409, detail="Этот вариант уже забронирован на выбранные даты")

    booking_id = bookings_repo.create_booking(
        user["id"],
        payload.camp_id,
        payload.room_id,
        payload.check_in,
        payload.check_out,
        guests_count,
        payload.comment,
    )
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
    row = bookings_repo.get_user_booking_row(booking_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True, "item": booking_serializers.serialize_booking(row)}


def auth_booking_edit(booking_id: int, payload: BookingEditRequest, user: dict = Depends(get_current_user)):
    booking = bookings_repo.get_booking_edit_state(booking_id, user["id"])
    if not booking:
        raise HTTPException(status_code=404, detail="not found")

    booking_domain.ensure_editable(booking.get("status"), booking.get("payment_status"))

    changed = bookings_repo.update_booking(
        booking_id,
        user["id"],
        check_in=payload.check_in,
        check_out=payload.check_out,
        guests_count=payload.guests_count,
        comment=(payload.comment or "").strip() if payload.comment is not None else None,
    )
    if not changed:
        return {"ok": True}

    log_user_event(user["id"], "booking_edit", {"booking_id": booking_id})
    return {"ok": True}


def auth_booking_cancel(booking_id: int, user: dict = Depends(get_current_user)):
    row = bookings_repo.get_booking_status_row(booking_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="not found")

    booking_domain.ensure_cancellable(row.get("status"))

    bookings_repo.cancel_booking(booking_id, user["id"])
    log_user_event(user["id"], "booking_cancel", {"booking_id": booking_id})
    return {"ok": True}


def auth_booking_pay(booking_id: int, user: dict = Depends(get_current_user)):
    row = bookings_repo.get_booking_payment_row(booking_id, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail="not found")

    booking_domain.ensure_payable(row.get("status"), row.get("payment_required"), row.get("payment_status"))

    log_user_event(user["id"], "booking_pay_click", {"booking_id": booking_id})
    return {"ok": True, "payment_url": None}
