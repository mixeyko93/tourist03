"""Security primitives for the isolated Owner Portal identity system."""

from __future__ import annotations

import hashlib
import hmac
import base64
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, Request, status

from tourist03.db import _db_conn


OWNER_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_owner_email(value: str) -> str:
    return (value or "").strip().casefold()


def validate_owner_email(value: str) -> str:
    email = normalize_owner_email(value)
    if not EMAIL_RE.fullmatch(email) or len(email) > 320:
        raise ValueError("Укажите корректный email")
    return email


def validate_owner_password(value: str) -> str:
    password = value or ""
    if len(password) < 12:
        raise ValueError("Пароль должен содержать не менее 12 символов")
    if len(password) > 256:
        raise ValueError("Пароль слишком длинный")
    if not re.search(r"[A-Za-zА-Яа-яЁё]", password) or not re.search(r"\d", password):
        raise ValueError("Пароль должен содержать буквы и цифры")
    return password


def hash_owner_password(password: str) -> str:
    return OWNER_PASSWORD_HASHER.hash(validate_owner_password(password))


def verify_owner_password(password: str, password_hash: str) -> bool:
    try:
        return bool(OWNER_PASSWORD_HASHER.verify(password_hash or "", password or ""))
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def owner_password_needs_rehash(password_hash: str) -> bool:
    try:
        return OWNER_PASSWORD_HASHER.check_needs_rehash(password_hash or "")
    except InvalidHashError:
        return True


def new_owner_reset_token() -> str:
    return secrets.token_urlsafe(40)


def owner_reset_token_for(reset_id: int, owner_id: int, expires_at: datetime, secret: str) -> str:
    """Create a reproducible token so the outbox never stores the bearer value."""
    normalized_expiry = expires_at.astimezone(timezone.utc).isoformat()
    digest = hmac.new(
        (secret or "").encode("utf-8"),
        f"owner-reset\0{int(reset_id)}\0{int(owner_id)}\0{normalized_expiry}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def hash_owner_token(value: str, secret: str) -> str:
    return hmac.new(
        (secret or "").encode("utf-8"),
        (value or "").encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_owner_technical_value(value: str, secret: str) -> str | None:
    normalized = (value or "").strip()
    return hash_owner_token(normalized, secret) if normalized else None


def owner_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "email": row.get("email") or "",
        "display_name": row.get("display_name") or "",
        "company": row.get("company"),
        "phone": row.get("phone"),
        "telegram": row.get("telegram"),
        "whatsapp": row.get("whatsapp"),
        "max": row.get("max"),
        "preferred_contact_type": row.get("preferred_contact_type"),
        "account_status": row.get("account_status") or "active",
        "two_factor_status": row.get("two_factor_status") or "disabled",
        "last_login": row.get("last_login"),
        "created_at": row.get("created_at"),
    }


def get_owner_session_principal(request: Request) -> dict[str, Any] | None:
    owner_id = request.session.get("owner_account_id")
    if not owner_id:
        return None
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM auth.owner_accounts
            WHERE id = %s
              AND is_active = TRUE
              AND account_status = 'active'
            LIMIT 1
            """,
            (int(owner_id),),
        )
        row = cur.fetchone()
    if row:
        return owner_public(dict(row))
    request.session.pop("owner_account_id", None)
    request.session.pop("csrf_token", None)
    return None


def get_current_owner(request: Request) -> dict[str, Any]:
    owner = get_owner_session_principal(request)
    if owner:
        return owner
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Войдите в кабинет владельца")


def reset_owner_session(request: Request, owner_id: int | None = None) -> None:
    request.session.clear()
    if owner_id is not None:
        request.session["owner_account_id"] = int(owner_id)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "get_current_owner",
    "get_owner_session_principal",
    "hash_owner_password",
    "hash_owner_technical_value",
    "hash_owner_token",
    "new_owner_reset_token",
    "normalize_owner_email",
    "owner_password_needs_rehash",
    "owner_public",
    "owner_reset_token_for",
    "reset_owner_session",
    "utc_now",
    "validate_owner_email",
    "validate_owner_password",
    "verify_owner_password",
]
