from datetime import date, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from tourist03.booking_db_errors import BookingConflictError, BookingValidationError
from tourist03.domain import bookings as booking_domain
from tourist03.repositories import admin as admin_repo
from tourist03.schemas import (
    AdminCampProfileUpdateRequest,
    AdminCreateBookingRequest,
    AdminLoginRequest,
    AdminRoomUpsertRequest,
    AdminServiceUpsertRequest,
    BookingAdminUpdateRequest,
)
from tourist03.serializers import bookings as booking_serializers
from tourist03.security import (
    _get_admin_camp_ids,
    _normalize_phone,
    get_current_admin,
    log_crm_audit_event,
    log_user_event,
    verify_password,
)


def _raise_booking_write_http_error(exc: Exception):
    if isinstance(exc, BookingConflictError):
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    if isinstance(exc, BookingValidationError):
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    raise exc


def _ensure_admin_camp_access(admin: dict, camp_id: int) -> list[int]:
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    if camp_id not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    return camp_ids


def admin_login(req: AdminLoginRequest, request: Request):
    row = admin_repo.find_admin_account_by_email(req.email.lower().strip())
    if not row or not row["is_active"] or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный логин или пароль")
    request.session["admin_id"] = row["id"]
    return {"status": "ok"}


def admin_logout(request: Request):
    request.session.pop("admin_id", None)
    return {"status": "ok"}


def admin_me(admin: dict = Depends(get_current_admin)):
    return admin


def _month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def _month_end(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1) - timedelta(days=1)
    return date(day.year, day.month + 1, 1) - timedelta(days=1)


def _resolve_calendar_range(date_from: Optional[date], date_to: Optional[date]) -> tuple[date, date]:
    today = date.today()
    start = date_from or _month_start(today)
    end = date_to or _month_end(start)
    if end < start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный диапазон дат")
    return start, end


def _calendar_status(status: Optional[str]) -> str:
    normalized = (status or "").strip().lower()
    if normalized in {
        "confirmed",
        "подтверждена",
        "подтверждено",
        "checked_in",
        "заселён",
        "заселен",
        "ожидает оплаты",
        "awaiting_payment",
    }:
        return "confirmed"
    if normalized in {"completed", "завершена", "завершено"}:
        return "completed"
    if normalized in {
        "cancelled",
        "cancelled_by_user",
        "cancelled_by_base",
        "отменена",
        "отменена гостем",
        "отменена базой",
        "rejected",
        "отклонена",
        "expired_pending",
        "просрочена без ответа",
        "no_show",
        "не заехал",
    }:
        return "cancelled"
    return "processing"


def _calendar_booking_label(row: dict) -> str:
    guest = (
        (row.get("guest_name") or "").strip()
        or (row.get("user_name") or "").strip()
        or (row.get("guest_phone") or "").strip()
        or (row.get("user_phone") or "").strip()
    )
    if guest:
        return guest
    return f"Бронь #{row.get('id')}"


def _days_between(check_in, check_out) -> int:
    if not check_in or not check_out:
        return 0
    return max((check_out - check_in).days, 1)


def _guest_status(visits_count: int) -> str:
    if visits_count >= 4:
        return "VIP"
    if visits_count >= 2:
        return "Постоянный"
    return "Новый"


def _normalize_service_status(status_value: Optional[str]) -> str:
    normalized = (status_value or "").strip().lower()
    allowed = {"draft", "active", "hidden", "sold_out", "paused", "archived"}
    if normalized in allowed:
        return normalized
    return "draft"


def api_admin_my_camps(admin: dict = Depends(get_current_admin)):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        return []

    rows = admin_repo.list_admin_camps(camp_ids)
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
    if camp_id and camp_id not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    return booking_serializers.serialize_admin_booking_list(
        admin_repo.list_admin_bookings(camp_ids, camp_id, date_from, date_to)
    )


