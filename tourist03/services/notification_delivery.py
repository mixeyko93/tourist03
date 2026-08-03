"""Delivery adapters for submission outbox events."""

from __future__ import annotations

import smtplib
import ssl
import hashlib
import hmac
from datetime import datetime
from email.headerregistry import Address
from email.message import EmailMessage
from urllib.parse import quote

from tourist03.owner_security import owner_reset_token_for
from tourist03.repositories import notifications as notification_repo
from tourist03.repositories import owners as owner_repo
from tourist03.repositories import submissions as submission_repo
from tourist03.settings import Settings, get_settings
from tourist03.submission_media import remove_stored_media


class EmailDeliveryUnavailable(RuntimeError):
    """SMTP is not configured for delivery."""


def _email_message_id(event: dict, settings: Settings) -> str:
    sender_domain = settings.smtp_from.strip().rsplit("@", 1)[-1].lower()
    if not sender_domain or sender_domain == settings.smtp_from.strip().lower():
        sender_domain = "turistika.invalid"
    stable_key = str(
        event.get("dedupe_key")
        or f"notification:{int(event.get('id') or 0)}"
    )
    digest = hmac.new(
        settings.session_secret_key.encode("utf-8"),
        stable_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"<{digest}@{sender_domain}>"


def _safe_delivery_error(exc: Exception, settings: Settings) -> str:
    rendered = str(exc) or type(exc).__name__
    for secret in (settings.smtp_password, settings.smtp_user):
        if secret:
            rendered = rendered.replace(secret, "[redacted]")
    return rendered[:1000]


def _send_email(event: dict, settings: Settings) -> str:
    if not settings.smtp_host or not settings.smtp_from:
        raise EmailDeliveryUnavailable("SMTP_HOST and SMTP_FROM are required")
    recipient = str(event.get("recipient_address") or "").strip()
    if not recipient or any(character in recipient for character in "\r\n"):
        raise EmailDeliveryUnavailable("A valid email recipient is required")
    sender = settings.smtp_from.strip()
    if not sender or any(character in sender for character in "\r\n"):
        raise EmailDeliveryUnavailable("A valid SMTP_FROM is required")
    message = EmailMessage()
    message["Subject"] = str(event.get("title") or "Туристика")
    message["From"] = (
        Address(display_name=settings.smtp_from_name.strip(), addr_spec=sender)
        if settings.smtp_from_name.strip()
        else sender
    )
    message["To"] = recipient
    message_id = _email_message_id(event, settings)
    message["Message-ID"] = message_id
    if settings.smtp_reply_to.strip():
        if any(character in settings.smtp_reply_to for character in "\r\n"):
            raise EmailDeliveryUnavailable("A valid SMTP_REPLY_TO is required")
        message["Reply-To"] = settings.smtp_reply_to.strip()
    action_url = str(event.get("action_url") or "").strip()
    if action_url.startswith("/"):
        if action_url == "/owner" or action_url.startswith("/owner/"):
            base_url = settings.owner_base_url
        elif action_url == "/admin" or action_url.startswith("/admin/"):
            base_url = settings.superadmin_base_url
        else:
            base_url = settings.public_base_url
        action_url = f"{base_url.rstrip('/')}{action_url}"
    if event.get("event_type") == "owner_password_reset_requested":
        payload = event.get("action_payload") or {}
        expires_at = datetime.fromisoformat(str(payload["expires_at"]).replace("Z", "+00:00"))
        token = owner_reset_token_for(
            int(payload["reset_id"]),
            int(payload["owner_id"]),
            expires_at,
            settings.session_secret_key,
        )
        # Keep the bearer token out of reverse-proxy access logs and Referer
        # headers.  The owner UI consumes the fragment locally and immediately
        # removes it from the address bar.
        action_url = f"{action_url.split('#', 1)[0]}#reset={quote(token, safe='')}"
    text = str(event.get("body") or "").strip()
    if action_url:
        text = f"{text}\n\nПроверить статус: {action_url}"
    message.set_content(text)

    context = ssl.create_default_context()
    if settings.smtp_security == "ssl":
        with smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
            context=context,
        ) as client:
            if settings.smtp_user:
                client.login(settings.smtp_user, settings.smtp_password)
            refused = client.send_message(message)
    elif settings.smtp_security == "starttls":
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
            if settings.smtp_user:
                client.login(settings.smtp_user, settings.smtp_password)
            refused = client.send_message(message)
    else:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as client:
            if settings.smtp_user:
                client.login(settings.smtp_user, settings.smtp_password)
            refused = client.send_message(message)
    if refused:
        raise smtplib.SMTPRecipientsRefused(refused)
    return message_id


def deliver_pending_email_notifications(
    *,
    settings: Settings | None = None,
    limit: int = 100,
) -> int:
    resolved = settings or get_settings()
    if not resolved.feature_email_delivery:
        return 0
    sent = 0
    for event in notification_repo.claim_pending_email_notifications(
        limit=limit,
        lease_seconds=resolved.notification_delivery_lease_seconds,
    ):
        claim_token = str(event.get("claim_token") or "")
        if not claim_token:
            continue
        try:
            message_id = _send_email(event, resolved)
        except Exception as exc:
            failed_recorded = notification_repo.mark_claimed_email_notification_failed(
                int(event["id"]),
                claim_token,
                _safe_delivery_error(exc, resolved),
            )
            submission_id = event.get("submission_id")
            if failed_recorded and submission_id:
                try:
                    submission = submission_repo.get_submission_detail(int(submission_id))
                    public_number = (
                        submission.get("public_number")
                        if submission
                        else "неизвестная заявка"
                    )
                    submission_repo.enqueue_submission_notifications(
                        int(submission_id),
                        event_type=f"placement_submission_email_failed_{int(event['id'])}",
                        title=f"Ошибка email: {public_number}",
                        body=(
                            f"Письмо заявителю не доставлено. "
                            f"Причина сохранена в outbox после попытки {int(event.get('attempts') or 0) + 1}."
                        ),
                        admin_action_url=(
                            f"{resolved.superadmin_base_url.rstrip('/')}"
                            f"/admin/submissions?submission={int(submission_id)}"
                        ),
                        severity="warning",
                    )
                except Exception:
                    # Ошибка резервного Telegram-события не меняет retry email.
                    pass
            continue
        if notification_repo.mark_claimed_email_notification_sent(
            int(event["id"]),
            claim_token,
            delivered_message_id=message_id,
        ):
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
    rows.extend(owner_repo.expire_owner_change_media(limit=limit))
    for row in rows:
        remove_stored_media(
            resolved,
            row.get("storage_key"),
            row.get("thumbnail_storage_key"),
        )
    return len(rows)
