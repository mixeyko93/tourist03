from datetime import date
from typing import Optional, Sequence

from fastapi import HTTPException


CONFLICT_IGNORED_STATUSES = (
    "rejected",
    "cancelled_by_user",
    "cancelled",
    "cancelled_by_base",
    "expired_pending",
    "no_show",
)
TERMINAL_BOOKING_STATUSES = (
    "completed",
    "rejected",
    "cancelled_by_user",
    "cancelled",
    "cancelled_by_base",
    "expired_pending",
    "no_show",
)
ACTIVE_BOOKING_STATUSES = ("pending", "awaiting_confirmation", "confirmed", "awaiting_payment", "checked_in")
ALLOWED_BOOKING_STATUSES = (
    "pending",
    "awaiting_confirmation",
    "confirmed",
    "awaiting_payment",
    "checked_in",
    "rejected",
    "completed",
    "no_show",
    "cancelled_by_user",
    "cancelled",
    "cancelled_by_base",
    "expired_pending",
)
ALLOWED_ADMIN_BOOKING_STATUSES = ALLOWED_BOOKING_STATUSES
ALLOWED_PAYMENT_STATUSES = (
    "unpaid",
    "awaiting_prepayment",
    "partially_paid",
    "paid",
    "cash",
    "refund_partial",
    "refund_full",
    "awaiting_refund",
    "failed",
    "chargeback",
    "overpaid",
)
PAYABLE_PAYMENT_STATUSES = ("unpaid", "awaiting_prepayment", "partially_paid", "failed")
SETTLED_PAYMENT_STATUSES = ("paid", "cash", "refund_partial", "refund_full", "awaiting_refund", "chargeback", "overpaid")

BOOKING_DATE_RANGE_CONSTRAINT = "bookings_check_valid_date_range"
BOOKING_GUESTS_COUNT_CONSTRAINT = "bookings_check_positive_guests"
BOOKING_STATUS_CONSTRAINT = "bookings_check_status"
BOOKING_PAYMENT_STATUS_CONSTRAINT = "bookings_check_payment_status"
BOOKING_PAYMENT_REQUIRED_CONSTRAINT = "bookings_check_payment_required_consistency"
BOOKING_OVERLAP_CONSTRAINT = "bookings_no_overlap_per_room"

BOOKING_CONSTRAINT_DETAILS = {
    BOOKING_DATE_RANGE_CONSTRAINT: "Дата выезда должна быть позже даты заезда",
    BOOKING_GUESTS_COUNT_CONSTRAINT: "Некорректное количество гостей",
    BOOKING_STATUS_CONSTRAINT: "Некорректный статус брони",
    BOOKING_PAYMENT_STATUS_CONSTRAINT: "Некорректный статус оплаты",
    BOOKING_PAYMENT_REQUIRED_CONSTRAINT: "Оплаченная бронь не может требовать оплату",
}


def normalize_booking_status(status: Optional[str], *, default: str = "pending") -> str:
    normalized = (status or default).strip().lower()
    return normalized or default


def normalize_payment_status(status: Optional[str], *, default: str = "unpaid", allow_none: bool = False) -> Optional[str]:
    if status is None and allow_none:
        return None
    normalized = (status or default).strip().lower()
    return normalized or default


def ensure_valid_date_range(check_in, check_out, *, detail: str = "Дата выезда должна быть позже даты заезда") -> None:
    if not check_in or not check_out or check_out <= check_in:
        raise HTTPException(status_code=400, detail=detail)


def ensure_positive_guest_count(guests_count, *, detail: str) -> int:
    try:
        guests_count = int(guests_count)
    except Exception:
        guests_count = 0
    if guests_count <= 0:
        raise HTTPException(status_code=400, detail=detail)
    return guests_count


def resolve_guests_count(guests_count, *, adults=0, kids=0, detail: str = "Укажите количество гостей") -> int:
    if guests_count is None:
        guests_count = int(adults or 0) + int(kids or 0)
    return ensure_positive_guest_count(guests_count, detail=detail)


def normalize_admin_booking_status(status: Optional[str]) -> str:
    normalized = normalize_booking_status(status, default="pending")
    if normalized not in ALLOWED_ADMIN_BOOKING_STATUSES:
        raise HTTPException(status_code=400, detail="Некорректный статус брони")
    return normalized


def normalize_admin_payment_status(status: Optional[str], *, allow_none: bool = False) -> Optional[str]:
    if status is None:
        return None if allow_none else "unpaid"
    normalized = str(status).strip().lower()
    if not normalized:
        if allow_none:
            raise HTTPException(status_code=400, detail="Некорректный статус оплаты")
        normalized = "unpaid"
    if normalized not in ALLOWED_PAYMENT_STATUSES:
        raise HTTPException(status_code=400, detail="Некорректный статус оплаты")
    return normalized


