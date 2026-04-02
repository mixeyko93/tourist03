import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException, Request, status
from passlib.context import CryptContext

from tourist03.config import SUPERADMIN_API_KEY, SUPERADMIN_LOCAL_BYPASS, SUPERADMIN_LOGIN, SUPERADMIN_PASSWORD, logger
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


def log_crm_audit_event(
    *,
    actor_type: str,
    action_type: str,
    action_label: str,
    target_type: str,
    actor_id: Optional[int] = None,
    actor_display: Optional[str] = None,
    camp_id: Optional[int] = None,
    target_id: Optional[Any] = None,
    changed_field: Optional[str] = None,
    old_value=None,
    new_value=None,
    comment: Optional[str] = None,
    is_sensitive: bool = False,
    was_auto_applied: bool = False,
    metadata: Optional[dict] = None,
) -> None:
    if not actor_type or not action_type or not action_label or not target_type:
        return
    try:
        with _db_conn("crm") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO crm.audit_log (
                    actor_type,
                    actor_id,
                    actor_display,
                    camp_id,
                    target_type,
                    target_id,
                    action_type,
                    action_label,
                    changed_field,
                    old_value,
                    new_value,
                    comment,
                    is_sensitive,
                    was_auto_applied,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s::jsonb)
                """,
                (
                    actor_type,
                    actor_id,
                    actor_display,
                    camp_id,
                    target_type,
                    str(target_id) if target_id is not None else None,
                    action_type,
                    action_label,
                    changed_field,
                    json.dumps(old_value, ensure_ascii=False) if old_value is not None else None,
                    json.dumps(new_value, ensure_ascii=False) if new_value is not None else None,
                    comment,
                    bool(is_sensitive),
                    bool(was_auto_applied),
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            conn.commit()
    except Exception:
        pass


def create_notification_event(
    *,
    event_type: str,
    title: str,
    body: str,
    channel: str = "in_app",
    recipient_scope: str = "crm",
    recipient_admin_id: Optional[int] = None,
    recipient_role_key: Optional[str] = None,
    camp_id: Optional[int] = None,
    action_url: Optional[str] = None,
    action_payload: Optional[dict] = None,
    severity: str = "info",
    metadata: Optional[dict] = None,
) -> None:
    if not event_type or not title or not body:
        return
    try:
        with _db_conn("crm") as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO crm.notification_events (
                    camp_id,
                    recipient_scope,
                    recipient_admin_id,
                    recipient_role_key,
                    channel,
                    event_type,
                    title,
                    body,
                    action_url,
                    action_payload,
                    severity,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)
                """,
                (
                    camp_id,
                    recipient_scope,
                    recipient_admin_id,
                    recipient_role_key,
                    channel,
                    event_type,
                    title,
                    body,
                    action_url,
                    json.dumps(action_payload or {}, ensure_ascii=False),
                    severity,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            conn.commit()
    except Exception:
        pass


def issue_admin_telegram_link_code(admin_id: int, *, ttl_minutes: int = 15) -> str:
    if not admin_id:
        raise ValueError("admin_id is required")
    code = secrets.token_urlsafe(12)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=max(int(ttl_minutes or 15), 1))
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.camp_admin_accounts
            SET telegram_link_code = %s,
                telegram_link_code_expires_at = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (code, expires_at, int(admin_id)),
        )
        conn.commit()
    return code


def issue_superadmin_telegram_link_code(account_id: int, *, ttl_minutes: int = 15) -> str:
    if not account_id:
        raise ValueError("account_id is required")
    code = f"sa_{secrets.token_urlsafe(12)}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=max(int(ttl_minutes or 15), 1))
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.superadmin_accounts
            SET telegram_link_code = %s,
                telegram_link_code_expires_at = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (code, expires_at, int(account_id)),
        )
        conn.commit()
    return code


