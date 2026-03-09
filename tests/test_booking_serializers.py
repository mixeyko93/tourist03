import unittest
from datetime import date

from tourist03.serializers import bookings as booking_serializers


class BookingSerializersTests(unittest.TestCase):
    def test_serialize_booking_applies_public_defaults(self):
        result = booking_serializers.serialize_booking(
            {
                "id": 1,
                "camp_id": 2,
                "camp_name": None,
                "room_id": 3,
                "room_name": None,
                "check_in": date(2026, 7, 10),
                "check_out": date(2026, 7, 12),
                "guests_count": 4,
                "status": None,
                "payment_required": 0,
                "payment_status": None,
                "comment": None,
                "created_at": "created",
                "updated_at": "updated",
            }
        )

        self.assertEqual(result["camp_name"], "")
        self.assertEqual(result["room_name"], "")
        self.assertEqual(result["status"], "")
        self.assertFalse(result["payment_required"])
        self.assertEqual(result["payment_status"], "unpaid")
        self.assertEqual(result["comment"], "")

    def test_serialize_order_rolls_up_items_and_status(self):
        rows = [
            {
                "id": 11,
                "camp_id": 7,
                "camp_name": "Camp",
                "room_id": 101,
                "room_name": "A",
                "check_in": date(2026, 8, 1),
                "check_out": date(2026, 8, 3),
                "guests_count": 2,
                "status": "confirmed",
                "payment_required": True,
                "payment_status": "unpaid",
                "comment": "",
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-02T00:00:00",
            },
            {
                "id": 12,
                "camp_id": 7,
                "camp_name": "Camp",
                "room_id": 102,
                "room_name": "B",
                "check_in": date(2026, 8, 1),
                "check_out": date(2026, 8, 3),
                "guests_count": 3,
                "status": "pending",
                "payment_required": False,
                "payment_status": "paid",
                "comment": "note",
                "created_at": "2026-01-03T00:00:00",
                "updated_at": "2026-01-04T00:00:00",
            },
        ]

        result = booking_serializers.serialize_order("order-1", rows)

        self.assertEqual(result["order_id"], "order-1")
        self.assertEqual(result["guests_count"], 5)
        self.assertEqual(result["status"], "pending")
        self.assertTrue(result["payment_required"])
        self.assertEqual(result["payment_status"], "unpaid")
        self.assertEqual(result["comment"], "note")
        self.assertEqual(len(result["items"]), 2)

    def test_serialize_admin_booking_preserves_admin_shape(self):
        row = {
            "id": 5,
            "camp_id": 9,
            "camp_name": None,
            "room_id": None,
            "room_name": None,
            "check_in": "in",
            "check_out": "out",
            "guests_count": 2,
            "status": None,
            "source": "crm",
            "payment_status": None,
            "payment_required": None,
            "user_id": None,
            "user_name": None,
            "user_phone": None,
            "user_email": "",
            "guest_name": None,
            "guest_phone": None,
            "guest_email": None,
            "comment": None,
        }

        result = booking_serializers.serialize_admin_booking(row)

        self.assertEqual(result["id"], 5)
        self.assertIsNone(result["camp_name"])
        self.assertEqual(result["source"], "crm")
        self.assertIsNone(result["guest_email"])


if __name__ == "__main__":
    unittest.main()