def coerce_payment_required(payment_status: Optional[str], payment_required: Optional[bool], *, default: Optional[bool] = None) -> Optional[bool]:
    normalized = normalize_payment_status(payment_status, default="", allow_none=True)
    if normalized in SETTLED_PAYMENT_STATUSES:
        return False
    if payment_required is None:
        return default
    return bool(payment_required)


def is_terminal_status(status: Optional[str]) -> bool:
    return normalize_booking_status(status, default="") in TERMINAL_BOOKING_STATUSES


def status_for_history(status: Optional[str], check_out, *, today: Optional[date] = None) -> str:
    today = today or date.today()
    normalized = normalize_booking_status(status, default="")
    if check_out is not None and check_out < today and normalized not in TERMINAL_BOOKING_STATUSES:
        return "completed"
    return normalized


def is_history_booking(status: Optional[str], check_out, *, today: Optional[date] = None) -> bool:
    return is_terminal_status(status_for_history(status, check_out, today=today))


def ensure_cancellable(status: Optional[str], *, detail: str = "Бронь уже завершена") -> None:
    if is_terminal_status(status):
        raise HTTPException(status_code=400, detail=detail)


def ensure_editable(
    status: Optional[str],
    payment_status: Optional[str],
    *,
    status_detail: str = "Нельзя редактировать завершённую бронь",
    payment_detail: str = "Нельзя редактировать оплаченную бронь",
) -> None:
    if is_terminal_status(status):
        raise HTTPException(status_code=400, detail=status_detail)
    if normalize_payment_status(payment_status, default="", allow_none=True) == "paid":
        raise HTTPException(status_code=400, detail=payment_detail)


def ensure_payable(status: Optional[str], payment_required: bool, payment_status: Optional[str]) -> None:
    if normalize_booking_status(status, default="") not in {"confirmed", "awaiting_payment"}:
        raise HTTPException(status_code=400, detail="Оплата доступна после подтверждения брони")
    if not bool(payment_required):
        raise HTTPException(status_code=400, detail="Оплата пока не запрошена администратором")
    if normalize_payment_status(payment_status, default="", allow_none=True) not in PAYABLE_PAYMENT_STATUSES:
        raise HTTPException(status_code=400, detail="Бронь уже оплачена или отмечена как наличная")


def rollup_order_status(statuses: Sequence[str]) -> str:
    sts = [normalize_booking_status(status, default="") for status in (statuses or [])]
    sts = [status for status in sts if status]
    if not sts:
        return "pending"

    if all(status in TERMINAL_BOOKING_STATUSES for status in sts):
        if any(status == "completed" for status in sts):
            return "completed"
        if any(status == "no_show" for status in sts):
            return "no_show"
        if any(status == "rejected" for status in sts):
            return "rejected"
        if any(status == "cancelled_by_user" for status in sts):
            return "cancelled_by_user"
        if any(status == "cancelled_by_base" for status in sts):
            return "cancelled_by_base"
        if any(status == "expired_pending" for status in sts):
            return "expired_pending"
        return "cancelled"

    if any(status in ("pending", "new", "") for status in sts):
        return "pending"
    if any(status == "awaiting_confirmation" for status in sts):
        return "awaiting_confirmation"
    if any(status == "awaiting_payment" for status in sts):
        return "awaiting_payment"
    if any(status == "checked_in" for status in sts):
        return "checked_in"
    if any(status == "confirmed" for status in sts):
        return "confirmed"
    return sts[0] or "pending"


def rollup_order_payment_status(statuses: Sequence[str]) -> str:
    sts = [normalize_payment_status(status, default="", allow_none=True) or "" for status in (statuses or [])]
    sts = [status for status in sts if status]
    if not sts:
        return "unpaid"
    if any(status == "failed" for status in sts):
        return "failed"
    if any(status == "unpaid" for status in sts):
        return "unpaid"
    if any(status == "awaiting_prepayment" for status in sts):
        return "awaiting_prepayment"
    if any(status == "partially_paid" for status in sts):
        return "partially_paid"
    if any(status == "cash" for status in sts):
        return "cash"
    if any(status == "awaiting_refund" for status in sts):
        return "awaiting_refund"
    if any(status == "refund_partial" for status in sts):
        return "refund_partial"
    if any(status == "refund_full" for status in sts):
        return "refund_full"
    if any(status == "chargeback" for status in sts):
        return "chargeback"
    if any(status == "overpaid" for status in sts):
        return "overpaid"
    if all(status == "paid" for status in sts):
        return "paid"
    return sts[0] or "unpaid"
