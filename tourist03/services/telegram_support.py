"""Fast, database-only ingestion for Telegram contact support webhooks."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from tourist03.domain.telegram_support import (
    NormalizedTelegramMessage,
    canonical_payload_hash,
    normalize_update,
    telegram_contact_public_config,
    verify_deep_link_payload,
)
from tourist03.repositories import telegram_support as support_repo


HELP_TEXT = (
    "Напишите вопрос текстом или отправьте фотографию/документ.\n\n"
    "Команды:\n"
    "/status — статус обращения\n"
    "/close — закрыть обращение\n"
    "/reopen — снова открыть последнее обращение\n"
    "/help — помощь"
)
OPERATOR_HELP_TEXT = (
    "Ответьте на конкретное сообщение пользователя.\n\n"
    "Команды в ответе на сообщение:\n"
    "/status — показать статус\n"
    "/close — закрыть обращение\n"
    "/reopen — снова открыть обращение\n"
    "/help — помощь\n\n"
    "Обычный текст, фотография или документ будут отправлены пользователю."
)
CONTACT_TOPIC_LABELS = {
    "general": "Общие вопросы",
    "placement": "Размещение объектов",
    "premium": "Премиум",
    "bug": "Ошибки",
    "suggestion": "Предложения",
}


@dataclass(frozen=True)
class TelegramUpdateResult:
    accepted: bool
    duplicate: bool = False
    ignored: bool = False
    ticket_id: Optional[int] = None
    reason: Optional[str] = None


def _setting(settings: Any, name: str, default: Any = None) -> Any:
    return getattr(settings, name, default)


def verify_webhook_secret(provided: str, settings: Any) -> bool:
    expected = str(
        _setting(settings, "telegram_webhook_secret", "")
        or _setting(settings, "telegram_support_webhook_secret", "")
        or ""
    )
    try:
        return bool(expected and provided and hmac.compare_digest(provided, expected))
    except (TypeError, UnicodeError):
        return False


def _support_chat_id(settings: Any) -> int:
    value = int(_setting(settings, "telegram_support_chat_id", 0) or 0)
    if value >= 0:
        raise RuntimeError("TELEGRAM_SUPPORT_CHAT_ID must be a supergroup id")
    return value


def _topic_id(settings: Any, topic_key: str) -> int:
    normalized = topic_key if topic_key in CONTACT_TOPIC_LABELS else "general"
    value = int(_setting(settings, f"telegram_support_topic_{normalized}", 0) or 0)
    if value <= 0:
        raise RuntimeError(f"Telegram support topic is not configured: {normalized}")
    return value


def _command_for_this_bot(
    command,
    settings: Any,
):
    if not command or not command.bot_username:
        return command
    expected = str(_setting(settings, "telegram_bot_username", "") or "").lstrip("@")
    if expected and hmac.compare_digest(
        command.bot_username.lower(),
        expected.lower(),
    ):
        return command
    return None


def _update_type(update: Mapping[str, Any]) -> str:
    for key in (
        "message",
        "edited_message",
        "channel_post",
        "edited_channel_post",
        "callback_query",
        "my_chat_member",
        "chat_member",
    ):
        if key in update:
            return key
    return "unsupported"


def _topic_intro(ticket: Mapping[str, Any]) -> str:
    snapshot = ticket.get("source_snapshot") or {}
    lines = [
        f"Обращение {ticket.get('public_number')}",
        f"Источник: {snapshot.get('kind') or snapshot.get('source_type') or 'Общий контакт'}",
        f"Название: {snapshot.get('title') or 'Общий вопрос'}",
    ]
    if snapshot.get("id") is not None:
        lines.append(f"ID: {snapshot['id']}")
    if snapshot.get("public_number"):
        lines.append(f"Заявка: {snapshot['public_number']}")
    if snapshot.get("canonical_url"):
        lines.append(f"Ссылка: {snapshot['canonical_url']}")
    return "\n".join(lines)


def _enqueue_ticket_opening(conn, ticket: Mapping[str, Any], *, created: bool) -> None:
    if not created:
        return
    ticket_id = int(ticket["id"])
    support_repo.enqueue_outbox(
        conn,
        ticket_id=ticket_id,
        action="send_text_topic",
        dedupe_key=f"ticket:{ticket_id}:source-context",
        payload={"text": _topic_intro(ticket)},
    )
    support_repo.append_audit(
        conn,
        action_type="telegram_ticket_opened",
        action_label="Создано обращение Telegram",
        target_type="telegram_ticket",
        target_id=ticket_id,
        metadata={"public_number": ticket.get("public_number")},
    )


def _enqueue_direct_user_text(
    conn,
    *,
    chat_id: int,
    update_id: int,
    key: str,
    text: str,
    ticket_id: Optional[int] = None,
    dedupe_key: Optional[str] = None,
) -> None:
    support_repo.enqueue_outbox(
        conn,
        ticket_id=ticket_id,
        action="send_text_user",
        dedupe_key=dedupe_key or f"update:{int(update_id)}:{key}",
        payload={"chat_id": int(chat_id), "text": text},
    )


def _enqueue_topic_text(
    conn,
    *,
    ticket_id: int,
    update_id: int,
    key: str,
    text: str,
) -> None:
    support_repo.enqueue_outbox(
        conn,
        ticket_id=ticket_id,
        action="send_text_topic",
        dedupe_key=f"update:{int(update_id)}:{key}",
        payload={"text": text},
    )


def _ticket_status_text(ticket: Optional[Mapping[str, Any]]) -> str:
    if not ticket:
        return "Открытого обращения пока нет. Напишите вопрос — мы создадим его."
    labels = {
        "opening": "создаётся",
        "open": "открыто",
        "closed": "закрыто",
        "blocked": "заблокировано",
    }
    return (
        f"Обращение {ticket.get('public_number')}: "
        f"{labels.get(str(ticket.get('status')), str(ticket.get('status') or 'неизвестно'))}."
    )


def _start_context(
    conn,
    *,
    argument: str,
    settings: Any,
) -> tuple[str, Optional[int], dict, bool]:
    source_type = "general"
    source_id: Optional[int] = None
    invalid = False
    if argument:
        try:
            source_type, source_id = verify_deep_link_payload(
                argument,
                str(_setting(settings, "telegram_deep_link_secret", "") or ""),
            )
        except ValueError:
            invalid = True
            source_type, source_id = "general", None
    if source_type in CONTACT_TOPIC_LABELS:
        return (
            "general",
            None,
            {
                "source_type": "general",
                "kind": CONTACT_TOPIC_LABELS[source_type],
                "title": CONTACT_TOPIC_LABELS[source_type],
                "topic_key": source_type,
            },
            invalid,
        )
    snapshot = support_repo.resolve_source_context(
        conn,
        source_type=source_type,
        source_id=source_id,
        public_base_url=str(_setting(settings, "public_base_url", "") or ""),
    )
    # A deleted/private source resolves to a deliberately generic snapshot.
    resolved_type = str(snapshot.get("source_type") or "general")
    resolved_id = snapshot.get("id") if resolved_type != "general" else None
    return resolved_type, int(resolved_id) if resolved_id is not None else None, snapshot, invalid


def _ensure_private_ticket(
    conn,
    message: NormalizedTelegramMessage,
    settings: Any,
    *,
    source_type: str = "general",
    source_id: Optional[int] = None,
    source_snapshot: Optional[Mapping[str, Any]] = None,
) -> tuple[dict, bool]:
    snapshot = dict(source_snapshot or {})
    topic_key = str(snapshot.get("topic_key") or "general")
    ticket, created = support_repo.ensure_open_ticket(
        conn,
        telegram_user_id=message.from_user_id,
        private_chat_id=message.chat_id,
        support_chat_id=_support_chat_id(settings),
        source_type=source_type,
        source_id=str(source_id) if source_id is not None else None,
        source_snapshot=snapshot,
        message_thread_id=_topic_id(settings, topic_key),
    )
    _enqueue_ticket_opening(conn, ticket, created=created)
    return ticket, created


def _handle_private_message(
    conn,
    message: NormalizedTelegramMessage,
    settings: Any,
) -> TelegramUpdateResult:
    if (
        message.chat_type != "private"
        or message.chat_id <= 0
        or message.chat_id != message.from_user_id
        or message.from_is_bot
    ):
        support_repo.mark_update(conn, message.update_id, "ignored")
        return TelegramUpdateResult(True, ignored=True, reason="invalid_private_sender")
    # Serialize the abuse checks and ticket transition for one Telegram user.
    # Distinct webhook requests can otherwise observe each other only after
    # commit and exceed the configured per-minute limit.
    support_repo.lock_user(conn, message.from_user_id)
    if support_repo.is_user_blocked(conn, message.from_user_id):
        support_repo.mark_update(conn, message.update_id, "ignored")
        support_repo.append_audit(
            conn,
            action_type="telegram_blocked_message_ignored",
            action_label="Сообщение заблокированного пользователя отклонено",
            target_type="telegram_webhook",
            target_id=message.update_id,
        )
        return TelegramUpdateResult(True, ignored=True, reason="blocked")

    per_minute = max(
        1,
        int(_setting(settings, "telegram_support_rate_per_minute", 12) or 12),
    )
    if (
        support_repo.count_recent_user_updates(
            conn,
            message.from_user_id,
            window_seconds=60,
        )
        > per_minute
    ):
        minute_bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        _enqueue_direct_user_text(
            conn,
            chat_id=message.chat_id,
            update_id=message.update_id,
            key="rate-limit",
            text="Слишком много сообщений. Подождите минуту и попробуйте снова.",
            dedupe_key=f"user:{message.from_user_id}:rate-limit:{minute_bucket}",
        )
        support_repo.mark_update(conn, message.update_id, "processed")
        return TelegramUpdateResult(True, ignored=True, reason="rate_limited")

    command = _command_for_this_bot(message.command, settings)
    if command and command.name == "start":
        source_type, source_id, snapshot, invalid = _start_context(
            conn,
            argument=command.argument,
            settings=settings,
        )
        ticket, _ = _ensure_private_ticket(
            conn,
            message,
            settings,
            source_type=source_type,
            source_id=source_id,
            source_snapshot=snapshot,
        )
        greeting = (
            "Ссылка устарела или некорректна, поэтому мы открыли общий контакт.\n\n"
            if invalid
            else "Здравствуйте! Напишите, чем вам помочь.\n\n"
        )
        _enqueue_direct_user_text(
            conn,
            chat_id=message.chat_id,
            update_id=message.update_id,
            key="start",
            text=greeting + HELP_TEXT,
            ticket_id=int(ticket["id"]),
        )
        support_repo.mark_update(conn, message.update_id, "processed")
        return TelegramUpdateResult(True, ticket_id=int(ticket["id"]))

    open_ticket = support_repo.get_open_ticket_for_user(
        conn,
        message.from_user_id,
        for_update=True,
    )
    if command and command.name == "help":
        _enqueue_direct_user_text(
            conn,
            chat_id=message.chat_id,
            update_id=message.update_id,
            key="help",
            text=HELP_TEXT,
            ticket_id=int(open_ticket["id"]) if open_ticket else None,
        )
        support_repo.mark_update(conn, message.update_id, "processed")
        return TelegramUpdateResult(
            True,
            ticket_id=int(open_ticket["id"]) if open_ticket else None,
        )
    if command and command.name == "status":
        ticket = open_ticket or support_repo.get_latest_closed_ticket_for_user(
            conn,
            message.from_user_id,
        )
        _enqueue_direct_user_text(
            conn,
            chat_id=message.chat_id,
            update_id=message.update_id,
            key="status",
            text=_ticket_status_text(ticket),
            ticket_id=int(ticket["id"]) if ticket else None,
        )
        support_repo.mark_update(conn, message.update_id, "processed")
        return TelegramUpdateResult(
            True,
            ticket_id=int(ticket["id"]) if ticket else None,
        )
    if command and command.name == "close":
        closed = (
            support_repo.close_ticket(conn, int(open_ticket["id"]))
            if open_ticket
            else None
        )
        if closed:
            ticket_id = int(closed["id"])
            support_repo.append_audit(
                conn,
                action_type="telegram_ticket_closed",
                action_label="Пользователь закрыл обращение Telegram",
                target_type="telegram_ticket",
                target_id=ticket_id,
            )
        else:
            ticket_id = None
        _enqueue_direct_user_text(
            conn,
            chat_id=message.chat_id,
            update_id=message.update_id,
            key="close",
            text=(
                f"Обращение {closed['public_number']} закрыто."
                if closed
                else "Открытого обращения нет."
            ),
            ticket_id=ticket_id,
        )
        support_repo.mark_update(conn, message.update_id, "processed")
        return TelegramUpdateResult(True, ticket_id=ticket_id)
    if command and command.name == "reopen":
        if open_ticket:
            reopened = open_ticket
            changed = False
        else:
            latest = support_repo.get_latest_closed_ticket_for_user(
                conn,
                message.from_user_id,
                for_update=True,
            )
            reopened = (
                support_repo.reopen_ticket(conn, int(latest["id"]))
                if latest
                else None
            )
            changed = reopened is not None
        ticket_id = int(reopened["id"]) if reopened else None
        if reopened and changed:
            support_repo.append_audit(
                conn,
                action_type="telegram_ticket_reopened",
                action_label="Пользователь снова открыл обращение Telegram",
                target_type="telegram_ticket",
                target_id=ticket_id,
            )
        _enqueue_direct_user_text(
            conn,
            chat_id=message.chat_id,
            update_id=message.update_id,
            key="reopen",
            text=(
                f"Обращение {reopened['public_number']} открыто."
                if reopened
                else "Закрытого обращения для повторного открытия нет."
            ),
            ticket_id=ticket_id,
        )
        support_repo.mark_update(conn, message.update_id, "processed")
        return TelegramUpdateResult(True, ticket_id=ticket_id)

    if message.text and message.text.lstrip().startswith("/"):
        _enqueue_direct_user_text(
            conn,
            chat_id=message.chat_id,
            update_id=message.update_id,
            key="unknown-command",
            text="Неизвестная команда.\n\n" + HELP_TEXT,
            ticket_id=int(open_ticket["id"]) if open_ticket else None,
        )
        support_repo.mark_update(conn, message.update_id, "processed")
        return TelegramUpdateResult(
            True,
            ignored=True,
            ticket_id=int(open_ticket["id"]) if open_ticket else None,
            reason="unknown_command",
        )

    max_document_bytes = int(
        _setting(settings, "telegram_support_max_document_bytes", 20 * 1024 * 1024)
        or 20 * 1024 * 1024
    )
    if (
        message.message_kind == "document"
        and message.file_size is not None
        and message.file_size > max_document_bytes
    ):
        _enqueue_direct_user_text(
            conn,
            chat_id=message.chat_id,
            update_id=message.update_id,
            key="oversized-document",
            text="Документ слишком большой. Отправьте файл меньшего размера.",
            ticket_id=int(open_ticket["id"]) if open_ticket else None,
        )
        support_repo.mark_update(conn, message.update_id, "processed")
        return TelegramUpdateResult(True, ignored=True, reason="oversized_document")

    ticket, _ = (
        (open_ticket, False)
        if open_ticket
        else _ensure_private_ticket(conn, message, settings)
    )
    stored = support_repo.create_message(
        conn,
        ticket_id=int(ticket["id"]),
        direction="user_to_support",
        telegram_update_id=message.update_id,
        source_chat_id=message.chat_id,
        source_message_id=message.message_id,
        sender_user_id=message.from_user_id,
        reply_to_source_message_id=message.reply_to_message_id,
        message_kind=message.message_kind,
        text=message.text,
        caption=message.caption,
        file_id=message.file_id,
        file_unique_id=message.file_unique_id,
        file_name=message.file_name,
        mime_type=message.mime_type,
        file_size=message.file_size,
    )
    support_repo.enqueue_outbox(
        conn,
        ticket_id=int(ticket["id"]),
        message_id=int(stored["id"]),
        action="copy_user_to_topic",
        dedupe_key=f"message:{stored['id']}:to-topic",
    )
    support_email = str(_setting(settings, "support_notification_email", "") or "").strip()
    if support_email:
        message_preview = (
            message.text
            or message.caption
            or f"Получен файл: {message.file_name or message.message_kind}"
        )
        support_repo.enqueue_support_email_notification(
            conn,
            recipient_address=support_email,
            event_type="telegram_support_message",
            title=f"Новое сообщение: {ticket['public_number']}",
            body=str(message_preview)[:2000],
            dedupe_key=f"telegram-support:{stored['id']}:email",
            metadata={
                "ticket_id": int(ticket["id"]),
                "message_id": int(stored["id"]),
            },
        )
    support_repo.mark_update(conn, message.update_id, "processed")
    return TelegramUpdateResult(True, ticket_id=int(ticket["id"]))


def _handle_operator_message(
    conn,
    message: NormalizedTelegramMessage,
    settings: Any,
) -> TelegramUpdateResult:
    support_chat_id = _support_chat_id(settings)
    if (
        message.chat_id != support_chat_id
        or message.chat_type not in {"supergroup", "group"}
        or not message.thread_id
        or message.from_is_bot
    ):
        support_repo.mark_update(conn, message.update_id, "ignored")
        support_repo.append_audit(
            conn,
            action_type="telegram_wrong_support_scope",
            action_label="Telegram update вне разрешённой темы отклонён",
            target_type="telegram_webhook",
            target_id=message.update_id,
        )
        return TelegramUpdateResult(True, ignored=True, reason="wrong_support_scope")

    ticket = (
        support_repo.get_ticket_by_relay_destination(
            conn,
            support_chat_id=support_chat_id,
            message_thread_id=message.thread_id,
            destination_message_id=message.reply_to_message_id,
            for_update=True,
        )
        if message.reply_to_message_id
        else None
    )
    operator = support_repo.get_operator(conn, message.from_user_id)
    if not ticket or not operator:
        support_repo.mark_update(conn, message.update_id, "ignored")
        support_repo.append_audit(
            conn,
            action_type="telegram_operator_rejected",
            action_label="Неавторизованный ответ Telegram отклонён",
            target_type="telegram_ticket" if ticket else "telegram_webhook",
            target_id=ticket.get("id") if ticket else message.update_id,
        )
        return TelegramUpdateResult(True, ignored=True, reason="operator_not_allowed")

    ticket_id = int(ticket["id"])
    command = _command_for_this_bot(message.command, settings)
    if command and command.name == "help":
        _enqueue_topic_text(
            conn,
            ticket_id=ticket_id,
            update_id=message.update_id,
            key="operator-help",
            text=OPERATOR_HELP_TEXT,
        )
    elif command and command.name == "status":
        _enqueue_topic_text(
            conn,
            ticket_id=ticket_id,
            update_id=message.update_id,
            key="operator-status",
            text=_ticket_status_text(ticket),
        )
    elif command and command.name == "close":
        if not operator.get("can_manage_topics"):
            support_repo.mark_update(conn, message.update_id, "ignored")
            return TelegramUpdateResult(True, ignored=True, reason="operator_cannot_manage")
        closed = support_repo.close_ticket(conn, ticket_id)
        if closed:
            support_repo.enqueue_outbox(
                conn,
                ticket_id=ticket_id,
                action="send_text_user",
                dedupe_key=f"update:{message.update_id}:operator-close-user",
                payload={
                    "chat_id": int(ticket["private_chat_id"]),
                    "text": f"Обращение {ticket['public_number']} закрыто оператором.",
                },
            )
            support_repo.append_audit(
                conn,
                actor_type="telegram_operator",
                actor_id=int(operator["id"]),
                actor_display=operator.get("display_name"),
                action_type="telegram_ticket_closed",
                action_label="Оператор закрыл обращение Telegram",
                target_type="telegram_ticket",
                target_id=ticket_id,
            )
    elif command and command.name == "reopen":
        if not operator.get("can_manage_topics"):
            support_repo.mark_update(conn, message.update_id, "ignored")
            return TelegramUpdateResult(True, ignored=True, reason="operator_cannot_manage")
        reopened = support_repo.reopen_ticket(conn, ticket_id)
        if reopened:
            support_repo.enqueue_outbox(
                conn,
                ticket_id=ticket_id,
                action="send_text_user",
                dedupe_key=f"update:{message.update_id}:operator-reopen-user",
                payload={
                    "chat_id": int(ticket["private_chat_id"]),
                    "text": f"Обращение {ticket['public_number']} снова открыто.",
                },
            )
            support_repo.append_audit(
                conn,
                actor_type="telegram_operator",
                actor_id=int(operator["id"]),
                actor_display=operator.get("display_name"),
                action_type="telegram_ticket_reopened",
                action_label="Оператор снова открыл обращение Telegram",
                target_type="telegram_ticket",
                target_id=ticket_id,
            )
    elif command or (message.text and message.text.lstrip().startswith("/")):
        # /start in a topic is a service command and must never reach the user.
        _enqueue_topic_text(
            conn,
            ticket_id=ticket_id,
            update_id=message.update_id,
            key="operator-command-help",
            text=OPERATOR_HELP_TEXT,
        )
    else:
        if not operator.get("can_reply") or ticket.get("status") != "open":
            support_repo.mark_update(conn, message.update_id, "ignored")
            return TelegramUpdateResult(True, ignored=True, reason="operator_cannot_reply")
        stored = support_repo.create_message(
            conn,
            ticket_id=ticket_id,
            direction="support_to_user",
            telegram_update_id=message.update_id,
            source_chat_id=message.chat_id,
            source_message_id=message.message_id,
            sender_user_id=message.from_user_id,
            reply_to_source_message_id=message.reply_to_message_id,
            message_kind=message.message_kind,
            text=message.text,
            caption=message.caption,
            file_id=message.file_id,
            file_unique_id=message.file_unique_id,
            file_name=message.file_name,
            mime_type=message.mime_type,
            file_size=message.file_size,
        )
        support_repo.enqueue_outbox(
            conn,
            ticket_id=ticket_id,
            message_id=int(stored["id"]),
            action="copy_operator_to_user",
            dedupe_key=f"message:{stored['id']}:to-user",
        )

    support_repo.mark_update(conn, message.update_id, "processed")
    return TelegramUpdateResult(True, ticket_id=ticket_id)


def process_telegram_update(
    update: Mapping[str, Any],
    settings: Any,
) -> TelegramUpdateResult:
    """Persist one update and enqueue work without making a Telegram API call."""

    try:
        update_id = int(update.get("update_id"))
    except (AttributeError, TypeError, ValueError):
        return TelegramUpdateResult(False, ignored=True, reason="invalid_update_id")
    if update_id < 0:
        return TelegramUpdateResult(False, ignored=True, reason="invalid_update_id")

    normalized = normalize_update(update)
    update_type = _update_type(update)
    with support_repo.transaction() as conn:
        registration = support_repo.register_update(
            conn,
            update_id=update_id,
            update_type=update_type,
            payload_sha256=canonical_payload_hash(update),
            telegram_user_id=normalized.from_user_id if normalized else None,
            source_chat_id=normalized.chat_id if normalized else None,
        )
        if registration in (False, "duplicate"):
            return TelegramUpdateResult(True, duplicate=True)
        if registration == "mismatch":
            support_repo.append_audit(
                conn,
                action_type="telegram_update_payload_mismatch",
                action_label="Отклонено изменение повторного Telegram update",
                target_type="telegram_webhook",
                target_id=update_id,
            )
            return TelegramUpdateResult(
                True,
                ignored=True,
                reason="duplicate_payload_mismatch",
            )
        if not normalized:
            support_repo.mark_update(conn, update_id, "ignored")
            return TelegramUpdateResult(True, ignored=True, reason="unsupported_update")
        if normalized.chat_type in {"supergroup", "group"}:
            return _handle_operator_message(conn, normalized, settings)
        return _handle_private_message(conn, normalized, settings)


__all__ = [
    "TelegramUpdateResult",
    "process_telegram_update",
    "telegram_contact_public_config",
    "verify_webhook_secret",
]