def api_admin_create_booking(payload: AdminCreateBookingRequest, admin: dict = Depends(get_current_admin)):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    if payload.camp_id not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    booking_domain.ensure_valid_date_range(payload.check_in, payload.check_out)
    guests_count = booking_domain.ensure_positive_guest_count(
        payload.guests_count,
        detail="Некорректное количество гостей",
    )
    booking_status = booking_domain.normalize_admin_booking_status(payload.status)
    payment_status = booking_domain.normalize_admin_payment_status(payload.payment_status)
    payment_required = booking_domain.coerce_payment_required(
        payment_status,
        payload.payment_required,
        default=False,
    )

    room_id = payload.room_id
    if room_id is not None and not admin_repo.room_exists_for_camp(room_id, payload.camp_id):
        raise HTTPException(status_code=400, detail="Некорректный номер (апартамент) для выбранной базы")
    if room_id is not None and admin_repo.booking_has_conflict(
        room_id,
        payload.camp_id,
        payload.check_in,
        payload.check_out,
        booking_domain.CONFLICT_IGNORED_STATUSES,
    ):
        raise HTTPException(status_code=409, detail="Этот вариант уже забронирован на выбранные даты")

    guest_name = (payload.guest_name or "").strip() or None
    guest_phone = (payload.guest_phone or "").strip() or None
    guest_email = (str(payload.guest_email).strip().lower() if payload.guest_email is not None else None) if payload.guest_email is not None else None
    comment = (payload.comment or "").strip() or None

    try:
        booking_id = admin_repo.create_admin_booking(
            payload.camp_id,
            room_id,
            payload.check_in,
            payload.check_out,
            guests_count,
            booking_status,
            comment,
            payment_status,
            payment_required,
            guest_name,
            guest_phone,
            guest_email,
        )
    except Exception as exc:
        _raise_booking_write_http_error(exc)
    return {"ok": True, "id": booking_id}


def api_admin_update_booking(
    booking_id: int,
    payload: BookingAdminUpdateRequest,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")

    payment_status = booking_domain.normalize_admin_payment_status(payload.payment_status, allow_none=True)

    new_status = booking_domain.normalize_admin_booking_status(payload.status) if payload.status is not None else None
    booking = admin_repo.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="not found")
    if booking["camp_id"] not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")

    payment_required = booking_domain.coerce_payment_required(
        payment_status,
        payload.payment_required,
        default=None,
    )

    try:
        changed = admin_repo.update_admin_booking(
            booking_id,
            status=new_status if new_status != booking.get("status") else None,
            payment_status=payment_status if payment_status != booking.get("payment_status") else None,
            payment_required=payment_required if payment_required != booking.get("payment_required") else None,
        )
    except Exception as exc:
        _raise_booking_write_http_error(exc)
    if not changed:
        return {"ok": True}

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
    if camp_id and camp_id not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    return admin_repo.list_admin_calendar(camp_ids, camp_id, date_from, date_to)


