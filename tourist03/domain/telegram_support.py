"""Pure validation and deep-link helpers for Telegram contact support."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional


SUPPORTED_COMMANDS = frozenset({"start", "help", "status", "close", "reopen"})
SOURCE_TYPE_CODES = {
    "general": "g",
    "entity": "e",
    "route": "r",
    "collection": "c",
    "submission": "s",
}
SOURCE_CODE_TYPES = {value: key for key, value in SOURCE_TYPE_CODES.items()}
BOT_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")
COMMAND_RE = re.compile(
    r"^/([A-Za-z]+)(?:@([A-Za-z0-9_]{5,32}))?(?:\s+(.+))?$"
)
MAX_DEEP_LINK_PAYLOAD_LENGTH = 64
MAX_TEXT_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024


@dataclass(frozen=True)
class TelegramCommand:
    name: str
    argument: str = ""
    bot_username: Optional[str] = None


@dataclass(frozen=True)
class NormalizedTelegramMessage:
    update_id: int
    chat_id: int
    chat_type: str
    message_id: int
    thread_id: Optional[int]
    from_user_id: int
    from_is_bot: bool
    username: Optional[str]
    display_name: str
    message_kind: str
    text: Optional[str]
    caption: Optional[str]
    file_id: Optional[str]
    file_unique_id: Optional[str]
    file_name: Optional[str]
    mime_type: Optional[str]
    file_size: Optional[int]
    reply_to_message_id: Optional[int]
    command: Optional[TelegramCommand]


def _base36_encode(value: int) -> str:
    if value < 0:
        raise ValueError("source_id must not be negative")
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    encoded = ""
    while value:
        value, remainder = divmod(value, 36)
        encoded = alphabet[remainder] + encoded
    return encoded


def _base36_decode(value: str) -> int:
    if not value or not re.fullmatch(r"[0-9a-z]+", value):
        raise ValueError("invalid base36 source id")
    return int(value, 36)


def _signature(value: str, secret: str) -> str:
    if not secret:
        raise ValueError("Telegram deep-link secret is required")
    digest = hmac.new(
        secret.encode("utf-8"),
        value.encode("ascii"),
        hashlib.sha256,
    ).digest()[:12]
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def sign_deep_link_payload(
    source_type: str,
    source_id: Optional[int],
    secret: str,
) -> str:
    """Return a compact, URL-safe and tamper-evident Telegram ``start`` payload."""

    normalized_type = str(source_type or "general").strip().lower()
    code = SOURCE_TYPE_CODES.get(normalized_type)
    if not code:
        raise ValueError("unsupported Telegram source type")
    normalized_id = 0 if normalized_type == "general" else int(source_id or 0)
    if normalized_type != "general" and normalized_id <= 0:
        raise ValueError("positive source_id is required")
    # Telegram's ``start`` parameter accepts only ``[A-Za-z0-9_-]``.
    # Keep the complete payload inside that alphabet (a dot-separated payload
    # looks URL-safe but Telegram rejects it before the bot receives /start).
    unsigned = f"v1_{code}_{_base36_encode(normalized_id)}"
    payload = f"{unsigned}_{_signature(unsigned, secret)}"
    if len(payload) > MAX_DEEP_LINK_PAYLOAD_LENGTH:
        raise ValueError("Telegram deep-link payload exceeds 64 characters")
    return payload


def verify_deep_link_payload(payload: str, secret: str) -> tuple[str, Optional[int]]:
    """Validate a signed payload and return ``(source_type, source_id)``."""

    raw = (payload or "").strip()
    if not raw or len(raw) > MAX_DEEP_LINK_PAYLOAD_LENGTH:
        raise ValueError("invalid Telegram deep-link payload")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", raw):
        raise ValueError("invalid Telegram deep-link payload")
    parts = raw.split("_", 3)
    if len(parts) != 4 or parts[0] != "v1":
        raise ValueError("invalid Telegram deep-link payload")
    source_type = SOURCE_CODE_TYPES.get(parts[1])
    if not source_type:
        raise ValueError("invalid Telegram deep-link source type")
    unsigned = "_".join(parts[:3])
    if not hmac.compare_digest(_signature(unsigned, secret), parts[3]):
        raise ValueError("invalid Telegram deep-link signature")
    source_id = _base36_decode(parts[2])
    if source_type == "general":
        if source_id != 0:
            raise ValueError("general Telegram context cannot have a source id")
        return source_type, None
    if source_id <= 0:
        raise ValueError("Telegram source id must be positive")
    return source_type, source_id


def _setting(settings: Any, name: str, default: Any = None) -> Any:
    return getattr(settings, name, default)


def build_telegram_deep_link(
    settings: Any,
    source_type: str = "general",
    source_id: Optional[int] = None,
) -> Optional[str]:
    """Build a public Telegram URL without exposing tokens or application secrets."""

    if not bool(_setting(settings, "feature_telegram_contact", False)):
        return None
    username = str(_setting(settings, "telegram_bot_username", "") or "").strip().lstrip("@")
    secret = str(_setting(settings, "telegram_deep_link_secret", "") or "")
    if not BOT_USERNAME_RE.fullmatch(username) or not secret:
        return None
    try:
        payload = sign_deep_link_payload(source_type, source_id, secret)
    except (TypeError, ValueError):
        return None
    return f"https://t.me/{username}?start={payload}"


def telegram_contact_public_config(settings: Any) -> dict[str, Any]:
    """Return the only Telegram support settings safe for a public response."""

    general_url = build_telegram_deep_link(settings)
    username = str(_setting(settings, "telegram_bot_username", "") or "").strip().lstrip("@")
    return {
        "enabled": bool(general_url),
        "bot_username": username if general_url else None,
        "general_url": general_url,
    }


def parse_command(text: Optional[str]) -> Optional[TelegramCommand]:
    raw = (text or "").strip()
    match = COMMAND_RE.match(raw)
    if not match:
        return None
    name = match.group(1).lower()
    if name not in SUPPORTED_COMMANDS:
        return None
    return TelegramCommand(
        name=name,
        bot_username=(match.group(2) or "").strip() or None,
        argument=(match.group(3) or "").strip(),
    )


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any, limit: int) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.replace("\x00", "").strip()
    return normalized[:limit] if normalized else None


def normalize_update(update: Mapping[str, Any]) -> Optional[NormalizedTelegramMessage]:
    """Normalize a supported Bot API message without retaining the raw update."""

    update_id = _safe_int(update.get("update_id"))
    message = update.get("message")
    if update_id is None or update_id < 0 or not isinstance(message, Mapping):
        return None
    chat = message.get("chat")
    sender = message.get("from")
    if not isinstance(chat, Mapping) or not isinstance(sender, Mapping):
        return None
    chat_id = _safe_int(chat.get("id"))
    message_id = _safe_int(message.get("message_id"))
    user_id = _safe_int(sender.get("id"))
    if chat_id is None or message_id is None or user_id is None:
        return None

    text = _clean_text(message.get("text"), MAX_TEXT_LENGTH)
    caption = _clean_text(message.get("caption"), MAX_CAPTION_LENGTH)
    file_id = file_unique_id = file_name = mime_type = None
    file_size: Optional[int] = None
    message_kind = "text"

    photo = message.get("photo")
    document = message.get("document")
    if isinstance(photo, list) and photo:
        candidates = [item for item in photo if isinstance(item, Mapping) and item.get("file_id")]
        if candidates:
            selected = max(
                candidates,
                key=lambda item: (
                    _safe_int(item.get("file_size")) or 0,
                    (_safe_int(item.get("width")) or 0) * (_safe_int(item.get("height")) or 0),
                ),
            )
            message_kind = "photo"
            file_id = str(selected.get("file_id") or "") or None
            file_unique_id = str(selected.get("file_unique_id") or "") or None
            file_size = _safe_int(selected.get("file_size"))
    elif isinstance(document, Mapping) and document.get("file_id"):
        message_kind = "document"
        file_id = str(document.get("file_id") or "") or None
        file_unique_id = str(document.get("file_unique_id") or "") or None
        file_name = _clean_text(document.get("file_name"), 255)
        mime_type = _clean_text(document.get("mime_type"), 255)
        file_size = _safe_int(document.get("file_size"))
    elif text is None:
        return None

    reply = message.get("reply_to_message")
    reply_to_message_id = (
        _safe_int(reply.get("message_id"))
        if isinstance(reply, Mapping)
        else None
    )
    first_name = _clean_text(sender.get("first_name"), 80) or ""
    last_name = _clean_text(sender.get("last_name"), 80) or ""
    display_name = " ".join(part for part in (first_name, last_name) if part).strip()
    if not display_name:
        display_name = "Пользователь Telegram"

    return NormalizedTelegramMessage(
        update_id=update_id,
        chat_id=chat_id,
        chat_type=str(chat.get("type") or "").strip().lower(),
        message_id=message_id,
        thread_id=_safe_int(message.get("message_thread_id")),
        from_user_id=user_id,
        from_is_bot=bool(sender.get("is_bot")),
        username=_clean_text(sender.get("username"), 64),
        display_name=display_name,
        message_kind=message_kind,
        text=text,
        caption=caption,
        file_id=file_id,
        file_unique_id=file_unique_id,
        file_name=file_name,
        mime_type=mime_type,
        file_size=file_size,
        reply_to_message_id=reply_to_message_id,
        command=parse_command(text),
    )


def safe_topic_name(public_number: str, source_snapshot: Mapping[str, Any]) -> str:
    title = re.sub(r"[\x00-\x1f\x7f]+", " ", str(source_snapshot.get("title") or ""))
    title = re.sub(r"\s+", " ", title).strip()
    prefix = f"Обращение {str(public_number).strip()}"
    result = f"{prefix} · {title}" if title else prefix
    return result[:128].rstrip()


def canonical_payload_hash(update: Mapping[str, Any]) -> str:
    """Hash an update deterministically without logging its contents."""

    import json

    encoded = json.dumps(
        update,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
