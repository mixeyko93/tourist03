from fastapi import APIRouter, Depends

from tourist03.api_responses import error_responses
from tourist03.dto.auth import (
    AuthProfileUpdateResponseDTO,
    AuthTokenUserResponseDTO,
    AuthUserResponseDTO,
    AuthUsersListItemDTO,
)
from tourist03.dto.common import OkResponseDTO
from tourist03.security import get_superadmin
from tourist03.services import auth as auth_service


router = APIRouter()
superadmin_guard = [Depends(get_superadmin)]

router.add_api_route(
    "/api/users",
    auth_service.api_users_list,
    methods=["GET"],
    dependencies=superadmin_guard,
    response_model=list[AuthUsersListItemDTO],
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/auth/register/start",
    auth_service.auth_register_start,
    methods=["POST"],
    response_model=OkResponseDTO,
    responses=error_responses(400, 409, 422, 500),
)
router.add_api_route(
    "/api/auth/register/verify-phone",
    auth_service.auth_register_verify_phone,
    methods=["POST"],
    response_model=AuthTokenUserResponseDTO,
    responses=error_responses(400, 404, 422, 500),
)
router.add_api_route(
    "/api/auth/register/verify-email",
    auth_service.auth_register_verify_email,
    methods=["POST"],
    response_model=AuthTokenUserResponseDTO,
    responses=error_responses(400, 404, 422, 500),
)
router.add_api_route(
    "/api/auth/register/skip-email",
    auth_service.auth_register_skip_email,
    methods=["POST"],
    response_model=AuthTokenUserResponseDTO,
    responses=error_responses(400, 404, 422, 500),
)
router.add_api_route(
    "/api/auth/login/start",
    auth_service.auth_login_start,
    methods=["POST"],
    response_model=OkResponseDTO,
    responses=error_responses(400, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/auth/login/verify",
    auth_service.auth_login_verify,
    methods=["POST"],
    response_model=AuthTokenUserResponseDTO,
    responses=error_responses(400, 404, 422, 500),
)
router.add_api_route(
    "/api/auth/me",
    auth_service.auth_me,
    methods=["GET"],
    response_model=AuthUserResponseDTO,
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/auth/logout",
    auth_service.auth_logout,
    methods=["POST"],
    response_model=OkResponseDTO,
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/auth/profile",
    auth_service.auth_update_profile,
    methods=["PUT"],
    response_model=AuthProfileUpdateResponseDTO,
    responses=error_responses(401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/auth/profile/verify-phone",
    auth_service.auth_profile_verify_phone,
    methods=["POST"],
    response_model=AuthUserResponseDTO,
    responses=error_responses(400, 401, 404, 422, 500),
)
router.add_api_route(
    "/api/auth/profile/verify-email",
    auth_service.auth_profile_verify_email,
    methods=["POST"],
    response_model=AuthUserResponseDTO,
    responses=error_responses(400, 401, 404, 422, 500),
)
