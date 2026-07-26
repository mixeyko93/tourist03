"""Routes for public placement submissions."""

from fastapi import APIRouter, Depends

from tourist03.api_responses import error_responses
from tourist03.dto.submissions import (
    SubmissionDraftCreateRequest,
    SubmissionDraftPatchRequest,
    SubmissionDraftResponseDTO,
    SubmissionDraftStateDTO,
    SubmissionPublicStatusDTO,
    SubmissionSubmitRequest,
    SubmissionSubmitResponseDTO,
    SubmissionAdminPatchRequest,
    SubmissionClarificationRequest,
    SubmissionNoteRequest,
    SubmissionObjectDraftRequest,
    SubmissionStatusRequest,
)
from tourist03.security import get_superadmin
from tourist03.services import submissions as submission_service
from tourist03.services import submission_moderation as moderation_service


router = APIRouter()
superadmin_guard = [Depends(get_superadmin)]

router.add_api_route(
    "/api/public/submissions/config",
    submission_service.public_submission_config,
    methods=["GET"],
    responses=error_responses(500),
)
router.add_api_route(
    "/api/public/submissions/drafts",
    submission_service.create_public_draft,
    methods=["POST"],
    response_model=SubmissionDraftResponseDTO,
    responses=error_responses(404, 422, 429, 500),
)
router.add_api_route(
    "/api/public/submissions/drafts/{draft_token}",
    submission_service.patch_public_draft,
    methods=["PATCH"],
    response_model=SubmissionDraftStateDTO,
    responses=error_responses(404, 409, 413, 422, 429, 500),
)
router.add_api_route(
    "/api/public/submissions/drafts/{draft_token}/media",
    submission_service.upload_public_draft_media,
    methods=["POST"],
    responses=error_responses(400, 404, 409, 413, 422, 429, 500),
)
router.add_api_route(
    "/api/public/submissions/drafts/{draft_token}/media/{media_id}",
    submission_service.delete_public_draft_media,
    methods=["DELETE"],
    responses=error_responses(404, 422, 429, 500),
)
router.add_api_route(
    "/api/public/submission-media/{preview_token}",
    submission_service.public_submission_media,
    methods=["GET"],
    responses=error_responses(404, 422, 500),
)
router.add_api_route(
    "/api/public/submissions/{public_number}/clarification",
    submission_service.respond_public_clarification,
    methods=["POST"],
    responses=error_responses(404, 409, 422, 429, 500),
)

router.add_api_route(
    "/api/superadmin/submissions",
    moderation_service.list_admin_submissions,
    methods=["GET"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 422, 500),
)
router.add_api_route(
    "/api/superadmin/submissions/{submission_id}",
    moderation_service.get_admin_submission,
    methods=["GET"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 404, 422, 500),
)
router.add_api_route(
    "/api/superadmin/submissions/{submission_id}",
    moderation_service.patch_admin_submission,
    methods=["PATCH"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/submissions/{submission_id}/status",
    moderation_service.change_admin_submission_status,
    methods=["POST"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/submissions/{submission_id}/notes",
    moderation_service.add_admin_submission_note,
    methods=["POST"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 404, 422, 500),
)
router.add_api_route(
    "/api/superadmin/submissions/{submission_id}/request-clarification",
    moderation_service.request_submission_clarification,
    methods=["POST"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/submissions/{submission_id}/approve",
    moderation_service.approve_submission,
    methods=["POST"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/submissions/{submission_id}/reject",
    moderation_service.reject_submission,
    methods=["POST"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/submissions/{submission_id}/create-object-draft",
    moderation_service.create_submission_object_draft,
    methods=["POST"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/submissions/{submission_id}/archive",
    moderation_service.archive_submission,
    methods=["POST"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/public/submissions",
    submission_service.submit_public_submission,
    methods=["POST"],
    response_model=SubmissionSubmitResponseDTO,
    responses=error_responses(400, 404, 409, 413, 422, 429, 503, 500),
)
router.add_api_route(
    "/api/public/submissions/{public_number}/status",
    submission_service.public_submission_status,
    methods=["GET"],
    response_model=SubmissionPublicStatusDTO,
    response_model_exclude_none=True,
    responses=error_responses(404, 422, 500),
)
