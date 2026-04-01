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
    BookingAdminUpdateRequest,
)
from tourist03.serializers import bookings as booking_serializers
from tourist03.security import (
    _get_admin_camp_ids,
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
