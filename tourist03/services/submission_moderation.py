"""Superadmin workflow for placement submission moderation."""

from __future__ import annotations

from fastapi import HTTPException, Query, Request

from tourist03.domain.submissions import SubmissionValidationError, validate_submission_payload
from tourist03.domain.submissions import tracking_token_for
from tourist03.dto.submissions import (
    SubmissionAdminPatchRequest,
    SubmissionNoteRequest,
    SubmissionObjectDraftRequest,
    SubmissionStatusRequest,
)
from tourist03.repositories import submissions as submission_repo
from tourist03.security import get_superadmin, log_crm_audit_event


def _actor(request: Request) -> dict:
    return get_superadmin(request)


def _audit(
    actor: dict,
    *,
    action_type: str,
    action_label: str,
    submission_id: int,
    metadata: dict | None = None,
    comment: str | None = None,
) -> None:
    log_crm_audit_event(
        actor_type="superadmin",
        actor_id=actor.get("id"),
        actor_display=actor.get("display_name") or actor.get("login"),
        action_type=action_type,
        action_label=action_label,
        target_type="placement_submission",
        target_id=submission_id,
        comment=comment,
        metadata=metadata or {},
    )


def list_admin_submissions(
    request: Request,
    status: str | None = Query(None, max_length=40),
    place_type_id: int | None = Query(None, ge=1),
    region: str | None = Query(None, max_length=160),
    applicant_role: str | None = Query(None, max_length=32),
    assigned_admin_id: int | None = Query(None, ge=1),
    has_photos: bool | None = Query(None),
    spam_risk: str | None = Query(None, max_length=20),
    q: str | None = Query(None, max_length=120),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100_000),
) -> dict:
    _actor(request)
    return submission_repo.list_submissions(
        status=(status or "").strip().lower() or None,
        place_type_id=place_type_id,
        region=(region or "").strip() or None,
        applicant_role=(applicant_role or "").strip().lower() or None,
        assigned_admin_id=assigned_admin_id,
        has_photos=has_photos,
        spam_risk=(spam_risk or "").strip().lower() or None,
        query=(q or "").strip() or None,
        limit=limit,
        offset=offset,
    )


def get_admin_submission(request: Request, submission_id: int) -> dict:
    actor = _actor(request)
    row = submission_repo.get_submission_detail(submission_id)
    if not row:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    _audit(
        actor,
        action_type="submission_opened",
        action_label="Открыта заявка",
        submission_id=submission_id,
    )
    return {"ok": True, "submission": row}


def patch_admin_submission(
    request: Request,
    submission_id: int,
    payload: SubmissionAdminPatchRequest,
) -> dict:
    actor = _actor(request)
    changes = payload.model_dump(exclude_unset=True)
    expected_version = int(changes.pop("content_version"))
    row = submission_repo.patch_submission_by_admin(
        submission_id,
        changes,
        expected_version=expected_version,
    )
    if not row:
        raise HTTPException(status_code=409, detail="Данные заявки изменились. Обновите страницу")
    _audit(
        actor,
        action_type="submission_updated",
        action_label="Изменена заявка",
        submission_id=submission_id,
        metadata={"fields": sorted(changes)},
    )
    return {"ok": True, "submission": row}


