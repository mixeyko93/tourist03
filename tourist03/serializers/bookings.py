from typing import Iterable, List

from tourist03.domain import bookings as booking_domain
from tourist03.dto.bookings import AdminBookingDTO, BookingPublicDTO, OrderDTO, OrderItemDTO


def serialize_booking(row: dict) -> BookingPublicDTO:
    return {
        "id": row.get("id"),
        "camp_id": row.get("camp_id"),
        "camp_name": row.get("camp_name") or "",
        "room_id": row.get("room_id"),
        "room_name": row.get("room_name") or "",
        "check_in": row.get("check_in"),
        "check_out": row.get("check_out"),
        "guests_count": row.get("guests_count"),
        "status": row.get("status") or "",
        "payment_required": bool(row.get("payment_required")),
        "payment_status": row.get("payment_status") or "unpaid",
        "comment": row.get("comment") or "",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def serialize_booking_list(rows: Iterable[dict]) -> List[BookingPublicDTO]:
    return [serialize_booking(row) for row in rows]


def serialize_order_item(row: dict) -> OrderItemDTO:
    return {
        "booking_id": row.get("id"),
        "room_id": row.get("room_id"),
        "room_name": row.get("room_name") or "",
        "check_in": row.get("check_in"),
        "check_out": row.get("check_out"),
        "guests_count": row.get("guests_count"),
        "status": row.get("status") or "",
        "payment_required": bool(row.get("payment_required")),
        "payment_status": row.get("payment_status") or "unpaid",
        "comment": row.get("comment") or "",
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def serialize_order(order_id: str, rows: List[dict]) -> OrderDTO:
    first = rows[0] if rows else {}
    guests_total = 0
    items = []
    for row in rows:
        try:
            guests_total += int(row.get("guests_count") or 0)
        except Exception:
            pass
        items.append(serialize_order_item(row))

    created_at = None
    updated_at = None
    for row in rows:
        created = row.get("created_at")
        updated = row.get("updated_at")
        if created and (created_at is None or created < created_at):
            created_at = created
        if updated and (updated_at is None or updated > updated_at):
            updated_at = updated

    return {
        "order_id": order_id,
        "camp_id": first.get("camp_id"),
        "camp_name": first.get("camp_name") or "",
        "check_in": first.get("check_in"),
        "check_out": first.get("check_out"),
        "guests_count": guests_total,
        "status": booking_domain.rollup_order_status([row.get("status") for row in rows]),
        "payment_required": any(bool(row.get("payment_required")) for row in rows),
        "payment_status": booking_domain.rollup_order_payment_status([row.get("payment_status") for row in rows]),
        "comment": next((comment for comment in (str(row.get("comment") or "").strip() for row in rows) if comment), ""),
        "created_at": created_at,
        "updated_at": updated_at,
        "items": items,
    }


def serialize_admin_booking(row: dict) -> AdminBookingDTO:
    return {
        "id": row.get("id"),
        "camp_id": row.get("camp_id"),
        "camp_name": row.get("camp_name"),
        "room_id": row.get("room_id"),
        "room_name": row.get("room_name"),
        "check_in": row.get("check_in"),
        "check_out": row.get("check_out"),
        "guests_count": row.get("guests_count"),
        "status": row.get("status"),
        "source": row.get("source"),
        "payment_status": row.get("payment_status"),
        "payment_required": row.get("payment_required"),
        "user_id": row.get("user_id"),
        "user_name": row.get("user_name"),
        "user_phone": row.get("user_phone"),
        "user_email": row.get("user_email"),
        "guest_name": row.get("guest_name"),
        "guest_phone": row.get("guest_phone"),
        "guest_email": row.get("guest_email"),
        "comment": row.get("comment"),
    }


def serialize_admin_booking_list(rows: Iterable[dict]) -> List[AdminBookingDTO]:
    return [serialize_admin_booking(row) for row in rows]
