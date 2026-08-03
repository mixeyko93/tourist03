#!/usr/bin/env python3
"""Run the real SMTP TLS/auth/send gate without touching the application outbox."""

from __future__ import annotations

import smtplib
import socket
import ssl
import sys
from email.headerregistry import Address
from email.message import EmailMessage
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tourist03.settings import Settings, get_settings  # noqa: E402


EXIT_CONFIG = 2
EXIT_DNS = 3
EXIT_TLS = 4
EXIT_AUTH = 5
EXIT_SEND = 6


def _status(stage: str, status: str, detail: str = "") -> None:
    suffix = f" detail={detail}" if detail else ""
    print(f"SMTP_GATE stage={stage} status={status}{suffix}", flush=True)


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, smtplib.SMTPResponseException):
        return f"{type(exc).__name__}:code={exc.smtp_code}"
    return type(exc).__name__


def _validate(settings: Settings) -> None:
    if not settings.smtp_host or not settings.smtp_from or not settings.smtp_test_email:
        raise ValueError("required SMTP settings are missing")
    if settings.smtp_user and not settings.smtp_password:
        raise ValueError("SMTP password is missing")
    if settings.is_production and settings.smtp_security == "plain":
        raise ValueError("plain SMTP is forbidden in production")
    for value in (
        settings.smtp_from,
        settings.smtp_test_email,
        settings.smtp_reply_to,
    ):
        if "\r" in value or "\n" in value:
            raise ValueError("invalid email header")


def run_gate(settings: Settings | None = None) -> int:
    resolved = settings or get_settings()
    try:
        _validate(resolved)
    except Exception as exc:
        _status("config", "failed", _safe_error(exc))
        return EXIT_CONFIG
    _status("config", "ok")

    try:
        socket.getaddrinfo(
            resolved.smtp_host,
            resolved.smtp_port,
            type=socket.SOCK_STREAM,
        )
    except Exception as exc:
        _status("dns", "failed", _safe_error(exc))
        return EXIT_DNS
    _status("dns", "ok")

    context = ssl.create_default_context()
    client: smtplib.SMTP
    try:
        if resolved.smtp_security == "ssl":
            client = smtplib.SMTP_SSL(
                resolved.smtp_host,
                resolved.smtp_port,
                timeout=resolved.smtp_timeout_seconds,
                context=context,
            )
        else:
            client = smtplib.SMTP(
                resolved.smtp_host,
                resolved.smtp_port,
                timeout=resolved.smtp_timeout_seconds,
            )
            client.ehlo()
            if resolved.smtp_security == "starttls":
                client.starttls(context=context)
                client.ehlo()
    except Exception as exc:
        _status("tls", "failed", _safe_error(exc))
        return EXIT_TLS
    _status("tls", "ok", resolved.smtp_security)

    try:
        if resolved.smtp_user:
            client.login(resolved.smtp_user, resolved.smtp_password)
    except Exception as exc:
        client.close()
        _status("auth", "failed", _safe_error(exc))
        return EXIT_AUTH
    _status("auth", "ok")

    message = EmailMessage()
    message["Subject"] = "Проверка почты «Туристики»"
    message["From"] = (
        Address(
            display_name=resolved.smtp_from_name.strip(),
            addr_spec=resolved.smtp_from.strip(),
        )
        if resolved.smtp_from_name.strip()
        else resolved.smtp_from.strip()
    )
    message["To"] = resolved.smtp_test_email.strip()
    if resolved.smtp_reply_to.strip():
        message["Reply-To"] = resolved.smtp_reply_to.strip()
    message.set_content(
        "SMTP TLS/Auth/Send gate проекта «Туристика» выполнен успешно."
    )
    try:
        refused = client.send_message(message)
        client.quit()
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    except Exception as exc:
        client.close()
        _status("send", "failed", _safe_error(exc))
        return EXIT_SEND
    _status("send", "ok")
    return 0


def main() -> int:
    return run_gate()


if __name__ == "__main__":
    raise SystemExit(main())
