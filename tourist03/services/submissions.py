"""Public HTTP workflow for placement submissions."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from tourist03.domain.submissions import (
    SubmissionValidationError,
    calculate_spam_score,
    hash_technical_value,
    hash_token,
    idempotency_hash_for,
    new_secret_token,
    tracking_token_for,
    validate_submission_payload,
)
from tourist03.dto.submissions import (
    SubmissionDraftCreateRequest,
    SubmissionDraftPatchRequest,
    SubmissionClarificationRequest,
    SubmissionSubmitRequest,
)
from tourist03.repositories import catalog as catalog_repo
from tourist03.repositories import submissions as submission_repo
from tourist03.security import log_crm_audit_event
from tourist03.submission_media import (
    SubmissionMediaError,
    prepare_submission_image,
    remove_stored_media,
    safe_storage_path,
    store_prepared_image,
)
from tourist03.submission_security import CaptchaUnavailableError, build_captcha_verifier


STATUS_LABELS = {
    "submitted": "Отправлена",
    "new": "Принята",
    "in_review": "На рассмотрении",
    "needs_clarification": "Нужны уточнения",
    "approved": "Одобрена",
    "object_draft_created": "Карточка создаётся",
    "published": "Опубликована",
    "rejected": "Отклонена",
    "withdrawn": "Отозвана",
    "archived": "Архивирована",
}


def _client_hashes(request: Request) -> tuple[str | None, str | None]:
    settings = request.app.state.settings
    host = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")
    return (
        hash_technical_value(host, settings.session_secret_key),
        hash_technical_value(user_agent, settings.session_secret_key),
    )


def public_submission_config(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "ok": True,
        "format_version": 1,
        "captcha_provider": settings.submission_captcha_provider,
        "limits": {
            "place_photos": settings.submission_max_place_photos,
            "room_photos": settings.submission_max_room_photos,
            "image_bytes": settings.submission_max_image_bytes,
        },
        "place_types": catalog_repo.list_place_types(),
        "amenities": catalog_repo.list_public_amenities(),
    }


def create_public_draft(request: Request, payload: SubmissionDraftCreateRequest) -> dict:
    settings = request.app.state.settings
    draft_token = new_secret_token()
    ip_hash, user_agent_hash = _client_hashes(request)
    row = submission_repo.create_draft(
        draft_token_hash=hash_token(draft_token),
        ip_hash=ip_hash,
        user_agent_hash=user_agent_hash,
        locale=payload.locale,
        source=payload.source,
        ttl_hours=settings.submission_draft_ttl_hours,
    )
    log_crm_audit_event(
        actor_type="applicant",
        action_type="submission_draft_created",
        action_label="Создан черновик заявки",
        target_type="placement_submission",
        target_id=row["public_number"],
        metadata={"source": row["source"]},
    )
    return {
        "ok": True,
        "public_number": row["public_number"],
        "draft_token": draft_token,
        "expires_at": row["draft_expires_at"],
        "content_version": row["content_version"],
    }


def patch_public_draft(
    draft_token: str,
    payload: SubmissionDraftPatchRequest,
) -> dict:
    changes = payload.model_dump(exclude_unset=True)
    expected_version = changes.pop("content_version", None)
    row = submission_repo.patch_draft(
        hash_token(draft_token),
        changes,
        expected_version=expected_version,
    )
    if not row:
        raise HTTPException(
            status_code=409 if expected_version is not None else 404,
            detail="Черновик не найден, истёк или был изменён в другой вкладке",
        )
    return {
        "ok": True,
        "public_number": row["public_number"],
        "status": row["status"],
        "content_version": row["content_version"],
        "updated_at": row["updated_at"],
    }


async def upload_public_draft_media(
    request: Request,
    draft_token: str,
    file: UploadFile = File(...),
    scope: str = Form("place"),
    room_client_id: str | None = Form(None),
    sort_order: int = Form(0),
    is_cover: bool = Form(False),
) -> dict:
    settings = request.app.state.settings
    draft_hash = hash_token(draft_token)
    draft = submission_repo.get_draft_by_token_hash(draft_hash)
    if not draft or draft["status"] != "draft" or draft["draft_expires_at"] <= datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="Черновик не найден или истёк")
    normalized_scope = (scope or "").strip().lower()
    normalized_room = (room_client_id or "").strip() or None
    if normalized_scope not in {"place", "room"}:
        raise HTTPException(status_code=400, detail="Некорректная область фотографии")
    if normalized_scope == "place":
        normalized_room = None
        limit = settings.submission_max_place_photos
    else:
        if not normalized_room or len(normalized_room) > 80:
            raise HTTPException(status_code=400, detail="Не указан вариант размещения")
        limit = settings.submission_max_room_photos
    if submission_repo.count_media(
        draft["id"],
        scope=normalized_scope,
        room_client_id=normalized_room,
    ) >= limit:
        raise HTTPException(status_code=409, detail="Достигнут лимит фотографий")

    raw = await file.read(settings.submission_max_image_bytes + 1)
    try:
        prepared = prepare_submission_image(raw, settings)
    except SubmissionMediaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    storage_key = thumbnail_key = safe_filename = ""
    try:
        storage_key, thumbnail_key, safe_filename = store_prepared_image(prepared, settings)
        preview_token = secrets.token_urlsafe(32)
        row = submission_repo.create_media(
            submission_id=draft["id"],
            scope=normalized_scope,
            room_client_id=normalized_room,
            storage_key=storage_key,
            thumbnail_storage_key=thumbnail_key,
            preview_token=preview_token,
            public_preview_url=f"/api/public/submission-media/{preview_token}",
            original_filename=Path(file.filename or "image").name[:240],
            safe_filename=safe_filename,
            mime_type=prepared.mime_type,
            size_bytes=len(prepared.content),
            width=prepared.width,
            height=prepared.height,
            sort_order=max(0, min(int(sort_order), 10_000)),
            is_cover=bool(is_cover),
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=settings.submission_upload_ttl_hours),
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


def delete_public_draft_media(request: Request, draft_token: str, media_id: int) -> dict:
    row = submission_repo.delete_media_for_draft(media_id, hash_token(draft_token))
    if not row:
        raise HTTPException(status_code=404, detail="Фотография не найдена")
    remove_stored_media(
        request.app.state.settings,
        row.get("storage_key"),
        row.get("thumbnail_storage_key"),
    )
    return {"ok": True}


def public_submission_media(
    request: Request,
    preview_token: str,
    thumbnail: bool = Query(False),
):
    if len(preview_token) < 32 or len(preview_token) > 200:
        raise HTTPException(status_code=404, detail="Файл не найден")
    row = submission_repo.get_media_by_preview_token(preview_token)
    if not row:
        raise HTTPException(status_code=404, detail="Файл не найден")
    storage_key = row["thumbnail_storage_key"] if thumbnail else row["storage_key"]
    path = safe_storage_path(request.app.state.settings, storage_key)
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    media_type = "image/webp" if thumbnail else row["mime_type"]
    return FileResponse(
        path,
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


async def submit_public_submission(
    request: Request,
    payload: SubmissionSubmitRequest,
) -> dict:
    settings = request.app.state.settings
    if payload.honeypot.strip():
        raise HTTPException(status_code=400, detail="Не удалось отправить заявку")
    draft_hash = hash_token(payload.draft_token)
    draft = submission_repo.get_draft_by_token_hash(draft_hash)
    if not draft:
        raise HTTPException(status_code=404, detail="Черновик не найден")

    try:
        captcha_ok = await build_captcha_verifier(settings).verify(payload.captcha_token)
    except CaptchaUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Проверка CAPTCHA временно недоступна") from exc
    if not captcha_ok:
        raise HTTPException(status_code=400, detail="Проверка CAPTCHA не пройдена")

    ip_hash, _ = _client_hashes(request)
    recent = submission_repo.count_recent_submissions_by_ip(ip_hash)
    if recent >= settings.submission_rate_per_hour:
        raise HTTPException(status_code=429, detail="Слишком много заявок. Повторите позже")
    try:
        cleaned = validate_submission_payload(draft)
    except SubmissionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    created_at = draft.get("created_at") or datetime.now(timezone.utc)
    fill_seconds = max(0.0, (datetime.now(timezone.utc) - created_at).total_seconds())
    spam_score = calculate_spam_score(
        cleaned,
        fill_seconds=fill_seconds,
        minimum_fill_seconds=settings.submission_min_fill_seconds,
        recent_ip_submissions=recent,
        max_links=settings.submission_max_links,
    )
    tracking_token = tracking_token_for(
        draft["public_number"],
        settings.session_secret_key,
    )
    idempotency_hash = idempotency_hash_for(
        draft["public_number"],
        payload.idempotency_key,
        settings.session_secret_key,
    )
    try:
        finalized, created = submission_repo.finalize_submission(
            draft_token_hash=draft_hash,
            tracking_token_hash=hash_token(tracking_token),
            idempotency_key_hash=idempotency_hash,
            spam_score=spam_score,
            cleaned_payload=cleaned,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not finalized:
        raise HTTPException(status_code=404, detail="Черновик не найден")
    if created:
        log_crm_audit_event(
            actor_type="applicant",
            action_type="submission_submitted",
            action_label="Отправлена заявка",
            target_type="placement_submission",
            target_id=finalized["public_number"],
            metadata={"spam_score_band": "high" if spam_score >= 60 else "normal"},
        )
    tracking_url = (
        f"{settings.public_base_url}/submission-status"
        f"#number={quote(finalized['public_number'])}&token={quote(tracking_token)}"
    )
    if created:
        applicant_contacts = " · ".join(
            value
            for value in (
                finalized.get("applicant_phone"),
                finalized.get("applicant_email"),
                finalized.get("applicant_telegram"),
            )
            if value
        )
        try:
            submission_repo.enqueue_submission_notifications(
                finalized["id"],
                event_type="placement_submission_new",
                title="Новая заявка на размещение"
                if spam_score < 60
                else "Заявка с высоким spam score",
                body=(
                    f"{finalized['public_number']} · {finalized['place_name']} · "
                    f"{finalized['region']} · {finalized['applicant_role']}"
                    + (f"\nКонтакты: {applicant_contacts}" if applicant_contacts else "")
                ),
                admin_action_url=(
                    f"{settings.superadmin_base_url.rstrip('/')}/admin/submissions"
                    f"?submission={finalized['id']}"
                ),
                applicant_email=finalized.get("applicant_email"),
                applicant_title=f"Заявка {finalized['public_number']} принята",
                applicant_body=(
                    "Мы получили информацию и передали её на ручную модерацию. "
                    "Объект не публикуется автоматически."
                ),
                applicant_action_url=tracking_url,
                severity="warning" if spam_score >= 60 else "info",
            )
        except Exception:
            # Сбой outbox не должен отменять уже принятую заявку.
            pass
    return {
        "ok": True,
        "public_number": finalized["public_number"],
        "tracking_token": tracking_token,
        "tracking_url": tracking_url,
        "status": finalized["status"],
        "preferred_contact_type": finalized.get("preferred_contact_type"),
    }


def public_submission_status(
    public_number: str,
    tracking_token: str | None = Header(None, alias="X-Submission-Tracking-Token"),
) -> dict:
    token = (tracking_token or "").strip()
    if len(token) < 32 or len(token) > 200:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    row = submission_repo.get_submission_status(public_number, hash_token(token))
    if not row:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    place_url = None
    if row.get("published_slug") and row.get("publication_status") == "published":
        place_url = f"/places/{quote(row['published_slug'])}"
    return {
        "ok": True,
        "public_number": row["public_number"],
        "status": row["status"],
        "status_label": STATUS_LABELS.get(row["status"], "На рассмотрении"),
        "public_comment": row.get("status_public_comment"),
        "updated_at": row["updated_at"],
        "place_url": place_url,
        "can_respond": row["status"] == "needs_clarification",
    }


def respond_public_clarification(
    request: Request,
    public_number: str,
    payload: SubmissionClarificationRequest,
    tracking_token: str | None = Header(None, alias="X-Submission-Tracking-Token"),
) -> dict:
    token = (tracking_token or "").strip()
    if len(token) < 32 or len(token) > 200:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    try:
        row = submission_repo.respond_to_clarification(
            public_number,
            hash_token(token),
            payload.message.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    settings = request.app.state.settings
    try:
        submission_repo.enqueue_submission_notifications(
            row["id"],
            event_type="placement_submission_clarification_received",
            title=f"Получен ответ: {row['public_number']}",
            body=f"{row['public_number']} · {row.get('place_name') or 'Объект'}",
            admin_action_url=(
                f"{settings.superadmin_base_url.rstrip('/')}"
                f"/admin/submissions?submission={row['id']}"
            ),
            severity="info",
        )
    except Exception:
        pass
    log_crm_audit_event(
        actor_type="applicant",
        action_type="submission_clarification_received",
        action_label="Получен ответ заявителя",
        target_type="placement_submission",
        target_id=row["public_number"],
    )
    return {
        "ok": True,
        "public_number": row["public_number"],
        "status": row["status"],
        "status_label": STATUS_LABELS[row["status"]],
    }
