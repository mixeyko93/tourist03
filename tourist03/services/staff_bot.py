from datetime import datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from tourist03.config import CRM_BASE_URL, STAFF_BOT_USERNAME, SUPERADMIN_BASE_URL, logger
from tourist03.repositories import admin as admin_repo
from tourist03.repositories import notifications as notification_repo
from tourist03.security import (
    _get_admin_camp_ids,
    create_notification_event,
    link_admin_telegram_account,
    link_superadmin_telegram_account,
    log_crm_audit_event,
)
from tourist03.services import superadmin as superadmin_service


DEFAULT_SHIFT_SETTINGS = {
    "time_zone": "Asia/Irkutsk",
    "booking_hold_hours": 4,
    "night_release_after_shift_minutes": 60,
    "escalation_step_minutes": 15,
    "escalation_repeats_before_manager": 2,
}

EVENT_STATUS_LABELS = {
    "new": "Новое",
    "viewed": "Просмотрено",
    "in_progress": "В работе",
    "closed": "Закрыто",
}


def _parse_shift_time(value) -> time:
    if isinstance(value, time):
        return value
    raw = str(value or "").strip()
    hour_str, minute_str = raw.split(":", 1)
    return time(hour=int(hour_str), minute=int(minute_str))


def _resolve_shift_window(anchor_day, starts_at_value, ends_at_value) -> tuple[datetime, datetime]:
    start_time = _parse_shift_time(starts_at_value)
    end_time = _parse_shift_time(ends_at_value)
    starts_at = datetime.combine(anchor_day, start_time)
    ends_at = datetime.combine(anchor_day, end_time)
    if ends_at <= starts_at:
        ends_at += timedelta(days=1)
    return starts_at, ends_at


def _zone_for_camp(camp_id: int) -> tuple[str, ZoneInfo]:
    settings = admin_repo.get_camp_shift_settings(camp_id) or DEFAULT_SHIFT_SETTINGS
    timezone_name = str(settings.get("time_zone") or DEFAULT_SHIFT_SETTINGS["time_zone"])
    try:
        zone = ZoneInfo(timezone_name)
    except Exception:
        timezone_name = DEFAULT_SHIFT_SETTINGS["time_zone"]
        zone = ZoneInfo(timezone_name)
    return timezone_name, zone


def _as_local(dt_value: datetime, zone: ZoneInfo) -> datetime:
    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=timezone.utc).astimezone(zone)
    return dt_value.astimezone(zone)


def _rule_is_active_at(rule: dict, moment_local: datetime) -> bool:
    naive_moment = moment_local.replace(tzinfo=None)
    for day_offset in (0, -1):
        anchor_day = (moment_local + timedelta(days=day_offset)).date()
        if int(rule.get("weekday") or 0) != anchor_day.weekday():
            continue
        starts_at, ends_at = _resolve_shift_window(anchor_day, rule.get("starts_at"), rule.get("ends_at"))
        if starts_at <= naive_moment < ends_at:
            return True
    return False


def _active_shift_admin_ids(rules: list[dict], moment_local: datetime) -> list[int]:
    admin_ids: list[int] = []
    seen: set[int] = set()
    for rule in rules:
        if not bool(rule.get("is_active")):
            continue
        if not _rule_is_active_at(rule, moment_local):
            continue
        admin_id = int(rule.get("admin_id") or 0)
        if admin_id and admin_id not in seen:
            seen.add(admin_id)
            admin_ids.append(admin_id)
    return admin_ids


def _next_shift_start(rules: list[dict], moment_local: datetime) -> Optional[datetime]:
    naive_moment = moment_local.replace(tzinfo=None)
    next_value: Optional[datetime] = None
    for offset in range(0, 14):
        anchor_day = (moment_local + timedelta(days=offset)).date()
        weekday_value = anchor_day.weekday()
        for rule in rules:
            if not bool(rule.get("is_active")):
                continue
            if int(rule.get("weekday") or 0) != weekday_value:
                continue
            starts_at, _ = _resolve_shift_window(anchor_day, rule.get("starts_at"), rule.get("ends_at"))
            if starts_at <= naive_moment:
                continue
            if next_value is None or starts_at < next_value:
                next_value = starts_at
    if next_value is None:
        return None
    return next_value.replace(tzinfo=moment_local.tzinfo)


