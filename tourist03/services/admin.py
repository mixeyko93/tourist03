from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request, status

from tourist03.booking_db_errors import BookingConflictError, BookingValidationError
from tourist03.config import STAFF_BOT_USERNAME
from tourist03.repositories import auth as auth_repo
from tourist03.domain import bookings as booking_domain
from tourist03.domain import crm as crm_domain
from tourist03.repositories import admin as admin_repo
from tourist03.repositories import notifications as notification_repo
from tourist03.repositories import ui_overrides as ui_override_repo
from tourist03.storage import _normalize_move
from tourist03.schemas import (
    AdminCampProfileUpdateRequest,
    AdminChangeRequestCreateRequest,
    AdminChangeRequestDecisionRequest,
    AdminCreateBookingRequest,
    AdminLoginRequest,
    AdminNotificationStatusUpdateRequest,
    AdminRoomUpsertRequest,
    AdminShiftRuleUpsertRequest,
    AdminShiftSettingsUpdateRequest,
    AdminStaffUpsertRequest,
    AdminServiceUpsertRequest,
    BookingAdminUpdateRequest,
    UiOverrideSaveRequest,
)
from tourist03.serializers import bookings as booking_serializers
from tourist03.security import (
    _get_admin_camp_ids,
    _normalize_phone,
    create_notification_event,
    get_current_admin,
    get_ui_override_editor,
    hash_password,
    is_valid_panel_login,
    issue_admin_telegram_link_code,
    log_crm_audit_event,
    log_user_event,
    normalize_panel_login,
    verify_password,
)


ALLOWED_UI_OVERRIDE_KEYS = {"crm_login_page"}


def _normalize_admin_login_or_400(value: str, *, allow_legacy_email: bool = False) -> str:
    login = normalize_panel_login(value)
    if not login:
        raise HTTPException(status_code=400, detail="Укажите логин")
    if allow_legacy_email and "@" in login:
        return login
    if not is_valid_panel_login(login):
        raise HTTPException(status_code=400, detail="Логин должен быть в формате mikhail.stasenko")
    return login


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


def _change_kind_permission_key(change_kind: str) -> Optional[str]:
    mapping = {
        "shift_schedule": "manage_shift_schedule",
        "pricing": "manage_pricing",
        "cancellation_policy": "manage_cancellation_policy",
        "camp_visibility": "manage_camp_visibility",
        "archive": "manage_camp_visibility",
    }
    return mapping.get((change_kind or "").strip())


def _camp_profile_payload_from_snapshot(snapshot: dict | None) -> dict:
    snapshot = snapshot or {}
    camp = snapshot.get("camp") or {}
    settings = snapshot.get("settings") or {}
    return {
        "name": camp.get("name") or "",
        "lake_name": camp.get("lake_name"),
        "address": camp.get("address"),
        "phone": camp.get("phone"),
        "site_url": camp.get("site_url"),
        "description": camp.get("description"),
        "time_zone": settings.get("time_zone"),
        "check_in_time": settings.get("check_in_time"),
        "check_out_time": settings.get("check_out_time"),
        "cancellation_policy": settings.get("cancellation_policy"),
        "arrival_instructions": settings.get("arrival_instructions"),
        "payment_instructions": settings.get("payment_instructions"),
        "admin_contact_phone": settings.get("admin_contact_phone"),
        "support_whatsapp": settings.get("support_whatsapp"),
        "support_telegram": settings.get("support_telegram"),
        "notifications_enabled": bool(settings.get("notifications_enabled", True)),
        "media": _normalize_media_payload(snapshot.get("media") or []),
    }


def _room_payload_from_snapshot(snapshot: dict | None) -> dict:
    snapshot = snapshot or {}
    return {
        "name": snapshot.get("name") or "",
        "room_type": snapshot.get("room_type"),
        "floors": int(snapshot.get("floors") or 1),
        "floor": int(snapshot.get("floor") or 1),
        "beds_single": int(snapshot.get("beds_single") or 0),
        "beds_double": int(snapshot.get("beds_double") or 0),
        "bath_type": snapshot.get("bath_type"),
        "wc_type": snapshot.get("wc_type"),
        "bbq_type": snapshot.get("bbq_type"),
        "kitchen_type": snapshot.get("kitchen_type"),
        "gazebo_type": snapshot.get("gazebo_type"),
        "terrace_type": snapshot.get("terrace_type"),
        "pool_type": snapshot.get("pool_type"),
        "balcony_type": snapshot.get("balcony_type"),
        "has_ac": bool(snapshot.get("has_ac")),
        "price_adult": int(snapshot.get("price_adult") or 0),
        "price_child": int(snapshot.get("price_child") or 0),
        "price": int(snapshot.get("price") or 0),
        "discount_pct": int(snapshot.get("discount_pct") or 0),
        "discount_from_nights": int(snapshot.get("discount_from_nights") or 0),
        "description": snapshot.get("description"),
        "media": _normalize_media_payload(snapshot.get("media") or []),
    }


def _normalize_media_payload(raw_media: Any, *, max_images: int = 20) -> list[dict]:
    items: list[dict] = []
    image_count = 0
    video_seen = False
    source = raw_media if isinstance(raw_media, list) else []
    for raw in source:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or "").strip()
        if not url:
            continue
        media_type = str(raw.get("media_type") or "").strip().lower()
        if media_type not in {"image", "video"}:
            media_type = "video" if any(url.lower().split("?", 1)[0].endswith(ext) for ext in (".mp4", ".mov", ".webm", ".m4v")) else "image"
        if media_type == "video":
            if video_seen:
                continue
            video_seen = True
        else:
            if image_count >= max_images:
                continue
            image_count += 1
        source_kind = str(raw.get("source_kind") or "").strip().lower()
        if source_kind not in {"upload", "external"}:
            source_kind = "external" if media_type == "video" and not url.startswith("/static/uploads/") else "upload"
        items.append(
            {
                "media_type": media_type,
                "url": url,
                "poster_url": str(raw.get("poster_url") or "").strip() or None,
                "source_kind": source_kind,
                "cover": bool(raw.get("cover")) if media_type == "image" else False,
                "sort": len(items),
            }
        )
    image_items = [item for item in items if item.get("media_type") == "image"]
    if image_items and not any(bool(item.get("cover")) for item in image_items):
        image_items[0]["cover"] = True
    return items


def _media_key(item: dict) -> tuple[str, str]:
    return (str(item.get("media_type") or "image").strip().lower(), str(item.get("url") or "").strip())


def _new_pending_media_items(before_items: list[dict], after_items: list[dict]) -> list[dict]:
    before_status = {_media_key(item): str(item.get("moderation_status") or "").strip().lower() for item in before_items}
    result: list[dict] = []
    for item in after_items:
        if str(item.get("moderation_status") or "").strip().lower() != "pending":
            continue
        if before_status.get(_media_key(item)) == "pending":
            continue
        result.append(item)
    return result


