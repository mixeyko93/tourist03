from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request, status

from tourist03.booking_db_errors import BookingConflictError, BookingValidationError
from tourist03.domain import bookings as booking_domain
from tourist03.domain import crm as crm_domain
from tourist03.repositories import admin as admin_repo
from tourist03.schemas import (
    AdminCampProfileUpdateRequest,
    AdminCreateBookingRequest,
    AdminLoginRequest,
    AdminNotificationStatusUpdateRequest,
    AdminRoomUpsertRequest,
    AdminShiftRuleUpsertRequest,
    AdminShiftSettingsUpdateRequest,
    AdminStaffUpsertRequest,
    AdminServiceUpsertRequest,
    BookingAdminUpdateRequest,
)
from tourist03.serializers import bookings as booking_serializers
from tourist03.security import (
    _get_admin_camp_ids,
    _normalize_phone,
    create_notification_event,
    get_current_admin,
    hash_password,
    issue_admin_telegram_link_code,
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


def _effective_permission_keys(admin_id: int, camp_id: int, *, role_key: Optional[str] = None) -> list[str]:
    explicit_keys = admin_repo.list_camp_admin_permission_keys(admin_id, camp_id)
    if explicit_keys:
        return explicit_keys
    normalized_role = (role_key or "").strip() or "administrator"
    return list(crm_domain.DEFAULT_ROLE_PERMISSIONS.get(normalized_role, ()))


def _ensure_admin_staff_access(admin: dict, camp_id: int):
    link = admin_repo.get_admin_camp_link(int(admin["id"]), camp_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    permission_keys = _effective_permission_keys(
        int(admin["id"]),
        camp_id,
        role_key=link.get("role_key") or admin.get("default_role_key"),
    )
    if not (link.get("can_manage_staff") or "manage_staff_accounts" in permission_keys or "manage_staff_permissions" in permission_keys):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для управления сотрудниками")
    return link, permission_keys


def _ensure_admin_audit_access(admin: dict, camp_id: int):
    link = admin_repo.get_admin_camp_link(int(admin["id"]), camp_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    permission_keys = _effective_permission_keys(
        int(admin["id"]),
        camp_id,
        role_key=link.get("role_key") or admin.get("default_role_key"),
    )
    if "view_audit_log" not in permission_keys and not link.get("can_manage_staff"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для просмотра журнала")
    return link, permission_keys


def _ensure_admin_shift_access(admin: dict, camp_id: int):
    link = admin_repo.get_admin_camp_link(int(admin["id"]), camp_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    permission_keys = _effective_permission_keys(
        int(admin["id"]),
        camp_id,
        role_key=link.get("role_key") or admin.get("default_role_key"),
    )
    if "manage_shift_schedule" not in permission_keys and not link.get("can_manage_staff"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для управления сменами")
    return link, permission_keys


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


def _normalize_staff_permission_keys(permission_keys: list[str]) -> list[str]:
    allowed = set(crm_domain.STAFF_PERMISSION_KEYS)
    result: list[str] = []
    seen: set[str] = set()
    for permission_key in permission_keys:
        normalized = str(permission_key or "").strip()
        if normalized not in allowed or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _booking_status_label(status_value: Optional[str]) -> str:
    return crm_domain.BOOKING_STATUS_UI_LABELS.get((status_value or "").strip().lower(), (status_value or "").strip() or "Без статуса")


def _payment_status_label(status_value: Optional[str]) -> str:
    return crm_domain.PAYMENT_STATUS_UI_LABELS.get((status_value or "").strip().lower(), (status_value or "").strip() or "Без статуса")


def _publish_crm_event(
    *,
    camp_id: Optional[int],
    admin: Optional[dict],
    event_type: str,
    title: str,
    body: str,
    severity: str = "info",
    action_url: Optional[str] = None,
    action_payload: Optional[dict] = None,
    recipient_admin_id: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> None:
    actor_id = int(admin["id"]) if admin and admin.get("id") is not None else None
    actor_name = (admin or {}).get("display_name") if admin else None
    create_notification_event(
        event_type=event_type,
        title=title,
        body=body,
        channel="in_app",
        recipient_scope="crm",
        recipient_admin_id=recipient_admin_id,
        camp_id=camp_id,
        action_url=action_url,
        action_payload=action_payload,
        severity=severity,
        metadata={
            "actor_id": actor_id,
            "actor_display": actor_name,
            **(metadata or {}),
        },
    )


def _parse_shift_time(value: str) -> time:
    raw = str(value or "").strip()
    try:
        hour_str, minute_str = raw.split(":", 1)
        return time(hour=int(hour_str), minute=int(minute_str))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Некорректное время смены") from exc


def _weekday_label(weekday: int) -> str:
    labels = [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
    ]
    try:
        return labels[int(weekday)]
    except Exception:
        return f"День {weekday}"


def _resolve_shift_window(anchor_day: date, starts_at_value, ends_at_value) -> tuple[datetime, datetime]:
    start_time = starts_at_value if isinstance(starts_at_value, time) else _parse_shift_time(str(starts_at_value))
    end_time = ends_at_value if isinstance(ends_at_value, time) else _parse_shift_time(str(ends_at_value))
    starts_at = datetime.combine(anchor_day, start_time)
    ends_at = datetime.combine(anchor_day, end_time)
    if ends_at <= starts_at:
        ends_at += timedelta(days=1)
    return starts_at, ends_at


def _serialize_shift_occurrence(rule: dict, starts_at: datetime, ends_at: datetime, *, timezone_name: str) -> dict:
    return {
        "rule_id": rule.get("id"),
        "admin_id": rule.get("admin_id"),
        "admin_name": rule.get("admin_name") or rule.get("admin_email") or f"Сотрудник #{rule.get('admin_id')}",
        "weekday": rule.get("weekday"),
        "weekday_label": _weekday_label(int(rule.get("weekday") or 0)),
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "starts_time": starts_at.strftime("%H:%M"),
        "ends_time": ends_at.strftime("%H:%M"),
        "is_night_shift": bool(rule.get("is_night_shift")),
        "is_active": bool(rule.get("is_active")),
        "comment": rule.get("comment") or "",
        "timezone": timezone_name,
    }


def _build_shift_overview(timezone_name: str, rules: list[dict]) -> dict:
    try:
        zone = ZoneInfo(timezone_name or "Asia/Irkutsk")
    except Exception:
        zone = ZoneInfo("Asia/Irkutsk")
        timezone_name = "Asia/Irkutsk"

    now = datetime.now(zone)
    active_rules: list[dict] = []
    next_occurrence: Optional[dict] = None
    upcoming_windows: list[dict] = []

    for offset in range(0, 14):
        anchor_day = (now + timedelta(days=offset)).date()
        weekday_value = anchor_day.weekday()
        for rule in rules:
            if not rule.get("is_active"):
                continue
            if int(rule.get("weekday") or 0) != weekday_value:
                continue
            starts_at_naive, ends_at_naive = _resolve_shift_window(anchor_day, rule.get("starts_at"), rule.get("ends_at"))
            starts_at = starts_at_naive.replace(tzinfo=zone)
            ends_at = ends_at_naive.replace(tzinfo=zone)
            occurrence = _serialize_shift_occurrence(rule, starts_at, ends_at, timezone_name=timezone_name)
            if starts_at <= now < ends_at:
                active_rules.append(occurrence)
            if starts_at > now:
                upcoming_windows.append(occurrence)
                if next_occurrence is None or starts_at < datetime.fromisoformat(next_occurrence["starts_at"]):
                    next_occurrence = occurrence

    previous_day = (now - timedelta(days=1)).date()
    previous_weekday = previous_day.weekday()
    for rule in rules:
        if not rule.get("is_active"):
            continue
        if int(rule.get("weekday") or 0) != previous_weekday:
            continue
        starts_at_naive, ends_at_naive = _resolve_shift_window(previous_day, rule.get("starts_at"), rule.get("ends_at"))
        starts_at = starts_at_naive.replace(tzinfo=zone)
        ends_at = ends_at_naive.replace(tzinfo=zone)
        if starts_at <= now < ends_at:
            active_rules.append(_serialize_shift_occurrence(rule, starts_at, ends_at, timezone_name=timezone_name))

    active_rules.sort(key=lambda item: (item["starts_at"], item["admin_name"]))
    upcoming_windows.sort(key=lambda item: (item["starts_at"], item["admin_name"]))
    return {
        "timezone": timezone_name,
        "now": now.isoformat(),
        "active_rules": active_rules,
        "next_rule": next_occurrence,
        "upcoming_windows": upcoming_windows[:10],
    }


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


def api_admin_events(
    camp_id: Optional[int] = None,
    search: Optional[str] = None,
    event_status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 200,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if camp_id and camp_id not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")

    normalized_status = (event_status or "").strip().lower() or None
    if normalized_status and normalized_status not in crm_domain.EVENT_CENTER_STATUS_KEYS:
        raise HTTPException(status_code=400, detail="Некорректный статус события")

    normalized_severity = (severity or "").strip().lower() or None
    if normalized_severity and normalized_severity not in {"info", "warning", "critical"}:
        raise HTTPException(status_code=400, detail="Некорректный приоритет события")

    items = admin_repo.list_admin_notification_events(
        int(admin["id"]),
        camp_ids,
        camp_id=camp_id,
        search=search,
        status=normalized_status,
        severity=normalized_severity,
        limit=limit,
    )
    summary = admin_repo.get_admin_notification_summary(int(admin["id"]), camp_ids, camp_id=camp_id)
    return {
        "items": items,
        "summary": summary,
    }


def api_admin_event_summary(
    camp_id: Optional[int] = None,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if camp_id and camp_id not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    return admin_repo.get_admin_notification_summary(int(admin["id"]), camp_ids, camp_id=camp_id)


def api_admin_update_event_status(
    event_id: int,
    payload: AdminNotificationStatusUpdateRequest,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    normalized_status = (payload.status or "").strip().lower()
    if normalized_status not in crm_domain.EVENT_CENTER_STATUS_KEYS:
        raise HTTPException(status_code=400, detail="Некорректный статус события")
    event_item = admin_repo.get_admin_notification_event(event_id, int(admin["id"]), camp_ids)
    if not event_item:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    if not admin_repo.update_admin_notification_status(event_id, normalized_status):
        raise HTTPException(status_code=404, detail="Событие не найдено")
    updated = admin_repo.get_admin_notification_event(event_id, int(admin["id"]), camp_ids)
    return {"ok": True, "item": updated}


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
    guest_label = guest_name or guest_phone or guest_email or f"Бронь #{booking_id}"
    _publish_crm_event(
        camp_id=payload.camp_id,
        admin=admin,
        event_type="booking_created",
        title="В CRM создана новая бронь",
        body=(
            f"{guest_label} · {payload.check_in.isoformat()} → {payload.check_out.isoformat()} · "
            f"статус: {_booking_status_label(booking_status)}."
        ),
        severity="warning",
        action_url="/bookings",
        action_payload={"booking_id": booking_id, "camp_id": payload.camp_id},
        metadata={"booking_id": booking_id, "room_id": room_id},
    )
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
    next_status = new_status or booking.get("status")
    next_payment_status = payment_status or booking.get("payment_status")
    _publish_crm_event(
        camp_id=booking.get("camp_id"),
        admin=admin,
        event_type="booking_updated",
        title=f"Бронь #{booking_id} обновлена",
        body=(
            f"Статус: {_booking_status_label(next_status)}. "
            f"Оплата: {_payment_status_label(next_payment_status)}."
        ),
        severity="info",
        action_url="/bookings",
        action_payload={"booking_id": booking_id, "camp_id": booking.get("camp_id")},
        metadata={"booking_id": booking_id},
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


def api_admin_camp_shifts(camp_id: int, admin: dict = Depends(get_current_admin)):
    _ensure_admin_shift_access(admin, camp_id)
    settings = admin_repo.get_camp_shift_settings(camp_id) or {
        "camp_id": camp_id,
        "time_zone": "Asia/Irkutsk",
        "booking_hold_hours": 4,
        "night_release_after_shift_minutes": 60,
        "escalation_step_minutes": 15,
        "escalation_repeats_before_manager": 2,
    }
    rules = admin_repo.list_camp_shift_rules(camp_id)
    staff_items = admin_repo.list_admin_staff(camp_id)
    staff = [
        {
            "id": item.get("id"),
            "display_name": item.get("display_name") or item.get("email") or f"Сотрудник #{item.get('id')}",
            "role_key": item.get("role_key") or item.get("default_role_key") or "administrator",
            "role_label": crm_domain.STAFF_ROLE_LABELS.get(item.get("role_key") or item.get("default_role_key") or "administrator", item.get("role_key") or "administrator"),
            "is_active": bool(item.get("is_active")),
            "notifications_enabled": bool(item.get("notifications_enabled", True)),
            "has_telegram_link": bool(item.get("telegram_chat_id")),
        }
        for item in staff_items
        if bool(item.get("is_active"))
    ]
    return {
        "settings": settings,
        "rules": rules,
        "overview": _build_shift_overview(str(settings.get("time_zone") or "Asia/Irkutsk"), rules),
        "staff": staff,
    }


def api_admin_update_shift_settings(
    camp_id: int,
    payload: AdminShiftSettingsUpdateRequest,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_shift_access(admin, camp_id)
    before = admin_repo.get_camp_shift_settings(camp_id)
    admin_repo.save_camp_shift_settings(camp_id, payload.model_dump())
    after = admin_repo.get_camp_shift_settings(camp_id)
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="shift_settings",
        target_id=camp_id,
        action_type="shift_settings_update",
        action_label="Обновил параметры смен",
        old_value=before,
        new_value=after,
        is_sensitive=True,
        was_auto_applied=True,
    )
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="shift_settings_updated",
        title="Параметры смен изменены",
        body=(
            f"{admin.get('display_name') or 'Сотрудник'} обновил SLA заявок, "
            f"ночной резерв и интервалы эскалации."
        ),
        severity="warning",
        action_url="/shifts",
        action_payload={"camp_id": camp_id},
    )
    return {"ok": True, "item": after}


def api_admin_create_shift_rule(
    camp_id: int,
    payload: AdminShiftRuleUpsertRequest,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_shift_access(admin, camp_id)
    if not admin_repo.get_admin_staff_member(camp_id, payload.admin_id):
        raise HTTPException(status_code=400, detail="Сотрудник не привязан к этой базе")
    if payload.weekday < 0 or payload.weekday > 6:
        raise HTTPException(status_code=400, detail="Некорректный день недели")
    _parse_shift_time(payload.starts_at)
    _parse_shift_time(payload.ends_at)
    rule_id = admin_repo.create_camp_shift_rule(camp_id, payload.model_dump(), int(admin["id"]))
    rule = admin_repo.get_camp_shift_rule(camp_id, rule_id)
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="shift_rule",
        target_id=rule_id,
        action_type="shift_rule_create",
        action_label="Создал правило смены",
        new_value=rule,
        is_sensitive=True,
        was_auto_applied=True,
    )
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="shift_rule_created",
        title="Добавлено новое правило смены",
        body=f"{rule.get('admin_name') or 'Сотрудник'} · {_weekday_label(payload.weekday)} · {payload.starts_at} → {payload.ends_at}.",
        severity="warning",
        action_url="/shifts",
        action_payload={"camp_id": camp_id, "rule_id": rule_id},
        metadata={"rule_id": rule_id},
    )
    return {"ok": True, "id": rule_id, "item": rule}


def api_admin_update_shift_rule(
    camp_id: int,
    rule_id: int,
    payload: AdminShiftRuleUpsertRequest,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_shift_access(admin, camp_id)
    before = admin_repo.get_camp_shift_rule(camp_id, rule_id)
    if not before:
        raise HTTPException(status_code=404, detail="Правило смены не найдено")
    if not admin_repo.get_admin_staff_member(camp_id, payload.admin_id):
        raise HTTPException(status_code=400, detail="Сотрудник не привязан к этой базе")
    if payload.weekday < 0 or payload.weekday > 6:
        raise HTTPException(status_code=400, detail="Некорректный день недели")
    _parse_shift_time(payload.starts_at)
    _parse_shift_time(payload.ends_at)
    changed = admin_repo.update_camp_shift_rule(camp_id, rule_id, payload.model_dump())
    if not changed:
        raise HTTPException(status_code=404, detail="Правило смены не найдено")
    after = admin_repo.get_camp_shift_rule(camp_id, rule_id)
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="shift_rule",
        target_id=rule_id,
        action_type="shift_rule_update",
        action_label="Обновил правило смены",
        old_value=before,
        new_value=after,
        is_sensitive=True,
        was_auto_applied=True,
    )
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="shift_rule_updated",
        title="Правило смены обновлено",
        body=f"{after.get('admin_name') or 'Сотрудник'} · {_weekday_label(payload.weekday)} · {payload.starts_at} → {payload.ends_at}.",
        severity="warning",
        action_url="/shifts",
        action_payload={"camp_id": camp_id, "rule_id": rule_id},
        metadata={"rule_id": rule_id},
    )
    return {"ok": True, "item": after}


def api_admin_delete_shift_rule(camp_id: int, rule_id: int, admin: dict = Depends(get_current_admin)):
    _ensure_admin_shift_access(admin, camp_id)
    before = admin_repo.get_camp_shift_rule(camp_id, rule_id)
    if not before:
        raise HTTPException(status_code=404, detail="Правило смены не найдено")
    if not admin_repo.delete_camp_shift_rule(camp_id, rule_id):
        raise HTTPException(status_code=404, detail="Правило смены не найдено")
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="shift_rule",
        target_id=rule_id,
        action_type="shift_rule_delete",
        action_label="Удалил правило смены",
        old_value=before,
        is_sensitive=True,
        was_auto_applied=True,
    )
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="shift_rule_deleted",
        title="Правило смены удалено",
        body=(
            f"{before.get('admin_name') or 'Сотрудник'} · "
            f"{_weekday_label(before.get('weekday') or 0)} · "
            f"{str(before.get('starts_at') or '')[:5]} → {str(before.get('ends_at') or '')[:5]}."
        ),
        severity="warning",
        action_url="/shifts",
        action_payload={"camp_id": camp_id},
        metadata={"rule_id": rule_id},
    )
    return {"ok": True}


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
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="camp_profile_updated",
        title="Профиль базы обновлён",
        body=f"{admin.get('display_name') or 'Сотрудник'} изменил карточку базы и контактные данные.",
        severity="info",
        action_url="/settings",
        action_payload={"camp_id": camp_id, "tab": "profile"},
    )
    return {"ok": True, "item": after}


def api_admin_camp_rooms(camp_id: int, admin: dict = Depends(get_current_admin)):
    _ensure_admin_camp_access(admin, camp_id)
    return admin_repo.list_admin_camp_rooms(camp_id)


def api_admin_camp_staff(camp_id: int, admin: dict = Depends(get_current_admin)):
    _ensure_admin_staff_access(admin, camp_id)
    items = admin_repo.list_admin_staff(camp_id)
    for item in items:
        role_key = (item.get("role_key") or item.get("default_role_key") or "administrator").strip() or "administrator"
        permission_keys = item.get("permission_keys") or list(crm_domain.DEFAULT_ROLE_PERMISSIONS.get(role_key, ()))
        item["permission_keys"] = permission_keys
        item["role_label"] = crm_domain.STAFF_ROLE_LABELS.get(role_key, role_key)
        item["has_telegram_link"] = bool(item.get("telegram_chat_id"))
    return {
        "items": items,
        "roles": [{"key": key, "label": crm_domain.STAFF_ROLE_LABELS[key]} for key in crm_domain.STAFF_ROLE_KEYS],
        "permissions": [{"key": key, "label": crm_domain.STAFF_PERMISSION_LABELS[key]} for key in crm_domain.STAFF_PERMISSION_KEYS],
    }


def api_admin_create_staff(
    camp_id: int,
    payload: AdminStaffUpsertRequest,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_staff_access(admin, camp_id)
    email = str(payload.email).strip().lower()
    display_name = (payload.display_name or "").strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="Укажите имя сотрудника")
    role_key = (payload.role_key or "").strip() or "administrator"
    if role_key not in crm_domain.STAFF_ROLE_KEYS:
        raise HTTPException(status_code=400, detail="Некорректная роль сотрудника")
    password_raw = (payload.password or "").strip()
    permission_keys = _normalize_staff_permission_keys(payload.permission_keys or [])
    if not permission_keys:
        permission_keys = list(crm_domain.DEFAULT_ROLE_PERMISSIONS.get(role_key, ()))

    try:
        staff_id = admin_repo.create_or_link_admin_staff(
            camp_id,
            {
                "email": email,
                "display_name": display_name,
                "phone": _normalize_phone(payload.phone or ""),
                "role_key": role_key,
                "can_manage_staff": bool(payload.can_manage_staff),
                "is_primary": bool(payload.is_primary),
                "is_active": bool(payload.is_active),
                "notifications_enabled": bool(payload.notifications_enabled),
                "permission_keys": permission_keys,
            },
            int(admin["id"]),
            hash_password(password_raw) if password_raw else None,
        )
    except ValueError as exc:
        if str(exc) == "password_required":
            raise HTTPException(status_code=400, detail="Для новой учётки задайте пароль") from exc
        if str(exc) == "already_linked":
            raise HTTPException(status_code=409, detail="Сотрудник уже привязан к этой базе") from exc
        raise

    staff = admin_repo.get_admin_staff_member(camp_id, staff_id)
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="staff_account",
        target_id=staff_id,
        action_type="staff_create",
        action_label="Создал учётку сотрудника",
        new_value=staff,
        is_sensitive=True,
        was_auto_applied=True,
    )
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="staff_created",
        title="В команду базы добавлен сотрудник",
        body=f"{staff.get('display_name') or staff.get('email') or 'Новый сотрудник'} · роль: {staff.get('role_label') or 'Не указана'}.",
        severity="warning",
        action_url="/settings",
        action_payload={"camp_id": camp_id, "tab": "team", "staff_id": staff_id},
        metadata={"staff_id": staff_id},
    )
    return {"ok": True, "id": staff_id, "item": staff}


def api_admin_update_staff(
    camp_id: int,
    staff_id: int,
    payload: AdminStaffUpsertRequest,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_staff_access(admin, camp_id)
    before = admin_repo.get_admin_staff_member(camp_id, staff_id)
    if not before:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    display_name = (payload.display_name or "").strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="Укажите имя сотрудника")
    role_key = (payload.role_key or "").strip() or "administrator"
    if role_key not in crm_domain.STAFF_ROLE_KEYS:
        raise HTTPException(status_code=400, detail="Некорректная роль сотрудника")
    permission_keys = _normalize_staff_permission_keys(payload.permission_keys or [])
    if not permission_keys:
        permission_keys = list(crm_domain.DEFAULT_ROLE_PERMISSIONS.get(role_key, ()))

    try:
        changed = admin_repo.update_admin_staff(
            camp_id,
            staff_id,
            {
                "email": str(payload.email).strip().lower(),
                "display_name": display_name,
                "phone": _normalize_phone(payload.phone or ""),
                "role_key": role_key,
                "can_manage_staff": bool(payload.can_manage_staff),
                "is_primary": bool(payload.is_primary),
                "is_active": bool(payload.is_active),
                "notifications_enabled": bool(payload.notifications_enabled),
                "permission_keys": permission_keys,
            },
            int(admin["id"]),
            hash_password((payload.password or "").strip()) if (payload.password or "").strip() else None,
        )
    except ValueError as exc:
        if str(exc) == "email_conflict":
            raise HTTPException(status_code=409, detail="Учётка с таким email уже существует") from exc
        raise
    if not changed:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    after = admin_repo.get_admin_staff_member(camp_id, staff_id)
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="staff_account",
        target_id=staff_id,
        action_type="staff_update",
        action_label="Обновил учётку сотрудника",
        old_value=before,
        new_value=after,
        is_sensitive=True,
        was_auto_applied=True,
    )
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="staff_updated",
        title="Учётка сотрудника обновлена",
        body=f"{after.get('display_name') or after.get('email') or 'Сотрудник'} · роль: {after.get('role_label') or 'Не указана'}.",
        severity="warning",
        action_url="/settings",
        action_payload={"camp_id": camp_id, "tab": "team", "staff_id": staff_id},
        metadata={"staff_id": staff_id},
    )
    return {"ok": True, "item": after}


def api_admin_issue_staff_telegram_link(
    camp_id: int,
    staff_id: int,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_staff_access(admin, camp_id)
    staff = admin_repo.get_admin_staff_member(camp_id, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    code = issue_admin_telegram_link_code(int(staff_id))
    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="staff_account",
        target_id=staff_id,
        action_type="staff_telegram_link_issue",
        action_label="Сгенерировал код привязки Telegram",
        comment=f"Код выдан для {staff.get('display_name') or staff.get('email')}",
        is_sensitive=False,
        was_auto_applied=True,
    )
    return {"ok": True, "code": code}


def api_admin_audit_log(
    camp_id: int,
    search: Optional[str] = None,
    actor_id: Optional[int] = None,
    target_type: Optional[str] = None,
    limit: int = 200,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_audit_access(admin, camp_id)
    items = admin_repo.list_admin_audit_log(
        camp_id,
        search=search,
        actor_id=actor_id,
        target_type=target_type,
        limit=limit,
    )
    actors = []
    seen_actors: set[int] = set()
    target_types: set[str] = set()
    for item in items:
        actor_value = item.get("actor_id")
        if actor_value is not None:
            actor_int = int(actor_value)
            if actor_int not in seen_actors:
                seen_actors.add(actor_int)
                actors.append(
                    {
                        "id": actor_int,
                        "label": item.get("actor_display") or f"Сотрудник #{actor_int}",
                    }
                )
        target_type_value = str(item.get("target_type") or "").strip()
        if target_type_value:
            target_types.add(target_type_value)
    return {
        "items": items,
        "actors": actors,
        "target_types": sorted(target_types),
    }


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
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="room_created",
        title="Добавлен новый апартамент",
        body=f"{room.get('name') or 'Апартамент'} теперь доступен в номерном фонде базы.",
        severity="info",
        action_url="/rooms",
        action_payload={"camp_id": camp_id, "room_id": room_id},
        metadata={"room_id": room_id},
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
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="room_updated",
        title="Апартамент обновлён",
        body=f"{after.get('name') or 'Апартамент'} изменён в CRM.",
        severity="info",
        action_url="/rooms",
        action_payload={"camp_id": camp_id, "room_id": room_id},
        metadata={"room_id": room_id},
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
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="room_deleted",
        title="Апартамент удалён",
        body=f"{before.get('name') or 'Апартамент'} удалён из номерного фонда.",
        severity="warning",
        action_url="/rooms",
        action_payload={"camp_id": camp_id},
        metadata={"room_id": room_id},
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
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="service_created",
        title="Создана новая услуга",
        body=f"{service.get('name') or 'Услуга'} добавлена в каталог базы.",
        severity="info",
        action_url="/services",
        action_payload={"camp_id": camp_id, "service_id": service_id},
        metadata={"service_id": service_id},
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
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="service_updated",
        title="Услуга обновлена",
        body=f"{after.get('name') or 'Услуга'} изменена в CRM.",
        severity="info",
        action_url="/services",
        action_payload={"camp_id": camp_id, "service_id": service_id},
        metadata={"service_id": service_id},
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
    _publish_crm_event(
        camp_id=camp_id,
        admin=admin,
        event_type="service_archived",
        title="Услуга отправлена в архив",
        body=f"{before.get('name') or 'Услуга'} больше не показывается в активном каталоге.",
        severity="warning",
        action_url="/services",
        action_payload={"camp_id": camp_id},
        metadata={"service_id": service_id},
    )
    return {"ok": True}
