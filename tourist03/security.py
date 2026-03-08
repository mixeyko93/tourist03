import json
import re
import secrets
from typing import Optional

from fastapi import HTTPException, Request, status
from passlib.context import CryptContext

from tourist03.config import SUPERADMIN_API_KEY, logger
from tourist03.db import _db_conn


pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)


def _normalize_phone(phone: str) -> str:
    phone = (phone or "").strip()
    if not phone:
        return ""
    s = re.sub(r"[^\d+]", "", phone)
    if not s:
        return ""
    if s.startswith("+"):
        s = "+" + re.sub(r"[^\d]", "", s[1:])
        if s.startswith("+8"):
            s = "+7" + s[2:]
        return s

    digits = re.sub(r"[^\d]", "", s)
    if not digits:
        return ""
    if digits.startswith("8"):
        return "+7" + digits[1:]
    if digits.startswith("9"):
        return "+7" + digits
    if digits.startswith("7"):
        return "+" + digits
    return digits


def _get_user_by_phone_email(conn, phone: str, email: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, phone, email, role, phone_verified, email_verified
        FROM auth.users
        WHERE phone = %s OR email = %s
        """,
        (phone, email),
    )
    return cur.fetchall()


def _get_user_by_phone(conn, phone: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, phone, email, role, phone_verified, email_verified
        FROM auth.users
        WHERE phone = %s
        """,
        (phone,),
    )
    return cur.fetchone()


def _user_public(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "name": row.get("name") or "",
        "phone": row.get("phone") or "",
        "email": row.get("email") or "",
        "role": row.get("role") or "user",
        "phone_verified": bool(row.get("phone_verified")),
        "email_verified": bool(row.get("email_verified")),
    }


def log_user_event(user_id: int, event_type: str, payload: Optional[dict] = None) -> None:
    if not user_id or not event_type:
        return
    try:
        with _db_conn("auth") as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO auth.user_events (user_id, event_type, payload) VALUES (%s, %s, %s::jsonb)",
                (int(user_id), str(event_type), json.dumps(payload or {}, ensure_ascii=False)),
            )
            conn.commit()
    except Exception:
        pass


def issue_user_token(user_id: int) -> str:
    token = secrets.token_urlsafe(24)
    try:
        with _db_conn("auth") as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO auth.user_tokens (token, user_id) VALUES (%s, %s)",
                (token, int(user_id)),
            )
            conn.commit()
    except Exception:
        pass
    return token


def get_current_user(request: Request) -> dict:
    authz = (request.headers.get("authorization") or "").strip()
    if not authz.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    token = authz.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.id, u.name, u.phone, u.email, u.role, u.phone_verified, u.email_verified, u.created_at
            FROM auth.user_tokens t
            JOIN auth.users u ON u.id = t.user_id
            WHERE t.token = %s AND t.revoked = FALSE
            """,
            (token,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
        user = dict(row)
        if not user.get("email_verified"):
            user["email"] = ""
        return user


def hash_password(password: str) -> str:
    if password is None:
        password = ""
    try:
        raw = str(password).encode("utf-8", errors="ignore")
        if len(raw) > 72:
            raw = raw[:72]
            password = raw.decode("utf-8", errors="ignore")
        return pwd_context.hash(password)
    except Exception:
        logger.exception("Error hashing password")
        raise


def verify_password(password: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(password, hashed)
    except Exception:
        return False


def get_current_admin(request: Request):
    admin_id = request.session.get("admin_id")
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email, display_name
            FROM auth.camp_admin_accounts
            WHERE id = %s AND is_active = TRUE
            """,
            (admin_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}


def _get_admin_camp_ids(admin_id: int) -> list[int]:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT camp_id FROM crm.camp_admin_links WHERE admin_id = %s",
            (admin_id,),
        )
        return [row["camp_id"] for row in cur.fetchall()]


def get_superadmin(request: Request):
    if request.session.get("superadmin") is True:
        return True
    if not SUPERADMIN_API_KEY:
        return True
    header_token = request.headers.get("x-superadmin-key") or request.headers.get("x-superadmin-token")
    if header_token == SUPERADMIN_API_KEY:
        return True
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нет доступа")


__all__ = [
    "_get_admin_camp_ids",
    "_get_user_by_phone",
    "_get_user_by_phone_email",
    "_normalize_phone",
    "_user_public",
    "get_current_admin",
    "get_current_user",
    "get_superadmin",
    "hash_password",
    "issue_user_token",
    "log_user_event",
    "verify_password",
]
