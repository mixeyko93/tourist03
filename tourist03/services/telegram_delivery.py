"""Lease-safe delivery worker for Telegram support topics and replies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from aiogram import Bot
from aiogram.types import ReplyParameters

from tourist03.repositories import telegram_support as support_repo


logger = logging.getLogger("tourist03.telegram_support")


@dataclass(frozen=True)
class DeliveryBatchResult:
    claimed: int
    sent: int
    retried: int
    dead_lettered: int


def _message_id(result: Any) -> Optional[int]:
    value = getattr(result, "message_id", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _thread_id(result: Any) -> Optional[int]:
    value = getattr(result, "message_thread_id", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _retry_after(exc: Exception) -> Optional[int]:
    value = getattr(exc, "retry_after", None)
    try:
        return max(1, int(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_permanent_error(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    text = str(exc).lower()
    return (
        "forbidden" in name
        or "notfound" in name
        or "chat not found" in text
        or "bot was blocked" in text
        or "user is deactivated" in text
    )


def _safe_delivery_error(exc: Exception, bot: Bot) -> str:
    """Render a bounded diagnostic without persisting a Bot API token."""

    rendered = str(exc) or exc.__class__.__name__
    token = str(getattr(bot, "token", "") or "")
    if token:
        rendered = rendered.replace(token, "[redacted]")
    return rendered[:1000]


def _reply_parameters(context: Mapping[str, Any]) -> Optional[ReplyParameters]:
    reply_to = context.get("reply_to_source_message_id")
    source_chat_id = context.get("source_chat_id")
    if not reply_to or not source_chat_id:
        return None
    mapped = support_repo.find_relay_reply_message_id(
        source_chat_id=int(source_chat_id),
        destination_message_id=int(reply_to),
    )
    return (
        ReplyParameters(message_id=mapped, allow_sending_without_reply=True)
        if mapped
        else None
    )


async def _deliver_one(bot: Bot, context: Mapping[str, Any]) -> dict:
    action = str(context.get("action") or "")
    payload = context.get("payload") or {}
    if not isinstance(payload, Mapping):
        payload = {}
    ticket_id = context.get("ticket_id")
    private_chat_id = context.get("private_chat_id")
    support_chat_id = context.get("support_chat_id")
    thread_id = context.get("message_thread_id")

    if action == "create_topic":
        if not ticket_id or not support_chat_id:
            raise RuntimeError("create_topic requires a ticket and support chat")
        result = await bot.create_forum_topic(
            chat_id=int(support_chat_id),
            name=str(payload.get("topic_name") or context.get("public_number") or "Обращение")[:128],
        )
        created_thread_id = _thread_id(result)
        if not created_thread_id:
            raise RuntimeError("Telegram did not return a topic id")
        return {
            "chat_id": int(support_chat_id),
            "thread_id": created_thread_id,
            "message_id": None,
            "result": {"message_thread_id": created_thread_id},
        }

    if action == "copy_user_to_topic":
        if not support_chat_id or not thread_id:
            raise RuntimeError("support topic is not ready")
        result = await bot.copy_message(
            chat_id=int(support_chat_id),
            from_chat_id=int(context["source_chat_id"]),
            message_id=int(context["source_message_id"]),
            message_thread_id=int(thread_id),
            reply_parameters=_reply_parameters(context),
        )
        return {
            "chat_id": int(support_chat_id),
            "thread_id": int(thread_id),
            "message_id": _message_id(result),
            "result": {"copied": True},
        }

    if action == "copy_operator_to_user":
        if not private_chat_id:
            raise RuntimeError("ticket private chat is missing")
        result = await bot.copy_message(
            chat_id=int(private_chat_id),
            from_chat_id=int(context["source_chat_id"]),
            message_id=int(context["source_message_id"]),
            reply_parameters=_reply_parameters(context),
        )
        return {
            "chat_id": int(private_chat_id),
            "thread_id": None,
            "message_id": _message_id(result),
            "result": {"copied": True},
        }

    if action == "send_text_user":
        chat_id = payload.get("chat_id") or private_chat_id
        if not chat_id:
            raise RuntimeError("send_text_user requires a destination chat")
        result = await bot.send_message(
            chat_id=int(chat_id),
            text=str(payload.get("text") or "")[:4096],
            parse_mode=None,
            disable_web_page_preview=True,
        )
        return {
            "chat_id": int(chat_id),
            "thread_id": None,
            "message_id": _message_id(result),
            "result": {"sent": True},
        }

    if action == "send_text_topic":
        if not support_chat_id or not thread_id:
            raise RuntimeError("send_text_topic requires an active topic")
        result = await bot.send_message(
            chat_id=int(support_chat_id),
            message_thread_id=int(thread_id),
            text=str(payload.get("text") or "")[:4096],
            parse_mode=None,
            disable_web_page_preview=True,
        )
        return {
            "chat_id": int(support_chat_id),
            "thread_id": int(thread_id),
            "message_id": _message_id(result),
            "result": {"sent": True},
        }

    if action == "close_topic":
        if not support_chat_id or not thread_id:
            raise RuntimeError("close_topic requires an active topic")
        await bot.close_forum_topic(
            chat_id=int(support_chat_id),
            message_thread_id=int(thread_id),
        )
        return {
            "chat_id": int(support_chat_id),
            "thread_id": int(thread_id),
            "message_id": None,
            "result": {"closed": True},
        }

    if action == "reopen_topic":
        if not support_chat_id or not thread_id:
            raise RuntimeError("reopen_topic requires an existing topic")
        await bot.reopen_forum_topic(
            chat_id=int(support_chat_id),
            message_thread_id=int(thread_id),
        )
        return {
            "chat_id": int(support_chat_id),
            "thread_id": int(thread_id),
            "message_id": None,
            "result": {"reopened": True},
        }

    raise RuntimeError(f"Unsupported Telegram outbox action: {action}")


async def deliver_support_outbox_batch(
    bot: Bot,
    *,
    limit: int = 50,
    lease_seconds: int = 60,
    max_attempts: int = 10,
) -> DeliveryBatchResult:
    claimed_rows = support_repo.claim_outbox_batch(
        limit=limit,
        lease_seconds=lease_seconds,
    )
    sent = retried = dead_lettered = 0
    for claimed in claimed_rows:
        outbox_id = int(claimed["id"])
        claim_token = str(claimed.get("claim_token") or "")
        if not claim_token:
            continue
        context = support_repo.load_delivery_context(outbox_id, claim_token)
        if not context:
            status = support_repo.mark_outbox_failed(
                outbox_id,
                claim_token,
                error="Telegram delivery context is missing",
                max_attempts=max_attempts,
                permanent=True,
            )
            dead_lettered += status == "dead_letter"
            continue
        delivered: Optional[dict] = None
        try:
            delivered = await _deliver_one(bot, context)
            if context.get("action") == "create_topic":
                support_repo.complete_topic_creation(
                    outbox_id,
                    claim_token,
                    ticket_id=int(context["ticket_id"]),
                    support_chat_id=int(delivered["chat_id"]),
                    message_thread_id=int(delivered["thread_id"]),
                )
            else:
                acknowledged = support_repo.mark_outbox_sent(
                    outbox_id,
                    claim_token,
                    telegram_result=delivered.get("result"),
                    destination_chat_id=delivered.get("chat_id"),
                    destination_thread_id=delivered.get("thread_id"),
                    destination_message_id=delivered.get("message_id"),
                )
                if acknowledged is False:
                    raise RuntimeError(
                        "Telegram delivery ACK did not match the active claim"
                    )
            sent += 1
        except Exception as exc:
            safe_error = _safe_delivery_error(exc, bot)
            if context.get("action") == "create_topic":
                # Telegram does not offer an idempotency key for
                # createForumTopic.  Any exception after starting the request
                # is therefore ambiguous: retrying could create a duplicate.
                # Preserve a returned thread id when available and require
                # explicit operator reconciliation.
                status = support_repo.mark_topic_creation_ambiguous(
                    outbox_id,
                    claim_token,
                    error=safe_error,
                    support_chat_id=(
                        delivered.get("chat_id") if delivered is not None else None
                    ),
                    message_thread_id=(
                        delivered.get("thread_id") if delivered is not None else None
                    ),
                )
            elif delivered is not None:
                # Telegram confirmed the non-idempotent remote operation.
                # Retrying after a local ACK failure could duplicate a message
                # or repeat a topic state change, so quarantine it instead.
                status = support_repo.mark_delivery_ambiguous(
                    outbox_id,
                    claim_token,
                    error=safe_error,
                    telegram_result=delivered.get("result"),
                    destination_chat_id=delivered.get("chat_id"),
                    destination_thread_id=delivered.get("thread_id"),
                    destination_message_id=delivered.get("message_id"),
                )
            else:
                status = support_repo.mark_outbox_failed(
                    outbox_id,
                    claim_token,
                    error=safe_error,
                    max_attempts=max_attempts,
                    retry_after_seconds=_retry_after(exc),
                    permanent=_is_permanent_error(exc),
                )
            if status == "sent":
                sent += 1
            elif status == "dead_letter":
                dead_lettered += 1
            elif status == "retry":
                retried += 1
            logger.warning(
                "Telegram support delivery failed for outbox id=%s status=%s",
                outbox_id,
                status,
            )
    return DeliveryBatchResult(
        claimed=len(claimed_rows),
        sent=sent,
        retried=retried,
        dead_lettered=dead_lettered,
    )


__all__ = ["DeliveryBatchResult", "deliver_support_outbox_batch"]
