from typing import Optional

from fastapi import HTTPException, Request

from tourist03.config import logger
from tourist03.repositories import superadmin as superadmin_repo
from tourist03.schemas import (
    SuperAdminCreateAccountRequest,
    SuperAdminLoginRequest,
    SuperAdminUpdateAccountRequest,
)
from tourist03.security import (
    extract_superadmin_header_token,
    hash_password,
    is_valid_superadmin_credentials,
    is_local_superadmin_bypass,
    is_valid_superadmin_key,
    superadmin_credentials_required,
)


def superadmin_session(request: Request):
    if request.session.get("superadmin") is True:
        return {"ok": True, "authenticated": True}

    if is_local_superadmin_bypass(request):
        request.session["superadmin"] = True
        return {"ok": True, "authenticated": True}

    header_token = extract_superadmin_header_token(request)
    if is_valid_superadmin_key(header_token):
        request.session["superadmin"] = True
        return {"ok": True, "authenticated": True}

    return {"ok": True, "authenticated": False}


def superadmin_login(payload: SuperAdminLoginRequest, request: Request):
    if is_local_superadmin_bypass(request):
        request.session["superadmin"] = True
        return {"ok": True, "authenticated": True}

    if superadmin_credentials_required():
        if not is_valid_superadmin_credentials(payload.login or "", payload.password or ""):
            raise HTTPException(status_code=401, detail="Нет доступа")
    elif not is_valid_superadmin_key(payload.key or ""):
        raise HTTPException(status_code=401, detail="Нет доступа")

    request.session["superadmin"] = True
    return {"ok": True, "authenticated": True}


def superadmin_logout(request: Request):
    request.session.pop("superadmin", None)
    return {"ok": True, "authenticated": False}


def superadmin_user_history(user_id: int):
    user = superadmin_repo.get_user_history_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="not found")

    events = superadmin_repo.get_user_events(user_id)
    bookings = superadmin_repo.get_user_bookings(user_id)
    if not user.get("email_verified"):
        user["email"] = ""

    return {"user": user, "bookings": bookings, "events": events, "payments": []}


def superadmin_list_camps(status: Optional[str] = None, archived_only: bool = False, search: Optional[str] = None):
    return superadmin_repo.list_camps(status=status, archived_only=archived_only, search=search)


def superadmin_camp_editor(camp_id: int):
    item = superadmin_repo.get_camp_editor_context(camp_id)
    if not item:
        raise HTTPException(status_code=404, detail="База не найдена")
    return item


def create_camp_admin_account(payload: SuperAdminCreateAccountRequest):
    email = payload.email.lower().strip()
    display_name = (payload.display_name or "").strip() or email
    password_raw = (payload.password or "").strip()
    if not password_raw:
        raise HTTPException(status_code=400, detail="Пароль не может быть пустым")

    logger.info("Запрос на создание учётки управляющего: email=%s, camps=%s", email, payload.camp_ids)
    if superadmin_repo.find_admin_account_by_email(email):
        logger.warning("Попытка создать дубликат учётки для email=%s", email)
        raise HTTPException(status_code=400, detail="Учётная запись с таким логином уже существует")

    password_hash = hash_password(password_raw)
    try:
        admin_id = superadmin_repo.create_admin_account(email, password_hash, display_name, payload.camp_ids)
    except Exception:
        logger.exception("Техническая ошибка при создании учётки email=%s", email)
        raise

    logger.info("Учётка управляющего создана: id=%s, email=%s", admin_id, email)
    return {"status": "ok", "admin_id": admin_id}


def update_camp_admin_account(account_id: int, payload: SuperAdminUpdateAccountRequest):
    email = payload.email.lower().strip() if payload.email is not None else None
    display_name = (payload.display_name or "").strip() if payload.display_name is not None else None
    password_raw = (payload.password or "").strip() if payload.password is not None else None
    is_active = payload.is_active
    camp_ids = payload.camp_ids if payload.camp_ids is not None else None

    if email is not None and not email:
        raise HTTPException(status_code=400, detail="Email не может быть пустым")
    if display_name is not None and not display_name:
        raise HTTPException(status_code=400, detail="Имя управляющего не может быть пустым")

    existing = superadmin_repo.get_admin_account(account_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Учётная запись не найдена")

    next_email = None
    if email is not None and email != (existing.get("email") or "").lower().strip():
        if superadmin_repo.admin_email_exists(email, account_id):
            raise HTTPException(status_code=409, detail="Учётная запись с таким email уже существует")
        next_email = email

    next_display_name = None
    if display_name is not None and display_name != (existing.get("display_name") or ""):
        next_display_name = display_name

    next_password_hash = hash_password(password_raw) if password_raw else None

    next_is_active = None
    if is_active is not None and bool(is_active) != bool(existing.get("is_active")):
        next_is_active = bool(is_active)

    try:
        superadmin_repo.update_admin_account(
            account_id,
            email=next_email,
            display_name=next_display_name,
            password_hash=next_password_hash,
            is_active=next_is_active,
            camp_ids=camp_ids,
        )
    except Exception:
        logger.exception("Техническая ошибка при обновлении учётки id=%s", account_id)
        raise

    logger.info("Учётка управляющего обновлена: id=%s", account_id)
    return {"ok": True}


def superadmin_list_accounts():
    return superadmin_repo.list_accounts()


def superadmin_list_users(search: Optional[str] = None):
    return superadmin_repo.list_users(search=search)


def superadmin_list_events(search: Optional[str] = None, camp_id: Optional[int] = None, limit: int = 20):
    return superadmin_repo.list_recent_events(search=search, camp_id=camp_id, limit=limit)
