from fastapi import Depends, HTTPException, Request
from psycopg2 import errors

from tourist03.config import SIM_VERIFY_CODE, TERMS_VERSION
from tourist03.repositories import auth as auth_repo
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
    _normalize_phone,
    _user_public,
    get_current_user,
    issue_user_token,
    log_user_event,
)


def api_users_list():
    rows = auth_repo.list_users()
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

    rows = auth_repo.find_users_for_registration(phone, email)
    ids = {row["id"] for row in rows}
    if len(ids) > 1:
        raise HTTPException(status_code=409, detail="Телефон или email уже используется")

    if rows:
        row = rows[0]
        row_email = (row.get("email") or "").strip().lower()
        email_present = bool(row_email)
        complete = bool(row.get("phone_verified")) and (not email_present or bool(row.get("email_verified")))
        if complete:
            raise HTTPException(status_code=409, detail="Пользователь уже зарегистрирован")
        user_id = auth_repo.update_pending_user(row["id"], name, email, TERMS_VERSION)
    else:
        user_id = auth_repo.create_user(name, phone, email, TERMS_VERSION)

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

    row = auth_repo.verify_phone(phone)
    if not row:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    log_user_event(row["id"], "verify_phone", {"phone": phone})
    email_present = bool((row.get("email") or "").strip())
    if not email_present:
        return {"ok": True, "token": issue_user_token(row["id"]), "user": _user_public(row)}
    return {"ok": True, "user": _user_public(row)}


def auth_register_verify_email(payload: VerifyEmailRequest):
    email = (payload.email or "").strip().lower()
    code = (payload.code or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Некорректный email")
    if code != SIM_VERIFY_CODE:
        raise HTTPException(status_code=400, detail="Неверный код")

    row = auth_repo.verify_email(email)
    if not row:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    log_user_event(row["id"], "verify_email", {"email": email})
    if row.get("phone_verified") and row.get("email_verified"):
        return {"ok": True, "token": issue_user_token(row["id"]), "user": _user_public(row)}
    return {"ok": True, "user": _user_public(row)}


def auth_register_skip_email(payload: SkipEmailRequest):
    phone = _normalize_phone(payload.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Введите телефон")

    row = auth_repo.skip_email(phone)
    if not row:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    log_user_event(row["id"], "skip_email", {"phone": phone})
    return {"ok": True, "token": issue_user_token(row["id"]), "user": _user_public(row)}


def auth_login_start(payload: LoginStartRequest):
    phone = _normalize_phone(payload.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Введите телефон")

    row = auth_repo.find_user_by_phone(phone)
    if not row:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if not row.get("phone_verified"):
        raise HTTPException(status_code=403, detail="Номер телефона не подтверждён")

    email_present = bool((row.get("email") or "").strip())
    if email_present and not row.get("email_verified"):
        raise HTTPException(status_code=403, detail="Email не подтверждён")

    log_user_event(row["id"], "login_start", {"phone": phone})
    return {"ok": True}


def auth_login_verify(payload: LoginVerifyRequest):
    phone = _normalize_phone(payload.phone)
    code = (payload.code or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Введите телефон")
    if code != SIM_VERIFY_CODE:
        raise HTTPException(status_code=400, detail="Неверный код")

    row = auth_repo.find_user_by_phone(phone)
    if not row:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    log_user_event(row["id"], "login_ok", {"phone": phone})
    return {"ok": True, "token": issue_user_token(row["id"]), "user": _user_public(row)}


def auth_me(user: dict = Depends(get_current_user)):
    return {"ok": True, "user": user}


def auth_logout(request: Request, user: dict = Depends(get_current_user)):
    authz = (request.headers.get("authorization") or "").strip()
    token = authz.split(" ", 1)[1].strip() if " " in authz else ""
    if token:
        try:
            auth_repo.revoke_token(token)
        except Exception:
            pass
    log_user_event(user["id"], "logout", {})
    return {"ok": True}


def auth_update_profile(payload: UpdateProfileRequest, user: dict = Depends(get_current_user)):
    name = (payload.name or "").strip() if payload.name is not None else None
    phone = _normalize_phone(payload.phone) if payload.phone is not None else None
    email = (str(payload.email).strip().lower() if payload.email is not None else None) if payload.email is not None else None

    current = auth_repo.get_profile(user["id"])
    if not current:
        raise HTTPException(status_code=404, detail="not found")

    new_name = name if name is not None else (current.get("name") or "")
    new_phone = phone if phone is not None else (current.get("phone") or "")
    new_email = email if email is not None else ((current.get("email") or "").strip().lower())

    need_phone_verify = new_phone != (current.get("phone") or "")
    need_email_verify = (new_email or "") != ((current.get("email") or "").strip().lower()) and bool(new_email)

    if new_phone and auth_repo.phone_in_use(new_phone, user["id"]):
        raise HTTPException(status_code=409, detail="Телефон уже используется")
    if new_email and auth_repo.email_in_use(new_email, user["id"]):
        raise HTTPException(status_code=409, detail="Email уже используется")

    try:
        updated_user = auth_repo.update_profile(
            user["id"],
            new_name,
            new_phone,
            new_email,
            False if need_phone_verify else bool(current.get("phone_verified")),
            False if need_email_verify else (bool(current.get("email_verified")) if new_email else False),
        )
    except errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Телефон или email уже используется")

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

    data = auth_repo.verify_profile_phone(user["id"], phone)
    if not data:
        raise HTTPException(status_code=404, detail="not found")
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

    data = auth_repo.verify_profile_email(user["id"], email)
    if not data:
        raise HTTPException(status_code=404, detail="not found")
    if not data.get("email_verified"):
        data["email"] = ""

    log_user_event(user["id"], "profile_verify_email", {"email": email})
    return {"ok": True, "user": data}