def change_admin_submission_status(
    request: Request,
    submission_id: int,
    payload: SubmissionStatusRequest,
) -> dict:
    actor = _actor(request)
    try:
        row = submission_repo.transition_submission(
            submission_id,
            payload.status.strip().lower(),
            actor_id=actor.get("id"),
            public_comment=payload.public_comment,
            internal_comment=payload.internal_comment,
            expected_version=payload.content_version,
            assign_to_actor=payload.status.strip().lower() == "in_review",
        )
    except (SubmissionValidationError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    _audit(
        actor,
        action_type="submission_status_changed",
        action_label="Изменён статус заявки",
        submission_id=submission_id,
        metadata={"status": row["status"]},
        comment=payload.internal_comment,
    )
    notification_templates = {
        "needs_clarification": (
            "Требуется уточнение",
            "Модератору нужна дополнительная информация по вашей заявке.",
        ),
        "approved": (
            "Заявка одобрена",
            "Заявка прошла первичную модерацию. Публикация объекта выполняется отдельно.",
        ),
        "rejected": (
            "Заявка отклонена",
            payload.public_comment or "Модератор завершил рассмотрение заявки.",
        ),
    }
    if row["status"] in notification_templates:
        title, body = notification_templates[row["status"]]
        tracking_token = tracking_token_for(
            row["public_number"],
            request.app.state.settings.session_secret_key,
        )
        tracking_url = (
            f"{request.app.state.settings.public_base_url}/submission-status"
            f"#number={row['public_number']}&token={tracking_token}"
        )
        try:
            submission_repo.enqueue_submission_notifications(
                row["id"],
                event_type=f"placement_submission_{row['status']}",
                title=f"{title}: {row['public_number']}",
                body=f"{row['public_number']} · {row.get('place_name') or 'Объект'}",
                admin_action_url=(
                    f"{request.app.state.settings.superadmin_base_url.rstrip('/')}"
                    f"/admin/submissions?submission={row['id']}"
                ),
                applicant_email=row.get("applicant_email"),
                applicant_title=f"{title} · {row['public_number']}",
                applicant_body=body,
                applicant_action_url=tracking_url,
                severity="warning" if row["status"] in {"needs_clarification", "rejected"} else "info",
            )
        except Exception:
            pass
    return {"ok": True, "submission": row}


def add_admin_submission_note(
    request: Request,
    submission_id: int,
    payload: SubmissionNoteRequest,
) -> dict:
    actor = _actor(request)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Текст заметки обязателен")
    row = submission_repo.add_submission_note(
        submission_id,
        author_id=actor.get("id"),
        text=text,
        visible_to_applicant=payload.is_visible_to_applicant,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    _audit(
        actor,
        action_type="submission_note_added",
        action_label="Добавлена заметка",
        submission_id=submission_id,
        metadata={"visible_to_applicant": payload.is_visible_to_applicant},
    )
    return {"ok": True, "note": row}


def request_submission_clarification(
    request: Request,
    submission_id: int,
    payload: SubmissionStatusRequest,
) -> dict:
    normalized = payload.model_copy(update={"status": "needs_clarification"})
    return change_admin_submission_status(request, submission_id, normalized)


def approve_submission(
    request: Request,
    submission_id: int,
    payload: SubmissionStatusRequest,
) -> dict:
    current = submission_repo.get_submission_detail(submission_id)
    if not current:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    try:
        validate_submission_payload(current)
    except SubmissionValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    normalized = payload.model_copy(update={"status": "approved"})
    return change_admin_submission_status(request, submission_id, normalized)


def reject_submission(
    request: Request,
    submission_id: int,
    payload: SubmissionStatusRequest,
) -> dict:
    normalized = payload.model_copy(update={"status": "rejected"})
    return change_admin_submission_status(request, submission_id, normalized)


def archive_submission(
    request: Request,
    submission_id: int,
    payload: SubmissionStatusRequest,
) -> dict:
    normalized = payload.model_copy(update={"status": "archived"})
    return change_admin_submission_status(request, submission_id, normalized)


def create_submission_object_draft(
    request: Request,
    submission_id: int,
    payload: SubmissionObjectDraftRequest,
) -> dict:
    actor = _actor(request)
    try:
        result, created = submission_repo.create_catalog_draft_from_submission(
            submission_id,
            actor_id=actor.get("id"),
            idempotency_key=payload.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if created:
        _audit(
            actor,
            action_type="submission_object_draft_created",
            action_label="Создан черновик объекта",
            submission_id=submission_id,
            metadata={"camp_id": result["camp_id"]},
        )
        detail = submission_repo.get_submission_detail(submission_id)
        if detail:
            settings = request.app.state.settings
            tracking_token = tracking_token_for(
                detail["public_number"],
                settings.session_secret_key,
            )
            try:
                submission_repo.enqueue_submission_notifications(
                    submission_id,
                    event_type="placement_submission_object_draft_created",
                    title=f"Создан черновик объекта: {detail['public_number']}",
                    body=(
                        f"Черновик каталога #{result['camp_id']} создан. "
                        "Публикация требует отдельного решения суперадмина."
                    ),
                    admin_action_url=(
                        f"{settings.superadmin_base_url.rstrip('/')}"
                        f"/admin/bases/{result['camp_id']}"
                    ),
                    applicant_email=detail.get("applicant_email"),
                    applicant_title=f"Карточка объекта подготовлена · {detail['public_number']}",
                    applicant_body=(
                        "По заявке создан внутренний черновик карточки. "
                        "Он ещё не опубликован и проходит финальную проверку."
                    ),
                    applicant_action_url=(
                        f"{settings.public_base_url}/submission-status"
                        f"#number={detail['public_number']}&token={tracking_token}"
                    ),
                )
            except Exception:
                pass
    return {"ok": True, "created": created, **result}
