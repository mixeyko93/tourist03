import unittest
from datetime import date

from fastapi import HTTPException

from tourist03.domain import bookings as booking_domain


class BookingDomainTests(unittest.TestCase):
    def test_resolve_guests_count_from_adults_and_kids(self):
        guests_count = booking_domain.resolve_guests_count(None, adults=2, kids=1)
        self.assertEqual(guests_count, 3)

    def test_status_for_history_marks_past_booking_completed(self):
        status = booking_domain.status_for_history("pending", date(2026, 1, 5), today=date(2026, 1, 10))
        self.assertEqual(status, "completed")
        self.assertTrue(booking_domain.is_history_booking("pending", date(2026, 1, 5), today=date(2026, 1, 10)))

    def test_normalize_admin_booking_status_rejects_unknown_value(self):
        with self.assertRaises(HTTPException) as ctx:
            booking_domain.normalize_admin_booking_status("mystery")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_paid_status_forces_payment_required_off(self):
        self.assertFalse(booking_domain.coerce_payment_required("paid", True, default=False))
        self.assertFalse(booking_domain.coerce_payment_required("cash", None, default=None))

    def test_normalize_admin_payment_status_rejects_blank_on_optional_update(self):
        with self.assertRaises(HTTPException) as ctx:
            booking_domain.normalize_admin_payment_status("", allow_none=True)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_ensure_payable_requires_confirmed_unpaid_requested_booking(self):
        with self.assertRaises(HTTPException) as ctx:
            booking_domain.ensure_payable("pending", True, "unpaid")
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            booking_domain.ensure_payable("confirmed", False, "unpaid")
        self.assertEqual(ctx.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx:
            booking_domain.ensure_payable("confirmed", True, "paid")
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
