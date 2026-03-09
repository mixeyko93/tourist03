from fastapi import APIRouter

from tourist03.dto.bookings import AdminBookingCreateResponseDTO, AdminBookingDTO
from tourist03.dto.common import OkResponseDTO
from tourist03.schemas import AdminMeResponse
from tourist03.services import admin as admin_service


router = APIRouter()

router.add_api_route("/api/admin/login", admin_service.admin_login, methods=["POST"])
router.add_api_route("/api/admin/logout", admin_service.admin_logout, methods=["POST"])
router.add_api_route("/api/admin/me", admin_service.admin_me, methods=["GET"], response_model=AdminMeResponse)
router.add_api_route("/api/admin/my-camps", admin_service.api_admin_my_camps, methods=["GET"])
router.add_api_route("/api/admin/bookings", admin_service.api_admin_bookings, methods=["GET"], response_model=list[AdminBookingDTO])
router.add_api_route(
    "/api/admin/bookings",
    admin_service.api_admin_create_booking,
    methods=["POST"],
    response_model=AdminBookingCreateResponseDTO,
)
router.add_api_route(
    "/api/admin/bookings/{booking_id}",
    admin_service.api_admin_update_booking,
    methods=["PATCH"],
    response_model=OkResponseDTO,
)
router.add_api_route("/api/admin/calendar", admin_service.api_admin_calendar, methods=["GET"])
router.add_api_route(
    "/api/admin/bookings/calendar",
    admin_service.api_admin_bookings_calendar,
    methods=["GET"],
    response_model=list[AdminBookingDTO],
)
