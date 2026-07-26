"""HTTP application service for Owner Portal and its moderation queue."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from tourist03.csrf import issue_csrf_token
from tourist03.domain.owner_changes import (
    OwnerChangeValidationError,
    calculate_card_quality,
    sanitize_owner_payload,
)
from tourist03.dto.owners import (
    OwnerAccountCreateRequest,
    OwnerAccountAdminPatchRequest,
    OwnerCampLinkRequest,
    OwnerChangeApplyRequest,
    OwnerChangeDecisionRequest,
    OwnerChangePatchRequest,
    OwnerForgotPasswordRequest,
    OwnerLoginRequest,
    OwnerPasswordPatchRequest,
    OwnerProfilePatchRequest,
    OwnerResetPasswordRequest,
)
from tourist03.owner_security import (
    get_current_owner,
    hash_owner_password,
    hash_owner_technical_value,
    hash_owner_token,
    normalize_owner_email,
    owner_password_needs_rehash,
    owner_public,
    reset_owner_session,
    validate_owner_email,
    verify_owner_password,
)
from tourist03.repositories import catalog as catalog_repo
from tourist03.repositories import owners as owner_repo
from tourist03.security import get_superadmin
from tourist03.submission_media import (
    SubmissionMediaError,
    prepare_submission_image,
    remove_stored_media,
    safe_storage_path,
    store_prepared_image,
)


def _technical_hash(request: Request, value: str) -> str | None:
    return hash_owner_technical_value(value, request.app.state.settings.session_secret_key)


def _request_fingerprint(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else ""
    return _technical_hash(request, ip), _technical_hash(request, request.headers.get("user-agent", ""))


def owner_session(request: Request) -> dict:
    owner = get_current_owner(request)
    return {"ok": True, "authenticated": True, "owner": owner, "csrf_token": issue_csrf_token(request)}


def owner_login(request: Request, payload: OwnerLoginRequest) -> dict:
    email = normalize_owner_email(str(payload.email))
    email_hash = _technical_hash(request, email)
    ip_hash, user_agent_hash = _request_fingerprint(request)
    account = owner_repo.get_owner_by_email(email)
    success = bool(
        account
        and account.get("is_active")
        and account.get("account_status") == "active"
        and verify_owner_password(payload.password, account.get("password_hash") or "")
    )
    owner_repo.log_owner_login(
        owner_id=account.get("id") if account else None,
        email_hash=email_hash,
        event_type="login",
        success=success,
        ip_hash=ip_hash,
        user_agent_hash=user_agent_hash,
    )
    if not success:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if owner_password_needs_rehash(account["password_hash"]):
        owner_repo.rehash_owner_password(account["id"], hash_owner_password(payload.password))
    reset_owner_session(request, account["id"])
    return {
        "ok": True,
        "authenticated": True,
        "owner": owner_public(account),
        "csrf_token": issue_csrf_token(request),
    }


def owner_logout(request: Request) -> dict:
    reset_owner_session(request)
    return {"ok": True, "authenticated": False, "owner": None}


def owner_forgot_password(request: Request, payload: OwnerForgotPasswordRequest) -> dict:
    """Always return the same response to prevent owner-account enumeration."""
    account = owner_repo.get_owner_by_email(normalize_owner_email(str(payload.email)))
    test_token = None
    if account and account.get("is_active") and account.get("account_status") == "active":
        ip_hash, _ = _request_fingerprint(request)
        _, test_token = owner_repo.create_owner_reset(
            owner_id=account["id"],
            requested_ip_hash=ip_hash,
            ttl_minutes=request.app.state.settings.owner_password_reset_ttl_minutes,
            secret=request.app.state.settings.session_secret_key,
            public_base_url=request.app.state.settings.public_base_url,
        )
    result = {
        "ok": True,
        "message": "Если аккаунт существует, письмо с инструкцией уже отправлено.",
    }
    if request.app.state.settings.environment == "test" and test_token:
        result["test_token"] = test_token
    return result


def owner_reset_password(request: Request, payload: OwnerResetPasswordRequest) -> dict:
    try:
        password_hash = hash_owner_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    token_hash = hash_owner_token(payload.token, request.app.state.settings.session_secret_key)
    owner_id = owner_repo.consume_owner_reset(token_hash=token_hash, password_hash=password_hash)
    if not owner_id:
        raise HTTPException(status_code=400, detail="Ссылка недействительна или устарела")
    reset_owner_session(request)
    return {"ok": True, "message": "Пароль обновлён. Теперь можно войти."}


def owner_update_profile(request: Request, payload: OwnerProfilePatchRequest) -> dict:
    owner = get_current_owner(request)
    changes = payload.model_dump(exclude_unset=True)
    cleaned = {}
    for key, value in changes.items():
        cleaned[key] = re.sub(r"\s+", " ", value).strip() or None if isinstance(value, str) else value
    row = owner_repo.update_owner_profile(owner["id"], cleaned)
    return {"ok": True, "owner": owner_public(row)}


def owner_change_password(request: Request, payload: OwnerPasswordPatchRequest) -> dict:
    owner = get_current_owner(request)
    account = owner_repo.get_owner_by_id(owner["id"])
    if not account or not verify_owner_password(payload.current_password, account["password_hash"]):
        raise HTTPException(status_code=400, detail="Текущий пароль указан неверно")
    try:
        password_hash = hash_owner_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    owner_repo.update_owner_password(owner["id"], password_hash)
    return {"ok": True, "message": "Пароль обновлён"}


def _camp_card(request: Request, camp: dict, snapshot: dict | None = None) -> dict:
    snapshot = snapshot or owner_repo.get_camp_snapshot(camp["id"])
    if not snapshot:
        return {**camp, "quality": None, "statistics": {}}
    quality = calculate_card_quality(snapshot, request.app.state.settings.owner_card_completeness_weights)
    return {
        **camp,
        "quality": quality,
        "statistics": {
            "last_changed_at": snapshot.get("updated_at"),
            "last_moderated_at": snapshot.get("confirmed_at"),
            "photos_count": len([item for item in snapshot.get("media", []) if item.get("media_type") == "image"]),
            "rooms_count": len(snapshot.get("rooms", [])),
            "amenities_count": len(snapshot.get("amenities", [])),
            "completeness": quality["score"],
            "pending_changes": camp.get("pending_changes", 0),
        },
    }


def _owner_camp_page(request: Request, owner_id: int, *, limit: int, offset: int) -> dict:
    profile_statistics = owner_repo.owner_profile_statistics(owner_id)
    camp_rows = owner_repo.list_owner_camps(owner_id, limit=limit, offset=offset)
    snapshots = owner_repo.get_camp_quality_snapshots(camp["id"] for camp in camp_rows)
    camps = [_camp_card(request, camp, snapshots.get(int(camp["id"]))) for camp in camp_rows]
    return {
        "camps": camps,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": profile_statistics["objects_count"],
            "has_more": offset + len(camps) < profile_statistics["objects_count"],
        },
        "profile_statistics": profile_statistics,
    }


def owner_dashboard(
    request: Request,
    object_limit: int = Query(20, ge=1, le=50),
    object_offset: int = Query(0, ge=0),
) -> dict:
    owner = get_current_owner(request)
    camp_page = _owner_camp_page(
        request,
        owner["id"],
        limit=object_limit,
        offset=object_offset,
    )
    camps = camp_page["camps"]
    pending = owner_repo.list_owner_change_summaries(
        owner["id"],
        statuses={"submitted", "in_review", "needs_changes", "approved"},
        limit=5,
    )
    attention = []
    for camp in camps:
        for recommendation in (camp.get("quality") or {}).get("recommendations", [])[:3]:
            attention.append({"camp_id": camp["id"], "camp_name": camp["name"], "message": recommendation})
    return {
        "ok": True,
        "features": {
            "change_requests": request.app.state.settings.feature_owner_change_requests,
        },
        "owner": owner,
        "profile_statistics": camp_page["profile_statistics"],
        "camps": camps,
        "object_pagination": camp_page["pagination"],
        "attention": attention,
        "pending_changes": pending,
        "activity": owner_repo.list_owner_activity(owner["id"], limit=7),
    }


def owner_list_camps(
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
) -> dict:
    owner = get_current_owner(request)
    camp_page = _owner_camp_page(request, owner["id"], limit=limit, offset=offset)
    return {
        "ok": True,
        "camps": camp_page["camps"],
        "pagination": camp_page["pagination"],
    }


def owner_camp_detail(request: Request, camp_id: int) -> dict:
    owner = get_current_owner(request)
    if not owner_repo.owner_can_access_camp(owner["id"], camp_id):
        raise HTTPException(status_code=404, detail="Объект не найден")
    snapshot = owner_repo.get_camp_snapshot(camp_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Объект не найден")
    quality = calculate_card_quality(snapshot, request.app.state.settings.owner_card_completeness_weights)
    changes = owner_repo.list_owner_change_summaries(
        owner["id"],
        camp_id=camp_id,
        limit=20,
    )
    return {
        "ok": True,
        "camp": snapshot,
        "quality": quality,
        "changes": changes,
        "amenity_catalog": catalog_repo.list_public_amenities(),
        "activity": [
            item for item in owner_repo.list_owner_activity(owner["id"], limit=100)
            if item.get("camp_id") == camp_id
        ][:30],
    }


def owner_list_changes(
    request: Request,
    camp_id: int | None = Query(None, ge=1),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    owner = get_current_owner(request)
    changes = owner_repo.list_owner_change_summaries(
        owner["id"],
        camp_id=camp_id,
        limit=limit,
        offset=offset,
    )
    total = owner_repo.count_owner_changes(owner["id"], camp_id=camp_id)
    return {
        "ok": True,
        "changes": changes,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
            "has_more": offset + len(changes) < total,
        },
    }


def owner_get_change(request: Request, change_id: int) -> dict:
    owner = get_current_owner(request)
    row = owner_repo.get_owner_change(change_id, owner_id=owner["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Изменения не найдены")
    return {"ok": True, "change": row}


def owner_create_change(request: Request, camp_id: int) -> dict:
    owner = get_current_owner(request)
    row, created = owner_repo.create_owner_change(owner["id"], camp_id)
    if not row:
        raise HTTPException(status_code=404, detail="Объект не найден или недоступен для изменения")
    return {"ok": True, "created": created, "change": row}


def owner_save_change(request: Request, change_id: int, payload: OwnerChangePatchRequest) -> dict:
    owner = get_current_owner(request)
    try:
        proposed = sanitize_owner_payload(payload.proposed_payload)
        row = owner_repo.save_owner_change(
            change_id,
            owner["id"],
            proposed,
            expected_version=payload.content_version,
        )
    except (OwnerChangeValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Черновик не найден или уже отправлен")
    return {"ok": True, "change": row}


def _owner_transition(request: Request, change_id: int, target: str) -> dict:
    owner = get_current_owner(request)
    try:
        row = owner_repo.transition_owner_change(
            change_id,
            target=target,
            actor_type="owner",
            actor_id=owner["id"],
            owner_id=owner["id"],
        )
    except (OwnerChangeValidationError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Изменения не найдены")
    return {"ok": True, "change": row}


def owner_submit_change(request: Request, change_id: int) -> dict:
    return _owner_transition(request, change_id, "submitted")


def owner_withdraw_change(request: Request, change_id: int) -> dict:
    return _owner_transition(request, change_id, "withdrawn")


def owner_unpublish_camp(request: Request, camp_id: int) -> dict:
    owner = get_current_owner(request)
    row = owner_repo.unpublish_owner_camp(owner["id"], camp_id)
    if not row:
        raise HTTPException(status_code=404, detail="Объект не найден")
    return {
        "ok": True,
        "camp": row,
        "message": "Объект снят с публикации. Повторная публикация потребует проверки.",
    }


async def owner_upload_change_media(
    request: Request,
    change_id: int,
    file: UploadFile = File(...),
    scope: str = Form("place"),
    room_client_id: str | None = Form(None),
    sort_order: int = Form(0),
    is_cover: bool = Form(False),
) -> dict:
    owner = get_current_owner(request)
    settings = request.app.state.settings
    normalized_scope = (scope or "").strip().lower()
    normalized_room = (room_client_id or "").strip() or None
    if normalized_scope not in {"place", "room"}:
        raise HTTPException(status_code=400, detail="Некорректный раздел фотографии")
    limit = settings.submission_max_place_photos
    if normalized_scope == "place":
        normalized_room = None
    else:
        if not normalized_room or len(normalized_room) > 80:
            raise HTTPException(status_code=400, detail="Не указан вариант размещения")
        limit = settings.submission_max_room_photos
    raw = await file.read(settings.owner_change_max_image_bytes + 1)
    image_settings = settings.model_copy(
        update={
            "submission_max_image_bytes": settings.owner_change_max_image_bytes,
            "submission_max_image_pixels": settings.owner_change_max_image_pixels,
        }
    )
    try:
        prepared = prepare_submission_image(raw, image_settings)
    except SubmissionMediaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    storage_key = thumbnail_key = safe_filename = ""
    try:
        storage_key, thumbnail_key, safe_filename = store_prepared_image(
            prepared,
            settings,
            relative_dir=Path("owner-changes") / "staged",
        )
        preview_token = secrets.token_urlsafe(32)
        row = owner_repo.create_owner_change_media(
            change_id=change_id,
            owner_id=owner["id"],
            scope=normalized_scope,
            room_client_id=normalized_room,
            storage_key=storage_key,
            thumbnail_storage_key=thumbnail_key,
            preview_token=preview_token,
            public_preview_url=f"/api/owner/change-media/{preview_token}",
            original_filename=Path(file.filename or "image").name[:240],
            safe_filename=safe_filename,
            mime_type=prepared.mime_type,
            size_bytes=len(prepared.content),
            width=prepared.width,
            height=prepared.height,
            sort_order=max(0, min(int(sort_order), 10_000)),
            is_cover=bool(is_cover),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.owner_change_request_ttl_days),
            max_count=limit,
        )
    except ValueError as exc:
        remove_stored_media(settings, storage_key, thumbnail_key)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        remove_stored_media(settings, storage_key, thumbnail_key)
        raise
    return {
        "ok": True,
        "media": {
            "id": row["id"],
            "scope": row["scope"],
            "room_client_id": row["room_client_id"],
            "url": row["public_preview_url"],
            "thumbnail_url": f"{row['public_preview_url']}?thumbnail=1",
            "width": row["width"],
            "height": row["height"],
            "sort_order": row["sort_order"],
            "is_cover": row["is_cover"],
        },
    }


def owner_change_media(
    request: Request,
    preview_token: str,
    thumbnail: bool = Query(False),
):
    owner = get_current_owner(request)
    if len(preview_token) < 32 or len(preview_token) > 200:
        raise HTTPException(status_code=404, detail="Файл не найден")
    row = owner_repo.get_owner_change_media(preview_token, owner["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Файл не найден")
    storage_key = row["thumbnail_storage_key"] if thumbnail else row["storage_key"]
    path = safe_storage_path(request.app.state.settings, storage_key)
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(
        path,
        media_type="image/webp" if thumbnail else row["mime_type"],
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


def owner_delete_change_media(request: Request, change_id: int, media_id: int) -> dict:
    owner = get_current_owner(request)
    row = owner_repo.delete_owner_change_media(media_id, change_id, owner["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Фотография не найдена")
    remove_stored_media(
        request.app.state.settings,
        row.get("storage_key"),
        row.get("thumbnail_storage_key"),
    )
    return {"ok": True}


def owner_remove_published_media(request: Request, change_id: int, media_id: int) -> dict:
    owner = get_current_owner(request)
    try:
        row = owner_repo.stage_owner_media_removal(
            change_id=change_id,
            owner_id=owner["id"],
            target_media_id=media_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "media": row}


def superadmin_list_owner_changes(
    request: Request,
    status: str | None = Query(None, max_length=40),
    camp_id: int | None = Query(None, ge=1),
    owner_id: int | None = Query(None, ge=1),
    region: str | None = Query(None, max_length=160),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
) -> dict:
    get_superadmin(request)
    return {
        "ok": True,
        "changes": owner_repo.list_moderation_changes(
            status=status,
            camp_id=camp_id,
            owner_id=owner_id,
            region=(region or "").strip() or None,
            date_from=date_from,
            date_to=date_to,
        ),
    }


def superadmin_get_owner_change(request: Request, change_id: int) -> dict:
    get_superadmin(request)
    row = owner_repo.get_owner_change(change_id)
    if not row:
        raise HTTPException(status_code=404, detail="Изменения не найдены")
    return {"ok": True, "change": row}


def superadmin_decide_owner_change(
    request: Request,
    change_id: int,
    payload: OwnerChangeDecisionRequest,
) -> dict:
    actor = get_superadmin(request)
    if actor.get("id") is None:
        raise HTTPException(status_code=403, detail="Для решения нужен именной аккаунт суперадмина")
    try:
        row = owner_repo.transition_owner_change(
            change_id,
            target=payload.status,
            actor_type="superadmin",
            actor_id=actor["id"],
            comment=payload.comment,
        )
    except (OwnerChangeValidationError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Изменения не найдены")
    return {"ok": True, "change": row}


def superadmin_apply_owner_change(
    request: Request,
    change_id: int,
    payload: OwnerChangeApplyRequest,
) -> dict:
    actor = get_superadmin(request)
    if actor.get("id") is None:
        raise HTTPException(status_code=403, detail="Для публикации нужен именной аккаунт суперадмина")
    scoped = hmac.new(
        request.app.state.settings.session_secret_key.encode("utf-8"),
        f"{change_id}\0{payload.idempotency_key}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    try:
        row, applied = owner_repo.apply_owner_change(
            change_id,
            moderator_id=actor["id"],
            idempotency_key_hash=scoped,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Изменения не найдены")
    return {"ok": True, "applied": applied, "change": row}


def superadmin_create_owner(request: Request, payload: OwnerAccountCreateRequest) -> dict:
    get_superadmin(request)
    try:
        email = validate_owner_email(str(payload.email))
        password_hash = hash_owner_password(payload.password)
        row = owner_repo.create_owner_account(
            email=email,
            password_hash=password_hash,
            display_name=payload.display_name.strip(),
            company=(payload.company or "").strip() or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        if getattr(exc, "pgcode", None) == "23505":
            raise HTTPException(status_code=409, detail="Владелец с таким email уже существует") from exc
        raise
    return {"ok": True, "owner": owner_public(row)}


def superadmin_list_owners(request: Request) -> dict:
    get_superadmin(request)
    return {"ok": True, "owners": owner_repo.list_owner_accounts()}


def superadmin_update_owner(
    request: Request,
    owner_id: int,
    payload: OwnerAccountAdminPatchRequest,
) -> dict:
    get_superadmin(request)
    row = owner_repo.update_owner_account_admin(
        owner_id,
        payload.model_dump(exclude_unset=True),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Владелец не найден")
    return {"ok": True, "owner": owner_public(row)}


def superadmin_link_owner_camp(
    request: Request,
    owner_id: int,
    payload: OwnerCampLinkRequest,
) -> dict:
    actor = get_superadmin(request)
    row = owner_repo.link_owner_camp(
        owner_id=owner_id,
        camp_id=payload.camp_id,
        role_key=payload.role_key,
        is_primary=payload.is_primary,
        superadmin_id=actor.get("id"),
    )
    return {"ok": True, "link": row}