def _notify_superadmins_about_media_review(
    *,
    camp_id: int,
    camp_name: str,
    actor_admin: dict,
    pending_items: list[dict],
    entity_type: str,
    room_id: Optional[int] = None,
    room_name: Optional[str] = None,
) -> None:
    if not pending_items:
        return
    recipients = notification_repo.list_active_superadmin_telegram_recipients()
    if not recipients:
        return

    actor_label = actor_admin.get("display_name") or actor_admin.get("email") or "Сотрудник CRM"
    for item in pending_items:
        media_id = item.get("id")
        media_label = "видео" if str(item.get("media_type") or "").lower() == "video" else "фото"
        location_label = (room_name or "общий контент базы") if entity_type == "room" else "карточка базы"
        title = "Новый контент ждёт модерации"
        body = (
            f"{actor_label} загрузил {media_label}.\n"
            f"База: {camp_name}\n"
            f"Раздел: {location_label}\n"
            "Проверьте материал и примите решение."
        )
        metadata = {
            "entity_type": entity_type,
            "media_id": media_id,
            "room_id": room_id,
            "room_name": room_name,
            "media_type": item.get("media_type"),
        }
        for recipient in recipients:
            for channel in ("in_app", "telegram"):
                create_notification_event(
                    event_type="superadmin_media_moderation",
                    title=title,
                    body=body,
                    channel=channel,
                    recipient_scope="superadmin",
                    recipient_admin_id=int(recipient["id"]),
                    camp_id=camp_id,
                    action_url="/admin/moderation",
                    action_payload={
                        "entity_type": entity_type,
                        "media_id": media_id,
                        "camp_id": camp_id,
                        "room_id": room_id,
                    },
                    severity="warning",
                    metadata=metadata,
                )


def _extract_camp_pending_media_notifications(before_snapshot: dict | None, after_snapshot: dict | None) -> list[dict]:
    before_items = (before_snapshot or {}).get("media") or []
    after_items = (after_snapshot or {}).get("media") or []
    return _new_pending_media_items(before_items, after_items)


def _extract_room_pending_media_notifications(before_snapshot: dict | None, after_snapshot: dict | None) -> list[dict]:
    before_items = (before_snapshot or {}).get("media") or []
    after_items = (after_snapshot or {}).get("media") or []
    return _new_pending_media_items(before_items, after_items)


def _emit_superadmin_media_notifications_from_snapshot(camp_id: int, actor_admin: dict, snapshot: dict) -> None:
    operation = str(snapshot.get("operation") or "").strip()
    if operation == "camp_profile_update":
        before = snapshot.get("before") or {}
        after = snapshot.get("after") or {}
        _notify_superadmins_about_media_review(
            camp_id=camp_id,
            camp_name=((after.get("camp") or {}) or {}).get("name") or f"База #{camp_id}",
            actor_admin=actor_admin,
            pending_items=_extract_camp_pending_media_notifications(before, after),
            entity_type="camp",
        )
    elif operation in {"room_create", "room_update"}:
        before = snapshot.get("before") or {}
        after = snapshot.get("after") or {}
        room_id = int(snapshot.get("target_id") or after.get("id") or 0) or None
        _notify_superadmins_about_media_review(
            camp_id=camp_id,
            camp_name=(admin_repo.get_admin_camp_profile(camp_id) or {}).get("camp", {}).get("name") or f"База #{camp_id}",
            actor_admin=actor_admin,
            pending_items=_extract_room_pending_media_notifications(before, after),
            entity_type="room",
            room_id=room_id,
            room_name=after.get("name") or before.get("name") or (f"Апартамент #{room_id}" if room_id else "Апартамент"),
        )


def _reviewer_candidates(camp_id: int, permission_key: Optional[str]) -> list[dict]:
    candidates: list[dict] = []
    for item in admin_repo.list_admin_staff(camp_id):
        if not bool(item.get("is_active")):
            continue
        role_key = (item.get("role_key") or item.get("default_role_key") or "administrator").strip() or "administrator"
        permission_keys = item.get("permission_keys") or list(crm_domain.DEFAULT_ROLE_PERMISSIONS.get(role_key, ()))
        if item.get("can_manage_staff") or item.get("is_primary") or (permission_key and permission_key in permission_keys):
            candidates.append(dict(item))
    return candidates


