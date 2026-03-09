from datetime import date
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from tourist03.booking_db_errors import BookingConflictError, BookingValidationError
from tourist03.domain import bookings as booking_domain
from tourist03.repositories import admin as admin_repo
from tourist03.schemas import AdminCreateBookingRequest, AdminLoginRequest, BookingAdminUpdateRequest
from tourist03.serializers import bookings as booking_serializers
from tourist03.security import _get_admin_camp_ids, get_current_admin, log_user_event, verify_password


def _raise_booking_write_http_error(exc: Exception):
    if isinstance(exc, BookingConflictError):
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    if isinstance(exc, BookingValidationError):
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    raise exc


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
