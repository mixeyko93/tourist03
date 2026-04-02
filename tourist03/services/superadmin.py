from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request, status

from tourist03.config import SUPERADMIN_LOGIN, logger
from tourist03.repositories import catalog as catalog_repo
from tourist03.repositories import superadmin as superadmin_repo
from tourist03.schemas import (
    SuperAdminCreateAccountRequest,
    SuperAdminCreateSuperadminRequest,
    SuperAdminLoginRequest,
    SuperAdminMediaModerationRequest,
    SuperAdminUpdateAccountRequest,
    SuperAdminUpdateSuperadminRequest,
)
from tourist03.security import (
    extract_superadmin_header_token,
    get_root_superadmin,
    get_superadmin_session_principal,
    hash_password,
    issue_superadmin_telegram_link_code,
    is_valid_superadmin_credentials,
    is_local_superadmin_bypass,
    is_valid_superadmin_key,
    log_crm_audit_event,
    superadmin_credentials_required,
    verify_password,
)


def _set_superadmin_session(request: Request, principal: Optional[dict]):
    if principal and principal.get("id") is not None:
        request.session["superadmin"] = True
        request.session["superadmin_account_id"] = int(principal["id"])
        request.session.pop("superadmin_principal", None)
    else:
        request.session["superadmin"] = True
        request.session.pop("superadmin_account_id", None)
        request.session["superadmin_principal"] = principal or {}


def _clear_superadmin_session(request: Request):
    request.session.pop("superadmin", None)
    request.session.pop("superadmin_account_id", None)
    request.session.pop("superadmin_principal", None)


def _bootstrap_root_superadmin(login: str, password: str) -> Optional[dict]:
    if not superadmin_credentials_required():
        return None
    if not is_valid_superadmin_credentials(login, password):
        return None
    normalized_login = (SUPERADMIN_LOGIN or login or "").strip().lower()
    if not normalized_login:
        return None
    return superadmin_repo.upsert_bootstrap_superadmin(
        login=normalized_login,
        password_hash=hash_password(password),
        display_name="Главный суперадминистратор",
    )


def _serialize_session(principal: Optional[dict]):
    return {
        "ok": True,
        "authenticated": bool(principal),
        "account": principal,
    }


def _principal_public(account: dict | None) -> dict | None:
    if not account:
        return None
    return {
        "id": account.get("id"),
        "login": account.get("login") or "",
        "display_name": account.get("display_name") or "",
        "is_root": bool(account.get("is_root")),
        "is_active": bool(account.get("is_active")),
        "telegram_chat_id": account.get("telegram_chat_id"),
        "telegram_username": account.get("telegram_username") or None,
        "has_telegram_link": bool(account.get("telegram_chat_id")),
    }


def superadmin_session(request: Request):
    return _serialize_session(get_superadmin_session_principal(request))


def superadmin_login(payload: SuperAdminLoginRequest, request: Request):
    if is_local_superadmin_bypass(request):
        principal = get_superadmin_session_principal(request)
        _set_superadmin_session(request, principal)
        return _serialize_session(principal)

    login = (payload.login or "").strip().lower()
    password = payload.password or ""
    account = superadmin_repo.get_superadmin_account_by_login(login) if login else None

    if account and account.get("archived_at") is None and bool(account.get("is_active")) and verify_password(password, account.get("password_hash") or ""):
        principal = _principal_public(account)
        _set_superadmin_session(request, principal)
        log_crm_audit_event(
            actor_type="superadmin",
            actor_id=account["id"],
            actor_display=principal["display_name"] or principal["login"],
            target_type="superadmin_session",
            target_id=account["id"],
            action_type="login",
            action_label="Вход в superadmin",
        )
        return _serialize_session(principal)

    bootstrap_account = _bootstrap_root_superadmin(login, password)
    if bootstrap_account:
        principal = _principal_public(bootstrap_account)
        _set_superadmin_session(request, principal)
        log_crm_audit_event(
            actor_type="superadmin",
            actor_id=bootstrap_account["id"],
            actor_display=principal["display_name"] or principal["login"],
            target_type="superadmin_account",
            target_id=bootstrap_account["id"],
            action_type="bootstrap",
            action_label="Инициализирован root-superadmin",
            metadata={"login": principal["login"]},
        )
        return _serialize_session(principal)

    if is_valid_superadmin_key(payload.key or ""):
        principal = {
            "id": None,
            "login": "api-key",
            "display_name": "API суперадмин",
            "is_root": True,
            "is_active": True,
        }
        _set_superadmin_session(request, principal)
        return _serialize_session(principal)

    raise HTTPException(status_code=401, detail="Нет доступа")


