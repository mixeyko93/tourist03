from fastapi import APIRouter, Depends

from tourist03.api_responses import error_responses
from tourist03.dto.bookings import AdminBookingCreateResponseDTO, AdminBookingDTO
from tourist03.dto.common import OkResponseDTO
from tourist03.dto.catalog import UploadResponseDTO
from tourist03.schemas import AdminMeResponse
from tourist03.security import get_current_admin
from tourist03.services import admin as admin_service
from tourist03.services import catalog as catalog_service


router = APIRouter()

router.add_api_route("/api/admin/login", admin_service.admin_login, methods=["POST"], responses=error_responses(400, 422, 500))
router.add_api_route("/api/admin/logout", admin_service.admin_logout, methods=["POST"], responses=error_responses(500))
router.add_api_route(
    "/api/public/ui-overrides/{override_key}",
    admin_service.api_public_ui_override,
    methods=["GET"],
    responses=error_responses(404, 500),
)
router.add_api_route(
    "/api/admin/me",
    admin_service.admin_me,
    methods=["GET"],
    response_model=AdminMeResponse,
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/admin/profile-switcher",
    admin_service.api_admin_profile_switcher,
    methods=["GET"],
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/admin/profile-switcher/setup-pin",
    admin_service.api_admin_profile_setup_pin,
    methods=["POST"],
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/admin/profile-switcher/switch",
    admin_service.api_admin_profile_switch,
    methods=["POST"],
    responses=error_responses(400, 401, 403, 404, 422, 429, 500),
)
router.add_api_route(
    "/api/admin/profile-switcher/forgot-pin",
    admin_service.api_admin_profile_forgot_pin,
    methods=["POST"],
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/profile-switcher/reset-pin",
    admin_service.api_admin_profile_reset_pin,
    methods=["POST"],
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/ui-overrides/{override_key}",
    admin_service.api_admin_save_ui_override,
    methods=["PUT"],
    responses=error_responses(401, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/my-camps",
    admin_service.api_admin_my_camps,
    methods=["GET"],
    responses=error_responses(401, 500),
)
router.add_api_route(
    "/api/admin/events",
    admin_service.api_admin_events,
    methods=["GET"],
    responses=error_responses(400, 401, 403, 422, 500),
)
router.add_api_route(
    "/api/admin/events/summary",
    admin_service.api_admin_event_summary,
    methods=["GET"],
    responses=error_responses(401, 403, 422, 500),
)
router.add_api_route(
    "/api/admin/events/{event_id}",
    admin_service.api_admin_update_event_status,
    methods=["PATCH"],
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/change-requests",
    admin_service.api_admin_change_requests,
    methods=["GET"],
    responses=error_responses(400, 401, 403, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/change-requests",
    admin_service.api_admin_create_change_request,
    methods=["POST"],
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/change-requests/{request_id}",
    admin_service.api_admin_change_request_action,
    methods=["PATCH"],
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/admin/bookings",
    admin_service.api_admin_bookings,
    methods=["GET"],
    response_model=list[AdminBookingDTO],
    responses=error_responses(401, 403, 422, 500),
)
router.add_api_route(
    "/api/admin/guests",
    admin_service.api_admin_guests,
    methods=["GET"],
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
    "/api/admin/camps/{camp_id}/shifts",
    admin_service.api_admin_camp_shifts,
    methods=["GET"],
    responses=error_responses(401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/shifts/settings",
    admin_service.api_admin_update_shift_settings,
    methods=["PUT"],
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/shift-rules",
    admin_service.api_admin_create_shift_rule,
    methods=["POST"],
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/shift-rules/{rule_id}",
    admin_service.api_admin_update_shift_rule,
    methods=["PUT"],
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/shift-rules/{rule_id}",
    admin_service.api_admin_delete_shift_rule,
    methods=["DELETE"],
    responses=error_responses(401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/staff",
    admin_service.api_admin_camp_staff,
    methods=["GET"],
    responses=error_responses(401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/staff",
    admin_service.api_admin_create_staff,
    methods=["POST"],
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/staff/{staff_id}",
    admin_service.api_admin_update_staff,
    methods=["PUT"],
    responses=error_responses(400, 401, 403, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/staff/{staff_id}/telegram-link",
    admin_service.api_admin_issue_staff_telegram_link,
    methods=["POST"],
    responses=error_responses(401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/audit-log",
    admin_service.api_admin_audit_log,
    methods=["GET"],
    responses=error_responses(401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/rooms",
    admin_service.api_admin_camp_rooms,
    methods=["GET"],
    responses=error_responses(401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/services",
    admin_service.api_admin_camp_services,
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
    "/api/admin/camps/{camp_id}/services",
    admin_service.api_admin_create_service,
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
    "/api/admin/camps/{camp_id}/services/{service_id}",
    admin_service.api_admin_update_service,
    methods=["PUT"],
    responses=error_responses(400, 401, 403, 404, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/rooms/{room_id}",
    admin_service.api_admin_delete_room,
    methods=["DELETE"],
    responses=error_responses(401, 403, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/admin/camps/{camp_id}/services/{service_id}",
    admin_service.api_admin_delete_service,
    methods=["DELETE"],
    responses=error_responses(401, 403, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/admin/upload",
    catalog_service.api_upload,
    methods=["POST"],
    dependencies=[Depends(get_current_admin)],
    response_model=UploadResponseDTO,
    responses=error_responses(400, 401, 422, 500),
)
