from fastapi import APIRouter

from tourist03.api_responses import error_responses
from tourist03.dto.bookings import (
    BookingCreateResponseDTO,
    BookingItemResponseDTO,
    BookingListResponseDTO,
    OrderCreateResponseDTO,
    OrderItemResponseDTO,
    OrderListResponseDTO,
)
from tourist03.dto.common import OkResponseDTO, PaymentLinkResponseDTO
from tourist03.services import bookings as bookings_service


router = APIRouter()

router.add_api_route(
    "/api/auth/bookings",
    bookings_service.auth_my_bookings,
    methods=["GET"],
    response_model=BookingListResponseDTO,
    responses=error_responses(401, 422, 500),
)
router.add_api_route(
    "/api/auth/orders",
    bookings_service.auth_my_orders,
    methods=["GET"],
    response_model=OrderListResponseDTO,
    responses=error_responses(401, 422, 500),
)
router.add_api_route(
    "/api/auth/orders/{order_id}",
    bookings_service.auth_order_one,
    methods=["GET"],
    response_model=OrderItemResponseDTO,
    responses=error_responses(400, 401, 404, 422, 500),
)
router.add_api_route(
    "/api/auth/orders",
    bookings_service.auth_order_create,
    methods=["POST"],
    response_model=OrderCreateResponseDTO,
    responses=error_responses(400, 401, 409, 422, 500),
)
router.add_api_route(
    "/api/auth/orders/{order_id}/cancel",
    bookings_service.auth_order_cancel,
    methods=["POST"],
    response_model=OkResponseDTO,
    responses=error_responses(400, 401, 404, 422, 500),
)
router.add_api_route(
    "/api/auth/orders/{order_id}/pay",
    bookings_service.auth_order_pay,
    methods=["POST"],
    response_model=PaymentLinkResponseDTO,
    responses=error_responses(400, 401, 404, 422, 500),
)
router.add_api_route(
    "/api/auth/orders/{order_id}",
    bookings_service.auth_order_edit,
    methods=["PUT"],
    response_model=OkResponseDTO,
    responses=error_responses(400, 401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/auth/bookings",
    bookings_service.auth_booking_create,
    methods=["POST"],
    response_model=BookingCreateResponseDTO,
    responses=error_responses(400, 401, 409, 422, 500),
)
router.add_api_route(
    "/api/auth/bookings/{booking_id}",
    bookings_service.auth_booking_one,
    methods=["GET"],
    response_model=BookingItemResponseDTO,
    responses=error_responses(401, 404, 422, 500),
)
router.add_api_route(
    "/api/auth/bookings/{booking_id}",
    bookings_service.auth_booking_edit,
    methods=["PUT"],
    response_model=OkResponseDTO,
    responses=error_responses(400, 401, 404, 409, 422, 500),
)
router.add_api_route(
    "/api/auth/bookings/{booking_id}/cancel",
    bookings_service.auth_booking_cancel,
    methods=["POST"],
    response_model=OkResponseDTO,
    responses=error_responses(400, 401, 404, 422, 500),
)
router.add_api_route(
    "/api/auth/bookings/{booking_id}/pay",
    bookings_service.auth_booking_pay,
    methods=["POST"],
    response_model=PaymentLinkResponseDTO,
    responses=error_responses(400, 401, 404, 422, 500),
)
