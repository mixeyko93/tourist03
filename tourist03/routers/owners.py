from fastapi import APIRouter, Depends

from tourist03.api_responses import error_responses
from tourist03.dto.owners import (
    OwnerAccountCreateRequest,
    OwnerAccountAdminPatchRequest,
    OwnerCampLinkRequest,
    OwnerChangeApplyRequest,
    OwnerChangeDecisionRequest,
    OwnerChangePatchRequest,
    OwnerEntityCreateRequest,
    OwnerForgotPasswordRequest,
    OwnerLoginRequest,
    OwnerPasswordPatchRequest,
    OwnerProfilePatchRequest,
    OwnerResetPasswordRequest,
)
from tourist03.owner_security import get_current_owner
from tourist03.security import get_superadmin
from tourist03.services import owners as owner_service


router = APIRouter()
owner_guard = [Depends(get_current_owner)]
superadmin_guard = [Depends(get_superadmin)]

router.add_api_route("/api/owner/auth/session", owner_service.owner_session, methods=["GET"], responses=error_responses(401, 500))
router.add_api_route("/api/owner/me", owner_service.owner_session, methods=["GET"], responses=error_responses(401, 500))
router.add_api_route("/api/owner/auth/login", owner_service.owner_login, methods=["POST"], responses=error_responses(401, 422, 500))
router.add_api_route("/api/owner/auth/logout", owner_service.owner_logout, methods=["POST"], responses=error_responses(500))
router.add_api_route("/api/owner/auth/forgot-password", owner_service.owner_forgot_password, methods=["POST"], responses=error_responses(422, 500))
router.add_api_route("/api/owner/auth/reset-password", owner_service.owner_reset_password, methods=["POST"], responses=error_responses(400, 422, 500))
router.add_api_route("/api/owner/profile", owner_service.owner_update_profile, methods=["PATCH"], dependencies=owner_guard, responses=error_responses(401, 422, 500))
router.add_api_route("/api/owner/profile/password", owner_service.owner_change_password, methods=["PATCH"], dependencies=owner_guard, responses=error_responses(400, 401, 422, 500))
router.add_api_route("/api/owner/dashboard", owner_service.owner_dashboard, methods=["GET"], dependencies=owner_guard, responses=error_responses(401, 500))
router.add_api_route("/api/owner/camps", owner_service.owner_list_camps, methods=["GET"], dependencies=owner_guard, responses=error_responses(401, 500))
router.add_api_route("/api/owner/camps/{camp_id}", owner_service.owner_camp_detail, methods=["GET"], dependencies=owner_guard, responses=error_responses(401, 404, 500))
router.add_api_route("/api/owner/camps/{camp_id}/unpublish", owner_service.owner_unpublish_camp, methods=["POST"], dependencies=owner_guard, responses=error_responses(401, 404, 500))
router.add_api_route("/api/owner/entities", owner_service.owner_list_entities, methods=["GET"], dependencies=owner_guard, responses=error_responses(401, 500))
router.add_api_route("/api/owner/entities", owner_service.owner_create_entity, methods=["POST"], dependencies=owner_guard, responses=error_responses(401, 404, 422, 500))
router.add_api_route("/api/owner/entities/{entity_id}", owner_service.owner_entity_detail, methods=["GET"], dependencies=owner_guard, responses=error_responses(401, 404, 500))
router.add_api_route("/api/owner/entities/{camp_id}/changes", owner_service.owner_create_change, methods=["POST"], dependencies=owner_guard, responses=error_responses(401, 404, 500))
router.add_api_route("/api/owner/changes", owner_service.owner_list_changes, methods=["GET"], dependencies=owner_guard, responses=error_responses(401, 500))
router.add_api_route("/api/owner/changes/{change_id}", owner_service.owner_get_change, methods=["GET"], dependencies=owner_guard, responses=error_responses(401, 404, 500))
router.add_api_route("/api/owner/camps/{camp_id}/changes", owner_service.owner_create_change, methods=["POST"], dependencies=owner_guard, responses=error_responses(401, 404, 500))
router.add_api_route("/api/owner/changes/{change_id}", owner_service.owner_save_change, methods=["PATCH"], dependencies=owner_guard, responses=error_responses(401, 404, 409, 422, 500))
router.add_api_route("/api/owner/changes/{change_id}/submit", owner_service.owner_submit_change, methods=["POST"], dependencies=owner_guard, responses=error_responses(401, 404, 409, 422, 500))
router.add_api_route("/api/owner/changes/{change_id}/withdraw", owner_service.owner_withdraw_change, methods=["POST"], dependencies=owner_guard, responses=error_responses(401, 404, 409, 500))
router.add_api_route("/api/owner/changes/{change_id}/media", owner_service.owner_upload_change_media, methods=["POST"], dependencies=owner_guard, responses=error_responses(400, 401, 404, 409, 422, 500))
router.add_api_route("/api/owner/changes/{change_id}/media/{media_id}", owner_service.owner_delete_change_media, methods=["DELETE"], dependencies=owner_guard, responses=error_responses(401, 404, 500))
router.add_api_route("/api/owner/changes/{change_id}/published-media/{media_id}", owner_service.owner_remove_published_media, methods=["DELETE"], dependencies=owner_guard, responses=error_responses(401, 404, 409, 500))
router.add_api_route("/api/owner/change-media/{preview_token}", owner_service.owner_change_media, methods=["GET"], dependencies=owner_guard, responses=error_responses(401, 404, 500))

router.add_api_route("/api/superadmin/owner-changes", owner_service.superadmin_list_owner_changes, methods=["GET"], dependencies=superadmin_guard, responses=error_responses(401, 500))
router.add_api_route("/api/superadmin/owner-changes/{change_id}", owner_service.superadmin_get_owner_change, methods=["GET"], dependencies=superadmin_guard, responses=error_responses(401, 404, 500))
router.add_api_route("/api/superadmin/owner-changes/{change_id}/decision", owner_service.superadmin_decide_owner_change, methods=["POST"], dependencies=superadmin_guard, responses=error_responses(401, 404, 409, 500))
router.add_api_route("/api/superadmin/owner-changes/{change_id}/apply", owner_service.superadmin_apply_owner_change, methods=["POST"], dependencies=superadmin_guard, responses=error_responses(401, 404, 409, 500))
router.add_api_route("/api/superadmin/owners", owner_service.superadmin_list_owners, methods=["GET"], dependencies=superadmin_guard, responses=error_responses(401, 500))
router.add_api_route("/api/superadmin/owners", owner_service.superadmin_create_owner, methods=["POST"], dependencies=superadmin_guard, responses=error_responses(401, 409, 422, 500))
router.add_api_route("/api/superadmin/owners/{owner_id}", owner_service.superadmin_update_owner, methods=["PATCH"], dependencies=superadmin_guard, responses=error_responses(401, 404, 422, 500))
router.add_api_route("/api/superadmin/owners/{owner_id}/camps", owner_service.superadmin_link_owner_camp, methods=["POST"], dependencies=superadmin_guard, responses=error_responses(401, 404, 422, 500))
