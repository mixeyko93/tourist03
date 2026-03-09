import unittest
from datetime import date
from unittest.mock import patch

from fastapi import HTTPException

from tourist03.schemas import BookingEditRequest, BookingOrderCreateRequest, OrderEditRequest
from tourist03.services import bookings


class BookingsServiceTests(unittest.TestCase):
    @patch("tourist03.services.bookings.bookings_repo.get_rooms_by_ids")
    def test_order_create_rejects_duplicate_rooms_before_repository(self, get_rooms_by_ids):
        payload = BookingOrderCreateRequest(
            camp_id=5,
            check_in=date(2026, 7, 10),
            check_out=date(2026, 7, 12),
            items=[
                {"room_id": 11, "adults": 2, "kids": 0},
                {"room_id": 11, "adults": 1, "kids": 1},
            ],
        )

        with self.assertRaises(HTTPException) as ctx:
            bookings.auth_order_create(payload, user={"id": 1})

        self.assertEqual(ctx.exception.status_code, 400)
        get_rooms_by_ids.assert_not_called()

    @patch("tourist03.services.bookings.log_user_event")
    @patch("tourist03.services.bookings.bookings_repo.update_order")
    @patch("tourist03.services.bookings.bookings_repo.order_has_conflict", return_value=True)
    @patch("tourist03.services.bookings.bookings_repo.get_order_edit_rows")
    def test_order_edit_stops_on_conflict(
        self,
        get_order_edit_rows,
        order_has_conflict,
        update_order,
        log_user_event,
    ):
        get_order_edit_rows.return_value = [
            {
                "id": 44,
                "room_id": 9,
                "camp_id": 5,
                "check_in": date(2026, 7, 10),
                "check_out": date(2026, 7, 12),
                "status": "pending",
                "payment_status": "unpaid",
            }
        ]
        payload = OrderEditRequest(check_in=date(2026, 7, 11), check_out=date(2026, 7, 13))

        with self.assertRaises(HTTPException) as ctx:
            bookings.auth_order_edit("group-1", payload, user={"id": 1})

        self.assertEqual(ctx.exception.status_code, 409)
        order_has_conflict.assert_called_once()
        update_order.assert_not_called()
        log_user_event.assert_not_called()

    @patch("tourist03.services.bookings.log_user_event")
    @patch("tourist03.services.bookings.bookings_repo.update_booking")
    @patch("tourist03.services.bookings.bookings_repo.booking_has_conflict_except", return_value=True)
    @patch("tourist03.services.bookings.bookings_repo.get_booking_edit_state")
    def test_booking_edit_stops_on_conflict(
        self,
        get_booking_edit_state,
        booking_has_conflict_except,
        update_booking,
        log_user_event,
    ):
        get_booking_edit_state.return_value = {
            "id": 44,
            "room_id": 9,
            "camp_id": 5,
            "check_in": date(2026, 7, 10),
            "check_out": date(2026, 7, 12),
            "status": "pending",
            "payment_status": "unpaid",
        }
        payload = BookingEditRequest(check_in=date(2026, 7, 11), check_out=date(2026, 7, 13))

        with self.assertRaises(HTTPException) as ctx:
            bookings.auth_booking_edit(44, payload, user={"id": 1})

        self.assertEqual(ctx.exception.status_code, 409)
        booking_has_conflict_except.assert_called_once()
        update_booking.assert_not_called()
        log_user_event.assert_not_called()


if __name__ == "__main__":
    unittest.main()
