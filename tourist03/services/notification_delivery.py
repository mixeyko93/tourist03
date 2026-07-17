"""Delivery adapters for submission outbox events."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from tourist03.repositories import notifications as notification_repo
from tourist03.repositories import submissions as submission_repo
from tourist03.settings import Settings, get_settings
from tourist03.submission_media import remove_stored_media


class EmailDeliveryUnavailable(RuntimeError):
    """SMTP is not configured for delivery."""


def _send_email(event: dict, settings: Settings) -> None:
    if not settings.smtp_host or not settings.smtp_from:
        raise EmailDeliveryUnavailable("SMTP_HOST and SMTP_FROM are required")
    message = EmailMessage()
    message["Subject"] = str(event.get("title") or "Туристика")
    message["From"] = settings.smtp_from
    message["To"] = str(event["recipient_address"])
    action_url = str(event.get("action_url") or "").strip()
    text = str(event.get("body") or "").strip()
    if action_url:
        text = f"{text}\n\nПроверить статус: {action_url}"
    message.set_content(text)

    if settings.smtp_use_tls:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
            client.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                client.login(settings.smtp_user, settings.smtp_password)
            client.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
            if settings.smtp_user:
                client.login(settings.smtp_user, settings.smtp_password)
            client.send_message(message)


def deliver_pending_email_notifications(
    *,
    settings: Settings | None = None,
    limit: int = 100,
) -> int:
    resolved = settings or get_settings()
    sent = 0
    for event in notification_repo.list_pending_email_notifications(limit=limit):
        try:
            _send_email(event, resolved)
        except Exception as exc:
            notification_repo.mark_notification_failed(int(event["id"]), str(exc))
            continue
        if notification_repo.mark_email_notification_sent(int(event["id"])):
            sent += 1
    return sent


def cleanup_expired_submission_uploads(
    *,
    settings: Settings | None = None,
    limit: int = 200,
) -> int:
    resolved = settings or get_settings()
    if not resolved.submission_cleanup_enabled:
        return 0
    rows = submission_repo.expire_staged_media(limit=limit)
    for row in rows:
        remove_stored_media(
            resolved,
            row.get("storage_key"),
            row.get("thumbnail_storage_key"),
        )
    return len(rows)