def _ensure_change_request_review_access(admin: dict, request_item: dict):
    camp_id = int(request_item.get("camp_id") or 0)
    link = admin_repo.get_admin_camp_link(int(admin["id"]), camp_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    permission_keys = _effective_permission_keys(
        int(admin["id"]),
        camp_id,
        role_key=link.get("role_key") or admin.get("default_role_key"),
    )
    permission_key = _change_kind_permission_key(str(request_item.get("change_kind") or ""))
    if not (link.get("can_manage_staff") or link.get("is_primary") or (permission_key and permission_key in permission_keys)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для согласования изменений")
    return link, permission_keys


def admin_login(req: AdminLoginRequest, request: Request):
    row = admin_repo.find_admin_account_by_login(_normalize_admin_login_or_400(req.login, allow_legacy_email=True))
    if not row or not row["is_active"] or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный логин или пароль")
    request.session["admin_id"] = row["id"]
    return {"status": "ok"}


def admin_logout(request: Request):
    request.session.pop("admin_id", None)
    return {"status": "ok"}


def admin_me(admin: dict = Depends(get_current_admin)):
    return admin


def _validate_ui_override_key(override_key: str) -> str:
    normalized = (override_key or "").strip().lower()
    if normalized not in ALLOWED_UI_OVERRIDE_KEYS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Шаблон интерфейса не найден")
    return normalized


def api_public_ui_override(override_key: str):
    normalized = _validate_ui_override_key(override_key)
    row = ui_override_repo.get_ui_override(normalized)
    return {
        "key": normalized,
        "payload": (row or {}).get("payload") or {},
        "updated_at": (row or {}).get("updated_at"),
    }


def api_admin_save_ui_override(
    override_key: str,
    payload: UiOverrideSaveRequest,
    editor: dict = Depends(get_ui_override_editor),
):
    normalized = _validate_ui_override_key(override_key)
    previous = ui_override_repo.get_ui_override(normalized)
    saved = ui_override_repo.save_ui_override(
        normalized,
        payload.payload if isinstance(payload.payload, dict) else {},
        actor_type=str(editor.get("actor_type") or "camp_admin"),
        actor_id=editor.get("actor_id"),
        actor_display=editor.get("actor_display"),
    )
    log_crm_audit_event(
        actor_type=str(editor.get("actor_type") or "camp_admin"),
        actor_id=editor.get("actor_id"),
        actor_display=editor.get("actor_display"),
        target_type="ui_override",
        target_id=normalized,
        action_type="ui_override_saved",
        action_label="Сохранены правки интерфейса",
        changed_field=normalized,
        old_value=(previous or {}).get("payload") or {},
        new_value=saved.get("payload") or {},
        comment="Изменена конфигурация публичной страницы CRM",
        metadata={"override_key": normalized},
    )
    return saved


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


def _normalize_guest_email(email_value: Optional[str]) -> Optional[str]:
    if email_value is None:
        return None
    normalized = str(email_value).strip().lower()
    return normalized or None


def _resolve_booking_user_link(*, guest_name: Optional[str], guest_phone: Optional[str], guest_email: Optional[str]) -> tuple[Optional[dict], Optional[dict], str]:
    normalized_phone = _normalize_phone((guest_phone or "").strip())
    normalized_email = _normalize_guest_email(guest_email)
    if not normalized_phone:
        return None, None, normalized_phone

    existing_user = auth_repo.find_user_by_phone(normalized_phone)
    if existing_user:
        return existing_user, None, normalized_phone

    shadow_email = normalized_email
    if shadow_email and auth_repo.find_user_by_email(shadow_email):
        shadow_email = None

    shadow_user = auth_repo.create_shadow_user(guest_name or "", normalized_phone, shadow_email)
    log_user_event(
        int(shadow_user["id"]),
        "crm_shadow_profile_created",
        {
            "phone": normalized_phone,
            "email": shadow_email,
            "display_name": (guest_name or "").strip() or None,
        },
    )
    return shadow_user, shadow_user, normalized_phone


def _booking_guest_label_from_row(row: dict) -> str:
    return (
        (row.get("guest_name") or "").strip()
        or (row.get("user_name") or "").strip()
        or (row.get("guest_phone") or "").strip()
        or (row.get("user_phone") or "").strip()
        or f"Бронь #{row.get('id')}"
    )


def _booking_customer_sync_note(row: dict) -> Optional[str]:
    user_id = row.get("user_id")
    if not user_id:
        return None
    if row.get("user_phone") and not row.get("user_email"):
        return "Бронь привязана к профилю по телефону, email ждёт подтверждения."
    return "Бронь синхронизирована с личным кабинетом пользователя."


def _booking_event_severity(status_value: Optional[str], payment_status_value: Optional[str]) -> str:
    normalized_status = booking_domain.normalize_booking_status(status_value, default="")
    normalized_payment = booking_domain.normalize_payment_status(payment_status_value, default="", allow_none=True)
    if normalized_status in {"awaiting_payment", "expired_pending", "cancelled", "cancelled_by_base", "rejected", "no_show"}:
        return "warning"
    if normalized_payment in {"awaiting_prepayment", "partially_paid", "failed"}:
        return "warning"
    return "info"


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
    if event_type in admin_repo.CRM_BOOKING_EVENT_TYPES:
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
    if camp_id and severity in {"warning", "critical"}:
        recipients = notification_repo.list_active_staff_telegram_recipients(
            int(camp_id),
            admin_ids=[int(recipient_admin_id)] if recipient_admin_id is not None else None,
            exclude_admin_ids=[actor_id] if actor_id is not None and recipient_admin_id is None else None,
        )
        for recipient in recipients:
            create_notification_event(
                event_type=event_type,
                title=title,
                body=body,
                channel="telegram",
                recipient_scope="crm",
                recipient_admin_id=int(recipient["id"]),
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


def _publish_targeted_staff_event(
    *,
    camp_id: int,
    recipient_admin_id: int,
    event_type: str,
    title: str,
    body: str,
    action_url: Optional[str] = None,
    action_payload: Optional[dict] = None,
    severity: str = "info",
    metadata: Optional[dict] = None,
) -> None:
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
        metadata=metadata or {},
    )
    recipients = notification_repo.list_active_staff_telegram_recipients(camp_id, admin_ids=[recipient_admin_id])
    for recipient in recipients:
        create_notification_event(
            event_type=event_type,
            title=title,
            body=body,
            channel="telegram",
            recipient_scope="crm",
            recipient_admin_id=int(recipient["id"]),
            camp_id=camp_id,
            action_url=action_url,
            action_payload=action_payload,
            severity=severity,
            metadata=metadata or {},
        )


def _normalize_room_payload(raw_payload: dict) -> dict:
    return {
        "name": str(raw_payload.get("name") or "").strip(),
        "room_type": raw_payload.get("room_type"),
        "floors": int(raw_payload.get("floors") or 1),
        "floor": int(raw_payload.get("floor") or 1),
        "beds_single": int(raw_payload.get("beds_single") or 0),
        "beds_double": int(raw_payload.get("beds_double") or 0),
        "bath_type": raw_payload.get("bath_type"),
        "wc_type": raw_payload.get("wc_type"),
        "bbq_type": raw_payload.get("bbq_type"),
        "kitchen_type": raw_payload.get("kitchen_type"),
        "gazebo_type": raw_payload.get("gazebo_type"),
        "terrace_type": raw_payload.get("terrace_type"),
        "pool_type": raw_payload.get("pool_type"),
        "balcony_type": raw_payload.get("balcony_type"),
        "has_ac": bool(raw_payload.get("has_ac")),
        "price_adult": int(raw_payload.get("price_adult") or 0),
        "price_child": int(raw_payload.get("price_child") or 0),
        "price": int(raw_payload.get("price") or 0),
        "discount_pct": int(raw_payload.get("discount_pct") or 0),
        "discount_from_nights": int(raw_payload.get("discount_from_nights") or 0),
        "description": raw_payload.get("description"),
        "media": _normalize_media_payload(raw_payload.get("media") or [], max_images=5),
    }


def _normalize_shift_rule_payload(raw_payload: dict) -> dict:
    try:
        shift_date_value = date.fromisoformat(str(raw_payload.get("shift_date") or "").strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Некорректная дата смены") from exc
    ends_on_date_raw = str(raw_payload.get("ends_on_date") or "").strip()
    ends_on_date_value: date | None = None
    if ends_on_date_raw:
        try:
            ends_on_date_value = date.fromisoformat(ends_on_date_raw)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Некорректная дата окончания смены") from exc
        if ends_on_date_value < shift_date_value:
            raise HTTPException(status_code=400, detail="Дата окончания смены не может быть раньше даты начала")
    starts_at = str(raw_payload.get("starts_at") or "").strip()
    ends_at = str(raw_payload.get("ends_at") or "").strip()
    _parse_shift_time(starts_at)
    _parse_shift_time(ends_at)
    _, normalized_end_at, resolved_end_date = _resolve_shift_window(
        shift_date_value,
        starts_at,
        ends_at,
        ends_on_date_value,
    )
    return {
        "admin_id": int(raw_payload.get("admin_id") or 0),
        "shift_date": shift_date_value,
        "ends_on_date": resolved_end_date,
        "weekday": shift_date_value.weekday(),
        "starts_at": starts_at,
        "ends_at": normalized_end_at.strftime("%H:%M"),
        "is_night_shift": bool(raw_payload.get("is_night_shift")),
        "is_active": bool(raw_payload.get("is_active", True)),
        "comment": (raw_payload.get("comment") or "").strip() or None,
    }


def _prepare_change_request_payload(camp_id: int, admin: dict, operation: str, raw_payload: dict) -> dict:
    normalized_operation = (operation or "").strip()
    if normalized_operation == "shift_settings_update":
        _ensure_admin_shift_access(admin, camp_id)
        night_starts_at = str(raw_payload.get("night_starts_at") or "22:00").strip()
        _parse_shift_time(night_starts_at)
        before = admin_repo.get_camp_shift_settings(camp_id) or {
            "camp_id": camp_id,
            "time_zone": "Asia/Irkutsk",
            "booking_hold_hours": 4,
            "night_starts_at": "22:00",
            "night_release_after_shift_minutes": 60,
            "escalation_step_minutes": 15,
            "escalation_repeats_before_manager": 2,
        }
        after = {
            "time_zone": str(raw_payload.get("time_zone") or "Asia/Irkutsk"),
            "booking_hold_hours": int(raw_payload.get("booking_hold_hours") or 4),
            "night_starts_at": night_starts_at,
            "night_release_after_shift_minutes": int(raw_payload.get("night_release_after_shift_minutes") or 60),
            "escalation_step_minutes": int(raw_payload.get("escalation_step_minutes") or 15),
            "escalation_repeats_before_manager": int(raw_payload.get("escalation_repeats_before_manager") or 2),
        }
        return {
            "change_kind": "shift_schedule",
            "target_type": "shift_settings",
            "target_id": str(camp_id),
            "summary": "Изменение параметров смен и эскалаций",
            "payload": {"operation": normalized_operation, "before": before, "after": after},
        }

    if normalized_operation == "shift_rule_create":
        _ensure_admin_shift_access(admin, camp_id)
        after = _normalize_shift_rule_payload(raw_payload)
        staff = admin_repo.get_admin_staff_member(camp_id, after["admin_id"])
        if not staff:
            raise HTTPException(status_code=400, detail="Сотрудник не привязан к этой базе")
        return {
            "change_kind": "shift_schedule",
            "target_type": "shift_rule",
            "target_id": None,
            "summary": f"Добавление смены · {staff.get('display_name') or staff.get('email') or 'Сотрудник'} · {_shift_window_label(after['shift_date'], after.get('ends_on_date'), after['starts_at'], after['ends_at'])}",
            "payload": {"operation": normalized_operation, "after": after},
        }

    if normalized_operation == "shift_rule_update":
        _ensure_admin_shift_access(admin, camp_id)
        rule_id = int(raw_payload.get("rule_id") or 0)
        before = admin_repo.get_camp_shift_rule(camp_id, rule_id)
        if not before:
            raise HTTPException(status_code=404, detail="Правило смены не найдено")
        after = _normalize_shift_rule_payload(raw_payload.get("data") or {})
        staff = admin_repo.get_admin_staff_member(camp_id, after["admin_id"])
        if not staff:
            raise HTTPException(status_code=400, detail="Сотрудник не привязан к этой базе")
        return {
            "change_kind": "shift_schedule",
            "target_type": "shift_rule",
            "target_id": str(rule_id),
            "summary": f"Изменение смены · {staff.get('display_name') or staff.get('email') or 'Сотрудник'} · {_shift_window_label(after['shift_date'], after.get('ends_on_date'), after['starts_at'], after['ends_at'])}",
            "payload": {"operation": normalized_operation, "rule_id": rule_id, "before": before, "after": after},
        }

    if normalized_operation == "shift_rule_delete":
        _ensure_admin_shift_access(admin, camp_id)
        rule_id = int(raw_payload.get("rule_id") or 0)
        before = admin_repo.get_camp_shift_rule(camp_id, rule_id)
        if not before:
            raise HTTPException(status_code=404, detail="Правило смены не найдено")
        return {
            "change_kind": "shift_schedule",
            "target_type": "shift_rule",
            "target_id": str(rule_id),
            "summary": f"Удаление смены · {before.get('admin_name') or before.get('admin_email') or 'Сотрудник'} · {_shift_window_label(before.get('shift_date'), before.get('ends_on_date'), str(before.get('starts_at') or ''), str(before.get('ends_at') or '')) if isinstance(before.get('shift_date'), date) else _weekday_label(int(before.get('weekday') or 0))}",
            "payload": {"operation": normalized_operation, "rule_id": rule_id, "before": before},
        }

    if normalized_operation == "camp_profile_update":
        _ensure_admin_camp_access(admin, camp_id)
        before = admin_repo.get_admin_camp_profile(camp_id)
        if not before:
            raise HTTPException(status_code=404, detail="База не найдена")
        after = _camp_profile_payload_from_snapshot({"camp": raw_payload, "settings": raw_payload})
        return {
            "change_kind": "cancellation_policy",
            "target_type": "camp_profile",
            "target_id": str(camp_id),
            "summary": "Изменение правил отмены и параметров базы",
            "payload": {
                "operation": normalized_operation,
                "before": _camp_profile_payload_from_snapshot(before),
                "after": after,
            },
        }

    if normalized_operation == "room_create":
        _ensure_admin_camp_access(admin, camp_id)
        after = _normalize_room_payload(raw_payload)
        if not after["name"]:
            raise HTTPException(status_code=400, detail="Укажите название апартамента")
        return {
            "change_kind": "pricing",
            "target_type": "room",
            "target_id": None,
            "summary": f"Добавление тарифов апартамента «{after['name']}»",
            "payload": {"operation": normalized_operation, "after": after},
        }

    if normalized_operation == "room_update":
        _ensure_admin_camp_access(admin, camp_id)
        room_id = int(raw_payload.get("room_id") or 0)
        before = admin_repo.get_admin_room(camp_id, room_id)
        if not before:
            raise HTTPException(status_code=404, detail="Апартамент не найден")
        after = _normalize_room_payload(raw_payload.get("data") or {})
        if not after["name"]:
            raise HTTPException(status_code=400, detail="Укажите название апартамента")
        return {
            "change_kind": "pricing",
            "target_type": "room",
            "target_id": str(room_id),
            "summary": f"Изменение тарифов апартамента «{after['name']}»",
            "payload": {"operation": normalized_operation, "room_id": room_id, "before": before, "after": after},
        }

    raise HTTPException(status_code=400, detail="Неизвестная операция для согласования")


def _apply_change_request_payload(camp_id: int, payload: dict, actor_admin: dict) -> dict:
    operation = str(payload.get("operation") or "").strip()
    actor_admin_id = int(actor_admin.get("id") or 0)

    if operation == "shift_settings_update":
        admin_repo.save_camp_shift_settings(camp_id, payload.get("after") or {})
        return {
            "operation": operation,
            "target_id": str(camp_id),
            "before": payload.get("before"),
            "after": admin_repo.get_camp_shift_settings(camp_id),
        }

    if operation == "shift_rule_create":
        rule_id = admin_repo.create_camp_shift_rule(camp_id, payload.get("after") or {}, actor_admin_id)
        return {
            "operation": operation,
            "target_id": str(rule_id),
            "after": admin_repo.get_camp_shift_rule(camp_id, rule_id),
        }

    if operation == "shift_rule_update":
        rule_id = int(payload.get("rule_id") or 0)
        if not admin_repo.update_camp_shift_rule(camp_id, rule_id, payload.get("after") or {}):
            raise HTTPException(status_code=404, detail="Правило смены не найдено")
        return {
            "operation": operation,
            "target_id": str(rule_id),
            "before": payload.get("before"),
            "after": admin_repo.get_camp_shift_rule(camp_id, rule_id),
        }

    if operation == "shift_rule_delete":
        rule_id = int(payload.get("rule_id") or 0)
        if not admin_repo.delete_camp_shift_rule(camp_id, rule_id):
            raise HTTPException(status_code=404, detail="Правило смены не найдено")
        return {
            "operation": operation,
            "target_id": str(rule_id),
            "before": payload.get("before"),
            "after": None,
        }

    if operation == "camp_profile_update":
        admin_repo.save_admin_camp_profile(camp_id, {**(payload.get("after") or {}), "normalize_move": _normalize_move})
        return {
            "operation": operation,
            "target_id": str(camp_id),
            "before": payload.get("before"),
            "after": admin_repo.get_admin_camp_profile(camp_id),
        }

    if operation == "room_create":
        room_id = admin_repo.create_admin_room(camp_id, {**(payload.get("after") or {}), "normalize_move": _normalize_move})
        return {
            "operation": operation,
            "target_id": str(room_id),
            "after": admin_repo.get_admin_room(camp_id, room_id),
        }

    if operation == "room_update":
        room_id = int(payload.get("room_id") or 0)
        if not admin_repo.update_admin_room(camp_id, room_id, {**(payload.get("after") or {}), "normalize_move": _normalize_move}):
            raise HTTPException(status_code=404, detail="Апартамент не найден")
        return {
            "operation": operation,
            "target_id": str(room_id),
            "before": payload.get("before"),
            "after": admin_repo.get_admin_room(camp_id, room_id),
        }

    raise HTTPException(status_code=400, detail="Операция не поддерживает применение")


def _rollback_change_request_payload(camp_id: int, request_item: dict, actor_admin: dict) -> dict:
    payload = request_item.get("payload") or {}
    applied_snapshot = request_item.get("applied_snapshot") or {}
    operation = str(payload.get("operation") or "").strip()
    actor_admin_id = int(actor_admin.get("id") or 0)

    if operation == "shift_settings_update":
        admin_repo.save_camp_shift_settings(camp_id, payload.get("before") or {})
        return {"operation": operation, "rolled_back_to": admin_repo.get_camp_shift_settings(camp_id)}

    if operation == "shift_rule_create":
        target_id = int(applied_snapshot.get("target_id") or request_item.get("target_id") or 0)
        if target_id and not admin_repo.delete_camp_shift_rule(camp_id, target_id):
            raise HTTPException(status_code=409, detail="Не удалось откатить правило смены")
        return {"operation": operation, "rolled_back_target_id": str(target_id)}

    if operation == "shift_rule_update":
        rule_id = int(applied_snapshot.get("target_id") or payload.get("rule_id") or request_item.get("target_id") or 0)
        if not admin_repo.update_camp_shift_rule(camp_id, rule_id, payload.get("before") or {}):
            raise HTTPException(status_code=409, detail="Не удалось откатить правило смены")
        return {"operation": operation, "rolled_back_to": admin_repo.get_camp_shift_rule(camp_id, rule_id)}

    if operation == "shift_rule_delete":
        restored_rule_id = admin_repo.create_camp_shift_rule(camp_id, payload.get("before") or {}, actor_admin_id)
        return {"operation": operation, "restored_rule_id": str(restored_rule_id), "rolled_back_to": admin_repo.get_camp_shift_rule(camp_id, restored_rule_id)}

    if operation == "camp_profile_update":
        admin_repo.save_admin_camp_profile(camp_id, {**(payload.get("before") or {}), "normalize_move": _normalize_move})
        return {"operation": operation, "rolled_back_to": admin_repo.get_admin_camp_profile(camp_id)}

    if operation == "room_create":
        room_id = int(applied_snapshot.get("target_id") or request_item.get("target_id") or 0)
        if admin_repo.room_has_any_booking(camp_id, room_id):
            raise HTTPException(status_code=409, detail="Нельзя откатить создание апартамента: по нему уже есть брони")
        if not admin_repo.delete_admin_room(camp_id, room_id):
            raise HTTPException(status_code=409, detail="Не удалось откатить создание апартамента")
        return {"operation": operation, "rolled_back_target_id": str(room_id)}

    if operation == "room_update":
        room_id = int(applied_snapshot.get("target_id") or payload.get("room_id") or request_item.get("target_id") or 0)
        if not admin_repo.update_admin_room(camp_id, room_id, {**_room_payload_from_snapshot(payload.get("before") or {}), "normalize_move": _normalize_move}):
            raise HTTPException(status_code=409, detail="Не удалось откатить изменение апартамента")
        return {"operation": operation, "rolled_back_to": admin_repo.get_admin_room(camp_id, room_id)}

    raise HTTPException(status_code=400, detail="Эту операцию пока нельзя откатить автоматически")


def _notify_change_request_reviewers(camp_id: int, actor_admin: dict, request_item: dict) -> None:
    permission_key = _change_kind_permission_key(str(request_item.get("change_kind") or ""))
    action_url = f"/approvals?request_id={request_item.get('id')}"
    metadata = {
        "change_request_id": int(request_item["id"]),
        "change_request_status": str(request_item.get("status") or ""),
        "change_kind": str(request_item.get("change_kind") or ""),
    }
    seen_ids: set[int] = set()
    for reviewer in _reviewer_candidates(camp_id, permission_key):
        reviewer_id = int(reviewer["id"])
        if reviewer_id in seen_ids:
            continue
        seen_ids.add(reviewer_id)
        _publish_crm_event(
            camp_id=camp_id,
            admin=actor_admin,
            event_type="change_request_pending_review",
            title="Изменение ждёт подтверждения",
            body=f"{request_item.get('summary') or 'Изменение по базе'}.\n\nОткройте согласование, чтобы подтвердить, отклонить или запросить уточнение.",
            severity="warning",
            action_url=action_url,
            action_payload={"change_request_id": int(request_item["id"])},
            recipient_admin_id=reviewer_id,
            metadata=metadata,
        )


def _notify_change_request_initiator(camp_id: int, request_item: dict, *, title: str, body: str, severity: str = "info") -> None:
    initiator_id = int(request_item.get("created_by_admin_id") or 0)
    if not initiator_id:
        return
    _publish_targeted_staff_event(
        camp_id=camp_id,
        recipient_admin_id=initiator_id,
        event_type="change_request_feedback",
        title=title,
        body=body,
        action_url=f"/approvals?request_id={request_item.get('id')}",
        action_payload={"change_request_id": int(request_item["id"])},
        severity=severity,
        metadata={
            "change_request_id": int(request_item["id"]),
            "change_request_status": str(request_item.get("status") or ""),
            "change_kind": str(request_item.get("change_kind") or ""),
        },
    )


def process_change_request_decision(request_item: dict, actor_admin: dict, *, action: str, comment: Optional[str] = None) -> dict:
    normalized_action = (action or "").strip().lower()
    camp_id = int(request_item.get("camp_id") or 0)
    if request_item.get("status") == "rolled_back":
        raise HTTPException(status_code=409, detail="Это изменение уже откатили")

    if normalized_action == "approve":
        if str(request_item.get("status") or "") != "pending_review":
            raise HTTPException(status_code=409, detail="Подтверждать можно только изменения со статусом «На подтверждении»")
        applied_snapshot = _apply_change_request_payload(camp_id, request_item.get("payload") or {}, actor_admin)
        _emit_superadmin_media_notifications_from_snapshot(camp_id, actor_admin, applied_snapshot)
        admin_repo.update_change_request(
            int(request_item["id"]),
            status="approved",
            reviewer_admin_id=int(actor_admin["id"]),
            reviewer_comment=(comment or "").strip() or "Подтверждено управляющим",
            applied_snapshot=applied_snapshot,
        )
        updated = admin_repo.get_change_request(int(request_item["id"]), [camp_id])
        log_crm_audit_event(
            actor_type="camp_admin",
            actor_id=actor_admin.get("id"),
            actor_display=actor_admin.get("display_name"),
            camp_id=camp_id,
            target_type="change_request",
            target_id=request_item["id"],
            action_type="change_request_approve",
            action_label="Подтвердил изменение",
            comment=(comment or "").strip() or "Подтверждено управляющим",
            is_sensitive=True,
            was_auto_applied=False,
        )
        _notify_change_request_initiator(
            camp_id,
            updated or request_item,
            title="Изменение подтверждено",
            body=f"{request_item.get('summary') or 'Изменение'} подтверждено и применено.",
            severity="info",
        )
        return updated or request_item

    if normalized_action == "reject":
        if str(request_item.get("status") or "") != "pending_review":
            raise HTTPException(status_code=409, detail="Отклонять можно только изменения со статусом «На подтверждении»")
        admin_repo.update_change_request(
            int(request_item["id"]),
            status="rejected",
            reviewer_admin_id=int(actor_admin["id"]),
            reviewer_comment=(comment or "").strip() or "Изменение отклонено",
        )
        updated = admin_repo.get_change_request(int(request_item["id"]), [camp_id])
        log_crm_audit_event(
            actor_type="camp_admin",
            actor_id=actor_admin.get("id"),
            actor_display=actor_admin.get("display_name"),
            camp_id=camp_id,
            target_type="change_request",
            target_id=request_item["id"],
            action_type="change_request_reject",
            action_label="Отклонил изменение",
            comment=(comment or "").strip() or "Изменение отклонено",
            is_sensitive=True,
            was_auto_applied=False,
        )
        _notify_change_request_initiator(
            camp_id,
            updated or request_item,
            title="Изменение отклонено",
            body=f"{request_item.get('summary') or 'Изменение'} отклонено. Проверьте комментарий управляющего и при необходимости отправьте правки заново.",
            severity="warning",
        )
        return updated or request_item

    if normalized_action == "clarify":
        if str(request_item.get("status") or "") != "pending_review":
            raise HTTPException(status_code=409, detail="Уточнение можно запросить только для ожидающего изменения")
        reviewer_comment = (comment or "").strip() or "Нужно уточнение. Проверьте детали изменения и отправьте новую версию."
        admin_repo.update_change_request(
            int(request_item["id"]),
            status="needs_clarification",
            reviewer_admin_id=int(actor_admin["id"]),
            reviewer_comment=reviewer_comment,
        )
        updated = admin_repo.get_change_request(int(request_item["id"]), [camp_id])
        log_crm_audit_event(
            actor_type="camp_admin",
            actor_id=actor_admin.get("id"),
            actor_display=actor_admin.get("display_name"),
            camp_id=camp_id,
            target_type="change_request",
            target_id=request_item["id"],
            action_type="change_request_clarify",
            action_label="Запросил уточнение",
            comment=reviewer_comment,
            is_sensitive=True,
            was_auto_applied=False,
        )
        _notify_change_request_initiator(
            camp_id,
            updated or request_item,
            title="Нужно уточнение по изменению",
            body=reviewer_comment,
            severity="warning",
        )
        return updated or request_item

    if normalized_action == "rollback":
        if str(request_item.get("status") or "") not in {"approved", "applied_with_responsibility"}:
            raise HTTPException(status_code=409, detail="Откат доступен только для уже применённых изменений")
        rollback_snapshot = _rollback_change_request_payload(camp_id, request_item, actor_admin)
        admin_repo.update_change_request(
            int(request_item["id"]),
            status="rolled_back",
            reviewer_admin_id=int(actor_admin["id"]),
            reviewer_comment=(comment or "").strip() or "Откат подтверждён управляющим",
            applied_snapshot={
                **(request_item.get("applied_snapshot") or {}),
                "rollback": rollback_snapshot,
            },
        )
        updated = admin_repo.get_change_request(int(request_item["id"]), [camp_id])
        log_crm_audit_event(
            actor_type="camp_admin",
            actor_id=actor_admin.get("id"),
            actor_display=actor_admin.get("display_name"),
            camp_id=camp_id,
            target_type="change_request",
            target_id=request_item["id"],
            action_type="change_request_rollback",
            action_label="Выполнил откат изменения",
            comment=(comment or "").strip() or "Откат подтверждён управляющим",
            is_sensitive=True,
            was_auto_applied=False,
        )
        _notify_change_request_initiator(
            camp_id,
            updated or request_item,
            title="Изменение откатили",
            body=f"{request_item.get('summary') or 'Изменение'} откатили. Проверьте текущую версию данных в CRM.",
            severity="warning",
        )
        return updated or request_item

    raise HTTPException(status_code=400, detail="Неизвестное действие по согласованию")


def get_accessible_change_request_for_admin(admin: dict, request_id: int) -> dict:
    camp_ids = _get_admin_camp_ids(admin["id"])
    request_item = admin_repo.get_change_request(request_id, camp_ids)
    if not request_item:
        raise HTTPException(status_code=404, detail="Согласование не найдено")
    return request_item


def handle_change_request_action_for_admin(admin: dict, request_id: int, *, action: str, comment: Optional[str] = None) -> dict:
    request_item = get_accessible_change_request_for_admin(admin, request_id)
    _ensure_change_request_review_access(admin, request_item)
    return process_change_request_decision(request_item, admin, action=action, comment=comment)


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


def _date_label(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _resolve_shift_window(
    anchor_day: date,
    starts_at_value,
    ends_at_value,
    ends_on_date_value: date | None = None,
) -> tuple[datetime, datetime, date]:
    start_time = starts_at_value if isinstance(starts_at_value, time) else _parse_shift_time(str(starts_at_value))
    end_time = ends_at_value if isinstance(ends_at_value, time) else _parse_shift_time(str(ends_at_value))
    starts_at = datetime.combine(anchor_day, start_time)
    end_day = ends_on_date_value if isinstance(ends_on_date_value, date) else anchor_day
    ends_at = datetime.combine(end_day, end_time)
    if ends_at <= starts_at:
        ends_at += timedelta(days=1)
    return starts_at, ends_at, ends_at.date()


def _shift_window_label(start_date: date, end_date: date | None, starts_at: str, ends_at: str) -> str:
    normalized_end_date = end_date or start_date
    if normalized_end_date == start_date:
        return f"{_date_label(start_date)} · {str(starts_at)[:5]} → {str(ends_at)[:5]}"
    return f"{_date_label(start_date)} {str(starts_at)[:5]} → {_date_label(normalized_end_date)} {str(ends_at)[:5]}"


def _serialize_shift_occurrence(rule: dict, starts_at: datetime, ends_at: datetime, *, timezone_name: str) -> dict:
    shift_date = rule.get("shift_date")
    ends_on_date = rule.get("ends_on_date")
    return {
        "rule_id": rule.get("id"),
        "admin_id": rule.get("admin_id"),
        "admin_name": rule.get("admin_name") or rule.get("admin_email") or f"Сотрудник #{rule.get('admin_id')}",
        "shift_date": shift_date.isoformat() if isinstance(shift_date, date) else shift_date,
        "ends_on_date": ends_on_date.isoformat() if isinstance(ends_on_date, date) else ends_on_date,
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

    for rule in rules:
        if not rule.get("is_active"):
            continue
        anchor_day = rule.get("shift_date")
        if not isinstance(anchor_day, date):
            continue
        ends_on_date = rule.get("ends_on_date")
        ends_on_date_value = ends_on_date if isinstance(ends_on_date, date) else None
        starts_at_naive, ends_at_naive, resolved_end_date = _resolve_shift_window(
            anchor_day,
            rule.get("starts_at"),
            rule.get("ends_at"),
            ends_on_date_value,
        )
        rule["ends_on_date"] = resolved_end_date
        starts_at = starts_at_naive.replace(tzinfo=zone)
        ends_at = ends_at_naive.replace(tzinfo=zone)
        occurrence = _serialize_shift_occurrence(rule, starts_at, ends_at, timezone_name=timezone_name)
        if starts_at <= now < ends_at:
            active_rules.append(occurrence)
        if starts_at > now:
            upcoming_windows.append(occurrence)
            if next_occurrence is None or starts_at < datetime.fromisoformat(next_occurrence["starts_at"]):
                next_occurrence = occurrence

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


def api_admin_change_requests(
    camp_id: Optional[int] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    change_kind: Optional[str] = None,
    limit: int = 200,
    admin: dict = Depends(get_current_admin),
):
    camp_ids = _get_admin_camp_ids(admin["id"])
    if camp_id and camp_id not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")

    normalized_status = (status or "").strip().lower() or None
    if normalized_status and normalized_status not in crm_domain.CHANGE_REQUEST_STATUS_KEYS:
        raise HTTPException(status_code=400, detail="Некорректный статус согласования")

    normalized_kind = (change_kind or "").strip().lower() or None
    if normalized_kind and normalized_kind not in crm_domain.SENSITIVE_CHANGE_KINDS:
        raise HTTPException(status_code=400, detail="Некорректный тип изменения")

    return {
        "items": admin_repo.list_change_requests(
            camp_ids,
            camp_id=camp_id,
            search=search,
            status=normalized_status,
            change_kind=normalized_kind,
            limit=limit,
        ),
        "status_labels": crm_domain.CHANGE_REQUEST_STATUS_LABELS,
        "change_kind_labels": crm_domain.SENSITIVE_CHANGE_LABELS,
    }


def api_admin_create_change_request(
    camp_id: int,
    payload: AdminChangeRequestCreateRequest,
    admin: dict = Depends(get_current_admin),
):
    _ensure_admin_camp_access(admin, camp_id)
    normalized_apply_mode = (payload.apply_mode or "").strip().lower()
    if normalized_apply_mode not in {"pending_review", "apply_with_responsibility"}:
        raise HTTPException(status_code=400, detail="Некорректный режим применения изменения")

    prepared = _prepare_change_request_payload(camp_id, admin, payload.operation, payload.payload or {})
    reviewer_permission = _change_kind_permission_key(prepared["change_kind"])
    reviewer_ids = [int(item["id"]) for item in _reviewer_candidates(camp_id, reviewer_permission)]
    reviewer_id = reviewer_ids[0] if reviewer_ids else None

    status_value = "pending_review" if normalized_apply_mode == "pending_review" else "applied_with_responsibility"
    applied_snapshot = None
    if normalized_apply_mode == "apply_with_responsibility":
        applied_snapshot = _apply_change_request_payload(camp_id, prepared["payload"], admin)
        _emit_superadmin_media_notifications_from_snapshot(camp_id, admin, applied_snapshot)

    request_id = admin_repo.create_change_request(
        camp_id,
        created_by_admin_id=int(admin["id"]),
        reviewer_admin_id=reviewer_id,
        target_type=prepared["target_type"],
        target_id=prepared["target_id"],
        change_kind=prepared["change_kind"],
        status=status_value,
        summary=prepared["summary"],
        request_comment=(payload.request_comment or "").strip() or None,
        payload=prepared["payload"],
        applied_snapshot=applied_snapshot,
    )
    created = admin_repo.get_change_request(request_id, [camp_id])
    if not created:
        raise HTTPException(status_code=500, detail="Не удалось сохранить согласование")

    log_crm_audit_event(
        actor_type="camp_admin",
        actor_id=admin.get("id"),
        actor_display=admin.get("display_name"),
        camp_id=camp_id,
        target_type="change_request",
        target_id=request_id,
        action_type="change_request_create",
        action_label="Создал согласование изменения" if normalized_apply_mode == "pending_review" else "Применил изменение под ответственность",
        comment=(payload.request_comment or "").strip() or None,
        new_value=created,
        is_sensitive=True,
        was_auto_applied=normalized_apply_mode == "apply_with_responsibility",
    )

    if normalized_apply_mode == "pending_review":
        _notify_change_request_reviewers(camp_id, admin, created)
    else:
        _publish_crm_event(
            camp_id=camp_id,
            admin=admin,
            event_type="change_request_applied",
            title="Изменение применено под ответственность",
            body=f"{created.get('summary') or 'Изменение по базе'}.\n\nУправляющий может открыть согласование и при необходимости подтвердить откат.",
            severity="warning",
            action_url=f"/approvals?request_id={request_id}",
            action_payload={"change_request_id": request_id},
            metadata={
                "change_request_id": request_id,
                "change_request_status": created.get("status"),
                "change_kind": created.get("change_kind"),
            },
        )

    return {"ok": True, "item": created}


def api_admin_change_request_action(
    request_id: int,
    payload: AdminChangeRequestDecisionRequest,
    admin: dict = Depends(get_current_admin),
):
    updated = handle_change_request_action_for_admin(
        admin,
        request_id,
        action=payload.action,
        comment=payload.comment,
    )
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
    guest_email = _normalize_guest_email(str(payload.guest_email) if payload.guest_email is not None else None)
    comment = (payload.comment or "").strip() or None
    linked_user, shadow_user, normalized_guest_phone = _resolve_booking_user_link(
        guest_name=guest_name,
        guest_phone=guest_phone,
        guest_email=guest_email,
    )
    user_id = int(linked_user["id"]) if linked_user and linked_user.get("id") is not None else None
    if normalized_guest_phone:
        guest_phone = normalized_guest_phone

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
            user_id,
        )
    except Exception as exc:
        _raise_booking_write_http_error(exc)
    booking = admin_repo.get_booking_by_id(booking_id) or {"id": booking_id, "camp_id": payload.camp_id, "room_id": room_id}
    guest_label = _booking_guest_label_from_row(booking)
    sync_note = _booking_customer_sync_note(booking)
    event_lines = [
        f"{guest_label} · {payload.check_in.isoformat()} → {payload.check_out.isoformat()} · статус: {_booking_status_label(booking_status)}."
    ]
    if sync_note:
        event_lines.append(sync_note)
    _publish_crm_event(
        camp_id=payload.camp_id,
        admin=admin,
        event_type="booking_created",
        title="В CRM создана новая бронь",
        body="\n".join(event_lines),
        severity="warning",
        action_url="/bookings",
        action_payload={"booking_id": booking_id, "camp_id": payload.camp_id},
        metadata={
            "booking_id": booking_id,
            "room_id": room_id,
            "user_id": user_id,
            "shadow_profile_created": bool(shadow_user),
        },
    )
    log_crm_audit_event(
        actor_type="admin",
        actor_id=int(admin["id"]),
        actor_display=admin.get("display_name"),
        camp_id=payload.camp_id,
        target_type="booking",
        target_id=booking_id,
        action_type="booking_create",
        action_label="Создал бронь",
        new_value={
            "status": booking_status,
            "payment_status": payment_status,
            "payment_required": payment_required,
            "guest_name": guest_name,
            "guest_phone": guest_phone,
            "guest_email": guest_email,
            "user_id": user_id,
        },
        comment=comment,
        metadata={"room_id": room_id, "shadow_profile_created": bool(shadow_user)},
    )
    if user_id:
        log_user_event(
            user_id,
            "booking_admin_created",
            {
                "booking_id": booking_id,
                "camp_id": payload.camp_id,
                "room_id": room_id,
                "status": booking_status,
                "payment_status": payment_status,
                "payment_required": payment_required,
                "shadow_profile_created": bool(shadow_user),
            },
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

    new_status = booking_domain.normalize_admin_booking_status(payload.status) if payload.status is not None else None
    booking = admin_repo.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="not found")
    if booking["camp_id"] not in camp_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к выбранной базе")
    payment_status = booking_domain.normalize_admin_payment_status(payload.payment_status, allow_none=True)
    effective_payment_status = payment_status if payment_status is not None else booking.get("payment_status")

    payment_required = booking_domain.coerce_payment_required(
        effective_payment_status,
        payload.payment_required,
        default=None,
    )
    next_comment = ((payload.comment or "").strip() or None) if payload.comment is not None else None
    next_status = new_status or booking.get("status")
    next_payment_status = payment_status or booking.get("payment_status")
    next_payment_required = payment_required if payment_required is not None else bool(booking.get("payment_required"))

    update_payload = {}
    if new_status != booking.get("status"):
        update_payload["status"] = new_status
    if payment_status != booking.get("payment_status"):
        update_payload["payment_status"] = payment_status
    if payment_required != booking.get("payment_required"):
        update_payload["payment_required"] = payment_required
    if next_comment != booking.get("comment"):
        update_payload["comment"] = next_comment

    try:
        changed = admin_repo.update_admin_booking(
            booking_id,
            **update_payload,
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
                "status": next_status,
                "payment_status": next_payment_status,
                "payment_required": next_payment_required,
                "admin_id": admin.get("id"),
                "comment": next_comment if next_comment is not None else booking.get("comment"),
            },
        )
    log_crm_audit_event(
        actor_type="admin",
        actor_id=int(admin["id"]),
        actor_display=admin.get("display_name"),
        camp_id=booking.get("camp_id"),
        target_type="booking",
        target_id=booking_id,
        action_type="booking_update",
        action_label="Обновил бронь",
        old_value={
            "status": booking.get("status"),
            "payment_status": booking.get("payment_status"),
            "payment_required": booking.get("payment_required"),
            "comment": booking.get("comment"),
        },
        new_value={
            "status": next_status,
            "payment_status": next_payment_status,
            "payment_required": next_payment_required,
            "comment": next_comment if next_comment is not None else booking.get("comment"),
        },
        comment=next_comment if next_comment is not None else None,
    )
    body_lines = [
        f"Статус: {_booking_status_label(next_status)}.",
        f"Оплата: {_payment_status_label(next_payment_status)}.",
    ]
    if next_payment_required and next_payment_status in {"unpaid", "awaiting_prepayment", "partially_paid", "failed"}:
        body_lines.append("По брони требуется действие по оплате.")
    sync_note = _booking_customer_sync_note(booking)
    if sync_note:
        body_lines.append(sync_note)
    _publish_crm_event(
        camp_id=booking.get("camp_id"),
        admin=admin,
        event_type="booking_updated",
        title=f"Бронь #{booking_id} обновлена",
        body=" ".join(body_lines),
        severity=_booking_event_severity(next_status, next_payment_status),
        action_url="/bookings",
        action_payload={"booking_id": booking_id, "camp_id": booking.get("camp_id")},
        metadata={"booking_id": booking_id, "user_id": booking.get("user_id")},
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
        "night_starts_at": "22:00",
        "night_release_after_shift_minutes": 60,
        "escalation_step_minutes": 15,
        "escalation_repeats_before_manager": 2,
    }
    rules = admin_repo.list_camp_shift_rules(camp_id)
    for rule in rules:
        shift_date = rule.get("shift_date")
        if not isinstance(shift_date, date):
            continue
        ends_on_date = rule.get("ends_on_date")
        starts_at_value, ends_at_value, resolved_end_date = _resolve_shift_window(
            shift_date,
            rule.get("starts_at"),
            rule.get("ends_at"),
            ends_on_date if isinstance(ends_on_date, date) else None,
        )
        rule["shift_date"] = shift_date
        rule["starts_at"] = starts_at_value.strftime("%H:%M")
        rule["ends_at"] = ends_at_value.strftime("%H:%M")
        rule["ends_on_date"] = resolved_end_date
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
    _parse_shift_time(payload.night_starts_at)
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
            f"время начала ночи, ночной резерв и интервалы эскалации."
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
    payload_data = _normalize_shift_rule_payload(payload.model_dump())
    if not admin_repo.get_admin_staff_member(camp_id, int(payload_data["admin_id"])):
        raise HTTPException(status_code=400, detail="Сотрудник не привязан к этой базе")
    rule_id = admin_repo.create_camp_shift_rule(camp_id, payload_data, int(admin["id"]))
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
        body=f"{rule.get('admin_name') or 'Сотрудник'} · {_shift_window_label(payload_data['shift_date'], payload_data.get('ends_on_date'), payload_data['starts_at'], payload_data['ends_at'])}.",
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
    payload_data = _normalize_shift_rule_payload(payload.model_dump())
    if not admin_repo.get_admin_staff_member(camp_id, int(payload_data["admin_id"])):
        raise HTTPException(status_code=400, detail="Сотрудник не привязан к этой базе")
    changed = admin_repo.update_camp_shift_rule(camp_id, rule_id, payload_data, int(admin["id"]))
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
        body=f"{after.get('admin_name') or 'Сотрудник'} · {_shift_window_label(payload_data['shift_date'], payload_data.get('ends_on_date'), payload_data['starts_at'], payload_data['ends_at'])}.",
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
            f"{_shift_window_label(before.get('shift_date'), before.get('ends_on_date'), str(before.get('starts_at') or ''), str(before.get('ends_at') or '')) if isinstance(before.get('shift_date'), date) else _weekday_label(before.get('weekday') or 0)}."
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
    admin_repo.save_admin_camp_profile(camp_id, {**payload.model_dump(), "normalize_move": _normalize_move})
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
    _notify_superadmins_about_media_review(
        camp_id=camp_id,
        camp_name=(after.get("camp") or {}).get("name") or f"База #{camp_id}",
        actor_admin=admin,
        pending_items=_extract_camp_pending_media_notifications(before, after),
        entity_type="camp",
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
    login = _normalize_admin_login_or_400(payload.login)
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
                "email": login,
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
        body=f"{staff.get('display_name') or staff.get('login') or staff.get('email') or 'Новый сотрудник'} · роль: {staff.get('role_label') or 'Не указана'}.",
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
                "email": _normalize_admin_login_or_400(payload.login),
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
            raise HTTPException(status_code=409, detail="Учётка с таким логином уже существует") from exc
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
        body=f"{after.get('display_name') or after.get('login') or after.get('email') or 'Сотрудник'} · роль: {after.get('role_label') or 'Не указана'}.",
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
    deep_link = f"https://t.me/{STAFF_BOT_USERNAME}?start={code}" if STAFF_BOT_USERNAME else None
    return {"ok": True, "code": code, "command": f"/start {code}", "deep_link": deep_link}


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
    room_id = admin_repo.create_admin_room(camp_id, {**payload.model_dump(), "normalize_move": _normalize_move})
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
    room_payload = room or {}
    _notify_superadmins_about_media_review(
        camp_id=camp_id,
        camp_name=(admin_repo.get_admin_camp_profile(camp_id) or {}).get("camp", {}).get("name") or f"База #{camp_id}",
        actor_admin=admin,
        pending_items=_extract_room_pending_media_notifications(None, room_payload),
        entity_type="room",
        room_id=room_id,
        room_name=room_payload.get("name") or f"Апартамент #{room_id}",
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
    changed = admin_repo.update_admin_room(camp_id, room_id, {**payload.model_dump(), "normalize_move": _normalize_move})
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
    _notify_superadmins_about_media_review(
        camp_id=camp_id,
        camp_name=(admin_repo.get_admin_camp_profile(camp_id) or {}).get("camp", {}).get("name") or f"База #{camp_id}",
        actor_admin=admin,
        pending_items=_extract_room_pending_media_notifications(before, after),
        entity_type="room",
        room_id=room_id,
        room_name=after.get("name") or f"Апартамент #{room_id}",
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