def _booking_dispatch_start(created_local: datetime, rules: list[dict]) -> datetime:
    if _active_shift_admin_ids(rules, created_local):
        return created_local
    next_shift = _next_shift_start(rules, created_local)
    if next_shift:
        return next_shift
    return created_local


def _booking_guest_label(booking: dict) -> str:
    return (
        (booking.get("guest_name") or "").strip()
        or (booking.get("user_name") or "").strip()
        or (booking.get("guest_phone") or "").strip()
        or (booking.get("user_phone") or "").strip()
        or f"Бронь #{booking.get('id')}"
    )


def _booking_escalation_title(booking: dict, attempt_no: int) -> str:
    if attempt_no <= 1:
        return "Новая заявка ждёт подтверждения"
    return f"Заявка без ответа · напоминание №{attempt_no}"


def _booking_escalation_body(booking: dict, *, attempt_no: int, waiting_minutes: int, escalate_to_manager: bool) -> str:
    room_name = booking.get("room_name") or "Без назначенного апартамента"
    extra = "Управляющий тоже подключён к оповещению." if escalate_to_manager else "Сигнал пока идёт только активной смене."
    return (
        f"{_booking_guest_label(booking)}\n"
        f"База: {booking.get('camp_name') or 'Не указана'}\n"
        f"Апартамент: {room_name}\n"
        f"Даты: {booking.get('check_in')} → {booking.get('check_out')}\n"
        f"Гостей: {booking.get('guests_count') or 1}\n"
        f"Ожидание без ответа: {waiting_minutes} мин.\n"
        f"{extra}"
    )


def _event_url(action_url: Optional[str], *, recipient_scope: Optional[str] = None) -> Optional[str]:
    normalized = (action_url or "").strip()
    if not normalized:
        return None
    if recipient_scope == "superadmin" or normalized.startswith("/admin"):
        base = (SUPERADMIN_BASE_URL or "https://superadmin.turist03.ru").rstrip("/")
    else:
        base = (CRM_BASE_URL or "https://crm.turist03.ru").rstrip("/")
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return normalized
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return f"{base}{normalized}"


def link_staff_account_by_code(code: str, *, telegram_user_id: int, telegram_chat_id: int, telegram_username: Optional[str] = None):
    linked = link_admin_telegram_account(
        code,
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        telegram_username=telegram_username,
    )
    if not linked:
        return None

    camp_ids = _get_admin_camp_ids(int(linked["id"]))
    for camp_id in camp_ids:
        log_crm_audit_event(
            actor_type="staff_bot",
            actor_id=int(linked["id"]),
            actor_display=linked.get("display_name") or linked.get("email"),
            camp_id=camp_id,
            target_type="staff_account",
            target_id=linked["id"],
            action_type="staff_telegram_link_complete",
            action_label="Подключил бот уведомлений CRM",
            comment=f"Telegram @{telegram_username}" if telegram_username else "Подключение через код",
            was_auto_applied=True,
        )
        create_notification_event(
            event_type="staff_telegram_linked",
            title="Сотрудник подключил бот уведомлений CRM",
            body=f"{linked.get('display_name') or linked.get('email')} теперь получает Telegram-уведомления.",
            channel="in_app",
            recipient_scope="crm",
            camp_id=camp_id,
            severity="info",
            metadata={"admin_id": int(linked["id"])},
        )
    return linked


def link_superadmin_account_by_code(code: str, *, telegram_user_id: int, telegram_chat_id: int, telegram_username: Optional[str] = None):
    linked = link_superadmin_telegram_account(
        code,
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        telegram_username=telegram_username,
    )
    if not linked:
        return None

    log_crm_audit_event(
        actor_type="superadmin_bot",
        actor_id=int(linked["id"]),
        actor_display=linked.get("display_name") or linked.get("login"),
        target_type="superadmin_account",
        target_id=linked["id"],
        action_type="superadmin_telegram_link_complete",
        action_label="Подключил бот уведомлений CRM",
        comment=f"Telegram @{telegram_username}" if telegram_username else "Подключение через код",
        was_auto_applied=True,
    )
    create_notification_event(
        event_type="superadmin_telegram_linked",
        title="Суперадмин подключил бот уведомлений CRM",
        body=f"{linked.get('display_name') or linked.get('login')} теперь получает Telegram-уведомления по модерации и системным событиям.",
        channel="in_app",
        recipient_scope="superadmin",
        recipient_admin_id=int(linked["id"]),
        severity="info",
        metadata={"superadmin_id": int(linked["id"])},
    )
    return linked