def link_admin_telegram_account(
    code: str,
    *,
    telegram_user_id: int,
    telegram_chat_id: int,
    telegram_username: Optional[str] = None,
) -> Optional[dict]:
    token = (code or "").strip()
    if not token:
        return None
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email, display_name, telegram_link_code_expires_at
            FROM auth.camp_admin_accounts
            WHERE telegram_link_code = %s
              AND archived_at IS NULL
              AND is_active = TRUE
            """,
            (token,),
        )
        row = cur.fetchone()
        if not row:
            return None

        expires_at = row.get("telegram_link_code_expires_at")
        if expires_at is None or expires_at < datetime.now(timezone.utc):
            return None

        cur.execute(
            """
            UPDATE auth.camp_admin_accounts
            SET telegram_user_id = %s,
                telegram_chat_id = %s,
                telegram_username = %s,
                telegram_link_code = NULL,
                telegram_link_code_expires_at = NULL,
                updated_at = NOW()
            WHERE id = %s
            """,
            (int(telegram_user_id), int(telegram_chat_id), (telegram_username or "").strip() or None, row["id"]),
        )
        conn.commit()
        return {"id": row["id"], "email": row["email"], "display_name": row["display_name"]}


def link_superadmin_telegram_account(
    code: str,
    *,
    telegram_user_id: int,
    telegram_chat_id: int,
    telegram_username: Optional[str] = None,
) -> Optional[dict]:
    token = (code or "").strip()
    if not token:
        return None
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, login, display_name, telegram_link_code_expires_at
            FROM auth.superadmin_accounts
            WHERE telegram_link_code = %s
              AND archived_at IS NULL
              AND is_active = TRUE
            """,
            (token,),
        )
        row = cur.fetchone()
        if not row:
            return None

        expires_at = row.get("telegram_link_code_expires_at")
        if expires_at is None or expires_at < datetime.now(timezone.utc):
            return None

        cur.execute(
            """
            UPDATE auth.superadmin_accounts
            SET telegram_user_id = %s,
                telegram_chat_id = %s,
                telegram_username = %s,
                telegram_link_code = NULL,
                telegram_link_code_expires_at = NULL,
                updated_at = NOW()
            WHERE id = %s
            """,
            (int(telegram_user_id), int(telegram_chat_id), (telegram_username or "").strip() or None, row["id"]),
        )
        conn.commit()
        return {"id": row["id"], "login": row["login"], "display_name": row["display_name"]}


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
            SELECT id, email, display_name, phone, default_role_key, telegram_chat_id
            FROM auth.camp_admin_accounts
            WHERE id = %s AND is_active = TRUE
            """,
            (admin_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "phone": row.get("phone") or "",
        "default_role_key": row.get("default_role_key") or "administrator",
        "telegram_chat_id": row.get("telegram_chat_id"),
    }


def _get_admin_camp_ids(admin_id: int) -> list[int]:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT camp_id FROM crm.camp_admin_links WHERE admin_id = %s",
            (admin_id,),
        )
        return [row["camp_id"] for row in cur.fetchall()]


def _superadmin_public(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    return {
        "id": row.get("id"),
        "login": row.get("login") or "",
        "display_name": row.get("display_name") or "",
        "is_root": bool(row.get("is_root")),
        "is_active": bool(row.get("is_active", True)),
        "telegram_chat_id": row.get("telegram_chat_id"),
        "telegram_username": row.get("telegram_username") or None,
        "has_telegram_link": bool(row.get("telegram_chat_id")),
    }


def _get_superadmin_account_by_id(account_id: int) -> Optional[dict]:
    with _db_conn("crm") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                login,
                password_hash,
                display_name,
                phone,
                is_active,
                is_root,
                telegram_user_id,
                telegram_chat_id,
                telegram_username,
                telegram_link_code,
                telegram_link_code_expires_at,
                created_by_id,
                archived_at,
                created_at,
                updated_at
            FROM auth.superadmin_accounts
            WHERE id = %s
            """,
            (int(account_id),),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_superadmin_session_principal(request: Request) -> Optional[dict]:
    superadmin_id = request.session.get("superadmin_account_id")
    if superadmin_id:
        row = _get_superadmin_account_by_id(int(superadmin_id))
        if row and row.get("archived_at") is None and bool(row.get("is_active")):
            request.session["superadmin"] = True
            return _superadmin_public(row)

        request.session.pop("superadmin_account_id", None)
        request.session.pop("superadmin", None)

    session_principal = request.session.get("superadmin_principal")
    if isinstance(session_principal, dict) and session_principal.get("login"):
        request.session["superadmin"] = True
        return {
            "id": session_principal.get("id"),
            "login": session_principal.get("login") or "",
            "display_name": session_principal.get("display_name") or "",
            "is_root": bool(session_principal.get("is_root")),
            "is_active": bool(session_principal.get("is_active", True)),
        }

    if is_local_superadmin_bypass(request):
        request.session["superadmin"] = True
        return {
            "id": None,
            "login": "local-bypass",
            "display_name": "Локальный суперадмин",
            "is_root": True,
            "is_active": True,
        }

    header_token = extract_superadmin_header_token(request)
    if is_valid_superadmin_key(header_token):
        request.session["superadmin"] = True
        return {
            "id": None,
            "login": "api-key",
            "display_name": "API суперадмин",
            "is_root": True,
            "is_active": True,
        }

    return None


