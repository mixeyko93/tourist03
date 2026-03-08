from fastapi import Depends, HTTPException, Request
from psycopg2 import errors

from tourist03.config import SIM_VERIFY_CODE, TERMS_VERSION
from tourist03.db import _db_conn
from tourist03.schemas import (
    LoginStartRequest,
    LoginVerifyRequest,
    RegisterStartRequest,
    SkipEmailRequest,
    UpdateProfileRequest,
    VerifyEmailRequest,
    VerifyPhoneRequest,
)
from tourist03.security import (
    _get_user_by_phone,
    _get_user_by_phone_email,
    _normalize_phone,
    _user_public,
    get_current_user,
    issue_user_token,
    log_user_event,
)


def api_users_list():
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, phone, role, email, email_verified, phone_verified, created_at
            FROM auth.users
            ORDER BY id
            """
        )
        rows = cur.fetchall()
    out = []
    for row in rows:
        data = dict(row)
        if not data.get("email_verified"):
            data["email"] = ""
        out.append(data)
    return out


def auth_register_start(payload: RegisterStartRequest):
    name = (payload.name or "").strip()
    phone = _normalize_phone(payload.phone)
    email = (payload.email or "").strip().lower() if payload.email else ""
    if not name or not phone:
        raise HTTPException(status_code=400, detail="Заполните имя и телефон")
    if payload.accept_terms is not True:
        raise HTTPException(status_code=400, detail="Нужно принять пользовательское соглашение")

    user_id = None
    with _db_conn("auth") as conn:
        if email:
            rows = _get_user_by_phone_email(conn, phone, email)
        else:
            row = _get_user_by_phone(conn, phone)
            rows = [row] if row else []

        rows = [row for row in rows if row]
        ids = {row["id"] for row in rows}
        if len(ids) > 1:
            raise HTTPException(status_code=409, detail="Телефон или email уже используется")

        if rows:
            row = rows[0]
            user_id = row["id"]
            row_email = (row.get("email") or "").strip().lower()
            email_present = bool(row_email)
            complete = bool(row.get("phone_verified")) and (not email_present or bool(row.get("email_verified")))
            if complete:
                raise HTTPException(status_code=409, detail="Пользователь уже зарегистрирован")

            cur = conn.cursor()
            if email:
                cur.execute(
                    """
                    UPDATE auth.users
                    SET name=%s, email=%s, phone_verified=FALSE, email_verified=FALSE
                    WHERE id=%s
                    RETURNING id
                    """,
                    (name, email, row["id"]),
                )
            else:
                cur.execute(
                    """
                    UPDATE auth.users
                    SET name=%s, email=NULL, phone_verified=FALSE, email_verified=FALSE
                    WHERE id=%s
                    RETURNING id
                    """,
                    (name, row["id"]),
                )
            user_id = cur.fetchone()["id"]
            cur.execute(
                """
                UPDATE auth.users
                SET terms_accepted_at=NOW(), terms_version=%s
                WHERE id=%s
                """,
                (TERMS_VERSION, user_id),
            )
            conn.commit()
        else:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO auth.users (
                    name, phone, email, role,
                    phone_verified, email_verified,
                    terms_accepted_at, terms_version
                )
                VALUES (%s, %s, %s, %s, FALSE, FALSE, NOW(), %s)
                RETURNING id
                """,
                (name, phone, email or None, "user", TERMS_VERSION),
            )
            user_id = cur.fetchone()["id"]
            conn.commit()

    log_user_event(
        user_id,
        "register_start",
        {
            "name": name,
            "phone": phone,
            "email": email or None,
            "accept_terms": True,
            "terms_version": TERMS_VERSION,
        },
    )
    return {"ok": True}