def get_staff_open_events_for_chat(chat_id: int, *, limit: int = 5):
    account = notification_repo.get_staff_account_by_chat_id(int(chat_id))
    if not account:
        return None, []
    camp_ids = notification_repo.list_staff_camp_ids(int(account["id"]))
    items = notification_repo.list_recent_open_events_for_admin(int(account["id"]), camp_ids, limit=limit)
    return account, items


def get_superadmin_open_events_for_chat(chat_id: int, *, limit: int = 5):
    account = notification_repo.get_superadmin_account_by_chat_id(int(chat_id))
    if not account:
        return None, []
    items = notification_repo.list_recent_open_events_for_superadmin(int(account["id"]), limit=limit)
    return account, items


def enqueue_booking_escalations(*, now_utc: Optional[datetime] = None) -> int:
    now_utc = now_utc or datetime.now(timezone.utc)
    bookings = notification_repo.list_pending_webapp_bookings(limit=300)
    if not bookings:
        return 0

    attempt_map = notification_repo.get_booking_escalation_attempt_map([int(item["id"]) for item in bookings])
    created_events = 0

    for booking in bookings:
        camp_id = int(booking.get("camp_id") or 0)
        if not camp_id:
            continue

        settings = admin_repo.get_camp_shift_settings(camp_id) or DEFAULT_SHIFT_SETTINGS
        timezone_name, zone = _zone_for_camp(camp_id)
        rules = admin_repo.list_camp_shift_rules(camp_id)
        created_at_value = booking.get("created_at")
        if not isinstance(created_at_value, datetime):
            continue

        created_local = _as_local(created_at_value, zone)
        now_local = _as_local(now_utc, zone)
        dispatch_start = _booking_dispatch_start(created_local, rules)
        if now_local <= dispatch_start:
            continue

        step_minutes = max(int(settings.get("escalation_step_minutes") or DEFAULT_SHIFT_SETTINGS["escalation_step_minutes"]), 1)
        repeats_before_manager = max(
            int(settings.get("escalation_repeats_before_manager") or DEFAULT_SHIFT_SETTINGS["escalation_repeats_before_manager"]),
            1,
        )
        next_attempt = int(attempt_map.get(int(booking["id"]), 0)) + 1
        due_at = dispatch_start + timedelta(minutes=step_minutes * next_attempt)
        if now_local < due_at:
            continue

        active_admin_ids = _active_shift_admin_ids(rules, now_local)
        active_recipients = notification_repo.list_active_staff_telegram_recipients(
            camp_id,
            admin_ids=active_admin_ids if active_admin_ids else None,
        )
        escalate_to_manager = next_attempt > repeats_before_manager
        manager_recipients = notification_repo.list_manager_telegram_recipients(
            camp_id,
            exclude_admin_ids=[int(item["id"]) for item in active_recipients],
        ) if escalate_to_manager else []

        recipients = active_recipients + [item for item in manager_recipients if item.get("id") not in {entry.get("id") for entry in active_recipients}]
        if not recipients:
            continue

        waiting_minutes = max(int((now_local - dispatch_start).total_seconds() // 60), step_minutes)
        title = _booking_escalation_title(booking, next_attempt)
        body = _booking_escalation_body(
            booking,
            attempt_no=next_attempt,
            waiting_minutes=waiting_minutes,
            escalate_to_manager=escalate_to_manager,
        )
        severity = "critical" if escalate_to_manager else "warning"
        metadata = {
            "booking_id": int(booking["id"]),
            "attempt_no": next_attempt,
            "source": "webapp",
            "dispatch_start": dispatch_start.isoformat(),
            "timezone": timezone_name,
        }

        create_notification_event(
            event_type="booking_escalation",
            title=title,
            body=body,
            channel="in_app",
            recipient_scope="crm",
            camp_id=camp_id,
            action_url="/bookings",
            action_payload={"booking_id": int(booking["id"]), "camp_id": camp_id},
            severity=severity,
            metadata=metadata,
        )
        created_events += 1

        for recipient in recipients:
            create_notification_event(
                event_type="booking_escalation",
                title=title,
                body=body,
                channel="telegram",
                recipient_scope="crm",
                recipient_admin_id=int(recipient["id"]),
                camp_id=camp_id,
                action_url="/bookings",
                action_payload={"booking_id": int(booking["id"]), "camp_id": camp_id},
                severity=severity,
                metadata=metadata,
            )
            created_events += 1

    return created_events


def format_staff_event_message(event: dict) -> str:
    header = "🛎️" if event.get("severity") == "info" else "⚠️" if event.get("severity") == "warning" else "🚨"
    camp_name = (event.get("camp_name") or "").strip()
    created_at_value = event.get("created_at")
    if isinstance(created_at_value, datetime):
        created_at_label = created_at_value.strftime("%d.%m.%Y %H:%M")
    else:
        created_at_label = str(created_at_value or "")
    lines = [
        f"{header} <b>{event.get('title') or 'Новое событие CRM'}</b>",
        "",
        str(event.get("body") or "").strip(),
    ]
    if camp_name:
        lines.extend(["", f"<b>База:</b> {camp_name}"])
    lines.extend(["", f"<b>Создано:</b> {created_at_label}"])
    return "\n".join([line for line in lines if line is not None])


def format_staff_events_digest(account: dict, items: list[dict]) -> str:
    staff_label = account.get("display_name") or account.get("email") or "Сотрудник"
    if not items:
        return (
            f"📭 <b>Открытых событий нет</b>\n\n"
            f"{staff_label}, по вашим базам сейчас нет непрочитанных предупреждений или задач."
        )
    lines = [f"📌 <b>Открытые события для {staff_label}</b>"]
    for item in items:
        severity_badge = "🚨" if item.get("severity") == "critical" else "⚠️" if item.get("severity") == "warning" else "🛎️"
        lines.extend(
            [
                "",
                f"{severity_badge} <b>{item.get('title') or 'Событие CRM'}</b>",
                str(item.get("body") or "").strip(),
                f"Статус: {EVENT_STATUS_LABELS.get(str(item.get('status') or 'new'), str(item.get('status') or 'Новое'))}",
            ]
        )
        if item.get("camp_name"):
            lines.append(f"База: {item['camp_name']}")
    return "\n".join(lines)


def format_superadmin_events_digest(account: dict, items: list[dict]) -> str:
    superadmin_label = account.get("display_name") or account.get("login") or "Суперадминистратор"
    if not items:
        return (
            f"📭 <b>Открытых событий нет</b>\n\n"
            f"{superadmin_label}, по системе сейчас нет непрочитанных событий, требующих вашего внимания."
        )
    lines = [f"🛡️ <b>События для {superadmin_label}</b>"]
    for item in items:
        severity_badge = "🚨" if item.get("severity") == "critical" else "⚠️" if item.get("severity") == "warning" else "🛎️"
        lines.extend(
            [
                "",
                f"{severity_badge} <b>{item.get('title') or 'Событие superadmin'}</b>",
                str(item.get("body") or "").strip(),
                f"Статус: {EVENT_STATUS_LABELS.get(str(item.get('status') or 'new'), str(item.get('status') or 'Новое'))}",
            ]
        )
        if item.get("camp_name"):
            lines.append(f"База: {item['camp_name']}")
    return "\n".join(lines)


def build_staff_event_keyboard(event: dict):
    recipient_scope = str(event.get("recipient_scope") or "").strip().lower() or "crm"
    url = _event_url(event.get("action_url"), recipient_scope=recipient_scope)
    metadata = event.get("metadata") or {}
    request_id = int(metadata.get("change_request_id") or 0) if metadata.get("change_request_id") else 0
    rows: list[list[InlineKeyboardButton]] = []

    if request_id and event.get("event_type") == "change_request_pending_review":
        rows.append(
            [
                InlineKeyboardButton(text="Подтвердить", callback_data=f"cr:approve:{request_id}"),
                InlineKeyboardButton(text="Отклонить", callback_data=f"cr:reject:{request_id}"),
            ]
        )
        rows.append([InlineKeyboardButton(text="Уточнить", callback_data=f"cr:clarify:{request_id}")])
    elif request_id and event.get("event_type") == "change_request_applied":
        rows.append([InlineKeyboardButton(text="Откатить", callback_data=f"cr:rollback:init:{request_id}")])
    elif recipient_scope == "superadmin" and event.get("event_type") == "superadmin_media_moderation":
        entity_type = str(metadata.get("entity_type") or "").strip().lower()
        media_id = int(metadata.get("media_id") or 0) if metadata.get("media_id") else 0
        if entity_type in {"camp", "room"} and media_id:
            rows.append(
                [
                    InlineKeyboardButton(text="Одобрить", callback_data=f"sa:media:approved:{entity_type}:{media_id}"),
                    InlineKeyboardButton(text="Отклонить", callback_data=f"sa:media:rejected:{entity_type}:{media_id}"),
                ]
            )
            rows.append([InlineKeyboardButton(text="Вернуть на модерацию", callback_data=f"sa:media:pending:{entity_type}:{media_id}")])
    elif event.get("event_type") in {"profile_pin_setup_request", "profile_pin_reset_request"}:
        token = str(metadata.get("profile_pin_token") or "").strip()
        action = str(metadata.get("profile_pin_action") or "").strip()
        if token and action in {"set", "reset"}:
            rows.append(
                [
                    InlineKeyboardButton(text="Подтвердить", callback_data=f"pin:{action}:confirm:{token}"),
                    InlineKeyboardButton(text="Отклонить", callback_data=f"pin:{action}:reject:{token}"),
                ]
            )

    if url:
        rows.append([InlineKeyboardButton(text="Открыть в панели", url=url)])
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_staff_rollback_confirm_keyboard(request_id: int, *, action_url: Optional[str] = None):
    rows = [
        [
            InlineKeyboardButton(text="Подтвердить откат", callback_data=f"cr:rollback:confirm:{request_id}"),
            InlineKeyboardButton(text="Отмена", callback_data=f"cr:rollback:cancel:{request_id}"),
        ]
    ]
    url = _event_url(action_url, recipient_scope="crm")
    if url:
        rows.append([InlineKeyboardButton(text="Открыть в CRM", url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def apply_profile_pin_action(*, telegram_chat_id: int, action: str, token: str, approved: bool):
    if action not in {"set", "reset"}:
        return {"status": "invalid"}
    return admin_repo.resolve_admin_profile_pin_request(
        token,
        telegram_chat_id=int(telegram_chat_id),
        approve=bool(approved),
    )


async def deliver_pending_telegram_notifications(bot: Bot, *, limit: int = 100) -> int:
    sent_count = 0
    for event in notification_repo.list_pending_telegram_notifications(limit=limit):
        chat_id = event.get("telegram_chat_id")
        if not chat_id:
            continue
        try:
            await bot.send_message(
                chat_id=int(chat_id),
                text=format_staff_event_message(event),
                reply_markup=build_staff_event_keyboard(event),
                disable_web_page_preview=True,
            )
        except Exception:
            logger.exception("Не удалось доставить служебное уведомление %s в Telegram", event.get("id"))
            continue
        if notification_repo.mark_telegram_notification_sent(int(event["id"])):
            sent_count += 1
    return sent_count


def build_staff_start_text() -> str:
    return (
        "👋 <b>Бот уведомлений CRM Tourist_03</b>\n\n"
        "Для привязки вашей учётки — просто напишите <b>6-значный код</b> из CRM прямо сюда в чат.\n\n"
        "Код можно найти в CRM → Настройки → ваша карточка → «Привязать Telegram»."
    )


def apply_superadmin_media_action(account: dict, *, entity_type: str, media_id: int, status_value: str):
    return superadmin_service.superadmin_update_media_moderation_by_account(
        account,
        entity_type=entity_type,
        media_id=media_id,
        status_value=status_value,
        comment="Решение принято через бот уведомлений CRM",
    )
