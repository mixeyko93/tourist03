#!/usr/bin/env python3
"""Safe operational checks for Telegram contact support.

The token and webhook secret are read only through :class:`Settings`; neither is
accepted on the command line or included in output.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from aiogram import Bot

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tourist03.repositories import telegram_support as support_repo
from tourist03.settings import get_settings


@dataclass(frozen=True)
class Validation:
    bot_ok: bool
    username_ok: bool
    support_chat_ok: bool
    support_chat_is_forum: bool
    bot_is_chat_admin: bool
    bot_can_manage_topics: bool
    operators_configured: int
    operators_validated: int


def _token(settings: Any) -> str:
    return str(
        getattr(settings, "telegram_support_bot_token", "")
        or getattr(settings, "telegram_bot_token", "")
        or ""
    ).strip()


def _operator_ids(settings: Any) -> list[int]:
    value = getattr(settings, "telegram_support_operator_ids", ())
    if isinstance(value, str):
        parts = value.split(",")
    else:
        parts = list(value or ())
    normalized: set[int] = set()
    for part in parts:
        try:
            user_id = int(str(part).strip())
        except (TypeError, ValueError):
            continue
        if user_id > 0:
            normalized.add(user_id)
    return sorted(normalized)


async def _inspect(bot: Bot, settings: Any) -> tuple[Validation, list[int]]:
    me = await bot.get_me()
    configured_username = str(
        getattr(settings, "telegram_bot_username", "") or ""
    ).strip().lstrip("@").lower()
    actual_username = str(getattr(me, "username", "") or "").lower()
    support_chat_id = int(
        getattr(settings, "telegram_support_chat_id", 0) or 0
    )
    chat = await bot.get_chat(support_chat_id)
    bot_member = await bot.get_chat_member(support_chat_id, int(me.id))
    bot_status = str(getattr(bot_member, "status", ""))
    bot_is_chat_admin = bot_status in {"administrator", "creator"}
    bot_can_manage_topics = bool(
        bot_status == "creator"
        or getattr(bot_member, "can_manage_topics", False)
    )
    operator_ids = _operator_ids(settings)
    validated: list[int] = []
    for operator_id in operator_ids:
        try:
            member = await bot.get_chat_member(support_chat_id, operator_id)
            if str(getattr(member, "status", "")) in {
                "administrator",
                "creator",
            }:
                validated.append(operator_id)
        except Exception:
            # A missing/invalid allowlist entry remains unvalidated in the
            # database; no token or Telegram response body is printed.
            continue
    validation = Validation(
        bot_ok=bool(getattr(me, "is_bot", False)),
        username_ok=bool(
            configured_username
            and actual_username
            and configured_username == actual_username
        ),
        support_chat_ok=support_chat_id < 0,
        support_chat_is_forum=bool(getattr(chat, "is_forum", False)),
        bot_is_chat_admin=bot_is_chat_admin,
        bot_can_manage_topics=bot_can_manage_topics,
        operators_configured=len(operator_ids),
        operators_validated=len(validated),
    )
    return validation, validated


async def _run(
    command: str,
    *,
    user_id: int | None = None,
    reason: str = "",
    expires_hours: int | None = None,
    ticket_id: int | None = None,
    thread_id: int | None = None,
    confirmation: str = "",
) -> int:
    settings = get_settings()
    token = _token(settings)
    if not token:
        raise RuntimeError("Telegram support bot token is not configured")
    secret = str(
        getattr(settings, "telegram_webhook_secret", "")
        or getattr(settings, "telegram_support_webhook_secret", "")
        or ""
    )
    if not secret:
        raise RuntimeError("Telegram webhook secret is not configured")

    bot = Bot(token=token)
    try:
        validation, validated_ids = await _inspect(bot, settings)
        output: dict[str, Any] = {
            "command": command,
            "validation": asdict(validation),
        }
        if command == "sync-operators":
            output["database_rows_changed"] = support_repo.sync_operators(
                _operator_ids(settings),
                validated_ids=validated_ids,
            )
        elif command == "configure":
            if not all(
                (
                    validation.bot_ok,
                    validation.username_ok,
                    validation.support_chat_ok,
                    validation.support_chat_is_forum,
                    validation.bot_is_chat_admin,
                    validation.operators_configured > 0,
                    validation.operators_validated
                    == validation.operators_configured,
                )
            ):
                raise RuntimeError("Telegram validation failed; webhook was not changed")
            # Persist the exact allowlist that was just checked before opening
            # the webhook. This prevents a valid configuration whose operators
            # are nevertheless rejected because ``validated_at`` remained NULL.
            output["database_rows_changed"] = support_repo.sync_operators(
                _operator_ids(settings),
                validated_ids=validated_ids,
            )
            public_base_url = str(
                getattr(settings, "public_base_url", "") or ""
            ).rstrip("/")
            if not public_base_url.startswith("https://"):
                raise RuntimeError("PUBLIC_BASE_URL must use HTTPS")
            await bot.set_webhook(
                url=f"{public_base_url}/api/telegram/support/webhook",
                secret_token=secret,
                allowed_updates=["message"],
                drop_pending_updates=False,
                max_connections=20,
            )
            output["configured"] = True
        elif command == "status":
            info = await bot.get_webhook_info()
            output["webhook"] = {
                "url": str(getattr(info, "url", "") or ""),
                "has_custom_certificate": bool(
                    getattr(info, "has_custom_certificate", False)
                ),
                "pending_update_count": int(
                    getattr(info, "pending_update_count", 0) or 0
                ),
                "last_error_date": getattr(info, "last_error_date", None),
                "last_error_message": str(
                    getattr(info, "last_error_message", "") or ""
                )[:500]
                or None,
                "max_connections": getattr(info, "max_connections", None),
                "allowed_updates": getattr(info, "allowed_updates", None),
            }
        elif command == "block-user":
            if user_id is None or user_id <= 0:
                raise RuntimeError("--user-id must be a positive Telegram user id")
            expires_at = (
                datetime.now(timezone.utc) + timedelta(hours=expires_hours)
                if expires_hours is not None
                else None
            )
            support_repo.block_user(
                user_id,
                reason=reason,
                expires_at=expires_at,
            )
            output["blocked"] = True
            output["telegram_user_id"] = user_id
            output["expires_at"] = expires_at
        elif command == "unblock-user":
            if user_id is None or user_id <= 0:
                raise RuntimeError("--user-id must be a positive Telegram user id")
            output["unblocked"] = support_repo.unblock_user(user_id)
            output["telegram_user_id"] = user_id
        elif command == "reconcile-topic":
            if confirmation != "RECONCILE_TOPIC":
                raise RuntimeError(
                    "Topic reconciliation requires --confirm RECONCILE_TOPIC"
                )
            if ticket_id is None or ticket_id <= 0:
                raise RuntimeError("--ticket-id must be positive")
            if thread_id is None or thread_id <= 0:
                raise RuntimeError("--thread-id must be positive")
            reconciled = support_repo.reconcile_topic_creation(
                ticket_id=ticket_id,
                support_chat_id=int(
                    getattr(settings, "telegram_support_chat_id", 0) or 0
                ),
                message_thread_id=thread_id,
            )
            output["reconciled"] = True
            output["ticket_id"] = int(reconciled["id"])
            output["message_thread_id"] = int(reconciled["message_thread_id"])
        elif command != "validate":
            raise RuntimeError("unsupported command")
        print(json.dumps(output, ensure_ascii=False, default=str, indent=2))
        return 0
    finally:
        await bot.session.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and configure Turistika Telegram support",
    )
    parser.add_argument(
        "command",
        choices=(
            "validate",
            "configure",
            "status",
            "sync-operators",
            "block-user",
            "unblock-user",
            "reconcile-topic",
        ),
    )
    parser.add_argument("--user-id", type=int)
    parser.add_argument("--reason", default="")
    parser.add_argument("--expires-hours", type=int)
    parser.add_argument("--ticket-id", type=int)
    parser.add_argument("--thread-id", type=int)
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.expires_hours is not None and not 1 <= args.expires_hours <= 24 * 365:
        parser.error("--expires-hours must be between 1 and 8760")
    return asyncio.run(
        _run(
            args.command,
            user_id=args.user_id,
            reason=args.reason,
            expires_hours=args.expires_hours,
            ticket_id=args.ticket_id,
            thread_id=args.thread_id,
            confirmation=args.confirm,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