def api_admin_bookings_calendar(
    camp_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        return []
    if camp_id and camp_id not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    return booking_serializers.serialize_admin_booking_list(
        admin_repo.list_admin_bookings_calendar(camp_ids, camp_id, date_from, date_to)
    )


def api_admin_guests(
    camp_id: Optional[int] = None,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        return []
    if camp_id and camp_id not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")

    rows = admin_repo.list_admin_guest_rows(camp_ids, camp_id)
    guests: dict[str, dict] = {}

    for row in rows:
        phone = _normalize_phone((row.get("guest_phone") or row.get("user_phone") or "").strip())
        email = (row.get("guest_email") or row.get("user_email") or "").strip().lower()
        name = (row.get("guest_name") or row.get("user_name") or "").strip()
        user_id = row.get("user_id")

        guest_key = ""
        if phone:
            guest_key = f"phone:{phone}"
        elif user_id:
            guest_key = f"user:{user_id}"
        elif email:
            guest_key = f"email:{email}"
        else:
            guest_key = f"booking:{row.get('id')}"

        guest = guests.get(guest_key)
        if guest is None:
            guest = {
                "id": guest_key,
                "name": name or "Гость без имени",
                "phone": phone,
                "email": email,
                "visits_count": 0,
                "total_estimate": 0,
                "last_visit": None,
                "status": "Новый",
                "bookings": [],
            }
            guests[guest_key] = guest

        if not guest.get("phone") and phone:
            guest["phone"] = phone
        if not guest.get("email") and email:
            guest["email"] = email
        if guest.get("name") in ("", "Гость без имени") and name:
            guest["name"] = name

        visit_total = int(row.get("room_price") or 0) * _days_between(row.get("check_in"), row.get("check_out"))
        guest["visits_count"] += 1
        guest["total_estimate"] += max(visit_total, 0)
        check_out = row.get("check_out")
        if check_out and (guest["last_visit"] is None or check_out > guest["last_visit"]):
            guest["last_visit"] = check_out

        guest["bookings"].append(
            {
                "id": row.get("id"),
                "camp_name": row.get("camp_name") or "",
                "room_name": row.get("room_name") or "Без апартамента",
                "check_in": row.get("check_in").isoformat() if row.get("check_in") else None,
                "check_out": row.get("check_out").isoformat() if row.get("check_out") else None,
                "guests_count": row.get("guests_count") or 0,
                "status": row.get("status") or "",
                "payment_status": row.get("payment_status") or "",
                "source": row.get("source") or "",
                "comment": row.get("comment") or "",
            }
        )

    items = []
    for guest in guests.values():
        guest["status"] = _guest_status(int(guest["visits_count"] or 0))
        last_visit = guest.get("last_visit")
        guest["last_visit"] = last_visit.isoformat() if last_visit else None
        guest["bookings"].sort(key=lambda item: ((item.get("check_in") or ""), int(item.get("id") or 0)), reverse=True)
        items.append(guest)

    items.sort(key=lambda item: ((item.get("last_visit") or ""), int(item.get("visits_count") or 0)), reverse=True)
    return items


def api_admin_calendar_feed(
    camp_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if not camp_ids:
        return {"date_from": None, "date_to": None, "rooms": []}
    if camp_id and camp_id not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")

    range_start, range_end = _resolve_calendar_range(date_from, date_to)
    rooms = admin_repo.list_admin_calendar_rooms(camp_ids, camp_id)
    bookings = admin_repo.list_admin_bookings_calendar(camp_ids, camp_id, range_start, range_end + timedelta(days=1))

    room_map: dict[str, dict] = {}
    for row in rooms:
        room_key = str(row["id"])
        room_map[room_key] = {
            "id": room_key,
            "room_id": row["id"],
            "camp_id": row["camp_id"],
            "camp_name": row.get("camp_name") or "",
            "title": row.get("name") or "Без названия",
            "category": (row.get("room_type") or "").strip() or "Апартамент",
            "bookings": [],
        }

    visible_range_end = range_end + timedelta(days=1)
    for booking in bookings:
        booking_start = booking.get("check_in")
        booking_end = booking.get("check_out")
        if booking_start is None or booking_end is None:
            continue

        display_start = max(booking_start, range_start)
        display_end = min(booking_end, visible_range_end)
        if display_end <= display_start:
            continue

        booking_room_id = booking.get("room_id")
        if booking_room_id is None:
            room_key = f"camp-{booking.get('camp_id')}-unassigned"
            room_entry = room_map.setdefault(
                room_key,
                {
                    "id": room_key,
                    "room_id": None,
                    "camp_id": booking.get("camp_id"),
                    "camp_name": booking.get("camp_name") or "",
                    "title": "Без назначенного апартамента",
                    "category": "Требует распределения",
                    "bookings": [],
                },
            )
        else:
            room_key = str(booking_room_id)
            room_entry = room_map.get(room_key)
            if room_entry is None:
                room_entry = {
                    "id": room_key,
                    "room_id": booking_room_id,
                    "camp_id": booking.get("camp_id"),
                    "camp_name": booking.get("camp_name") or "",
                    "title": booking.get("room_name") or "Апартамент",
                    "category": "Апартамент",
                    "bookings": [],
                }
                room_map[room_key] = room_entry

        room_entry["bookings"].append(
            {
                "id": booking.get("id"),
                "label": _calendar_booking_label(booking),
                "status": _calendar_status(booking.get("status")),
                "start_day": (display_start - range_start).days + 1,
                "span_days": max((display_end - display_start).days, 1),
                "check_in": booking_start.isoformat(),
                "check_out": booking_end.isoformat(),
                "source": booking.get("source") or "",
            }
        )

    return {
        "date_from": range_start.isoformat(),
        "date_to": range_end.isoformat(),
        "rooms": list(room_map.values()),
    }


def api_admin_camp_profile(camp_id: int, admin: dict = Depends(get_current_admin)):
    _ensure_admin_camp_access(admin, camp_id)
    payload = admin_repo.get_admin_camp_profile(camp_id)
    if not payload:
        raise HTTPException(status_code=404, detail="База не найдена")
    return payload


def api_admin_update_camp_profile(
    camp_id: int,
    payload: AdminCampProfileUpdateRequest,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_camp_access(admin, camp_id)
    before = admin_repo.get_admin_camp_profile(camp_id)
    if not before:
        raise HTTPException(status_code=404, detail="База не найдена")
    admin_repo.save_admin_camp_profile(camp_id, payload.model_dump())
    after = admin_repo.get_admin_camp_profile(camp_id)
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="camp_profile",
        target_id=camp_id,
        action_type="camp_profile_update",
        action_label="Обновил профиль базы",
        old_value=before,
        new_value=after,
        was_auto_applied=True,
    )
    return {"ok": True, "item": after}


def api_admin_camp_rooms(camp_id: int, admin: dict = Depends(get_current_admin)):
    _ensure_admin_camp_access(admin, camp_id)
    return admin_repo.list_admin_camp_rooms(camp_id)


def api_admin_camp_services(camp_id: int, admin: dict = Depends(get_current_admin)):
    _ensure_admin_camp_access(admin, camp_id)
    return admin_repo.list_admin_services(camp_id)


def api_admin_create_room(
    camp_id: int,
    payload: AdminRoomUpsertRequest,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_camp_access(admin, camp_id)
    room_id = admin_repo.create_admin_room(camp_id, payload.model_dump())
    room = admin_repo.get_admin_room(camp_id, room_id)
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="room",
        target_id=room_id,
        action_type="room_create",
        action_label="Создал апартамент",
        new_value=room,
        is_sensitive=True,
        was_auto_applied=True,
    )
    return {"ok": True, "id": room_id}


def api_admin_update_room(
    camp_id: int,
    room_id: int,
    payload: AdminRoomUpsertRequest,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_camp_access(admin, camp_id)
    before = admin_repo.get_admin_room(camp_id, room_id)
    if not before:
        raise HTTPException(status_code=404, detail="Апартамент не найден")
    changed = admin_repo.update_admin_room(camp_id, room_id, payload.model_dump())
    if not changed:
        raise HTTPException(status_code=404, detail="Апартамент не найден")
    after = admin_repo.get_admin_room(camp_id, room_id)
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="room",
        target_id=room_id,
        action_type="room_update",
        action_label="Обновил апартамент",
        old_value=before,
        new_value=after,
        is_sensitive=True,
        was_auto_applied=True,
    )
    return {"ok": True}


def api_admin_delete_room(camp_id: int, room_id: int, admin: dict = Depends(get_current_admin)):
    _ensure_admin_camp_access(admin, camp_id)
    before = admin_repo.get_admin_room(camp_id, room_id)
    if not before:
        raise HTTPException(status_code=404, detail="Апартамент не найден")
    if admin_repo.room_has_any_booking(camp_id, room_id):
        raise HTTPException(status_code=409, detail="Нельзя удалить апартамент, по нему уже есть бронирования")
    if not admin_repo.delete_admin_room(camp_id, room_id):
        raise HTTPException(status_code=404, detail="Апартамент не найден")
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="room",
        target_id=room_id,
        action_type="room_delete",
        action_label="Удалил апартамент",
        old_value=before,
        is_sensitive=True,
        was_auto_applied=True,
    )
    return {"ok": True}


def api_admin_create_service(
    camp_id: int,
    payload: AdminServiceUpsertRequest,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_camp_access(admin, camp_id)
    normalized_payload = payload.model_dump()
    normalized_payload["status"] = _normalize_service_status(payload.status)
    if normalized_payload["requires_booking"]:
        normalized_payload["allows_standalone"] = False
    service_id = admin_repo.create_admin_service(camp_id, normalized_payload, int(admin.get("id")))
    service = admin_repo.get_admin_service(camp_id, service_id)
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="service",
        target_id=service_id,
        action_type="service_create",
        action_label="Создал услугу",
        new_value=service,
        is_sensitive=False,
        was_auto_applied=True,
    )
    return {"ok": True, "id": service_id}


def api_admin_update_service(
    camp_id: int,
    service_id: int,
    payload: AdminServiceUpsertRequest,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_camp_access(admin, camp_id)
    before = admin_repo.get_admin_service(camp_id, service_id)
    if not before:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    normalized_payload = payload.model_dump()
    normalized_payload["status"] = _normalize_service_status(payload.status)
    if normalized_payload["requires_booking"]:
        normalized_payload["allows_standalone"] = False
    changed = admin_repo.update_admin_service(camp_id, service_id, normalized_payload, int(admin.get("id")))
    if not changed:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    after = admin_repo.get_admin_service(camp_id, service_id)
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="service",
        target_id=service_id,
        action_type="service_update",
        action_label="Обновил услугу",
        old_value=before,
        new_value=after,
        is_sensitive=False,
        was_auto_applied=True,
    )
    return {"ok": True}


def api_admin_delete_service(camp_id: int, service_id: int, admin: dict = Depends(get_current_admin)):
    _ensure_admin_camp_access(admin, camp_id)
    before = admin_repo.get_admin_service(camp_id, service_id)
    if not before:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    if not admin_repo.archive_admin_service(camp_id, service_id, int(admin.get("id"))):
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="service",
        target_id=service_id,
        action_type="service_archive",
        action_label="Отправил услугу в архив",
        old_value=before,
        is_sensitive=False,
        was_auto_applied=True,
    )
    return {"ok": True}
