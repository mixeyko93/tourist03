from fastapi import APIRouter, Depends

from tourist03.api_responses import error_responses
from tourist03.dto.superadmin import (
    SuperAdminAccountDTO,
    SuperAdminAuditRecordDTO,
    SuperAdminCampSummaryDTO,
    SuperAdminCreateAccountResponseDTO,
    SuperAdminCreateRootAccountResponseDTO,
    SuperAdminMediaQueueItemDTO,
    SuperAdminRootAccountDTO,
    SuperAdminSystemEventDTO,
    SuperAdminSessionResponseDTO,
    SuperAdminUpdateAccountResponseDTO,
    SuperAdminUserHistoryResponseDTO,
    SuperAdminUserSummaryDTO,
)
from tourist03.security import get_superadmin
from tourist03.services import superadmin as superadmin_service


router = APIRouter()
superadmin_guard = [Depends(get_superadmin)]

router.add_api_route(
    "/api/superadmin/session",
    superadmin_service.superadmin_session,
    methods=["GET"],
    response_model=SuperAdminSessionResponseDTO,
    responses=error_responses(500),
)
router.add_api_route(
    "/api/superadmin/session",
    superadmin_service.superadmin_login,
    methods=["POST"],
    response_model=SuperAdminSessionResponseDTO,
    responses=error_responses(401, 422, 500),
)
router.add_api_route(
    "/api/superadmin/session",
    superadmin_service.superadmin_logout,
    methods=["DELETE"],
    response_model=SuperAdminSessionResponseDTO,
    responses=error_responses(500),
)
router.add_api_route(
    "/api/superadmin/users/{user_id}/history",
    superadmin_service.superadmin_user_history,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=SuperAdminUserHistoryResponseDTO,
    responses=error_responses(401, 404, 422, 500),
)
router.add_api_route(
    "/api/superadmin/camps",
    superadmin_service.superadmin_list_camps,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=list[SuperAdminCampSummaryDTO],
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/superadmin/camps/{camp_id}",
    superadmin_service.superadmin_camp_editor,
    methods=["GET"],
    dependencies=superadmin_guard,
    responses=error_responses(401, 404, 422, 500),
)
router.add_api_route(
    "/api/superadmin/accounts",
    superadmin_service.superadmin_list_accounts,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=list[SuperAdminAccountDTO],
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/admincamps/accounts",
    superadmin_service.superadmin_list_accounts,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=list[SuperAdminAccountDTO],
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/superadmin/accounts",
    superadmin_service.create_camp_admin_account,
    methods=["POST"],
    dependencies=superadmin_guard,
    response_model=SuperAdminCreateAccountResponseDTO,
    responses=error_responses(400, 401, 422, 500),
)
router.add_api_route(
    "/api/admincamps/accounts",
    superadmin_service.create_camp_admin_account,
    methods=["POST"],
    dependencies=superadmin_guard,
    response_model=SuperAdminCreateAccountResponseDTO,
    responses=error_responses(400, 401, 422, 500),
)
router.add_api_route(
    "/api/admincamps/account",
    superadmin_service.create_camp_admin_account,
    methods=["POST"],
    dependencies=superadmin_guard,
    response_model=SuperAdminCreateAccountResponseDTO,
    responses=error_responses(400, 401, 422, 500),
)
router.add_api_route(
    "/api/admin/accounts",
    superadmin_service.create_camp_admin_account,
    methods=["POST"],
    dependencies=superadmin_guard,
    response_model=SuperAdminCreateAccountResponseDTO,
    responses=error_responses(400, 401, 422, 500),
)
router.add_api_route(
    "/api/admin/account",
    superadmin_service.create_camp_admin_account,
    methods=["POST"],
    dependencies=superadmin_guard,
    response_model=SuperAdminCreateAccountResponseDTO,
    responses=error_responses(400, 401, 422, 500),
)
router.add_api_route(
    "/api/superadmin/accounts/{account_id}",
    superadmin_service.update_camp_admin_account,
    methods=["PATCH"],
    dependencies=superadmin_guard,
    response_model=SuperAdminUpdateAccountResponseDTO,
    responses=error_responses(400, 401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/users",
    superadmin_service.superadmin_list_users,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=list[SuperAdminUserSummaryDTO],
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/superadmin/events",
    superadmin_service.superadmin_list_events,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=list[SuperAdminSystemEventDTO],
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/superadmin/media",
    superadmin_service.superadmin_list_media_queue,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=list[SuperAdminMediaQueueItemDTO],
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/superadmin/media/{entity_type}/{media_id}/moderation",
    superadmin_service.superadmin_update_media_moderation,
    methods=["PATCH"],
    dependencies=superadmin_guard,
    response_model=SuperAdminUpdateAccountResponseDTO,
    responses=error_responses(400, 401, 404, 422, 500),
)
router.add_api_route(
    "/api/superadmin/superadmins",
    superadmin_service.superadmin_list_root_accounts,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=list[SuperAdminRootAccountDTO],
    responses=error_responses(401, 403, 500),
)
router.add_api_route(
    "/api/superadmin/superadmins",
    superadmin_service.create_root_superadmin_account,
    methods=["POST"],
    dependencies=superadmin_guard,
    response_model=SuperAdminCreateRootAccountResponseDTO,
    responses=error_responses(400, 401, 403, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/superadmins/{account_id}",
    superadmin_service.update_root_superadmin_account,
    methods=["PATCH"],
    dependencies=superadmin_guard,
    response_model=SuperAdminUpdateAccountResponseDTO,
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/superadmin/superadmins/{account_id}",
    superadmin_service.archive_root_superadmin_account,
    methods=["DELETE"],
    dependencies=superadmin_guard,
    response_model=SuperAdminUpdateAccountResponseDTO,
    responses=error_responses(401, 403, 404, 409, 500),
)
router.add_api_route(
    "/api/superadmin/superadmins/{account_id}/restore",
    superadmin_service.restore_root_superadmin_account,
    methods=["POST"],
    dependencies=superadmin_guard,
    response_model=SuperAdminUpdateAccountResponseDTO,
    responses=error_responses(401, 403, 404, 409, 500),
)
router.add_api_route(
    "/api/superadmin/audit-log",
    superadmin_service.superadmin_list_audit_records,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=list[SuperAdminAuditRecordDTO],
    responses=error_responses(401, 403, 500),
)
router.add_api_route(
    "/api/admincamps/accounts/{account_id}",
    superadmin_service.update_camp_admin_account,
    methods=["PATCH"],
    dependencies=superadmin_guard,
    response_model=SuperAdminUpdateAccountResponseDTO,
    responses=error_responses(400, 401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/admin/accounts/{account_id}",
    superadmin_service.update_camp_admin_account,
    methods=["PATCH"],
    dependencies=superadmin_guard,
    response_model=SuperAdminUpdateAccountResponseDTO,
    responses=error_responses(400, 401, 404, 409, 422, 500),
)
