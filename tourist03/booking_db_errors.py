from psycopg2 import errors

from tourist03.domain import bookings as booking_domain


class BookingConflictError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class BookingValidationError(Exception):
    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def translate_booking_integrity_error(exc: Exception, *, conflict_detail: str) -> None:
    constraint_name = getattr(getattr(exc, "diag", None), "constraint_name", "") or ""

    if isinstance(exc, errors.ExclusionViolation) or constraint_name == booking_domain.BOOKING_OVERLAP_CONSTRAINT:
        raise BookingConflictError(conflict_detail) from exc

    if isinstance(exc, errors.CheckViolation):
        detail = booking_domain.BOOKING_CONSTRAINT_DETAILS.get(constraint_name)
        if detail:
            raise BookingValidationError(detail) from exc