def superadmin_logout(request: Request):
    principal = get_superadmin_session_principal(request)
    if principal and principal.get("id") is not None:
        log_crm_audit_event(
            actor_type="superadmin",
            actor_id=principal["id"],
            actor_display=principal.get("display_name") or principal.get("login"),
            target_type="superadmin_session",
            target_id=principal["id"],
            action_type="logout",
            action_label="Выход из superadmin",
        )
    _clear_superadmin_session(request)
    return _serialize_session(None)


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


def superadmin_list_media_queue(search: Optional[str] = None, status: Optional[str] = None, limit: int = 120):
    return catalog_repo.list_public_media_queue(search=search, status=status, limit=limit)


def superadmin_update_media_moderation(entity_type: str, media_id: int, payload: SuperAdminMediaModerationRequest, request: Request):
    actor = get_superadmin_session_principal(request) or {}
    superadmin_update_media_moderation_by_account(
        actor,
        entity_type=entity_type,
        media_id=media_id,
        status_value=payload.status,
        comment=payload.comment,
    )
    return {"ok": True}


def superadmin_issue_telegram_link(request: Request):
    principal = get_superadmin_session_principal(request) or {}
    account_id = principal.get("id")
    if not account_id:
        raise HTTPException(status_code=400, detail="Эта superadmin-сессия не поддерживает Telegram-привязку")
    code = issue_superadmin_telegram_link_code(int(account_id))
    from tourist03.config import STAFF_BOT_USERNAME

    deep_link = f"https://t.me/{STAFF_BOT_USERNAME}?start={code}" if STAFF_BOT_USERNAME else None
    log_crm_audit_event(
        actor_type="superadmin",
        actor_id=principal.get("id"),
        actor_display=principal.get("display_name") or principal.get("login"),
        target_type="superadmin_account",
        target_id=account_id,
        action_type="superadmin_telegram_link_issue",
        action_label="Сгенерировал код привязки Telegram",
        was_auto_applied=True,
    )
    return {"ok": True, "code": code, "command": f"/start {code}", "deep_link": deep_link}


def superadmin_update_media_moderation_by_account(
    account: dict,
    *,
    entity_type: str,
    media_id: int,
    status_value: str,
    comment: Optional[str] = None,
):
    current = catalog_repo.get_public_media_item(entity_type, media_id)
    if not current:
        raise HTTPException(status_code=404, detail="Медиаматериал не найден")

    next_status = (status_value or "").strip().lower()
    if next_status not in {"pending", "approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Недопустимый статус модерации")

    catalog_repo.update_public_media_moderation(
        entity_type,
        media_id,
        moderation_status=next_status,
        moderation_comment=(comment or "").strip() or None,
        approved_by_superadmin_id=account.get("id"),
    )
    updated = catalog_repo.get_public_media_item(entity_type, media_id)
    log_crm_audit_event(
        actor_type="superadmin",
        actor_id=account.get("id"),
        actor_display=account.get("display_name") or account.get("login"),
        camp_id=current.get("camp_id"),
        target_type="public_media",
        target_id=f"{entity_type}:{media_id}",
        action_type="moderation",
        action_label="Изменён статус модерации контента",
        old_value={
            "moderation_status": current.get("moderation_status"),
            "moderation_comment": current.get("moderation_comment"),
        },
        new_value={
            "moderation_status": updated.get("moderation_status") if updated else next_status,
            "moderation_comment": updated.get("moderation_comment") if updated else (comment or "").strip() or None,
            "entity_type": entity_type,
            "media_type": current.get("media_type"),
            "url": current.get("url"),
        },
    )
    return updated or {"ok": True}


