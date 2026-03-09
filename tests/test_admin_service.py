import unittest
from unittest.mock import patch

from fastapi import HTTPException

from tourist03.schemas import AdminCreateBookingRequest, BookingAdminUpdateRequest
from tourist03.services import admin


class AdminServiceTests(unittest.TestCase):
    @patch("tourist03.services.admin.admin_repo.booking_has_conflict", return_value=True)
    @patch("tourist03.services.admin.admin_repo.room_exists_for_camp", return_value=True)
    @patch("tourist03.services.admin._get_admin_camp_ids", return_value=[10])
    def test_create_booking_returns_conflict_for_busy_room(
        self,
        get_admin_camp_ids,
        room_exists_for_camp,
        booking_has_conflict,
    ):
        payload = AdminCreateBookingRequest(
            camp_id=10,
            room_id=3,
            check_in="2026-08-01",
            check_out="2026-08-05",
            guests_count=2,
        )

        with self.assertRaises(HTTPException) as ctx:
            admin.api_admin_create_booking(payload, admin={"id": 2})

        self.assertEqual(ctx.exception.status_code, 409)
        booking_has_conflict.assert_called_once()
        room_exists_for_camp.assert_called_once_with(3, 10)
        get_admin_camp_ids.assert_called_once_with(2)

    @patch("tourist03.services.admin.log_user_event")
    @patch("tourist03.services.admin.admin_repo.update_admin_booking", return_value=True)
    @patch("tourist03.services.admin.admin_repo.get_booking_by_id")
    @patch("tourist03.services.admin._get_admin_camp_ids", return_value=[10])
    def test_update_booking_paid_forces_payment_required_false(
        self,
        get_admin_camp_ids,
        get_booking_by_id,
        update_admin_booking,
        log_user_event,
    ):
        get_booking_by_id.return_value = {
            "id": 5,
            "camp_id": 10,
            "user_id": 77,
            "status": "confirmed",
            "payment_status": "unpaid",
            "payment_required": True,
        }
        payload = BookingAdminUpdateRequest(payment_status="paid")

        result = admin.api_admin_update_booking(5, payload, admin={"id": 2})

        self.assertEqual(result, {"ok": True})
        update_admin_booking.assert_called_once_with(
            5,
            status=None,
            payment_status="paid",
            payment_required=False,
        )
        log_user_event.assert_called_once()
        get_admin_camp_ids.assert_called_once_with(2)

    @patch("tourist03.services.admin.admin_repo.update_admin_booking", return_value=False)
    @patch("tourist03.services.admin.admin_repo.get_booking_by_id")
    @patch("tourist03.services.admin._get_admin_camp_ids", return_value=[10])
    def test_update_booking_normalizes_status_before_repository(
        self,
        get_admin_camp_ids,
        get_booking_by_id,
        update_admin_booking,
    ):
        get_booking_by_id.return_value = {
            "id": 5,
            "camp_id": 10,
            "user_id": None,
            "status": "pending",
            "payment_status": "unpaid",
            "payment_required": False,
        }
        payload = BookingAdminUpdateRequest(status="CONFIRMED")

        result = admin.api_admin_update_booking(5, payload, admin={"id": 2})

        self.assertEqual(result, {"ok": True})
        update_admin_booking.assert_called_once_with(
            5,
            status="confirmed",
            payment_status=None,
            payment_required=None,
        )
        get_admin_camp_ids.assert_called_once_with(2)


if __name__ == "__main__":
    unittest.main()
