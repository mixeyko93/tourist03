from fastapi import APIRouter

from tourist03.services import bookings as bookings_service


router = APIRouter()

router.add_api_route("/api/auth/bookings", bookings_service.auth_my_bookings, methods=["GET"])
router.add_api_route("/api/auth/orders", bookings_service.auth_my_orders, methods=["GET"])
router.add_api_route("/api/auth/orders/{order_id}", bookings_service.auth_order_one, methods=["GET"])
router.add_api_route("/api/auth/orders", bookings_service.auth_order_create, methods=["POST"])
router.add_api_route("/api/auth/orders/{order_id}/cancel", bookings_service.auth_order_cancel, methods=["POST"])
router.add_api_route("/api/auth/orders/{order_id}/pay", bookings_service.auth_order_pay, methods=["POST"])
router.add_api_route("/api/auth/orders/{order_id}", bookings_service.auth_order_edit, methods=["PUT"])
router.add_api_route("/api/auth/bookings", bookings_service.auth_booking_create, methods=["POST"])
router.add_api_route("/api/auth/bookings/{booking_id}", bookings_service.auth_booking_one, methods=["GET"])
router.add_api_route("/api/auth/bookings/{booking_id}", bookings_service.auth_booking_edit, methods=["PUT"])
router.add_api_route("/api/auth/bookings/{booking_id}/cancel", bookings_service.auth_booking_cancel, methods=["POST"])
router.add_api_route("/api/auth/bookings/{booking_id}/pay", bookings_service.auth_booking_pay, methods=["POST"])