def superadmin_list_root_accounts(request: Request, include_archived: bool = False):
    get_root_superadmin(request)
    return superadmin_repo.list_superadmin_accounts(include_archived=include_archived)


def create_root_superadmin_account(payload: SuperAdminCreateSuperadminRequest, request: Request):
    actor = get_root_superadmin(request)
    login = (payload.login or "").strip().lower()
    display_name = (payload.display_name or "").strip()
    password_raw = (payload.password or "").strip()
    phone = (payload.phone or "").strip() or None

    if not login:
        raise HTTPException(status_code=400, detail="Логин не может быть пустым")
    if not display_name:
        raise HTTPException(status_code=400, detail="Имя суперадмина не может быть пустым")
    if not password_raw:
        raise HTTPException(status_code=400, detail="Пароль не может быть пустым")
    if superadmin_repo.superadmin_login_exists(login):
        raise HTTPException(status_code=409, detail="Суперадмин с таким логином уже существует")

    superadmin_id = superadmin_repo.create_superadmin_account(
        login=login,
        password_hash=hash_password(password_raw),
        display_name=display_name,
        phone=phone,
        is_active=bool(payload.is_active),
        is_root=bool(payload.is_root),
        created_by_id=actor.get("id"),
    )
    log_crm_audit_event(
        actor_type="superadmin",
        actor_id=actor.get("id"),
        actor_display=actor.get("display_name") or actor.get("login"),
        target_type="superadmin_account",
        target_id=superadmin_id,
        action_type="create",
        action_label="Создана учётка суперадмина",
        new_value={
            "login": login,
            "display_name": display_name,
            "phone": phone,
            "is_active": bool(payload.is_active),
            "is_root": bool(payload.is_root),
        },
    )
    return {"status": "ok", "superadmin_id": superadmin_id}


def update_root_superadmin_account(account_id: int, payload: SuperAdminUpdateSuperadminRequest, request: Request):
    actor = get_root_superadmin(request)
    existing = superadmin_repo.get_superadmin_account_by_id(account_id)
    if not existing or existing.get("archived_at") is not None:
        raise HTTPException(status_code=404, detail="Учётная запись суперадмина не найдена")

    login = (payload.login or "").strip().lower() if payload.login is not None else None
    display_name = (payload.display_name or "").strip() if payload.display_name is not None else None
    phone = (payload.phone or "").strip() if payload.phone is not None else None
    password_raw = (payload.password or "").strip() if payload.password is not None else None
    next_is_active = payload.is_active
    next_is_root = payload.is_root

    if login is not None and not login:
        raise HTTPException(status_code=400, detail="Логин не может быть пустым")
    if display_name is not None and not display_name:
        raise HTTPException(status_code=400, detail="Имя суперадмина не может быть пустым")
    if login is not None and superadmin_repo.superadmin_login_exists(login, account_id):
        raise HTTPException(status_code=409, detail="Суперадмин с таким логином уже существует")

    is_last_active_root = bool(existing.get("is_root")) and bool(existing.get("is_active")) and superadmin_repo.count_active_root_superadmins() <= 1
    if is_last_active_root and (next_is_active is False or next_is_root is False):
        raise HTTPException(status_code=409, detail="В системе должен остаться хотя бы один активный root-superadmin")

    next_password_hash = hash_password(password_raw) if password_raw else None
    update_payload = {}
    if payload.login is not None:
        update_payload["login"] = login
    if payload.display_name is not None:
        update_payload["display_name"] = display_name
    if payload.phone is not None:
        update_payload["phone"] = phone
    if next_password_hash is not None:
        update_payload["password_hash"] = next_password_hash
    if next_is_active is not None:
        update_payload["is_active"] = next_is_active
    if next_is_root is not None:
        update_payload["is_root"] = next_is_root

    superadmin_repo.update_superadmin_account(account_id, **update_payload)
    log_crm_audit_event(
        actor_type="superadmin",
        actor_id=actor.get("id"),
        actor_display=actor.get("display_name") or actor.get("login"),
        target_type="superadmin_account",
        target_id=account_id,
        action_type="update",
        action_label="Обновлена учётка суперадмина",
        old_value={
            "login": existing.get("login"),
            "display_name": existing.get("display_name"),
            "phone": existing.get("phone"),
            "is_active": bool(existing.get("is_active")),
            "is_root": bool(existing.get("is_root")),
        },
        new_value={
            "login": login if login is not None else existing.get("login"),
            "display_name": display_name if display_name is not None else existing.get("display_name"),
            "phone": phone if payload.phone is not None else existing.get("phone"),
            "is_active": next_is_active if next_is_active is not None else bool(existing.get("is_active")),
            "is_root": next_is_root if next_is_root is not None else bool(existing.get("is_root")),
            "password_changed": bool(next_password_hash),
        },
    )
    return {"ok": True}