def auth_register_verify_phone(payload: VerifyPhoneRequest):
    phone = _normalize_phone(payload.phone)
    code = (payload.code or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Некорректный номер телефона")
    if code != SIM_VERIFY_CODE:
        raise HTTPException(status_code=400, detail="Неверный код")

    user_id = None
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET phone_verified=TRUE
            WHERE phone=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified
            """,
            (phone,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user_id = row["id"]
        conn.commit()

    log_user_event(user_id, "verify_phone", {"phone": phone})
    email_present = bool((row.get("email") or "").strip())
    if not email_present:
        return {"ok": True, "token": issue_user_token(user_id), "user": _user_public(row)}
    return {"ok": True, "user": _user_public(row)}


def auth_register_verify_email(payload: VerifyEmailRequest):
    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Некорректный email")
    if code != SIM_VERIFY_CODE:
        raise HTTPException(status_code=400, detail="Неверный код")

    user_id = None
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET email_verified=TRUE
            WHERE email=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified
            """,
            (email,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user_id = row["id"]
        conn.commit()

    log_user_event(user_id, "verify_email", {"email": email})
    if row.get("phone_verified") and row.get("email_verified"):
        return {"ok": True, "token": issue_user_token(user_id), "user": _user_public(row)}
    return {"ok": True, "user": _user_public(row)}


def auth_register_skip_email(payload: SkipEmailRequest):
    phone = _normalize_phone(payload.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Введите телефон")
    user_id = None
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET email=NULL, email_verified=FALSE, phone_verified=TRUE
            WHERE phone=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified
            """,
            (phone,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user_id = row["id"]
        conn.commit()
    log_user_event(user_id, "skip_email", {"phone": phone})
    return {"ok": True, "token": issue_user_token(user_id), "user": _user_public(row)}


def auth_login_start(payload: LoginStartRequest):
    phone = _normalize_phone(payload.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Введите телефон")
    user_id = None
    with _db_conn("auth") as conn:
        row = _get_user_by_phone(conn, phone)
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user_id = row["id"]
        if not row.get("phone_verified"):
            raise HTTPException(status_code=403, detail="Номер телефона не подтверждён")
        email_present = bool((row.get("email") or "").strip())
        if email_present and not row.get("email_verified"):
            raise HTTPException(status_code=403, detail="Email не подтверждён")
    log_user_event(user_id, "login_start", {"phone": phone})
    return {"ok": True}


def auth_login_verify(payload: LoginVerifyRequest):
    phone = _normalize_phone(payload.phone)
    code = (payload.code or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Введите телефон")
    if code != SIM_VERIFY_CODE:
        raise HTTPException(status_code=400, detail="Неверный код")
    user_id = None
    with _db_conn("auth") as conn:
        row = _get_user_by_phone(conn, phone)
        if not row:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user_id = row["id"]
    log_user_event(user_id, "login_ok", {"phone": phone})
    return {"ok": True, "token": issue_user_token(user_id), "user": _user_public(row)}


def auth_me(user: dict = Depends(get_current_user)):
    return {"ok": True, "user": user}


def auth_logout(request: Request, user: dict = Depends(get_current_user)):
    authz = (request.headers.get("authorization") or "").strip()
    token = authz.split(" ", 1)[1].strip() if " " in authz else ""
    if token:
        try:
            with _db_conn("auth") as conn:
                cur = conn.cursor()
                cur.execute("UPDATE auth.user_tokens SET revoked=TRUE WHERE token=%s", (token,))
                conn.commit()
        except Exception:
            pass
    log_user_event(user["id"], "logout", {})
    return {"ok": True}


def auth_update_profile(payload: UpdateProfileRequest, user: dict = Depends(get_current_user)):
    name = (payload.name or "").strip() if payload.name is not None else None
    phone = _normalize_phone(payload.phone) if payload.phone is not None else None
    email = (str(payload.email).strip().lower() if payload.email is not None else None) if payload.email is not None else None

    need_phone_verify = False
    need_email_verify = False
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, phone, email, phone_verified, email_verified
            FROM auth.users
            WHERE id=%s
            """,
            (user["id"],),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        current = dict(row)

        new_name = name if name is not None else (current.get("name") or "")
        new_phone = phone if phone is not None else (current.get("phone") or "")
        new_email = email if email is not None else ((current.get("email") or "").strip().lower())

        if new_phone != (current.get("phone") or ""):
            need_phone_verify = True
        if (new_email or "") != ((current.get("email") or "").strip().lower()):
            need_email_verify = bool(new_email)

        if new_phone:
            cur.execute(
                "SELECT 1 FROM auth.users WHERE phone=%s AND id<>%s LIMIT 1",
                (new_phone, user["id"]),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Телефон уже используется")
        if new_email:
            cur.execute(
                "SELECT 1 FROM auth.users WHERE lower(email)=lower(%s) AND id<>%s LIMIT 1",
                (new_email, user["id"]),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Email уже используется")

        try:
            cur.execute(
                """
                UPDATE auth.users
                SET name=%s,
                    phone=%s,
                    email=%s,
                    phone_verified=%s,
                    email_verified=%s
                WHERE id=%s
                RETURNING id, name, phone, email, role, phone_verified, email_verified, created_at
                """,
                (
                    new_name,
                    new_phone or None,
                    new_email or None,
                    (False if need_phone_verify else bool(current.get("phone_verified"))),
                    (False if need_email_verify else (bool(current.get("email_verified")) if new_email else False)),
                    user["id"],
                ),
            )
        except errors.UniqueViolation:
            conn.rollback()
            raise HTTPException(status_code=409, detail="Телефон или email уже используется")

        updated = cur.fetchone()
        conn.commit()

    updated_user = dict(updated)
    if not updated_user.get("email_verified"):
        updated_user["email"] = ""

    log_user_event(user["id"], "profile_update", {"name": new_name, "phone": new_phone, "email": new_email or None})
    return {"ok": True, "user": updated_user, "need_phone_verify": need_phone_verify, "need_email_verify": need_email_verify}


def auth_profile_verify_phone(payload: VerifyPhoneRequest, user: dict = Depends(get_current_user)):
    phone = _normalize_phone(payload.phone)
    code = (payload.code or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Некорректный номер телефона")
    if code != SIM_VERIFY_CODE:
        raise HTTPException(status_code=400, detail="Неверный код")
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET phone_verified=TRUE
            WHERE id=%s AND phone=%s
            RETURNING id, name, phone, email, role, phone_verified, email_verified, created_at
            """,
            (user["id"], phone),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        conn.commit()
    data = dict(row)
    if not data.get("email_verified"):
        data["email"] = ""
    log_user_event(user["id"], "profile_verify_phone", {"phone": phone})
    return {"ok": True, "user": data}


def auth_profile_verify_email(payload: VerifyEmailRequest, user: dict = Depends(get_current_user)):
    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Некорректный email")
    if code != SIM_VERIFY_CODE:
        raise HTTPException(status_code=400, detail="Неверный код")
    with _db_conn("auth") as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE auth.users
            SET email_verified=TRUE
            WHERE id=%s AND lower(email)=lower(%s)
            RETURNING id, name, phone, email, role, phone_verified, email_verified, created_at
            """,
            (user["id"], email),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        conn.commit()
    data = dict(row)
    if not data.get("email_verified"):
        data["email"] = ""
    log_user_event(user["id"], "profile_verify_email", {"email": email})
    return {"ok": True, "user": data}