def extract_superadmin_header_token(request: Request) -> str:
    return (
        request.headers.get("x-superadmin-key")
        or request.headers.get("x-superadmin-token")
        or (
            request.headers.get("authorization", "").split(" ", 1)[1].strip()
            if request.headers.get("authorization", "").lower().startswith("bearer ")
            else ""
        )
    )


def is_valid_superadmin_key(token: str) -> bool:
    candidate = (token or "").strip()
    return bool(SUPERADMIN_API_KEY and candidate and secrets.compare_digest(candidate, SUPERADMIN_API_KEY))


def superadmin_credentials_required() -> bool:
    return bool((SUPERADMIN_LOGIN or "").strip() or (SUPERADMIN_PASSWORD or ""))


def is_valid_superadmin_credentials(login: str, password: str) -> bool:
    expected_login = (SUPERADMIN_LOGIN or "").strip()
    expected_password = SUPERADMIN_PASSWORD or ""
    if not superadmin_credentials_required():
        return True

    candidate_login = (login or "").strip()
    candidate_password = password or ""
    return bool(
        expected_login
        and expected_password
        and candidate_login
        and secrets.compare_digest(candidate_login, expected_login)
        and secrets.compare_digest(candidate_password, expected_password)
    )


def is_local_superadmin_bypass(request: Request) -> bool:
    if not SUPERADMIN_LOCAL_BYPASS:
        return False
    if SUPERADMIN_API_KEY:
        return False
    try:
        client_host = (request.client.host or "").strip().lower() if request and request.client else ""
    except Exception:
        client_host = ""
    return client_host in {"127.0.0.1", "::1", "localhost"}


def get_superadmin(request: Request):
    principal = get_superadmin_session_principal(request)
    if principal:
        return principal
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нет доступа")


def get_root_superadmin(request: Request):
    principal = get_superadmin(request)
    if not principal.get("is_root"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    return principal


__all__ = [
    "_get_admin_camp_ids",
    "_get_user_by_phone",
    "_get_user_by_phone_email",
    "_normalize_phone",
    "_user_public",
    "get_current_admin",
    "get_current_user",
    "get_superadmin",
    "get_root_superadmin",
    "get_superadmin_session_principal",
    "is_valid_superadmin_credentials",
    "superadmin_credentials_required",
    "hash_password",
    "extract_superadmin_header_token",
    "create_notification_event",
    "is_valid_superadmin_key",
    "issue_user_token",
    "issue_admin_telegram_link_code",
    "issue_superadmin_telegram_link_code",
    "link_admin_telegram_account",
    "link_superadmin_telegram_account",
    "log_crm_audit_event",
    "log_user_event",
    "verify_password",
    "is_local_superadmin_bypass",
    "_superadmin_public",
    "_get_superadmin_account_by_id",
]