def archive_root_superadmin_account(account_id: int, request: Request):
    actor = get_root_superadmin(request)
    existing = superadmin_repo.get_superadmin_account_by_id(account_id)
    if not existing or existing.get("archived_at") is not None:
        raise HTTPException(status_code=404, detail="Учётная запись суперадмина не найдена")
    is_last_active_root = bool(existing.get("is_root")) and bool(existing.get("is_active")) and superadmin_repo.count_active_root_superadmins() <= 1
    if is_last_active_root:
        raise HTTPException(status_code=409, detail="В системе должен остаться хотя бы один активный root-superadmin")

    superadmin_repo.update_superadmin_account(account_id, archived_at=datetime.now(timezone.utc), is_active=False)
    log_crm_audit_event(
        actor_type="superadmin",
        actor_id=actor.get("id"),
        actor_display=actor.get("display_name") or actor.get("login"),
        target_type="superadmin_account",
        target_id=account_id,
        action_type="archive",
        action_label="Архивирована учётка суперадмина",
        old_value={
            "login": existing.get("login"),
            "display_name": existing.get("display_name"),
            "is_active": bool(existing.get("is_active")),
            "is_root": bool(existing.get("is_root")),
        },
    )
    return {"ok": True}


def restore_root_superadmin_account(account_id: int, request: Request):
    actor = get_root_superadmin(request)
    existing = superadmin_repo.get_superadmin_account_by_id(account_id)
    if not existing or existing.get("archived_at") is None:
        raise HTTPException(status_code=404, detail="Архивная учётка суперадмина не найдена")

    superadmin_repo.update_superadmin_account(account_id, archived_at=None, is_active=True)
    log_crm_audit_event(
        actor_type="superadmin",
        actor_id=actor.get("id"),
        actor_display=actor.get("display_name") or actor.get("login"),
        target_type="superadmin_account",
        target_id=account_id,
        action_type="restore",
        action_label="Восстановлена учётка суперадмина",
        old_value={"archived_at": existing.get("archived_at")},
    )
    return {"ok": True}


def superadmin_list_audit_records(
    request: Request,
    search: Optional[str] = None,
    actor_type: Optional[str] = None,
    target_type: Optional[str] = None,
    camp_id: Optional[int] = None,
    limit: int = 100,
):
    get_root_superadmin(request)
    return superadmin_repo.list_system_audit(
        search=search,
        actor_type=(actor_type or "").strip() or None,
        target_type=(target_type or "").strip() or None,
        camp_id=camp_id,
        limit=limit,
    )
