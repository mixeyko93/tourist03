from fastapi import APIRouter

from tourist03.api_responses import error_responses
from tourist03.dto.bookings import AdminBookingCreateResponseDTO, AdminBookingDTO
from tourist03.dto.common import OkResponseDTO
from tourist03.schemas import AdminMeResponse
from tourist03.services import admin as admin_service


router = APIRouter()

router.add_api_route("/api/admin/login", admin_service.admin_login, methods=["POST"], responses=error_responses(400, 422, 500))
router.add_api_route("/api/admin/logout", admin_service.admin_logout, methods=["POST"], responses=error_responses(500))
router.add_api_route(
    "/api/admin/me",
    admin_service.admin_me,
    methods=["GET"],
    response_model=AdminMeResponse,
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/admin/my-camps",
    admin_service.api_admin_my_camps,
    methods=["GET"],
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/admin/bookings",
    admin_service.api_admin_bookings,
    methods=["GET"],
    response_model=list[AdminBookingDTO],
    responses=error_responses(401, 403, 422, 500),
)
router.add_api_route(
    "/api/admin/bookings",
    admin_service.api_admin_create_booking,
    methods=["POST"],
    response_model=AdminBookingCreateResponseDTO,
    responses=error_responses(400, 401, 403, 409, 422, 500),
)
router.add_api_route(
    "/api/admin/bookings/{booking_id}",
    admin_service.api_admin_update_booking,
    methods=["PATCH"],
    response_model=OkResponseDTO,
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/calendar",
    admin_service.api_admin_calendar,
    methods=["GET"],
    responses=error_responses(401, 403, 422, 500),
)
router.add_api_route(
    "/api/admin/bookings/calendar",
    admin_service.api_admin_bookings_calendar,
    methods=["GET"],
    response_model=list[AdminBookingDTO],
    responses=error_responses(401, 403, 422, 500),
)
router.add_api_route(
    "/api/admin/calendar-feed",
    admin_service.api_admin_calendar_feed,
    methods=["GET"],
    responses=error_responses(401, 403, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/profile",
    admin_service.api_admin_camp_profile,
    methods=["GET"],
    responses=error_responses(401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/profile",
    admin_service.api_admin_update_camp_profile,
    methods=["PUT"],
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/rooms",
    admin_service.api_admin_camp_rooms,
    methods=["GET"],
    responses=error_responses(401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/rooms",
    admin_service.api_admin_create_room,
    methods=["POST"],
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/rooms/{room_id}",
    admin_service.api_admin_update_room,
    methods=["PUT"],
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/rooms/{room_id}",
    admin_service.api_admin_delete_room,
    methods=["DELETE"],
    responses=error_responses(401, 403, 404, 409, 422, 500),
)
